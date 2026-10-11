# The objects you find and carry, one per object, named by its id in
# data/world.json. Each lies as it would on the ground, its middle at the
# origin and its underside at z = 0, along y (the game turns it as it lands).
#
# The ladder and the key so far; the rest are to come (PLAN-V3.md).

import math
import sys
from pathlib import Path

from mathutils import Vector

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
# in brass. A ring to hold it by, a shaft, and its bit with teeth.
BRASS = c.linear("#c9a03a")
key = c.Builder()
ring, thick = 0.075, 0.022
sides = 10
for k in range(sides):
    a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
    x0, y0 = math.cos(a0) * ring, -0.17 + math.sin(a0) * ring
    x1, y1 = math.cos(a1) * ring, -0.17 + math.sin(a1) * ring
    # Each piece of the ring, a little box from one point round it to the next.
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    half = math.dist((x0, y0), (x1, y1)) / 2 + 0.006
    ux, uy = (x1 - x0) / (2 * half), (y1 - y0) / (2 * half)
    vx, vy = -uy * thick / 2, ux * thick / 2
    pts = [(cx - ux * half + vx, cy - uy * half + vy), (cx + ux * half + vx, cy + uy * half + vy),
           (cx + ux * half - vx, cy + uy * half - vy), (cx - ux * half - vx, cy - uy * half - vy)]
    verts = [(x, y, z) for z in (0, thick) for x, y in pts]
    faces = [(0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)]
    for face in faces:
        f = [verts[i] for i in face]
        key.add(f, [(0, 1, 2, 3)], [c.vary(BRASS, 0.12, Vector(p) * 9) for p in f])
box(key, -0.014, -0.17 + ring - 0.01, 0, 0.014, 0.25, thick, BRASS)  # the shaft
box(key, 0.014, 0.16, 0, 0.075, 0.25, thick, BRASS)  # the bit
box(key, 0.075, 0.17, 0, 0.095, 0.195, thick, BRASS)  # and its teeth
box(key, 0.075, 0.215, 0, 0.095, 0.24, thick, BRASS)
key.build("key", smooth=False)

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2.5, -3.5, 2.5), (0, 0, 0), (-0.7, 0.5, -0.45), lens=35)
