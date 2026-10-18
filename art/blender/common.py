# Helpers shared by the scripts that build each place in Blender.
#
# Blender's axes: x is east, y is north, z is up, in metres. The exporter
# turns these into three.js's (y up, north is -z).
#
# Everything is coloured with vertex colours rather than textures for now,
# so a whole place is a handful of meshes and one material.

import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector, noise

HERE = Path(__file__).parent


def args():
    """The arguments after Blender's own `--`: the .glb to write, and
    --preview=<png> for a picture of the place."""
    rest = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    out = next((a for a in rest if not a.startswith("--")), None)
    preview = next((a.split("=", 1)[1] for a in rest if a.startswith("--preview=")), None)
    return out, preview


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def linear(hex_colour):
    """An sRGB colour like "#7a9a3c", as linear RGBA for Blender."""
    h = hex_colour.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i : i + 2], 16) / 255
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, 1.0)


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def vary(colour, amount, seed_vec):
    """A colour nudged lighter or darker by a little noise, for a painted look."""
    n = noise.noise(seed_vec) * amount
    return (*(max(0.0, c * (1 + n)) for c in colour[:3]), 1.0)


_material = None


def vertex_material():
    """One material for everything: the colour comes from each vertex."""
    global _material
    if _material:
        return _material
    m = bpy.data.materials.new("painted")
    if hasattr(m, "use_nodes") and not m.use_nodes:
        m.use_nodes = True
    nodes = m.node_tree.nodes
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    colour = nodes.new("ShaderNodeVertexColor")
    colour.layer_name = "Col"
    m.node_tree.links.new(colour.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    _material = m
    return m


def mesh_object(name, verts, faces, colours, smooth=True):
    """A mesh from lists of vertices, faces and one colour per vertex."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    layer = mesh.color_attributes.new(name="Col", type="FLOAT_COLOR", domain="POINT")
    for i, c in enumerate(colours):
        layer.data[i].color = c
    if smooth:
        mesh.shade_smooth()
    mesh.materials.append(vertex_material())
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


class Builder:
    """Collects many small shapes (trees, rocks) into one mesh."""

    def __init__(self):
        self.verts, self.faces, self.colours = [], [], []

    def add(self, verts, faces, colours):
        base = len(self.verts)
        self.verts += verts
        self.faces += [tuple(i + base for i in f) for f in faces]
        self.colours += colours

    def blob(self, centre, radius, colour, squash=1.0, lumpy=0.25, seed=0, subdivisions=2, shade=None, lit=True):
        """A lumpy sphere: a treetop, a bush or a rock. (Not lit, it isn't
        darker underneath: it rolls, and its underside comes up.)"""
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
        verts, colours = [], []
        offset = Vector((seed * 7.1, seed * 3.3, seed * 1.7))
        for v in bm.verts:
            d = v.co.normalized()
            r = radius * (1 + lumpy * noise.noise(d * 1.8 + offset))
            p = Vector((d.x * r, d.y * r, d.z * r * squash)) + Vector(centre)
            verts.append(tuple(p))
            # Darker underneath and lighter on top, as if lit from above.
            light = 0.72 + 0.4 * (d.z * 0.5 + 0.5) if lit else 0.92
            c = vary(colour, 0.18, d * 3 + offset)
            if shade:
                c = shade(p, d, c)
            colours.append((c[0] * light, c[1] * light, c[2] * light, 1.0))
        faces = [tuple(v.index for v in f.verts) for f in bm.faces]
        bm.free()
        self.add(verts, faces, colours)

    def cylinder(self, base, top, radius_base, radius_top, colour, sides=7):
        """A tapering cylinder from base to top: a trunk."""
        bx, by, bz = base
        tx, ty, tz = top
        verts, colours = [], []
        for i in range(sides):
            a = 2 * math.pi * i / sides
            verts.append((bx + math.cos(a) * radius_base, by + math.sin(a) * radius_base, bz))
            verts.append((tx + math.cos(a) * radius_top, ty + math.sin(a) * radius_top, tz))
            colours += [vary(colour, 0.2, Vector((a, bz, 0))), vary(colour, 0.2, Vector((a, tz, 1)))]
        faces = [(2 * i, 2 * ((i + 1) % sides), 2 * ((i + 1) % sides) + 1, 2 * i + 1) for i in range(sides)]
        self.add(verts, faces, colours)

    def cone(self, base, height, radius, colour, sides=9, droop=0.25, seed=0):
        """A cone with a drooping, slightly ragged skirt: one layer of a fir tree."""
        bx, by, bz = base
        verts = [(bx, by, bz + height)]
        colours = [mix(colour, linear("#ffffff"), 0.05)]
        for i in range(sides):
            a = 2 * math.pi * i / sides + seed
            r = radius * (0.85 + 0.3 * random.random())
            verts.append((bx + math.cos(a) * r, by + math.sin(a) * r, bz - droop * random.random()))
            colours.append(vary(mix(colour, linear("#000000"), 0.35), 0.15, Vector((a, seed, 0))))
        verts.append((bx, by, bz + height * 0.15))
        colours.append(mix(colour, linear("#000000"), 0.5))
        faces = [(0, 1 + i, 1 + (i + 1) % sides) for i in range(sides)]
        faces += [(sides + 1, 1 + (i + 1) % sides, 1 + i) for i in range(sides)]
        self.add(verts, faces, colours)

    def build(self, name, smooth=True):
        return mesh_object(name, self.verts, self.faces, self.colours, smooth)


# Names use hyphens: three.js drops dots (and colons, slashes and spaces)
# from names when it loads a file.


PROUD = 0.008  # metres the kits' metal fittings stand clear of what they're on


class Kit:
    """Models from one of Quaternius's packs (art/models/), made ours: each a
    list of faces, coloured at each corner from its texture (times its own
    vertex colours, as the pack's materials have it), so they go into one
    vertex-coloured mesh like everything else."""

    def __init__(self, folder, texture=512):
        self.folder, self.texture = folder, texture
        self.models, self.images = {}, {}

    def _image(self, image):
        """A texture's colours, shrunk, as linear RGB."""
        import numpy as np

        if image.name not in self.images:
            image.scale(self.texture, self.texture)
            px = np.empty(len(image.pixels), dtype=np.float32)
            image.pixels.foreach_get(px)
            rgb = px.reshape(self.texture, self.texture, 4)[:, :, :3]
            self.images[image.name] = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
        return self.images[image.name]

    def faces(self, name, ratio=None):
        """A model's faces: (corners, their colours, its material's name) for
        each; simpler, given a ratio of its faces to keep."""
        if (name, ratio) in self.models:
            return self.models[name, ratio]
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(self.folder / f"{name}.gltf"))
        new = [o for o in bpy.data.objects if o not in before]
        faces = []
        for obj in new:
            # (Not one with nothing on it: a helper, like the chest's sphere round it.)
            if obj.type != "MESH" or not obj.data.materials:
                continue
            textures, names = [], []
            for material in obj.data.materials:
                nodes = material.node_tree.nodes if material and material.node_tree else []
                images = [n.image for n in nodes if n.type == "TEX_IMAGE" and n.image]
                image = next((i for i in images if "BaseColor" in i.name or "Page" in i.name), None)
                textures.append(self._image(image) if image and image.size[0] else None)
                names.append(material.name if material else "")
            if ratio:
                obj.modifiers.new("simpler", "DECIMATE").ratio = ratio
            mesh = obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
            uvs = mesh.uv_layers.active.data if mesh.uv_layers.active else None
            tints = mesh.color_attributes.active_color
            turn = obj.matrix_world.to_3x3()
            # Metal laid over wood, as straps and hinges, is only a millimetre
            # or two proud of it: lifted clear, or the two flicker, one through
            # the other, once land.glb rounds where they are. Only on what's
            # mostly not metal (a table's straps, not a candle stand's legs,
            # too thin to swell), and each corner along its own normal, so the
            # fitting's faces stay joined.
            metal = [poly for poly in mesh.polygons if "Metal" in (names[poly.material_index] if names else "")]
            fitted = 0 < len(metal) < len(mesh.polygons) / 2
            lifted = {v for poly in metal for v in poly.vertices} if fitted else set()
            for poly in mesh.polygons:
                texture = textures[poly.material_index] if textures else None
                pts, colours = [], []
                for li, vi in zip(poly.loop_indices, poly.vertices):
                    p = obj.matrix_world @ mesh.vertices[vi].co
                    if vi in lifted:
                        p = p + (turn @ mesh.vertices[vi].normal).normalized() * PROUD
                    pts.append(tuple(p))
                    colour = [1.0, 1.0, 1.0]
                    if texture is not None and uvs:
                        u, v = uvs[li].uv
                        i = min(self.texture - 1, max(0, int((v % 1.0) * self.texture)))
                        j = min(self.texture - 1, max(0, int((u % 1.0) * self.texture)))
                        colour = list(texture[i, j])
                    if tints:
                        tint = tints.data[li if tints.domain == "CORNER" else vi].color
                        colour = [a * b for a, b in zip(colour, tint)]
                    colours.append((*colour, 1.0))
                faces.append((pts, colours, names[poly.material_index] if names else ""))
        for obj in new:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.models[name, ratio] = faces
        return faces

    def tips(self, name):
        """The tops of a model's candles (their wax is the props' material):
        where their flames go."""
        tips = []
        for pts, _, material in self.faces(name):
            if "Props" not in material:
                continue
            for p in pts:
                near = next((i for i, t in enumerate(tips) if math.hypot(t[0] - p[0], t[1] - p[1]) < 0.08), None)
                if near is None:
                    tips.append(p)
                elif p[2] > tips[near][2]:
                    tips[near] = p
        return tips

    @staticmethod
    def placing(at, yaw=0.0, scale=1.0):
        """Where a point of a model goes, its origin at `at`, turned by yaw
        (radians, anticlockwise: 0 faces -y, the way the packs face)."""
        x, y, z = at
        cos, sin = math.cos(yaw), math.sin(yaw)

        def move(p):
            return x + (p[0] * cos - p[1] * sin) * scale, y + (p[0] * sin + p[1] * cos) * scale, z + p[2] * scale

        return move

    def put(self, builder, name, at, yaw=0.0, scale=1.0, ratio=None, tint=None):
        """A model into a builder (see placing; tint, an RGBA colour mixed in
        by its alpha). Its footprint there, as (x0, y0, x1, y1), and its top."""
        move = self.placing(at, yaw, scale)
        xs, ys, top = [], [], at[2]
        for pts, colours, _ in self.faces(name, ratio):
            moved = [move(p) for p in pts]
            xs += [p[0] for p in moved]
            ys += [p[1] for p in moved]
            top = max(top, *(p[2] for p in moved))
            shades = [mix(colour, tint, tint[3]) for colour in colours] if tint else colours
            builder.add(moved, [tuple(range(len(moved)))], [(*s[:3], 1.0) for s in shades])
        return (min(xs), min(ys), max(xs), max(ys)), top


def collider(name, x, y, radius):
    """An empty that tells the game where something solid stands: its scale is the radius."""
    empty = bpy.data.objects.new(name, None)
    empty.location = (x, y, 0)
    empty.scale = (radius, radius, radius)
    bpy.context.collection.objects.link(empty)
    return empty


def export(path, **options):
    # Meshopt compression shrinks the file several times over, and three.js
    # decodes it with no extra files to host. Blender keeps only 12 bits of
    # each point's position, shared by its x, y and z: 150 m out, that rounds
    # every height to 7 cm, and a carpet sinks into the floor under it. 16
    # bits keeps it to a few millimetres, all the way to the edge.
    from io_scene_gltf2.io.exp import meshopt

    meshopt.EXP_FILTER_BITS = 16
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format="GLB",
        export_apply=True,
        export_yup=True,
        export_extras=True,
        export_vertex_color="ACTIVE",
        export_meshopt_compression_enable=True,
        **options,
    )


def preview(path, camera_at, look_at, sun_dir, lens=24):
    """Renders a quick picture of the place, so it can be checked without the game."""
    scene = bpy.context.scene
    cam_data = bpy.data.cameras.new("preview")
    cam_data.lens = lens
    cam_data.clip_end = 2000
    cam = bpy.data.objects.new("preview", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = camera_at
    direction = Vector(look_at) - Vector(camera_at)
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam

    sun_data = bpy.data.lights.new("sun", "SUN")
    sun_data.energy = 4.0
    sun_data.color = (1.0, 0.86, 0.66)
    sun_data.angle = math.radians(3)
    sun = bpy.data.objects.new("sun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (-Vector(sun_dir)).to_track_quat("-Z", "Y").to_euler()

    world = bpy.data.worlds.new("sky")
    scene.world = world
    if hasattr(world, "use_nodes") and not world.use_nodes:
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = linear("#9fc3e6")
    bg.inputs["Strength"].default_value = 1.0

    scene.render.resolution_x = 1280
    scene.render.resolution_y = 800
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "CYCLES"
        scene.cycles.samples = 16
    scene.view_settings.view_transform = "AgX" if "AgX" in [
        v.identifier for v in scene.view_settings.bl_rna.properties["view_transform"].enum_items
    ] else "Filmic"
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


# ---- People: made from Quaternius's kits, on their one humanoid skeleton ------

MODELS = HERE.parent / "models"
OUTFITS = MODELS / "modular-character-outfits/Exports/glTF (Godot-Unreal)/Outfits"
BODIES = MODELS / "universal-base-characters/Base Characters/Godot - UE"
HAIR = MODELS / "universal-base-characters/Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)"
LIBRARIES = [MODELS / f"universal-animation-library-{n}/Unreal-Godot/UAL{n}_Standard.glb" for n in (1, 2)]


def load(path):
    """A glTF file's objects, and its skeleton."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    return new, next((o for o in new if o.type == "ARMATURE"), None)


def remove(objects):
    for o in objects:
        bpy.data.objects.remove(o, do_unlink=True)


def onto(obj, skeleton):
    """A skinned mesh from another file, moved onto this skeleton (the same
    bones, in the same places, so it fits as it is)."""
    obj.parent = skeleton
    for m in obj.modifiers:
        if m.type == "ARMATURE":
            m.object = skeleton


def skinned(name, verts, faces, colours, weights, skeleton):
    """A mesh of our own, moved by the skeleton's bones: weights is a {bone:
    weight} for each vertex."""
    obj = mesh_object(name, verts, faces, colours)
    for i, w in enumerate(weights):
        total = sum(w.values())
        for bone, amount in w.items():
            if amount <= 0:
                continue
            group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
            group.add([i], amount / total, "REPLACE")
    obj.parent = skeleton
    obj.modifiers.new("skeleton", "ARMATURE").object = skeleton
    return obj


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def head(path, skeleton, prefix):
    """A base character's head (the mesh named starting with prefix), cut off
    at the neck, with its eyes and eyebrows, onto this skeleton."""
    body, _ = load(path)
    mesh = next(o for o in body if o.name.startswith(prefix))
    groups = {g.index: g.name for g in mesh.vertex_groups}
    bm = bmesh.new()
    bm.from_mesh(mesh.data)
    deform = bm.verts.layers.deform.active
    cut = [v for v in bm.verts if sum(w for g, w in v[deform].items() if groups[g] in ("Head", "neck_01")) < 0.5]
    bmesh.ops.delete(bm, geom=cut, context="VERTS")
    bm.to_mesh(mesh.data)
    bm.free()
    for o in body:
        if o is mesh or o.name.startswith(("Eyes", "Eyebrows")):
            onto(o, skeleton)
    remove([o for o in body if o.parent != skeleton])
    return mesh


def hairstyle(name, skeleton):
    """One of the kit's hairstyles, onto this skeleton."""
    parts, rig = load(HAIR / f"{name}.gltf")
    mesh = next(o for o in parts if o.type == "MESH")
    # (Some are made for the shorter base characters: up onto the head, by as
    # much as this one's higher than theirs.)
    ours, theirs = (s.matrix_world @ s.data.bones["Head"].head_local for s in (skeleton, rig))
    up = ours - theirs
    for v in mesh.data.vertices:
        v.co += mesh.matrix_world.inverted().to_3x3() @ up
    onto(mesh, skeleton)
    remove([o for o in parts if o is not mesh])
    return mesh


def drop_missing_textures():
    """The base characters' files name normal maps they don't come with: those
    go, or they'd be empty textures, which three.js can't load."""
    for material in bpy.data.materials:
        if material.node_tree:
            for node in list(material.node_tree.nodes):
                if node.type == "TEX_IMAGE" and node.image and not node.image.size[0]:
                    material.node_tree.nodes.remove(node)


def clips(skeleton, names):
    """The Universal Animation Libraries' clips, onto the skeleton, each its
    own NLA track (so each is exported as a clip), named as they are there."""
    before = set(bpy.data.actions)
    library = [o for path in LIBRARIES for o in load(path)[0]]
    actions = [a for a in bpy.data.actions if a not in before]
    skeleton.animation_data_create()
    for name in names:
        action = next(a for a in actions if a.name == name or a.name.startswith(name + "_"))
        track = skeleton.animation_data.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, int(action.frame_range[0]), action)
        if hasattr(strip, "action_slot") and action.slots:
            strip.action_slot = action.slots[0]
    skeleton.animation_data.action = None
    remove(library)


def pose(skeleton, clip, frame):
    """Shows the skeleton at a frame of one of its clips (for previews)."""
    for track in skeleton.animation_data.nla_tracks:
        track.mute = track.name != clip
    bpy.context.scene.frame_set(frame)


def girth(meshes, z, sides, centre=(0.0, 0.01), band=0.015):
    """How far out the meshes reach at this height, all round: for each of
    `sides` directions (at 2πk/sides, from facing -y, as the robes go round),
    the furthest out of their points near that height and that way. For a
    robe snug to what's under it."""
    cx, cy = centre
    reach = [None] * sides
    for obj in meshes:
        for v in obj.data.vertices:
            p = obj.matrix_world @ v.co
            if abs(p.z - z) > band:
                continue
            a = math.atan2(p.x - cx, -(p.y - cy)) % (2 * math.pi)
            k = round(a / (2 * math.pi) * sides) % sides
            r = math.hypot(p.x - cx, p.y - cy)
            reach[k] = max(reach[k] or 0.0, r)
    known = [k for k in range(sides) if reach[k] is not None]
    if not known:
        return [0.0] * sides
    # (Where no point falls, as far out as the nearest that does; then each
    # as far as either neighbour, so nothing between two points pokes out.)
    filled = [reach[k] if reach[k] is not None else reach[min(known, key=lambda j: min(abs(j - k), sides - abs(j - k)))]
              for k in range(sides)]
    return [max(filled[k - 1], filled[k], filled[(k + 1) % sides]) for k in range(sides)]


def hang(girths):
    """A robe's shape, ring by ring from its top, from the girths of what's
    under it (girth): never in from the ring above (it hangs down over what
    it's passed), and smoothed round, so it doesn't follow every lump."""
    sides = len(girths[0])
    widest = list(girths[0])
    rings = []
    for g in girths:
        widest = [max(w, r) for w, r in zip(widest, g)]
        rings.append([sum(widest[(k + d) % sides] for d in (-2, -1, 0, 1, 2)) / 5 for k in range(sides)])
    # (Smoothed, it mustn't come in anywhere past what it was fitted to.)
    return [[max(r, w) for r, w in zip(ring, g)] for ring, g in zip(rings, girths)]


def cut_below(obj, z):
    """Takes away a mesh's points below this height (what a robe hides)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < z], context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
