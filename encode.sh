#!/bin/bash
# Grain + encode the 3D swing loop.  (NAME env var sets output basename)
#
#   ./encode.sh
#
# Expects out/frames_rgb/  (opaque, background + floor)  -> H.264 MP4
#     and out/frames_rgba/ (film_transparent, no floor)  -> VP9 WebM with alpha
#
# Grain runs before encoding, from a single static plate, so it is identical on
# every frame and cannot crawl. It is a darkening-only scalar gain applied
# equally to R/G/B, so it preserves hue and leaves alpha untouched.

set -euo pipefail
cd "$(dirname "$0")"
OUT=out
NAME="${NAME:-eez_linework}"
FPS=30

echo "=== grain: opaque pass ==="
python3 grain.py "$OUT/frames_rgb"
echo "=== grain: alpha pass ==="
python3 grain.py "$OUT/frames_rgba"

echo "=== encode H.264 MP4 ==="
# yuv420p + even dimensions for universal playback; crf 16 keeps the flat
# brand fields free of banding, which low bitrates destroy on gradients.
ffmpeg -y -loglevel error -framerate $FPS -i "$OUT/frames_rgb/f_%04d.png" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
  -movflags +faststart "$OUT/${NAME}_swing.mp4"

echo "=== encode VP9 WebM (alpha) ==="
# -auto-alt-ref 0 is required: VP9 alt-ref frames silently discard the alpha
# plane, which yields a black background instead of a transparent one.
ffmpeg -y -loglevel error -framerate $FPS -i "$OUT/frames_rgba/f_%04d.png" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 24 \
  -auto-alt-ref 0 -row-mt 1 "$OUT/${NAME}_swing.webm"

echo "=== verify ==="
for f in "$OUT/${NAME}_swing.mp4" "$OUT/${NAME}_swing.webm"; do
  printf '%s\n' "$f"
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,pix_fmt,width,height,nb_read_frames,r_frame_rate \
    -count_frames -of default=nw=1 "$f" | sed 's/^/    /'
  printf '    size=%s\n' "$(du -h "$f" | cut -f1)"
done
