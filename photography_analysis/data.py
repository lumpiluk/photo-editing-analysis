from typing import Generator, Iterable

import json
import os
import pathlib

import exiftool


def collect_file_stats(
    files: Iterable[pathlib.Path],
) -> Generator[float]:
    """Return the file modification times in unix seconds."""
    for file in files:
        stat = os.stat(file)
        yield stat.st_mtime


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


