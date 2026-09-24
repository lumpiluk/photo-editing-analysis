import pathlib

import dash
import dash_ag_grid as dag
import dash_bootstrap_components as dbc
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback, Input, Output, State

from photography_analysis.dashboard.config import settings

dash.register_page(__name__, path="/people")


def load_people():
    ranges_path = pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv"
    photos_path = pathlib.Path(settings.data_cache_dir) / "person-photo-dates.csv"

    if not ranges_path.exists():
        return pd.DataFrame(columns=["id", "name", "num_assets", "last", "num_days"])

    df = pd.read_csv(ranges_path)
    df["last"] = pd.to_datetime(df["last"], format="ISO8601").dt.strftime("%Y-%m-%d")

    photos = pd.read_csv(photos_path)
    photos["date"] = pd.to_datetime(photos["date"], format="ISO8601").dt.normalize()
    num_days = (
        photos.groupby("person_id")["date"]
        .nunique()
        .rename("num_days")
        .reset_index()
        .rename(columns={"person_id": "id"})
    )

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
    dcc.Graph(id="num-days-ecdf", figure=build_num_days_ecdf(load_people())),

    html.H2("Distribution of photo counts"),
    dcc.Graph(id="num-assets-ecdf", figure=build_num_assets_ecdf(load_people())),
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
    Output("num-days-ecdf", "figure"),
    Input("global-data-version", "data"),
)
def update_num_days_ecdf(_version):
    return build_num_days_ecdf(load_people())


@callback(
    Output("num-assets-ecdf", "figure"),
    Input("global-data-version", "data"),
)
def update_num_assets_ecdf(_version):
    return build_num_assets_ecdf(load_people())


@callback(
    Output("people-grid", "rowData"),
    Input("global-data-version", "data"),
)
def update_people_grid(_version):
    return load_people().to_dict("records")
