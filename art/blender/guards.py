# The guards at the moat's toll gate, as in their pictures: mail shirts
# under red-and-white tabards, kettle helmets, and halberds.
#
# Made from Quaternius's kits (CC0, art/models/), as Merlin is: the Ranger
# outfit's tunic, arms, legs and boots (its cloth turned to grey mail), and
# the head of a Universal Base Character, with the kit's beard
# (guard-beard: the game shows it on one of them, so they don't look the
# same). The tabard, the belt over it, the helmet and the halberd are made
# here. All of it shares the kits' one skeleton, so the Universal Animation
# Libraries' clips play on them (ANIMS). The halberd is held in his right
# fist (moved by that hand only), upright as he stands idle, its foot on the
# ground beside him.
#
# He stands in a T-pose, his feet at z = 0, facing -y (the way the kits face).

import colorsys
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector, kdtree

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

OUTFIT = c.OUTFITS / "Male_Ranger.gltf"
BODY = c.BODIES / "Superhero_Male_FullBody.gltf"

ANIMS = ["Idle_Loop", "Interact", "Yes"]
IDLE = ("Idle_Loop", 20)  # the pose the halberd's upright in
TEXTURE = 1024  # the size every texture is shrunk to (the kits' are 2048 and 4096)

RED = "#b3262b"
WHITE = "#efe6d2"
TRIM = "#c9a043"
STEEL = "#9ea4aa"
STEEL_DARK = "#6c7176"
LEATHER = "#5a3a22"
SHAFT = "#7a5230"

SIDES = 32  # round the tabard and the helmet
TOP, HEM, WAIST = 1.58, 0.74, 1.04  # the tabard: from his shoulders to his thighs; belted here
PANEL = 1.0  # radians either side of his front (and back) the tabard reaches round him
FIT = 0.012  # metres it stands clear of his tunic, at its snuggest

# ---- The outfit: his skeleton, tunic, arms, legs and boots ---------------------

outfit, skeleton = c.load(OUTFIT)
skeleton.name = "guard"
keep = ("Body", "Arms", "Feet", "Legs")
c.remove([o for o in outfit if o.type == "MESH" and (not any(k in o.name for k in keep) or "Bracer" in o.name)])

# ---- His head, and a beard (for one of them) ---------------------------------

head = c.head(BODY, skeleton, "SuperHero")
beard = c.hairstyle("Hair_Beard", skeleton)
beard.name = "guard-beard"

# ---- His tabard: front and back, from his chest to his thighs ------------------

# (Round his tunic, its straps and buckles, and his breeches.)
under = [o for o in skeleton.children if o.name.startswith(("Male_Ranger_Body", "Male_Ranger_Legs"))]
RINGS = 18
heights = [TOP + (HEM - TOP) * i / RINGS for i in range(RINGS + 1)]
# (Bands meeting, so nothing's missed between them.) Down to his belt, as
# snug as what's under it (an oval, his chest broader than his waist, and
# cinched in by the belt); below it, hanging down from there, never in.
girths = [c.girth(under, z, SIDES, (0.0, 0.01), band=0.03) for z in heights]
belted = next(i for i, z in enumerate(heights) if z <= WAIST)
snug = [[max(g[k - 1], g[k], g[(k + 1) % SIDES]) for k in range(SIDES)] for g in girths[:belted]]
snug += c.hang(girths[belted:])


def tabard_colour(u, z, seed):
    """Quartered red and white, edged in gold."""
    if abs(u) > 0.85 or z < HEM + 0.045:
        return c.vary(c.linear(TRIM), 0.1, Vector((u * 5, z * 9, seed)))
    red = (u < 0) != (z < (TOP + HEM) / 2 + 0.06)
    return c.vary(c.linear(RED if red else WHITE), 0.08, Vector((u * 3, z * 6, seed)))


verts, faces, colours, weights = [], [], [], []
ACROSS = 10
for side, facing in ((0, 0.0), (1, math.pi)):  # his front, then his back
    grid = []
    for i, z in enumerate(heights):
        t = i / RINGS
        row = []
        for j in range(ACROSS + 1):
            u = -1 + 2 * j / ACROSS
            # (Narrower at the top, between his shoulders.)
            a = facing + u * PANEL * (1 - 0.35 * c.smooth((z - 1.42) / 0.16))
            k = round(a / (2 * math.pi) * SIDES) % SIDES
            r = snug[i][k] + FIT + 0.012 * max(0.0, (WAIST - z) / (WAIST - HEM))
            x = math.sin(a) * r
            y = -math.cos(a) * r
            low = c.smooth((WAIST + 0.08 - z) / 0.25)
            row.append(((x, y + 0.01, z), {"spine_03": (1 - low) * c.smooth((z - 1.2) / 0.2), "spine_01": (1 - low) * 0.6,
                                           "pelvis": low + 0.05, "thigh_l": 0.12 * low * (x > 0),
                                           "thigh_r": 0.12 * low * (x < 0)}))
        grid.append(row)
    # (Each piece its own colour, sharp at the quarters' edges.)
    for i in range(RINGS):
        for j in range(ACROSS):
            u = -1 + 2 * (j + 0.5) / ACROSS
            z = (heights[i] + heights[i + 1]) / 2
            colour = tabard_colour(u * (1 if side == 0 else -1), z, side)
            first = len(verts)
            for p, w in (grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]):
                verts.append(p)
                weights.append(w)
                colours.append(colour)
            faces.append((first, first + 1, first + 2, first + 3))


# What's under it moves it as it moves what's under it (so, his body bending,
# nothing comes through it): each of its points by the bones that move the
# nearest point of his tunic. (Below his belt, it hangs from his hips.)
groups = {}
tree = kdtree.KDTree(sum(len(o.data.vertices) for o in under))
n = 0
for obj in under:
    names = {g.index: g.name for g in obj.vertex_groups}
    for v in obj.data.vertices:
        tree.insert(obj.matrix_world @ v.co, n)
        groups[n] = {names[g.group]: g.weight for g in v.groups if g.weight > 0}
        n += 1
tree.balance()


def as_under(p, own):
    """The weights of the nearest point of what's under it, above the belt; its own, below."""
    _, nearest, _ = tree.find(Vector(p))
    t = c.smooth((p[2] - (WAIST - 0.06)) / 0.12)
    mixed = {bone: w * (1 - t) for bone, w in own.items()}
    # (Only his body's bones: not his arms', which would swing its corners out at his shoulders.)
    body = {bone: w for bone, w in groups[nearest].items() if bone.startswith(("pelvis", "spine", "neck"))}
    total = sum(body.values()) or 1.0
    for bone, w in (body or {"spine_03": 1.0}).items():
        mixed[bone] = mixed.get(bone, 0.0) + w / total * t
    return mixed


weights = [as_under(p, w) for p, w in zip(verts, weights)]
tabard = c.skinned("guard-tabard", verts, faces, colours, weights, skeleton)
# (And his tunic, under it, pressed in: nothing of it, a strap or a stud,
# pokes out through it.)
for obj in under:
    to_mesh = obj.matrix_world.inverted()
    for v in obj.data.vertices:
        p = obj.matrix_world @ v.co
        if not HEM < p.z < TOP:
            continue
        a = math.atan2(p.x, -(p.y - 0.01)) % (2 * math.pi)
        if min(abs(a), abs(a - math.pi), abs(a - 2 * math.pi)) > PANEL + 0.05:
            continue
        i = min(RINGS, max(0, round((TOP - p.z) / (TOP - HEM) * RINGS)))
        k = round(a / (2 * math.pi) * SIDES) % SIDES
        limit = snug[i][k] + FIT - 0.006
        r = math.hypot(p.x, p.y - 0.01)
        if r > limit:
            p = Vector((p.x * limit / r, 0.01 + (p.y - 0.01) * limit / r, p.z))
            v.co = to_mesh @ p
tabard.data.materials.append(c.vertex_material())

# Its belt, round his waist over it.
verts, faces, colours = [], [], []
k_ = heights.index(min(heights, key=lambda z: abs(z - WAIST)))
for ring, dz in enumerate((-0.035, 0.035)):
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        r = snug[k_][k] + FIT + 0.01  # (just over the tabard, and as snug: an oval)
        verts.append((math.sin(a) * r, -math.cos(a) * r + 0.01, WAIST + dz))
        buckle = abs(math.sin(a / 2)) < 0.08
        colours.append(c.linear(TRIM if buckle else LEATHER))
faces = [(k, (k + 1) % SIDES, SIDES + (k + 1) % SIDES, SIDES + k) for k in range(SIDES)]
belt = c.skinned("guard-belt", verts, faces, colours, [as_under(p, {"pelvis": 1.0}) for p in verts], skeleton)
belt.data.materials.append(c.vertex_material())

# ---- His helmet: a kettle hat, a round steel cap with a wide brim -------------

# Fitted to his head (an oval, as heads are): its rim snug round it, just
# above his eyebrows, and its crown just over the top of it, never in.
BROW = 1.75  # where it sits on his head (above his eyes)
SNUG = 0.008  # metres it stands clear of his head
DOME = 8
skull = [skeleton.matrix_world.inverted() @ head.matrix_world @ v.co for v in head.data.vertices]
cy = sum(p.y for p in skull if p.z > BROW) / max(1, sum(1 for p in skull if p.z > BROW))
crown = max(p.z for p in skull) + SNUG  # (how high it comes)
rise = crown - BROW
levels = [BROW + rise * i / DOME for i in range(DOME + 1)]
heads = [c.girth([head], z, SIDES, (0.0, cy), band=rise / DOME) for z in levels]


def oval(ring):
    """A ring smoothed round, then made just big enough to cover what it was."""
    smooth_ = [sum(ring[(k + d) % SIDES] for d in range(-3, 4)) / 7 for k in range(SIDES)]
    grow = max(r / max(s_, 1e-6) for r, s_ in zip(ring, smooth_))
    return [s_ * grow for s_ in smooth_]


rim = oval([r + SNUG for r in heads[0]])
dome = []
for i in range(DOME):
    t = i / DOME
    need = [max(h[k] for h in heads[i:]) + SNUG for k in range(SIDES)]
    ring = [r * math.sqrt(1 - t * t) for r in rim]
    grow = max(1.0, *(n / max(r, 1e-6) for n, r in zip(need, ring)))
    dome.append([r * grow for r in ring])
verts, faces, colours = [], [], []
for i, z in enumerate(levels[:-1]):
    t = i / DOME
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        # (Round as a dome, from its rim; but never into his head.)
        r = dome[i][k]
        verts.append((math.sin(a) * r, cy - math.cos(a) * r, z))
        ridge = abs(math.sin(a)) < 0.06  # (a ridge over the top, front to back)
        colours.append(c.vary(c.linear(STEEL_DARK if ridge or i == 0 else STEEL), 0.06, Vector((a, i, 3))))
top = len(verts)
verts.append((0.0, cy, crown))
colours.append(c.linear(STEEL))
for i in range(DOME - 1):
    for k in range(SIDES):
        a, b = i * SIDES + k, i * SIDES + (k + 1) % SIDES
        faces.append((a, b, b + SIDES, a + SIDES))
last = (DOME - 1) * SIDES
faces += [(last + k, last + (k + 1) % SIDES, top) for k in range(SIDES)]
# The brim, out and a little down, all round (an oval, as its rim is).
base = len(verts)
for ring, (out_, dz) in enumerate(((0.0, 0.0), (0.0, -0.01), (0.07, -0.016), (0.076, -0.024))):
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        r = rim[k] + out_
        verts.append((math.sin(a) * r, cy - math.cos(a) * r, BROW + dz))
        colours.append(c.vary(c.linear(STEEL_DARK if ring in (1, 3) else STEEL), 0.06, Vector((a, ring, 4))))
for ring in range(3):
    for k in range(SIDES):
        a, b = base + ring * SIDES + k, base + ring * SIDES + (k + 1) % SIDES
        faces.append((a, a + SIDES, b + SIDES, b))
helmet = c.skinned("guard-helmet", verts, faces, colours, [{"Head": 1.0}] * len(verts), skeleton)
helmet.data.materials.append(c.vertex_material())

# ---- His halberd, in his right fist ----------------------------------------

c.clips(skeleton, ANIMS)
c.pose(skeleton, *IDLE)
bpy.context.view_layer.update()
fist = skeleton.pose.bones["hand_r"]
grip = fist.head + fist.y_axis * 0.085 + fist.x_axis * 0.012  # (through his fist, in the skeleton's space)
held = fist.bone.matrix_local @ fist.matrix.inverted()  # from where it's held, idle, to how it's made
verts, faces, colours = [], [], []
d = Vector((-1.0, 0.0, 0.0))  # its blade, out to his right
e = Vector((0.0, 0.0, 1.0)).cross(d)


def prism(outline, thick, colour, centre_z):
    """A flat piece of its head: an outline (out along d, up) thick across."""
    first = len(verts)
    for side in (-1, 1):
        for s, z in outline:
            p = Vector((grip.x, grip.y, centre_z)) + d * s + Vector((0, 0, z)) + e * (side * thick / 2)
            verts.append(tuple(p))
            colours.append(c.vary(c.linear(colour), 0.06, p * 20))
    n = len(outline)
    faces.append(tuple(first + k for k in range(n))[::-1])
    faces.append(tuple(first + n + k for k in range(n)))
    for k in range(n):
        a, b = first + k, first + (k + 1) % n
        faces.append((a, b, b + n, a + n))


def rod(z0, z1, r0, r1, colour, sides=8):
    first = len(verts)
    for z, r in ((z0, r0), (z1, r1)):
        for k in range(sides):
            a = 2 * math.pi * k / sides
            verts.append((grip.x + math.cos(a) * r, grip.y + math.sin(a) * r, z))
            colours.append(c.vary(c.linear(colour), 0.08, Vector((a, z * 4, 1))))
    for k in range(sides):
        a, b = first + k, first + (k + 1) % sides
        faces.append((a, b, b + sides, a + sides))
    faces.append(tuple(first + sides + k for k in range(sides)))
    faces.append(tuple(first + k for k in range(sides))[::-1])


FOOT, SOCKET = 0.03, 2.05
rod(FOOT, SOCKET, 0.021, 0.019, SHAFT)
rod(FOOT, FOOT + 0.06, 0.024, 0.024, STEEL_DARK)  # (shod with iron)
rod(SOCKET - 0.1, SOCKET + 0.06, 0.026, 0.026, STEEL_DARK)  # the socket
rod(SOCKET + 0.06, SOCKET + 0.4, 0.016, 0.002, STEEL, sides=4)  # the spike on top
# The axe blade, curved along its edge, and the hook behind.
edge = [(0.21 + 0.035 * math.sin(math.pi * k / 6), -0.09 + 0.3 * k / 6) for k in range(7)]
prism([(0.02, -0.04), *edge, (0.02, 0.17)], 0.012, STEEL, SOCKET)
prism([(-0.02, 0.03), (-0.14, 0.11), (-0.02, 0.09)], 0.014, STEEL_DARK, SOCKET)
verts = [tuple(held @ Vector(v)) for v in verts]
halberd = c.skinned("guard-halberd", verts, faces, colours, [{"hand_r": 1.0}] * len(verts), skeleton)
halberd.data.materials.append(c.vertex_material())
for track in skeleton.animation_data.nla_tracks:
    track.mute = False
for pb in skeleton.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.context.scene.frame_set(0)

# Tabard and helmet, seen from inside too.
c.vertex_material().use_backface_culling = False

# ---- Textures: shrunk, his cloth turned to grey mail ---------------------------

c.drop_missing_textures()

for image in bpy.data.images:
    if not image.size[0]:
        continue
    if image.size[0] > TEXTURE:
        image.scale(TEXTURE, TEXTURE)
    name = image.name.lower()
    if "basecolor" in name and "ranger" in name:
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        rgb = rgba[:, :3]
        # The greens (the cloth) to steel grey, the browns (leather) left be.
        mx, mn = rgb.max(1), rgb.min(1)
        for i in np.nonzero((rgb[:, 1] >= mx - 1e-6) & (mx - mn > 0.04))[0]:
            h, s, v = colorsys.rgb_to_hsv(*rgb[i])
            rgb[i] = colorsys.hsv_to_rgb(0.6, 0.03, min(1.0, 0.22 + 0.6 * v))
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    image.pack()

if out:
    for o in bpy.data.objects:
        o.select_set(o == skeleton or o.parent == skeleton)
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS", export_image_format="WEBP")

if preview:
    # Standing idle, from the front, a little to one side; and from his side.
    c.pose(skeleton, *IDLE)
    c.preview(preview, (1.0, -3.0, 1.4), (0, 0, 1.05), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-side.png"), (-3.2, -0.6, 1.3), (0, 0, 1.05), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-face.png"), (0.35, -1.3, 1.62), (0, 0, 1.45), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-back.png"), (-0.8, 3.0, 1.5), (0, 0, 1.15), (0.4, 0.8, -1), lens=40)
    c.pose(skeleton, "Interact", 30)
    c.preview(preview.replace(".png", "-taking.png"), (1.0, -3.0, 1.4), (0, 0, 1.05), (0.4, 0.8, -1), lens=40)
