import datetime
import pathlib

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from photography_analysis.data import get_metadata, try_get_tag


def plot_metadata(
    metadata_lists: list[list[dict]],
    metadata_labels: list[str],
    tag: str,
    xlabel: str,
    out_filename: pathlib.Path,
    log_scale=False,
    x_tick_formatter=None,
    x_ticks: list[float] | None = None,
    x_tick_params: dict | None = None,
    nan_if_tag_missing=False,
):
    assert len(metadata_lists) == len(metadata_labels)

    df = pd.DataFrame({
        metadata_label: pd.Series(sorted([
            float(try_get_tag(it, tag, use_nan=nan_if_tag_missing))
            for it in metadata_list
        ]))
        for metadata_label, metadata_list
        in zip(metadata_labels, metadata_lists)
    })

    fig, ax = plt.subplots(figsize=(4, 3))
    sns.ecdfplot(
        data=df,
        ax=ax,
    )
    ax.set_xlabel(xlabel)
    if log_scale:
        ax.set_xscale("log", base=2)
    if x_ticks:
        ax.set_xticks(x_ticks)
    if x_tick_formatter:
        ax.xaxis.set_major_formatter(x_tick_formatter)
    if x_tick_params:
        ax.tick_params(axis='x', **x_tick_params)
    sns.move_legend(ax, "best")
    fig.tight_layout()
    fig.savefig(out_filename)


def plot_photo_capture_hours_of_day(
    metadata_lists: list[list[dict]],
    metadata_labels: list[str],
    out_filename: pathlib.Path,
):
    assert len(metadata_lists) == len(metadata_labels)

    df = pd.DataFrame({
        metadata_label: pd.Series(sorted([
            datetime.datetime.fromisoformat(
                # EXIF dates look like 2025:09:27 18:23:00 instead of
                # 2025-09-27 18:23:00, so we'll have to fix that:
                try_get_tag(it, "EXIF:DateTimeOriginal").replace(
                    ":", "-", count=2
                )
            )
            for it in metadata_list
        ]))
        for metadata_label, metadata_list
        in zip(metadata_labels, metadata_lists)
    })
    df_hours = df.apply(lambda col: col.dt.hour)

    fig, ax = plt.subplots(figsize=(4, 3))
    g = sns.displot(
        data=df_hours.melt(
            var_name="Category",
            value_name="Hour",
        ),
        x="Hour",
        col="Category",
        col_wrap=3 if len(df_hours.columns) > 4 else 2,
        bins=24,
        binrange=(0, 24),
        height=3.5,
        aspect=1.3,
        facet_kws={"sharex": True, "sharey": True},
    )
    g.set_axis_labels("Hour of day", "Number of photos")
    g.set_titles(col_template="{col_name}", weight="bold")
    g.fig.subplots_adjust(top=.93)
    g.set(xticks=range(0, 25, 2))
    for ax in g.axes.flat:
        ax.tick_params(labelbottom=True)
    g.tight_layout()
    g.fig.savefig(out_filename)
