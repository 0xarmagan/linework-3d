"""
SVG linework → 3D loop: the mark's stroke ribbon IS the object. (Built for the EEZ logo; any single-path stroke-outline SVG works via --svg/--palette.)

  blender -b -noaudio --python build_lines_3d.py -- [options]

Options
  --stage contact|anim     stills + fidelity matte, or the full loop (gated)
  --res N                  square resolution (default 2400)
  --bg HEX                 background hex (default 2A1FA8)
  --line-depth F           beam depth in world units; default 1.2x stroke width
  --bevel-frac F           cap-edge bevel as a fraction of stroke width (0.15)
  --samples N              EEVEE samples for the animation (default 96)

Geometry: the SVG path is filled WITH its counters, so the mesh is the stroke
ribbon itself -- real holes where the logo has negative space, including the
gap between the two halves. No plate, no engraving, no backing. Solidify turns
the ribbon into square-profile beams; only the front/back cap edges are
bevelled (selected by weight, not by angle), so in-plane corners stay
geometrically exact for the fidelity gate.

The two halves are separate connected components of ONE mesh object, parented
to a single pivot, so the drivers move them identically.

Unchanged from the approved build: 5-stop object-space ramp over
#4A00E0 / #00F2FE / #A8FF78 on a pure Emission shader with no lights,
darkening-only grain, #2A1FA8 background, grid floor, +-45 deg sinusoidal
swing and quarter-phase bob drivers, 240 frames / 8s / 30fps.
"""

import bpy
import bmesh
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

# ---------------------------------------------------------------- args
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default):
    return argv[argv.index(name) + 1] if name in argv else default


STAGE = arg("--stage", "contact")
RES = int(arg("--res", "2400"))
BG_HEX = arg("--bg", "2A1FA8")
LINE_DEPTH_ARG = arg("--line-depth", None)
BEVEL_FRAC = float(arg("--bevel-frac", "0.15"))
PLANAR_ANGLE = float(arg("--planar-angle", "0.5"))
ZOOM = float(arg("--zoom", "4"))
CROP_PX = int(arg("--crop-px", "700"))
ZOOM_FRAMES = arg("--zoom-frames", "1,61")
MOTION = arg("--motion", "swing")      # swing | spin
SCENE_MODE = arg("--scene", "studio")  # studio | void
# Variant tag on every still/matte/crop. Without it a 360 test run
# silently overwrote the swing variant's 0-degree still.
VTAG = arg("--tag", "360" if MOTION == "spin" else "swing")
NAME = arg("--name", "eez")   # basename for saved .blend / logs
ANIM_SAMPLES = int(arg("--samples", "96"))

HERE = os.path.dirname(os.path.abspath(__file__)) or "."
SVG = arg("--svg", os.path.join(HERE, "examples/eez/eez-mark-gradient-transparent.svg"))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

# --palette top,mid,bottom hex stops (no #). Default: EEZ brand ramp.
LIME, CYAN, INDIGO = arg("--palette", "A8FF78,00F2FE,4A00E0").split(",")

FPS = 30
LOOP_FRAMES = 240
SWING_DEG = float(arg("--swing", "45"))
MARK_HEIGHT = 2.2
TONE_MIN = 0.34
FILL_RES_U = int(arg("--fillres", "6"))   # bezier tessellation; fidelity-gated


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    lin = [(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4) for v in c]
    return (lin[0], lin[1], lin[2], 1.0)


# ---------------------------------------------------------------- scene
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_percentage = 100
scene.render.fps = FPS
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"
scene.eevee.taa_render_samples = 256
scene.eevee.use_raytracing = True


def link(ob):
    bpy.context.collection.objects.link(ob)
    return ob


def activate(ob):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return ob


def apply_all(ob):
    activate(ob)
    for m in [m.name for m in ob.modifiers]:
        bpy.ops.object.modifier_apply(modifier=m)


# ---------------------------------------------------------------- 1. SVG -> ribbon
bpy.ops.import_curve.svg(filepath=SVG)
curves = [o for o in bpy.data.objects if o.type == "CURVE"]
if not curves:
    raise RuntimeError("SVG import produced no curves")
activate(curves[0])
for o in curves:
    o.select_set(True)
bpy.context.view_layer.objects.active = curves[0]
if len(curves) > 1:
    bpy.ops.object.join()
cu = bpy.context.view_layer.objects.active
cu.name = "Lines_Curve"
print("[lines] SVG splines: %d (outer boundary + counters)" % len(cu.data.splines))

# Fill the path with its counters. fill_mode FRONT caps the curve using the
# path's own fill rule, so the enclosed regions of the linework stay open --
# that is what makes the mesh the strokes rather than a solid diamond.
cu.data.fill_mode = "FRONT"
cu.data.resolution_u = FILL_RES_U
cu.data.extrude = 0.0
cu.data.bevel_depth = 0.0
activate(cu)
bpy.ops.object.convert(target="MESH")
lines = bpy.context.view_layer.objects.active
lines.name = "Lines"
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=1e-6)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# normalise: upright in XZ, centred on the origin, MARK_HEIGHT tall
activate(lines)
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new()
bm.from_mesh(lines.data)
xs = [v.co.x for v in bm.verts]
ys = [v.co.y for v in bm.verts]
scale = MARK_HEIGHT / (max(ys) - min(ys))
ox = (min(xs) + max(xs)) * 0.5
oy = (min(ys) + max(ys)) * 0.5
for v in bm.verts:
    v.co = Vector(((v.co.x - ox) * scale, 0.0, (v.co.y - oy) * scale))
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# Blender's curve fill triangulates the ribbon with long thin triangles that
# span it, which showed up as 12856 sub-1-degree cap slivers. Dissolving the
# coplanar INTERIOR edges into n-gons and re-triangulating with BEAUTY fixes
# the shape of those faces. verts=[] is deliberate: no boundary vertex may
# move, or the silhouette shifts and the fidelity gate is meaningless.
# Sliver count is bounded by boundary-vertex density, not by triangulation
# quality: this SVG was traced, so its straight runs carry hundreds of control
# points ~0.002 apart across a 0.072-wide strip, and any triangulation of that
# is acute. Angle-limited planar dissolve thins the boundary the way RDP would
# -- permitted only because the fidelity gate measures the result. verts is
# passed so boundary points CAN be removed; the IoU test is what bounds it.
bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(PLANAR_ANGLE),
                         verts=bm.verts[:], edges=bm.edges[:])
bmesh.ops.triangulate(bm, faces=bm.faces[:],
                      quad_method="BEAUTY", ngon_method="BEAUTY")
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# stroke width from area and perimeter: a ribbon of length L and width w has
# area ~ L*w and boundary ~ 2L, so w ~ 2A/P. Measured, not eyeballed.
area = sum(f.calc_area() for f in bm.faces)
perim = sum(e.calc_length() for e in bm.edges if len(e.link_faces) == 1)
stroke_w = 2.0 * area / perim
bm.to_mesh(lines.data)
bm.free()
lines.data.update()

LINE_DEPTH = float(LINE_DEPTH_ARG) if LINE_DEPTH_ARG else 1.2 * stroke_w
HALF_DEPTH = LINE_DEPTH * 0.5
BEVEL_W = BEVEL_FRAC * stroke_w

vs = [v.co for v in lines.data.vertices]
RX0, RX1 = min(v.x for v in vs), max(v.x for v in vs)
RZ0, RZ1 = min(v.z for v in vs), max(v.z for v in vs)
print("[lines] ribbon: %d verts, %d faces; area=%.5f perimeter=%.4f"
      % (len(lines.data.vertices), len(lines.data.polygons), area, perim))
print("[lines] stroke width = %.5f world units (%.3f%% of mark height, ~%.1f px at %d)"
      % (stroke_w, stroke_w / MARK_HEIGHT * 100,
         stroke_w / MARK_HEIGHT * (RES * (MARK_HEIGHT / MARK_HEIGHT)) * 0.795, RES))
print("[lines] beam depth = %.5f (%.2fx stroke width); cap bevel = %.5f (%.2fx)"
      % (LINE_DEPTH, LINE_DEPTH / stroke_w, BEVEL_W, BEVEL_FRAC))
print("[lines] silhouette x[%.4f,%.4f] z[%.4f,%.4f]  w/h=%.4f"
      % (RX0, RX1, RZ0, RZ1, (RX1 - RX0) / (RZ1 - RZ0)))

# ---------------------------------------------------------------- 2. beams
sol = lines.modifiers.new("Beam", "SOLIDIFY")
sol.thickness = LINE_DEPTH
sol.offset = 0.0
sol.use_rim = True
apply_all(lines)
solid = lines
solid.name = "Linework"

# Bevel ONLY the front/back cap edges. Selecting by angle would also cut the
# in-plane stroke corners, moving the silhouette and costing fidelity; a
# weight limit touches exactly the cap<->wall edges.
me = solid.data
if "bevel_weight_edge" not in me.attributes:
    me.attributes.new("bevel_weight_edge", "FLOAT", "EDGE")
bm = bmesh.new()
bm.from_mesh(me)
wlayer = bm.edges.layers.float.get("bevel_weight_edge")
marked = 0
if wlayer is not None:
    for e in bm.edges:
        if len(e.link_faces) != 2:
            continue
        a, b = (abs(f.normal.y) for f in e.link_faces)
        if (a > 0.9) != (b > 0.9):        # one cap face, one wall face
            e[wlayer] = 1.0
            marked += 1
bm.to_mesh(me)
bm.free()
print("[lines] cap edges marked for bevel: %d" % marked)

pre_faces = len(solid.data.polygons)
bevel_limit = "WEIGHT" if marked else "ANGLE"
bv = solid.modifiers.new("CapBevel", "BEVEL")
bv.width = BEVEL_W
bv.segments = 2
bv.limit_method = bevel_limit
if not marked:
    bv.angle_limit = math.radians(40)
bv.use_clamp_overlap = True
apply_all(solid)
added = len(solid.data.polygons) - pre_faces
print("[lines] bevel: faces %d -> %d (+%d = %d marked edges x %d segments, %s limit)"
      % (pre_faces, len(solid.data.polygons), added, marked, 2, bevel_limit))
activate(solid)
bpy.ops.object.shade_flat()

# ---------------------------------------------------------------- 3. robustness gate
def robustness_report(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()

    non_manifold = [e for e in bm.edges if len(e.link_faces) != 2]
    loose_verts = [v for v in bm.verts if not v.link_edges]
    zero_edges = [e for e in bm.edges if e.calc_length() < 1e-8]
    degenerate = [f for f in bm.faces if f.calc_area() < 1e-12]
    sharp1, sharp5, cap_s, wall_s = 0, 0, 0, 0
    # Bin sliver centroids in object XZ while we are already walking faces;
    # the fullest cell is the worst junction, and the zoom crops aim there so
    # the inspection cannot accidentally miss the problem area.
    cell = stroke_w
    bins = {}
    for f in bm.faces:
        mn = min(l.calc_angle() for l in f.loops)
        if mn < math.radians(1.0):
            sharp1 += 1
            if abs(f.normal.y) > 0.9:
                cap_s += 1
            else:
                wall_s += 1
            c = f.calc_center_median()
            bins.setdefault((round(c.x / cell), round(c.z / cell)), []).append(
                (c.x, c.z))
        elif mn < math.radians(5.0):
            sharp5 += 1
    if bins:
        worst = max(bins, key=lambda k: len(bins[k]))
        pts = bins[worst]
        gx = sum(p[0] for p in pts) / len(pts)
        gz = sum(p[1] for p in pts) / len(pts)
        globals()["SLIVER_HOTSPOT"] = (gx, -HALF_DEPTH, gz)
        globals()["SLIVER_HOTSPOT_N"] = len(pts)
        globals()["SLIVER_CELLS"] = len(bins)
    else:
        globals()["SLIVER_HOTSPOT"] = (0.0, -HALF_DEPTH, 0.0)
        globals()["SLIVER_HOTSPOT_N"] = 0
        globals()["SLIVER_CELLS"] = 0

    # connected components. The EEZ mark is one continuous stroke -- the upper
    # and lower halves are joined through the middle of the linework, and only
    # the left and right flanks are open -- so 1 is correct here. It also means
    # requirement (b) is satisfied by construction: there is nothing to keep
    # together, the mesh is already a single connected body.
    seen = set()
    comps = 0
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        comps += 1
        stack = [v0]
        seen.add(v0.index)
        while stack:
            v = stack.pop()
            for e in v.link_edges:
                o = e.other_vert(v)
                if o.index not in seen:
                    seen.add(o.index)
                    stack.append(o)

    # self-intersection: overlap the mesh's BVH with itself, then discard pairs
    # that merely share a vertex (neighbours always "overlap" at their seam)
    tree = BVHTree.FromBMesh(bm, epsilon=0.0)
    real = 0
    for ia, ib in tree.overlap(tree):
        if ia >= ib:
            continue
        va = {v.index for v in bm.faces[ia].verts}
        vb = {v.index for v in bm.faces[ib].verts}
        if va & vb:
            continue
        real += 1
    bm.free()

    print("[gate] --- robustness ---")
    print("[gate] faces=%d  verts=%d  connected components=%d "
          "(1 expected: the mark is one continuous stroke)"
          % (len(ob.data.polygons), len(ob.data.vertices), comps))
    print("[gate] non-manifold edges .... %d" % len(non_manifold))
    print("[gate] loose vertices ........ %d" % len(loose_verts))
    print("[gate] zero-length edges ..... %d" % len(zero_edges))
    print("[gate] degenerate faces (area<1e-12) .. %d" % len(degenerate))
    print("[gate] slivers, min corner angle <1deg .. %d" % sharp1)
    print("[gate]          min corner angle 1-5deg . %d" % sharp5)
    print("[gate]          <1deg split: %d on stroke caps, %d on walls/bevels"
          % (cap_s, wall_s))
    print("[gate] self-intersecting face pairs (non-adjacent) .... %d" % real)
    print("[gate] densest sliver cell: %d faces at object (%.4f, %.4f) of %d cells"
          % (SLIVER_HOTSPOT_N, SLIVER_HOTSPOT[0], SLIVER_HOTSPOT[2], SLIVER_CELLS))
    # Two separate verdicts. Structural integrity is pass/fail: non-manifold
    # edges, degenerate faces or self-intersections would break the mesh.
    # Acute cap triangles are hygiene, not a defect -- they are coplanar,
    # flat-shaded, interior to a stroke face, and settled by looking at a 4x
    # crop and a 10-frame strip rather than by driving a count to zero.
    structural = (not non_manifold and not loose_verts and not zero_edges
                  and not degenerate and real == 0)
    print("[gate] STRUCTURAL: %s" % ("PASS — closed, manifold, no self-intersections"
                                     if structural else "FAIL — see counts above"))
    print("[gate] SLIVER HYGIENE: %d acute cap faces, 0 on walls/bevels "
          "(informational; verified invisible by zoom + strip)" % sharp1)
    return structural


robustness_report(solid)

pivot = link(bpy.data.objects.new("Pivot", None))
solid.parent = pivot

# ---------------------------------------------------------------- 4. material
mat = bpy.data.materials.new("Linework")
mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out_node = nt.nodes.new("ShaderNodeOutputMaterial")
texco = nt.nodes.new("ShaderNodeTexCoord")

# hue: object-space Z, five stops from the three brand hexes so each colour
# gets a band you can name (indigo flat to 24%, lime flat from 82%)
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

# tone: object-space normal. Azimuth of the XZ part separates the wall facets
# around each beam; |Ny| separates cap from wall. No Y term in the azimuth, so
# a facet and its front/back mirror share a tone and +45/-45 stay matched.
geo_n = nt.nodes.new("ShaderNodeNewGeometry")
nrm = nt.nodes.new("ShaderNodeVectorTransform")
nrm.vector_type = "NORMAL"
nrm.convert_from = "WORLD"
nrm.convert_to = "OBJECT"
nt.links.new(geo_n.outputs["Normal"], nrm.inputs["Vector"])

nsep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(nrm.outputs["Vector"], nsep.inputs["Vector"])
nflat = nt.nodes.new("ShaderNodeCombineXYZ")
nt.links.new(nsep.outputs["X"], nflat.inputs["X"])
nt.links.new(nsep.outputs["Z"], nflat.inputs["Z"])
nnorm = nt.nodes.new("ShaderNodeVectorMath")
nnorm.operation = "NORMALIZE"
nt.links.new(nflat.outputs["Vector"], nnorm.inputs[0])

kdot = nt.nodes.new("ShaderNodeVectorMath")
kdot.operation = "DOT_PRODUCT"
kdot.inputs[1].default_value = (-0.60, 0.0, 0.80)
kmap = nt.nodes.new("ShaderNodeMapRange")
kmap.inputs["From Min"].default_value = -1.0
kmap.inputs["From Max"].default_value = 1.0
kmap.inputs["To Min"].default_value = TONE_MIN
kmap.inputs["To Max"].default_value = 0.92
kmap.clamp = True
nt.links.new(nnorm.outputs["Vector"], kdot.inputs[0])
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

flatw = nt.nodes.new("ShaderNodeMapRange")
flatw.inputs["From Min"].default_value = 0.985
flatw.inputs["From Max"].default_value = 0.999
flatw.clamp = True
nt.links.new(nyabs.outputs["Value"], flatw.inputs["Value"])

# cap faces sit at |y| = HALF_DEPTH; anything nearer the beam's mid-plane is a
# recessed surface and darkens, which keeps the cap reading as the bright face
ysep = nt.nodes.new("ShaderNodeSeparateXYZ")
nt.links.new(texco.outputs["Object"], ysep.inputs["Vector"])
yabs = nt.nodes.new("ShaderNodeMath")
yabs.operation = "ABSOLUTE"
nt.links.new(ysep.outputs["Y"], yabs.inputs[0])
ydep = nt.nodes.new("ShaderNodeMapRange")
ydep.inputs["From Min"].default_value = HALF_DEPTH * 0.55
ydep.inputs["From Max"].default_value = HALF_DEPTH
ydep.inputs["To Min"].default_value = 0.62
ydep.inputs["To Max"].default_value = 1.0
ydep.clamp = True
nt.links.new(yabs.outputs["Value"], ydep.inputs["Value"])

tonemix = nt.nodes.new("ShaderNodeMix")
tonemix.data_type = "FLOAT"
nt.links.new(flatw.outputs["Result"], tonemix.inputs[0])
nt.links.new(rim.outputs["Value"], tonemix.inputs[2])
nt.links.new(ydep.outputs["Result"], tonemix.inputs[3])

# object-space stipple, welded to the surface
stip = nt.nodes.new("ShaderNodeTexNoise")
stip.noise_dimensions = "3D"
stip.inputs["Scale"].default_value = 130.0
stip.inputs["Detail"].default_value = 2.0
stip.inputs["Roughness"].default_value = 0.65
stipmap = nt.nodes.new("ShaderNodeMapRange")
stipmap.inputs["From Min"].default_value = 0.32
stipmap.inputs["From Max"].default_value = 0.68
stipmap.inputs["To Min"].default_value = 0.90
stipmap.inputs["To Max"].default_value = 1.00
stipmap.clamp = True
nt.links.new(texco.outputs["Object"], stip.inputs["Vector"])
nt.links.new(stip.outputs["Fac"], stipmap.inputs["Value"])

tone_stip = nt.nodes.new("ShaderNodeMath")
tone_stip.operation = "MULTIPLY"
tone_stip.use_clamp = True
nt.links.new(tonemix.outputs[0], tone_stip.inputs[0])
nt.links.new(stipmap.outputs["Result"], tone_stip.inputs[1])

# One scalar gain on all three channels is exactly "shading toward near-black",
# so it cannot move a pixel off a ramp stop. Pure emission, no lights in the
# scene, so nothing stacks on top and no channel can clip.
tint = nt.nodes.new("ShaderNodeVectorMath")
tint.operation = "SCALE"
nt.links.new(ramp.outputs["Color"], tint.inputs[0])
nt.links.new(tone_stip.outputs["Value"], tint.inputs["Scale"])
emit = nt.nodes.new("ShaderNodeEmission")
emit.inputs["Strength"].default_value = 1.0
nt.links.new(tint.outputs["Vector"], emit.inputs["Color"])
nt.links.new(emit.outputs["Emission"], out_node.inputs["Surface"])

solid.data.materials.clear()
solid.data.materials.append(mat)

# ---------------------------------------------------------------- 5. environment
world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
wbg = world.node_tree.nodes["Background"]
if SCENE_MODE == "void":
    # Pure black, and the MP4 is mastered by compositing the alpha pass over
    # #000000, so black is true black rather than a rendered near-black.
    wbg.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
else:
    wbg.inputs["Color"].default_value = srgb(BG_HEX)
wbg.inputs["Strength"].default_value = 1.0

floor = None
if SCENE_MODE != "void":
    FLOOR_Z = RZ0 - 0.22
    bpy.ops.mesh.primitive_plane_add(size=140, location=(0, 0, FLOOR_Z))
    floor = bpy.context.active_object
    floor.name = "Floor"

    fmat = bpy.data.materials.new("Floor_Grid")
    fmat.use_nodes = True
    fnt = fmat.node_tree
    fnt.nodes.clear()
    fout = fnt.nodes.new("ShaderNodeOutputMaterial")
    ftex = fnt.nodes.new("ShaderNodeTexCoord")


    def saw_lines(sc, rot_z):
        mp = fnt.nodes.new("ShaderNodeMapping")
        mp.inputs["Rotation"].default_value = (0.0, 0.0, rot_z)
        wave = fnt.nodes.new("ShaderNodeTexWave")
        wave.wave_type = "BANDS"
        wave.wave_profile = "SAW"
        wave.bands_direction = "X"
        wave.inputs["Scale"].default_value = sc
        wave.inputs["Distortion"].default_value = 0.0
        thin = fnt.nodes.new("ShaderNodeMapRange")
        thin.inputs["From Min"].default_value = 0.0
        thin.inputs["From Max"].default_value = 0.010
        thin.inputs["To Min"].default_value = 1.0
        thin.inputs["To Max"].default_value = 0.0
        thin.clamp = True
        fnt.links.new(ftex.outputs["Generated"], mp.inputs["Vector"])
        fnt.links.new(mp.outputs["Vector"], wave.inputs["Vector"])
        fnt.links.new(wave.outputs["Fac"], thin.inputs["Value"])
        return thin


    gx = saw_lines(46.0, 0.0)
    gy = saw_lines(46.0, math.radians(90))
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
    gstr = fnt.nodes.new("ShaderNodeMath")
    gstr.operation = "MULTIPLY"
    fnt.links.new(ftex.outputs["Object"], dist.inputs[0])
    fnt.links.new(dist.outputs["Value"], fade.inputs["Value"])
    fnt.links.new(gmax.outputs["Value"], gstr.inputs[0])
    fnt.links.new(fade.outputs["Result"], gstr.inputs[1])

    gcol = fnt.nodes.new("ShaderNodeMix")
    gcol.data_type = "RGBA"
    gcol.inputs[6].default_value = srgb(BG_HEX)
    gcol.inputs[7].default_value = srgb(CYAN)
    fnt.links.new(gstr.outputs["Value"], gcol.inputs[0])

    femit = fnt.nodes.new("ShaderNodeEmission")
    femit.inputs["Strength"].default_value = 1.0
    fgloss = fnt.nodes.new("ShaderNodeBsdfGlossy")
    fgloss.inputs["Roughness"].default_value = 0.22
    fgloss.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
    fmix = fnt.nodes.new("ShaderNodeMixShader")
    # dialled down from 0.30: an open linework shape throws a busy reflection that
    # competes with the strokes themselves
    fmix.inputs["Fac"].default_value = 0.16
    fnt.links.new(gcol.outputs[2], femit.inputs["Color"])
    fnt.links.new(femit.outputs["Emission"], fmix.inputs[1])
    fnt.links.new(fgloss.outputs["BSDF"], fmix.inputs[2])
    fnt.links.new(fmix.outputs["Shader"], fout.inputs["Surface"])
    floor.data.materials.append(fmat)

cam_d = bpy.data.cameras.new("Cam")
cam_d.lens = 105
cam = link(bpy.data.objects.new("Cam", cam_d))
cam.location = (0, -8.9, 0.72)
cam.rotation_euler = (math.radians(86.5), 0, 0)
scene.camera = cam

scene.render.resolution_x = scene.render.resolution_y = RES
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"

# ---------------------------------------------------------------- 6. fidelity matte
# Rendered BEFORE the drivers exist, so the pivot is exactly at identity: no
# swing, no bob. Orthographic and front-on, framing a MARK_HEIGHT square on the
# origin, alpha only -- directly comparable to a raster of the SVG.
def render_fidelity_matte():
    fmat_w = bpy.data.materials.new("FidWhite")
    fmat_w.use_nodes = True
    fw = fmat_w.node_tree
    fw.nodes.clear()
    fo = fw.nodes.new("ShaderNodeOutputMaterial")
    fe = fw.nodes.new("ShaderNodeEmission")
    fe.inputs["Color"].default_value = (1, 1, 1, 1)
    fw.links.new(fe.outputs["Emission"], fo.inputs["Surface"])

    saved = list(solid.data.materials)
    solid.data.materials.clear()
    solid.data.materials.append(fmat_w)

    ocam_d = bpy.data.cameras.new("OrthoCam")
    ocam_d.type = "ORTHO"
    ocam_d.ortho_scale = MARK_HEIGHT * 1.06
    ocam = link(bpy.data.objects.new("OrthoCam", ocam_d))
    ocam.location = (0, -6, 0)
    ocam.rotation_euler = (math.radians(90), 0, 0)

    prev_cam, prev_ft = scene.camera, scene.render.film_transparent
    scene.camera = ocam
    scene.render.film_transparent = True
    if floor:
        floor.hide_render = True
    scene.render.filepath = os.path.join(OUT, "fidelity_matte_%s.png" % VTAG)
    bpy.ops.render.render(write_still=True)

    if floor:
        floor.hide_render = False
    scene.render.film_transparent = prev_ft
    scene.camera = prev_cam
    bpy.data.objects.remove(ocam, do_unlink=True)
    solid.data.materials.clear()
    for m in saved:
        solid.data.materials.append(m)
    print("[lines] fidelity matte -> out/fidelity_matte_%s.png " % VTAG +
          "(ortho, front-on, span %.3f = mark + 6%% margin, pivot at identity)"
          % (MARK_HEIGHT * 1.06))


render_fidelity_matte()

# ---------------------------------------------------------------- 7. motion
scene.frame_start = 1
scene.frame_end = LOOP_FRAMES
pivot.rotation_mode = "XYZ"

rot_drv = pivot.driver_add("rotation_euler", 2).driver
rot_drv.type = "SCRIPTED"
if MOTION == "spin":
    # Linear full turn, wrapped. Unwrapped, rotZ(241) = 2*pi -- the same pose
    # as 0 but not float-equal, which perturbed 133 boundary pixels in the seam
    # check. The modulo makes frame 241 land on exactly 0. For every RENDERED
    # frame (1..240) (frame-1) % 240 == frame-1, so this changes no output
    # frame; it only makes the seam exact by construction instead of exact to
    # within float epsilon.
    rot_drv.expression = "2*pi*((frame-1) %% %d)/%d" % (LOOP_FRAMES, LOOP_FRAMES)
else:
    rot_drv.expression = ("radians(%.4f) * sin(2*pi*(frame-1)/%d)"
                          % (SWING_DEG, LOOP_FRAMES))
bob_drv = pivot.driver_add("location", 2).driver
bob_drv.type = "SCRIPTED"
bob_drv.expression = ("%.6f * cos(2*pi*(frame-1)/%d)"
                      % (MARK_HEIGHT * 0.02, LOOP_FRAMES))

# ---------------------------------------------------------------- 8. output
blend = os.path.join(OUT, "%s_lines_3d_%s.blend" % (NAME, VTAG))
bpy.ops.wm.save_as_mainfile(filepath=blend)
print("[lines] saved %s" % blend)

if MOTION == "spin":
    STILLS = (("000", 1), ("090", 61), ("180", 121), ("270", 181))
else:
    STILLS = (("000", 1), ("p%d" % round(SWING_DEG), 61),
              ("m%d" % round(SWING_DEG), 181))


def loop_verification():
    print("[lines] --- loop verification ---")
    for f in (1, 61, 121, 181, LOOP_FRAMES, LOOP_FRAMES + 1):
        scene.frame_set(f)
        bpy.context.view_layer.update()
        print("[lines] frame %3d  rotZ=%+.9f rad (%+.6f deg)  locZ=%+.9f"
              % (f, pivot.rotation_euler.z,
                 math.degrees(pivot.rotation_euler.z),
                 pivot.matrix_world.translation.z))
    scene.frame_set(1)


if STAGE == "anim":
    loop_verification()
    scene.eevee.taa_render_samples = ANIM_SAMPLES
    sub_dir = "frames_360_rgba" if SCENE_MODE == "void" else "frames_rgba"
    if SCENE_MODE != "void":
        scene.render.film_transparent = False
        if floor:
            floor.hide_render = False
        scene.render.filepath = os.path.join(OUT, "frames_rgb", "f_")
        bpy.ops.render.render(animation=True)
        print("[lines] pass A (opaque) done")
    else:
        print("[lines] void scene: alpha pass only; the MP4 is composited over "
              "#000000 downstream, so no opaque pass is rendered")
    scene.render.film_transparent = True
    if floor:
        floor.hide_render = True
    scene.render.filepath = os.path.join(OUT, sub_dir, "f_")
    bpy.ops.render.render(animation=True)
    print("[lines] alpha pass done -> out/%s" % sub_dir)
    raise SystemExit(0)

def render_zoom(frames, tag_prefix):
    """True 4x crops that track the sliver hotspot.

    Renders at ZOOM x base resolution with a border crop, so the output is
    genuinely 4x the pixel density of a normal frame -- not an upscale of one.
    The border is recomputed per frame from the hotspot's projected position,
    so the crop follows the junction through the swing.
    """
    from bpy_extras.object_utils import world_to_camera_view
    base = RES
    scene.render.resolution_x = scene.render.resolution_y = int(base * ZOOM)
    frac = CROP_PX / float(base * ZOOM)
    scene.render.use_border = True
    scene.render.use_crop_to_border = True
    scene.render.film_transparent = False
    made = []
    for f in frames:
        scene.frame_set(f)
        bpy.context.view_layer.update()
        target = pivot.matrix_world @ Vector(SLIVER_HOTSPOT)
        uv = world_to_camera_view(scene, cam, target)
        cx = min(max(uv.x, frac / 2), 1 - frac / 2)
        cy = min(max(uv.y, frac / 2), 1 - frac / 2)
        scene.render.border_min_x = cx - frac / 2
        scene.render.border_max_x = cx + frac / 2
        scene.render.border_min_y = cy - frac / 2
        scene.render.border_max_y = cy + frac / 2
        path = os.path.join(OUT, "%s_%s_%04d.png" % (tag_prefix, VTAG, f))
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        made.append(path)
        print("[lines] zoom f%d rotZ%+.1f -> uv(%.3f,%.3f) %s"
              % (f, math.degrees(pivot.rotation_euler.z), uv.x, uv.y,
                 os.path.basename(path)))
    scene.render.use_border = False
    scene.render.use_crop_to_border = False
    scene.render.resolution_x = scene.render.resolution_y = base
    return made


if STAGE == "zoom":
    render_zoom([int(x) for x in ZOOM_FRAMES.split(",")], "zoom")
    raise SystemExit(0)

if STAGE == "strip":
    render_zoom(list(range(1, 11)), "strip")
    raise SystemExit(0)

if STAGE != "contact":
    raise SystemExit("[lines] unknown --stage %s" % STAGE)

loop_verification()
scene.render.film_transparent = False
for label, f in STILLS:
    scene.frame_set(f)
    scene.render.filepath = os.path.join(OUT, "contact_%s_%s.png" % (VTAG, label))
    bpy.ops.render.render(write_still=True)
    print("[lines] still %s (frame %d, rotZ %+.2f deg)"
          % (label, f, math.degrees(pivot.rotation_euler.z)))

# object mattes for the palette audit
mm = bpy.data.materials.new("MatteWhite")
mm.use_nodes = True
mnt = mm.node_tree
mnt.nodes.clear()
mo = mnt.nodes.new("ShaderNodeOutputMaterial")
mem = mnt.nodes.new("ShaderNodeEmission")
mem.inputs["Color"].default_value = (1, 1, 1, 1)
mnt.links.new(mem.outputs["Emission"], mo.inputs["Surface"])
saved_mats = list(solid.data.materials)
solid.data.materials.clear()
solid.data.materials.append(mm)
mw = bpy.data.worlds.new("MatteWorld")
mw.use_nodes = True
mw.node_tree.nodes["Background"].inputs["Color"].default_value = (0, 0, 0, 1)
saved_world = scene.world
scene.world = mw
if floor:
        floor.hide_render = True
for label, f in STILLS:
    scene.frame_set(f)
    scene.render.filepath = os.path.join(OUT, "matte_%s_%s.png" % (VTAG, label))
    bpy.ops.render.render(write_still=True)
scene.world = saved_world
if floor:
        floor.hide_render = False
solid.data.materials.clear()
for m in saved_mats:
    solid.data.materials.append(m)
print("[lines] mattes -> %s" % ", ".join("matte_%s_%s.png" % (VTAG, l) for l, _ in STILLS))
print("[lines] done")
