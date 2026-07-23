import pathlib

import dash
from dash import html, dcc, callback, Input, Output

from photography_analysis.dashboard.config import settings
from photography_analysis.dashboard.data_fetcher import (
    fetch_and_save_immich_data,
)
from photography_analysis.plots.people_heatmap import (
    plot_heatmap_plotly,
)

dash.register_page(__name__)

layout = html.Div([
    html.H1("People"),
    html.Button("Refresh overview data", id="overview-refresh-btn"),
    html.Div(id="overview-refresh-status"),
    dcc.Graph(id="heatmap-graph"),
])


@callback(
    Output("overview-refresh-status", "children"),
    Input("overview-refresh-btn", "n_clicks"),
    background=True,
    on_error=lambda e: f"Refresh failed.",
    prevent_initial_call=True,
)
def refresh_overview(n_clicks):
    fetch_and_save_immich_data()
    return "Overview data refreshed."


@callback(
    Output("heatmap-graph", "figure"),
    #Input(...),
)
def update_heatmap():
    fig = plot_heatmap_plotly(
        person_photo_dates_path=(
            pathlib.Path(settings.data_cache_dir)
            / "person-photo-dates.csv"
        ),
        person_date_ranges_path=(
            pathlib.Path(settings.data_cache_dir)
            / "person-date-ranges.csv"
        ),
        # start_date=start_date,
        # end_date=end_date,
        start_date=None, end_date=None,
    )
    return fig


# TODO:
# - heatmap
#   - refresh button
#   - select date range
#   - select subset of people
#   - link from person name to person page
