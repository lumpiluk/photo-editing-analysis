import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go


def prepare_heatmap_data(
    person_photo_dates_path: pathlib.Path,
    person_date_ranges_path: pathlib.Path,
    start_date: str | None,
    end_date: str | None,
):
    photos = pd.read_csv(person_photo_dates_path)
    photos["date"] = pd.to_datetime(photos["date"], format="ISO8601")

    if start_date is None:
        start_date = photos["date"].min()
    else:
        start_date = pd.Timestamp(start_date, tz="UTC")
    if end_date is None:
        end_date = photos["date"].max()
    else:
        end_date = pd.Timestamp(end_date, tz="UTC")
    photos = photos[photos["date"].between(start_date, end_date)]

    ranges = pd.read_csv(person_date_ranges_path)
    ranges["last"] = pd.to_datetime(ranges["last"], format="ISO8601")

    # --- bin into monthly counts per person ---
    photos["month"] = photos["date"].dt.to_period("M")
    counts = (
        photos.groupby(["person_id", "month"])
        .size()
        .rename("n")
        .reset_index()
    )

    # --- sort order: by 'last' ---
    order = ranges.sort_values("last", ascending=False)["id"].tolist()
    name_by_id = ranges.set_index("id")["name"].to_dict()

    # --- pivot, with EVERY month present so the x-axis is truly linear ---
    full_months = pd.period_range(counts["month"].min(), counts["month"].max(), freq="M")
    pivot = counts.pivot(index="person_id", columns="month", values="n").fillna(0)
    pivot = pivot.reindex(columns=full_months, fill_value=0)
    pivot = pivot.reindex(order, fill_value=0)

    log_vals = np.log1p(pivot.values)

    return (log_vals, name_by_id, order, pivot)


def plot_heatmap(
    out_filename: pathlib.Path,
    person_photo_dates_path: pathlib.Path,
    person_date_ranges_path: pathlib.Path,
    start_date: str | None,
    end_date: str | None,
) -> None:
    log_vals, name_by_id, order, pivot = prepare_heatmap_data(
        person_photo_dates_path=person_photo_dates_path,
        person_date_ranges_path=person_date_ranges_path,
        start_date=start_date,
        end_date=end_date,
    )
    fig, ax = plt.subplots(
        figsize=(9, len(order) * 0.05),
        constrained_layout=True,
    )
    im = ax.imshow(
        log_vals,
        aspect="auto",
        cmap="viridis",
        interpolation="none",
    )

    # --- y labels on both sides ---
    labels = [name_by_id.get(pid) or pid for pid in order]
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(labels, fontsize=4)

    ax_right = ax.secondary_yaxis("right")
    ax_right.set_yticks(range(len(order)))
    ax_right.set_yticklabels(labels, fontsize=4)

    # --- horizontal gridlines between rows ---
    ax.set_yticks(np.arange(-0.5, len(order), 1), minor=True)
    ax.grid(which="minor", axis="y", color="white", linewidth=0.3, alpha=0.4)
    ax.tick_params(which="minor", length=0)

    # --- x-axis: every year gets a tick, evenly spaced now ---
    month_labels = pivot.columns.to_timestamp()
    year_starts = [i for i, d in enumerate(month_labels) if d.month == 1]
    ax.set_xticks(year_starts)
    ax.set_xticklabels([month_labels[i].year for i in year_starts], fontsize=4)

    ax.set_xticks(range(len(month_labels)), minor=True)
    ax.grid(which="minor", axis="x", color="white", linewidth=0.2, alpha=0.3)

    ax_top = ax.secondary_xaxis("top")
    ax_top.set_xticks(year_starts)
    ax_top.set_xticklabels([month_labels[i].year for i in year_starts], fontsize=4)

    # --- colorbar in real photo counts, not log space ---
    max_count = int(pivot.values.max())
    candidate_ticks = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    tick_counts = [t for t in candidate_ticks if t <= max_count] or [0, max_count]
    if tick_counts[-1] != max_count:
        tick_counts.append(max_count)

    # cbar = fig.colorbar(im, ax=ax, shrink=0.5)
    cbar = fig.colorbar(
        im,
        ax=ax,
        orientation="horizontal",
        location="top",
        # shrink=0.5,
        pad=0.02,
    )
    cbar.set_label("Photos per month")
    cbar.set_ticks(np.log1p(tick_counts))
    cbar.set_ticklabels([str(t) for t in tick_counts])

    fig.savefig(out_filename)


def plot_heatmap_plotly(
    person_photo_dates_path,
    person_date_ranges_path,
    start_date,
    end_date,
):
    log_vals, name_by_id, order, pivot = prepare_heatmap_data(
        person_photo_dates_path=person_photo_dates_path,
        person_date_ranges_path=person_date_ranges_path,
        start_date=start_date,
        end_date=end_date,
    )

    labels = [name_by_id.get(pid) or pid for pid in order]
    month_labels = pivot.columns.to_timestamp()
    raw_counts = pivot.values

    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        z=log_vals,
        x=month_labels,
        y=list(range(len(order))),
        customdata=raw_counts,
        hovertemplate="%{customdata} photos<br>%{x|%Y-%m}<extra></extra>",
        colorscale="Viridis",
        xgap=0.5,
        ygap=0.5,
        showscale=True,
    ))

    # --- colorbar in real counts, not log space (same trick as matplotlib version) ---
    max_count = int(raw_counts.max())
    candidate_ticks = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    tick_counts = [t for t in candidate_ticks if t <= max_count] or [0, max_count]
    if tick_counts[-1] != max_count:
        tick_counts.append(max_count)

    fig.data[0].colorbar.update(
        title="Photos/month",
        orientation="h",
        y=1.02, yanchor="bottom",
        len=0.6,
        tickvals=np.log1p(tick_counts),
        ticktext=[str(t) for t in tick_counts],
    )

    # --- left y-axis: names, top-to-bottom matching imshow's row order ---
    fig.update_yaxes(
        tickmode="array",
        tickvals=list(range(len(order))),
        ticktext=labels,
        # tickfont=dict(size=6),
        autorange="reversed",   # imshow puts row 0 at the top; Plotly's default is bottom
    )

    # --- right y-axis: mirrored names ---
    fig.update_layout(
        yaxis2=dict(
            tickmode="array",
            tickvals=list(range(len(order))),
            ticktext=labels,
            # tickfont=dict(size=6),
            overlaying="y",
            side="right",
            matches="y",
        )
    )
    # a real trace has to reference yaxis2 for Plotly to render its ticks at all
    fig.add_trace(go.Scatter(
        x=[month_labels[0]], y=[0], yaxis="y2",
        mode="markers", marker=dict(opacity=0),
        showlegend=False, hoverinfo="skip",
    ))

    # --- x-axis: year major ticks, month minor gridlines ---
    year_starts = [d for d in month_labels if d.month == 1]
    fig.update_xaxes(
        tickmode="array",
        tickvals=year_starts,
        tickformat="%Y",
        # tickfont=dict(size=8),
        minor=dict(dtick="M1", ticklen=2, showgrid=True, gridcolor="rgba(255,255,255,0.3)"),
    )

    fig.update_layout(
        height=max(500, len(order) * 12),
        # margin=dict(l=140, r=140, t=90, b=40),
    )

    return fig
