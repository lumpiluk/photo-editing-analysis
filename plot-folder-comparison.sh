#!/usr/bin/env bash

out_folder=2025-02-14_vs_2025-05-17_vs_2025-09-20_edited
mkdir -p "$out_folder"
poetry run ./analysis.py \
    --delta-plot "$out_folder/delta.pdf" \
    --sessions-plot "$out_folder/sessions.pdf" \
    --focal-lengths-plot "$out_folder/focal-lengths.pdf" \
    --exposure-times-plot "$out_folder/exposure-times.pdf" \
    --apertures-plot "$out_folder/apertures.pdf" \
    --isos-plot "$out_folder/isos.pdf" \
    --cache-metadata \
    --folder-comparison-labels "2025-02-14" "2025-05-17" "2025-09-20" \
    --compare-folders edited \
    /mnt/nfs/pictures/{2025-02-14*,2025-05-17*,2025-09-20*}

cd "$out_folder"
mogrify -format 'png' -density 300 -- *.pdf
