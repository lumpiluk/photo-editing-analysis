import logging

import dash
from dash import (
    callback,
    CeleryManager,
    Dash,
    dcc,
    DiskcacheManager,
    html,
    Input,
    Output,
)
import dash_bootstrap_components as dbc

from photography_analysis.dashboard.config import settings
from photography_analysis.dashboard.data_fetcher import fetch_and_save_immich_data


if settings.redis_url:
    # Use Redis & Celery if REDIS_URL set as an env variable
    from celery import Celery
    celery_app = Celery(
        __name__,
        broker=os.environ['REDIS_URL'],
        backend=os.environ['REDIS_URL'],
    )
    background_callback_manager = CeleryManager(celery_app)
else:
    # Diskcache for non-production apps when developing locally
    import diskcache
    cache = diskcache.Cache("./cache")
    background_callback_manager = DiskcacheManager(cache)


app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,  # because not all elements exist on events-detail page on startup
    background_callback_manager=background_callback_manager,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
)

app.layout = html.Div([
    dcc.Store(id="global-data-version"),
    html.Header([
        html.Nav([
            dcc.Link("People", href="/people"),
            dcc.Link("Events", href="/events"),
        ], style={"display": "flex", "gap": "1rem"}),
        html.Button("Refresh Immich data", id="global-refresh-btn"),
        html.Span(id="global-refresh-status", style={"marginLeft": "1rem"}),
    ], style={"padding": "10px", "borderBottom": "1px solid #ccc"}),
    dash.page_container,
])


def run_dashboard() -> None:
    logging.basicConfig(level=logging.INFO)
    app.run(
        host="0.0.0.0",
        debug=True,
        exclude_patterns=["data/*", "*.csv", "cache/*"],
    )


@callback(
    Output("global-refresh-status", "children"),
    Output("global-data-version", "data"),
    Input("global-refresh-btn", "n_clicks"),
    background=True,
    on_error=lambda e: f"Refresh failed: {e}",
    prevent_initial_call=True,
)
def refresh_immich_data(n_clicks):
    fetch_and_save_immich_data()
    return "Immich data refreshed.", n_clicks
