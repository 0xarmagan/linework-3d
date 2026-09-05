"""
EEZ mark as THE SOLID IT DEPICTS — v3 iteration 2 (corrected boundary).

  blender -b -noaudio --python build_v3_solid.py -- [options]

  --bow F        swoosh-patch bow as a fraction of mark height (0.02 | 0.05)
  --scene S      studio | void
  --res N        square resolution (default 1600)
  --stage S      stills | matte | flatref
  --label NAME   output tag

CORRECTED READING (iteration 1 got this wrong; the overlay diff proved it).
The mark's outer contour FOLLOWS THE SWOOSH -- it does not run straight along
the bottom. So the swoosh is a curved SILHOUETTE edge, not an internal crease,
and the upper half has 3 facets, not 4:

  upper boundary : A -> L -> M -> [swoosh M->J] -> J -> R -> A
  upper chords   : A-J and J-L        =>  3 facets
      (A,J,L)  (J,L,M+swoosh)  (A,J,R)
  lower boundary : L' -> A' -> R' -> [swoosh R'->J'] -> J' -> L'
  lower chord    : J'-A'               =>  2 facets
      (L',A',J')  (J',A',R'+swoosh)

CONSEQUENCE OF THE CORRECTION: every vertex now lies ON the boundary, so a
flat-faceted front surface would be planar and show no creases whatsoever. The
creases must therefore be bowed ridges -- which is what --bow controls, and why
the two readings are curvature readings rather than vertex-position readings.

Ridges bow 1.6x the patches so the mark's lines stand proud of the fields.

CLOSURE: the silhouette ring is planar at y=0, and the back shell is the front
shell mirrored through it, sharing the ring. That makes a symmetric gem with
zero boundary edges, and the ring's projection is the mark's outline exactly.
"""

import bpy
import bmesh
import functools
import math
import os
import sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


print = functools.partial(print, flush=True)


def arg(n, d):
    return argv[argv.index(n) + 1] if n in argv else d


BOW = float(arg("--bow", "0.05"))
SCENE_MODE = arg("--scene", "studio")
RES = int(arg("--res", "1600"))
STAGE = arg("--stage", "stills")
LABEL = arg("--label", "bow%02d" % round(BOW * 100))
RUN_TAG = arg("--run-tag", "gem")

HERE = os.path.dirname(os.path.abspath(__file__)) or "."
OUT = os.path.join(HERE, "out", "v3b_%d" % RES)
os.makedirs(OUT, exist_ok=True)

LIME, CYAN, INDIGO = "A8FF78", "00F2FE", "4A00E0"
BG_HEX = "2A1FA8"
MARK_W, MARK_H = 1.3935, 2.1991
STROKE_W = 0.07243
CAM_POS = Vector((0.0, -8.9, 0.72))
FPS, LOOP_FRAMES = 30, 240
TONE_MIN, SHADE, DOF_FSTOP, SHADOW = 0.34, 0.5, 5.6, 0.3
BOW_P = BOW * MARK_H              # patch bow, world units
BOW_R = BOW_P * 1.6               # ridge bow
CHORD_SEG = 10


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c]
    return (lin[0], lin[1], lin[2], 1.0)


def Wp(nx, ny):
    return Vector(((nx - 0.5) * MARK_W, 0.0, (0.5 - ny) * MARK_H))


def bez(p0, p1, p2, p3, n):
    o = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        o.append((u**3*p0[0] + 3*u*u*t*p1[0] + 3*u*t*t*p2[0] + t**3*p3[0],
                  u**3*p0[1] + 3*u*u*t*p1[1] + 3*u*t*t*p2[1] + t**3*p3[1]))
    return o


A  = (0.475, 0.005); L  = (0.020, 0.395); M  = (0.320, 0.565)
R  = (0.955, 0.505); J  = (0.495, 0.305)
Lp = (0.105, 0.605); Ap = (0.475, 1.000); Rp = (0.965, 0.605); Jp = (0.435, 0.735)
SW_U = bez(M, (0.430, 0.520), (0.492, 0.410), J, 14)     # swoosh M -> J
SW_L = bez(Rp, (0.760, 0.650), (0.570, 0.700), Jp, 14)   # swoosh R' -> J'

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = scene.render.resolution_y = RES
scene.render.fps = FPS
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.eevee.taa_render_samples = 128
scene.eevee.use_raytracing = True


def link(o):
    bpy.context.collection.objects.link(o)
    return o


def ray_push(p, d):
    """move p along its rest-camera ray by d (+ = away from camera)."""
    if abs(d) < 1e-12:
        return p.copy()
    v = p - CAM_POS
    return CAM_POS + v * (1.0 + d / v.length)


def offset_ring(ring2, t):
    """Push a closed centreline polygon outward by t, onto the mark's contour.

    Offsets each vertex along its angle bisector with a miter limit. The first
    attempt intersected consecutive offset EDGE lines, which is unstable when
    consecutive edges are near-collinear -- the swoosh contributes 13 samples
    with tiny turn angles, the determinant went to ~0, and vertices were flung
    to astronomical coordinates, which hung the render with no output at all.
    """
    pts = [Wp(*p) for p in ring2]
    n = len(pts)
    ar = sum(pts[i].x * pts[(i+1) % n].z - pts[(i+1) % n].x * pts[i].z
             for i in range(n))
    s = 1.0 if ar > 0 else -1.0

    def edge_n(a, b):
        d = b - a
        ln = math.hypot(d.x, d.z) or 1e-9
        return Vector((d.z / ln * s, 0.0, -d.x / ln * s))

    out = []
    for i in range(n):
        np_ = edge_n(pts[i - 1], pts[i])
        nn_ = edge_n(pts[i], pts[(i + 1) % n])
        bis = np_ + nn_
        if bis.length < 1e-9:
            bis = nn_.copy()
        bis.normalize()
        cosh = max(bis.dot(nn_), 0.5)          # miter limit: never exceed 2x t
        out.append(pts[i] + bis * (t / cosh))
    return out


# ---------------------------------------------------------------- flat reference
if STAGE == "flatref":
    SVG = os.path.join(HERE, "eez-mark-gradient-transparent.svg")
    bpy.ops.import_curve.svg(filepath=SVG)
    cs = [o for o in bpy.data.objects if o.type == "CURVE"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in cs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = cs[0]
    if len(cs) > 1:
        bpy.ops.object.join()
    cu = bpy.context.view_layer.objects.active
    areas = []
    for i, sp in enumerate(cu.data.splines):
        ps = sp.bezier_points if sp.type == "BEZIER" else sp.points
        n = len(ps)
        a = sum(ps[k].co[0]*ps[(k+1) % n].co[1] - ps[(k+1) % n].co[0]*ps[k].co[1]
                for k in range(n))
        areas.append((abs(a), i))
    keep = max(areas)[1]
    for sp in [sp for i, sp in enumerate(cu.data.splines) if i != keep]:
        cu.data.splines.remove(sp)          # outer contour only -> filled region
    cu.data.fill_mode = "FRONT"
    cu.data.resolution_u = 8
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    sc = MARK_H / (max(ys) - min(ys))
    ox = (min(xs)+max(xs))*0.5
    oy = (min(ys)+max(ys))*0.5
    for v in bm.verts:
        v.co = Vector(((v.co.x-ox)*sc, 0.0, (v.co.y-oy)*sc))
    bm.to_mesh(ob.data)
    bm.free()
    print("[v3b] flat reference: %d verts" % len(ob.data.vertices))
    mm = bpy.data.materials.new("FlatMatte")
    mm.use_nodes = True
    nt0 = mm.node_tree
    nt0.nodes.clear()
    o0 = nt0.nodes.new("ShaderNodeOutputMaterial")
    e0 = nt0.nodes.new("ShaderNodeEmission")
    e0.inputs["Color"].default_value = (1, 1, 1, 1)
    nt0.links.new(e0.outputs["Emission"], o0.inputs["Surface"])
    ob.data.materials.clear()
    ob.data.materials.append(mm)
    w0 = bpy.data.worlds.new("Blk")
    w0.use_nodes = True
    w0.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    scene.world = w0
    cd0 = bpy.data.cameras.new("C0")
    cd0.lens = 105
    c0 = link(bpy.data.objects.new("C0", cd0))
    c0.location = CAM_POS
    c0.rotation_euler = (math.radians(86.5), 0, 0)
    scene.camera = c0
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = os.path.join(OUT, "flatref_persp.png")
    bpy.ops.render.render(write_still=True)
    print("[v3b] flat reference perspective matte -> %s" % scene.render.filepath)
    raise SystemExit(0)


if STAGE != "flatref":
    pass


# ---------------------------------------------------------------- 1. SVG contour
def svg_outer_contour():
    """The mark's own outer contour, as a closed world-XZ loop at y=0.

    This replaces iteration 2's offset-a-hand-read-polygon step, which was the
    entire remaining fidelity error: the offset flipped to the wrong side along
    concave stretches such as the swoosh. Taking the contour directly makes the
    silhouette exact by construction, the same way v1/v2 reach 99.723%.
    """
    bpy.ops.import_curve.svg(filepath=os.path.join(HERE,
                             "eez-mark-gradient-transparent.svg"))
    cs = [o for o in bpy.data.objects if o.type == "CURVE"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in cs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = cs[0]
    if len(cs) > 1:
        bpy.ops.object.join()
    cu = bpy.context.view_layer.objects.active
    ar = []
    for i, sp in enumerate(cu.data.splines):
        ps = sp.bezier_points if sp.type == "BEZIER" else sp.points
        n = len(ps)
        a = sum(ps[k].co[0]*ps[(k+1) % n].co[1] - ps[(k+1) % n].co[0]*ps[k].co[1]
                for k in range(n))
        ar.append((abs(a), i))
    keep = max(ar)[1]
    for sp in [sp for i, sp in enumerate(cu.data.splines) if i != keep]:
        cu.data.splines.remove(sp)
    cu.data.fill_mode = "FRONT"
    cu.data.resolution_u = 8
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.edges.ensure_lookup_table()
    be = [e for e in bm.edges if len(e.link_faces) == 1]
    adj = {}
    for e in be:
        for v in e.verts:
            adj.setdefault(v.index, []).append(e)
    st = be[0].verts[0]
    loop = [st]
    prev = None
    while True:
        c = [e for e in adj[loop[-1].index] if e is not prev]
        if not c:
            break
        e = c[0]
        nx = e.other_vert(loop[-1])
        prev = e
        if nx is st:
            break
        loop.append(nx)
    raw = [(v.co.x, v.co.y) for v in loop]
    bm.free()
    bpy.data.objects.remove(ob, do_unlink=True)
    xs = [p[0] for p in raw]
    ys = [p[1] for p in raw]
    wid = max(xs) - min(xs)
    hei = max(ys) - min(ys)
    ox, oy = min(xs), min(ys)
    norm = [((p[0]-ox)/wid, 1.0 - (p[1]-oy)/hei) for p in raw]
    print("[v3c] SVG outer contour: %d pts, aspect %.4f" % (len(norm), wid/hei))
    return norm


def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    ax, ay = pts[0]
    bx, by = pts[-1]
    dx, dy = bx-ax, by-ay
    nrm = math.hypot(dx, dy)
    worst, wi = -1.0, 0
    for i in range(1, len(pts)-1):
        px, py = pts[i]
        d = (math.hypot(px-ax, py-ay) if nrm < 1e-12
             else abs(dx*(py-ay) - dy*(px-ax))/nrm)
        if d > worst:
            worst, wi = d, i
    if worst <= eps:
        return [pts[0], pts[-1]]
    return rdp(pts[:wi+1], eps)[:-1] + rdp(pts[wi:], eps)


CON = svg_outer_contour()
NC = len(CON)


def band_tip(lo, hi, side):
    cand = [(i, p) for i, p in enumerate(CON) if lo <= p[1] <= hi
            and ((p[0] < 0.5) if side == "L" else (p[0] >= 0.5))]
    return (max(cand, key=lambda ip: ip[1][0]) if side == "L"
            else min(cand, key=lambda ip: ip[1][0]))[0]


T1 = band_tip(0.42, 0.68, "L")
T2 = band_tip(0.42, 0.68, "R")


def arc_idx(a, b):
    return list(range(a, b)) if a < b else list(range(a, NC)) + list(range(0, b))


A1, A2 = arc_idx(T1, T2), arc_idx(T2, T1)
mean1 = sum(CON[i][1] for i in A1)/len(A1)
mean2 = sum(CON[i][1] for i in A2)/len(A2)
UP_I, LO_I = (A1, A2) if mean1 < mean2 else (A2, A1)
print("[v3c] waist tips at idx %d (%.3f,%.3f) and %d (%.3f,%.3f); bridge chord "
      "%.4f of height" % (T1, CON[T1][0], CON[T1][1], T2, CON[T2][0], CON[T2][1],
                          math.hypot(CON[T1][0]-CON[T2][0], CON[T1][1]-CON[T2][1])))
print("[v3c] upper arc %d pts, lower arc %d pts" % (len(UP_I), len(LO_I)))

RDP_EPS = 0.00035          # < 0.5 px at 2400; gate measures the result


def prep(idxs):
    pts = [CON[i] for i in idxs]
    s = rdp(pts, RDP_EPS)
    return s


UP_N, LO_N = prep(UP_I), prep(LO_I)
print("[v3c] rings simplified: upper %d -> %d, lower %d -> %d (eps %.5f)"
      % (len(UP_I), len(UP_N), len(LO_I), len(LO_N), RDP_EPS))


def anchor(ring, target):
    best = None
    for k, p in enumerate(ring):
        d = (p[0]-target[0])**2 + (p[1]-target[1])**2
        if best is None or d < best[0]:
            best = (d, k)
    return best[1]


# ---------------------------------------------------------------- 2. shells
def build_shell(ringn, chords, facets, tag):
    ringw = [Wp(*p) for p in ringn]
    verts, faces, key = [], [], {}

    def vid(k, pos):
        if k not in key:
            key[k] = len(verts)
            verts.append(pos)
        return key[k]

    n = len(ringn)
    for i in range(n):
        vid("r%d" % i, ringw[i])

    chord_keys = {}
    for (i0, i1) in chords:
        ks = ["r%d" % i0]
        a, b = ringw[i0], ringw[i1]
        for s in range(1, CHORD_SEG):
            t = s / CHORD_SEG
            k = "c%d_%d_%d" % (i0, i1, s)
            vid(k, ray_push(a + (b-a)*t, -BOW_R*math.sin(math.pi*t)))
            ks.append(k)
        ks.append("r%d" % i1)
        chord_keys[(i0, i1)] = ks
        chord_keys[(i1, i0)] = list(reversed(ks))

    def expand(loop):
        out = []
        for it in loop:
            if isinstance(it, tuple) and it[0] == "chord":
                out.extend(chord_keys[(it[1], it[2])][1:-1])
            elif isinstance(it, tuple) and it[0] == "arc":
                a, b = it[1], it[2]
                idx = list(range(a, b)) if a <= b else list(range(a, n))+list(range(0, b))
                out.extend("r%d" % i for i in idx)
            else:
                out.append(it)
        return out

    for fi, loop in enumerate(facets):
        ks = expand(loop)
        if len(set(ks)) != len(ks):
            dup = sorted({k for k in ks if ks.count(k) > 1})
            raise SystemExit("[v3c] facet %d repeats keys %s" % (fi, dup[:6]))
        # ONE n-gon per facet. A centroid fan was tried first and bridged
        # straight across the waist notch -- these facets are concave, and the
        # fan filled the notch in, which was the whole of iteration 3's
        # remaining 8.5% silhouette excess. Blender tessellates a concave n-gon
        # correctly; the crease still comes from the bowed chord in its
        # boundary, so no interior vertex is needed.
        faces.append(tuple(key[k] for k in ks))
    print("[v3c] %s shell: %d verts %d faces (%d facets)"
          % (tag, len(verts), len(faces), len(facets)))
    return verts, faces, [key["r%d" % i] for i in range(n)]


def close_gem(verts, faces, ring_ids, name):
    vs = [v.copy() for v in verts]
    fs = list(faces)
    rs = set(ring_ids)
    mir = {}
    for i, v in enumerate(verts):
        mir[i] = i if i in rs else len(vs)
        if i not in rs:
            vs.append(Vector((v.x, -v.y, v.z)))
    for f in faces:
        fs.append(tuple(reversed([mir[i] for i in f])))
    nv = len(vs)
    for f in fs:
        if len(set(f)) != len(f) or any(i < 0 or i >= nv for i in f):
            raise SystemExit("[v3c] invalid face %s" % str(f))
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in vs], [], fs)
    me.update()
    ob = link(bpy.data.objects.new(name, me))
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    bmx = bmesh.new()
    bmx.from_mesh(ob.data)
    ne = len([e for e in bmx.edges if len(e.link_faces) == 1])
    print("[v3c]   %s before triangulation: %d boundary edges" % (name, ne))
    bmx.free()
    bpy.ops.object.shade_flat()
    return ob


# upper: traversal order along the arc is J, M, L, A, R (verified against the
# contour), so the contour segment M->J IS the swoosh.
uJ = anchor(UP_N, (0.495, 0.305))
uM = anchor(UP_N, (0.320, 0.565))
uL = anchor(UP_N, (0.020, 0.395))
uA = anchor(UP_N, (0.475, 0.005))
uR = anchor(UP_N, (0.955, 0.505))
print("[v3c] upper anchors J=%d M=%d L=%d A=%d R=%d of %d"
      % (uJ, uM, uL, uA, uR, len(UP_N)))
U_CH = [(uA, uJ), (uJ, uL)]
U_FA = [
    [("arc", uL, uA), "r%d" % uA, ("chord", uA, uJ), "r%d" % uJ, ("chord", uJ, uL)],
    [("arc", uJ, uL), "r%d" % uL, ("chord", uL, uJ)],
    [("arc", uA, uJ), "r%d" % uJ, ("chord", uJ, uA)],
]
uv, uf, ur = build_shell(UP_N, U_CH, U_FA, "upper")
upper = close_gem(uv, uf, ur, "EEZ_Upper")

lJ = anchor(LO_N, (0.435, 0.735))
lR = anchor(LO_N, (0.965, 0.605))
lA = anchor(LO_N, (0.475, 1.000))
lL = anchor(LO_N, (0.105, 0.605))
print("[v3c] lower anchors J'=%d R'=%d A'=%d L'=%d of %d"
      % (lJ, lR, lA, lL, len(LO_N)))
L_CH = [(lJ, lA)]
L_FA = [
    [("arc", lA, lJ), "r%d" % lJ, ("chord", lJ, lA)],
    [("arc", lJ, lA), "r%d" % lA, ("chord", lA, lJ)],
]
lv, lf, lr = build_shell(LO_N, L_CH, L_FA, "lower")
lower = close_gem(lv, lf, lr, "EEZ_Lower")

bpy.ops.object.select_all(action="DESELECT")
upper.select_set(True)
lower.select_set(True)
bpy.context.view_layer.objects.active = upper
bpy.ops.object.join()
solid = bpy.context.view_layer.objects.active
solid.name = "EEZ_Solid_v3c"

bm = bmesh.new()
bm.from_mesh(solid.data)
open_e = [e for e in bm.edges if len(e.link_faces) == 1]
nonman = [e for e in bm.edges if len(e.link_faces) > 2]
zs = [v.co.z for v in solid.data.vertices]
ys = [v.co.y for v in solid.data.vertices]
print("[v3c] gem: %d verts %d faces | boundary edges %d | non-manifold %d"
      % (len(solid.data.vertices), len(solid.data.polygons), len(open_e), len(nonman)))
print("[v3c] bow %.1f%% -> patch %.4f ridge %.4f | thickness %.4f (%.1f%% of width)"
      % (BOW*100, BOW_P, BOW_R, max(ys)-min(ys), (max(ys)-min(ys))/MARK_W*100))
bm.free()
RZ0, RZ1 = min(zs), max(zs)

pivot = link(bpy.data.objects.new("Pivot", None))
solid.parent = pivot

if STAGE == "geo":
    raise SystemExit(0)

# ---------------------------------------------------------------- material
mat = bpy.data.materials.new("EEZ_v3")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out_n = nt.nodes.new("ShaderNodeOutputMaterial")
texco = nt.nodes.new("ShaderNodeTexCoord")

sep = nt.nodes.new("ShaderNodeSeparateXYZ")
zmap = nt.nodes.new("ShaderNodeMapRange")
zmap.inputs["From Min"].default_value = RZ0
zmap.inputs["From Max"].default_value = RZ1
zmap.clamp = True
nt.links.new(texco.outputs["Object"], sep.inputs["Vector"])
nt.links.new(sep.outputs["Z"], zmap.inputs["Value"])

ramp = nt.nodes.new("ShaderNodeValToRGB")
ramp.color_ramp.interpolation = "LINEAR"
ramp.color_ramp.elements[0].position = 0.0
ramp.color_ramp.elements[0].color = srgb(INDIGO)
ramp.color_ramp.elements[1].position = 1.0
ramp.color_ramp.elements[1].color = srgb(LIME)
ramp.color_ramp.elements.new(0.24).color = srgb(INDIGO)
ramp.color_ramp.elements.new(0.60).color = srgb(CYAN)
ramp.color_ramp.elements.new(0.82).color = srgb(LIME)
nt.links.new(zmap.outputs["Result"], ramp.inputs["Fac"])

geo = nt.nodes.new("ShaderNodeNewGeometry")
nrm = nt.nodes.new("ShaderNodeVectorTransform")
nrm.vector_type = "NORMAL"
nrm.convert_from = "WORLD"
nrm.convert_to = "OBJECT"
nt.links.new(geo.outputs["Normal"], nrm.inputs["Vector"])
nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(nrm.outputs["Vector"], nsep.inputs["Vector"])
nflat = nt.nodes.new("ShaderNodeCombineXYZ")
nt.links.new(nsep.outputs["X"], nflat.inputs["X"])
nt.links.new(nsep.outputs["Z"], nflat.inputs["Z"])
nn = nt.nodes.new("ShaderNodeVectorMath")
nn.operation = "NORMALIZE"
nt.links.new(nflat.outputs["Vector"], nn.inputs[0])
kdot = nt.nodes.new("ShaderNodeVectorMath")
kdot.operation = "DOT_PRODUCT"
kdot.inputs[1].default_value = (-0.60, 0.0, 0.80)
kmap = nt.nodes.new("ShaderNodeMapRange")
kmap.inputs["From Min"].default_value = -1.0
kmap.inputs["From Max"].default_value = 1.0
kmap.inputs["To Min"].default_value = TONE_MIN
kmap.inputs["To Max"].default_value = 0.92
kmap.clamp = True
nt.links.new(nn.outputs["Vector"], kdot.inputs[0])
nt.links.new(kdot.outputs["Value"], kmap.inputs["Value"])
nyabs = nt.nodes.new("ShaderNodeMath")
nyabs.operation = "ABSOLUTE"
nt.links.new(nsep.outputs["Y"], nyabs.inputs[0])
nystep = nt.nodes.new("ShaderNodeMapRange")
nystep.inputs["From Min"].default_value = 0.0
nystep.inputs["From Max"].default_value = 0.60
nystep.inputs["To Min"].default_value = 0.55
nystep.inputs["To Max"].default_value = 1.0
nystep.clamp = True
nt.links.new(nyabs.outputs["Value"], nystep.inputs["Value"])
rim = nt.nodes.new("ShaderNodeMath")
rim.operation = "MULTIPLY"
rim.use_clamp = True
nt.links.new(kmap.outputs["Result"], rim.inputs[0])
nt.links.new(nystep.outputs["Result"], rim.inputs[1])

# v2 shading term at 0.5: hue-neutral scalar, wall falloff + fresnel rim,
# clamped so a lift can reach tone 1.0 (the palette peak) and no further
wall = nt.nodes.new("ShaderNodeMapRange")
wall.inputs["To Min"].default_value = 0.45
wall.inputs["To Max"].default_value = 1.0
wall.clamp = True
nt.links.new(nyabs.outputs["Value"], wall.inputs["Value"])
fres = nt.nodes.new("ShaderNodeFresnel")
fres.inputs["IOR"].default_value = 1.45
rimf = nt.nodes.new("ShaderNodeMapRange")
rimf.inputs["To Min"].default_value = 1.0
rimf.inputs["To Max"].default_value = 1.55
rimf.clamp = True
nt.links.new(fres.outputs["Fac"], rimf.inputs["Value"])
sraw = nt.nodes.new("ShaderNodeMath")
sraw.operation = "MULTIPLY"
nt.links.new(wall.outputs["Result"], sraw.inputs[0])
nt.links.new(rimf.outputs["Result"], sraw.inputs[1])
smix = nt.nodes.new("ShaderNodeMix")
smix.data_type = "FLOAT"
smix.inputs[0].default_value = SHADE
smix.inputs[2].default_value = 1.0
nt.links.new(sraw.outputs["Value"], smix.inputs[3])

stip = nt.nodes.new("ShaderNodeTexNoise")
stip.noise_dimensions = "3D"
stip.inputs["Scale"].default_value = 130.0
stip.inputs["Detail"].default_value = 2.0
stip.inputs["Roughness"].default_value = 0.65
smap = nt.nodes.new("ShaderNodeMapRange")
smap.inputs["From Min"].default_value = 0.32
smap.inputs["From Max"].default_value = 0.68
smap.inputs["To Min"].default_value = 0.90
smap.inputs["To Max"].default_value = 1.00
smap.clamp = True
nt.links.new(texco.outputs["Object"], stip.inputs["Vector"])
nt.links.new(stip.outputs["Fac"], smap.inputs["Value"])

t1 = nt.nodes.new("ShaderNodeMath")
t1.operation = "MULTIPLY"
t1.use_clamp = True
nt.links.new(rim.outputs["Value"], t1.inputs[0])
nt.links.new(smap.outputs["Result"], t1.inputs[1])
t2 = nt.nodes.new("ShaderNodeMath")
t2.operation = "MULTIPLY"
t2.use_clamp = True
nt.links.new(t1.outputs["Value"], t2.inputs[0])
nt.links.new(smix.outputs[0], t2.inputs[1])

tint = nt.nodes.new("ShaderNodeVectorMath")
tint.operation = "SCALE"
nt.links.new(ramp.outputs["Color"], tint.inputs[0])
nt.links.new(t2.outputs["Value"], tint.inputs["Scale"])
emit = nt.nodes.new("ShaderNodeEmission")
emit.inputs["Strength"].default_value = 1.0
nt.links.new(tint.outputs["Vector"], emit.inputs["Color"])
nt.links.new(emit.outputs["Emission"], out_n.inputs["Surface"])
solid.data.materials.append(mat)

# ---------------------------------------------------------------- environment
world = bpy.data.worlds.new("W")
scene.world = world
world.use_nodes = True
wbg = world.node_tree.nodes["Background"]
wbg.inputs["Color"].default_value = ((0, 0, 0, 1) if SCENE_MODE == "void"
                                    else srgb(BG_HEX))

floor = None
if SCENE_MODE != "void":
    bpy.ops.mesh.primitive_plane_add(size=140, location=(0, 0, RZ0 - 0.22))
    floor = bpy.context.active_object
    fm = bpy.data.materials.new("Floor")
    fm.use_nodes = True
    fnt = fm.node_tree
    fnt.nodes.clear()
    fo = fnt.nodes.new("ShaderNodeOutputMaterial")
    ftx = fnt.nodes.new("ShaderNodeTexCoord")

    def saw(sc, rz):
        mp = fnt.nodes.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0, 0, rz)
        wv = fnt.nodes.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.wave_profile = "SAW"
        wv.bands_direction = "X"
        wv.inputs["Scale"].default_value = sc
        th = fnt.nodes.new("ShaderNodeMapRange")
        th.inputs["From Max"].default_value = 0.010
        th.inputs["To Min"].default_value = 1.0
        th.inputs["To Max"].default_value = 0.0
        th.clamp = True
        fnt.links.new(ftx.outputs["Generated"], mp.inputs["Vector"])
        fnt.links.new(mp.outputs["Vector"], wv.inputs["Vector"])
        fnt.links.new(wv.outputs["Fac"], th.inputs["Value"])
        return th

    gx, gy = saw(46.0, 0.0), saw(46.0, math.radians(90))
    gmax = fnt.nodes.new("ShaderNodeMath")
    gmax.operation = "MAXIMUM"
    fnt.links.new(gx.outputs["Result"], gmax.inputs[0])
    fnt.links.new(gy.outputs["Result"], gmax.inputs[1])
    dist = fnt.nodes.new("ShaderNodeVectorMath")
    dist.operation = "LENGTH"
    fade = fnt.nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = 5.0
    fade.inputs["From Max"].default_value = 30.0
    fade.inputs["To Min"].default_value = 0.34
    fade.inputs["To Max"].default_value = 0.0
    fade.clamp = True
    gs = fnt.nodes.new("ShaderNodeMath")
    gs.operation = "MULTIPLY"
    fnt.links.new(ftx.outputs["Object"], dist.inputs[0])
    fnt.links.new(dist.outputs["Value"], fade.inputs["Value"])
    fnt.links.new(gmax.outputs["Value"], gs.inputs[0])
    fnt.links.new(fade.outputs["Result"], gs.inputs[1])
    gcol = fnt.nodes.new("ShaderNodeMix")
    gcol.data_type = "RGBA"
    gcol.inputs[6].default_value = srgb(BG_HEX)
    gcol.inputs[7].default_value = srgb(CYAN)
    fnt.links.new(gs.outputs["Value"], gcol.inputs[0])
    # contact shadow, shader-side, no light object
    gp = fnt.nodes.new("ShaderNodeSeparateXYZ")
    fnt.links.new(ftx.outputs["Object"], gp.inputs["Vector"])
    gf = fnt.nodes.new("ShaderNodeCombineXYZ")
    fnt.links.new(gp.outputs["X"], gf.inputs["X"])
    fnt.links.new(gp.outputs["Y"], gf.inputs["Y"])
    gl = fnt.nodes.new("ShaderNodeVectorMath")
    gl.operation = "LENGTH"
    fnt.links.new(gf.outputs["Vector"], gl.inputs[0])
    pool = fnt.nodes.new("ShaderNodeMapRange")
    pool.inputs["From Min"].default_value = 0.35
    pool.inputs["From Max"].default_value = 1.75
    pool.inputs["To Min"].default_value = SHADOW
    pool.inputs["To Max"].default_value = 0.0
    pool.clamp = True
    fnt.links.new(gl.outputs["Value"], pool.inputs["Value"])
    shm = fnt.nodes.new("ShaderNodeMix")
    shm.data_type = "RGBA"
    shm.inputs[7].default_value = (0, 0, 0, 1)
    fnt.links.new(gcol.outputs[2], shm.inputs[6])
    fnt.links.new(pool.outputs["Result"], shm.inputs[0])
    fe = fnt.nodes.new("ShaderNodeEmission")
    fg = fnt.nodes.new("ShaderNodeBsdfGlossy")
    fg.inputs["Roughness"].default_value = 0.22
    fg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    fx = fnt.nodes.new("ShaderNodeMixShader")
    fx.inputs["Fac"].default_value = 0.16
    fnt.links.new(shm.outputs[2], fe.inputs["Color"])
    fnt.links.new(fe.outputs["Emission"], fx.inputs[1])
    fnt.links.new(fg.outputs["BSDF"], fx.inputs[2])
    fnt.links.new(fx.outputs["Shader"], fo.inputs["Surface"])
    floor.data.materials.append(fm)

cd = bpy.data.cameras.new("Cam")
cd.lens = 105
cam = link(bpy.data.objects.new("Cam", cd))
cam.location = CAM_POS
cam.rotation_euler = (math.radians(86.5), 0, 0)
scene.camera = cam
bpy.context.view_layer.update()
if SCENE_MODE != "void":
    view = cam.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    cd.dof.use_dof = True
    cd.dof.aperture_fstop = DOF_FSTOP
    cd.dof.focus_distance = (Vector((0, 0, 0)) - cam.location).dot(view)

scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = False

# ---------------------------------------------------------------- output
if STAGE == "matte":
    mm = bpy.data.materials.new("Matte")
    mm.use_nodes = True
    mt = mm.node_tree
    mt.nodes.clear()
    mo = mt.nodes.new("ShaderNodeOutputMaterial")
    me2 = mt.nodes.new("ShaderNodeEmission")
    me2.inputs["Color"].default_value = (1, 1, 1, 1)
    mt.links.new(me2.outputs["Emission"], mo.inputs["Surface"])
    solid.data.materials.clear()
    solid.data.materials.append(mm)
    if floor:
        floor.hide_render = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
    oc = bpy.data.cameras.new("Ortho")
    oc.type = "ORTHO"
    oc.ortho_scale = MARK_H * 1.06
    oo = link(bpy.data.objects.new("Ortho", oc))
    oo.location = (0, -6, 0)
    oo.rotation_euler = (math.radians(90), 0, 0)
    scene.camera = oo
    scene.render.filepath = os.path.join(OUT, "v3s_matte_%s.png" % LABEL)
    bpy.ops.render.render(write_still=True)
    print("[v3] ortho matte -> %s" % scene.render.filepath)
    # and a perspective matte for the crease overlay
    scene.camera = cam
    scene.render.filepath = os.path.join(OUT, "v3s_persp_matte_%s.png" % LABEL)
    bpy.ops.render.render(write_still=True)
    print("[v3] perspective matte -> %s" % scene.render.filepath)
    raise SystemExit(0)

if STAGE in ("anim", "strip", "seam"):
    # Linear full turn, WRAPPED so frame 241 lands on exactly 0 rather than
    # 2*pi (same pose, but not float-equal -- that cost 133 boundary pixels on
    # the earlier variant). For every rendered frame 1..240,
    # (frame-1) %% 240 == frame-1, so no output frame is affected.
    scene.frame_start = 1
    scene.frame_end = LOOP_FRAMES
    pivot.rotation_mode = "XYZ"
    rd = pivot.driver_add("rotation_euler", 2).driver
    rd.type = "SCRIPTED"
    rd.expression = "2*pi*((frame-1) %% %d)/%d" % (LOOP_FRAMES, LOOP_FRAMES)
    bd = pivot.driver_add("location", 2).driver
    bd.type = "SCRIPTED"
    bd.expression = "%.6f * cos(2*pi*((frame-1) %% %d)/%d)" % (
        MARK_H * 0.02, LOOP_FRAMES, LOOP_FRAMES)
    print("[v3c] spin driver: %s" % rd.expression)
    print("[v3c] bob driver : %s" % bd.expression)
    print("[v3c] --- loop verification ---")
    for f in (1, 61, 121, 181, LOOP_FRAMES, LOOP_FRAMES + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        print("[v3c] frame %3d  rotZ=%+.9f rad (%+.6f deg)  locZ=%+.9f"
              % (f, pivot.rotation_euler.z, math.degrees(pivot.rotation_euler.z),
                 pivot.matrix_world.translation.z))

if STAGE == "anim":
    if SCENE_MODE == "void":
        # hero: one alpha pass only; the MP4 is composited over #000000
        # downstream so black is true black, not a rendered near-black
        scene.render.film_transparent = True
        sub_dir = "frames_%s_void_rgba" % RUN_TAG
    else:
        scene.render.film_transparent = False
        if floor:
            floor.hide_render = False
        sub_dir = "frames_%s_studio_rgb" % RUN_TAG
    scene.render.filepath = os.path.join(OUT, sub_dir, "f_")
    bpy.ops.render.render(animation=True)
    print("[v3c] %s pass done -> %s" % (SCENE_MODE, sub_dir))
    raise SystemExit(0)

if STAGE == "seam":
    # frame 241 must reproduce frame 1 exactly; rendered with the same settings
    # as the animation pass so the comparison is like-for-like
    scene.render.film_transparent = (SCENE_MODE == "void")
    for f in (1, LOOP_FRAMES + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(
            OUT, "seam_%s_%s_%04d.png" % (RUN_TAG, SCENE_MODE, f))
        bpy.ops.render.render(write_still=True)
        print("[v3c] seam frame %d rendered" % f)
    raise SystemExit(0)

if STAGE == "strip":
    frames = [int(x) for x in arg("--strip-frames", "1,41,81,121,161,201").split(",")]
    scene.render.film_transparent = False
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(
            OUT, "strip_%s_%s_f%03d.png" % (RUN_TAG, SCENE_MODE, f))
        bpy.ops.render.render(write_still=True)
        print("[v3c] strip f%d rotZ %+.1f deg" % (f, math.degrees(pivot.rotation_euler.z)))
    raise SystemExit(0)

for lab, deg in (("000", 0.0), ("045", 45.0), ("090", 90.0), ("135", 135.0)):
    pivot.rotation_euler = (0.0, 0.0, math.radians(deg))
    bpy.context.view_layer.update()
    scene.render.filepath = os.path.join(
        OUT, "v3s_%s_%s_%s.png" % (LABEL, SCENE_MODE, lab))
    bpy.ops.render.render(write_still=True)
    print("[v3] still %s %s %s deg" % (LABEL, SCENE_MODE, lab))
print("[v3] done")
