# The snake on the mossy steps, as in their picture: a big python, olive and
# tan, with dark brown saddles edged in gold down its back and a cream belly,
# a broad wedge of a head with yellow eyes, and a pink mouth that opens.
#
# It's made lying dead straight, its spine along y from the tip of its tail
# (y = 0) to its nose (y = LENGTH), its middle at z = 0: the game bends it
# along any curve it likes (coiled, rearing, slithering away), so each piece
# is a separate object it can move on its own: the body (and the top of the
# head), the lower jaw (which drops open on its hinge) and the tongue (which
# flicks out of the front of the mouth).

import math
import sys
from pathlib import Path

import bmesh
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

LENGTH = 3.2  # from the tip of its tail to its nose
THICK = 0.075  # its radius, at its fattest
HEAD = 0.21  # how long its head is, back to its hinge and the end of its neck
MOUTH = -0.012  # the line of its mouth, a little under the middle of its head
SIZE = 1.2  # (made as big as a real python, then scaled up: see the end)

OLIVE = c.linear("#8b7d46")
TAN = c.linear("#b49a5c")
SADDLE = c.linear("#3e2c17")
GOLD = c.linear("#d0b263")
BELLY = c.linear("#ddd2a2")
PINK = c.linear("#8e4a50")
THROAT = c.linear("#2e1012")
FANG = c.linear("#f1ece0")
EYE = c.linear("#e8c13a")
PUPIL = c.linear("#120d08")
TONGUE = c.linear("#8a1a2a")


def outward(obj):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def smooth_step(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def thickness(s):
    """Its radius at s along it: a fine tip, fattening quickly, fattest
    through its middle, slimmer at its neck."""
    tail = smooth_step(s / (LENGTH * 0.38)) ** 0.7
    neck = 1 - 0.28 * smooth_step((s - (LENGTH - HEAD - 0.5)) / 0.5)
    neck *= 1 - 0.2 * smooth_step((s - (LENGTH - HEAD - 0.04)) / 0.08)  # tucked under the back of its head
    return max(0.006, THICK * tail * neck)


def skin(s, a, p):
    """Its colour at s along it and a round it (0 on its back, pi on its
    belly): saddles down its back, blotches on its sides, a cream belly."""
    up = math.cos(a)  # 1 on top, -1 underneath
    side = abs(math.sin(a))
    colour = c.mix(OLIVE, TAN, 0.4 + 0.3 * noise.noise(p * 9))
    # The saddles: dark, wavy-edged patches across its back, one every 17 cm,
    # each edged in gold.
    wave = 0.025 * math.sin(a * 3 + s * 4)
    phase = ((s + wave) / 0.17) % 1
    saddle = 1 - abs(phase - 0.5) / 0.5  # 1 in the middle of a saddle
    reach = smooth_step((up + 0.35) / 0.5)  # down to its sides
    dark = smooth_step((saddle - 0.45) / 0.12) * reach
    rim = smooth_step((saddle - 0.32) / 0.08) * (1 - smooth_step((saddle - 0.45) / 0.06)) * reach
    # And smaller blotches lower on its sides, between them.
    blotch = smooth_step((noise.noise(Vector((s * 7, side * 2, up * 2))) - 0.15) / 0.2) * side * (1 - reach)
    colour = c.mix(colour, GOLD, rim * 0.8)
    colour = c.mix(colour, SADDLE, max(dark, blotch * 0.8))
    colour = c.mix(colour, BELLY, smooth_step((-up - 0.45) / 0.3))
    # Fading a little paler towards the very tip of its tail.
    colour = c.mix(colour, TAN, 0.4 * (1 - smooth_step(s / 0.4)))
    return c.vary(colour, 0.08, p * 25)


# ---- The body: rings of 18 round it, every 2 cm, from its tail to its neck
# (which runs on into the back of the head, under it).
AROUND = 18
STEP = 0.02
body = c.Builder()
end = LENGTH - HEAD + 0.04
rings = [k * STEP for k in range(int(end / STEP) + 1)]
verts, colours = [], []
for s in rings:
    r = thickness(s)
    for j in range(AROUND):
        a = 2 * math.pi * j / AROUND
        # A little flatter underneath, where it lies on the ground.
        x = math.sin(a) * r * 1.08
        z = math.cos(a) * r * (0.95 if math.cos(a) > 0 else 0.8)
        p = Vector((x, s, z))
        verts.append(tuple(p))
        colours.append(skin(s, a, p))
faces = [(k * AROUND + j, k * AROUND + (j + 1) % AROUND, (k + 1) * AROUND + (j + 1) % AROUND, (k + 1) * AROUND + j)
         for k in range(len(rings) - 1) for j in range(AROUND)]
tip = len(verts)
verts.append((0, -0.01, 0))
colours.append(TAN)
faces += [(tip, (j + 1) % AROUND, j) for j in range(AROUND)]
neck = (len(rings) - 1) * AROUND
faces.append(tuple(neck + j for j in range(AROUND)))
body.add(verts, faces, colours)


# ---- The head: a broad, flat wedge, its top from the back of its skull to
# its snout, and under it (above the mouth's line) the pink roof of its mouth
# with two fangs at the front.
H0 = LENGTH - HEAD  # its hinge, at the back of its jaws


def head_shape(t):
    """Its half-width, the height of its crown above the mouth, and how deep
    its lower jaw is, t from the hinge (0) to the snout (1)."""
    wide = 0.068 * (1 - 0.15 * t) * math.sqrt(max(0.0, 1 - max(0.0, (t - 0.72) / 0.28) ** 2) * 0.85 + 0.15)
    if t < 0.25:
        wide *= 0.86 + 0.14 * smooth_step(t / 0.25)  # the jowls, a little narrower than the skull behind
    crown = 0.064 * (1 - 0.45 * smooth_step(t)) * math.sqrt(max(0.0, 1 - max(0.0, (t - 0.8) / 0.2) ** 2) * 0.9 + 0.1)
    jaw = 0.036 * (1 - 0.5 * t) * math.sqrt(max(0.0, 1 - max(0.0, (t - 0.82) / 0.18) ** 2) * 0.9 + 0.1)
    return wide, crown, jaw


def head_colour(p, a, t, top):
    """Olive above, with a dark band from snout through the eye; cream lips
    and chin."""
    up = math.cos(a)
    colour = c.mix(OLIVE, TAN, 0.4 + 0.3 * noise.noise(p * 12))
    if top:
        # A dark arrow down the top of its head, and a stripe through each eye.
        arrow = smooth_step((0.5 - abs(math.sin(a)) - 0.25 * (1 - t)) / 0.1) * smooth_step((0.75 - t) / 0.1)
        stripe = smooth_step((0.25 - abs(up - 0.25)) / 0.1) * (1 - smooth_step((up - 0.6) / 0.1))
        colour = c.mix(colour, SADDLE, max(arrow * up, stripe * 0.85))
        colour = c.mix(colour, BELLY, smooth_step((0.15 - up) / 0.15) * 0.8)  # its lip
    else:
        colour = c.mix(colour, BELLY, 0.75)
    return c.vary(colour, 0.06, p * 30)


ALONG, ROUND = 14, 14


def wedge(top):
    """The top of the head (top) or the lower jaw: a half-round shell over (or
    under) the mouth's line, from the hinge to the snout, and the inside of
    the mouth closing it."""
    build = c.Builder()
    verts, colours = [], []
    for i in range(ALONG + 1):
        t = i / ALONG
        wide, crown, jaw = head_shape(t)
        y = H0 + HEAD * t
        for j in range(ROUND + 1):
            a = -math.pi / 2 + math.pi * j / ROUND  # from one side, over (or under) to the other
            if top:
                x, z = math.sin(a) * wide, MOUTH + math.cos(a) * crown
                # Its brows bulge a little over its eyes.
                z += 0.012 * math.exp(-((t - 0.55) / 0.15) ** 2) * math.exp(-((abs(math.sin(a)) - 0.7) / 0.2) ** 2)
            else:
                x, z = math.sin(a) * wide * 0.92, MOUTH - math.cos(a) * jaw
            p = Vector((x, y, z))
            verts.append(tuple(p))
            colours.append(head_colour(p, a if top else math.pi - a, t, top))
    faces = []
    for i in range(ALONG):
        for j in range(ROUND):
            q = (i * (ROUND + 1) + j, (i + 1) * (ROUND + 1) + j, (i + 1) * (ROUND + 1) + j + 1, i * (ROUND + 1) + j + 1)
            faces.append(q if top else q[::-1])
    # The inside of the mouth: a pink floor (or roof) across, from side to
    # side, darker deep in at the hinge; its back closed too.
    inside = len(verts)
    for i in range(ALONG + 1):
        t = i / ALONG
        wide = head_shape(t)[0] * (1 if top else 0.92)
        y = H0 + HEAD * t
        sink = 0.006 * (1 - t) if top else -0.006 * (1 - t)
        for j in range(3):
            x = (-1 + j) * wide
            verts.append((x, y, MOUTH + (sink if j == 1 else 0)))
            colours.append(c.mix(THROAT, PINK, smooth_step(t / 0.5)))
    for i in range(ALONG):
        for j in range(2):
            q = (inside + i * 3 + j, inside + i * 3 + j + 1, inside + (i + 1) * 3 + j + 1, inside + (i + 1) * 3 + j)
            faces.append(q if top else q[::-1])
    back = [k for k in range(ROUND + 1)]
    faces.append(tuple(back if not top else back[::-1]))
    build.add(verts, faces, colours)
    return build


upper = wedge(True)
# Its eyes: yellow, round, each with a black slit, high on the sides of its
# head, looking out and a little forward.
for side in (-1, 1):
    t = 0.56
    wide, crown, _ = head_shape(t)
    centre = Vector((side * wide * 0.83, H0 + HEAD * t, MOUTH + crown * 0.62))
    look = Vector((side * 0.9, 0.35, 0.25)).normalized()
    verts, colours, faces = [], [], []
    N, M = 8, 10
    for k in range(N + 1):
        phi = math.pi * k / N
        for j in range(M):
            a = 2 * math.pi * j / M
            d = Vector((math.sin(phi) * math.cos(a), math.sin(phi) * math.sin(a), math.cos(phi)))
            p = centre + d * 0.0125
            verts.append(tuple(p))
            facing = d.dot(look)
            # The slit: narrow, upright, in the middle of the side that looks out.
            across = d - look * facing
            slit = facing > 0.55 and abs(across.dot(Vector((0, 1, -0.4)).normalized())) < 0.18
            colours.append(PUPIL if slit else c.mix(EYE, c.linear("#8a6a12"), 0.6 * (1 - max(0.0, facing))))
    for k in range(N):
        for j in range(M):
            faces.append((k * M + j, k * M + (j + 1) % M, (k + 1) * M + (j + 1) % M, (k + 1) * M + j))
    upper.add(verts, faces, colours)
# Its fangs: two little curved teeth hanging from the front of its upper jaw.
for side in (-1, 1):
    t = 0.82
    wide = head_shape(t)[0]
    root = Vector((side * wide * 0.62, H0 + HEAD * t, MOUTH))
    verts = [tuple(root + Vector((math.cos(a) * 0.004, math.sin(a) * 0.004, 0))) for a in (0, 2.1, 4.2)]
    verts.append(tuple(root + Vector((0, -0.006, -0.02))))
    upper.add(verts, [(0, 1, 2), (0, 3, 1), (1, 3, 2), (2, 3, 0)], [FANG] * 4)
body.add(upper.verts, upper.faces, upper.colours)
body_object = body.build("snake", smooth=True)
outward(body_object)

jaw = wedge(False)
jaw_object = jaw.build("snake-jaw", smooth=True)
outward(jaw_object)

# The tongue: thin and dark red, forked at its tip, lying in its mouth (the
# game slides it out and in).
tongue = c.Builder()
TONGUE_LONG = 0.11
verts, colours, faces = [], [], []
k = 6
for i in range(k + 1):
    t = i / k
    y = LENGTH - 0.05 + TONGUE_LONG * t
    w = 0.005 * (1 - 0.5 * t)
    verts += [(-w, y, MOUTH - 0.002), (w, y, MOUTH - 0.002), (0, y, MOUTH + 0.002)]
for i in range(k):
    for a, b in ((0, 1), (1, 2), (2, 0)):
        faces.append((i * 3 + a, i * 3 + b, (i + 1) * 3 + b, (i + 1) * 3 + a))
tongue.add(verts, faces, [TONGUE] * len(verts))
for side in (-1, 1):
    base = Vector((0, LENGTH - 0.05 + TONGUE_LONG, MOUTH))
    point = base + Vector((side * 0.012, 0.03, 0.002))
    w = 0.0022
    verts = [tuple(base + Vector((-w, 0, -0.002))), tuple(base + Vector((w, 0, -0.002))),
             tuple(base + Vector((0, 0, 0.002))), tuple(point)]
    tongue.add(verts, [(0, 1, 3), (1, 2, 3), (2, 0, 3), (0, 2, 1)], [TONGUE] * 4)
tongue_object = tongue.build("snake-tongue", smooth=False)
outward(tongue_object)

# All of it a fifth bigger than a real one, to hold the apple in its jaws.
for obj in (body_object, jaw_object, tongue_object):
    obj.data.transform(Matrix.Scale(SIZE, 4))

if out:
    c.export(out)
    print(f"Exported {out}")

if preview:
    # Just its head, from the front and above, to see its face.
    c.preview(preview, (0.55, SIZE * LENGTH + 0.55, 0.35), (0, SIZE * (LENGTH - 0.1), 0), (0.3, 0.6, -1), lens=50)
