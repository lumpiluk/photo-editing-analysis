#!/usr/bin/env python3

from typing import Generator, Iterable

import argparse
import datetime
import fractions
import json
import os
import pathlib

import exiftool
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns


# Further ideas:
# - keep-ratio over time (1 folder = 1 data point)
# - photos per hour (by session)


def main():
    args = parse_args()

    for folder in args.folders:
        if not folder.exists():
            raise ValueError(
                f"The provided folder does not seem to exist: "
                f"{folder}"
            )

    process_time_based_plots(args)
    process_metadata_plots(args)


def process_metadata_plots(args: argparse.Namespace):
    if not (
        args.hour_of_day_plot
        or args.focal_lengths_plot
        or args.focal_lengths_full_frame_plot
        or args.exposure_times_plot
        or args.apertures_plot
        or args.isos_plot
    ):
        return

    labels = (
        args.folder_comparison_labels
        if args.compare_folders
        else ["Raw photos", "Edited photos"]
    )

    metadata_collections: list[list[dict]] = []
    if args.compare_folders:
        if args.compare_folders == "raw":
            glob_pattern = args.raw_files_glob
            cache_filename = "metadata_raw.json"
        else:
            glob_pattern = args.edited_files_glob
            cache_filename = "metadata_edited.json"
        for folder in args.folders:
            metadata_collections.append(
                get_metadata(
                    files=(file for file in folder.glob(
                        glob_pattern, case_sensitive=False
                    )),
                    cache_file=folder / cache_filename,
                    write_cache=args.cache_metadata,
                )
            )
    else:  # compare raw vs. edited aggregated over all folders
        metadata_raw = []
        metadata_edited = []
        for folder in args.folders:
            folder_metadata_raw = get_metadata(
                files=(file for file in folder.glob(
                    args.raw_files_glob, case_sensitive=False
                )),
                cache_file=folder / "metadata_raw.json",
                write_cache=args.cache_metadata,
            )
            folder_metadata_edited = get_metadata(
                files=(file for file in folder.glob(
                    args.edited_files_glob, case_sensitive=False
                )),
                cache_file=folder / "metadata_edited.json",
                write_cache=args.cache_metadata,
            )
            metadata_raw.extend(folder_metadata_raw)
            metadata_edited.extend(folder_metadata_edited)
        metadata_collections = [metadata_raw, metadata_edited]

    # print(metadata_collections[0][0].keys())

    if args.hour_of_day_plot:
        plot_photo_capture_hours_of_day(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            out_filename=args.hour_of_day_plot,
        )
    if args.focal_lengths_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:FocalLength",
            xlabel="Focal length in mm",
            out_filename=args.focal_lengths_plot,
        )
    if args.focal_lengths_full_frame_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            # tag="EXIF:FocalLengthIn35mmFormat",
            tag="Composite:FocalLength35efl",
            xlabel="Focal length in mm (35 mm equiv.)",
            out_filename=args.focal_lengths_full_frame_plot,
        )
    if args.exposure_times_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:ExposureTime",
            xlabel="Exposure time in seconds",
            out_filename=args.exposure_times_plot,
            log_scale=True,
            x_tick_formatter=fraction_formatter,
            x_tick_params={"labelrotation": 30},
        )
    if args.apertures_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:FNumber",
            xlabel="Aperture",
            out_filename=args.apertures_plot,
            log_scale=True,
            x_tick_formatter=aperture_formatter,
            x_ticks=[1 * 2 ** i for i in range(0, 5, 1)],
        )
    if args.isos_plot:
        x_tick_formatter = ticker.ScalarFormatter()
        x_tick_formatter.set_scientific(False)
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:ISO",
            xlabel="ISO",
            out_filename=args.isos_plot,
            log_scale=True,
            x_tick_formatter=x_tick_formatter,
            x_ticks=[100 * 2 ** i for i in range(0, 9, 2)],
        )


def process_time_based_plots(args: argparse.Namespace):
    if not args.delta_plot and not args.sessions_plot:
        return
    if args.compare_folders:
        glob_pattern = (
            args.raw_files_glob
            if args.compare_folders == "raw"
            else args.edited_files_glob
        )
        files_collections: list[list[pathlib.Path]] = [
            [
                file
                for file in folder.glob(glob_pattern, case_sensitive=False)
            ]
            for folder in args.folders
        ]
    else:  # compare raw vs. edited
        files_collections: list[list[pathlib.Path]] = [
            [
                file
                for folder in args.folders
                for file in folder.glob(glob_pattern, case_sensitive=False)
            ]
            for glob_pattern
            in [args.raw_files_glob, args.edited_files_glob]
        ]

    mtimes_collections: list[list[float]] = [
        sorted(collect_file_stats(files=files_collection))
        for files_collection in files_collections
    ]

    if args.delta_plot:
        plot_time_between_photos(
            mtimes_list=mtimes_collections,
            mtimes_labels=(
                args.folder_comparison_labels
                if args.compare_folders
                else ["Photos shot", "Photos edited"]
            ),
            out_filename=args.delta_plot,
        )

    if args.sessions_plot:
        sessions_collections = [
            get_sessions_from_time_series(
                timestamps_sec=mtimes_collection,
                min_break_between_sessions_sec=60 * 30,
            )
            for mtimes_collection in mtimes_collections
        ]
        plot_sessions(
            sessions_list=sessions_collections,
            sessions_labels=(
                args.folder_comparison_labels
                if args.compare_folders
                else ["Photo shoot sessions", "Editing sessions"]
            ),
            out_filename=args.sessions_plot,
            show_info_text=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Analyze and plot a number of different metrics for your "
                    "photographs. ",
    )
    parser.add_argument(
        "folders",
        nargs="+",
        type=pathlib.Path,
        help="Image folders to analyze. "
             "Assumes that each folder contains raw files and edited images, "
             "as defined by --raw-files-glob and --edited-files-glob.",
    )
    parser.add_argument(
        "--delta-plot",
        type=pathlib.Path,
        help="File name of the plot of time between "
             "raw files and edited files.",
    )
    parser.add_argument(
        "--sessions-plot",
        type=pathlib.Path,
        help="File name of the plot of session durations.",
    )
    parser.add_argument(
        "--hour-of-day-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--focal-lengths-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--focal-lengths-full-frame-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--exposure-times-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--apertures-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--isos-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--cache-metadata",
        action="store_true",
        help="After reading the metadata of image files within a folder, "
             "store the results in a JSON file in the same folder. "
             "Reading metadata requires opening each file, which can be slow "
             "especially for raw files.",
    )
    parser.add_argument(
        "--raw-files-glob",
        default="*.CR3",
        help="Glob pattern for finding raw files within each provided folder. "
             "Take care to pass this value in single quotation marks; "
             "otherwise your shell may try to expand "
             "the pattern prematurely.",
    )
    parser.add_argument(
        "--edited-files-glob",
        default="converted*/*.jpg",
        help="Glob pattern for finding edited files within each "
             "provided folder. "
             "Take care to pass this value in single quotation marks; "
             "otherwise your shell may try to expand "
             "the pattern prematurely.",
    )
    parser.add_argument(
        "--compare-folders",
        choices=["raw", "edited"],
        help="Instead of aggregating over all folders, compare them instead. "
             "If 'raw': only use the raw files; if 'edited': only use the "
             "edited files (see --raw-files-glob and --edited-files-glob).",
    )
    parser.add_argument(
        "--folder-comparison-labels",
        nargs='*',
        help="Label to use for each folder in the legend of each plot. "
             "Only used if --compare-folders is active.",
    )
    args = parser.parse_args()
    if (
        args.compare_folders
        and len(args.folders) != len(args.folder_comparison_labels)
    ):
        raise ValueError(
            "When using --compare-folders, "
            "--folder-comparison-labels must have the same number of "
            "arguments as there are folders."
        )
    return args


def collect_file_stats(
    files: Iterable[pathlib.Path],
) -> Generator[float]:
    """Return the file modification times in unix seconds."""
    for file in files:
        stat = os.stat(file)
        yield stat.st_mtime


def get_sessions_from_time_series(
    timestamps_sec: Iterable[float],
    min_break_between_sessions_sec: float = 60 * 30,
) -> Generator[float]:
    assert len(timestamps_sec) > 1
    timestamps_sec = sorted(timestamps_sec)
    session_start = timestamps_sec[0]
    for prev_time, cur_time in zip(timestamps_sec, timestamps_sec[1:]):
        if cur_time - prev_time >= min_break_between_sessions_sec:
            session_duration = prev_time - session_start
            session_start = cur_time
            if session_duration > 0:
                # Still reset session_start, but don't count sessions
                # that are too short
                yield session_duration
    # Final session:
    yield timestamps_sec[-1] - session_start


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


def get_metadata(
    files: list[pathlib.Path],
    cache_file: pathlib.Path | None = None,
    write_cache=True,
) -> list[dict]:
    if cache_file and cache_file.exists():
        with open(cache_file, 'r') as fp:
            return json.load(fp)
    with exiftool.ExifToolHelper() as et:
        try:
            metadata = et.get_metadata(files, params=["-fast2"])
        except exiftool.exceptions.ExifToolOutputEmptyError:
            print(
                f"No metadata found for images in "
                f"{files[0].parent}"
            )
            return [dict()]
        if write_cache and cache_file:
            with open(cache_file, 'w') as fp:
                json.dump(metadata, fp, indent=2)
        return metadata


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
):
    assert len(metadata_lists) == len(metadata_labels)

    df = pd.DataFrame({
        metadata_label: pd.Series(sorted([
            it[tag] for it in metadata_list
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
                it["EXIF:DateTimeOriginal"].replace(":", "-", count=2)
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
    g.set_axis_labels("Hour of Day", "Number of Photos")
    g.set_titles(col_template="{col_name}", weight="bold")
    g.fig.subplots_adjust(top=.93)
    g.set(xticks=range(0, 25, 2))
    for ax in g.axes.flat:
        ax.tick_params(labelbottom=True)
    g.tight_layout()
    g.fig.savefig(out_filename)


def fraction_formatter(x, pos):
    # (With help from Claude)
    if x <= 0:
        return "0"
    elif x < 1:
        frac = fractions.Fraction(x)
        if frac.numerator == 1:
            return f"1/{frac.denominator}"
        else:
            return f"{frac.numerator}/{frac.denominator}"
    else:
        if x == int(x):
            return f"{int(x)}s"
        else:
            return f"{x:.1f}s"


def aperture_formatter(x, pos):
    # We just pretend it's fractions
    return f"1/{x:g}"


if __name__ == '__main__':
    main()
