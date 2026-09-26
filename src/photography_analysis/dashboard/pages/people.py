import pathlib

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback, Input, Output, State

from photography_analysis.dashboard.config import settings
from photography_analysis.dashboard.data_fetcher import (
    load_asset_people,
    load_photos,
    load_ranges,
)
from photography_analysis.pseudonyms import pseudonym_for_id
from photography_analysis.plots.people_per_photo import (
    build_people_per_photo_ecdf_plotly,
)

dash.register_page(__name__, path="/people")


def get_num_days_by_id(photos: pd.DataFrame) -> pd.DataFrame:
    photos = photos.copy()
    photos["date"] = pd.to_datetime(photos["date"], format="ISO8601").dt.normalize()
    return (
        photos.groupby("person_id")["date"]
        .nunique()
        .rename("num_days")
        .reset_index()
        .rename(columns={"person_id": "id"})
    )


def load_people(demo_mode: bool):
    ranges_path = pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv"
    photos_path = pathlib.Path(settings.data_cache_dir) / "person-photo-dates.csv"

    if not ranges_path.exists():
        return pd.DataFrame(columns=["id", "name", "num_assets", "last", "num_days"])

    df = pd.read_csv(ranges_path)
    df["last"] = pd.to_datetime(df["last"], format="ISO8601").dt.strftime("%Y-%m-%d")

    if demo_mode:
        df["name"] = df["id"].apply(pseudonym_for_id)

    photos = pd.read_csv(photos_path)
    num_days = get_num_days_by_id(photos)

    df = df.merge(num_days, on="id", how="left")
    df["num_days"] = df["num_days"].fillna(0).astype(int)

    return df[["id", "name", "num_assets", "last", "num_days"]]


def build_num_days_ecdf(people_df):
    values = np.sort(people_df["num_days"].values)
    y = np.arange(1, len(values) + 1) / len(values)

    fig = go.Figure(go.Scatter(x=values, y=y, mode="lines"))
    fig.update_layout(
        xaxis_title="Days photographed",
        yaxis_title="Fraction of people ≤ x",
        height=350,
    )
    return fig


def build_num_assets_ecdf(people_df):
    values = np.sort(people_df["num_assets"].values)
    y = np.arange(1, len(values) + 1) / len(values)

    fig = go.Figure(go.Scatter(x=values, y=y, mode="lines"))
    fig.update_layout(
        xaxis_title="Number of photos",
        yaxis_title="Fraction of people ≤ x",
        height=350,
    )
    return fig


def build_retention_curve(photos):
    photos = photos.copy()
    photos["year"] = photos["date"].dt.year

    person_years = photos.groupby("person_id")["year"].apply(set)
    first_year = person_years.apply(min)
    max_year = photos["year"].max()

    max_offset = int(max_year - first_year.min())
    offsets = range(0, max_offset + 1)

    retention = []
    for k in offsets:
        # only include cohorts old enough that year (first_year + k) could have happened
        eligible = first_year[first_year + k <= max_year]
        if eligible.empty:
            continue
        still_present = sum(
            (first_year[pid] + k) in person_years[pid]
            for pid in eligible.index
        )
        retention.append({"years_since_first": k, "fraction_retained": still_present / len(eligible)})

    df = pd.DataFrame(retention)
    fig = go.Figure(go.Scatter(x=df["years_since_first"], y=df["fraction_retained"], mode="lines+markers"))
    fig.update_layout(
        xaxis_title="Years since first photographed",
        yaxis_title="Fraction of that cohort still photographed",
        yaxis=dict(range=[0, 1]),
    )
    return fig


def build_timespan_vs_days_photographed_scatter(ranges, num_days_by_id, name_by_id):
    span_days = (
        ranges["last"] - pd.to_datetime(ranges["first"], format="ISO8601")
    ).dt.days

    fig = go.Figure(go.Scatter(
        x=span_days,
        y=ranges["id"].map(num_days_by_id),
        mode="markers",
        marker=dict(
            size=6,
            color=ranges["num_assets"],
            colorscale="Viridis",
            colorbar=dict(title="Photos"),
            cmin=1,
            showscale=True,
        ),
        text=ranges["name"],
        customdata=ranges["num_assets"],
        hovertemplate=
            "%{text}<br>Span: %{x} days<br>"
            "Photos: %{customdata}<br>"
            "Days photographed: %{y}<extra></extra>",
    ))
    fig.update_layout(
        xaxis_title="Days between first and last photo",
        yaxis_title="Distinct days photographed",
    )
    return fig


layout = html.Div(dbc.Container([
    html.H1("People"),
    html.Nav([
        dcc.Link("Photos per Month Heatmap (slow)", href="/people-heatmap"),
        dcc.Link("People Network (slow)", href="/people-network"),
    ], style={"display": "flex", "gap": "1rem"}),

    html.Div(
        dag.AgGrid(
            id="people-grid",
            columnDefs=[
                {
                    "headerName": "#",
                    "valueGetter": {"function": "params.node.rowIndex + 1"},
                    "width": 50,
                    # "columnSizing": "autoSize",
                    "sortable": False,
                    "pinned": "left",
                    "flex": 0,
                },
                {"headerName": "", "checkboxSelection": True, "width": 50},
                {
                    "headerName": "",
                    "cellRenderer": "PersonLinksRenderer",
                    "width": 70,
                    "sortable": False,
                    "filter": False,
                },
                {
                    "field": "name",
                    "headerName": "Name",
                    "flex": 1,
                    "filter": True,
                },
                {
                    "field": "last",
                    "headerName": "Most recent photo",
                    "width": 160,
                    "sort": "desc",
                    "filter": True,
                },
                {
                    "field": "num_assets",
                    "headerName": "Photos",
                    "width": 120,
                    "filter": True,
                },
                {
                    "field": "num_days",
                    "headerName": "Days photographed",
                    "width": 150,
                    "filter": True,
                },
                # once thumbnails are available:
                # {"field": "thumbnail", "headerName": "", "cellRenderer": "ImageRenderer", "width": 80},
            ],
            rowData=[],  # start empty; filled in by callback below
            dashGridOptions={
                "context": {"immichHost": settings.immich_host},
                "rowSelection": "multiple",
                "suppressRowClickSelection": False,
                "pagination": False,
                # "paginationPageSize": 1000,
            },
            columnSize="sizeToFit",
            style={"height": "100%", "width": "100%"},
        ),
        style={"resize": "both", "overflow": "auto", "height": "400px", "width": "100%"},
    ),

    html.Button("View people", id="view-people-btn", style={"marginTop": "10px"}),

    html.H2("Distribution of days photographed"),
    dcc.Graph(id="num-days-ecdf"),  # , figure=build_num_days_ecdf(load_people())),

    html.H2("Distribution of photo counts"),
    dcc.Graph(id="num-assets-ecdf"),  # , figure=build_num_assets_ecdf(load_people())),

    html.H2("Known people per photo"),
    dcc.Graph(id="people-per-photo-ecdf"),

    html.H2("Retention"),
    dcc.Graph(id="retention-curve"),

    html.H2("Timespan vs. days photographed"),
    dcc.Graph(id="timespan-vs-days-scatter"),
]))


@callback(
    Output("_pages_location", "pathname", allow_duplicate=True),
    Output("_pages_location", "search", allow_duplicate=True),
    Input("view-people-btn", "n_clicks"),
    State("people-grid", "selectedRows"),
    prevent_initial_call=True,
)
def go_to_detail(n_clicks, selected_rows):
    if not selected_rows:
        return dash.no_update, dash.no_update

    ids = ",".join(str(row["id"]) for row in selected_rows)
    return "/people-detail", f"?ids={ids}"


@callback(
    Output("people-per-photo-ecdf", "figure"),
    Input("global-data-version", "data"),
)
def update_people_per_photo_ecdf(_version):
    return build_people_per_photo_ecdf_plotly(load_asset_people())


@callback(
    Output("retention-curve", "figure"),
    Input("global-data-version", "data"),
    Input("demo-mode", "data"),
)
def update_retention_curve(_version, demo_mode: bool):
    return build_retention_curve(load_photos(demo_mode=demo_mode))


@callback(
    Output("timespan-vs-days-scatter", "figure"),
    Input("global-data-version", "data"),
    Input("demo-mode", "data"),
)
def update_timespan_vs_days_photographed_scatter(_version, demo_mode: bool):
    ranges = load_ranges(demo_mode=demo_mode)
    name_by_id = ranges.set_index("id")["name"].to_dict()

    num_days_df = get_num_days_by_id(load_photos(demo_mode=demo_mode))
    num_days_by_id = num_days_df.set_index("id")["num_days"].to_dict()

    return build_timespan_vs_days_photographed_scatter(
        ranges=load_ranges(demo_mode=demo_mode),
        num_days_by_id=num_days_by_id,
        name_by_id=name_by_id,
    )


@callback(
    Output("num-days-ecdf", "figure"),
    Input("global-data-version", "data"),
    Input("demo-mode", "data"),
)
def update_num_days_ecdf(_version, demo_mode):
    return build_num_days_ecdf(load_people(demo_mode=demo_mode))


@callback(
    Output("num-assets-ecdf", "figure"),
    Input("global-data-version", "data"),
    Input("demo-mode", "data"),
)
def update_num_assets_ecdf(_version, demo_mode):
    return build_num_assets_ecdf(load_people(demo_mode=demo_mode))


@callback(
    Output("people-grid", "rowData"),
    Input("global-data-version", "data"),
    Input("demo-mode", "data"),
)
def update_people_grid(_version, demo_mode):
    return load_people(demo_mode=demo_mode).to_dict("records")
