from typing import Iterable

import pathlib

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_time_between_photos(
    mtimes_list: list[Iterable[float]],
    mtimes_labels: list[str],
    out_filename: pathlib.Path,
):
    df = pd.DataFrame({
        # Compute delta times (first item will be NaN):
        label: pd.Series(mtimes).diff()
        for label, mtimes
        in zip(mtimes_labels, mtimes_list)
    })

    fig, ax = plt.subplots(figsize=(4, 3))
    sns.ecdfplot(
        data=df,
        ax=ax,
    )
    ax.set_xlim(left=0, right=60 * 5)  # max. … minutes
    ax.set_xlabel("Time between photos in seconds")
    sns.move_legend(ax, "lower right")
    fig.tight_layout()
    fig.savefig(out_filename)
