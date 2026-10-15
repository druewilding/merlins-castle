# Merlin, as in his pictures: tall, a long silver beard and hair, a deep blue
# starry robe and a pointed hat.
#
# Made from Quaternius's kits (CC0, art/models/): the Ranger outfit's tunic,
# arms and boots (its cloth turned from green to Merlin's blue), the head of a
# Universal Base Character, its long hair, and its beard drawn out long. The
# robe and the hat are made here. All of it shares the kits' one humanoid
# skeleton, so every clip of the Universal Animation Library plays on him: the
# ones he needs are copied in (ANIMS), named as they are there.
#
# He stands in a T-pose, his feet at z = 0, facing -y (the way the kits face).

import colorsys
import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

MODELS = HERE.parent / "models"
OUTFIT = MODELS / "modular-character-outfits/Exports/glTF (Godot-Unreal)/Outfits/Male_Ranger.gltf"
BODY = MODELS / "universal-base-characters/Base Characters/Godot - UE/Superhero_Male_FullBody.gltf"
HAIR = MODELS / "universal-base-characters/Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)"
LIBRARY = MODELS / "universal-animation-library-1/Unreal-Godot/UAL1_Standard.glb"

ANIMS = [
    "Idle_Loop",
    "Walk_Loop",
    "Walk_Formal_Loop",
    "Spell_Simple_Enter",
    "Spell_Simple_Idle_Loop",
    "Spell_Simple_Exit",
]
TEXTURE = 1024  # the size every texture is shrunk to (the kits' are 2048 and 4096)

BLUE = 0.64  # the hue his cloth is turned to (from the Ranger's green)
ROBE = "#2c3a94"
GOLD = "#e0b04a"
HAT_BAND = "#4a2f7a"

WAIST = 1.16  # the robe hangs from here (the belt)...
HEM = 0.035  # ...down to here
HEAD = (0.0, 0.0, 1.735)  # the middle of the hat's brim
SIDES = 28  # round the robe and the hat
TIP = 14  # degrees the hat's tipped back


def load(path):
    """A glTF file's objects, and its skeleton."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    return new, next((o for o in new if o.type == "ARMATURE"), None)


def remove(objects):
    for o in objects:
        bpy.data.objects.remove(o, do_unlink=True)


def onto(obj):
    """A skinned mesh from another file, moved onto Merlin's skeleton (the same
    bones, in the same places, so it fits as it is)."""
    obj.parent = skeleton
    for m in obj.modifiers:
        if m.type == "ARMATURE":
            m.object = skeleton


def skinned(name, verts, faces, colours, weights):
    """A mesh of our own, moved by his bones: weights is a {bone: weight} for each vertex."""
    obj = c.mesh_object(name, verts, faces, colours)
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


# ---- The outfit: his skeleton, tunic, arms and boots -------------------------

outfit, skeleton = load(OUTFIT)
skeleton.name = "merlin"
keep = ("Body", "Arms", "Feet", "Legs")
remove([o for o in outfit if o.type == "MESH" and (not any(k in o.name for k in keep) or "Bracer" in o.name)])

# ---- His head: from the base character, cut off at the neck ------------------

body, _ = load(BODY)
head = next(o for o in body if o.name.startswith("SuperHero"))
groups = {g.index: g.name for g in head.vertex_groups}
bm = bmesh.new()
bm.from_mesh(head.data)
deform = bm.verts.layers.deform.active
cut = [v for v in bm.verts if sum(w for g, w in v[deform].items() if groups[g] in ("Head", "neck_01")) < 0.5]
bmesh.ops.delete(bm, geom=cut, context="VERTS")
bm.to_mesh(head.data)
bm.free()
for o in body:
    if o is head or o.name.startswith(("Eyes", "Eyebrows")):
        onto(o)
remove([o for o in body if o.parent != skeleton])

# ---- His hair, and a long beard ----------------------------------------------

hair = []
for name in ("Hair_Long", "Hair_Beard"):
    parts, _ = load(HAIR / f"{name}.gltf")
    mesh = next(o for o in parts if o.type == "MESH")
    onto(mesh)
    remove([o for o in parts if o is not mesh])
    hair.append(mesh)
long_hair, beard = hair

# The beard drawn down from his chin to the middle of his chest (and out a
# little, over it), and his hair down past his shoulders.
for mesh, start, stretch, forward in ((beard, 1.64, 4.5, 0.25), (long_hair, 1.6, 1.7, 0.0)):
    for v in mesh.data.vertices:
        if v.co.z < start:
            drop = (start - v.co.z) * (stretch - 1)
            v.co.z -= drop
            v.co.y -= drop * forward
            if mesh is beard:
                v.co.x *= 1 + drop * 4  # (and wider, not drawn into a string)

# ---- His robe: from the belt to his ankles, flaring out ---------------------

RINGS = 20
verts, colours, weights = [], [], []
for i in range(RINGS + 1):
    t = i / RINGS  # 0 at the waist, 1 at the hem
    z = WAIST + (HEM - WAIST) * t
    radius = 0.165 + 0.21 * t**1.1
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        # Soft folds, deeper towards the hem.
        r = radius * (1 + 0.05 * t * math.sin(a * 9 + 1.3))
        x, y = math.sin(a) * r, -math.cos(a) * r
        verts.append((x, y + 0.02, z))
        # Gold trim round the hem and down the front.
        trim = t > 0.96 or (abs(math.sin(a / 2) * 2) < 0.12 and t > 0.05)
        colours.append(c.vary(c.linear(GOLD if trim else ROBE), 0.12, Vector((a * 2, t * 6, 0))))
        # Moved by his hips at the top, and below by his legs, each side by its
        # own: mostly by his thigh, so the hem swings out in a wide arc with each
        # stride (and his knee stays inside), and at the back by his calf too, as
        # his heel lifts behind him.
        side = smooth((x / max(radius, 0.01) + 0.35) / 0.7)  # 0 on his right, 1 on his left
        back = smooth((y / max(radius, 0.01) + 0.3) / 1.0)  # 0 at his front, 1 at his back
        hip = 1 - smooth(t * 2.5)
        calf = (0.25 + 0.5 * back) * smooth((t - 0.4) * 2)
        thigh = (1 - hip) - calf
        weights.append(
            {
                "pelvis": hip + 0.08,
                "thigh_l": thigh * side,
                "thigh_r": thigh * (1 - side),
                "calf_l": calf * side,
                "calf_r": calf * (1 - side),
            }
        )
faces = []
for i in range(RINGS):
    for k in range(SIDES):
        a, b = i * SIDES + k, i * SIDES + (k + 1) % SIDES
        faces.append((a, b, b + SIDES, a + SIDES))
robe = skinned("merlin-robe", verts, faces, colours, weights)
robe.data.materials.append(c.vertex_material())

# ---- His hat: a tall cone, its tip bent back, on a wide brim ----------------

verts, colours, faces = [], [], []
hx, hy, hz = HEAD


def on_cone(t, a, lift=0.0):
    """A point on the hat's cone, t from its foot (0) to its tip (1), round it by a."""
    r = 0.115 * (1 - t) ** 1.15 + 0.004 + lift
    return Vector((hx + math.sin(a) * r, hy - math.cos(a) * r + 0.16 * t**2.2, hz + 0.5 * t - 0.12 * t**3))


# The brim: a flat ring, drooping a little at its edge.
for ring, (r, dz) in enumerate([(0.11, 0.0), (0.2, -0.01), (0.27, -0.035)]):
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        verts.append((hx + math.sin(a) * r, hy - math.cos(a) * r, hz + dz))
        colours.append(c.vary(c.linear(ROBE), 0.12, Vector((a, ring, 3))))
for ring in range(2):
    for k in range(SIDES):
        a, b = ring * SIDES + k, ring * SIDES + (k + 1) % SIDES
        faces.append((a, a + SIDES, b + SIDES, b))
# The cone, bending back (+y) as it rises, with a band round its foot.
CONE = 12
base = len(verts)
for i in range(CONE + 1):
    t = i / CONE
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        verts.append(tuple(on_cone(t, a)))
        colours.append(c.vary(c.linear(HAT_BAND if t < 0.1 else ROBE), 0.12, Vector((a, t * 5, 4))))
for i in range(CONE):
    for k in range(SIDES):
        a, b = base + i * SIDES + k, base + i * SIDES + (k + 1) % SIDES
        faces.append((a, b, b + SIDES, a + SIDES))
# A few gold stars (little flat diamonds) scattered on the cone.
rng = random.Random(3)
for _ in range(16):
    t, a = 0.15 + 0.6 * rng.random(), rng.random() * 2 * math.pi
    centre = on_cone(t, a, 0.002)
    up, across = Vector((0, 0, 1)), Vector((math.cos(a), math.sin(a), 0))
    s = 0.014
    first = len(verts)
    for p in (up * s, across * s * 0.7, -up * s, -across * s * 0.7):
        verts.append(tuple(centre + p))
        colours.append(c.linear(GOLD))
    faces.append((first, first + 1, first + 2, first + 3))
# Tipped back on his head, so his face shows under the brim.
tip = Matrix.Rotation(math.radians(-TIP), 4, "X")
pivot = Vector((hx, hy + 0.05, hz - 0.06))
verts = [tuple(tip @ (Vector(v) - pivot) + pivot) for v in verts]
hat = skinned("merlin-hat", verts, faces, colours, [{"Head": 1.0}] * len(verts))
hat.data.materials.append(c.vertex_material())

# Robe and hat, seen from inside too (the brim from below, the hem lifting).
c.vertex_material().use_backface_culling = False

# His hair, under the hat: none pokes out through its crown.
for v in long_hair.data.vertices:
    if v.co.z > hz - 0.01:
        v.co.z = hz - 0.01 + (v.co.z - hz) * 0.2

# ---- Textures: shrunk, his cloth turned blue, his hair silver ----------------

# (The base character's file names two normal maps it doesn't come with: those
# go, or they'd be empty textures, which three.js can't load.)
for material in bpy.data.materials:
    if material.node_tree:
        for node in list(material.node_tree.nodes):
            if node.type == "TEX_IMAGE" and node.image and not node.image.size[0]:
                material.node_tree.nodes.remove(node)

for image in bpy.data.images:
    if not image.size[0]:
        continue
    if image.size[0] > TEXTURE:
        image.scale(TEXTURE, TEXTURE)
    name = image.name.lower()
    if "basecolor" in name and ("ranger" in name or "hair" in name):
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        rgb = rgba[:, :3]
        if "ranger" in name:
            # The greens (the cloth) to his blue, the browns (leather) left be.
            mx, mn = rgb.max(1), rgb.min(1)
            for i in np.nonzero((rgb[:, 1] >= mx - 1e-6) & (mx - mn > 0.04))[0]:
                h, s, v = colorsys.rgb_to_hsv(*rgb[i])
                rgb[i] = colorsys.hsv_to_rgb(BLUE, min(1.0, s * 1.05), min(1.0, 1.25 * v**0.75))
        else:
            # Grey hair to silver: lighter, and a touch cooler.
            rgb[:] = 1 - (1 - rgb) * 0.35
            rgb[:, 2] = np.minimum(1, rgb[:, 2] * 1.03)
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    # Packed into the file, as it's been changed here.
    image.pack()

# ---- His animations ------------------------------------------------------------

before = set(bpy.data.actions)
library, _ = load(LIBRARY)
actions = [a for a in bpy.data.actions if a not in before]
skeleton.animation_data_create()
for name in ANIMS:
    action = next(a for a in actions if a.name == name or a.name.startswith(name + "_"))
    track = skeleton.animation_data.nla_tracks.new()
    track.name = name
    strip = track.strips.new(name, int(action.frame_range[0]), action)
    if hasattr(strip, "action_slot") and action.slots:
        strip.action_slot = action.slots[0]
skeleton.animation_data.action = None
remove(library)

if out:
    for o in bpy.data.objects:
        o.select_set(o == skeleton or o.parent == skeleton)
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS", export_image_format="WEBP")

if preview:
    # Standing idle, seen from the front, a little to one side; and mid-stride,
    # from the side and the front (-stride.png, -stride-front.png).
    def pose(clip, frame):
        for track in skeleton.animation_data.nla_tracks:
            track.mute = track.name != clip
        bpy.context.scene.frame_set(frame)

    pose("Idle_Loop", 10)
    c.preview(preview, (1.2, -4.2, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    pose("Walk_Formal_Loop", 8)
    c.preview(preview.replace(".png", "-stride.png"), (4.3, 0.3, 1.0), (0, 0, 0.85), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-stride-front.png"), (0.8, -4.3, 1.0), (0, 0, 0.85), (0.4, 0.8, -1), lens=40)
