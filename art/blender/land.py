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
# its way down to the dark tunnels. Indoors is the same: the castle's rooms
# are halls with square corners, in the keep, joined by corridors.
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
BANK = 8.5  # from the river's middle to where its banks come up out of the water
SHORE = 10  # and to where you can walk: back from the edge, where the bank levels out
BRIDGE_HALF = SHORE + 0.5  # half the forest bridge's length, so it reaches the shore
BRIDGE = P["old-wall"][0], -40 * K  # where the path south from the old wall crosses
TOWER = (P["tower"][0], P["tower"][1] + 6)  # on its knoll, north of the mossy steps
TOWER_R = 6
HUT = P["charcoal-hut"]
# Where you step in at their doors: the tower's faces south, down the mossy
# steps; the hut's north, to the crossroads.
TOWER_LIP = (TOWER[0], TOWER[1] - TOWER_R - 1.8)
HUT_LIP = (HUT[0], HUT[1] + 3 + 1.8)

# ---------------------------------------------------------------- the paths

CASTLE_ROOMS = {"coach-house", "wizards-kitchen", "grand-hall", "dungeon", "merlins-lair", "small-room"}
INDOORS = CASTLE_ROOMS | {"charcoal-hut", "tower"}  # places inside buildings

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
        if {place, to} & INDOORS:
            continue  # indoors, along the castle's corridors (or up to a door, below)
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
# And to the tower's and the hut's doors.
paths += [[P["mossy-steps"], TOWER_LIP], [P["forest-crossroads"], HUT_LIP]]

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

    def __init__(self, points, half=TUNNEL_HALF, indoor=False):
        self.points = points
        self.half = half
        self.indoor = indoor  # a corridor in a building: walls and a roof all the way
        self.segments = list(zip(points, points[1:]))
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        self.box = (min(xs), max(xs), min(ys), max(ys))

    def settle(self):
        """Puts the mouths on the ground, once its shape is known; and finds
        how far in from each end it's open to the sky (until it first goes
        under cover: from there on it's roofed, even where the ground dips
        close over it, as under the river)."""
        self.points = [(x, y, height(x, y) if f is None else f) for x, y, f in self.points]
        self.segments = list(zip(self.points, self.points[1:]))
        along, covered, so_far = [], [], 0.0
        samples = self.samples()
        for k, (x, y, f) in enumerate(samples):
            if k:
                so_far += math.dist(samples[k - 1][:2], (x, y))
            along.append(so_far)
            covered.append(f + TUNNEL_TALL <= height(x, y) - 0.4)
        under = [a for a, c in zip(along, covered) if c]
        self.roofed = (under[0], under[-1]) if under and not self.indoor else None
        self.length = so_far

    def along(self, x, y):
        """How far along the way the spot nearest x, y is."""
        best, so_far = None, 0.0
        for (ax, ay, _), (bx, by, _) in self.segments:
            dx, dy = bx - ax, by - ay
            length = math.hypot(dx, dy)
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (length * length)))
            d = math.hypot(x - ax - t * dx, y - ay - t * dy)
            if best is None or d < best[0]:
                best = (d, so_far + t * length)
            so_far += length
        return best[1]

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
    """A cavern underground, round with a domed roof; or (given half its
    width w and depth d) a room in a building, square-cornered with a flat
    ceiling; or (indoor, with no w and d) a round room, as in the tower.
    Either way it has a flat floor, and being in it is being in its place."""

    def __init__(self, place, floor, r, tall, ground, wall, light=None, glow=0.0, w=None, d=None, at=None,
                 indoor=False):
        self.place = place
        self.x, self.y = at or P[place]  # (a room can be off its place's spot, to sit against its neighbour)
        self.floor, self.tall = floor, tall
        self.w, self.d = w, d
        self.room = w is not None  # square-cornered
        self.indoor = indoor or self.room  # in a building: walls, a ceiling, and the light of indoors
        self.r = math.hypot(w, d) if self.room else r  # how far it reaches, at most
        self.ground, self.wall = ground, wall  # colours
        self.light, self.glow = light, glow  # its own light, if it has one

    @property
    def doorway(self):
        """How far past its wall a way's walls stop, and its door frame
        stands: just outside a room's wall, and half a metre on into a cave
        (in front of its lumpy wall, so there's nothing to see behind the
        frame)."""
        return 0.3 if self.indoor else -0.5

    def inside(self, x, y, margin=0.0):
        if self.room:
            return abs(x - self.x) < self.w + margin and abs(y - self.y) < self.d + margin
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
    # The castle's rooms, in the keep (and the coach house, in the courtyard).
    Hall("grand-hall", 0.4, 0, 9, c.linear("#c9bca0"), c.linear("#a89d88"), "#ffcf87", 16, w=10, d=8),
    Hall("wizards-kitchen", 0.4, 0, 6, c.linear("#b3a58a"), c.linear("#9a8e78"), "#ff9a4a", 10, w=7, d=6,
         at=(P["grand-hall"][0] - 10 - 1 - 7, P["grand-hall"][1])),
    Hall("dungeon", -3, 0, 6, c.linear("#5c5850"), c.linear("#6c675c"), "#a9c6ff", 7, w=7, d=7),
    Hall("small-room", 0.4, 0, 4.5, c.linear("#7a4a2a"), c.linear("#8e2a26"), "#ffb070", 6, w=6, d=6),
    Hall("merlins-lair", 0.4, 0, 8, c.linear("#6f6a62"), c.linear("#5d5868"), "#b8ff9a", 18, w=14.5, d=14,
         at=((P["grand-hall"][0] - 6 + P["small-room"][0] - 6 - 1) / 2, P["grand-hall"][1] - 8 - 1 - 14)),
    Hall("coach-house", 0.4, 0, 6, c.linear("#b89a5a"), c.linear("#8a6a44"), "#ffd28a", 9, w=8, d=6),
    # Out in the land, on the ground where they stand (their floors are set
    # once the land's shape is known): the charcoal burner's hut, lit by its
    # fire, and the round room in the tower, just inside its wall.
    Hall("charcoal-hut", 0, 0, 3.8, c.linear("#5e4a36"), c.linear("#6e5236"), "#ffb878", 1.2, w=3.4, d=2.4),
    Hall("tower", 0, TOWER_R - 0.8, 6, c.linear("#8d8a80"), c.linear("#807d76"), "#ffd9a0", 3, at=TOWER, indoor=True),
]}

T, O, G, DM = P["trolls"], P["oak-door"], P["giant"], P["damp-tunnels"]
TR, MZ, DK, BC = P["treasure-room"], P["maze"], P["dark-tunnels"], P["beautiful-chamber"]
GH, WK, DU = P["grand-hall"], P["wizards-kitchen"], P["dungeon"]
SR, ML, CH = P["small-room"], P["merlins-lair"], P["coach-house"]
KEEP_NORTH = P["courtyard"][1] - 16  # the keep's front, across the south of the courtyard
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
    # The castle: in at the keep's door to the grand hall, and on: straight
    # through into the kitchen, east along the corridor and down the steps to
    # the dungeon, south and up again to the small room, through the door
    # that locks behind you into Merlin's lair, and through the hidden door
    # back into the hall. (Rooms side by side still have a short way between
    # them: the doorway through the wall.)
    "keep-door": Way([(GH[0], KEEP_NORTH + 1.2, None), (*GH, 0.4)], indoor=True),
    "hall-kitchen": Way([(*GH, 0.4), (HALLS["wizards-kitchen"].x, GH[1], 0.4)], indoor=True),
    "hall-dungeon": Way([(*GH, 0.4), (GH[0] + 13, GH[1], 0.4), (DU[0] - 9, DU[1], -3), (*DU, -3)], indoor=True),
    "dungeon-small": Way([(*DU, -3), (DU[0], DU[1] - 9, -3), (SR[0], SR[1] + 9, 0.4), (*SR, 0.4)], indoor=True),
    "small-lair": Way([(*SR, 0.4), (SR[0] - 14, SR[1], 0.4)], indoor=True),
    "lair-hall": Way([(GH[0], HALLS["merlins-lair"].y, 0.4), (*GH, 0.4)], indoor=True),
    # And in through the coach house's wide doors.
    "coach-door": Way([(CH[0] - HALLS["coach-house"].w - 1.8, CH[1], None), (*CH, 0.4)], half=2.4, indoor=True),
    # In at the tower's door, and the hut's.
    "tower-door": Way([(*TOWER_LIP, None), (*TOWER, None)], half=1.3, indoor=True),
    "hut-door": Way([(*HUT_LIP, None), (*HUT, None)], half=1.2, indoor=True),
}

# ---------------------------------------------------------------- the shape of the land

MOUND = Vector((P["grassy-bank"][0] - 9, P["grassy-bank"][1] + 9))  # between the west and north paths
CASTLE = (-62 * K, 62 * K, -262 * K, -142 * K)  # its walls: west, east, south, north
MOAT = (-72 * K, 72 * K, -272 * K, -130 * K)
KEEP = (CASTLE[0] + 1, CASTLE[1] - 1, CASTLE[2] + 1, KEEP_NORTH)  # west, east, south, north


def in_building(x, y, whole=False):
    """Inside the keep or the coach house, where you only ever are along a way.
    (Or, whole, for the ground's square at x, y: the hut and the tower stand
    on the land, so only squares wholly inside them are cut out, not ones
    reaching out past their walls.)"""
    w, e, s, n = KEEP
    if w <= x <= e and s <= y <= n:
        return True
    coach = HALLS["coach-house"]
    if abs(x - coach.x) <= coach.w + 0.6 and abs(y - coach.y) <= coach.d + 0.6:
        return True
    reach = STEP / 2 if whole else 0.0
    if abs(x - HUT[0]) <= 4 - reach and abs(y - HUT[1]) <= 3 - reach:
        return True
    return math.hypot(x - TOWER[0], y - TOWER[1]) <= TOWER_R - reach * math.sqrt(2)


def by_a_building(x, y, margin=3.0):
    """Too near a building for a tree: its branches would come through the walls."""
    return any(in_building(x + dx, y + dy) for dx in (-margin, 0, margin) for dy in (-margin, 0, margin))


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
for place, door in (("tower", "tower-door"), ("charcoal-hut", "hut-door")):
    # A step up from the ground in the middle (so the hillside never shows
    # through the floor), with the doorway rising gently to it.
    way = WAYS[door]
    HALLS[place].floor = way.points[-1][2] + 0.2
    way.points[-1] = (*way.points[-1][:2], HALLS[place].floor)
    way.segments = list(zip(way.points, way.points[1:]))


def deck(x, y):
    """The bridge and drawbridge, for walking on."""
    if abs(x - BRIDGE[0]) <= 2.2 and abs(y - BRIDGE[1]) <= BRIDGE_HALF:
        return 0.9
    if abs(x) <= 3 and -143 * K <= y <= -127 * K:
        return 0.6
    return None


def open_to_the_sky(x, y, margin):
    """Over a ramp or a mouth into a way, where there's no earth over it:
    the ground has a hole here. Gives the floor's height there, or None."""
    for way in WAYS.values():
        if way.indoor or not way.near(x, y, way.half + margin):
            continue  # (a building's floor is cut out of the land already)
        d, floor, beyond = way.nearest(x, y)
        if not beyond and d < way.half + margin and floor + TUNNEL_TALL > height(x, y) - 0.4:
            if way.roofed and way.roofed[0] <= way.along(x, y) <= way.roofed[1]:
                continue  # (between its mouths, under its roof)
            return floor
    return None


def over_an_opening(x, y):
    """Whether a spot is over (or nearly) the open part of a ramp, or just
    past its lintel, where the earth over the roof still lies under the
    ground's hole."""
    for way in WAYS.values():
        if way.indoor or not way.near(x, y, way.half + 0.3):
            continue
        d, _, beyond = way.nearest(x, y)
        if beyond or d >= way.half + 0.3:
            continue
        if way.roofed is None:
            return True
        # (Past the lintel at a mouth: an end deep underground has none.)
        start, end = way.roofed
        a = way.along(x, y)
        if (start > 0 and a < start + 0.3) or (end < way.length and a > end - 0.3):
            return True
    return False


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
    return path_lines.distance(x, y) < 5.5 or river.distance(x, y) < BANK or in_moat(x, y)


def walkable(x, y):
    """Where you can stand: open ground that isn't water, or a bridge."""
    if deck(x, y) is not None:
        return True
    if river.distance(x, y) < SHORE or in_moat(x, y):
        return False
    floor = open_to_the_sky(x, y, 2.0)
    if floor is not None and floor < height(x, y) - 0.35:
        return False  # over the ramp: you go in at the top
    return open_ground(x, y) and not rocky(x, y) and not in_building(x, y)


# ---------------------------------------------------------------- the ground


def drawn_height(x, y):
    """The ground's height as drawn: flat triangles between the grid's points
    (whichever way each square is split), so a little under height()."""
    fi, fj = (x - X0) / STEP, (y - Y0) / STEP
    i, j = math.floor(fi), math.floor(fj)
    fx, fy = fi - i, fj - j
    x0, y0 = X0 + i * STEP, Y0 + j * STEP
    h00, h10 = height(x0, y0), height(x0 + STEP, y0)
    h01, h11 = height(x0, y0 + STEP), height(x0 + STEP, y0 + STEP)
    if fx > fy:
        a = h00 + fx * (h10 - h00) + fy * (h11 - h10)
    else:
        a = h00 + fy * (h01 - h00) + fx * (h11 - h01)
    if fx + fy < 1:
        b = h00 + fx * (h10 - h00) + fy * (h01 - h00)
    else:
        b = h11 + (1 - fx) * (h01 - h11) + (1 - fy) * (h10 - h11)
    return min(a, b)


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
        qx, qy = X0 + (i + 0.5) * STEP, Y0 + (j + 0.5) * STEP
        # The hole over a ramp (a square with its middle by the ramp, or any
        # of it over the opening: by the lintel, a square can reach back
        # over it from beyond), or the floor of a building.
        if open_to_the_sky(qx, qy, 1.0) is not None or in_building(qx, qy, whole=True) \
                or any(over_an_opening(qx + STEP * u / 8, qy + STEP * v / 8)
                       for u in range(-4, 5) for v in range(-4, 5)):
            continue
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
            # (Wound to face up: facing down, the sun's shadows fall on the
            # path in stripes.)
            a = (i - 1) * 2
            faces.append((a, a + 2, a + 3, a + 1))
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
    builder.add(v, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (0, 3, 2, 1)], shade)
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
        if open_ground(x, y) or open_to_the_sky(x, y, 4.5) is not None or rocky(x, y) or by_a_building(x, y):
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
# The river: one ribbon, its sides joined round the bends (separate pieces
# leave wedges of riverbed showing between them), reaching in under the
# banks (which come up out of the water at BANK).
verts, faces = [], []
for k, (x, y) in enumerate(RIVER):
    (ax, ay), (bx, by) = RIVER[max(k - 1, 0)], RIVER[min(k + 1, len(RIVER) - 1)]
    dd = math.hypot(bx - ax, by - ay) or 1
    ox, oy = -(by - ay) / dd * 9.5, (bx - ax) / dd * 9.5
    verts += [(x + ox, y + oy, -1), (x - ox, y - oy, -1)]
    if k:
        a = (k - 1) * 2
        faces.append((a, a + 2, a + 3, a + 1))
water.add(verts, faces, [WATER] * len(verts))
# The moat: a ring round the castle (not a sheet under it, where the dungeon is).
mw, me, ms, mn = MOAT
iw, ie, is_, in_ = CASTLE[0] - 2, CASTLE[1] + 2, CASTLE[2] - 2, CASTLE[3] + 2
for x0, y0, x1, y1 in ((mw, in_, me, mn), (mw, ms, me, is_), (mw, is_, iw, in_), (ie, is_, me, in_)):
    water.add([(x0, y0, -1), (x1, y0, -1), (x1, y1, -1), (x0, y1, -1)], [(0, 1, 2, 3)], [WATER] * 4)
water.build("water", smooth=False)

# ---------------------------------------------------------------- built things

built = c.Builder()

# The forest bridge and the drawbridge.
block(built, BRIDGE[0] - 2.4, BRIDGE[1] - BRIDGE_HALF, 0.5, BRIDGE[0] + 2.4, BRIDGE[1] + BRIDGE_HALF, 0.9,
      c.linear("#8a5a33"), solid=False)
for side in (-1, 1):
    block(built, BRIDGE[0] + side * 2.4 - 0.15, BRIDGE[1] - BRIDGE_HALF, 0.9, BRIDGE[0] + side * 2.4 + 0.15,
          BRIDGE[1] + BRIDGE_HALF, 1.9,
          c.linear("#6b4426"))
block(built, -3, -143 * K, 0.2, 3, -127 * K, 0.6, c.linear("#7a5230"), solid=False)
# The drawbridge is up: over the middle of the water, so its far half (where
# you can walk out of the courtyard) is only on the bridge.
obstacle(["moat south"], "box", 0, -(MOAT[3] + CASTLE[3] + 2) / 2, 3.2, 1.5)

# The old stone wall: north from the forest, west along the gate, north again.
WALL = 4.5
WX, WY = -100 * K, 60 * K  # the corner by the old stone wall, and the gate's line
y = -18 * K
while y < WY:
    block(built, WX - 0.6, y, height(WX, y) - 0.5, WX + 0.6, min(y + 2, WY + 0.6), height(WX, y) + WALL, STONE,
          solid=False)
    y += 2
# Between the old wall and the old stone wall, it's too high to climb without the ladder.
obstacle(["old-wall east", "old-stone-wall west"], "box", WX, -(-18 * K + WY + 0.6) / 2, 0.6, (WY + 0.6 + 18 * K) / 2)
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
# Its round wall, with a door in the south side (the doorway's own walls and
# roof line the gap), and its flat top and roof.
SIDES = 24
tz0, tz1 = height(*TOWER) - 0.5, height(*TOWER) - 0.5 + 20
door_top = HALLS["tower"].floor + TUNNEL_TALL - 0.3  # under the doorway's roof (which slopes down a little), so there's no gap
ring = [(TOWER[0] + math.cos(-math.pi / 2 + 2 * math.pi * k / SIDES) * TOWER_R,
         TOWER[1] + math.sin(-math.pi / 2 + 2 * math.pi * k / SIDES) * TOWER_R) for k in range(SIDES)]
for k in range(SIDES):
    p0, p1 = ring[k], ring[(k + 1) % SIDES]
    door = k in (0, SIDES - 1)  # the two sides either side of due south
    built.add([(*p0, door_top if door else tz0), (*p1, door_top if door else tz0), (*p1, tz1), (*p0, tz1)],
              [(0, 1, 2, 3)], [c.vary(GREY, 0.06, Vector((*p0, 1.0)))] * 4)
built.add([(*p, tz1) for p in ring], [tuple(range(SIDES))], [GREY] * SIDES)
built.cone((*TOWER, tz1), 9, TOWER_R * 1.15, ROOF, sides=SIDES, droop=0)
solid_circle(*TOWER, TOWER_R)
fl = HALLS["tower"].floor
block(built, TOWER[0] - 1.6, TOWER[1] - TOWER_R - 0.2, fl - 0.6, TOWER[0] + 1.6, TOWER[1] - TOWER_R + 0.6, fl - 0.02,
      STONE, solid=False)  # the sill under the door
block(built, TOWER[0] + 6, TOWER[1] - 2, height(*TOWER) + 11, TOWER[0] + 8.5, TOWER[1] + 2, height(*TOWER) + 11.5, GREY, solid=False)
for k in range(6):
    sy = P["mossy-steps"][1] + 18 + k * 1.4
    block(built, TOWER[0] - 2, sy, height(TOWER[0], sy) - 0.4, TOWER[0] + 2, sy + 1.4, height(TOWER[0], sy) + 0.15,
          c.linear("#7f8f6a"), solid=False)
# The snake, coiled at the top of the steps (and the stone that shuts you in,
# from inside), and the balcony, too high to reach from the ground under it.
# (The snake reaches out from just inside the wall, so its far side is in the
# tower, where you can't be on the land; the stone is in the doorway, so
# indoors, for the way out.)
obstacle(["mossy-steps north"], "box", TOWER[0], -(TOWER[1] - TOWER_R + 1), 3.0, 0.8)
obstacle(["tower south"], "box", TOWER[0], -(TOWER[1] - TOWER_R - 0.6), 1.6, 0.5, under=True)
obstacle(["mossy-steps east"], "box", TOWER[0] + 9.5, -TOWER[1], 0.6, 2.5)

# The witches, on the way west to the crossroads.
wx, wy = P["forest-witches"]
obstacle(["forest-witches west"], "box", (wx + P["forest-crossroads"][0]) / 2, -wy, 1.0, 5.5)

# The charcoal burner's hut, its door facing north to the crossroads.
hx, hy = HUT
HUT_WALL = c.linear("#7a5b3e")
hz0, hz1 = height(hx, hy) - 0.3, HALLS["charcoal-hut"].floor + 4.2
gap = 1.2 + 0.1
block(built, hx - 4, hy - 3, hz0, hx + 4, hy - 2.5, hz1, HUT_WALL, solid=False)
block(built, hx - 4, hy - 3, hz0, hx - 3.5, hy + 3, hz1, HUT_WALL, solid=False)
block(built, hx + 3.5, hy - 3, hz0, hx + 4, hy + 3, hz1, HUT_WALL, solid=False)
block(built, hx - 4, hy + 2.5, hz0, hx - gap, hy + 3, hz1, HUT_WALL, solid=False)
block(built, hx + gap, hy + 2.5, hz0, hx + 4, hy + 3, hz1, HUT_WALL, solid=False)
block(built, hx - gap, hy + 2.5, HALLS["charcoal-hut"].floor + TUNNEL_TALL - 0.3, hx + gap, hy + 3, hz1, HUT_WALL,
      solid=False)  # over the door, down to the doorway's roof
built.cone((hx, hy, hz1), 3, 5.5, c.linear("#5d4630"), sides=4, droop=0)
# A sill under the door, where the doorway's floor meets the room's (over
# the hole in the ground the hut stands in).
fl = HALLS["charcoal-hut"].floor
block(built, hx - gap, hy + 2.3, fl - 0.6, hx + gap, hy + 3.2, fl - 0.02, STONE, solid=False)
solid_box(hx, hy, 4, 3)

# The cave entrance's mound, and the pile of leaves filling the mouth of the
# dragon's cave, just inside.
ce = P["cave-entrance"]
built.blob((ce[0] + 3, ce[1] + 8, height(*ce)), 7, ROCK, squash=0.55, lumpy=0.25, seed=1)
solid_circle(ce[0] + 3, ce[1] + 8, 6)
lx, ly = DRAGON_LIP[0] + 3, DRAGON_LIP[1]
built.blob((lx, ly, WAYS["dragon-mouth"].nearest(lx, ly)[1] + 0.2), 2.6, LEAVES, squash=0.55, lumpy=0.35, seed=2)

# The tunnels' mouths are obstacles on the land, 3 m down the ramp (where the
# leaves are), reaching out over the top so you're stopped (and told why)
# before you go down: the leaves, and the lamp tunnel's two mouths, too dark
# to go in without the lamp.
obstacle(["cave-entrance east"], "box", lx, -ly, 1.0, TUNNEL_HALF + 0.3)
obstacle(["old-wall west"], "box", WEST_LIP[0] - 3, -WEST_LIP[1], 1.0, TUNNEL_HALF + 0.3)
obstacle(["cave-entrance south"], "box", EAST_LIP[0], -(EAST_LIP[1] - 3), TUNNEL_HALF + 0.3, 1.0)

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
# Where the river goes under (clear of the beautiful chamber, down below).
built.blob((RIVER[-1][0] + 5, RIVER[-1][1] + 3, -1.5), 9, ROCK, squash=0.7, lumpy=0.3, seed=4)

# The castle: walls with a gate to the north, and corner towers.
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
# The keep across the south of the courtyard, with its door to the grand
# hall; the golden spire rises from the hall, through the roof. All of the
# castle's other rooms are inside it.
KEEP_TALL = 12
kw, ke, ks, kn = KEEP
door = TUNNEL_HALF + 0.1
for x0, x1 in ((kw, GH[0] - door), (GH[0] + door, ke)):
    block(built, x0, kn - 1, 0, x1, kn, KEEP_TALL, GREY, solid=False)
block(built, GH[0] - door, kn - 1, TUNNEL_TALL + 0.4, GH[0] + door, kn, KEEP_TALL, GREY, solid=False)
block(built, kw, ks, 0, ke, ks + 1, KEEP_TALL, GREY, solid=False)
block(built, kw, ks, 0, kw + 1, kn, KEEP_TALL, GREY, solid=False)
block(built, ke - 1, ks, 0, ke, kn, KEEP_TALL, GREY, solid=False)
block(built, kw, ks, KEEP_TALL - 0.4, ke, kn, KEEP_TALL, c.linear("#8d8a80"), solid=False)
x = kw
while x < ke - 1:
    block(built, x, kn - 1, KEEP_TALL, x + 1, kn, KEEP_TALL + 1, GREY, solid=False)  # battlements
    x += 2
gx, gy = GH
built.cylinder((gx, gy - 6, KEEP_TALL - 0.5), (gx, gy - 6, 32), 4, 3.6, GREY, sides=14)
built.cone((gx, gy - 6, 32), 16, 4.6, GOLD, sides=12, droop=0)
kitchen = HALLS["wizards-kitchen"]
block(built, kitchen.x - kitchen.w, kitchen.y - 1, KEEP_TALL - 0.5, kitchen.x - kitchen.w + 2, kitchen.y + 1, KEEP_TALL + 4,
      ROCK, solid=False)  # the chimney, over the hearth

# The coach house: a barn in the courtyard, its wide doors facing west.
coach = HALLS["coach-house"]
cw0, cw1, cd0, cd1 = coach.x - coach.w - 0.6, coach.x + coach.w + 0.6, coach.y - coach.d - 0.6, coach.y + coach.d + 0.6
BARN = c.linear("#7a5634")
wide = 2.4 + 0.1
block(built, cw0, cd0, 0, cw1, cd0 + 0.5, 6.8, BARN, solid=False)
block(built, cw0, cd1 - 0.5, 0, cw1, cd1, 6.8, BARN, solid=False)
block(built, cw1 - 0.5, cd0, 0, cw1, cd1, 6.8, BARN, solid=False)
block(built, cw0, cd0, 0, cw0 + 0.5, coach.y - wide, 6.8, BARN, solid=False)
block(built, cw0, coach.y + wide, 0, cw0 + 0.5, cd1, 6.8, BARN, solid=False)
block(built, cw0, coach.y - wide, TUNNEL_TALL + 0.4, cw0 + 0.5, coach.y + wide, 6.8, BARN, solid=False)
built.cone((coach.x, coach.y, 6.8), 4.5, max(coach.w, coach.d) * 1.5, c.linear("#9a4c32"), sides=4, droop=0)

# The well, and flowers along the walls.
cx, cy = P["courtyard"]
tower(built, cx + 4, cy - 2, 1.2, 1.0, STONE)
block(built, cx + 3.1, cy - 2.1, 1.4, cx + 3.3, cy - 1.9, 3.2, c.linear("#5e3b1f"), solid=False)
block(built, cx + 4.7, cy - 2.1, 1.4, cx + 4.9, cy - 1.9, 3.2, c.linear("#5e3b1f"), solid=False)
built.cone((cx + 4, cy - 2, 3.1), 1.0, 1.7, c.linear("#8a4a2e"), sides=4, droop=0)
for k, (fx, fy) in enumerate([(CASTLE[0] + 3, cy + 8), (CASTLE[0] + 3, cy - 4), (CASTLE[0] + 3, KEEP_NORTH + 3),
                              (-12, CASTLE[3] - 3), (12, CASTLE[3] - 3), (-24, CASTLE[3] - 3), (-8, KEEP_NORTH + 2.5)]):
    built.blob((fx, fy, 0.5), 1.6, c.linear("#4e7a34"), squash=0.5, lumpy=0.3, seed=20 + k)
    for m in range(5):
        a = m * 1.3 + k
        built.blob((fx + math.cos(a) * 1.0, fy + math.sin(a) * 0.9, 1.1), 0.35, c.linear(["#e0607e", "#f2a3b8", "#fff1c8"][m % 3]),
                   squash=0.8, lumpy=0.2, seed=k * 5 + m, subdivisions=1)

built.build("built", smooth=False)

# ---------------------------------------------------------------- underground

EARTH = c.linear("#5a4632")
TUNNEL_STONE = c.linear("#7d7568")
FLAME = c.linear("#ffb347")
IRON = c.linear("#2b2a2c")
OAK = c.linear("#5e3b1f")
GOLD_STONE = c.linear("#c9a25a")
PIT_DARK = c.linear("#100b08")
CORRIDOR_FLOOR = c.linear("#9a917f")
CORRIDOR_WALL = c.linear("#8f8878")

# What's solid underground, apart from the ways' and the halls' own walls.
under_circles, under_boxes = [], []


# (Given its top, a thing low enough to climb onto: you can stand on it.)
def under_circle(x, y, r, top=None):
    under_circles.append([round(x, 2), round(-y, 2), round(r, 2)] + ([round(top, 2)] if top is not None else []))


def under_box(x, y, half_x, half_y, top=None):
    under_boxes.append([round(x, 2), round(-y, 2), round(half_x, 2), round(half_y, 2)]
                       + ([round(top, 2)] if top is not None else []))


def in_a_hall(x, y, floor, margin=0.0):
    """The hall a spot is in, on that floor, if any."""
    for hall in HALLS.values():
        if abs(hall.floor - floor) < 1.5 and hall.inside(x, y, margin):
            return hall
    return None


def earth_wall(e0, e1, bottom0, bottom1):
    """A wall of earth from a roof's edge up to just under the ground (as it's
    drawn, so it never shows through on a slope), in pieces a metre long."""
    n = max(1, math.ceil(math.dist(e0, e1)))
    for k in range(n):
        f0, f1 = k / n, (k + 1) / n
        p0 = (e0[0] + (e1[0] - e0[0]) * f0, e0[1] + (e1[1] - e0[1]) * f0)
        p1 = (e0[0] + (e1[0] - e0[0]) * f1, e0[1] + (e1[1] - e0[1]) * f1)
        b0, b1 = bottom0 + (bottom1 - bottom0) * f0, bottom0 + (bottom1 - bottom0) * f1
        t0, t1 = drawn_height(*p0) - 0.05, drawn_height(*p1) - 0.05
        if t0 > b0 or t1 > b1:
            quad(tunnel, [(*p0, b0), (*p1, b1), (*p1, max(t1, b1)), (*p0, max(t0, b0))], EARTH)


def quad(builder, pts, colour, vary=0.12):
    # Anything lying flat faces up: facing down, the sun's shadows fall on it
    # in stripes ("shadow acne").
    (ax, ay, az), (bx, by, bz), (cx_, cy_, cz) = pts[0], pts[1], pts[2]
    ux, uy, uz, vx, vy, vz = bx - ax, by - ay, bz - az, cx_ - ax, cy_ - ay, cz - az
    nz = ux * vy - uy * vx
    if nz < 0 and abs(nz) > 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + nz * nz):
        pts = pts[::-1]
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
# half its size across and along. At the far end, by the treasure room, so
# its reach doesn't come back into the maze: you only meet it once you've
# gone into the tunnel, not while you're finding your way round.
PIT = (MZ[0], MZ[1] + MAZE_HALF + 7.5, TUNNEL_HALF + 0.4, 1.5)


def in_pit(x, y):
    px, py, hx, hy = PIT
    return abs(x - px) <= hx and abs(y - py) <= hy


# The ways: floor, walls and roof, stone walls up the ramps, a lip of stone
# round the hole, and a lintel where the roof begins. Inside a hall, the
# hall's own floor and walls take over, with a door frame where they meet.
tunnel = c.Builder()
DROPS = []  # (cave, and the two sides of where a way drops away out of it)
for way in WAYS.values():
    half = way.half
    # The way's two edges, as lines meeting exactly at every bend (mitred,
    # like the corner of a picture frame), so the floor never folds over
    # itself on the inside of a bend (the fold flickers).
    pts = way.points
    seg_normals = []
    for (ax, ay, _), (bx, by, _) in zip(pts, pts[1:]):
        d = math.hypot(bx - ax, by - ay) or 1
        seg_normals.append((-(by - ay) / d, (bx - ax) / d))
    corners = []
    for i, (x, y, _) in enumerate(pts):
        n1 = seg_normals[max(i - 1, 0)]
        n2 = seg_normals[min(i, len(seg_normals) - 1)]
        mx_, my_ = n1[0] + n2[0], n1[1] + n2[1]
        m = math.hypot(mx_, my_) or 1
        stretch = 1 / max(0.5, (mx_ * n1[0] + my_ * n1[1]) / m)
        corners.append((mx_ / m * stretch, my_ / m * stretch))
    rows, edge_left, edge_right = [], [], []
    for si, ((ax, ay, af), (bx, by, bf)) in enumerate(zip(pts, pts[1:])):
        n = max(1, int(math.hypot(bx - ax, by - ay) / 0.5))
        last = si == len(pts) - 2
        length = math.hypot(bx - ax, by - ay)
        bend = min(2 * half, length)  # how far from a bend its mitre reaches
        for k in range(n + 1 if last else n):
            t = k / n
            x, y, floor = ax + (bx - ax) * t, ay + (by - ay) * t, af + (bf - af) * t
            (c0x, c0y), (c1x, c1y) = corners[si], corners[si + 1]
            sx, sy = seg_normals[si]
            # (Square across the way, but for a bend's mitre, eased in over
            # the last few metres to it: straight on, everything placed
            # across the way meets the walls.)
            w0, w1 = max(0.0, 1 - t * length / bend), max(0.0, 1 - (1 - t) * length / bend)
            for edge, off in ((edge_left, -half), (edge_right, half)):
                edge.append((x + sx * off + ((c0x - sx) * w0 + (c1x - sx) * w1) * off,
                             y + sy * off + ((c0y - sy) * w0 + (c1y - sy) * w1) * off))
            ground = height(x, y)
            covered = way.indoor or floor + TUNNEL_TALL <= ground - 0.4
            nx_, ny_ = seg_normals[si]
            rows.append((x, y, floor, nx_, ny_, covered))
    # Across the way at each row, as its walls go: after a bend, the mitred
    # edges are skewed (one side runs on ahead of the other) all along to the
    # next bend, so everything placed across the way (the lip, the lintel,
    # the earth behind it, door frames) follows the same skew, not the square.
    rows = [(x, y, floor, (rx - x) / half, (ry - y) / half, covered)
            for (x, y, floor, _, _, covered), (rx, ry) in zip(rows, edge_right)]
    # Open to the sky from each mouth until it first goes under cover, and
    # covered from then on (on bumpy ground it would flip back and forth near
    # the lintel, leaving holes in the roof).
    under_cover = [k for k, row in enumerate(rows) if row[5]]
    if under_cover:
        first, last_ = under_cover[0], under_cover[-1]
        rows = [(*row[:5], first <= k <= last_) for k, row in enumerate(rows)]
    # Earth and rough stone underground; flagstones, walls and beams indoors.
    floor_colour, wall_colour = (CORRIDOR_FLOOR, CORRIDOR_WALL) if way.indoor else (EARTH, TUNNEL_STONE)
    roof_colour = c.linear("#5b4632") if way.indoor else c.mix(TUNNEL_STONE, EARTH, 0.5)

    def side(row, offset):
        x, y, _, nx_, ny_, _ = row
        return x + nx_ * offset, y + ny_ * offset

    for k, (a, b) in enumerate(zip(rows, rows[1:])):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        # (Floor, walls and roof go on as far as the doorway: just past a
        # room's wall, or on into a cave, past its lumpy wall. The floor
        # overlaps the hall's own, a doorstep over the seam.)
        hall = in_a_hall(*mid, 0.3)
        if hall and hall.inside(mid[0], mid[1], hall.doorway):
            continue
        (alx, aly), (arx, ary) = edge_left[k], edge_right[k]
        (blx, bly), (brx, bry) = edge_left[k + 1], edge_right[k + 1]
        if not in_pit(mid[0], mid[1]):
            # (Indoors, a shade up: off the ground, out of the door, and the
            # same all the way in, so there's no step at the wall.)
            lift = 0.04 if way.indoor else 0.0
            quad(tunnel, [(alx, aly, a[2] + lift), (arx, ary, a[2] + lift), (brx, bry, b[2] + lift), (blx, bly, b[2] + lift)],
                 floor_colour)
            near = in_a_hall(*mid, 2.0)
            if near:
                # A doorstep: edges down to the hall's floor, so there's no gap
                # under it (a way can still be climbing as it comes in).
                bottom = near.floor - 0.12
                for p0, p1, z0, z1 in (((alx, aly), (blx, bly), a[2], b[2]), ((arx, ary), (brx, bry), a[2], b[2]),
                                       ((alx, aly), (arx, ary), a[2], a[2]), ((blx, bly), (brx, bry), b[2], b[2])):
                    quad(tunnel, [(*p0, z0 + lift), (*p1, z1 + lift), (*p1, min(z1 - 0.12, bottom)), (*p0, min(z0 - 0.12, bottom))],
                         floor_colour)
        # (Up the ramps, the walls stop exactly under the stone lip on top of them.)
        for (ax_, ay_), (bx_, by_) in (((alx, aly), (blx, bly)), ((arx, ary), (brx, bry))):
            # (Where the ramp goes under the lintel, the walls stay up at the
            # ground: sloping down to the roof, they'd leave a gap above them.)
            roofed = a[5] and b[5]
            top_a = a[2] + TUNNEL_TALL if roofed else max(height(ax_, ay_) + 0.32, a[2] + 0.6)
            top_b = b[2] + TUNNEL_TALL if roofed else max(height(bx_, by_) + 0.32, b[2] + 0.6)
            quad(tunnel, [(ax_, ay_, a[2] - 0.1), (bx_, by_, b[2] - 0.1), (bx_, by_, top_b), (ax_, ay_, top_a)], wall_colour)
        if a[5] and b[5]:
            quad(tunnel, [(alx, aly, a[2] + TUNNEL_TALL), (arx, ary, a[2] + TUNNEL_TALL), (brx, bry, b[2] + TUNNEL_TALL),
                          (blx, bly, b[2] + TUNNEL_TALL)], roof_colour)
        if not (a[5] and b[5]):
            # A lip of stone round the hole, hiding its ragged edge (in strips,
            # so it follows the ground even up the crags, never under it).
            for sign in (1, -1):
                across = [sign * (half + 2.4 * t / 4) for t in range(5)]
                for inner, outer in zip(across, across[1:]):
                    pa = [side(a, inner), side(a, outer)]
                    pb = [side(b, outer), side(b, inner)]
                    quad(tunnel, [(*p, height(*p) + 0.32) for p in pa + pb], STONE)
                    # Solid down into the ground at its outer edge and its
                    # ends, so there's nothing to see under it.
                    (ia, oa), (ob, ib) = pa, pb
                    for p0, p1 in ((oa, ob),) * (outer == across[-1]) + ((ia, oa), (ib, ob)):
                        quad(tunnel, [(*p0, height(*p0) + 0.32), (*p1, height(*p1) + 0.32), (*p1, height(*p1) - 0.6),
                                      (*p0, height(*p0) - 0.6)], STONE)
        if a[5] != b[5]:
            # Just behind the lintel, the earth over the roof: from the top of
            # a steep ramp you look down over the roof (it drops away faster
            # than you're looking), so there has to be something there to see.
            # A box of earth: the roof made wide, its sides, and a back.
            inward = 1 if b[5] else -1
            start = k + 1 if b[5] else k
            span = [rows[i] for i in range(start, start + inward * 9, inward) if 0 <= i < len(rows)]
            wide = half + 2.4
            for r0, r1 in zip(span, span[1:]):
                l0, q0, l1_, q1 = side(r0, -wide), side(r0, wide), side(r1, -wide), side(r1, wide)
                quad(tunnel, [(*l0, r0[2] + TUNNEL_TALL + 0.02), (*q0, r0[2] + TUNNEL_TALL + 0.02),
                              (*q1, r1[2] + TUNNEL_TALL + 0.02), (*l1_, r1[2] + TUNNEL_TALL + 0.02)], EARTH)
                for e0, e1 in ((l0, l1_), (q0, q1)):
                    earth_wall(e0, e1, r0[2] + TUNNEL_TALL, r1[2] + TUNNEL_TALL)
            back = span[-1]
            earth_wall(side(back, -wide), side(back, wide), back[2] + TUNNEL_TALL, back[2] + TUNNEL_TALL)
            # The lintel: the face of earth and stone over the opening.
            row = b if b[5] else a
            l1, r1 = side(row, -half - 2.4), side(row, half + 2.4)
            low = row[2] + TUNNEL_TALL
            high = max(height(*l1), height(*r1), height(row[0], row[1])) + 0.8
            quad(tunnel, [(*l1, low), (*r1, low), (*r1, high), (*l1, high)], STONE)
    # Door frames, where the way goes into a hall.
    # (Hung on the walls' own edges: near a bend, they're mitred.)
    for k, (a, b) in enumerate(zip(rows, rows[1:])):
        for hall in HALLS.values():
            m = hall.doorway
            if abs(hall.floor - a[2]) > 1.5 or hall.inside(a[0], a[1], m) == hall.inside(b[0], b[1], m):
                continue
            i = k + 1 if hall.inside(a[0], a[1], m) else k
            row = rows[i]
            f = row[2]
            nx_, ny_ = row[3], row[4]
            # (In a cave, as high as its wall goes before the dome.)
            top = f + TUNNEL_TALL + 0.1 if hall.indoor else hall.floor + max(TUNNEL_TALL + 0.8, hall.tall * 0.5)
            for p, jut in ((edge_right[i], 1.8), (edge_left[i], -1.8)):
                q = (p[0] + nx_ * jut, p[1] + ny_ * jut)
                quad(tunnel, [(*p, f - 0.3), (*q, f - 0.3), (*q, top), (*p, top)], hall.wall)
            if not hall.indoor:
                p, q = edge_left[i], edge_right[i]
                quad(tunnel, [(*p, f + TUNNEL_TALL), (*q, f + TUNNEL_TALL), (*q, top), (*p, top)], hall.wall)
    # Where it drops away steeply out of a cave's doorway: the cave's floor
    # is cut off there (it reaches out under the cave's lumpy wall, and would
    # stick out over the drop, a ledge).
    skipped = []
    for a, b in zip(rows, rows[1:]):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        hall = in_a_hall(*mid, 0.3)
        skipped.append(hall if hall and hall.inside(mid[0], mid[1], hall.doorway) else None)
    for k in range(len(skipped) - 1):
        for inner, outer, step in ((k, k + 1, 1), (k + 1, k, -1)):
            hall = skipped[inner]
            if hall and not hall.indoor and not skipped[outer]:
                on = rows[min(max(k + 1 + step * 4, 0), len(rows) - 1)]  # 2 m on
                if on[2] < hall.floor - 0.5:
                    DROPS.append((hall, edge_left[k + 1], edge_right[k + 1]))
    # A dead end, deep under the land (off into the mist): a metre more of
    # tunnel, and earth across the end of it.
    for row, edges, outward in ((rows[0], (edge_left[0], edge_right[0]), -1), (rows[-1], (edge_left[-1], edge_right[-1]), 1)):
        x, y, f, nx_, ny_, roofed = row
        if way.indoor or not roofed or in_a_hall(x, y, f, 1.3):
            continue
        ox, oy = ny_ * outward, -nx_ * outward
        (lx_, ly_), (rx_, ry_) = edges
        el, er = (lx_ + ox, ly_ + oy), (rx_ + ox, ry_ + oy)
        quad(tunnel, [(lx_, ly_, f), (rx_, ry_, f), (*er, f), (*el, f)], EARTH)
        quad(tunnel, [(lx_, ly_, f + TUNNEL_TALL), (rx_, ry_, f + TUNNEL_TALL), (*er, f + TUNNEL_TALL), (*el, f + TUNNEL_TALL)],
             roof_colour)
        for p, q in (((lx_, ly_), el), ((rx_, ry_), er)):
            quad(tunnel, [(*p, f), (*q, f), (*q, f + TUNNEL_TALL), (*p, f + TUNNEL_TALL)], wall_colour)
        quad(tunnel, [(*el, f), (*er, f), (*er, f + TUNNEL_TALL), (*el, f + TUNNEL_TALL)], EARTH)
# A stone threshold at every mouth onto the land, over the ragged edge of the
# hole in the ground (which comes in whole squares, so it reaches a little
# past where the ramp begins, and shows the sky through the gap).
for way in WAYS.values():
    if way.indoor:
        continue
    for end, nextp in ((way.points[0], way.points[1]), (way.points[-1], way.points[-2])):
        ex, ey, ef = end
        if abs(ef - height(ex, ey)) > 0.6:
            continue  # (an end deep underground, into the mist)
        dx, dy = ex - nextp[0], ey - nextp[1]
        dd = math.hypot(dx, dy) or 1
        dx, dy = dx / dd, dy / dd  # outward, onto the land
        sx, sy = -dy, dx
        reach = way.half + 2.4
        steps = [t / 2 for t in range(0, 7)]  # from the top of the ramp to 3 m out
        across = [reach * (2 * k / 8 - 1) for k in range(9)]
        grid = [[(ex + dx * t + sx * o, ey + dy * t + sy * o) for o in across] for t in steps]
        for i in range(len(steps) - 1):
            for j in range(len(across) - 1):
                pts = [grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]]
                quad(tunnel, [(x, y, height(x, y) + 0.06) for x, y in pts], STONE, 0.1)
        # Its sides, down into the ground; and its edge over the ramp, down to
        # the ramp's floor: seen from below, there's nothing to look under.
        for i in range(len(steps) - 1):
            for j in (0, len(across) - 1):
                (x0, y0), (x1, y1) = grid[i][j], grid[i + 1][j]
                quad(tunnel, [(x0, y0, height(x0, y0) + 0.06), (x1, y1, height(x1, y1) + 0.06), (x1, y1, height(x1, y1) - 0.6),
                              (x0, y0, height(x0, y0) - 0.6)], STONE, 0.1)
        for j in range(len(across) - 1):
            (x0, y0), (x1, y1) = grid[0][j], grid[0][j + 1]
            quad(tunnel, [(x0, y0, height(x0, y0) + 0.06), (x1, y1, height(x1, y1) + 0.06), (x1, y1, ef - 0.3),
                          (x0, y0, ef - 0.3)], STONE, 0.1)
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

def clip(polygon, px, py, tx, ty):
    """The part of a polygon on the near side of the line through px, py
    across the direction tx, ty."""
    side = [(x - px) * tx + (y - py) * ty for x, y in polygon]
    out = []
    for k, (p, s0) in enumerate(zip(polygon, side)):
        q, s1 = polygon[(k + 1) % len(polygon)], side[(k + 1) % len(polygon)]
        if s0 <= 0:
            out.append(p)
        if (s0 < 0) != (s1 < 0) and s0 != s1:
            t = s0 / (s0 - s1)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


# The halls: a floor of squares out under the walls, a lumpy round wall with
# openings where the ways come in, and a dome.
caves = c.Builder()
for hall in HALLS.values():
    if hall.indoor:
        continue  # (below)
    hx, hy, f, R = hall.x, hall.y, hall.floor, hall.r
    step = 1.5
    reach = R + 1.4
    n = int(reach / step) + 1
    drops = [(left, right) for cave, left, right in DROPS if cave is hall]
    for i in range(-n, n):
        for j in range(-n, n):
            x0, y0 = hx + i * step, hy + j * step
            nearest_x, nearest_y = max(x0, min(hx, x0 + step)), max(y0, min(hy, y0 + step))
            if math.hypot(nearest_x - hx, nearest_y - hy) > reach:
                continue
            # (Cut off where a way drops away out of the doorway, along the
            # way's first row of floor, which goes on down from there.)
            square = [(x0, y0), (x0 + step, y0), (x0 + step, y0 + step), (x0, y0 + step)]
            for (lx_, ly_), (rx_, ry_) in drops:
                mx, my = (lx_ + rx_) / 2, (ly_ + ry_) / 2
                across = math.hypot(rx_ - lx_, ry_ - ly_)
                ux, uy = (rx_ - lx_) / across, (ry_ - ly_) / across
                tx, ty = -uy, ux  # out of the cave
                if (hx - mx) * tx + (hy - my) * ty > 0:
                    tx, ty = -tx, -ty
                if abs((x0 + step / 2 - mx) * ux + (y0 + step / 2 - my) * uy) < across / 2 + 1.1:
                    square = clip(square, mx, my, tx, ty)
            if len(square) < 3:
                continue
            colour, vary = hall.ground, 0.12
            if hall.place == "beautiful-chamber":
                colour, vary = (hall.ground if (i + j) % 2 else c.linear("#1d1a1c")), 0.03
            elif hall.place == "treasure-room":
                colour = c.mix(hall.ground, GOLD_STONE, 0.5 if (i + j) % 2 else 0.1)
            elif hall.place == "damp-tunnels" and noise.noise(Vector((x0 / 4, y0 / 4, 9.0))) > 0.15:
                colour = c.linear("#2f3c44")  # puddles
            # (A shade lower than the ways' floors, where they overlap.)
            fl = f - 0.06
            caves.add([(x, y, fl) for x, y in square], [tuple(range(len(square)))],
                      [c.vary(colour, vary, Vector((x0, y0, fl)))] * len(square))

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

# The castle's rooms: a patterned floor out under the walls, walls with a
# darker band at the bottom and doorways where the corridors come in, a
# beamed ceiling, and what's in each room.
rooms = c.Builder()
WOOD = c.linear("#6b4a2c")
DARK_WOOD = c.linear("#4a3220")
RED = c.linear("#9e2b25")
BLUE = c.linear("#2f4f8a")
BRASS = c.linear("#c9a04a")


def floor_colour(hall, i, j, x, y):
    """The colour of a square of floor, and how much it varies."""
    if hall.place in ("grand-hall", "wizards-kitchen", "merlins-lair"):
        return c.mix(hall.ground, c.linear("#ffffff"), 0.08 if (i // 2 + j // 2) % 2 else 0.0), 0.08
    if hall.place == "dungeon":
        straw = noise.noise(Vector((x / 3, y / 3, 11.0))) > 0.2
        return (c.linear("#a88a48") if straw else hall.ground), 0.15
    if hall.place in ("small-room", "coach-house"):
        plank = c.mix(hall.ground, DARK_WOOD, 0.3 if i % 2 else 0.0)  # boards, running north and south
        if hall.place == "coach-house" and noise.noise(Vector((x / 2.5, y / 2.5, 12.0))) > 0.1:
            plank = c.linear("#c9a85a")  # straw
        return plank, 0.06
    return hall.ground, 0.12


def wall_panel(b, x, y, along, f, z0, z1, colour):
    """Something flat on a wall: a banner, a curtain, a bookcase's face. `along`
    is (dx, dy), half its width along the wall."""
    dx, dy = along
    quad(b, [(x - dx, y - dy, z0), (x + dx, y + dy, z0), (x + dx, y + dy, z1), (x - dx, y - dy, z1)], colour, 0.06)


def furniture(b, x0, y0, x1, y1, z0, z1, colour):
    """A solid thing standing on the floor."""
    block(b, x0, y0, z0, x1, y1, z1, colour, solid=False)
    under_box((x0 + x1) / 2, (y0 + y1) / 2, abs(x1 - x0) / 2, abs(y1 - y0) / 2, top=z1)


def flame(b, x, y, z, size=0.35):
    b.cone((x, y, z), size, size * 0.3, FLAME, sides=6, droop=0)


def room(b, hall):
    hx, hy, f, W, D, tall = hall.x, hall.y, hall.floor, hall.w, hall.d, hall.tall
    # The floor reaches just under the walls (and no further: the room next
    # door may be right there).
    fx0, fx1, fy0, fy1 = hx - W - 0.5, hx + W + 0.5, hy - D - 0.5, hy + D + 0.5
    for i in range(-math.ceil(W + 0.5), math.ceil(W + 0.5)):
        for j in range(-math.ceil(D + 0.5), math.ceil(D + 0.5)):
            x0, y0 = max(hx + i, fx0), max(hy + j, fy0)
            x1, y1 = min(hx + i + 1, fx1), min(hy + j + 1, fy1)
            colour, vary = floor_colour(hall, i, j, x0, y0)
            fl = f - 0.06  # (a shade lower than the corridors' floors, where they overlap)
            quad(b, [(x0, y0, fl), (x1, y0, fl), (x1, y1, fl), (x0, y1, fl)], colour, vary)
    E = 0.35
    corners = [(hx - W - E, hy - D - E), (hx + W + E, hy - D - E), (hx + W + E, hy + D + E), (hx - W - E, hy + D + E)]
    band = c.mix(hall.wall, c.linear("#000000"), 0.3)
    for k in range(4):
        (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
        length = math.hypot(bx - ax, by - ay)
        ox, oy = (by - ay) / length, -(bx - ax) / length  # outward
        n = max(1, round(length))
        for m in range(n):
            p0 = (ax + (bx - ax) * m / n, ay + (by - ay) * m / n)
            p1 = (ax + (bx - ax) * (m + 1) / n, ay + (by - ay) * (m + 1) / n)
            mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            if opening(hall, mx + ox * 0.6, my + oy * 0.6):
                # (Down a little over the doorway's roof, which can slope down
                # outward, as to the hut's door.)
                low = f + TUNNEL_TALL - 0.3
                quad(b, [(*p0, low), (*p1, low), (*p1, f + tall), (*p0, f + tall)], hall.wall)
                continue
            quad(b, [(*p0, f - 0.3), (*p1, f - 0.3), (*p1, f + 1.0), (*p0, f + 1.0)], band)
            quad(b, [(*p0, f + 1.0), (*p1, f + 1.0), (*p1, f + tall), (*p0, f + tall)], hall.wall)
    # The ceiling, and beams across it.
    top = f + tall
    quad(b, [(hx - W - E, hy - D - E, top), (hx + W + E, hy - D - E, top), (hx + W + E, hy + D + E, top),
             (hx - W - E, hy + D + E, top)], c.mix(hall.wall, c.linear("#000000"), 0.35), 0.05)
    y = hy - D + 1
    while y < hy + D:
        block(b, hx - W - E, y - 0.2, top - 0.45, hx + W + E, y + 0.2, top, DARK_WOOD, solid=False)
        y += 2.5

    if hall.place == "grand-hall":
        # Two rows of pillars, a long red carpet from door to door with the
        # compass in the middle, banners, and candles.
        for px in (-6.5, 6.5):
            for py in (-5.5, -2.2, 2.2, 5.5):
                b.cylinder((hx + px, hy + py, f), (hx + px, hy + py, top), 0.55, 0.5, c.linear("#bdb39c"), sides=10)
                under_circle(hx + px, hy + py, 0.55)
        # (Things lying on the floor are lifted well clear of it, or they flicker.)
        quad(b, [(hx - 1.4, hy - D - E, f + 0.05), (hx + 1.4, hy - D - E, f + 0.05), (hx + 1.4, hy + D + E, f + 0.05),
                 (hx - 1.4, hy + D + E, f + 0.05)], RED, 0.05)
        for radius, colour, lift in ((2.4, BRASS, 0.1), (1.9, c.linear("#3a3a5a"), 0.15), (0.6, BRASS, 0.2)):
            sides = 24
            verts = [(hx, hy, f + lift)] + [(hx + math.cos(2 * math.pi * k / sides) * radius,
                                              hy + math.sin(2 * math.pi * k / sides) * radius, f + lift) for k in range(sides)]
            b.add(verts, [(0, 1 + k, 1 + (k + 1) % sides) for k in range(sides)], [colour] * len(verts))
        for side, colours in ((-1, (BLUE, RED)), (1, (RED, BLUE))):
            for py, colour in zip((-5, 5), colours):
                wall_panel(b, hx + side * (W + 0.3), hy + py, (0, 0.8), f, f + 3.2, f + 7.2, colour)
        for px in (-5, 5):
            wall_panel(b, hx + px, hy + D + 0.3, (0.8, 0), f, f + 3.2, f + 7.2, RED if px < 0 else BLUE)
        for px, py in ((-3.5, -6.5), (3.5, -6.5), (-3.5, 6.5), (3.5, 6.5)):
            block(b, hx + px - 0.08, hy + py - 0.08, f, hx + px + 0.08, hy + py + 0.08, f + 1.6, BRASS, solid=False)
            flame(b, hx + px, hy + py, f + 1.6)
            under_circle(hx + px, hy + py, 0.25)
    elif hall.place == "wizards-kitchen":
        # The hearth on the west wall with its cauldron, a long table with
        # benches, and a dresser and shelves of pots.
        hw = hx - W
        furniture(b, hw - 0.35, hy - 2.6, hw + 1.2, hy - 2.0, f, f + 2.8, STONE)
        furniture(b, hw - 0.35, hy + 2.0, hw + 1.2, hy + 2.6, f, f + 2.8, STONE)
        block(b, hw - 0.35, hy - 2.6, f + 2.8, hw + 1.3, hy + 2.6, f + 3.4, STONE, solid=False)
        block(b, hw - 0.35, hy - 2.0, f, hw + 1.2, hy + 2.0, f + 0.12, c.linear("#2a1c14"), solid=False)
        under_box(hw + 0.4, hy, 0.8, 2.0)
        for k in range(5):
            flame(b, hw + 0.3 + (k % 2) * 0.3, hy - 1.2 + k * 0.6, f + 0.12, 0.6)
        b.cylinder((hw + 0.6, hy, f + 0.5), (hw + 0.6, hy, f + 1.3), 0.6, 0.7, IRON, sides=12)
        furniture(b, hx - 1.2, hy - 0.6, hx + 2.6, hy + 0.6, f + 0.75, f + 0.9, WOOD)
        for lx in (hx - 1.0, hx + 2.4):
            for ly in (hy - 0.45, hy + 0.45):
                block(b, lx - 0.06, ly - 0.06, f, lx + 0.06, ly + 0.06, f + 0.75, DARK_WOOD, solid=False)
        for by_ in (hy - 1.25, hy + 1.25):
            furniture(b, hx - 1.0, by_ - 0.2, hx + 2.4, by_ + 0.2, f + 0.4, f + 0.5, DARK_WOOD)
        furniture(b, hx - 4, hy + D - 0.6, hx + 1, hy + D + 0.35, f, f + 1.0, WOOD)
        for z in (f + 1.9, f + 2.7):
            block(b, hx - 4, hy + D - 0.1, z, hx + 3, hy + D + 0.35, z + 0.1, WOOD, solid=False)
            for k in range(7):
                px = hx - 3.6 + k * 0.95
                b.cylinder((px, hy + D + 0.12, z + 0.1), (px, hy + D + 0.12, z + 0.45), 0.18, 0.13,
                           c.linear(["#a85f3a", "#c9b38a", "#6a7a4a"][k % 3]), sides=8)
    elif hall.place == "dungeon":
        # Pillars, the old well under a shaft of light, chains, and stone
        # beasts on their plinths in the corners.
        for px in (-3.5, 3.5):
            for py in (-3.5, 3.5):
                b.cylinder((hx + px, hy + py, f), (hx + px, hy + py, top), 0.6, 0.55, c.linear("#7a756a"), sides=8)
                under_circle(hx + px, hy + py, 0.6)
        b.cylinder((hx, hy, f), (hx, hy, f + 0.8), 1.3, 1.3, STONE, sides=16)
        verts = [(hx, hy, f + 0.75)] + [(hx + math.cos(2 * math.pi * k / 16) * 1.25, hy + math.sin(2 * math.pi * k / 16) * 1.25,
                                         f + 0.75) for k in range(16)]
        b.add(verts, [(0, 1 + k, 1 + (k + 1) % 16) for k in range(16)], [c.linear("#0c0a0a")] * 17)
        under_circle(hx, hy, 1.4)
        for a in range(4):
            cxx, cyy = hx + math.cos(a * math.pi / 2 + 0.4) * 1.1, hy + math.sin(a * math.pi / 2 + 0.4) * 1.1
            block(b, cxx - 0.03, cyy - 0.03, f + 0.8, cxx + 0.03, cyy + 0.03, top, IRON, solid=False)
        for px, py in ((-5.6, -5.6), (5.6, -5.6), (-5.6, 5.6), (5.6, 5.6)):
            furniture(b, hx + px - 0.6, hy + py - 0.6, hx + px + 0.6, hy + py + 0.6, f, f + 1.1, STONE)
            b.blob((hx + px, hy + py, f + 1.8), 0.7, c.linear("#8a857a"), squash=1.1, lumpy=0.4, seed=int(px + py * 3))
    elif hall.place == "small-room":
        # A red room: curtains, a rug, and little tables with flowers.
        quad(b, [(hx - 3.2, hy - 2.4, f + 0.05), (hx + 3.2, hy - 2.4, f + 0.05), (hx + 3.2, hy + 2.4, f + 0.05),
                 (hx - 3.2, hy + 2.4, f + 0.05)], c.linear("#b0472c"), 0.05)
        quad(b, [(hx - 2.7, hy - 1.9, f + 0.1), (hx + 2.7, hy - 1.9, f + 0.1), (hx + 2.7, hy + 1.9, f + 0.1),
                 (hx - 2.7, hy + 1.9, f + 0.1)], c.linear("#7a2a2a"), 0.05)
        for py in (-3.5, 3.5):
            furniture(b, hx + W - 0.8, hy + py - 0.45, hx + W + 0.3, hy + py + 0.45, f, f + 0.8, DARK_WOOD)
            b.blob((hx + W - 0.25, hy + py, f + 1.1), 0.35, c.linear("#e06a8a"), squash=0.9, lumpy=0.4, seed=int(py))
        for k in range(8):
            px = hx - W + 0.6 + k * (2 * W - 1.2) / 7
            wall_panel(b, px, hy - D - 0.3, (0.35, 0), f, f, f + 4.4, c.linear("#7e1f1d"))
    elif hall.place == "merlins-lair":
        # The cauldron bubbling green on its round step, on a purple rug;
        # bookcases on every wall (but not across the doors), a table of
        # potions, his desk with the crystal ball, a chart of the stars, and
        # candles.
        dx, dy = hx - 3, hy - 2
        verts = [(dx, dy, f + 0.05)] + [(dx + math.cos(2 * math.pi * k / 24) * 4.2, dy + math.sin(2 * math.pi * k / 24) * 3.4,
                                         f + 0.05) for k in range(24)]
        b.add(verts, [(0, 1 + k, 1 + (k + 1) % 24) for k in range(24)], [c.linear("#4a2a5e")] * 25)
        b.cylinder((dx, dy, f), (dx, dy, f + 0.3), 2.0, 2.0, STONE, sides=20)
        b.cylinder((dx, dy, f + 0.3), (dx, dy, f + 1.3), 1.0, 1.2, IRON, sides=16)
        verts = [(dx, dy, f + 1.25)] + [(dx + math.cos(2 * math.pi * k / 16) * 1.15, dy + math.sin(2 * math.pi * k / 16) * 1.15,
                                         f + 1.25) for k in range(16)]
        b.add(verts, [(0, 1 + k, 1 + (k + 1) % 16) for k in range(16)], [c.linear("#5cff6a")] * 17)
        under_circle(dx, dy, 2.0)

        def bookcase(x0, y0, x1, y1, face):
            """Shelves of books, their spines facing into the room (+x, -x, +y or -y)."""
            furniture(b, x0, y0, x1, y1, f, f + 3.4, DARK_WOOD)
            across = abs(x1 - x0) > abs(y1 - y0)
            length = abs(x1 - x0) if across else abs(y1 - y0)
            for z in (f + 0.5, f + 1.3, f + 2.1, f + 2.9):
                for k in range(int(length / 0.4)):
                    colour = c.linear(["#7a2a2a", "#2a4a7a", "#4a6a2a", "#8a6a2a", "#5a2a6a"][(k * 7 + int(z * 3)) % 5])
                    if across:
                        bx_, by_ = x0 + 0.2 + k * 0.4, (y1 if face == "+y" else y0 - 0.05)
                        block(b, bx_, by_, z, bx_ + 0.3, by_ + 0.05, z + 0.6, colour, solid=False)
                    else:
                        bx_, by_ = (x1 if face == "+x" else x0 - 0.05), y0 + 0.2 + k * 0.4
                        block(b, bx_, by_, z, bx_ + 0.05, by_ + 0.3, z + 0.6, colour, solid=False)

        west, east, south, north = hx - W, hx + W, hy - D, hy + D
        bookcase(west - 0.3, hy - 9, west + 0.5, hy + 9, "+x")
        bookcase(west + 2, south - 0.3, east - 2, south + 0.5, "+y")
        bookcase(east - 0.5, hy - 3, east + 0.3, north - 2, "-x")
        bookcase(east - 10, north - 0.5, east - 2, north + 0.3, "-y")
        bookcase(west + 2, north - 0.5, P["grand-hall"][0] - 2.5, north + 0.3, "-y")  # (up to the hidden door)
        # The desk, and a table of potions.
        furniture(b, hx + 1, north - 2.6, hx + 4, north - 1.6, f + 0.8, f + 0.9, WOOD)
        b.blob((hx + 2.5, north - 2.1, f + 1.15), 0.25, c.linear("#bfe6ff"), squash=1, lumpy=0.05, seed=3)  # crystal ball
        for px in (hx + 1.2, hx + 3.8):
            flame(b, px, north - 1.8, f + 0.9, 0.2)
        tx, ty = hx + 6, hy - 6
        furniture(b, tx - 1.6, ty - 0.6, tx + 1.6, ty + 0.6, f + 0.8, f + 0.9, WOOD)
        for k in range(9):
            b.cylinder((tx - 1.3 + k * 0.32, ty + (k % 3 - 1) * 0.3, f + 0.9), (tx - 1.3 + k * 0.32, ty + (k % 3 - 1) * 0.3, f + 1.25),
                       0.09, 0.05, c.linear(["#5cff6a", "#c45cff", "#5cc4ff", "#ffb35c"][k % 4]), sides=6)
        # The chart of the stars, over the bookcase on the south wall.
        wall_panel(b, hx, south - 0.3 + 0.01, (3, 0), f, f + 4.0, f + 6.8, c.linear("#1a2350"))
        for k in range(30):
            sx = hx - 2.7 + (k * 0.377) % 5.4
            sz = f + 4.2 + (k * 0.613) % 2.4
            wall_panel(b, sx, south - 0.28, (0.05, 0), f, sz, sz + 0.1, c.linear("#fff3b0"))
        # Candles on stands.
        for px, py in ((hx - 9, hy + 4), (hx - 9, hy - 8), (hx + 9, hy + 6), (hx + 2, hy - 10), (hx - 3, hy + 9)):
            block(b, px - 0.08, py - 0.08, f, px + 0.08, py + 0.08, f + 1.6, BRASS, solid=False)
            flame(b, px, py, f + 1.6)
            under_circle(px, py, 0.25)
    elif hall.place == "charcoal-hut":
        # The hearth against the back wall, glowing; a straw bed; sacks of charcoal.
        furniture(b, hx - 1.0, hy - D, hx + 1.0, hy - D + 0.9, f, f + 0.55, STONE)
        for dx in (-0.4, 0.0, 0.4):
            flame(b, hx + dx, hy - D + 0.45, f + 0.55, 0.3)
        furniture(b, hx - W, hy - D + 0.3, hx - W + 1.1, hy + 0.9, f, f + 0.4, c.linear("#c9a85a"))
        for k, (px, py) in enumerate(((hx + W - 0.6, hy - 0.4), (hx + W - 0.7, hy + 0.6))):
            b.blob((px, py, f + 0.35), 0.55, c.linear("#2a2622"), squash=0.8, lumpy=0.3, seed=40 + k)
            under_circle(px, py, 0.5)
    elif hall.place == "coach-house":
        # The red coach on its four wheels, and hay.
        cxx, cyy = hx + 1.5, hy
        furniture(b, cxx - 1.7, cyy - 0.85, cxx + 1.7, cyy + 0.85, f + 0.8, f + 2.3, c.linear("#a5281e"))
        block(b, cxx - 1.9, cyy - 1.0, f + 2.3, cxx + 1.9, cyy + 1.0, f + 2.45, c.linear("#2a1a12"), solid=False)
        for wx in (cxx - 1.1, cxx + 1.1):
            for wy in (cyy - 0.95, cyy + 0.95):
                b.cylinder((wx, wy - 0.06, f + 0.65), (wx, wy + 0.06, f + 0.65), 0.65, 0.65, c.linear("#3a2416"), sides=14)
        for k, (px, py) in enumerate(((hx + W - 1.3, hy - D + 1.3), (hx + W - 1.3, hy + D - 1.3), (hx - 2, hy + D - 1.2))):
            b.blob((px, py, f + 0.4), 1.3, c.linear("#d6b25a"), squash=0.6, lumpy=0.35, seed=30 + k)
            under_circle(px, py, 1.2)
        for px in (hx - 4.5, hx - 3.6):
            b.cylinder((px, hy - D + 0.8, f), (px, hy - D + 0.8, f + 1.1), 0.4, 0.42, WOOD, sides=10)
            under_circle(px, hy - D + 0.8, 0.45)


def round_room(b, hall):
    """A round room: a floor of flagstones in rings, out just under the wall;
    the wall, with a doorway where a way comes in; and a flat ceiling."""
    hx, hy, f, R, tall = hall.x, hall.y, hall.floor, hall.r, hall.tall
    sides = 32
    at = lambda k, r: (hx + math.cos(2 * math.pi * k / sides) * r, hy + math.sin(2 * math.pi * k / sides) * r)
    rings = [0.0, 1.4, 2.8, 4.2, R + 0.5]
    fl = f - 0.06  # (a shade under the doorway's floor, where they overlap)
    for i in range(len(rings) - 1):
        for k in range(sides):
            pts = [at(k, rings[i]), at(k + 1, rings[i]), at(k + 1, rings[i + 1]), at(k, rings[i + 1])]
            quad(b, [(*p, fl) for p in pts], hall.ground, 0.12)
    E = 0.35
    band = c.mix(hall.wall, c.linear("#000000"), 0.3)
    for k in range(sides):
        p0, p1 = at(k, R + E), at(k + 1, R + E)
        mx, my = at(k + 0.5, R + E + 0.6)
        if opening(hall, mx, my):
            # (Down a little over the door frame, which is straight where the
            # wall curves, and the doorway's roof, which slopes down outward.)
            low = f + TUNNEL_TALL - 0.3
            quad(b, [(*p0, low), (*p1, low), (*p1, f + tall), (*p0, f + tall)], hall.wall)
            continue
        quad(b, [(*p0, f - 0.3), (*p1, f - 0.3), (*p1, f + 1.0), (*p0, f + 1.0)], band)
        quad(b, [(*p0, f + 1.0), (*p1, f + 1.0), (*p1, f + tall), (*p0, f + tall)], hall.wall)
    b.add([(*at(k, R + E), f + tall) for k in range(sides)], [tuple(range(sides))],
          [c.mix(hall.wall, c.linear("#000000"), 0.35)] * sides)
    if hall.place == "tower":
        # A chest against the north wall, and stone steps curling up the wall
        # from the west towards the north, to the floor above. (Nothing in the
        # middle: you'd stop there, in the reach of the stone that shuts you in.)
        furniture(b, hx - 0.9, hy + R - 1.0, hx + 0.9, hy + R - 0.3, f, f + 0.7, DARK_WOOD)
        for k in range(6):
            a0, a1 = math.pi - k * 0.2, math.pi - (k + 1) * 0.2
            inner, outer = R - 1.1, R + E + 0.2  # (into the wall, which is straight between its corners)
            pts = [(hx + math.cos(a) * r, hy + math.sin(a) * r) for a, r in ((a0, inner), (a1, inner), (a1, outer), (a0, outer))]
            top = f + 0.35 * (k + 1)
            quad(b, [(*p, top) for p in pts], STONE, 0.08)
            quad(b, [(*pts[0], f), (*pts[1], f), (*pts[1], top), (*pts[0], top)], STONE, 0.08)
            quad(b, [(*pts[1], f), (*pts[2], f), (*pts[2], top), (*pts[1], top)], STONE, 0.08)
            quad(b, [(*pts[3], f), (*pts[0], f), (*pts[0], top), (*pts[3], top)], STONE, 0.08)  # up from the step below
            mid = (a0 + a1) / 2
            under_circle(hx + math.cos(mid) * (R - 0.5), hy + math.sin(mid) * (R - 0.5), 0.6, top=top)


for hall in HALLS.values():
    if hall.room:
        room(rooms, hall)
    elif hall.indoor:
        round_room(rooms, hall)

# The castle's guards and doors, in its corridors.
gh, wk, du, ml = HALLS["grand-hall"], HALLS["wizards-kitchen"], HALLS["dungeon"], HALLS["merlins-lair"]
obstacle(["grand-hall west"], "box", gh.x - gh.w - 0.5, -gh.y, 0.5, TUNNEL_HALF + 0.3, under=True)  # the goblins' trap
obstacle(["wizards-kitchen east"], "box", wk.x + wk.w + 0.5, -gh.y, 0.5, TUNNEL_HALF + 0.3, under=True)  # Merlin
obstacle(["grand-hall east"], "box", gh.x + gh.w + 1.5, -gh.y, 1.0, TUNNEL_HALF + 0.3, under=True)  # the goblins
obstacle(["dungeon south"], "box", du.x, -(du.y - du.d - 1.5), TUNNEL_HALF + 0.3, 1.0, under=True)  # the old woman
# The hidden door into the hall, which looks like wall from the hall's side
# and won't open from there ("You cannot pass."); from the lair, Merlin
# turns you into a frog.
hy_ = gh.y - gh.d - 0.6
block(rooms, gh.x - TUNNEL_HALF, hy_ - 0.15, gh.floor, gh.x + TUNNEL_HALF, hy_ + 0.15, gh.floor + TUNNEL_TALL, gh.wall, solid=False)
obstacle(["grand-hall south", "merlins-lair north"], "box", gh.x, -hy_, TUNNEL_HALF + 0.3, 0.5, under=True)
# The lair's door, which slams and locks behind you.
lx_, ly_ = ml.x + ml.w + 0.6, SR[1]
block(rooms, lx_ - 0.15, ly_ - TUNNEL_HALF, ml.floor, lx_ + 0.15, ly_ + TUNNEL_HALF, ml.floor + TUNNEL_TALL, OAK, solid=False)
obstacle(["merlins-lair east"], "box", lx_, -ly_, 0.5, TUNNEL_HALF + 0.3, under=True)
rooms.build("rooms", smooth=False)

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

# Rocks either side of the mouths. (Their buried halves reach down a long
# way, so they stand clear of where the tunnels run underground.)
rocks = c.Builder()
for x, y, r in ((WEST_LIP[0] - 6, WEST_LIP[1] + 6.5, 4.2), (WEST_LIP[0] - 6, WEST_LIP[1] - 6.5, 4.2),
                (WEST_LIP[0] - 27, WEST_LIP[1] + 2, 6.5), (EAST_LIP[0] - 5, EAST_LIP[1] - 5, 2.8), (EAST_LIP[0] + 5, EAST_LIP[1] - 5, 2.8)):
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
        "ways": {name: {"half": way.half, "points": [[round(x, 2), round(-y, 2), round(f, 2)] for x, y, f in way.points],
                        **({"indoor": True} if way.indoor else {})}
                 for name, way in WAYS.items()},
        # The halls they join: being in one is being in its place.
        "halls": {place: {"x": hall.x, "z": -hall.y, "floor": hall.floor, "r": round(hall.r, 2), "tall": hall.tall,
                          **({"w": hall.w, "d": hall.d} if hall.room else {}),
                          **({"indoor": True} if hall.indoor else {}),
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
