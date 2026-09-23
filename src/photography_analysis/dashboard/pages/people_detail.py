from collections import Counter
import json
import pathlib
from urllib.parse import parse_qs

import dash
import dash_ag_grid as dag
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

from photography_analysis.dashboard.config import settings

dash.register_page(__name__, path="/people-detail")

layout = html.Div([
    html.Div(id="detail-content"),
])


def load_ranges():
    path = pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv"
    df = pd.read_csv(path)
    df["last"] = pd.to_datetime(df["last"], format="ISO8601")
    return df


def load_photos():
    path = pathlib.Path(settings.data_cache_dir) / "person-photo-dates.csv"
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format="ISO8601")
    return df


def load_asset_people():
    path = pathlib.Path(settings.data_cache_dir) / "asset-people.json"
    with open(path, "r") as f:
        return json.load(f)


def compute_gaps(photos, person_id):
    days = (
        photos.loc[photos["person_id"] == person_id, "date"]
        .dt.normalize()
        .drop_duplicates()
        .sort_values()
    )
    return days.diff().dt.days.dropna().values


def build_heatmap_figure(photos, ranges, person_ids, name_by_id):
    sub_photos = photos[photos["person_id"].isin(person_ids)]
    sub_photos = sub_photos.assign(month=sub_photos["date"].dt.to_period("M"))

    counts = (
        sub_photos.groupby(["person_id", "month"]).size().rename("n").reset_index()
    )

    full_months = pd.period_range(counts["month"].min(), counts["month"].max(), freq="M")
    pivot = counts.pivot(index="person_id", columns="month", values="n").fillna(0)
    pivot = pivot.reindex(columns=full_months, fill_value=0)
    pivot = pivot.reindex(person_ids, fill_value=0)

    labels = [name_by_id.get(pid) or pid for pid in person_ids]
    month_labels = pivot.columns.to_timestamp()

    fig = go.Figure(go.Heatmap(
        z=np.log1p(pivot.values),
        x=month_labels,
        y=labels,
        customdata=pivot.values,
        hovertemplate="%{y}<br>%{x|%Y-%m}<br>%{customdata:.0f} photos<extra></extra>",
        colorscale="Viridis",
        xgap=1,
        ygap=1,
        showscale=False,
    ))
    fig.update_layout(
        height=max(200, len(person_ids) * 60),
        margin=dict(l=120, r=20, t=20, b=40),
    )
    return fig


def build_gap_ecdf_figure(photos, person_ids, name_by_id):
    fig = go.Figure()
    for pid in person_ids:
        gaps = compute_gaps(photos, pid)
        if len(gaps) == 0:
            continue
        x = np.sort(gaps)
        y = np.arange(1, len(x) + 1) / len(x)
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", name=name_by_id.get(pid) or pid,
        ))

    fig.update_layout(
        xaxis_title="Gap between photos (days)",
        yaxis_title="Fraction of gaps ≤ x",
        height=400,
        margin=dict(b=120),  # bottom margin for label + legend
        legend={
            "yanchor": "top",
            "orientation": "h",
            "xanchor": "left",
            "y": -.25
        },
    )
    return fig


def build_totals_table(ranges, ids, name_by_id, num_days_by_id):
    sub = ranges[ranges["id"].isin(ids)].set_index("id").loc[ids]
    rows = [
        html.Tr([
            html.Td(name_by_id.get(pid) or pid),
            html.Td(int(sub.loc[pid, "num_assets"])),
            html.Td(int(num_days_by_id.get(pid, 0))),
        ])
        for pid in ids
    ]
    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("Name"), html.Th("Total photos"), html.Th("Days photographed"),
        ])),
        html.Tbody(rows),
    ])


def build_face_count_ecdf(asset_people, ids, name_by_id):
    fig = go.Figure()
    for pid in ids:
        counts = [len(photo) - 1 for photo in asset_people if pid in photo]
        if not counts:
            continue
        x = np.sort(counts)
        y = np.arange(1, len(x) + 1) / len(x)
        fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name=name_by_id.get(pid) or pid))

    fig.update_layout(
        xaxis_title="Other known people in the same photo",
        yaxis_title="Fraction of photos ≤ x",
    )
    return fig


def build_co_occurrence_table(asset_people, person_id, name_by_id):
    counts = Counter()
    for photo in asset_people:
        if person_id in photo:
            for other in photo:
                if other != person_id:
                    counts[other] += 1

    rows = [
        {
            "name": name_by_id.get(other_id) or "UNKNOWN",
            "id": other_id,
            "count": n,
        }
        for other_id, n in counts.most_common()
    ]
    return html.Div(
        dag.AgGrid(
            columnDefs=[
                {
                    "headerName": "",
                    "cellRenderer": "PersonLinksRenderer",
                    "width": 70,
                    "sortable": False,
                    "filter": False,
                },
                {
                    "field": "name",
                    "headerName": "Person",
                    "flex": 1,
                    "sortable": True,
                },
                {
                    "field": "count",
                    "headerName": "Photos together",
                    "width": 160,
                    "sortable": True,
                    "sort": "desc",
                },
            ],
            rowData=rows,
            columnSize="sizeToFit",
            dashGridOptions={
                "context": {"immichHost": settings.immich_host},
            },
            style={"height": "100%", "width": "100%"},
        ),
        style={"resize": "both", "overflow": "auto", "height": "400px", "width": "100%"},
    )


@callback(
    Output("detail-content", "children"),
    Input("_pages_location", "search"),
    Input("global-data-version", "data"),
)
def render_detail(search, _version):
    if not search:
        return html.Div("No people selected.")

    params = parse_qs(search.lstrip("?"))
    ids = params.get("ids", [""])[0].split(",")
    ids = [i for i in ids if i]

    if not ids:
        return html.Div("No people selected.")

    ranges = load_ranges()
    photos = load_photos()
    asset_people = load_asset_people()

    name_by_id = ranges.set_index("id")["name"].to_dict()

    num_days = (
        photos[photos["person_id"].isin(ids)]
        .assign(date=lambda d: d["date"].dt.normalize())
        .groupby("person_id")["date"]
        .nunique()
    )
    num_days_by_id = num_days.to_dict()

    return html.Div([
        dbc.Container([
            html.H2("Total photos"),
            build_totals_table(ranges, ids, name_by_id, num_days_by_id),

            html.H2("Photos per month"),
            dcc.Graph(figure=build_heatmap_figure(photos, ranges, ids, name_by_id)),

            html.H2("Gap between photos (ECDF)"),
            dcc.Graph(figure=build_gap_ecdf_figure(photos, ids, name_by_id)),

            html.H2("Photographed With"),
            dcc.Graph(figure=build_face_count_ecdf(asset_people, ids, name_by_id)),
            html.Div([
                html.Div([
                    html.H3(name_by_id.get(pid) or pid),
                    build_co_occurrence_table(asset_people, pid, name_by_id),
                ], style={"margin-bottom": "5rem"})
                for pid in ids
            ])
        ]),
    ])
