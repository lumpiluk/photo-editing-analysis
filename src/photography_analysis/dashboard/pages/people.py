import pathlib

import dash
import dash_ag_grid as dag
import pandas as pd
from dash import html, dcc, callback, Input, Output, State

from photography_analysis.dashboard.config import settings

dash.register_page(__name__, path="/people")


def load_people():
    path = pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv"
    if not path.exists():
        return pd.DataFrame(columns=["id", "name", "num_assets"])
    df = pd.read_csv(path)
    df["last"] = pd.to_datetime(df["last"], format="ISO8601").dt.strftime("%Y-%m-%d")
    return df[["id", "name", "num_assets", "last"]]


layout = html.Div([
    html.H1("People"),

    dcc.Input(
        id="people-search",
        type="text",
        placeholder="Search people...",
        style={"marginBottom": "10px", "width": "300px"},
    ),

    dag.AgGrid(
        id="people-grid",
        columnDefs=[
            {"headerName": "", "checkboxSelection": True, "width": 50},
            {"field": "name", "headerName": "Name", "flex": 1},
            {"field": "num_assets", "headerName": "Photos", "width": 120},
            {"field": "last", "headerName": "Most recent photo", "width": 160, "sort": "desc"},
            # once thumbnails are available:
            # {"field": "thumbnail", "headerName": "", "cellRenderer": "ImageRenderer", "width": 80},
        ],
        rowData=load_people().to_dict("records"),
        dashGridOptions={
            "rowSelection": "multiple",
            "suppressRowClickSelection": False,
            "pagination": False,
            # "paginationPageSize": 1000,
        },
        columnSize="sizeToFit",
        style={"height": "600px"},
    ),

    html.Button("View people", id="view-people-btn", style={"marginTop": "10px"}),
])


@callback(
    Output("people-grid", "dashGridOptions"),
    Input("people-search", "value"),
    State("people-grid", "dashGridOptions"),
)
def filter_people(search_value, current_options):
    current_options = dict(current_options or {})
    current_options["quickFilterText"] = search_value or ""
    return current_options


@callback(
    Output("_pages_location", "pathname"),
    Output("_pages_location", "search"),
    Input("view-people-btn", "n_clicks"),
    State("people-grid", "selectedRows"),
    prevent_initial_call=True,
)
def go_to_detail(n_clicks, selected_rows):
    if not selected_rows:
        return dash.no_update, dash.no_update

    ids = ",".join(str(row["id"]) for row in selected_rows)
    return "/people-detail", f"?ids={ids}"


# TODO
# - refresh peoples names (and thumbnails)
# - select subset of people
# - link from person name to person page
