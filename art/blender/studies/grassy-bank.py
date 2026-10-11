# A study: the grassy bank on its own, as the look to aim for when the grey
# land gets its details. Not part of the game.
#
#   blender --background --python art/blender/studies/grassy-bank.py -- out.glb --preview=out.png
#
# The grassy bank, where the adventure starts: a crossroads of paths around a
# low grassy mound, as in art/originals/rooms/grassy-bank.png. Leafy trees to
# the north-west, firs to the east, open meadow to the south, the old stone
# wall away to the west along the long path, and the mountain to the north.
#
import math
import random
import sys
from pathlib import Path

from mathutils import Vector, noise

sys.path.append(str(Path(__file__).parents[1]))
import common as c  # noqa: E402

random.seed(20)
out, preview = c.args()
c.clear()

SIZE = 100  # the walkable ground runs from -SIZE to SIZE metres
STEP = 1.25
MOUND = Vector((-5, 3))
MOUND_RADII = (9, 6.5)
CROSSROADS = (2, -6)

# The four paths, from the crossroads out (smoothed below).
PATHS = {
    "south": [CROSSROADS, (1.5, -16), (0, -30), (0, -60), (0, -130)],
    "west": [CROSSROADS, (-4, -8.5), (-11, -7), (-16, -3), (-24, 1), (-40, 2), (-56, 2), (-130, 2)],
    "north": [CROSSROADS, (4.5, 0), (5, 8), (3.5, 16), (2, 30), (1, 60), (1, 130)],
    "east": [CROSSROADS, (9, -4.5), (18, -2), (30, -1), (60, 0), (130, 0)],
}
PATH_WIDTH = 1.4  # half-width, in metres

# The old stone wall, away to the west, running north and south.
WALL_X = -60
WALL_FROM, WALL_TO = -45, 75

GRASS = c.linear("#6f9a34")
GRASS_SUN = c.linear("#a4bb4a")
GRASS_DEEP = c.linear("#4d7a2c")
DIRT = c.linear("#c69057")
DIRT_DARK = c.linear("#9a6a3e")
ROCK = c.linear("#8b8d80")
MOSS = c.linear("#6f8a3a")
LEAVES = c.linear("#5f8a2c")
LEAVES_SUN = c.linear("#9bb53e")
FIR = c.linear("#2e5634")
BARK = c.linear("#5b4433")
STONE = c.linear("#9a978a")


def chaikin(points, rounds=3):
    """Rounds the corners of a polyline."""
    for _ in range(rounds):
        out = [points[0]]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            out += [(ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25), (ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75)]
        out.append(points[-1])
        points = out
    return points


SEGMENTS = []
for line in PATHS.values():
    pts = chaikin(line)
    SEGMENTS += list(zip(pts, pts[1:]))


def path_distance(x, y):
    best = 1e9
    for (ax, ay), (bx, by) in SEGMENTS:
        if min(ax, bx) - 4 > x or max(ax, bx) + 4 < x or min(ay, by) - 4 > y or max(ay, by) + 4 < y:
            continue
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def mound_distance(x, y):
    """0 at the mound's middle, 1 at its foot."""
    return math.hypot((x - MOUND.x) / MOUND_RADII[0], (y - MOUND.y) / MOUND_RADII[1])


def height(x, y):
    h = 0.45 * noise.noise(Vector((x / 28, y / 28, 0.3))) + 0.12 * noise.noise(Vector((x / 7, y / 7, 1.7)))
    d = mound_distance(x, y)
    if d < 1.35:
        h += 3.0 * (math.cos(min(d, 1.35) / 1.35 * math.pi) + 1) / 2
        h += 0.15 * noise.noise(Vector((x / 2.5, y / 2.5, 4.0))) * (1.35 - d)
    # The land rises a little towards the edges, closing the place in.
    r = math.hypot(x, y)
    if r > 60:
        h += (r - 60) * 0.045
    return h


# The ground.
n = int(2 * SIZE / STEP) + 1
verts, colours, faces = [], [], []
for j in range(n):
    for i in range(n):
        x, y = -SIZE + i * STEP, -SIZE + j * STEP
        z = height(x, y)
        verts.append((x, y, z))
        grass = c.mix(GRASS, GRASS_SUN, 0.5 + 0.9 * noise.noise(Vector((x / 14, y / 14, 7.0))))
        grass = c.mix(grass, GRASS_DEEP, max(0.0, noise.noise(Vector((x / 9, y / 9, 3.0)))) * 0.8)
        if mound_distance(x, y) < 1.1:
            grass = c.mix(grass, GRASS_DEEP, 0.25)
        p = path_distance(x, y)
        if p < PATH_WIDTH + 1.2:
            # Worn grass along the paths, under and beside the path strips.
            grass = c.mix(c.mix(grass, DIRT_DARK, 0.45), grass, max(0.0, p - PATH_WIDTH) / 1.2)
        colours.append(c.vary(grass, 0.12, Vector((x / 3, y / 3, 5.0))))
for j in range(n - 1):
    for i in range(n - 1):
        a = j * n + i
        faces.append((a, a + 1, a + n + 1, a + n))
c.mesh_object("ground", verts, faces, colours)

# The paths: strips of earth laid on the ground, a little ragged at the edges.
strips = c.Builder()
for k, line in enumerate(PATHS.values()):
    pts = chaikin(line, 4)
    samples = []
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        length = math.hypot(bx - ax, by - ay)
        for t in range(max(1, int(length / 0.7))):
            f = t / max(1, int(length / 0.7))
            samples.append((ax + (bx - ax) * f, ay + (by - ay) * f))
    samples = [(x, y) for x, y in samples if max(abs(x), abs(y)) < SIZE - 1]
    lift = 0.05 + 0.01 * k  # so crossing paths don't flicker
    verts, colours, faces = [], [], []
    for i, (x, y) in enumerate(samples):
        nx, ny = samples[min(i + 1, len(samples) - 1)]
        px, py = samples[max(i - 1, 0)]
        tx, ty = nx - px, ny - py
        d = math.hypot(tx, ty) or 1
        ox, oy = -ty / d, tx / d
        left = PATH_WIDTH * (1 + 0.22 * noise.noise(Vector((x / 3, y / 3, 11.0 + k))))
        right = PATH_WIDTH * (1 + 0.22 * noise.noise(Vector((x / 3, y / 3, 13.0 + k))))
        for side, colour_at in ((-left, 0.0), (-left * 0.45, 1.0), (right * 0.45, 1.0), (right, 0.0)):
            vx, vy = x + ox * side, y + oy * side
            verts.append((vx, vy, height(vx, vy) + lift))
            dirt = c.mix(DIRT, DIRT_DARK, 0.5 + 0.8 * noise.noise(Vector((vx * 0.9, vy * 0.9, 9.0))))
            colours.append(c.vary(c.mix(c.mix(dirt, DIRT_DARK, 0.4), dirt, colour_at), 0.1, Vector((vx, vy, 2.0))))
        if i:
            a, b = (i - 1) * 4, i * 4
            faces += [(a + j, a + j + 1, b + j + 1, b + j) for j in range(3)]
    strips.add(verts, faces, colours)
strips.build("paths")

# Beyond the ground: a ring of forest tops and hills, seen through the haze,
# with gaps where the paths lead away.
OUTER, OUTER_STEP = 340, 10
m = int(2 * OUTER / OUTER_STEP) + 1
verts, colours, faces, index = [], [], [], {}
for j in range(m):
    for i in range(m):
        x, y = -OUTER + i * OUTER_STEP, -OUTER + j * OUTER_STEP
        z = height(x, y) if max(abs(x), abs(y)) <= SIZE else (math.hypot(x, y) - 60) * 0.045
        if max(abs(x), abs(y)) > SIZE:
            gap = min(abs(x), abs(y)) < 8  # the four paths run out along the axes
            canopy = 0.0 if gap else min(1.0, (max(abs(x), abs(y)) - SIZE) / 12)
            z += canopy * (11 + 4 * noise.noise(Vector((x / 15, y / 15, 2.0))))
            col = c.mix(GRASS, FIR, canopy)
        else:
            col = GRASS
        index[(i, j)] = len(verts)
        verts.append((x, y, z))
        colours.append(c.vary(col, 0.2, Vector((x / 20, y / 20, 6.0))))
for j in range(m - 1):
    for i in range(m - 1):
        xs = [-OUTER + (i + di) * OUTER_STEP for di in (0, 1)]
        ys = [-OUTER + (j + dj) * OUTER_STEP for dj in (0, 1)]
        if all(abs(x) <= SIZE for x in xs) and all(abs(y) <= SIZE for y in ys):
            continue
        faces.append((index[(i, j)], index[(i + 1, j)], index[(i + 1, j + 1)], index[(i, j + 1)]))
c.mesh_object("far-forest", verts, faces, colours)

# The mountain, far to the north, and low hills to the west.
far = c.Builder()
far.blob((60, 620, -90), 330, c.linear("#8d86a6"), squash=0.85, lumpy=0.18, seed=3, subdivisions=4,
         shade=lambda p, d, col: c.mix(col, c.linear("#e9e2ee"), max(0.0, (p.z - 150) / 90) * 0.6))
for k, (x, y, r) in enumerate([(-300, 120, 90), (-320, -40, 70), (-260, 260, 110), (260, 300, 120), (320, 60, 80)]):
    far.blob((x, y, -r * 0.55), r, c.linear("#6f8a6a"), squash=0.6, lumpy=0.2, seed=10 + k, subdivisions=3)
far.build("far-mountain")


def ground_z(x, y):
    return height(x, y)


def free(x, y, path_gap, mound_gap=1.15):
    return path_distance(x, y) > path_gap and mound_distance(x, y) > mound_gap


# Trees: leafy ones north-west, firs east. A scattering with a little spacing.
trunks, tops, firs = c.Builder(), c.Builder(), c.Builder()
placed = []


def spaced(x, y, gap):
    return all(math.hypot(x - px, y - py) > gap for px, py in placed)


def leafy(x, y, size):
    z = ground_z(x, y) - 0.2
    h = 3.2 * size
    trunks.cylinder((x, y, z), (x + random.uniform(-0.3, 0.3), y, z + h), 0.32 * size, 0.18 * size, BARK)
    for k in range(random.randint(3, 5)):
        a = random.uniform(0, 2 * math.pi)
        r = random.uniform(0.6, 1.6) * size
        top = (x + math.cos(a) * r, y + math.sin(a) * r, z + h + random.uniform(0.4, 2.2) * size)
        tops.blob(top, random.uniform(1.7, 2.6) * size, LEAVES, squash=0.8, lumpy=0.3, seed=random.random() * 100,
                  shade=lambda p, d, col: c.mix(col, LEAVES_SUN, max(0.0, d.z * 0.6 - d.x * 0.3)))
    c.collider(f"col-tree-{len(placed)}", x, y, 0.45 * size)
    placed.append((x, y))


def fir(x, y, size):
    z = ground_z(x, y) - 0.2
    h = random.uniform(9, 14) * size
    trunks.cylinder((x, y, z), (x, y, z + h * 0.3), 0.3 * size, 0.2 * size, BARK)
    layers = 6
    for k in range(layers):
        t = k / layers
        firs.cone((x, y, z + h * (0.18 + 0.72 * t)), h * 0.28, (3.0 - 2.4 * t) * size, FIR,
                  seed=random.random() * 6)
    c.collider(f"col-tree-{len(placed)}", x, y, 0.4 * size)
    placed.append((x, y))


for _ in range(4000):
    x, y = random.uniform(-SIZE + 4, SIZE - 4), random.uniform(-SIZE + 4, SIZE - 4)
    r = math.hypot(x, y)
    east = x > 8 and y > -14 or x > 14
    north_west = x < 2 and y > 9 or (x < -14 and y > -3)
    # Woods close in towards the edges everywhere, thinner in the southern meadow.
    edge = r > 55
    meadow = y < -10 and x < 14
    want = 0.0
    if east:
        want = 0.55
    elif north_west:
        want = 0.5
    elif edge:
        want = 0.25 if meadow else 0.45
    if x < WALL_X + 4:
        want = 0.0  # the far side of the wall is another place
    if random.random() > want or not free(x, y, 4.0):
        continue
    if abs(x - WALL_X) < 4:
        continue
    if east and spaced(x, y, 3.2):
        fir(x, y, random.uniform(0.8, 1.2))
    elif not east and spaced(x, y, 5.0):
        leafy(x, y, random.uniform(0.9, 1.3))
    if len(placed) > 330:
        break

trunks.build("trees-trunks")
tops.build("trees-leaves")
firs.build("trees-firs", smooth=False)

# Rocks round the foot of the mound, and a few in the grass.
rocks = c.Builder()
moss_top = lambda p, d, col: c.mix(col, MOSS, max(0.0, d.z) * 0.8)  # noqa: E731
for k in range(14):
    a = math.radians(150 + k * 13 + random.uniform(-4, 4))
    x = MOUND.x + math.cos(a) * MOUND_RADII[0] * 0.95
    y = MOUND.y + math.sin(a) * MOUND_RADII[1] * 0.95
    if path_distance(x, y) < PATH_WIDTH + 0.8:
        continue
    size = random.uniform(0.5, 0.9)
    rocks.blob((x, y, ground_z(x, y) + size * 0.25), size, ROCK, squash=0.6, lumpy=0.2, seed=k, shade=moss_top)
    c.collider(f"col-rock-{k}", x, y, size * 0.9)
for k in range(30):
    x, y = random.uniform(-50, 50), random.uniform(-50, 50)
    if not free(x, y, 2.5, 1.3):
        continue
    size = random.uniform(0.3, 0.8)
    rocks.blob((x, y, ground_z(x, y) + size * 0.2), size, ROCK, squash=0.55, lumpy=0.25, seed=50 + k, shade=moss_top)
    if size > 0.55:
        c.collider(f"col-rock-{50 + k}", x, y, size * 0.9)
rocks.build("rocks")

# Bushes along the paths and round the mound, and flowers in the grass.
bushes, flowers = c.Builder(), c.Builder()
for k in range(260):
    x, y = random.uniform(-45, 45), random.uniform(-45, 45)
    p = path_distance(x, y)
    if p < PATH_WIDTH + 1.2 or mound_distance(x, y) < 0.9:
        continue
    if p > 6 and random.random() < 0.7:
        continue
    size = random.uniform(0.6, 1.3)
    bushes.blob((x, y, ground_z(x, y) + size * 0.2), size, c.mix(LEAVES, GRASS_DEEP, random.random()),
                squash=0.7, lumpy=0.35, seed=200 + k, subdivisions=1)
PETALS = [c.linear(h) for h in ("#b07ad6", "#f4f0e6", "#f2cf46", "#d68ad0")]
for k in range(900):
    x, y = random.uniform(-40, 40), random.uniform(-40, 40)
    if path_distance(x, y) < PATH_WIDTH + 0.2:
        continue
    on_mound = mound_distance(x, y) < 1.1
    if not on_mound and random.random() < 0.55:
        continue
    colour = random.choice(PETALS)
    z = ground_z(x, y)
    if on_mound and random.random() < 0.35:
        # A foxglove: a little spire of purple flowers.
        for s in range(4):
            flowers.blob((x, y, z + 0.25 + s * 0.16), 0.09 - s * 0.012, PETALS[0], seed=k + s, subdivisions=0, lumpy=0)
    else:
        flowers.blob((x, y, z + 0.12), 0.07, colour, seed=k, subdivisions=0, lumpy=0)
bushes.build("bushes")
flowers.build("flowers", smooth=False)

# The old stone wall, with blocks along its top.
wall = c.Builder()
y = WALL_FROM
while y < WALL_TO:
    length = random.uniform(1.6, 2.4)
    z = ground_z(WALL_X, y + length / 2) - 0.4
    h = 4.0 + random.uniform(-0.15, 0.15)
    x0, x1, y0, y1 = WALL_X - 0.5, WALL_X + 0.5, y, y + length
    box = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z + h), (x1, y0, z + h), (x1, y1, z + h), (x0, y1, z + h)]
    shade = [c.vary(STONE, 0.15, Vector((y, k, 0))) for k in range(8)]
    wall.add(box, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], shade)
    if random.random() < 0.6:
        wall.blob((WALL_X + 0.4, y + length / 2, z + h * 0.7), 0.6, MOSS, squash=1.4, lumpy=0.4, seed=y, subdivisions=1)
    y += length
for k, y in enumerate(range(WALL_FROM, WALL_TO, 4)):
    z = ground_z(WALL_X, y) - 0.4 + 4.0
    box = [(WALL_X - 0.6, y, z), (WALL_X + 0.6, y, z), (WALL_X + 0.6, y + 1.4, z), (WALL_X - 0.6, y + 1.4, z),
           (WALL_X - 0.6, y, z + 0.6), (WALL_X + 0.6, y, z + 0.6), (WALL_X + 0.6, y + 1.4, z + 0.6), (WALL_X - 0.6, y + 1.4, z + 0.6)]
    wall.add(box, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)],
             [c.vary(STONE, 0.15, Vector((y, k, 1))) for k in range(8)])
wall.build("wall", smooth=False)
box = c.collider("col-box-wall", WALL_X, (WALL_FROM + WALL_TO) / 2, 1)
box.scale = (0.7, (WALL_TO - WALL_FROM) / 2, 1)

# Where you start: on the south path, looking north at the crossroads and the
# mound, as in the painting.
start = c.collider("start", 2, -15, 1)

if out:
    c.export(out)
    print(f"Exported {out}")
if preview:
    c.preview(preview, (2, -24, 7), (-1, 6, 1.5), (-0.7, 0.5, -0.45))
