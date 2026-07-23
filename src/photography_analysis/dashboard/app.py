import dash
from dash import (
    CeleryManager,
    Dash,
    DiskcacheManager,
    html,
    dcc,
)

from photography_analysis.dashboard.config import settings


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
    background_callback_manager=background_callback_manager,
)

app.layout = html.Div([
    html.H1("Photography Dashboard"),
    html.Div([
        html.Div(
            dcc.Link(
                f"{page["name"]}",  #  - {page["path"]}",
                href=page["relative_path"],
            )
        ) for page in dash.page_registry.values()
    ]),
    dash.page_container
])


def run_dashboard() -> None:
    app.run(
        debug=True,
        exclude_patterns=["data/*", "*.csv", "cache/*"],
    )
