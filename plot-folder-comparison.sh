#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

out_folder=2025-02-14_vs_2025-05-17_vs_2025-09-20_edited
mkdir -p "$out_folder"
poetry run ./analysis.py \
    --delta-plot "$out_folder/delta.pdf" \
    --sessions-plot "$out_folder/sessions.pdf" \
    --hour-of-day-plot "$out_folder/hour-of-day.pdf" \
    --focal-lengths-plot "$out_folder/focal-lengths.pdf" \
    --exposure-times-plot "$out_folder/exposure-times.pdf" \
    --apertures-plot "$out_folder/apertures.pdf" \
    --isos-plot "$out_folder/isos.pdf" \
    --light-values-plot "$out_folder/light-values.pdf" \
    --cache-metadata \
    --folder-comparison-labels 2025-02-14 2025-05-17 2025-09-20 \
    --compare-folders edited \
    --raw-files-glob '*.CR3' \
    --edited-files-glob 'converted*/*.jpg' \
    /mnt/nfs/pictures/{2025-02-14*,2025-05-17*,2025-09-20*}

cd "$out_folder"
mogrify -format 'png' -density 300 -- *.pdf
