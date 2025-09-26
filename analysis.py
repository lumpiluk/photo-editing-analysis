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
        required=True,
        help="File name of the plot of time between "
             "raw files and edited files.",
    )
    parser.add_argument(
        "--sessions-plot",
        type=pathlib.Path,
        required=True,
        help="File name of the plot of session durations.",
    )
    parser.add_argument(
        "--focal-lengths-plot",
        type=pathlib.Path,
        required=False,
    )
    parser.add_argument(
        "--exposure-times-plot",
        type=pathlib.Path,
        required=False,
    )
    parser.add_argument(
        "--apertures-plot",
        type=pathlib.Path,
        required=False,
    )
    parser.add_argument(
        "--isos-plot",
        type=pathlib.Path,
        required=False,
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

    mtimes_raw = sorted(collect_file_stats(files=raw_files))
    mtimes_edit = sorted(collect_file_stats(files=edited_files))

    plot_time_between_photos(
        mtimes_raw=mtimes_raw,
        mtimes_edit=mtimes_edit,
        out_filename=args.delta_plot,
    )

    sessions_raw = get_sessions_from_time_series(
        timestamps_sec=mtimes_raw,
        min_break_between_sessions_sec=60 * 30,
    )
    sessions_edit = get_sessions_from_time_series(
        timestamps_sec=mtimes_edit,
        min_break_between_sessions_sec=60 * 30,
    )

    plot_sessions(
        sessions_raw=sessions_raw,
        sessions_edit=sessions_edit,
        out_filename=args.sessions_plot,
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
                metadata_raw=metadata_raw,
                metadata_edited=metadata_edited,
                tag="EXIF:FocalLength",
                xlabel="Focal length in mm",
                out_filename=args.focal_lengths_plot,
            )
        if args.exposure_times_plot:
            # TODO: or will it return strings here?
            plot_metadata(
                metadata_raw=metadata_raw,
                metadata_edited=metadata_edited,
                tag="EXIF:ExposureTime",
                xlabel="Exposure time in seconds",
                out_filename=args.exposure_times_plot,
            )
        if args.apertures_plot:
            plot_metadata(
                metadata_raw=metadata_raw,
                metadata_edited=metadata_edited,
                tag="EXIF:FNumber",
                xlabel="Aperture as 1/x",
                out_filename=args.apertures_plot,
            )
        if args.isos_plot:
            plot_metadata(
                metadata_raw=metadata_raw,
                metadata_edited=metadata_edited,
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
    mtimes_raw: Iterable[float],
    mtimes_edit: Iterable[float],
    out_filename: pathlib.Path,
):
    # Compute delta times (first item will be NaN):
    dt_raw = pd.Series(mtimes_raw).diff()
    dt_edit = pd.Series(mtimes_edit).diff()
    df = pd.DataFrame({"Photos shot": dt_raw, "Photos edited": dt_edit})

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
    sessions_raw: Iterable[float],
    sessions_edit: Iterable[float],
    out_filename: pathlib.Path,
):
    sessions_raw_minutes = pd.Series(sessions_raw) / 60
    sessions_edit_minutes = pd.Series(sessions_edit) / 60
    df = pd.DataFrame({
        "Photo shoot sessions": sessions_raw_minutes,
        "Editing sessions": sessions_edit_minutes,
    })

    fig, ax = plt.subplots(figsize=(4, 3.5))
    sns.ecdfplot(
        data=df,
        ax=ax,
    )
    # ax.set_xlim(left=0, right=
    ax.set_xlabel("Session duration in minutes")
    fig.text(
        .05,
        .05,
        f"{len(sessions_raw_minutes)} photo shoot sessions, "
        # f"{datetime.timedelta(minutes=sum(sessions_raw_minutes))}\n"
        f"{sum(sessions_raw_minutes) / 60:.2f} hours total\n"
        f"{len(sessions_edit_minutes)} editing sessions, "
        # f"{datetime.timedelta(minutes=sum(sessions_edit_minutes))}",
        f"{sum(sessions_edit_minutes) / 60:.2f} hours total",
        ha="left",
        va="bottom",
        fontsize=10,
        transform=fig.transFigure,
    )
    fig.tight_layout()
    fig.subplots_adjust(bottom=.30)
    fig.savefig(out_filename)


def get_metadata(
    files: Iterable[pathlib.Path],
) -> list[dict]:
    with exiftool.ExifToolHelper() as et:
        return et.get_metadata(files)


def plot_metadata(
    metadata_raw: list[dict],
    metadata_edited: list[dict],
    tag: str,
    xlabel: str,
    out_filename: pathlib.Path,
):
    data_raw = sorted([it[tag] for it in metadata_raw])
    data_edit = sorted([it[tag] for it in metadata_edited])
    df = pd.DataFrame({
        "Raw photos": pd.Series(data_raw),
        "Edited photos": pd.Series(data_edit),
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
