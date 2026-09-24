import logging
import os

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
    State,
)
import dash_bootstrap_components as dbc
import dash_cytoscape as cyto

from photography_analysis.dashboard.config import settings
from photography_analysis.dashboard.data_fetcher import fetch_and_save_immich_data


cyto.load_extra_layouts()

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
    cache = diskcache.Cache(os.environ.get("DASH_CACHE", "./cache"))
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
    dcc.Store(id="demo-mode", storage_type="local", data=False),
    html.Header([
        html.Nav([
            dcc.Link("People", href="/people"),
            dcc.Link("Events", href="/events"),
        ], style={"display": "flex", "gap": "1rem"}),
        html.Button("Refresh Immich data", id="global-refresh-btn"),
        dcc.Checklist(
            id="demo-mode-toggle",
            options=[{"label": " Demo mode", "value": "on"}],
            value=[],
            style={"marginLeft": "1rem"},
        ),
        html.Span(id="global-refresh-status", style={"marginLeft": "1rem"}),
    ], style={"padding": "10px", "borderBottom": "1px solid #ccc"}),
    dash.page_container,
])


def run_dashboard() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    app.run(
        host=os.environ.get("DASH_HOST", "0.0.0.0"),
        port=os.environ.get("DASH_PORT", 8050),
        debug=os.environ.get("DASH_DEBUG", "True") == "True",
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


@callback(
    Output("demo-mode", "data"),
    Output("demo-mode-toggle", "value"),
    Input("demo-mode-toggle", "value"),
    State("demo-mode", "data"),
)
def sync_demo_mode(toggle_value, stored_value):
    triggered_id = dash.callback_context.triggered_id

    if triggered_id is None:
        # initial page load: reflect whatever was already in localStorage
        is_on = bool(stored_value)
    else:
        # user actually clicked the checkbox
        is_on = "on" in toggle_value

    return is_on, (["on"] if is_on else [])
