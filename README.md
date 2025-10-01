# Empirical Analysis of Your Photography Habits

This project allows you to analyze one or multiple of your photo folders and generate plots for the following metrics:
- Time between photos
- Session duration
- Number of photos by hour of day
- Focal lengths
- Aperture values
- ISO values
- Exposure times

## Installation

Prerequisites:
- [Python](https://www.python.org/)
- [Poetry](https://python-poetry.org/)
- [Exiftool](https://exiftool.org/)

Clone this repository, then:
```bash
poetry install
poetry run ./analysis.py --help
```

## Generating Plots

First you should decide if you want to compare your raw files with your edited files in each plot, aggregated over all folders, or if you want to compare each folder.
You can switch to the latter behavior by using the `--compare-folders` argument.

Have a look at the examples in `plot-folder-comparison.sh` and `plot-raw-vs-edited.sh` and adjust the paths as needed.
