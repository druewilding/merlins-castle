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
from mathutils import Matrix, Vector

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
FIT = 0.025  # metres it stands clear of his tunic, at its snuggest (over its studs)

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
snug = c.hang([c.girth(under, z, SIDES, (0.0, 0.01), band=0.03) for z in heights])  # (bands meeting: nothing missed between)


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
            a = facing + u * PANEL
            k = round(a / (2 * math.pi) * SIDES) % SIDES
            r = snug[i][k] + FIT + 0.03 * max(0.0, (WAIST - z) / (WAIST - HEM))
            # (Below the belt, hanging flat, not round his legs.)
            flat = c.smooth((WAIST - z) / 0.12)
            x = math.sin(a) * r
            y = -math.cos(a) * r
            y = y * (1 - flat) + (-1 if side == 0 else 1) * max(abs(y), 0.13 + 0.02 * t) * flat
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
tabard = c.skinned("guard-tabard", verts, faces, colours, weights, skeleton)
tabard.data.materials.append(c.vertex_material())

# Its belt, round his waist over it.
verts, faces, colours = [], [], []
k_ = heights.index(min(heights, key=lambda z: abs(z - WAIST)))
for ring, dz in enumerate((-0.035, 0.035)):
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        r = snug[k_][k] + FIT + 0.012
        verts.append((math.sin(a) * r, -math.cos(a) * r + 0.01, WAIST + dz))
        buckle = abs(math.sin(a / 2)) < 0.08
        colours.append(c.linear(TRIM if buckle else LEATHER))
faces = [(k, (k + 1) % SIDES, SIDES + (k + 1) % SIDES, SIDES + k) for k in range(SIDES)]
belt = c.skinned("guard-belt", verts, faces, colours, [{"spine_01": 0.3, "pelvis": 0.7}] * len(verts), skeleton)
belt.data.materials.append(c.vertex_material())

# ---- His helmet: a kettle hat, a round steel cap with a wide brim -------------

skull = [skeleton.matrix_world.inverted() @ head.matrix_world @ v.co for v in head.data.vertices]
BROW = 1.765  # where it sits on his head (above his eyes)
TILT = 8  # degrees it's tipped back, so you see his eyes under its brim
cy = sum(p.y for p in skull if p.z > BROW) / max(1, sum(1 for p in skull if p.z > BROW))
cap = Vector((0.0, cy, BROW))
rx, ry, rz = 0.1, 0.115, 0.1
# (Big enough to cover all of his head above its brim.)
fit = max(math.sqrt((p.x / rx) ** 2 + ((p.y - cy) / ry) ** 2 + ((p.z - BROW) / rz) ** 2) for p in skull if p.z > BROW)
rx, ry, rz = (r * fit * 1.1 for r in (rx, ry, rz))
verts, faces, colours = [], [], []
DOME = 8
for i in range(DOME + 1):
    up = (i / DOME) * math.pi / 2
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        verts.append((math.sin(a) * rx * math.cos(up), cy - math.cos(a) * ry * math.cos(up), BROW + rz * math.sin(up)))
        ridge = abs(math.sin(a)) < 0.06  # (a ridge over the top, front to back)
        colours.append(c.vary(c.linear(STEEL_DARK if ridge or i == 0 else STEEL), 0.06, Vector((a, i, 3))))
for i in range(DOME):
    for k in range(SIDES):
        a, b = i * SIDES + k, i * SIDES + (k + 1) % SIDES
        faces.append((a, b, b + SIDES, a + SIDES))
# The brim, out and a little down, all round.
base = len(verts)
for ring, (out_, dz) in enumerate(((1.0, 0.0), (1.0, -0.01), (1.0 + 0.075 / rx, -0.025), (1.0 + 0.082 / rx, -0.034))):
    for k in range(SIDES):
        a = 2 * math.pi * k / SIDES
        grow = out_ - 1
        verts.append((math.sin(a) * (rx + grow * rx), cy - math.cos(a) * (ry + grow * rx), BROW + dz))
        colours.append(c.vary(c.linear(STEEL_DARK if ring in (1, 3) else STEEL), 0.06, Vector((a, ring, 4))))
for ring in range(3):
    for k in range(SIDES):
        a, b = base + ring * SIDES + k, base + ring * SIDES + (k + 1) % SIDES
        faces.append((a, a + SIDES, b + SIDES, b))
tip = Matrix.Rotation(math.radians(-TILT), 4, "X")
verts = [tuple(tip @ (Vector(v) - cap) + cap) for v in verts]
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
    c.pose(skeleton, "Interact", 30)
    c.preview(preview.replace(".png", "-taking.png"), (1.0, -3.0, 1.4), (0, 0, 1.05), (0.4, 0.8, -1), lens=40)
