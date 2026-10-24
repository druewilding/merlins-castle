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
from mathutils import Vector, kdtree, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

BODY = c.BODIES / "Superhero_Male_FullBody.gltf"

ANIMS = ["Sitting_Idle_Loop", "Sitting_Talking_Loop", "Sitting_Exit", "Dance_Loop"]
TEXTURE = 1024  # the size every texture is shrunk to (the kit's are 2048)

HEAD_SIZE = 1.25  # times bigger, his head...
HANDS = 1.45  # ...his hands...
FEET = 1.35  # ...and his feet
BULK = (0.024, 0.018)  # metres his limbs and his body are bulked out
BELLY = (0.22, 1.02, 0.19)  # metres his belly sticks out, at its middle (its height), and how tall it is
NOSE = (1.8, 0.042)  # how much bigger his nose is grown, and the radius of the round bulb it's made
EARS = 2.0  # and his ears

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


def bone_at(name):
    return skeleton.matrix_world @ skeleton.data.bones[name].head_local


def weights_of(obj):
    names = {g.index: g.name for g in obj.vertex_groups}
    return [{names[g.group]: g.weight for g in v.groups if g.weight > 0} for v in obj.data.vertices]


def side_weight(w, starts, side):
    """How much of a point's weight is on bones of this side starting with any of these."""
    return sum(amount for bone, amount in w.items() if bone.endswith("_" + side) and bone.startswith(starts))


HEAD_AT = bone_at("Head")
FINGERS = ("hand", "index", "middle", "pinky", "ring", "thumb")


def grown(p, w):
    """Where a point of him goes, made a troll: his head, hands and feet
    bigger (blended by how much each bone moves it, so nothing tears)."""
    head = w.get("Head", 0.0)
    p = HEAD_AT + (p - HEAD_AT) * (1 + (HEAD_SIZE - 1) * head)
    for side in ("l", "r"):
        hand = side_weight(w, FINGERS, side)
        if hand:
            at = bone_at(f"hand_{side}")
            p = at + (p - at) * (1 + (HANDS - 1) * hand)
        foot = side_weight(w, ("foot", "ball"), side)
        if foot:
            # (About the ground under his ankle: his soles stay on it.)
            at = bone_at(f"foot_{side}")
            at = Vector((at.x, at.y + 0.03, 0))
            p = at + (p - at) * (1 + (FEET - 1) * foot)
    return p


# ---- His face: a big round nose, and big ears ---------------------------------

to_world = body.matrix_world
to_mesh = to_world.inverted()
weights = weights_of(body)
points = [to_world @ v.co for v in body.data.vertices]
normals = [(to_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices]
face = [i for i, w in enumerate(weights) if w.get("Head", 0) > 0.9]
tip = min((points[i] for i in face if abs(points[i].x) < 0.01 and 1.6 < points[i].z < 1.72), key=lambda p: p.y)
EAR = Vector((0.072, 0.025, 1.695))  # where his ears join his head (on his left; his right's the mirror)
NOSE_AT = tip + Vector((0, 0.027, -0.002))  # the middle of his nose, behind its tip
print(f"nose tip {tuple(round(a, 3) for a in tip)}")

for i in face:
    p = points[i]
    # The nose: grown round and heavy, all of it, from its middle (and
    # drooping a little).
    d = Vector(((p.x - NOSE_AT.x) / 0.035, (p.y - NOSE_AT.y) / 0.045, (p.z - NOSE_AT.z) / 0.035)).length
    if d < 1 and p.y < NOSE_AT.y + 0.01:
        near = c.smooth((1 - d) / 0.5)
        p = NOSE_AT + (p - NOSE_AT) * (1 + (NOSE[0] - 1) * near)
        # (Rounded: its front pulled towards a ball, not a beak.)
        ball = NOSE_AT + (p - NOSE_AT).normalized() * NOSE[1]
        p = p.lerp(ball, 0.7 * near * c.smooth((NOSE_AT.y + 0.005 - p.y) / 0.02))
        p.z -= 0.01 * near
    # The ears: grown out and up from where they join his head.
    if abs(p.x) > EAR.x and abs(p.z - EAR.z) < 0.05 and -0.015 < p.y < 0.07:
        root = Vector((math.copysign(EAR.x, p.x), EAR.y, EAR.z))
        out_by = c.smooth((abs(p.x) - EAR.x) / 0.01)
        p = root + (p - root) * (1 + (EARS - 1) * out_by)
        p.z += 0.02 * out_by * max(0.0, p.z - EAR.z) / 0.04  # (a little pointed)
    # A heavy brow, and the corners of his mouth turned up in a smile.
    if 1.695 < p.z < 1.735 and abs(p.x) < 0.065 and p.y < -0.06:
        p.y -= 0.012 * c.smooth(1 - abs(p.z - 1.712) / 0.022)
    if 1.595 < p.z < 1.63 and 0.01 < abs(p.x) < 0.045 and p.y < -0.05:
        p.z += 0.005 * c.smooth((abs(p.x) - 0.01) / 0.025)
    points[i] = p

# ---- His body: bulked out, a belly, his head, hands and feet bigger -------------

LIMBS = ("upperarm", "lowerarm", "thigh", "calf")
TRUNK = ("spine", "pelvis", "clavicle", "neck")
for i, (p, n, w) in enumerate(zip(points, normals, weights)):
    limb = sum(a for b, a in w.items() if b.startswith(LIMBS))
    trunk = sum(a for b, a in w.items() if b.startswith(TRUNK))
    p = p + n * (BULK[0] * limb + BULK[1] * trunk)
    # His belly: round, out in front, low on him.
    tummy = sum(w.get(b, 0) for b in ("spine_01", "spine_02", "pelvis"))
    if tummy and p.y < 0.02:
        f = math.exp(-(((p.z - BELLY[1]) / BELLY[2]) ** 2)) * tummy
        front = c.smooth(-p.y / 0.13)
        p = Vector((p.x * (1 + 0.14 * f), p.y - BELLY[0] * f * front, p.z))
    # (A little hunched: his upper back up and back.)
    hunch = w.get("spine_03", 0) + 0.5 * w.get("neck_01", 0)
    if p.y > 0:
        p = p + Vector((0, 0.03, 0.01)) * hunch * c.smooth(p.y / 0.1)
    points[i] = grown(p, w)
for v, p in zip(body.data.vertices, points):
    v.co = to_mesh @ p
BROWS = 0.007  # metres his eyebrows are lifted in the middle (kindly: they come frowning)
for obj in faces_on:
    m = obj.matrix_world
    if obj.name.startswith("Eyebrows"):
        for v in obj.data.vertices:
            v.co.z += BROWS * (1 - 2 * min(1.0, abs(v.co.x) / 0.062))
    for v, w in zip(obj.data.vertices, weights_of(obj)):
        v.co = m.inverted() @ grown(m @ v.co, w or {"Head": 1.0})
body.data.update()

# ---- His moss: tufts growing wild on his head and shoulders, down his back,
# and hanging round his hips --------------------------------------------------

rng = random.Random(5)
normals = [(to_world.to_3x3() @ v.normal).normalized() for v in body.data.vertices]
crown = max(p.z for p in points)
tree = kdtree.KDTree(len(points))
for i, p in enumerate(points):
    tree.insert(p, i)
tree.balance()


def where_moss(p, n, w):
    """How thick the moss grows here (0 to 1), and how far it hangs down (0
    sticking out, to 1 hanging straight down)."""
    head = w.get("Head", 0)
    if head > 0.5:
        # (His hair: over the top and the back of his head, not his face, nor
        # his ears.)
        if abs(p.x) > 0.06 and p.z < EAR.z + 0.06 and p.y < EAR.y + 0.05:
            return 0, 0
        if p.z > crown - 0.14 and (p.y > -0.04 or p.z > crown - 0.07):
            return 1.0, 0.3
        if p.y > 0.0 and p.z > crown - 0.3:
            return 1.0, 0.7
        return 0, 0
    shoulders = sum(w.get(b, 0) for b in ("spine_03", "clavicle_l", "clavicle_r", "neck_01"))
    arms = w.get("upperarm_l", 0) + w.get("upperarm_r", 0)
    if p.z > 1.3 and (shoulders > 0.3 or (arms > 0.3 and n.z > 0.1)):
        # (Over his shoulders and down his back; only a little on his chest.)
        return (1.0 if p.y > -0.05 else 0.6), 0.7
    if 0.8 < p.z < 1.04 and (w.get("pelvis", 0) + w.get("thigh_l", 0) + w.get("thigh_r", 0)) > 0.4:
        return 1.0, 1.0  # round his hips, hanging down
    if p.y > 0.05 and 1.0 < p.z < 1.3 and w.get("spine_02", 0) + w.get("spine_01", 0) > 0.4:
        return 0.6, 0.8  # (and a little down his back)
    return 0, 0


verts, faces, colours, moss_weights = [], [], [], []
growing = [where_moss(p, n, w) for p, n, w in zip(points, normals, weights)]


def mossy(p):
    """Moss's colour here: patchy greens, darker in its hollows."""
    v = p * 25
    colour = c.mix(MOSS[3], MOSS[2], 0.5 + noise.noise(v) * 0.8)
    colour = c.mix(colour, MOSS[4], max(0.0, noise.noise(v * 0.4 + Vector((5, 1, 2)))))
    return c.vary(colour, 0.12, v * 3)


# A bed of it, lumpy, just over his skin (moved as his skin is), with a
# ragged edge: wherever all of a face of him grows it.
SHELL = (0.012, 0.012)  # metres it stands off his skin, and how lumpy
bed = {}
for i, (thick, _) in enumerate(growing):
    p = points[i]
    if thick > 0 and thick + 0.35 * noise.noise(p * 14) > 0.5:
        bed[i] = len(bed)
shell = [None] * len(bed)
for i, k in bed.items():
    p = points[i]
    shell[k] = p + normals[i] * (SHELL[0] + SHELL[1] * (0.5 + 0.5 * noise.noise(p * 30)))
verts += [tuple(q) for q in shell]
colours += [mossy(q) for q in shell]
moss_weights += [weights[i] for i in bed]
faces += [tuple(bed[v] for v in poly.vertices) for poly in body.data.polygons if all(v in bed for v in poly.vertices)]

# And blades of it, shaggy, sticking out of the bed (on his head, wild).
DOWN = Vector((0, 0, -1))
for i, (p, n, w) in enumerate(zip(points, normals, weights)):
    thick, hang = growing[i]
    if thick <= 0 or rng.random() > (0.75 if w.get("Head", 0) > 0.5 else 0.3) * thick:
        continue
    near = {b: a for b, a in w.items()}
    skirt = hang > 0.9
    for blade in range(3):
        wild = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.4
        way = (n * (1 - hang) + DOWN * hang * 1.2 + wild).normalized()
        long = rng.uniform(0.15, 0.24) if skirt else rng.uniform(0.04, 0.085)
        across = way.cross(n)
        if across.length < 1e-3:
            across = way.cross(Vector((1, 0, 0)))
        across = across.normalized() * (rng.uniform(0.012, 0.019) if skirt else rng.uniform(0.007, 0.012))
        root = p + n * 0.006 + across * rng.uniform(-1.5, 1.5)
        colour = rng.choice(MOSS)
        first = len(verts)
        # (Two pieces, bending further as it goes: a blade of moss, pointed.)
        bend = way + DOWN * 0.35
        mid = root + way * long * 0.55
        end = mid + bend.normalized() * long * 0.5
        for q, half in ((root, 1.0), (mid, 0.6)):
            verts += [tuple(q - across * half), tuple(q + across * half)]
        verts.append(tuple(end))
        dark = c.mix(colour, (0, 0, 0, 1), 0.35)
        colours += [dark, dark, colour, colour, c.mix(colour, MOSS_TIP, 0.6)]
        faces += [(first, first + 1, first + 3, first + 2), (first + 2, first + 3, first + 4)]
        moss_weights += [near] * 5
moss = c.skinned("troll-moss", verts, faces, colours, moss_weights, skeleton)
c.vertex_material().use_backface_culling = False  # (one layer, seen from both sides)
print(f"moss: {len(verts)} points")

# ---- His skin: pebbly, stone-brown, greener in places ---------------------------

c.drop_missing_textures()
# (And its normal map: the kit's hero's muscles. A troll's lumps are in his skin.)
for material in bpy.data.materials:
    if material.node_tree:
        for node in list(material.node_tree.nodes):
            if node.type == "TEX_IMAGE" and node.image and "normal" in node.image.name.lower() and "superhero" in node.image.name.lower():
                material.node_tree.nodes.remove(node)


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
        # (The kit's dark briefs, as skin: the moss covers them.)
        light = np.where(light < 0.55, 0.85, light)
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
    # Standing, from the front and the side; his face; sitting (on a block
    # for a rock), asking for a tune; and dancing.
    seat = c.Builder()
    seat.add([(x, y, z) for z in (0, 0.48) for y in (0.05, 0.6) for x in (-0.35, 0.35)],
             [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)],
             [c.linear("#6b5a46")] * 8)
    rock = seat.build("seat")
    rock.hide_render = True
    drum_object.location = (0.7, -0.3, 0)
    for track in skeleton.animation_data.nla_tracks:
        track.mute = True
    bpy.context.scene.frame_set(0)
    c.preview(preview, (1.2, -4.2, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-side.png"), (-4.2, -0.6, 1.3), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-back.png"), (-1.2, 4.2, 1.6), (0, 0, 1.1), (0.4, 0.8, -1), lens=40)
    c.preview(preview.replace(".png", "-face.png"), (0.5, -1.2, 1.75), (0, 0, 1.68), (0.4, 0.8, -1), lens=50)
    c.preview(preview.replace(".png", "-profile.png"), (-1.3, -0.5, 1.75), (0, 0, 1.68), (0.4, 0.8, -1), lens=50)
    rock.hide_render = False
    c.pose(skeleton, "Sitting_Talking_Loop", 30)
    c.preview(preview.replace(".png", "-sitting.png"), (1.6, -3.6, 1.3), (0, 0, 0.75), (0.4, 0.8, -1), lens=40)
    rock.hide_render = True
    c.pose(skeleton, "Dance_Loop", 20)
    c.preview(preview.replace(".png", "-dance.png"), (1.8, -4.0, 1.2), (0, 0, 0.95), (0.4, 0.8, -1), lens=40)
