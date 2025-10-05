import argparse
import pathlib

import matplotlib as mpl
import matplotlib.ticker as ticker

from photography_analysis import (
    data,
    plots,
)

# Further ideas:
# - keep-ratio over time (1 folder = 1 data point)
# - photos per hour (by session)
# - (Optionally) use Composite:SubSecModifyDate and CreateDate instead of stat
# - optionally as many glob patterns as there are folders


def main():
    args = parse_args()

    # Give plots a reasonable size when users decide to save them
    # as raster graphics:
    mpl.rcParams['figure.dpi'] = 300

    process_time_based_plots(args)
    process_metadata_plots(args)


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
        "--light-values-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--crop-factors-plot",
        type=pathlib.Path,
    )
    parser.add_argument(
        "--custom-metadata-plot",
        type=pathlib.Path,
        nargs='*',
        help="Plot an ECDF for any metadata tag. "
             "Use in conjunction with --custom-metadata-plot-tag "
             "and --custom-metadata-plot-axis-label.",
    )
    parser.add_argument(
        "--custom-metadata-plot-tag",
        type=str,
        nargs='*',
    )
    parser.add_argument(
        "--custom-metadata-plot-axis-label",
        type=str,
        nargs='*',
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
    parser.add_argument(
        "--use-nan-if-metadata-missing",
        action='store_true',
        help="Use 'NaN' if a metadata tag cannot be found for a given image. "
             "Use this if you know that some or most images do have the tag. "
             "Otherwise, leave it off to avoid failing silently.",
    )

    args = parser.parse_args()
    validate_args(args)
    return args


def process_metadata_plots(args: argparse.Namespace):
    if not (
        args.hour_of_day_plot
        or args.focal_lengths_plot
        or args.focal_lengths_full_frame_plot
        or args.exposure_times_plot
        or args.apertures_plot
        or args.isos_plot
        or args.light_values_plot
        or args.crop_factors_plot
        or args.custom_metadata_plot
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
                data.get_metadata(
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
            folder_metadata_raw = data.get_metadata(
                files=(file for file in folder.glob(
                    args.raw_files_glob, case_sensitive=False
                )),
                cache_file=folder / "metadata_raw.json",
                write_cache=args.cache_metadata,
            )
            folder_metadata_edited = data.get_metadata(
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

    common_args = {
        'metadata_lists': metadata_collections,
        'metadata_labels': labels,
        'nan_if_tag_missing': args.use_nan_if_metadata_missing,
    }

    if args.hour_of_day_plot:
        plots.plot_photo_capture_hours_of_day(
            metadata_lists=metadata_collections,
            metadata_labels=labels,
            out_filename=args.hour_of_day_plot,
        )
    if args.focal_lengths_plot:
        plots.plot_metadata(
            tag="EXIF:FocalLength",
            xlabel="Focal length in mm",
            out_filename=args.focal_lengths_plot,
            **common_args,
        )
    if args.focal_lengths_full_frame_plot:
        plots.plot_metadata(
            # tag="EXIF:FocalLengthIn35mmFormat",
            tag="Composite:FocalLength35efl",
            xlabel="Focal length in mm (35 mm equiv.)",
            out_filename=args.focal_lengths_full_frame_plot,
            **common_args,
        )
    if args.exposure_times_plot:
        plots.plot_metadata(
            tag="EXIF:ExposureTime",
            xlabel="Exposure time in seconds",
            out_filename=args.exposure_times_plot,
            log_scale=True,
            x_tick_formatter=plots.fraction_formatter,
            x_tick_params={"labelrotation": 30},
            **common_args,
        )
    if args.apertures_plot:
        plots.plot_metadata(
            tag="EXIF:FNumber",
            xlabel="Aperture",
            out_filename=args.apertures_plot,
            log_scale=True,
            x_tick_formatter=plots.aperture_formatter,
            x_ticks=[1 * 2 ** i for i in range(0, 5, 1)],
            **common_args,
        )
    if args.isos_plot:
        x_tick_formatter = ticker.ScalarFormatter()
        x_tick_formatter.set_scientific(False)
        plots.plot_metadata(
            tag="EXIF:ISO",
            xlabel="ISO",
            out_filename=args.isos_plot,
            log_scale=True,
            x_tick_formatter=x_tick_formatter,
            x_ticks=[100 * 2 ** i for i in range(0, 9, 2)],
            **common_args,
        )
    if args.light_values_plot:
        plots.plot_metadata(
            tag="Composite:LightValue",
            # Def.: https://exiftool.org/TagNames/Composite.html
            # lv = 2 * log2(f_number) - log2(exp_time) - log2(iso/100)
            xlabel="Light Value (EV at ISO 100)",
            out_filename=args.light_values_plot,
            **common_args,
        )
    if args.crop_factors_plot:
        plots.plot_metadata(
            tag="Composite:ScaleFactor35efl",
            xlabel="Scale factor (compared to 35 mm film)",
            out_filename=args.crop_factors_plot,
            **common_args,
        )
    if args.custom_metadata_plot:
        for out_file, tag, xlabel in zip(
            args.custom_metadata_plot,
            args.custom_metadata_plot_tag,
            args.custom_metadata_plot_axis_label
        ):
            plots.plot_metadata(
                tag=tag,
                xlabel=xlabel,
                out_filename=out_file,
                **common_args,
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
        sorted(data.collect_file_stats(files=files_collection))
        for files_collection in files_collections
    ]

    if args.delta_plot:
        plots.plot_time_between_photos(
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
            data.get_sessions_from_time_series(
                timestamps_sec=mtimes_collection,
                min_break_between_sessions_sec=60 * 30,
            )
            for mtimes_collection in mtimes_collections
        ]
        plots.plot_sessions(
            sessions_list=sessions_collections,
            sessions_labels=(
                args.folder_comparison_labels
                if args.compare_folders
                else ["Photo shoot sessions", "Editing sessions"]
            ),
            out_filename=args.sessions_plot,
            show_info_text=True,
        )


def validate_args(args: argparse.Namespace):
    if (
        args.compare_folders
        and len(args.folders) != len(args.folder_comparison_labels)
    ):
        raise ValueError(
            "When using --compare-folders, "
            "--folder-comparison-labels must have the same number of "
            "arguments as there are folders."
        )

    if (
        args.custom_metadata_plot
        or args.custom_metadata_plot_tag
        or args.custom_metadata_plot_axis_label
    ):
        if not (
            args.custom_metadata_plot
            and args.custom_metadata_plot_tag
            and args.custom_metadata_plot_axis_label
        ):
            raise ValueError(
                "The arguments --custom-metadata-plot, "
                "--custom-metadata-plot-tag, and "
                "--custom-metadata-plot-axis-label must be used "
                "in conjunction."
            )
        if not (
            len(args.custom_metadata_plot)
            == len(args.custom_metadata_plot_tag)
            == len(args.custom_metadata_plot_axis_label)
        ):
            raise ValueError(
                "The arguments --custom-metadata-plot, "
                "--custom-metadata-plot-tag, and "
                "--custom-metadata-plot-axis-label must have the same "
                "number of values."
            )

    for folder in args.folders:
        if not folder.exists():
            raise ValueError(
                f"The provided folder does not seem to exist: "
                f"{folder}"
            )
