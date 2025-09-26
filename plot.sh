#!/usr/bin/env bash

out_folder=2025-09-20
mkdir -p "$out_folder"
poetry run ./analysis.py \
    --delta-plot "$out_folder/delta.pdf" \
    --sessions-plot "$out_folder/sessions.pdf" \
    --focal-lengths-plot "$out_folder/focal-lengths.pdf" \
    --exposure-times-plot "$out_folder/exposure-times.pdf" \
    --apertures-plot "$out_folder/apertures.pdf" \
    --isos-plot "$out_folder/isos.pdf" \
    /mnt/nfs/pictures/2025-09-20_fff_exit-gas-enter-future_draw-the-line

cd "$out_folder"
mogrify -format 'png' -density 300 -- *.pdf
