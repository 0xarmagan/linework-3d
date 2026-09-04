"""Fidelity gate: is the 3D linework's silhouette the SVG?

  python3 fidelity.py out/fidelity_matte.png out/svg_reference_2400.png

Compares an orthographic, front-on, alpha-only matte of the 3D object against
an independent raster of the source SVG, and writes an overlay diff.

Method
  * The matte's mask is its alpha channel. The SVG raster from qlmanage has an
    opaque white ground, so its mask is "not near-white".
  * Both masks are cropped to their own tight bounding box and resampled to a
    common size before comparison. That makes this a test of SHAPE -- which is
    what "no redrawing, no simplification that rounds or moves corners" is
    about -- and removes camera framing and raster padding as sources of a
    false failure. Placement is already exact by construction: the ortho camera
    frames a known square centred on the origin.
  * Reported as intersection-over-union, plus which side each disagreeing
    pixel came from, so a systematic shrink (bevel eating corners) is
    distinguishable from a systematic bulge.

Overlay legend in the diff image
  white   = both agree (inside the mark)
  green   = 3D only  (mesh bulges past the SVG)
  magenta = SVG only (mesh is missing coverage)
"""

import sys

from PIL import Image

WHITE_CUT = 235      # SVG raster ground is pure white


def coverage_from_matte(path):
    """Antialiased coverage 0-255 from the render's alpha channel."""
    im = Image.open(path)
    if im.mode in ("RGBA", "LA"):
        return im.convert("RGBA").getchannel("A")
    return im.convert("L")


def coverage_from_svg_raster(path):
    """Antialiased coverage from a BLACK-on-white raster: 255 - luminance.

    A gradient-filled reference cannot be used here -- treating any non-white
    pixel as ink is an ~8%-coverage threshold against the matte's 50%, which
    dilates the reference by ~0.5px around a ~19,700px perimeter.
    """
    from PIL import ImageChops
    g = Image.open(path).convert("L")
    return ImageChops.invert(g)


def binarize(cov):
    return cov.point(lambda v: 255 if v >= 128 else 0).convert("L")


def tight(cov):
    bb = binarize(cov).getbbox()
    if bb is None:
        raise SystemExit("mask is empty")
    return cov.crop(bb), bb


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    matte_path, svg_path = sys.argv[1], sys.argv[2]

    a_cov, abb = tight(coverage_from_matte(matte_path))
    b_cov, bbb = tight(coverage_from_svg_raster(svg_path))

    # Resample COVERAGE (not the binary mask) onto a common grid with an area
    # filter, then threshold. Binarising first and upscaling with NEAREST
    # quantised the lower-resolution side and cost ~1px of apparent error.
    W = min(a_cov.width, b_cov.width)
    H = min(a_cov.height, b_cov.height)
    a = binarize(a_cov.resize((W, H), Image.BOX))
    b = binarize(b_cov.resize((W, H), Image.BOX))

    from PIL import ImageChops
    # Vectorised in C: a pure-Python per-pixel loop over 5.76M px was the
    # bottleneck in the parameter sweep.
    def count(m):
        return sum(n for v, n in enumerate(m.histogram()) if v > 127)

    inter_img = ImageChops.darker(a, b)
    union_img = ImageChops.lighter(a, b)
    onlya_img = ImageChops.subtract(a, b)
    onlyb_img = ImageChops.subtract(b, a)
    inter = count(inter_img)
    union = count(union_img)
    only_a = count(onlya_img)
    only_b = count(onlyb_img)
    if not union:
        raise SystemExit("empty union -- one of the masks is blank")
    iou = inter / union * 100.0

    print("fidelity: 3D silhouette vs SVG raster")
    print("  matte  %s  bbox %s  -> %dx%d" % (matte_path.split("/")[-1], abb, a.width, a.height))
    print("  svg    %s  bbox %s" % (svg_path.split("/")[-1], bbb))
    print("  compare grid ......... %dx%d" % (W, H))
    print("  intersection ......... %d px" % inter)
    print("  3D only (bulge) ...... %d px  (%.3f%% of union)" % (only_a, only_a / union * 100))
    print("  SVG only (missing) ... %d px  (%.3f%% of union)" % (only_b, only_b / union * 100))
    print("  IoU .................. %.3f%%" % iou)
    print("  aspect: 3D %.5f  SVG %.5f  (delta %.4f%%)"
          % (a.width / a.height, (bbb[2] - bbb[0]) / (bbb[3] - bbb[1]),
             abs(a.width / a.height - (bbb[2] - bbb[0]) / (bbb[3] - bbb[1]))
             / (a.width / a.height) * 100))
    print("  VERDICT: %s (target >= 99%%)"
          % ("PASS" if iou >= 99.0 else "FAIL"))

    # overlay diff, composed from the three masks
    from PIL import ImageChops as _IC
    both = _IC.darker(a, b)
    r = _IC.lighter(both, _IC.multiply(onlyb_img, Image.new("L", (W, H), 255)))
    g = _IC.lighter(both, onlya_img)
    bl = _IC.lighter(both, onlyb_img)
    out = Image.merge("RGB", (r, g, bl))
    dest = "/".join(matte_path.split("/")[:-1] + ["fidelity_diff.png"])
    out.save(dest)
    print("  overlay -> %s" % dest)


if __name__ == "__main__":
    main()
