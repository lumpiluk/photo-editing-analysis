import re
import pathlib
from urllib.parse import quote, unquote

import dash
import dash_ag_grid as dag
import pandas as pd
from dash import html, dcc, callback, Input, Output, State
import dash_bootstrap_components as dbc

from photography_analysis.dashboard.config import settings

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

    dag.AgGrid(
        id="events-grid",
        columnDefs=[
            {"headerName": "", "checkboxSelection": True, "width": 50},
            {"field": "date", "headerName": "Date", "width": 130, "sort": "desc"},
            {"field": "name", "headerName": "Project", "flex": 1},
            {"field": "path", "headerName": "Folder", "flex": 1},
        ],
        rowData=discover_events(settings.photos_dir).to_dict("records"),
        dashGridOptions={
            "rowSelection": "multiple",
            "pagination": False,
            # "paginationPageSize": 25,
        },
        columnSize="sizeToFit",
        style={"height": "600px"},
    ),

    html.Button("View events", id="view-events-btn", style={"marginTop": "10px"}),
]))


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
