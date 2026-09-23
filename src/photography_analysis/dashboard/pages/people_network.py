import json
import pathlib
from collections import Counter
from itertools import combinations

import dash
import dash_cytoscape as cyto
import pandas as pd
from dash import html, dcc, callback, Input, Output

from photography_analysis.dashboard.config import settings

dash.register_page(__name__, path="/people-network")

CACHE_FILE = pathlib.Path(settings.data_cache_dir) / "asset-people.json"

layout = html.Div([
    dcc.Location(id="network-url-redirect", refresh=False),
    html.H1("Who was photographed with whom"),

    html.Label("Minimum shared photos to show a connection:"),
    dcc.Slider(id="min-shared-slider", min=1, max=20, step=1, value=10,
               marks={i: str(i) for i in range(1, 21, 2)}),

    html.Div(id="network-content"),
])


def load_ranges():
    return pd.read_csv(pathlib.Path(settings.data_cache_dir) / "person-date-ranges.csv")


def build_graph_elements(min_shared: int):
    with open(CACHE_FILE) as f:
        asset_people = json.load(f)

    ranges = load_ranges()
    named_ids = set(ranges.loc[ranges["name"].notna() & (ranges["name"] != ""), "id"])

    pair_counts = Counter()
    node_photo_counts = Counter()
    for people_in_photo in asset_people:
        named_people = [pid for pid in people_in_photo if pid in named_ids]
        for pid in named_people:
            node_photo_counts[pid] += 1
        for a, b in combinations(sorted(set(named_people)), 2):
            pair_counts[(a, b)] += 1

    name_by_id = ranges.set_index("id")["name"].to_dict()

    edges = [(a, b, n) for (a, b), n in pair_counts.items() if n >= min_shared]
    connected_ids = {pid for a, b, _ in edges for pid in (a, b)}

    nodes = [
        {
            "data": {
                "id": pid,
                "label": name_by_id.get(pid) or pid,
                "size": 1  # node_photo_counts.get(pid, 1),
            }
        }
        for pid in connected_ids
    ]
    edge_elements = [{"data": {"source": a, "target": b, "weight": n}} for a, b, n in edges]

    return nodes + edge_elements


@callback(
    Output("network-content", "children"),
    Input("min-shared-slider", "value"),
)
def update_graph(min_shared):
    if not CACHE_FILE.exists():
        return html.Div(
            "No co-occurrence data found. Click \"Refresh Immich Data\" in the header first — "
            "this may take a few minutes on first run.",
            style={"color": "orange"},
        )

    elements = build_graph_elements(min_shared)
    if not elements:
        return html.Div(f"No pairs of people share at least {min_shared} photos. Try lowering the threshold.")

    return cyto.Cytoscape(
        id="co-occurrence-graph",
        layout={
            "name": "cose-bilkent",
            "animate": False,
            "nodeRepulsion": 16000,
            "idealEdgeLength": 100,
            "gravity": 0.3,
        },
        style={"width": "100%", "height": "1000px"},
        elements=elements,
        stylesheet=[
            {"selector": "node", "style": {
                "label": "data(label)",
                # mapData: low node value, high node value, low node px, high node px
                "width": "mapData(size, 1, 100, 5, 20)",
                "height": "mapData(size, 1, 100, 5, 20)",
                "font-size": "4px",
            }},
            {"selector": "edge", "style": {
                "width": "mapData(weight, 1, 50, .1, 1)",
                "opacity": 0.4,
                "curve-style": "haystack",
            }},
        ],
    )


@callback(
    Output("network-url-redirect", "pathname"),
    Output("network-url-redirect", "search"),
    Input("co-occurrence-graph", "tapNodeData"),
    prevent_initial_call=True,
)
def go_to_tapped_person(node_data):
    if not node_data:
        return dash.no_update, dash.no_update
    return "/people-detail", f"?ids={node_data['id']}"
