# The objects you find and carry, one per object, named by its id in
# data/world.json. Each lies as it would on the ground, its middle at the
# origin and its underside at z = 0, along y (the game turns it as it lands).
#
# The ladder, the plank, the key, the axe, the apple, the emerald, the
# broom, the lamp, the rope, the penny, the water, the harp, the cake, the gold, the silver and the ring so far; the rest are to come (PLAN-V3.md).

import math
import random
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()


def outward(obj):
    """Every face facing out (the game's glow round what you point at grows
    out along them)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()


def out_from(obj, centre):
    """Every face facing away from centre: for a cut stone, whose facets are
    each their own (not joined, so outward can't tell which way is out)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for f in bm.faces:
        if f.normal.dot(f.calc_center_median() - Vector(centre)) < 0:
            f.normal_flip()
    bm.to_mesh(obj.data)
    bm.free()


WOOD = c.linear("#8a5a33")
RUNG = c.linear("#a2703f")


def box(builder, x0, y0, z0, x1, y1, z1, colour):
    """A box with its own corners for each face, so it shades flat."""
    corners = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    for face in faces:
        pts = [corners[i] for i in face]
        builder.add(pts, [(0, 1, 2, 3)], [c.vary(colour, 0.15, Vector(p) * 3) for p in pts])


def rung(builder, x0, x1, y, z, r, colour, sides=6):
    """A round rung across, from one rail to the other."""
    verts, faces = [], []
    for k in range(sides):
        a = 2 * math.pi * k / sides
        dy, dz = math.cos(a) * r, math.sin(a) * r
        verts += [(x0, y + dy, z + dz), (x1, y + dy, z + dz)]
    faces = [(2 * k, 2 * ((k + 1) % sides), 2 * ((k + 1) % sides) + 1, 2 * k + 1) for k in range(sides)]
    builder.add(verts, faces, [c.vary(colour, 0.15, Vector(v) * 3) for v in verts])


# The ladder: long enough to lean on the old stone wall (4.5 m) and reach
# over the top. Two rails, and a rung every 30 cm.
LENGTH, WIDTH, RAIL, DEEP = 5.0, 0.5, 0.07, 0.09
ladder = c.Builder()
for side in (-1, 1):
    x = side * WIDTH / 2
    box(ladder, x - RAIL / 2, -LENGTH / 2, 0, x + RAIL / 2, LENGTH / 2, DEEP, WOOD)
n = int(LENGTH / 0.3)
for k in range(n):
    y = -LENGTH / 2 + (k + 0.5) * LENGTH / n
    rung(ladder, -WIDTH / 2, WIDTH / 2, y, DEEP / 2, 0.022, RUNG)
outward(ladder.build("ladder", smooth=False))

# The plank: long enough to bridge the deep river where it narrows (its
# shores 6 m apart: art/blender/land.py), with half a metre on either bank.
# One long, weathered board, grey-brown, its grain running along it, with a
# few dark knots, and its ends (sawn across) darker.
PLANK_LONG, PLANK_WIDE, PLANK_THICK = 7.0, 0.45, 0.08
PLANK = c.linear("#8d7454")
KNOT = c.linear("#4a3826")
ENDS = c.linear("#5c4630")
KNOTS = [(0.08, -2.3), (-0.1, -0.6), (0.06, 1.2), (-0.05, 2.9)]  # across and along


def plank_colour(x, y, z):
    """Its grain: streaks along it (noise stretched out lengthways), and its knots."""
    grain = noise.noise(Vector((x * 40, y * 1.2, z * 40 + 3)))
    col = c.mix(PLANK, c.linear("#a68c66"), 0.5 + 0.5 * grain)
    for kx, ky in KNOTS:
        d = math.hypot((x - kx) * 1.0, (y - ky) * 0.6)
        col = c.mix(col, KNOT, max(0.0, 1 - d / 0.06))
    return col


plank = c.Builder()
ACROSS, ALONG = 4, 56  # points across its faces, and along it
xs = [-PLANK_WIDE / 2 + PLANK_WIDE * i / ACROSS for i in range(ACROSS + 1)]
ys = [-PLANK_LONG / 2 + PLANK_LONG * j / ALONG for j in range(ALONG + 1)]
zs = [0.0, PLANK_THICK]


def strip(points):
    """A face made of a grid of points (rows of them), each corner coloured by its grain."""
    rows, cols = len(points), len(points[0])
    verts = [p for row in points for p in row]
    faces = [(r * cols + k, r * cols + k + 1, (r + 1) * cols + k + 1, (r + 1) * cols + k)
             for r in range(rows - 1) for k in range(cols - 1)]
    plank.add(verts, faces, [plank_colour(*p) for p in verts])


strip([[(x, y, PLANK_THICK) for x in xs] for y in ys])  # its top
strip([[(x, y, 0.0) for x in xs[::-1]] for y in ys])  # its underside
for side in (-1, 1):  # its long edges
    x = side * PLANK_WIDE / 2
    strip([[(x, y, z) for z in (zs if side > 0 else zs[::-1])] for y in ys])
for end in (-1, 1):  # its ends, sawn across
    y = end * PLANK_LONG / 2
    pts = [(x, y, z) for z in zs for x in (xs[0], xs[-1])]
    plank.add(pts, [(0, 1, 3, 2)], [c.vary(ENDS, 0.1, Vector(p) * 5) for p in pts])
outward(plank.build("plank", smooth=False))

# The key: a big old one (70 cm, so you can spot it in the grass: drawn half a
# metre long, then made KEY_SIZE times bigger), rusty bronze as in its
# picture: a curly bow (two loops and a little crown), a round shaft with
# collars, and a chunky bit with notches.
KEY_SIZE = 1.4
RUST = c.linear("#a8692f")
RUST_DARK = c.linear("#62371a")
RUST_LIGHT = c.linear("#d6903f")


def rusty(p):
    """Mottled: orange where it's rubbed, dark brown where it's rusted through."""
    v = Vector(p) * 45
    t = 0.5 + noise.noise(v) * 0.9
    colour = c.mix(RUST_DARK, RUST_LIGHT, t)
    if noise.noise(v * 0.5 + Vector((7, 3, 1))) > 0.25:
        colour = c.mix(colour, RUST_DARK, 0.6)
    return c.mix(colour, RUST, 0.25)


def tube(builder, path, radius, closed=False, sides=7):
    """A round bar along a path lying flat (in x and y, at the path's z), or straight along y."""
    n = len(path)
    rings = []
    for k, p in enumerate(path):
        a, b = path[(k - 1) % n if closed else max(k - 1, 0)], path[(k + 1) % n if closed else min(k + 1, n - 1)]
        tangent = (Vector(b) - Vector(a)).normalized()
        across = tangent.cross(Vector((0, 0, 1))).normalized()
        rings.append([Vector(p) + across * math.cos(2 * math.pi * j / sides) * radius
                      + Vector((0, 0, 1)) * math.sin(2 * math.pi * j / sides) * radius for j in range(sides)])
    verts = [tuple(v) for ring in rings for v in ring]
    faces = [(k * sides + j, k * sides + (j + 1) % sides, ((k + 1) % n) * sides + (j + 1) % sides,
              ((k + 1) % n) * sides + j)
             for k in range(n if closed else n - 1) for j in range(sides)]
    if not closed:
        faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    builder.add(verts, faces, [rusty(v) for v in verts])


def loop(cx, cy, r, z, points=18):
    return [(cx + math.cos(2 * math.pi * k / points) * r, cy + math.sin(2 * math.pi * k / points) * r, z)
            for k in range(points)]


key = c.Builder()
Z = 0.02  # the shaft's middle, above the ground
tube(key, loop(-0.042, -0.19, 0.04, Z), 0.012, closed=True)  # the bow's two loops
tube(key, loop(0.042, -0.19, 0.04, Z), 0.012, closed=True)
tube(key, loop(0, -0.255, 0.018, Z), 0.009, closed=True)  # and its little crown
tube(key, [(0, -0.237, Z), (0, -0.14, Z)], 0.011)  # up the middle of the bow
tube(key, [(0, y / 100, Z) for y in range(-15, 25)], 0.017)  # the shaft
for y0, y1, r in ((-0.155, -0.125, 0.026), (0.09, 0.115, 0.025), (0.235, 0.25, 0.022)):
    tube(key, [(0, y0, Z), (0, y1, Z)], r)  # its collars, and the end
for x0, y0, x1, y1 in ((0.015, 0.13, 0.05, 0.225), (0.05, 0.13, 0.08, 0.155), (0.05, 0.172, 0.08, 0.193),
                       (0.05, 0.21, 0.08, 0.225), (0.08, 0.13, 0.095, 0.14), (0.08, 0.21, 0.095, 0.225)):
    corners = [(x, y, z) for z in (Z - 0.014, Z + 0.014) for y in (y0, y1) for x in (x0, x1)]
    for face in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]:
        pts = [corners[i] for i in face]
        key.add(pts, [(0, 1, 2, 3)], [rusty(p) for p in pts])  # the bit, and its notches
key_object = key.build("key", smooth=False)
key_object.data.transform(Matrix.Scale(KEY_SIZE, 4))
outward(key_object)

# The axe: as in its picture, a rusty iron head with a bearded blade (its
# edge rubbed bright), on a curved wooden handle swelling to a knob at the
# end. Lying flat, its blade to the west (-x); 0.87 m long.
IRON = c.linear("#6f6c66")
IRON_LIGHT = c.linear("#b9b6ae")
AXE_WOOD = c.linear("#c99550")
AXE_WOOD_DARK = c.linear("#86592c")
MID = Vector((-0.106, 0.0125, 0))  # its middle, moved to the origin
AZ = 0.035  # the head's middle, above the ground (half its thickness at the eye)


def iron(p, s):
    """Grey iron, rusty in patches, brighter towards the edge (s, 0 to 1)."""
    v = Vector(p) * 30
    colour = c.mix(IRON, IRON_LIGHT, 0.15 + 0.5 * s ** 2 + noise.noise(v) * 0.15)
    if noise.noise(v * 0.6 + Vector((2, 9, 4))) > 0.3 + s * 0.3:
        colour = c.mix(colour, rusty(p), 0.6)
    return colour


def grain(p):
    """Wood, with streaks along the handle."""
    v = Vector(p)
    t = 0.5 + noise.noise(Vector((v.x * 60, v.y * 6, v.z * 60))) * 0.8
    return c.vary(c.mix(AXE_WOOD_DARK, AXE_WOOD, t), 0.1, v * 20)


axe = c.Builder()
# The handle: rings along a gentle curve, thin under the head, a knob at the end.
SIDES, STEPS = 8, 24
ring_list = []
for k in range(STEPS + 1):
    u = k / STEPS  # 0 at the end, 1 through the top of the head
    y = -0.42 + u * 0.865
    x = 0.025 * math.sin(u * math.pi * 1.2)
    r = 0.024 + 0.004 * u + 0.01 * max(0, 1 - u / 0.1) ** 2
    ring_list.append([Vector((x + math.cos(2 * math.pi * j / SIDES) * r, y,
                              AZ + math.sin(2 * math.pi * j / SIDES) * r)) - MID for j in range(SIDES)])
verts = [tuple(v) for ring in ring_list for v in ring]
faces = [(k * SIDES + j, k * SIDES + (j + 1) % SIDES, (k + 1) * SIDES + (j + 1) % SIDES, (k + 1) * SIDES + j)
         for k in range(STEPS) for j in range(SIDES)]
faces += [tuple(range(SIDES))[::-1], tuple(STEPS * SIDES + j for j in range(SIDES))]
axe.add(verts, faces, [grain(v) for v in verts])

# The head: a grid across it (u from the poll to the edge, v from its
# underside to its top), thick at the eye and thinning to the edge.
EYE_X, POLL_X = -0.06, 0.05
NU, NV = 14, 6


def head_point(u, v, top):
    edge = -0.25 - 0.012 * math.sin(math.pi * v)
    x = POLL_X + u * (edge - POLL_X)
    s = max(0.0, (EYE_X - x) / (EYE_X - edge))  # 0 at the eye, 1 at the edge
    low = 0.31 - 0.11 * s ** 1.6  # the beard sweeps down
    high = 0.42 + 0.03 * s ** 2  # and the toe up
    y = low + v * (high - low)
    thick = 0.07 if s == 0 else 0.07 - 0.062 * s ** 0.8
    z = AZ + (thick / 2 if top else -thick / 2)
    return Vector((x, y, z)) - MID, s


grid = {}
verts, colours = [], []
for top in (True, False):
    for i in range(NU + 1):
        for j in range(NV + 1):
            p, s = head_point(i / NU, j / NV, top)
            grid[top, i, j] = len(verts)
            verts.append(tuple(p))
            colours.append(iron(p, s))
faces = []
for i in range(NU):
    for j in range(NV):
        a, b, cc, d = (i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)
        faces.append(tuple(grid[True, *q] for q in (a, b, cc, d)))
        faces.append(tuple(grid[False, *q] for q in (d, cc, b, a)))
# Its sides: underneath and along the top, the poll and the edge.
for i in range(NU):
    faces.append((grid[True, i + 1, 0], grid[True, i, 0], grid[False, i, 0], grid[False, i + 1, 0]))
    faces.append((grid[True, i, NV], grid[True, i + 1, NV], grid[False, i + 1, NV], grid[False, i, NV]))
for j in range(NV):
    faces.append((grid[True, 0, j], grid[True, 0, j + 1], grid[False, 0, j + 1], grid[False, 0, j]))
    faces.append((grid[True, NU, j + 1], grid[True, NU, j], grid[False, NU, j], grid[False, NU, j + 1]))
axe.add(verts, faces, colours)
outward(axe.build("axe", smooth=False))

# The apple: as in its picture, a rosy red one, streaked with gold, yellower
# round the dimple at the top, with a woody stalk and one leaf curling off
# it. Standing on its five little bumps, stalk up; 27 cm across (big, like
# the key, so you can spot it in the grass).
R = 0.135  # its radius, round its middle
APPLE_RED = c.linear("#cc1d1f")
APPLE_DARK = c.linear("#7a0d12")
APPLE_GOLD = c.linear("#e7a23a")
APPLE_YELLOW = c.linear("#c9bd45")
STALK = c.linear("#6b4424")
STALK_LIGHT = c.linear("#9a7046")
LEAF = c.linear("#5b8a2e")
LEAF_DARK = c.linear("#2f5a1d")
LEAF_LIGHT = c.linear("#a9c25a")


def smooth_step(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def apple_point(phi, a):
    """On its skin: phi from the bottom (0) to the top (pi), a round it."""
    lobes = 1 + 0.025 * math.cos(5 * a) + 0.07 * math.cos(5 * a) * smooth_step((0.9 - phi) / 0.9)
    wide = R * math.sin(phi) * (1 + 0.1 * (1 - math.cos(phi)) / 2) * lobes  # broader at the shoulders
    z = -R * 0.92 * math.cos(phi)
    z -= R * 0.38 * math.exp(-(((math.pi - phi) / 0.42) ** 2))  # the dimple round the stalk
    z += R * 0.16 * math.exp(-((phi / 0.4) ** 2))  # and the little one underneath
    return Vector((math.cos(a) * wide, math.sin(a) * wide, z))


def apple_skin(p, phi, a):
    """Red, darker underneath, streaked gold down from the top, and yellow round the stalk."""
    up = 1 - phi / math.pi  # 0 at the top, 1 at the bottom
    colour = c.mix(APPLE_RED, APPLE_DARK, 0.15 + 0.5 * up ** 2 + noise.noise(p * 14) * 0.15)
    streak = noise.noise(Vector((math.cos(a) * 3.2, math.sin(a) * 3.2, phi * 0.6)) * 2.5)
    colour = c.mix(colour, APPLE_GOLD, max(0.0, streak) * 0.9 * (1 - up) ** 1.5)
    colour = c.mix(colour, APPLE_YELLOW, smooth_step((0.2 - up) / 0.2) * 0.85)
    return c.vary(colour, 0.06, p * 20)


apple = c.Builder()
AROUND, UP = 40, 28
rings = [[apple_point(math.pi * k / UP, 2 * math.pi * j / AROUND) for j in range(AROUND)] for k in range(1, UP)]
bottom, top = apple_point(0, 0), apple_point(math.pi, 0)
verts = [tuple(bottom)] + [tuple(v) for ring in rings for v in ring] + [tuple(top)]
colours = [apple_skin(bottom, 0, 0)] + [
    apple_skin(rings[k][j], math.pi * (k + 1) / UP, 2 * math.pi * j / AROUND)
    for k in range(UP - 1) for j in range(AROUND)
] + [apple_skin(top, math.pi, 0)]
last = len(verts) - 1
faces = [(0, 1 + (j + 1) % AROUND, 1 + j) for j in range(AROUND)]
faces += [(1 + k * AROUND + j, 1 + k * AROUND + (j + 1) % AROUND, 1 + (k + 1) * AROUND + (j + 1) % AROUND,
           1 + (k + 1) * AROUND + j) for k in range(UP - 2) for j in range(AROUND)]
faces += [(1 + (UP - 2) * AROUND + j, 1 + (UP - 2) * AROUND + (j + 1) % AROUND, last) for j in range(AROUND)]
apple.add(verts, faces, colours)

# The stalk: from deep in the dimple, up and leaning a little, thinner at its tip.
stalk = [top + Vector((-0.012 * t ** 2, 0.004 * t, 0.085 * t)) for t in (k / 8 for k in range(9))]
STALK_SIDES = 6
verts, colours = [], []
for k, p in enumerate(stalk):
    r = 0.009 - 0.002 * k / 8
    for j in range(STALK_SIDES):
        a = 2 * math.pi * j / STALK_SIDES
        verts.append(tuple(p + Vector((math.cos(a) * r, math.sin(a) * r, 0))))
        colours.append(c.vary(c.mix(STALK, STALK_LIGHT, 0.5 + 0.4 * math.cos(a - 1)), 0.1, p * 60))
faces = [(k * STALK_SIDES + j, k * STALK_SIDES + (j + 1) % STALK_SIDES, (k + 1) * STALK_SIDES + (j + 1) % STALK_SIDES,
          (k + 1) * STALK_SIDES + j) for k in range(len(stalk) - 1) for j in range(STALK_SIDES)]
faces.append(tuple((len(stalk) - 1) * STALK_SIDES + j for j in range(STALK_SIDES)))
apple.add(verts, faces, colours)

# The leaf: from near the stalk's tip, out and up and drooping at its point,
# folded a little along its middle, pointed, lighter along the vein. Thin,
# but solid (so it shows from above and below).
LEAF_LONG, LEAF_WIDE = 0.17, 0.05
ALONG, ACROSS = 14, 6
base = stalk[6]
out_dir = Vector((1, -0.35, 0)).normalized()
side_dir = Vector((0, 0, 1)).cross(out_dir).normalized()


def leaf_point(s, t):
    """s from its base (0) to its point (1), t from one edge (-1) to the other (1)."""
    width = LEAF_WIDE * math.sin(math.pi * min(1.0, s * 1.15)) ** 0.7 * (1 - 0.25 * s) if s < 1 else 0
    height = 0.05 * s - 0.09 * s ** 2 + abs(t) * width * 0.45  # rising, then drooping; its edges up
    return base + out_dir * (LEAF_LONG * s) + side_dir * (t * width) + Vector((0, 0, height))


def leaf_colour(p, s, t):
    colour = c.mix(LEAF_DARK, LEAF, 0.55 + noise.noise(p * 50) * 0.3 + 0.2 * (1 - abs(t)))
    if abs(t) < 0.2:
        colour = c.mix(colour, LEAF_LIGHT, 0.6 * (1 - abs(t) / 0.2))  # the vein
    return c.mix(colour, LEAF_LIGHT, 0.15 * s)


grid, verts, colours = {}, [], []
for under in (False, True):
    for i in range(ALONG + 1):
        for j in range(ACROSS + 1):
            s, t = i / ALONG, -1 + 2 * j / ACROSS
            p = leaf_point(s, t) - Vector((0, 0, 0.002 if under else 0))
            grid[under, i, j] = len(verts)
            verts.append(tuple(p))
            colours.append(c.mix(leaf_colour(p, s, t), LEAF_DARK, 0.3 if under else 0))
faces = []
for i in range(ALONG):
    for j in range(ACROSS):
        q = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
        faces.append(tuple(grid[False, *k] for k in q[::-1]))
        faces.append(tuple(grid[True, *k] for k in q))
# And round its edge, closing it up.
edge = [(i, 0) for i in range(ALONG)] + [(ALONG, j) for j in range(ACROSS)]
edge += [(i, ACROSS) for i in range(ALONG, 0, -1)] + [(0, j) for j in range(ACROSS, 0, -1)]
for k, a in enumerate(edge):
    b = edge[(k + 1) % len(edge)]
    faces.append((grid[False, *a], grid[False, *b], grid[True, *b], grid[True, *a]))
apple.add(verts, faces, colours)

# Standing on the ground, its middle (across) at the origin.
apple_object = apple.build("apple", smooth=True)
low = min(v.co.z for v in apple_object.data.vertices)
apple_object.data.transform(Matrix.Translation((0, 0, -low)))
outward(apple_object)

# The emerald: as in its picture, a step-cut one, an octagon (a rectangle
# with its corners cut) with a broad flat table on top, stepping down to its
# girdle and in again underneath, to a little flat base it lies on. Each
# facet its own shade of deep green (bluer than the grass), lighter on top; 30 cm long (big, like the
# key, so you can spot it).
emerald = c.Builder()
EM_HALF, EM_WIDE, EM_CUT = 0.15, 0.12, 0.04  # half its length and width, at its girdle, and its corners cut


def octagon(scale, z):
    a, b, k = EM_HALF * scale, EM_WIDE * scale, EM_CUT * scale
    return [(x, y, z) for x, y in ((b - k, a), (-b + k, a), (-b, a - k), (-b, -a + k),
                                   (-b + k, -a), (b - k, -a), (b, -a + k), (b, a - k))]


# From its base up: the base, the girdle (bottom and top), a step on the
# crown, and the table.
rings = [octagon(0.4, 0.0), octagon(1.0, 0.09), octagon(1.0, 0.11), octagon(0.85, 0.15), octagon(0.6, 0.18)]
EM_COLOURS = [c.linear(h) for h in ("#02381f", "#065c34", "#0c8a48", "#22b866")]  # the pavilion, girdle, crown and step
for ring_, (lo, hi) in enumerate(zip(rings, rings[1:])):
    for k in range(8):
        pts = [lo[k], lo[(k + 1) % 8], hi[(k + 1) % 8], hi[k]]
        emerald.add(pts, [(0, 1, 2, 3)], [c.vary(EM_COLOURS[ring_], 0.18, Vector((k, ring_, 1.0)))] * 4)
emerald.add(rings[0][::-1], [tuple(range(8))], [c.linear("#022c18")] * 8)
emerald.add(rings[-1], [tuple(range(8))], [c.linear("#0f9a50")] * 8)
out_from(emerald.build("emerald", smooth=False), (0, 0, 0.1))

# The broom: as in its picture, a witch's besom. A long, knobbly handle,
# bent a little, swelling to a knob at its end, and a bundle of twigs bound
# round it with rope (their tops sticking out above it), spreading out and
# a little flattened, as they would be from sweeping. 1.6 m long, lying on
# its knob and its twigs.
BROOM_WOOD = c.linear("#d29a52")
BROOM_WOOD_DARK = c.linear("#7a4f27")
BROOM_KNOT = c.linear("#3e2614")
MOSS = c.linear("#8c8a48")
TWIG = c.linear("#c8873e")
TWIG_DARK = c.linear("#4f321a")
ROPE = c.linear("#d9a650")
ROPE_DARK = c.linear("#8f6428")
broom_rng = random.Random(7)


def round_tube(builder, path, radii, colour, sides=6):
    """A round bar along any path (mostly along y, or mostly round it),
    `radii` at each point, each point coloured by colour(p, k, a): how far
    along it (0 to 1) and round it."""
    n = len(path)
    mean = (Vector(path[-1]) - Vector(path[0])).normalized()
    ref = Vector((0, 0, 1)) if abs(mean.y) > 0.7 else Vector((0, 1, 0))
    verts, colours = [], []
    for k, p in enumerate(path):
        tangent = (Vector(path[min(k + 1, n - 1)]) - Vector(path[max(k - 1, 0)])).normalized()
        across = tangent.cross(ref).normalized()
        up = across.cross(tangent).normalized()
        for j in range(sides):
            a = 2 * math.pi * j / sides
            v = Vector(p) + (across * math.cos(a) + up * math.sin(a)) * radii[k]
            verts.append(tuple(v))
            colours.append(colour(v, k / (n - 1), a))
    faces = [(k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
             for k in range(n - 1) for j in range(sides)]
    faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    builder.add(verts, faces, colours)


broom = c.Builder()

# The handle: s is how far along it from its knob (0), the twigs bound from
# BIND to BOUND. It bends gently this way and that, and has knots: bumps on
# one side, dark at their middles.
BIND, BOUND, TOP, TIPS = 1.06, 1.16, 0.95, 1.62  # and the twigs' tops, and their tips
KNOTS_ALONG = [(0.12, 0.6, 0.016), (0.27, 3.5, 0.012), (0.38, 1.9, 0.015), (0.52, 4.6, 0.011),
               (0.63, 0.2, 0.016), (0.77, 2.7, 0.013), (0.88, 5.4, 0.012)]  # s, round it, how big


def handle_centre(s):
    return Vector((0.055 * math.sin(s * 2.6 + 0.4) + 0.015 * math.sin(s * 8.3), -s,
                   0.018 * math.sin(s * 3.3 + 1.1)))


def handle_radius(s, a):
    if s < 0:  # the knob's rounded end
        r = 0.04 * math.sqrt(max(0.0, 1 - (s / 0.04) ** 2))
    else:
        r = 0.024 + 0.004 * s + 0.016 * math.exp(-((s / 0.06) ** 2))
        r *= 1 + 0.08 * noise.noise(Vector((s * 9, math.cos(a), math.sin(a))))
    for ks, ka, size in KNOTS_ALONG:
        r += size * math.exp(-(((s - ks) / 0.025) ** 2)) * max(0.0, math.cos(a - ka)) ** 3
    return r


def handle_colour(p, s, a):
    v = Vector(p)
    t = 0.5 + noise.noise(Vector((v.x * 50, v.y * 4, v.z * 50))) * 0.8
    colour = c.mix(BROOM_WOOD_DARK, BROOM_WOOD, t)
    if noise.noise(v * 8 + Vector((4, 1, 7))) > 0.35 and s < 0.7:
        colour = c.mix(colour, MOSS, 0.45)  # a little moss, up by the knob
    for ks, ka, size in KNOTS_ALONG:
        d = math.hypot((s - ks) / 0.02, (math.cos(a - ka) - 1) * 4)
        colour = c.mix(colour, BROOM_KNOT, max(0.0, 1 - d) * 0.9)  # its eye
        colour = c.mix(colour, BROOM_WOOD_DARK, max(0.0, 1 - abs(d - 1.4)) * 0.5)  # and a dark rim round it
    return c.vary(colour, 0.08, v * 20)


H_SIDES = 10
ss = [-0.04 * math.cos(math.pi / 2 * k / 4) for k in range(4)]  # round the knob
ss += [k / 100 for k in range(0, 126)]
verts, colours = [], []
for s in ss:
    centre = handle_centre(max(s, 0))
    for j in range(H_SIDES):
        a = 2 * math.pi * j / H_SIDES
        p = centre + Vector((math.cos(a), 0, math.sin(a))) * handle_radius(s, a) + Vector((0, -min(s, 0), 0))
        verts.append(tuple(p))
        colours.append(handle_colour(p, s, a))
faces = [(k * H_SIDES + j, k * H_SIDES + (j + 1) % H_SIDES, (k + 1) * H_SIDES + (j + 1) % H_SIDES,
          (k + 1) * H_SIDES + j) for k in range(len(ss) - 1) for j in range(H_SIDES)]
faces += [tuple(range(H_SIDES)), tuple((len(ss) - 1) * H_SIDES + j for j in range(H_SIDES))]
broom.add(verts, faces, colours)

# The twigs: each from its top above the rope, squeezed in under it, then
# spreading (the outer ones most), wandering a little as twigs do, a little
# flattened (FLAT, up and down) the further they go. The middle ones longest.
FLAT = 0.6
TWIGS = 260


def bundle_at(s, a, f, top_r, end_r, tip):
    """Where a twig is at s: round the handle (a), f of the way out."""
    bound_r = 0.03 + 0.036 * f
    if s < BIND:
        r = top_r + (bound_r - top_r) * (s - TOP) / (BIND - TOP)
    elif s < BOUND:
        r = bound_r
    else:
        r = bound_r + (end_r - bound_r) * ((s - BOUND) / (tip - BOUND)) ** 0.85
    flat = 1 - (1 - FLAT) * max(0.0, (s - BOUND) / (tip - BOUND))
    centre = handle_centre(min(s, 1.25))
    return centre + Vector((math.cos(a) * r, 0, math.sin(a) * r * flat)) + Vector((0, -(s - min(s, 1.25)), 0))


for i in range(TWIGS):
    a = broom_rng.uniform(0, 2 * math.pi)
    twist = broom_rng.uniform(-0.6, 0.6)  # (so they cross each other)
    f = math.sqrt(broom_rng.random())
    top = TOP + broom_rng.uniform(-0.03, 0.07)
    tip = TIPS - 0.1 * f ** 2 + broom_rng.uniform(-0.12, 0.05)
    top_r = 0.035 + 0.04 * f
    end_r = (0.05 + 0.16 * f) * broom_rng.uniform(0.85, 1.25)
    thick = broom_rng.uniform(0.003, 0.006)
    shade = broom_rng.random()
    seed = Vector((i * 1.7, i * 0.3, 5.0))
    steps = 10
    path, radii = [], []
    for k in range(steps + 1):
        s = top + (tip - top) * k / steps
        u = max(0.0, (s - BOUND) / (tip - BOUND))
        wander = Vector((noise.noise(seed + Vector((s * 6, 0, 0))), 0, noise.noise(seed + Vector((0, s * 6, 3)))))
        p = bundle_at(s, a + twist * u, f, top_r, end_r, tip) + wander * 0.035 * u
        path.append(tuple(p))
        radii.append(thick * (1 - 0.65 * k / steps))

    def twig_colour(p, along, around, shade=shade, seed=seed):
        colour = c.mix(TWIG_DARK, TWIG, 0.15 + 0.75 * shade + 0.15 * along)
        return c.vary(colour, 0.12, seed + Vector(p) * 30)

    round_tube(broom, path, radii, twig_colour, sides=4)
    # Some fork, a twiglet splaying off, outwards.
    if f > 0.4 and broom_rng.random() < 0.45:
        k = broom_rng.randint(5, 7)
        start = Vector(path[k])
        centre = handle_centre(1.25) + Vector((0, start.y - handle_centre(1.25).y, 0))
        out_dir = Vector((start.x - centre.x, 0, (start.z - centre.z) * 0.6)).normalized()
        long_ = broom_rng.uniform(0.1, 0.25)
        ts = (0, 0.33, 0.66, 1)
        branch = [tuple(start + Vector((0, -long_ * t, 0)) + out_dir * long_ * 0.35 * t ** 0.8) for t in ts]
        round_tube(broom, branch, [radii[k] * 0.8 * (1 - 0.6 * t) for t in ts], twig_colour, sides=4)

# And inside them, so you don't see through: a dark core, as if packed with
# more twigs (streaked along).
C_SIDES = 12
cs = [TOP + 0.03 + (TIPS - 0.12 - TOP - 0.03) * k / 20 for k in range(21)]
verts, colours = [], []
for s in cs:
    for j in range(C_SIDES):
        a = 2 * math.pi * j / C_SIDES
        u = max(0.0, min(1.0, (s - TOP - 0.03) / (TIPS - 0.12 - TOP - 0.03)))
        p = bundle_at(s, a, 0.6, 0.05, 0.13, TIPS - 0.12)
        # (Pulled in a little round its middle, and tapering at its end.)
        squeeze = 0.2 * math.sin(math.pi * u) ** 4 + 0.75 * max(0.0, (u - 0.7) / 0.3) ** 1.5
        p = p.lerp(handle_centre(min(s, 1.25)) + Vector((0, -(s - min(s, 1.25)), 0)), squeeze)
        verts.append(tuple(p))
        streak = noise.noise(Vector((math.cos(a) * 6, s * 1.5, math.sin(a) * 6)))
        colours.append(c.mix(TWIG_DARK, TWIG, 0.2 + 0.25 * streak))
faces = [(k * C_SIDES + j, k * C_SIDES + (j + 1) % C_SIDES, (k + 1) * C_SIDES + (j + 1) % C_SIDES,
          (k + 1) * C_SIDES + j) for k in range(len(cs) - 1) for j in range(C_SIDES)]
faces += [tuple(range(C_SIDES)), tuple((len(cs) - 1) * C_SIDES + j for j in range(C_SIDES))]
broom.add(verts, faces, colours)

# The rope: wound round and round the twigs, pale straw, its strands twisted.
TURNS, ROPE_R = 5, 0.0095
WOUND = 0.066 + 0.006 + ROPE_R  # round the twigs, and their thickness
coil = []
for k in range(TURNS * 16 + 1):
    t = k / (TURNS * 16)
    a = 2 * math.pi * TURNS * t
    s = BIND + ROPE_R + (BOUND - BIND - 2 * ROPE_R) * t
    coil.append(tuple(handle_centre(s) + Vector((math.cos(a) * WOUND, 0, math.sin(a) * WOUND))))


def rope_colour(p, along, around):
    strand = math.sin(along * TURNS * 16 * 1.3 + around * 3)
    return c.vary(c.mix(ROPE_DARK, ROPE, 0.55 + 0.45 * strand), 0.06, Vector(p) * 40)


round_tube(broom, coil, [ROPE_R] * len(coil), rope_colour, sides=7)

# Lying on the ground: tilted so it rests on its knob and its twigs, its
# middle at the origin.
broom_object = broom.build("broom", smooth=True)
mesh = broom_object.data
points = [v.co.copy() for v in mesh.vertices]
y_hi, y_lo = max(p.y for p in points), min(p.y for p in points)
knob_end = [p for p in points if p.y > y_hi - 0.08]
twig_end = [p for p in points if p.y < y_lo + 0.35]


def lowest(group, angle):
    return min(p.y * math.sin(angle) + p.z * math.cos(angle) for p in group)


lo_angle, hi_angle = -0.4, 0.4
for _ in range(40):
    mid = (lo_angle + hi_angle) / 2
    if lowest(knob_end, mid) > lowest(twig_end, mid):
        hi_angle = mid
    else:
        lo_angle = mid
mesh.transform(Matrix.Rotation(mid, 4, "X"))
xs_ = [v.co.x for v in mesh.vertices]
ys_ = [v.co.y for v in mesh.vertices]
low = min(v.co.z for v in mesh.vertices)
mesh.transform(Matrix.Translation((-(min(xs_) + max(xs_)) / 2, -(min(ys_) + max(ys_)) / 2, -low)))
outward(broom_object)

# The lamp: as in its picture, an old brass lantern. A round foot flaring
# out under a square body, its four panes of glass crossed by wires, a
# little latch on its door; a sloping roof, and on it a round chimney with
# holes round it for the smoke, a domed cap and a knob; and its handle
# arching over it all. Inside, an oil lamp: its font, its burner, and its
# glass chimney round the wick. Its glass (`lamp-glass`) and its flame
# (`lamp-flame`, shown only once it's lit) are their own, inside it, for the
# game to make see-through and bright. Standing up, 77 cm high to the top of
# its handle (big, like the key, so you can spot it).
LAMP_SIZE = 1.4
BRASS = c.linear("#cf9f48")
BRASS_LIGHT = c.linear("#f7dc8e")
BRASS_DARK = c.linear("#7d5824")
PATINA = c.linear("#6f5b34")
SOOT = c.linear("#1d140b")
GLASS = c.linear("#f4ecd6")
lamp, lamp_glass, lamp_flame = c.Builder(), c.Builder(), c.Builder()


def brass(p, shine=0.5):
    """Mottled brass: rubbed bright in places, dull and dark in others."""
    v = Vector(p) * 40
    colour = c.mix(BRASS_DARK, BRASS_LIGHT, shine + noise.noise(v) * 0.3)
    if noise.noise(v * 0.4 + Vector((3, 8, 2))) > 0.4:
        colour = c.mix(colour, PATINA, 0.35)  # tarnished
    return c.vary(colour, 0.05, v)


def lathe(builder, profile, colour, sides=28):
    """Turned round its middle (up z): a profile of (radius, z), from the
    bottom up, a radius of 0 closing it there. colour(p, t): t along it."""
    rings, colours = [], []
    for k, (r, z) in enumerate(profile):
        t = k / (len(profile) - 1)
        ring = [(math.cos(2 * math.pi * j / sides) * r, math.sin(2 * math.pi * j / sides) * r, z)
                for j in range(1 if r == 0 else sides)]
        rings.append(ring)
        colours.append([colour(p, t) for p in ring])
    verts, cols, starts = [], [], []
    for ring, ring_colours in zip(rings, colours):
        starts.append(len(verts))
        verts += ring
        cols += ring_colours
    faces = []
    for k in range(len(rings) - 1):
        a, b = starts[k], starts[k + 1]
        if len(rings[k]) == 1:
            faces += [(a, b + (j + 1) % sides, b + j) for j in range(sides)]
        elif len(rings[k + 1]) == 1:
            faces += [(a + j, a + (j + 1) % sides, b) for j in range(sides)]
        else:
            faces += [(a + j, a + (j + 1) % sides, b + (j + 1) % sides, b + j) for j in range(sides)]
    builder.add(verts, faces, cols)


def shaded(top, bottom=0.25):
    """Brass lighter going up a turned part (catching the light above it)."""
    return lambda p, t: brass(p, bottom + (top - bottom) * t)


# The foot: a broad base, a bead, then sweeping in and up to a rim under the body.
lathe(lamp, [(0, 0), (0.122, 0), (0.125, 0.008), (0.125, 0.016)], shaded(0.35, 0.2))
lathe(lamp, [(0.125, 0.016), (0.119, 0.021), (0.113, 0.026)], shaded(0.75, 0.5))  # (its bead)
foot = [(0.113 - 0.012 * math.sin(math.pi / 2 * k / 8), 0.026 + 0.034 * (1 - math.cos(math.pi / 2 * k / 8)))
        for k in range(9)]
lathe(lamp, foot + [(0.104, 0.064), (0.106, 0.072), (0.1, 0.078), (0, 0.078)], shaded(0.7, 0.3))
# (A ring of rivets round its rim.)
for k in range(16):
    a = 2 * math.pi * (k + 0.5) / 16
    lamp.blob((math.cos(a) * 0.104, math.sin(a) * 0.104, 0.067), 0.0045, BRASS_LIGHT, subdivisions=1, lumpy=0)

# The body: square, its frame of brass bars, from the plate it stands on to
# the one under its roof.
HALF, POST = 0.086, 0.009  # half its width (to its posts' middles), and half a post's thickness
BODY_LOW, BODY_HIGH = 0.078, 0.29


def lamp_box(x0, y0, z0, x1, y1, z1, shine=0.5):
    corners = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for face in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]:
        pts = [corners[i] for i in face]
        up = sum(p[2] for p in pts) / 4 > (z0 + z1) / 2 + 1e-6
        lamp.add(pts, [(0, 1, 2, 3)], [brass(p, shine + (0.15 if up else 0)) for p in pts])


def square_frame(z0, z1, half, thick):
    """A square ring of bars, half wide round its middle, `thick` across."""
    for s in (-1, 1):
        lamp_box(-half - thick, s * half - thick, z0, half + thick, s * half + thick, z1)
        lamp_box(s * half - thick, -half + thick, z0, s * half + thick, half - thick, z1)


lamp_box(-HALF - POST, -HALF - POST, BODY_LOW, HALF + POST, HALF + POST, BODY_LOW + 0.014, 0.4)  # its floor
for sx in (-1, 1):
    for sy in (-1, 1):
        x, y = sx * HALF, sy * HALF
        lamp_box(x - POST, y - POST, BODY_LOW, x + POST, y + POST, BODY_HIGH, 0.55)  # its posts
        for z in (BODY_LOW + 0.03, BODY_HIGH - 0.03):  # riveted top and bottom
            for dx, dy in ((sx * POST, 0), (0, sy * POST)):
                lamp.blob((x + dx, y + dy, z), 0.0035, BRASS_LIGHT, subdivisions=1, lumpy=0)
square_frame(BODY_LOW + 0.014, BODY_LOW + 0.026, HALF, POST * 0.8)
square_frame(BODY_HIGH - 0.016, BODY_HIGH, HALF + 0.002, POST * 1.1)

# Its panes, set in a little from the posts' fronts, each crossed corner to
# corner by two wires (in front of it).
PANE = HALF - 0.002
WIRE = 0.0022
low, high = BODY_LOW + 0.026, BODY_HIGH - 0.016
for side in range(4):
    a = math.pi / 2 * side
    out_, along = Vector((math.cos(a), math.sin(a), 0)), Vector((-math.sin(a), math.cos(a), 0))
    pane = [out_ * PANE + along * s * (HALF - POST) + Vector((0, 0, z)) for s, z in
            ((-1, low), (1, low), (1, high), (-1, high))]
    lamp_glass.add([tuple(p) for p in pane], [(0, 1, 2, 3)], [GLASS] * 4)
    front = out_ * (PANE + POST * 0.6)
    for s in (-1, 1):
        ends = [front + along * (-s * (HALF - POST)) + Vector((0, 0, low)),
                front + along * (s * (HALF - POST)) + Vector((0, 0, high))]
        wire = [tuple(ends[0].lerp(ends[1], t / 6)) for t in range(7)]
        round_tube(lamp, wire, [WIRE] * 7, lambda p, along_, around: brass(p, 0.45), sides=5)
# The door's latch, on the front (towards -y), by its right-hand post: a
# little hinged catch, and its knob.
lamp_box(HALF - 0.03, -HALF - POST - 0.006, 0.17, HALF - POST, -HALF - POST, 0.2, 0.6)
lamp.blob((HALF - 0.032, -HALF - POST - 0.01, 0.185), 0.006, BRASS_LIGHT, subdivisions=1, lumpy=0)

# The roof: sloping up from the body on all four sides to the chimney.
ROOF_LOW, ROOF_HIGH = BODY_HIGH, 0.345
roof_low, roof_high = HALF + POST + 0.008, 0.05
for side in range(4):
    a0, a1 = math.pi / 2 * side - math.pi / 4, math.pi / 2 * side + math.pi / 4
    pts = [(math.cos(a) * r * math.sqrt(2), math.sin(a) * r * math.sqrt(2), z)
           for r, z, a in ((roof_low, ROOF_LOW, a0), (roof_low, ROOF_LOW, a1),
                           (roof_high, ROOF_HIGH, a1), (roof_high, ROOF_HIGH, a0))]
    lamp.add(pts, [(0, 1, 2, 3)], [brass(p, 0.45 + 0.25 * (p[2] - ROOF_LOW) / (ROOF_HIGH - ROOF_LOW)) for p in pts])
    lamp.add([pts[1], pts[0], (pts[0][0], pts[0][1], ROOF_LOW - 0.006), (pts[1][0], pts[1][1], ROOF_LOW - 0.006)],
             [(0, 1, 2, 3)], [brass(p, 0.3) for p in pts[:2]] * 2)  # (its edge)
# The chimney on top: a drum with a ring of holes, a rim, a domed cap and a knob.
CHIM_R = 0.044
holes = [(2 * math.pi * k / 10, 0.372) for k in range(10)]


def drum(p, t):
    """Brass, with dark holes round it (for the smoke), sooty round them."""
    a = math.atan2(p[1], p[0])
    colour = brass(p, 0.45 + 0.25 * t)
    for ha, hz in holes:
        d = math.hypot((((a - ha + math.pi) % (2 * math.pi)) - math.pi) * CHIM_R / 0.008, (p[2] - hz) / 0.009)
        colour = c.mix(colour, SOOT, max(0.0, min(1.0, 1.6 - d)))
    return colour


lathe(lamp, [(roof_high + 0.004, ROOF_HIGH - 0.004), (CHIM_R, ROOF_HIGH)], shaded(0.5, 0.4), sides=40)
lathe(lamp, [(CHIM_R, ROOF_HIGH + z / 20 * 0.055) for z in range(21)], drum, sides=60)
cap = [(CHIM_R + 0.006, 0.4), (CHIM_R + 0.008, 0.404), (CHIM_R + 0.004, 0.409)]
cap += [((CHIM_R + 0.002) * math.cos(math.pi / 2 * k / 6), 0.409 + 0.03 * math.sin(math.pi / 2 * k / 6))
        for k in range(1, 7)]
lathe(lamp, [(CHIM_R, 0.4)] + cap[:-1] + [(0.008, 0.439), (0.006, 0.444)], shaded(0.9, 0.4), sides=40)
knob = [(0.006, 0.444)] + [(0.013 * math.sin(math.pi * k / 8), 0.452 - 0.012 * math.cos(math.pi * k / 8))
                           for k in range(1, 9)]
lathe(lamp, knob[:-1] + [(0, knob[-1][1])], shaded(0.95, 0.6), sides=16)

# The handle: a brass bail, from a pivot either side of the chimney,
# hooking out, then arching up high over the knob.
PIVOT_Z = 0.372
for s in (-1, 1):
    round_tube(lamp, [(s * (CHIM_R - 0.002), 0, PIVOT_Z), (s * (CHIM_R + 0.01), 0, PIVOT_Z)], [0.011, 0.011],
               lambda p, along_, around: brass(p, 0.65), sides=12)  # (its pivots)
bail = []
for k in range(33):
    t = k / 32
    a = math.pi * (1 - t)
    # (Out from each pivot first, then up and over: wider than the chimney.)
    wide = 0.07 + 0.022 * math.sin(math.pi * t)
    x = math.cos(a) * wide
    z = PIVOT_Z + 0.006 + math.sin(a) * 0.15 + 0.02 * max(0.0, math.sin(a)) ** 0.5
    bail.append((x, 0.0, z))
bail = [(-(CHIM_R + 0.01), 0, PIVOT_Z)] + bail + [(CHIM_R + 0.01, 0, PIVOT_Z)]
round_tube(lamp, bail, [0.0055] * len(bail), lambda p, along_, around: brass(p, 0.4 + 0.3 * math.sin(around)),
           sides=8)

# Inside: the lamp's font (where its oil is), round and squat, on the floor;
# its burner, a little crown with holes round it; and its glass chimney,
# bulging round the flame, and up to the roof.
font = [(0, BODY_LOW + 0.014)] + [(0.05 + 0.008 * math.sin(math.pi * k / 8), BODY_LOW + 0.014 + 0.045 * k / 8)
                                  for k in range(9)]
lathe(lamp, font + [(0.026, BODY_LOW + 0.064), (0.024, BODY_LOW + 0.074)], shaded(0.8, 0.3))
BURNER = BODY_LOW + 0.074
lathe(lamp, [(0.024, BURNER), (0.031, BURNER + 0.004), (0.031, BURNER + 0.018), (0.027, BURNER + 0.02),
             (0.027, BURNER + 0.024)], lambda p, t: c.mix(brass(p, 0.6), SOOT, 0.5 if 0.3 < t < 0.6 else 0))
WICK = BURNER + 0.024
lathe(lamp, [(0, WICK - 0.002), (0.009, WICK - 0.002), (0.009, WICK + 0.006), (0, WICK + 0.006)],
      lambda p, t: SOOT, sides=8)
chimney = [(0.028, WICK), (0.03, WICK + 0.01)]
chimney += [(0.031 + 0.017 * math.sin(math.pi * k / 10), WICK + 0.012 + 0.08 * k / 10) for k in range(1, 11)]
chimney += [(0.024, WICK + 0.11), (0.022, BODY_HIGH - 0.02)]
lathe(lamp_glass, chimney, lambda p, t: GLASS, sides=24)

# The flame: a long teardrop, blue at its root, white-gold in its heart, and
# orange to its tip.
FLAME_LOW, FLAME_HIGH, FLAME_R = WICK + 0.004, WICK + 0.07, 0.011
flame = [(0, FLAME_LOW)]
flame += [(FLAME_R * math.sin(math.pi * k / 16) ** 0.6 * (1 - k / 16) ** 0.8 * 1.6,
           FLAME_LOW + (FLAME_HIGH - FLAME_LOW) * (k / 16) ** 1.2) for k in range(1, 16)]
flame += [(0, FLAME_HIGH)]


def flame_colour(p, t):
    if t < 0.15:
        return c.mix(c.linear("#4b6cff"), c.linear("#fff3c4"), t / 0.15)
    if t < 0.5:
        return c.mix(c.linear("#fff3c4"), c.linear("#ffd25e"), (t - 0.15) / 0.35)
    return c.mix(c.linear("#ffd25e"), c.linear("#ff8a22"), (t - 0.5) / 0.5)


lathe(lamp_flame, flame, flame_colour, sides=12)

lamp_object = lamp.build("lamp", smooth=True)
glass_object = lamp_glass.build("lamp-glass", smooth=True)
flame_object = lamp_flame.build("lamp-flame", smooth=True)
for part in (lamp_object, glass_object, flame_object):
    part.data.transform(Matrix.Scale(LAMP_SIZE, 4))
outward(lamp_object)
outward(flame_object)
glass_object.parent = flame_object.parent = lamp_object

# The rope: as in its picture, a coil of thick, golden-brown rope, its three
# strands twisted round it, wound round and round in rows and layers (a
# ring of it, with a hole in the middle); bound round the bundle in one place
# by a few turns of its other end, and its end sticking out, whipped round
# with twine and frayed at its tip. 62 cm across. (The game hangs a length
# of it, made the same way, from the deep hole's beam: rope.ts.)
ROPE_STRAND = c.linear("#c99a5a")  # on a strand
ROPE_GROOVE = c.linear("#7c5730")  # between them
ROPE_TWINE = c.linear("#8d6a3c")
ROPE_THICK = 0.03  # its radius
TWIST = 0.075  # metres along it, for a strand to go once round it
rope = c.Builder()


def roped(builder, path, radius=ROPE_THICK, strands=True, colour=None, sides=12, closed=False):
    """A length of rope along a path (points every centimetre or so): round
    it a frame carried along it (so it never flips, round a coil), and on
    that, its strands, bulging (and lighter) where they are."""
    pts = [Vector(p) for p in path]
    n = len(pts)
    tangents = [(pts[min(k + 1, n - 1)] - pts[max(k - 1, 0)]).normalized() for k in range(n)]
    if closed:
        tangents[0] = tangents[-1] = (pts[1] - pts[-2]).normalized()
    ref = Vector((0, 0, 1)) if abs(tangents[0].z) < 0.9 else Vector((1, 0, 0))
    normal = (ref - tangents[0] * ref.dot(tangents[0])).normalized()
    verts, colours, along = [], [], 0.0
    for k in range(n):
        if k:
            along += (pts[k] - pts[k - 1]).length
            normal = (normal - tangents[k] * normal.dot(tangents[k])).normalized()
        side = tangents[k].cross(normal)
        for j in range(sides):
            a = 2 * math.pi * j / sides
            crest = math.cos(3 * a - 2 * math.pi * along / TWIST) if strands else 1.0
            r = radius * (1 + 0.1 * crest)
            v = pts[k] + (normal * math.cos(a) + side * math.sin(a)) * r
            verts.append(tuple(v))
            shade = colour or c.mix(ROPE_GROOVE, ROPE_STRAND, 0.5 + 0.5 * crest)
            colours.append(c.vary(shade, 0.08, v * 30))
    rings = n - 1 if closed else n
    faces = [(k * sides + j, k * sides + (j + 1) % sides, ((k + 1) % n) * sides + (j + 1) % sides,
              ((k + 1) % n) * sides + j) for k in range(rings - (0 if closed else 1)) for j in range(sides)]
    if not closed:
        faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    builder.add(verts, faces, colours)


# Its turns, from the outside of the bottom row in: (how far out, how high),
# a row on the ground, over it, in the grooves between, another, and over
# that, a third, out again.
ROW = 2 * ROPE_THICK * 0.97
TURNS = [(0.265, 0), (0.265 - ROW, 0), (0.265 - 2 * ROW, 0), (0.265 - 1.5 * ROW, 1), (0.265 - 0.5 * ROW, 1),
         (0.265, 2), (0.265 - ROW, 2), (0.265 - 2 * ROW, 2)]
LAYER = ROPE_THICK * 1.7
STEP = 0.009  # metres between the rings round it, along it
coiled = []
for k, (r0, h0) in enumerate(TURNS):
    r1, h1 = TURNS[min(k + 1, len(TURNS) - 1)]
    steps = int(2 * math.pi * r0 / STEP)
    for i in range(steps):
        u = i / steps
        a = 2 * math.pi * (k + u)
        # (Over to the next turn in the last quarter of each one.)
        f = smooth_step(max(0.0, (u - 0.75) / 0.25)) if k < len(TURNS) - 1 else 0.0
        r = r0 + (r1 - r0) * f + 0.006 * math.sin(3 * a + k)
        z = ROPE_THICK + LAYER * (h0 + (h1 - h0) * f) + 0.004 * math.sin(5 * a + 2 * k)
        coiled.append((math.cos(a) * r, math.sin(a) * r, z))
# Its end (the first turn's start), out from the bottom row, along the way
# it was going: whipped round with twine near its tip, and frayed past that.
start, after = Vector(coiled[0]), Vector(coiled[1])
heading = (start - after).normalized()
heading = (heading + Vector((0.35, 0, 0))).normalized()  # (turning out a little)
END = 0.16
lead = [tuple(start + heading * (END * (1 - i / 16))) for i in range(16)]
roped(rope, lead + coiled)
tip = start + heading * END
for i in range(4):
    at = tip - heading * (0.025 + i * 0.012)
    ring = []
    for k in range(25):
        a = 2 * math.pi * k / 24
        side = heading.cross(Vector((0, 0, 1))).normalized()
        up = side.cross(heading)
        ring.append(tuple(at + (side * math.cos(a) + up * math.sin(a)) * ROPE_THICK * 1.12))
    roped(rope, ring, radius=0.0045, strands=False, colour=ROPE_TWINE, sides=6, closed=True)
frayed = random.Random("the rope's end")
for _ in range(16):
    a, out_ = frayed.uniform(0, 2 * math.pi), frayed.uniform(0.2, 0.9) * ROPE_THICK
    side = heading.cross(Vector((0, 0, 1))).normalized()
    up = side.cross(heading)
    root = tip - heading * 0.012 + (side * math.cos(a) + up * math.sin(a)) * out_
    spread = (side * math.cos(a) + up * math.sin(a)) * frayed.uniform(0.2, 0.6)
    reach = frayed.uniform(0.025, 0.05)
    fibre = [tuple(root + (heading + spread * t) * reach * t) for t in (0, 0.5, 1)]
    roped(rope, fibre, radius=0.0035, strands=False, colour=c.mix(ROPE_STRAND, ROPE_GROOVE, frayed.random() * 0.5),
          sides=4)
# Bound round the bundle, in one place: a few turns of its other end, round
# the rows and layers (and the rope's end tucked in under them).
BUNDLE_R = (TURNS[0][0] + TURNS[2][0]) / 2
BUNDLE_Z = ROPE_THICK + LAYER
for k in range(3):
    a = 2.3 + k * 0.075
    out_, up = Vector((math.cos(a), math.sin(a), 0)), Vector((0, 0, 1))
    middle = out_ * BUNDLE_R + up * BUNDLE_Z
    ring = [tuple(middle + out_ * math.cos(2 * math.pi * i / 40) * (ROW + 2 * ROPE_THICK)
                  + up * math.sin(2 * math.pi * i / 40) * (LAYER + 2 * ROPE_THICK)) for i in range(41)]
    roped(rope, ring, closed=True)
rope_object = rope.build("rope", smooth=True)
low = min(v.co.z for v in rope_object.data.vertices)
rope_object.data.transform(Matrix.Translation((0, 0, -low)))
outward(rope_object)

# The penny: as in its picture, a big old bronze coin, a worn king's head on
# it (its picture's colours: no one looks closely enough for more), inside
# a raised rim; plain and worn on its other side. 34 cm across, like the
# key, big enough to spot.
PENNY_R, PENNY_T = 0.17, 0.024  # its radius, and how thick it is
RIM = 0.86  # where its rim starts, of the way out
PENNY_RINGS, PENNY_SIDES = 56, 120
BRONZE = c.linear("#8c5530")
BRONZE_DARK = c.linear("#4f2c17")
picture = bpy.data.images.load(str(HERE.parent / "originals/items/penny.png"))
W, H = picture.size
pixels = np.empty(W * H * 4, dtype=np.float32)
picture.pixels.foreach_get(pixels)
pixels = pixels.reshape(H, W, 4)[::-1]  # (its top row first)
CX, CY, RX, RY = 634.5, 632.0, 570.5, 552.0  # the coin, in its picture


def face_at(u, v):
    """Its picture's colour (linear), u and v from -1 to 1 across it."""
    x = int(min(W - 1, max(0, CX + u * RX)))
    y = int(min(H - 1, max(0, CY - v * RY)))
    rgb = [p / 12.92 if p <= 0.04045 else ((p + 0.055) / 1.055) ** 2.4 for p in pixels[y, x, :3]]
    return (*rgb, 1.0)


def worn(p):
    v = Vector(p) * 60
    return c.mix(BRONZE_DARK, BRONZE, 0.6 + noise.noise(v) * 0.35 + noise.noise(v * 3) * 0.1)


penny = c.Builder()
verts, faces, colours = [], [], []
# Its face, ring by ring out from its middle (the rim higher, rounded at its edge).
verts.append((0, 0, PENNY_T))
colours.append(face_at(0, 0))
for i in range(1, PENNY_RINGS + 1):
    t = i / PENNY_RINGS
    for k in range(PENNY_SIDES):
        a = 2 * math.pi * k / PENNY_SIDES
        u, v = math.cos(a) * t, math.sin(a) * t
        colour = face_at(u * 0.985, v * 0.985)
        z = PENNY_T + (0.0055 * math.sin(math.pi * (t - RIM) / (1 - RIM)) ** 0.6 if t > RIM else 0.0)
        verts.append((u * PENNY_R, v * PENNY_R, z))
        colours.append(colour)
for k in range(PENNY_SIDES):
    faces.append((0, 1 + k, 1 + (k + 1) % PENNY_SIDES))
for i in range(PENNY_RINGS - 1):
    for k in range(PENNY_SIDES):
        a, b = 1 + i * PENNY_SIDES + k, 1 + i * PENNY_SIDES + (k + 1) % PENNY_SIDES
        faces.append((a, a + PENNY_SIDES, b + PENNY_SIDES, b))
penny.add(verts, faces, colours)
# Its edge, and its other side: plain, worn bronze.
edge = [(math.cos(2 * math.pi * k / PENNY_SIDES) * PENNY_R, math.sin(2 * math.pi * k / PENNY_SIDES) * PENNY_R)
        for k in range(PENNY_SIDES)]
top = 1 + (PENNY_RINGS - 1) * PENNY_SIDES  # (its face's outermost ring)
penny.add([(x, y, z) for x, y in edge for z in (0.0, penny.verts[top][2])],
          [(2 * k, 2 * ((k + 1) % PENNY_SIDES), 2 * ((k + 1) % PENNY_SIDES) + 1, 2 * k + 1) for k in range(PENNY_SIDES)],
          [c.mix(worn((x, y, z)), BRONZE_DARK, 0.2) for x, y in edge for z in (0.0, 1.0)])
penny.add([(0, 0, 0)] + [(x, y, 0.0) for x, y in edge],
          [(0, 1 + (k + 1) % PENNY_SIDES, 1 + k) for k in range(PENNY_SIDES)],
          [worn((0, 0, 0))] + [worn((x, y, 0)) for x, y in edge])
outward(penny.build("penny", smooth=True))

# The water: as in its picture, in a round glass flask, standing on a little
# flat base, with a short neck, a thick lip round its top, and a cork pushed
# into it. Its glass (`water-glass`) and the water in it (`water-inside`,
# half full, its surface flat) are their own, on the cork, for the game to
# make see-through. 56 cm high to the top of its cork (big, like the lamp,
# so you can spot it).
FLASK_SIZE = 1.2
FLASK_R = 0.165  # its bulb's radius
FLASK_Z = FLASK_R * math.sqrt(1 - 0.5 ** 2)  # its bulb's middle (cut flat underneath, half as wide)
NECK_R = 0.3 * FLASK_R
NECK_LOW = FLASK_Z + FLASK_R * math.sqrt(1 - 0.36 ** 2)  # where the bulb narrows to its neck
NECK_HIGH = NECK_LOW + 0.07
LIP = NECK_HIGH + 0.03  # the top of its lip
CORK_TOP = LIP + 0.07
FILL = FLASK_Z + 0.1 * FLASK_R  # its surface, a little over halfway up
WALL = 0.004  # the glass's thickness, to the water inside it
FLASK_GLASS = c.linear("#dfeef6")
WATER_DEEP = c.linear("#1f5fae")
WATER_LIGHT = c.linear("#4f9ad8")
CORK = c.linear("#b07a45")
CORK_DARK = c.linear("#6e4523")
CORK_LIGHT = c.linear("#d3a066")
flask, flask_glass, flask_water = c.Builder(), c.Builder(), c.Builder()


def bulb(r, start, end, steps):
    """Round its bulb (r out from its middle), from start to end (angles from straight down)."""
    return [(r * math.sin(start + (end - start) * k / steps), FLASK_Z - r * math.cos(start + (end - start) * k / steps))
            for k in range(steps + 1)]


def corky(p, t):
    """Cork: speckled with dark pits, lighter towards its top."""
    v = Vector(p) * 90
    colour = c.mix(CORK, CORK_LIGHT, 0.25 * t + 0.3 * noise.noise(v * 0.3))
    if noise.noise(v) > 0.35:
        colour = c.mix(colour, CORK_DARK, 0.75)
    return c.vary(colour, 0.06, v)


# Its glass: in a little under its base (pushed up, as a flask's is), out
# to its edge, round its bulb, in to its neck, up to its lip, round over it,
# and down a little way inside (where the cork hides the rest).
base = [(0, 0.012), (0.3 * FLASK_R, 0.006), (0.5 * FLASK_R - 0.006, 0.0)]
round_ = bulb(FLASK_R, math.asin(0.5), math.pi - math.asin(0.36), 28)
neck = [(NECK_R + 0.012, NECK_LOW + 0.01), (NECK_R + 0.002, NECK_LOW + 0.025), (NECK_R, NECK_LOW + 0.04),
        (NECK_R, NECK_HIGH)]
lip = [(NECK_R + 0.012 * math.sin(math.pi * k / 8), NECK_HIGH + (LIP - NECK_HIGH) * (1 - math.cos(math.pi * k / 8)) / 2)
       for k in range(1, 9)]
lip += [(NECK_R - 0.005, LIP + 0.002), (NECK_R - 0.012, LIP - 0.006), (NECK_R - 0.013, NECK_HIGH - 0.02)]
lathe(flask_glass, base + round_[1:] + neck + lip, lambda p, t: FLASK_GLASS, sides=48)

# The water: just inside its glass, from its base up to its surface, and
# across that (lighter, and rippled a little).
inside = [(0, 0.012 + WALL)] + bulb(FLASK_R - WALL, math.asin(0.5), math.acos((FLASK_Z - FILL) / (FLASK_R - WALL)), 20)
inside += [(inside[-1][0] * (1 - k / 6), FILL) for k in range(1, 7)]


def watery(p, t):
    if p[2] >= FILL - 1e-6:
        return c.vary(WATER_LIGHT, 0.12, Vector(p) * 25)
    return c.mix(WATER_DEEP, WATER_LIGHT, 0.6 * (p[2] / FILL) ** 2)


lathe(flask_water, inside, watery, sides=48)

# The cork: pushed in down its neck, standing up out of it, a little wider
# than its lip at its top, its edge rounded.
CORK_LOW = NECK_HIGH - 0.03
cork = [(0, CORK_LOW), (NECK_R - 0.016, CORK_LOW), (NECK_R - 0.014, LIP), (NECK_R + 0.002, LIP + 0.004)]
cork += [(NECK_R + 0.014 + 0.004 * k / 4, LIP + 0.004 + (CORK_TOP - LIP - 0.02) * k / 4) for k in range(1, 5)]
cork += [(NECK_R + 0.018 - 0.008 * (1 - math.cos(math.pi / 2 * k / 4)),
          CORK_TOP - 0.016 + 0.016 * math.sin(math.pi / 2 * k / 4)) for k in range(1, 5)]
cork += [(0, CORK_TOP + 0.002)]
lathe(flask, cork, corky, sides=32)

flask_object = flask.build("water", smooth=True)
flask_glass_object = flask_glass.build("water-glass", smooth=True)
flask_water_object = flask_water.build("water-inside", smooth=True)
for part in (flask_object, flask_glass_object, flask_water_object):
    part.data.transform(Matrix.Scale(FLASK_SIZE, 4))
outward(flask_object)
outward(flask_water_object)
flask_glass_object.parent = flask_water_object.parent = flask_object

# The harp: as in its picture, a little wooden harp, standing on a stepped
# plinth with four feet. Its pillar curves up at the front, carved down
# both sides with a gilded vine, to a collar and a round scrolled head; its
# neck swoops from the head, dips in the middle and rises to a curl at its
# other end, gold pins along it; and from there its soundbox slopes back
# down to the plinth, its soundboard pale and painted with leafy sprigs.
# Thirteen gold strings, from the pins down to the soundboard. Standing up,
# 98 cm high (big, like the lamp, so you can spot it).
HARP_SIZE = 1.4
HARP_WOOD = c.linear("#9a5a2c")
HARP_WOOD_DARK = c.linear("#55301a")
HARP_WOOD_LIGHT = c.linear("#cf8d4f")
BOARD = c.linear("#e2b874")
BOARD_LIGHT = c.linear("#f3d89c")
BOARD_PAINT = c.linear("#9a6235")
GOLD = c.linear("#d9a93f")
GOLD_LIGHT = c.linear("#f8e08e")
GOLD_DARK = c.linear("#8a6420")
X = Vector((1, 0, 0))
harp = c.Builder()


def harp_wood(p, shine=0.5):
    """Polished wood: its grain in streaks, rubbed lighter in places."""
    v = Vector(p) * 30
    streak = noise.noise(Vector((p[0] * 20, p[1] * 90, p[2] * 25)))
    colour = c.mix(HARP_WOOD_DARK, HARP_WOOD_LIGHT, shine + noise.noise(v) * 0.25 + streak * 0.15)
    return c.mix(c.vary(colour, 0.06, v * 2), HARP_WOOD, 0.2)


def gold(p, shine=0.6):
    """Gilding: bright, a little rubbed and darker in its hollows."""
    v = Vector(p) * 60
    return c.vary(c.mix(GOLD_DARK, GOLD_LIGHT, shine + noise.noise(v) * 0.3), 0.05, v)


def spline(points, steps):
    """A smooth path through points (y, z), `steps` between each."""
    pts = [Vector(p) for p in points]
    path = []
    for i in range(len(pts) - 1):
        p0, p1, p2, p3 = pts[max(i - 1, 0)], pts[i], pts[i + 1], pts[min(i + 2, len(pts) - 1)]
        for k in range(steps):
            t = k / steps
            path.append(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                               + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3))
    return path + [pts[-1]]


def carved(path, half_h, half_w, colour, sides=16):
    """A bar along a path (y, z), squarish with rounded corners: half_h(s)
    across it in its plane, half_w(s) in x, s how far along it (0 to 1).
    colour(p, s, up): up from -1 to 1 across it."""
    n = len(path)
    verts, colours = [], []
    for k, p in enumerate(path):
        s = k / (n - 1)
        t = (path[min(k + 1, n - 1)] - path[max(k - 1, 0)]).normalized()
        m = Vector((-t.y, t.x))
        h, w = half_h(s), half_w(s)
        for j in range(sides):
            a = 2 * math.pi * j / sides
            cx = math.copysign(abs(math.cos(a)) ** 0.5, math.cos(a))
            cn = math.copysign(abs(math.sin(a)) ** 0.5, math.sin(a))
            v = (w * cx, p.x + m.x * h * cn, p.y + m.y * h * cn)
            verts.append(v)
            colours.append(colour(v, s, cn))
    faces = [(k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
             for k in range(n - 1) for j in range(sides)]
    faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    harp.add(verts, faces, colours)


def rod(path, radius, colour, sides=6):
    """A thin round rod along a path in a plane across x (a string, a gilded
    line): colour(p)."""
    n = len(path)
    verts = []
    for k, p in enumerate(path):
        t = (Vector(path[min(k + 1, n - 1)]) - Vector(path[max(k - 1, 0)])).normalized()
        across = t.cross(X).normalized()
        verts += [tuple(Vector(p) + (across * math.cos(2 * math.pi * j / sides) + X * math.sin(2 * math.pi * j / sides))
                        * radius) for j in range(sides)]
    faces = [(k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
             for k in range(n - 1) for j in range(sides)]
    faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    harp.add(verts, faces, [colour(v) for v in verts])


def gilded_leaf(x, at, towards, length, width):
    """A little gilded leaf standing proud of a side (at x), from `at` (y, z)
    towards `towards`, pointed, ridged along its vein."""
    side, out = Vector((-towards.y, towards.x)), math.copysign(1, x)
    verts = []
    for k in range(8):
        s = k / 7
        mid = at + towards * length * s
        half = width * math.sin(math.pi * s) ** 0.7
        for dx, d in ((0.0015, half), (0.005, 0), (0.0015, -half), (-0.003, 0)):
            q = mid + side * d
            verts.append((x + out * dx, q.x, q.y))
    faces = [(k * 4 + j, k * 4 + (j + 1) % 4, (k + 1) * 4 + (j + 1) % 4, (k + 1) * 4 + j)
             for k in range(7) for j in range(4)]
    harp.add(verts, faces, [gold(v, 0.7) for v in verts])


def spiral(x, centre, r0, r1, turns, start=0.0):
    """A gilded curl on a side (at x): from r0 out round to r1 in."""
    n = int(24 * turns)
    path = []
    for k in range(n + 1):
        a = start + 2 * math.pi * turns * k / n
        r = r0 + (r1 - r0) * k / n
        path.append((x, centre[0] + math.cos(a) * r, centre[1] + math.sin(a) * r))
    rod(path, 0.0038, lambda p: gold(p, 0.65))


def harp_box(x0, y0, z0, x1, y1, z1):
    """A block of the plinth, its top lighter."""
    corners = [(x, y, z) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for face in [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]:
        pts = [corners[i] for i in face]
        up = sum(p[2] for p in pts) / 4 > (z0 + z1) / 2 + 1e-6
        harp.add(pts, [(0, 1, 2, 3)], [harp_wood(p, 0.55 if up else 0.35) for p in pts])


# The plinth: four feet, a broad block on them, and a step on that.
PLINTH = 0.075  # its top
for x0 in (-0.105, 0.06):
    for y0 in (-0.18, 0.16):
        harp_box(x0, y0, 0, x0 + 0.045, y0 + 0.05, 0.025)
harp_box(-0.105, -0.18, 0.025, 0.105, 0.21, 0.06)
harp_box(-0.088, -0.165, 0.06, 0.088, 0.195, PLINTH)

# The soundbox: sloping up from the plinth (its soundboard facing the
# pillar) to the neck's end, narrowing and shallower towards the top.
S0, S1 = Vector((-0.06, PLINTH)), Vector((0.215, 0.49))
ALONG = (S1 - S0).normalized()
BACK = Vector((ALONG.y, -ALONG.x))  # from its soundboard into it
SB_STEPS, SB_ACROSS = 140, 36


def soundboard(t):
    return S0 + (S1 - S0) * t


def box_half(t):
    return 0.06 - 0.025 * t


def box_back(t):
    return soundboard(t) + BACK * (0.1 - 0.04 * t)


def board_colour(p, u, t):
    """Pale, its grain along it, framed in dark wood, painted with a leafy
    sprig either side of its middle."""
    colour = c.mix(BOARD, BOARD_LIGHT, 0.45 + 0.35 * noise.noise(Vector((u * 9, t * 1.5, 2))))
    if abs(u) > 0.86:
        return harp_wood(p, 0.3)
    for sign in (-1, 1):
        stem = 0.48 + 0.1 * math.sin(t * 2 * math.pi * 3.5 + sign)
        if 0.12 < t < 0.92 and abs(sign * u - stem) < 0.035:
            colour = c.mix(colour, BOARD_PAINT, 0.8)
        for k in range(7):
            tk = 0.16 + 0.11 * k + 0.03 * sign
            lean = 1 if k % 2 else -1
            uk = sign * (0.48 + 0.1 * math.sin(tk * 2 * math.pi * 3.5 + sign) + lean * 0.14)
            if ((u - uk) / 0.1) ** 2 + ((t - tk - 0.012) / 0.018) ** 2 < 1:
                colour = c.mix(colour, BOARD_PAINT, 0.8)
    return c.vary(colour, 0.05, Vector(p) * 40)


ts = [k / SB_STEPS for k in range(SB_STEPS + 1)]
us = [-1 + 2 * j / SB_ACROSS for j in range(SB_ACROSS + 1)]
verts, colours = [], []
for t in ts:
    f = soundboard(t)
    for u in us:
        p = (u * box_half(t), f.x, f.y)
        verts.append(p)
        colours.append(board_colour(p, u, t))
cols = len(us)
harp.add(verts, [(k * cols + j, k * cols + j + 1, (k + 1) * cols + j + 1, (k + 1) * cols + j)
                 for k in range(SB_STEPS) for j in range(SB_ACROSS)], colours)
for sx in (-1, 1):  # its sides
    verts = [(sx * box_half(t), q.x, q.y) for t in ts for q in (soundboard(t), box_back(t))]
    harp.add(verts, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(SB_STEPS)],
             [harp_wood(v, 0.35) for v in verts])
verts = [(sx * box_half(t), box_back(t).x, box_back(t).y) for t in ts for sx in (-1, 1)]  # its back
harp.add(verts, [(2 * k, 2 * k + 1, 2 * k + 3, 2 * k + 2) for k in range(SB_STEPS)],
         [harp_wood(v, 0.3) for v in verts])
for t in (0, 1):  # and its ends
    f, b = soundboard(t), box_back(t)
    pts = [(-box_half(t), f.x, f.y), (box_half(t), f.x, f.y), (box_half(t), b.x, b.y), (-box_half(t), b.x, b.y)]
    harp.add(pts, [(0, 1, 2, 3)], [harp_wood(p, 0.4) for p in pts])

# The pillar: from the plinth, curving out and up to its collar under the head.
pillar = spline([(-0.095, 0.05), (-0.145, 0.2), (-0.18, 0.37), (-0.192, 0.5), (-0.19, 0.58)], 8)
P_HALF_H, P_HALF_W = 0.03, 0.026
carved(pillar, lambda s: P_HALF_H, lambda s: P_HALF_W, lambda p, s, up: harp_wood(p, 0.42 + 0.1 * up))
collar = [p for p in pillar if 0.535 < p.y < 0.57]
carved(collar, lambda s: P_HALF_H + 0.007, lambda s: P_HALF_W + 0.006, lambda p, s, up: harp_wood(p, 0.55))
# Its vine, gilded, down both sides: a wavy stem, a leaf at each wave.
for sx in (-1, 1):
    x = sx * (P_HALF_W + 0.002)
    stem, leaves = [], []
    n = len(pillar)
    for k in range(int(0.08 * n), int(0.82 * n)):
        s = k / (n - 1)
        t = (pillar[min(k + 1, n - 1)] - pillar[k - 1]).normalized()
        m = Vector((-t.y, t.x))
        wave = math.sin(2 * math.pi * 3.5 * s)
        q = pillar[k] + m * P_HALF_H * 0.45 * wave
        stem.append((x, q.x, q.y))
        if abs(wave) > 0.99 and (not leaves or k - leaves[-1][0] > 2):
            leaves.append((k, q, (t + m * math.copysign(1.2, wave)).normalized()))
    rod(stem, 0.003, lambda p: gold(p, 0.6))
    for _, q, towards in leaves:
        gilded_leaf(x, q, towards, 0.04, 0.011)

# The head: round, on top of the pillar, a gilded curl on either side.
HEAD, HEAD_R, HEAD_HALF = Vector((-0.212, 0.636)), 0.062, 0.027
head = c.Builder()
lathe(head, [(0, -HEAD_HALF), (HEAD_R - 0.01, -HEAD_HALF), (HEAD_R - 0.003, -HEAD_HALF + 0.003),
             (HEAD_R, -HEAD_HALF + 0.01), (HEAD_R, HEAD_HALF - 0.01), (HEAD_R - 0.003, HEAD_HALF - 0.003),
             (HEAD_R - 0.01, HEAD_HALF), (0, HEAD_HALF)], lambda p, t: (0, 0, 0, 1), sides=32)
head_verts = [(z, HEAD.x + x, HEAD.y + y) for x, y, z in head.verts]
harp.add(head_verts, head.faces, [harp_wood(v, 0.45 + 4 * (v[2] - HEAD.y)) for v in head_verts])
for sx in (-1, 1):
    spiral(sx * (HEAD_HALF + 0.001), HEAD, HEAD_R - 0.012, 0.012, 1.6, start=-0.5 * math.pi)
    gilded_leaf(sx * (HEAD_HALF + 0.001), HEAD + Vector((0.0, -0.005)), Vector((0.3, 1)).normalized(), 0.03, 0.009)

# The neck: from the head, dipping in its middle and rising to a curl at its
# end, then turning down into the top of the soundbox (and on into it, so
# they meet).
neck = spline([(-0.2, 0.64), (-0.12, 0.645), (-0.04, 0.62), (0.03, 0.583), (0.09, 0.567), (0.15, 0.583),
               (0.205, 0.612), (0.245, 0.605), (0.264, 0.565), (0.252, 0.505), (0.24, 0.455)], 8)
N_HALF_W = 0.022


def neck_half_h(s):
    return 0.027 + 0.01 * max(0.0, (s - 0.72) / 0.28)


carved(neck, neck_half_h, lambda s: N_HALF_W, lambda p, s, up: harp_wood(p, 0.42 + 0.12 * up))
for sx in (-1, 1):
    spiral(sx * (N_HALF_W + 0.001), Vector((0.236, 0.582)), 0.024, 0.007, 1.4, start=0.4 * math.pi)

# The strings, gold, from the neck down to the soundboard; a pin over each
# on top of the neck, another on its side, and a little eyelet where each
# goes into the soundboard.
STRINGS = 13


def neck_at(y):
    """The neck's middle (z), and how far along it, over y."""
    for k in range(len(neck) - 1):
        a, b = neck[k], neck[k + 1]
        if a.x <= y <= b.x:
            f = (y - a.x) / (b.x - a.x)
            return a.y + (b.y - a.y) * f, (k + f) / (len(neck) - 1)
    raise ValueError(y)


for i in range(STRINGS):
    y = -0.035 + 0.235 * i / (STRINGS - 1)
    t = (y - S0.x) / (S1.x - S0.x)
    low = soundboard(t).y
    top, s = neck_at(y)
    rod([(0, y, low - 0.004), (0, y, top)], 0.0022, lambda p: gold(p, 0.75), sides=5)
    harp.blob((0, y, low + 0.002), 0.005, GOLD, subdivisions=1, lumpy=0)
    harp.blob((0, y, top + neck_half_h(s) + 0.006), 0.0085, GOLD, subdivisions=1, lumpy=0)
    harp.blob((N_HALF_W + 0.003, y + 0.006, top + 0.008), 0.0065, GOLD, subdivisions=1, lumpy=0)

# Its middle (along it) at the origin.
ys = [v[1] for v in harp.verts]
mid = (min(ys) + max(ys)) / 2
harp.verts = [(x, y - mid, z) for x, y, z in harp.verts]
harp_object = harp.build("harp", smooth=True)
harp_object.data.transform(Matrix.Scale(HARP_SIZE, 4))
outward(harp_object)

# The cake: as in its picture, a round cake covered in swirled cream, a slice
# cut out of it; in the cut, three layers of golden sponge with cherries in
# jam between them, under a little cream. Round the edge of its top, piped
# rosettes of cream, a shiny cherry on its stalk on each; and flakes of
# chocolate scattered all over it, top and sides. Built 23 cm across, then made
# twice that (CAKE_SIZE), so you can spot it from across a cave.
CAKE_SIZE = 2.0
CAKE_R, CAKE_TALL = 0.115, 0.1  # its radius and height, as built
CUT = (-0.42, 0.42)  # the slice cut out: radians round, from and to
CREAM = c.linear("#f4e4bc")
CREAM_SHADE = c.linear("#dcc392")
SPONGE = c.linear("#e3b45c")
SPONGE_DARK = c.linear("#c08a3a")
JAM = c.linear("#8a1222")
CHERRY = c.linear("#c41420")
CHERRY_DARK = c.linear("#62060e")
CHERRY_SHINE = c.linear("#ff9c8a")
CHERRY_STALK = c.linear("#7d7a2c")
CHERRY_STALK_TIP = c.linear("#5a3a1a")
CHOCOLATE = c.linear("#5c2f17")
CHOCOLATE_LIGHT = c.linear("#86502a")
cake = c.Builder()
cake_rng = random.Random(11)


def creamy(p, shade=0.0):
    """Cream: swirled, a little shadow in the hollows of its swirls."""
    v = Vector(p) * 60
    return c.vary(c.mix(CREAM, CREAM_SHADE, shade + 0.25 * max(0.0, noise.noise(v))), 0.03, v)


def cream_out(a, z):
    """How far out its cream is, round at a and up at z: swirled by the knife."""
    v = Vector((math.cos(a) * 3, math.sin(a) * 3, z * 25))
    return 0.004 * noise.noise(v) + 0.0025 * math.sin(7 * a + 40 * z + 2 * noise.noise(v * 0.5))


# Its cream, round its side and over its top: a profile (out, up) from its
# foot up over its rounded edge to its middle, turned round all but the cut.
CAKE_PROFILE = [(CAKE_R, 0.0), (CAKE_R, 0.25 * CAKE_TALL), (CAKE_R, 0.5 * CAKE_TALL), (CAKE_R, 0.75 * CAKE_TALL),
                (CAKE_R, CAKE_TALL - 0.012), (CAKE_R - 0.004, CAKE_TALL - 0.004), (CAKE_R - 0.012, CAKE_TALL),
                (CAKE_R * 0.66, CAKE_TALL), (CAKE_R * 0.33, CAKE_TALL), (0.0, CAKE_TALL)]
CAKE_AROUND = 64
arc = [CUT[1] + (2 * math.pi - (CUT[1] - CUT[0])) * j / CAKE_AROUND for j in range(CAKE_AROUND + 1)]
verts, colours = [], []
for a in arc:
    for k, (r, z) in enumerate(CAKE_PROFILE):
        out_by = cream_out(a, z) * (r / CAKE_R) if 0 < k < len(CAKE_PROFILE) - 1 else 0.0
        p = (math.cos(a) * (r + out_by), math.sin(a) * (r + out_by), z + (out_by * 0.5 if k > 5 else 0.0))
        verts.append(p)
        colours.append(creamy(p, 0.35 if k == 0 else 0.0))
n = len(CAKE_PROFILE)
faces = [(j * n + k, (j + 1) * n + k, (j + 1) * n + k + 1, j * n + k + 1) for j in range(CAKE_AROUND) for k in range(n - 1)]
cake.add(verts, faces, colours)
# (Its underside.)
cake.add([(0, 0, 0)] + [(math.cos(a) * CAKE_R, math.sin(a) * CAKE_R, 0) for a in arc],
         [(0, j + 2, j + 1) for j in range(CAKE_AROUND)], [CREAM_SHADE] * (CAKE_AROUND + 2))

def cherry_skin(p, d, colour):
    """Shiny: deep red, darker underneath, with a bright spot where the light catches it."""
    colour = c.mix(CHERRY, CHERRY_DARK, max(0.0, -d.z) * 0.7)
    shine = max(0.0, d.dot(Vector((-0.4, -0.3, 0.87))))
    return c.mix(colour, CHERRY_SHINE, shine ** 12)


# The cut: each face of it in layers, from the bottom up, sponge, cream,
# cherries in jam, sponge, cream, jam, sponge, and the cream on top; and the
# cream round its outside, a thin rim.
LAYERS = [(0.0, 0.24, SPONGE), (0.24, 0.27, CREAM), (0.27, 0.37, JAM), (0.37, 0.58, SPONGE), (0.58, 0.61, CREAM),
          (0.61, 0.71, JAM), (0.71, 0.92, SPONGE), (0.92, 1.0, CREAM)]
RIM = 0.007  # metres of cream round its outside, as built


def layer_colour(colour, p):
    v = Vector(p) * 220
    if colour is SPONGE:
        crumb = noise.noise(v) + 0.5 * noise.noise(v * 2.3)
        return c.vary(c.mix(SPONGE, SPONGE_DARK, max(0.0, crumb) * 0.9), 0.08, v)  # (crumbly: holes in it)
    if colour is JAM:
        return c.vary(c.mix(JAM, CHERRY, 0.3 + 0.3 * noise.noise(v * 0.3)), 0.06, v)
    return creamy(p)


for side, a in ((1, CUT[0]), (-1, CUT[1])):
    out_ = Vector((math.cos(a), math.sin(a), 0))
    facing = Vector((math.sin(a), -math.cos(a), 0)) * side  # (out of the cut face)
    for z0, z1, colour in LAYERS:
        for r0, r1, colour_ in ((0.0, CAKE_R - RIM, colour), (CAKE_R - RIM, CAKE_R, CREAM)):
            # (The top corner rounded, as the cream is.)
            top_r1 = r1 - (0.012 if z1 == 1.0 and r1 == CAKE_R else 0.0)
            quad = [out_ * r0 + Vector((0, 0, z0 * CAKE_TALL)), out_ * r1 + Vector((0, 0, z0 * CAKE_TALL)),
                    out_ * top_r1 + Vector((0, 0, z1 * CAKE_TALL)), out_ * r0 + Vector((0, 0, z1 * CAKE_TALL))]
            # (Each layer a grid of quads, so its colour can vary: the sponge's crumb finest.)
            steps, rows = (24, 6) if colour_ is SPONGE else (12, 1) if colour_ is JAM else (2, 1)
            verts = [tuple(quad[0].lerp(quad[1], s / steps).lerp(quad[3].lerp(quad[2], s / steps), m / rows))
                     for s in range(steps + 1) for m in range(rows + 1)]
            faces = [(s * (rows + 1) + m, (s + 1) * (rows + 1) + m, (s + 1) * (rows + 1) + m + 1, s * (rows + 1) + m + 1)
                     for s in range(steps) for m in range(rows)]
            if side < 0:
                faces = [f[::-1] for f in faces]
            cake.add(verts, faces, [layer_colour(colour_, p) for p in verts])
    # The cherries in its jam, halfway into the cut.
    for z0, z1, colour in LAYERS:
        if colour is not JAM:
            continue
        for k in range(9):
            r = 0.008 + (CAKE_R - RIM - 0.014) * (k + cake_rng.uniform(0.2, 0.8)) / 9
            z = (z0 + z1) / 2 * CAKE_TALL + cake_rng.uniform(-0.0015, 0.0015)
            cake.blob(tuple(out_ * r + Vector((0, 0, z)) - facing * 0.0015), 0.0045, CHERRY, lumpy=0.1,
                      subdivisions=2, seed=k, shade=cherry_skin, lit=False)


def piped(builder, x, y, z, size):
    """A rosette of piped cream: twisted ridges, round, up to a curl on top."""
    sides, rows = 20, 7
    profile = [(1.0, 0.0), (1.05, 0.25), (0.95, 0.5), (0.75, 0.75), (0.5, 1.0), (0.25, 1.2), (0.0, 1.3)]
    verts, colours = [], []
    for r, h in profile:
        for j in range(sides):
            a = 2 * math.pi * j / sides
            ridge = 1 + 0.24 * math.cos(6 * a + 5 * h) * min(1.0, r * 2)
            p = (x + math.cos(a) * r * ridge * size, y + math.sin(a) * r * ridge * size, z + h * size * 0.9)
            verts.append(p)
            colours.append(creamy(p, 0.45 * (1 - ridge + 0.24) / 0.48))
    faces = [(k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
             for k in range(rows - 1) for j in range(sides)]
    builder.add(verts, faces, colours)


# The rosettes, each with its cherry and stalk, round the top, between the cut's sides.
ROSETTES = 9
ROSETTE_R = CAKE_R - 0.024  # how far out they stand
ROSETTE_SIZE = 0.021
CHERRY_R = 0.0115
rosettes = []
for k in range(ROSETTES):
    a = CUT[1] + 0.3 + (2 * math.pi - (CUT[1] - CUT[0]) - 0.6) * k / (ROSETTES - 1)
    x, y = math.cos(a) * ROSETTE_R, math.sin(a) * ROSETTE_R
    rosettes.append((x, y))
    piped(cake, x, y, CAKE_TALL - 0.003, ROSETTE_SIZE)
    top = Vector((x, y, CAKE_TALL + ROSETTE_SIZE * 0.9 + CHERRY_R * 0.75))
    cake.blob(tuple(top), CHERRY_R, CHERRY, squash=0.92, lumpy=0.04, seed=k, shade=cherry_skin, lit=False,
              subdivisions=3)
    # (Its stalk, from deep in its dimple, curving up and over to one side.)
    lean = cake_rng.uniform(0, 2 * math.pi)
    stalk_path = [top + Vector((math.cos(lean) * 0.014 * t * t, math.sin(lean) * 0.014 * t * t, CHERRY_R * 0.6 + 0.034 * t))
                  for t in (s / 6 for s in range(7))]
    round_tube(cake, [tuple(p) for p in stalk_path], [0.0016 - 0.0004 * s / 6 for s in range(7)],
               lambda p, t, a_: c.mix(CHERRY_STALK, CHERRY_STALK_TIP, smooth_step((t - 0.8) / 0.2)), sides=5)


def flake(at, along, up, size):
    """A flake of chocolate, flat against what it's on: a thin, ragged-edged sliver."""
    across = up.cross(along).normalized()
    long_, wide = size * cake_rng.uniform(0.8, 1.4), size * cake_rng.uniform(0.35, 0.6)
    thick = 0.0012
    corners = [along * long_ + across * wide * 0.2, across * wide, -along * long_ * 0.8 + across * wide * 0.3,
               -along * long_ * 0.6 - across * wide, along * long_ * 0.5 - across * wide * 0.7]
    low = [tuple(at + q) for q in corners]
    high = [tuple(at + q + up * thick) for q in corners]
    m = len(corners)
    faces = [tuple(range(m))[::-1], tuple(range(m, 2 * m))] + [(j, (j + 1) % m, m + (j + 1) % m, m + j) for j in range(m)]
    colour = c.mix(CHOCOLATE, CHOCOLATE_LIGHT, cake_rng.random())
    cake.add(low + high, faces, [c.mix(colour, (0, 0, 0, 1), 0.25)] * m + [colour] * m)


def in_cut(a):
    """Whether round at a is in the slice cut out (or right by it)."""
    return math.cos(a - (CUT[0] + CUT[1]) / 2) > math.cos((CUT[1] - CUT[0]) / 2 + 0.08)


# Flakes over its top (not on the rosettes), and round its side.
for _ in range(110):
    a, r = cake_rng.uniform(0, 2 * math.pi), CAKE_R * math.sqrt(cake_rng.uniform(0.02, 0.85))
    x, y = math.cos(a) * r, math.sin(a) * r
    if in_cut(a) or any(math.hypot(x - rx, y - ry) < ROSETTE_SIZE * 1.15 for rx, ry in rosettes):
        continue
    spin = cake_rng.uniform(0, 2 * math.pi)
    tilt = Vector((cake_rng.uniform(-0.3, 0.3), cake_rng.uniform(-0.3, 0.3), 1)).normalized()
    along = Vector((math.cos(spin), math.sin(spin), 0))
    along = (along - tilt * along.dot(tilt)).normalized()
    flake(Vector((x, y, CAKE_TALL + 0.0015)), along, tilt, 0.0055)
for _ in range(170):
    a, z = cake_rng.uniform(0, 2 * math.pi), cake_rng.uniform(0.06, 0.86) * CAKE_TALL
    if in_cut(a):
        continue
    out_ = Vector((math.cos(a), math.sin(a), 0))
    spin = cake_rng.uniform(0, math.pi)
    along = (Vector((-out_.y, out_.x, 0)) * math.cos(spin) + Vector((0, 0, 1)) * math.sin(spin)).normalized()
    flake(out_ * (CAKE_R + cream_out(a, z) + 0.0012) + Vector((0, 0, z)), along, out_, 0.005)

cake_object = cake.build("cake", smooth=True)
cake_object.data.transform(Matrix.Scale(CAKE_SIZE, 4))
outward(cake_object)

# The gold: as in its picture, three gold bars stacked, two side by side and
# one on top, across the gap between them, all lying the same way. Each is
# wider at its foot than its top, its edges worn round, its faces hammered
# and dented, with a few fine cracks; deep gold, lighter where it's rubbed.
# Built 24 cm long, then made two and a half times that (GOLD_SIZE), so it
# shines out from across the treasure room.
GOLD_SIZE = 2.5
# (A bar's length, width and height; how much narrower its top is, on each
# side; and how round its top edges are worn.)
GOLD_BAR = (0.24, 0.092, 0.066, 0.014, 0.012)
BAR_FOOT = 0.004  # its bottom edges, a little round
BAR_GAP = 0.008  # between the two side by side
BULLION = c.linear("#b87810")
BULLION_LIGHT = c.linear("#e9ae35")
BULLION_DARK = c.linear("#5e3406")
gold_bars = c.Builder()


def rounded_ring(half_x, half_y, corner, z):
    """A rounded rectangle at height z, always the same number of points
    (round its corners, and along its sides between them)."""
    corner = max(0.0, min(corner, half_x, half_y))
    pts = []
    corners = [(half_x, half_y, 0.0), (-half_x, half_y, 0.5), (-half_x, -half_y, 1.0), (half_x, -half_y, 1.5)]
    for k, (cx, cy, turn) in enumerate(corners):
        ox = cx - math.copysign(corner, cx)
        oy = cy - math.copysign(corner, cy)
        for j in range(5):
            a = (turn + 0.5 * j / 4) * math.pi
            pts.append((ox + corner * math.cos(a), oy + corner * math.sin(a), z))
        # (Then on to the next corner: across its ends, or along its long sides.)
        nx, ny, _ = corners[(k + 1) % 4]
        ex = nx - math.copysign(corner, nx)
        ey = ny - math.copysign(corner, ny)
        a1 = (turn + 0.5) * math.pi
        start = (ox + corner * math.cos(a1), oy + corner * math.sin(a1))
        end = (ex + corner * math.cos(a1), ey + corner * math.sin(a1))
        steps = 22 if k % 2 else 7
        for j in range(1, steps):
            t = j / steps
            pts.append((start[0] + (end[0] - start[0]) * t, start[1] + (end[1] - start[1]) * t, z))
    return pts


def bullion(p, seed):
    """Gold: deep, lighter where it's rubbed, dark in its dents and cracks."""
    v = Vector(p) * 40 + Vector((seed * 5.3, seed * 2.9, 0))
    colour = c.mix(BULLION, BULLION_LIGHT, 0.35 + noise.noise(v * 0.6) * 0.5)
    pit = max(0.0, noise.noise(v * 1.4) - 0.5) * 1.2
    # (A few fine cracks: thin lines where a noise crosses zero, only in places.)
    line = abs(noise.noise(v * 0.9 + Vector((7, 1, 3))))
    some = noise.noise(v * 0.25 + Vector((2, 9, 4))) > 0.15
    crack = (1 - line / 0.05) if some and line < 0.05 else 0.0
    return c.vary(c.mix(colour, BULLION_DARK, min(0.8, 0.6 * pit + crack)), 0.06, v * 3)


def metal_bar(builder, shape, colour, x, y, z, yaw, seed):
    """One bar (gold or silver), lying along y, its foot at height z."""
    long_, wide, tall, taper, worn = shape
    hx, hy = wide / 2, long_ / 2
    # Its outline from the bottom up, as (how far in, how high): in from its
    # middle underneath, round its foot, up its sloping sides, round over its
    # top edges, and in across its top.
    profile = [(min(hx, hy) - 0.002, 0.0), (BAR_FOOT * 3, 0.0)]
    profile += [(BAR_FOOT * (1 - math.sin(a)), BAR_FOOT * (1 - math.cos(a)))
                for a in (math.pi / 2 * k / 3 for k in range(4))]
    side_top = tall - worn
    profile += [(taper * zz / tall, zz) for zz in (side_top * k / 8 for k in range(1, 9))]
    d0 = taper * side_top / tall
    profile += [(d0 + worn * (1 - math.cos(a)), side_top + worn * math.sin(a))
                for a in (math.pi / 2 * k / 6 for k in range(1, 7))]
    inner = hx - (d0 + worn)
    profile += [(d0 + worn + inner * k / 7, tall) for k in range(1, 7)]
    profile += [(hx - 0.0008, tall)]
    turn = Matrix.Rotation(yaw, 4, "Z")
    verts, colours, rings = [], [], []
    for d, zz in profile:
        ring = rounded_ring(hx - d, hy - d, max(0.0, 0.016 - d * 0.5), zz)
        rings.append(len(verts))
        for p in ring:
            # (Hammered: its faces a little uneven.)
            dent = 0.0012 * noise.noise(Vector(p) * 30 + Vector((seed * 3.1, 0, 0)))
            q = Vector(p) * (1 + dent / max(0.03, Vector(p).length))
            q = turn @ q + Vector((x, y, z))
            verts.append(tuple(q))
            colours.append(colour(p, seed))
    n = len(verts) // len(profile)
    faces = []
    for r in range(len(profile) - 1):
        a, b = rings[r], rings[r + 1]
        faces += [(a + k, a + (k + 1) % n, b + (k + 1) % n, b + k) for k in range(n)]
    # (Closing its middle, under and on top.)
    for r, up in ((0, False), (len(profile) - 1, True)):
        mid = len(verts)
        verts.append(tuple(turn @ Vector((0, 0, profile[r][1])) + Vector((x, y, z))))
        colours.append(colour((0, 0, profile[r][1]), seed))
        a = rings[r]
        faces += [(a + k, a + (k + 1) % n, mid) if not up else (a + (k + 1) % n, a + k, mid) for k in range(n)]
    builder.add(verts, faces, colours)


# Two side by side, and one on top, resting on both (a little back, and
# turned a touch, as if put down by hand).
side = GOLD_BAR[1] / 2 + BAR_GAP / 2
metal_bar(gold_bars, GOLD_BAR, bullion, -side, 0.006, 0.0, 0.02, 1)
metal_bar(gold_bars, GOLD_BAR, bullion, side, -0.008, 0.0, -0.015, 2)
metal_bar(gold_bars, GOLD_BAR, bullion, 0.0, 0.018, GOLD_BAR[2] - 0.0015, 0.035, 3)
gold_object = gold_bars.build("gold", smooth=True)
gold_object.data.transform(Matrix.Scale(GOLD_SIZE, 4))
outward(gold_object)

# The silver: as in its picture, one big bar of silver, chunkier than the
# gold's, its sides sloping more steeply in to its top, its edges worn
# round; cool grey, warm and creamy where it catches the light, scratched
# bright across its top and pocked with little dents. Built 26 cm long, then
# made a little over twice that (SILVER_SIZE), so you can spot it.
SILVER_SIZE = 2.3
SILVER_BAR = (0.26, 0.11, 0.08, 0.02, 0.011)
SILVER = c.linear("#80848e")
SILVER_LIGHT = c.linear("#d9d2c0")
SILVER_DARK = c.linear("#3e3f46")
SILVER_WARM = c.linear("#b9a47c")


def silvery(p, seed):
    """Silver: cool grey, warm and light in streaks, bright in its scratches,
    dark in its dents."""
    v = Vector(p) * 40 + Vector((seed * 5.3, seed * 2.9, 0))
    colour = c.mix(SILVER, SILVER_LIGHT, 0.2 + noise.noise(v * 0.5) * 0.6)
    colour = c.mix(colour, SILVER_WARM, max(0.0, noise.noise(v * 0.35 + Vector((4, 4, 1)))) * 0.6)
    pit = max(0.0, noise.noise(v * 1.6) - 0.5) * 1.4
    # (Scratches: thin bright lines where a noise crosses zero, mostly on top.)
    line = abs(noise.noise(Vector((p[0] * 30, p[1] * 70, p[2] * 30)) + Vector((7, 1, 3))))
    scratch = (1 - line / 0.04) if line < 0.04 and p[2] > SILVER_BAR[2] * 0.8 else 0.0
    colour = c.mix(c.mix(colour, SILVER_DARK, min(0.8, pit)), SILVER_LIGHT, scratch * 0.8)
    return c.vary(colour, 0.05, v * 3)


silver_bar = c.Builder()
metal_bar(silver_bar, SILVER_BAR, silvery, 0.0, 0.0, 0.0, 0.0, 4)
silver_object = silver_bar.build("silver", smooth=True)
silver_object.data.transform(Matrix.Scale(SILVER_SIZE, 4))
outward(silver_object)

# The ring: as in its picture, a gold ring, its band thin underneath and
# swelling, wider and thicker, up its shoulders to its setting; scrolls of
# gold raised along its shoulders, a big curl either side of the setting; a
# gold cup (a collet) on top, holding an oval purple stone in four claws,
# each ending in a little drop. It lies on its side, as a ring does, resting
# on the edge of its band and the rim of its setting (wider than the band),
# so it tips a little, its stone turned up a touch. (Made standing, its
# stone on top, then laid down.) Built at a ring's size, 2.3 cm across, then made sixteen times that (RING_SIZE), a
# little bigger than the key. The stone (`ring-gem`) is faceted, and dressed in the game.
RING_SIZE = 16.0
RING_IN = 0.0088  # its inside, round the finger
RING_GOLD = c.linear("#c8902a")
RING_GOLD_LIGHT = c.linear("#f2c866")
RING_GOLD_DARK = c.linear("#6a4210")
AMETHYST = [c.linear(h) for h in ("#3b1468", "#7234c0", "#9a5ae0", "#d9a8ff")]  # under it, its crown, higher, its table
GEM_LONG, GEM_WIDE = 0.0056, 0.0046  # half the stone's length (along the band) and width
ring_band = c.Builder()
ring_gem = c.Builder()


def ring_shape(a):
    """How wide (half) and thick the band is, a round from its top: more up its shoulders."""
    s = max(0.0, math.cos(a)) ** 2
    return 0.0018 + 0.0014 * s, 0.0014 + 0.0011 * s


RING_MID = RING_IN + ring_shape(math.pi)[1]  # (its middle, so its foot is at z = 0)


def round_ring(a):
    """Out from the ring's middle, a round from its top (towards +y)."""
    return Vector((0, math.sin(a), math.cos(a)))


def on_band(a, xf, lift=0.0):
    """A point on the band's outside, a round from its top and xf across it
    (-1 to 1), lifted off it; and which way is out there."""
    half, thick = ring_shape(a)
    r = RING_IN + thick / 2 + thick / 2 * max(0.0, 1 - abs(xf) ** 4) ** 0.25 + lift
    return Vector((half * xf, 0, RING_MID)) + round_ring(a) * r, round_ring(a)


def ring_gold(p, t=0.0, a=0.0):
    """Gold: warm, lighter where it's rubbed and on top, dark in its hollows."""
    v = Vector(p) * 900
    colour = c.mix(RING_GOLD, RING_GOLD_LIGHT, 0.3 + 0.4 * noise.noise(v * 0.4) + 0.25 * (p[2] / (2 * RING_MID)))
    return c.vary(colour, 0.06, v)


# The band, ring by ring round it, each its cross-section: flat inside,
# rounded outside; its shoulders' faces a little darker (the scrolls stand
# out against them).
AROUND, ACROSS = 120, 16
verts, colours = [], []
for k in range(AROUND):
    a = 2 * math.pi * k / AROUND
    half, thick = ring_shape(a)
    for j in range(ACROSS):
        f = 2 * math.pi * j / ACROSS
        cf, sf = math.cos(f), math.sin(f)
        r = RING_IN + thick / 2 + thick / 2 * math.copysign(abs(cf) ** (0.5 if cf > 0 else 0.2), cf)
        p = Vector((half * math.copysign(abs(sf) ** 0.5, sf), 0, RING_MID)) + round_ring(a) * r
        verts.append(tuple(p))
        shoulder = max(0.0, math.cos(a)) * max(0.0, cf) * (1 - abs(sf))
        colours.append(c.mix(ring_gold(p), RING_GOLD_DARK, 0.35 * shoulder))
faces = [(k * ACROSS + j, k * ACROSS + (j + 1) % ACROSS, ((k + 1) % AROUND) * ACROSS + (j + 1) % ACROSS,
          ((k + 1) % AROUND) * ACROSS + j) for k in range(AROUND) for j in range(ACROSS)]
ring_band.add(verts, faces, colours)


def scroll(points, radii, sides=6):
    """A raised gold scroll along the band: points (a round from its top, xf
    across it), radii at each; round, sitting on it, a drop at its end."""
    rings_, verts, colours = [], [], []
    path = [on_band(a, xf) for a, xf in points]
    for k, (p, out_) in enumerate(path):
        p = p + out_ * radii[k] * 0.5
        tangent = (path[min(k + 1, len(path) - 1)][0] - path[max(k - 1, 0)][0]).normalized()
        across = tangent.cross(out_).normalized()
        up = across.cross(tangent).normalized()
        for j in range(sides):
            f = 2 * math.pi * j / sides
            v = p + (across * math.cos(f) + up * math.sin(f)) * radii[k]
            verts.append(tuple(v))
            colours.append(c.mix(ring_gold(v), RING_GOLD_LIGHT, 0.3 * max(0.0, math.sin(f))))
    n = len(path)
    faces = [(k * sides + j, k * sides + (j + 1) % sides, (k + 1) * sides + (j + 1) % sides, (k + 1) * sides + j)
             for k in range(n - 1) for j in range(sides)]
    faces += [tuple(range(sides))[::-1], tuple((n - 1) * sides + j for j in range(sides))]
    ring_band.add(verts, faces, colours)
    end, out_ = path[-1]
    ring_band.blob(tuple(end + out_ * radii[-1]), radii[-1] * 1.6, RING_GOLD_LIGHT, lumpy=0.0, subdivisions=1)


def curl(a0, xf0, size, turns, way, step):
    """A spiral, in to its middle: from a round a0 and xf0 across, size (metres) out."""
    _, thick = ring_shape(a0)
    half, _ = ring_shape(a0)
    points, n = [], 14
    for k in range(n + 1):
        t = k / n
        f = way * 2 * math.pi * turns * t + step
        r = size * (1 - 0.8 * t)
        points.append((a0 + r * math.cos(f) / (RING_IN + thick), max(-0.95, min(0.95, xf0 + r * math.sin(f) / half))))
    return points


for side_ in (-1, 1):
    # A big curl beside the setting, either side.
    points = curl(side_ * 0.34, 0.0, 0.0020, 1.15, side_, 0.0)
    scroll(points, [0.0008 - 0.0003 * k / (len(points) - 1) for k in range(len(points))])
    # A stem down the shoulder, swaying across it, a curl off each sway.
    vine = [(side_ * (0.5 + 0.6 * k / 16), 0.3 * math.sin(k / 16 * 2 * math.pi)) for k in range(17)]
    scroll(vine, [0.0006 - 0.00025 * k / 16 for k in range(17)])
    for n, (s_, xf) in enumerate(((0.66, 0.45), (0.94, -0.45))):
        points = curl(side_ * s_, xf, 0.0013 - 0.0003 * n, 1.0, side_ * (1 if xf > 0 else -1), math.pi)
        scroll(points, [0.00058 - 0.00022 * k / (len(points) - 1) for k in range(len(points))])

# The collet: an oval gold cup on top, from down in the band, flaring out to
# a rim round the stone; and its four claws, up over the stone's edge.
SEAT = RING_MID + RING_IN + ring_shape(0)[1] - 0.0004  # (its foot, in the top of the band)


def collet_at(s, h, f):
    return (GEM_WIDE * s * math.cos(f), GEM_LONG * s * math.sin(f), SEAT + h)


cup = [(0.55, -0.0004), (0.8, 0.0008), (1.0, 0.0022), (1.1, 0.0034), (1.12, 0.0039), (1.02, 0.0041), (0.9, 0.0036),
       (0.0, 0.0036)]
SIDES = 32
verts, colours = [], []
for s, h in cup:
    for j in range(SIDES):
        p = collet_at(s, h, 2 * math.pi * j / SIDES)
        verts.append(p)
        colours.append(ring_gold(p))
faces = [(k * SIDES + j, k * SIDES + (j + 1) % SIDES, (k + 1) * SIDES + (j + 1) % SIDES, (k + 1) * SIDES + j)
         for k in range(len(cup) - 1) for j in range(SIDES)]
faces.append(tuple(range(SIDES))[::-1])
ring_band.add(verts, faces, colours)
for n in range(4):
    f = math.pi / 4 + math.pi / 2 * n
    claw = [collet_at(s, h, f) for s, h in ((1.08, 0.0026), (1.06, 0.0040), (0.99, 0.0046), (0.9, 0.0051))]
    round_tube(ring_band, claw, [0.0006, 0.00055, 0.0005, 0.00045], lambda p, t, a: ring_gold(p), sides=7)
    ring_band.blob(claw[-1], 0.00072, RING_GOLD_LIGHT, squash=0.8, lumpy=0.0, subdivisions=2)

# The stone: an oval, cut in facets: from its girdle (just over the rim) up
# in two rows of facets to its flat table, and down under it to a point (in
# the cup). Each facet its own purple, lighter higher up.
GIRDLE = 0.0040
gem_rings = [(0.97, GIRDLE, 0.0), (0.82, GIRDLE + 0.0016, 0.5), (0.58, GIRDLE + 0.0028, 1.0)]
pavilion = [(0.97, GIRDLE, 0.0), (0.55, GIRDLE - 0.0016, 0.5)]
GEM_SIDES = 16


def gem_ring(s, h, turn):
    return [Vector(collet_at(s, h, 2 * math.pi * (j + turn) / GEM_SIDES)) for j in range(GEM_SIDES)]


def facet(pts, colour, seed):
    ring_gem.add([tuple(p) for p in pts], [tuple(range(len(pts)))], [c.vary(colour, 0.2, Vector((seed, len(pts), 1.0)))] * len(pts))


for rows, colours_ in ((gem_rings, (AMETHYST[1], AMETHYST[2])), (pavilion, (AMETHYST[0],))):
    for r_, ((s0, h0, t0), (s1, h1, t1)) in enumerate(zip(rows, rows[1:])):
        lo, hi = gem_ring(s0, h0, t0), gem_ring(s1, h1, t1)
        if t1 < t0:  # (the table's ring, half a facet on from the one under it)
            hi = hi[1:] + hi[:1]
        for j in range(GEM_SIDES):
            j1 = (j + 1) % GEM_SIDES
            facet([lo[j], lo[j1], hi[j]], colours_[r_], j * 2 + r_ * 40)
            facet([hi[j], lo[j1], hi[j1]], colours_[r_], j * 2 + 1 + r_ * 40)
table = gem_ring(*gem_rings[-1])
facet(table, AMETHYST[3], 99)
under = gem_ring(*pavilion[-1])
point = Vector(collet_at(0, GIRDLE - 0.0034, 0))
for j in range(GEM_SIDES):
    facet([under[(j + 1) % GEM_SIDES], under[j], point], AMETHYST[0], 200 + j)

ring_object = ring_band.build("ring", smooth=True)
ring_gem_object = ring_gem.build("ring-gem", smooth=False)


def lying_ring(turn):
    """Its points laid over by turn (radians, round y: a quarter turn lays it flat)."""
    return [Matrix.Rotation(turn, 3, "Y") @ v.co for part in (ring_object, ring_gem_object) for v in part.data.vertices]


# Laid down: turned until it rests on both sides of its middle (the band's
# edge, and its setting's rim), as low on one as on the other.
def rocking(turn):
    pts = lying_ring(turn)
    mid = sum(p.x for p in pts) / len(pts)
    return abs(min(p.z for p in pts if p.x > mid) - min(p.z for p in pts if p.x < mid))


turn = min((math.pi / 2 - math.radians(d / 4) for d in range(0, 160)), key=rocking)
pts = lying_ring(turn)
low, across = min(p.z for p in pts), (min(p.x for p in pts) + max(p.x for p in pts)) / 2
for part in (ring_object, ring_gem_object):
    part.data.transform(Matrix.Translation((-across, 0, -low)) @ Matrix.Rotation(turn, 4, "Y"))
    part.data.transform(Matrix.Scale(RING_SIZE, 4))
outward(ring_object)
gem_points = ring_gem_object.data.vertices
out_from(ring_gem_object, sum((v.co for v in gem_points), Vector()) / len(gem_points))
ring_gem_object.parent = ring_object

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2.5, -3.5, 2.5), (0, 0, 0), (-0.7, 0.5, -0.45), lens=35)
    c.preview(preview.replace(".png", "-penny.png"), (0.0, -0.25, 0.45), (0, 0, 0), (-0.7, 0.5, -0.45), lens=50)
    # (And the cake, close up, from its cut side; the others moved out of the way.)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name != "cake" and o.parent is None:
            o.location.x += 50
    c.preview(preview.replace(".png", "-cake.png"), (0.75, -0.35, 0.45), (0, 0, 0.1), (-0.7, 0.5, -0.45), lens=50)
