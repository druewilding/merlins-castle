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
import bpy  # noqa: E402
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
# The forest's dead ends, where a path comes into a clearing and goes on as a
# trail, into the trees, to old stones, with a clue on a post among them
# (each clears the forest round it, on the side you come from). Underground,
# the clues are at the tunnels' dead ends (a Way's `clue`).
CLUES = {k: at(v) for k, v in layout["clues"].items() if k != "_"}
DEATHS = {k: at(v) for k, v in layout["deaths"].items() if k != "_"}

X0, X1, Y0, Y1 = (round(v * K) for v in (-200, 200, -290, 260))  # (north, past the mountain, for its far side)
STEP = 2.0

GRASS = c.linear("#7c9f3a")  # (as the grass on it looks, from a little way off: plants.ts)
BUTTERCUPS = c.linear("#a8a83a")  # and where the yellow flowers grow thick
FOREST_FLOOR = c.linear("#3f5f2a")
DIRT = c.linear("#b88754")
ROCK = c.linear("#8a8478")
CRAG = c.linear("#6f6a66")  # the mountain's cliffs, darker
SNOW = c.linear("#f2f4f7")
RIVERBED = c.linear("#55655c")
FLAGS = c.linear("#a39d90")
STONE = c.linear("#9a978a")
WATER = c.linear("#3d7fa8")
GREY = c.linear("#b9b4a8")
ROOF = c.linear("#6d6a78")
GOLD = c.linear("#e8b84a")


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
# Where the way crosses the deep river, it narrows: its rocky banks close in
# (a plank reaches across), for a stretch either side, then it widens again.
NARROWS_X = 0  # its middle (the river runs straight east there, 60 * K south)
NARROWS_HALF = 12  # half its length
NARROWS_EASE = 12  # and how far it takes to widen out again
NARROW = 0.3  # how wide the river is there, of its usual width (its shores 6 m apart)


def narrowing(x, y):
    """How wide the river is here, of its usual width (narrower at the narrows)."""
    return NARROW + (1 - NARROW) * smooth((abs(x - NARROWS_X) - NARROWS_HALF) / NARROWS_EASE)


def from_river(x, y):
    """How far from the river's middle, as if it were its usual width here
    (so its banks, shore and bed all come in where it narrows)."""
    return river.distance(x, y) / narrowing(x, y)

BRIDGE = P["old-wall"][0], -40 * K  # where the path south from the old wall crosses
TOWER = (P["tower"][0], P["tower"][1] + 6)  # on its knoll, north of the mossy steps
TOWER_R = 6
TOWER_LANDING = 5.6  # the top of its stairs, at the window onto the balcony, above its floor
HUT_FIRE = {}  # the fire in the charcoal burner's hut: its middle, and the smoke hole over it (charcoal_hut)
CHEST = {}  # the chest in the tower: where its middle is, and its tray (round_room)
TOWER_WINDOW = (0.9, 2.6)  # the window's sill and lintel, above the landing
# Which way the window and the balcony face (round from due east): to the
# mountain, with the castle's spire off to the right. (A whole number of the
# round room's sides, so its wall opens at its corners.)
TOWER_FACING = -3 * 2 * math.pi / 32
# By the balcony, on its side towards the mossy steps, a little rise in the
# ground for the ladder to stand on: from there, it reaches up to the
# balcony's underside (not quite: it's not hooked over anything, so it
# slips). Not so wide it rises through the tower's floor, but wider than the
# ground's grid (2 m), or there'd be nothing of it.
BALCONY_RISE = (TOWER[0] + math.cos(TOWER_FACING) * 7.9 + math.sin(TOWER_FACING) * 3.3,
                TOWER[1] + math.sin(TOWER_FACING) * 7.9 - math.cos(TOWER_FACING) * 3.3)
# All its windows: which way each faces (round from due east), half its
# width (as an angle), and its sill and lintel above the floor. The big one at
# the top of the stairs, onto the balcony; and two narrow ones, letting a
# little daylight into the dark, clear of the stairs (the north-west one over
# a low step, the south-west one where there are none).
TOWER_WINDOWS = [
    (TOWER_FACING, 2 * math.pi / 32, TOWER_LANDING + TOWER_WINDOW[0], TOWER_LANDING + TOWER_WINDOW[1]),
    (2.3, 0.05, 2.6, 3.9),
    (3.75, 0.05, 2.2, 3.5),
]


def polygon_at(a, r, sides, start):
    """Round the tower's middle, a point at an angle on a regular polygon
    (its corners r out, the first at angle start): its walls are straight
    between their corners."""
    side = math.floor((a - start) / (2 * math.pi / sides))
    middle = start + (side + 0.5) * 2 * math.pi / sides
    d = r * math.cos(math.pi / sides) / math.cos(a - middle)
    return TOWER[0] + math.cos(a) * d, TOWER[1] + math.sin(a) * d


def tower_door():
    """The doorway through the round room's wall, as a window (no wider than
    the doorway: wider, you'd see the doorway's thick sides past it)."""
    return -math.pi / 2, math.asin((WAYS["tower-door"].half + 0.02) / (HALLS["tower"].r + 0.35)), -0.3, TUNNEL_TALL - 0.3


def wall_pieces(p0, p1, a0, a1, low, high, floor, at, openings=TOWER_WINDOWS):
    """A side of the tower's wall, from p0 (at angle a0) to p1 (a1), low to
    high: in pieces round a window in it, if there is one (at: the point on
    the wall at an angle)."""
    for a, half, z0, z1 in openings:
        for turn in (-2 * math.pi, 0, 2 * math.pi):
            lo, hi = a + turn - half, a + turn + half
            if a0 < hi and a1 > lo:
                sill, lintel = floor + z0, floor + z1
                pieces = [[(*p0, low), (*p1, low), (*p1, sill), (*p0, sill)],
                          [(*p0, lintel), (*p1, lintel), (*p1, high), (*p0, high)]]
                for q0, q1 in ([(p0, at(lo))] if a0 < lo - 0.001 else []) + ([(at(hi), p1)] if a1 > hi + 0.001 else []):
                    pieces.append([(*q0, sill), (*q1, sill), (*q1, lintel), (*q0, lintel)])
                return pieces
    return [[(*p0, low), (*p1, low), (*p1, high), (*p0, high)]]
HUT = P["charcoal-hut"]
HUT_R = 4.47  # the hut's round wall of logs, to its outside
# Where you step in at their doors: the tower's faces south, down the mossy
# steps; the hut's north, to the crossroads (just outside its wall: it has
# no doorway, only an opening, so you're in as soon as you're through it).
TOWER_LIP = (TOWER[0], TOWER[1] - TOWER_R - 1.8)
HUT_LIP = (HUT[0], HUT[1] + HUT_R + 0.45)

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

# Straight from place to place, unless something's in the way (an obstacle,
# the castle's walls, the way up the mountain): then windy (below).
STRAIGHT = {"courtyard", "mountain", "maze"}


def windy(line, seed):
    """A path from one place to another, wandering a little from side to side
    as a trodden path does: not at its ends (where it meets the place, and
    other paths, as it did), nor by the river (over its bridge, straight)."""
    (ax, ay), (bx, by) = line
    run = math.hypot(bx - ax, by - ay)
    if run < 12:
        return line
    ux, uy = (bx - ax) / run, (by - ay) / run
    rng = random.Random(f"windy {seed}")
    wide = min(2.0, run * 0.06) * rng.choice((1, -1))
    bends, phase = rng.uniform(1.0, 2.0), rng.uniform(0, math.pi)
    steps = max(2, round(run / 2.5))
    out = []
    for k in range(steps + 1):
        t = k / steps
        px, py = ax + (bx - ax) * t, ay + (by - ay) * t
        free = smooth((from_river(px, py) - BANK - 2) / 8)
        o = wide * free * math.sin(math.pi * t) ** 2 * math.sin(math.pi * bends * t + phase)
        out.append((px - uy * o, py + ux * o))
    return out


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
        shape = SHAPES.get((place, to)) or SHAPES.get((to, place))
        back = world["rooms"][to]["exits"]
        blocked = exit.get("obstacle") or any(e.get("to") == place and e.get("obstacle") for e in back.values())
        if shape or blocked or {place, to} & STRAIGHT:
            paths.append(shape or [P[place], P[to]])
        else:
            paths.append(windy([P[place], P[to]], pair))
# To the brambles, and to Merlin's trap.
for key, spot in {**CLUES, **DEATHS}.items():
    place = key.split(" ")[0]
    if KIND.get(place) != "cave" and key != "mossy-steps east":
        paths.append(windy([P[place], spot], key) if key in CLUES else [P[place], spot])

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
# And down to the water's edge at the narrows, from both sides: trodden, as if
# others had crossed there. (It goes on into the river: stopped where the
# water is, at the edge of its bank.)
paths += [[P["deep-river"], (NARROWS_X, -60 * K)], [P["river-south-bank"], (NARROWS_X, -60 * K)]]

path_lines = Lines()
for line in paths:
    path_lines.add(line)

# From each dead end's clearing, a trail goes on into the trees, wandering,
# little trodden, to something old in a sunlit gap (standing stones, a
# ruined arch), where the clue is hidden among the stones. (Its kind, how far
# it goes past the path's end, and how far it turns off straight on: south
# of the witches, away from the moat's bank.)
LURE_KINDS = {"forest-crossroads west": ("ring", 20, 0), "forest-witches north": ("ruined arch", 10, 0),
              "forest-witches south": ("stones", 16, -0.7)}
GAP = 4.5  # the sunlit gap round what's there
TRAIL_WALK = 1.5  # how far either side of a trail's middle you can walk
LURES = {}  # each dead end's trail on: [(x, y)], and where it ends
trails = Lines()
for key, spot in CLUES.items():
    px, py = P[key.split(" ")[0]]
    ax, ay = spot[0] - px, spot[1] - py
    run = math.hypot(ax, ay)
    _, long, turn = LURE_KINDS[key]
    ax, ay = (ax * math.cos(turn) - ay * math.sin(turn)) / run, (ax * math.sin(turn) + ay * math.cos(turn)) / run
    bend = random.Random(f"lure {key}").choice((1, -1))
    trail = [spot] + [(spot[0] + ax * long * t - ay * o, spot[1] + ay * long * t + ax * o)
                      for t in (0.2, 0.4, 0.6, 0.8, 1.0) for o in [bend * 2.2 * math.sin(t * math.pi * 1.2)]]
    trails.add(trail)
    LURES[key] = trail


def on_a_lure(x, y):
    """Along a trail on from a dead end's clearing, or in the gap at its end."""
    return trails.distance(x, y) < 2.6 or any(math.hypot(x - t[-1][0], y - t[-1][1]) < GAP for t in LURES.values())

# ---------------------------------------------------------------- ways underground

TUNNEL_HALF = 1.7  # half a tunnel's width
TUNNEL_TALL = 3.2  # floor to roof
DEEP = -6.2  # the lamp tunnel's floor, under the meadows (and the river: deep enough for its roof, and the timber props, under the riverbed)
TOP = 30 * K  # the mountain's height, where the maze is: lower when the places are closer, so it's no steeper
CAVE = TOP - 3  # the floor of the caves in the mountain


class Way:
    """A way underground: a line of points, each with its floor's height.
    A floor of None is the ground's height there: a mouth."""

    def __init__(self, points, half=TUNNEL_HALF, indoor=False, open=False, clue=None):
        self.points = points
        self.half = half
        self.clue = clue  # (a dead end at its far end, with this clue: the exit that leads there)
        self.indoor = indoor  # a corridor in a building: walls and a roof all the way
        self.open = open  # (or just a floor, through an opening in a wall: no walls, roof or door frame of its own)
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
                 indoor=False, dark=False):
        self.place = place
        self.x, self.y = at or P[place]  # (a room can be off its place's spot, to sit against its neighbour)
        self.floor, self.tall = floor, tall
        self.w, self.d = w, d
        self.room = w is not None  # square-cornered
        self.indoor = indoor or self.room  # in a building: walls, a ceiling, and the light of indoors
        self.r = math.hypot(w, d) if self.room else r  # how far it reaches, at most
        self.ground, self.wall = ground, wall  # colours
        self.light, self.glow = light, glow  # its own light, if it has one
        # Or (no light of its own) the light coming in, where it does; and
        # dark, without: dim and cold (the tower). And its windows' light.
        self.lights, self.dark, self.windows = [], dark, []

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
ROOM_EDGE = 0.35  # from a room's edge (its w and d) out to its walls
LAIR_FLOOR = -1.6  # Merlin's lair, and the small room beside it
LAIR_STAIRS = 6.0  # from the lair's north wall up to the grand hall's
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
    # Merlin's lair, sunk below the hall, south of it (up a flight of steps to
    # the hidden door in its south wall); and the small room, as low, against
    # the lair's east side, through the door that locks behind you.
    Hall("small-room", LAIR_FLOOR, 0, 4.5, c.linear("#7a4a2a"), c.linear("#8e2a26"), "#ffb070", 6, w=6, d=6,
         at=(P["grand-hall"][0] + 8 + 1 + 6, P["grand-hall"][1] - 8 - 1 - LAIR_STAIRS - 7 - 3)),
    Hall("merlins-lair", LAIR_FLOOR, 0, 6.5, c.linear("#6f6a62"), c.linear("#5e3f7a"), "#cdf5b4", 12, w=8, d=7,
         at=(P["grand-hall"][0], P["grand-hall"][1] - 8 - 1 - LAIR_STAIRS - 7)),
    Hall("coach-house", 0.4, 0, 6, c.linear("#b89a5a"), c.linear("#8a6a44"), "#ffd28a", 9, w=8, d=6),
    # Out in the land, on the ground where they stand (their floors are set
    # once the land's shape is known): the charcoal burner's hut, lit by its
    # fire, and the round room in the tower, just inside its wall (dark and
    # musty, lit only by what comes in: round_room; its floor and wall the
    # mortar between its stones, tower_stones). The hut is round, to the
    # inside of its logs (charcoal_hut).
    Hall("charcoal-hut", 0, HUT_R - 0.33, 3.8, c.linear("#5e4a36"), c.linear("#6e5236"), "#ff9a50", 1.2, indoor=True),
    Hall("tower", 0, TOWER_R - 0.8, 9, c.linear("#2c2a26"), c.linear("#34312c"), at=TOWER, indoor=True, dark=True),
]}

T, O, G, DM = P["trolls"], P["oak-door"], P["giant"], P["damp-tunnels"]
TR, MZ, DK, BC = P["treasure-room"], P["maze"], P["dark-tunnels"], P["beautiful-chamber"]
GH, WK, DU = P["grand-hall"], P["wizards-kitchen"], P["dungeon"]
CH = P["coach-house"]
SR, ML = ((HALLS[place].x, HALLS[place].y) for place in ("small-room", "merlins-lair"))
LAIR_STAIRS_FOOT = ML[1] + HALLS["merlins-lair"].d + 0.3  # (just out through the lair's wall)
LAIR_STAIRS_TOP = GH[1] - HALLS["grand-hall"].d - 1.0  # (just short of the hidden door)
KEEP_NORTH = P["courtyard"][1] - 16  # the keep's front, across the south of the courtyard
MAZE_CELLS, MAZE_CELL = 5, 4.4
MAZE_HALF = MAZE_CELLS * MAZE_CELL / 2  # to the maze's outer wall

# The long way from the dragon's cave up under the ridge into the giant's
# cave, by its east side (and back down again).
DRAGON_TUNNEL = Way([
    (*DC, 0.2),
    (DC[0], DC[1] + 9, 0.2),
    (DC[0] + 2, DC[1] + 40, CAVE * 0.19),
    (DC[0] - 13, DC[1] + 72, CAVE * 0.48),
    (G[0] + 30, G[1] - 28, CAVE * 0.74),
    (G[0] + 20, G[1] - 10, CAVE * 0.94),
    (G[0] + 14, G[1], CAVE),  # (out past its wall, so it comes in straight: a slant left a gap by the doorway)
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
    # The giant's way east, north-east into the ridge, away from the long
    # tunnel (and deep under it, so it comes out nowhere): a dead end.
    "giant-east": Way([(*G, CAVE), (G[0] + 7, G[1] + 10, CAVE), (G[0] + 18, G[1] + 19, CAVE)], clue="giant east"),
    # Into the dragon's hill, past the leaves; and the dragon's way south,
    # down into the dark tunnels, which go on west, east and south.
    "dragon-mouth": Way([(*DRAGON_LIP, None), (DC[0] - 12, DC[1], 0.2), (*DC, 0.2)]),
    "dragon-giant": DRAGON_TUNNEL,
    "dragon-dark": Way([(*DC, 0.2), (DC[0], DC[1] - 10, 0.2), (DK[0], DK[1] + 8, -8), (*DK, -8)]),
    "dark-west": Way([(*DK, -8), (DK[0] - 34, DK[1], -8)], clue="dark-tunnels west"),
    "dark-east": Way([(*DK, -8), (DK[0] + 34, DK[1], -8)], clue="dark-tunnels east"),
    "dark-beautiful": Way([(*DK, -8), (DK[0], DK[1] - 10, -8), (BC[0], BC[1] + 12, -10), (*BC, -10)]),
    # The castle: in at the keep's door to the grand hall, and on: straight
    # through into the kitchen, east along the corridor and down the steps to
    # the dungeon, south and up again, and west, to the small room, through
    # the door that locks behind you into Merlin's lair, and up the stairs
    # through the hidden door back into the hall. (Rooms side by side still have a short way between
    # them: the doorway through the wall.)
    "keep-door": Way([(GH[0], KEEP_NORTH + 1.2, None), (*GH, 0.4)], indoor=True),
    "hall-kitchen": Way([(*GH, 0.4), (HALLS["wizards-kitchen"].x, GH[1], 0.4)], indoor=True),
    "hall-dungeon": Way([(*GH, 0.4), (GH[0] + 13, GH[1], 0.4), (DU[0] - 9, DU[1], -3), (*DU, -3)], indoor=True),
    "dungeon-small": Way([(*DU, -3), (DU[0], DU[1] - 9, -3), (DU[0], DU[1] - 15, LAIR_FLOOR),
                          (SR[0], DU[1] - 15, LAIR_FLOOR), (*SR, LAIR_FLOOR)], indoor=True),
    "small-lair": Way([(*SR, LAIR_FLOOR), (ML[0], SR[1], LAIR_FLOOR)], indoor=True),
    "lair-hall": Way([(*ML, LAIR_FLOOR), (ML[0], LAIR_STAIRS_FOOT, LAIR_FLOOR), (GH[0], LAIR_STAIRS_TOP, 0.4), (*GH, 0.4)],
                     indoor=True),
    # And in through the coach house's wide doors.
    "coach-door": Way([(CH[0] - HALLS["coach-house"].w - 1.8, CH[1], None), (*CH, 0.4)], half=2.4, indoor=True),
    # In at the tower's door, and the hut's.
    "tower-door": Way([(*TOWER_LIP, None), (*TOWER, None)], half=1.3, indoor=True),
    "hut-door": Way([(*HUT_LIP, None), (*HUT, None)], half=1.2, indoor=True, open=True),
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
    if math.hypot(x - HUT[0], y - HUT[1]) <= HUT_R - reach * math.sqrt(2):
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
    behind = smooth((255 - y) / 45)  # (its far side, coming down again by the land's north edge)
    return K * behind * (30 * smooth((y - 45) / 75) * across
                         + 28 * smooth((y - 150) / 45) * smooth((80 - abs(x)) / 40))


# The mountain's peaks, as in the paintings: a tall summit behind the maze,
# lesser ones round it, and crags all over its upper slopes (where they're
# high enough, snow: ground_colour). Never near the maze or the way up to
# it, nor anywhere else you can go, so there the ground is as it was. ((x, y) as in
# mountain(), how high, and how far its slopes reach.)
SUMMITS = [((6, 186), 48, 44), ((-40, 170), 28, 26), ((44, 176), 26, 24), ((-16, 208), 34, 30),
           ((28, 212), 24, 24)]


def peaks(x, y):
    m = mountain(x, y) / TOP
    if m < 0.25:
        return 0.0
    dx = max(0.0, abs(x - MZ[0]) - MAZE_HALF)
    dy = max(0.0, abs(y - MZ[1]) - MAZE_HALF)
    away = smooth((math.hypot(dx, dy) - 9) / 14)
    if y < MZ[1]:
        away *= smooth((abs(x - MZ[0]) - 14) / 14)  # (the way up, and the mountain at its foot)
    if away <= 0:
        return 0.0
    away *= clear_of_paths(x, y)
    if away <= 0:
        return 0.0
    u, v = x / K, y / K
    summit = sum(tall * max(0.0, 1 - math.hypot(u - sx, v - sy) / wide) ** 1.4 for (sx, sy), tall, wide in SUMMITS)
    crag = ridged(u, v, 22, 11.0)
    rough = smooth((m - 0.25) / 0.6)
    return K * away * smooth((m - 0.25) / 0.2) * (summit * (0.7 + 0.35 * crag) + rough * 9 * crag)


# How far round each place the forest is cleared (12 metres, unless it says).
CLEARING = {"grassy-bank": 17, "deep-river": 15, "river-south-bank": 15}


def clear_of_paths(x, y):
    """0 near a path, a clearing or a dead end, to 1 well away from them: where
    the mountain can be rougher, and no one will ever walk."""
    clear = min([path_lines.distance(x, y) - 5.5]
                + [math.hypot(x - sx, y - sy) - 11 for sx, sy in CLUES.values()]
                + [math.hypot(x - px, y - py) - CLEARING.get(place, 12)
                   for place, (px, py) in P.items() if KIND.get(place) != "cave"])
    return smooth((clear - 4) / 12)


def ridged(x, y, size, seed):
    """Noise with sharp crests, rough at every size from `size` metres down:
    0 to nearly 2."""
    total, part, f = 0.0, 1.0, 1 / size
    for octave in range(4):
        total += part * (1 - abs(noise.noise(Vector((x * f, y * f, seed + octave))))) ** 2
        part, f = part * 0.5, f * 2.1
    return total


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
    # Jagged further out, past the tunnels' mouths, and not the same on both
    # sides: to the west, a tall sharp crag, a little behind the maze; to the
    # east, a lower one (lower than the crags were), with two rough tops.
    far = smooth((d - 10) / 10)
    jagged = 0.0
    if far > 0:
        far *= clear_of_paths(x, y)
        if x < MZ[0]:
            u = 1 - math.hypot(x - MZ[0] + 26, y - MZ[1] - 4) / 15
            jagged = 4 * ridged(x, y, 10, 21.0) + 22 * smooth(u) ** 1.5
        else:
            jagged = 5 * ridged(x, y, 8, 25.0) * smooth((y - MZ[1] + 30) / 30) - 8
            jagged += 4 * smooth(1 - math.hypot(x - MZ[0] - 30, y - MZ[1] + 6) / 10)
            jagged += 3 * smooth(1 - math.hypot(x - MZ[0] - 22, y - MZ[1] - 10) / 8)
        jagged *= far
    return top * (15 * smooth((d - 1) / 6) * (1 + 0.15 * noise.noise(Vector((x / 6, y / 6, 4.0)))) + jagged)


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
    h += mountain(x, y) + crags(x, y) + peaks(x, y)
    h = max(h, dragon_hill(x, y), ridge(x, y))
    t = math.hypot(x - TOWER[0], y - TOWER[1])
    h += 5 * smooth(1 - (t - 8) / 10)
    h += 1.3 * smooth(1 - math.hypot(x - BALCONY_RISE[0], y - BALCONY_RISE[1]) / 3)
    g = math.hypot(x - P["evergreen-glade"][0], y - P["evergreen-glade"][1])
    h -= 1.5 * smooth(1 - (g - 10) / 8)  # the glade lies a little low
    r = from_river(x, y)
    if r < 10:
        h = h + (-3.2 - h) * smooth(1 - (r - 5) / 5)
    if in_moat(x, y):
        h = -3.2
    w, e, s, n = CASTLE
    if w - 8 <= x <= e + 8 and s - 8 <= y <= n + 8 and not in_moat(x, y):
        h = 0.4  # the castle stands on flat ground
    # (And the bank comes up to the drawbridge's landing, a step below it.)
    landing = smooth(1 - (max(0.0, abs(x) - 4) + max(0.0, y - (MOAT[3] + 3))) / 4)
    if landing > 0 and not in_moat(x, y):
        h += (0.45 - h) * landing
    return h


def rocky(x, y):
    """Bare rock you can't climb: the crags, the mountain's peaks, the
    dragon's hill and the ridge."""
    return crags(x, y) > 1 or peaks(x, y) > 3 or dragon_hill(x, y) > 1 or ridge(x, y) > 1


def maze_meadow(x, y):
    """The little meadow on the mountain top, round the maze and up the way
    to it, where the crags let it be: 1 in it, fading out to 0."""
    dx = max(0.0, abs(x - MZ[0]) - MAZE_HALF)
    dy = max(0.0, abs(y - MZ[1]) - MAZE_HALF)
    return smooth(1 - (math.hypot(dx, dy) - 6) / 4) * (1 - smooth((crags(x, y) - 0.3) / 1.2))


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

OPEN_ZONES = [(w * K, e * K, s * K, n * K) for w, e, s, n in [
    (-96, 25, -7, 22),  # the meadow, along the long path to the old stone wall
    (-80, 80, -282, -124),  # the castle grounds
]] + [(MZ[0] - MAZE_HALF - 0.5, MZ[0] + MAZE_HALF + 0.5, MZ[1] - MAZE_HALF - 0.5, MZ[1] + MAZE_HALF + 0.5)]  # the maze
AXE_TREES = (-14, 14, 49 * K, 58 * K)  # the dense trees across the mountain path


def ahead_of(key, x, y):
    """How far on a point is past a dead end's spot, along the way you come
    to it (and how far to the side: to your left, negative)."""
    spot = CLUES[key]
    px, py = P[key.split(" ")[0]]
    ax, ay = spot[0] - px, spot[1] - py
    run = math.hypot(ax, ay) or 1
    ax, ay = ax / run, ay / run
    return (x - spot[0]) * ax + (y - spot[1]) * ay, (x - spot[0]) * ay - (y - spot[1]) * ax


def beyond_the_dead_end(x, y):
    """On the far side of a dead end from the place you come to it from:
    forest again (its clearing is only on the near side), so from beyond
    (across the river from the old stone wall) you only glimpse it through
    the trees."""
    return any(math.hypot(x - spot[0], y - spot[1]) < 11 and ahead_of(key, x, y)[0] > 2 for key, spot in CLUES.items())


def open_ground(x, y, lures=True):
    """Ground with no forest on it: round the places, along the paths and the
    river, and round the dead ends (on the side you come to them from). And
    (unless not) along the trails past them."""
    if lures and on_a_lure(x, y):
        return True
    for place, (px, py) in P.items():
        if KIND.get(place) == "cave":
            continue
        if math.hypot(x - px, y - py) < CLEARING.get(place, 12):
            return True
    for w, e, s, n in OPEN_ZONES:
        if w <= x <= e and s <= y <= n:
            return True
    # (All round the grassy mound: its back reaches past the meadow, and you
    # can walk round it.)
    if math.hypot((x - MOUND.x) / (9 * 1.35 + 3.5), (y - MOUND.y) / (6.5 * 1.35 + 3.5)) < 1:
        return True
    for spot in CLUES.values():
        if math.hypot(x - spot[0], y - spot[1]) < 11 and not beyond_the_dead_end(x, y):
            return True
    return path_lines.distance(x, y) < 5.5 or from_river(x, y) < BANK or in_moat(x, y)


def under_a_tree(x, y):
    """Within a tree's spreading branches (with room for you): a tree at the
    forest's edge reaches out over the open ground."""
    i, j = int(x // 10), int(y // 10)
    return any(math.hypot(x - tx, y - ty) < r + 0.4
               for di in (-1, 0, 1) for dj in (-1, 0, 1) for tx, ty, r in TREES.get((i + di, j + dj), ()))


def walkable(x, y):
    """Where you can stand: open ground that isn't water, or a bridge, and
    not under a tree."""
    if deck(x, y) is not None:
        return True
    if from_river(x, y) < SHORE or in_moat(x, y):
        return False
    floor = open_to_the_sky(x, y, 2.0)
    if floor is not None and floor < height(x, y) - 0.35:
        return False  # over the ramp: you go in at the top
    # Along the trails to the old stones, and round them (under the trees'
    # branches, in the middle: their trunks are off the trail).
    if trails.distance(x, y) < TRAIL_WALK or any(math.hypot(x - t[-1][0], y - t[-1][1]) < GAP - 0.6 for t in LURES.values()):
        return True
    return open_ground(x, y, lures=False) and not rocky(x, y) and not in_building(x, y) and not under_a_tree(x, y)


# ---------------------------------------------------------------- the ground


def drawn_height(x, y, exactly=False):
    """The ground's height as drawn: flat triangles between the grid's points
    (whichever way each square is split, so it's never above it), so a little
    under height(). Exactly: as Blender splits them (from each square's first
    corner to its third), for laying something right on it."""
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
    if exactly:
        return a
    if fx + fy < 1:
        b = h00 + fx * (h10 - h00) + fy * (h01 - h00)
    else:
        b = h11 + (1 - fx) * (h01 - h11) + (1 - fy) * (h10 - h11)
    return min(a, b)


def ground_colour(x, y, z):
    if from_river(x, y) < 7 or in_moat(x, y):
        col = RIVERBED
    elif CASTLE[0] <= x <= CASTLE[1] and CASTLE[2] <= y <= CASTLE[3]:
        col = FLAGS
    elif open_ground(x, y):
        col = GRASS
        yellow = P["yellow-flowers"]
        col = c.mix(col, BUTTERCUPS, 0.6 * smooth(1 - (math.hypot(x - yellow[0], y - yellow[1]) - 6) / 10))
    else:
        col = FOREST_FLOOR
    if z > 8:
        col = c.mix(col, ROCK, smooth((z - 8) / 10))
    if z > 20:
        # On the mountain: its cliffs darker, and snow on its heights, lying
        # lower in hollows than on the crests, and not on the steepest rock.
        steep = math.hypot(height(x + 1, y) - height(x - 1, y), height(x, y + 1) - height(x, y - 1)) / 2
        col = c.mix(col, CRAG, smooth((steep - 0.8) / 0.6) * smooth((z - 20) / 8))
        line = 62 + 6 * noise.noise(Vector((x / 10, y / 10, 13.0)))
        col = c.mix(col, SNOW, smooth((z - line) / 5) * (1 - 0.7 * smooth((steep - 1.2) / 0.8)))
    return c.mix(col, GRASS, maze_meadow(x, y))


nx, ny = int((X1 - X0) / STEP) + 1, int((Y1 - Y0) / STEP) + 1
verts, colours, faces, walk = [], [], [], []
CUT = set()  # the squares cut out of the ground
for j in range(ny):
    for i in range(nx):
        x, y = X0 + i * STEP, Y0 + j * STEP
        z = height(x, y)
        verts.append((x, y, z))
        d = deck(x, y)
        walk.append(d if d is not None else z)
        colours.append(c.vary(ground_colour(x, y, z), 0.12, Vector((x / 6, y / 6, 5.0))))
for j in range(ny - 1):
    for i in range(nx - 1):
        qx, qy = X0 + (i + 0.5) * STEP, Y0 + (j + 0.5) * STEP
        # The hole over a ramp (a square with its middle by the ramp, or any
        # of it over the opening: by the lintel, a square can reach back
        # over it from beyond), or the floor of a building.
        if open_to_the_sky(qx, qy, 1.0) is not None or in_building(qx, qy, whole=True) \
                or any(over_an_opening(qx + STEP * u / 8, qy + STEP * v / 8)
                       for u in range(-4, 5) for v in range(-4, 5)):
            CUT.add((i, j))
            continue
        a = j * nx + i
        faces.append((a, a + 1, a + nx + 1, a + nx))
ground_obj = c.mesh_object("ground", verts, faces, colours)


def ground_normal(i, j):
    """The ground's normal at a point of its grid, from the slope there (the
    paths' edges are lit the same, so they don't show where they meet it)."""
    h = lambda a, b: verts[min(max(b, 0), ny - 1) * nx + min(max(a, 0), nx - 1)][2]
    n = Vector((-(h(i + 1, j) - h(i - 1, j)) / (2 * STEP), -(h(i, j + 1) - h(i, j - 1)) / (2 * STEP), 1.0))
    return tuple(n.normalized())


GROUND_NORMALS = [ground_normal(i, j) for j in range(ny) for i in range(nx)]
GROUND_HEIGHTS = [z for _, _, z in verts]
ground_obj.data.normals_split_custom_set_from_vertices(GROUND_NORMALS)

# Paths: earth on the ground, all of them one surface (so there's no seeing
# where one meets another), lying a few centimetres over the ground, on a
# finer grid than it but split as it is, so it follows it exactly. Worn, as
# in the paintings: pale and dusty down the middle, where feet go, darker
# towards the edges, in patches; wandering a little wider and narrower, with
# ragged edges fading into the grass. Past the dirt, it's the ground's own
# colour and lit as the ground is, coming down onto it, so there's no line
# where they meet.
GROUND_COLOURS = colours
DIRT_WORN = c.linear("#c99c66")
DIRT_EDGE = c.linear("#8e6a45")
HALF = 1.45  # half a path's width, on the whole
WANDERS = 0.3  # wider or narrower than that, by as much as this
REACH = HALF + WANDERS  # (as far as the dirt can be from its middle)
FADES = 1.3  # how far out, of its width, it's faded into the grass
PATH_LIFT = 0.03
SUB = 4  # its grid: this many squares across each of the ground's


def ground_at(x, y, values):
    """Something of the ground's (its colour, its normal) as drawn, between
    the grid's points: as drawn_height, on the triangle it's on."""
    fi, fj = (x - X0) / STEP, (y - Y0) / STEP
    i, j = min(math.floor(fi), nx - 2), min(math.floor(fj), ny - 2)
    fx, fy = fi - i, fj - j
    at = lambda a, b: values[(j + b) * nx + i + a]
    w = ((1 - fx), (fx - fy), 0, fy) if fx > fy else ((1 - fy), 0, (fy - fx), fx)
    corners = (at(0, 0), at(1, 0), at(0, 1), at(1, 1))
    return tuple(sum(wk * ck[n] for wk, ck in zip(w, corners)) for n in range(len(corners[0])))


def dirt(x, y, u):
    """The path's colour, u of the way out from its middle to the edge of its dirt."""
    worn = smooth(1 - abs(u) / 0.75)
    patch = noise.noise(Vector((x / 4, y / 4, 11.0)))
    col = c.mix(c.mix(DIRT, DIRT_EDGE, smooth((abs(u) - 0.4) / 0.6)), DIRT_WORN, worn * (0.6 + 0.4 * patch))
    return c.vary(col, 0.12, Vector((x, y, 2.0)))


def out_on_the_path(x, y):
    """How far out from the nearest path's middle, of its width there (1 at
    the edge of its dirt): wandering, and frayed."""
    half = HALF + WANDERS * noise.noise(Vector((x / 7, y / 7, 0.5)))
    fray = 0.13 * noise.noise(Vector((x / 1.2, y / 1.2, 4.0))) + 0.05 * noise.noise(Vector((x / 0.4, y / 0.4, 6.0)))
    # (The trails past the brambles narrower: less trodden. And at the narrows,
    # going down to the water, it peters out into the grass of the bank,
    # raggedly: no one's trodden the last of it.)
    out = min(path_lines.distance(x, y), trails.distance(x, y) * 1.4) / half + fray
    if abs(x - NARROWS_X) < NARROWS_HALF:
        bank = (from_river(x, y) - BANK) * narrowing(x, y) + 0.5 * noise.noise(Vector((x / 1.5, y / 1.5, 8.0)))
        out += 1.5 * (1 - smooth(bank / 2.5))
    return out


def off_the_land(x, y):
    """Over water, beside a bridge: no path there (it'd hang down to the
    riverbed). (Nor on the drawbridge, which moves, nor the stone either
    end of it.)"""
    if abs(x) <= 3.3 and CASTLE[3] - 1.2 <= y <= -127 * K:
        return True
    return deck(x, y) is None and (from_river(x, y) < BANK + 0.5 or in_moat(x, y))


path_points, path_index = [], {}


def path_point(gi, gj):
    """A point of the paths' grid (SUB to each of the ground's squares), made once."""
    if (gi, gj) in path_index:
        return path_index[(gi, gj)]
    x, y = X0 + gi * STEP / SUB, Y0 + gj * STEP / SUB
    u = out_on_the_path(x, y)
    d = deck(x, y)
    if d is not None:
        z, colour, normal = d + PATH_LIFT, dirt(x, y, min(u, 1.0)), (0.0, 0.0, 1.0)
    else:
        grass = ground_at(x, y, GROUND_COLOURS)
        faded = smooth((u - 1) / (FADES - 1))
        colour = c.mix(dirt(x, y, min(u, 1.0)), grass, faded)
        # (Coming down onto the ground at its very edge, where it's the ground's colour.)
        z = drawn_height(x, y, exactly=True) + PATH_LIFT * (1 - smooth((u - 1.05) / (FADES - 1.05)))
        normal = tuple(Vector(ground_at(x, y, GROUND_NORMALS)).normalized())
    path_index[(gi, gj)] = len(path_points)
    path_points.append(((x, y, z), colour, normal, u, off_the_land(x, y)))
    return path_index[(gi, gj)]


path_faces = []
for j in range(ny - 1):
    for i in range(nx - 1):
        if (i, j) in CUT:
            continue
        mx_, my_ = X0 + (i + 0.5) * STEP, Y0 + (j + 0.5) * STEP
        if min(path_lines.distance(mx_, my_), trails.distance(mx_, my_)) > REACH * FADES + 1.6:
            continue
        for a in range(SUB):
            for b in range(SUB):
                gi, gj = i * SUB + a, j * SUB + b
                k00, k10 = path_point(gi, gj), path_point(gi + 1, gj)
                k11, k01 = path_point(gi + 1, gj + 1), path_point(gi, gj + 1)
                corners = [path_points[k] for k in (k00, k10, k11, k01)]
                if min(p[3] for p in corners) >= FADES or any(p[4] for p in corners):
                    continue
                # (Split as the ground is: from the first corner to the third.)
                path_faces += [(k00, k10, k11), (k00, k11, k01)]
# (Only the points it uses.)
used = sorted({k for f in path_faces for k in f})
renumber = {k: n for n, k in enumerate(used)}
paths_obj = c.mesh_object("paths", [path_points[k][0] for k in used],
                          [tuple(renumber[k] for k in f) for f in path_faces], [path_points[k][1] for k in used])
paths_obj.data.normals_split_custom_set_from_vertices([path_points[k][2] for k in used])

# ---------------------------------------------------------------- what's solid

circles, boxes = [], []
# What stands in the way until the right object is used, by the exit it
# blocks: "box" [x, z, half x, half z] or "circle" [x, z, r], in three.js's axes.
obstacles = {}


def obstacle(exits, shape, *values, under=False, reach=None, all_round=False):
    """Underground ones block only the ways, and land ones only the land. You
    bump into one this far before it, all round it (5 m, unless it says).
    (All round: it stops you from every side, with no far side on the land
    to come from: only out of a door, which the game lets you.)"""
    for exit in exits:
        obstacles[exit] = {shape: [round(v, 2) for v in values], **({"under": True} if under else {}),
                           **({"reach": reach} if reach is not None else {}), **({"allRound": True} if all_round else {})}


def solid_box(x, y, half_x, half_y):
    boxes.append([round(x, 2), round(-y, 2), round(half_x, 2), round(half_y, 2)])


def solid_circle(x, y, r, top=None):
    """Solid, up from the ground (or to a top you can stand on)."""
    circles.append([round(x, 2), round(-y, 2), round(r, 2)] + ([round(top, 2)] if top is not None else []))


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


# Trees: Quaternius's (art/models/ultimate-nature), a few kinds, each kept
# once in land.glb (as "tree-<kind>", and simpler "tree-<kind>-far" and
# "tree-<kind>-distant" to draw further off); land.json says where each one
# grows, and the game stamps them there (src/three/trees.ts).
NATURE = HERE.parent / "models/ultimate-nature/Blends"
LEAFY = {"Green", "DarkGreen"}  # (their materials, without Blender's .001)
# Their colours, made ours: grey-brown bark (not the pack's reddish brown),
# and sunnier leaves, as in the pictures.
RECOLOUR = {"Wood": c.linear("#6b5846"), "Green": c.linear("#5f8c3a"), "DarkGreen": c.linear("#3f6930")}


def nature(kind):
    """A model from the pack, and how tall it is."""
    with bpy.data.libraries.load(str(NATURE / f"{kind}.blend")) as (src, dst):
        dst.objects = [name for name in src.objects if name == kind]
    obj = dst.objects[0]
    bpy.context.collection.objects.link(obj)
    return obj, max(v.co.z for v in obj.data.vertices)


def vertex_coloured(obj, name, top, ratio=None):
    """A copy of a model as one vertex-coloured mesh, its leaves lighter at
    the top (and simpler, given a ratio of its faces to keep)."""
    mesh = obj.data
    if ratio:
        copy = obj.copy()
        copy.data = mesh.copy()
        bpy.context.collection.objects.link(copy)
        mod = copy.modifiers.new("simpler", "DECIMATE")
        mod.ratio = ratio
        mesh = copy.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh().copy()
        bpy.data.objects.remove(copy)
    colours_of = []
    for slot in obj.material_slots:
        material = slot.material
        node = material.node_tree.nodes.get("Principled BSDF") if material and material.use_nodes else None
        base = material.name.split(".")[0] if material else ""
        colour = RECOLOUR.get(base) or (node.inputs["Base Color"].default_value[:3] if node else (0.3, 0.3, 0.3))
        colours_of.append((tuple(colour[:3]), base in LEAFY))
    b = c.Builder()
    for poly in mesh.polygons:
        colour, leafy = colours_of[poly.material_index] if colours_of else ((0.3, 0.3, 0.3), False)
        pts = [tuple(mesh.vertices[i].co) for i in poly.vertices]
        shades = []
        for p in pts:
            v = c.vary(colour, 0.12, Vector(p) * 2)
            light = 0.75 + 0.4 * max(0.0, p[2] / top) if leafy else 1.0
            shades.append((v[0] * light, v[1] * light, v[2] * light, 1.0))
        b.add(pts, [tuple(range(len(pts)))], shades)
    return b.build(name, smooth=False)


# Which trees grow where: round each place, its own mix (by the original's
# words, and the illustrated version's pictures), blending into the next.
FIRS = ["PineTree_1", "PineTree_2", "PineTree_3", "PineTree_4", "PineTree_5"]
OAKS = ["CommonTree_1", "CommonTree_2", "CommonTree_3", "CommonTree_4", "CommonTree_5"]
BIRCHES = ["BirchTree_1", "BirchTree_2", "BirchTree_3", "BirchTree_5"]
WILLOWS = ["Willow_1", "Willow_2", "Willow_4"]
DEAD = ["CommonTree_Dead_2", "BirchTree_Dead_5"]
GROVES = {
    # The forest in the south west: big old broadleaf trees.
    **dict.fromkeys(["forest-crossroads", "forest-witches", "forest-edge", "charcoal-hut", "old-wall"],
                    [(OAKS, 8), (BIRCHES, 1)]),
    # The evergreen glade, and the mountain and the dense trees at its foot: firs.
    **dict.fromkeys(["evergreen-glade", "mountain-path", "mountain", "cave-entrance", "dragon-cave", "maze",
                     "trolls", "oak-door", "treasure-room", "giant", "damp-tunnels"], [(FIRS, 1)]),
    # The mossy steps up to the tower: a little eerie.
    **dict.fromkeys(["mossy-steps", "tower"], [(FIRS, 3), (BIRCHES, 2), (DEAD, 2)]),
    # The meadows in the north west.
    **dict.fromkeys(["yellow-flowers", "rusty-gate", "old-stone-wall"], [(BIRCHES, 3), (OAKS, 2), (FIRS, 1)]),
}
MIXED = [(OAKS, 3), (BIRCHES, 2), (FIRS, 2)]  # anywhere else
GROVE_AT = [(P[place], mix) for place, mix in GROVES.items()]


def tree_kind(x, y, rng):
    """Which kind of tree grows here: the mix of the place nearest (give or
    take, so the groves blend), and willows down by the river."""
    if from_river(x, y) < BANK + 9 and rng.random() < 0.7:
        return rng.choice(WILLOWS)
    jx, jy = noise.noise(Vector((x / 25, y / 25, 1))) * 18, noise.noise(Vector((x / 25, y / 25, 7))) * 18
    nearest = min(P.values(), key=lambda p: math.hypot(x + jx - p[0], y + jy - p[1]))
    mix = next((m for p, m in GROVE_AT if p == nearest), MIXED)
    kinds, = rng.choices([k for k, _ in mix], [w for _, w in mix])
    return rng.choice(kinds)


KINDS = FIRS + OAKS + BIRCHES + WILLOWS + DEAD
TREE_MODEL = {}  # each kind's height, as it comes
for kind in KINDS:
    obj, top = nature(kind)
    vertex_coloured(obj, f"tree-{kind}", top)
    vertex_coloured(obj, f"tree-{kind}-far", top, ratio=0.15)
    vertex_coloured(obj, f"tree-{kind}-distant", top, ratio=0.04)
    TREE_MODEL[kind] = top
    bpy.data.objects.remove(obj)
# And a stump, for where the axe fells one.
obj, top = nature("TreeStump")
vertex_coloured(obj, "stump", top)
bpy.data.objects.remove(obj)

# What grows on the ground, each kind once in land.glb ("plant-<kind>"): the
# game scatters them round you, by what grows where (growth(), below), as in
# the paintings. Grass and flowers are ours (the pack's are stiff and few);
# the leafy plants, ferns, bushes and stones are the pack's.
RECOLOUR["Rock"] = c.linear("#8e877b")  # (warm grey, not the pack's blue)
for kind, name in (("Plant_1", "leafy"), ("Plant_3", "fern"), ("Rock_Moss_1", "boulder-1"), ("Rock_Moss_3", "boulder-2"),
                   ("Rock_Moss_5", "boulder-3"), ("Rock_Moss_7", "boulder-4"), ("Rock_2", "pebble-1"),
                   ("Rock_4", "pebble-2")):
    obj, top = nature(kind)
    # (The leafy ones simpler: there are hundreds round you.)
    vertex_coloured(obj, f"plant-{name}", top, ratio=0.4 if name in ("leafy", "fern") else None)
    bpy.data.objects.remove(obj)

BLADE_BASE = c.linear("#4a7425")
BLADE_TIP = c.linear("#9dbb4c")


def blade(b, x, y, angle, tall, lean, wide, base=BLADE_BASE, tip=BLADE_TIP, simple=False):
    """A blade of grass (or a leaf): from its foot at [x, y], up and arching
    over, away from the middle, tapering to a point. (Simple: straight, one
    triangle, for the thousands of tufts in the grass.)"""
    ox, oy = math.cos(angle), math.sin(angle)
    sx, sy = -oy, ox  # across it
    pts, cols = [], []
    for t in (0.0,) if simple else (0.0, 0.4, 0.75):
        out = lean * tall * t * t
        w = wide * (1 - 0.7 * t)
        z = tall * t * (1 - 0.25 * lean * t)
        for side in (-1, 1):
            pts.append((x + ox * out + sx * w * side, y + oy * out + sy * w * side, z))
            cols.append(c.mix(base, tip, t))
    pts.append((x + ox * lean * tall, y + oy * lean * tall, tall * (1 - 0.25 * lean)))
    cols.append(tip)
    b.add(pts, [(0, 1, 2)] if simple else [(0, 1, 3, 2), (2, 3, 5, 4), (4, 5, 6)], cols)


def tuft(b, rng, blades, tall, spread=0.08, lean=(0.15, 0.6), base=BLADE_BASE, tip=BLADE_TIP, wide=(0.018, 0.03),
         simple=False):
    for _ in range(blades):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0, spread)
        shade = rng.uniform(0.85, 1.1)
        blade(b, math.cos(a) * r, math.sin(a) * r, a + rng.uniform(-0.6, 0.6), tall * rng.uniform(0.55, 1.0),
              rng.uniform(*lean), rng.uniform(*wide), base, tuple(v * shade for v in tip[:3]) + (1.0,), simple)


def flower_head(b, x, y, z, petals, size, colour, middle, cup=0.0, tilt=(0.0, 0.0)):
    """A flower facing up (tipped a little by tilt): petals round a middle,
    flat (a daisy) or cupped up (a buttercup)."""
    tx, ty = tilt

    def at(px, py, pz):
        return (x + px, y + py, z + pz + px * tx + py * ty)

    for k in range(petals):
        a = 2 * math.pi * k / petals
        ca, sa = math.cos(a), math.sin(a)
        da = math.pi / petals * 0.8
        lift = size * cup
        b.add([at(0, 0, 0),
               at(math.cos(a - da) * size * 0.55, math.sin(a - da) * size * 0.55, lift * 0.5),
               at(ca * size, sa * size, lift),
               at(math.cos(a + da) * size * 0.55, math.sin(a + da) * size * 0.55, lift * 0.5)],
              [(0, 1, 2, 3)], [colour] * 4)
    r = size * 0.32
    b.add([at(math.cos(2 * math.pi * k / 6) * r, math.sin(2 * math.pi * k / 6) * r, size * 0.08) for k in range(6)],
          [tuple(range(6))], [middle] * 6)


def stem(b, x0, y0, x1, y1, z1, colour=BLADE_BASE, wide=0.008):
    """A thin stem up to a flower: two crossed strips."""
    for sx, sy in ((wide, 0), (0, wide)):
        b.add([(x0 - sx, y0 - sy, 0), (x0 + sx, y0 + sy, 0), (x1 + sx, y1 + sy, z1), (x1 - sx, y1 - sy, z1)],
              [(0, 1, 2, 3)], [colour, colour, c.mix(colour, BLADE_TIP, 0.4), c.mix(colour, BLADE_TIP, 0.4)])


def bell(b, x, y, z, angle, size, colour, inside):
    """A foxglove's flower: a little bell hanging off its stem (at [x, y, z]),
    its open end out (towards angle) and down."""
    sides = 5
    ox, oy = math.cos(angle), math.sin(angle)
    tip = (x, y, z + size * 0.4)
    mouth = (x + ox * size, y + oy * size, z - size * 0.35)
    sx, sy = -oy, ox
    rim = []
    for k in range(sides):
        a = 2 * math.pi * k / sides
        u, v = math.cos(a) * size * 0.42, math.sin(a) * size * 0.42
        # (round the mouth: across it, and up and down, tipped back towards the stem)
        rim.append((mouth[0] + sx * u - ox * v * 0.4, mouth[1] + sy * u - oy * v * 0.4, mouth[2] + v * 0.9))
    b.add([tip] + rim, [(0, 1 + k, 1 + (k + 1) % sides) for k in range(sides)], [colour] + [inside] * sides)


plant_rng = random.Random("what grows")
for name, tall, blades in (("grass", 0.45, 16), ("grass-short", 0.26, 14)):
    b = c.Builder()
    tuft(b, plant_rng, blades, tall, spread=0.22, lean=(0.1, 0.5), wide=(0.03, 0.05), simple=True)
    b.build(f"plant-{name}", smooth=False)
# Ox-eye daisies: white with yellow middles, held up over the grass.
b = c.Builder()
tuft(b, plant_rng, 5, 0.14, spread=0.05, lean=(0.6, 1.0), wide=(0.03, 0.04), simple=True)
for k in range(4):
    a = plant_rng.uniform(0, 2 * math.pi)
    r = plant_rng.uniform(0.04, 0.14)
    x, y, z = math.cos(a) * r, math.sin(a) * r, plant_rng.uniform(0.38, 0.55)
    stem(b, 0, 0, x, y, z)
    flower_head(b, x, y, z, 9, plant_rng.uniform(0.06, 0.075), c.linear("#fbf8ee"), c.linear("#f0c02a"),
                tilt=(x * 2, y * 2))
b.build("plant-daisy", smooth=False)
# Buttercups: glossy yellow cups, on tall stems.
b = c.Builder()
tuft(b, plant_rng, 4, 0.16, spread=0.05, lean=(0.6, 1.0), wide=(0.03, 0.04), simple=True)
for k in range(6):
    a = plant_rng.uniform(0, 2 * math.pi)
    r = plant_rng.uniform(0.05, 0.16)
    x, y, z = math.cos(a) * r, math.sin(a) * r, plant_rng.uniform(0.4, 0.6)
    stem(b, 0, 0, x, y, z)
    flower_head(b, x, y, z, 5, 0.055, c.linear("#f6c425"), c.linear("#d99a12"), cup=0.7)
b.build("plant-buttercup", smooth=False)
# Foxgloves: tall spikes of purple bells over a rosette of broad leaves.
b = c.Builder()
tuft(b, plant_rng, 7, 0.28, spread=0.04, lean=(0.9, 1.3), base=c.linear("#35591f"), tip=c.linear("#6f9a3c"))
for x0, y0, tall in ((0.0, 0.0, 1.05), (0.12, 0.05, 0.8)):
    stem(b, x0, y0, x0, y0, tall, wide=0.012)
    n = 11
    for k in range(n):
        f = k / (n - 1)
        z = tall * (0.45 + 0.5 * f)
        a = k * 2.4
        size = 0.055 * (1 - 0.55 * f)
        colour = c.mix(c.linear("#a8509f"), c.linear("#c983c4"), plant_rng.random() * 0.5 + f * 0.3)
        bell(b, x0 + math.cos(a) * 0.012, y0 + math.sin(a) * 0.012, z, a, size, colour, c.linear("#f0d8ea"))
b.build("plant-foxglove", smooth=False)
# Bushes: round, leafy clumps, lighter where the sun's on them (one with berries).
for k, (lumps, berries) in enumerate(((4, False), (6, False), (5, True)), 1):
    b = c.Builder()
    leaves = c.linear(("#55822f", "#4b7a2c", "#5c8a35")[k - 1])
    for n in range(lumps):
        a = 2 * math.pi * n / lumps + plant_rng.uniform(-0.4, 0.4)
        r = plant_rng.uniform(0.25, 0.5) if n else 0
        size = plant_rng.uniform(0.45, 0.6) * (1.2 if not n else 1)
        b.blob((math.cos(a) * r, math.sin(a) * r, size * 0.75 + (0.15 if not n else 0)), size, leaves, squash=0.85,
               lumpy=0.3, seed=k * 10 + n)
    if berries:
        for n in range(14):
            a, up = plant_rng.uniform(0, 2 * math.pi), plant_rng.uniform(0.2, 1.0)
            r = 0.75 * math.sqrt(1 - up * up * 0.6)
            b.blob((math.cos(a) * r, math.sin(a) * r, 0.25 + up * 0.75), 0.045, c.linear("#b3202a"), subdivisions=1)
    b.build(f"plant-bush-{k}", smooth=False)

TREES = {}  # each tree's spot and how far its branches spread, by 10 m square
tree_spots = {"kinds": KINDS, "at": [], "dense": []}  # [kind, x, y, z, yaw, scale], in three.js's axes


def grow(x, y, tall, kind, rng, into="at", sink=0.3):
    """A tree of a kind, `tall` metres high, turned whichever way `rng` says."""
    scale = tall / TREE_MODEL[kind]
    z = height(x, y) - sink
    tree_spots[into].append([KINDS.index(kind), round(x, 2), round(z, 2), round(-y, 2),
                             round(rng.uniform(0, 2 * math.pi), 2), round(scale, 2)])


# On a jittered grid wherever the ground isn't open. Each spot on the grid
# has its own random numbers (from where it is), so a change anywhere (a
# clearing, a path) only changes the trees there.
for gx in range(X0 + 3, X1 - 2, 5):
    for gy in range(Y0 + 3, Y1 - 2, 5):
        here = random.Random(f"tree {gx} {gy}")
        x, y = gx + here.uniform(-2, 2), gy + here.uniform(-2, 2)
        if open_ground(x, y) or open_to_the_sky(x, y, 4.5) is not None or rocky(x, y) or by_a_building(x, y):
            continue
        tall = here.uniform(9, 14)
        r = here.uniform(2.2, 3.0)
        # (Their branches clear of the maze's walls.)
        if abs(x - MZ[0]) < MAZE_HALF + r + 0.8 and abs(y - MZ[1]) < MAZE_HALF + r + 0.8:
            continue
        grow(x, y, tall, tree_kind(x, y, here), here)
        TREES.setdefault((int(x // 10), int(y // 10)), []).append((x, y, r))
# A few firs in the meadow round the maze (on the mountain top, where the
# grid finds none): their branches clear of its walls, the path and the
# tunnels' mouths.
here = random.Random("the maze's firs")
maze_firs, tries = 0, 0
while maze_firs < 7 and tries < 2000:
    tries += 1
    x, y = MZ[0] + here.uniform(-1, 1) * (MAZE_HALF + 10), MZ[1] + here.uniform(-1, 1) * (MAZE_HALF + 10)
    r = here.uniform(2.2, 2.8)
    if abs(x - MZ[0]) < MAZE_HALF + r + 0.8 and abs(y - MZ[1]) < MAZE_HALF + r + 0.8:
        continue
    if maze_meadow(x, y) < 0.6 or rocky(x, y) or path_lines.distance(x, y) < r + 2.5:
        continue
    if open_to_the_sky(x, y, 4.5) is not None or under_a_tree(x, y):
        continue
    grow(x, y, here.uniform(8, 12), here.choice(FIRS), here)
    TREES.setdefault((int(x // 10), int(y // 10)), []).append((x, y, r))
    maze_firs += 1
print(f"{maze_firs} firs round the maze")
# Trees close in on both sides of the dragon's mouth, so the only way on is
# down into it (not round its side, past the leaves).
here = random.Random("dragon's trees")
for dx, dy, r in ((1.5, 6.2, 1.7), (2.0, 7.5, 2.6), (5.0, 9.5, 2.8), (-1.5, 9.0, 2.4), (-0.5, 12.0, 2.6)):
    for side in (1, -1):
        x, y = DRAGON_LIP[0] + dx, DRAGON_LIP[1] + side * dy
        grow(x, y, here.uniform(10, 13), here.choice(FIRS), here)
        TREES.setdefault((int(x // 10), int(y // 10)), []).append((x, y, r))
# A copse in the triangle of paths between the grassy bank, the deep river
# and the evergreen glade: its forest is only a thin strip (between their
# clearings and the paths), too thin for the grid to find more than one spot.
here = random.Random("the triangle's copse")
for x, y in ((8.0, -16.0), (14.5, -12.0), (17.0, -8.5)):
    assert not open_ground(x, y), (x, y)
    grow(x, y, here.uniform(9, 13), tree_kind(x, y, here), here)
    TREES.setdefault((int(x // 10), int(y // 10)), []).append((x, y, here.uniform(2.2, 3.0)))
# The dense trees across the mountain path, which only the axe will clear:
# firs, close together (on their own, so the game can fell them).
here = random.Random("dense trees")
w, e, s, n = AXE_TREES
obstacle(["mountain-path north"], "box", (w + e) / 2, -(s + n) / 2, (e - w) / 2 + 2, (n - s) / 2)
for x in range(w, e + 1, 3):
    for y in (s + 2, s + 5, n - 1):
        xx, yy = x + here.uniform(-0.8, 0.8), y + here.uniform(-0.8, 0.8)
        grow(xx, yy, here.uniform(8, 11), here.choice(FIRS), here, into="dense")

# Water: the river, and the moat round the castle.
water = c.Builder()
# The river: one ribbon, its sides joined round the bends (separate pieces
# leave wedges of riverbed showing between them), reaching in under the
# banks (which come up out of the water at BANK).
verts, faces = [], []
for k, (x, y) in enumerate(RIVER):
    (ax, ay), (bx, by) = RIVER[max(k - 1, 0)], RIVER[min(k + 1, len(RIVER) - 1)]
    dd = math.hypot(bx - ax, by - ay) or 1
    w = 9.5 * narrowing(x, y)
    ox, oy = -(by - ay) / dd * w, (bx - ax) / dd * w
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
WATER_LEVEL = -1
# The deep river, where the way crosses it, from shore to shore: from the
# north bank it kills you (you're swept away: you walk in, and the game plays
# it out), and from the south one you fall in, but get out safely.
# (Along the narrows, from shore to shore there: further along, where it's
# wider, its shores are out of reach of the places either side.)
obstacle(["deep-river south", "river-south-bank north"], "box", NARROWS_X, 60 * K, NARROWS_HALF + 1,
         SHORE * NARROW + 0.2, reach=0.5)

# ---------------------------------------------------------------- built things

built = c.Builder()
# Rocks along the narrows, either side, at the water's edge (but for where
# the way comes down to it, either side, for a plank's ends).
rock_rng = random.Random(61)
for side in (-1, 1):
    x = NARROWS_X - NARROWS_HALF - NARROWS_EASE / 2
    while x < NARROWS_X + NARROWS_HALF + NARROWS_EASE / 2:
        x += rock_rng.uniform(1.4, 2.4)
        if abs(x - NARROWS_X) < 2.2:
            continue
        y = -60 * K + side * (BANK * narrowing(x, -60 * K) - 0.1)
        built.blob((x, y, WATER_LEVEL + rock_rng.uniform(-0.25, 0.1)), rock_rng.uniform(0.55, 0.85), ROCK,
                   squash=rock_rng.uniform(0.45, 0.7), lumpy=0.35, seed=300 + int(x * 7) + side)
    # And smaller ones where the way comes down: either side of it, at the
    # edge, and a few out in the shallows, worn smooth.
    for k in range(9):
        x = NARROWS_X + rock_rng.choice((-1, 1)) * rock_rng.uniform(0.9, 3.2)
        wet = rock_rng.uniform(-0.5, 0.5) if k < 6 else rock_rng.uniform(0.5, 1.0)
        y = -60 * K + side * (BANK * narrowing(x, -60 * K) - wet)
        built.blob((x, y, WATER_LEVEL + rock_rng.uniform(-0.15, 0.1)), rock_rng.uniform(0.18, 0.4), ROCK,
                   squash=rock_rng.uniform(0.4, 0.65), lumpy=0.3, seed=400 + k * 2 + side)

# The forest bridge and the drawbridge.
block(built, BRIDGE[0] - 2.4, BRIDGE[1] - BRIDGE_HALF, 0.5, BRIDGE[0] + 2.4, BRIDGE[1] + BRIDGE_HALF, 0.9,
      c.linear("#8a5a33"), solid=False)
for side in (-1, 1):
    block(built, BRIDGE[0] + side * 2.4 - 0.15, BRIDGE[1] - BRIDGE_HALF, 0.9, BRIDGE[0] + side * 2.4 + 0.15,
          BRIDGE[1] + BRIDGE_HALF, 1.9,
          c.linear("#6b4426"))
# The drawbridge, as in its pictures: planks on beams, edged with iron, on
# chains up to the gatehouse over the castle's gate. Hinged at the foot of
# the wall (the game raises it, and lowers it while the penny's in use
# here, and keeps it down while you're in the castle); lying across the
# moat, it rests on a stone landing on the bank, between two posts. You
# walk on its deck at deck()'s height, up or down: from the bank, it stops
# you on the landing (so you never walk out where it'd be).
DB_HINGE = CASTLE[3] + 1.2  # its hinge, out from the wall's face
DB_TIP = MOAT[3] - 0.1  # where it rests, at the landing's edge
DB_TOP = 0.6  # its deck (deck())
DB_HALF = 2.9  # half its width, a shade narrower than the gate
DB_THICK = 0.34
DB_CHAIN = 0.4  # how far in from its tip its chains are fixed
GATEHOUSE = (7.0, 9.8)  # over the gate, from the top of the way through to its battlements
DB_ANCHORS = [(side * (DB_HALF - 0.15), CASTLE[3] + 1, GATEHOUSE[0] + 1.6) for side in (-1, 1)]  # the chains' holes
PLANKS = [c.linear(h) for h in ("#8a5a33", "#7d5130", "#93613a", "#835634", "#8f5d35")]
DB_IRON = c.linear("#3b3836")
DB_LENGTH = DB_TIP - DB_HINGE
drawbridge = c.Builder()


def db_box(x0, a0, z0, x1, a1, z1, colour):
    """A piece of it, a0 to a1 out from its hinge, z up from its deck."""
    block(drawbridge, x0, a0, z0, x1, a1, z1, colour, solid=False)


k = 0
a = 0.0
while a < DB_LENGTH - 0.01:
    a1 = min(DB_LENGTH, a + 0.32)
    db_box(-DB_HALF, a + 0.012, -0.12, DB_HALF, a1 - 0.012, 0, PLANKS[(k * 3) % len(PLANKS)])  # (a dark gap between them)
    a, k = a1, k + 1
db_box(-DB_HALF + 0.1, 0.02, -0.13, DB_HALF - 0.1, DB_LENGTH - 0.02, -0.1, c.linear("#3d2817"))  # (the gaps, dark)
for x in (-DB_HALF + 0.25, 0, DB_HALF - 0.25):
    db_box(x - 0.14, 0.05, -DB_THICK, x + 0.14, DB_LENGTH - 0.05, -0.12, c.linear("#5e3b1f"))  # the beams under it
for side in (-1, 1):
    db_box(side * DB_HALF - 0.06, 0, -0.16, side * DB_HALF + 0.06, DB_LENGTH, 0.04, DB_IRON)  # its iron edges
    # (And where its chains are fixed: a ring standing up on each side.)
    db_box(side * (DB_HALF - 0.15) - 0.05, DB_LENGTH - DB_CHAIN - 0.08, 0, side * (DB_HALF - 0.15) + 0.05,
           DB_LENGTH - DB_CHAIN + 0.08, 0.14, DB_IRON)
for a in (0.25, DB_LENGTH - 0.25):
    db_box(-DB_HALF, a - 0.06, 0, DB_HALF, a + 0.06, 0.015, DB_IRON)  # straps across its ends
drawbridge.build("drawbridge", smooth=False).location = (0, DB_HINGE, DB_TOP)
# The way in under the gatehouse, and the landing on the bank, between its posts.
block(built, -3, CASTLE[3] - 1.1, 0.0, 3, DB_HINGE, DB_TOP, c.linear("#8d887c"), solid=False)
block(built, -3.2, DB_TIP, -0.6, 3.2, -127 * K, DB_TOP, c.linear("#8d887c"), solid=False)
for side in (-1, 1):
    block(built, side * 3.55 - 0.3, DB_TIP + 0.15, -0.6, side * 3.55 + 0.3, DB_TIP + 0.75, 1.5, STONE)
    built.cone((side * 3.55, DB_TIP + 0.45, 1.5), 0.3, 0.42, STONE, sides=4, droop=0)
# The gatehouse over the gate, between the towers either side of it, with
# the chains' holes in its face.
block(built, -3.2, CASTLE[3] - 1, GATEHOUSE[0], 3.2, CASTLE[3] + 1, GATEHOUSE[1], GREY, solid=False)
for x in (-3.2, -1.2, 0.8, 2.6):
    block(built, x, CASTLE[3] + 0.4, GATEHOUSE[1], x + 0.6, CASTLE[3] + 1, GATEHOUSE[1] + 0.8, GREY, solid=False)
for x, y, z in DB_ANCHORS:
    block(built, x - 0.12, y, z - 0.12, x + 0.12, y + 0.02, z + 0.12, c.linear("#1d1b19"), solid=False)
# The toll booth, beside the guards: striped red and white, as in its
# picture, under a pointed roof, its doorway to the path.
BOOTH = (6.6, MOAT[3] + 3.4)
BOOTH_R, BOOTH_TALL, BOOTH_SIDES = 0.95, 2.3, 10
for k in range(BOOTH_SIDES):
    a0, a1 = (2 * math.pi * (k + j) / BOOTH_SIDES for j in (0, 1))
    pts = [(BOOTH[0] + math.cos(a) * BOOTH_R, BOOTH[1] + math.sin(a) * BOOTH_R, z)
           for a, z in ((a0, -0.1), (a1, -0.1), (a1, BOOTH_TALL), (a0, BOOTH_TALL))]
    door = k == BOOTH_SIDES // 2  # (facing west, to the path)
    colour = c.linear("#2a1d14") if door else c.linear("#c23a33" if k % 2 else "#f1eadb")
    built.add(pts, [(0, 1, 2, 3)], [colour] * 4)
built.cone((*BOOTH, BOOTH_TALL), 1.3, BOOTH_R * 1.2, c.linear("#c23a33"), sides=BOOTH_SIDES, droop=0)
block(built, BOOTH[0] - 0.02, BOOTH[1] - 0.02, BOOTH_TALL + 1.2, BOOTH[0] + 0.02, BOOTH[1] + 0.02, BOOTH_TALL + 1.8,
      c.linear("#5e3b1f"), solid=False)
built.add([(BOOTH[0], BOOTH[1], BOOTH_TALL + 1.8), (BOOTH[0] + 0.45, BOOTH[1], BOOTH_TALL + 1.68),
           (BOOTH[0], BOOTH[1], BOOTH_TALL + 1.56)], [(0, 1, 2)], [c.linear("#f1eadb")] * 3)  # its pennant
solid_circle(*BOOTH, BOOTH_R + 0.05)
# Where the guards stand: either side of the way onto the landing, facing up
# the path, clear of the bridge's width (coming off it, you'd bump into one,
# and be pushed back, as if you'd turned back into the moat).
GUARDS = [(side * 3.7, DB_TIP + 1.2) for side in (-1, 1)]
# The drawbridge is up: across the water, so from the bank it stops you
# just short of the guards (it's they who stop you, at the toll gate).
obstacle(["moat south"], "box", 0, -(DB_TIP + CASTLE[3] + 2) / 2, 3.2, (DB_TIP - CASTLE[3] - 2) / 2, reach=2.65)

# The old stone wall: north from the forest, west along the gate, north again.
WALL = 4.5
WX, WY = -100 * K, 60 * K  # the corner by the old stone wall, and the gate's line
# Between the old wall and the old stone wall, it's too high to climb without the ladder.
obstacle(["old-wall east", "old-stone-wall west"], "box", WX, -(-18 * K + WY + 0.6) / 2, 0.6, (WY + 0.6 + 18 * K) / 2)
GATE = (P["rusty-gate"][0] - 2.2, P["rusty-gate"][0] + 2.2)  # the gap in the wall, exactly the gate's width
WW = -140 * K  # where it turns north again, up the west of the yellow flowers
for start, end in ((WW - 0.6, GATE[0]), (GATE[1], WX + 0.6)):
    x = start
    while x < end - 0.01:
        solid_box((x + min(x + 2, end)) / 2, WY, (min(x + 2, end) - x) / 2, 0.6)
        x += 2
# The rusty gate, locked: two halves, each on its hinge at the wall, which
# the game swings open (north, away from the rusty gate) while the key's in use.
RUST = c.linear("#a5532c")
GATE_FOOT = height((GATE[0] + GATE[1]) / 2, WY) - 0.1
for name, hinge, way in (("gate-west", GATE[0], 1), ("gate-east", GATE[1], -1)):
    leaf = c.Builder()
    wide = (GATE[1] - GATE[0]) / 2 - 0.02

    def bar(a0, a1, z0, z1, t=0.05):
        """A piece of the gate, from a0 to a1 out from its hinge."""
        lo, hi = sorted((a0 * way, a1 * way))
        block(leaf, lo, -t, z0, hi, t, z1, RUST, solid=False)

    bar(0, 0.12, 0, 3.6)  # the stile on the hinge
    bar(wide - 0.1, wide, 0, 3.6)  # and where the two halves meet
    for z in (0.15, 1.8, 3.35):
        bar(0, wide, z, z + 0.12)  # the rails
    for k in range(1, 8):
        a = k * wide / 8
        bar(a - 0.025, a + 0.025, 0, 3.8, t=0.025)  # the bars, poking up above the top rail
    obj = leaf.build(name, smooth=False)
    obj.location = (hinge, WY, GATE_FOOT)
obstacle(["rusty-gate north", "yellow-flowers south"], "box", (GATE[0] + GATE[1]) / 2, -WY, (GATE[1] - GATE[0]) / 2, 0.6)
y = WY
while y < 118 * K:
    solid_box(WW, y + 1, 0.6, 1)
    y += 2
WALL_END = y

# What it looks like: dry stone, as in the paintings. Rough courses of
# stones of every size and shade (bigger low down), wider at its foot and
# leaning in a little as it rises; a row of stones on edge along its top;
# moss low down, on its top and on its shady side, pale lichen here and
# there; ivy hanging down from its top in places; a stone missing, or
# sticking out, now and then; and a few fallen at its foot. (Solid as the
# boxes above, and as the obstacle: this is only how it looks.)
# (Light sand, so the ladder shows up clearly against it.)
WALL_STONES = [c.linear(h) for h in ("#dcc08a", "#e6cf9f", "#d1b47f", "#dfc596", "#ecdbb4", "#ccae7c", "#e2cc9c")]
WALL_GAP = c.linear("#9a8868")  # (in between them, deep in)
MOSS = c.linear("#8a9446")
LICHEN = c.linear("#eee8cf")
IVY = (c.linear("#2c5220"), c.linear("#4c7a2c"))
WALL_TALL = WALL + 0.5  # from its foot, under the ground, to its top
FOOT_HALF, TOP_HALF = 0.62, 0.56  # half its thickness (the ladder rests on its top edge: ladder.ts)
SUN_XY = Vector((-0.75, 0.5)).normalized()  # where the sun is (main.ts), in Blender's axes, across the land
wall = c.Builder()
wall_rng = random.Random("the old stone wall")


def facing(builder, pts, colours, outward):
    """A face, wound to face outward (or it's not drawn: it's facing away)."""
    n = (Vector(pts[1]) - Vector(pts[0])).cross(Vector(pts[2]) - Vector(pts[0]))
    if n.dot(Vector(outward)) < 0:
        pts, colours = pts[::-1], colours[::-1]
    builder.add(pts, [tuple(range(len(pts)))], colours)


def stone_wall(x0, y0, x1, y1):
    length = math.hypot(x1 - x0, y1 - y0)
    dx, dy = (x1 - x0) / length, (y1 - y0) / length
    nx_, ny_ = -dy, dx  # across it

    def foot(t):
        return height(x0 + dx * t, y0 + dy * t) - 0.5

    def half(h):
        return FOOT_HALF + (TOP_HALF - FOOT_HALF) * h / WALL_TALL

    def at(t, h, side, depth=0.0):
        """A point on its face (side 1 or -1), t along it and h up from its foot, depth in from its face."""
        out = (half(h) - depth) * side
        return (x0 + dx * t + nx_ * out, y0 + dy * t + ny_ * out, foot(t) + h)

    def stone(a0, a1, b0, b1, side, shady, bevel=None, bulge=None):
        """One stone, its face from a0 to a1 along the wall and b0 to b1 up,
        bevelled round its edges, a little askew, and some of it standing out."""
        bevel = wall_rng.uniform(0.03, 0.06) if bevel is None else bevel
        bevel = min(bevel, (a1 - a0) / 3, (b1 - b0) / 3)
        if bulge is None:
            bulge = wall_rng.uniform(0.0, 0.04) + (0.07 if wall_rng.random() < 0.02 else 0.0)
        mid, h = (a0 + a1) / 2, (b0 + b1) / 2
        colour = c.vary(wall_rng.choice(WALL_STONES), 0.1, Vector((a0, b0, side * 3)))
        mossy = max(smooth(1 - (h - 0.5) / 1.2), smooth((h - WALL_TALL + 1.2) / 1.0) * 0.6) * (0.5 + 0.6 * shady)
        mossy *= max(0.0, 0.6 + 0.8 * noise.noise(Vector((x0 + dx * mid, y0 + dy * mid, h * 2))))
        colour = c.mix(colour, MOSS, min(0.6, mossy * 0.75))
        if wall_rng.random() < 0.15:
            colour = c.mix(colour, LICHEN, wall_rng.uniform(0.25, 0.55))
        dark = c.mix(colour, WALL_GAP, 0.35)
        # (Askew: its corners up or down a little.)
        tip = [wall_rng.uniform(-0.025, 0.025) for _ in range(4)]
        ts, hs = (a0, a1, a1, a0), (b0, b0, b1, b1)
        towards = ((1, 1), (-1, 1), (-1, -1), (1, -1))
        front = [at(ts[k] + towards[k][0] * bevel, hs[k] + towards[k][1] * bevel + tip[k], side, -bulge)
                 for k in range(4)]
        rim = [at(ts[k], hs[k] + tip[k], side, 0.02) for k in range(4)]
        out = (nx_ * side, ny_ * side, 0)
        facing(wall, front, [colour, colour, c.mix(colour, LICHEN, 0.06), colour], out)
        for k in range(4):
            facing(wall, [front[k], rim[k], rim[(k + 1) % 4], front[(k + 1) % 4]], [colour, dark, dark, colour], out)

    # Its core, deep in: what you see between the stones, and at its ends.
    for side in (1, -1):
        facing(wall, [at(0, 0, side, 0.05), at(length, 0, side, 0.05), at(length, WALL_TALL, side, 0.05),
                      at(0, WALL_TALL, side, 0.05)], [WALL_GAP] * 4, (nx_ * side, ny_ * side, 0))
    for t in (0.0, length):
        way = -1 if t == 0 else 1
        pts = [at(t, 0, -1, 0.05), at(t, 0, 1, 0.05), at(t, WALL_TALL, 1, 0.05), at(t, WALL_TALL, -1, 0.05)]
        facing(wall, pts, [c.mix(WALL_GAP, WALL_STONES[0], 0.5)] * 4, (dx * way, dy * way, 0))
    facing(wall, [at(0, WALL_TALL, -1, 0.05), at(length, WALL_TALL, -1, 0.05), at(length, WALL_TALL, 1, 0.05),
                  at(0, WALL_TALL, 1, 0.05)], [WALL_GAP] * 4, (0, 0, 1))
    # The stones, in rough courses, each side: none quite filling its course
    # (a dark chink over it, now and then packed with a small stone), now
    # and then two on top of each other, or one gone.
    for side in (1, -1):
        shady = max(0.0, -(nx_ * side * SUN_XY.x + ny_ * side * SUN_XY.y))
        h = 0.0
        while h < WALL_TALL - 0.05:
            low = 1 - h / WALL_TALL
            tall = min(wall_rng.uniform(0.32, 0.5) + 0.18 * low, WALL_TALL - h)
            if WALL_TALL - h - tall < 0.15:
                tall = WALL_TALL - h
            t = -wall_rng.uniform(0, 0.5)
            while t < length:
                long = wall_rng.uniform(0.5, 1.2) + 0.45 * low
                ta, tb = max(t, 0.0), min(t + long, length)
                t += long
                if tb - ta < 0.12:
                    continue
                if wall_rng.random() < 0.012 and 0.6 < h < WALL_TALL - 0.6:
                    continue
                gap = 0.02
                short = wall_rng.uniform(0.0, 0.12) if h + tall < WALL_TALL - 0.01 else 0.0
                a0, a1, b0, b1 = ta + gap, tb - gap, h + gap, h + tall - gap - short
                if short > 0.06 and a1 - a0 > 0.45:
                    pa = wall_rng.uniform(a0 + 0.05, a1 - 0.25)
                    stone(pa, pa + wall_rng.uniform(0.15, 0.28), b1 + gap, h + tall - gap, side, shady, 0.015, 0.0)
                if wall_rng.random() < 0.08 and b1 - b0 > 0.3:
                    split = b0 + (b1 - b0) * wall_rng.uniform(0.4, 0.6)
                    cut = wall_rng.uniform(a0 + 0.1, a1 - 0.1) if a1 - a0 > 0.5 else None
                    stone(a0, a1, b0, split - gap, side, shady)
                    if cut:
                        stone(a0, cut - gap, split + gap, b1, side, shady)
                        stone(cut + gap, a1, split + gap, b1, side, shady)
                    else:
                        stone(a0, a1, split + gap, b1, side, shady)
                else:
                    stone(a0, a1, b0, b1, side, shady)
            h += tall
    # Along its top, stones on edge, leaning this way and that, ragged.
    t = 0.0
    while t < length - 0.1:
        thick = wall_rng.uniform(0.18, 0.3)
        ta, tb = t + 0.015, min(t + thick, length) - 0.015
        t += thick
        lean = wall_rng.uniform(-0.08, 0.08)
        up = wall_rng.uniform(0.3, 0.5)
        colour = c.mix(c.vary(wall_rng.choice(WALL_STONES), 0.1, Vector((ta, 0, 9))), MOSS, wall_rng.uniform(0.1, 0.45))
        w = TOP_HALF + 0.02
        corners = []
        for z in (0.0, 1.0):
            for (tt, side) in ((ta, -1), (tb, -1), (tb, 1), (ta, 1)):
                rise = up + wall_rng.uniform(-0.07, 0.07) if z else 0.0
                base = foot(tt) + WALL_TALL - 0.05
                tt2 = tt + lean * rise
                corners.append((x0 + dx * tt2 + nx_ * w * side, y0 + dy * tt2 + ny_ * w * side, base + rise))
        middle = Vector(corners[0]) + Vector(corners[6])
        for f in [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]:
            pts = [corners[k] for k in f]
            shade = c.mix(colour, LICHEN, 0.1) if f == (4, 5, 6, 7) else colour
            facing(wall, pts, [shade] * 4, tuple(Vector(pts[0]) + Vector(pts[2]) - middle))
    # Ivy, hanging down from its top, here and there, either side.
    for side in (1, -1):
        t = wall_rng.uniform(2, 8)
        while t < length - 1:
            wide = wall_rng.uniform(1.5, 3.5)
            drop = wall_rng.uniform(1.5, 4.0)
            for _ in range(int(wide * drop * 32)):
                u = wall_rng.uniform(-1, 1)
                # (Hanging lower in the middle, and ragged at its foot.)
                reach = drop * (1 - 0.6 * u * u) * wall_rng.uniform(0.55, 1.0)
                down = reach * wall_rng.random() ** 1.4
                lt = t + u * wide / 2
                if not 0 < lt < length:
                    continue
                h = min(WALL_TALL + 0.15, WALL_TALL - down + 0.15)
                size = wall_rng.uniform(0.13, 0.21)
                spin = wall_rng.uniform(0, 2 * math.pi)
                cx, cy, cz = at(lt, h, side, -wall_rng.uniform(0.02, 0.1))
                corners = []
                for a, r in ((0, 1.0), (math.pi / 2, 0.6), (math.pi, 0.5), (3 * math.pi / 2, 0.6)):
                    along_, up_ = math.cos(spin + a) * size * r, math.sin(spin + a) * size * r
                    lift = 0.04 * wall_rng.random() if a == 0 else 0.0
                    corners.append((cx + dx * along_ + nx_ * side * lift, cy + dy * along_ + ny_ * side * lift, cz + up_))
                leaf = c.mix(*IVY, wall_rng.random())
                facing(wall, corners, [leaf, c.mix(leaf, IVY[0], 0.4), c.mix(leaf, IVY[0], 0.6), leaf],
                       (nx_ * side, ny_ * side, 0))
            t += wide + wall_rng.uniform(5, 14)
    # Fallen stones, at its foot, either side (just out of your reach).
    t = wall_rng.uniform(1, 5)
    while t < length - 1:
        side = wall_rng.choice((1, -1))
        out = FOOT_HALF + wall_rng.uniform(0.05, 0.3)
        cx, cy = x0 + dx * t + nx_ * out * side, y0 + dy * t + ny_ * out * side
        size = wall_rng.uniform(0.18, 0.3)
        wall.blob((cx, cy, drawn_height(cx, cy) + size * 0.25), size, c.mix(wall_rng.choice(WALL_STONES), MOSS, 0.3),
                  squash=0.55, lumpy=0.2, seed=int(t * 13) + side, subdivisions=1)
        t += wall_rng.uniform(3, 9)


for run in ((WX, -18 * K, WX, WY + 0.6), (WW - 0.6, WY, GATE[0], WY), (GATE[1], WY, WX + 0.6, WY),
            (WW, WY, WW, WALL_END)):
    stone_wall(*run)
wall.build("old-stone-wall", smooth=False)


# A clue at each dead end: a note, nailed to a rough board on a stake, the
# board leaning back a little, to read. Its words are written on in the game
# (notes.ts), in your language: here, only where they go (NOTES, in
# land.json).
NOTE_WOOD, NOTE_DARK = c.linear("#7d654b"), c.linear("#4f3f2e")
NOTE_BOARD = (0.46, 0.38)  # across and up
NOTE_PAPER = (0.34, 0.28)  # the note on it
NOTE_UP = 1.15  # the board's middle, above the ground
NOTE_LEAN = math.radians(10)
NOTES = []  # each: the exit that leads to its clue, where its note's middle is [x, y, z], which way it faces [x, z]


def note_post(builder, key, x, y, ground, facing, earth=DIRT_EDGE):
    """A stake at [x, y] (standing on `ground`), its board facing `facing`
    (a unit [x, y]), with the note for the clue the exit `key` leads to."""
    fx, fy = facing
    rng = random.Random(f"note {key}")
    builder.cylinder((x, y, ground - 0.3), (x, y, ground + NOTE_UP + 0.3), 0.055, 0.045, NOTE_DARK, sides=6)
    # Bedded in: a little heap of earth round its foot, and stones wedged in
    # it (so it's plainly in the ground, its shadow or not).
    builder.blob((x, y, ground - 0.04), 0.24, earth, squash=0.5, lumpy=0.3, seed=rng.random() * 100, subdivisions=1)
    for k in range(4):
        a = k * math.pi / 2 + rng.uniform(-0.5, 0.5)
        builder.blob((x + math.cos(a) * 0.12, y + math.sin(a) * 0.12, ground + 0.01), rng.uniform(0.04, 0.065),
                     c.vary(STONE, 0.15, Vector((x, y, k))), squash=0.7, lumpy=0.35, seed=rng.random() * 100, subdivisions=1)
    across = Vector((-fy, fx, 0))  # (to your right, reading it)
    up = Vector((-fx * math.sin(NOTE_LEAN), -fy * math.sin(NOTE_LEAN), math.cos(NOTE_LEAN)))
    out = Vector((fx * math.cos(NOTE_LEAN), fy * math.cos(NOTE_LEAN), math.sin(NOTE_LEAN)))  # out of its face
    middle = Vector((x, y, ground + NOTE_UP)) + Vector((fx, fy, 0)) * 0.075  # (in front of the stake)
    w, h = NOTE_BOARD[0] / 2, NOTE_BOARD[1] / 2
    # Its outline, roughly cut: each corner a little off.
    ends = [(-w + rng.uniform(0, 0.03), -h + rng.uniform(0, 0.02)), (w - rng.uniform(0, 0.03), -h + rng.uniform(0, 0.02)),
            (w - rng.uniform(0, 0.03), h - rng.uniform(0, 0.02)), (-w + rng.uniform(0, 0.03), h - rng.uniform(0, 0.02))]
    face = [middle + across * u + up * v for u, v in ends]
    back = [p - out * 0.03 for p in face]
    builder.add([tuple(p) for p in face + back], [(0, 1, 2, 3), (7, 6, 5, 4)] + [(i, 4 + i, 4 + (i + 1) % 4, (i + 1) % 4) for i in range(4)],
                [c.vary(NOTE_WOOD, 0.12, p * 4) for p in face + back])
    paper = middle + out * 0.004
    NOTES.append({"clue": key, "at": [round(paper.x, 3), round(paper.z, 3), round(-paper.y, 3)],
                  "facing": [round(fx, 3), round(-fy, 3)], "lean": round(NOTE_LEAN, 4), "size": list(NOTE_PAPER)})

# What's at the end of each trail past the brambles: old stones, grey and mossy,
# standing in the sunlit gap. A ring of them; an arch, fallen in on one
# side; or a few left standing.
OLD_STONE = c.linear("#a5a196")


def slab(b, x, y, yaw, wide, thick, tall, lean=0.0, sink=0.4, colour=OLD_STONE):
    """A standing stone: rough, a little narrower at the top, leaning over
    (forward, towards yaw) by `lean`, and sunk into the ground."""
    z = height(x, y) - sink
    ux, uy = math.cos(yaw), math.sin(yaw)  # across it
    fx, fy = -uy, ux  # out of its face
    rng = random.Random(f"slab {x:.1f} {y:.1f}")
    verts = []
    for level, (w, t) in enumerate(((wide, thick), (wide * 0.82, thick * 0.85))):
        up = (tall + sink) * level
        tip = lean * up
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            jx = rng.uniform(-0.06, 0.06)
            verts.append((x + ux * (sx * w / 2 + jx) + fx * (sy * t / 2 + tip),
                          y + uy * (sx * w / 2 + jx) + fy * (sy * t / 2 + tip), z + up + rng.uniform(-0.08, 0.08) * level))
    shade = [c.mix(c.vary(colour, 0.12, Vector(v)), MOSS, 0.45 if k < 4 else 0.1) for k, v in enumerate(verts)]
    b.add(verts, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], shade)
    return verts[4:]


def lintel(b, a, z_a, d, z_d, wide=0.7, thick=0.55):
    """A stone laid from one point [x, y] at z_a to another at z_d."""
    (ax, ay), (dx, dy) = a, d
    run = math.hypot(dx - ax, dy - ay) or 1
    ox, oy = -(dy - ay) / run * wide / 2, (dx - ax) / run * wide / 2
    verts = [(px + sx * ox, py + sx * oy, pz + up) for (px, py, pz) in ((ax, ay, z_a), (dx, dy, z_d))
             for sx, up in ((-1, 0), (1, 0), (1, thick), (-1, thick))]
    b.add(verts, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (0, 3, 2, 1), (4, 5, 6, 7)],
          [c.mix(c.vary(OLD_STONE, 0.12, Vector(v)), MOSS, 0.25 if v[2] > max(z_a, z_d) else 0.05) for v in verts])


def old_stones(b, kind, ex, ey, yaw, solid=False):
    """Old stones round [ex, ey], facing along yaw (towards you, coming): a
    ring of them (one fallen), an arch (whole, or fallen in on one side), or
    a few left standing. Solid, where you can get to them."""
    rng = random.Random(f"old stones {ex:.1f} {ey:.1f}")
    pillars = []  # (x, y, how wide): to bump into

    def standing(x, y, a, wide, thick, tall, lean=0.0):
        slab(b, x, y, a, wide, thick, tall, lean=lean)
        pillars.append((x, y, max(wide, thick) / 2))

    def fallen(a, z_a, d, z_d, wide, thick):
        lintel(b, a, z_a, d, z_d, wide, thick)
        pillars.extend(((a[0] + (d[0] - a[0]) * f, a[1] + (d[1] - a[1]) * f, wide / 2) for f in (0.15, 0.5, 0.85)))

    if kind == "ring":
        # (A gap in it facing you.)
        for k in range(8):
            a = yaw + math.pi + math.pi / 8 + k * 2 * math.pi / 9
            x, y = ex + math.cos(a) * 3.3, ey + math.sin(a) * 3.3
            if k == 5:
                fallen((x - math.cos(a) * 0.2, y - math.sin(a) * 0.2), height(x, y) - 0.1,
                       (x + math.sin(a) * 1.9, y - math.cos(a) * 1.9), height(x, y) - 0.15, 0.8, 0.45)
                continue
            standing(x, y, a + math.pi / 2, rng.uniform(0.8, 1.1), rng.uniform(0.35, 0.5), rng.uniform(1.6, 2.4),
                     lean=rng.uniform(-0.06, 0.06))
    elif kind in ("arch", "ruined arch"):
        across = yaw + math.pi / 2
        ux, uy = math.cos(across), math.sin(across)
        left, right = (ex + ux * 1.4, ey + uy * 1.4), (ex - ux * 1.4, ey - uy * 1.4)
        if kind == "arch":
            # Whole: high enough to walk under.
            standing(*left, yaw, 0.75, 0.7, 3.3, lean=0.02)
            standing(*right, yaw, 0.75, 0.7, 3.2, lean=-0.02)
            lintel(b, (left[0] + ux * 0.45, left[1] + uy * 0.45), height(*left) + 2.95,
                   (right[0] - ux * 0.45, right[1] - uy * 0.45), height(*right) + 2.85, 0.8, 0.55)
        else:
            # The lintel fallen in on one side: from the tall pillar's top down
            # to the broken one's.
            standing(*left, yaw, 0.75, 0.7, 3.3, lean=0.02)
            standing(*right, yaw, 0.75, 0.7, 1.7, lean=-0.03)
            lintel(b, left, height(*left) + 2.9, right, height(*right) + 1.25)
        x, y = ex - ux * 2.6 + math.cos(yaw) * 1.2, ey - uy * 2.6 + math.sin(yaw) * 1.2
        fallen((x, y), height(x, y) - 0.15, (x + math.cos(yaw) * 1.1, y + math.sin(yaw) * 1.1),
               height(x, y) - 0.2, 0.7, 0.6)  # a fallen block
    else:
        for a, r, tall, lean in ((-0.7, 2.4, 2.6, 0.04), (0.2, 2.8, 1.9, -0.1), (1.1, 2.2, 2.2, 0.08)):
            x, y = ex + math.cos(yaw + a) * r, ey + math.sin(yaw + a) * r
            standing(x, y, yaw + a + math.pi / 2, 0.9, 0.45, tall, lean=lean)
    if solid:
        for x, y, r in pillars:
            solid_circle(x, y, r)
            OLD_STONES.append((x, y, r))


OLD_STONES = []  # (x, y, r): stones you can get to (nothing grows in them)
lures = c.Builder()
for key, trail in LURES.items():
    (ex, ey), (bx, by) = trail[-1], trail[-2]
    kind, yaw = LURE_KINDS[key][0], math.atan2(ey - by, ex - bx)
    old_stones(lures, kind, ex, ey, yaw, solid=True)
    # The clue among them, facing the way you come: in the middle (through
    # the arch, just past it: further, by the witches, it's on the river's
    # bank).
    on = 0.8 if "arch" in kind else 0.0
    post_x, post_y = ex + math.cos(yaw) * on, ey + math.sin(yaw) * on
    note_post(built, key, post_x, post_y, height(post_x, post_y), (-math.cos(yaw), -math.sin(yaw)))
    solid_circle(post_x, post_y, 0.15)
# And some where you can get to them, so there's something to them: a ring
# in the meadow, between the grassy bank and the old stone wall; an arch at
# the forest's edge, to walk through; and a few among the yellow flowers.
# (Where they are [x, y], and which way they face.)
VISITED = [("ring", (-38, 13), math.pi / 2), ("arch", (-30, -70), math.pi / 2), ("stones", (-79, 64), math.pi)]
for kind, (x, y), yaw in VISITED:
    old_stones(lures, kind, x, y, yaw, solid=True)
lures.build("old-stones", smooth=False)

# A few brambles round each of the forest's dead ends: either side of where
# the trail goes on into the trees, and by the old stones. Mounds of leaves,
# canes arching out of them, thorny and purple-red, with blackberries on them
# (and a few still red), and here and there a white flower.
BRAMBLE_LEAVES = [c.linear(h) for h in ("#4a6e2c", "#557a31", "#3f6128", "#5c7f36")]
BRAMBLE_CANE = c.linear("#6d3b3f")
BERRIES = [c.linear(h) for h in ("#1e1024", "#2c1433", "#4a1d3f", "#b0303a")]
BRAMBLE_FLOWER = c.linear("#f1ece0")
brambles = c.Builder()


def bramble_cane(b, rng, x, y, z, yaw, reach, tall):
    """A cane arching out of a mound at [x, y, z], towards yaw: up, over and
    down again, `reach` metres out, with berries along it."""
    dx, dy = math.cos(yaw), math.sin(yaw)
    pts = [(x + dx * reach * t, y + dy * reach * t, z + tall * math.sin(math.pi * min(1.0, t * 0.85)) - 0.25 * t)
           for t in (0, 0.25, 0.5, 0.75, 1.0)]
    for k, (p, q) in enumerate(zip(pts, pts[1:])):
        b.cylinder(p, q, 0.016 * (1 - k * 0.18), 0.016 * (1 - (k + 1) * 0.18), BRAMBLE_CANE, sides=4)
    for p in pts[1:]:
        if rng.random() < 0.7:
            for n in range(rng.randint(1, 3)):
                b.blob((p[0] + rng.uniform(-0.06, 0.06), p[1] + rng.uniform(-0.06, 0.06), p[2] - rng.uniform(0.02, 0.07)),
                       0.024, rng.choice(BERRIES), subdivisions=1)


def bramble(rng, x, y, size, squash):
    """A mound of brambles at [x, y], `size` across (to its middle), and as
    much taller or flatter as `squash` says: solid."""
    tall = 2 * size * squash
    z = height(x, y) - 0.15
    brambles.blob((x, y, z + tall * 0.45), size, rng.choice(BRAMBLE_LEAVES), squash=squash, lumpy=0.22,
                  seed=rng.random() * 100, subdivisions=2)
    # Canes out of it, every which way.
    for n in range(rng.randint(2, 4)):
        bramble_cane(brambles, rng, x, y, z + tall * rng.uniform(0.5, 0.8), rng.uniform(0, 2 * math.pi),
                     rng.uniform(0.6, 1.3), rng.uniform(0.25, 0.5))
    # Berries in its leaves, and now and then a flower.
    for n in range(rng.randint(4, 9)):
        a, up = rng.uniform(0, 2 * math.pi), rng.uniform(0.2, 0.9)
        r = size * 0.97 * math.sqrt(1 - up * up)
        colour = BRAMBLE_FLOWER if rng.random() < 0.12 else rng.choice(BERRIES)
        brambles.blob((x + math.cos(a) * r, y + math.sin(a) * r, z + tall * 0.45 + up * tall * 0.5),
                      0.03 if colour is BRAMBLE_FLOWER else 0.025, colour, subdivisions=1)
    solid_circle(x, y, size * 0.85)


def thicket(key, spot):
    """A dead end's few brambles: in its clearing, either side of the trail
    on, and at the edge of the gap round its old stones (never on the way)."""
    px, py = P[key.split(" ")[0]]
    run = math.hypot(spot[0] - px, spot[1] - py)
    dx, dy = (spot[0] - px) / run, (spot[1] - py) / run  # on, past the path's end
    sx, sy = -dy, dx  # to the side
    rng = random.Random(f"brambles {key}")
    (ex, ey) = LURES[key][-1]
    spots = [(spot[0] + dx * rng.uniform(-0.5, 1.8) + sx * side * rng.uniform(3.5, 8),
              spot[1] + dy * rng.uniform(-0.5, 1.8) + sy * side * rng.uniform(3.5, 8))
             for side in (1, -1) for _ in range(3)]
    spots += [(ex + math.cos(a) * (GAP - 0.4), ey + math.sin(a) * (GAP - 0.4))
              for a in (rng.uniform(0, 2 * math.pi) for _ in range(3))]
    for x, y in spots:
        size = rng.uniform(0.6, 0.9)
        if trails.distance(x, y) < TRAIL_WALK + size + 0.5 or path_lines.distance(x, y) < 3 + size:
            continue
        bramble(rng, x, y, size, rng.uniform(0.62, 0.85))


for key, spot in CLUES.items():
    thicket(key, spot)
brambles.build("brambles", smooth=False)

def quad(builder, pts, colour, vary=0.12):
    # Anything lying flat faces up: facing down, the sun's shadows fall on it
    # in stripes ("shadow acne").
    (ax, ay, az), (bx, by, bz), (cx_, cy_, cz) = pts[0], pts[1], pts[2]
    ux, uy, uz, vx, vy, vz = bx - ax, by - ay, bz - az, cx_ - ax, cy_ - ay, cz - az
    nz = ux * vy - uy * vx
    if nz < 0 and abs(nz) > 0.5 * math.sqrt((uy * vz - uz * vy) ** 2 + (uz * vx - ux * vz) ** 2 + nz * nz):
        pts = pts[::-1]
    builder.add(pts, [(0, 1, 2, 3)], [c.vary(colour, vary, Vector(pts[0])) for _ in pts])


# The tower's stonework, inside and out: course on course of blocks, each
# its own shade, damp and mossy near the floor (the dark mortar between is
# the wall behind them).
TOWER_BLOCK, TOWER_FLAG = c.linear("#6e6a62"), c.linear("#615d55")
TOWER_DAMP, TOWER_MOSS = c.linear("#3f4434"), c.linear("#4a5a2c")
TOWER_MORTAR = c.linear("#3a3732")  # (outside: inside, it's the hall's wall)
COURSE, JOINT = (0.34, 0.48), 0.035  # how tall a course of blocks is, and the mortar between


def stone_shade(rnd, base, z, foot):
    """A stone's colour: its own shade, damp and sometimes mossy low down (above foot)."""
    t = rnd.uniform(-0.2, 0.35)
    colour = c.mix(base, c.linear("#000000"), t) if t > 0 else c.mix(base, c.linear("#a8a398"), -t)
    low = max(0.0, 1 - (z - foot) / 1.4)
    if rnd.random() < low * 0.8:
        colour = c.mix(colour, TOWER_DAMP, rnd.uniform(0.3, 0.7))
    if rnd.random() < low * 0.35:
        colour = c.mix(colour, TOWER_MOSS, rnd.uniform(0.3, 0.6))
    return colour


def stone_courses(b, rnd, at, corners, r, z0, z1, holes, foot):
    """The tower's wall in courses of blocks, from z0 to z1 (at: the point on
    the wall's face at an angle; corners: its corners' angles, where a block
    is split to lie flat on it; r: about how far out it is), each block a
    little longer or shorter, the joints never in line with the course's
    below, and none where the wall's open (holes: a0, a1, z0, z1, with
    angles from 0 to 4 pi)."""

    def on_wall(a0, a1, lo, hi, colour):
        cuts = [a0] + [k for k in corners if a0 < k < a1] + [a1]
        for b0, b1 in zip(cuts, cuts[1:]):
            p0, p1 = at(b0), at(b1)
            quad(b, [(*p0, lo), (*p1, lo), (*p1, hi), (*p0, hi)], colour, 0.05)

    def clear(rect):
        """The parts of a block (a0, a1, z0, z1) clear of the openings."""
        out = [rect]
        for lo, hi, h0, h1 in holes:
            left = []
            for a0, a1, za, zb in out:
                if a1 <= lo or a0 >= hi or zb <= h0 or za >= h1:
                    left.append((a0, a1, za, zb))
                    continue
                left += [(a0, a1, za, h0)] if za < h0 else []
                left += [(a0, a1, h1, zb)] if zb > h1 else []
                zl, zh = max(za, h0), min(zb, h1)
                left += [(a0, lo, zl, zh)] if a0 < lo else []
                left += [(hi, a1, zl, zh)] if a1 > hi else []
            out = left
        return out

    z = z0
    while z < z1 - 0.05:
        h = min(rnd.uniform(*COURSE), z1 - z)
        start = a = rnd.uniform(0.2, 0.7) / r
        while a < start + 2 * math.pi - 0.3 / r:
            a1 = min(a + rnd.uniform(0.55, 1.15) / r, start + 2 * math.pi)
            colour = stone_shade(rnd, TOWER_BLOCK, z, foot)
            for a0_, a1_, z0_, z1_ in clear((a + JOINT / r / 2, a1 - JOINT / r / 2, z + JOINT / 2, z + h - JOINT / 2)):
                if (a1_ - a0_) * r > 0.04 and z1_ - z0_ > 0.04:
                    on_wall(a0_, a1_, z0_, z1_, colour)
            a = a1
        z += h


def porch(x, y_wall, y_lip, half, colour):
    """Where a building's doorway sticks out of its wall (to the lip, where
    you step in): its walls and roof are only its inside, seen from in it;
    from outside, they're a thick stone shell round it, solid, so you can't
    walk into them and look through."""
    y0, y1 = sorted((y_wall, y_lip))
    thick = 0.45
    way = next(w for w in WAYS.values() if w.indoor and math.hypot(w.points[0][0] - x, w.points[0][1] - y_lip) < 0.1)
    roof = max(p[2] for p in way.points) + TUNNEL_TALL + 0.02
    top = roof + 0.35
    low = min(height(x + dx, y) for dx in (-half - thick, half + thick) for y in (y0, y1)) - 0.4
    for x0, x1 in ((x - half - 0.02 - thick, x - half - 0.02), (x + half + 0.02, x + half + 0.02 + thick)):
        block(built, x0, y0, low, x1, y1, top, colour)
    block(built, x - half - 0.02 - thick, y0, roof, x + half + 0.02 + thick, y1, top, colour, solid=False)


# The tower on its knoll, with the balcony high on its east side, and the
# mossy steps up to it.
# Its round wall, with a door in the south side (the doorway's own walls and
# roof line the gap), and its flat top and roof.
SIDES = 24
tz0, tz1 = height(*TOWER) - 0.5, height(*TOWER) - 0.5 + 20
door_top = HALLS["tower"].floor + TUNNEL_TALL - 0.3  # under the doorway's roof (which slopes down a little), so there's no gap
ring = [(TOWER[0] + math.cos(-math.pi / 2 + 2 * math.pi * k / SIDES) * TOWER_R,
         TOWER[1] + math.sin(-math.pi / 2 + 2 * math.pi * k / SIDES) * TOWER_R) for k in range(SIDES)]
# Its windows (TOWER_WINDOWS), through both its walls: their stone sills,
# lintels and sides through the wall between.
for k in range(SIDES):
    p0, p1 = ring[k], ring[(k + 1) % SIDES]
    door = k in (0, SIDES - 1)  # the two sides either side of due south
    shade = [c.vary(TOWER_MORTAR, 0.06, Vector((*p0, 1.0)))] * 4  # (the mortar: its stones go on in front)
    a0 = -math.pi / 2 + 2 * math.pi * k / SIDES
    for piece in wall_pieces(p0, p1, a0, a0 + 2 * math.pi / SIDES, door_top if door else tz0, tz1, HALLS["tower"].floor,
                             lambda a: polygon_at(a, TOWER_R, SIDES, -math.pi / 2)):
        built.add(piece, [(0, 1, 2, 3)], shade)
for a, half, z0, z1 in TOWER_WINDOWS:
    angles = (a - half, a, a + half)
    inside = [polygon_at(t, HALLS["tower"].r + 0.35, 32, 0) for t in angles]  # (round_room's wall)
    outside = [polygon_at(t, TOWER_R, SIDES, -math.pi / 2) for t in angles]
    sill, lintel = HALLS["tower"].floor + z0, HALLS["tower"].floor + z1
    for k in range(2):
        for z, colour in ((sill, STONE), (lintel, GREY)):  # (facing up, both: see quad())
            pts = [(*inside[k], z), (*outside[k], z), (*outside[k + 1], z), (*inside[k + 1], z)]
            built.add(pts, [(0, 1, 2, 3)], [c.vary(colour, 0.06, Vector(pts[0]))] * 4)
    for k in (0, 2):
        # (Each facing into the window: facing into the stone, the sun's
        # shadows fall on it in stripes.)
        pts = [(*inside[k], sill), (*outside[k], sill), (*outside[k], lintel), (*inside[k], lintel)]
        built.add(pts if k else pts[::-1], [(0, 1, 2, 3)], [c.vary(GREY, 0.06, Vector(pts[0]))] * 4)
built.add([(*p, tz1) for p in ring], [tuple(range(SIDES))], [GREY] * SIDES)
# Its stones, outside as in, a little out from the wall (all round, but at
# the doorway, where the porch is, and the windows).
door_half = 2 * math.pi / SIDES
outside_holes = [((-math.pi / 2 - door_half) % (2 * math.pi), (-math.pi / 2 - door_half) % (2 * math.pi) + 2 * door_half,
                  tz0 - 1, door_top)]
outside_holes += [((a - half) % (2 * math.pi), (a - half) % (2 * math.pi) + 2 * half, HALLS["tower"].floor + z0,
                   HALLS["tower"].floor + z1) for a, half, z0, z1 in TOWER_WINDOWS]
outside_holes += [(lo + 2 * math.pi, hi + 2 * math.pi, h0, h1) for lo, hi, h0, h1 in outside_holes]
stone_courses(built, random.Random("tower's outside stones"), lambda a: polygon_at(a, TOWER_R + 0.03, SIDES, -math.pi / 2),
              [-math.pi / 2 + 2 * math.pi * k / SIDES for k in range(2 * SIDES + 3)], TOWER_R, tz0, tz1, outside_holes,
              height(*TOWER))
# Its roof: a tall cone of slates, a little flared at its foot, out over the
# wall at its eaves (an edge to them, and under them flat, so from below you
# see them, not up inside it).
EAVE_R = TOWER_R * 1.15
ROOF_PROFILE = [(EAVE_R, tz1 - 0.3), (EAVE_R * 0.87, tz1 + 1.3), (EAVE_R * 0.6, tz1 + 4.6), (EAVE_R * 0.31, tz1 + 8.2)]


def round_roof(r, z):
    return [(*polygon_at(-math.pi / 2 + 2 * math.pi * k / SIDES, r, SIDES, -math.pi / 2), z) for k in range(SIDES)]


rings = [round_roof(r, z) for r, z in ROOF_PROFILE]
apex = (*TOWER, tz1 + 11.5)
for n, (lower, upper) in enumerate(zip(rings, rings[1:] + [None])):
    for k in range(SIDES):
        k1 = (k + 1) % SIDES
        shade = c.vary(c.mix(ROOF, c.linear("#000000"), 0.12 * (n == 0)), 0.07, Vector((*lower[k][:2], n)))
        if upper:
            built.add([lower[k], lower[k1], upper[k1], upper[k]], [(0, 1, 2, 3)], [shade] * 4)
        else:
            built.add([apex, lower[k], lower[k1]], [(0, 1, 2)], [shade] * 3)
fascia = round_roof(EAVE_R, tz1 - 0.55)
soffit = round_roof(TOWER_R + 0.02, tz1 - 0.55)
for k in range(SIDES):
    k1 = (k + 1) % SIDES
    edge = c.mix(ROOF, c.linear("#000000"), 0.3)
    built.add([fascia[k], fascia[k1], rings[0][k1], rings[0][k]], [(0, 1, 2, 3)], [edge] * 4)
    built.add([fascia[k], soffit[k], soffit[k1], fascia[k1]], [(0, 1, 2, 3)], [c.mix(ROOF, c.linear("#000000"), 0.45)] * 4)
solid_circle(*TOWER, TOWER_R)
fl = HALLS["tower"].floor
porch(TOWER[0], TOWER[1] - HALLS["tower"].r - 0.37, TOWER_LIP[1], WAYS["tower-door"].half, GREY)  # (from the round room's wall)
block(built, TOWER[0] - 1.6, TOWER[1] - TOWER_R - 0.2, fl - 0.6, TOWER[0] + 1.6, TOWER[1] - TOWER_R + 0.6, fl - 0.02,
      STONE, solid=False)  # the sill under the door


def out_from_tower(u, v):
    """A spot u out from the tower's middle, the way the balcony faces, and v across."""
    fx, fy = math.cos(TOWER_FACING), math.sin(TOWER_FACING)
    return TOWER[0] + fx * u - fy * v, TOWER[1] + fy * u + fx * v


def balcony_block(u0, v0, u1, v1, z0, z1):
    """A box, square to the way the balcony faces."""
    corners = [out_from_tower(u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))]
    v = [(*p, z0) for p in corners] + [(*p, z1) for p in corners]
    shade = [c.vary(TOWER_BLOCK, 0.1, Vector((*corners[0], z0 + k))) for k in range(8)]  # (the tower's stone)
    built.add(v, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (0, 3, 2, 1)], shade)


# The balcony, out under the window: level with the landing inside, with a
# parapet round it, on two stone brackets.
bz = fl + TOWER_LANDING
bu0, bu1, bv = 5.5, 8.5, 2.0
# (Where the ladder's top rests: under the edge of the balcony's side towards
# the mossy steps, past its bracket, so it faces you coming up them.)
LADDER_TOP = (*out_from_tower(7.9, -bv + 0.15), bz - 0.42)
balcony_block(bu0, -bv, bu1, bv, bz - 0.4, bz)
for u0, v0, u1, v1 in ((bu1 - 0.25, -bv, bu1, bv), (bu0, -bv, bu1 - 0.25, -bv + 0.25), (bu0, bv - 0.25, bu1 - 0.25, bv)):
    balcony_block(u0, v0, u1, v1, bz, bz + 0.9)
for v in (-1.3, 1.3):
    balcony_block(bu0, v - 0.25, 7.2, v + 0.25, bz - 1.4, bz - 0.4)
# The mossy steps: what slithers or lies on them is on top of them (STEPS).
STEPS = []
for k in range(6):
    sy = P["mossy-steps"][1] + 18 + k * 1.4
    block(built, TOWER[0] - 2, sy, height(TOWER[0], sy) - 0.4, TOWER[0] + 2, sy + 1.4, height(TOWER[0], sy) + 0.15,
          c.linear("#7f8f6a"), solid=False)
    STEPS.append([TOWER[0], round(-(sy + 0.7), 2), 2, 0.7, round(height(TOWER[0], sy) + 0.15, 2)])
# The snake, coiled at the top of the steps (and the stone that shuts you in,
# from inside), and the balcony, too high to reach from the ground under it.
# (The snake's round, in the doorway at the wall's line, so its far side is
# in the tower, where you can't be on the land: it reaches out just past its
# coil in front of the door, and stops you from every side (coming round
# the tower's wall from the east, you'd come into it from its far side).
# That leaves the way round to the ladder under the balcony, whose reach
# covers the balcony and the ladder's foot, and no more. The stone is indoors, for the way out, its
# middle just before you're far enough in to be in the tower (the round
# room's edge, less your body's 0.35 m, player.ts): once you're in the
# tower, you're past it, and shut in. Any further in, and you'd be in the
# tower but not past it, and could still turn back and walk out.)
obstacle(["mossy-steps north"], "circle", TOWER[0], -(TOWER[1] - TOWER_R), 0.8, reach=2.4, all_round=True)
# The enormous stone: waiting beside the door, to the west (out of the way
# round to the balcony), until you're in the tower, when the game rolls it
# across the doorway, just outside it, where the snake was; using the ring,
# it rolls back. Its own object, round its middle, so it turns as it rolls.
STONE_R = 2.0
stone = c.Builder()
stone.blob((0, 0, 0), STONE_R, c.linear("#8a8478"), squash=0.9, lumpy=0.18, seed=11, subdivisions=3, lit=False)
stone_y = TOWER_LIP[1] - STONE_R - 0.05  # (just outside the doorway: in it, it would roll through its sides)
STONE_SPOTS = {k: (x, stone_y, height(x, stone_y) + STONE_R * 0.75) for k, x in (("aside", TOWER[0] - 5.0), ("door", TOWER[0]))}
stone.build("stone", smooth=False).location = STONE_SPOTS["aside"]
solid_circle(*STONE_SPOTS["aside"][:2], STONE_R * 0.9)
stone_at = HALLS["tower"].r - 0.35 + 0.15
obstacle(["tower south"], "box", TOWER[0], -(TOWER[1] - stone_at), 1.6, 0.5, under=True, reach=1.5)  # (so you can walk round the room)
bx, by = out_from_tower(7.4, -0.8)  # (under the balcony, and with its reach, all of it, and the ladder's foot)
obstacle(["mossy-steps east"], "circle", bx, -by, 2.6, reach=0.4)

# Merlin's trap, east of the mountain, where its path ends: a pile of
# treasure, glinting, to tempt you on (a chest, gold spilling round it, a
# goblet), with an old oak leaning over it, among the firs. Come near, and
# the net hidden in front of it scoops you up, to dangle from the oak (the
# game plays it: trap.ts).
PROPS = c.Kit(HERE.parent / "models/fantasy-props-megakit/Exports/glTF")
TX, TY = DEATHS["mountain east"]
TZ = height(TX, TY)
GOLD = (*c.linear("#e0a024")[:3], 1.0)  # (the kit's metal is silvery: all gold, deep, as it shines)
HEAP = c.linear("#dba22a")
here = random.Random("Merlin's trap")
# (The gold and the jewels on their own, for the game to make them shine.)
gold = c.Builder()
jewels = c.Builder()
# The chest, open, facing the way you come, full to the brim with gold; and
# a heap of it spilling out in front, coins and a goblet on it, and more
# rolled away.
CHEST_AT = (TX + 0.95, TY)
PROPS.put(built, "Chest_Wood", (*CHEST_AT, height(*CHEST_AT) - 0.03), -math.pi / 2, 1.2)
gold.blob((*CHEST_AT, height(*CHEST_AT) + 0.5), 0.5, HEAP, squash=0.35, lumpy=0.12, seed=3)
gold.blob((TX - 0.1, TY, TZ - 0.12), 0.9, HEAP, squash=0.5, lumpy=0.14, seed=5)
for name, u, v, up, yaw, scale in (("Coin_Pile_2", -0.15, 0.15, 0.28, 0.3, 2.8), ("Coin_Pile", -0.55, 0.45, 0.06, 1.9, 2.4),
                                   ("Coin_Pile", 0.05, -0.55, 0.08, -0.6, 2.2), ("Coin_Pile_2", 1.0, 0.05, 0.52, 2.0, 2.2),
                                   ("Chalice", -0.1, -0.2, 0.25, 0.8, 2.4)):
    x, y = TX + u, TY + v
    PROPS.put(gold, name, (x, y, height(x, y) + up), yaw, scale, tint=GOLD)
for n in range(14):
    a, r = here.uniform(0, 2 * math.pi), here.uniform(0.75, 1.7)
    x, y = TX - 0.1 + math.cos(a) * r, TY + math.sin(a) * r
    PROPS.put(gold, "Coin", (x, y, height(x, y)), here.uniform(0, 2 * math.pi), 2.2, tint=GOLD)
# And jewels among it, rubies and emeralds, cut and gleaming: on the heap, in
# the chest, and one or two fallen on the path. (Their own random numbers,
# so the oak's as it was.)
JEWELS = {"ruby": c.linear("#e8173f"), "emerald": c.linear("#1fd06e")}
jewel_spots = []  # [x, y, z, "ruby" or "emerald"], in three.js's axes, for the glints on them
gems = random.Random("Merlin's jewels")


def on_heap(x, y):
    """How high the gold is here: on the heap in front, or in the chest."""
    d = math.hypot(x - (TX - 0.1), y - TY)
    heap = TZ - 0.12 + 0.45 * math.sqrt(max(0.0, 1 - (d / 0.9) ** 2)) if d < 0.9 else None
    d = math.hypot(x - CHEST_AT[0], y - CHEST_AT[1])
    chest = height(*CHEST_AT) + 0.5 + 0.175 * math.sqrt(max(0.0, 1 - (d / 0.5) ** 2)) if d < 0.5 else None
    return max((h for h in (heap, chest) if h is not None), default=height(x, y))


for n in range(16):
    kind = "ruby" if n % 2 else "emerald"
    if n < 10:
        a, r = gems.uniform(0, 2 * math.pi), 0.8 * math.sqrt(gems.random())
        x, y = TX - 0.1 + math.cos(a) * r, TY + math.sin(a) * r
    elif n < 14:
        x, y = CHEST_AT[0] + gems.uniform(-0.15, 0.15), CHEST_AT[1] + gems.uniform(-0.3, 0.3)
    else:
        a, r = gems.uniform(-1, 1) + math.pi, gems.uniform(1.0, 1.5)
        x, y = TX - 0.1 + math.cos(a) * r, TY + math.sin(a) * r
    size = gems.uniform(0.08, 0.13)
    z = on_heap(x, y) + size * 0.4
    jewels.blob((x, y, z), size, JEWELS[kind], squash=0.75, lumpy=0.0, seed=n, subdivisions=0)
    jewel_spots.append([round(x, 2), round(z, 2), round(-y, 2), kind])
# More gold on the heap, coins lying all over it.
for n in range(18):
    a, r = gems.uniform(0, 2 * math.pi), 0.85 * math.sqrt(gems.random())
    x, y = TX - 0.1 + math.cos(a) * r, TY + math.sin(a) * r
    PROPS.put(gold, "Coin", (x, y, on_heap(x, y) - 0.01), gems.uniform(0, 2 * math.pi), 2.2, tint=GOLD)
gold.build("treasure", smooth=False)
jewels.build("jewels", smooth=False)
# Where the net lies, on the path in front of the treasure, as near as you
# come to it (the trap's reach, round the treasure, below).
TRAP_REACH = (1.0, 2.0)
TRAP_NET = (TX - sum(TRAP_REACH), TY)
# The oak, up the slope to the north (so its leaves are high over the path,
# clear of you, swinging in the net under them), and where the net's rope's
# tied, up in its leaves, over the path.
TRAP_OAK = (TRAP_NET[0] + 0.3, TRAP_NET[1] + 3.8)
TRAP_HOOK = (TRAP_NET[0], TRAP_NET[1] + 0.3, height(*TRAP_NET) + 10.4)
grow(*TRAP_OAK, 11, "CommonTree_2", here, sink=0.4)
solid_circle(*TRAP_OAK, 0.6)
obstacle(["mountain east"], "circle", TX, -TY, TRAP_REACH[0], reach=TRAP_REACH[1])

# The witches, on the way west to the crossroads.
wx, wy = P["forest-witches"]
obstacle(["forest-witches west"], "box", (wx + P["forest-crossroads"][0]) / 2, -wy, 1.0, 5.5)

# A sign by the paths' crossing in the witches' clearing, on the corner
# south of the way west, facing east: you read it looking west, towards the
# witches; coming from them, you see only its back. A post, and two rough
# planks nailed across it, one above the other, a little askew. Its words are
# painted on in the game (sign.ts), in your language: here, only where they go
# (SIGN, in land.json).
SIGN_POST = (wx - 3.4, wy - 3.3)  # (south of the way west, just off its edge)
SIGN_WOOD, SIGN_DARK = c.linear("#8d7457"), c.linear("#5c4a36")
SIGN_TILT = math.radians(3)  # how askew its planks are nailed (the north end up)
SIGN_FACE = (1.2, 0.54)  # the painted face, across and up: a little in from its planks' edges
sx, sy = SIGN_POST
s_ground = height(sx, sy)
built.cylinder((sx, sy, s_ground - 0.3), (sx, sy, s_ground + 1.72), 0.08, 0.07, SIGN_DARK, sides=6)
solid_circle(sx, sy, 0.2)
SIGN_MIDDLE = Vector((sx + 0.08 + 0.03, sy, s_ground + 1.3))  # the planks' middle, in front of the post
sign_across = Vector((0, math.cos(SIGN_TILT), math.sin(SIGN_TILT)))  # (to your right, reading it: north)
sign_up = Vector((0, -math.sin(SIGN_TILT), math.cos(SIGN_TILT)))
sign_rnd = random.Random("witches' sign")
# Each plank: its middle, up from the sign's, and half its height.
for k, (mid, half) in enumerate([(0.15, 0.135), (-0.15, 0.135)]):
    # Its outline, roughly cut: each end a little uneven.
    ends = [(-0.72 + sign_rnd.uniform(0, 0.05), -half), (0.72 - sign_rnd.uniform(0, 0.05), -half),
            (0.74 - sign_rnd.uniform(0, 0.03), 0), (0.72 - sign_rnd.uniform(0, 0.05), half),
            (-0.72 + sign_rnd.uniform(0, 0.05), half), (-0.74 + sign_rnd.uniform(0, 0.03), 0)]
    face = [SIGN_MIDDLE + sign_across * s + sign_up * (mid + t * 0.96) for s, t in ends]
    back = [p - Vector((0.04, 0, 0)) for p in face]
    n = len(face)
    shade = c.mix(SIGN_WOOD, c.linear("#000000"), 0.1 * k)
    built.add([tuple(p) for p in face + back],
              [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))] +
              [(i, n + i, n + (i + 1) % n, (i + 1) % n) for i in range(n)],
              [c.vary(shade, 0.12, p * 4) for p in face + back])
# (The face's middle, and which way it faces, for its words: in three.js's axes.)
SIGN = {"at": [round(SIGN_MIDDLE.x + 0.004, 3), round(SIGN_MIDDLE.z, 3), round(-SIGN_MIDDLE.y, 3)],
        "facing": [1, 0], "tilt": round(SIGN_TILT, 4), "size": list(SIGN_FACE)}


# The charcoal burner's hut, as in its picture: round, a wall of upright
# logs with an opening in it facing north to the crossroads, and a cone of a
# roof, its planks laid in courses on rafters, with a hole at the top for the
# smoke of the fire in the middle (charcoal_hut) to go out by.
hx, hy = HUT
fl = HALLS["charcoal-hut"].floor
HUT_LOGS = HUT_R - 0.17  # the logs' middles
EAVE = fl + 2.5  # the top of the wall
HUT_EAVE_R, HUT_HOLE_R = 5.0, 0.55  # the roof's edge, out over the wall, and the smoke hole
HUT_LOW, HUT_TOP = fl + 2.25, fl + 5.7  # their heights
HUT_OPEN = 1.35  # half the opening, to its posts' middles
HUT_WOOD, HUT_DARK = c.linear("#8a6a48"), c.linear("#5a4430")
hut_rnd = random.Random("charcoal hut")  # (its own: a change anywhere else doesn't move its logs)


def hut_roof(r, under=0.0):
    """The roof's height at r out from the middle (its underside, under it)."""
    return HUT_LOW + (HUT_EAVE_R - r) * (HUT_TOP - HUT_LOW) / (HUT_EAVE_R - HUT_HOLE_R) - under


def log(b, p0, p1, r, colour, sides=6):
    """A round log from one end to the other, any way up."""
    p0, p1 = Vector(p0), Vector(p1)
    along = (p1 - p0).normalized()
    u = along.cross(Vector((0, 0, 1)) if abs(along.z) < 0.9 else Vector((1, 0, 0))).normalized()
    v = along.cross(u)
    verts, colours = [], []
    for k in range(sides):
        a = 2 * math.pi * k / sides
        off = (u * math.cos(a) + v * math.sin(a)) * r
        verts += [tuple(p0 + off), tuple(p1 + off)]
        colours += [c.vary(colour, 0.15, p0 + off * 3), c.vary(colour, 0.15, p1 + off * 3)]
    faces = [(2 * k, 2 * ((k + 1) % sides), 2 * ((k + 1) % sides) + 1, 2 * k + 1) for k in range(sides)]
    b.add(verts, faces, colours)


def ring_at(r, a):
    return hx + math.cos(a) * r, hy + math.sin(a) * r


# The wall: logs standing side by side, round all but the opening.
n = int(2 * math.pi * HUT_LOGS / 0.31)
for k in range(n):
    a = 2 * math.pi * (k + 0.5) / n
    x, y = ring_at(HUT_LOGS, a)
    if y > hy and abs(x - hx) < HUT_OPEN + 0.15:
        continue
    shade = c.mix(HUT_WOOD, c.linear("#000000"), hut_rnd.uniform(-0.15, 0.3))
    built.cylinder((x, y, min(fl, height(x, y)) - 0.4), (x, y, EAVE + hut_rnd.uniform(0, 0.12)), 0.17, 0.16, shade)
# Either side of the opening, a stouter post, and a lintel across between them.
oy = hy + math.sqrt(HUT_LOGS ** 2 - HUT_OPEN ** 2)
for side in (-1, 1):
    built.cylinder((hx + side * HUT_OPEN, oy, min(fl, height(hx + side * HUT_OPEN, oy)) - 0.4),
                   (hx + side * HUT_OPEN, oy, EAVE + 0.1), 0.21, 0.19, HUT_DARK, sides=8)
log(built, (hx - HUT_OPEN - 0.25, oy, EAVE - 0.12), (hx + HUT_OPEN + 0.25, oy, EAVE - 0.12), 0.14, HUT_DARK)
# Round the top of the wall, a ring of logs the rafters rest on.
for k in range(32):
    a0, a1 = 2 * math.pi * k / 32, 2 * math.pi * (k + 1) / 32
    log(built, (*ring_at(HUT_LOGS, a0 - 0.02), EAVE + 0.05), (*ring_at(HUT_LOGS, a1 + 0.02), EAVE + 0.05), 0.15, HUT_DARK)
# The roof: planks in five courses, each overlapping the one below, every
# plank its own weathered shade; under them, sooty boards, and the rafters
# and rings of poles that hold them up; and a collar round the smoke hole.
SIDES_ROOF = 48
for course in range(5):
    r0 = HUT_EAVE_R - course * (HUT_EAVE_R - HUT_HOLE_R) / 5 + (0.1 if course else 0)
    r1 = HUT_EAVE_R - (course + 1) * (HUT_EAVE_R - HUT_HOLE_R) / 5
    z0, z1 = hut_roof(r0) + (-0.06 if course else 0), hut_roof(r1)
    turn = hut_rnd.uniform(0, 1)  # (the joins between planks not lining up from course to course)
    for k in range(SIDES_ROOF):
        a0, a1 = 2 * math.pi * (k + turn) / SIDES_ROOF, 2 * math.pi * (k + 1 + turn) / SIDES_ROOF
        shade = c.mix(c.linear("#8a7052"), c.linear("#3a2e22"), hut_rnd.uniform(0, 0.4))
        quad(built, [(*ring_at(r0, a0), z0), (*ring_at(r0, a1), z0), (*ring_at(r1, a1), z1), (*ring_at(r1, a0), z1)],
             shade, 0.08)
for k in range(SIDES_ROOF):
    a0, a1 = 2 * math.pi * k / SIDES_ROOF, 2 * math.pi * (k + 1) / SIDES_ROOF
    r0, r1 = HUT_EAVE_R - 0.05, HUT_HOLE_R
    quad(built, [(*ring_at(r0, a0), hut_roof(r0, 0.12)), (*ring_at(r0, a1), hut_roof(r0, 0.12)),
                 (*ring_at(r1, a1), hut_roof(r1, 0.12)), (*ring_at(r1, a0), hut_roof(r1, 0.12))],
         c.linear("#2e241c"), 0.15)
    # (And the hole's rim, between them.)
    quad(built, [(*ring_at(r1, a0), hut_roof(r1, 0.12)), (*ring_at(r1, a1), hut_roof(r1, 0.12)),
                 (*ring_at(r1, a1), hut_roof(r1)), (*ring_at(r1, a0), hut_roof(r1))], c.linear("#2e241c"), 0.15)
for k in range(16):
    a = 2 * math.pi * k / 16
    log(built, (*ring_at(HUT_EAVE_R - 0.2, a), hut_roof(HUT_EAVE_R - 0.2, 0.2)),
        (*ring_at(HUT_HOLE_R + 0.1, a), hut_roof(HUT_HOLE_R + 0.1, 0.2)), 0.07, HUT_DARK)
for r in (3.2, 1.8):
    for k in range(16):
        a0, a1 = 2 * math.pi * k / 16, 2 * math.pi * (k + 1) / 16
        log(built, (*ring_at(r, a0), hut_roof(r, 0.29)), (*ring_at(r, a1), hut_roof(r, 0.29)), 0.06, HUT_DARK)
for k in range(12):
    a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12
    r = HUT_HOLE_R + 0.06
    log(built, (*ring_at(r, a0 - 0.05), hut_roof(r) + 0.05), (*ring_at(r, a1 + 0.05), hut_roof(r) + 0.05), 0.07, HUT_DARK)
solid_circle(hx, hy, HUT_R)

# The pile of leaves filling the mouth of the dragon's cave, just inside (the
# game heaps them up there, and sweeps them aside, leaves.ts): and where they
# go, swept, in heaps either side of the mouth, outside.
lx, ly = DRAGON_LIP[0] + 3, DRAGON_LIP[1]
LEAF_HEAPS = [(DRAGON_LIP[0] - 1.2, DRAGON_LIP[1] + side * (TUNNEL_HALF + 1.4)) for side in (1, -1)]

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

# What it looks like: the kit's stone (the game puts its texture on, by
# where each face is: maze.ts), only shaded here, mossy at its foot, and
# ivy hanging down from its tops, here and there. Its floor, flagstones
# (the texture again), just over the ground.
MAZE_THICK, MAZE_TALL = 0.35, 2.9  # half its thickness, and its height over the ground
MAZE_FLOOR = 0.14  # how far its floor's over the ground (what's dropped there lies on it, not under it)
MAZE_MOSS = c.linear("#9fae7a")
MAZE_LIGHT = c.linear("#ffffff")
maze = c.Builder()
maze_floor = c.Builder()
runs = []  # (along x?, the line it's on, from, to), in cells


def maze_wall(x0, y0, x1, y1):
    if y0 == y1:
        runs.append((True, round((y0 - my0) / MAZE_CELL), round((min(x0, x1) - mx0) / MAZE_CELL),
                     round((max(x0, x1) - mx0) / MAZE_CELL)))
    else:
        runs.append((False, round((x0 - mx0) / MAZE_CELL), round((min(y0, y1) - my0) / MAZE_CELL),
                     round((max(y0, y1) - my0) / MAZE_CELL)))


def maze_run(along_x, line, a, b):
    """One straight stretch of wall, from cell a to cell b along its line."""
    lo, hi = a * MAZE_CELL - MAZE_THICK, b * MAZE_CELL + MAZE_THICK
    at = line * MAZE_CELL
    if along_x:
        x0, x1, y0, y1 = mx0 + lo, mx0 + hi, my0 + at - MAZE_THICK, my0 + at + MAZE_THICK
    else:
        x0, x1, y0, y1 = mx0 + at - MAZE_THICK, mx0 + at + MAZE_THICK, my0 + lo, my0 + hi
    grounds = [height(x0 + (x1 - x0) * k / 8, y0 + (y1 - y0) * k / 8) for k in range(9)]
    # (Those along x a hair taller, so where two meet their tops don't fight.)
    z0, z1 = min(grounds) - 0.6, max(grounds) + MAZE_TALL + (0.02 if along_x else 0)
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    shade = [c.mix(MAZE_LIGHT, MAZE_MOSS, 0.6 if k < 4 else 0.0) for k in range(8)]
    maze.add(v, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)], shade)
    solid_box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2)
    # Ivy, hanging down from its top, here and there, either side.
    length = hi - lo
    for side in (1, -1):
        t = maze_rng.uniform(0.5, 4)
        while t < length - 0.8:
            wide, drop = maze_rng.uniform(0.8, 2.2), maze_rng.uniform(0.8, 2.6)
            for _ in range(int(wide * drop * 40)):
                u = maze_rng.uniform(-1, 1)
                reach = drop * (1 - 0.6 * u * u) * maze_rng.uniform(0.55, 1.0)
                down = reach * maze_rng.random() ** 1.4
                lt = min(max(lo + t + u * wide / 2, lo + 0.05), hi - 0.05)
                size, spin = maze_rng.uniform(0.12, 0.2), maze_rng.uniform(0, 2 * math.pi)
                out = MAZE_THICK + maze_rng.uniform(0.01, 0.06)
                if along_x:
                    cx, cy, d, n = mx0 + lt, my0 + at + out * side, (1, 0), (0, side)
                else:
                    cx, cy, d, n = mx0 + at + out * side, my0 + lt, (0, 1), (side, 0)
                cz = z1 + 0.03 - size - down  # (its tip at the most just over the top)
                corners = []
                for ang, r in ((0, 1.0), (math.pi / 2, 0.6), (math.pi, 0.5), (3 * math.pi / 2, 0.6)):
                    along_, up_ = math.cos(spin + ang) * size * r, math.sin(spin + ang) * size * r
                    corners.append((cx + d[0] * along_, cy + d[1] * along_, cz + up_))
                leaf = c.mix(*IVY, maze_rng.random())
                facing(built, corners, [leaf, c.mix(leaf, IVY[0], 0.4), c.mix(leaf, IVY[0], 0.6), leaf], (*n, 0))
            t += wide + maze_rng.uniform(3, 9)


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
# The walls, joined into long straight runs.
for along_x in (True, False):
    lines = {}
    for ax, line, a, b in runs:
        if ax == along_x:
            lines.setdefault(line, []).append((a, b))
    for line, pieces in sorted(lines.items()):
        pieces.sort()
        a, b = pieces[0]
        for pa, pb in pieces[1:]:
            if pa == b:
                b = pb
            else:
                maze_run(along_x, line, a, b)
                a, b = pa, pb
        maze_run(along_x, line, a, b)
maze.build("maze", smooth=False)
# Its floor, a little over the ground (and the tunnels' stone lips): on the ground's own grid (and split
# the way it is), so the ground never comes up through it.
def maze_lines(lo, hi, origin):
    k = math.floor((lo - origin) / STEP) + 1
    inside = [origin + i * STEP for i in range(k, math.ceil((hi - origin) / STEP))]
    return [lo] + [v for v in inside if lo < v < hi] + [hi]


xs, ys = maze_lines(mx0, mx0 + 2 * MAZE_HALF, X0), maze_lines(my0, my0 + 2 * MAZE_HALF, Y0)
for i in range(len(xs) - 1):
    for j in range(len(ys) - 1):
        pts = [(xs[i], ys[j]), (xs[i + 1], ys[j]), (xs[i + 1], ys[j + 1]), (xs[i], ys[j + 1])]
        maze_floor.add([(x, y, drawn_height(x, y, exactly=True) + MAZE_FLOOR) for x, y in pts], [(0, 1, 2), (0, 2, 3)],
                       [MAZE_LIGHT] * 4)
# And its edge, all round it, from its top down into the ground: a low step
# up onto it (at the way in, you'd see under it).
MAZE_EDGE = c.linear("#c9c2b4")  # (a little darker than its top)
for line, along_x, out_ in ((ys[0], True, (0, -1, 0)), (ys[-1], True, (0, 1, 0)),
                            (xs[0], False, (-1, 0, 0)), (xs[-1], False, (1, 0, 0))):
    edge = xs if along_x else ys
    for a, b in zip(edge, edge[1:]):
        (x0, y0), (x1, y1) = ((a, line), (b, line)) if along_x else ((line, a), (line, b))
        top0, top1 = (drawn_height(x, y, exactly=True) for x, y in ((x0, y0), (x1, y1)))
        facing(maze_floor, [(x0, y0, top0 - 0.3), (x1, y1, top1 - 0.3), (x1, y1, top1 + MAZE_FLOOR),
                            (x0, y0, top0 + MAZE_FLOOR)], [MAZE_EDGE] * 4, out_)
maze_floor.build("maze-floor", smooth=True)
# Boulders at the foot of its south wall, either side of the way in: past
# them, between the wall and the crags, there's only a narrow strip, which
# you'd only get stuck in.
for bx, by, size, seed in ((5.0, -0.95, 0.85, 1), (6.3, -0.75, 0.55, 2), (-5.6, -0.95, 0.85, 3), (-6.9, -0.7, 0.55, 4)):
    x, y = MZ[0] + bx, my0 + by
    built.blob((x, y, height(x, y) + size * 0.35), size, c.mix(ROCK, MOSS, 0.25 + 0.1 * (seed % 2)),
               squash=0.75, lumpy=0.25, seed=40 + seed)
    solid_circle(x, y, size * 0.95)
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
LINTEL_DROP = 0.03  # how far over a door hangs below its doorway's roof
kw, ke, ks, kn = KEEP
# (A shade narrower than the way in, so its walls meet the sides of the
# doorway: any wider, and there's a slit between them, into the keep.)
door = TUNNEL_HALF - 0.05
for x0, x1 in ((kw, GH[0] - door), (GH[0] + door, ke)):
    block(built, x0, kn - 1, 0, x1, kn, KEEP_TALL, GREY, solid=False)
# (Over the door: a shade below the doorway's roof, not level with it,
# where the two would flicker against each other in blocky stripes.)
block(built, GH[0] - door, kn - 1, TUNNEL_TALL + 0.4 - LINTEL_DROP, GH[0] + door, kn, KEEP_TALL, GREY, solid=False)
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
wide = 2.4 - 0.05  # (a shade narrower than the way in, as at the keep's door)
block(built, cw0, cd0, 0, cw1, cd0 + 0.5, 6.8, BARN, solid=False)
block(built, cw0, cd1 - 0.5, 0, cw1, cd1, 6.8, BARN, solid=False)
block(built, cw1 - 0.5, cd0, 0, cw1, cd1, 6.8, BARN, solid=False)
block(built, cw0, cd0, 0, cw0 + 0.5, coach.y - wide, 6.8, BARN, solid=False)
block(built, cw0, coach.y + wide, 0, cw0 + 0.5, cd1, 6.8, BARN, solid=False)
block(built, cw0, coach.y - wide, TUNNEL_TALL + 0.4 - LINTEL_DROP, cw0 + 0.5, coach.y + wide, 6.8, BARN, solid=False)  # (a shade low, as over the keep's door)
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
TUNNEL_STONE = c.linear("#76746f")  # grey rock
TUNNEL_FLOOR = c.linear("#4d4a46")  # grey grit underfoot, a little warm
FLAME = c.linear("#ffb347")
IRON = c.linear("#2b2a2c")
OAK = c.linear("#5e3b1f")
GOLD_STONE = c.linear("#c9a25a")
PIT_DARK = c.linear("#100b08")
CORRIDOR_FLOOR = c.linear("#9a917f")
CORRIDOR_WALL = c.linear("#8f8878")

# What's solid underground, apart from the ways' and the halls' own walls.
under_circles, under_boxes = [], []


# (Given its top, a thing low enough to climb onto: you can stand on it. And
# given its bottom too, a slab: you can walk under it, once it's over your head.)
def under_circle(x, y, r, top=None, bottom=None):
    under_circles.append([round(x, 2), round(-y, 2), round(r, 2)] + ([round(top, 2)] if top is not None else [])
                         + ([round(bottom, 2)] if bottom is not None else []))


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


def lid_over(row, back, wide):
    """The ground's cut squares between a lintel's row and the back of the
    earth behind it, clipped to the part behind the lintel."""
    x, y, (ux, uy) = row[0], row[1], (row[3], row[4])
    inward = 1 if ux * (back[1] - y) - uy * (back[0] - x) > 0 else -1
    reach = wide + STEP
    xs = [row[0] + ux * d for d in (-reach, reach)] + [back[0] + back[3] * d for d in (-reach, reach)]
    ys = [row[1] + uy * d for d in (-reach, reach)] + [back[1] + back[4] * d for d in (-reach, reach)]
    for i in range(int((min(xs) - X0) // STEP), int((max(xs) - X0) // STEP) + 1):
        for j in range(int((min(ys) - Y0) // STEP), int((max(ys) - Y0) // STEP) + 1):
            if (i, j) not in CUT:
                continue
            x0, y0 = X0 + i * STEP, Y0 + j * STEP
            c00, c10, c11, c01 = (x0, y0), (x0 + STEP, y0), (x0 + STEP, y0 + STEP), (x0, y0 + STEP)
            for tri in ((c00, c10, c11), (c00, c11, c01)):
                pts = clip(list(tri), x, y, inward * uy, -inward * ux)
                if len(pts) < 3:
                    continue
                verts = [(px, py, drawn_height(px, py, exactly=True)) for px, py in pts]
                colour = ground_colour(*pts[0], height(*pts[0]))
                tunnel.add(verts, [tuple(range(len(verts)))], [c.vary(colour, 0.12, Vector(v)) for v in verts])


def spike(builder, x, y, z, tall, radius, colour, sides=6):
    """A stalagmite, or (tall below zero) a stalactite."""
    verts = [(x + math.cos(2 * math.pi * k / sides) * radius, y + math.sin(2 * math.pi * k / sides) * radius, z)
             for k in range(sides)] + [(x, y, z + tall)]
    faces = [(k, (k + 1) % sides, sides) for k in range(sides)]
    builder.add(verts, faces, [c.vary(colour, 0.15, Vector((x, y, z + k))) for k in range(sides + 1)])


def opening(hall, x, y, margin=0.5):
    """Whether a way comes into the hall here, at its wall (or within a margin of it)."""
    for way in WAYS.values():
        if way.near(x, y, way.half + 1):
            d, floor, beyond = way.nearest(x, y)
            if not beyond and d < way.half + margin and abs(floor - hall.floor) < 1.5:
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

# Underground, under cover, a way is dug through rock: rough walls (pushed
# out, never in, by noise, so they're the same from one stretch to the next
# and never narrow the way), a rounded roof, in layers of earth and stone;
# timber props across it every few metres, and rubble along the foot of its
# walls. Across the way, from the left wall's foot over the roof to the right
# wall's foot: (how far across, -1 to 1, and how high).
VAULT = [(-1, -0.1), (-1, 0.6), (-1, 1.3), (-1, 2.0), (-0.96, 2.45), (-0.8, 2.82), (-0.45, 3.08), (0, TUNNEL_TALL)]
VAULT += [(-u, h) for u, h in reversed(VAULT[:-1])]
SPRING = 2.3  # where the roof springs from the walls (the middle of its curve)
DOME_RINGS, DOME_DEEP = 5, 1.5  # a dead end's dome: rings of rock, and how far on it's dug
NOTE_IN = 0.75  # its clue's post, on in the dome
PROP_EVERY = 8  # rows (half a metre each) between the timber props
PROP_TALL = 2.95  # up to its beam: over your head even jumping (its ends go into the rock)
TIMBER = c.linear("#4a3420")
# (Grey rock, in layers: one a little warmer, for a hint of iron in it.)
LAYERS = (c.linear("#6e6d6a"), c.linear("#5a5957"), c.linear("#7c7a76"), c.linear("#4c4b4a"), c.linear("#6a6560"))


def vault_point(row, u, h, half):
    """A point of the rock round a way: pushed out by up to 0.4 m (but not at
    the foot of its walls, where they meet the floor)."""
    x, y, f = row[0], row[1], row[2]
    bx, by = x + row[3] * u * half, y + row[4] * u * half
    if h < 0:
        return bx, by, f + h
    if h <= SPRING:
        ox, oz = u, 0.0
    else:
        ox, oz = u * half, h - SPRING
        m = math.hypot(ox, oz) or 1
        ox, oz = ox / m, oz / m
    push = 0.4 * max(0.0, min(1.0, 0.45 + noise.noise(Vector((bx / 1.4, by / 1.4, (f + h) / 1.1)))))
    push *= min(1.0, h / 0.6)  # (easing out from the foot)
    px, py = bx + row[3] * ox * push, by + row[4] * ox * push
    # (Always under the ground: under the river, its bank comes down close
    # over the roof.)
    return px, py, min(f + h + oz * push, max(height(px, py) - 0.15, f + min(h, 2.0)))


def rock_colour(x, y, z):
    """Layers of earth and stone, tilted a little, darker towards the floor."""
    t = noise.noise(Vector((x / 9, y / 9, 0.3))) * 1.5 + z * 0.9
    k = int(math.floor(t)) % len(LAYERS)
    return c.mix(LAYERS[k], c.linear("#1d1d1f"), 0.25 * max(0.0, 1 - (z % 3.2) / 1.2) * 0.6)


def oriented_box(builder, corners, z0, z1, colour):
    """A box standing on four corners (in order round it), from z0 up to z1."""
    for i in range(4):
        p, q = corners[i], corners[(i + 1) % 4]
        quad(builder, [(*p, z0), (*q, z0), (*q, z1), (*p, z1)], colour, 0.06)
    quad(builder, [(*p, z1) for p in corners], colour, 0.06)
    quad(builder, [(*p, z0) for p in corners], colour, 0.06)


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
    floor_colour, wall_colour = (CORRIDOR_FLOOR, CORRIDOR_WALL) if way.indoor else (TUNNEL_FLOOR, TUNNEL_STONE)
    roof_colour = c.linear("#5b4632") if way.indoor else LAYERS[1]

    def side(row, offset):
        x, y, _, nx_, ny_, _ = row
        return x + nx_ * offset, y + ny_ * offset

    def drawn(a, b):
        """Whether this stretch is drawn (as far as a hall's doorway)."""
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        hall = in_a_hall(*mid, 0.3)
        return not (hall and hall.inside(mid[0], mid[1], hall.doorway))

    # The stretches dug through rock (under cover, underground).
    rocky_ = [not way.indoor and a[5] and b[5] and drawn(a, b) for a, b in zip(rows, rows[1:])]
    # Its dead ends, deep under the land: where it stops in the rock, not in
    # a hall or out at a mouth (each end's row, and which way is on past it).
    dead_ends = [(i, outward) for i, outward in ((0, -1), (len(rows) - 1, 1))
                 if not way.indoor and rows[i][5] and not in_a_hall(*rows[i][:3], 1.3)]
    dead_rows = {i for i, _ in dead_ends}
    rubble = random.Random(f"rubble {way.points[0]}")
    for k, (a, b) in enumerate(zip(rows, rows[1:])):
        mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2)
        # (Floor, walls and roof go on as far as the doorway: just past a
        # room's wall, or on into a cave, past its lumpy wall. The floor
        # overlaps the hall's own, a doorstep over the seam.)
        if not drawn(a, b):
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
        if rocky_[k]:
            # The rock round it, all the way over.
            pa = [vault_point(a, u, h, half) for u, h in VAULT]
            pb = [vault_point(b, u, h, half) for u, h in VAULT]
            for i in range(len(VAULT) - 1):
                face = [pa[i], pa[i + 1], pb[i + 1], pb[i]]
                cx_, cy_, cz_ = (sum(p[j] for p in face) / 4 for j in range(3))
                quad(tunnel, face, rock_colour(cx_, cy_, cz_ - a[2]), 0.1)
            # (And a plain dark backing just beyond the rock, so where it
            # folds over itself, round a tight bend, there's no slit to see
            # through.)
            back = half + 0.45
            la, ra, lb, rb = side(a, -back), side(a, back), side(b, -back), side(b, back)
            def top(row, p):
                return min(row[2] + TUNNEL_TALL + 0.45, max(height(*p) - 0.08, row[2] + 2.0))

            for p0, p1 in ((la, lb), (ra, rb)):
                quad(tunnel, [(*p0, a[2] - 0.1), (*p1, b[2] - 0.1), (*p1, top(b, p1)), (*p0, top(a, p0))], LAYERS[3], 0.0)
            quad(tunnel, [(*la, top(a, la)), (*ra, top(a, ra)), (*rb, top(b, rb)), (*lb, top(b, lb))], LAYERS[3], 0.0)
            if not in_pit(mid[0], mid[1]):
                quad(tunnel, [(*la, a[2] - 0.1), (*ra, a[2] - 0.1), (*rb, b[2] - 0.1), (*lb, b[2] - 0.1)], LAYERS[3], 0.0)
            # Where the rock stops (into a hall, out under the lintel, a dead
            # end): a ring of it, from the rock in to the square opening.
            # (The door frames and lintels stand a shade out from it, or the
            # two would flicker against each other.)
            for row, pts_, ends in ((a, pa, k == 0 or not rocky_[k - 1]), (b, pb, k == len(rocky_) - 1 or not rocky_[k + 1])):
                if not ends or (row is a and k in dead_rows) or (row is b and k + 1 in dead_rows):
                    continue  # (a dead end: the rock closes round it, below)
                square = [(*side(row, u * half), row[2] + (h if h <= SPRING else TUNNEL_TALL)) for u, h in VAULT]
                for i in range(len(VAULT) - 1):
                    quad(tunnel, [pts_[i], pts_[i + 1], square[i + 1], square[i]], rock_colour(*pts_[i]), 0.1)
            # Timber props, every few metres (not by a hall).
            if k % PROP_EVERY == PROP_EVERY // 2 and not in_a_hall(*mid, 4):
                dx, dy = b[0] - a[0], b[1] - a[1]
                dd = math.hypot(dx, dy) or 1
                ux, uy = dx / dd, dy / dd  # along the way
                ax2, ay2 = a[3], a[4]
                am = math.hypot(ax2, ay2) or 1
                vx, vy = ax2 / am, ay2 / am  # across it
                f = a[2]
                for sign in (1, -1):
                    px, py = side(a, sign * (half - 0.14))
                    post = [(px + ux * su * 0.13 + vx * sv * 0.13, py + uy * su * 0.13 + vy * sv * 0.13)
                            for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
                    oriented_box(tunnel, post, f - 0.05, f + PROP_TALL, TIMBER)
                lx2, ly2 = side(a, -half - 0.2)
                rx2, ry2 = side(a, half + 0.2)
                beam = [(lx2 - ux * 0.15, ly2 - uy * 0.15), (rx2 - ux * 0.15, ry2 - uy * 0.15),
                        (rx2 + ux * 0.15, ry2 + uy * 0.15), (lx2 + ux * 0.15, ly2 + uy * 0.15)]
                oriented_box(tunnel, beam, f + PROP_TALL, f + PROP_TALL + 0.25, c.mix(TIMBER, c.linear("#000000"), 0.15))
            # Rubble along the foot of the walls.
            if rubble.random() < 0.22:
                sign = rubble.choice((1, -1))
                rx3, ry3 = side(a, sign * (half - 0.08))
                r = rubble.uniform(0.12, 0.28)
                tunnel.blob((rx3, ry3, a[2] + r * 0.2), r, c.mix(LAYERS[2], LAYERS[3], rubble.random()),
                            squash=0.6, lumpy=0.35, seed=rubble.random() * 100, subdivisions=1)
            continue
        if way.open:
            continue
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
            # (A shade out from under cover, off the rock's end.)
            outside = a if b[5] else b
            run = math.hypot(outside[0] - row[0], outside[1] - row[1]) or 1
            ox_, oy_ = (outside[0] - row[0]) / run * 0.03, (outside[1] - row[1]) / run * 0.03
            l1, r1 = side(row, -half - 2.4), side(row, half + 2.4)
            l1, r1 = (l1[0] + ox_, l1[1] + oy_), (r1[0] + ox_, r1[1] + oy_)
            low = row[2] + TUNNEL_TALL
            high = max(height(*l1), height(*r1), height(row[0], row[1])) + 0.8
            quad(tunnel, [(*l1, low), (*r1, low), (*r1, high), (*l1, high)], STONE)
            # And a lid over the box: the ground's hole reaches a square's
            # width back past the lintel, and on a cliff the box's back would
            # show through it. So the ground's cut squares are drawn again,
            # just the part behind the lintel.
            lid_over(row, back, wide)
    # Door frames, where the way goes into a hall.
    # (Hung on the walls' own edges: near a bend, they're mitred.)
    for k, (a, b) in enumerate(zip(rows, rows[1:]) if not way.open else ()):
        for hall in HALLS.values():
            m = hall.doorway
            if abs(hall.floor - a[2]) > 1.5 or hall.inside(a[0], a[1], m) == hall.inside(b[0], b[1], m):
                continue
            i = k + 1 if hall.inside(a[0], a[1], m) else k
            row = rows[i]
            f = row[2]
            nx_, ny_ = row[3], row[4]
            # (In a cave, a shade out into it, off the rock's end.)
            inner = a if i == k + 1 else b
            run = math.hypot(inner[0] - row[0], inner[1] - row[1]) or 1
            hx_, hy_ = ((inner[0] - row[0]) / run * 0.03, (inner[1] - row[1]) / run * 0.03) if not hall.indoor else (0, 0)
            el_, er_ = (edge_left[i][0] + hx_, edge_left[i][1] + hy_), (edge_right[i][0] + hx_, edge_right[i][1] + hy_)
            # (In a cave, as high as its wall goes before the dome.)
            top = f + TUNNEL_TALL + 0.1 if hall.indoor else hall.floor + max(TUNNEL_TALL + 0.8, hall.tall * 0.5)
            for p, jut in ((er_, 1.8), (el_, -1.8)):
                q = (p[0] + nx_ * jut, p[1] + ny_ * jut)
                quad(tunnel, [(*p, f - 0.3), (*q, f - 0.3), (*q, top), (*p, top)], hall.wall)
            # (Into a room, the frame can stand a little out from its wall,
            # where the way's walls begin: the sides of the doorway, back
            # from the frame to the wall, so there's no gap to see out of.)
            if hall.room:
                ux, uy = (inner[0] - row[0]) / run, (inner[1] - row[1]) / run
                for p in (el_, er_):
                    ts = [(hall.x + sign * (hall.w + ROOM_EDGE) - p[0]) / ux for sign in (1, -1) if abs(ux) > 1e-6]
                    ts += [(hall.y + sign * (hall.d + ROOM_EDGE) - p[1]) / uy for sign in (1, -1) if abs(uy) > 1e-6]
                    t = min((t for t in ts if t > 0), default=0.0)
                    if 0 < t < 1:
                        q = (p[0] + ux * t, p[1] + uy * t)
                        # (Facing both ways: one side's faces in, the other's out.)
                        quad(tunnel, [(*p, f - 0.3), (*q, f - 0.3), (*q, top), (*p, top)], hall.wall)
                        quad(tunnel, [(*p, top), (*q, top), (*q, f - 0.3), (*p, f - 0.3)], hall.wall)
            if not hall.indoor:
                p, q = el_, er_
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
    # A dead end, deep under the land: the rock closes round it, a rough
    # half dome dug on a little past where you can walk (as if they'd given
    # up digging there), with the floor going on under it. In it, on a post,
    # the clue (note_post).
    for i, outward in dead_ends:
        row = rows[i]
        x, y, f, nx_, ny_, _ = row
        ox, oy = ny_ * outward, -nx_ * outward  # on, past the end
        ring = [vault_point(row, u, h, half) for u, h in VAULT]
        foot = (x, y, f - 0.1)  # (the middle of its floor, where the dome shrinks to)
        rings = [ring]
        for j in range(1, DOME_RINGS + 1):
            s_ = 1 - j / DOME_RINGS
            on = DOME_DEEP * math.sqrt(1 - s_ * s_)
            next_ring = []
            for px, py, pz in ring:
                qx, qy, qz = foot[0] + (px - foot[0]) * s_, foot[1] + (py - foot[1]) * s_, foot[2] + (pz - foot[2]) * s_
                # (Rough: pushed on, never back, by noise; but not at its foot, nor its back, where it all meets.)
                bump = 0.3 * max(0.0, noise.noise(Vector((qx / 0.9, qy / 0.9, qz / 0.9))) + 0.2) * s_ * (1 - s_) * 4
                next_ring.append((qx + ox * (on + bump), qy + oy * (on + bump), qz))
            rings.append(next_ring)
        for j in range(DOME_RINGS):
            near, far = (rings[j], rings[j + 1]) if outward > 0 else (rings[j + 1], rings[j])
            for k in range(len(VAULT) - 1):
                face = [near[k], near[k + 1], far[k + 1], far[k]]
                colour = rock_colour(*face[0][:2], face[0][2] - f)
                if j == DOME_RINGS - 1:  # (at its back, where the ring's shrunk to a point: a triangle)
                    tri = [p for n, p in enumerate(face) if p != face[n - 1]]
                    tunnel.add(tri, [(0, 1, 2)], [c.vary(colour, 0.1, Vector(tri[0]))] * 3)
                else:
                    quad(tunnel, face, colour, 0.1)
        # Its floor, out to the dome's foot all round.
        feet = [(r[0][0], r[0][1], f) for r in rings] + [(r[-1][0], r[-1][1], f) for r in reversed(rings[:-1])]
        (ax_, ay_, _), (bx_, by_, _), (cx_, cy_, _) = feet[0], feet[len(rings) - 1], feet[-1]
        up = (bx_ - ax_) * (cy_ - ay_) - (by_ - ay_) * (cx_ - ax_) > 0  # (facing up)
        tunnel.add(feet, [tuple(range(len(feet)))[::1 if up else -1]], [c.vary(floor_colour, 0.12, Vector(p)) for p in feet])
        if way.clue:
            px, py = x + ox * NOTE_IN, y + oy * NOTE_IN
            note_post(tunnel, way.clue, px, py, f, (-ox, -oy), TUNNEL_FLOOR)
# A stone threshold at every mouth onto the land, over the ragged edge of the
# hole in the ground (which comes in whole squares, so it reaches a little
# past where the ramp begins, and shows the sky through the gap).
for way in WAYS.values():
    if way.indoor:
        continue
    for end, nextp in ((way.points[0], way.points[1]), (way.points[-1], way.points[-2])):
        ex, ey, ef = end
        if abs(ef - height(ex, ey)) > 0.6:
            continue  # (a dead end deep underground)
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

# The deep, deep hole: straight down into the dark, a long way (you only
# see how far falling down it: hole.ts). Its walls rough rock, in layers,
# darker and darker down it, so going down them you see them go by. And a
# beam across its top, under the tunnel's roof, its ends in the rock (for a
# rope to hang from).
px, py, phx, phy = PIT
PIT_DEEP = 48
PIT_ROW, PIT_ACROSS = 1.2, 0.7  # (its walls' pieces: how tall, and how wide)
pit = c.Builder()
corners = [(px - phx, py - phy), (px + phx, py - phy), (px + phx, py + phy), (px - phx, py + phy)]
tops = [WAYS["maze-treasure"].nearest(x, y)[1] for x, y in corners]
pit_floor = WAYS["maze-treasure"].nearest(px, py)[1]
bottom = min(tops) - PIT_DEEP
rough = random.Random("the deep hole")
# (Every wall in as many rows, and its bottom's edge in as many pieces as
# theirs, so they all meet exactly: where they didn't, the sky behind them
# showed through, in sparkling specks. And behind them, a dark shell, in
# case.)
rows = math.ceil((min(tops) - bottom) / PIT_ROW)
floor_edge = []
for k in range(4):
    (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
    across = max(1, round(math.dist((ax, ay), (bx, by)) / PIT_ACROSS))
    # (Pushed out a little, here and there, never in; but not at the top's
    # edge, or the corners, where the walls meet.)
    out_x, out_y = (by - ay), -(bx - ax)
    m = math.hypot(out_x, out_y)
    out_x, out_y = out_x / m, out_y / m
    def wall_point(i, j):
        f = i / across
        x, y = ax + (bx - ax) * f, ay + (by - ay) * f
        top = tops[k] + (tops[(k + 1) % 4] - tops[k]) * f
        z = top - j * PIT_ROW if j < rows else bottom
        push = 0.0 if j == 0 or i in (0, across) or j == rows else 0.25 * (0.5 + noise.noise(Vector((x / 1.3, y / 1.3, z / 1.1))))
        return x + out_x * push, y + out_y * push, z
    for j in range(rows):
        for i in range(across):
            face = [wall_point(i, j), wall_point(i + 1, j), wall_point(i + 1, j + 1), wall_point(i, j + 1)]
            cz = sum(p[2] for p in face) / 4
            deep = min(1.0, (pit_floor - cz) / PIT_DEEP)
            shade = c.mix(rock_colour(face[0][0], face[0][1], cz), PIT_DARK, 0.1 + 0.35 * deep)
            quad(pit, face, c.mix(shade, PIT_DARK, rough.random() * 0.25), 0.1)
    floor_edge += [wall_point(i, rows) for i in range(across)]
pit.add(floor_edge, [tuple(range(len(floor_edge)))], [PIT_DARK] * len(floor_edge))
shell = [(x + 0.6 * (1 if x > px else -1), y + 0.6 * (1 if y > py else -1)) for x, y in corners]
for k in range(4):
    (ax, ay), (bx, by) = shell[k], shell[(k + 1) % 4]
    quad(pit, [(ax, ay, min(tops) - 0.1), (bx, by, min(tops) - 0.1), (bx, by, bottom - 0.3), (ax, ay, bottom - 0.3)], PIT_DARK, 0)
quad(pit, [(x, y, bottom - 0.3) for x, y in shell], PIT_DARK, 0)
PIT_BEAM = pit_floor + PROP_TALL  # its underside
beam = [(px - phx - 0.3, py - 0.16), (px + phx + 0.3, py - 0.16), (px + phx + 0.3, py + 0.16), (px - phx - 0.3, py + 0.16)]
oriented_box(pit, beam, PIT_BEAM, PIT_BEAM + 0.3, c.mix(TIMBER, c.linear("#000000"), 0.1))
# (You can go right up to its edge, and look in: only over it, you slip in.)
obstacle(["maze north", "treasure-room south"], "box", px, -py, phx, phy - 0.3, under=True, reach=0)

# The halls: a floor of squares out under the walls, a lumpy round wall with
# openings where the ways come in, and a dome.
caves = c.Builder()
for hall in HALLS.values():
    if hall.indoor:
        continue  # (below)
    random.seed(f"cave {hall.place}")  # (its rocks its own: a change anywhere else doesn't move them)
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
# (The tower's inside, its own object: the game keeps it dark, seen from outside.)
tower_inside = c.Builder()
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


# Merlin's lair, furnished from Quaternius's Fantasy Props MegaKit
# (art/models/fantasy-props-megakit), as in its painting: the cauldron
# boiling green over its fire on a round step, on a purple rug; bookcases of
# books (and now and then bottles) either side of the stairs up and round
# the walls, but not across the doors; his desk with the crystal ball; a
# bench of potions; candles on stands and in a chandelier; a chart of the
# stars; and green banners on the purple walls.
#
# What's furnished many times over (a bookcase full of books, a candle stand)
# is kept once in land.glb, as "prop-<kind>", and land.json says where each
# one stands: the game stamps them there (src/three/props.ts).
prop_spots = {"kinds": [], "at": []}  # [kind, x, y, z, yaw], in three.js's axes
prop_kinds = {}  # each kind's footprint (x0, y0, x1, y1) and top, as it's made


def stamp(kind, make, at, yaw, solid=True):
    """One of a kind (made, the first time, by make(builder), at the origin
    facing -y: its footprint and top) at `at`, turned by yaw: solid, as
    furniture, unless it's up out of the way."""
    if kind not in prop_kinds:
        made = c.Builder()
        prop_kinds[kind] = make(made)
        made.build(f"prop-{kind}", smooth=False)
        prop_spots["kinds"].append(kind)
    (x0, y0, x1, y1), top = prop_kinds[kind]
    x, y, z = at
    cos, sin = math.cos(yaw), math.sin(yaw)
    corners = [(x + px * cos - py * sin, y + px * sin + py * cos) for px in (x0, x1) for py in (y0, y1)]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    if solid:
        under_box((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2,
                  top=z + top)
    prop_spots["at"].append([prop_spots["kinds"].index(kind), round(x, 2), round(z, 2), round(-y, 2), round(yaw, 3)])

SHELVES = (0.77, 1.15, 1.53, 1.92)  # in the kit's bookcase, its shelves' heights
BOOKCASE = 1.3  # times the kit's size: its bookcases as tall as the old ones (3.3 m)
POTIONS = ["#5cff6a", "#c45cff", "#5cc4ff", "#ffb35c"]


def lair(b, hall):
    hx, hy, f, W, D = hall.x, hall.y, hall.floor, hall.w, hall.d
    rng = random.Random(7)
    wall = 0.3  # from the room's edge to its walls' faces

    def prop(name, u, v, z=0.0, face=(0, -1), scale=1.0, ratio=None, solid=True, tint=None):
        """One of the kit's models, at (u, v) from the room's middle, its front
        facing `face`: solid (as furniture), and where its points go."""
        yaw = math.atan2(face[0], -face[1])
        at = (hx + u, hy + v, f + z)
        (x0, y0, x1, y1), top = PROPS.put(b, name, at, yaw, scale, ratio, tint and (*c.linear(tint)[:3], 0.65))
        if solid:
            under_box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2, top=top)
        return PROPS.placing(at, yaw, scale)

    def lit(name, scale):
        """Candlesticks, lit: to make, for stamp."""

        def make(t):
            made = PROPS.put(t, name, (0, 0, 0), 0, scale)  # (in full: made simpler, their thin stems break up)
            for x, y, z in PROPS.tips(name):
                flame(t, x * scale, y * scale, z * scale, 0.06 * scale)
            return made

        return make

    def candles(name, u, v, z=0.0, scale=1.0, solid=True):
        stamp(f"{name}-lit".lower().replace("_", "-"), lit(name, scale), (hx + u, hy + v, f + z), 0.0, solid)

    def books(variant):
        """A bookcase full of books (and on one shelf, bottles): to make, for stamp."""

        def make(t):
            shelves = random.Random(variant)
            made = PROPS.put(t, "Bookcase_2", (0, 0, 0), 0, BOOKCASE, 0.35)
            for k, shelf in enumerate(SHELVES):
                z = (shelf + 0.005) * BOOKCASE
                if k == variant % 4 and variant >= 2:
                    for j in range(-2, 3):
                        bottle = shelves.choice(["Potion_1", "Potion_2", "Potion_4", "Bottle_1"])
                        tint = (*c.linear(shelves.choice(POTIONS))[:3], 0.5)
                        PROPS.put(t, bottle, (j * 0.28, -0.04, z), 0, BOOKCASE * 0.9, 0.3, tint)
                else:
                    group = f"BookGroup_Medium_{shelves.randint(1, 3)}"
                    PROPS.put(t, group, (0, -0.04, z), 0, BOOKCASE, 0.4)
            return made

        return make

    def bookcase(u, v, face):
        """A bookcase against the wall (one of a few, filled differently)."""
        back = 0.21 * BOOKCASE + 0.02
        u, v = u - face[0] * (wall - back), v - face[1] * (wall - back)  # (its back to the wall)
        variant = rng.randrange(4)
        stamp(f"bookcase-{variant + 1}", books(variant), (hx + u, hy + v, f), math.atan2(face[0], -face[1]))

    # The cauldron, a little east of the middle, on its round step on the
    # rug, over its fire, boiling.
    du, dv = 2.2, 0.8
    dx, dy = hx + du, hy + dv
    rim = [(math.cos(2 * math.pi * k / 24), math.sin(2 * math.pi * k / 24)) for k in range(24)]
    verts = [(dx, dy, f + 0.05)] + [(dx + ca * 3.0, dy + sa * 2.6, f + 0.05) for ca, sa in rim]
    b.add(verts, [(0, 1 + k, 1 + (k + 1) % 24) for k in range(24)], [c.linear("#4a2a5e")] * 25)
    R = 1.6  # the step's radius
    b.cylinder((dx, dy, f), (dx, dy, f + 0.3), R, R, STONE, sides=20)
    step = [(dx, dy, f + 0.3)] + [(dx + ca * R, dy + sa * R, f + 0.3) for ca, sa in rim]
    b.add(step, [(0, 1 + k, 1 + (k + 1) % 24) for k in range(24)], [c.vary(STONE, 0.08, Vector(p)) for p in step])
    under_circle(dx, dy, R)
    SIZE = 1.6  # (its brew just below your eyes, so you see into it)
    prop("Cauldron", du, dv, 0.3, scale=SIZE, ratio=0.5, solid=False)
    for k in range(5):
        a = 2 * math.pi * k / 5
        flame(b, dx + math.cos(a) * 0.3, dy + math.sin(a) * 0.3, f + 0.3, 0.3)
    brew = f + 0.3 + 0.8 * SIZE  # (just over the kit cauldron's own top, inside its rim)
    verts = [(dx, dy, brew)] + [(dx + ca * 0.41 * SIZE, dy + sa * 0.41 * SIZE, brew) for ca, sa in rim]
    b.add(verts, [(0, 1 + k, 1 + (k + 1) % 24) for k in range(24)], [c.linear("#5cff6a")] * 25)
    for k in range(6):
        a, r = rng.random() * 2 * math.pi, rng.random() * 0.4
        b.blob((dx + math.cos(a) * r, dy + math.sin(a) * r, brew), 0.05 + 0.05 * rng.random(), c.linear("#8aff8a"),
               squash=0.6, lumpy=0.1, seed=k)
    # A stand beside it, for his book of spells.
    prop("BookStand", du - 2.3, dv + 0.4, face=(1, 0), ratio=0.5)

    # Bookcases: either side of the stairs up (and round the corners), and
    # by the door he locks behind you.
    west, east, south, north = -W, W, -D, D
    for u in (-3.2, -5.1, -7.0, 3.2, 5.1, 7.0):
        bookcase(u, north, (0, -1))
    for v in (4.9, 3.0):
        bookcase(west, v, (1, 0))
    for v in (-5.6,):
        bookcase(east, v, (-1, 0))
    for u in (-7.0, -5.1, 5.1, 7.0):
        bookcase(u, south, (0, 1))

    # His desk, along the west wall: the crystal ball on it, candles, books
    # and scrolls.
    tu, tv = west + 0.9, -1.6
    prop("Table_Large", tu, tv, face=(1, 0), ratio=0.5)
    prop("Chair_1", tu - 0.05, tv + 1.9, face=(0, -1), ratio=0.5)
    top = 0.81
    b.cylinder((hx + tu, hy + tv, f + top), (hx + tu, hy + tv, f + top + 0.08), 0.14, 0.1, BRASS, sides=10)
    b.blob((hx + tu, hy + tv, f + top + 0.28), 0.22, c.linear("#bfe6ff"), squash=1, lumpy=0.05, seed=3)
    move = prop("CandleStick_Triple", tu - 0.1, tv - 1.0, top, face=(1, 0), ratio=0.3, solid=False)
    for tip in PROPS.tips("CandleStick_Triple"):
        flame(b, *move(tip), 0.06)
    prop("Book_Stack_1", tu, tv + 0.9, top, face=(1, 0), solid=False)
    prop("Scroll_1", tu + 0.25, tv + 0.4, top, face=(1, 0.3), solid=False)
    prop("Pouch_Large", tu + 0.2, tv - 0.5, top, face=(1, 0), solid=False)
    prop("Book_Stack_2", west + 0.5, tv - 2.3, ratio=0.6)

    # His bench of potions, along the east wall north of the door, a stool,
    # and bottles on a shelf by the door.
    wu, wv = east - 0.75, 2.6
    prop("Workbench", wu, wv, face=(-1, 0), ratio=0.5)
    top = 0.89
    for k in range(7):
        name = ["Potion_1", "Potion_2", "Potion_4", "Bottle_1"][k % 4]
        prop(name, wu + (k % 3 - 1) * 0.25, wv - 0.7 + k * 0.23, top, scale=1.3, ratio=0.3, solid=False,
             tint=POTIONS[k % 4])
    prop("SmallBottles_1", wu - 0.2, wv + 0.75, top, face=(-1, 0), ratio=0.3, solid=False)
    prop("Stool", wu - 1.2, wv, ratio=0.5)
    prop("Shelf_Small_Bottles", east + wall, -0.6, 1.3, face=(-1, 0), ratio=0.25)

    # Candles on stands, and a chandelier.
    for u, v in ((-2.6, 5.6), (2.6, 5.6), (-5.8, -5.4), (0.6, -5.6)):  # (clear of the doors)
        candles("CandleStick_Stand", u, v, scale=1.2)
    candles("Chandelier", 0, -0.5, hall.tall - 0.05, scale=1.5, solid=False)

    # A cage, empty; vases, and a bag.
    prop("Cage_Small", 3.0, -5.9, scale=1.2, ratio=0.25)
    prop("Vase_2", -7.2, 6.2, ratio=0.5)
    prop("Vase_4", -7.3, 1.9, ratio=0.5)
    prop("Bag", 7.2, 6.2, face=(-1, -1), ratio=0.5)

    # The chart of the stars, on the south wall.
    wall_panel(b, hx, hy + south - wall + 0.01, (2.4, 0), f, f + 2.4, f + 4.6, c.linear("#1a2350"))
    for k in range(24):
        sx = hx - 2.1 + (k * 0.377) % 4.2
        sz = f + 2.6 + (k * 0.613) % 1.8
        wall_panel(b, sx, hy + south - wall + 0.02, (0.05, 0), f, sz, sz + 0.1, c.linear("#fff3b0"))
    # Green banners on the purple walls: either side of the stairs, and on
    # the west wall.
    # (Each hangs from its rod, along it from its left end: half its width.)
    half = 1.61 * 1.4 / 2
    for u in (-3.6, 3.6):
        prop("Banner_2", u - half, north + wall - 0.15, 5.0, face=(0, -1), scale=1.4, solid=False, tint="#2f8a3a")
    prop("Banner_2", west - wall + 0.15, -4.4 - half, 5.0, face=(1, 0), scale=1.4, solid=False, tint="#2f8a3a")


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
    E = ROOM_EDGE
    corners = [(hx - W - E, hy - D - E), (hx + W + E, hy - D - E), (hx + W + E, hy + D + E), (hx - W - E, hy + D + E)]
    band = c.mix(hall.wall, c.linear("#000000"), 0.3)
    for k in range(4):
        (ax, ay), (bx, by) = corners[k], corners[(k + 1) % 4]
        length = math.hypot(bx - ax, by - ay)
        ox, oy = (by - ay) / length, -(bx - ax) / length  # outward
        # Where ways come through it, exactly as wide as they are (to 5 cm),
        # so their walls meet its edges; and the rest, in pieces of about a
        # metre.
        def along(t, ax=ax, ay=ay, bx=bx, by=by, length=length):
            return ax + (bx - ax) * t / length, ay + (by - ay) * t / length

        fine = 0.05
        open_ = [opening(hall, *(v + o * 0.6 for v, o in zip(along((i + 0.5) * fine), (ox, oy))), margin=0.0)
                 for i in range(int(length / fine))]
        runs, start = [], 0
        for i in range(1, len(open_) + 1):
            if i == len(open_) or open_[i] != open_[start]:
                t0, t1 = start * fine, (length if i == len(open_) else i * fine)
                n = 1 if open_[start] else max(1, round(t1 - t0))
                runs += [(t0 + (t1 - t0) * m / n, t0 + (t1 - t0) * (m + 1) / n, open_[start]) for m in range(n)]
                start = i
        for t0, t1, through in runs:
            p0, p1 = along(t0), along(t1)
            if through:
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
        lair(b, hall)
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


# The tower's stonework, in front of its floor and wall (which are the dark
# mortar between): the wall in courses of blocks, each its own shade, damp
# and mossy near the floor; big uneven flagstones; moss and rubble at the
# foot of the wall, and heaped at the foot of the stairs. And cobwebs (their
# own object, which the game makes see-through), in the doorway's top
# corners, the narrow windows' and under the stairs.
DAMP, MOSS, WEB = TOWER_DAMP, TOWER_MOSS, c.linear("#d8d8d4")
webs = c.Builder()


def tower_stones(b, hall, sides):
    rnd = random.Random("tower stones")  # (its own: a change anywhere else doesn't move them)
    hx, hy, f, R, tall = hall.x, hall.y, hall.floor, hall.r, hall.tall
    wall_r = R + 0.35  # (round_room's wall)
    corners = [2 * math.pi * k / sides for k in range(2 * sides + 1)]

    # Where the wall's open: the doorway, and the windows (once round, and
    # again past the start, where the courses end).
    holes = []
    for a, half, z0, z1 in [tower_door()] + TOWER_WINDOWS:
        holes.append(((a - half) % (2 * math.pi), (a - half) % (2 * math.pi) + 2 * half, f + z0, f + z1))
    holes += [(lo + 2 * math.pi, hi + 2 * math.pi, h0, h1) for lo, hi, h0, h1 in holes]
    stone_courses(b, rnd, lambda a: polygon_at(a, wall_r - 0.03, sides, 0), corners, wall_r, f, f + tall, holes, f)

    def stone(base, z):
        return stone_shade(rnd, base, z, f)

    # The floor: flagstones on a jittered grid, some of them two together,
    # cut at the outer wall (it reaches out under the doorway).
    cell, out = 0.95, TOWER_R * math.cos(math.pi / SIDES) - 0.02
    n = int(out / cell) + 2
    grid = {(i, j): (hx + i * cell + rnd.uniform(-0.27, 0.27) * cell, hy + j * cell + rnd.uniform(-0.27, 0.27) * cell)
            for i in range(-n, n + 2) for j in range(-n, n + 2)}
    taken = set()
    for i in range(-n, n):
        for j in range(-n, n):
            if (i, j) in taken:
                continue
            ring_ = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            if rnd.random() < 0.25 and (i + 1, j) not in taken:
                ring_ = [(i, j), (i + 1, j), (i + 2, j), (i + 2, j + 1), (i + 1, j + 1), (i, j + 1)]
                taken.add((i + 1, j))
            elif rnd.random() < 0.25 and (i, j + 1) not in taken:
                ring_ = [(i, j), (i + 1, j), (i + 1, j + 1), (i + 1, j + 2), (i, j + 2), (i, j + 1)]
                taken.add((i, j + 1))
            pts = [grid[k] for k in ring_]
            mx, my = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
            if math.hypot(mx - hx, my - hy) > out + 0.3:
                continue
            # (In to the outer wall; and in from the joints all round.)
            pts = [(hx + (x - hx) * min(1, out / (math.hypot(x - hx, y - hy) or 1)),
                    hy + (y - hy) * min(1, out / (math.hypot(x - hx, y - hy) or 1))) for x, y in pts]
            pts = [(x + (mx - x) * JOINT / (math.hypot(mx - x, my - y) or 1), y + (my - y) * JOINT / (math.hypot(mx - x, my - y) or 1))
                   for x, y in pts]
            colour = stone(TOWER_FLAG, f + 0.4)
            if math.hypot(mx - hx, my - hy) > R - 1.0 and rnd.random() < 0.45:
                colour = c.mix(colour, MOSS, rnd.uniform(0.25, 0.55))
            b.add([(x, y, f - 0.045) for x, y in pts], [tuple(range(len(pts)))], [c.vary(colour, 0.05, Vector((x, y, 3.0))) for x, y in pts])

    # Moss and rubble at the foot of the wall (not in the doorway, nor by the
    # chest, under the stairs at the back), and a heap at the foot of the stairs.
    def free(a):
        a %= 2 * math.pi
        return not (holes[0][0] - 0.3 < a < holes[0][1] + 0.3) and abs(a - math.pi / 2) > 0.25

    for k in range(26):
        a = rnd.uniform(0, 2 * math.pi)
        if free(a):
            x, y = hx + math.cos(a) * (wall_r - 0.25), hy + math.sin(a) * (wall_r - 0.25)
            b.blob((x, y, f - 0.03), rnd.uniform(0.2, 0.4), c.mix(MOSS, DAMP, rnd.random() * 0.5), squash=0.18, lumpy=0.4,
                   seed=200 + k, subdivisions=1)
    spots = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.1, 0.5), rnd.uniform(0.05, 0.16)) for _ in range(60)]
    spots += [(math.pi + rnd.uniform(0.05, 0.45), rnd.uniform(0.15, 0.9), rnd.uniform(0.07, 0.24)) for _ in range(16)]
    for k, (a, inwards, size) in enumerate(spots):
        if free(a):
            x, y = hx + math.cos(a) * (wall_r - inwards), hy + math.sin(a) * (wall_r - inwards)
            b.blob((x, y, f - 0.02 + size * 0.3), size, stone(TOWER_BLOCK, f + 0.5), squash=0.65, lumpy=0.35,
                   seed=300 + k, subdivisions=1)

    # The doorway's sides, inside: stone too, on its mortar.
    def flat_wall(x, y0, y1, z0, z1):
        """Blocks on a flat wall facing across the doorway, at x, from y0 to y1."""
        quad(b, [(x, y0, z0), (x, y1, z0), (x, y1, z1), (x, y0, z1)], hall.wall, 0.04)
        x -= math.copysign(0.02, x - hx)
        z = z0
        while z < z1 - 0.05:
            h = min(rnd.uniform(*COURSE), z1 - z)
            y = y0 + rnd.uniform(0.2, 0.7)
            ends = [y0]
            while y < y1:
                ends.append(y)
                y += rnd.uniform(0.55, 1.15)
            ends.append(y1)
            colour = None
            for e0, e1 in zip(ends, ends[1:]):
                if e1 - e0 > 0.1:
                    colour = stone(TOWER_BLOCK, z)
                    quad(b, [(x, e0 + JOINT / 2, z + JOINT / 2), (x, e1 - JOINT / 2, z + JOINT / 2),
                             (x, e1 - JOINT / 2, z + h - JOINT / 2), (x, e0 + JOINT / 2, z + h - JOINT / 2)], colour, 0.05)
            z += h

    for side in (-1, 1):
        flat_wall(hx + side * (WAYS["tower-door"].half + 0.01), TOWER_LIP[1], hy - wall_r, f - 0.6, f + TUNNEL_TALL)

    # Cobwebs: in the top corners of the doorway, just in from the room
    # (you see them against the stone, looking back)...
    for side in (-1, 1):
        cobweb((hx + side * (WAYS["tower-door"].half - 0.03), hy - wall_r - 0.35, f + TUNNEL_TALL - 0.02),
               (0, 0, -1), (-side, 0, 0), 0.75, f"door {side}")
    # ...in a top corner of each narrow window, against the light...
    for k, (a, half, z0, z1) in enumerate(TOWER_WINDOWS[1:]):
        side = 1 if k == 0 else -1
        x, y = polygon_at(a - side * (half - 0.01), wall_r - 0.05, sides, 0)
        cobweb((x, y, f + z1 - 0.01), (0, 0, -1), (-math.sin(a) * side, math.cos(a) * side, 0), 0.22, f"window {k}")
    # ...and under a few of the stairs' slabs, strung along the corner where
    # the slab meets the wall, facing into the room (the first over the chest).
    turn = (math.pi - 0.25 - TOWER_FACING) / 15
    for k in (6, 9, 12):
        a = math.pi - (k + 0.85) * turn
        x, y = polygon_at(a, wall_r - 0.04, sides, 0)
        inward = Vector((-math.cos(a), -math.sin(a), 0))
        cobweb((x, y, f + TOWER_LANDING / 16 * (k + 1) - 0.15), (math.sin(a), -math.cos(a), 0),
               Vector((0, 0, -1)) + inward * 0.7, 0.7, f"stair {k}")


def cobweb(corner, e1, e2, size, seed):
    """A cobweb across a corner: threads out from it, between its two edges
    (e1, e2: which way they go from it), and rings of thread across them,
    sagging a little towards it."""
    rnd = random.Random(seed)
    corner, e1, e2 = Vector(corner), Vector(e1).normalized(), Vector(e2).normalized()
    normal = e1.cross(e2).normalized()

    def thread(p, q):
        w = normal.cross((q - p).normalized()) * 0.006
        webs.add([tuple(p - w), tuple(q - w), tuple(q + w), tuple(p + w)], [(0, 1, 2, 3)], [WEB] * 4)

    spokes = 7
    ends = []
    for k in range(spokes):
        t = k / (spokes - 1) * math.pi / 2
        ends.append((e1 * math.cos(t) + e2 * math.sin(t)) * size * rnd.uniform(0.7, 1.0))
        thread(corner, corner + ends[-1])
    for ring_ in range(1, 6):
        out = ring_ / 5.6 * rnd.uniform(0.9, 1.05)
        pts = [corner + e * out for e in ends]
        for p, q in zip(pts, pts[1:]):
            m = (p + q) / 2
            m = m + (corner - m) * 0.1
            thread(p, m)
            thread(m, q)


def round_room(b, hall):
    """A round room: a floor of flagstones in rings, out under the wall;
    the wall, with a doorway where a way comes in; and a flat ceiling."""
    hx, hy, f, R, tall = hall.x, hall.y, hall.floor, hall.r, hall.tall
    sides = 32
    at = lambda k, r: (hx + math.cos(2 * math.pi * k / sides) * r, hy + math.sin(2 * math.pi * k / sides) * r)
    # (In the tower, right out to its outer wall: by the doorway, where the
    # room's own wall is open, you'd see the ground between them.)
    out = TOWER_R * math.cos(math.pi / SIDES) - 0.02 if hall.place == "tower" else R + 0.5
    rings = [0.0, 1.4, 2.8, 4.2, out]
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
        if hall.place == "tower":
            # (Its doorway, and its windows: just as wide as they are.)
            a0 = 2 * math.pi * k / sides
            for piece in wall_pieces(p0, p1, a0, a0 + 2 * math.pi / sides, f - 0.3, f + tall, f,
                                     lambda a: polygon_at(a, R + E, sides, 0), TOWER_WINDOWS + [tower_door()]):
                quad(b, piece, hall.wall)
            continue
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
        tower_stones(b, hall, sides)
        # No light of its own: what comes in at its windows (cold daylight,
        # most at the big one), and warm through the cracks round the stone
        # across the doorway, on the floor just inside it. And the shafts of
        # light from the windows (the game draws them): where each one's
        # inside face is, and which way is in.
        for a, half, z0, z1 in TOWER_WINDOWS:
            big = half > 0.1
            # (The big one's, out over the room: right by you on the landing,
            # it would blaze.)
            hall.lights.append({"at": (*polygon_at(a, R - (2.5 if big else 0.4), sides, 0), f + (z0 + z1) / 2),
                                "colour": "#dbe7ff" if big else "#b9cbef", "glow": 1.0 if big else 0.7,
                                "reach": 11 if big else 6})
            x_, y_ = polygon_at(a, R + E, sides, 0)
            hall.windows.append({"at": (x_, y_), "sill": f + z0, "lintel": f + z1, "wide": 2 * (R + E) * math.sin(half),
                                 "in": (-math.cos(a), -math.sin(a))})
        hall.lights.append({"at": (hx, hy - R + 0.5, f + 0.3), "colour": "#ffb066", "glow": 0.5, "reach": 4.5})
        # Stone slabs coming out of the wall, curling up it from the west,
        # round by the north, to a landing in the east, at the window onto the
        # balcony: you walk under them, once they're over your head. (Nothing
        # in the middle: you'd stop there, in the reach of the stone that
        # shuts you in.)
        n, wide, ahead = 15, 0.25, TOWER_FACING  # steps, half the landing's angle, and its middle
        rise, thick = TOWER_LANDING / (n + 1), 0.15
        turn = (math.pi - wide - ahead) / n
        flights = [(math.pi - k * turn, math.pi - (k + 1) * turn, f + rise * (k + 1)) for k in range(n)]
        flights += [(ahead + wide, ahead, f + TOWER_LANDING), (ahead, ahead - wide, f + TOWER_LANDING)]  # (in two, to follow the wall)
        for a0, a1, top in flights:
            inner, outer = R - 1.1, R + E + 0.2  # (into the wall, which is straight between its corners)
            pts = [(hx + math.cos(a) * r, hy + math.sin(a) * r) for a, r in ((a0, inner), (a1, inner), (a1, outer), (a0, outer))]
            low = max(f, top - thick)
            quad(b, [(*p, top) for p in pts], STONE, 0.08)
            quad(b, [(*p, low) for p in pts], STONE, 0.08)
            for i, j in ((0, 1), (1, 2), (3, 0)):  # its inner edge and its ends
                quad(b, [(*pts[i], low), (*pts[j], low), (*pts[j], top), (*pts[i], top)], STONE, 0.08)
            for a in ((3 * a0 + a1) / 4, (a0 + 3 * a1) / 4):  # (two, or near its inner edge you'd fall through)
                under_circle(hx + math.cos(a) * (R - 0.5), hy + math.sin(a) * (R - 0.5), 0.6, top=top, bottom=low)
        # A chest at the back, under the stairs, with the emerald in it: on a
        # shallow tray (so you see it over the front, and what you drop in
        # lands on it), under a lid on its back edge, its own object, which
        # the game opens as you come up to it. Its sides are too high to step
        # over: you can't climb in (but you can go over them, up the stairs).
        x0, y0, x1, y1, top, tray, t = hx - 0.8, hy + R - 1.0, hx + 0.8, hy + R - 0.3, f + 0.62, f + 0.4, 0.06
        block(b, x0, y0, f, x1, y1, tray, DARK_WOOD, solid=False)
        for wx0, wy0, wx1, wy1 in ((x0, y0, x1, y0 + t), (x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1)):
            block(b, wx0, wy0, tray, wx1, wy1, top, DARK_WOOD, solid=False)
            under_box((wx0 + wx1) / 2, (wy0 + wy1) / 2, (wx1 - wx0) / 2, (wy1 - wy0) / 2, top=top)
        under_box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2 - t, (y1 - y0) / 2 - t, top=tray)
        lid = c.Builder()
        block(lid, -(x1 - x0) / 2 - 0.02, -(y1 - y0) - 0.02, 0, (x1 - x0) / 2 + 0.02, 0, 0.08, DARK_WOOD, solid=False)
        for bx in (-0.5, 0.5):
            block(lid, bx - 0.04, -(y1 - y0) - 0.03, -0.01, bx + 0.04, 0.01, 0.09, IRON, solid=False)
        lid.build("chest-lid", smooth=False).location = ((x0 + x1) / 2, y1, top)
        CHEST.update(x=(x0 + x1) / 2, y=(y0 + y1) / 2, floor=tray)


# The fire's embers and flames: their own object, which the game makes glow.
embers = c.Builder()


def charcoal_hut(b, hall):
    """Inside the charcoal burner's hut, as in its picture: an earth floor,
    and in the middle the fire, smouldering in a ring of stones (the game
    sends its smoke up and out of the hole in the roof); a bench, sacks of
    charcoal, a table with a bowl and a stool, a heap of charcoal, and the
    burner's cloak hanging on one of the posts holding up the roof."""
    hx, hy, f, R = hall.x, hall.y, hall.floor, hall.r
    rnd = random.Random("charcoal hut inside")
    at = lambda r, a: (hx + math.cos(a) * r, hy + math.sin(a) * r)
    # The floor, out under the wall: trodden earth, grey with ash by the fire.
    sides, rings = 32, [0.0, 0.8, 1.4, 2.0, 2.6, 3.3, 4.0, HUT_R + 0.05]
    for i in range(len(rings) - 1):
        for k in range(sides):
            a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
            corners = [(rings[i], a0), (rings[i], a1), (rings[i + 1], a1), (rings[i + 1], a0)]
            verts = [(*at(r, a), f - 0.06) for r, a in corners]
            b.add(verts, [(0, 1, 2, 3)], [c.vary(c.mix(c.linear("#4a3e34"), c.linear("#6b4f35"), (r - 0.6) / 1.6), 0.15,
                                                 Vector(v)) for (r, _), v in zip(corners, verts)])
    # The fire: a ring of stones round a bed of ash, burnt logs fallen in
    # together, and charcoal, glowing (embers, its own object) under little flames.
    for k in range(11):
        a = 2 * math.pi * k / 11 + rnd.uniform(-0.1, 0.1)
        b.blob((*at(0.85 + rnd.uniform(-0.04, 0.06), a), f + 0.06), rnd.uniform(0.2, 0.27), c.linear("#7d7468"),
               squash=0.72, lumpy=0.3, seed=60 + k)
    ash = [(hx, hy, f + 0.02)] + [(*at(0.75, 2 * math.pi * k / 16), f + 0.02) for k in range(16)]
    b.add(ash, [(0, 1 + k, 1 + (k + 1) % 16) for k in range(16)], [c.linear("#3c3631")] * 17)
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2 + rnd.uniform(-0.2, 0.2)
        inner = (*at(0.12, a + math.pi), f + 0.22)
        log(b, (*at(0.68, a), f + 0.07), inner, 0.07, c.linear("#2a1f18"))
        embers.blob(inner, 0.085, c.linear("#e8561a"), squash=0.8, lumpy=0.3, seed=70 + k, subdivisions=1, lit=False)
    for k in range(26):
        a, r = rnd.uniform(0, 2 * math.pi), 0.55 * math.sqrt(rnd.random())
        hot = rnd.random() < 0.6
        target = embers if hot else b
        colour = c.mix(c.linear("#8a1c08"), c.linear("#f0702a"), rnd.random()) if hot else c.linear("#1c1916")
        target.blob((*at(r, a), f + 0.06), rnd.uniform(0.04, 0.09), colour, squash=0.7, lumpy=0.3, seed=80 + k,
                    subdivisions=1, lit=False)
    for k in range(2):
        a = math.pi * k + 0.4
        embers.cone((*at(0.12, a), f + 0.16), rnd.uniform(0.1, 0.14), 0.04, c.linear("#ff8a2a"), sides=5, droop=0)
    under_circle(hx, hy, 1.15)
    # Four posts holding up the roof (on the north side, either side of the opening).
    for a in (math.pi / 3, 2 * math.pi / 3, 4 * math.pi / 3, 5 * math.pi / 3):
        px, py = at(3.55, a)
        b.cylinder((px, py, f - 0.1), (px, py, hut_roof(3.55, 0.15)), 0.18, 0.16, HUT_DARK, sides=8)
        under_circle(px, py, 0.25)
    # The bench, along the west wall.
    furniture(b, hx - 3.2, hy - 1.1, hx - 2.8, hy + 0.7, f + 0.38, f + 0.48, WOOD)
    for lx in (hx - 3.12, hx - 2.88):
        for ly in (hy - 0.95, hy + 0.55):
            block(b, lx - 0.05, ly - 0.05, f, lx + 0.05, ly + 0.05, f + 0.38, DARK_WOOD, solid=False)
    # Sacks of charcoal, heaped up.
    for k, (sx, sy) in enumerate(((2.85, 1.45), (2.2, 2.3), (-2.5, 2.2))):
        sx, sy = hx + sx, hy + sy
        b.blob((sx, sy, f + 0.4), 0.42, c.linear("#7a6448"), squash=1.15, lumpy=0.15, seed=90 + k)
        for m in range(7):
            a, r = rnd.uniform(0, 2 * math.pi), 0.22 * math.sqrt(rnd.random())
            b.blob((sx + math.cos(a) * r, sy + math.sin(a) * r, f + 0.84), rnd.uniform(0.07, 0.11), c.linear("#1e1b19"),
                   lumpy=0.35, seed=100 + k * 10 + m, subdivisions=1)
        under_circle(sx, sy, 0.45)
    # The table on the east side, with a bowl and a cup on it, and a stump for a stool.
    tx0, ty0, tx1, ty1 = hx + 2.75, hy - 1.5, hx + 3.25, hy - 0.2
    furniture(b, tx0, ty0, tx1, ty1, f + 0.7, f + 0.78, WOOD)
    for lx in (tx0 + 0.07, tx1 - 0.07):
        for ly in (ty0 + 0.07, ty1 - 0.07):
            block(b, lx - 0.05, ly - 0.05, f, lx + 0.05, ly + 0.05, f + 0.7, DARK_WOOD, solid=False)
    b.cylinder((hx + 3.0, hy - 1.0, f + 0.78), (hx + 3.0, hy - 1.0, f + 0.9), 0.1, 0.18, c.linear("#7a5a3a"), sides=10)
    b.cylinder((hx + 3.0, hy - 0.5, f + 0.78), (hx + 3.0, hy - 0.5, f + 0.92), 0.05, 0.05, c.linear("#8a6a48"), sides=8)
    sx, sy = hx + 2.2, hy - 1.9
    b.cylinder((sx, sy, f - 0.05), (sx, sy, f + 0.45), 0.25, 0.24, c.linear("#5e4630"), sides=10)
    lid = [(sx, sy, f + 0.45)] + [(sx + math.cos(2 * math.pi * k / 10) * 0.24, sy + math.sin(2 * math.pi * k / 10) * 0.24,
                                   f + 0.45) for k in range(10)]
    b.add(lid, [(0, 1 + k, 1 + (k + 1) % 10) for k in range(10)], [c.linear("#a88a60")] * 11)
    under_circle(sx, sy, 0.27, top=f + 0.45)
    # A heap of charcoal against the south wall.
    cx_, cy_ = hx - 0.3, hy - 3.2
    for m in range(40):
        a, r = rnd.uniform(0, 2 * math.pi), 0.55 * math.sqrt(rnd.random())
        b.blob((cx_ + math.cos(a) * r, cy_ + math.sin(a) * r, f + 0.05 + (0.55 - r) * 0.4), rnd.uniform(0.07, 0.12),
               c.linear("#1e1b19"), lumpy=0.35, seed=150 + m, subdivisions=1)
    under_circle(cx_, cy_, 0.55)
    # The cloak, on the south-east post, facing in.
    a = 5 * math.pi / 3
    px, py = at(3.55 - 0.2, a)
    wall_panel(b, px, py, (-math.sin(a) * 0.3, math.cos(a) * 0.3), f, f + 0.8, f + 2.0, c.linear("#6a4a2a"))
    log(b, (*at(3.4, a), f + 2.0), (*at(3.25, a), f + 2.05), 0.03, DARK_WOOD)
    # The fire, glowing, and where its smoke goes out (the game draws it).
    HUT_FIRE.update(x=hx, y=hy, floor=f, hole=hut_roof(HUT_HOLE_R), r=HUT_HOLE_R)

for hall in HALLS.values():
    if hall.place == "charcoal-hut":
        charcoal_hut(rooms, hall)
    elif hall.room:
        room(rooms, hall)
    elif hall.indoor:
        round_room(tower_inside if hall.place == "tower" else rooms, hall)

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
# The stairs up to it from the lair, over the way's ramp (which is what you
# walk on): each tread's top just over the ramp's floor at the tread's back,
# so the ramp never shows through it.
TREADS = 12
rise, run = gh.floor - ml.floor, LAIR_STAIRS_TOP - LAIR_STAIRS_FOOT
for k in range(TREADS):
    # (Clear of the way's own faces: the bottom one a little out in front of
    # the doorstep's edge, and each a shade narrower than its walls.)
    y0, y1 = LAIR_STAIRS_FOOT + run * k / TREADS - (0.03 if k == 0 else 0), LAIR_STAIRS_FOOT + run * (k + 1) / TREADS
    top = ml.floor + rise * (k + 1) / TREADS + 0.08  # (the ramp's floor is 4 cm up)
    block(rooms, gh.x - TUNNEL_HALF + 0.01, y0, ml.floor - 0.1, gh.x + TUNNEL_HALF - 0.01, y1, top,
          c.vary(c.linear("#7d7568"), 0.1, Vector((k, 0, 7))), solid=False)
# The lair's door, which slams and locks behind you.
lx_, ly_ = ml.x + ml.w + 0.6, SR[1]
block(rooms, lx_ - 0.15, ly_ - TUNNEL_HALF, ml.floor, lx_ + 0.15, ly_ + TUNNEL_HALF, ml.floor + TUNNEL_TALL, OAK, solid=False)
# (Reaching only a little way into the lair: it's small, and he'd otherwise
# keep you from its whole east end.)
obstacle(["merlins-lair east"], "box", lx_, -ly_, 0.5, TUNNEL_HALF + 0.3, under=True, reach=1.0)
rooms.build("rooms", smooth=False)
webs.build("cobwebs", smooth=False)
tower_inside.build("tower-inside", smooth=False)
embers.build("embers", smooth=False)

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

# The evergreen glade's "red spotted toadstools growing in a ring": on the
# grass north of the path, as in its picture, big and small, here and there
# two or three together. Quaternius's (Ultimate Crops, art/models/), their
# caps already spotted, made a brighter red. Solid (nothing can be dropped
# into them), but you can step up onto the little ones, and jump onto the
# big ones.
CROPS = HERE.parent / "models/ultimate-crops/Blends"
TOADSTOOL_COLOURS = {"Red": c.linear("#c7261c"), "Mushroom1": c.linear("#efe6d2")}
RING = (P["evergreen-glade"][0] + 1.5, P["evergreen-glade"][1] + 6.0, 3.4)  # its middle, and how far round


def toadstool(kind, tall):
    """One of the pack's mushrooms, `tall` metres high: to make, for stamp."""

    def make(b):
        with bpy.data.libraries.load(str(CROPS / f"{kind}.blend")) as (src, dst):
            dst.objects = [name for name in src.objects if name == kind]
        obj = dst.objects[0]
        mesh = obj.data
        scale = tall / max(v.co.z for v in mesh.vertices)
        colours = [TOADSTOOL_COLOURS.get(m.name.split(".")[0], (0.5, 0.5, 0.5, 1)) for m in mesh.materials]
        for poly in mesh.polygons:
            pts = [tuple(mesh.vertices[i].co * scale) for i in poly.vertices]
            b.add(pts, [tuple(range(len(pts)))], [c.vary(colours[poly.material_index], 0.1, Vector(p) * 8) for p in pts])
        wide = max(abs(v.co.x) for v in mesh.vertices) * scale
        bpy.data.objects.remove(obj)
        return (-wide, -wide, wide, wide), tall

    return make


here = random.Random("the toadstool ring")
KINDS_OF_TOADSTOOL = ["Mushroom_1", "Mushroom_2", "Mushroom_3", "Mushroom_4"]
TOADSTOOL_TALL = [0.36, 0.46, 0.6, 0.75]  # metres, each kind
SPOTS = 26
for n in range(SPOTS):
    a = 2 * math.pi * (n + here.uniform(-0.3, 0.3)) / SPOTS
    # (Now and then a little one or two beside a bigger one.)
    for k in range(1 if here.random() < 0.6 else here.choice((2, 3))):
        r = RING[2] + here.uniform(-0.25, 0.25) + (here.uniform(-0.45, 0.45) if k else 0)
        x, y = RING[0] + math.cos(a + k * 0.05) * r, RING[1] + math.sin(a + k * 0.05) * r
        assert out_on_the_path(x, y) > 1.4, (x, y)  # (on the grass, clear of the path)
        size = here.randrange(4) if not k else here.randrange(2)
        z = drawn_height(x, y) - 0.03
        stamp(f"toadstool-{size}", toadstool(KINDS_OF_TOADSTOOL[size], TOADSTOOL_TALL[size]), (x, y, z),
              here.uniform(0, 2 * math.pi), solid=False)
        (_, _, wide, _), tall = prop_kinds[f"toadstool-{size}"]
        solid_circle(x, y, wide * 0.9, top=z + tall)

# ---------------------------------------------------------------- what grows where

# Where you can stand, a square metre at a time.
MASK_STEP = 1.0
mx, my = int((X1 - X0) / MASK_STEP), int((Y1 - Y0) / MASK_STEP)
mask = bytes(1 if walkable(X0 + (i + 0.5) * MASK_STEP, Y0 + (j + 0.5) * MASK_STEP) else 0
             for j in range(my) for i in range(mx))


def out_of_sight():
    """The trees no one will ever see: from everywhere you can stand (and the
    balcony), the land's in the way (behind the mountain, or the ridge).
    They're not grown at all."""
    import numpy as np
    heights = np.array(GROUND_HEIGHTS).reshape(ny, nx)

    def lowest(xs, ys):
        # (The lowest corner of the ground's square: so a crest never hides
        # more than it would.)
        i = np.clip(((xs - X0) // STEP).astype(int), 0, nx - 2)
        j = np.clip(((ys - Y0) // STEP).astype(int), 0, ny - 2)
        return np.minimum(np.minimum(heights[j, i], heights[j, i + 1]),
                          np.minimum(heights[j + 1, i], heights[j + 1, i + 1]))

    spots = [(X0 + (i + 0.5) * MASK_STEP, Y0 + (j + 0.5) * MASK_STEP)
             for j in range(0, my, 3) for i in range(0, mx, 3) if mask[j * mx + i]]
    ex, ey = np.array([x for x, _ in spots]), np.array([y for _, y in spots])
    ez = np.array([height(x, y) for x, y in spots]) + 1.6
    ex, ey, ez = np.append(ex, LADDER_TOP[0]), np.append(ey, LADDER_TOP[1]), np.append(ez, LADDER_TOP[2] + 1.6)
    t = np.linspace(0.02, 0.97, 96)
    hidden = []
    for k, (kind, x, z, y, _, scale) in enumerate(tree_spots["at"]):
        y = -y
        d = np.hypot(ex - x, ey - y)
        if d.min() < 25:
            continue
        near = np.argsort(d)
        tall = scale * TREE_MODEL[KINDS[kind]]
        seen = False
        for chunk in np.array_split(near, max(1, len(near) // 400)):
            for top in (z + 0.4 * tall, z + 0.9 * tall):
                sx = ex[chunk, None] + (x - ex[chunk, None]) * t
                sy = ey[chunk, None] + (y - ey[chunk, None]) * t
                sz = ez[chunk, None] + (top - ez[chunk, None]) * t
                if (lowest(sx, sy) < sz + 0.2).all(axis=1).any():
                    seen = True
                    break
            if seen:
                break
        if not seen:
            hidden.append(k)
    return hidden


hidden = set(out_of_sight())
print(f"{len(hidden)} of {len(tree_spots['at'])} trees out of sight")
tree_spots["at"] = [spot for k, spot in enumerate(tree_spots["at"]) if k not in hidden]

# A square metre at a time (as the walkable mask), what grows there: what
# kind of ground (GROUND, its lowest three bits; 0, nothing: water, paths,
# floors, bare rock), and what mix of flowers and plants (MIXES, the rest),
# by the place nearest (give or take, so they blend). The game scatters
# grass, flowers, bushes and stones by it, round you (src/three/plants.ts).
GROUND = {"meadow": 1, "verge": 2, "forest": 3, "bank": 4, "wall": 5, "path": 6}
MOUNTAIN_TOP = 6  # the meadow round the maze: daisies and buttercups (growing high up, as nothing else does)
MIXES = {
    # Daisies and buttercups, and foxgloves here and there.
    **dict.fromkeys(["old-wall", "old-stone-wall", "rusty-gate", "grassy-bank", "forest-edge", "deep-river",
                     "river-south-bank", "moat", "courtyard"], 1),
    "yellow-flowers": 2,  # buttercups everywhere
    **dict.fromkeys(["mossy-steps", "tower"], 3),  # ferns and mossy stones
    **dict.fromkeys(["evergreen-glade", "mountain-path", "mountain", "cave-entrance", "dragon-cave", "maze",
                     "trolls", "oak-door", "treasure-room", "giant", "damp-tunnels"], 4),  # under the firs: ferns
    **dict.fromkeys(["forest-crossroads", "forest-witches", "charcoal-hut"], 5),  # woodland: foxgloves and ferns
}
WALL_LINES = Lines()
WALL_LINES.add([(WX, -18 * K), (WX, WY), (WW, WY), (WW, 118 * K)])


def growth(x, y):
    # (Nor up through the bridges' sides, nor the drawbridge's.)
    if abs(x - BRIDGE[0]) <= 3.0 and abs(y - BRIDGE[1]) <= BRIDGE_HALF + 0.6:
        return 0
    if abs(x) <= 3.6 and -143 * K - 0.6 <= y <= -127 * K + 0.6:
        return 0
    if deck(x, y) is not None or in_moat(x, y) or rocky(x, y) or in_building(x, y):
        return 0
    if CASTLE[0] - 1 <= x <= CASTLE[1] + 1 and CASTLE[2] - 1 <= y <= CASTLE[3] + 1:
        return 0
    if abs(x - MZ[0]) <= MAZE_HALF + 0.4 and abs(y - MZ[1]) <= MAZE_HALF + 0.4:
        return 0  # (nor up through the maze's floor)
    river = from_river(x, y)
    if river < BANK + 0.6 or open_to_the_sky(x, y, 1.0) is not None or over_an_opening(x, y):
        return 0
    if any(abs(x - sx) <= hx + 0.4 and abs(y + sz) <= hz + 0.4 for sx, sz, hx, hz, _ in STEPS):
        return 0
    if any(math.hypot(x - sx, y - sy) < r + 0.3 for sx, sy, r in OLD_STONES):
        return 0
    to_path = min(path_lines.distance(x, y), trails.distance(x, y) * 1.4)
    to_wall = WALL_LINES.distance(x, y)
    if to_wall < 0.75:
        return 0
    # (On a path, only grit; and the grass by it growing a little way over its
    # edges. But not where it peters out, at the narrows: the bank's grass and
    # stones, up to the water; but for under the plank, laid across there.)
    if 1.0 < abs(x - NARROWS_X) < NARROWS_HALF and (river - BANK) * narrowing(x, y) < 1.6:
        ground = "bank"
    elif to_path < HALF - 0.4:
        ground = "path"
    elif to_wall < 2.4:
        ground = "wall"
    elif to_path < 3.4:
        ground = "verge"
    elif river < SHORE + 2.5:
        ground = "bank"
    elif open_ground(x, y):
        ground = "meadow"
    else:
        ground = "forest"
    if ground != "path" and maze_meadow(x, y) > 0.5:
        return GROUND["meadow"] | MOUNTAIN_TOP << 3  # (grass and flowers, high up)
    jx, jy = noise.noise(Vector((x / 25, y / 25, 3))) * 14, noise.noise(Vector((x / 25, y / 25, 9))) * 14
    nearest = min(P, key=lambda p: math.hypot(x + jx - P[p][0], y + jy - P[p][1]))
    return GROUND[ground] | MIXES.get(nearest, 1) << 3


growing = bytes(growth(X0 + (i + 0.5) * MASK_STEP, Y0 + (j + 0.5) * MASK_STEP)
                for j in range(my) for i in range(mx))

# ---------------------------------------------------------------- write it all out


if out:
    c.export(out)
    base = Path(out).with_suffix("")
    base.with_suffix(".bin").write_bytes(struct.pack(f"<{len(walk)}f", *walk) + mask + growing)
    base.with_suffix(".json").write_text(json.dumps({
        "ground": {"x0": X0, "y0": Y0, "step": STEP, "nx": nx, "ny": ny},
        "walkable": {"x0": X0, "y0": Y0, "step": MASK_STEP, "nx": mx, "ny": my, "offset": len(walk) * 4},
        # What grows where, on the same grid (just after it).
        "growth": {"offset": len(walk) * 4 + len(mask)},
        "obstacles": obstacles,
        # The river's middle, upstream to down, [x, z] in three.js's axes, and its water's height.
        # (And how wide it is at each, of its usual width: narrower at the narrows.)
        "river": {"line": [[round(x, 2), round(-y, 2), round(narrowing(x, y), 3)] for x, y in RIVER], "water": WATER_LEVEL,
                  "bank": BANK, "narrows": {"x": NARROWS_X, "z": round(60 * K, 2), "shore": round(SHORE * NARROW, 2)}},
        # The ways underground: points [x, z, floor] in three.js's axes.
        "ways": {name: {"half": way.half, "points": [[round(x, 2), round(-y, 2), round(f, 2)] for x, y, f in way.points],
                        **({"indoor": True} if way.indoor else {})}
                 for name, way in WAYS.items()},
        # The halls they join: being in one is being in its place.
        "halls": {place: {"x": hall.x, "z": -hall.y, "floor": hall.floor, "r": round(hall.r, 2), "tall": hall.tall,
                          **({"w": hall.w, "d": hall.d} if hall.room else {}),
                          **({"indoor": True} if hall.indoor else {}),
                          **({"light": hall.light, "glow": hall.glow} if hall.light else {}),
                          # (Or the light coming in, at [x, y, z]; and dark without it.)
                          **({"lights": [{"at": [round(x, 2), round(z, 2), round(-y, 2)], "colour": l["colour"],
                                          "glow": l["glow"], "reach": l["reach"]}
                                         for l in hall.lights for x, y, z in [l["at"]]]} if hall.lights else {}),
                          **({"dark": True} if hall.dark else {}),
                          # (And its windows' shafts of light: each one's inside face, and which way is in.)
                          **({"windows": [{"x": round(w["at"][0], 2), "z": round(-w["at"][1], 2), "sill": round(w["sill"], 2),
                                           "lintel": round(w["lintel"], 2), "wide": round(w["wide"], 2),
                                           "in": [round(w["in"][0], 3), round(-w["in"][1], 3)]} for w in hall.windows]}
                             if hall.windows else {})}
                  for place, hall in HALLS.items()},
        "under": {"circles": under_circles, "boxes": under_boxes},
        # Where the ladder rests under the balcony, its top [x, y, z], and which way is out from it [x, z].
        "balcony": {"top": [round(LADDER_TOP[0], 2), round(LADDER_TOP[2], 2), round(-LADDER_TOP[1], 2)],
                    "out": [round(math.sin(TOWER_FACING), 3), round(math.cos(TOWER_FACING), 3)]},
        # The tower's stone: how big, and where its middle is [x, z, y], beside the door and across it.
        "stone": {"r": STONE_R, **{k: [round(x, 2), round(-y, 2), round(z, 2)] for k, (x, y, z) in STONE_SPOTS.items()}},
        # The chest in the tower, where the emerald starts: its middle [x, z], and its tray.
        "chest": [round(CHEST["x"], 2), round(-CHEST["y"], 2), round(CHEST["floor"], 2)],
        # Merlin's trap: where the net lies [x, z] (on the ground), its treasure [x, y, z] and the jewels in it
        # ([x, y, z, kind]), and where its rope's tied, up in the oak.
        "trap": {"net": [round(TRAP_NET[0], 2), round(-TRAP_NET[1], 2)], "gold": [round(TX, 2), round(TZ, 2), round(-TY, 2)],
                 "jewels": jewel_spots,
                 "hook": [round(TRAP_HOOK[0], 2), round(TRAP_HOOK[2], 2), round(-TRAP_HOOK[1], 2)]},
        # The deep hole: [x, z, half x, half z], the way's floor across it, how deep it goes and its beam's underside.
        "hole": {"box": [round(px, 2), round(-py, 2), round(phx, 2), round(phy, 2)], "floor": round(pit_floor, 2),
                 "bottom": round(bottom, 2), "beam": round(PIT_BEAM, 2)},
        # The drawbridge: its hinge [x, y, z] (at its deck), how long and half how wide it is, how far in from
        # its tip its chains are fixed, and their holes in the gatehouse [x, y, z]; where the guards stand [x, z]
        # and the castle's walls [west, east, north, south] (in it, it's down).
        "drawbridge": {"hinge": [0, DB_TOP, round(-DB_HINGE, 2)], "length": round(DB_LENGTH, 2), "half": DB_HALF,
                       "chain": DB_CHAIN, "anchors": [[round(x, 2), round(z, 2), round(-y, 2)] for x, y, z in DB_ANCHORS],
                       "guards": [[round(x, 2), round(-y, 2)] for x, y in GUARDS],
                       "castle": [CASTLE[0], CASTLE[1], round(-CASTLE[3], 2), round(-CASTLE[2], 2)]},
        # The leaves in the dragon's mouth: where the pile is [x, z] (on the way's floor), and the heaps they're swept into.
        "leaves": {"at": [round(lx, 2), round(-ly, 2)], "heaps": [[round(x, 2), round(-y, 2)] for x, y in LEAF_HEAPS]},
        # The fire in the charcoal burner's hut, its middle [x, z] and floor, and the smoke hole over it: how high, and how wide.
        "hut": {"fire": [round(HUT_FIRE["x"], 2), round(-HUT_FIRE["y"], 2), round(HUT_FIRE["floor"], 2)],
                "hole": round(HUT_FIRE["hole"], 2), "r": HUT_FIRE["r"]},
        # The witches' sign: its painted face's middle [x, y, z], which way it faces [x, z], how askew, and how big.
        "sign": SIGN,
        # The clues, a note on a post at each dead end: the exit that leads there, the note's middle [x, y, z],
        # which way it faces [x, z], how far it leans back, and how big it is.
        "notes": NOTES,
        "bounds": [X0 + 4, X1 - 4, Y0 + 4, Y1 - 4],
        "circles": circles,
        "boxes": boxes,
        "trees": tree_spots,
        "props": prop_spots,
        # Steps on the land, for lying on: [x, z, half x, half z, top].
        "steps": STEPS,
        # Floors over the ground, for lying on: [x, z, half x, half z, how far up]. (The maze's.)
        "floors": [[round(MZ[0], 2), round(-MZ[1], 2), round(MAZE_HALF, 2), round(MAZE_HALF, 2), MAZE_FLOOR]],
        # The paths, lying a little above the ground (so what's dropped on
        # one lies on it, not in it): each its line [x, z], in three.js's
        # axes, how far either side of it it goes, and how far up it is.
        "paths": [{"half": round(REACH * 1.1, 2), "lift": PATH_LIFT,
                   "points": [[round(x, 2), round(-y, 2)] for x, y in line]} for k, line in enumerate(paths)],
    }, separators=(",", ":")))
    print(f"Exported {out}: {len(circles)} solid circles, {len(boxes)} boxes, {len(obstacles)} obstacles")
if preview:
    c.preview(preview, (60, -120, 160), (0, -20, 0), (-0.7, 0.5, -0.45), lens=20)
