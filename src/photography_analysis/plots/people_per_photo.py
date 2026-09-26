import numpy as np
import plotly.graph_objects as go


def build_people_per_photo_ecdf_plotly(asset_people: list[dict], title=None):
    counts = [len(r["people"]) for r in asset_people]
    if not counts:
        return go.Figure()
    x = np.sort(counts)
    y = np.arange(1, len(x) + 1) / len(x)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines"))
    fig.update_layout(
        xaxis_title="Number of (known) people in photo",
        yaxis_title="Fraction of photos ≤ x",
        title=title,
    )
    return fig
