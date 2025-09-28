#!/usr/bin/env python3

from typing import Generator, Iterable

import argparse
import os
import pathlib

import exiftool
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
    args = parser.parse_args()

    raw_files = [
        file
        for folder in args.folders
        for file in folder.glob("*.CR3")
    ]
    edited_files = [
        file
        for folder in args.folders
        for file in folder.glob("converted*/*.jpg")
    ]

    if args.delta_plot or args.sessions_plot:
        mtimes_raw = sorted(collect_file_stats(files=raw_files))
        mtimes_edit = sorted(collect_file_stats(files=edited_files))

        if args.delta_plot:
            plot_time_between_photos(
                mtimes_list=[mtimes_raw, mtimes_edit],
                mtimes_labels=["Photos shot", "Photos edited"],
                out_filename=args.delta_plot,
            )

        if args.sessions_plot:
            sessions_raw = get_sessions_from_time_series(
                timestamps_sec=mtimes_raw,
                min_break_between_sessions_sec=60 * 30,
            )
            sessions_edit = get_sessions_from_time_series(
                timestamps_sec=mtimes_edit,
                min_break_between_sessions_sec=60 * 30,
            )
            plot_sessions(
                sessions_list=[sessions_raw, sessions_edit],
                sessions_labels=["Photo shoot sessions", "Editing sessions"],
                out_filename=args.sessions_plot,
                show_info_text=True,
            )

    if (
            args.focal_lengths_plot
            or args.exposure_times_plot
            or args.apertures_plot
            or args.isos_plot
    ):
        metadata_raw = get_metadata(raw_files)
        metadata_edited = get_metadata(edited_files)
        # print(metadata_raw[0].keys())

        if args.focal_lengths_plot:
            plot_metadata(
                metadata_lists=[metadata_raw, metadata_edited],
                metadata_labels=["Raw photos", "Edited photos"],
                tag="EXIF:FocalLength",
                xlabel="Focal length in mm",
                out_filename=args.focal_lengths_plot,
            )
        if args.exposure_times_plot:
            plot_metadata(
                metadata_lists=[metadata_raw, metadata_edited],
                metadata_labels=["Raw photos", "Edited photos"],
                tag="EXIF:ExposureTime",
                xlabel="Exposure time in seconds",
                out_filename=args.exposure_times_plot,
            )
        if args.apertures_plot:
            plot_metadata(
                metadata_lists=[metadata_raw, metadata_edited],
                metadata_labels=["Raw photos", "Edited photos"],
                tag="EXIF:FNumber",
                xlabel="Aperture (F-number)",
                out_filename=args.apertures_plot,
            )
        if args.isos_plot:
            plot_metadata(
                metadata_lists=[metadata_raw, metadata_edited],
                metadata_labels=["Raw photos", "Edited photos"],
                tag="EXIF:ISO",
                xlabel="ISO",
                out_filename=args.isos_plot,
            )

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
) -> list[dict]:
    with exiftool.ExifToolHelper() as et:
        return et.get_metadata(files)


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
