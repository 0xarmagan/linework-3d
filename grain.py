"""Film-grain + stipple post-pass for the EEZ 3D loop.

  python3 grain.py <file-or-dir> [--strength 0.30] [--stipple 0.55] [--seed N]

Blender 5.x moved the scene compositor to a node group whose graph rendered
black here, so the grain runs as a deterministic post-pass instead. One plate
is generated per resolution and applied identically to every frame, which is
what keeps the grain from crawling — a per-frame random plate would shimmer.

The grain is a darkening-only scalar gain applied equally to R, G and B, so it
preserves hue exactly and cannot push a channel up into clipping.

RGB is grained; alpha is passed through untouched so the transparent WebM
keeps a clean matte.
"""

import os
import random
import sys

from PIL import Image, ImageChops

STRENGTH = 0.16      # overall grain weight
STIPPLE = 0.35       # share of the plate that is coarse (2px) stipple vs fine
SEED = 20260904

_plates = {}


def plate(size, stipple, seed):
    """Static grey noise plate, cached per (size, params) so it is reused."""
    key = (size, round(stipple, 4), seed)
    if key in _plates:
        return _plates[key]
    w, h = size
    rnd = random.Random(seed)

    fine = Image.new("L", (w, h))
    fine.putdata([rnd.randint(0, 255) for _ in range(w * h)])

    # coarse layer: half-res noise scaled up, giving the reference's chunkier
    # stipple alongside the fine film grain
    cw, ch = max(1, w // 2), max(1, h // 2)
    coarse = Image.new("L", (cw, ch))
    coarse.putdata([rnd.randint(0, 255) for _ in range(cw * ch)])
    coarse = coarse.resize((w, h), Image.NEAREST)

    mix = Image.blend(fine, coarse, stipple)
    _plates[key] = mix
    return mix


def gain_map(plate_img, strength):
    """Per-pixel scalar gain in [1-strength, 1] from the plate.

    Darkening only, and the SAME gain on all three channels. That matters for
    the palette audit: scaling R, G and B by one scalar is exactly "shading
    toward near-black", so it cannot move a pixel off a brand ramp stop, and
    it cannot clip a channel upward the way an OVERLAY blend can.
    """
    lo = 1.0 - strength
    return plate_img.point(lambda v: int(round((lo + (v / 255.0) * strength) * 255)))


def apply_grain(path, strength=STRENGTH, stipple=STIPPLE, seed=SEED):
    im = Image.open(path)
    has_alpha = im.mode in ("RGBA", "LA")
    alpha = im.getchannel("A") if has_alpha else None
    rgb = im.convert("RGB")

    g = gain_map(plate(rgb.size, stipple, seed), strength)
    r, gr, b = rgb.split()
    out = Image.merge("RGB", (ImageChops.multiply(r, g),
                              ImageChops.multiply(gr, g),
                              ImageChops.multiply(b, g)))

    if has_alpha:
        out = out.convert("RGBA")
        out.putalpha(alpha)
    out.save(path)
    return path


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    target = args[0]

    def opt(name, default, cast=float):
        return cast(args[args.index(name) + 1]) if name in args else default

    strength = opt("--strength", STRENGTH)
    stipple = opt("--stipple", STIPPLE)
    seed = opt("--seed", SEED, int)

    if os.path.isdir(target):
        files = sorted(f for f in os.listdir(target) if f.lower().endswith(".png"))
        for i, f in enumerate(files):
            apply_grain(os.path.join(target, f), strength, stipple, seed)
            if (i + 1) % 40 == 0 or i + 1 == len(files):
                print("[grain] %d/%d" % (i + 1, len(files)))
    else:
        apply_grain(target, strength, stipple, seed)
        print("[grain] %s" % target)


if __name__ == "__main__":
    main()
