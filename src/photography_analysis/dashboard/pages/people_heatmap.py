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
    dcc.Store(id="data-version"),
    html.H1("People Heatmap"),
    dcc.DatePickerRange(id="date-range-picker"),
    html.Div(id="overview-refresh-status"),
    dcc.Graph(id="heatmap-graph"),
])


@callback(
    Output("heatmap-graph", "figure"),
    Input("date-range-picker", "start_date"),
    Input("date-range-picker", "end_date"),
    Input("global-data-version", "data"),
)
def update_heatmap(start_date: str, end_date: str, _version):
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
        start_date=start_date, end_date=end_date,
    )
    return fig
