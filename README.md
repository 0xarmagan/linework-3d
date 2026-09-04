# eez-logo-3d-lines

Logo-faithful 3D animation of the EEZ mark, built headlessly in Blender. The mesh **is** the logo's linework — the SVG path filled with its counters and extruded into square-profile beams (1.2× measured stroke width), so the negative space is real and the front-on pose is an exact replica of the flat mark (silhouette IoU 99.723% vs the rastered SVG, verified orthographically).

## Deliverables (`out/`)

| file | motion | scene |
|---|---|---|
| `eez_linework_swing.mp4` / `.webm` (transparent) | ±45° pendulum swing — mark legible every frame | royal blue, grid, floor reflection |
| `eez_linework_360_black.mp4` / `eez_linework_360.webm` (transparent) | full 360° turn — edge-on "blade flash" ~1s twice/turn | pure black, floating |

All loops: 8 s / 240 frames / 30 fps / 2400×2400, seamless (0-pixel seam, driver-exact endpoints). WebMs carry VP9 out-of-band alpha (`alpha_mode=1`) — background swaps are a composite, not a re-render.

**Use the swing variant for brand surfaces** (identity never leaves the screen); the 360° is for ambient/backdrop use.

## Palette

Object gradient `#A8FF78` → `#00F2FE` → `#4A00E0` on a 5-stop object-space ramp (pure emission, no lights, so hexes can't drift); background `#2A1FA8` (swing variant only); darkening-only grain so the palette audits exactly.

## Pipeline

- `build_lines_3d.py` — full scene build + animation drivers + rendering (Blender headless, `bpy`)
- `fidelity.py` — orthographic silhouette IoU gate vs the source SVG
- `palette_audit.py` — per-band hex audit of rendered frames
- `grain.py` — static grain plate
- `encode.sh` / `encode_360.sh` — ffmpeg: H.264 MP4, VP9 alpha WebM (`-auto-alt-ref 0`), black composite
- `out/eez_lines_3d_{swing,360}.blend` — saved scenes
- Source mark: `eez-mark-gradient-transparent.svg`

Intermediate frame directories (`out/frames_*`) are gitignored; regenerate via the build script (~32 min).
