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

from mathutils import Matrix, Vector, noise

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
FLAGS = c.linear("#6f6656")  # (the joints between the courtyard's cobbles)
STONE = c.linear("#9a978a")
WATER = c.linear("#3d7fa8")
GREY = c.linear("#b9b4a8")
MORTAR = c.linear("#8e8676")  # (between the castle's stones: the courtyard)
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

# The dragon (dragon.py), standing just in from the tunnel south, beside
# it, facing west-south-west, across the way in from the west: it turns its
# head to breathe its fire across the mouth of the tunnel. (Its head as near
# the roof as it can be, and nothing hanging there; its tail curled round
# behind it, on its right.) Where it stands, which way it faces, and its
# shape on the ground: circles [x, y, r] from where it stands, as it faces -y.
DRAGON_AT = (P["dragon-cave"][0] + 3.6, P["dragon-cave"][1] - 4.2)
DRAGON_YAW = math.atan2(-0.96, 0.29)  # (anticlockwise, from facing -y)
DRAGON_SHAPE = [(0, -0.9, 1.5), (0, 1.0, 1.4), (-0.3, 3.6, 0.55), (-0.8, 5.2, 0.4), (-2.0, 5.6, 0.35),
                (-3.0, 4.8, 0.3), (-2.9, 3.6, 0.25)]
DRAGON_CLEAR = 5.5  # metres round it, with no stalactites (and no stalagmites near any of it)


def dragon_shape():
    """Its circles on the ground, where it stands: [x, y, r]."""
    move = c.Kit.placing((*DRAGON_AT, 0), DRAGON_YAW, 0.91)  # (as dragon.py scales it)
    return [(*move((x, y, 0))[:2], r) for x, y, r in DRAGON_SHAPE]


# The trolls (trolls.py), sitting on boulders round the north of their cave,
# two either side of the way north, facing in across it, as in its picture;
# one with its drum on the floor beside it. Each: how far round from north it
# sits (radians, anticlockwise), how big it is (times the model's size), and
# how far out from the cave's middle (metres: the bigger ones further in, off
# the wall). The two biggest on the west, away from the way in from the east.
TROLLS = [(0.86, 1.9, 6.1), (0.48, 2.3, 5.7), (-0.42, 1.38, 6.3), (-0.74, 1.8, 6.1)]
TROLL_SEAT = (0.48, 0.33)  # its seat: how high, and how far behind it (at the model's size: sitting, as its clip does)
TROLL_BODY = 0.75  # its radius, at the model's size: for bumping into, and keeping the rocks clear
TROLL_DRUM = 2  # which of them has the drum


def troll_spots():
    """Each troll: where it sits [x, y], which way it faces [x, y] (to the
    cave's middle, a little south of it), and how big it is."""
    hall = HALLS["trolls"]
    spots = []
    for round_, size, out in TROLLS:
        a = math.pi / 2 + round_
        x, y = hall.x + math.cos(a) * out, hall.y + math.sin(a) * out
        facing = Vector((hall.x - x, hall.y - 1.5 - y)).normalized()
        spots.append(((x, y), (facing.x, facing.y), size))
    return spots


# The giant (giant.py), sitting on a boulder beside the way west out of his
# cave, north of it, facing in: in the way's reach, so you bump into it with
# him by you, watching you.
GIANT_SIZE = 4.0  # times the model's size
GIANT_SEAT = (0.475, 3.8)  # where he sits: radians round from the way west (north of it), and metres in from the wall
GIANT_BODY = 0.6  # his radius sitting, at the model's size: for bumping into, and keeping the rocks clear
GIANT_ROCK = (0.55, 0.33)  # his boulder's top: how high, and how far behind him (at the model's size: his legs are longer than a troll's)


def giant_spot():
    """Where the giant sits [x, y], and which way he faces [x, y] (to the cave's middle)."""
    hall = HALLS["giant"]
    a = math.pi - GIANT_SEAT[0]
    out = hall.r - GIANT_SEAT[1]
    seat = (hall.x + math.cos(a) * out, hall.y + math.sin(a) * out)
    facing = Vector((hall.x - seat[0], hall.y - seat[1])).normalized()
    return seat, (facing.x, facing.y)


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
    # And in through the coach house's wide doors (its own doorway: courtyard).
    "coach-door": Way([(CH[0] - HALLS["coach-house"].w - 1.8, CH[1], None), (*CH, 0.4)], half=2.4, indoor=True,
                      open=True),
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


# The forest bridge and the drawbridge (with the way in under the gatehouse,
# and the landing on the bank), for walking on: their middles, half how wide
# and long, and how high. (The game walks you on them at exactly that
# height: the ground's grid, every 2 m, would sink you at their edges.)
DECKS = [(BRIDGE[0], BRIDGE[1], 2.2, BRIDGE_HALF, 0.9), (0, -135 * K, 3, 8 * K, 0.6)]


def deck(x, y):
    """The bridge and drawbridge, for walking on."""
    for x0, y0, half_x, half_y, top in DECKS:
        if abs(x - x0) <= half_x and abs(y - y0) <= half_y:
            return top
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
    if CASTLE[0] <= x <= CASTLE[1] and CASTLE[2] <= y <= CASTLE[3]:
        return True  # (in the castle: its courtyard is cobbled)
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
# (Only over the gate up to the walls' tops, and its full width above them:
# overlapping them, their faces would be in the same place, and flicker.)
block(built, -3, CASTLE[3] - 1, GATEHOUSE[0], 3, CASTLE[3] + 1, 8, MORTAR, solid=False)
block(built, -3.2, CASTLE[3] - 1, 8, 3.2, CASTLE[3] + 1, GATEHOUSE[1], MORTAR, solid=False)
for x in (-3.2, -1.2, 0.8, 2.6):
    block(built, x, CASTLE[3] + 0.4, GATEHOUSE[1], x + 0.6, CASTLE[3] + 1, GATEHOUSE[1] + 0.8, c.linear("#c4b598"), solid=False)
for x, y, z in DB_ANCHORS:
    # (A shade out in front of the stones laid on the wall's face: the courtyard's courses.)
    block(built, x - 0.12, y, z - 0.12, x + 0.12, y + 0.035, z + 0.12, c.linear("#1d1b19"), solid=False)
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
# (Nor off its corners at the castle end, onto the strip of ground at the
# foot of the wall, between it and the water.)
for side in (-1, 1):
    solid_box(side * 3.9, CASTLE[3] + 1.75, 1.0, 0.85)  # (out over the water's edge: you're never wider than the deck there)
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

# The stone archway north of the moat, as in its picture: an old wall of
# dressed stone across the path between the trees (its ends in the forest
# either side), crumbling along its top, mossy low down, ivy hanging from
# it; and a round arch over the path, on a pier either side, its stones
# laid round it, rising over the wall. Solid but for the way through.
ARCH_Y = -82.0  # where it crosses the path
ARCH_X = 0.6  # the path's middle, there
ARCH_ENDS = (-13.0, 13.0)
ARCH_HALF = 1.9  # half the way through
ARCH_SPRING = 2.3  # where the arch springs from its piers
ARCH_RING = 0.5  # how deep its stones are
ARCH_PIER = 1.0  # how wide each pier is
ARCH_TOP = ARCH_SPRING + ARCH_HALF + ARCH_RING + 0.55  # the top over the arch
ARCH_WALL = 2.9  # the wall's height either side (less where it's crumbled)
ARCH_THICK = 0.42  # half its thickness
ARCH_STONES = [c.linear(h) for h in ("#a39d90", "#958f83", "#ada79a", "#8a857a", "#9c968a", "#b2ada2")]
ARCH_GAP = c.linear("#5f584c")
arch = c.Builder()
arch_ivy = c.Builder()  # (its own: casting no shadows, so close to the stones the sun's shadows would speckle them)
arch_rng = random.Random("the stone archway")
arch_tops = []  # (from, to, how high its top is there), as it's built: for the ivy to hang from
arch_laid = []  # (from, to, its top): each stone of the wall, as it's laid, for its core to come up to


def arch_foot(x):
    return drawn_height(x, ARCH_Y, exactly=True) - 0.3


def arch_colour(x, z):
    colour = c.vary(arch_rng.choice(ARCH_STONES), 0.08, Vector((x, z, 5)))
    mossy = smooth(1 - (z - arch_foot(x) - 0.3) / 1.2) * 0.55 + 0.4 * max(0.0, noise.noise(Vector((x / 2, z, 3))))
    colour = c.mix(colour, MOSS, min(0.55, mossy))
    if arch_rng.random() < 0.12:
        colour = c.mix(colour, LICHEN, arch_rng.uniform(0.2, 0.45))
    return colour


def arch_stone(x0, x1, z0, z1):
    """A dressed stone, through the wall, each face standing out a little from its core."""
    arch_laid.append((x0, x1, z1))
    out = ARCH_THICK + arch_rng.uniform(-0.02, 0.03)
    back = ARCH_THICK + arch_rng.uniform(-0.02, 0.03)
    block(arch, x0 + 0.015, ARCH_Y - out, z0 + 0.015, x1 - 0.015, ARCH_Y + back, z1 - 0.015,
          arch_colour((x0 + x1) / 2, (z0 + z1) / 2), solid=False)


# Where it's fallen in from its top: a V, deepest in its middle (its
# middle along it, how wide, and how deep), the stones lying at its foot.
ARCH_BREACHES = [(-7.4, 1.8, 0.85), (4.7, 1.3, 0.6)]


def arch_breach(x):
    """How far down from its top it's fallen in, here."""
    return max([deep * (1 - abs(x - mid) / (wide / 2)) for mid, wide, deep in ARCH_BREACHES
                if abs(x - mid) < wide / 2], default=0.0)


# And where the archway's own top has broken away: from over its crown,
# down to its east pier's outer edge (its ring of stones still whole).
ARCH_BREAK = (ARCH_X + 0.9, ARCH_X + ARCH_HALF + ARCH_PIER, 1.3)  # from, to, and how far down it's gone, there


def arch_broken(x, z1):
    """Whether a stone, its middle along at x and its top at z1, has fallen from the archway's broken corner."""
    start, end, deep = ARCH_BREAK
    return x > start and z1 > ARCH_TOP - deep * min(1.0, (x - start) / (end - start)) + 0.05


def arch_course(x0, x1, z0, z1, short=(0.45, 0.9), top=None, gone=None):
    """A course of stones from x0 to x1, joints staggered. (Along the wall's
    top, one gone now and then; and none where it's fallen in.)"""
    x = x0 - arch_rng.uniform(0, short[0])
    while x < x1 - 0.05:
        long = arch_rng.uniform(*short)
        a, b = max(x, x0), min(x + long, x1)
        x += long
        if b - a <= 0.12:
            continue
        if gone and gone((a + b) / 2, z1):
            continue
        if top is not None:
            if z1 > top - max(arch_breach(a), arch_breach(b), arch_breach((a + b) / 2)) + 0.05:
                continue
            if z1 > top - 0.05 and arch_rng.random() < 0.12:
                continue
        arch_stone(a, b, z0, z1)


def extrados(x):
    """The top of the arch's ring of stones, over x (None beyond it)."""
    dx = abs(x - ARCH_X)
    r = ARCH_HALF + ARCH_RING
    return ARCH_SPRING + math.sqrt(r * r - dx * dx) if dx < r else None


# The wall either side, and the piers: in courses from below the ground,
# its top ragged (stones gone here and there, a few left standing higher).
pier_in, pier_out = ARCH_X - ARCH_HALF, ARCH_X - ARCH_HALF - ARCH_PIER
for lo, hi, pier in ((ARCH_ENDS[0], pier_out, False), (pier_out, pier_in, True),
                     (ARCH_X + ARCH_HALF, ARCH_X + ARCH_HALF + ARCH_PIER, True),
                     (ARCH_X + ARCH_HALF + ARCH_PIER, ARCH_ENDS[1], False)):
    z = min(arch_foot(lo), arch_foot(hi))
    top = ARCH_TOP if pier else ARCH_WALL
    while z < top - 0.05:
        tall = min(arch_rng.uniform(0.3, 0.42), top - z)
        if pier:
            # (Big quoins, the full width of the pier, every other course.)
            arch_course(lo, hi, z, z + tall, (0.45, 0.6) if arch_rng.random() < 0.5 else (ARCH_PIER, ARCH_PIER), top=top,
                        gone=arch_broken)
        else:
            arch_course(lo, hi, z, z + tall, top=top)
        z += tall
    if pier:
        arch_tops.append((lo, hi, top))
    else:
        # Crumbling along its top: a stone or two still standing here and
        # there, lower in places, as in the picture.
        x = lo
        while x < hi - 0.3:
            wide = arch_rng.uniform(0.5, 1.1)
            a, b = x, min(x + wide, hi)
            stack = arch_rng.choice((0, 0, 1, 1, 2))
            fallen = max(arch_breach(a), arch_breach(b), arch_breach((a + b) / 2))
            if fallen > 0:
                stack = 0  # (nothing standing over where it's fallen in)
            for k in range(stack):
                arch_stone(a + 0.05 * k, b - 0.05 * k, top + k * 0.36, top + (k + 1) * 0.36 - 0.02)
            arch_tops.append((a + 0.05 * max(0, stack - 1), b - 0.05 * max(0, stack - 1),
                              top + stack * 0.36 - 0.02 - fallen))
            x += wide
    # Its core, deep in: dark between the stones (and down where it's fallen in).
    steps_ = max(1, int((hi - lo) / 0.2))
    for side in (-1, 1):
        y = ARCH_Y + side * (ARCH_THICK - 0.05)
        for k in range(steps_):
            a, b = lo + (hi - lo) * k / steps_, lo + (hi - lo) * (k + 1) / steps_
            # (Up to its stones' tops, just there: stepping down, a course at a
            # time, where it's fallen in, as its stones do.)
            m = (a + b) / 2
            t = top if not pier and not arch_breach(m) else max(
                (z1 for x0, x1, z1 in arch_laid if x0 <= m <= x1 and z1 <= top + 0.01), default=top) - 0.03
            ta = tb = t
            facing(arch, [(a, y, arch_foot(a)), (b, y, arch_foot(b)), (b, y, tb), (a, y, ta)], [ARCH_GAP] * 4,
                   (0, side, 0))
    solid_box((lo + hi) / 2, ARCH_Y, (hi - lo) / 2, ARCH_THICK + 0.05)
# The arch: its stones laid round it, wedges between its springings, a
# keystone at its crown, a little proud.
VOUSSOIRS = 13
for k in range(VOUSSOIRS):
    a0, a1 = math.pi * k / VOUSSOIRS, math.pi * (k + 1) / VOUSSOIRS
    gap = 0.012
    a0, a1 = a0 + gap, a1 - gap
    key = k == VOUSSOIRS // 2
    r0, r1 = ARCH_HALF, ARCH_HALF + ARCH_RING + (0.08 if key else 0.0)
    # (Standing well out from the wall's stones, where they overlap the piers': not flickering through each other.)
    proud = 0.1 if key else 0.06 + arch_rng.uniform(0.0, 0.02)
    colour = arch_colour(ARCH_X, ARCH_SPRING + 2)
    corners = []
    for y in (ARCH_Y - ARCH_THICK - proud, ARCH_Y + ARCH_THICK + proud):
        for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1)):
            corners.append((ARCH_X + math.cos(a) * r, y, ARCH_SPRING + math.sin(a) * r))
    middle = sum((Vector(p) for p in corners), Vector()) / 8
    for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
        pts = [corners[i] for i in f]
        centre = sum((Vector(p) for p in pts), Vector()) / 4
        facing(arch, pts, [colour] * 4, tuple(centre - middle))
# Over the arch, between the piers: courses down to the arch's ring, each
# stone cut off where it meets it; and the core behind, with the way
# through cut out of it.
z = ARCH_SPRING + 0.2
while z < ARCH_TOP - 0.05:
    tall = min(arch_rng.uniform(0.3, 0.4), ARCH_TOP - z)
    x = pier_in
    while x < ARCH_X + ARCH_HALF - 0.05:
        long = arch_rng.uniform(0.4, 0.8)
        a, b = x, min(x + long, ARCH_X + ARCH_HALF)
        x += long
        lows = [extrados(v) for v in (a, b, (a + b) / 2)]
        floor_ = max((v for v in lows if v is not None), default=0.0)
        # (None where its corner's broken away; a stone gone from its top now and then.)
        if arch_broken((a + b) / 2, z + tall) or (z + tall > ARCH_TOP - 0.05 and arch_rng.random() < 0.2):
            continue
        if z + tall - 0.08 > floor_:
            arch_stone(a, b, max(z, floor_ + 0.02), z + tall)
    z += tall
for side in (-1, 1):
    y = ARCH_Y + side * (ARCH_THICK - 0.05)
    # (Right down to its underside: the joints between its stones dark, not open to the sky.)
    edge = [(ARCH_X + math.cos(math.pi * k / 16) * (ARCH_HALF + 0.03), y,
             ARCH_SPRING + math.sin(math.pi * k / 16) * (ARCH_HALF + 0.03)) for k in range(17)]
    for p, q in zip(edge, edge[1:]):
        # (Up to its stones' tops, just there: down where they're gone, behind its ring.)
        m = (p[0] + q[0]) / 2
        ring = extrados(m) or ARCH_SPRING
        t = max([z1 for x0, x1, z1 in arch_laid if x0 <= m <= x1 and z1 > ring - 0.01] + [ring]) - 0.03
        facing(arch, [p, q, (q[0], y, t), (p[0], y, t)], [ARCH_GAP] * 4, (0, side, 0))
# Behind the joints in the arch's underside, between its two faces: dark,
# and a little way up into its stones (whose own undersides are what you see).
for k in range(16):
    a0, a1 = math.pi * k / 16, math.pi * (k + 1) / 16
    pts = [(ARCH_X + math.cos(a) * (ARCH_HALF + 0.03), y, ARCH_SPRING + math.sin(a) * (ARCH_HALF + 0.03))
           for a, y in ((a0, ARCH_Y - ARCH_THICK), (a1, ARCH_Y - ARCH_THICK), (a1, ARCH_Y + ARCH_THICK),
                        (a0, ARCH_Y + ARCH_THICK))]
    facing(arch, pts, [ARCH_GAP] * 4, (-math.cos((a0 + a1) / 2), 0, -math.sin((a0 + a1) / 2)))
# Ivy, hanging from its top in places, either side, and over the arch.
for side in (-1, 1):
    for cx, wide, drop in ((-9.5, 2.2, 2.0), (-4.2, 1.4, 2.4), (6.5, 2.8, 2.2), (10.5, 1.6, 1.5)):
        cx += arch_rng.uniform(-0.6, 0.6) * side
        for _ in range(int(wide * drop * 30)):
            u = arch_rng.uniform(-1, 1)
            down = drop * (1 - 0.6 * u * u) * arch_rng.uniform(0.5, 1.0) * arch_rng.random() ** 1.3
            lx = cx + u * wide / 2
            # (From the top of the wall just there: never above it, where it's crumbled.)
            top = max((t for a, b, t in arch_tops if a <= lx <= b), default=ARCH_WALL) - 0.05
            lz = top - down
            size = arch_rng.uniform(0.13, 0.2)
            spin = arch_rng.uniform(0, 2 * math.pi)
            # (Clear of the stones standing out, each leaf at its own depth and
            # tipped out towards its tip, the whole of it: two overlapping, at
            # the same depth and flat there, would flicker through each other.)
            y = ARCH_Y + side * (ARCH_THICK + 0.06 + arch_rng.uniform(0, 0.08))
            tip = arch_rng.uniform(0.04, 0.08)
            corners = [(lx + math.cos(spin + a) * size * r, y + side * tip * (1 + math.cos(a)) / 2,
                        lz + math.sin(spin + a) * size * r)
                       for a, r in ((0, 1.0), (math.pi / 2, 0.6), (math.pi, 0.5), (3 * math.pi / 2, 0.6))]
            leaf = c.mix(*IVY, arch_rng.random())
            facing(arch_ivy, corners, [leaf, c.mix(leaf, IVY[0], 0.4), c.mix(leaf, IVY[0], 0.6), leaf], (0, side, 0))
# Its fallen stones, at its foot either side: most under where it's fallen
# in, a few elsewhere; tumbled every which way, half sunk in the ground, and
# mossy. Not on the path, nor in a tree; the big ones solid.
ARCH_TREES = [(7.8, -79.6), (-8.1, -78.5), (-5.6, -75.8), (-15.3, -81.1), (13.7, -78.5), (9.6, -76.6), (-11.2, -84.7)]


def tumbled(cx, cy, size):
    long, wide, tall = size, size * arch_rng.uniform(0.55, 0.8), size * arch_rng.uniform(0.45, 0.65)
    turn = Matrix.Rotation(arch_rng.uniform(0, math.pi), 4, "Z") @ Matrix.Rotation(arch_rng.uniform(-0.45, 0.45), 4, "X") \
        @ Matrix.Rotation(arch_rng.uniform(-0.35, 0.35), 4, "Y")
    centre = Vector((cx, cy, drawn_height(cx, cy, exactly=True) + tall * 0.2))
    corners = [tuple(centre + turn @ Vector((sx * long / 2, sy * wide / 2, sz * tall / 2)))
               for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    colour = c.mix(arch_colour(cx, 3), MOSS, arch_rng.uniform(0.15, 0.45))
    for f in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
        pts = [corners[i] for i in f]
        out_ = sum((Vector(p) for p in pts), Vector()) / 4 - centre
        shade = colour if f != (4, 5, 7, 6) else c.mix(colour, MOSS, 0.2)
        facing(arch, pts, [shade] * 4, tuple(out_))
    if size > 0.35:
        solid_circle(cx, cy, size * 0.45)


fallen_at = []
for mid, wide, deep in ARCH_BREACHES:
    for _ in range(int(wide * deep * 9)):
        side = arch_rng.choice((-1, 1))
        fallen_at.append((mid + arch_rng.uniform(-1.2, 1.2) * wide, ARCH_Y + side * arch_rng.uniform(0.7, 2.6),
                          arch_rng.uniform(0.3, 0.55)))
# (And from the archway's broken corner, beside the path.)
for _ in range(5):
    fallen_at.append((arch_rng.uniform(ARCH_X + ARCH_HALF + 1.0, ARCH_X + ARCH_HALF + 2.6),
                      ARCH_Y + arch_rng.choice((-1, 1)) * arch_rng.uniform(0.7, 2.2), arch_rng.uniform(0.3, 0.5)))
for _ in range(6):
    fallen_at.append((arch_rng.uniform(*ARCH_ENDS), ARCH_Y + arch_rng.choice((-1, 1)) * arch_rng.uniform(0.7, 2.0),
                      arch_rng.uniform(0.25, 0.45)))
placed = []  # (the fallen stones: where, and how big)
for cx, cy, size in fallen_at:
    if abs(cx - ARCH_X) < ARCH_HALF + 0.9 or not ARCH_ENDS[0] < cx < ARCH_ENDS[1]:
        continue  # (off the path through it)
    if any(math.hypot(cx - tx, cy - ty) < 1.2 for tx, ty in ARCH_TREES):
        continue
    if any(math.hypot(cx - px, cy - py) < (size + ps) * 0.6 for px, py, ps in placed):
        continue
    placed.append((cx, cy, size))
    tumbled(cx, cy, size)
arch.build("archway", smooth=False)
arch_ivy.build("archway-ivy", smooth=False)


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


def stone_courses(b, rnd, at, corners, r, z0, z1, holes, foot, course=COURSE, shade=None):
    """The tower's wall in courses of blocks, from z0 to z1 (at: the point on
    the wall's face at an angle; corners: its corners' angles, where a block
    is split to lie flat on it; r: about how far out it is), each block a
    little longer or shorter, the joints never in line with the course's
    below, and none where the wall's open (holes: a0, a1, z0, z1, with
    angles from 0 to 4 pi). (Course: how tall they are, from and to; shade:
    each one's colour, given rnd, how high it is and the foot.)"""

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
        h = min(rnd.uniform(*course), z1 - z)
        start = a = rnd.uniform(0.2, 0.7) / r
        while a < start + 2 * math.pi - 0.3 / r:
            a1 = min(a + rnd.uniform(0.55, 1.15) / r, start + 2 * math.pi)
            colour = shade(rnd, z, foot) if shade else stone_shade(rnd, TOWER_BLOCK, z, foot)
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
LEAVES = (DRAGON_LIP[0] + 3, DRAGON_LIP[1])
LEAF_HEAPS = [(DRAGON_LIP[0] - 1.2, DRAGON_LIP[1] + side * (TUNNEL_HALF + 1.4)) for side in (1, -1)]

# The tunnels' mouths are obstacles on the land, 3 m down the ramp (where the
# leaves are), reaching out over the top so you're stopped (and told why)
# before you go down: the leaves, and the lamp tunnel's two mouths, too dark
# to go in without the lamp.
obstacle(["cave-entrance east"], "box", LEAVES[0], -LEAVES[1], 1.0, TUNNEL_HALF + 0.3)
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
maze_ivy = c.Builder()  # (its own: casting no shadows, so close to the stones the sun's shadows would speckle them)
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
    # (Those along y a hair thinner and shorter, so where two meet, their
    # faces are never in the same plane, fighting: just behind the other's.)
    thick = MAZE_THICK if along_x else MAZE_THICK - 0.004
    lo, hi = a * MAZE_CELL - thick, b * MAZE_CELL + thick
    at = line * MAZE_CELL
    if along_x:
        x0, x1, y0, y1 = mx0 + lo, mx0 + hi, my0 + at - thick, my0 + at + thick
    else:
        x0, x1, y0, y1 = mx0 + at - thick, mx0 + at + thick, my0 + lo, my0 + hi
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
                # (Each leaf at its own depth, and tipped out towards its tip:
                # flat, two overlapping all but in the same plane would flicker.)
                out = MAZE_THICK + 0.02 + maze_rng.uniform(0, 0.06)
                tip = maze_rng.uniform(0.04, 0.08)
                if along_x:
                    cx, cy, d, n = mx0 + lt, my0 + at + out * side, (1, 0), (0, side)
                else:
                    cx, cy, d, n = mx0 + at + out * side, my0 + lt, (0, 1), (side, 0)
                cz = z1 + 0.03 - size - down  # (its tip at the most just over the top)
                corners = []
                for ang, r in ((0, 1.0), (math.pi / 2, 0.6), (math.pi, 0.5), (3 * math.pi / 2, 0.6)):
                    along_, up_ = math.cos(spin + ang) * size * r, math.sin(spin + ang) * size * r
                    lift = tip * (1 + math.cos(ang)) / 2
                    corners.append((cx + d[0] * along_ + n[0] * lift, cy + d[1] * along_ + n[1] * lift, cz + up_))
                leaf = c.mix(*IVY, maze_rng.random())
                facing(maze_ivy, corners, [leaf, c.mix(leaf, IVY[0], 0.4), c.mix(leaf, IVY[0], 0.6), leaf], (*n, 0))
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
maze_ivy.build("maze-ivy", smooth=False)
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
    block(built, x0, cn - 1, 0, x1, cn + 1, 8, MORTAR)
block(built, cw, cs - 1, 0, ce_, cs + 1, 8, MORTAR)
block(built, cw - 1, cs, 0, cw + 1, cn, 8, MORTAR)
block(built, ce_ - 1, cs, 0, ce_ + 1, cn, 8, MORTAR)
for tx, ty in ((cw, cn), (ce_, cn), (cw, cs), (ce_, cs)):
    tower(built, tx, ty, 5, 13, MORTAR, ROOF, 8)
for tx in (-6, 6):
    tower(built, tx, cn, 3, 11, MORTAR, ROOF, 5)
# (Their stonework, and the courtyard in front of the keep, the coach house
# and the well: the courtyard, below.)
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
    block(built, x0, kn - 1, 0, x1, kn, KEEP_TALL, MORTAR, solid=False)
# (Over the door: a shade below the doorway's roof, not level with it,
# where the two would flicker against each other in blocky stripes.)
block(built, GH[0] - door, kn - 1, TUNNEL_TALL + 0.4 - LINTEL_DROP, GH[0] + door, kn, KEEP_TALL, MORTAR, solid=False)
block(built, kw, ks, 0, ke, ks + 1, KEEP_TALL, GREY, solid=False)
# (Its sides between its front and back, and its roof between its walls:
# over them, their faces would be in the same place, and flicker.)
block(built, kw, ks + 1, 0, kw + 1, kn - 1, KEEP_TALL, GREY, solid=False)
block(built, ke - 1, ks + 1, 0, ke, kn - 1, KEEP_TALL, GREY, solid=False)
block(built, kw + 1, ks + 1, KEEP_TALL - 0.4, ke - 1, kn - 1, KEEP_TALL, c.linear("#8d8a80"), solid=False)
x = kw
while x < ke - 1:
    block(built, x, kn - 1, KEEP_TALL, x + 1, kn, KEEP_TALL + 1, c.linear("#c4b598"), solid=False)  # battlements
    x += 2
gx, gy = GH
built.cylinder((gx, gy - 6, KEEP_TALL - 0.5), (gx, gy - 6, 32), 4, 3.6, GREY, sides=14)
built.cone((gx, gy - 6, 32), 16, 4.6, GOLD, sides=12, droop=0)
kitchen = HALLS["wizards-kitchen"]
block(built, kitchen.x - kitchen.w, kitchen.y - 1, KEEP_TALL - 0.5, kitchen.x - kitchen.w + 2, kitchen.y + 1, KEEP_TALL + 4,
      ROCK, solid=False)  # the chimney, over the hearth

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
            quad(built_ways, [(*p0, b0), (*p1, b1), (*p1, max(t1, b1)), (*p0, max(t0, b0))], EARTH)


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
                built_ways.add(verts, [tuple(range(len(verts)))], [c.vary(colour, 0.12, Vector(v)) for v in verts])


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
# (Two lots: dug through rock, which the game draws grainy; and built,
# indoors, or into the halls of worked stone, and what's made in the ways dug
# (their timber props, stonework and posts), and the earth and ground over
# their mouths, outside, which it doesn't.)
dug, built_ways = c.Builder(), c.Builder()
tunnel = dug
SMOOTH_HALLS = ("treasure-room", "beautiful-chamber")
# Each doorway into the treasure room or the beautiful chamber: its room, its
# frame's edges, its floor, and the way into the room.
ARCHES = []
DROPS = []  # (cave, and the two sides of where a way drops away out of it)
# (Each doorway into a cave of rough rock: the cave, the way's two edges
# there, its floor, and how high the cave's wall goes. The cave draws round
# it: its rock curving in to meet the way's mouth.)
CAVE_DOORS = []

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


def swept_by_a_door(x, y):
    """Whether a spot is where one of the locked doors (below) swings, opening:
    south from its line, as far as it's wide, across the way."""
    for place in ("oak-door", "giant"):
        hall = HALLS[place]
        line = hall.y - hall.r - 1.2
        if abs(x - hall.x) < TUNNEL_HALF + 0.5 and line - 2 * TUNNEL_HALF - 0.4 < y < line + 0.4:
            return True
    return False


RING_OUT = 0.6  # metres past the way's square, round it: past the most its rock is pushed out


def ring_out(row, rock, half):
    """For a point of the rock round a way's end: on out from the middle of
    the roof's curve, through it, to a frame round the square opening."""
    x, y, f = row[0], row[1], row[2]
    across = (rock[0] - x) * row[3] + (rock[1] - y) * row[4]
    up = rock[2] - (f + SPRING)
    ts = []
    if abs(across) > 1e-6:
        ts.append((half + RING_OUT) / abs(across))
    if up > 1e-6:
        ts.append((TUNNEL_TALL - SPRING + RING_OUT) / up)
    elif up < -1e-6:
        ts.append((SPRING + RING_OUT) / -up)
    t = max(1.0, min(ts))
    return (x + row[3] * across * t, y + row[4] * across * t, f + SPRING + up * t)


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
    tunnel = built_ways if way.indoor else dug
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
                # (Not across an end at the deep hole's edge: the hole's wall
                # is just there, and the two would flicker.)
                past_a = in_pit(a[0] - (b[0] - a[0]) / 2, a[1] - (b[1] - a[1]) / 2)
                past_b = in_pit(b[0] + (b[0] - a[0]) / 2, b[1] + (b[1] - a[1]) / 2)
                for p0, p1, z0, z1 in (((alx, aly), (blx, bly), a[2], b[2]), ((arx, ary), (brx, bry), a[2], b[2])) + \
                        (((alx, aly), (arx, ary), a[2], a[2]),) * (not past_a) + (((blx, bly), (brx, bry), b[2], b[2]),) * (not past_b):
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
                # (Each piece straight out from the rock, away from the middle
                # of the roof's curve, to a frame round it a little bigger
                # than the rock ever is: pieces side by side never cross, and
                # fold over each other, and flicker. The door frames and
                # lintels in front hide what's past the square opening.)
                beyond = [ring_out(row, p, half) for p in pts_]
                for i in range(len(VAULT) - 1):
                    quad(tunnel, [pts_[i], pts_[i + 1], beyond[i + 1], beyond[i]], rock_colour(*pts_[i]), 0.1)
                # (And in, up its walls, from the rock, pushed out, to the way's
                # own walls going on past it, out under the sky: or there's a
                # slit between them to see out of. Not into a hall: its door
                # frame does that, just where this would go, and they'd flicker.)
                on = k - 1 if row is a else k + 1
                if not (0 <= on < len(rocky_) and drawn(rows[on], rows[on + 1])):
                    continue
                flat = [(*side(row, u * half), p[2]) for (u, _), p in zip(VAULT, pts_)]
                for i in range(len(VAULT) - 1):
                    if abs(VAULT[i][0]) == 1 and VAULT[i + 1][0] == VAULT[i][0]:
                        quad(tunnel, [flat[i], flat[i + 1], pts_[i + 1], pts_[i]], rock_colour(*pts_[i]), 0.1)
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
                    oriented_box(built_ways, post, f - 0.05, f + PROP_TALL, TIMBER)
                lx2, ly2 = side(a, -half - 0.2)
                rx2, ry2 = side(a, half + 0.2)
                beam = [(lx2 - ux * 0.15, ly2 - uy * 0.15), (rx2 - ux * 0.15, ry2 - uy * 0.15),
                        (rx2 + ux * 0.15, ry2 + uy * 0.15), (lx2 + ux * 0.15, ly2 + uy * 0.15)]
                oriented_box(built_ways, beam, f + PROP_TALL, f + PROP_TALL + 0.25, c.mix(TIMBER, c.linear("#000000"), 0.15))
            # Rubble along the foot of the walls.
            if rubble.random() < 0.22:
                sign = rubble.choice((1, -1))
                rx3, ry3 = side(a, sign * (half - 0.08))
                r = rubble.uniform(0.12, 0.28)
                shade, seed = c.mix(LAYERS[2], LAYERS[3], rubble.random()), rubble.random() * 100
                if not swept_by_a_door(rx3, ry3):
                    tunnel.blob((rx3, ry3, a[2] + r * 0.2), r, shade, squash=0.6, lumpy=0.35, seed=seed, subdivisions=1)
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
                    quad(built_ways, [(*p, height(*p) + 0.32) for p in pa + pb], STONE)
                    # Solid down into the ground at its outer edge and its
                    # ends, so there's nothing to see under it.
                    (ia, oa), (ob, ib) = pa, pb
                    for p0, p1 in ((oa, ob),) * (outer == across[-1]) + ((ia, oa), (ib, ob)):
                        quad(built_ways, [(*p0, height(*p0) + 0.32), (*p1, height(*p1) + 0.32), (*p1, height(*p1) - 0.6),
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
                quad(built_ways, [(*l0, r0[2] + TUNNEL_TALL + 0.02), (*q0, r0[2] + TUNNEL_TALL + 0.02),
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
            ox_, oy_ = (outside[0] - row[0]) / run * 0.06, (outside[1] - row[1]) / run * 0.06
            l1, r1 = side(row, -half - 2.4), side(row, half + 2.4)
            l1, r1 = (l1[0] + ox_, l1[1] + oy_), (r1[0] + ox_, r1[1] + oy_)
            low = row[2] + TUNNEL_TALL
            high = max(height(*l1), height(*r1), height(row[0], row[1])) + 0.8
            quad(built_ways, [(*l1, low), (*r1, low), (*r1, high), (*l1, high)], STONE)
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
            framed = built_ways if hall.place in SMOOTH_HALLS else tunnel
            row = rows[i]
            f = row[2]
            nx_, ny_ = row[3], row[4]
            # (In a cave, a shade out into it, off the rock's end.)
            inner = a if i == k + 1 else b
            run = math.hypot(inner[0] - row[0], inner[1] - row[1]) or 1
            hx_, hy_ = ((inner[0] - row[0]) / run * 0.06, (inner[1] - row[1]) / run * 0.06) if not hall.indoor else (0, 0)
            el_, er_ = (edge_left[i][0] + hx_, edge_left[i][1] + hy_), (edge_right[i][0] + hx_, edge_right[i][1] + hy_)
            # (In a cave, as high as its wall goes before the dome.)
            top = f + TUNNEL_TALL + 0.1 if hall.indoor else hall.floor + max(TUNNEL_TALL + 0.8, hall.tall * 0.5)
            if not hall.indoor and hall.place not in SMOOTH_HALLS:
                CAVE_DOORS.append((hall, el_, er_, f, top))
                continue
            if hall.place in SMOOTH_HALLS:
                ARCHES.append((hall.place, el_, er_, f, (inner[0] - row[0]) / run, (inner[1] - row[1]) / run))
            for p, jut in ((er_, 1.8), (el_, -1.8)):
                q = (p[0] + nx_ * jut, p[1] + ny_ * jut)
                quad(framed, [(*p, f - 0.3), (*q, f - 0.3), (*q, top), (*p, top)], hall.wall)
            # (Into a room, the frame can stand a little out from its wall,
            # where the way's walls begin: the sides of the doorway, back
            # from the frame to the wall, so there's no gap to see out of. Not
            # where the way's own walls go on past it: they'd be in the same
            # place, and fight.)
            if hall.room and not drawn(a, b):
                ux, uy = (inner[0] - row[0]) / run, (inner[1] - row[1]) / run
                for p in (el_, er_):
                    ts = [(hall.x + sign * (hall.w + ROOM_EDGE) - p[0]) / ux for sign in (1, -1) if abs(ux) > 1e-6]
                    ts += [(hall.y + sign * (hall.d + ROOM_EDGE) - p[1]) / uy for sign in (1, -1) if abs(uy) > 1e-6]
                    t = min((t for t in ts if t > 0), default=0.0)
                    if 0 < t < 1:
                        q = (p[0] + ux * t, p[1] + uy * t)
                        # (Facing both ways: one side's faces in, the other's out.)
                        quad(framed, [(*p, f - 0.3), (*q, f - 0.3), (*q, top), (*p, top)], hall.wall)
                        quad(framed, [(*p, top), (*q, top), (*q, f - 0.3), (*p, f - 0.3)], hall.wall)
            if not hall.indoor:
                p, q = el_, er_
                quad(framed, [(*p, f + TUNNEL_TALL), (*q, f + TUNNEL_TALL), (*q, top), (*p, top)], hall.wall)
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
            note_post(built_ways, way.clue, px, py, f, (-ox, -oy), TUNNEL_FLOOR)
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
                quad(built_ways, [(x, y, height(x, y) + 0.06) for x, y in pts], STONE, 0.1)
        # Its sides, down into the ground; and its edge over the ramp, down to
        # the ramp's floor: seen from below, there's nothing to look under.
        for i in range(len(steps) - 1):
            for j in (0, len(across) - 1):
                (x0, y0), (x1, y1) = grid[i][j], grid[i + 1][j]
                quad(built_ways, [(x0, y0, height(x0, y0) + 0.06), (x1, y1, height(x1, y1) + 0.06), (x1, y1, height(x1, y1) - 0.6),
                              (x0, y0, height(x0, y0) - 0.6)], STONE, 0.1)
        for j in range(len(across) - 1):
            (x0, y0), (x1, y1) = grid[0][j], grid[0][j + 1]
            quad(built_ways, [(x0, y0, height(x0, y0) + 0.06), (x1, y1, height(x1, y1) + 0.06), (x1, y1, ef - 0.3),
                          (x0, y0, ef - 0.3)], STONE, 0.1)
dug.build("tunnel", smooth=False)
built_ways.build("tunnel-built", smooth=False)

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

# The treasure room, as in its painting: walls of dressed stone and a floor of
# flagstones; columns round it, with gold bands and capitals; and against
# its walls, pillars carved with lions in gold (the painting's own lions).
# Arches over its doorways, gold keystones in them; at its north end, the
# altar up its steps, carved too, and behind it a niche with a gold sunburst
# in it. Gold braziers burning, pedestals, the two chests (open, as in the
# painting: empty), and rubble at the foot of its walls.
TREASURE_STONE = c.linear("#97896f")
TREASURE_FLOOR = c.linear("#8f8370")
TREASURE_MORTAR = c.linear("#3a3026")
GILT = c.linear("#e0a024")
EMBERS = c.linear("#c8300a")
FIRE, FIRE_HEART = c.linear("#ff6a10"), c.linear("#ffc23a")  # (the game adds them to what's behind: they glow)
SEAM = 0.02  # the mortar between stones, either side
gilding = c.Builder()  # (gold: the game makes it shine, as Merlin's treasure does)
brazier_flames = c.Builder()  # (and the braziers' fire glow, and the beautiful chamber's candles')
hoard_jewels = c.Builder()  # (and the jewels in its chests, glassy, as the treasure's are)
# Carvings, from the painting: (left, top, right, bottom) in its pixels.
CARVED = {"lion": (297, 108, 380, 297), "lion facing left": (1166, 108, 1249, 297),
          "griffin": (707, 237, 832, 325)}
painting = bpy.data.images.load(str(HERE.parent / "originals/rooms/treasure-room.png"))
import numpy as np  # noqa: E402

PAINTED_W, PAINTED_H = painting.size
painted = np.empty(PAINTED_W * PAINTED_H * 4, dtype=np.float32)
painting.pixels.foreach_get(painted)
painted = painted.reshape(PAINTED_H, PAINTED_W, 4)[::-1]  # (its top row first)


def painted_at(carving, s, t):
    """A carving's colour (linear), s across it and t up it, 0 to 1: the
    painting's, but its gold less fiery, and lighter (the room's light warms
    it, and it's lit by the painting's own light: darker than the stone)."""
    x0, y0, x1, y1 = CARVED[carving]
    px = painted[int(y0 + (1 - t) * (y1 - y0 - 1)), int(x0 + s * (x1 - x0 - 1)), :3]
    rgb = [p / 12.92 if p <= 0.04045 else ((p + 0.055) / 1.055) ** 2.4 for p in px]
    grey = 0.3 * rgb[0] + 0.6 * rgb[1] + 0.1 * rgb[2]
    return (*(min(1.0, 1.45 * (0.55 * v + 0.45 * grey)) for v in rgb), 1.0)


def face(b, pts, colour, towards, vary=0.06):
    """A flat face, turned towards a direction (a colour, or one for each corner)."""
    a, b_, c_ = (Vector(p) for p in pts[:3])
    colours = colour if isinstance(colour, list) else [c.vary(colour, vary, Vector(pts[0]))] * len(pts)
    if (b_ - a).cross(c_ - a).dot(Vector(towards)) < 0:
        pts, colours = pts[::-1], colours[::-1]
    b.add(list(pts), [tuple(range(len(pts)))], colours)


def facing_out(mx, my, f, lx, ly, ix, iy):
    """Where a point is, given how far along (u), out into the room (d) and
    up (z) from a spot on a wall."""
    return lambda u, d, z: (mx + lx * u + ix * d, my + ly * u + iy * d, f + z)


def dressed(b, at, u0, u1, d0, d1, z0, z1, colour, vary=0.06):
    """A box, along, out from and up a wall (at: facing_out)."""
    corners = [at(u, d, z) for z in (z0, z1) for d in (d0, d1) for u in (u0, u1)]
    middle = Vector(at((u0 + u1) / 2, (d0 + d1) / 2, (z0 + z1) / 2))
    for side in ((0, 1, 3, 2), (4, 5, 7, 6), (0, 1, 5, 4), (2, 3, 7, 6), (0, 2, 6, 4), (1, 3, 7, 5)):
        pts = [corners[i] for i in side]
        face(b, pts, colour, sum((Vector(p) for p in pts), Vector()) / 4 - middle, vary)
    return corners


def footprint(corners):
    """Solid underfoot: round a slab's corners."""
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    under_box((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2)


def carving(at, carved, u0, u1, z0, z1, d, cell=0.035, deep=0.035):
    """A carving from the painting on a face (out at d), in relief: its
    brighter parts (the gold) stand out from it."""
    nu, nz = max(2, round((u1 - u0) / cell)), max(2, round((z1 - z0) / cell))
    colours = [painted_at(carved, i / nu, j / nz) for j in range(nz + 1) for i in range(nu + 1)]
    # (How far it stands out: from how bright it is, blurred, so the
    # painting's brushstrokes don't make it rough.)
    bright = np.array([0.3 * r + 0.6 * g + 0.1 * b for r, g, b, _ in colours]).reshape(nz + 1, nu + 1)
    for _ in range(2):
        padded = np.pad(bright, 1, mode="edge")
        bright = sum(padded[1 + dj:nz + 2 + dj, 1 + di:nu + 2 + di] for dj in (-1, 0, 1) for di in (-1, 0, 1)) / 9
    verts = []
    for j in range(nz + 1):
        for i in range(nu + 1):
            edge = 0.0 if i in (0, nu) or j in (0, nz) else 1.0
            verts.append(at(u0 + (u1 - u0) * i / nu, d + edge * deep * min(1.0, bright[j, i] * 1.6), z0 + (z1 - z0) * j / nz))
    faces = [(j * (nu + 1) + i, j * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i + 1, (j + 1) * (nu + 1) + i)
             for j in range(nz) for i in range(nu)]
    # (Facing out: flipped if along and out from the wall turn the other way.)
    a, b_, c_ = (Vector(at(0, 0, 0)), Vector(at(1, 0, 0)), Vector(at(0, 0, 1)))
    if (b_ - a).cross(c_ - a).dot(Vector(at(0, 1, 0)) - a) < 0:
        faces = [f_[::-1] for f_ in faces]
    cave_made.add(verts, faces, colours)
    gilt_frame(at, u0, u1, z0, z1, d)


def gilt_frame(at, u0, u1, z0, z1, d, wide=0.035):
    """A thin gold frame round something on a face."""
    for a0, a1, b0, b1 in ((u0 - wide, u1 + wide, z0 - wide, z0), (u0 - wide, u1 + wide, z1, z1 + wide),
                           (u0 - wide, u0, z0, z1), (u1, u1 + wide, z0, z1)):
        dressed(gilding, at, a0, a1, d - 0.01, d + 0.03, b0, b1, GILT, 0.04)


def plaque(at, u0, u1, z0, z1, d):
    """A gold frame on a face, and a gold diamond in it."""
    gilt_frame(at, u0, u1, z0, z1, d)
    um, zm, du, dz = (u0 + u1) / 2, (z0 + z1) / 2, (u1 - u0) * 0.3, (z1 - z0) * 0.3
    diamond = [at(um, d + 0.02, zm - dz), at(um + du, d + 0.02, zm), at(um, d + 0.02, zm + dz), at(um - du, d + 0.02, zm)]
    face(gilding, diamond, GILT, Vector(at(0, 1, 0)) - Vector(at(0, 0, 0)), 0.04)


def arch_front(at, a, spring, top, blind=False, stones_=(TREASURE_STONE, GOLD_STONE, TREASURE_MORTAR)):
    """An arch, built out from the wall: round over its opening (a either
    side of its middle, from `spring` up), a ring of stones round it with a
    gold keystone at its crown, pilasters either side, and a cornice over
    it. Blind, a niche: a recess, with a gold sunburst in it. (Its stone, a
    lighter shade of it, and its mortar: the treasure room's, unless it says.)"""
    stone_, lighter_, mortar_ = stones_
    ring, face_d, back = a + 0.6, 0.15, -0.3 if blind else -0.6
    p0, p1 = ring + 0.35, ring + 1.15
    out = Vector(at(0, 1, 0)) - Vector(at(0, 0, 0))
    here = random.Random(f"arch {at(0, 0, 0)}")

    def stone(darker=0.0):
        return c.mix(c.mix(stone_, lighter_, here.uniform(0, 0.3)), mortar_, darker)

    def rim(r, t):
        return r * math.cos(t), spring + r * math.sin(t)

    def to_edge(t):
        """Out from the arch's middle, at t, to the edge of its front (the pilasters, and its top)."""
        dx, dz = math.cos(t), math.sin(t)
        s = min(p0 / abs(dx) if abs(dx) > 1e-6 else 1e9, (top - spring) / dz if dz > 1e-6 else 1e9)
        return s * dx, spring + s * dz

    stones = 11
    corner = math.atan2(top - spring, p0)
    for n in range(stones):
        t0, t1 = math.pi * n / stones, math.pi * (n + 1) / stones
        (iu0, iz0), (iu1, iz1), (ou0, oz0), (ou1, oz1) = rim(a, t0), rim(a, t1), rim(ring, t0), rim(ring, t1)
        if n == stones // 2:
            # The keystone: gold, standing out, and up past the ring, leaning
            # out at its top (lit by the room, not the roof).
            ku, kz = rim(ring + 0.15, (t0 + t1) / 2)
            lean = lambda z: 0.17 if z > (iz0 + kz) / 2 else 0.07  # noqa: E731
            pts = [at(iu0, face_d + 0.07, iz0), at(iu1, face_d + 0.07, iz1), at(ou1, face_d + 0.17, kz),
                   at(ou0, face_d + 0.17, kz)]
            face(gilding, pts, GILT, out, 0.04)
            for (u_, z_), (v_, w_) in (((iu0, iz0), (ou0, kz)), ((iu1, iz1), (ou1, kz)), ((ou0, kz), (ou1, kz))):
                side = [at(u_, face_d, z_), at(v_, face_d, w_), at(v_, face_d + lean(w_), w_), at(u_, face_d + lean(z_), z_)]
                face(gilding, side, GILT, Vector(at((u_ + v_) / 2, face_d, (z_ + w_) / 2)) - Vector(at(0, face_d, spring)), 0.04)
        else:
            face(cave_made, [at(iu0, face_d, iz0), at(iu1, face_d, iz1), at(ou1, face_d, oz1), at(ou0, face_d, oz0)],
                 stone(0.12 * (n % 2)), out)
        # Round from the ring to the front's edge (with its corner, if it's in between).
        edge = [to_edge(t0)] + [to_edge(t) for t in (corner, math.pi - corner) if t0 < t < t1] + [to_edge(t1)]
        face(cave_made, [at(ou1, face_d, oz1), at(ou0, face_d, oz0)] + [at(u_, face_d, z_) for u_, z_ in edge],
             stone(), out)
        # Under the arch, back into the way.
        towards = Vector(at(-math.cos((t0 + t1) / 2), 0, spring - math.sin((t0 + t1) / 2))) - Vector(at(0, 0, spring))
        face(cave_made, [at(iu0, face_d, iz0), at(iu1, face_d, iz1), at(iu1, back, iz1), at(iu0, back, iz0)],
             stone(0.15), towards)
    # Its jambs, in courses, and under the arch, back into the way.
    courses = 3
    for sign in (1, -1):
        for k in range(courses):
            z0, z1 = spring * k / courses, spring * (k + 1) / courses
            face(cave_made, [at(sign * a, face_d, z0), at(sign * p0, face_d, z0), at(sign * p0, face_d, z1),
                             at(sign * a, face_d, z1)], stone(), out)
        face(cave_made, [at(sign * a, face_d, 0), at(sign * a, back, 0), at(sign * a, back, spring),
                         at(sign * a, face_d, spring)], stone(0.15), Vector(at(-sign, 0, 0)) - Vector(at(0, 0, 0)))
        # The pilasters: a base, a gold frame on its face, and a capital.
        footprint(dressed(cave_made, at, sign * p0, sign * p1, -0.6, 0.45, 0, top, stone()))
        dressed(cave_made, at, sign * (p0 - 0.06), sign * (p1 + 0.06), -0.6, 0.51, 0, 0.32, stone(0.1))
        dressed(cave_made, at, sign * (p0 - 0.06), sign * (p1 + 0.06), -0.6, 0.51, top - 0.32, top, stone(0.1))
        lo, hi = sorted((sign * (p0 + 0.16), sign * (p1 - 0.16)))
        gilt_frame(at, lo, hi, 0.65, top - 0.65, 0.46)
    # The cornice, over it all.
    dressed(cave_made, at, -p1 - 0.12, p1 + 0.12, -0.6, 0.6, top, top + 0.3, stone(0.05))
    dressed(gilding, at, -p1 - 0.12, p1 + 0.12, 0.6, 0.63, top + 0.05, top + 0.1, GILT, 0.04)
    if blind:
        # Its recess, dark, and the sunburst in it: rays round a gold sun.
        outline = [(a, 0.0)] + [rim(a, math.pi * k / 24) for k in range(25)] + [(-a, 0.0)]
        face(cave_made, [at(u_, back, z_) for u_, z_ in outline], c.mix(stone_, mortar_, 0.55), out)
        rays = 13
        for k in range(rays):
            t = math.pi * (k + 0.5) / rays
            long = a * (0.92 if k % 2 else 0.7)
            u0_, z0_ = rim(0.3, t - 0.06)
            u1_, z1_ = rim(0.3, t + 0.06)
            ut, zt = rim(long, t)
            face(gilding, [at(u0_, back + 0.02, z0_), at(u1_, back + 0.02, z1_), at(ut, back + 0.02, zt)], GILT, out, 0.04)
        sun = [rim(0.3, math.pi * k / 12) for k in range(13)]
        face(gilding, [at(u_, back + 0.03, z_) for u_, z_ in sun], GILT, out, 0.04)


# The beautiful chamber, as in its painting: gold walls, in arched panels
# carved with the painting's own gold fleurs, between gold columns, candles
# burning in sconces either side of each panel, and over it all a cornice,
# and a dome of paler gold, gold ribs up it. An arch over
# its doorway, and in the middle, on a stepped pedestal, the flute, floating,
# playing (the game makes it bob and turn, and plays its tune).
CHAMBER_GOLD = c.linear("#d9a640")  # (its walls' gold, as the hall's)
CHAMBER_DEEP = c.linear("#b9842c")  # (the gold in the panels, and its plinths and cornice)
CHAMBER_DOME = c.linear("#f2d58e")
CHAMBER_STONES = (CHAMBER_GOLD, c.linear("#ecc066"), c.linear("#5a3c14"))  # (its arch's: as arch_front's)
CANDLE = c.linear("#f3ead6")
SILVER, SILVER_DARK = c.linear("#e4e8ee"), c.linear("#80858e")
FLUTE_LONG, FLUTE_R = 0.94, 0.02  # metres, as it's made: a real one's 67cm, but it's thin
FLUTE_SIZE = 1.25  # (so it's made bigger still, to be easy to see)
flute_model = c.Builder()  # (standing, as it's made: then laid along x)


def sconce(at):
    """A gold sconce on a wall (at: facing_out, from its foot), three candles
    burning in it, the middle one higher."""
    dressed(gilding, at, -0.06, 0.06, 0.0, 0.03, 1.72, 2.12, GILT, 0.04)  # (its back plate)
    dressed(gilding, at, -0.025, 0.025, 0.03, 0.3, 1.87, 1.91, GILT, 0.04)  # (its arm)
    dressed(gilding, at, -0.22, 0.22, 0.27, 0.31, 1.91, 1.95, GILT, 0.04)  # (and the bar across it)
    gilding.blob(at(0, 0.29, 1.93), 0.045, GILT, lumpy=0.0, subdivisions=1)
    for u, z in ((-0.2, 1.95), (0.0, 2.07), (0.2, 1.95)):
        if z > 1.95:
            gilding.cylinder(at(u, 0.29, 1.95), at(u, 0.29, z), 0.018, 0.018, GILT, sides=6)
        gilding.cylinder(at(u, 0.29, z), at(u, 0.29, z + 0.05), 0.035, 0.06, GILT, sides=10)  # (its cup)
        cave_made.cylinder(at(u, 0.29, z + 0.02), at(u, 0.29, z + 0.27), 0.028, 0.026, CANDLE, sides=8)
        x, y, top = at(u, 0.29, z + 0.27)
        brazier_flames.cone((x, y, top + 0.005), 0.17, 0.034, FIRE, sides=7, droop=0, seed=round(x * 10 + y))
        brazier_flames.cone((x, y, top + 0.01), 0.1, 0.02, FIRE_HEART, sides=6, droop=0, seed=1)


def arched(w, z0, spring, wider=0.0):
    """An arched panel's outline (along, up), round from its foot: w either
    side of its middle, its arch springing at `spring` (and, wider, a frame round it)."""
    w += wider
    return [(-w, z0 - wider), (w, z0 - wider)] + [(w * math.cos(math.pi * k / 16), spring + w * math.sin(math.pi * k / 16))
                                                for k in range(17)] + [(-w, z0 - wider)]


def curl(sign, u, z, size, turns=1.25):
    """A leaf curling off a stem at (u, z), to one side (sign): up, out,
    over and round in on itself, size across."""
    pts = []
    for n in range(25):
        t = n / 24
        a = math.pi - turns * 1.4 * math.pi * t
        r = size / 2 * (1 - 0.55 * t * t)
        pts.append((u + sign * (size / 2 + r * math.cos(a)), z + size * 0.25 * t + r * math.sin(a)))
    return pts


def scroll(at, path, wide0, wide1, d=0.05, raised=0.025):
    """Gold scrollwork on a face (out at d): a raised ribbon along a path
    (along, up), wide0 wide where it starts, tapering to wide1."""
    out = Vector(at(0, 1, 0)) - Vector(at(0, 0, 0))
    edges = []
    for n, (u, z) in enumerate(path):
        (u0, z0), (u1, z1) = path[max(n - 1, 0)], path[min(n + 1, len(path) - 1)]
        across = math.hypot(u1 - u0, z1 - z0) or 1
        half = (wide0 + (wide1 - wide0) * n / max(1, len(path) - 1)) / 2
        nu, nz = -(z1 - z0) / across * half, (u1 - u0) / across * half
        edges.append(((u + nu, z + nz), (u - nu, z - nz)))
    for ((a0, b0), (a1, b1)) in zip(edges, edges[1:]):
        face(gilding, [at(a0[0], d + raised, a0[1]), at(a1[0], d + raised, a1[1]), at(b1[0], d + raised, b1[1]),
                       at(b0[0], d + raised, b0[1])], GILT, out, 0.04)
        for p0, p1 in ((a0, a1), (b0, b1)):
            mid = Vector(at((p0[0] + p1[0]) / 2, d, (p0[1] + p1[1]) / 2))
            middle = Vector(at(((a0[0] + b0[0]) / 2 + (a1[0] + b1[0]) / 2) / 2, d, ((a0[1] + b0[1]) / 2 + (a1[1] + b1[1]) / 2) / 2))
            face(gilding, [at(p0[0], d, p0[1]), at(p1[0], d, p1[1]), at(p1[0], d + raised, p1[1]), at(p0[0], d + raised, p0[1])],
                 GILT, mid - middle, 0.04)


def chamber_panel(at, w, z0, spring):
    """An arched panel on the wall, deeper gold, a gold fleur carved in it,
    in a gold frame."""
    out = Vector(at(0, 1, 0)) - Vector(at(0, 0, 0))
    face(cave_made, [at(u, 0.05, z) for u, z in arched(w, z0, spring)[:-1]], CHAMBER_DEEP, out, 0.05)
    # Its gold scrollwork: a stem up the middle, leaves curling off it in
    # pairs, and a fleur-de-lis at its top.
    top = spring + w * 0.55
    scroll(at, [(0.0, z0 + 0.2), (0.0, top - 0.2)], 0.035, 0.035)
    for k, h in enumerate((z0 + 0.25, z0 + 0.7, z0 + 1.15)):
        size = w * (0.62 - 0.1 * k)
        for sign in (1, -1):
            scroll(at, curl(sign, 0.0, h, size), 0.035, 0.015)
    for sign in (1, -1):
        scroll(at, curl(sign, 0.0, top - 0.3, w * 0.2, turns=1.0), 0.03, 0.012)
    petal = [(w * 0.13 * math.sin(math.pi * t / 10), top - 0.25 + 0.5 * t / 10) for t in range(11)]
    scroll(at, petal, 0.03, 0.03)
    scroll(at, [(-u, z) for u, z in petal], 0.03, 0.03)
    inner, outer = arched(w, z0, spring), arched(w, z0, spring, 0.08)
    middle = Vector(at(0, 0, (z0 + spring) / 2))
    for (u0, z0_), (u1, z1_), (v0, y0_), (v1, y1_) in zip(inner, inner[1:], outer, outer[1:]):
        face(gilding, [at(u0, 0.1, z0_), at(u1, 0.1, z1_), at(v1, 0.1, y1_), at(v0, 0.1, y0_)], GILT, out, 0.04)
        face(gilding, [at(u0, 0.0, z0_), at(u1, 0.0, z1_), at(u1, 0.1, z1_), at(u0, 0.1, z0_)], GILT,
             middle - Vector(at((u0 + u1) / 2, 0, (z0_ + z1_) / 2)), 0.04)


# The halls: a floor of squares out under the walls, a lumpy round wall with
# openings where the ways come in, and a dome.
caves = c.Builder()
# (And what's made, in the caves, not rock: built, carved or forged; and the
# halls with smooth walls, of worked stone. The game draws the rock grainy.)
cave_made = c.Builder()
for hall in HALLS.values():
    if hall.indoor:
        continue  # (below)
    random.seed(f"cave {hall.place}")  # (its rocks its own: a change anywhere else doesn't move them)
    hx, hy, f, R = hall.x, hall.y, hall.floor, hall.r
    smooth_wall = hall.place in SMOOTH_HALLS
    rock_of = cave_made if smooth_wall else caves
    step = 1.5
    reach = R + 1.4
    n = int(reach / step) + 1
    drops = [(left, right) for cave, left, right in DROPS if cave is hall]

    def cut(square):
        """A piece of floor, cut off where a way drops away out of the
        doorway, along the way's first row of floor, which goes on down from
        there."""
        x_, y_ = sum(p[0] for p in square) / len(square), sum(p[1] for p in square) / len(square)
        for (lx_, ly_), (rx_, ry_) in drops:
            mx, my = (lx_ + rx_) / 2, (ly_ + ry_) / 2
            across = math.hypot(rx_ - lx_, ry_ - ly_)
            ux, uy = (rx_ - lx_) / across, (ry_ - ly_) / across
            tx, ty = -uy, ux  # out of the cave
            if (hx - mx) * tx + (hy - my) * ty > 0:
                tx, ty = -tx, -ty
            if abs((x_ - mx) * ux + (y_ - my) * uy) < across / 2 + 1.1:
                square = clip(square, mx, my, tx, ty)
        return square

    for i in range(-n, n):
        for j in range(-n, n):
            x0, y0 = hx + i * step, hy + j * step
            nearest_x, nearest_y = max(x0, min(hx, x0 + step)), max(y0, min(hy, y0 + step))
            if math.hypot(nearest_x - hx, nearest_y - hy) > reach:
                continue
            square = cut([(x0, y0), (x0 + step, y0), (x0 + step, y0 + step), (x0, y0 + step)])
            if len(square) < 3:
                continue
            colour, vary = hall.ground, 0.12
            if hall.place == "beautiful-chamber":
                colour, vary = (hall.ground if (i + j) % 2 else c.linear("#1d1a1c")), 0.03
            elif hall.place == "treasure-room":
                colour, vary = TREASURE_MORTAR, 0.05  # (between its flagstones, below)
            elif hall.place == "damp-tunnels" and noise.noise(Vector((x0 / 4, y0 / 4, 9.0))) > 0.15:
                colour = c.linear("#2f3c44")  # puddles
            # (A shade lower than the ways' floors, where they overlap.)
            fl = f - 0.06
            rock_of.add([(x, y, fl) for x, y in square], [tuple(range(len(square)))],
                      [c.vary(colour, vary, Vector((x0, y0, fl)))] * len(square))
    if hall.place == "treasure-room":
        # Its flagstones, in rows of all lengths, a shade over the mortar.
        flags = random.Random("the treasure room's flagstones")
        y0 = hy - reach
        while y0 < hy + reach:
            deep = flags.uniform(1.0, 1.5)
            x0 = hx - reach - flags.uniform(0, 1.2)
            while x0 < hx + reach:
                wide = flags.uniform(0.9, 1.8)
                if math.hypot(x0 + wide / 2 - hx, y0 + deep / 2 - hy) < R + 1.0:
                    flag = cut([(x0 + SEAM, y0 + SEAM), (x0 + wide - SEAM, y0 + SEAM), (x0 + wide - SEAM, y0 + deep - SEAM),
                                (x0 + SEAM, y0 + deep - SEAM)])
                    if len(flag) >= 3:
                        fl = f - 0.045
                        colour = c.mix(TREASURE_FLOOR, GOLD_STONE, flags.uniform(0, 0.35) ** 2 * 2)
                        rock_of.add([(x, y, fl) for x, y in flag], [tuple(range(len(flag)))],
                                    [c.vary(colour, 0.06, Vector((x, y, fl))) for x, y in flag])
                x0 += wide
            y0 += deep

    sides = max(28, int(2 * math.pi * R / (1.1 if smooth_wall else 0.55)))
    wall_top = f + max(TUNNEL_TALL + 0.8, hall.tall * 0.5)
    domes = 6 if smooth_wall else 10

    def bulge(k, level):
        """Its great bulges of rock (as they were, before the cave had as many sides)."""
        if smooth_wall:
            return R + 0.4
        old = max(28, int(2 * math.pi * R / 1.1))
        return R + 0.4 + 0.9 * abs(noise.noise(Vector((k * old / sides / 3, level / 2, hx / 10 + f))))

    def crag(k, z):
        """How far the rock here is pushed out (a hollow) or in (a ridge), metres: craggy, as rock is."""
        if smooth_wall:
            return 0.0
        a = 2 * math.pi * k / sides
        v = Vector((math.cos(a) * R, math.sin(a) * R, z * 1.3)) * 0.55 + Vector((hx, hy, f)) * 0.1
        return 0.55 * noise.noise(v) + 0.25 * noise.noise(v * 2.7) + 0.1 * noise.noise(v * 6.1)

    # Its rings of rock, round it: each, a radius for every side, and a
    # height; up the wall, then curving in over the dome. (Craggy, but never
    # in past where the torches are, against it.)
    # (Each ring: its radius at every side, its height, and how craggy at every side.)
    levels = [0.0] + ([] if smooth_wall else [m / 5 for m in range(1, 5)]) + [1.0]
    rings = []
    for up in levels:
        z = f - 0.3 + (wall_top - f + 0.3) * up
        rough = [crag(k, z) for k in range(sides)]
        rings.append(([max(R + 0.3, bulge(k, 0) * (1 - up) + bulge(k, 1) * up + rough[k]) for k in range(sides)], z, rough))
    for m in range(1, domes + 1):
        t = m / (domes + 1) * math.pi / 2
        z = wall_top + (f + hall.tall - wall_top) * math.sin(t)
        rough = [crag(k, z) * math.cos(t) for k in range(sides)]
        rings.append(([(bulge(k, m + 1) + rough[k]) * math.cos(t) for k in range(sides)], z, rough))
    point = lambda k, ring: (hx + math.cos(2 * math.pi * k / sides) * ring[0][k % sides],  # noqa: E731
                             hy + math.sin(2 * math.pi * k / sides) * ring[0][k % sides], ring[1])

    def wall_at(a, z):
        """How far out the rock is, round at a (radians) and up at z (on its wall, below its dome)."""
        k = round(a / (2 * math.pi) * sides) % sides
        for r0, r1 in zip(rings, rings[1:]):
            if r0[1] <= z <= r1[1]:
                t = (z - r0[1]) / (r1[1] - r0[1])
                return r0[0][k] + (r1[0][k] - r0[0][k]) * t
        return R + 0.4

    def shade(k, ring, darker):
        """The rock's colour here: its hollows darker, its ridges lit."""
        colour = c.mix(hall.wall, c.linear("#000000"), darker)
        if not smooth_wall:
            deep = max(-1.0, min(1.0, ring[2][k % sides] / 0.45))
            colour = c.mix(colour, c.linear("#000000"), 0.55 * deep) if deep > 0 else \
                c.mix(colour, c.linear("#fff0d8"), -0.3 * deep)
        return c.vary(colour, 0.12, Vector(point(k, ring)))

    wall_rings = len(levels)
    for k in range(sides):
        am = 2 * math.pi * (k + 0.5) / sides
        door = opening(hall, hx + math.cos(am) * (R + 0.6), hy + math.sin(am) * (R + 0.6))
        for j, (r0, r1) in enumerate(zip(rings, rings[1:])):
            darker = 0.0 if j < wall_rings - 1 else 0.15
            a0, b0, a1, b1 = point(k, r0), point(k + 1, r0), point(k, r1), point(k + 1, r1)
            if door:
                # (Over the doorway, from clear above the way's rock, which bulges
                # up past its roof: lower, the wall cuts across the inside of the
                # way. The door frame's lintel hides the gap below, from the cave.)
                low = f + TUNNEL_TALL + 0.5
                if r1[1] <= low:
                    continue
                if r0[1] < low:
                    t = (low - r0[1]) / (r1[1] - r0[1])
                    a0 = tuple(p + (q - p) * t for p, q in zip(a0, a1))
                    b0 = tuple(p + (q - p) * t for p, q in zip(b0, b1))
            pts = [a0, b0, b1, a1]
            colours = [shade(k, r0, darker), shade(k + 1, r0, darker), shade(k + 1, r1, darker), shade(k, r1, darker)]
            if hall.place == "treasure-room" and j < wall_rings - 1:
                colours = [TREASURE_MORTAR] * 4  # (between its stones, below)
            if hall.place == "beautiful-chamber" and j >= wall_rings - 1:
                colours = [c.vary(CHAMBER_DOME, 0.05, Vector(q)) for q in pts]
            rock_of.add(pts, [(0, 1, 2, 3)], colours)
        last = rings[-1]
        rock_of.add([point(k, last), point(k + 1, last), (hx, hy, f + hall.tall)], [(0, 1, 2)],
                    [CHAMBER_DOME if hall.place == "beautiful-chamber" else hall.wall] * 3)
    if hall.place == "treasure-room":
        # Its wall in courses of dressed stone, each stone a shade in from
        # the mortar, every other course along by half a stone. (Not over
        # the doorways: their arches are there.)
        courses = random.Random("the treasure room's walls")
        wall_r = rings[0][0][0]

        def on_wall(a, z):
            """A point on the wall, round at a (radians), a shade in from it."""
            k = math.floor(a / (2 * math.pi) * sides)
            t = a / (2 * math.pi) * sides - k
            p, q = point(k, rings[0]), point(k + 1, rings[0])
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            inward = 1 - 0.025 / wall_r
            return hx + (x - hx) * inward, hy + (y - hy) * inward, z

        for row in range(round((wall_top - f) / 0.5)):  # (courses half a metre tall)
            z0, z1 = f + row * 0.5 + SEAM, f + (row + 1) * 0.5 - SEAM
            for k in range(sides):
                k0 = k + 0.5 * (row % 2)
                a0, a1 = 2 * math.pi * k0 / sides + SEAM / wall_r, 2 * math.pi * (k0 + 1) / sides - SEAM / wall_r
                am = (a0 + a1) / 2
                if z0 < f + TUNNEL_TALL + 0.5 and opening(hall, hx + math.cos(am) * (R + 0.6), hy + math.sin(am) * (R + 0.6)):
                    continue
                colour = c.vary(c.mix(TREASURE_STONE, GOLD_STONE, courses.uniform(0, 0.3) ** 2 * 3), 0.05,
                                Vector((am * 10, z0, 0)))
                # (Bent where it's round a corner of the wall.)
                ends = [a0] + ([2 * math.pi * (k + 1) / sides] if row % 2 else []) + [a1]
                for b0_, b1_ in zip(ends, ends[1:]):
                    rock_of.add([on_wall(b0_, z0), on_wall(b1_, z0), on_wall(b1_, z1), on_wall(b0_, z1)], [(0, 1, 2, 3)],
                                [colour] * 4)
        # And a cornice along its top, a gold line along it.
        for k in range(sides):
            p, q = point(k, rings[0]), point(k + 1, rings[0])

            def ledge(pt, by, z):
                inward = 1 - by / wall_r
                return hx + (pt[0] - hx) * inward, hy + (pt[1] - hy) * inward, z

            top_, out_ = wall_top, 0.28
            for (u0_, z0_), (u1_, z1_) in (((0.0, top_ - 0.3), (out_, top_ - 0.3)), ((out_, top_ - 0.3), (out_, top_)),
                                           ((out_, top_), (0.0, top_))):
                face(rock_of, [ledge(p, u0_, z0_), ledge(q, u0_, z0_), ledge(q, u1_, z1_), ledge(p, u1_, z1_)],
                     c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1), (hx - p[0], hy - p[1], 0.5 if z1_ >= top_ else -0.5))
            face(gilding, [ledge(p, out_ + 0.01, top_ - 0.2), ledge(q, out_ + 0.01, top_ - 0.2), ledge(q, out_ + 0.01, top_ - 0.14),
                           ledge(p, out_ + 0.01, top_ - 0.14)], GILT, (hx - p[0], hy - p[1], 0), 0.04)

    # Round each doorway, the rock curving in to meet the way's mouth: from
    # its edges (the way's walls and roof end there) back into the cave's
    # wall, out to each side and up, so it closes round the way, no gap
    # between them to see into. (Just behind the wall, where it meets it.)
    for cave, el_, er_, df, top in CAVE_DOORS:
        if cave is not hall:
            continue
        mx, my = (el_[0] + er_[0]) / 2, (el_[1] + er_[1]) / 2
        half_ = math.hypot(er_[0] - el_[0], er_[1] - el_[1]) / 2
        lx, ly = (er_[0] - el_[0]) / (2 * half_), (er_[1] - el_[1]) / (2 * half_)
        roof = df + TUNNEL_TALL
        SWEEP = 2.2  # metres, out from its mouth, it curves back into the wall
        SHELL = 0.7  # metres the way's rock reaches out round its mouth
        # Its mouth: the way's own arch (VAULT), a little ragged, in (so its
        # lip hangs over the way's rock).
        mouth = []
        for k, (u, h) in enumerate(VAULT):
            u, z = u * half_, df + max(h, -0.3)
            jag = 0.05 + 0.18 * abs(noise.noise(Vector((mx + u, my, z)) * 1.4))
            mouth.append((u - math.copysign(jag, u) if abs(u) > 0.5 * half_ else u, z - (jag if h > SPRING else 0.0)))
        mouth[0], mouth[-1] = (mouth[0][0], df - 0.3), (mouth[-1][0], df - 0.3)
        # (Out from each point of it, square to it: sideways at its foot, up over its top.)
        outward = []
        for k, (u, z) in enumerate(mouth):
            (u0, z0), (u1, z1) = mouth[max(k - 1, 0)], mouth[min(k + 1, len(mouth) - 1)]
            du, dz = u1 - u0, z1 - z0
            n = math.hypot(du, dz) or 1
            outward.append((-1.0, 0.0) if k == 0 else (1.0, 0.0) if k == len(mouth) - 1 else (-dz / n, du / n))
        steps = [0.0, 0.06, 0.14, 0.25, 0.38, 0.52, 0.68, 0.84, 1.0]

        def skirt(u, z, lipless=False):
            px, py = mx + lx * u, my + ly * u
            a = math.atan2(py - hy, px - hx)
            back = wall_at(a, min(z, wall_top)) + 0.08
            wx, wy = hx + math.cos(a) * back, hy + math.sin(a) * back
            out = max(abs(u) - half_, z - roof, 0.0)
            # (Not curving back till it's past the end of the way's own rock, round it.)
            t = c.smooth((out - SHELL) / (SWEEP - SHELL)) ** 0.6
            t = max(t, c.smooth((z - roof - SHELL) / max(top - roof - SHELL, 0.1)))
            # (Lumpy, as the rock is, where it curves; and round the way's
            # mouth, a lip of it jutting out over the way's own rock's end.)
            v = Vector((px, py, z))
            lip = (0.0 if lipless else 0.3) * (1 - c.smooth((out - SHELL) / 1.0)) * (0.7 + 0.6 * abs(noise.noise(v * 1.3)))
            lump = t * (1 - t) * 4 * 0.3 * noise.noise(v * 0.7) - lip
            return (px + (wx - px) * t + math.cos(a) * lump, py + (wy - py) * t + math.sin(a) * lump, z), lump

        def at(k, s_):
            (u, z), (nu, nz) = mouth[k], outward[k]
            return u + nu * s_ * SWEEP, max(df - 0.3, z + nz * s_ * SWEEP)

        for k in range(len(mouth) - 1):
            for j_ in range(len(steps) - 1):
                corners = [skirt(*at(k, steps[j_])), skirt(*at(k + 1, steps[j_])),
                           skirt(*at(k + 1, steps[j_ + 1])), skirt(*at(k, steps[j_ + 1]))]
                pts = [q for q, _ in corners]
                # (Darker in its hollows, as the cave's wall is.)
                caves.add(pts, [(0, 1, 2, 3)], [c.vary(c.mix(hall.wall, c.linear("#000000"), min(0.45, max(0.0, d) * 1.2)),
                                                       0.12, Vector(q)) for q, d in corners])
        # (Under its lip, back to the way's own rock, all round its mouth.)
        for k in range(len(mouth) - 1):
            (u0, z0), (u1, z1) = mouth[k], mouth[k + 1]
            pts = [skirt(u0, z0)[0], skirt(u1, z1)[0], skirt(u1, z1, True)[0], skirt(u0, z0, True)[0]]
            caves.add(pts, [(0, 1, 2, 3)], [c.vary(c.mix(hall.wall, c.linear("#000000"), 0.3), 0.12, Vector(q)) for q in pts])

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

    if hall.place == "beautiful-chamber":
        wall_r = R + 0.4
        doors = [math.atan2((ly_ + ry_) / 2 - hy, (lx_ + rx_) / 2 - hx)
                 for (lx_, ly_), (rx_, ry_), *_ in (arch[1:] for arch in ARCHES if arch[0] == hall.place)]

        def by_door(a, half):
            """Whether something round at a, half wide (metres), is by a doorway (its arch, and a little more)."""
            return any(abs((a - d + math.pi) % (2 * math.pi) - math.pi) * wall_r < half + 3.6 for d in doors)

        def on_wall(a):
            """Along (to the right, looking at it), out from and up the wall, round at a."""
            inward = wall_r * math.cos(math.pi / sides)  # (flat between its corners)
            return facing_out(hx + math.cos(a) * inward, hy + math.sin(a) * inward, f, math.sin(a), -math.cos(a),
                              -math.cos(a), -math.sin(a))

        # Round its foot, a plinth, a gold rail along it; round its top, a
        # cornice, a gold band in it, and a ledge.
        for k in range(sides):
            p, q = point(k, rings[0]), point(k + 1, rings[0])
            am = 2 * math.pi * (k + 0.5) / sides

            def jutting(pt, by, z):
                inward = 1 - by / wall_r
                return hx + (pt[0] - hx) * inward, hy + (pt[1] - hy) * inward, z

            towards = (hx - (p[0] + q[0]) / 2, hy - (p[1] + q[1]) / 2, 0)
            if not opening(hall, hx + math.cos(am) * (R + 0.6), hy + math.sin(am) * (R + 0.6)):
                face(cave_made, [jutting(p, 0.08, f - 0.1), jutting(q, 0.08, f - 0.1), jutting(q, 0.08, f + 0.5), jutting(p, 0.08, f + 0.5)],
                     CHAMBER_DEEP, towards)
                face(cave_made, [jutting(p, 0.0, f + 0.5), jutting(q, 0.0, f + 0.5), jutting(q, 0.08, f + 0.5), jutting(p, 0.08, f + 0.5)],
                     CHAMBER_DEEP, (0, 0, 1))
                face(gilding, [jutting(p, 0.1, f + 0.42), jutting(q, 0.1, f + 0.42), jutting(q, 0.1, f + 0.48), jutting(p, 0.1, f + 0.48)],
                     GILT, towards, 0.04)
            for (u0_, z0_), (u1_, z1_), up in (((0.0, 3.7), (0.14, 3.7), -1), ((0.14, 3.7), (0.14, 3.95), 0),
                                               ((0.14, 3.95), (0.42, 3.95), -1), ((0.42, 3.95), (0.42, 4.1), 0),
                                               ((0.42, 4.1), (0.0, 4.1), 1)):
                face(cave_made, [jutting(p, u0_, f + z0_), jutting(q, u0_, f + z0_), jutting(q, u1_, f + z1_), jutting(p, u1_, f + z1_)],
                     CHAMBER_DEEP, (towards[0], towards[1], up * 3))
            face(gilding, [jutting(p, 0.15, f + 3.78), jutting(q, 0.15, f + 3.78), jutting(q, 0.15, f + 3.86), jutting(p, 0.15, f + 3.86)],
                 GILT, towards, 0.04)
        # Gold columns against the wall: a plinth, a base, a shaft, a capital
        # with its leaves, and a block on it, under the cornice.
        columns = 14
        for k in range(columns):
            a = 2 * math.pi * (k + 0.5) / columns
            if by_door(a, -2.6):
                continue
            on = on_wall(a)
            x, y, _ = on(0, 0.45, 0)
            footprint(dressed(cave_made, on, -0.45, 0.45, 0.0, 0.9, 0, 0.5, CHAMBER_DEEP))
            gilding.cylinder((x, y, f + 0.5), (x, y, f + 0.58), 0.4, 0.38, GILT, sides=16)
            gilding.cylinder((x, y, f + 0.58), (x, y, f + 0.66), 0.36, 0.31, GILT, sides=16)
            gilding.cylinder((x, y, f + 0.66), (x, y, f + 3.2), 0.3, 0.27, GILT, sides=16)
            gilding.cylinder((x, y, f + 3.2), (x, y, f + 3.5), 0.28, 0.46, GILT, sides=16)
            for n in range(8):
                t = 2 * math.pi * n / 8
                gilding.blob((x + math.cos(t) * 0.3, y + math.sin(t) * 0.3, f + 3.3), 0.09, GILT, squash=1.6, lumpy=0.2,
                             seed=n, subdivisions=1)
            dressed(gilding, on, -0.48, 0.48, -0.03, 0.93, 3.5, 3.7, GILT, 0.04)
        # Between them, panels, a sconce either side of each.
        for k in range(columns):
            a = 2 * math.pi * k / columns
            if not by_door(a, 1.0):
                chamber_panel(on_wall(a), 0.9, 0.85, 2.6)
            for u in (-1.65, 1.65):
                if not by_door(a + u / wall_r, 0.3):
                    sconce(on_wall(a + u / wall_r))
        # The arch over its doorway.
        for (lx_, ly_), (rx_, ry_), df, ix, iy in (arch[1:] for arch in ARCHES if arch[0] == hall.place):
            half_ = math.hypot(rx_ - lx_, ry_ - ly_) / 2
            on = facing_out((lx_ + rx_) / 2, (ly_ + ry_) / 2, df, (rx_ - lx_) / (2 * half_), (ry_ - ly_) / (2 * half_), ix, iy)
            arch_front(on, half_ - 0.2, 1.65, 3.7, stones_=CHAMBER_STONES)
        # Gold ribs up the dome, over the columns, to a gold ring round its
        # top, and a gold boss in it.
        dome = rings[wall_rings - 1:]
        for k in range(columns):
            a = 2 * math.pi * (k + 0.5) / columns
            for r0, r1 in zip(dome, dome[1:]):
                (ra, za), (rb, zb) = (r0[0][0] - 0.04, r0[1] - 0.03), (r1[0][0] - 0.04, r1[1] - 0.03)
                da, db = 0.16 / ra, 0.16 / rb
                pts = [(hx + math.cos(a + s_ * d_) * r_, hy + math.sin(a + s_ * d_) * r_, z_)
                       for s_, d_, r_, z_ in ((-1, da, ra, za), (1, da, ra, za), (1, db, rb, zb), (-1, db, rb, zb))]
                face(gilding, pts, GILT, (hx - pts[0][0], hy - pts[0][1], f + 1 - za), 0.04)
        top_r, top_z = dome[-1][0][0] - 0.04, dome[-1][1] - 0.03
        ring_ = [(hx + math.cos(2 * math.pi * n / 28) * top_r, hy + math.sin(2 * math.pi * n / 28) * top_r) for n in range(29)]
        for (x0_, y0_), (x1_, y1_) in zip(ring_, ring_[1:]):
            face(gilding, [(x0_, y0_, top_z), (x1_, y1_, top_z), (hx + (x1_ - hx) * 0.85, hy + (y1_ - hy) * 0.85, top_z - 0.08),
                           (hx + (x0_ - hx) * 0.85, hy + (y0_ - hy) * 0.85, top_z - 0.08)], GILT, (0, 0, -1), 0.04)
        gilding.blob((hx, hy, f + hall.tall - 0.1), 0.5, GILT, squash=0.6, lumpy=0.15, subdivisions=2)
        # In the middle, the pedestal: a step of white marble, one of black,
        # then a gold-banded drum of white, a gold dish on it; and over it,
        # the flute, floating.
        for r_, z0_, z1_, colour in ((1.3, -0.05, 0.15, hall.ground), (0.95, 0.15, 0.3, c.linear("#1d1a1c"))):
            cave_made.cylinder((hx, hy, f + z0_), (hx, hy, f + z1_), r_, r_, colour, sides=32)
            cave_made.add([(hx + math.cos(2 * math.pi * n / 32) * r_, hy + math.sin(2 * math.pi * n / 32) * r_, f + z1_)
                           for n in range(32)], [tuple(range(32))], [c.vary(colour, 0.03, Vector((n, z1_, 0))) for n in range(32)])
        gilding.cylinder((hx, hy, f + 0.29), (hx, hy, f + 0.31), 0.97, 0.97, GILT, sides=28)
        gilding.cylinder((hx, hy, f + 0.3), (hx, hy, f + 0.42), 0.55, 0.48, GILT, sides=20)
        cave_made.cylinder((hx, hy, f + 0.42), (hx, hy, f + 0.92), 0.42, 0.38, hall.ground, sides=20)
        gilding.cylinder((hx, hy, f + 0.6), (hx, hy, f + 0.64), 0.415, 0.41, GILT, sides=20)
        gilding.cylinder((hx, hy, f + 0.92), (hx, hy, f + 1.04), 0.4, 0.55, GILT, sides=20)
        gilding.add([(hx + math.cos(2 * math.pi * n / 20) * 0.55, hy + math.sin(2 * math.pi * n / 20) * 0.55, f + 1.04)
                     for n in range(20)], [tuple(range(20))], [GILT] * 20)
        under_circle(hx, hy, 1.3)
        # The flute: a silver tube, its crown at its head, the hole to blow
        # across, its joints, and its keys along it on
        # their rod. (Made standing, its head at the top, its keys towards
        # -x: then laid down, keys up.)
        half = FLUTE_LONG / 2
        flute_model.cylinder((0, 0, -half), (0, 0, half), FLUTE_R, FLUTE_R, SILVER, sides=14)
        for z0_, z1_, r_ in ((half, half + 0.035, FLUTE_R * 1.2), (-half - 0.01, -half, FLUTE_R * 1.15),
                             (half - 0.25, half - 0.22, FLUTE_R * 1.2), (-half + 0.13, -half + 0.16, FLUTE_R * 1.2)):
            flute_model.cylinder((0, 0, z0_), (0, 0, z1_), r_, r_, SILVER, sides=14)
            for z_ in (z0_, z1_):
                ends_ = [(math.cos(2 * math.pi * n / 14) * r_, math.sin(2 * math.pi * n / 14) * r_, z_) for n in range(14)]
                flute_model.add(ends_ if z_ == z1_ else ends_[::-1], [tuple(range(14))], [SILVER] * 14)
        flute_model.blob((0, 0, half + 0.04), FLUTE_R * 1.1, SILVER, squash=0.6, lumpy=0.0, subdivisions=1)
        flute_model.blob((-FLUTE_R * 0.85, 0, half - 0.12), 0.0085, c.linear("#1a1a1e"), squash=1.3, lumpy=0.0, subdivisions=1)
        for n in range(12):
            z_ = half - 0.3 - n * 0.048 - (0.02 if n > 5 else 0.0)
            flute_model.blob((-FLUTE_R + 0.004, 0, z_), 0.015, SILVER if n % 3 else SILVER_DARK, lumpy=0.0, subdivisions=1)
        flute_model.cylinder((-FLUTE_R * 0.7, FLUTE_R * 0.9, -half + 0.05), (-FLUTE_R * 0.7, FLUTE_R * 0.9, half - 0.27),
                             0.004, 0.004, SILVER_DARK, sides=5)
        flute_model.verts = [(z * FLUTE_SIZE, y * FLUTE_SIZE, -x * FLUTE_SIZE)
                             for x, y, z in flute_model.verts]  # (laid along x, its keys up)
    if hall.place == "treasure-room":
        luck = random.Random("the treasure room")
        wall_r = R + 0.4
        # Columns round the room: a square plinth, a round shaft between gold
        # bands, a gold capital, and over it, square, into the roof.
        for k in range(8):
            a = 2 * math.pi * (k + 0.5) / 8
            x, y = hx + math.cos(a) * (R - 2.2), hy + math.sin(a) * (R - 2.2)
            if opening(hall, x, y):
                continue
            on = facing_out(x, y, f, 1, 0, 0, 1)
            dressed(cave_made, on, -0.62, 0.62, -0.62, 0.62, 0, 0.35, TREASURE_STONE)
            gilding.cylinder((x, y, f + 0.35), (x, y, f + 0.5), 0.56, 0.47, GILT, sides=16)
            cave_made.cylinder((x, y, f + 0.5), (x, y, f + 5.3), 0.45, 0.4, TREASURE_STONE, sides=16)
            for z in (1.4, 4.3):
                gilding.cylinder((x, y, f + z), (x, y, f + z + 0.1), 0.455, 0.45, GILT, sides=16)
            gilding.cylinder((x, y, f + 5.3), (x, y, f + 5.6), 0.41, 0.6, GILT, sides=16)
            dressed(cave_made, on, -0.66, 0.66, -0.66, 0.66, 5.6, ceiling(x, y) + 0.3 - f, TREASURE_STONE)
            under_circle(x, y, 0.62)
        # Against the wall, between the doorways, pillars carved with lions,
        # turned in to face the room.
        for degrees, lion in ((50, "lion facing left"), (130, "lion"), (230, "lion facing left"), (310, "lion")):
            a = math.radians(degrees)
            front = wall_r - 0.85
            on = facing_out(hx + math.cos(a) * front, hy + math.sin(a) * front, f,
                            math.sin(a), -math.cos(a), -math.cos(a), -math.sin(a))
            footprint(dressed(cave_made, on, -0.7, 0.7, -1.3, 0, 0, 4.4, TREASURE_STONE))
            dressed(cave_made, on, -0.8, 0.8, -1.3, 0.1, 0, 0.45, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
            dressed(cave_made, on, -0.8, 0.8, -1.3, 0.12, 4.4, 4.8, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
            dressed(gilding, on, -0.8, 0.8, 0.12, 0.15, 4.5, 4.6, GILT, 0.04)
            carving(on, lion, -0.47, 0.47, 0.95, 3.1, 0.005)
        # Arches over the doorways.
        for (lx_, ly_), (rx_, ry_), df, ix, iy in (arch[1:] for arch in ARCHES if arch[0] == hall.place):
            half_ = math.hypot(rx_ - lx_, ry_ - ly_) / 2
            on = facing_out((lx_ + rx_) / 2, (ly_ + ry_) / 2, df, (rx_ - lx_) / (2 * half_), (ry_ - ly_) / (2 * half_), ix, iy)
            arch_front(on, half_ - 0.2, 1.65, 4.05)
        # The altar, at the north end: up its steps, carved, and behind it, a
        # niche with a gold sunburst.
        niche = facing_out(hx, hy + R - 0.5, f, 1, 0, 0, -1)
        arch_front(niche, 1.4, 2.5, 4.6, blind=True)
        for hw, y0, z in ((1.95, 3.8, 0.2), (1.6, 4.3, 0.4), (1.25, 4.8, 0.6)):
            on = facing_out(hx, hy, f, 1, 0, 0, -1)
            dressed(cave_made, on, -hw, hw, -8.2, -y0, 0, z, c.mix(TREASURE_STONE, c.linear("#ffffff"), 0.06))
        under_box(hx, hy + 6.0, 1.95, 2.2)
        altar = facing_out(hx, hy + 5.35, f, 1, 0, 0, -1)
        dressed(cave_made, altar, -1.05, 1.05, -1.55, 0.15, 0.6, 0.8, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
        dressed(cave_made, altar, -0.9, 0.9, -1.4, 0, 0.8, 1.75, TREASURE_STONE)
        dressed(cave_made, altar, -1.05, 1.05, -1.55, 0.15, 1.75, 1.95, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
        dressed(gilding, altar, -1.06, 1.06, -1.56, 0.16, 1.8, 1.86, GILT, 0.04)
        carving(altar, "griffin", -0.62, 0.62, 0.85, 1.7, 0.005)
        for sign in (1, -1):
            flank = facing_out(hx + sign * 0.9, hy + 6.05, f, 0, sign, sign, 0)
            plaque(flank, -0.42, 0.42, 0.95, 1.6, 0.005)
        # Gold braziers burning: a foot, a stem with a knop on it, and a
        # bowl of embers, its fire flickering up out of it.
        for x, y in ((hx - 1.45, hy + 3.05), (hx + 1.45, hy + 3.05), (hx - 4.0, hy + 5.9), (hx + 4.0, hy + 5.9)):
            gilding.cylinder((x, y, f), (x, y, f + 0.12), 0.36, 0.3, GILT, sides=12)
            gilding.cylinder((x, y, f + 0.12), (x, y, f + 0.9), 0.08, 0.06, GILT, sides=8)
            gilding.blob((x, y, f + 0.5), 0.12, GILT, squash=0.8, lumpy=0.0, subdivisions=1)
            gilding.cylinder((x, y, f + 0.88), (x, y, f + 1.15), 0.1, 0.42, GILT, sides=14)
            gilding.cylinder((x, y, f + 1.15), (x, y, f + 1.2), 0.43, 0.44, GILT, sides=14)
            brazier_flames.blob((x, y, f + 1.1), 0.4, EMBERS, squash=0.18, lumpy=0.1, seed=round(x), lit=False)
            for k, (size, tall, colour) in enumerate(((0.24, 0.75, FIRE), (0.13, 0.5, FIRE_HEART))):
                brazier_flames.cone((x, y, f + 1.12), tall, size, colour, sides=11, droop=0, seed=k)
            for k in range(4):
                t = 2 * math.pi * (k + luck.random()) / 4
                brazier_flames.cone((x + math.cos(t) * 0.18, y + math.sin(t) * 0.18, f + 1.12), luck.uniform(0.3, 0.5), 0.08,
                                    FIRE, sides=5, droop=0, seed=k)
            under_circle(x, y, 0.42)
        # Pedestals, a gold diamond on each side.
        for x, y in ((hx - 4.4, hy - 4.4), (hx + 4.4, hy - 4.4)):
            on = facing_out(x, y, f, 1, 0, 0, 1)
            dressed(cave_made, on, -0.5, 0.5, -0.5, 0.5, 0, 0.22, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
            dressed(cave_made, on, -0.4, 0.4, -0.4, 0.4, 0.22, 1.15, TREASURE_STONE)
            dressed(cave_made, on, -0.52, 0.52, -0.52, 0.52, 1.15, 1.32, c.mix(TREASURE_STONE, TREASURE_MORTAR, 0.1))
            for ux, uy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                flank = facing_out(x + ux * 0.4, y + uy * 0.4, f, -uy, ux, ux, uy)
                plaque(flank, -0.26, 0.26, 0.35, 1.02, 0.005)
            under_box(x, y, 0.5, 0.5)
        # The chests, open, by the altar, turned to the room: full to their
        # rims with coins, heaps of them, and rubies and emeralds among them
        # (a goblet in one).
        (cx0, cy0, cx1, cy1), _ = PROPS.put(c.Builder(), "Chest_Wood", (0, 0, 0), 0, 1.3)  # (its size, as it's made)
        for n, (x, y) in enumerate(((hx - 3.9, hy + 2.4), (hx + 3.9, hy + 2.4))):
            yaw = math.atan2(hx - x, y - hy)
            (x0, y0, x1, y1), _ = PROPS.put(cave_made, "Chest_Wood", (x, y, f - 0.045), yaw, 1.3)
            under_box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2)
            inside = c.Kit.placing((x, y, f + 0.46), yaw)

            def anywhere(margin):
                """Somewhere inside it, its middle (from above), and how high."""
                u = luck.uniform(cx0 + 0.14 + margin, cx1 - 0.14 - margin)
                v = luck.uniform(cy0 + 0.12 + margin, cy1 - 0.12 - margin)
                return inside((u, v, luck.uniform(0, 0.04)))

            for spot, model in (((-0.22, 0.0), "Coin_Pile_2"), ((0.2, 0.03), "Coin_Pile"), ((0.0, -0.02), "Coin_Pile")):
                PROPS.put(gilding, model, inside((*spot, -0.06)), luck.uniform(0, 2 * math.pi), 2.2, tint=GOLD)
            for k in range(36):
                PROPS.put(gilding, "Coin", anywhere(0.0), luck.uniform(0, 2 * math.pi), 2.2, tint=GOLD)
            if n == 1:
                PROPS.put(gilding, "Chalice", inside((0.15, 0.0, 0.0)), 0.8, 2.2, tint=GOLD)
            for k in range(6):
                size = luck.uniform(0.07, 0.1)
                sx, sy, sz = anywhere(0.05)
                hoard_jewels.blob((sx, sy, sz + size * 0.5), size, JEWELS["ruby" if k % 2 else "emerald"],
                                  squash=0.75, lumpy=0.0, seed=k + 10 * n, subdivisions=0)
        # Rubble, fallen at the foot of the walls.
        for degrees in (30, 150, 205, 335):
            for k in range(5):
                a = math.radians(degrees + luck.uniform(-5, 5))
                r = wall_r - luck.uniform(0.3, 0.9)
                size = luck.uniform(0.12, 0.32)
                x, y = hx + math.cos(a) * r, hy + math.sin(a) * r
                caves.blob((x, y, f - size * 0.3), size, c.mix(TREASURE_STONE, ROCK, 0.5), squash=0.7, lumpy=0.2,
                           seed=k + degrees)
                if size > 0.2:
                    under_circle(x, y, size)
    elif hall.place != "beautiful-chamber":
        # Stalagmites round the edge, stalactites overhead.
        rock = c.mix(hall.wall, ROCK, 0.4)
        for _ in range(int(R * 1.6)):
            spot = free_spot(R - random.uniform(0.6, 2.4))
            if spot and hall.place == "dragon-cave" and any(math.hypot(spot[0] - x, spot[1] - y) < r + 1.3
                                                            for x, y, r in dragon_shape()):
                continue
            if spot:
                x, y, _ = spot
                r, tall = random.uniform(0.35, 0.7), random.uniform(1.0, 2.8)
                # (Clear of the trolls: drawn all the same, so the caves after this one come out as they did.)
                if hall.place == "trolls" and any(math.hypot(x - tx, y - ty) < TROLL_BODY * size + 1.5
                                                  for (tx, ty), _, size in troll_spots()):
                    continue
                # (And of the giant.)
                if hall.place == "giant" and math.dist((x, y), giant_spot()[0]) < GIANT_BODY * GIANT_SIZE + 1.5:
                    continue
                spike(caves, x, y, f - 0.1, tall, r, rock)
                under_circle(x, y, r * 0.8)
        for _ in range(int(R * 2)):
            a, rho = random.uniform(0, 2 * math.pi), random.uniform(1.5, R - 0.5)
            x, y = hx + math.cos(a) * rho, hy + math.sin(a) * rho
            if hall.place == "dragon-cave" and math.hypot(x - DRAGON_AT[0], y - DRAGON_AT[1]) < DRAGON_CLEAR:
                continue
            long, r = random.uniform(0.6, min(2.0, hall.tall - 3.4)), random.uniform(0.2, 0.45)
            # (None over the trolls, who stand up to dance: drawn all the same, as the stalagmites are.)
            if hall.place == "trolls" and any(math.hypot(x - tx, y - ty) < TROLL_BODY * size + 1.2
                                              for (tx, ty), _, size in troll_spots()):
                continue
            if hall.place == "giant" and math.dist((x, y), giant_spot()[0]) < GIANT_BODY * GIANT_SIZE + 1.5:
                continue
            spike(caves, x, y, ceiling(x, y) + 0.3, -long, r, rock)
    if hall.place == "trolls":
        # The trolls' seats: a boulder behind each, its top as high as they
        # sit; and the drum's on the floor (the game puts it there).
        for (x, y), (fx, fy), size in troll_spots():
            r = 0.42 * size
            sx, sy = x - fx * TROLL_SEAT[1] * size, y - fy * TROLL_SEAT[1] * size
            caves.blob((sx, sy, f + TROLL_SEAT[0] * size - r * 0.85), r, c.mix(hall.wall, ROCK, 0.5), squash=0.85,
                       lumpy=0.1, seed=round(x))
            under_circle(x, y, TROLL_BODY * size)
    if hall.place == "giant":
        # The giant's seat: a boulder, its top as high as he sits.
        (x, y), (fx, fy) = giant_spot()
        r = 0.42 * GIANT_SIZE
        sx, sy = x - fx * GIANT_ROCK[1] * GIANT_SIZE, y - fy * GIANT_ROCK[1] * GIANT_SIZE
        caves.blob((sx, sy, f + GIANT_ROCK[0] * GIANT_SIZE - r * 0.85), r, c.mix(hall.wall, ROCK, 0.5), squash=0.85,
                   lumpy=0.1, seed=3)
        under_circle(x, y, GIANT_BODY * GIANT_SIZE)
    if hall.light == TORCH:
        # Torches on the walls.
        for _ in range(4 if R < 10 else 6):
            spot = free_spot(R + 0.25)
            if spot:
                # (Against the rock, however far in or out it is there.)
                _, _, a = spot
                back = min(wall_at(a, f + 1.9), wall_at(a, f + 2.5)) - 0.12
                x, y = hx + math.cos(a) * back, hy + math.sin(a) * back
                block(cave_made, x - 0.08, y - 0.08, f + 1.9, x + 0.08, y + 0.08, f + 2.5, IRON, solid=False)
                cave_made.cone((x, y, f + 2.5), 0.5, 0.16, FLAME, sides=6, droop=0)

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
    if hall.place == "coach-house":
        # Flagstones, under drifts of straw.
        straw = smooth((noise.noise(Vector((x / 3, y / 3, 12.0))) + 0.35) / 0.5)
        return c.mix(c.linear("#8f7f66"), c.linear("#bf9f55"), straw), 0.05
    if hall.place == "small-room":
        plank = c.mix(hall.ground, DARK_WOOD, 0.3 if i % 2 else 0.0)  # boards, running north and south
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
            pts = [(x0, y0, fl), (x1, y0, fl), (x1, y1, fl), (x0, y1, fl)]
            if hall.place == "coach-house":  # (its straw and flags blending, corner to corner)
                b.add(pts, [(0, 1, 2, 3)], [floor_colour(hall, i, j, x, y)[0] for x, y, _ in pts])
                continue
            quad(b, pts, colour, vary)
    if hall.place == "coach-house":
        return coach_house(b, hall)  # (a barn's walls, and open up to its roof: the courtyard, below)
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

# ---------------------------------------------------------------- the courtyard and the coach house

# The castle's courtyard, as in its picture: sunny, cobbled in warm stone,
# with the well in the middle under its little roof, roses round its foot;
# rambling pink roses up the walls and the towers, and in beds along their
# feet, behind low kerbs; a rose garden in its west half, a pergola of roses
# over a walk between beds; the keep's front, with its windows (their
# shutters open), lanterns by its door and banners; and in the east, the
# coach house: a timber barn on a stone footing under a tiled roof, its
# great doors open, a cart and barrels outside it. Inside, the red coach on
# the straw, hay, tack on the wall, and Merlin's cloak (as in its picture).
# Some of it is Quaternius's, from the Medieval Village MegaKit
# (art/models/medieval-village-megakit: the roofs, the windows and their
# shutters, the cart) and the Fantasy Props MegaKit (the lanterns, barrels,
# crates, the bucket, the benches, the banners).
VILLAGE = c.Kit(HERE.parent / "models/medieval-village-megakit/glTF")
court = c.Builder()
window_glass = c.Builder()  # (its windows' glass: the game draws it see-through, shining)
court_rng = random.Random("courtyard")  # (its own: a change anywhere else doesn't move what's here)
YARD = (CASTLE[0] + 1, CASTLE[1] - 1, KEEP_NORTH, CASTLE[3] - 1)  # its walls' faces: west, east, south, north
YARD_FLOOR = height(0, (YARD[2] + YARD[3]) / 2)  # (the castle stands on flat ground)
WELL = (0.0, (YARD[2] + YARD[3]) / 2)
CASTLE_STONE = [c.linear(h) for h in ("#cdbf9f", "#c0ae8b", "#d8cbae", "#b6a586", "#c8b595", "#bfb39b")]
COBBLES = [c.linear(h) for h in ("#cbb68e", "#bca57d", "#d9c7a0", "#b09a74", "#c5aa82", "#d2bc92")]
ROSES = [c.linear(h) for h in ("#f27aa6", "#f7a1c2", "#e9578f", "#ffc8dc", "#dc4a80")]
ROSE_HEART = c.linear("#a8204f")
ROSE_LEAVES = [c.linear(h) for h in ("#2c5a22", "#3a6c2a", "#477d31", "#25491c", "#56893a")]
ROSE_CANE = c.linear("#4d5a2a")
SOIL = c.linear("#4a3424")
BOARDS = [c.linear(h) for h in ("#7a5232", "#6e4a2c", "#86603a", "#73502f", "#68452a")]


def castle_stone(rnd, z, foot):
    """A block of the castle's stone: warm, each its own shade, damp and now
    and then mossy near the ground."""
    colour = rnd.choice(CASTLE_STONE)
    t = rnd.uniform(-0.12, 0.2)
    colour = c.mix(colour, c.linear("#000000"), t) if t > 0 else c.mix(colour, c.linear("#ffffff"), -t)
    low = max(0.0, 1 - (z - foot) / 1.2)
    if rnd.random() < low * 0.6:
        colour = c.mix(colour, TOWER_DAMP, rnd.uniform(0.15, 0.4))
    if rnd.random() < low * 0.25:
        colour = c.mix(colour, TOWER_MOSS, rnd.uniform(0.2, 0.45))
    return colour


def clear_of(rect, holes):
    """The parts of a block (t0, t1, z0, z1) clear of the openings (the same)."""
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


def courses(b, rnd, p0, p1, z0, z1, holes=(), big=1.0, foot=None):
    """A straight wall's face, from p0 to p1 (facing out to the right, looking
    along it), in courses of blocks from z0 to z1, just in front of it (the
    wall behind is the mortar between them): each a little longer or
    shorter, the joints never in line with the course's below. Holes: (t0,
    t1, z0, z1), along it from p0, where it's open."""
    (ax, ay), (bx, by) = p0, p1
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    ox, oy = uy * 0.02, -ux * 0.02

    def at(t, z):
        return ax + ux * t + ox, ay + uy * t + oy, z

    z = z0
    while z < z1 - 0.05:
        h = min(rnd.uniform(0.42, 0.58) * big, z1 - z)
        t = -rnd.uniform(0.0, 0.9) * big
        while t < length:
            t1 = t + rnd.uniform(0.75, 1.45) * big
            colour = castle_stone(rnd, z, z0 if foot is None else foot)
            for a, e, lo, hi in clear_of((max(t, 0) + JOINT / 2, min(t1, length) - JOINT / 2, z + JOINT / 2,
                                          z + h - JOINT / 2), holes):
                if e - a > 0.04 and hi - lo > 0.04:
                    b.add([at(a, lo), at(e, lo), at(e, hi), at(a, hi)], [(0, 1, 2, 3)],
                          [c.vary(colour, 0.05, Vector((a, lo, z0)))] * 4)
            t = t1
        z += h


def round_courses(b, rnd, x, y, r, sides, z0, z1):
    """A round tower's wall in courses of blocks, as the tower's (stone_courses)."""

    def at(a):
        side = math.floor(a / (2 * math.pi / sides))
        middle = (side + 0.5) * 2 * math.pi / sides
        d = (r + 0.02) * math.cos(math.pi / sides) / math.cos(a - middle)
        return x + math.cos(a) * d, y + math.sin(a) * d

    stone_courses(b, rnd, at, [2 * math.pi * k / sides for k in range(2 * sides + 1)], r, z0, z1, [], z0,
                  course=(0.44, 0.6), shade=castle_stone)


def oriented(b, at, across, x0, x1, y0, y1, z0, z1, colour, vary=0.1):
    """A box in a frame of its own: from `at`, x along `across` (level), y
    out to its left, z up."""
    ax, ay = across
    ox, oy = -ay, ax

    def p(x, y, z):
        return at[0] + ax * x + ox * y, at[1] + ay * x + oy * y, at[2] + z

    v = [p(x0, y0, z0), p(x1, y0, z0), p(x1, y1, z0), p(x0, y1, z0), p(x0, y0, z1), p(x1, y0, z1), p(x1, y1, z1),
         p(x0, y1, z1)]
    b.add(v, [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7), (0, 3, 2, 1)],
          [c.vary(colour, vary, Vector(q) * 2) for q in v])


def timber(b, p0, p1, w, colour, h=None):
    """A squared timber from one end to the other, w wide (and h deep), any way up."""
    p0, p1 = Vector(p0), Vector(p1)
    along = (p1 - p0).normalized()
    side = along.cross(Vector((0, 0, 1)) if abs(along.z) < 0.95 else Vector((1, 0, 0))).normalized()
    top = side.cross(along)
    h = h or w
    corners = [side * sx * w / 2 + top * tz * h / 2 for sx, tz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    verts = [tuple(p0 + q) for q in corners] + [tuple(p1 + q) for q in corners]
    b.add(verts, [(4, 5, 1, 0), (5, 6, 2, 1), (6, 7, 3, 2), (7, 4, 0, 3), (1, 2, 3, 0), (7, 6, 5, 4)],
          [c.vary(colour, 0.12, Vector(v) * 3) for v in verts])


def both_ways(b, verts, faces, colours):
    """Something thin (a leaf, a petal), seen from either side."""
    n = len(verts)
    b.add(verts + verts, faces + [tuple(i + n for i in f[::-1]) for f in faces], colours + colours)


def sett(b, rnd, pts, z, colour):
    """A cobble, set in the ground: its top rounded down into the joints round it."""
    n = len(pts)
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    low = [(mx + (x - mx) * 0.88, my + (y - my) * 0.88) for x, y in pts]
    top = [(mx + (x - mx) * 0.6, my + (y - my) * 0.6) for x, y in pts]
    h = rnd.uniform(0.04, 0.065)
    edge = c.mix(colour, c.linear("#000000"), 0.2)
    verts = [(x, y, z + 0.006) for x, y in low] + [(x, y, z + h) for x, y in top]
    faces = [tuple(range(n, 2 * n))] + [(k, (k + 1) % n, n + (k + 1) % n, n + k) for k in range(n)]
    b.add(verts, faces, [edge] * n + [c.vary(colour, 0.05, Vector((mx, my, 3.0)))] * n)


def cobble_colour(rnd, x, y):
    colour = rnd.choice(COBBLES)
    t = rnd.uniform(-0.1, 0.18)
    colour = c.mix(colour, c.linear("#000000"), t) if t > 0 else c.mix(colour, c.linear("#fff4dc"), -t)
    if rnd.random() < 0.06:
        colour = c.mix(colour, c.linear("#7d8a4a"), rnd.uniform(0.15, 0.35))  # (a little moss)
    return colour


def rose_leaf(b, rnd, p, out, size, shade=1.0):
    """A rose's leaf: a little folded diamond, facing about `out`, turned any
    way. (Only one side of it: the game draws roses from either side.)"""
    n = (Vector(out).normalized() + Vector((rnd.uniform(-0.8, 0.8), rnd.uniform(-0.8, 0.8),
                                            rnd.uniform(-0.4, 0.8)))).normalized()
    t = n.orthogonal().normalized()
    a = rnd.uniform(0, 2 * math.pi)
    t = t * math.cos(a) + n.cross(t) * math.sin(a)
    s = n.cross(t)
    p = Vector(p)
    pts = [p - t * size * 0.45, p + s * size * 0.27 + n * size * 0.1, p + t * size * 0.55,
           p - s * size * 0.27 + n * size * 0.1]
    colour = c.mix(rnd.choice(ROSE_LEAVES), c.linear("#000000"), 1 - shade)
    b.add([tuple(q) for q in pts], [(0, 1, 2), (0, 2, 3)], [colour, c.mix(colour, c.linear("#ffffff"), 0.08),
                                                                     colour, colour])


def rose(b, rnd, p, out, size):
    """A rose, open, facing about `out`: a ring of petals round a cupped ring
    of deeper ones, round its heart."""
    n = (Vector(out).normalized() + Vector([rnd.uniform(-0.45, 0.45) for _ in range(3)])).normalized()
    t = n.orthogonal().normalized()
    s = n.cross(t)
    p = Vector(p)
    colour = rnd.choice(ROSES)
    turn = rnd.uniform(0, 2 * math.pi)
    for count, r_in, r_out, lift, wide, shade in ((5, 0.15, 1.0, 0.22, 0.45, c.mix(colour, c.linear("#ffffff"), 0.22)),
                                                  (5, 0.1, 0.62, 0.5, 0.36, colour)):
        for k in range(count):
            a = turn + 2 * math.pi * k / count
            d = t * math.cos(a) + s * math.sin(a)
            e = t * math.cos(a + math.pi / 2) + s * math.sin(a + math.pi / 2)
            pts = [p + (d * r_in - e * wide * 0.4) * size, p + (d * r_out - e * wide + n * lift) * size,
                   p + (d * r_out * 1.1 + n * lift * 1.1) * size, p + (d * r_out + e * wide + n * lift) * size,
                   p + (d * r_in + e * wide * 0.4) * size]
            b.add([tuple(q) for q in pts], [(0, 1, 2, 3, 4)], [c.mix(shade, ROSE_HEART, 0.25)] + [shade] * 4)
        turn += math.pi / count
    heart = [tuple(p + (t * math.cos(a) + s * math.sin(a)) * 0.22 * size + n * 0.3 * size)
             for a in (2 * math.pi * k / 5 for k in range(5))]
    b.add(heart + [tuple(p + n * 0.55 * size)], [(k, (k + 1) % 5, 5) for k in range(5)],
          [c.mix(colour, ROSE_HEART, 0.6)] * 5 + [ROSE_HEART])


def rose_bush(variant, R=0.75, H=0.95):
    """A rose bush (to make, for stamp): a mound of leaves, roses all over it."""

    def make(t):
        rnd = random.Random(f"rose bush {variant}")
        t.blob((0, 0, H * 0.4), R * 0.8, c.linear("#22401a"), squash=H / R * 0.75, lumpy=0.3, seed=variant)
        offset = Vector((variant * 3.1, 1.7, 0.4))

        def on(d, lift=1.0):
            r = rnd.uniform(0.8, 1.04) * (1 + 0.2 * noise.noise(d * 2 + offset)) * lift
            return (d.x * R * r, d.y * R * r, H * 0.42 + d.z * H * 0.58 * r)

        def direction():
            while True:
                d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
                if d.z > -0.72:
                    return d

        for _ in range(620):
            d = direction()
            rose_leaf(t, rnd, on(d), d, rnd.uniform(0.12, 0.17), shade=0.72 + 0.28 * (d.z * 0.5 + 0.5))
        for _ in range(24 + variant * 3):
            d = direction()
            if d.z > -0.3:
                rose(t, rnd, on(d, 1.06), d, rnd.uniform(0.07, 0.095))
        return (-R, -R, R, R), H

    return make


def rose_climber(variant, wide, tall):
    """Rambling roses (to make, for stamp), climbing a wall at its back (y =
    0), into the room in front of it (-y): canes from its foot fanning up
    over it, arching over at their tops, in leaf, with roses all along them."""

    def make(t):
        rnd = random.Random(f"rose climber {variant}")
        canes = max(3, round(wide * 2.4))
        for k in range(canes):
            x, z = rnd.uniform(-0.25, 0.25) * min(wide, 1.2), 0.0
            # (Up, leaning out towards its own part of the wall, then over.)
            aim = (k + 0.5) / canes - 0.5
            heading = aim * 1.6 + rnd.uniform(-0.2, 0.2)
            top = tall * rnd.uniform(0.55, 1.0) * (1 - 0.35 * abs(aim) * 2)
            step, length, arching = 0.26, 0.0, False
            if k % 2 == 0:
                log(t, (x, -0.15, 0), (x + math.sin(heading) * 0.8, -0.14, 0.8), 0.025, ROSE_CANE, sides=5)
            while length < tall * 1.7:
                x += math.sin(heading) * step
                z += math.cos(heading) * step
                length += step
                heading += rnd.uniform(-0.25, 0.25)
                if abs(x) > wide / 2 + 0.15:
                    break  # (no further: past its own part of the wall, it'd sprawl over a door or a window)
                if abs(x) > wide / 2 - 0.2:
                    heading -= 0.3 * math.copysign(1, x)
                if z > top:
                    arching = True
                if arching:
                    heading += 0.22 * (1 if heading >= 0 else -1)
                    if abs(heading) > 2.6:
                        break
                if z < 0.3 and arching:
                    break
                for _ in range(6):
                    p = (x + rnd.uniform(-0.28, 0.28), rnd.uniform(-0.42, -0.05), z + rnd.uniform(-0.26, 0.26))
                    rose_leaf(t, rnd, p, (rnd.uniform(-0.4, 0.4), -1, 0.3), rnd.uniform(0.15, 0.21),
                              shade=0.62 + 0.38 * min(1.0, -p[1] / 0.4))
                if z > 0.6 and rnd.random() < 0.45:
                    for _ in range(rnd.choice((1, 1, 2, 3))):
                        rose(t, rnd, (x + rnd.uniform(-0.2, 0.2), rnd.uniform(-0.48, -0.3), z + rnd.uniform(-0.2, 0.2)),
                             (0, -1, 0.2), rnd.uniform(0.075, 0.1))
        return (-wide / 2, -0.5, wide / 2, 0), tall

    return make


def rose_canopy(variant, wide, deep):
    """Roses over the top of a pergola (to make, for stamp): leaves lying
    over it, wide across and deep along it, and sprays hanging down its
    sides, in flower."""

    def make(t):
        rnd = random.Random(f"rose canopy {variant}")
        for _ in range(int(wide * deep * 70)):
            p = (rnd.uniform(-wide / 2, wide / 2), rnd.uniform(-deep / 2, deep / 2), rnd.uniform(0.0, 0.32))
            rose_leaf(t, rnd, p, (0, 0, 1), rnd.uniform(0.13, 0.19), shade=0.65 + 0.35 * p[2] / 0.32)
        for side in (-1, 1):
            y = rnd.uniform(-deep / 2, -deep / 2 + 0.4)
            while y < deep / 2:
                drop = rnd.uniform(0.3, 1.1)
                z = 0.0
                while z > -drop:
                    p = (side * (wide / 2 + rnd.uniform(-0.15, 0.05)), y + rnd.uniform(-0.15, 0.15), z)
                    rose_leaf(t, rnd, p, (side, 0, 0), rnd.uniform(0.12, 0.17), shade=0.85)
                    if rnd.random() < 0.18:
                        rose(t, rnd, p, (side, 0, -0.3), rnd.uniform(0.07, 0.09))
                    z -= 0.07
                y += rnd.uniform(0.3, 0.6)
        for _ in range(int(wide * deep * 5)):
            rose(t, rnd, (rnd.uniform(-wide / 2, wide / 2), rnd.uniform(-deep / 2, deep / 2), 0.34), (0, 0, 1),
                 rnd.uniform(0.075, 0.1))
        return (-wide / 2, -deep / 2, wide / 2, deep / 2), 0.4

    return make


# Each kind of rose: what makes it.
ROSE_KINDS = {
    "rose-bush-1": rose_bush(1),
    "rose-bush-2": rose_bush(2, R=0.65, H=0.85),
    "rose-bush-3": rose_bush(3, R=0.85, H=1.05),
    "rose-climber-1": rose_climber(1, 3.4, 6.2),
    "rose-climber-2": rose_climber(2, 4.0, 4.2),
    "rose-climber-3": rose_climber(3, 1.4, 5.0),
    "rose-climber-4": rose_climber(4, 1.0, 2.8),
    "rose-canopy": rose_canopy(1, 4.0, 3.1),
}


def roses_at(kind, x, y, z, yaw):
    """Roses of a kind, there, turned by yaw (facing -y at 0), not solid (what's
    under them, or the bed they're in, is)."""
    stamp(kind, ROSE_KINDS[kind], (x, y, z), yaw, solid=False)


def kit_window(name, at, yaw, scale, room):
    """One of the kit's windows (its back to the wall): its frame; its glass,
    to see through; and, `room` (as the kit measures) back behind the
    glass, the dark of the room it lights, glowing a little low down, as if
    a candle were lit in there (in the shape of its glass, so nothing shows
    round it)."""
    VILLAGE.put(court, name, at, yaw, scale, where=lambda material: "Glass" not in material)
    VILLAGE.put(window_glass, name, at, yaw, scale, where=lambda material: "Glass" in material)
    move = VILLAGE.placing(at, yaw, scale)
    panes = [pts for pts, _, material in VILLAGE.faces(name) if "Glass" in material]
    low, high = min(p[2] for pts in panes for p in pts), max(p[2] for pts in panes for p in pts)
    for pts in panes:
        back = [move((x, y + room, z)) for x, y, z in pts]
        glow = [smooth(1 - (z - low) / (high - low) * 1.6) for _, _, z in pts]
        court.add(back, [tuple(range(len(back)))], [c.mix(c.linear("#15131a"), c.linear("#6a4222"), 0.7 * t) for t in glow])


def facing_yaw(fx, fy):
    """The yaw that turns what faces -y to face (fx, fy)."""
    return math.atan2(fx, -fy)


# The coach house, a barn (its outside: courtyard; its inside: coach_house):
# its walls' outer faces, west, east, south and north, and how it's built up.
BARN = HALLS["coach-house"]
BARN_W, BARN_E = BARN.x - BARN.w - 0.6, BARN.x + BARN.w + 0.6
BARN_S, BARN_N = BARN.y - BARN.d - 0.6, BARN.y + BARN.d + 0.6
BARN_SHELL = 0.25  # from its walls' faces outside to inside
BARN_EAVE = BARN.floor + 5.6
BARN_RIDGE = BARN_EAVE + 4.6
BARN_FOOTING = YARD_FLOOR + 0.85
BARN_DOOR = 2.4 - 0.05  # (a shade narrower than the way in, as at the keep's door)
BARN_DOOR_TOP = TUNNEL_TALL + 0.4 - LINTEL_DROP


def roof_line(x):
    """How high its roof's underside is, over a point across it."""
    return BARN_EAVE + (BARN_RIDGE - BARN_EAVE) * max(0.0, 1 - abs(x - BARN.x) / (BARN_E - BARN.x))


def barn_wall(b, p0, p1, z_top, holes, inside):
    """One of its walls' faces, boards upright from its footing up to z_top(t)
    (along it, from p0), facing out to the right as you look along it:
    outside, on its stone footing; inside, boards all the way down."""
    (ax, ay), (bx, by) = p0, p1
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    ox, oy = uy * 0.03, -ux * 0.03
    rnd = random.Random(f"barn {p0} {p1}")
    low = BARN.floor - 0.06 if inside else BARN_FOOTING
    if not inside:
        courses(court, court_rng, p0, p1, YARD_FLOOR - 0.1, BARN_FOOTING, holes, big=0.7)
    t = 0.0
    while t < length - 0.02:
        t1 = min(length, t + rnd.uniform(0.26, 0.32))
        mid = (t + t1) / 2
        hi = z_top(mid)
        colour = rnd.choice(BOARDS)
        if inside:
            colour = c.mix(colour, c.linear("#c9a26a"), 0.2)
        for a, e, lo, top in clear_of((t + 0.012, t1 - 0.012, low, hi), holes):
            pts = [(ax + ux * a + ox, ay + uy * a + oy, lo), (ax + ux * e + ox, ay + uy * e + oy, lo),
                   (ax + ux * e + ox, ay + uy * e + oy, min(top, z_top(e))),
                   (ax + ux * a + ox, ay + uy * a + oy, min(top, z_top(a)))]
            b.add(pts, [(0, 1, 2, 3)], [c.vary(colour, 0.08, Vector((a, lo, 1.0))), colour,
                                        c.mix(colour, c.linear("#ffffff"), 0.05), colour])
        t = t1


def barn_frame(b, p0, p1, posts_at, holes, out):
    """Its oak frame on a wall's face: posts (at those distances along it),
    a sill on the footing, a rail and a plate along the top, and braces."""
    (ax, ay), (bx, by) = p0, p1
    length = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / length, (by - ay) / length
    o = (uy * out, -ux * out)

    def at(t, z):
        return ax + ux * t + o[0], ay + uy * t + o[1], z

    low = BARN_FOOTING if out > 0 else BARN.floor
    for t in posts_at:
        timber(b, at(t, low - 0.02), at(t, BARN_EAVE), 0.3, TIMBER)
    for z in (low + 0.1, BARN_EAVE - 0.15):
        for a, e, lo, hi in clear_of((0, length, z - 0.12, z + 0.12), holes):
            timber(b, at(a, z), at(e, z), 0.24, TIMBER)
    # (Braces, from the posts up to the plate, at either end of each bay.)
    for t0, t1 in zip(posts_at, posts_at[1:]):
        if any(a < (t0 + t1) / 2 < e and z0 < low + 1 for a, e, z0, _ in holes):
            continue
        timber(b, at(t0 + 0.15, BARN_EAVE - 1.6), at(t0 + 1.4, BARN_EAVE - 0.2), 0.16, TIMBER)
        timber(b, at(t1 - 0.15, BARN_EAVE - 1.6), at(t1 - 1.4, BARN_EAVE - 0.2), 0.16, TIMBER)


def courtyard():
    """Builds it all (the coach house's inside is coach_house's)."""
    g = YARD_FLOOR
    yw, ye, ys, yn = YARD

    # The castle's stonework: its walls (inside and out), the keep's front, the
    # gatehouse and the towers, in courses of blocks (the walls themselves, the
    # mortar between: MORTAR); and battlements along the tops of its walls.
    door_half = TUNNEL_HALF - 0.05
    courses(court, court_rng, (yw, yn), (-3, yn), g, 8)  # the north wall, inside, either side of the gate
    courses(court, court_rng, (3, yn), (ye, yn), g, 8)
    # (And the gatehouse over the gate: only over the opening, up to the wall's
    # top, and its full width above it. Over the wall too, two lots of stones
    # in one place would flicker.)
    courses(court, court_rng, (-3, yn), (3, yn), GATEHOUSE[0], 8)
    courses(court, court_rng, (-3.2, yn), (3.2, yn), 8, GATEHOUSE[1])
    courses(court, court_rng, (ye + 2, yn + 2), (3, yn + 2), g, 8, big=1.6)  # and outside
    courses(court, court_rng, (-3, yn + 2), (yw - 2, yn + 2), g, 8, big=1.6)
    courses(court, court_rng, (3, yn + 2), (-3, yn + 2), GATEHOUSE[0], 8, big=1.6)
    courses(court, court_rng, (3.2, yn + 2), (-3.2, yn + 2), 8, GATEHOUSE[1], big=1.6)
    courses(court, court_rng, (yw, ys), (yw, yn), g, 8)  # the west wall, inside
    courses(court, court_rng, (yw - 2, yn + 2), (yw - 2, CASTLE[2] - 1), g, 8, big=1.6)  # and outside
    courses(court, court_rng, (ye, yn), (ye, ys), g, 8)  # the east wall, inside
    courses(court, court_rng, (ye + 2, CASTLE[2] - 1), (ye + 2, yn + 2), g, 8, big=1.6)  # and outside
    # The keep's front, round its door.
    courses(court, court_rng, (ye, ys), (yw, ys), g, KEEP_TALL, [(ye - GH[0] - door_half, ye - GH[0] + door_half, 0,
                                                                 TUNNEL_TALL + 0.4)])
    for tx, ty, r, tall in ((CASTLE[0], CASTLE[3], 5, 13), (CASTLE[1], CASTLE[3], 5, 13), (CASTLE[0], CASTLE[2], 5, 13),
                            (CASTLE[1], CASTLE[2], 5, 13), (-6, CASTLE[3], 3, 11), (6, CASTLE[3], 3, 11)):
        round_courses(court, court_rng, tx, ty, r, 12, g, height(tx, ty) - 0.5 + tall)
    # Battlements along the walls, but where the towers stand.
    for (x0, y0), (x1, y1), across in (((CASTLE[0], CASTLE[3]), (CASTLE[1], CASTLE[3]), (0, 1)),
                                       ((CASTLE[0], CASTLE[2]), (CASTLE[1], CASTLE[2]), (0, 1)),
                                       ((CASTLE[0], CASTLE[2]), (CASTLE[0], CASTLE[3]), (1, 0)),
                                       ((CASTLE[1], CASTLE[2]), (CASTLE[1], CASTLE[3]), (1, 0))):
        length = math.hypot(x1 - x0, y1 - y0)
        t = 0.6
        while t < length - 1.2:
            mx, my = x0 + (x1 - x0) * (t + 0.55) / length, y0 + (y1 - y0) * (t + 0.55) / length
            clear = all(math.hypot(mx - tx, my - ty) > r + 0.8 for tx, ty, r in (
                (CASTLE[0], CASTLE[3], 5), (CASTLE[1], CASTLE[3], 5), (CASTLE[0], CASTLE[2], 5), (CASTLE[1], CASTLE[2], 5),
                (-6, CASTLE[3], 3), (6, CASTLE[3], 3)))
            if clear and not (across == (0, 1) and y0 == CASTLE[3] and abs(mx) < 3.6):
                ax, ay = (x1 - x0) / length, (y1 - y0) / length
                p = (x0 + ax * t, y0 + ay * t)
                q = (x0 + ax * (t + 1.1), y0 + ay * (t + 1.1))
                block(court, min(p[0], q[0]) - across[0], min(p[1], q[1]) - across[1], 8, max(p[0], q[0]) + across[0],
                      max(p[1], q[1]) + across[1], 9.1, castle_stone(court_rng, 9, 0), solid=False)
            t += 2.2

    # Dressed stones round the keep's door and the gate: big corner stones up
    # their sides, alternately long and short, and a lintel over the door.
    for side in (-1, 1):
        for k in range(7):
            z = g + k * 0.45
            if z + 0.43 > TUNNEL_TALL + 0.4:
                break
            long_ = 0.8 if k % 2 else 0.5
            x0 = GH[0] + side * (door_half + 0.02)
            block(court, min(x0, x0 + side * long_), ys, z + 0.02, max(x0, x0 + side * long_), ys + 0.1, z + 0.43,
                  c.mix(castle_stone(court_rng, z + 2, 0), c.linear("#fff6e2"), 0.25), solid=False)
        for k in range(15):
            z = g + k * 0.45
            long_ = 0.75 if k % 2 else 0.45
            x0 = side * 3.02
            block(court, min(x0, x0 + side * long_), yn - 0.1, z + 0.02, max(x0, x0 + side * long_), yn, z + 0.43,
                  c.mix(castle_stone(court_rng, z + 2, 0), c.linear("#fff6e2"), 0.25), solid=False)
    block(court, GH[0] - door_half - 0.9, ys, TUNNEL_TALL + 0.4, GH[0] + door_half + 0.9, ys + 0.14, TUNNEL_TALL + 1.05,
          c.mix(CASTLE_STONE[2], c.linear("#fff6e2"), 0.2), solid=False)

    # The cobbles, all over it but for the beds, the well's ring and the coach house.
    WELL_R = 1.15  # its wall, round
    WELL_RING = (WELL_R + 0.12, WELL_R + 1.85)  # the ring of stones round it
    BEDS = []  # rose beds: x0, y0, x1, y1, and which side is against a wall ("n", "s", "e", "w" or "")
    TOWERS_IN = [(CASTLE[0], CASTLE[3], 5), (CASTLE[1], CASTLE[3], 5), (-6, CASTLE[3], 3), (6, CASTLE[3], 3)]


    def in_bed(x, y, margin=0.0):
        return any(x0 - margin <= x <= x1 + margin and y0 - margin <= y <= y1 + margin for x0, y0, x1, y1, _ in BEDS)


    def bed(x0, y0, x1, y1, wall=""):
        BEDS.append((x0, y0, x1, y1, wall))


    # Along the north wall, either side of the gate, between the towers; along
    # the west and east walls; and along the keep's front, either side of its door.
    bed(CASTLE[0] + 5.2, yn - 2.0, -9.2, yn, "n")
    bed(9.2, yn - 2.0, CASTLE[1] - 5.2, yn, "n")
    bed(yw, ys + 2.6, yw + 2.0, yn - 4.6, "w")
    bed(ye - 2.0, ys + 2.6, ye, yn - 4.6, "e")
    bed(yw + 2.6, ys, -4.2, ys + 2.0, "s")
    bed(4.2, ys, ye - 2.6, ys + 2.0, "s")
    # In the rose garden, either side of the pergola.
    PERGOLA = (-27.0, ys + 5.0, ys + 23.0, 1.7)  # its middle (x), from and to (y), and half its width
    bed(PERGOLA[0] - 6.4, PERGOLA[1] + 0.5, PERGOLA[0] - 3.0, PERGOLA[2] - 0.5)
    bed(PERGOLA[0] + 3.0, PERGOLA[1] + 0.5, PERGOLA[0] + 6.4, PERGOLA[2] - 0.5)


    def cobbled(x, y):
        if in_bed(x, y, 0.1) or in_building(x, y) or math.hypot(x - WELL[0], y - WELL[1]) < WELL_RING[1] + 0.1:
            return False
        return all(math.hypot(x - tx, y - ty) > r + 0.15 for tx, ty, r in TOWERS_IN)


    CELL = 0.8
    nx_, ny_ = math.ceil((ye - yw) / CELL), math.ceil((yn - ys) / CELL)
    corner = {}
    for i in range(nx_ + 1):
        for j in range(ny_ + 1):
            jx = court_rng.uniform(-0.22, 0.22) * CELL if 0 < i < nx_ else 0.0
            jy = court_rng.uniform(-0.22, 0.22) * CELL if 0 < j < ny_ else 0.0
            corner[i, j] = (min(ye, yw + i * CELL + jx), min(yn, ys + j * CELL + jy))
    for i in range(nx_):
        for j in range(ny_):
            pts = [corner[i, j], corner[i + 1, j], corner[i + 1, j + 1], corner[i, j + 1]]
            mx, my = sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4
            if cobbled(mx, my):
                sett(court, court_rng, pts, g, cobble_colour(court_rng, mx, my))
    # Round the well, in rings.
    for r0, r1 in ((WELL_RING[0], WELL_RING[0] + 0.6), (WELL_RING[0] + 0.6, WELL_RING[0] + 1.2), (WELL_RING[0] + 1.2, WELL_RING[1])):
        n = round(2 * math.pi * (r0 + r1) / 2 / 0.62)
        turn = court_rng.uniform(0, 1)
        for k in range(n):
            a0, a1 = 2 * math.pi * (k + turn) / n, 2 * math.pi * (k + 1 + turn) / n
            pts = [(WELL[0] + math.cos(a) * r, WELL[1] + math.sin(a) * r) for r, a in ((r0, a0), (r1, a0), (r1, a1), (r0, a1))]
            colour = cobble_colour(court_rng, *pts[0])
            sett(court, court_rng, pts, g, c.mix(colour, c.linear("#ffffff"), 0.08))
    # Tufts of grass between them, more near the walls and the beds.
    for _ in range(900):
        x, y = court_rng.uniform(yw, ye), court_rng.uniform(ys, yn)
        near = min(x - yw, ye - x, y - ys, yn - y)
        if not cobbled(x, y) or court_rng.random() > 0.25 + 0.75 * smooth(1 - near / 3):
            continue
        for k in range(3):
            a = court_rng.uniform(0, 2 * math.pi)
            tall = court_rng.uniform(0.08, 0.2)
            tip = (x + math.cos(a) * 0.06, y + math.sin(a) * 0.06, g + tall)
            pts = [(x - math.sin(a) * 0.025, y + math.cos(a) * 0.025, g + 0.01), (x + math.sin(a) * 0.025,
                                                                                  y - math.cos(a) * 0.025, g + 0.01), tip]
            both_ways(court, pts, [(0, 1, 2)], [c.linear("#4c6e2a"), c.linear("#4c6e2a"), c.linear("#8fae4c")])

    # The beds: earth, a low kerb of stones along their open sides, roses in
    # them, and climbing the wall behind.
    for x0, y0, x1, y1, wall in BEDS:
        quad(court, [(x0, y0, g + 0.12), (x1, y0, g + 0.12), (x1, y1, g + 0.12), (x0, y1, g + 0.12)], SOIL, 0.15)
        sides = {"s": ((x0, y0), (x1, y0)), "e": ((x1, y0), (x1, y1)), "n": ((x1, y1), (x0, y1)),
                 "w": ((x0, y1), (x0, y0))}
        for name, ((ax, ay), (bx, by)) in sides.items():
            if name == wall:
                continue
            length = math.hypot(bx - ax, by - ay)
            ux, uy = (bx - ax) / length, (by - ay) / length
            t = 0.0
            while t < length - 0.05:
                t1 = min(length, t + court_rng.uniform(0.45, 0.7))
                oriented(court, (ax + ux * t, ay + uy * t, g), (ux, uy), 0.015, t1 - t - 0.015, -0.12, 0.12, -0.05,
                         court_rng.uniform(0.22, 0.28), c.mix(castle_stone(court_rng, 2, 0), c.linear("#ffffff"), 0.1), 0.05)
                t = t1
        solid_box((x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2)
        # Roses all along it, in a row (two, if it's deep enough).
        along_x = x1 - x0 >= y1 - y0
        length, deep = (x1 - x0, y1 - y0) if along_x else (y1 - y0, x1 - x0)
        rows = 1 if deep < 2.6 else 2
        for row in range(rows):
            t = court_rng.uniform(0.6, 1.0)
            while t < length - 0.6:
                across = deep * (row + 0.5) / rows + court_rng.uniform(-0.15, 0.15)
                if wall in ("n", "e"):
                    across = deep - across
                x, y = (x0 + t, y0 + across) if along_x else (x0 + across, y0 + t)
                roses_at(f"rose-bush-{court_rng.randint(1, 3)}", x, y, g + 0.1, court_rng.uniform(0, 2 * math.pi))
                t += court_rng.uniform(1.25, 1.7)
    # Climbing the walls behind the beds.
    for x0, x1, y, face in ((CASTLE[0] + 5.6, -9.4, yn, (0, -1)), (9.4, CASTLE[1] - 5.6, yn, (0, -1)),
                            (-44.0, -4.6, ys, (0, 1)), (4.6, 44.0, ys, (0, 1))):
        x = x0 + court_rng.uniform(1.0, 2.5)
        while x < x1 - 1.0:
            kind = court_rng.choice(("rose-climber-1", "rose-climber-1", "rose-climber-2", "rose-climber-3"))
            roses_at(kind, x, y, g + 0.1, facing_yaw(*face))
            x += court_rng.uniform(3.6, 6.0)
    for x, face in ((yw, (1, 0)), (ye, (-1, 0))):
        y = ys + 3.5 + court_rng.uniform(0, 1.5)
        while y < yn - 6:
            kind = court_rng.choice(("rose-climber-1", "rose-climber-2", "rose-climber-3"))
            roses_at(kind, x, y, g + 0.1, facing_yaw(*face))
            y += court_rng.uniform(3.8, 6.0)
    # Up the towers (on their sides to the courtyard), and either side of the gate.
    for tx, ty, r, angles in ((CASTLE[0], CASTLE[3], 5, (-0.35, -1.2)), (CASTLE[1], CASTLE[3], 5, (-1.95, -2.8)),
                              (-6, CASTLE[3], 3, (-1.2, -2.3)), (6, CASTLE[3], 3, (-0.85, -1.95))):
        for a in angles:
            x, y = tx + math.cos(a) * (r * 0.97), ty + math.sin(a) * (r * 0.97)
            roses_at("rose-climber-3", x, y, g, facing_yaw(math.cos(a), math.sin(a)))
            solid_circle(x + math.cos(a) * 0.25, y + math.sin(a) * 0.25, 0.45)

    # The well, in the middle: a round wall of stone, capped with a ring of
    # flat stones, the dark shaft and the water far down; two oak posts, the
    # windlass between them with its rope wound round it and its crank, the
    # bucket hanging, and a little roof of shingles over it. Roses round its foot.
    wx, wy = WELL
    WELL_TALL, WELL_IN, WELL_SIDES = 0.85, 0.8, 20
    ring = [(math.cos(2 * math.pi * k / WELL_SIDES), math.sin(2 * math.pi * k / WELL_SIDES)) for k in range(WELL_SIDES)]
    court.cylinder((wx, wy, g - 0.2), (wx, wy, g + WELL_TALL), WELL_R, WELL_R, MORTAR, sides=WELL_SIDES)
    stone_courses(court, court_rng, lambda a: (wx + math.cos(a) * (WELL_R + 0.015) / math.cos(
        a - (math.floor(a / (2 * math.pi / WELL_SIDES)) + 0.5) * 2 * math.pi / WELL_SIDES) * math.cos(math.pi / WELL_SIDES),
                                               wy + math.sin(a) * (WELL_R + 0.015) / math.cos(
        a - (math.floor(a / (2 * math.pi / WELL_SIDES)) + 0.5) * 2 * math.pi / WELL_SIDES) * math.cos(math.pi / WELL_SIDES)),
                  [2 * math.pi * k / WELL_SIDES for k in range(2 * WELL_SIDES + 1)], WELL_R, g, g + WELL_TALL - 0.14, [], g,
                  course=(0.2, 0.27), shade=castle_stone)
    # (Its shaft, inside, facing in, dark; and the water.)
    for k in range(WELL_SIDES):
        (ca, sa), (cb, sb) = ring[k], ring[(k + 1) % WELL_SIDES]
        court.add([(wx + cb * WELL_IN, wy + sb * WELL_IN, g - 1.6), (wx + ca * WELL_IN, wy + sa * WELL_IN, g - 1.6),
                   (wx + ca * WELL_IN, wy + sa * WELL_IN, g + WELL_TALL), (wx + cb * WELL_IN, wy + sb * WELL_IN, g + WELL_TALL)],
                  [(0, 1, 2, 3)], [c.linear("#0e0d0b")] * 2 + [c.linear("#4a4236")] * 2)
    court.add([(wx, wy, g - 1.4)] + [(wx + ca * WELL_IN, wy + sa * WELL_IN, g - 1.4) for ca, sa in ring],
              [(0, 1 + k, 1 + (k + 1) % WELL_SIDES) for k in range(WELL_SIDES)], [c.linear("#1d3a40")] + [c.linear("#0b1a1e")] * WELL_SIDES)
    # The cap: flat stones round its top.
    caps = 14
    for k in range(caps):
        a0, a1 = 2 * math.pi * (k + 0.03) / caps, 2 * math.pi * (k + 0.97) / caps
        pts = [(wx + math.cos(a) * r, wy + math.sin(a) * r) for r, a in ((WELL_IN - 0.03, a0), (WELL_R + 0.07, a0),
                                                                           (WELL_R + 0.07, a1), (WELL_IN - 0.03, a1))]
        colour = c.mix(castle_stone(court_rng, 3, 0), c.linear("#ffffff"), 0.1)
        court.add([(x, y, g + WELL_TALL - 0.14) for x, y in pts] + [(x, y, g + WELL_TALL) for x, y in pts],
                  [(4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)], [colour] * 8)
    solid_circle(wx, wy, WELL_R + 0.1)
    # The posts, the windlass and its crank, the rope and the bucket.
    OAK_POST = c.linear("#6a4528")
    POST_TOP = g + 3.05
    for side in (-1, 1):
        px = wx + side * (WELL_R - 0.12)
        block(court, px - 0.1, wy - 0.1, g + WELL_TALL, px + 0.1, wy + 0.1, POST_TOP, OAK_POST, solid=False)
        timber(court, (px, wy, g + WELL_TALL + 0.02), (px - side * 0.0, wy + 0.42, g + WELL_TALL - 0.02), 0.07, OAK_POST)
    timber(court, (wx - WELL_R - 0.05, wy, POST_TOP - 0.06), (wx + WELL_R + 0.05, wy, POST_TOP - 0.06), 0.14, OAK_POST)
    AXLE = g + 1.95
    log(court, (wx - WELL_R + 0.02, wy, AXLE), (wx + WELL_R + 0.25, wy, AXLE), 0.07, c.linear("#7a5634"), sides=8)
    log(court, (wx - 0.38, wy, AXLE), (wx + 0.38, wy, AXLE), 0.12, c.linear("#b4955f"), sides=8)  # (the rope, wound)
    crank = wx + WELL_R + 0.22
    timber(court, (crank, wy, AXLE), (crank, wy - 0.05, AXLE - 0.36), 0.05, IRON)
    timber(court, (crank, wy - 0.05, AXLE - 0.36), (crank + 0.24, wy - 0.05, AXLE - 0.36), 0.045, IRON)
    BUCKET = 1.6  # times the kit's size
    bucket_z = g + WELL_TALL + 0.32
    log(court, (wx, wy - 0.12, AXLE - 0.05), (wx, wy, bucket_z + 0.29 * BUCKET + 0.06), 0.014, c.linear("#b4955f"),
        sides=4)
    PROPS.put(court, "Bucket_Wooden_1", (wx, wy, bucket_z), 0.4, BUCKET, 0.4)
    for yaw in (0.0, math.pi):
        VILLAGE.put(court, "Roof_Wooden_2x1", (wx, wy, POST_TOP + 0.08), yaw, 1.12)
    # Roses round its foot.
    for a in (0.65, 2.35, 3.9):
        x, y = wx + math.cos(a) * (WELL_R + 0.45), wy + math.sin(a) * (WELL_R + 0.45)
        roses_at("rose-bush-2", x, y, g, a)
        solid_circle(x, y, 0.55)

    # The keep's front: windows high up, their shutters open; lanterns either
    # side of its door, and banners.
    WINDOW = 1.5  # times the kit's size
    for x in (-36, -27, -18, -9, 9, 18, 27, 36):
        # (Its glass 22 cm out from the wall, its frame's back in it; the room behind 17 cm back.)
        at = (x, ys + 0.22, g + 5.0 - 1.02 * WINDOW)
        kit_window("Window_Wide_Round1", at, math.pi, WINDOW, 0.17 / WINDOW)
        VILLAGE.put(court, "WindowShutters_Wide_Round_Open", at, math.pi, WINDOW)
    for x in (-13.5, 13.5, -31.5, 31.5, -40.5, 40.5, -22.5, 22.5):
        if abs(x) < 40:
            roses_at(court_rng.choice(("rose-climber-1", "rose-climber-3")), x, ys, g + 0.1, facing_yaw(0, 1))
    LANTERN = 1.2


    def lit_lantern(t):
        """A lantern on its bracket, lit (to make, for stamp). (In full: made
        simpler, its thin arm folds over on itself, and flickers.)"""
        made = PROPS.put(t, "Lantern_Wall", (0, 0, 0), 0, LANTERN)
        flame(t, *PROPS.placing((0, 0, 0), 0, LANTERN)((0, -1.0, 0.55)), 0.14)
        return made

    def lantern(x, y, z, face):
        """A lantern on a wall, lit, its arm out the way it faces."""
        stamp("lantern-wall-lit", lit_lantern, (x, y, z), facing_yaw(*face), solid=False)


    for side in (-1, 1):
        # (Their backplates on the stones, not in them: in the wall's face, they'd flicker.)
        lantern(GH[0] + side * 2.7, ys + 0.06, g + 2.4, (0, 1))
        lantern(side * 4.6, yn - 0.06, g + 2.6, (0, -1))
    BANNER = 1.9
    # (Each a sign on a bracket: its post against the wall, its arm straight out, the banner hanging under it.)
    for x, tint in ((-5.4, "#9e2b25"), (5.4, "#2f4f8a")):
        PROPS.put(court, "Banner_1", (x, ys + 0.05, g + 7.6), math.pi / 2, BANNER, 0.5, tint=(*c.linear(tint)[:3], 0.6))

    # The rose garden: a pergola of oak, roses over it and up its posts, along
    # a walk between two beds, with benches under it.
    px_, py0, py1, half = PERGOLA
    OAK_LIGHT = c.linear("#7a5634")
    posts = [py0 + k * (py1 - py0) / 6 for k in range(7)]
    for y in posts:
        for side in (-1, 1):
            x = px_ + side * half
            block(court, x - 0.11, y - 0.11, g, x + 0.11, y + 0.11, g + 2.75, OAK_LIGHT, solid=False)
            solid_circle(x, y, 0.2)
            roses_at("rose-climber-4", x + side * 0.12, y, g, facing_yaw(side, 0))
    for side in (-1, 1):
        block(court, px_ + side * half - 0.1, py0 - 0.4, g + 2.75, px_ + side * half + 0.1, py1 + 0.4, g + 2.97, OAK_LIGHT,
              solid=False)
    y = py0 - 0.2
    while y < py1 + 0.3:
        block(court, px_ - half - 0.55, y - 0.05, g + 2.97, px_ + half + 0.55, y + 0.05, g + 3.09, OAK_LIGHT, solid=False)
        y += 0.7
    for k in range(6):
        roses_at("rose-canopy", px_ + court_rng.uniform(-0.15, 0.15), (posts[k] + posts[k + 1]) / 2, g + 3.0,
                 court_rng.choice((0, math.pi)))
    for y in (posts[1] + 1.4, posts[4] + 1.6):
        PROPS.put(court, "Bench", (px_ - half + 0.42, y, g), facing_yaw(1, 0), 1.2)
        solid_box(px_ - half + 0.42, y, 0.35, 1.7)
    # The sundial, beside the rose garden (in the shade: out in the sun, its
    # gnomon's shadow is too fine for the sun's shadows, and blurs).
    sx_, sy_ = px_ - 11.0, (py0 + py1) / 2
    court.cylinder((sx_, sy_, g), (sx_, sy_, g + 0.2), 0.55, 0.5, castle_stone(court_rng, 2, 0), sides=10)
    quad_ring = [(sx_ + math.cos(2 * math.pi * k / 10) * 0.5, sy_ + math.sin(2 * math.pi * k / 10) * 0.5, g + 0.2)
                 for k in range(10)]
    court.add(quad_ring, [tuple(range(10))], [castle_stone(court_rng, 2, 0)] * 10)  # (its step's top)
    court.cylinder((sx_, sy_, g + 0.2), (sx_, sy_, g + 0.95), 0.2, 0.17, castle_stone(court_rng, 2, 0), sides=10)
    court.cylinder((sx_, sy_, g + 0.95), (sx_, sy_, g + 1.05), 0.36, 0.38, castle_stone(court_rng, 2, 0), sides=14)
    court.add([(sx_, sy_, g + 1.05)] + [(sx_ + math.cos(2 * math.pi * k / 14) * 0.38, sy_ + math.sin(2 * math.pi * k / 14) * 0.38,
                                         g + 1.05) for k in range(14)], [(0, 1 + k, 1 + (k + 1) % 14) for k in range(14)],
              [c.linear("#c9a04a")] * 15)
    # (Its gnomon: a wedge of bronze, standing on it.)
    bronze = c.linear("#6a5430")
    wedge = [(y, z) for y, z in ((sy_ - 0.26, g + 1.05), (sy_ + 0.22, g + 1.05), (sy_ - 0.26, g + 1.32))]
    left, right = [(sx_ - 0.012, y, z) for y, z in wedge], [(sx_ + 0.012, y, z) for y, z in wedge]
    facing(court, left, [bronze] * 3, (-1, 0, 0))
    facing(court, right, [bronze] * 3, (1, 0, 0))
    for k, out in ((0, (0, 0, -1)), (1, (0, 0.27, 0.48)), (2, (0, -1, 0))):
        n = (k + 1) % 3
        facing(court, [left[k], left[n], right[n], right[k]], [bronze] * 4, out)
    solid_circle(sx_, sy_, 0.55)

    # The coach house: on a footing of stone, walls of boards, upright, between
    # oak posts and beams (braced at the corners), under a roof of red tiles
    # (the kit's, stretched to fit: its ridge north and south, its eaves over the
    # doors); its great doors open out, its lantern lit; roses up its corners.
    door_t = (BARN_N - BARN.y - BARN_DOOR, BARN_N - BARN.y + BARN_DOOR)  # (along its west face, from the north)
    walls = [  # p0, p1 (facing out to the right), its holes
        ((BARN_W, BARN_S), (BARN_E, BARN_S), []),
        ((BARN_E, BARN_S), (BARN_E, BARN_N), []),
        ((BARN_E, BARN_N), (BARN_W, BARN_N), []),
        ((BARN_W, BARN_N), (BARN_W, BARN_S), [(door_t[0], door_t[1], -1, BARN_DOOR_TOP)]),
    ]
    for p0, p1, holes in walls:
        gable = abs(p1[1] - p0[1]) < 0.01  # (the north and south walls rise under the roof's ends)
        (ax, ay), (bx, by) = p0, p1
        length = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / length, (by - ay) / length

        def top(t, ax=ax, ux=ux, gable=gable):
            return roof_line(ax + ux * t) - 0.05 if gable else BARN_EAVE + 0.35

        barn_wall(court, p0, p1, top, holes, inside=False)
        posts_at = [0.2, length / 3, 2 * length / 3, length - 0.2]
        if holes:
            posts_at = [0.2, holes[0][0] - 0.2, holes[0][1] + 0.2, length - 0.2]
        barn_frame(court, p0, p1, posts_at, holes, 0.14)
        # (The wall itself, behind the boards: dark, between them.)
        ix, iy = -uy * BARN_SHELL, ux * BARN_SHELL  # (in)
        for a, e, lo, hi in clear_of((0, length, g - 0.2, BARN_EAVE + 0.35), holes):
            q0, q1 = (ax + ux * a, ay + uy * a), (ax + ux * e, ay + uy * e)
            oriented(court, (q0[0], q0[1], 0), (ux, uy), 0, e - a, 0, BARN_SHELL, lo, hi, c.linear("#2a1e14"), 0.05)
        if gable:
            pts = [(ax, ay, BARN_EAVE + 0.3), (bx, by, BARN_EAVE + 0.3), (BARN.x, ay, BARN_RIDGE - 0.05)]
            facing(court, pts, [c.linear("#2a1e14")] * 3, (uy, -ux, 0))
            inner = [(x + ix, y + iy, z) for x, y, z in pts]
            facing(court, inner, [c.linear("#2a1e14")] * 3, (-uy, ux, 0))
    # The lintel over the doors, and the doors, open out (planks on ledges,
    # with iron straps across them), and the lantern beside them.
    # (Its underside a shade below the wall's over the doorway, and out in front of it: level, they'd flicker.)
    timber(court, (BARN_W - 0.16, BARN.y - BARN_DOOR - 0.5, BARN_DOOR_TOP + 0.15),
           (BARN_W - 0.16, BARN.y + BARN_DOOR + 0.5, BARN_DOOR_TOP + 0.15), 0.3, TIMBER, 0.36)
    LEAF = BARN_DOOR - 0.02
    for side in (-1, 1):
        hinge = (BARN_W - 0.05, BARN.y + side * BARN_DOOR, g + 0.04)
        swing = math.radians(100)  # (from shut)
        shut = (0, -side)
        across = (shut[0] * math.cos(-side * swing) - shut[1] * math.sin(-side * swing),
                  shut[0] * math.sin(-side * swing) + shut[1] * math.cos(-side * swing))
        u = 0.0
        k = 0
        while u < LEAF - 0.02:
            u1 = min(LEAF, u + 0.29)
            oriented(court, hinge, across, u + 0.008, u1 - 0.008, -0.05, 0.05, 0, BARN_DOOR_TOP - 0.1 - g,
                     BOARDS[(k * 3) % len(BOARDS)], 0.06)
            u, k = u1, k + 1
        for z in (0.45, BARN_DOOR_TOP - g - 0.6):
            for face in (-1, 1):
                oriented(court, hinge, across, 0.05, LEAF - 0.1, face * 0.05, face * 0.085, z - 0.11, z + 0.11, TIMBER, 0.06)
        for z in (0.75, (BARN_DOOR_TOP - g) / 2, BARN_DOOR_TOP - g - 0.9):
            for face in (-1, 1):
                oriented(court, hinge, across, -0.02, LEAF * 0.7, face * 0.055, face * 0.1, z - 0.05, z + 0.05, IRON, 0.04)
        end = (hinge[0] + across[0] * LEAF, hinge[1] + across[1] * LEAF)
        solid_box((hinge[0] + end[0]) / 2, (hinge[1] + end[1]) / 2, abs(end[0] - hinge[0]) / 2 + 0.12,
                  abs(end[1] - hinge[1]) / 2 + 0.12)
    lantern(BARN_W - 0.17, BARN.y + BARN_DOOR + 1.2, g + 2.6, (-1, 0))
    # The roof.
    TILES = (BARN_E - BARN.x + 0.1) / 4.0, (BARN_N - BARN_S) / 14.0, (BARN_RIDGE - BARN_EAVE) / 6.0
    VILLAGE.put(court, "Roof_RoundTiles_8x14", (BARN.x, BARN.y, BARN_EAVE), 0, TILES, 0.6)
    # Little windows up in its gables, facing out (their glass 15 cm out from its boards' wall).
    for y, yaw in ((BARN_N + 0.15, facing_yaw(0, 1)), (BARN_S - 0.15, facing_yaw(0, -1))):
        kit_window("Window_Thin_Round1", (BARN.x, y, BARN_EAVE + 0.2), yaw, 1.1, 0.09 / 1.1)
    # Roses up its corners by the doors (narrow ones, clear of them), and on
    # its north wall, facing the gate.
    for x, y, face in ((BARN_W - 0.03, BARN_N - 0.8, (-1, 0)), (BARN_W - 0.03, BARN_S + 0.8, (-1, 0)),
                       (BARN.x - 3.5, BARN_N + 0.03, (0, 1)), (BARN.x + 4.5, BARN_N + 0.03, (0, 1))):
        kind = court_rng.choice(("rose-climber-2", "rose-climber-3"))
        roses_at("rose-climber-3" if face[0] else kind, x, y, g, facing_yaw(*face))
        solid_box(x + face[0] * 0.3, y + face[1] * 0.3, 0.3 if face[0] else 1.6, 1.6 if face[0] else 0.3)
    # Straw blown out of its doors, over the cobbles.
    for _ in range(500):
        r, a = court_rng.uniform(0, 3.4) ** 1.3 / 3.4 ** 0.3, court_rng.uniform(-1.4, 1.4)
        x, y = BARN_W - 0.2 - abs(math.cos(a)) * r, BARN.y + math.sin(a) * r * 1.2
        turn = court_rng.uniform(0, math.pi)
        lx, ly = math.cos(turn) * 0.09, math.sin(turn) * 0.09
        both_ways(court, [(x - lx, y - ly, g + 0.07), (x + lx, y + ly, g + 0.07), (x + ly * 0.15, y - lx * 0.15, g + 0.075)],
                  [(0, 1, 2)], [c.linear(court_rng.choice(("#d8b862", "#c9a24e", "#e6cc7a")))] * 3)

    # Outside it: a cart, barrels and crates, and a water trough.
    # (In full: made simpler, its wheels lose their round. Solid all along it,
    # from its shafts to its tail: its bed is 2 m across, 4 long, in the kit.)
    cart = ((BARN_W - 5.0, BARN_N + 1.8, g), facing_yaw(-0.5, 1), 1.15)
    VILLAGE.put(court, "Prop_Wagon", *cart)
    for along in (-0.5, 0.4, 1.3, 2.2, 3.0):
        solid_circle(*VILLAGE.placing(*cart)((0, along, 0))[:2], 1.15)
    for dx, dy, kind in ((-0.6, -1.0, "Barrel"), (-1.35, -1.5, "Barrel_Apples"), (-0.6, -1.85, "Barrel")):
        PROPS.put(court, kind, (BARN_W + dx, BARN_S - dy, g), court_rng.uniform(0, 6), 1.1, 0.5)
    for dx, dy, z, turn in ((-2.3, 1.2, 0, 0.2), (-2.4, 1.15, 0.88, 0.5)):
        PROPS.put(court, "Crate_Wooden", (BARN_W + dx, BARN_S + dy, g + z), turn, 1.0, 0.3)
    solid_box(BARN_W - 1.4, BARN_S + 1.5, 1.4, 1.2)
    TROUGH = (BARN_W - 0.55, BARN.y + BARN_DOOR + 2.9)
    block(court, TROUGH[0] - 0.4, TROUGH[1] - 1.0, g, TROUGH[0] + 0.4, TROUGH[1] + 1.0, g + 0.62, TIMBER, solid=False)
    quad(court, [(TROUGH[0] - 0.32, TROUGH[1] - 0.92, g + 0.55), (TROUGH[0] + 0.32, TROUGH[1] - 0.92, g + 0.55),
                 (TROUGH[0] + 0.32, TROUGH[1] + 0.92, g + 0.55), (TROUGH[0] - 0.32, TROUGH[1] + 0.92, g + 0.55)],
         c.linear("#3d6f86"), 0.05)
    solid_box(*TROUGH, 0.45, 1.05)

    court.build("courtyard", smooth=False)
    window_glass.build("window-glass", smooth=False)


courtyard()


def coach(b, x, y, f):
    """The red coach, as in its picture (facing west, its pole to the doors):
    a body curved underneath, red, its windows curtained, edged in gold,
    a crest on its door; lamps at its front corners, the driver's seat up in
    front, and four spoked wheels, the back ones bigger."""
    RED_COACH = c.linear("#a3221c")
    GILT = c.linear("#d9a640")
    WHEEL_WOOD = c.linear("#6e4426")
    # The body: its side's outline (along it, up), out to either side.
    outline = [(-0.72, 0.98), (-0.45, 0.8), (0.55, 0.8), (0.98, 0.98), (1.12, 1.45), (1.05, 2.1), (-0.82, 2.1),
               (-0.86, 1.45)]
    half = 0.72
    verts = [(x + u, y - half, f + z) for u, z in outline] + [(x + u, y + half, f + z) for u, z in outline]
    n = len(outline)
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    faces += [(k, (k + 1) % n, n + (k + 1) % n, n + k)[::-1] for k in range(n)]
    b.add(verts, faces, [c.vary(RED_COACH, 0.08, Vector(v) * 4) for v in verts])
    # (Which way round those go: the first face is its side facing -y.)
    # On each side: its windows (in gilt frames, curtained), its door (edged in
    # gilt, its crest on it) and gilt bands along it: each layer standing a
    # little further out from the body than what it's on, or they'd flicker.
    for side in (-1, 1):

        def layer(u0, u1, z0, z1, out, colour, vary=0.05, side=side):
            """A layer on its side, from the body out to `out`."""
            y0, y1 = (half + 0.002, half + out) if side > 0 else (-half - out, -half - 0.002)
            oriented(b, (x, y, f), (1, 0), u0, u1, y0, y1, z0, z1, colour, vary)

        for u0, u1 in ((-0.62, -0.18), (-0.06, 0.38), (0.5, 0.92)):
            layer(u0 - 0.05, u1 + 0.05, 1.38, 2.0, 0.008, GILT)
            layer(u0 + 0.01, u1 - 0.01, 1.44, 1.94, 0.014, c.linear("#3a1420"), 0.04)  # (its edges behind the curtains')
            layer(u0, u0 + 0.1, 1.43, 1.95, 0.02, c.linear("#c83a52"))
            layer(u1 - 0.1, u1, 1.43, 1.95, 0.02, c.linear("#c83a52"))
        layer(-0.1, 0.42, 0.85, 1.34, 0.008, GILT)  # (the door)
        layer(-0.06, 0.38, 0.89, 1.3, 0.014, RED_COACH)
        for z in (2.08, 1.36):
            layer(-0.84, 1.1, z - 0.025, z + 0.025, 0.026, GILT)
        # (Its crest: a round of gilt on the door, facing out.)
        crest_y = y + side * (half + 0.02)
        crest = [(x + 0.16 + math.cos(2 * math.pi * k / 12) * 0.11, crest_y, f + 1.09 + math.sin(2 * math.pi * k / 12) * 0.13)
                 for k in range(12)]
        facing(b, crest, [GILT] * 12, (0, side, 0))
    block(b, x - 0.92, y - half - 0.08, f + 2.1, x + 1.15, y + half + 0.08, f + 2.18, c.linear("#3a1a14"), solid=False)
    for u in (-0.9, -0.3, 0.3, 0.9):
        for side in (-1, 1):
            block(b, x + u - 0.02, y + side * (half + 0.04) - 0.02, f + 2.18, x + u + 0.02, y + side * (half + 0.04) + 0.02,
                  f + 2.36, GILT, solid=False)
    for side in (-1, 1):
        block(b, x - 0.92, y + side * (half + 0.04) - 0.02, f + 2.33, x + 1.12, y + side * (half + 0.04) + 0.02, f + 2.37,
              GILT, solid=False)
    # Its lamps, lit.
    for side in (-1, 1):
        lx, ly = x - 0.9, y + side * (half + 0.1)
        block(b, lx - 0.08, ly - 0.08, f + 1.62, lx + 0.08, ly + 0.08, f + 1.9, c.linear("#3a3532"), solid=False)
        block(b, lx - 0.065, ly - 0.065, f + 1.66, lx + 0.065, ly + 0.065, f + 1.86, c.linear("#ffd27a"), solid=False)
        b.cone((lx, ly, f + 1.9), 0.12, 0.1, c.linear("#3a3532"), sides=4, droop=0)
    # The undercarriage, the driver's seat and footboard, and the pole.
    timber(b, (x - 1.25, y, f + 0.62), (x + 1.2, y, f + 0.72), 0.14, c.linear("#3a2416"))
    for ax_, az in ((-1.2, 0.6), (1.1, 0.78)):
        timber(b, (x + ax_, y - 1.0, f + az), (x + ax_, y + 1.0, f + az), 0.1, c.linear("#2a2522"))
        timber(b, (x + ax_, y, f + az), (x + ax_ * 0.65, y, f + 0.85), 0.1, c.linear("#3a2416"))
    block(b, x - 1.5, y - 0.62, f + 1.5, x - 0.9, y + 0.62, f + 1.68, c.linear("#5a1814"), solid=False)
    block(b, x - 1.0, y - 0.62, f + 1.68, x - 0.9, y + 0.62, f + 2.0, c.linear("#5a1814"), solid=False)
    timber(b, (x - 1.85, y, f + 1.1), (x - 1.4, y, f + 1.15), 0.08, c.linear("#3a2416"), 1.1)
    timber(b, (x - 1.4, y, f + 1.15), (x - 1.2, y, f + 0.6), 0.1, c.linear("#3a2416"))
    timber(b, (x - 1.2, y, f + 0.6), (x - 3.4, y, f + 0.12), 0.09, c.linear("#3a2416"))
    # The wheels: rims, spokes and hubs.
    for wx_, r in ((-1.2, 0.6), (1.1, 0.78)):
        for side in (-1, 1):
            cx_, cy_, cz = x + wx_, y + side * 0.98, f + r
            rim = [(cx_ + math.cos(2 * math.pi * k / 20) * r, cy_, cz + math.sin(2 * math.pi * k / 20) * r) for k in range(20)]
            for k in range(20):
                timber(b, rim[k], rim[(k + 1) % 20], 0.07, WHEEL_WOOD, 0.07)
                timber(b, rim[k], rim[(k + 1) % 20], 0.035, c.linear("#2a2522"), 0.09)
            for k in range(12):
                a = 2 * math.pi * k / 12
                timber(b, (cx_ + math.cos(a) * 0.1, cy_, cz + math.sin(a) * 0.1),
                     (cx_ + math.cos(a) * (r - 0.04), cy_, cz + math.sin(a) * (r - 0.04)), 0.035, c.linear("#c08a40"))
            log(b, (cx_, cy_ - 0.12, cz), (cx_, cy_ + 0.12, cz), 0.1, c.linear("#3a2416"), sides=8)


def hay_bale(b, x, y, z, turn, rnd):
    """A bale of hay, tied with twine."""
    across = (math.cos(turn), math.sin(turn))
    straw = c.mix(c.linear("#d6b25a"), c.linear("#b8923c"), rnd.uniform(0, 1))
    oriented(b, (x, y, z), across, -0.55, 0.55, -0.28, 0.28, 0, 0.45, straw, 0.12)
    for u in (-0.25, 0.25):
        oriented(b, (x, y, z), across, u - 0.02, u + 0.02, -0.285, 0.285, -0.005, 0.455, c.linear("#6a5030"), 0.05)


def coach_house(b, hall):
    """Inside the coach house, as in its picture: its walls boards between oak
    posts and beams, and open up to its roof, tie beams across under it;
    the red coach on the straw, hay stacked in the corner, barrels, crates
    and sacks, tack and a horse's collar on pegs, a shelf of pots, a cart
    wheel against the wall, a lantern hung from a beam, and Merlin's
    cloak, blue with silver stars (a button missing), hanging on the back wall."""
    hx, hy, f, W, D = hall.x, hall.y, hall.floor, hall.w, hall.d
    rnd = random.Random("coach house inside")
    E = ROOM_EDGE
    x0, x1, y0, y1 = hx - W - E, hx + W + E, hy - D - E, hy + D + E
    # Its walls, inside: boards, on the shell (faces to the room).
    inner = [((x0, y1), (x0, y0), [((y1 - hy) - BARN_DOOR, (y1 - hy) + BARN_DOOR, -1, BARN_DOOR_TOP)]),
             ((x0, y0), (x1, y0), []), ((x1, y0), (x1, y1), []), ((x1, y1), (x0, y1), [])]
    for p0, p1, holes in inner:
        # (Facing in: walking it the other way round, its right is the room.)
        q0, q1 = p1, p0
        gable = abs(p1[1] - p0[1]) < 0.01
        length = math.hypot(q1[0] - q0[0], q1[1] - q0[1])
        ux = (q1[0] - q0[0]) / length
        flipped = [(length - e, length - a, lo, hi) for a, e, lo, hi in holes]

        def top(t, ax=q0[0], ux=ux, gable=gable):
            return roof_line(ax + ux * t) - 0.08 if gable else BARN_EAVE + 0.3

        barn_wall(b, q0, q1, top, flipped, inside=True)
        barn_frame(b, q0, q1, [0.2, length / 3, 2 * length / 3, length - 0.2] if not flipped else
                   [0.2, flipped[0][0] - 0.2, flipped[0][1] + 0.2, length - 0.2], flipped, 0.14)
    # Tie beams across under the roof, a post up from each to the ridge,
    # and struts.
    for k in range(4):
        y = y0 + 0.2 + k * (y1 - y0 - 0.4) / 3
        timber(b, (x0, y, BARN_EAVE - 0.15), (x1, y, BARN_EAVE - 0.15), 0.3, TIMBER, 0.34)
        timber(b, (hx, y, BARN_EAVE), (hx, y, BARN_RIDGE - 0.35), 0.26, TIMBER)
        for side in (-1, 1):
            timber(b, (hx + side * 0.15, y, BARN_EAVE + 0.1), (hx + side * 4.2, y, roof_line(hx + side * 4.2) - 0.25), 0.18,
                 TIMBER)
    # Loose straw all over the floor (thick where it's straw, and thin over the flags).
    for _ in range(2600):
        x, y = rnd.uniform(x0 + 0.2, x1 - 0.2), rnd.uniform(y0 + 0.2, y1 - 0.2)
        if rnd.random() > 0.2 + 0.8 * smooth((noise.noise(Vector((x / 3, y / 3, 12.0))) + 0.35) / 0.5):
            continue
        turn = rnd.uniform(0, math.pi)
        lx, ly = math.cos(turn) * 0.1, math.sin(turn) * 0.1
        z = f - 0.05 + rnd.uniform(0.0, 0.03)
        b.add([(x - lx, y - ly, z), (x + ly * 0.2, y - lx * 0.2, z), (x + lx, y + ly, z)], [(0, 1, 2)],
              [c.linear(rnd.choice(("#e0c06a", "#c9a24e", "#ecd488", "#b8923c")))] * 3)
    # The coach, half as big again as it's made (as grand as in its picture),
    # by the south wall (room to walk round it: 1.4 m clear of the wall's
    # posts), its pole towards the doors; solid from its front wheels to its
    # back ones (its pole, lying low, you can step over).
    COACH_SIZE = 1.5
    made = c.Builder()
    coach(made, 0, 0, 0)
    cx_, cy_ = hx + 0.6, y0 + 0.3 + 1.4 + 1.1 * COACH_SIZE
    b.add([(cx_ + px * COACH_SIZE, cy_ + py * COACH_SIZE, f + pz * COACH_SIZE) for px, py, pz in made.verts], made.faces,
          made.colours)
    under_box(cx_ - 0.03 * COACH_SIZE, cy_, 1.98 * COACH_SIZE, 1.1 * COACH_SIZE, top=f + 2.4 * COACH_SIZE)
    # A lantern hung from a beam, lit.
    ly = y0 + 0.2 + (y1 - y0 - 0.4) / 3
    log(b, (hx + 1.0, ly, BARN_EAVE - 0.32), (hx + 1.0, ly, BARN_EAVE - 1.3), 0.012, IRON, sides=4)
    block(b, hx + 0.88, ly - 0.12, BARN_EAVE - 1.65, hx + 1.12, ly + 0.12, BARN_EAVE - 1.3, c.linear("#3a3532"), solid=False)
    flame(b, hx + 1.0, ly, BARN_EAVE - 1.6, 0.2)
    # Hay: bales stacked in the north-east corner, and loose straw heaped about.
    for k, (u, v, z, turn) in enumerate(((6.9, 5.6, 0, 0), (5.75, 5.6, 0, 0), (7.4, 4.3, 0, math.pi / 2),
                                          (6.3, 5.55, 0.45, 0.05), (7.35, 4.4, 0.45, math.pi / 2), (6.8, 5.0, 0.9, 0.3))):
        hay_bale(b, hx + u, hy + v, f + z, turn, rnd)
    under_box(hx + 6.6, hy + 5.0, 1.6, 1.3, top=f + 1.35)
    for k, (u, v, r) in enumerate(((5.3, 4.2, 1.1), (7.0, -4.9, 1.2), (-3.2, 5.2, 0.9))):
        b.blob((hx + u, hy + v, f + 0.25), r, c.linear("#d6b25a"), squash=0.45, lumpy=0.35, seed=30 + k)
        under_circle(hx + u, hy + v, r * 0.85)
    # Barrels, crates and sacks in the south-west corner, by the doors.
    for u, v, kind in ((-7.4, -5.5, "Barrel"), (-6.6, -5.6, "Barrel"), (-7.3, -4.7, "Barrel_Apples")):
        PROPS.put(b, kind, (hx + u, hy + v, f), rnd.uniform(0, 6), 1.1, 0.5)
        under_circle(hx + u, hy + v, 0.42)
    for u, v, z in ((7.5, -2.8, 0.0), (7.5, -2.8, 0.88), (7.4, -1.9, 0.0)):
        PROPS.put(b, "Crate_Wooden", (hx + u, hy + v, f + z), rnd.uniform(-0.2, 0.2), 1.0, 0.5)
    under_box(hx + 7.45, hy - 2.35, 0.5, 0.95, top=f + 1.8)
    PROPS.put(b, "Rope_1", (hx + 7.5, hy - 2.8, f + 1.76), 0.3, 1.2, 0.4)
    for u, v in ((-5.8, -5.9), (-5.3, -5.7)):
        PROPS.put(b, "Bag", (hx + u, hy + v, f), rnd.uniform(0, 6), 1.2, 0.5)
    # Tack on pegs, and a horse's collar, on the north wall; a shelf of pots.
    # (Facing into the room, between the wall's posts: at hx -2.8 and +2.8.)
    wall_y = y1 - 0.04
    PROPS.put(b, "Peg_Rack", (hx - 5.0, wall_y, f + 2.2), 0.0, 1.4, 0.6)
    for k, u in enumerate((-5.65, -5.2, -4.75, -4.3)):
        for d in (-0.06, 0.06):
            timber(b, (hx + u + d, wall_y - 0.12, f + 2.15), (hx + u + d * 3, wall_y - 0.1, f + 1.2 - 0.15 * (k % 2)), 0.03,
                   c.linear("#4a2c18"), 0.012)
    collar = (hx - 0.9, wall_y - 0.12, f + 1.75)
    for k in range(14):
        a0, a1 = 2 * math.pi * k / 14, 2 * math.pi * (k + 1) / 14
        p0 = (collar[0] + math.cos(a0) * 0.36, collar[1], collar[2] + math.sin(a0) * 0.46)
        p1 = (collar[0] + math.cos(a1) * 0.36, collar[1], collar[2] + math.sin(a1) * 0.46)
        timber(b, p0, p1, 0.12, c.linear("#5a3a22"), 0.1)
    PROPS.put(b, "Shelf_Simple", (hx + 0.9, wall_y, f + 2.9), 0.0, 1.4, 0.6)
    for u, kind in ((0.4, "Pot_1"), (0.85, "Vase_2"), (1.3, "Pot_1"), (1.5, "Bottle_1")):
        PROPS.put(b, kind, (hx + u, wall_y - 0.25, f + 2.9 + 0.11 * 1.4 + 0.01), rnd.uniform(0, 6), 1.0, 0.4)
    # A cart wheel, leaning on the south wall (past the coach).
    wc = (hx + 5.0, y0 + 0.3, f + 0.7)
    lean = 0.2
    rim = [(wc[0] + math.cos(2 * math.pi * k / 18) * 0.7, wc[1] + math.sin(2 * math.pi * k / 18) * 0.7 * math.sin(lean) + 0.0,
            wc[2] + math.sin(2 * math.pi * k / 18) * 0.7 * math.cos(lean)) for k in range(18)]
    for k in range(18):
        timber(b, rim[k], rim[(k + 1) % 18], 0.08, c.linear("#5e3b1f"), 0.08)
    for k in range(10):
        timber(b, wc, rim[(k * 18) // 10], 0.04, c.linear("#7a5232"))
    under_box(wc[0], wc[1] + 0.1, 0.75, 0.2)
    # Merlin's cloak, on a peg on the back wall, facing the doors: deep blue,
    # hooded, folds falling to its hem, scattered with silver stars, silver
    # buttons down its front (one missing).
    cloak(b, x1 - 0.05, hy + 1.4, f + 3.3)


def cloak(b, x, y, top):
    """Merlin's cloak, hanging from a peg on a wall (facing -x)."""
    BLUE = c.linear("#22306e")
    log(b, (x, y, top + 0.02), (x - 0.2, y, top + 0.05), 0.035, DARK_WOOD)
    rows, cols = 10, 12
    pts, colours = [], []
    for i in range(rows + 1):
        t = i / rows
        z = top - 0.05 - t * 2.1
        half = 0.3 + 0.55 * t ** 0.8
        for j in range(cols + 1):
            s = j / cols * 2 - 1
            fold = 0.07 * math.sin(s * math.pi * 3 + 0.5) * t
            out = 0.12 + 0.18 * (1 - s * s) * (0.4 + 0.6 * t) + fold
            pts.append((x - out, y + s * half, z))
            light = 0.8 + 0.25 * math.sin(s * math.pi * 3 + 0.5)
            colours.append(c.mix(BLUE, c.linear("#000000"), 0.25 * (1 - light)) if light < 1 else
                           c.mix(BLUE, c.linear("#6a7ac8"), (light - 1) * 0.8))
    faces = [(i * (cols + 1) + j, i * (cols + 1) + j + 1, (i + 1) * (cols + 1) + j + 1, (i + 1) * (cols + 1) + j)
             for i in range(rows) for j in range(cols)]
    b.add(pts, faces, colours)
    # Its hood, folded back over its shoulders.
    b.blob((x - 0.2, y, top - 0.2), 0.28, BLUE, squash=0.8, lumpy=0.2, seed=5)
    # Stars, and its buttons (the third one gone).
    rnd = random.Random("merlin's cloak")
    for _ in range(26):
        i, j = rnd.randint(1, rows - 1), rnd.randint(1, cols - 1)
        px, py, pz = pts[i * (cols + 1) + j]
        r = 0.045
        star = [(px - 0.02, py + math.cos(2 * math.pi * k / 10) * r * (1 if k % 2 == 0 else 0.45),
                 pz + math.sin(2 * math.pi * k / 10) * r * (1 if k % 2 == 0 else 0.45)) for k in range(10)]
        b.add([(px - 0.02, py, pz)] + star, [(0, 1 + k, 1 + (k + 1) % 10)[::-1] for k in range(10)],
              [c.linear("#e8ecf4")] * 11)
    for k in range(5):
        if k == 2:
            continue
        pz = top - 0.35 - k * 0.32
        b.blob((x - 0.32, y, pz), 0.035, c.linear("#d8dce4"), squash=0.6, lumpy=0.0, seed=k, subdivisions=1)


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
# The two locked doors across the ways south, the oak door's and the giant's
# iron gate: each its own object, on its hinge at one of the way's walls, which
# the game swings open (south, away from its hall) and shut again. Each hangs
# below where the roof starts to curve in (so, opening, it clears the roof),
# under a fixed piece filling the arch over it: oak boards over the door, bars
# over the gate. (Each object's origin is its hinge, at the door's south face
# and its foot: swinging, it never goes into the post it hangs on.)
DOOR_IN = 0.08  # its hinge, in from the way's wall
DOOR_TALL = 2.15  # its height, under the roof's curve
DOOR_WIDE = 2 * (TUNNEL_HALF - DOOR_IN) - 0.02
OLD_OAK = c.linear("#6b4a2c")
DOOR_IRON = c.linear("#242325")
BRASS = c.linear("#a8823a")
KEYHOLE = c.linear("#0a0806")
STEEL = c.linear("#a19d94")


def strap(b, x0, x1, z, y0, y1, studs=True):
    """A door's iron strap across it, from x0 to x1, with studs along it."""
    block(b, x0, y0, z - 0.045, x1, y1, z + 0.045, DOOR_IRON, solid=False)
    out = y1 - y0
    for k in range(int((x1 - x0) / 0.28) + 1 if studs else 0):
        x = x0 + 0.1 + k * 0.28
        if x < x1 - 0.05:
            near = y1 if y1 > y0 else y0
            block(b, x - 0.018, near - out * 0.1, z - 0.018, x + 0.018, near + out * 0.6, z + 0.018, DOOR_IRON,
                  solid=False)


def ring_handle(b, x, y, z, out):
    """A ring to pull it by, hanging from a round plate: out (+1 or -1) is
    which face it's on."""
    block(b, x - 0.06, y, z - 0.06, x + 0.06, y + out * 0.015, z + 0.06, DOOR_IRON, solid=False)
    block(b, x - 0.015, y, z - 0.015, x + 0.015, y + out * 0.05, z + 0.015, DOOR_IRON, solid=False)
    r, t = 0.075, 0.014
    for k in range(10):
        a0, a1 = 2 * math.pi * k / 10, 2 * math.pi * (k + 1) / 10
        p0 = (x + r * math.sin(a0), z - r + r * math.cos(a0))
        p1 = (x + r * math.sin(a1), z - r + r * math.cos(a1))
        xs, zs = sorted((p0[0], p1[0])), sorted((p0[1], p1[1]))
        block(b, xs[0] - t, y + out * 0.04, zs[0] - t, xs[1] + t, y + out * 0.065, zs[1] + t, DOOR_IRON, solid=False)


# The oak door: old planks, dark seams between them, iron straps from its
# hinges across both faces, studded, a ring to pull it by and a keyhole.
oy = O[1] - HALLS["oak-door"].r - 1.2
ox0, ox1 = O[0] - TUNNEL_HALF, O[0] + TUNNEL_HALF
for x0, x1 in ((ox0 - 0.3, ox0 + DOOR_IN), (ox1 - DOOR_IN - 0.02, ox1 + 0.3)):
    block(cave_made, x0, oy - 0.14, CAVE, x1, oy + 0.14, CAVE + DOOR_TALL + 0.05, OAK, solid=False)  # its posts
block(cave_made, ox0 - 0.3, oy - 0.16, CAVE + DOOR_TALL + 0.02, ox1 + 0.3, oy + 0.16, CAVE + DOOR_TALL + 0.3, OAK,
      solid=False)  # the beam over it
for k in range(9):
    x0 = ox0 - 0.3 + k * (ox1 - ox0 + 0.6) / 9
    block(cave_made, x0 + 0.01, oy - 0.07, CAVE + DOOR_TALL + 0.3, x0 + (ox1 - ox0 + 0.6) / 9 - 0.01, oy + 0.07,
          CAVE + TUNNEL_TALL + 0.3, c.vary(OAK, 0.2, Vector((k, 1.7, 0))), solid=False)  # the boards over it
block(cave_made, ox0, oy - 0.05, CAVE + DOOR_TALL + 0.3, ox1, oy + 0.05, CAVE + TUNNEL_TALL + 0.3, KEYHOLE,
      solid=False)  # (dark, between them)
oak_leaf = c.Builder()
THICK = 0.12  # its thickness
PLANKS = 6
block(oak_leaf, 0.02, 0.012, 0.01, DOOR_WIDE - 0.02, THICK - 0.012, DOOR_TALL - 0.01, KEYHOLE, solid=False)  # (the seams)
for k in range(PLANKS):
    x0, x1 = k * DOOR_WIDE / PLANKS, (k + 1) * DOOR_WIDE / PLANKS
    shade = c.mix(c.vary(OLD_OAK, 0.25, Vector((k * 1.3, 4, 2))), c.linear("#3a2a1c"), 0.15 * (k % 2))
    block(oak_leaf, x0 + 0.008, 0, 0, x1 - 0.008, THICK, DOOR_TALL - 0.004 * (k % 3), shade, solid=False)
for z in (0.42, DOOR_TALL - 0.42):
    strap(oak_leaf, -0.02, DOOR_WIDE * 0.8, z, THICK, THICK + 0.014)  # (its north face)
    strap(oak_leaf, -0.02, DOOR_WIDE * 0.8, z, 0, -0.014)  # (and its south)
for y, face in ((THICK, 1), (0, -1)):
    ring_handle(oak_leaf, DOOR_WIDE - 0.32, y, 1.12, face)
    block(oak_leaf, DOOR_WIDE - 0.36, y, 0.82, DOOR_WIDE - 0.28, y + face * 0.012, 0.96, DOOR_IRON, solid=False)
    block(oak_leaf, DOOR_WIDE - 0.33, y + face * 0.012, 0.85, DOOR_WIDE - 0.31, y + face * 0.016, 0.91, KEYHOLE, solid=False)
oak_leaf.build("oak-door-leaf", smooth=False).location = (ox0 + DOOR_IN, oy - THICK / 2, CAVE)
obstacle(["oak-door south"], "box", O[0], -oy, TUNNEL_HALF + 0.3, 0.5, under=True)  # the oak door, locked
gx = G[0] - HALLS["giant"].r - 1.5
obstacle(["giant west"], "box", gx, -G[1], 1.0, TUNNEL_HALF + 0.3, under=True,
         reach=7.5)  # the giant, by the way (you bump into it while he's still in view, shaking his head)
# The giant's iron gate: bars and rails, between iron posts at the walls, with
# more bars fixed over it, up into the roof; padlocked, on the hall's side, to
# a staple on the west post, its hinges on the east one (the padlock, brass, stays there, its shackle its
# own object, steel, which the game springs open with the key).
gy = G[1] - HALLS["giant"].r - 1.2
gx0, gx1 = G[0] - TUNNEL_HALF, G[0] + TUNNEL_HALF
BARS = 11
for x0, x1 in ((gx0 - 0.2, gx0 + DOOR_IN), (gx1 - DOOR_IN - 0.02, gx1 + 0.2)):
    block(cave_made, x0, gy - 0.08, CAVE, x1, gy + 0.08, CAVE + DOOR_TALL + 0.05, IRON, solid=False)  # its posts
block(cave_made, gx0 - 0.2, gy - 0.08, CAVE + DOOR_TALL + 0.03, gx1 + 0.2, gy + 0.08, CAVE + DOOR_TALL + 0.18, IRON,
      solid=False)  # the rail over it
block(cave_made, gx0, gy - 0.08, CAVE + TUNNEL_TALL - 0.2, gx1, gy + 0.08, CAVE + TUNNEL_TALL - 0.05, IRON, solid=False)
for k in range(BARS):
    x = gx0 + DOOR_IN + 0.05 + k * (DOOR_WIDE - 0.1) / (BARS - 1)
    block(cave_made, x - 0.05, gy - 0.05, CAVE + DOOR_TALL + 0.18, x + 0.05, gy + 0.05, CAVE + TUNNEL_TALL + 0.3, IRON,
          solid=False)  # (the bars over it, in line with its own)
gate_leaf = c.Builder()
THICK = 0.16  # its thickness, at its rails
for k in range(BARS):
    x = -0.05 - k * (DOOR_WIDE - 0.1) / (BARS - 1)  # (out west from its hinge)
    block(gate_leaf, x - 0.05, THICK / 2 - 0.05, 0, x + 0.05, THICK / 2 + 0.05, DOOR_TALL, IRON, solid=False)
for z in (0.25, 1.15, DOOR_TALL - 0.15):
    block(gate_leaf, -DOOR_WIDE, 0, z, 0, THICK, z + 0.15, IRON, solid=False)
# (A hasp on its end, for the padlock's shackle to go through, at the post's staple.)
block(gate_leaf, -DOOR_WIDE - 0.01, THICK, 1.17, -DOOR_WIDE + 0.1, THICK + 0.08, 1.25, IRON, solid=False)
gate_leaf.build("iron-gate-leaf", smooth=False).location = (gx1 - DOOR_IN, gy - THICK / 2, CAVE)
lock_x, lock_y, lock_z = gx0 + DOOR_IN + 0.01, gy + THICK / 2 + 0.07, CAVE + 1.0  # the padlock's middle, on the hall's side
block(cave_made, lock_x - 0.035, gy + 0.08, lock_z + 0.15, lock_x + 0.015, lock_y, lock_z + 0.24, IRON, solid=False)  # the staple
block(cave_made, lock_x - 0.075, lock_y - 0.03, lock_z - 0.09, lock_x + 0.075, lock_y + 0.03, lock_z + 0.09, BRASS, solid=False)  # its body
block(cave_made, lock_x - 0.016, lock_y + 0.03, lock_z - 0.01, lock_x + 0.016, lock_y + 0.036, lock_z + 0.035, KEYHOLE, solid=False)  # keyhole
block(cave_made, lock_x - 0.006, lock_y + 0.03, lock_z - 0.05, lock_x + 0.006, lock_y + 0.036, lock_z - 0.01, KEYHOLE, solid=False)
shackle = c.Builder()
for x0, x1, z0, z1 in ((-0.015, 0.015, -0.07, 0.13), (0.085, 0.115, -0.01, 0.13), (-0.015, 0.115, 0.11, 0.145)):
    block(shackle, x0, -0.015, z0, x1, 0.015, z1, STEEL, solid=False)  # (one leg longer, deep in it: lifted, it stays in on that one)
shackle.build("padlock-shackle", smooth=False).location = (lock_x - 0.05, lock_y, lock_z + 0.09)
obstacle(["giant south"], "box", G[0], -gy, TUNNEL_HALF + 0.3, 0.5, under=True)  # the padlocked gate
dy = DC[1] - HALLS["dragon-cave"].r - 1.5
obstacle(["dragon-cave south"], "box", DC[0], -dy, TUNNEL_HALF + 0.3, 1.0, under=True)  # the dragon's fire
for x, y, r in dragon_shape():
    under_circle(x, y, r)  # (the dragon itself)
ky = DK[1] - HALLS["dark-tunnels"].r - 1.5
obstacle(["dark-tunnels south"], "box", DK[0], -ky, TUNNEL_HALF + 0.3, 1.0, under=True)  # too dark to go on
caves.build("caves", smooth=False)
cave_made.build("cave-made", smooth=False)
gilding.build("gilding", smooth=False)
brazier_flames.build("brazier-flames", smooth=False)
hoard_jewels.build("hoard-jewels", smooth=False)
flute_model.build("flute", smooth=False).location = (BC[0], BC[1], HALLS["beautiful-chamber"].floor + 1.4)
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
    # (And the archway's wall, and the stones fallen from it, lying in the open.)
    if ARCH_ENDS[0] - 0.5 <= x <= ARCH_ENDS[1] + 0.5:
        to_wall = min(to_wall, abs(y - ARCH_Y))
    if any(math.hypot(x - sx, y - sy) < size * 0.5 + 0.35 for sx, sy, size in placed):
        return 0
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
        "leaves": {"at": [round(LEAVES[0], 2), round(-LEAVES[1], 2)], "heaps": [[round(x, 2), round(-y, 2)] for x, y in LEAF_HEAPS]},
        # The dragon: where it stands [x, z] and its floor, which way it faces [x, z], and where it breathes its
        # fire, across the mouth of the tunnel south [x, y, z].
        # The trolls: where each sits [x, z] and its floor, which way it faces [x, z], and how big it is; and
        # where the drum is [x, z] (beside the one with it).
        "trolls": {"sitting": [{"at": [round(x, 2), round(-y, 2), HALLS["trolls"].floor],
                                "facing": [round(fx, 3), round(-fy, 3)], "size": size}
                               for (x, y), (fx, fy), size in troll_spots()],
                   "drum": TROLL_DRUM},
        # The giant: where he sits [x, z] and his floor, which way he faces [x, z], and how big he is.
        "giant": {"at": [round(giant_spot()[0][0], 2), round(-giant_spot()[0][1], 2), HALLS["giant"].floor],
                  "facing": [round(giant_spot()[1][0], 3), round(-giant_spot()[1][1], 3)], "size": GIANT_SIZE},
        "dragon": {"at": [round(DRAGON_AT[0], 2), round(-DRAGON_AT[1], 2), HALLS["dragon-cave"].floor],
                   "facing": [round(math.sin(DRAGON_YAW), 3), round(math.cos(DRAGON_YAW), 3)],
                   "fire": [DC[0], HALLS["dragon-cave"].floor, round(-(DC[1] - HALLS["dragon-cave"].r + 1), 2)]},
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
        # The bridges' decks, for walking on at exactly their height: [x, z, half x, half z, top].
        "decks": [[round(x, 2), round(-y, 2), round(hx, 2), round(hy, 2), top] for x, y, hx, hy, top in DECKS],
        # Floors over the ground, for lying on: [x, z, half x, half z, how far up]. (The maze's.)
        "floors": [[round(MZ[0], 2), round(-MZ[1], 2), round(MAZE_HALF, 2), round(MAZE_HALF, 2), MAZE_FLOOR],
                   [round((YARD[0] + YARD[1]) / 2, 2), round(-(YARD[2] + YARD[3]) / 2, 2), round((YARD[1] - YARD[0]) / 2, 2),
                    round((YARD[3] - YARD[2]) / 2, 2), 0.05]],  # (and the courtyard's cobbles)
        # The paths, lying a little above the ground (so what's dropped on
        # one lies on it, not in it): each its line [x, z], in three.js's
        # axes, how far either side of it it goes, and how far up it is.
        "paths": [{"half": round(REACH * 1.1, 2), "lift": PATH_LIFT,
                   "points": [[round(x, 2), round(-y, 2)] for x, y in line]} for k, line in enumerate(paths)],
    }, separators=(",", ":")))
    print(f"Exported {out}: {len(circles)} solid circles, {len(boxes)} boxes, {len(obstacles)} obstacles")
if preview:
    c.preview(preview, (60, -120, 160), (0, -20, 0), (-0.7, 0.5, -0.45), lens=20)
