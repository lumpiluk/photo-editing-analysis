import re
import pathlib
from urllib.parse import quote, unquote

import dash
import dash_ag_grid as dag
import pandas as pd
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from photography_analysis.dashboard.config import settings
from photography_analysis.dashboard.data_fetcher import (
    load_asset_people,
)

dash.register_page(__name__, path="/events")

DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)$")
YEAR_DIR_RE = re.compile(r"^\d{4}$")


def _build_record(project_dir: pathlib.Path, photos_dir: pathlib.Path, match: re.Match):
    date_str, title = match.group(1), match.group(2)
    return {
        "path": project_dir.relative_to(photos_dir).as_posix(),
        "name": title.replace("-", " "),
        "date": date_str,
    }


def discover_events(photos_dir: pathlib.Path) -> pd.DataFrame:
    photos_dir = pathlib.Path(photos_dir)
    records = []

    if not photos_dir.exists():
        return pd.DataFrame(columns=["path", "name", "date"])

    for entry in sorted(photos_dir.iterdir()):
        if not entry.is_dir():
            continue

        m = DATE_PREFIX_RE.match(entry.name)
        if m:
            records.append(_build_record(entry, photos_dir, m))
            continue

        if YEAR_DIR_RE.match(entry.name):
            for sub in sorted(entry.iterdir()):
                if not sub.is_dir():
                    continue
                m2 = DATE_PREFIX_RE.match(sub.name)
                if m2:
                    records.append(_build_record(sub, photos_dir, m2))

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values("date", ascending=False).reset_index(drop=True)
    return df


layout = html.Div(dbc.Container([
    html.H1("Events"),

    dcc.Input(
        id="events-search",
        type="text",
        placeholder="Search events...",
        style={"marginBottom": "10px", "width": "300px"},
    ),
    html.Button(
        "Refresh folder list",
        id="events-refresh-btn",
        style={"marginBottom": "10px", "marginLeft": "10px"},
    ),

    html.Div(
        dag.AgGrid(
            id="events-grid",
            columnDefs=[
                {"headerName": "", "checkboxSelection": True, "width": 50},
                {"field": "date", "headerName": "Date", "width": 130, "sort": "desc"},
                {"field": "name", "headerName": "Project", "flex": 1},
                {"field": "path", "headerName": "Folder", "flex": 1},
            ],
            rowData=[],  # filled in update_events_grid
            dashGridOptions={
                "rowSelection": "multiple",
                "pagination": False,
                # "paginationPageSize": 25,
            },
            columnSize="sizeToFit",
            style={"height": "100%", "width": "100%"},
        ),
        style={"resize": "both", "overflow": "auto", "height": "400px", "width": "100%"},
    ),

    html.Button("View events", id="view-events-btn", style={"marginTop": "10px"}),

    html.H2("Hour of day"),
    dcc.Graph(id="hour-of-day-histogram"),

    html.H2("Day of week"),
    dcc.Graph(id="day-of-week-histogram"),

    html.H2("Month of year"),
    dcc.Graph(id="month-of-year-histogram"),
]))


@callback(
    Output("events-grid", "rowData"),
    Input("events-refresh-btn", "n_clicks"),
)
def update_events_grid(n_clicks):
    return discover_events(settings.photos_dir).to_dict("records")


@callback(
    Output("events-grid", "dashGridOptions"),
    Input("events-search", "value"),
    State("events-grid", "dashGridOptions"),
)
def filter_events(search_value, current_options):
    current_options = dict(current_options or {})
    current_options["quickFilterText"] = search_value or ""
    return current_options


@callback(
    Output("_pages_location", "pathname", allow_duplicate=True),
    Output("_pages_location", "search", allow_duplicate=True),
    Input("view-events-btn", "n_clicks"),
    State("events-grid", "selectedRows"),
    prevent_initial_call=True,
)
def go_to_project_detail(n_clicks, selected_rows):
    if not selected_rows:
        return dash.no_update, dash.no_update

    paths = ",".join(quote(row["path"], safe="") for row in selected_rows)
    return "/events-detail", f"?paths={paths}"


def build_seasonality_histogram(dates: pd.Series, extractor, xaxis_title, xbins, tick_labels=None):
    values = extractor(dates)
    fig = go.Figure(go.Histogram(x=values, xbins=xbins))
    fig.update_layout(xaxis_title=xaxis_title, yaxis_title="Number of photos")
    if tick_labels:
        fig.update_xaxes(tickmode="array", tickvals=list(range(len(tick_labels))), ticktext=tick_labels)
    return fig


def build_hour_of_day_histogram(dates: pd.Series):
    fig = build_seasonality_histogram(
        dates, extractor=lambda d: d.dt.hour,
        xaxis_title="Hour of day (24h)",
        xbins=dict(start=-0.5, end=23.5, size=1),
    )
    fig.update_xaxes(tick0=0, dtick=2)
    return fig


def build_day_of_week_histogram(dates: pd.Series):
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return build_seasonality_histogram(
        dates, extractor=lambda d: d.dt.dayofweek,
        xaxis_title="Day of week",
        xbins=dict(start=-0.5, end=6.5, size=1),
        tick_labels=day_names,
    )


def build_month_of_year_histogram(dates: pd.Series):
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    return build_seasonality_histogram(
        dates, extractor=lambda d: d.dt.month - 1,
        xaxis_title="Month",
        xbins=dict(start=-0.5, end=11.5, size=1),
        tick_labels=month_names,
    )


@callback(
    Output("hour-of-day-histogram", "figure"),
    Output("day-of-week-histogram", "figure"),
    Output("month-of-year-histogram", "figure"),
    Input("global-data-version", "data"),
)
def update_seasonality_histograms(_version):
    asset_people = load_asset_people()
    dates = pd.to_datetime(
        pd.Series([r["date"] for r in asset_people]), format="ISO8601"
    )
    return (
        build_hour_of_day_histogram(dates),
        build_day_of_week_histogram(dates),
        build_month_of_year_histogram(dates),
    )
