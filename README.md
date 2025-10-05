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
- [Exiftool](https://exiftool.org/)

Clone this repository, then:
```bash
# Create a virtual environment and activate it:
python -m venv .venv
source .venv/bin/activate

# Install this package into the virtual environment:
# (For development: `pip install -e .`)
pip install .

# Test it:
analyze-photos -h
```

## Generating Plots

First you should decide if you want to compare your raw files with your edited files in each plot, aggregated over all folders, or if you want to compare each folder.
You can switch to the latter behavior by using the `--compare-folders` argument.

Have a look at the examples in `plot-folder-comparison.sh` and `plot-raw-vs-edited.sh` and adjust the paths as needed.

### Examples

Compare the time difference between each photo that you shot versus each photo that you edited, based on the file modification timestamps.

```bash
analyze-photos \
    --raw-files-glob '*.CR3' \
    --edited-files-glob 'converted*/*.jpg' \
    --delta-plot 'delta_raw-vs-jpg.pdf' \
    /path/to/images/2025-09-20 /path/to/images/2025-10-*
```

![ECDF plot of delta times between raw and edited photos](examples/delta_raw-vs-jpg.png)
