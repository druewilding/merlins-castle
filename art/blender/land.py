# The whole land in grey boxes: every place at its spot from layout.json,
# joined by paths, with the river and its bridge, the old stone wall and its
# gate, the mountain with the maze on top, and the castle in its moat.
#
# Forest is the barrier: trees grow everywhere except at the places, along the
# paths, on the meadow, the mountain top and the castle grounds, so you can
# only go where the original lets you.
#
# Writes land.glb (what you see), land.json (what's solid, and how high the
# ground is) and land.bin (the ground's heights).

import json
import math
import random
import struct
import sys
from pathlib import Path

from mathutils import Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

random.seed(40)
out, preview = c.args()
c.clear()

layout = json.loads((HERE / "layout.json").read_text())
world = json.loads((HERE.parents[1] / "data/world.json").read_text())
S = layout["spacing"]
OX, OY = layout["origin"]


def at(col_row):
    col, row = col_row
    return ((col - OX) * S, (OY - row) * S)


P = {place: at(cr) for place, cr in layout["places"].items()}
KIND = {place: kind for kind, places in layout["kinds"].items() if kind != "_" for place in places}
# Only the mist above ground: getting lost underground comes with the caves.
LOST = {k: at(v) for k, v in layout["lost"].items() if k != "_" and KIND.get(k.split(" ")[0]) != "cave"}
DEATHS = {k: at(v) for k, v in layout["deaths"].items() if k != "_"}

X0, X1, Y0, Y1 = -200, 200, -290, 210
STEP = 2.0

GRASS = c.linear("#77a03a")
FOREST_FLOOR = c.linear("#3f5f2a")
DIRT = c.linear("#b88754")
ROCK = c.linear("#8a8478")
RIVERBED = c.linear("#55655c")
FLAGS = c.linear("#a39d90")
STONE = c.linear("#9a978a")
TREE = c.linear("#2f5a32")
WATER = c.linear("#3d7fa8")
GREY = c.linear("#b9b4a8")
ROOF = c.linear("#6d6a78")
GOLD = c.linear("#e8b84a")
LEAVES = c.linear("#c46f2c")


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def chaikin(points, rounds=3):
    for _ in range(rounds):
        out = [points[0]]
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            out += [(ax * 0.75 + bx * 0.25, ay * 0.75 + by * 0.25), (ax * 0.25 + bx * 0.75, ay * 0.25 + by * 0.75)]
        out.append(points[-1])
        points = out
    return points


class Lines:
    """Polylines, with a quick nearest-distance lookup."""

    CELL = 20

    def __init__(self):
        self.cells = {}

    def add(self, points):
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            seg = (ax, ay, bx, by)
            for cx in range(int(math.floor((min(ax, bx) - 12) / self.CELL)), int(math.floor((max(ax, bx) + 12) / self.CELL)) + 1):
                for cy in range(int(math.floor((min(ay, by) - 12) / self.CELL)), int(math.floor((max(ay, by) + 12) / self.CELL)) + 1):
                    self.cells.setdefault((cx, cy), []).append(seg)

    def distance(self, x, y):
        best = 1e9
        for ax, ay, bx, by in self.cells.get((int(math.floor(x / self.CELL)), int(math.floor(y / self.CELL))), ()):
            dx, dy = bx - ax, by - ay
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy or 1)))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return best


# ---------------------------------------------------------------- the river

RIVER = chaikin([(-215, -40), (-150, -41), (-120, -40), (-100, -36), (-82, -24), (-64, -25), (-44, -46),
                 (-20, -60), (20, -60), (60, -61), (94, -60)])
river = Lines()
river.add(RIVER)
BRIDGE = P["old-wall"][0], -40  # where the path south from the old wall crosses

# ---------------------------------------------------------------- the paths

# Exits that aren't walked along the land: across the river by plank, the
# tunnels, and everything underground.
NOT_A_PATH = {
    ("deep-river", "river-south-bank"),
    ("old-wall", "cave-entrance"),
    ("dragon-cave", "giant"),
    ("dragon-cave", "dark-tunnels"),
}
SHAPES = {
    # The slide from the deep river down the mossy bank into the glade.
    ("deep-river", "evergreen-glade"): [P["deep-river"], (22, -32), (34, -14), P["evergreen-glade"]],
}

paths = []
done = set()
for place, room in world["rooms"].items():
    if place not in P:
        continue
    for direction, exit in room["exits"].items():
        to = exit.get("to")
        if not to or to == place or to not in P:
            continue
        pair = tuple(sorted((place, to)))
        if pair in done or pair in {tuple(sorted(p)) for p in NOT_A_PATH}:
            continue
        if KIND.get(place) == "cave" and KIND.get(to) == "cave":
            continue  # underground
        if KIND.get(place) == "cave" and place != "dragon-cave" or KIND.get(to) == "cave" and to != "dragon-cave":
            continue  # into the mountain: next stage
        done.add(pair)
        paths.append(SHAPES.get((place, to)) or SHAPES.get((to, place)) or [P[place], P[to]])
# Into the mist, and to Merlin's trap.
for key, spot in {**LOST, **DEATHS}.items():
    place = key.split(" ")[0]
    if KIND.get(place) != "cave" and key != "mossy-steps east":
        paths.append([P[place], spot])

path_lines = Lines()
for line in paths:
    path_lines.add(line)

# ---------------------------------------------------------------- the shape of the land

MOUND = Vector((P["grassy-bank"][0] - 9, P["grassy-bank"][1] + 9))  # between the west and north paths
TOWER = (P["tower"][0], P["tower"][1] + 6)
CASTLE = (-62, 62, -262, -142)  # its walls: west, east, south, north
MOAT = (-72, 72, -272, -130)


def in_moat(x, y):
    w, e, s, n = MOAT
    cw, ce, cs, cn = CASTLE
    return w <= x <= e and s <= y <= n and not (cw - 2 <= x <= ce + 2 and cs - 2 <= y <= cn + 2)


def mountain(x, y):
    across = smooth((95 - abs(x)) / 45)
    return 30 * smooth((y - 45) / 75) * across + 28 * smooth((y - 150) / 45) * smooth((80 - abs(x)) / 40)


def height(x, y):
    h = 0.35 * noise.noise(Vector((x / 30, y / 30, 0.3)))
    d = math.hypot((x - MOUND.x) / 9, (y - MOUND.y) / 6.5)
    if d < 1.35:
        h += 3.0 * (math.cos(d / 1.35 * math.pi) + 1) / 2
    h += mountain(x, y)
    t = math.hypot(x - TOWER[0], y - TOWER[1])
    h += 5 * smooth(1 - (t - 8) / 10)
    g = math.hypot(x - P["evergreen-glade"][0], y - P["evergreen-glade"][1])
    h -= 1.5 * smooth(1 - (g - 10) / 8)  # the glade lies a little low
    r = river.distance(x, y)
    if r < 10:
        h = h + (-3.2 - h) * smooth(1 - (r - 5) / 5)
    if in_moat(x, y):
        h = -3.2
    w, e, s, n = CASTLE
    if w - 8 <= x <= e + 8 and s - 8 <= y <= n + 8 and not in_moat(x, y):
        h = 0.4  # the castle stands on flat ground
    return h


def deck(x, y):
    """The bridge and drawbridge, for walking on."""
    if abs(x - BRIDGE[0]) <= 2.2 and abs(y - BRIDGE[1]) <= 9:
        return 0.9
    if abs(x) <= 3 and -143 <= y <= -127:
        return 0.6
    return None


# ---------------------------------------------------------------- where the forest isn't

CLEARING = {"grassy-bank": 17, "deep-river": 15, "river-south-bank": 15}
OPEN_ZONES = [
    (-96, 25, -7, 22),  # the meadow, along the long path to the old stone wall
    (-50, 50, 58, 178),  # the mountain top and the maze
    (-80, 80, -282, -124),  # the castle grounds
]
AXE_TREES = (-14, 14, 49, 58)  # the dense trees across the mountain path


def open_ground(x, y):
    for place, (px, py) in P.items():
        if KIND.get(place) == "cave" and place not in ("dragon-cave",):
            continue
        if math.hypot(x - px, y - py) < CLEARING.get(place, 12):
            return True
    for w, e, s, n in OPEN_ZONES:
        if w <= x <= e and s <= y <= n:
            return True
    for spot in LOST.values():
        if math.hypot(x - spot[0], y - spot[1]) < 11:
            return True
    return path_lines.distance(x, y) < 5.5 or river.distance(x, y) < 6.5 or in_moat(x, y)


def walkable(x, y):
    """Where you can stand: open ground that isn't water, or a bridge."""
    if deck(x, y) is not None:
        return True
    if river.distance(x, y) < 6.5 or in_moat(x, y):
        return False
    return open_ground(x, y)


# ---------------------------------------------------------------- the ground

nx, ny = int((X1 - X0) / STEP) + 1, int((Y1 - Y0) / STEP) + 1
verts, colours, faces, walk = [], [], [], []
for j in range(ny):
    for i in range(nx):
        x, y = X0 + i * STEP, Y0 + j * STEP
        z = height(x, y)
        verts.append((x, y, z))
        d = deck(x, y)
        walk.append(d if d is not None else z)
        if river.distance(x, y) < 7 or in_moat(x, y):
            col = RIVERBED
        elif CASTLE[0] <= x <= CASTLE[1] and CASTLE[2] <= y <= CASTLE[3]:
            col = FLAGS
        elif open_ground(x, y):
            col = GRASS
        else:
            col = FOREST_FLOOR
        if z > 8:
            col = c.mix(col, ROCK, smooth((z - 8) / 10))
        colours.append(c.vary(col, 0.12, Vector((x / 6, y / 6, 5.0))))
for j in range(ny - 1):
    for i in range(nx - 1):
        a = j * nx + i
        faces.append((a, a + 1, a + nx + 1, a + nx))
c.mesh_object("ground", verts, faces, colours)

# Paths: strips of earth on the ground.
strips = c.Builder()
for k, line in enumerate(paths):
    samples = []
    for (ax, ay), (bx, by) in zip(line, line[1:]):
        n = max(1, int(math.hypot(bx - ax, by - ay) / 1.0))
        samples += [(ax + (bx - ax) * f / n, ay + (by - ay) * f / n) for f in range(n)]
    samples.append(line[-1])
    lift = 0.05 + 0.004 * (k % 10)
    verts, colours, faces = [], [], []
    for i, (x, y) in enumerate(samples):
        nx_, ny_ = samples[min(i + 1, len(samples) - 1)]
        px_, py_ = samples[max(i - 1, 0)]
        tx, ty = nx_ - px_, ny_ - py_
        dd = math.hypot(tx, ty) or 1
        ox, oy = -ty / dd, tx / dd
        for side in (-1.5, 1.5):
            vx, vy = x + ox * side, y + oy * side
            d = deck(vx, vy)
            verts.append((vx, vy, (d if d is not None else height(vx, vy)) + lift))
            colours.append(c.vary(DIRT, 0.12, Vector((vx, vy, 2.0))))
        if i:
            a = (i - 1) * 2
            faces.append((a, a + 1, a + 3, a + 2))
    strips.add(verts, faces, colours)
strips.build("paths")

# ---------------------------------------------------------------- what's solid

circles, boxes = [], []
# What stands in the way until the right object is used, by the exit it
# blocks: "box" [x, z, half x, half z] or "circle" [x, z, r], in three.js's axes.
obstacles = {}


def obstacle(exits, shape, *values):
    for exit in exits:
        obstacles[exit] = {shape: [round(v, 2) for v in values]}


def solid_box(x, y, half_x, half_y):
    boxes.append([round(x, 2), round(-y, 2), round(half_x, 2), round(half_y, 2)])


def solid_circle(x, y, r):
    circles.append([round(x, 2), round(-y, 2), round(r, 2)])


def block(builder, x0, y0, z0, x1, y1, z1, colour, solid=True):
    """A box from one corner to the other."""
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    shade = [c.vary(colour, 0.1, Vector((x0 + k, y0, z0))) for k in range(8)]
    builder.add(v, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], shade)
    if solid:
        solid_box((x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2)


def tower(builder, x, y, radius, tall, colour, roof=None, roof_tall=None, sides=12):
    z = height(x, y) - 0.5
    builder.cylinder((x, y, z), (x, y, z + tall), radius, radius, colour, sides=sides)
    builder.add([(x + math.cos(2 * math.pi * k / sides) * radius, y + math.sin(2 * math.pi * k / sides) * radius, z + tall)
                 for k in range(sides)], [tuple(range(sides))], [colour] * sides)
    if roof:
        builder.cone((x, y, z + tall), roof_tall or radius * 2, radius * 1.15, roof, sides=sides, droop=0)
    solid_circle(x, y, radius)


# Trees: on a jittered grid wherever the ground isn't open.
trees = c.Builder()
for gx in range(X0 + 3, X1 - 2, 5):
    for gy in range(Y0 + 3, Y1 - 2, 5):
        x, y = gx + random.uniform(-2, 2), gy + random.uniform(-2, 2)
        if open_ground(x, y):
            continue
        z = height(x, y)
        tall = random.uniform(9, 14)
        trees.cone((x, y, z - 0.3), tall, random.uniform(2.2, 3.0), c.vary(TREE, 0.2, Vector((x, y, 0))), sides=7, droop=0.3)
# The dense trees across the mountain path, which only the axe will clear.
w, e, s, n = AXE_TREES
obstacle(["mountain-path north"], "box", (w + e) / 2, -(s + n) / 2, (e - w) / 2 + 2, (n - s) / 2)
for x in range(w, e + 1, 3):
    for y in (s + 2, s + 5, n - 1):
        xx, yy = x + random.uniform(-0.8, 0.8), y + random.uniform(-0.8, 0.8)
        trees.cone((xx, yy, height(xx, yy) - 0.3), random.uniform(8, 11), 1.8, c.vary(TREE, 0.2, Vector((xx, yy, 1))), sides=7, droop=0.2)
trees.build("trees", smooth=False)

# Water: the river, and the moat round the castle.
water = c.Builder()
for (ax, ay), (bx, by) in zip(RIVER, RIVER[1:]):
    dx, dy = bx - ax, by - ay
    dd = math.hypot(dx, dy) or 1
    ox, oy = -dy / dd * 7, dx / dd * 7
    water.add([(ax - ox, ay - oy, -1), (ax + ox, ay + oy, -1), (bx + ox, by + oy, -1), (bx - ox, by - oy, -1)],
              [(0, 1, 2, 3)], [WATER] * 4)
mw, me, ms, mn = MOAT
water.add([(mw, ms, -1), (me, ms, -1), (me, mn, -1), (mw, mn, -1)], [(0, 1, 2, 3)], [WATER] * 4)
water.build("water", smooth=False)

# ---------------------------------------------------------------- built things

built = c.Builder()

# The forest bridge and the drawbridge.
block(built, BRIDGE[0] - 2.4, BRIDGE[1] - 9, 0.5, BRIDGE[0] + 2.4, BRIDGE[1] + 9, 0.9, c.linear("#8a5a33"), solid=False)
for side in (-1, 1):
    block(built, BRIDGE[0] + side * 2.4 - 0.15, BRIDGE[1] - 9, 0.9, BRIDGE[0] + side * 2.4 + 0.15, BRIDGE[1] + 9, 1.9,
          c.linear("#6b4426"))
block(built, -3, -143, 0.2, 3, -127, 0.6, c.linear("#7a5230"), solid=False)
obstacle(["moat south"], "box", 0, 129, 3.2, 1.5)  # the drawbridge is up

# The old stone wall: north from the forest, west along the gate, north again.
WALL = 4.5
y = -18
while y < 60:
    block(built, -100.6, y, height(-100, y) - 0.5, -99.4, min(y + 2, 60.6), height(-100, y) + WALL, STONE)
    y += 2
GATE = (-122.2, -117.8)  # the gap in the wall, exactly the gate's width
for start, end in ((-140.6, GATE[0]), (GATE[1], -99.4)):
    x = start
    while x < end - 0.01:
        block(built, x, 59.4, height(x, 60) - 0.5, min(x + 2, end), 60.6, height(x, 60) + WALL, STONE)
        x += 2
block(built, GATE[0], 59.7, 0.0, GATE[1], 60.3, 3.6, c.linear("#a5532c"), solid=False)  # the rusty gate, locked
obstacle(["rusty-gate north", "yellow-flowers south"], "box", (GATE[0] + GATE[1]) / 2, -60, (GATE[1] - GATE[0]) / 2, 0.6)
y = 60
while y < 118:
    block(built, -140.6, y, height(-140, y) - 0.5, -139.4, y + 2, height(-140, y) + WALL, STONE)
    y += 2

# The tower on its knoll, with the balcony high on its east side, and the
# mossy steps up to it.
tower(built, TOWER[0], TOWER[1], 6, 20, GREY, ROOF, 9)
block(built, TOWER[0] + 6, TOWER[1] - 2, height(*TOWER) + 11, TOWER[0] + 8.5, TOWER[1] + 2, height(*TOWER) + 11.5, GREY, solid=False)
for k in range(6):
    sy = P["mossy-steps"][1] + 18 + k * 1.4
    block(built, TOWER[0] - 2, sy, height(TOWER[0], sy) - 0.4, TOWER[0] + 2, sy + 1.4, height(TOWER[0], sy) + 0.15,
          c.linear("#7f8f6a"), solid=False)

# The charcoal burner's hut.
hx, hy = P["charcoal-hut"]
block(built, hx - 4, hy - 3, height(hx, hy) - 0.3, hx + 4, hy + 3, height(hx, hy) + 3.2, c.linear("#7a5b3e"))
built.cone((hx, hy, height(hx, hy) + 3.2), 3, 5.5, c.linear("#5d4630"), sides=4, droop=0)

# The cave entrance's mound, with the pile of leaves blocking the way east,
# and the dragon's outcrop with its cave mouth facing west.
ce = P["cave-entrance"]
built.blob((ce[0] + 3, ce[1] + 8, height(*ce)), 7, ROCK, squash=0.55, lumpy=0.25, seed=1)
solid_circle(ce[0] + 3, ce[1] + 8, 6)
built.blob(((ce[0] + P["dragon-cave"][0]) / 2, ce[1], height(*ce) + 0.5), 5.5, LEAVES, squash=0.6, lumpy=0.35, seed=2)
obstacle(["cave-entrance east"], "circle", (ce[0] + P["dragon-cave"][0]) / 2, -ce[1], 6)
dc = P["dragon-cave"]
built.blob((dc[0] + 17, dc[1], height(*dc) - 2), 15, ROCK, squash=0.75, lumpy=0.25, seed=3)
solid_circle(dc[0] + 17, dc[1], 12.5)
block(built, dc[0] + 3.5, dc[1] - 3, height(*dc) - 0.2, dc[0] + 5.5, dc[1] + 3, height(*dc) + 5, c.linear("#1d1915"), solid=False)
built.blob((P["river-south-bank"][0] + 100, -60, -2), 9, ROCK, squash=0.7, lumpy=0.3, seed=4)  # where the river goes under

# The castle: walls with a gate to the north, corner towers, and the rooms as
# buildings round the courtyard. The golden spire rises from the great hall.
cw, ce_, cs, cn = CASTLE
for x0, x1 in ((cw, -3), (3, ce_)):
    block(built, x0, cn - 1, 0, x1, cn + 1, 8, GREY)
block(built, cw, cs - 1, 0, ce_, cs + 1, 8, GREY)
block(built, cw - 1, cs, 0, cw + 1, cn, 8, GREY)
block(built, ce_ - 1, cs, 0, ce_ + 1, cn, 8, GREY)
for tx, ty in ((cw, cn), (ce_, cn), (cw, cs), (ce_, cs)):
    tower(built, tx, ty, 5, 13, GREY, ROOF, 8)
for tx in (-6, 6):
    tower(built, tx, cn, 3, 11, GREY, ROOF, 5)
ROOMS = {
    "coach-house": (16, 12, 7),
    "wizards-kitchen": (16, 14, 8),
    "grand-hall": (26, 18, 12),
    "dungeon": (14, 14, 10),
    "merlins-lair": (18, 14, 9),
    "small-room": (12, 12, 8),
}
for place, (bw, bd, bh) in ROOMS.items():
    bx, by = P[place]
    block(built, bx - bw / 2, by - bd / 2, 0.2, bx + bw / 2, by + bd / 2, bh, GREY)
    built.cone((bx, by, bh), bh * 0.5, max(bw, bd) * 0.62, ROOF, sides=4, droop=0)
gx, gy = P["grand-hall"]
tower(built, gx, gy - 6, 4, 30, GREY)
built.cone((gx, gy - 6, 30), 16, 4.6, GOLD, sides=12, droop=0)
kx, ky = P["wizards-kitchen"]
block(built, kx + 4, ky + 2, 7, kx + 6, ky + 4, 11, ROCK, solid=False)  # the chimney
cx, cy = P["courtyard"]
tower(built, cx + 4, cy - 2, 1.2, 1.0, STONE)  # the well

built.build("built", smooth=False)

# ---------------------------------------------------------------- write it all out

# Where you can stand, a square metre at a time.
MASK_STEP = 1.0
mx, my = int((X1 - X0) / MASK_STEP), int((Y1 - Y0) / MASK_STEP)
mask = bytes(1 if walkable(X0 + (i + 0.5) * MASK_STEP, Y0 + (j + 0.5) * MASK_STEP) else 0
             for j in range(my) for i in range(mx))

if out:
    c.export(out)
    base = Path(out).with_suffix("")
    base.with_suffix(".bin").write_bytes(struct.pack(f"<{len(walk)}f", *walk) + mask)
    base.with_suffix(".json").write_text(json.dumps({
        "ground": {"x0": X0, "y0": Y0, "step": STEP, "nx": nx, "ny": ny},
        "walkable": {"x0": X0, "y0": Y0, "step": MASK_STEP, "nx": mx, "ny": my, "offset": len(walk) * 4},
        "obstacles": obstacles,
        "bounds": [X0 + 4, X1 - 4, Y0 + 4, Y1 - 4],
        "circles": circles,
        "boxes": boxes,
    }, separators=(",", ":")))
    print(f"Exported {out}: {len(circles)} solid circles, {len(boxes)} boxes, {len(obstacles)} obstacles")
if preview:
    c.preview(preview, (60, -120, 160), (0, -20, 0), (-0.7, 0.5, -0.45), lens=20)
