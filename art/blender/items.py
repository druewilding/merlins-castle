# The objects you find and carry, one per object, named by its id in
# data/world.json. Each lies as it would on the ground, its middle at the
# origin and its underside at z = 0, along y (the game turns it as it lands).
#
# The ladder, the key and the axe so far; the rest are to come (PLAN-V3.md).

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

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2.5, -3.5, 2.5), (0, 0, 0), (-0.7, 0.5, -0.45), lens=35)
