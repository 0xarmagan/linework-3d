#!/bin/bash
# Grain + encode the EEZ 360 void variant.
#
# One render pass only: frames_360_rgba (film_transparent, no floor).
#   MP4  = that pass composited over #000000, so black is TRUE black rather
#          than a rendered near-black.
#   WebM = that pass with its alpha preserved.
set -euo pipefail
cd "$(dirname "$0")"
OUT=out
FPS=30
SRC="$OUT/frames_360_rgba"

echo "=== grain (static plate, darkening-only, alpha untouched) ==="
python3 grain.py "$SRC"

echo "=== encode H.264 MP4, composited over #000000 ==="
ffmpeg -y -loglevel error \
  -f lavfi -i "color=c=black:s=2400x2400:r=$FPS" \
  -framerate $FPS -i "$SRC/f_%04d.png" \
  -filter_complex "[0:v][1:v]overlay=shortest=1,format=yuv420p" \
  -c:v libx264 -preset slow -crf 16 -movflags +faststart \
  "$OUT/eez_linework_360_black.mp4"

echo "=== encode VP9 WebM (alpha preserved) ==="
# -auto-alt-ref 0 is mandatory: VP9 alt-ref frames silently discard the alpha
# plane, which yields a black background instead of a transparent one.
ffmpeg -y -loglevel error -framerate $FPS -i "$SRC/f_%04d.png" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 24 \
  -auto-alt-ref 0 -row-mt 1 "$OUT/eez_linework_360.webm"

echo "=== verify ==="
for f in "$OUT/eez_linework_360_black.mp4" "$OUT/eez_linework_360.webm"; do
  printf '%s\n' "$f"
  ffprobe -v error -select_streams v:0 -count_frames \
    -show_entries stream=codec_name,pix_fmt,width,height,nb_read_frames,r_frame_rate \
    -show_entries stream_tags=alpha_mode -show_entries format=duration \
    -of default=nw=1 "$f" | sed 's/^/    /'
  printf '    size=%s\n' "$(du -h "$f" | cut -f1)"
done
