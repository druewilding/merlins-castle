# The objects you find and carry, one per object, named by its id in
# data/world.json. Each lies as it would on the ground, its middle at the
# origin and its underside at z = 0, along y (the game turns it as it lands).
#
# The ladder, the plank, the key, the axe, the apple and the emerald so far;
# the rest are to come (PLAN-V3.md).

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


def outward(obj):
    """Every face facing out (the game's glow round what you point at grows
    out along them)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
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
# facet its own shade of green, lighter on top; 30 cm long (big, like the
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
EM_COLOURS = [c.linear(h) for h in ("#0f5c2e", "#167a3c", "#2aa85a", "#3cc46e")]  # the pavilion, girdle, crown and step
for ring_, (lo, hi) in enumerate(zip(rings, rings[1:])):
    for k in range(8):
        pts = [lo[k], lo[(k + 1) % 8], hi[(k + 1) % 8], hi[k]]
        emerald.add(pts, [(0, 1, 2, 3)], [c.vary(EM_COLOURS[ring_], 0.18, Vector((k, ring_, 1.0)))] * 4)
emerald.add(rings[0][::-1], [tuple(range(8))], [c.linear("#0b4a24")] * 8)
emerald.add(rings[-1], [tuple(range(8))], [c.linear("#34c26c")] * 8)
outward(emerald.build("emerald", smooth=False))

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2.5, -3.5, 2.5), (0, 0, 0), (-0.7, 0.5, -0.45), lens=35)
