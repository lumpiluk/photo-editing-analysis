#!/usr/bin/env python3

import argparse
import os
import pathlib

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "folders",
        nargs="+",
        type=pathlib.Path,
        help="Image folders to analyze. "
             "Assumes that each folder contains *.CR3 raw files "
             "and a subfolder named 'converted' or 'converted_dt'.",
    )
    parser.add_argument(
        "--plot",
        type=pathlib.Path,
        help="File name of the resulting plot.",
    )
    args = parser.parse_args()

    mtimes_raw = collect_file_stats(files=[
        file
        for folder in args.folders
        for file in folder.glob("*.CR3")
    ])
    mtimes_edit = collect_file_stats(files=[
        file
        for folder in args.folders
        for file in folder.glob("converted*/*.jpg")
    ])

    # Compute delta times (first item will be NaN):
    dt_raw = pd.Series(sorted(mtimes_raw)).diff()
    dt_edit = pd.Series(sorted(mtimes_edit)).diff()
    df = pd.DataFrame({"Photos shot": dt_raw, "Photos edited": dt_edit})

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.ecdfplot(
        data=df,
        ax=ax,
    )
    ax.set_xlim(left=0, right=60 * 5)  # max. … minutes
    ax.set_xlabel("Time between photos in seconds")
    sns.move_legend(ax, "lower right")
    fig.tight_layout()
    fig.savefig(args.plot)


def collect_file_stats(
    files: list[pathlib.Path],
) -> list[float]:
    """Return the file modification times in unix seconds."""
    for file in files:
        stat = os.stat(file)
        yield stat.st_mtime


if __name__ == '__main__':
    main()
