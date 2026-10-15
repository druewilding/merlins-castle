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

import bmesh
import bpy
from mathutils import Vector, noise


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
