# linework-3d

Turn a flat line-art SVG logo into a seamless 3D animation loop — headless Blender. The mesh **is** the linework (path filled with counters, extruded to square beams), and a fidelity gate keeps the front-on pose an exact replica of the mark (silhouette IoU ≥ 99% vs the rastered SVG).

Input: a single-path stroke-outline SVG. Two pipelines share the gates (all loops 8 s / 240 f / 2400², bit-identical seam):

- **Linework** (`build_lines_3d.py`) — the stroke ribbon extruded; the logo, animated. Ortho IoU 99.723%.
- **Gem** (`build_v3_solid.py`) — the solid faceted volume the mark depicts: outer contour = silhouette, inner lines = facet creases (curved creases supported), mirrored closed solid. Perspective fidelity 99.807%. No bad angle → full 360° spin.

`examples/eez/`: `eez_linework_swing.*` (v1), `eez_linework_swing_v2.*` (+ dimension stack: shade 0.5, dof f/5.6, contact shadow), `eez_linework_360*` (black), `eez_gem_360_black.mp4` / `eez_gem_360.webm` / `eez_gem_360_studio.mp4`.

**Which variant:** linework swing = brand surfaces (the logo itself, legible every frame); gem 360 = emblem/coin-style stings; linework 360 black = ambient only.

**Swing vs spin (linework):** a flat mark disappears edge-on — structural, not tunable. Use `--motion swing` for brand assets; `--motion spin` only for ambient loops. The gem has no such limit.

Dimension flags (v2 stack): `--shade 0.5` (hue-neutral facet modeling), `--dof 5.6`, `--shadow 0.3`.

## Usage

Needs Blender 4.x+, Python 3 (Pillow, numpy), ffmpeg.

```bash
# checkpoint stills (fast): contacts + fidelity diff + palette audit
blender -b -noaudio --python build_lines_3d.py -- --stage contact \
  --svg your-mark.svg --palette FFAA00,FF2266,220066 --name mymark

# full render (~30 min), then encode → MP4 + alpha WebM
blender -b -noaudio --python build_lines_3d.py -- --stage anim --motion swing [same flags]
NAME=mymark_linework ./encode.sh      # ./encode_360.sh for spin
```

| flag | default | |
|---|---|---|
| `--svg` | EEZ example | source SVG |
| `--palette` | `A8FF78,00F2FE,4A00E0` | gradient hexes, top→mid→bottom |
| `--name` / `--tag` | `eez` / variant | output naming |
| `--motion` / `--swing` | `swing` / `45` | `swing` or `spin` |
| `--scene` / `--bg` | `studio` / `2A1FA8` | `studio` (grid+reflection) or `void` |
| `--line-depth` / `--res` | 1.2× stroke width / `2400` | |

## Verify

- `python3 fidelity.py out/fidelity_matte_<tag>.png <svg-raster>.png` — IoU ≥ 99%
- `PALETTE=top,mid,bottom python3 palette_audit.py out/<frame>.png` — on-palette
- Seam: frame 241 == frame 1 (encode scripts print the diff)

Composite the transparent WebM over anything (decode with `-c:v libvpx-vp9` — the stock decoder drops alpha):

```bash
ffmpeg -f lavfi -i color=0x101014:s=2400x2400:r=30 -c:v libvpx-vp9 -i out/mymark_linework_swing.webm \
  -filter_complex "[0][1]overlay=shortest=1" -c:v libx264 -crf 18 -pix_fmt yuv420p out.mp4
```
