# The whole land in grey boxes: every place at its spot from layout.json,
# joined by paths, with the river and its bridge, the old stone wall and its
# gate, the mountain with the maze on top, and the castle in its moat.
#
# Forest is the barrier: trees grow everywhere except at the places, along the
# paths, on the meadow, round the maze and on the castle grounds, so you can
# only go where the original lets you. Bare rock is a barrier too: the crags
# round the maze, the dragon's hill and the ridge.
#
# Underground, ways (tunnels) join halls (caverns, and the treasure room and
# the beautiful chamber): the lamp tunnel, the caves in the mountain behind
# the maze, and the dragon's cave, with its long tunnel up to the giant and
# its way down to the dark tunnels.
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
K = S / 40  # the land below was laid out 40 metres apart: K scales it
OX, OY = layout["origin"]


def at(col_row):
    col, row = col_row
    return ((col - OX) * S, (OY - row) * S)


P = {place: at(cr) for place, cr in layout["places"].items()}
KIND = {place: kind for kind, places in layout["kinds"].items() if kind != "_" for place in places}
# The mist above ground clears the forest round it (underground, it's in a tunnel).
LOST = {k: at(v) for k, v in layout["lost"].items() if k != "_" and KIND.get(k.split(" ")[0]) != "cave"}
DEATHS = {k: at(v) for k, v in layout["deaths"].items() if k != "_"}

X0, X1, Y0, Y1 = (round(v * K) for v in (-200, 200, -290, 210))
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

RIVER = chaikin([(x * K, y * K) for x, y in [(-215, -40), (-150, -41), (-120, -40), (-100, -36), (-82, -24), (-64, -25),
                                             (-44, -46), (-20, -60), (20, -60), (60, -61), (94, -60)]])
river = Lines()
river.add(RIVER)
BRIDGE = P["old-wall"][0], -40 * K  # where the path south from the old wall crosses

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
    ("deep-river", "evergreen-glade"): [P["deep-river"], (22 * K, -32 * K), (34 * K, -14 * K), P["evergreen-glade"]],
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
        if KIND.get(place) == "cave" or KIND.get(to) == "cave":
            continue  # underground, or in at a cave's mouth (below)
        done.add(pair)
        paths.append(SHAPES.get((place, to)) or SHAPES.get((to, place)) or [P[place], P[to]])
# Into the mist, and to Merlin's trap.
for key, spot in {**LOST, **DEATHS}.items():
    place = key.split(" ")[0]
    if KIND.get(place) != "cave" and key != "mossy-steps east":
        paths.append([P[place], spot])

# Up to the lamp tunnel's mouths: in the rocky bank west of the old wall, and
# down the steps south of the cave entrance.
WEST_LIP = (P["old-wall"][0] - 13, P["old-wall"][1])
EAST_LIP = (P["cave-entrance"][0], P["cave-entrance"][1] - 11)
# And east from the cave entrance, into the dragon's hill.
DC = P["dragon-cave"]
DRAGON_LIP = (DC[0] - 22, DC[1])
paths += [[P["old-wall"], WEST_LIP], [P["cave-entrance"], EAST_LIP], [P["cave-entrance"], DRAGON_LIP]]

path_lines = Lines()
for line in paths:
    path_lines.add(line)

# ---------------------------------------------------------------- ways underground

TUNNEL_HALF = 1.7  # half a tunnel's width
TUNNEL_TALL = 3.2  # floor to roof
DEEP = -5.0  # the lamp tunnel's floor, under the meadows
TOP = 30 * K  # the mountain's height, where the maze is: lower when the places are closer, so it's no steeper
CAVE = TOP - 3  # the floor of the caves in the mountain


class Way:
    """A way underground: a line of points, each with its floor's height.
    A floor of None is the ground's height there: a mouth."""

    def __init__(self, points, half=TUNNEL_HALF):
        self.points = points
        self.half = half
        self.segments = list(zip(points, points[1:]))
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.box = (min(xs), max(xs), min(ys), max(ys))

    def settle(self):
        """Puts the mouths on the ground, once its shape is known."""
        self.points = [(x, y, height(x, y) if f is None else f) for x, y, f in self.points]
        self.segments = list(zip(self.points, self.points[1:]))

    def near(self, x, y, margin):
        w, e, s, n = self.box
        return w - margin <= x <= e + margin and s - margin <= y <= n + margin

    def nearest(self, x, y):
        """How far from the middle of the way, the floor's height there, and
        whether the spot is past either end."""
        best = None
        last = len(self.segments) - 1
        for k, ((ax, ay, af), (bx, by, bf)) in enumerate(self.segments):
            dx, dy = bx - ax, by - ay
            t = ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)
            tc = max(0.0, min(1.0, t))
            d = math.hypot(x - ax - tc * dx, y - ay - tc * dy)
            if best is None or d < best[0]:
                best = (d, af + (bf - af) * tc, (k == 0 and t < 0) or (k == last and t > 1))
        return best

    def samples(self, step=0.5):
        """Points along the way, every half metre."""
        out = []
        for (ax, ay, af), (bx, by, bf) in self.segments:
            n = max(1, int(math.hypot(bx - ax, by - ay) / step))
            out += [(ax + (bx - ax) * k / n, ay + (by - ay) * k / n, af + (bf - af) * k / n) for k in range(n)]
        out.append(self.points[-1])
        return out


class Hall:
    """A cavern (or a room) underground: round, with a flat floor and a domed
    roof. Being in it is being in its place."""

    def __init__(self, place, floor, r, tall, ground, wall, light=None, glow=0.0):
        self.place = place
        self.x, self.y = P[place]
        self.floor, self.r, self.tall = floor, r, tall
        self.ground, self.wall = ground, wall  # colours
        self.light, self.glow = light, glow  # its own light, if it has one

    def inside(self, x, y, margin=0.0):
        return math.hypot(x - self.x, y - self.y) < self.r + margin


TORCH = "#ffa24a"
HALLS = {h.place: h for h in [
    Hall("trolls", CAVE, 8, 6, c.linear("#6e5a42"), c.linear("#7a6650"), TORCH, 9),
    Hall("oak-door", CAVE, 7, 5.5, c.linear("#6b5a46"), c.linear("#7d6a52"), TORCH, 5),
    Hall("treasure-room", CAVE, 9, 7, c.linear("#a58a55"), c.linear("#9b8660"), "#ffc766", 12),
    Hall("giant", CAVE, 11, 10, c.linear("#6e5a42"), c.linear("#7a6650"), TORCH, 11),
    Hall("damp-tunnels", CAVE, 8, 5, c.linear("#4c5149"), c.linear("#646a5c"), TORCH, 6),
    Hall("dragon-cave", 0.2, 10, 9, c.linear("#7a5a3a"), c.linear("#8a6244"), "#ff7a30", 14),
    Hall("dark-tunnels", -8, 7, 5, c.linear("#3a342c"), c.linear("#4a4238")),
    Hall("beautiful-chamber", -10, 12, 8, c.linear("#f2eee2"), c.linear("#d9a640"), "#ffd98a", 26),
]}

T, O, G, DM = P["trolls"], P["oak-door"], P["giant"], P["damp-tunnels"]
TR, MZ, DK, BC = P["treasure-room"], P["maze"], P["dark-tunnels"], P["beautiful-chamber"]
MAZE_CELLS, MAZE_CELL = 5, 4.4
MAZE_HALF = MAZE_CELLS * MAZE_CELL / 2  # to the maze's outer wall

# The long way from the dragon's cave up under the ridge into the giant's
# cave, by its east side. Coming back the other way, you get lost.
DRAGON_TUNNEL = Way([
    (*DC, 0.2),
    (DC[0], DC[1] + 9, 0.2),
    (DC[0] + 2, DC[1] + 40, CAVE * 0.19),
    (DC[0] - 13, DC[1] + 72, CAVE * 0.48),
    (G[0] + 30, G[1] - 28, CAVE * 0.74),
    (G[0] + 20, G[1] - 10, CAVE * 0.94),
    (G[0] + 11, G[1], CAVE),
    (*G, CAVE),
])

WAYS = {
    # From the rocky bank west of the old wall, down and round under the old
    # stone wall, the meadow and the grassy bank, and up the steps into the
    # cave entrance.
    "lamp-tunnel": Way([
        (*WEST_LIP, None),
        (WEST_LIP[0] - 12, WEST_LIP[1], DEEP),
        (WEST_LIP[0] - 15, WEST_LIP[1] - 3, DEEP),
        (WEST_LIP[0] - 15, WEST_LIP[1] - 7, DEEP),
        (WEST_LIP[0] - 12, WEST_LIP[1] - 10, DEEP),
        (-40 * K, -10, DEEP),
        (-30 * K, EAST_LIP[1] - 12, DEEP),
        (EAST_LIP[0], EAST_LIP[1] - 12, DEEP),
        (*EAST_LIP, None),
    ]),
    # Out of the maze, west, east and north into the mountain.
    "maze-trolls": Way([(MZ[0] - MAZE_HALF - 0.5, MZ[1], None), (MZ[0] - MAZE_HALF - 6, MZ[1], CAVE + 1.4),
                        (T[0] + 8, T[1], CAVE), (*T, CAVE)]),
    "maze-damp": Way([(MZ[0] + MAZE_HALF + 0.5, MZ[1], None), (MZ[0] + MAZE_HALF + 6, MZ[1], CAVE + 1.4),
                      (DM[0] - 8, DM[1], CAVE), (*DM, CAVE)]),
    "maze-treasure": Way([(MZ[0], MZ[1] + MAZE_HALF + 0.5, None), (MZ[0], MZ[1] + MAZE_HALF + 3, CAVE + 1),
                          (TR[0], TR[1] - 9.5, CAVE), (*TR, CAVE)]),
    # Between the caves.
    "trolls-oak": Way([(*T, CAVE), (*O, CAVE)]),
    "oak-treasure": Way([(*O, CAVE), (*TR, CAVE)]),
    "treasure-giant": Way([(*TR, CAVE), (*G, CAVE)]),
    "giant-damp": Way([(*G, CAVE), (*DM, CAVE)]),
    # Into the dragon's hill, past the leaves; and the dragon's way south,
    # down into the dark tunnels, which go on west, east and south.
    "dragon-mouth": Way([(*DRAGON_LIP, None), (DC[0] - 12, DC[1], 0.2), (*DC, 0.2)]),
    "dragon-giant": DRAGON_TUNNEL,
    "dragon-dark": Way([(*DC, 0.2), (DC[0], DC[1] - 10, 0.2), (DK[0], DK[1] + 8, -8), (*DK, -8)]),
    "dark-west": Way([(*DK, -8), (DK[0] - 34, DK[1], -8)]),
    "dark-east": Way([(*DK, -8), (DK[0] + 34, DK[1], -8)]),
    "dark-beautiful": Way([(*DK, -8), (DK[0], DK[1] - 10, -8), (BC[0], BC[1] + 12, -10), (*BC, -10)]),
}

# ---------------------------------------------------------------- the shape of the land

MOUND = Vector((P["grassy-bank"][0] - 9, P["grassy-bank"][1] + 9))  # between the west and north paths
TOWER = (P["tower"][0], P["tower"][1] + 6)
CASTLE = (-62 * K, 62 * K, -262 * K, -142 * K)  # its walls: west, east, south, north
MOAT = (-72 * K, 72 * K, -272 * K, -130 * K)


def in_moat(x, y):
    w, e, s, n = MOAT
    cw, ce, cs, cn = CASTLE
    return w <= x <= e and s <= y <= n and not (cw - 2 <= x <= ce + 2 and cs - 2 <= y <= cn + 2)


def mountain(x, y):
    x, y = x / K, y / K
    across = smooth((95 - abs(x)) / 45)
    return K * (30 * smooth((y - 45) / 75) * across + 28 * smooth((y - 150) / 45) * smooth((80 - abs(x)) / 40))


def crags(x, y):
    """Rocks round the maze on the mountain top, which its caves are dug into.
    They leave the maze, and the way up to it from the south, open."""
    top = smooth((mountain(x, y) / TOP - 0.6) / 0.27)
    if top <= 0:
        return 0.0
    dx = max(0.0, abs(x - MZ[0]) - MAZE_HALF - 0.5)
    dy = max(0.0, abs(y - MZ[1]) - MAZE_HALF - 0.5)
    d = math.hypot(dx, dy)
    if y < MZ[1]:
        d = min(d, max(0.0, abs(x - MZ[0]) - 6))  # the way up
    return 15 * top * smooth((d - 1) / 6) * (1 + 0.15 * noise.noise(Vector((x / 6, y / 6, 4.0))))


def dragon_hill(x, y):
    """The rocky hill the dragon lives in."""
    d = math.hypot(x - DC[0], y - DC[1])
    return 14 * smooth(1 - (d - 12) / 10) * (1 + 0.12 * noise.noise(Vector((x / 5, y / 5, 6.0))))


def ridge(x, y):
    """The ridge from the dragon's hill up to the mountain, with the long
    tunnel inside it."""
    if not DRAGON_TUNNEL.near(x, y, 20):
        return 0.0
    d, floor, _ = DRAGON_TUNNEL.nearest(x, y)
    return (floor + 11) * smooth(1 - (d - 5) / 14) * (1 + 0.12 * noise.noise(Vector((x / 6, y / 6, 8.0))))


def height(x, y):
    h = 0.35 * noise.noise(Vector((x / 30, y / 30, 0.3)))
    d = math.hypot((x - MOUND.x) / 9, (y - MOUND.y) / 6.5)
    if d < 1.35:
        h += 3.0 * (math.cos(d / 1.35 * math.pi) + 1) / 2
    h += mountain(x, y) + crags(x, y)
    h = max(h, dragon_hill(x, y), ridge(x, y))
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


def rocky(x, y):
    """Bare rock you can't climb: the crags, the dragon's hill and the ridge."""
    return crags(x, y) > 1 or dragon_hill(x, y) > 1 or ridge(x, y) > 1


for way in WAYS.values():
    way.settle()


def deck(x, y):
    """The bridge and drawbridge, for walking on."""
    if abs(x - BRIDGE[0]) <= 2.2 and abs(y - BRIDGE[1]) <= 9:
        return 0.9
    if abs(x) <= 3 and -143 * K <= y <= -127 * K:
        return 0.6
    return None


def open_to_the_sky(x, y, margin):
    """Over a ramp or a mouth into a way, where there's no earth over it:
    the ground has a hole here. Gives the floor's height there, or None."""
    for way in WAYS.values():
        if not way.near(x, y, way.half + margin):
            continue
        d, floor, beyond = way.nearest(x, y)
        if not beyond and d < way.half + margin and floor + TUNNEL_TALL > height(x, y) - 0.4:
            return floor
    return None


# ---------------------------------------------------------------- where the forest isn't

CLEARING = {"grassy-bank": 17, "deep-river": 15, "river-south-bank": 15}
OPEN_ZONES = [(w * K, e * K, s * K, n * K) for w, e, s, n in [
    (-96, 25, -7, 22),  # the meadow, along the long path to the old stone wall
    (-80, 80, -282, -124),  # the castle grounds
]] + [(MZ[0] - MAZE_HALF - 0.5, MZ[0] + MAZE_HALF + 0.5, MZ[1] - MAZE_HALF - 0.5, MZ[1] + MAZE_HALF + 0.5)]  # the maze
AXE_TREES = (-14, 14, 49 * K, 58 * K)  # the dense trees across the mountain path


def open_ground(x, y):
    for place, (px, py) in P.items():
        if KIND.get(place) == "cave":
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
    floor = open_to_the_sky(x, y, 2.0)
    if floor is not None and floor < height(x, y) - 0.35:
        return False  # over the ramp: you go in at the top
    return open_ground(x, y) and not rocky(x, y)


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
        if open_to_the_sky(X0 + (i + 0.5) * STEP, Y0 + (j + 0.5) * STEP, 1.0) is not None:
            continue  # the hole over a ramp
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


def obstacle(exits, shape, *values, under=False):
    """Underground ones block only the ways, and land ones only the land."""
    for exit in exits:
        obstacles[exit] = {shape: [round(v, 2) for v in values], **({"under": True} if under else {})}


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
        if open_ground(x, y) or open_to_the_sky(x, y, 4.5) is not None or rocky(x, y):
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
block(built, -3, -143 * K, 0.2, 3, -127 * K, 0.6, c.linear("#7a5230"), solid=False)
obstacle(["moat south"], "box", 0, 129 * K, 3.2, 1.5)  # the drawbridge is up

# The old stone wall: north from the forest, west along the gate, north again.
WALL = 4.5
WX, WY = -100 * K, 60 * K  # the corner by the old stone wall, and the gate's line
y = -18 * K
while y < WY:
    block(built, WX - 0.6, y, height(WX, y) - 0.5, WX + 0.6, min(y + 2, WY + 0.6), height(WX, y) + WALL, STONE)
    y += 2
GATE = (P["rusty-gate"][0] - 2.2, P["rusty-gate"][0] + 2.2)  # the gap in the wall, exactly the gate's width
WW = -140 * K  # where it turns north again, up the west of the yellow flowers
for start, end in ((WW - 0.6, GATE[0]), (GATE[1], WX + 0.6)):
    x = start
    while x < end - 0.01:
        block(built, x, WY - 0.6, height(x, WY) - 0.5, min(x + 2, end), WY + 0.6, height(x, WY) + WALL, STONE)
        x += 2
block(built, GATE[0], WY - 0.3, 0.0, GATE[1], WY + 0.3, 3.6, c.linear("#a5532c"), solid=False)  # the rusty gate, locked
obstacle(["rusty-gate north", "yellow-flowers south"], "box", (GATE[0] + GATE[1]) / 2, -WY, (GATE[1] - GATE[0]) / 2, 0.6)
y = WY
while y < 118 * K:
    block(built, WW - 0.6, y, height(WW, y) - 0.5, WW + 0.6, y + 2, height(WW, y) + WALL, STONE)
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

# The cave entrance's mound, and the pile of leaves filling the mouth of the
# dragon's cave, just inside.
ce = P["cave-entrance"]
built.blob((ce[0] + 3, ce[1] + 8, height(*ce)), 7, ROCK, squash=0.55, lumpy=0.25, seed=1)
solid_circle(ce[0] + 3, ce[1] + 8, 6)
lx, ly = DRAGON_LIP[0] + 3, DRAGON_LIP[1]
built.blob((lx, ly, WAYS["dragon-mouth"].nearest(lx, ly)[1] + 0.2), 2.6, LEAVES, squash=0.55, lumpy=0.35, seed=2)
obstacle(["cave-entrance east"], "box", lx, -ly, 1.0, TUNNEL_HALF + 0.3, under=True)

# The maze on the mountain top: old stone walls, one way through from every
# side to every other.
maze_rng = random.Random(7)
n = MAZE_CELLS
east_wall = [[True] * n for _ in range(n)]  # between cell (i, j) and (i + 1, j)
north_wall = [[True] * n for _ in range(n)]  # between cell (i, j) and (i, j + 1)
seen, stack = {(n // 2, 0)}, [(n // 2, 0)]
while stack:
    i, j = stack[-1]
    nexts = [(i + di, j + dj) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))
             if 0 <= i + di < n and 0 <= j + dj < n and (i + di, j + dj) not in seen]
    if not nexts:
        stack.pop()
        continue
    ni, nj = maze_rng.choice(nexts)
    if ni != i:
        east_wall[min(i, ni)][j] = False
    else:
        north_wall[i][min(j, nj)] = False
    seen.add((ni, nj))
    stack.append((ni, nj))
mx0, my0 = MZ[0] - MAZE_HALF, MZ[1] - MAZE_HALF
MAZE_STONE = c.linear("#8d8a74")


def maze_wall(x0, y0, x1, y1):
    x0, x1 = min(x0, x1) - 0.3, max(x0, x1) + 0.3
    y0, y1 = min(y0, y1) - 0.3, max(y0, y1) + 0.3
    base = height((x0 + x1) / 2, (y0 + y1) / 2)
    block(built, x0, y0, base - 0.6, x1, y1, base + 2.8, MAZE_STONE)


gap = n // 2  # the openings, in the middle of every side
for k in range(n):
    sx, sy = mx0 + k * MAZE_CELL, my0 + k * MAZE_CELL
    if k != gap:
        maze_wall(sx, my0, sx + MAZE_CELL, my0)  # south
        maze_wall(sx, my0 + n * MAZE_CELL, sx + MAZE_CELL, my0 + n * MAZE_CELL)  # north
        maze_wall(mx0, sy, mx0, sy + MAZE_CELL)  # west
        maze_wall(mx0 + n * MAZE_CELL, sy, mx0 + n * MAZE_CELL, sy + MAZE_CELL)  # east
for i in range(n):
    for j in range(n):
        x, y = mx0 + i * MAZE_CELL, my0 + j * MAZE_CELL
        if i < n - 1 and east_wall[i][j]:
            maze_wall(x + MAZE_CELL, y, x + MAZE_CELL, y + MAZE_CELL)
        if j < n - 1 and north_wall[i][j]:
            maze_wall(x, y + MAZE_CELL, x + MAZE_CELL, y + MAZE_CELL)
built.blob((RIVER[-1][0] + 6, RIVER[-1][1], -2), 9, ROCK, squash=0.7, lumpy=0.3, seed=4)  # where the river goes under

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

# ---------------------------------------------------------------- underground

EARTH = c.linear("#5a4632")
TUNNEL_STONE = c.linear("#7d7568")
FLAME = c.linear("#ffb347")
IRON = c.linear("#2b2a2c")
OAK = c.linear("#5e3b1f")
GOLD_STONE = c.linear("#c9a25a")
PIT_DARK = c.linear("#100b08")

# What's solid underground, apart from the ways' and the halls' own walls.
under_circles, under_boxes = [], []


def under_circle(x, y, r):
    under_circles.append([round(x, 2), round(-y, 2), round(r, 2)])


def under_box(x, y, half_x, half_y):
    under_boxes.append([round(x, 2), round(-y, 2), round(half_x, 2), round(half_y, 2)])


def in_a_hall(x, y, floor, margin=0.0):
    """The hall a spot is in, on that floor, if any."""
    for hall in HALLS.values():
        if abs(hall.floor - floor) < 1.5 and hall.inside(x, y, margin):
            return hall
    return None


def quad(builder, pts, colour, vary=0.12):
    builder.add(pts, [(0, 1, 2, 3)], [c.vary(colour, vary, Vector(pts[0])) for _ in pts])


def spike(builder, x, y, z, tall, radius, colour, sides=6):
    """A stalagmite, or (tall below zero) a stalactite."""
    verts = [(x + math.cos(2 * math.pi * k / sides) * radius, y + math.sin(2 * math.pi * k / sides) * radius, z)
             for k in range(sides)] + [(x, y, z + tall)]
    faces = [(k, (k + 1) % sides, sides) for k in range(sides)]
    builder.add(verts, faces, [c.vary(colour, 0.15, Vector((x, y, z + k))) for k in range(sides + 1)])


def opening(hall, x, y):
    """Whether a way comes into the hall here, at its wall."""
    for way in WAYS.values():
        if way.near(x, y, way.half + 1):
            d, floor, beyond = way.nearest(x, y)
            if not beyond and d < way.half + 0.5 and abs(floor - hall.floor) < 1.5:
                return True
    return False


# The deep hole across the way from the maze to the treasure room: x, y, and
# half its size across and along.
PIT = (MZ[0], MZ[1] + MAZE_HALF + 5.4, TUNNEL_HALF + 0.4, 1.8)


def in_pit(x, y):
    px, py, hx, hy = PIT
    return abs(x - px) <= hx and abs(y - py) <= hy


# The ways: floor, walls and roof, stone walls up the ramps, a lip of stone
# round the hole, and a lintel where the roof begins. Inside a hall, the
# hall's own floor and walls take over, with a door frame where they meet.
tunnel = c.Builder()
for way in WAYS.values():
    half = way.half
    points = way.samples()
    rows = []
    for k, (x, y, floor) in enumerate(points):
        ax, ay, _ = points[max(k - 1, 0)]
        bx, by, _ = points[min(k + 1, len(points) - 1)]
        d = math.hypot(bx - ax, by - ay) or 1
        nx_, ny_ = -(by - ay) / d, (bx - ax) / d
        ground = height(x, y)
        covered = floor + TUNNEL_TALL <= ground - 0.4
        rows.append((x, y, floor, nx_, ny_, covered))

    def side(row, offset):
        x, y, _, nx_, ny_, _ = row
        return x + nx_ * offset, y + ny_ * offset

    for (a, b) in zip(rows, rows[1:]):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        if in_a_hall(*mid, 0.3):
            continue
        (alx, aly), (arx, ary) = side(a, -half), side(a, half)
        (blx, bly), (brx, bry) = side(b, -half), side(b, half)
        if not in_a_hall(*mid, 1.3) and not in_pit(mid[0], mid[1]):
            quad(tunnel, [(alx, aly, a[2]), (arx, ary, a[2]), (brx, bry, b[2]), (blx, bly, b[2])], EARTH)
        for (ax_, ay_), (bx_, by_) in (((alx, aly), (blx, bly)), ((arx, ary), (brx, bry))):
            top_a = a[2] + TUNNEL_TALL if a[5] else max(height(ax_, ay_) + 0.3, a[2] + 0.6)
            top_b = b[2] + TUNNEL_TALL if b[5] else max(height(bx_, by_) + 0.3, b[2] + 0.6)
            quad(tunnel, [(ax_, ay_, a[2]), (bx_, by_, b[2]), (bx_, by_, top_b), (ax_, ay_, top_a)], TUNNEL_STONE)
        if a[5] and b[5]:
            quad(tunnel, [(alx, aly, a[2] + TUNNEL_TALL), (arx, ary, a[2] + TUNNEL_TALL), (brx, bry, b[2] + TUNNEL_TALL),
                          (blx, bly, b[2] + TUNNEL_TALL)], c.mix(TUNNEL_STONE, EARTH, 0.5))
        if not a[5] and not b[5]:
            # A lip of stone round the hole, hiding its ragged edge.
            for inner, outer in ((half, half + 2.4), (-half, -half - 2.4)):
                pa = [side(a, inner), side(a, outer)]
                pb = [side(b, outer), side(b, inner)]
                quad(tunnel, [(*p, height(*p) + 0.32) for p in pa + pb], STONE)
        if a[5] != b[5]:
            # The lintel: the face of earth and stone over the opening.
            row = b if b[5] else a
            l1, r1 = side(row, -half - 2.4), side(row, half + 2.4)
            low = row[2] + TUNNEL_TALL
            high = max(height(*l1), height(*r1), height(row[0], row[1])) + 0.8
            quad(tunnel, [(*l1, low), (*r1, low), (*r1, high), (*l1, high)], STONE)
    # Door frames, where the way goes into a hall.
    for a, b in zip(rows, rows[1:]):
        for hall in HALLS.values():
            if abs(hall.floor - a[2]) > 1.5 or hall.inside(a[0], a[1], 0.3) == hall.inside(b[0], b[1], 0.3):
                continue
            row = b if hall.inside(a[0], a[1], 0.3) else a
            f = row[2]
            for inner, outer in ((half, half + 1.8), (-half, -half - 1.8)):
                p, q = side(row, inner), side(row, outer)
                quad(tunnel, [(*p, f - 0.3), (*q, f - 0.3), (*q, f + TUNNEL_TALL), (*p, f + TUNNEL_TALL)], hall.wall)
tunnel.build("tunnel", smooth=False)

# The deep hole: straight down into the dark.
px, py, phx, phy = PIT
pit = c.Builder()
corners = [(px - phx, py - phy), (px + phx, py - phy), (px + phx, py + phy), (px - phx, py + phy)]
tops = [WAYS["maze-treasure"].nearest(x, y)[1] for x, y in corners]
bottom = min(tops) - 9
for k in range(4):
    (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
    quad(pit, [(ax, ay, tops[k]), (bx, by, tops[(k + 1) % 4]), (bx, by, bottom), (ax, ay, bottom)], c.mix(EARTH, PIT_DARK, 0.6))
quad(pit, [(x, y, bottom) for x, y in corners], PIT_DARK)
obstacle(["maze north", "treasure-room south"], "box", px, -py, phx, phy, under=True)

# The halls: a floor of squares out under the walls, a lumpy round wall with
# openings where the ways come in, and a dome.
caves = c.Builder()
for hall in HALLS.values():
    hx, hy, f, R = hall.x, hall.y, hall.floor, hall.r
    step = 1.5
    reach = R + 1.4
    n = int(reach / step) + 1
    for i in range(-n, n):
        for j in range(-n, n):
            x0, y0 = hx + i * step, hy + j * step
            nearest_x, nearest_y = max(x0, min(hx, x0 + step)), max(y0, min(hy, y0 + step))
            if math.hypot(nearest_x - hx, nearest_y - hy) > reach:
                continue
            colour, vary = hall.ground, 0.12
            if hall.place == "beautiful-chamber":
                colour, vary = (hall.ground if (i + j) % 2 else c.linear("#1d1a1c")), 0.03
            elif hall.place == "treasure-room":
                colour = c.mix(hall.ground, GOLD_STONE, 0.5 if (i + j) % 2 else 0.1)
            elif hall.place == "damp-tunnels" and noise.noise(Vector((x0 / 4, y0 / 4, 9.0))) > 0.15:
                colour = c.linear("#2f3c44")  # puddles
            # (A shade lower than the ways' floors, where they overlap.)
            fl = f - 0.03
            quad(caves, [(x0, y0, fl), (x0 + step, y0, fl), (x0 + step, y0 + step, fl), (x0, y0 + step, fl)], colour, vary)

    sides = max(28, int(2 * math.pi * R / 1.1))
    wall_top = f + max(TUNNEL_TALL + 0.8, hall.tall * 0.5)
    domes = 6
    smooth_wall = hall.place in ("treasure-room", "beautiful-chamber")

    def bulge(k, level):
        if smooth_wall:
            return R + 0.4
        return R + 0.4 + 0.9 * abs(noise.noise(Vector((k / 3, level / 2, hx / 10 + f))))

    rings = []  # each: a radius for every side, and a height
    rings.append(([bulge(k, 0) for k in range(sides)], f - 0.3))
    rings.append(([bulge(k, 1) for k in range(sides)], wall_top))
    for m in range(1, domes + 1):
        t = m / (domes + 1) * math.pi / 2
        rings.append(([bulge(k, m + 1) * math.cos(t) for k in range(sides)], wall_top + (f + hall.tall - wall_top) * math.sin(t)))
    point = lambda k, ring: (hx + math.cos(2 * math.pi * k / sides) * ring[0][k % sides],  # noqa: E731
                             hy + math.sin(2 * math.pi * k / sides) * ring[0][k % sides], ring[1])
    for k in range(sides):
        am = 2 * math.pi * (k + 0.5) / sides
        door = opening(hall, hx + math.cos(am) * (R + 0.6), hy + math.sin(am) * (R + 0.6))
        a0, b0, a1, b1 = point(k, rings[0]), point(k + 1, rings[0]), point(k, rings[1]), point(k + 1, rings[1])
        if door:
            low = f + TUNNEL_TALL
            a0, b0 = (a1[0], a1[1], low), (b1[0], b1[1], low)
        quad(caves, [a0, b0, b1, a1], hall.wall)
        for r0, r1 in zip(rings[1:], rings[2:]):
            colour = c.mix(hall.wall, c.linear("#000000"), 0.15)
            quad(caves, [point(k, r0), point(k + 1, r0), point(k + 1, r1), point(k, r1)], colour)
        last = rings[-1]
        caves.add([point(k, last), point(k + 1, last), (hx, hy, f + hall.tall)], [(0, 1, 2)], [hall.wall] * 3)

    def free_spot(radius):
        """Somewhere near the wall that isn't in a doorway."""
        for _ in range(40):
            a = random.uniform(0, 2 * math.pi)
            x, y = hx + math.cos(a) * radius, hy + math.sin(a) * radius
            if not opening(hall, hx + math.cos(a) * (R + 0.6), hy + math.sin(a) * (R + 0.6)) \
                    and not opening(hall, x, y):
                return x, y, a
        return None

    def ceiling(x, y):
        rho = math.hypot(x - hx, y - hy) / (R + 0.4)
        return wall_top + (f + hall.tall - wall_top) * math.sqrt(max(0.0, 1 - rho * rho))

    if hall.place in ("treasure-room", "beautiful-chamber"):
        # Pillars round the room.
        count = 8 if hall.place == "treasure-room" else 14
        inset = 2.2 if hall.place == "treasure-room" else 0.9
        for k in range(count):
            a = 2 * math.pi * (k + 0.5) / count
            x, y = hx + math.cos(a) * (R - inset), hy + math.sin(a) * (R - inset)
            if opening(hall, x, y):
                continue
            caves.cylinder((x, y, f), (x, y, ceiling(x, y) + 0.2), 0.55, 0.45, GOLD_STONE if hall.place == "beautiful-chamber"
                           else c.linear("#b49a68"), sides=10)
            under_circle(x, y, 0.55)
    if hall.place == "treasure-room":
        # The altar on its steps, against the north wall, and chests.
        ax, ay = hx, hy + R - 3.2
        block(caves, ax - 2.6, ay - 1.6, f, ax + 2.6, ay + 1.6, f + 0.4, GOLD_STONE, solid=False)
        block(caves, ax - 1.6, ay - 0.9, f + 0.4, ax + 1.6, ay + 0.9, f + 1.5, c.linear("#d8b46a"), solid=False)
        under_box(ax, ay, 2.6, 1.6)
        for cx_, cy_ in ((hx - 4.5, hy + 3), (hx + 4.5, hy + 3), (hx - 5, hy - 3.5), (hx + 5, hy - 3.5)):
            block(caves, cx_ - 0.7, cy_ - 0.45, f, cx_ + 0.7, cy_ + 0.45, f + 0.8, c.linear("#7a4e26"), solid=False)
            under_box(cx_, cy_, 0.7, 0.45)
    elif hall.place != "beautiful-chamber":
        # Stalagmites round the edge, stalactites overhead.
        rock = c.mix(hall.wall, ROCK, 0.4)
        for _ in range(int(R * 1.6)):
            spot = free_spot(R - random.uniform(0.6, 2.4))
            if spot:
                x, y, _ = spot
                r = random.uniform(0.35, 0.7)
                spike(caves, x, y, f - 0.1, random.uniform(1.0, 2.8), r, rock)
                under_circle(x, y, r * 0.8)
        for _ in range(int(R * 2)):
            a, rho = random.uniform(0, 2 * math.pi), random.uniform(1.5, R - 0.5)
            x, y = hx + math.cos(a) * rho, hy + math.sin(a) * rho
            spike(caves, x, y, ceiling(x, y) + 0.3, -random.uniform(0.6, min(2.0, hall.tall - 3.4)), random.uniform(0.2, 0.45), rock)
    if hall.light == TORCH:
        # Torches on the walls.
        for _ in range(4 if R < 10 else 6):
            spot = free_spot(R + 0.25)
            if spot:
                x, y, a = spot
                block(caves, x - 0.08, y - 0.08, f + 1.9, x + 0.08, y + 0.08, f + 2.5, IRON, solid=False)
                caves.cone((x, y, f + 2.5), 0.5, 0.16, FLAME, sides=6, droop=0)

# Doors and things that block the ways (until the game opens them).
t_edge = T[1] + HALLS["trolls"].r + 1.5
obstacle(["trolls north"], "box", T[0], -t_edge, TUNNEL_HALF + 0.3, 1.0, under=True)  # the trolls, in the way
oy = O[1] - HALLS["oak-door"].r - 1.2
block(caves, O[0] - TUNNEL_HALF, oy - 0.15, CAVE, O[0] + TUNNEL_HALF, oy + 0.15, CAVE + TUNNEL_TALL, OAK, solid=False)
obstacle(["oak-door south"], "box", O[0], -oy, TUNNEL_HALF + 0.3, 0.5, under=True)  # the oak door, locked
gx = G[0] - HALLS["giant"].r - 1.5
obstacle(["giant west"], "box", gx, -G[1], 1.0, TUNNEL_HALF + 0.3, under=True)  # the giant, in the way
gy = G[1] - HALLS["giant"].r - 1.2
for k in range(11):
    x = G[0] - TUNNEL_HALF + 0.15 + k * (2 * TUNNEL_HALF - 0.3) / 10
    block(caves, x - 0.05, gy - 0.05, CAVE, x + 0.05, gy + 0.05, CAVE + TUNNEL_TALL, IRON, solid=False)
for z in (CAVE + 0.3, CAVE + 1.6, CAVE + TUNNEL_TALL - 0.2):
    block(caves, G[0] - TUNNEL_HALF, gy - 0.08, z, G[0] + TUNNEL_HALF, gy + 0.08, z + 0.15, IRON, solid=False)
obstacle(["giant south"], "box", G[0], -gy, TUNNEL_HALF + 0.3, 0.5, under=True)  # the padlocked gate
dy = DC[1] - HALLS["dragon-cave"].r - 1.5
obstacle(["dragon-cave south"], "box", DC[0], -dy, TUNNEL_HALF + 0.3, 1.0, under=True)  # the dragon's fire
ky = DK[1] - HALLS["dark-tunnels"].r - 1.5
obstacle(["dark-tunnels south"], "box", DK[0], -ky, TUNNEL_HALF + 0.3, 1.0, under=True)  # too dark to go on
caves.build("caves", smooth=False)
pit.build("pit", smooth=False)

# Rocks either side of the mouths.
rocks = c.Builder()
for x, y, r in ((WEST_LIP[0] - 6, WEST_LIP[1] + 6.5, 4.2), (WEST_LIP[0] - 6, WEST_LIP[1] - 6.5, 4.2),
                (WEST_LIP[0] - 15, WEST_LIP[1], 6.5), (EAST_LIP[0] - 5, EAST_LIP[1] - 5, 2.8), (EAST_LIP[0] + 5, EAST_LIP[1] - 5, 2.8)):
    rocks.blob((x, y, height(x, y) - 0.5), r, ROCK, squash=0.7, lumpy=0.25, seed=x + y)
    solid_circle(x, y, r * 0.85)
rocks.build("rocks", smooth=True)

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
        # The ways underground: points [x, z, floor] in three.js's axes.
        "ways": {name: {"half": way.half, "points": [[round(x, 2), round(-y, 2), round(f, 2)] for x, y, f in way.points]}
                 for name, way in WAYS.items()},
        # The halls they join: being in one is being in its place.
        "halls": {place: {"x": hall.x, "z": -hall.y, "floor": hall.floor, "r": hall.r, "tall": hall.tall,
                          **({"light": hall.light, "glow": hall.glow} if hall.light else {})}
                  for place, hall in HALLS.items()},
        "under": {"circles": under_circles, "boxes": under_boxes},
        "bounds": [X0 + 4, X1 - 4, Y0 + 4, Y1 - 4],
        "circles": circles,
        "boxes": boxes,
    }, separators=(",", ":")))
    print(f"Exported {out}: {len(circles)} solid circles, {len(boxes)} boxes, {len(obstacles)} obstacles")
if preview:
    c.preview(preview, (60, -120, 160), (0, -20, 0), (-0.7, 0.5, -0.45), lens=20)
