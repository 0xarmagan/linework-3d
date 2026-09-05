#!/bin/bash
# Grain + encode the v3 gem 360 loop.
#   void  : one alpha pass -> transparent WebM, and an MP4 composited over #000000
#   studio: one opaque pass -> MP4
# v1 and v2 outputs are never touched.
set -euo pipefail
cd "$(dirname "$0")"
OUT=out/v3b_2400
FPS=30
V="$OUT/frames_gem_void_rgba"
S="$OUT/frames_gem_studio_rgb"

echo "=== grain: void alpha pass ==="
python3 grain.py "$V"

echo "=== encode void MP4, composited over #000000 ==="
ffmpeg -y -loglevel error \
  -f lavfi -i "color=c=black:s=2400x2400:r=$FPS" \
  -framerate $FPS -i "$V/f_%04d.png" \
  -filter_complex "[0:v][1:v]overlay=shortest=1,format=yuv420p" \
  -c:v libx264 -preset slow -crf 16 -movflags +faststart \
  "out/eez_gem_360_black.mp4"

echo "=== encode void WebM (alpha preserved) ==="
# -auto-alt-ref 0 is mandatory: VP9 alt-ref frames silently drop the alpha
# plane, giving a black background instead of a transparent one.
ffmpeg -y -loglevel error -framerate $FPS -i "$V/f_%04d.png" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 24 \
  -auto-alt-ref 0 -row-mt 1 "out/eez_gem_360.webm"

if [ -d "$S" ]; then
  echo "=== grain: studio pass ==="
  python3 grain.py "$S"
  echo "=== encode studio MP4 ==="
  ffmpeg -y -loglevel error -framerate $FPS -i "$S/f_%04d.png" \
    -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
    -movflags +faststart "out/eez_gem_360_studio.mp4"
fi

echo "=== verify ==="
for f in out/eez_gem_360_black.mp4 out/eez_gem_360.webm out/eez_gem_360_studio.mp4; do
  [ -f "$f" ] || continue
  printf '%s\n' "$f"
  ffprobe -v error -select_streams v:0 -count_frames \
    -show_entries stream=codec_name,pix_fmt,width,height,nb_read_frames,r_frame_rate \
    -show_entries stream_tags=alpha_mode -show_entries format=duration \
    -of default=nw=1 "$f" | sed 's/^/    /'
  printf '    size=%s\n' "$(du -h "$f" | cut -f1)"
done
