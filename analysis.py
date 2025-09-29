#!/usr/bin/env python3

from typing import Generator, Iterable

import argparse
import json
import os
import pathlib

import exiftool
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def main():
    args = parse_args()
    process_time_based_plots(args)
    process_metadata_plots(args)


def process_metadata_plots(args: argparse.Namespace):
    if not (
        args.focal_lengths_plot
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
                    files=(file for file in folder.glob(glob_pattern)),
                    cache_file=folder / cache_filename,
                    write_cache=args.cache_metadata,
                )
            )
    else:  # compare raw vs. edited aggregated over all folders
        metadata_raw = []
        metadata_edited = []
        for folder in args.folders:
            folder_metadata_raw = get_metadata(
                files=(file for file in folder.glob(args.raw_files_glob)),
                cache_file=folder / "metadata_raw.json",
                write_cache=args.cache_metadata,
            )
            folder_metadata_edited = get_metadata(
                files=(file for file in folder.glob(args.edited_files_glob)),
                cache_file=folder / "metadata_edited.json",
                write_cache=args.cache_metadata,
            )
            metadata_raw.extend(folder_metadata_raw)
            metadata_edited.extend(folder_metadata_edited)
        metadata_collections = [metadata_raw, metadata_edited]

    # print(metadata_collections[0][0].keys())

    if args.focal_lengths_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:FocalLength",
            xlabel="Focal length in mm",
            out_filename=args.focal_lengths_plot,
        )
    if args.exposure_times_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:ExposureTime",
            xlabel="Exposure time in seconds",
            out_filename=args.exposure_times_plot,
        )
    if args.apertures_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:FNumber",
            xlabel="Aperture (F-number)",
            out_filename=args.apertures_plot,
        )
    if args.isos_plot:
        plot_metadata(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            tag="EXIF:ISO",
            xlabel="ISO",
            out_filename=args.isos_plot,
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
                for file in folder.glob(glob_pattern)
            ]
            for folder in args.folders
        ]
    else:  # compare raw vs. edited
        files_collections: list[list[pathlib.Path]] = [
            [
                file
                for folder in args.folders
                for file in folder.glob(glob_pattern)
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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "folders",
        nargs="+",
        type=pathlib.Path,
        help="Image folders to analyze. "
             "Assumes that each folder contains raw files and edited images, "
             "as defined by --raw-files-glob and --edited-files-glob",
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
        "--focal-lengths-plot",
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
             "Reading metadata requires opening each file, which can be slow. ",
    )
    parser.add_argument(
        "--raw-files-glob",
        default="*.CR3",
    )
    parser.add_argument(
        "--edited-files-glob",
        default="converted*/*.jpg",
    )
    parser.add_argument(
        "--compare-folders",
        choices=["raw", "edited"],
        help="Instead of aggregating over all folders, compare them instead. "
             "If 'raw': Only use the raw files; if 'edited': only use the "
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
    timestamps_sec = sorted(timestamps_sec)
    assert len(timestamps_sec) > 1
    session_start = timestamps_sec[0]
    for prev_time, cur_time in zip(timestamps_sec, timestamps_sec[1:]):
        if cur_time - prev_time >= min_break_between_sessions_sec:
            yield prev_time - session_start
            session_start = cur_time
    # Final session:
    yield timestamps_sec[-1] - session_start


def plot_time_between_photos(
    mtimes_list: list[Iterable[float]],
    mtimes_labels: list[str],
    out_filename: pathlib.Path,
):
    # Compute delta times (first item will be NaN):
    df = pd.DataFrame({
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
    files: Iterable[pathlib.Path],
    cache_file: pathlib.Path | None = None,
    write_cache=True,
) -> list[dict]:
    if cache_file and cache_file.exists():
        with open(cache_file, 'r') as fp:
            return json.load(fp)
    with exiftool.ExifToolHelper() as et:
        metadata = et.get_metadata(files, params=["-fast2"])
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
    fig.tight_layout()
    fig.savefig(out_filename)


if __name__ == '__main__':
    main()
