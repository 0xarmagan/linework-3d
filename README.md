# linework-3d

Turn a flat line-art logo (SVG) into a seamless 3D animation loop — headless Blender, no GUI. The mesh **is** the logo's linework: the SVG path is filled with its counters and extruded into square-profile beams, so negative space is real and the front-on pose is an exact replica of the flat mark, enforced by a measured fidelity gate (orthographic silhouette IoU vs the rastered SVG, target ≥ 99%).

Works with any **single-path stroke-outline SVG** (a filled outline of the stroke, counters as sub-paths — the usual export for line-art marks).

## Example — EEZ logo (`examples/eez/`)

| file | motion | scene |
|---|---|---|
| `eez_linework_swing.mp4` / `.webm` (transparent) | ±45° pendulum swing — mark legible every frame | brand blue, grid, floor reflection |
| `eez_linework_360_black.mp4` / `eez_linework_360.webm` | full 360° turn — edge-on collapse ~1 s twice/turn | pure black, floating |

8 s / 240 frames / 30 fps / 2400², bit-identical loop seam, IoU 99.723%.

**Design note baked into the tool:** a flat mark's identity lives in its 2D linework, so a full spin hides it edge-on — that's structural, not tunable. The swing motion (`--motion swing`) keeps identity in every frame; use `--motion spin` only for ambient/backdrop assets where a rhythmic "blade flash" is acceptable.

## Usage

Requires Blender 4.x+ on PATH, Python 3 with Pillow + numpy, ffmpeg.

```bash
# 1. Checkpoint stills (fast): contacts at rest + extremes, fidelity diff, palette audit
blender -b -noaudio --python build_lines_3d.py -- --stage contact \
  --svg path/to/your-mark.svg --palette FFAA00,FF2266,220066 --name mymark

# 2. Full render (~30 min at 2400²)
blender -b -noaudio --python build_lines_3d.py -- --stage anim --motion swing --scene studio \
  --svg path/to/your-mark.svg --palette FFAA00,FF2266,220066 --name mymark

#    or the 360° floating-on-black variant
blender -b -noaudio --python build_lines_3d.py -- --stage anim --motion spin --scene void --bg 000000 ...

# 3. Grain + encode → H.264 MP4 + VP9 alpha WebM
NAME=mymark_linework ./encode.sh        # swing
NAME=mymark_linework ./encode_360.sh    # 360
```

### Options (after `--`)

| flag | default | meaning |
|---|---|---|
| `--svg` | EEZ example mark | source SVG (single path, stroke-outline) |
| `--palette` | `A8FF78,00F2FE,4A00E0` | gradient hex stops, top → mid → bottom |
| `--name` | `eez` | basename for saved `.blend` / logs |
| `--motion` | `swing` | `swing` (±`--swing`°, default 45) or `spin` (360°) |
| `--scene` | `studio` | `studio` (bg + grid + reflection) or `void` (transparent/black float) |
| `--bg` | `2A1FA8` | studio background hex |
| `--line-depth` | 1.2× measured stroke width | beam depth |
| `--res` | `2400` | output resolution |
| `--stage` | `contact` | `contact` (stills only) or `anim` (full render; gated so you can't loop-render by accident) |

### Verify after any change

- `python3 fidelity.py out/fidelity_matte_<tag>.png <svg-raster>.png` — silhouette IoU must stay ≥ 99%
- `PALETTE=<top,mid,bottom> python3 palette_audit.py out/<frame>.png` — hexes must resolve to your stops
- Loop seam: frame 241 must equal frame 1 bit-identically (encode scripts print the diff)

### Compositing the transparent WebM

```bash
ffmpeg -f lavfi -i color=0x101014:s=2400x2400:r=30 -c:v libvpx-vp9 -i out/mymark_linework_swing.webm \
  -filter_complex "[0][1]overlay=shortest=1" -c:v libx264 -crf 18 -pix_fmt yuv420p custom_bg.mp4
```

Decode with `-c:v libvpx-vp9` explicitly — the stock VP9 decoder silently drops the out-of-band alpha.

## How it holds quality

- **Fidelity gate:** ortho silhouette IoU vs the rastered source SVG — "exact replica" is measured, not asserted.
- **Palette welded to geometry:** pure Emission shader, no lights, 5-stop object-space ramp — brand hexes can't drift.
- **Stable grain:** one static darkening-only plate applied identically to every frame — no crawl, no hue shift.
- **Exact loop:** motion is driver-based sinusoids/linear ramps with whole periods over the loop — the seam is exact by construction and verified as a pixel diff.
- **Structural mesh gate:** zero non-manifold edges / self-intersections / degenerate faces, checked every build.
