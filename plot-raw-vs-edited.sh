#!/usr/bin/env bash

out_folder=2025-09-27
mkdir -p "$out_folder"
poetry run ./analysis.py \
    --delta-plot "$out_folder/delta.pdf" \
    --sessions-plot "$out_folder/sessions.pdf" \
    --hour-of-day-plot "$out_folder/hour-of-day.pdf" \
    --focal-lengths-plot "$out_folder/focal-lengths.pdf" \
    --exposure-times-plot "$out_folder/exposure-times.pdf" \
    --apertures-plot "$out_folder/apertures.pdf" \
    --isos-plot "$out_folder/isos.pdf" \
    --cache-metadata \
    --raw-files-glob '*.CR3' \
    --edited-files-glob 'converted*/*.jpg' \
    /mnt/nfs/pictures/2025-09-27_all*

cd "$out_folder"
mogrify -format 'png' -density 300 -- *.pdf
