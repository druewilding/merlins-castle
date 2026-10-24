# The trolls in their cave, as in its picture: big, friendly and lumpy, with
# pot bellies, big hands and feet, bulbous noses and big ears, their skin
# pebbly and stone-brown, and moss growing wild on their heads and shoulders,
# down their backs, and hanging round their hips.
#
# Made from Quaternius's kits (CC0, art/models/): a Universal Base
# Character's whole body (its head, hands and feet made bigger, its body and
# limbs bulked out, a belly, its nose and ears grown), its skin recoloured
# to stone. The moss (troll-moss) is made here, each tuft moved by the bones
# that move the skin it grows from. All of it shares the kits' one skeleton,
# so the Universal Animation Libraries' clips play on them (ANIMS): sitting,
# asking for a tune, getting up, and dancing. And one troll's drum
# (troll-drum), on its own.
#
# He stands in a T-pose, his feet at z = 0, facing -y (the way the kits face).

import math
import random
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

BODY = c.BODIES / "Superhero_Male_FullBody.gltf"

ANIMS = ["Sitting_Idle_Loop", "Sitting_Talking_Loop", "Sitting_Exit", "Dance_Loop"]
TEXTURE = 1024  # the size every texture is shrunk to (the kit's are 2048)

HEAD_SIZE = 1.25  # times bigger, his head (and the game makes each one's its own size)...
FEET = 1.35  # ...and his feet (his hands are made bigger in the game, by their bones: so his
# fingers bend where their joints are, and don't fold through his palms)
BULK = (0.024, 0.018)  # metres his limbs and his body are bulked out
BELLY = (0.07, 1.1, 0.2, 0.15)  # metres his belly sticks out, at its middle (its height), and how far it goes up and down
# from there (not far down: it's his tummy, not his hips, which bend their own way, dancing)
FATTER = 0.035  # metres more, for the trolls with bigger bellies (the shape key "belly")
FAT = (0.03, 0.03, 0.02)  # and for the fatter trolls (the shape key "fat"): metres more on his limbs, his body and his belly
NOSE = (1.5, 0.036, 0.006)  # how much bigger his nose is grown, the radius of the round bulb it's made, and how far it's lifted (off his smile)
LONG_NOSE = (1.35, 2.3, 0.022)  # or (the shape key "long-nose"): as much bigger across, along, and drooping
EARS = (1.8, 2.5)  # how much bigger his ears are grown (or, the shape key "big-ears", these)
SMILE = (0.014, 0.008)  # metres the corners of his mouth are lifted, and his cheeks pushed up and out

SKIN_DARK = np.array(c.linear("#6a5236")[:3], dtype=np.float32)
SKIN = np.array(c.linear("#b4935f")[:3], dtype=np.float32)
SKIN_LIGHT = np.array(c.linear("#e2c48c")[:3], dtype=np.float32)
SKIN_MOSSY = np.array(c.linear("#9a9058")[:3], dtype=np.float32)
MOSS = [c.linear(h) for h in ("#5f6a2a", "#737c32", "#8a8a3a", "#4e5626", "#7a6c38", "#6a7a30")]
MOSS_TIP = c.linear("#b8ae5a")

# ---- His body, skeleton and all --------------------------------------------

parts, skeleton = c.load(BODY)
skeleton.name = "troll"
c.remove([o for o in parts if o.type == "MESH" and o.parent != skeleton])
body = next(o for o in skeleton.children if o.name.startswith("SuperHero"))
faces_on = [o for o in skeleton.children if o.name.startswith(("Eyes", "Eyebrows"))]
# (The kit's colour masks on his body go: the game would darken his skin by them, black where his briefs were.)
for layer in list(body.data.color_attributes):
    body.data.color_attributes.remove(layer)


def bone_at(name):
    return skeleton.matrix_world @ skeleton.data.bones[name].head_local


def weights_of(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in obj.data.vertices]


def side_weight(w, starts, side):
    """How much of a point's weight is on bones of this side starting with any of these."""
    return sum(amount for bone, amount in w.items() if bone.endswith("_" + side) and bone.startswith(starts))


HEAD_AT = bone_at("Head")


def grown(p, w):
    """Where a point of him goes, made a troll: his head and feet bigger
    (blended by how much each bone moves it, so nothing tears)."""
    head = w.get("Head", 0.0)
    p = HEAD_AT + (p - HEAD_AT) * (1 + (HEAD_SIZE - 1) * head)
    for side in ("l", "r"):
        foot = side_weight(w, ("foot", "ball"), side)
        if foot:
            # (About the ground under his ankle: his soles stay on it.)
            at = bone_at(f"foot_{side}")
            at = Vector((at.x, at.y + 0.03, 0))
            p = at + (p - at) * (1 + (FEET - 1) * foot)
    return p


# ---- His face: a big round nose, big ears, and a smile -------------------------

to_world = body.matrix_world
to_mesh = to_world.inverted()
weights = weights_of(body)
rest = [to_world @ v.co for v in body.data.vertices]  # (as the kit made him)
# (The kit's file splits his skin along its seams: each point on one is two
# or three, one for each side. Each is moved as one, or the seams would open.)
seams = {}
for i, p in enumerate(rest):
    seams.setdefault(tuple(round(a, 5) for a in p), []).append(i)
seams = [group for group in seams.values() if len(group) > 1]


def welded(ps, unit=False):
    """Each seam's points all where they are, together (or, unit, all their ways, averaged)."""
    ps = list(ps)
    for group in seams:
        middle = sum((ps[i] for i in group), Vector()) / len(group)
        if unit:
            middle.normalize()
        for i in group:
            ps[i] = middle.copy()
    return ps


normals = welded([(to_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices], unit=True)
# (The front of his body smoothed: the kit's hero's muscles, which a troll hasn't.)
around = [[] for _ in rest]
for edge in body.data.edges:
    a, b = edge.vertices
    around[a].append(b)
    around[b].append(a)
SMOOTHED = 6  # times
smoothing = [c.smooth((-rest[i].y + 0.02) / 0.05) * c.smooth(1 - abs(rest[i].z - 1.22) / 0.3)
             * sum(w.get(b, 0) for b in ("spine_01", "spine_02", "spine_03", "pelvis")) for i, w in enumerate(weights)]
for _ in range(SMOOTHED):
    rest = [p.lerp(sum((rest[j] for j in around[i]), Vector()) / len(around[i]), 0.5 * smoothing[i]) if around[i] else p
            for i, p in enumerate(rest)]
    rest = welded(rest)
face = {i for i, w in enumerate(weights) if w.get("Head", 0) > 0.9}
tip = min((rest[i] for i in face if abs(rest[i].x) < 0.01 and 1.6 < rest[i].z < 1.72), key=lambda p: p.y)
EAR = Vector((0.072, 0.025, 1.695))  # where his ears join his head (on his left; his right's the mirror)
NOSE_AT = tip + Vector((0, 0.027, -0.002))  # the middle of his nose, behind its tip
MOUTH = 1.607  # the line between his lips
CHEEK = Vector((0.04, -0.072, 1.64))  # the middle of his cheek (his left)
EYE = (Vector((0.0338, -0.066, 1.6986)), 0.0148)  # the middle of his eye (his left), and how big it is
# Where his lids open, the upper and the lower, and where they meet, blinking
# (the shape key "blink"): radians up from straight ahead, round his eye's middle.
LIDS = (0.204, -0.49, -0.28)


def blinked(p):
    """A point of his face, his eyes shut: each lid turned round his eye's
    middle over it (so it never goes into it), most at its edge, less going
    away from it."""
    eye = Vector((math.copysign(EYE[0].x, p.x), EYE[0].y, EYE[0].z))
    d = p - eye
    if d.y > 0.003 or d.length > EYE[1] + 0.012:
        return p
    across = c.smooth(1 - (abs(d.x) - 0.85 * EYE[1]) / (0.6 * EYE[1]))
    up = math.atan2(d.z, -d.y)
    if up > 0.1:
        turn = (LIDS[2] - LIDS[0]) * c.smooth(1 - (up - LIDS[0]) / 0.9)  # (down)
    elif up < -0.2:
        turn = (LIDS[2] - LIDS[1]) * c.smooth(1 - (LIDS[1] - up) / 0.6)  # (up)
    else:
        return p
    turn *= across * c.smooth(1 - (d.length - EYE[1] - 0.004) / 0.008)
    out = math.hypot(d.y, d.z)
    return Vector((p.x, eye.y - out * math.cos(up + turn), eye.z + out * math.sin(up + turn)))


def faced(p, long_nose=False, big_ears=False, blink=False):
    """A point of his face, made a troll's, and smiling (or blinking)."""
    if blink:
        p = blinked(p)
    # The nose: grown round and heavy, all of it, from its middle; or long,
    # and drooping at its end.
    d = Vector(((p.x - NOSE_AT.x) / 0.035, (p.y - NOSE_AT.y) / 0.045, (p.z - NOSE_AT.z) / 0.035)).length
    if d < 1 and p.y < NOSE_AT.y + 0.01:
        near = c.smooth((1 - d) / 0.5)
        if long_nose:
            k = LONG_NOSE
            out = p - NOSE_AT
            p = NOSE_AT + Vector((out.x * (1 + (k[0] - 1) * near), out.y * (1 + (k[1] - 1) * near),
                                  out.z * (1 + (k[0] - 1) * near)))
            p.z -= k[2] * near * c.smooth((NOSE_AT.y - p.y) / 0.06)
        else:
            p = NOSE_AT + (p - NOSE_AT) * (1 + (NOSE[0] - 1) * near)
            # (Rounded: its front pulled towards a ball, not a beak.)
            ball = NOSE_AT + (p - NOSE_AT).normalized() * NOSE[1]
            p = p.lerp(ball, 0.7 * near * c.smooth((NOSE_AT.y + 0.005 - p.y) / 0.02))
            p.z += NOSE[2] * near
    # The ears: grown out and up from where they join his head.
    if abs(p.x) > EAR.x and abs(p.z - EAR.z) < 0.05 and -0.015 < p.y < 0.07:
        root = Vector((math.copysign(EAR.x, p.x), EAR.y, EAR.z))
        out_by = c.smooth((abs(p.x) - EAR.x) / 0.01)
        p = root + (p - root) * (1 + (EARS[1 if big_ears else 0] - 1) * out_by)
        p.z += 0.02 * out_by * max(0.0, p.z - EAR.z) / 0.04  # (a little pointed)
    # A smile: the corners of his mouth lifted, and a little wider (most at the
    # corners, none in the middle)...
    if abs(p.z - MOUTH) < 0.02 and abs(p.x) < 0.045 and p.y < -0.04:
        corner = c.smooth((abs(p.x) - 0.006) / 0.022) * c.smooth(1 - abs(p.z - MOUTH) / 0.02)
        p = Vector((p.x * (1 + 0.18 * corner), p.y + 0.005 * corner, p.z + SMILE[0] * corner))
    # ...and his cheeks pushed up round and out by it.
    cheek = Vector((abs(p.x) - CHEEK.x, p.y - CHEEK.y, p.z - CHEEK.z)).length
    if cheek < 0.026 and p.y < -0.04:
        lift = c.smooth(1 - cheek / 0.026)
        p = p + Vector((math.copysign(0.002, p.x), -SMILE[1], SMILE[1] * 0.6)) * lift
    return p


# ---- His body: bulked out, a belly, his head and feet bigger --------------------

LIMBS = ("upperarm", "lowerarm", "thigh", "calf")
TRUNK = ("spine", "pelvis", "clavicle", "neck")


def trolled(i, belly=BELLY[0], fat=0.0, **face_):
    """Where a point of him goes: his face, his bulk, his belly, a hunch, his head and feet."""
    p, n, w = rest[i], normals[i], weights[i]
    if i in face:
        p = faced(p, **face_)
    limb = sum(a for b, a in w.items() if b.startswith(LIMBS))
    trunk = sum(a for b, a in w.items() if b.startswith(TRUNK))
    # (Fatter, but not on the fronts of his thighs, where his hands rest, sitting.)
    lap = (w.get("thigh_l", 0) + w.get("thigh_r", 0)) * c.smooth(-n.y / 0.5)
    p = p + n * (BULK[0] * limb + FAT[0] * fat * (limb - 0.9 * lap) + (BULK[1] + FAT[1] * fat) * trunk)
    # His belly: round, out in front, low on him.
    tummy = sum(w.get(b, 0) for b in ("spine_01", "spine_02", "pelvis"))
    if tummy and p.y < 0.02:
        f = math.exp(-(((p.z - BELLY[1]) / (BELLY[2] if p.z > BELLY[1] else BELLY[3])) ** 2)) * tummy
        front = c.smooth(-p.y / 0.13)
        p = Vector((p.x * (1 + 0.35 * belly * f), p.y - belly * f * front, p.z))
    # (A little hunched: his upper back up and back.)
    hunch = w.get("spine_03", 0) + 0.5 * w.get("neck_01", 0)
    if p.y > 0:
        p = p + Vector((0, 0.03, 0.01)) * hunch * c.smooth(p.y / 0.1)
    return grown(p, w)


everyone = range(len(rest))
points = welded(trolled(i) for i in everyone)
# Each a little different (the game mixes these in): a bigger belly, fatter all over, a long
# droopy nose, bigger ears. And his eyes shut, for the game to blink them.
KEYS = {
    "belly": welded(trolled(i, belly=BELLY[0] + FATTER) for i in everyone),
    "fat": welded(trolled(i, belly=BELLY[0] + FAT[2], fat=1.0) for i in everyone),
    "long-nose": welded(trolled(i, long_nose=True) if i in face else points[i] for i in everyone),
    "big-ears": welded(trolled(i, big_ears=True) if i in face else points[i] for i in everyone),
    "blink": welded(trolled(i, blink=True) if i in face else points[i] for i in everyone),
}
for v, p in zip(body.data.vertices, points):
    v.co = to_mesh @ p
body.shape_key_add(name="Basis")
for name, moved in KEYS.items():
    key = body.shape_key_add(name=name, from_mix=False)
    for k, p in zip(key.data, moved):
        k.co = to_mesh @ p
BROWS = (0.004, 0.008)  # metres his eyebrows are lifted, and arched over each eye (friendly: they come frowning)
for obj in faces_on:
    m = obj.matrix_world
    if obj.name.startswith("Eyebrows"):
        for v in obj.data.vertices:
            v.co.z += BROWS[0] + BROWS[1] * math.sin(math.pi * min(1.0, abs(v.co.x) / 0.062))
    for v, w in zip(obj.data.vertices, weights_of(obj)):
        v.co = m.inverted() @ grown(m @ v.co, w or {"Head": 1.0})
body.data.update()

# ---- His moss: on his shoulders, down his back, and round his hips (troll-moss);
# his hair, in three styles (troll-hair-0..2), and a beard (troll-beard): the
# game gives each troll its own ----------------------------------------------

rng = random.Random(5)
normals = welded([(to_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices], unit=True)
crown = max(p.z for p in rest)
DOWN = Vector((0, 0, -1))


def on_body(i):
    """How thick the moss grows here on his body (0 to 1), and how far it
    hangs down (0 sticking out, to 1 hanging straight down)."""
    p, n, w = rest[i], normals[i], weights[i]
    if w.get("Head", 0) > 0.5:
        return 0, 0
    shoulders = sum(w.get(b, 0) for b in ("spine_03", "clavicle_l", "clavicle_r", "neck_01"))
    arms = w.get("upperarm_l", 0) + w.get("upperarm_r", 0)
    if p.z > 1.3 and (shoulders > 0.3 or (arms > 0.3 and n.z > 0.1)):
        # (Over his shoulders and down his back; on his chest, only over the top of it.)
        if p.y < -0.05 and p.z < 1.45:
            return 0, 0
        return 1.0, 0.7
    if 0.8 < p.z < 1.04 and (w.get("pelvis", 0) + w.get("thigh_l", 0) + w.get("thigh_r", 0)) > 0.4:
        return 1.0, 1.0  # round his hips, hanging down
    if p.y > 0.05 and 1.0 < p.z < 1.3 and w.get("spine_02", 0) + w.get("spine_01", 0) > 0.4:
        return 0.6, 0.8  # (and a little down his back)
    return 0, 0


def scalp(i):
    """Whether this is his scalp: over the top and back of his head, not his
    face, nor round his ears."""
    p, w = rest[i], weights[i]
    if w.get("Head", 0) <= 0.5 or (abs(p.x) > 0.06 and p.z < EAR.z + 0.06 and p.y < EAR.y + 0.05):
        return False
    return (p.z > crown - 0.14 and (p.y > -0.04 or p.z > crown - 0.07)) or (p.y > 0.0 and p.z > crown - 0.3)


def wild(i):
    """Hair sticking up and out, everywhere on his scalp."""
    return (1.0, 0.3) if scalp(i) else (0, 0)


def shaggy(i):
    """Hair hanging down, long, round the sides and back, and a short fringe in front."""
    if not scalp(i):
        return 0, 0
    return (1.0, 0.2) if rest[i].y < -0.03 else (1.0, 0.85)


def tufty(i):
    """A tuft standing up on top, and short, flat moss round the back."""
    if not scalp(i):
        return 0, 0
    if rest[i].z > crown - 0.05 and abs(rest[i].x) < 0.04:
        return 1.0, 0.0
    return (0.25, 0.6) if rest[i].y > -0.01 else (0, 0)


def bearded(i):
    """A beard: on the front of his chin and along his jaw, below his mouth."""
    p, w = rest[i], weights[i]
    return (1.0, 1.0) if w.get("Head", 0) > 0.5 and 1.54 < p.z < MOUTH - 0.016 and p.y < -0.045 and abs(p.x) < 0.06 else (0, 0)


def mossy(p):
    """Moss's colour here: patchy greens, darker in its hollows."""
    v = p * 25
    colour = c.mix(MOSS[3], MOSS[2], 0.5 + noise.noise(v) * 0.8)
    colour = c.mix(colour, MOSS[4], max(0.0, noise.noise(v * 0.4 + Vector((5, 1, 2)))))
    return c.vary(colour, 0.12, v * 3)


def grow_moss(name, where, blades, length, width, keys=()):
    """A bed of moss, lumpy, just over his skin (moved as his skin is), with a
    ragged edge, wherever where(i) says it grows; and blades sticking out of
    it, as many as blades (each point's chance of a tuft), as long and as wide
    as those (low, high), longer where it hangs. With the body's shape keys
    (keys) too, each of its points moved as the point of him it grows from."""
    growing = [where(i) for i in everyone]
    verts, faces, colours, weights_, grows_from, offsets = [], [], [], [], [], []
    SHELL = (0.012, 0.012)  # metres it stands off his skin, and how lumpy
    bed = {}
    for i, (thick, _) in enumerate(growing):
        if thick > 0 and thick + 0.35 * noise.noise(rest[i] * 14) > 0.5:
            bed[i] = len(bed)
    for i in bed:
        q = points[i] + normals[i] * (SHELL[0] + SHELL[1] * (0.5 + 0.5 * noise.noise(rest[i] * 30)))
        verts.append(tuple(q))
        colours.append(mossy(q))
        weights_.append(weights[i])
        grows_from.append(i)
    faces += [tuple(bed[v] for v in poly.vertices) for poly in body.data.polygons if all(v in bed for v in poly.vertices)]
    for i, (thick, hang) in enumerate(growing):
        if thick <= 0 or rng.random() > blades * thick:
            continue
        p, n = points[i], normals[i]
        for _ in range(3):
            stray = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.4
            way = (n * (1 - hang) + DOWN * hang * 1.2 + stray).normalized()
            long = rng.uniform(*length) * (1 + 2 * hang**4)  # (hanging, much longer)
            across = way.cross(n)
            if across.length < 1e-3:
                across = way.cross(Vector((1, 0, 0)))
            across = across.normalized() * rng.uniform(*width) * (1 + 0.6 * hang)
            root = p + n * 0.006 + across * rng.uniform(-1.5, 1.5)
            colour = rng.choice(MOSS)
            first = len(verts)
            # (Two pieces, bending further as it goes: a blade of moss, pointed.)
            mid = root + way * long * 0.55
            end = mid + (way + DOWN * 0.35).normalized() * long * 0.5
            for q, half in ((root, 1.0), (mid, 0.6)):
                verts += [tuple(q - across * half), tuple(q + across * half)]
            verts.append(tuple(end))
            dark = c.mix(colour, (0, 0, 0, 1), 0.35)
            colours += [dark, dark, colour, colour, c.mix(colour, MOSS_TIP, 0.6)]
            faces += [(first, first + 1, first + 3, first + 2), (first + 2, first + 3, first + 4)]
            weights_ += [weights[i]] * 5
            grows_from += [i] * 5
    obj = c.skinned(name, verts, faces, colours, weights_, skeleton)
    if keys:
        obj.shape_key_add(name="Basis")
        for key_name in keys:
            key = obj.shape_key_add(name=key_name, from_mix=False)
            for k, v, i in zip(key.data, verts, grows_from):
                k.co = Vector(v) + KEYS[key_name][i] - points[i]
    print(f"{name}: {len(verts)} points")
    return obj


grow_moss("troll-moss", on_body, 0.25, (0.04, 0.085), (0.007, 0.012), keys=["belly", "fat"])
grow_moss("troll-hair-0", wild, 0.55, (0.04, 0.085), (0.007, 0.012))
grow_moss("troll-hair-1", shaggy, 0.55, (0.045, 0.075), (0.008, 0.013))
grow_moss("troll-hair-2", tufty, 0.9, (0.07, 0.11), (0.007, 0.011))
grow_moss("troll-beard", bearded, 1.0, (0.045, 0.075), (0.008, 0.012))
c.vertex_material().use_backface_culling = False  # (one layer, seen from both sides)

# ---- His skin: pebbly, stone-brown, greener in places ---------------------------

c.drop_missing_textures()
# (And its normal and roughness maps: the kit's hero's muscles, and his briefs
# shiny, black in a cave. A troll's lumps are in his skin, and he's matt all over.)
for material in bpy.data.materials:
    if material.node_tree and "superhero" in material.name.lower():
        for node in list(material.node_tree.nodes):
            name = node.image.name.lower() if node.type == "TEX_IMAGE" and node.image else ""
            if "normal" in name or "rough" in name:
                material.node_tree.nodes.remove(node)
        shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        shader.inputs["Metallic"].default_value = 0.0
        shader.inputs["Roughness"].default_value = 0.9


def upsampled(size, cells, seed):
    """Smooth random noise over a square picture: random at each of cells x
    cells points, blended between them."""
    grid = np.random.default_rng(seed).random((cells + 1, cells + 1)).astype(np.float32)
    t = np.linspace(0, cells, size, endpoint=False, dtype=np.float32)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    rows = grid[i] * (1 - f)[:, None] + grid[i + 1] * f[:, None]
    return rows[:, i] * (1 - f)[None, :] + rows[:, i + 1] * f[None, :]


for image in bpy.data.images:
    if not image.size[0]:
        continue
    if image.size[0] > TEXTURE:
        image.scale(TEXTURE, TEXTURE)
    name = image.name.lower()
    size = image.size[0]
    if "superhero" in name and "normal" not in name and "rough" not in name:
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(size, size, 4)
        grey = rgba[..., :3] @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
        light = np.clip(grey / max(float(np.percentile(grey, 70)), 1e-4), 0, 1.6)
        # (Its fine shading softened: the kit's hero's muscles, which a troll hasn't.)
        cell = size // 64
        soft = light.reshape(64, cell, 64, cell).mean((1, 3)).repeat(cell, 0).repeat(cell, 1)
        light = 0.4 * light + 0.6 * soft
        # (The kit's dark briefs, as skin: the moss covers them. They're grey, where his skin's brown.)
        top, bottom = rgba[..., :3].max(-1), rgba[..., :3].min(-1)
        light = np.where((top - bottom) < 0.2 * np.maximum(top, 1e-4), 0.85, light)
        # (Its shading kept: light to dark, in stone-browns.)
        low = np.clip(light, 0, 1)[..., None]
        high = np.clip(light - 1, 0, 0.6)[..., None] / 0.6
        rgb = SKIN_DARK * (1 - low) + SKIN * low
        rgb = rgb * (1 - high) + SKIN_LIGHT * high
        # Greener in patches, and pebbly all over: little lumps, light and dark.
        patches = upsampled(size, 6, 1)[..., None]
        rgb = rgb * (1 - 0.35 * patches) + SKIN_MOSSY * 0.35 * patches * (rgb / SKIN).mean(-1, keepdims=True)
        pebbles = 0.6 * upsampled(size, 160, 2) + 0.4 * upsampled(size, 70, 3)
        rgb *= (0.72 + 0.56 * pebbles)[..., None]
        rgba[..., :3] = rgb
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    elif "hair" in name and "normal" not in name:
        # His eyebrows: bushy moss.
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        grey = rgba[:, :3] @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
        rgba[:, :3] = grey[:, None] * np.array(MOSS[1][:3], dtype=np.float32) * 2.2
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    image.pack()

# ---- The drum, for one of them: a wooden shell, two skins, laced between ------------

drum = c.Builder()
DRUM_R, DRUM_TALL, DRUM_SIDES = 0.17, 0.2, 24
SHELL = c.linear("#8a5a30")
SKIN_HEAD = c.linear("#e6d2a6")
LACE = c.linear("#c9a46a")
HOOP = c.linear("#5e3b1e")
for ring in range(2):
    z0 = ring * (DRUM_TALL - 0.025)
    drum.cylinder((0, 0, z0), (0, 0, z0 + 0.025), DRUM_R + 0.012, DRUM_R + 0.012, HOOP, sides=DRUM_SIDES)
drum.cylinder((0, 0, 0.02), (0, 0, DRUM_TALL - 0.02), DRUM_R, DRUM_R, SHELL, sides=DRUM_SIDES)
for z, flip in ((DRUM_TALL, False), (0.0, True)):
    ring_ = [(math.cos(2 * math.pi * k / DRUM_SIDES) * (DRUM_R + 0.012),
              math.sin(2 * math.pi * k / DRUM_SIDES) * (DRUM_R + 0.012), z) for k in range(DRUM_SIDES)]
    fan = [(DRUM_SIDES, k, (k + 1) % DRUM_SIDES) for k in range(DRUM_SIDES)]
    drum.add(ring_ + [(0, 0, z)], [f[::-1] for f in fan] if flip else fan,
             [c.vary(SKIN_HEAD, 0.08, Vector(p) * 12) for p in ring_] + [SKIN_HEAD])
# (Its lacing, zigzag round its shell between the hoops.)
for k in range(12):
    a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 0.5) / 12
    for (a, z), (b, z1) in (((a0, 0.025), (a1, DRUM_TALL - 0.025)), ((a1, DRUM_TALL - 0.025), (a0 + math.pi / 6, 0.025))):
        p0 = Vector((math.cos(a) * (DRUM_R + 0.004), math.sin(a) * (DRUM_R + 0.004), z))
        p1 = Vector((math.cos(b) * (DRUM_R + 0.004), math.sin(b) * (DRUM_R + 0.004), z1))
        side = (p1 - p0).cross(Vector((p0.x, p0.y, 0))).normalized() * 0.004
        out_ = Vector((p0.x, p0.y, 0)).normalized() * 0.003
        drum.add([tuple(p0 - side), tuple(p0 + side), tuple(p1 + side + out_), tuple(p1 - side + out_)],
                 [(0, 1, 2, 3)], [LACE] * 4)
drum_object = drum.build("troll-drum", smooth=False)

# ---- Their animations ------------------------------------------------------------

c.clips(skeleton, ANIMS)

print(f"body: {len(body.data.vertices)} points")

if out:
    for o in bpy.data.objects:
        o.select_set(o == skeleton or o.parent == skeleton or o == drum_object)
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS", export_image_format="WEBP")

if preview:
    # Each of the game's four (LOOKS, in src/three/trolls.ts: their hair,
    # beard and shape keys), standing, and close up on his face; one from
    # the side; sitting (on a block for a rock), asking for a tune; and dancing.
    LOOKS = [(0, False, {"belly": 0.2}), (1, True, {"belly": 1.0, "fat": 1.0, "big-ears": 0.6}),
             (2, False, {"long-nose": 1.0}), (1, False, {"belly": 0.6, "fat": 1.0, "big-ears": 1.0, "long-nose": 0.4})]
    seat = c.Builder()
    seat.add([(x, y, z) for z in (0, 0.48) for y in (0.05, 0.6) for x in (-0.35, 0.35)],
             [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)],
             [c.linear("#6b5a46")] * 8)
    rock = seat.build("seat")
    rock.hide_render = True
    drum_object.hide_render = True
    for track in skeleton.animation_data.nla_tracks:
        track.mute = True
    bpy.context.scene.frame_set(0)
    for n, (hair, beard, keys) in enumerate(LOOKS):
        for o in skeleton.children:
            if o.name.startswith("troll-hair"):
                o.hide_render = not o.name.endswith(f"-{hair}")
            elif o.name == "troll-beard":
                o.hide_render = not beard
            if o.data.shape_keys:
                for block in o.data.shape_keys.key_blocks[1:]:
                    block.value = keys.get(block.name, 0.0)
        c.preview(preview.replace(".png", f"-{n}.png"), (1.2, -4.2, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
        c.preview(preview.replace(".png", f"-face-{n}.png"), (0.2, -0.8, 1.5), (0, 0, 1.64), (0.4, 0.8, -1), lens=50)
    c.preview(preview.replace(".png", "-profile.png"), (-0.8, -0.35, 1.64), (0, 0, 1.63), (0.4, 0.8, -1), lens=50)
    # (And blinking, close up: open, and shut.)
    keys = body.data.shape_keys.key_blocks
    for shut in (0.0, 1.0):
        keys["blink"].value = shut
        c.preview(preview.replace(".png", f"-blink-{int(shut)}.png"), (0.1, -0.45, 1.69), (0.02, 0, 1.69), (0.4, 0.8, -1),
                  lens=60)
    keys["blink"].value = 0.0
    rock.hide_render = False
    c.pose(skeleton, "Sitting_Talking_Loop", 30)
    c.preview(preview.replace(".png", "-sitting.png"), (1.6, -3.6, 1.3), (0, 0, 0.75), (0.4, 0.8, -1), lens=40)
    rock.hide_render = True
    c.pose(skeleton, "Dance_Loop", 20)
    c.preview(preview.replace(".png", "-dance.png"), (1.8, -4.0, 1.2), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
