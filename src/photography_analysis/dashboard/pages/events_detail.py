from datetime import datetime
import pathlib
from urllib.parse import parse_qs, unquote

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback, Input, Output
import dash_ag_grid as dag
import dash_bootstrap_components as dbc

from photography_analysis import data
from photography_analysis.dashboard.config import settings

dash.register_page(__name__, path="/events-detail")

RAW_GLOB = "*.CR3"
EDITED_GLOB = "converted*/*.jpg"

layout = html.Div(dbc.Container([
    dcc.Location(id="events-detail-url"),
    html.Div(id="events-detail-content"),
]))


def resolve_event_dir(path_str: str) -> pathlib.Path:
    return pathlib.Path(settings.photos_dir) / path_str


def gather_files(event_dirs, glob_pattern):
    return [
        f
        for d in event_dirs
        for f in d.glob(glob_pattern, case_sensitive=False)
    ]


# --- Immich-based people table / ECDFs (unchanged from before) ---

def load_ranges():
    df = pd.read_csv(pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv")
    df["last"] = pd.to_datetime(df["last"], format="ISO8601")
    return df


def load_photos():
    df = pd.read_csv(pathlib.Path(settings.data_cache_dir) / "person-photo-dates.csv")
    df["date"] = pd.to_datetime(df["date"], format="ISO8601").dt.normalize()
    return df


def build_people_table(photos, event_dates, name_by_id):
    at_event = photos[photos["date"].isin(event_dates)]
    counts = at_event.groupby("person_id").size().rename("n_photos")

    rows = []
    for pid, n in counts.items():
        prior = photos[(photos["person_id"] == pid) & (photos["date"] < event_dates.min())]
        gap = (event_dates.min() - prior["date"].max()).days if not prior.empty else None
        rows.append({
            "name": name_by_id.get(pid) or pid,
            "n_photos": int(n),
            "days_since_last": gap,
        })

    return html.Div(
        dag.AgGrid(
            columnDefs=[
                {"field": "name", "headerName": "Name", "flex": 1, "sortable": True},
                {"field": "n_photos", "headerName": "Photos at event", "width": 160, "sortable": True, "sort": "desc"},
                {"field": "days_since_last", "headerName": "Days since last event", "width": 180, "sortable": True},
            ],
            rowData=rows,
            columnSize="sizeToFit",
            style={"height": "100%", "width": "100%"},
        ),
        style={"resize": "both", "overflow": "auto", "height": "400px", "width": "100%"},
    )


def build_people_count_ecdf(photos, event_dates):
    counts = photos[photos["date"].isin(event_dates)].groupby("person_id").size().values
    if len(counts) == 0:
        return go.Figure()
    x = np.sort(counts)
    y = np.arange(1, len(x) + 1) / len(x)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines"))
    fig.update_layout(xaxis_title="Photos per person at this event", yaxis_title="Fraction of people ≤ x")
    return fig


def build_gap_ecdf(photos, event_dates):
    at_event_people = photos[photos["date"].isin(event_dates)]["person_id"].unique()
    gaps = []
    for pid in at_event_people:
        prior = photos[(photos["person_id"] == pid) & (photos["date"] < event_dates.min())]
        if not prior.empty:
            gaps.append((event_dates.min() - prior["date"].max()).days)
    if not gaps:
        return go.Figure()
    x = np.sort(gaps)
    y = np.arange(1, len(x) + 1) / len(x)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines"))
    fig.update_layout(xaxis_title="Days since person's last event", yaxis_title="Fraction of people ≤ x")
    return fig


# --- raw-vs-edited: mtimes based, fast, no caching needed ---

def ecdf_trace(values, name):
    x = np.sort(values)
    y = np.arange(1, len(x) + 1) / len(x)
    return go.Scatter(x=x, y=y, mode="lines", name=name)


def build_delta_ecdf(raw_mtimes, edited_mtimes):
    fig = go.Figure()
    for mtimes, label in [(raw_mtimes, "Raw"), (edited_mtimes, "Edited")]:
        mtimes = sorted(mtimes)
        if len(mtimes) < 2:
            continue
        gaps = np.diff(mtimes)  # seconds, matching time_between_photos.py
        fig.add_trace(ecdf_trace(gaps, label))
    fig.update_layout(
        xaxis_title="Time between photos (seconds)",
        yaxis_title="Fraction of gaps ≤ x",
        xaxis=dict(range=[0, 300]),  # matches CLI's ax.set_xlim(0, 300)
    )
    return fig


def build_sessions_ecdf(raw_mtimes, edited_mtimes):
    fig = go.Figure()
    for mtimes, label in [(raw_mtimes, "Raw"), (edited_mtimes, "Edited")]:
        if len(mtimes) < 2:
            continue
        durations = list(data.get_sessions_from_time_series(
            timestamps_sec=sorted(mtimes),
            min_break_between_sessions_sec=60 * 30,
        ))
        if not durations:
            continue
        fig.add_trace(ecdf_trace(np.array(durations) / 60, label))
    fig.update_layout(
        xaxis_title="Session duration (minutes)",
        yaxis_title="Fraction of sessions ≤ x",
    )
    return fig


# --- shared metadata fetch: one exiftool call per raw/edited, reused by all plots below ---

def parse_capture_hour(val):
    if not isinstance(val, str):
        return None
    try:
        dt = datetime.strptime(val.replace(":", "-", 2), "%Y-%m-%d %H:%M:%S")
        return dt.hour
    except ValueError:
        return None  # e.g. malformed dates like '1900:01:00 00:00:00'


def get_metadata_locked(files, cache_file, write_cache=True):
    if cache_file and cache_file.exists():
        return data.get_metadata(files=files, cache_file=cache_file, write_cache=write_cache)

    lock_file = cache_file.with_suffix(cache_file.suffix + ".lock")
    if lock_file.exists():
        raise RuntimeError(f"Metadata parsing already in progress for {cache_file}")

    lock_file.touch()
    try:
        return data.get_metadata(files=files, cache_file=cache_file, write_cache=write_cache)
    finally:
        lock_file.unlink(missing_ok=True)


def fetch_all_metadata(event_dirs):
    raw_files = gather_files(event_dirs, RAW_GLOB)
    edited_files = gather_files(event_dirs, EDITED_GLOB)

    # single cache file per event dir, shared across all metadata-based plots
    raw_meta = []
    edited_meta = []
    for d in event_dirs:
        raw_meta += get_metadata_locked(
            files=list(d.glob(RAW_GLOB, case_sensitive=False)),
            cache_file=d / "metadata_raw.json",
        )
        edited_meta += get_metadata_locked(
            files=list(d.glob(EDITED_GLOB, case_sensitive=False)),
            cache_file=d / "metadata_edited.json",
        )
    return raw_meta, edited_meta


def build_metadata_ecdf(raw_meta, edited_meta, tag, xlabel, log_scale=False,
                         tickvals=None, ticktext=None):
    fig = go.Figure()
    for meta, label in [(raw_meta, "Raw"), (edited_meta, "Edited")]:
        values = [m[tag] for m in meta if tag in m]
        if values:
            fig.add_trace(ecdf_trace(values, label))

    fig.update_layout(xaxis_title=xlabel, yaxis_title="Fraction of photos ≤ x")
    if log_scale:
        fig.update_xaxes(type="log")
    if tickvals:
        fig.update_xaxes(tickmode="array", tickvals=tickvals, ticktext=ticktext or [str(t) for t in tickvals])
    return fig


def metadata_cache_exists(event_dirs) -> bool:
    return all(
        (d / "metadata_raw.json").exists() and (d / "metadata_edited.json").exists()
        for d in event_dirs
    )


def build_hour_of_day_histogram(raw_meta, edited_meta):
    fig = go.Figure()
    for meta, label in [(raw_meta, "Raw"), (edited_meta, "Edited")]:
        hours = [
            h for h in (
                parse_capture_hour(m.get("EXIF:DateTimeOriginal"))
                for m in meta
            ) if h is not None
        ]
        if hours:
            fig.add_trace(go.Histogram(x=hours, name=label, opacity=0.6,
                                        xbins=dict(start=-0.5, end=23.5, size=1)))
    fig.update_layout(barmode="overlay", xaxis_title="Hour of day",
                       yaxis_title="Number of photos", xaxis=dict(tick0=0, dtick=2))
    return fig


# --- assemble all metadata-based figures from one fetch ---

def build_all_metadata_figures(event_dirs):
    raw_meta, edited_meta = fetch_all_metadata(event_dirs)

    return {
        "hour_of_day": build_hour_of_day_histogram(raw_meta, edited_meta),
        "focal_lengths": build_metadata_ecdf(
            raw_meta, edited_meta, "EXIF:FocalLength", "Focal length (mm)",
        ),
        "exposure_times": build_metadata_ecdf(
            raw_meta, edited_meta, "EXIF:ExposureTime", "Exposure time (s)", log_scale=True,
        ),
        "apertures": build_metadata_ecdf(
            raw_meta, edited_meta, "EXIF:FNumber", "Aperture", log_scale=True,
            tickvals=[1 * 2 ** i for i in range(5)],
            ticktext=[f"1/{v:g}" for v in [1 * 2 ** i for i in range(5)]],
        ),
        "isos": build_metadata_ecdf(
            raw_meta, edited_meta, "EXIF:ISO", "ISO", log_scale=True,
            tickvals=[100 * 2 ** i for i in range(0, 9, 2)],
        ),
        "light_values": build_metadata_ecdf(
            raw_meta, edited_meta, "Composite:LightValue", "Light Value (EV @ ISO 100)",
        ),
    }


# --- page ---

@callback(
    Output("events-detail-content", "children"),
    Input("events-detail-url", "search"),
    Input("global-data-version", "data"),
)
def render_events_detail(search, _version):
    if not search:
        return html.Div("No events selected.")

    params = parse_qs(search.lstrip("?"))
    paths = [unquote(p) for p in params.get("paths", [""])[0].split(",") if p]
    if not paths:
        return html.Div("No events selected.")

    event_dirs = [resolve_event_dir(p) for p in paths]
    event_dates_raw = [pathlib.Path(p).name.split("_")[0] for p in paths]
    event_dates = pd.to_datetime(event_dates_raw).tz_localize("UTC")

    ranges = load_ranges()
    photos = load_photos()
    name_by_id = ranges.set_index("id")["name"].to_dict()

    raw_mtimes = list(data.collect_file_stats(gather_files(event_dirs, RAW_GLOB)))
    edited_mtimes = list(data.collect_file_stats(gather_files(event_dirs, EDITED_GLOB)))

    cache_ready = metadata_cache_exists(event_dirs)

    return html.Div([
        html.H1("Event details"),
        html.P(f"Selected events: {', '.join(pathlib.Path(p).name for p in paths)}"),

        html.H2("People at this event"),
        build_people_table(photos, event_dates, name_by_id),

        html.H2("Photos per person (ECDF)"),
        dcc.Graph(figure=build_people_count_ecdf(photos, event_dates)),

        html.H2("Days since last event, per person (ECDF)"),
        dcc.Graph(figure=build_gap_ecdf(photos, event_dates)),

        html.H2("Time between photos: raw vs. edited"),
        dcc.Graph(figure=build_delta_ecdf(raw_mtimes, edited_mtimes)),

        html.H2("Session durations: raw vs. edited"),
        dcc.Graph(figure=build_sessions_ecdf(raw_mtimes, edited_mtimes)),

        html.P(
            "Metadata cache not found — reading EXIF data may take a few "
            "minutes on first load." if not cache_ready else "",
            style={"color": "orange"},
        ),

        html.H2("Photo capture hour of day"),
        dcc.Loading(type="circle", children=dcc.Graph(id="hour-of-day-graph")),

        html.H2("Focal lengths"),
        dcc.Loading(type="circle", children=dcc.Graph(id="focal-lengths-graph")),

        html.H2("Exposure times"),
        dcc.Loading(type="circle", children=dcc.Graph(id="exposure-times-graph")),

        html.H2("Apertures"),
        dcc.Loading(type="circle", children=dcc.Graph(id="apertures-graph")),

        html.H2("ISOs"),
        dcc.Loading(type="circle", children=dcc.Graph(id="isos-graph")),

        html.H2("Light values"),
        dcc.Loading(type="circle", children=dcc.Graph(id="light-values-graph")),
    ])


@callback(
    Output("hour-of-day-graph", "figure"),
    Output("focal-lengths-graph", "figure"),
    Output("exposure-times-graph", "figure"),
    Output("apertures-graph", "figure"),
    Output("isos-graph", "figure"),
    Output("light-values-graph", "figure"),
    Input("events-detail-url", "search"),
    Input("global-data-version", "data"),
    background=True,
)
def render_metadata_plots(search, _version):
    params = parse_qs((search or "").lstrip("?"))
    paths = [unquote(p) for p in params.get("paths", [""])[0].split(",") if p]
    event_dirs = [resolve_event_dir(p) for p in paths]

    figs = build_all_metadata_figures(event_dirs)
    return (
        figs["hour_of_day"],
        figs["focal_lengths"],
        figs["exposure_times"],
        figs["apertures"],
        figs["isos"],
        figs["light_values"],
    )
