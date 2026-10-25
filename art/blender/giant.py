# The giant in his cave, as in its picture: huge and hungry, with a big
# round belly, a bulbous nose and a grin; shaggy brown hair and a bushy
# beard; a ragged hide round his hips; strips of cloth wound round his shins;
# and big bare feet.
#
# Made from Quaternius's kits (CC0, art/models/): a Universal Base
# Character's whole body (his head, hands and feet made bigger, his body and
# limbs bulked out, a belly, his nose grown), his skin recoloured. His hair
# and beard (giant-hair, giant-beard), his hide (giant-hide, giant-apron, giant-flap) and his wraps
# (giant-wraps) are made here, each moved by the bones that move the skin
# it's on. All of
# it shares the kits' one skeleton, so the Universal Animation Libraries'
# clips play on him (ANIMS): sitting. (It doesn't eat: the game lifts his
# hand to his mouth.) The game makes him giant-sized.
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

ANIMS = ["Sitting_Idle_Loop"]
TEXTURE = 1024  # the size every texture is shrunk to (the kit's are 2048)

HEAD_SIZE = 1.15  # times bigger, his head...
HEAD_WIDE = 1.1  # (and wider than that, side to side: a broad face)
FEET = 1.3  # ...and his feet (his hands are made bigger in the game, by their bones)
BULK = (0.02, 0.022)  # metres his limbs and his body are bulked out
BELLY = (0.085, 1.1, 0.2, 0.14)  # metres his belly sticks out, at its middle (its height), and how far it goes up and down
NOSE = (1.6, 0.036, 0.006)  # how much bigger his nose is grown, the radius of the round bulb it's made, and how far it's lifted
EARS = 1.3  # how much bigger his ears are
SMILE = (0.012, 0.008)  # metres the corners of his mouth are lifted, and his cheeks pushed up and out
BEAM = (0.016, 0.012, 0.16, 0.3)  # or, smiling broadly (the shape key "smile"): those, how much wider his mouth is, and
# how far his lower lids come up (his eyes creased, smiling)

SKIN_DARK = np.array(c.linear("#5c463e")[:3], dtype=np.float32)
SKIN = np.array(c.linear("#ae968a")[:3], dtype=np.float32)
SKIN_LIGHT = np.array(c.linear("#dccabe")[:3], dtype=np.float32)
SKIN_RUDDY = np.array(c.linear("#b48a7c")[:3], dtype=np.float32)
HAIR = [c.linear(h) for h in ("#5a3a22", "#6e4a2a", "#4a2e1a", "#7a5634", "#3f2716", "#664026")]
HAIR_TIP = c.linear("#9a7448")
HIDE = c.linear("#7c7a58")
HIDE_DARK = c.linear("#504e36")
HIDE_LIGHT = c.linear("#9a9874")
WRAP = c.linear("#6e5c44")
WRAP_DARK = c.linear("#45382a")

# ---- His body, skeleton and all --------------------------------------------

parts, skeleton = c.load(BODY)
skeleton.name = "giant"
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


def grown(p, w, wide=True):
    """Where a point of him goes: his head and feet bigger (blended by how
    much each bone moves it, so nothing tears), and his head wider (not wide,
    an eye: it's moved out whole, not stretched)."""
    head = w.get("Head", 0.0)
    p = HEAD_AT + (p - HEAD_AT) * (1 + (HEAD_SIZE - 1) * head)
    if wide:
        p.x = HEAD_AT.x + (p.x - HEAD_AT.x) * (1 + (HEAD_WIDE - 1) * head)
    for side in ("l", "r"):
        foot = side_weight(w, ("foot", "ball"), side)
        if foot:
            # (About the ground under his ankle: his soles stay on it.)
            at = bone_at(f"foot_{side}")
            at = Vector((at.x, at.y + 0.03, 0))
            p = at + (p - at) * (1 + (FEET - 1) * foot)
    return p


# ---- His face: a big round nose, and a grin ------------------------------------

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
# (The front of his body smoothed: the kit's hero's muscles, which a giant hasn't.)
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
# (His face: all of it moved by his head, his mouth and chin too, which his neck moves a little.)
face = {i for i, w in enumerate(weights) if w.get("Head", 0) > 0.6}
tip = min((rest[i] for i in face if abs(rest[i].x) < 0.01 and 1.6 < rest[i].z < 1.72), key=lambda p: p.y)
EAR = Vector((0.072, 0.025, 1.695))  # where his ears join his head (on his left; his right's the mirror)
NOSE_AT = tip + Vector((0, 0.027, -0.002))  # the middle of his nose, behind its tip
MOUTH = 1.607  # the line between his lips
CHEEK = Vector((0.04, -0.072, 1.64))  # the middle of his cheek (his left)
EYE = (Vector((0.0338, -0.066, 1.6986)), 0.0148)  # the middle of his eye (his left), and how big it is
# Where his lids open, the upper and the lower, and where they meet, blinking
# (the shape key "blink"): radians up from straight ahead, round his eye's middle.
LIDS = (0.204, -0.49, -0.28)


def blinked(p, upper=1.0, lower=1.0):
    """A point of his face, his eyes shut: each lid turned round his eye's
    middle over it (so it never goes into it), most at its edge, less going
    away from it. (Or each only so far shut: upper, lower.)"""
    eye = Vector((math.copysign(EYE[0].x, p.x), EYE[0].y, EYE[0].z))
    d = p - eye
    if d.y > 0.003 or d.length > EYE[1] + 0.012:
        return p
    across = c.smooth(1 - (abs(d.x) - 0.85 * EYE[1]) / (0.6 * EYE[1]))
    up = math.atan2(d.z, -d.y)
    if up > 0.1:
        turn = (LIDS[2] - LIDS[0]) * c.smooth(1 - (up - LIDS[0]) / 0.9) * upper  # (down)
    elif up < -0.2:
        turn = (LIDS[2] - LIDS[1]) * c.smooth(1 - (LIDS[1] - up) / 0.6) * lower  # (up)
    else:
        return p
    turn *= across * c.smooth(1 - (d.length - EYE[1] - 0.004) / 0.008)
    out = math.hypot(d.y, d.z)
    return Vector((p.x, eye.y - out * math.cos(up + turn), eye.z + out * math.sin(up + turn)))


def faced(p, blink=False, beam=False):
    """A point of his face, made a giant's, and grinning (or blinking, or beaming)."""
    if blink:
        p = blinked(p)
    elif beam:
        p = blinked(p, upper=0.0, lower=BEAM[3])
    # The nose: grown round and heavy, all of it, from its middle.
    d = Vector(((p.x - NOSE_AT.x) / 0.035, (p.y - NOSE_AT.y) / 0.045, (p.z - NOSE_AT.z) / 0.035)).length
    if d < 1 and p.y < NOSE_AT.y + 0.01:
        near = c.smooth((1 - d) / 0.5)
        p = NOSE_AT + (p - NOSE_AT) * (1 + (NOSE[0] - 1) * near)
        # (Rounded: its front pulled towards a ball, not a beak.)
        ball = NOSE_AT + (p - NOSE_AT).normalized() * NOSE[1]
        p = p.lerp(ball, 0.7 * near * c.smooth((NOSE_AT.y + 0.005 - p.y) / 0.02))
        p.z += NOSE[2] * near
    # The ears: grown out from where they join his head.
    if abs(p.x) > EAR.x and abs(p.z - EAR.z) < 0.05 and -0.015 < p.y < 0.07:
        root = Vector((math.copysign(EAR.x, p.x), EAR.y, EAR.z))
        p = root + (p - root) * (1 + (EARS - 1) * c.smooth((abs(p.x) - EAR.x) / 0.01))
    # A grin: the corners of his mouth lifted, and wider (most at the corners,
    # none in the middle; beaming, more of them, and further, curving round his cheeks)...
    # (Over more of his face, beaming, so nothing lifted passes what's over it.)
    up, out, wide, tall, broad = (*BEAM[:3], 0.036, 0.056) if beam else (*SMILE, 0.2, 0.02, 0.045)
    # (Beaming, lifted mostly above the line between his lips: below it, only
    # just, or his chin and lower lip go up and in, and his face looks sunken.)
    below = 0.014 if beam else tall
    if -below < p.z - MOUTH < tall and abs(p.x) < broad and p.y < -0.04:
        dz = p.z - MOUTH
        corner = c.smooth((abs(p.x) - 0.006) / 0.022) * c.smooth(1 - (dz / tall if dz > 0 else -dz / below))
        back = 0.004 if beam else 0.005
        p = Vector((p.x * (1 + wide * corner), p.y + back * corner, p.z + up * corner * (c.smooth(abs(p.x) / 0.03) if beam else 1)))
    # ...and his cheeks pushed up round and out by it.
    cheek = Vector((abs(p.x) - CHEEK.x, p.y - CHEEK.y, p.z - CHEEK.z)).length
    reach = 0.032 if beam else 0.026
    if cheek < reach and p.y < -0.04:
        lift = c.smooth(1 - cheek / reach)
        p = p + Vector((math.copysign(0.002, p.x), -out * (1.4 if beam else 1), out * 0.6)) * lift  # (round, out)
    return p


# ---- His body: bulked out, a belly, his head and feet bigger --------------------

LIMBS = ("upperarm", "lowerarm", "thigh", "calf")
TRUNK = ("spine", "pelvis", "clavicle", "neck")


def giant(i, **face_):
    """Where a point of him goes: his face, his bulk, his belly, his head and feet."""
    p, n, w = rest[i], normals[i], weights[i]
    if i in face:
        p = faced(p, **face_)
    limb = sum(a for b, a in w.items() if b.startswith(LIMBS))
    trunk = sum(a for b, a in w.items() if b.startswith(TRUNK))
    p = p + n * (BULK[0] * limb + BULK[1] * trunk)
    # His belly: round, out in front, low on him (his tummy, not his hips,
    # which bend their own way).
    tummy = sum(w.get(b, 0) for b in ("spine_01", "spine_02", "pelvis"))
    if tummy and p.y < 0.02:
        f = math.exp(-(((p.z - BELLY[1]) / (BELLY[2] if p.z > BELLY[1] else BELLY[3])) ** 2)) * tummy
        front = c.smooth(-p.y / 0.13)
        p = Vector((p.x * (1 + 0.25 * BELLY[0] * f / 0.07), p.y - BELLY[0] * f * front, p.z))
    return grown(p, w)


everyone = range(len(rest))
points = welded(giant(i) for i in everyone)
# His eyes shut, for the game to blink them; and smiling broadly, fed.
blinking = welded(giant(i, blink=True) if i in face else points[i] for i in everyone)
beaming = welded(giant(i, beam=True) if i in face else points[i] for i in everyone)
for v, p in zip(body.data.vertices, points):
    v.co = to_mesh @ p
body.shape_key_add(name="Basis")
key = body.shape_key_add(name="blink", from_mix=False)
for k, p in zip(key.data, blinking):
    k.co = to_mesh @ p
key = body.shape_key_add(name="smile", from_mix=False)
for k, p in zip(key.data, beaming):
    k.co = to_mesh @ p
BROWS = (0.004, 0.008)  # metres his eyebrows are lifted, and arched over each eye (friendly: they come frowning)
for obj in faces_on:
    m = obj.matrix_world
    if obj.name.startswith("Eyebrows"):
        for v in obj.data.vertices:
            v.co.z += BROWS[0] + BROWS[1] * math.sin(math.pi * min(1.0, abs(v.co.x) / 0.062))
    eye = obj.name.startswith("Eyes")
    for v, w in zip(obj.data.vertices, weights_of(obj)):
        v.co = m.inverted() @ grown(m @ v.co, w or {"Head": 1.0}, wide=not eye)
    if eye:
        # (Each eye moved out whole, as far as its middle is by his head's being wider.)
        for side in (1, -1):
            ball = [v for v in obj.data.vertices if (m @ v.co).x * side > 0]
            middle = sum(((m @ v.co).x for v in ball), 0.0) / len(ball)
            apart = (middle - HEAD_AT.x) * (HEAD_WIDE - 1)
            for v in ball:
                v.co = m.inverted() @ ((m @ v.co) + Vector((apart, 0, 0)))
body.data.update()

# ---- His hair and beard (giant-hair, giant-beard), his hide (giant-hide), and the wraps
# round his shins (giant-wraps) ---------------------------------------------------

rng = random.Random(9)
normals = welded([(to_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices], unit=True)
crown = max(p.z for p in rest)
DOWN = Vector((0, 0, -1))


def scalp(i):
    """Whether this is his scalp: over the top and back of his head, not his
    face, nor round his ears."""
    p, w = rest[i], weights[i]
    if w.get("Head", 0) <= 0.5 or (abs(p.x) > 0.06 and p.z < EAR.z + 0.06 and p.y < EAR.y + 0.05):
        return False
    return (p.z > crown - 0.14 and (p.y > -0.04 or p.z > crown - 0.07)) or (p.y > 0.0 and p.z > crown - 0.3)


def hairy(i):
    """His hair: shaggy, swept back."""
    p = rest[i]
    if not scalp(i) or (p.y < -0.03 and p.z < crown - 0.035):
        return 0, 0  # (not on his forehead: it's swept back off it)
    return (1.0, 0.4) if p.y < 0.0 else (1.0, 0.75)


def bearded(i):
    """His beard: bushy, from just under his lower lip round his chin and jaw,
    and up his cheeks beside his mouth (clear of it, so you can see him smile)."""
    p, w = rest[i], weights[i]
    if w.get("Head", 0) <= 0.35 or p.y > -0.01 or abs(p.x) > 0.085 or p.z < 1.5:
        return 0, 0  # (on his face, and under his jaw)
    if p.z < MOUTH - 0.02:
        return 1.0, 0.5  # (out from his chin, and then down: a bushy beard you see from in front)
    if p.z < MOUTH - 0.007 and abs(p.x) < 0.05:
        return 1.0, 0.95  # (and from just under his lower lip, falling straight down over his chin)
    return (0.9, 0.6) if abs(p.x) > 0.055 and p.z < 1.66 else (0, 0)


def hairs(p):
    """His hair's colour here: browns, darker in its hollows."""
    v = p * 25
    colour = c.mix(HAIR[2], HAIR[3], 0.5 + noise.noise(v) * 0.8)
    return c.vary(colour, 0.12, v * 3)


def grow(name, where, blades, length, width, colours, tip, bed_colour, hung=None, bed=True, stray=0.4, comb=None,
         droop=None, smiles=False, spread=0.0):
    """Something growing from his skin (moved as his skin is), as a lumpy bed
    just over it with a ragged edge, wherever where(i) says (how thick, 0 to 1,
    and how far it hangs, 0 sticking out to 1 straight down), and blades out
    of it: as many as blades (each point's chance of a tuft), as long and as
    wide as those (low, high), longer where it hangs. Its blades moved by his
    bone hung, if it's given, not by his skin under them; each straying
    from its way by up to stray, and combed (comb(i): which way, as well, if it's given). (Or, droop,
    its blades' ends moved halfway by that bone: so they hang, when he bends his legs.) With his
    body's shape key "smile" too, if smiles (round his mouth: moved as the skin it grows from). (And its
    blades' roots scattered as far as spread over his skin round each point, where its points are few.)"""
    growing = [where(i) for i in everyone]
    verts, faces, colours_, weights_, grows_from = [], [], [], [], []
    SHELL = (0.012, 0.01)  # metres it stands off his skin, and how lumpy
    if bed:
        on = {}
        for i, (thick, _) in enumerate(growing):
            if thick > 0 and thick + 0.35 * noise.noise(rest[i] * 14) > 0.5:
                on[i] = len(on)
        for i in on:
            q = points[i] + normals[i] * (SHELL[0] + SHELL[1] * (0.5 + 0.5 * noise.noise(rest[i] * 30)))
            verts.append(tuple(q))
            colours_.append(bed_colour(q))
            weights_.append(weights[i])
            grows_from.append(i)
        faces += [tuple(on[v] for v in poly.vertices) for poly in body.data.polygons if all(v in on for v in poly.vertices)]
    for i, (thick, hang) in enumerate(growing):
        if thick <= 0 or rng.random() > blades * thick:
            continue
        p, n = points[i], normals[i]
        for _ in range(max(3, round(3 * blades * thick))):  # (thicker, more of them)
            off = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * stray
            way = (n * (1 - hang) + DOWN * hang * 1.2 + off + (comb(i) if comb else Vector())).normalized()
            if comb and rest[i].y < 0:
                way.y = max(way.y, 0.2)  # (combed back: never forward, down over his face)
                way.normalize()
            long = rng.uniform(*length) * (1 + 1.5 * hang**4)  # (hanging, longer)
            across = way.cross(n)
            if across.length < 1e-3:
                across = way.cross(Vector((1, 0, 0)))
            across = across.normalized() * rng.uniform(*width) * (1 + 0.6 * hang)
            root = p + n * 0.006 + across * rng.uniform(-1.5, 1.5)
            if spread:
                scatter = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * spread
                root += scatter - n * scatter.dot(n)
            colour = rng.choice(colours)
            first = len(verts)
            # (Two pieces, bending further as it goes: a lock, pointed.)
            mid = root + way * long * 0.55
            end = mid + (way + DOWN * 0.35).normalized() * long * 0.5
            for q, half in ((root, 1.0), (mid, 0.6)):
                verts += [tuple(q - across * half), tuple(q + across * half)]
            verts.append(tuple(end))
            grows_from += [i] * 5
            dark = c.mix(colour, (0, 0, 0, 1), 0.35)
            colours_ += [dark, dark, colour, colour, c.mix(colour, tip, 0.6)]
            faces += [(first, first + 1, first + 3, first + 2), (first + 2, first + 3, first + 4)]
            if droop:
                ends = {**{b: a * 0.5 for b, a in weights[i].items()}}
                ends[droop] = ends.get(droop, 0) + 0.5 * sum(weights[i].values())
                weights_ += [weights[i]] * 2 + [ends] * 3
            else:
                weights_ += [{hung: 1.0} if hung else weights[i]] * 5
    obj = c.skinned(name, verts, faces, colours_, weights_, skeleton)
    if smiles:
        obj.shape_key_add(name="Basis")
        key = obj.shape_key_add(name="smile", from_mix=False)
        for k, v, i in zip(key.data, verts, grows_from):
            k.co = Vector(v) + beaming[i] - points[i]
    print(f"{name}: {len(verts)} points")
    return obj


grow("giant-hair", hairy, 2.2, (0.07, 0.13), (0.004, 0.007), HAIR, HAIR_TIP, hairs, stray=0.35,
     comb=lambda i: Vector((0, 0.5, 0.15)))  # (his hair swept back, off his face)
grow("giant-beard", bearded, 4.0, (0.07, 0.12), (0.004, 0.008), HAIR, HAIR_TIP, hairs, stray=0.3, smiles=True,
     spread=0.012, bed=False)  # (all locks: under them, a bed of it, on his small chin, looked flat)


# His hide: a band round his hips, and hanging from it, a panel of it
# behind, a sheet, its hem a little uneven (and one in front, over his lap:
# giant-apron, below, made as he sits).
def hidden(p):
    v = p * 18
    colour = c.mix(HIDE, HIDE_DARK, 0.4 + 0.6 * noise.noise(v))
    colour = c.mix(colour, HIDE_LIGHT, max(0.0, noise.noise(v * 0.5 + Vector((4, 2, 7)))) * 0.3)
    return c.vary(colour, 0.08, v * 4)


def hide(i):
    """The band round his hips."""
    p, w = rest[i], weights[i]
    hips = w.get("pelvis", 0) + w.get("thigh_l", 0) + w.get("thigh_r", 0) + w.get("spine_01", 0)
    return (1.0, 1.0) if 0.84 < p.z < 1.06 and hips > 0.4 else (0, 0)


HIDES = [HIDE, c.mix(HIDE, HIDE_DARK, 0.3), c.mix(HIDE, HIDE_LIGHT, 0.3), c.mix(HIDE, HIDE_DARK, 0.15)]
grow("giant-hide", hide, 0.0, (0, 0), (0, 0), HIDES, HIDE, hidden)

PANEL = (0.36, 0.96, 0.3, 0.025)  # metres across, how high its top is, how long, and how far off his skin
PANEL_GRID = (9, 7)  # its points, across and down


def panel(name):
    """A sheet of hide, hung from his belt behind, moved by his hips: hanging
    straight down."""
    width, top, long, off = PANEL
    across, down = PANEL_GRID
    side = 1  # (behind him: his front is -y)
    near = [p for p in points if p.y * side > 0 and top - long - 0.05 < p.z < top + 0.05 and abs(p.x) < width]
    verts, colours_, weights_ = [], [], []
    for row in range(down):
        t = row / (down - 1)
        for col in range(across):
            u = col / (across - 1)
            x = (u - 0.5) * width
            z = top - long * t
            if row == down - 1:
                z += 0.012 * noise.noise(Vector((x * 30, 9.0, 0)))  # (its hem, a little uneven)
            # (Over his skin there: the furthest out of it, near that spot.)
            by = [p.y for p in near if abs(p.x - x) < 0.03 and abs(p.z - z) < 0.03]
            y = (max(by, key=lambda v: v * side) if by else side * 0.1) + side * (off + 0.01 * t)
            verts.append((x, y, z))
            colours_.append(hidden(Vector((x, y, z))))
            weights_.append({"pelvis": 1.0})
    faces = [(r * across + k, r * across + k + 1, (r + 1) * across + k + 1, (r + 1) * across + k)
             for r in range(down - 1) for k in range(across - 1)]
    c.skinned(name, verts, faces, colours_, weights_, skeleton)


panel("giant-flap")


# The wraps round his shins: strips of cloth wound round and round, from his
# ankles to below his knees.
def wrapped(p):
    a = math.atan2(p.y, abs(p.x) - 0.1)
    band = math.sin(p.z * 90 + a * 1.0)
    colour = c.mix(WRAP, WRAP_DARK, 0.5 * max(0.0, -band) + 0.25 * noise.noise(p * 40))
    return c.vary(colour, 0.06, p * 60)


def wraps(i):
    p, w = rest[i], weights[i]
    shin = w.get("calf_l", 0) + w.get("calf_r", 0)
    return (1.5, 0.0) if shin > 0.5 and 0.1 < p.z < 0.42 else (0, 0)


grow("giant-wraps", wraps, 0.0, (0, 0), (0, 0), [WRAP], WRAP, wrapped)
c.vertex_material().use_backface_culling = False  # (one layer, seen from both sides)

# ---- His skin: weathered, ruddy -------------------------------------------------

c.drop_missing_textures()
# (And its normal and roughness maps: the kit's hero's muscles, and his briefs
# shiny, which the hide covers.)
for material in bpy.data.materials:
    if material.node_tree and "superhero" in material.name.lower():
        for node in list(material.node_tree.nodes):
            name = node.image.name.lower() if node.type == "TEX_IMAGE" and node.image else ""
            if "normal" in name or "rough" in name:
                material.node_tree.nodes.remove(node)
        shader = next(n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        shader.inputs["Metallic"].default_value = 0.0
        shader.inputs["Roughness"].default_value = 0.85


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
        # (Its fine shading softened: the kit's hero's muscles.)
        cell = size // 64
        soft = light.reshape(64, cell, 64, cell).mean((1, 3)).repeat(cell, 0).repeat(cell, 1)
        light = 0.4 * light + 0.6 * soft
        # (The kit's dark briefs, as skin: the hide covers them.)
        top, bottom = rgba[..., :3].max(-1), rgba[..., :3].min(-1)
        light = np.where((top - bottom) < 0.2 * np.maximum(top, 1e-4), 0.85, light)
        low = np.clip(light, 0, 1)[..., None]
        high = np.clip(light - 1, 0, 0.6)[..., None] / 0.6
        rgb = SKIN_DARK * (1 - low) + SKIN * low
        rgb = rgb * (1 - high) + SKIN_LIGHT * high
        # Ruddy in patches, and weathered: a little uneven all over.
        patches = upsampled(size, 8, 1)[..., None]
        rgb = rgb * (1 - 0.3 * patches) + SKIN_RUDDY * 0.3 * patches * (rgb / SKIN).mean(-1, keepdims=True)
        rgb *= (0.9 + 0.2 * upsampled(size, 120, 2))[..., None]
        rgba[..., :3] = rgb
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    elif "hair" in name and "normal" not in name:
        # His eyebrows: bushy, brown.
        pixels = np.empty(len(image.pixels), dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(-1, 4)
        grey = rgba[:, :3] @ np.array([0.3, 0.59, 0.11], dtype=np.float32)
        rgba[:, :3] = grey[:, None] * np.array(HAIR[1][:3], dtype=np.float32) * 2.2
        image.pixels.foreach_set(rgba.ravel())
        image.update()
    image.pack()

# ---- His animations --------------------------------------------------------------

c.clips(skeleton, ANIMS)

# His apron (giant-apron): a sheet of hide over his lap, from his belt to his
# knees, its front edge falling over them, a little unevenly. Made as he sits
# (he always does), over his thighs as they are then, and moved by his hips
# alone: cloth moved by his thighs' bones, in the game, sank into them.
APRON = (0.4, 0.02, 0.1)  # metres across, how far over his thighs, and how far its front edge falls
APRON_GRID = (11, 8)  # its points, across and along
c.pose(skeleton, ANIMS[0], 0)
graph = bpy.context.evaluated_depsgraph_get()
sitting = body.evaluated_get(graph)
# (Only his thighs: not his belly, nor his hands on his knees.)
lap = [sitting.matrix_world @ v.co for v, w in zip(sitting.to_mesh().vertices, weights)
       if sum(a for b, a in w.items() if b.startswith("thigh")) > 0.5]
hips = skeleton.pose.bones["pelvis"]
unsit = (skeleton.matrix_world @ hips.bone.matrix_local) @ (skeleton.matrix_world @ hips.matrix).inverted()
belt = (skeleton.matrix_world @ hips.matrix).translation
knee = (skeleton.matrix_world @ skeleton.pose.bones["calf_l"].matrix).translation
width, off, fall = APRON
across, along = APRON_GRID
verts, colours_, posed = [], [], []
for row in range(along + 2):
    for col in range(across):
        x = (col / (across - 1) - 0.5) * width
        if row < along:
            # (On the tops of his thighs, and across between them.)
            y = belt.y - 0.12 + (knee.y + 0.02 - belt.y + 0.12) * row / (along - 1)
            # (Not up round his hips, where his thighs move his skin too.)
            tops = [p.z for p in lap if abs(p.x - x) < 0.06 and abs(p.y - y) < 0.03 and p.z < belt.z + 0.15]
            q = Vector((x, y, (max(tops) if tops else belt.z) + off))
        else:
            # (Its front edge, falling over his knees.)
            edge = posed[(along - 1) * across + col]
            drop = fall * (row - along + 1) / 2 * (1 + 0.25 * noise.noise(Vector((x * 25, 3.0, 0))))
            q = Vector((edge[0], edge[1] - 0.01 * (row - along + 1), edge[2] - drop))
        posed.append(q)
        verts.append(tuple(unsit @ q))
        colours_.append(hidden(q))
faces = [(r * across + k, r * across + k + 1, (r + 1) * across + k + 1, (r + 1) * across + k)
         for r in range(along + 1) for k in range(across - 1)]
c.skinned("giant-apron", verts, faces, colours_, [{"pelvis": 1.0}] * len(verts), skeleton)
sitting.to_mesh_clear()
bpy.context.scene.frame_set(0)

print(f"body: {len(body.data.vertices)} points")

if out:
    for o in bpy.data.objects:
        o.select_set(o == skeleton or o.parent == skeleton)
    c.export(out, use_selection=True, export_animation_mode="NLA_TRACKS", export_image_format="WEBP")

if preview:
    # Standing, from the front and the back; close up on his face (and blinking);
    # and sitting (on a block for a rock).
    for track in skeleton.animation_data.nla_tracks:
        track.mute = True
    bpy.context.scene.frame_set(0)
    c.preview(preview, (1.2, -4.2, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-back.png"), (-1.6, 3.6, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-face.png"), (0.2, -0.8, 1.5), (0, 0, 1.64), (0.4, 0.8, -1), lens=50)
    keys = body.data.shape_keys.key_blocks
    keys["blink"].value = 1.0
    c.preview(preview.replace(".png", "-blink.png"), (0.1, -0.45, 1.69), (0.02, 0, 1.69), (0.4, 0.8, -1), lens=60)
    keys["blink"].value = 0.0
    seat = c.Builder()
    seat.add([(x, y, z) for z in (0, 0.48) for y in (0.05, 0.6) for x in (-0.35, 0.35)],
             [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)],
             [c.linear("#6b5a46")] * 8)
    seat.build("seat")
    c.pose(skeleton, "Sitting_Idle_Loop", 30)
    c.preview(preview.replace(".png", "-sitting.png"), (1.6, -3.6, 1.3), (0, 0, 0.75), (0.4, 0.8, -1), lens=40)
