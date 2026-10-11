# The objects you find and carry, one per object, named by its id in
# data/world.json. Each lies as it would on the ground, its middle at the
# origin and its underside at z = 0, along y (the game turns it as it lands).
#
# The ladder and the key so far; the rest are to come (PLAN-V3.md).

import math
import sys
from pathlib import Path

from mathutils import Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

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
ladder.build("ladder", smooth=False)

# The key: a big old one (half a metre, so you can spot it in the grass),
# rusty bronze as in its picture: a curly bow (two loops and a little crown),
# a round shaft with collars, and a chunky bit with notches.
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
key.build("key", smooth=False)

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2.5, -3.5, 2.5), (0, 0, 0), (-0.7, 0.5, -0.45), lens=35)
