# linework-3d

Turn a flat line-art SVG logo into a seamless 3D animation loop — headless Blender. The mesh **is** the linework (path filled with counters, extruded to square beams), and a fidelity gate keeps the front-on pose an exact replica of the mark (silhouette IoU ≥ 99% vs the rastered SVG).

Input: a single-path stroke-outline SVG. Example output in `examples/eez/` (8 s / 240 f / 2400², bit-identical seam, IoU 99.723%): `eez_linework_swing.*` (±45° swing, brand scene) and `eez_linework_360*` (full turn on black).

**Swing vs spin:** a flat mark disappears edge-on — structural, not tunable. Use `--motion swing` for brand assets (identity in every frame); `--motion spin` only for ambient loops.

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
