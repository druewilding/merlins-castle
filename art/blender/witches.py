# The witches who dance in the forest, as in their pictures: ragged dark
# robes, wild grey hair and tall crooked hats.
#
# Made from Quaternius's kits (CC0, art/models/), as Merlin is: the Peasant
# outfit's bodice, sleeves and boots (its colours dulled), the head of a
# Universal Base Character (its nose made longer), and its long hair. The robes
# and the hats are made here, three of each (witch-robe-0..2, witch-hat-0..2):
# the game shows one of each on each witch it makes from this one, so they
# don't all look the same. All of it shares the kits' one skeleton, so the
# Universal Animation Libraries' clips play on them (ANIMS).
#
# She stands in a T-pose, her feet at z = 0, facing -y (the way the kits face).

import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

OUTFIT = c.OUTFITS / "Female_Peasant.gltf"
BODY = c.BODIES / "Superhero_Female_FullBody.gltf"

ANIMS = [
    "Dance_Loop",
    "Crouch_Idle_Loop",
    "Jog_Fwd_Loop",
    "Jump_Start",
    "Sitting_Idle_Loop",
    "Idle_Loop",
]
TEXTURE = 1024  # the size every texture is shrunk to

# Each witch's robe and hat (and her hat's band).
WITCHES = [
    {"robe": "#54465f", "hat": "#2f2836", "band": "#7a3d66", "bend": (0.10, 0.12), "tall": 0.5},
    {"robe": "#66533b", "hat": "#3b2f23", "band": "#8a7434", "bend": (-0.13, 0.08), "tall": 0.46},
    {"robe": "#48573f", "hat": "#2b3424", "band": "#6b3a2e", "bend": (0.04, 0.17), "tall": 0.54},
]

WAIST = 1.1  # the robe hangs from here (from under her bodice)...
HEM = 0.03  # ...down to here, at its longest rags
RAGS = 13  # points round its hem
CUFF = (0.045, 0.11, 0.03)  # her sleeves' cuffs: how wide at her forearm, at their ends, and how far past her wrist
HEAD = (0.0, 0.007, 1.715)  # the middle of the hat's brim: on her hair
CROWN = (0.094, 0.118)  # the hat's foot, across and front to back: just over her hair
SIDES = 28  # round the robe and the hat
TIP = 9  # degrees the hats are tipped back
NOSE = (0.032, 0.012)  # metres her nose is made longer, and its tip bent down


# ---- The outfit: her skeleton, bodice, sleeves and boots --------------------

outfit, skeleton = c.load(OUTFIT)
skeleton.name = "witch"
c.remove([o for o in outfit if o.type == "MESH" and not o.name.startswith("Female_Peasant")])

# ---- Her head, with a longer nose; her hair, wild ---------------------------

head = c.head(BODY, skeleton, "Superhero_Female")
tip = max((v.co for v in head.data.vertices), key=lambda p: -p.y).copy()
for v in head.data.vertices:
    # (Drawn out forward and down from her face, most at its tip.)
    near = 1 - min(1.0, math.hypot(v.co.x / 0.024, (v.co.z - tip.z) / 0.03))
    if near > 0 and v.co.y < tip.y + 0.04:
        reach = near * c.smooth((tip.y + 0.04 - v.co.y) / 0.04)
        v.co.y -= NOSE[0] * reach
        v.co.z -= NOSE[1] * reach * reach

hair = c.hairstyle("Hair_Long", skeleton)
for v in hair.data.vertices:
    # Down past her shoulders, and straggling: pushed out from her head here
    # and there, more towards its ends.
    if v.co.z < 1.64:
        v.co.z -= (1.64 - v.co.z) * 0.9
    out_by = max(0.0, 1.66 - v.co.z) * 0.25 * (0.5 + noise.noise(v.co * 40))
    across = Vector((v.co.x, v.co.y - 0.01, 0))
    if across.length > 0.001:
        v.co += across.normalized() * out_by

# ---- Their robes: from the waist to the ground, in rags at the hem ----------

RINGS = 18
FIT = 0.012  # metres the robe stands clear of her clothes under it, at its snuggest
# (Round her as snug as her bodice and her breeches are, at each height: then
# flaring out from that.)
# (Her bodice's flared foot, and the pouch on it, go: hidden by her robe, and
# they'd poke through it.)
under = [o for o in skeleton.children if o.name.startswith(("Female_Peasant_Body", "Female_Peasant_Legs"))]
c.cut_below(next(o for o in under if "Body" in o.name), WAIST - 0.03)
snug = c.hang([c.girth(under, WAIST + (HEM - WAIST) * i / RINGS, SIDES, (0.0, 0.02)) for i in range(RINGS + 1)])
robes = []
for n, witch in enumerate(WITCHES):
    rng = random.Random(n)
    rag = [rng.uniform(0.0, 0.13) for _ in range(RAGS)]  # how short each rag is cut
    verts, colours, weights = [], [], []
    for i in range(RINGS + 1):
        t = i / RINGS  # 0 at the waist, 1 at the hem
        for k in range(SIDES):
            a = 2 * math.pi * k / SIDES
            flare = 0.2 * t**1.2 * (1 + 0.3 * math.sin(a * 7 + n))
            r = snug[i][k] + FIT + flare
            x, y = math.sin(a) * r, -math.cos(a) * r
            # The hem: pointed rags (each at its own length), between them cut up.
            u = a / (2 * math.pi) * RAGS
            between = abs(u - round(u)) * 2  # 0 at a rag's point, 1 between two
            short = rag[round(u) % RAGS] + 0.09 * between
            z = WAIST + (HEM + short - WAIST) * t
            verts.append((x, y + 0.02, z))
            patch = noise.noise(Vector((x * 9, y * 9, z * 5 + n * 10)))
            colours.append(c.vary(c.linear(witch["robe"]), 0.16 + 0.1 * patch, Vector((a * 3, t * 8, n))))
            # (Moved as Merlin's robe is: by her hips, and below by her legs.)
            side = c.smooth((x / r + 0.35) / 0.7)
            back = c.smooth((y / r + 0.3) / 1.0)
            hip = 1 - c.smooth(t * 2.5)
            calf = (0.25 + 0.5 * back) * c.smooth((t - 0.4) * 2)
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
    robe = c.skinned(f"witch-robe-{n}", verts, faces, colours, weights, skeleton)
    robe.data.materials.append(c.vertex_material())
    robes.append(robe)

# Their sleeves: ragged cuffs (part of their robes), flaring out from her forearms over her hands.
CUT = 9  # rags round each cuff
for n, witch in enumerate(WITCHES):
    rng = random.Random(10 + n)
    verts, colours, faces, weights = [], [], [], []
    for side in ("l", "r"):
        bones = skeleton.data.bones
        elbow, wrist = bones[f"lowerarm_{side}"].head_local, bones[f"lowerarm_{side}"].tail_local
        along = (wrist - elbow).normalized()
        start = elbow.lerp(wrist, 0.15)
        length = (wrist - start).length + CUFF[2]
        rag = [rng.uniform(0.0, 0.06) for _ in range(CUT)]
        first = len(verts)
        STEPS = 5
        for i in range(STEPS + 1):
            t = i / STEPS
            for k in range(SIDES):
                a = 2 * math.pi * k / SIDES
                u = a / (2 * math.pi) * CUT
                short = (rag[round(u) % CUT] + 0.03 * abs(u - round(u)) * 2) * t
                r = CUFF[0] + (CUFF[1] - CUFF[0]) * t**2.2
                # (Round her arm: up is z, forward is -y; hanging low beneath it, the
                # rags underneath longest.)
                below = max(0.0, -math.cos(a))
                around = Vector((0, -math.sin(a), math.cos(a))) * r + Vector((0, 0, -0.06 * t**2 * (0.4 + below)))
                verts.append(tuple(start + along * (length * t - short) + around))
                colours.append(c.vary(c.linear(witch["robe"]), 0.18, Vector((a * 3, t * 4, n + 7))))
                weights.append({f"lowerarm_{side}": 1 - 0.4 * t, f"hand_{side}": 0.4 * t})
        for i in range(STEPS):
            for k in range(SIDES):
                a, b = first + i * SIDES + k, first + i * SIDES + (k + 1) % SIDES
                faces.append((a, b, b + SIDES, a + SIDES))
    sleeves = c.skinned(f"witch-sleeves-{n}", verts, faces, colours, weights, skeleton)
    # (One with her robe.)
    with bpy.context.temp_override(active_object=robes[n], selected_editable_objects=[robes[n], sleeves]):
        bpy.ops.object.join()

# ---- Their hats: tall, crooked cones on wide, drooping brims ----------------

hx, hy, hz = HEAD
# Tipped back on her head, so her eyes show under the brim.
tip_back = Matrix.Rotation(math.radians(-TIP), 4, "X")
pivot = Vector((hx, hy + 0.05, hz - 0.06))


def middle(t, witch):
    """The middle of a hat's cone, t from its foot (0) to its tip (1): bending
    one way, then flopping over at its top."""
    sx, sy = witch["bend"]
    tall = witch["tall"]
    return Vector((hx + sx * t**2.5, hy + sy * t**1.8, hz + tall * t - (tall * 0.25) * t**3))


def on_cone(t, a, witch, lift=0.0):
    rx, ry = ((r - 0.004) * (1 - t) ** 1.1 + 0.003 + lift for r in CROWN)
    # (A kink part way up, where the cloth's creased.)
    crease = 1 - 0.12 * math.exp(-(((t - 0.45) / 0.07) ** 2))
    m = middle(t, witch)
    return Vector((m.x + math.sin(a) * rx * crease, m.y - math.cos(a) * ry * crease, m.z))


for n, witch in enumerate(WITCHES):
    verts, colours, faces = [], [], []
    hat, band = c.linear(witch["hat"]), c.linear(witch["band"])
    # The brim: flat by her head, wide and wavy, drooping at its edge.
    rings = [(*CROWN, 0.0, 0.0), (0.18, 0.2, -0.01, 0.01), (0.25, 0.26, -0.035, 0.025)]
    for ring, (rx, ry, dz, wave) in enumerate(rings):
        for k in range(SIDES):
            a = 2 * math.pi * k / SIDES
            z = hz + dz - wave * (1 + math.sin(3 * a + n * 2))
            verts.append((hx + math.sin(a) * rx, hy - math.cos(a) * ry, z))
            colours.append(c.vary(hat, 0.14, Vector((a, ring, n + 3))))
    for ring in range(len(rings) - 1):
        for k in range(SIDES):
            a, b = ring * SIDES + k, ring * SIDES + (k + 1) % SIDES
            faces.append((a, a + SIDES, b + SIDES, b))
    verts.append((hx, hy, hz))
    colours.append(hat)
    faces += [(len(verts) - 1, (k + 1) % SIDES, k) for k in range(SIDES)]
    # The cone, with a band round its foot.
    CONE = 16
    base = len(verts)
    for i in range(CONE + 1):
        t = i / CONE
        for k in range(SIDES):
            a = 2 * math.pi * k / SIDES
            verts.append(tuple(on_cone(t, a, witch)))
            colours.append(c.vary(band if t < 0.09 else hat, 0.14, Vector((a, t * 5, n + 4))))
    for i in range(CONE):
        for k in range(SIDES):
            a, b = base + i * SIDES + k, base + i * SIDES + (k + 1) % SIDES
            faces.append((a, b, b + SIDES, a + SIDES))
    verts = [tuple(tip_back @ (Vector(v) - pivot) + pivot) for v in verts]
    obj = c.skinned(f"witch-hat-{n}", verts, faces, colours, [{"Head": 1.0}] * len(verts), skeleton)
    obj.data.materials.append(c.vertex_material())

# Her hair, inside the hats: drawn in where it would poke through any of their
# cones (their feet are all the same; they part only above her head).
untip = tip_back.inverted()
for v in hair.data.vertices:
    p = untip @ (v.co - pivot) + pivot  # (as if the hats weren't tipped)
    t = (p.z - hz) / min(w["tall"] for w in WITCHES)
    if t < -0.01:
        continue
    t = max(t, 0.0)
    rx, ry = ((r - 0.004) * (1 - t) ** 1.1 + 0.003 for r in CROWN)
    dx, dy = p.x - hx, p.y - hy
    beyond = math.hypot(dx / rx, dy / ry) / 0.92
    if beyond > 1:
        p.x, p.y = hx + dx / beyond, hy + dy / beyond
        v.co = tip_back @ (p - pivot) + pivot

# Robes and hats, seen from inside too (under the brims, the rags lifting).
c.vertex_material().use_backface_culling = False

# ---- Textures: shrunk, her clothes dulled, her hair grey, her skin sallow --------------------

c.drop_missing_textures()

for image in bpy.data.images:
    if not image.size[0]:
        continue
    if image.size[0] > TEXTURE:
        image.scale(TEXTURE, TEXTURE)
    name = image.name.lower()
    if "basecolor" in name and ("peasant" in name or "hair" in name or "superhero" in name):
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        rgb = rgba[:, :3]
        grey = rgb @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
        if "peasant" in name:
            # Her clothes, old and faded to dark, dusty greys and browns.
            rgb[:] = (rgb * 0.35 + grey[:, None] * 0.65) * 0.62
        elif "hair" in name:
            # Her hair, a dull, tangled grey (a touch warm, not the kit's blue).
            rgb[:] = grey[:, None] * np.array([0.78, 0.76, 0.72], dtype=np.float32)
        else:
            # Her skin, old and sallow: paler, towards a grey-green.
            rgb[:] = rgb * 0.55 + grey[:, None] * np.array([0.42, 0.45, 0.36], dtype=np.float32) + 0.04
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    image.pack()

# ---- Their animations --------------------------------------------------------

c.clips(skeleton, ANIMS)

if out:
    for o in bpy.data.objects:
        o.select_set(o == skeleton or o.parent == skeleton)
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS", export_image_format="WEBP")

if preview:
    # Each of them, standing, from the front (only her robe and hat showing);
    # then dancing (-dance.png).
    def dressed(n):
        for o in skeleton.children:
            if o.name.startswith(("witch-robe", "witch-hat")):
                o.hide_render = not o.name.endswith(f"-{n}")

    c.pose(skeleton, "Idle_Loop", 10)
    for n in range(len(WITCHES)):
        dressed(n)
        c.preview(preview.replace(".png", f"-{n}.png"), (1.2, -4.2, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    dressed(0)
    c.preview(preview.replace(".png", "-face.png"), (0.45, -1.3, 1.5), (0, 0, 1.6), (0.4, 0.8, -1), lens=50)
    c.pose(skeleton, "Dance_Loop", 20)
    c.preview(preview.replace(".png", "-dance.png"), (1.8, -4.0, 1.2), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
