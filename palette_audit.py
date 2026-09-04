"""Palette audit for the EEZ 3D renders.

  python3 palette_audit.py <render.png> --matte <matte.png>

Pixel-picks the object using a white-on-black object matte, reports the
dominant sampled hexes, and tests each against the brand ramp.

The matte is required: selecting "everything unlike the background" instead
pulled in the floor plane, which is background-hued and swamped the histogram
with 23% floor pixels.

The test: the material scales one ramp colour by a single scalar tone, and the
grain applies another single scalar gain to all three channels. So every legal
object pixel must be s * lerp(stop_i, stop_i+1, t) in LINEAR space, for some
s in (0, 1] and some point t on the ramp. For each sampled colour this finds
the best (segment, t, s) and reports the residual as a percentage of the
colour's own magnitude. A small residual means the hue sits on the ramp and
only the brightness moved -- "shading toward near-black". A large residual
means a hue leaked in from somewhere, which is the failure iteration 1 had.
"""

import sys
from collections import Counter

from PIL import Image

import os
_pal = os.environ.get("PALETTE", "A8FF78,00F2FE,4A00E0").split(",")  # top,mid,bottom
LIME, CYAN, INDIGO = _pal
STOPS = [("#%s bottom" % INDIGO, INDIGO), ("#%s mid" % CYAN, CYAN), ("#%s top" % LIME, LIME)]


def to_lin(rgb):
    out = []
    for v in rgb:
        v /= 255.0
        out.append(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4)
    return out


def hexlin(h):
    return to_lin([int(h[i:i + 2], 16) for i in (0, 2, 4)])


def best_fit(c_lin):
    """Best (label, t, s, residual%) over the two ramp segments."""
    best = None
    segs = [(STOPS[0], STOPS[1]), (STOPS[1], STOPS[2])]
    mag = sum(v * v for v in c_lin) ** 0.5
    if mag < 1e-6:
        return ("near-black", 0.0, 0.0, 0.0)
    for (la, ha), (lb, hb) in segs:
        a, b = hexlin(ha), hexlin(hb)
        for i in range(101):
            t = i / 100.0
            r = [a[k] + (b[k] - a[k]) * t for k in range(3)]
            rr = sum(v * v for v in r)
            if rr < 1e-12:
                continue
            s = sum(c_lin[k] * r[k] for k in range(3)) / rr
            if s <= 0:
                continue
            resid = sum((c_lin[k] - s * r[k]) ** 2 for k in range(3)) ** 0.5
            pct = resid / mag * 100.0
            if best is None or pct < best[3]:
                label = la if t < 0.02 else (lb if t > 0.98 else "%s->%s" % (la, lb))
                best = (label, t, s, pct)
    return best


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    path = args[0]
    if "--matte" not in args:
        raise SystemExit("--matte <matte.png> is required")
    matte = Image.open(args[args.index("--matte") + 1]).convert("L")

    im = Image.open(path).convert("RGB")
    w, h = im.size
    if matte.size != (w, h):
        matte = matte.resize((w, h), Image.NEAREST)
    px = im.load()
    mk = matte.load()

    counts = Counter()
    step = max(1, w // 700)
    for y in range(0, h, step):
        for x in range(0, w, step):
            if mk[x, y] < 200:          # only fully-covered object pixels
                continue
            c = px[x, y]
            counts[(c[0] // 6 * 6, c[1] // 6 * 6, c[2] // 6 * 6)] += 1

    total = sum(counts.values())
    if not total:
        print("no object pixels found")
        return
    print("%s  (%d sampled object px)" % (path.split("/")[-1], total))
    print("  %-9s %6s  %-26s %7s %7s" % ("hex", "share", "ramp position", "tone", "resid%"))
    worst = 0.0
    for c, n in counts.most_common(12):
        label, t, s, pct = best_fit(to_lin(c))
        worst = max(worst, pct)
        print("  #%02X%02X%02X %5.1f%%  %-26s %6.2f %6.1f%%"
              % (c[0], c[1], c[2], n / total * 100, label, s, pct))
    print("  worst residual among reported colours: %.1f%%" % worst)

    # --- per-band read: is each of the three stops actually visible at 0 deg?
    ys = [y for y in range(0, h, step)
          for x in range(0, w, step) if mk[x, y] >= 200]
    y0, y1 = min(ys), max(ys)
    print("  band report (object spans y %d..%d):" % (y0, y1))
    for name, lo, hi in (("upper third", 0.00, 0.33),
                         ("middle third", 0.33, 0.66),
                         ("lower third", 0.66, 1.00)):
        band = Counter()
        for y in range(int(y0 + (y1 - y0) * lo), int(y0 + (y1 - y0) * hi), step):
            for x in range(0, w, step):
                if mk[x, y] < 200:
                    continue
                c = px[x, y]
                band[(c[0] // 6 * 6, c[1] // 6 * 6, c[2] // 6 * 6)] += 1
        if not band:
            continue
        # brightest colour in the band is the one carrying that stop's identity
        bright = max(band, key=lambda c: sum(c))
        modal = band.most_common(1)[0][0]
        lb, _, sb, pb = best_fit(to_lin(bright))
        lm, _, sm_, pm = best_fit(to_lin(modal))
        print("    %-13s brightest #%02X%02X%02X -> %-26s (tone %.2f, resid %.1f%%)"
              % (name, bright[0], bright[1], bright[2], lb, sb, pb))
        print("    %-13s modal     #%02X%02X%02X -> %-26s (tone %.2f, resid %.1f%%)"
              % ("", modal[0], modal[1], modal[2], lm, sm_, pm))

    # --- explicit check for iteration 1's failure signature.
    # That failure was emission stacked on diffuse clipping BOTH R and G to
    # 255 while B trailed, giving cream. The test is two clipped channels --
    # not "R and G high", which #A8FF78 lime (168,255,120) trips by itself.
    yellowish = sum(n for c, n in counts.items()
                    if c[0] >= 250 and c[1] >= 250 and c[2] < 235)
    maxch = (max(c[0] for c in counts), max(c[1] for c in counts),
             max(c[2] for c in counts))
    print("  peak channel values R/G/B: %d/%d/%d (255 on two = clipping)" % maxch)
    offpal = 0
    for c, n in counts.items():
        if best_fit(to_lin(c))[3] > 8.0:
            offpal += n
    print("  clipped-cream signature px (R>=250 G>=250 B<235): %d (%.3f%%)"
          % (yellowish, yellowish / total * 100))
    print("  off-ramp px (residual > 8%%): %d (%.3f%%)" % (offpal, offpal / total * 100))
    ok = worst < 8.0 and yellowish == 0 and offpal / total < 0.005
    print("  VERDICT: %s" % ("ON-PALETTE (hue on the ramp, brightness only)" if ok
                             else "OFF-PALETTE — a foreign hue leaked in"))


if __name__ == "__main__":
    main()
