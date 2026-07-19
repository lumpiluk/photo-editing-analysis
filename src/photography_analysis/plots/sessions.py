from typing import Iterable

import pathlib

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def plot_sessions(
    sessions_list: list[Iterable[float]],
    sessions_labels: list[str],
    out_filename: pathlib.Path,
    show_info_text=True,  # Currently only for <= 2 collections of sessions
):
    sessions_list_minutes = [
        pd.Series(sessions) / 60
        for sessions in sessions_list
    ]
    df = pd.DataFrame({
        label: sessions
        for label, sessions
        in zip(sessions_labels, sessions_list_minutes)
    })

    fig, ax = plt.subplots(figsize=(
        4,
        3.5 if show_info_text else 3
    ))
    sns.ecdfplot(
        data=df,
        ax=ax,
    )
    ax.set_xlabel("Session duration in minutes")
    if show_info_text:
        fig.text(
            .05,
            .05,
            "\n".join(
                f"{label} total: {len(sessions_minutes)}, "
                f"duration: {sum(sessions_minutes) / 60:.2f} hours"
                # f"{datetime.timedelta(minutes=sum(sessions_minutes))}",
                for label, sessions_minutes
                in zip(sessions_labels, sessions_list_minutes)
            ),
            ha="left",
            va="bottom",
            fontsize=9,
            transform=fig.transFigure,
        )
    fig.tight_layout()
    if show_info_text:
        fig.subplots_adjust(bottom=.30)
    fig.savefig(out_filename)
