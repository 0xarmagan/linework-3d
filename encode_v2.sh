#!/bin/bash
# Grain + encode the v2 swing loop (shade 0.5 / dof f5.6 / shadow 0.3).
# Reads out/frames_v2_rgb (opaque) and out/frames_v2_rgba (alpha).
# v1 outputs and frame dirs are never touched.
set -euo pipefail
cd "$(dirname "$0")"
OUT=out
FPS=30

echo "=== grain: opaque pass ==="
python3 grain.py "$OUT/frames_v2_rgb"
echo "=== grain: alpha pass ==="
python3 grain.py "$OUT/frames_v2_rgba"

echo "=== encode H.264 MP4 ==="
ffmpeg -y -loglevel error -framerate $FPS -i "$OUT/frames_v2_rgb/f_%04d.png" \
  -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p \
  -movflags +faststart "$OUT/eez_linework_swing_v2.mp4"

echo "=== encode VP9 WebM (alpha) ==="
# -auto-alt-ref 0 is mandatory: VP9 alt-ref frames silently drop the alpha
# plane, producing a black background instead of a transparent one.
ffmpeg -y -loglevel error -framerate $FPS -i "$OUT/frames_v2_rgba/f_%04d.png" \
  -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 24 \
  -auto-alt-ref 0 -row-mt 1 "$OUT/eez_linework_swing_v2.webm"

echo "=== mid-loop still (frame 121, already graded and grained) ==="
cp "$OUT/frames_v2_rgb/f_0121.png" "$OUT/still_v2_midloop_f121.png"

echo "=== verify ==="
for f in "$OUT/eez_linework_swing_v2.mp4" "$OUT/eez_linework_swing_v2.webm"; do
  printf '%s\n' "$f"
  ffprobe -v error -select_streams v:0 -count_frames \
    -show_entries stream=codec_name,pix_fmt,width,height,nb_read_frames,r_frame_rate \
    -show_entries stream_tags=alpha_mode -show_entries format=duration \
    -of default=nw=1 "$f" | sed 's/^/    /'
  printf '    size=%s\n' "$(du -h "$f" | cut -f1)"
done
