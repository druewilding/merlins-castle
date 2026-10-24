# The dragon in its cave, by the tunnel south: a splendid dragon, as in its
# picture, crimson and rose, its scales darker down its back and paler
# across its belly, a row of spines from its horns to the tip of its tail,
# great bat's wings raised, and a long neck up to a horned head that reaches
# the cave's roof.
#
# It stands on the ground at z = 0, facing -y, on four legs, its tail curled
# round on the ground to its right. It has its own skeleton, made here: the
# game moves its bones itself (no clips), so it can look at you, breathe
# fire where it likes, and sway its tail. Its bones:
#
#   body                the hips to the chest, and its legs (still)
#   tail-1 .. tail-6    from its hips to the tip of its tail
#   neck-1 .. neck-5    from its chest up to its head
#   head, jaw           the jaw on its hinge, under the head
#   mouth               (nothing on it) where the fire comes out, and which way
#   arm-l, fore-l, ...  each wing: from the shoulder to the elbow, and from
#                       the elbow out to the wrist and its fingers
#
# Its meshes: "dragon" (its body, with its head, legs, horns and spines),
# "dragon-wings" (the thin skin between the bones of its wings, which the
# game lets the firelight through) and "dragon-eyes" (which glow).

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector, noise

HERE = Path(__file__).parent
sys.path.append(str(HERE))
import common as c  # noqa: E402

out, preview = c.args()
c.clear()

SCALE = 0.11  # metres across each of its scales (a little smaller on its head)
TALL = 7.9  # metres, from its feet to the top of its horns (made bigger, then scaled to this: see the end)
STEP = 0.1  # metres between the rings round its body
AROUND = 22  # points round each ring

# Its colours (as in the picture: crimson, rose and a pinkish orange).
BACK = c.linear("#521030")
SIDE = c.linear("#a0244c")
ROSE = c.linear("#c44a6e")
BELLY = c.linear("#e0906a")
SEAM = c.linear("#9a4a44")
WING = c.linear("#b0447a")
VEIN = c.linear("#6a1840")
SPAR = c.linear("#6e1a3e")
SPINE = c.linear("#4a0e2a")
HORN = c.linear("#e6d2ae")
HORN_TIP = c.linear("#7a6a52")
CLAW = c.linear("#2a1814")
TOOTH = c.linear("#f2ead6")
GUMS = c.linear("#5a0c16")
THROAT = c.linear("#2a0408")
EYE = c.linear("#ffc23a")
PUPIL = c.linear("#1a0804")


def smooth(t):
    return c.smooth(t)


def lerp(a, b, t):
    return a + (b - a) * t


# ---- Curves and tubes -------------------------------------------------------


def spline(points, step=STEP):
    """Points (each a position and whatever numbers go with it: radii) joined
    by a smooth curve through them (Catmull-Rom; the numbers eased from one
    to the next), every `step` metres along it. Each sample: its position,
    its numbers, and how far along the curve it is."""
    ps = [Vector(p[0]) for p in points]
    dense = []
    for i in range(len(ps) - 1):
        p0, p1, p2, p3 = ps[max(0, i - 1)], ps[i], ps[i + 1], ps[min(len(ps) - 1, i + 2)]
        for k in range(40):
            t = k / 40
            t2, t3 = t * t, t * t * t
            at = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            values = [lerp(a, b, smooth(t)) for a, b in zip(points[i][1:], points[i + 1][1:])]
            dense.append((at, values, i + t))
    dense.append((ps[-1], list(points[-1][1:]), len(ps) - 1))
    # (Evenly spaced along it.)
    along = [0.0]
    for a, b in zip(dense, dense[1:]):
        along.append(along[-1] + (b[0] - a[0]).length)
    total = along[-1]
    count = max(2, round(total / step) + 1)
    samples, j = [], 0
    for k in range(count):
        s = total * k / (count - 1)
        while j < len(dense) - 2 and along[j + 1] < s:
            j += 1
        span = along[j + 1] - along[j] or 1
        t = (s - along[j]) / span
        at = dense[j][0].lerp(dense[j + 1][0], t)
        values = [lerp(a, b, t) for a, b in zip(dense[j][1], dense[j + 1][1])]
        samples.append((at, values, s, lerp(dense[j][2], dense[j + 1][2], t)))
    return samples


def frames(samples, up):
    """For each sample of a curve: which way it goes, and which way is up (its
    back) and across (its side), turning no more than the curve does
    (rotation-minimising, from `up` at its start)."""
    out = []
    for k, (at, _, _, _) in enumerate(samples):
        nxt = samples[min(k + 1, len(samples) - 1)][0]
        prv = samples[max(k - 1, 0)][0]
        tangent = (nxt - prv).normalized()
        if not out:
            u = (Vector(up) - tangent * tangent.dot(Vector(up))).normalized()
        else:
            t0, u0 = out[-1][0], out[-1][1]
            # (Double reflection: Wang et al.)
            v1 = at - samples[k - 1][0]
            c1 = v1.dot(v1) or 1e-9
            rl = u0 - (2 / c1) * v1.dot(u0) * v1
            tl = t0 - (2 / c1) * v1.dot(t0) * v1
            v2 = tangent - tl
            c2 = v2.dot(v2) or 1e-9
            u = (rl - (2 / c2) * v2.dot(rl) * v2).normalized()
        out.append((tangent, u, tangent.cross(u).normalized()))
    return out


def tube(build, samples, fs, colour, weight, around=AROUND, start_cap=True, end_cap=True, shape=None, scaly=None):
    """A tube along a curve's samples, each ring as wide and as tall as its
    first two numbers (half-widths). colour(sample, a) and weight(sample)
    for each point (a: round it, from its back, 0, to its belly, pi); shape
    (sample, a), how far out each point is, of the ring's radius. Scaly
    ("belly": scales but for its belly; "all": all round), it says where
    each point is, for the game to draw its scales (Skinned)."""
    verts, colours, weights, faces = [], [], [], []
    rounds, alongs = [], []
    for sample, (t, u, x) in zip(samples, fs):
        at, values, s, _ = sample
        w, h = values[0], values[1]
        for j in range(around):
            a = 2 * math.pi * j / around
            r = shape(sample, a) if shape else 1.0
            p = at + x * (math.sin(a) * w * r) + u * (math.cos(a) * h * r)
            verts.append(tuple(p))
            colours.append(colour(sample, a, p))
            weights.append(weight(sample))
            rounds.append((math.cos(a), math.sin(a)))
            # (Each scale lies over the one before it, along the tube: its
            # body from its tail to its head; its legs, down from its body.)
            alongs.append((s / SCALE * (1 if scaly == "belly" else -1), (w + h) / 2 * r / SCALE * (1 if scaly == "belly" else -1)))
    n = len(samples)
    faces += [(k * around + j, (k + 1) * around + j, (k + 1) * around + (j + 1) % around, k * around + (j + 1) % around)
              for k in range(n - 1) for j in range(around)]
    for cap, k, sign in ((start_cap, 0, -1), (end_cap, n - 1, 1)):
        if not cap:
            continue
        at, values, s, _ = samples[k]
        tip = len(verts)
        verts.append(tuple(at + fs[k][0] * sign * min(values[0], values[1]) * 0.5))
        colours.append(colours[k * around])
        weights.append(weight(samples[k]))
        rounds.append((1.0, 0.0))
        alongs.append((0.0, 0.0))
        for j in range(around):
            a, b = k * around + j, k * around + (j + 1) % around
            faces.append((tip, a, b) if sign > 0 else (tip, b, a))
    build.put(verts, faces, colours, weights, (rounds, alongs) if scaly else None)


class Skinned(c.Builder):
    """A builder that keeps each point's bone weights as well, and where it
    is on its scales: which way round its tube (or its head) it is, as a
    cosine and a sine (so they blend smoothly all the way round), and how
    far along it, and how big round it is there, both counted in scales
    (round 0: no scales; less than 0, scales all round, more, but for its
    belly). Exported as its two sets of UVs."""

    def __init__(self):
        super().__init__()
        self.weights = []
        self.rounds, self.alongs = [], []

    def put(self, verts, faces, colours, weights, scales=None):
        self.add(verts, faces, colours)
        self.weights += weights if isinstance(weights, list) else [weights] * len(verts)
        rounds, alongs = scales or ([(1.0, 0.0)] * len(verts), [(0.0, 0.0)] * len(verts))
        self.rounds += rounds
        self.alongs += alongs


def cone(build, base, tip, radius, colour, weight, tip_colour=None, sides=6, bend=None):
    """A horn, a claw or a spine: from a round base to a point, along a curve
    (through bend, if it's given)."""
    base, tip = Vector(base), Vector(tip)
    mid = Vector(bend) if bend is not None else (base + tip) / 2
    pts = [(base, radius), (mid, radius * 0.55), (tip, radius * 0.04)]
    samples = spline([(tuple(p), r, r) for p, r in pts], step=max(0.02, (tip - base).length / 6))
    fs = frames(samples, (0, 0, 1) if abs((tip - base).normalized().z) < 0.9 else (0, 1, 0))
    k = len(samples)
    tube(build, samples, fs,
         lambda smp, a, p: c.mix(colour, tip_colour or colour, smp[2] / samples[-1][2]),
         lambda smp: weight, around=sides, start_cap=False, end_cap=True)
    return k


# ---- Its body: from the tip of its tail to its head -------------------------
#
# Each point: where, its half-width and half-height there.
SPINE_POINTS = [
    ((-2.9, 3.4, 0.12), 0.04, 0.04),  # the tip of its tail, curled round to its right
    ((-3.2, 4.7, 0.16), 0.10, 0.09),
    ((-2.2, 5.7, 0.25), 0.18, 0.16),
    ((-0.8, 5.4, 0.42), 0.28, 0.26),
    ((-0.15, 4.0, 0.85), 0.42, 0.42),
    ((0.0, 2.6, 1.65), 0.62, 0.64),  # the root of its tail
    ((0.0, 1.3, 2.6), 0.95, 1.0),  # its hips
    ((0.0, 0.1, 3.3), 1.12, 1.22),  # its belly
    ((0.0, -0.8, 4.0), 0.98, 1.08),  # its chest
    ((0.0, -1.3, 4.9), 0.66, 0.70),  # the bottom of its neck
    ((0.0, -1.48, 5.9), 0.50, 0.52),
    ((0.0, -1.28, 6.8), 0.44, 0.45),
    ((0.0, -1.45, 7.5), 0.40, 0.40),  # the top of its neck, where its head is
]
HIPS, CHEST, NECK, HEAD = 6, 8, 9, 12
HEAD_LONG = 1.75  # from the back of its skull to its nose
FORWARD = Vector((0, -1, -0.38)).normalized()  # which way its head points
HEAD_UP = Vector((0, 0, 1)) - FORWARD * FORWARD.z
HEAD_UP.normalize()
# (On past the top of its neck, into its head, so there's no gap under its skull.)
head_at = Vector(SPINE_POINTS[HEAD][0])
SPINE_POINTS.append((tuple(head_at + FORWARD * 0.45 - HEAD_UP * 0.1), 0.34, 0.32))

spine = spline(SPINE_POINTS)
spine_frames = frames(spine, (0, 0, 1))
mark = {}  # how far along it each of its points is
for at, values, s, i in spine:
    for k in range(len(SPINE_POINTS)):
        if abs(i - k) < 1e-6 or (k not in mark and i >= k):
            mark.setdefault(k, s)
mark[len(SPINE_POINTS) - 1] = spine[-1][2]

# Its bones along its body: the tail's six, from its hips to its tip, its
# body, and the neck's five, from its chest to its head.
CHAIN = []
for k in range(6):
    CHAIN.append((f"tail-{k + 1}", mark[HIPS] * (1 - k / 6), mark[HIPS] * (1 - (k + 1) / 6)))
CHAIN.append(("body", mark[HIPS], mark[NECK]))
for k in range(5):
    a, b = mark[NECK], mark[HEAD]
    CHAIN.append((f"neck-{k + 1}", a + (b - a) * k / 5, a + (b - a) * (k + 1) / 5))


def along(s):
    """Its bone weights at s along its body: whichever bone's piece it's on,
    blending into the next near the ends of each (and its head, past its
    neck)."""
    if s > mark[HEAD] + 0.15:
        return {"head": 1.0}
    out = {}
    for name, a, b in CHAIN:
        lo, hi = min(a, b), max(a, b)
        d = 0 if lo <= s <= hi else min(abs(s - lo), abs(s - hi))
        blend = 0.5 * (hi - lo) if name != "body" else 0.6
        w = max(0.0, 1 - d / blend)
        if lo <= s <= hi and name != "body":
            # (The middle of a piece all its own: its ends shared.)
            w = 1.0
        if w > 0:
            out[name] = w
    if s > mark[HEAD] - 0.2:
        out["head"] = smooth((s - mark[HEAD] + 0.2) / 0.35)
    return out


def scales(p, a, s, back=BACK, side=SIDE, belly=BELLY, plates=True):
    """Its colour at a point (a: round from its back, 0, to its belly, pi):
    dark down its back, crimson on its sides, rose lower down, and pale plates
    across its belly, with darker seams; all of it a little uneven, like scales."""
    up = math.cos(a)
    colour = c.mix(side, back, smooth((up - 0.35) / 0.6))
    colour = c.mix(colour, ROSE, smooth((-up + 0.1) / 0.5) * 0.7)
    # (Scales: small and uneven.)
    grain = noise.noise(Vector(p) * 5.0)
    colour = c.vary(colour, 0.12, Vector(p) * 3.1)
    colour = tuple(x * (1 + 0.08 * grain) for x in colour[:3]) + (1.0,)
    if plates:
        under = smooth((-up - 0.45) / 0.25)
        plate = (s / 0.32) % 1
        seam = smooth((abs(plate - 0.5) - 0.4) / 0.08)
        colour = c.mix(colour, c.mix(belly, SEAM, 0.6 * seam), under)
    return colour


body = Skinned()
tube(body, spine, spine_frames, lambda smp, a, p: scales(p, a, smp[2]), lambda smp: along(smp[2]),
     shape=lambda smp, a: 1.0 - 0.06 * max(0.0, -math.cos(a)) if smp[2] > mark[HIPS] else 1.0, scaly="belly")


def on_spine(s):
    """Where it is at s along its body, and its frame there."""
    k = min(range(len(spine)), key=lambda i: abs(spine[i][2] - s))
    return spine[k], spine_frames[k]


# The row of spines down its back: from the back of its head to the tip of
# its tail, tallest over its shoulders, leaning back towards its tail.
s = mark[HEAD] - 0.1
while s > 0.15:
    (at, values, _, _), (t, u, x) = on_spine(s)
    h = values[1]
    tall = 0.12 + 0.55 * math.exp(-((s - mark[CHEST]) / 2.2) ** 2) + 0.22 * min(1.0, h)
    tall *= 0.8 + 0.4 * abs(noise.noise(Vector((s, 0.3, 1.7))))
    root = at + u * h * 0.92
    w = 0.06 + 0.14 * min(1.0, h)
    verts = [tuple(root + t * w * 1.2), tuple(root - t * w * 1.2 + x * w * 0.6), tuple(root - t * w * 1.2 - x * w * 0.6),
             tuple(root + u * tall - t * tall * 0.55)]
    body.put(verts, [(0, 1, 3), (1, 2, 3), (2, 0, 3), (0, 2, 1)], [SPINE, SPINE, SPINE, c.mix(SPINE, CLAW, 0.5)],
             along(s))
    s -= 0.22 + 0.2 * min(1.0, h)


# ---- Its legs: big hind legs under its hips, and front legs under its
# chest, each with three clawed toes. (All of them still: on its body.)
def leg(side, joints, toe_y):
    """A leg, through its joints (each a point and how thick it is there),
    from well inside its body (so it grows out of it, with no edge to
    see) down to its foot, the last; and three toes on that, spreading
    forward to toe_y, each with a hooked claw."""
    pts = [((side * p[0], p[1], p[2]), r, r) for p, r in joints]
    samples = spline(pts, step=0.08)
    fs = frames(samples, (0, -1, 0))
    tube(body, samples, fs, lambda smp, a, p: scales(p, a + math.pi * 0.5, smp[2], plates=False),
         lambda smp: {"body": 1.0}, around=16, start_cap=False, scaly="all")
    (fx, fy, fz), foot = joints[-1]
    for k, spread in enumerate((-0.3, 0.0, 0.3)):
        # (From inside its foot, so each grows out of it.)
        root = Vector((side * (fx + spread * 0.35), fy, fz + foot * 0.3))
        tip = Vector((side * (fx + spread * 1.15), toe_y, 0.08))
        knuckle = root.lerp(tip, 0.55) + Vector((0, 0, 0.07))
        toe = spline([(tuple(root), foot * 0.75, foot * 0.65), (tuple(knuckle), 0.11, 0.1), (tuple(tip), 0.08, 0.065)],
                     step=0.05)
        tube(body, toe, frames(toe, (0, 0, 1)), lambda smp, a, p: scales(p, a, smp[2], plates=False),
             lambda smp: {"body": 1.0}, around=10, start_cap=False, end_cap=True, scaly="all")
        # Its claw, from inside the end of its toe, hooked down to the ground.
        ahead = (tip - knuckle).normalized()
        claw_root = tip - ahead * 0.05
        cone(body, claw_root, claw_root + ahead * 0.3 + Vector((0, 0, -0.08)), 0.065, CLAW, {"body": 1.0},
             bend=claw_root + ahead * 0.17 + Vector((0, 0, 0.02)), sides=6)


for side in (-1, 1):
    # Its hind legs, as a beast's: a great thigh, its knee forward, its long
    # shin back to its hock, high off the ground, and from there its long
    # foot down to its toes.
    leg(side, [((0.3, 1.35, 2.9), 0.5), ((0.66, 1.3, 2.55), 0.8), ((0.9, 0.8, 2.05), 0.74), ((1.02, 0.3, 1.62), 0.5),
               ((1.08, 0.75, 1.15), 0.36), ((1.12, 1.2, 0.78), 0.26), ((1.14, 0.95, 0.4), 0.21),
               ((1.15, 0.65, 0.17), 0.2)], -0.35)
    # Its front legs: a big shoulder, its elbow back, its forearm thick near
    # the elbow and slimming to its wrist, and its paw forward.
    # (From straight above its shoulder, inside its chest, so it runs down
    # from the first, and so do its scales.)
    leg(side, [((0.5, -0.75, 4.45), 0.4), ((0.62, -0.72, 3.9), 0.56), ((0.68, -0.7, 3.45), 0.64), ((0.86, -0.35, 2.75), 0.52),
               ((0.95, -0.2, 2.25), 0.44), ((0.98, -0.55, 1.5), 0.33), ((0.98, -0.85, 0.75), 0.24),
               ((0.97, -1.0, 0.4), 0.22), ((0.96, -1.1, 0.17), 0.2)], -1.75)


# ---- Its head: a long, broad skull, a jaw hinged under it, horns sweeping
# back, a brow over each eye, and teeth. Made in the head's own frame:
# forward along it from the back of its skull (at the top of its neck),
# up, and across.
ACROSS = FORWARD.cross(HEAD_UP).normalized() * -1  # (its left: +x)
MOUTH = -0.13  # the line of its mouth, under the middle of its head
HINGE = 0.14  # of the way along its head, where its jaw is hinged


def at_head(f, x, z):
    """A point on its head: f forward along it (0 to 1), x across, z up."""
    return head_at + FORWARD * (f * HEAD_LONG) + ACROSS * x + HEAD_UP * z


def head_shape(t):
    """Its half-width, the height of its crown above its mouth, and the depth
    of its lower jaw, t from the back of its skull (0) to its nose (1)."""
    end = math.sqrt(max(0.0, 1 - max(0.0, (t - 0.82) / 0.18) ** 2) * 0.88 + 0.12)
    wide = (0.47 - 0.2 * smooth((t - 0.15) / 0.75)) * end
    if t < 0.12:
        wide *= 0.82 + 0.18 * smooth(t / 0.12)
    crown = (0.5 - 0.27 * smooth((t - 0.1) / 0.75)) * end
    if t < 0.1:
        crown *= 0.8 + 0.2 * smooth(t / 0.1)
    jaw = (0.3 - 0.16 * smooth((t - HINGE) / 0.8)) * math.sqrt(max(0.0, 1 - max(0.0, (t - 0.86) / 0.13) ** 2) * 0.9 + 0.1)
    return wide, crown, jaw


ALONG, ROUND = 26, 18


LIP = 0.22  # radians its upper jaw's sides wrap on down past its mouth's line, over its lower jaw's edge


def wedge(top):
    """The top of its head (top) or its lower jaw: a shell over (or under)
    the mouth's line, the inside of its mouth closing it, and its nose (or
    chin) closing the front. The top's sides come down a little past the
    line, as lips, over the edge of its jaw: shut, there's no gap to see
    into its mouth."""
    verts, colours, faces = [], [], []
    rounds, alongs = [], []
    t0 = 0.0 if top else HINGE - 0.1
    t1 = 1.0 if top else 0.97
    angles = [-math.pi / 2 + math.pi * j / ROUND for j in range(ROUND + 1)]
    if top:
        angles = [-math.pi / 2 - LIP] + angles + [math.pi / 2 + LIP]
    n = len(angles)
    for i in range(ALONG + 1):
        t = t0 + (t1 - t0) * i / ALONG
        wide, crown, jaw = head_shape(t)
        for a in angles:
            if top:
                x, z = math.sin(a) * wide, MOUTH + math.cos(a) * crown
                # Its brows: a ridge over each eye; and its nostrils, raised on its snout.
                side = abs(math.sin(a))
                z += 0.11 * math.exp(-((t - 0.36) / 0.1) ** 2) * math.exp(-((side - 0.62) / 0.2) ** 2)
                x += math.copysign(0.05, x) * math.exp(-((t - 0.36) / 0.1) ** 2) * math.exp(-((side - 0.75) / 0.2) ** 2)
                z += 0.05 * math.exp(-((t - 0.93) / 0.04) ** 2) * math.exp(-((side - 0.45) / 0.18) ** 2)
            else:
                x, z = math.sin(a) * wide * 0.92, MOUTH - math.cos(a) * jaw
                # (Its chin a little heavier.)
                z -= 0.04 * math.exp(-((t - 0.8) / 0.12) ** 2) * math.cos(a)
            p = at_head(t, x, z)
            verts.append(tuple(p))
            up = math.cos(a) if top else -math.cos(a)
            colour = scales(p, math.acos(max(-1.0, min(1.0, up))), t * 2, plates=not top)
            if top and t > 0.9 and abs(math.sin(a)) < 0.6 and math.exp(-((t - 0.93) / 0.03) ** 2) > 0.5 \
                    and abs(abs(math.sin(a)) - 0.4) < 0.15:
                colour = THROAT  # (its nostrils)
            colours.append(colour)
            # (Its scales smaller on its head; under its jaw, plates.)
            rounds.append((math.cos(a), math.sin(a)) if top else (-math.cos(a), math.sin(a)))
            alongs.append((t * HEAD_LONG / (SCALE * 0.7), (wide if top else 0.7 * wide) / (SCALE * 0.7) * (-1 if top else 1)))
    for i in range(ALONG):
        for j in range(n - 1):
            q = (i * n + j, (i + 1) * n + j, (i + 1) * n + j + 1, i * n + j + 1)
            faces.append(q if top else q[::-1])
    # The inside of its mouth: a dark red roof (or floor), darker deep in.
    inside = len(verts)
    for i in range(ALONG + 1):
        t = t0 + (t1 - t0) * i / ALONG
        wide = head_shape(t)[0] * (1 if top else 0.92)
        sink = (0.06 if top else -0.06) * (1 - t)
        for j in range(3):
            verts.append(tuple(at_head(t, (-1 + j) * wide, MOUTH + (sink if j == 1 else 0))))
            colours.append(c.mix(THROAT, GUMS, smooth((t - 0.1) / 0.5)))
            rounds.append((1.0, 0.0))
            alongs.append((0.0, 0.0))
    for i in range(ALONG):
        for j in range(2):
            q = (inside + i * 3 + j, inside + i * 3 + j + 1, inside + (i + 1) * 3 + j + 1, inside + (i + 1) * 3 + j)
            faces.append(q if top else q[::-1])
    # Its back, closed; and its front (its nose, or its chin): the shell's
    # last ring, from one side of its mouth over to the other, and back
    # along the inside of its mouth. (Each facing out.)
    first = 1 if top else 0
    ends = [(list(range(n)), -FORWARD),
            ([ALONG * n + j for j in range(first, n - first)] + [inside + ALONG * 3 + 1], FORWARD)]
    for loop, facing in ends:
        pts = [Vector(verts[k]) for k in loop]
        normal = Vector((0, 0, 0))
        for p0, p1 in zip(pts, pts[1:] + pts[:1]):
            normal += Vector(((p0.y - p1.y) * (p0.z + p1.z), (p0.z - p1.z) * (p0.x + p1.x), (p0.x - p1.x) * (p0.y + p1.y)))
        faces.append(tuple(loop if normal.dot(facing) > 0 else loop[::-1]))
    return verts, faces, colours, (rounds, alongs)


verts, faces, colours, scaled = wedge(True)
body.put(verts, faces, colours, {"head": 1.0}, scaled)
verts, faces, colours, scaled = wedge(False)
body.put(verts, faces, colours, {"jaw": 1.0}, scaled)

# Its teeth: a row along each side of its upper jaw, pointing down, and of
# its lower jaw, pointing up; a long fang at the front of each.
for top in (True, False):
    t = 0.3
    while t < 0.93:
        wide = head_shape(t)[0] * (0.88 if top else 0.82)
        fang = abs(t - 0.82) < 0.04
        long = (0.2 if fang else 0.09) * (1 if top else 0.8)
        for side in (-1, 1):
            root = at_head(t, side * wide, MOUTH + (0.01 if top else -0.01))
            tip = root + HEAD_UP * (-long if top else long) - FORWARD * 0.02
            cone(body, root, tip, 0.035 if not fang else 0.05, TOOTH, {"head" if top else "jaw": 1.0}, sides=5)
        t += 0.085

# Its horns: two great ones from the back of its skull, sweeping back and up
# and out; two smaller ones under them, from its cheeks; and a fringe of
# little spikes along the back of its jaw.
def on_skull(t, across, up):
    """A point on the top of its head, t along it, `across` of the way out to
    its side, and sunk `up` of the way in, from its surface to its middle
    (for the roots of its horns, deep enough in that none of their base
    shows)."""
    wide, crown, _ = head_shape(t)
    a = math.asin(max(-1.0, min(1.0, across)))
    return at_head(t, math.sin(a) * wide * up, MOUTH + math.cos(a) * crown * up)


for side in (-1, 1):
    root = on_skull(0.14, side * 0.55, 0.8)
    bend = root - FORWARD * 0.6 + HEAD_UP * 0.5 + ACROSS * side * 0.16
    tip = root - FORWARD * 1.35 + HEAD_UP * 0.55 + ACROSS * side * 0.3
    cone(body, root, tip, 0.15, HORN, {"head": 1.0}, tip_colour=HORN_TIP, sides=10, bend=bend)
    root = on_skull(0.22, side * 0.9, 0.82)
    cone(body, root, root - FORWARD * 0.65 + HEAD_UP * 0.14 + ACROSS * side * 0.3, 0.08, HORN, {"head": 1.0},
         tip_colour=HORN_TIP, sides=8, bend=root - FORWARD * 0.32 + HEAD_UP * 0.1 + ACROSS * side * 0.2)
    for k, t in enumerate((0.1, 0.22, 0.34)):
        root = at_head(t, side * head_shape(t)[0] * 0.85, MOUTH - head_shape(t)[2] * 0.7)
        cone(body, root, root - FORWARD * 0.28 - HEAD_UP * 0.08 + ACROSS * side * 0.16, 0.05, SPINE, {"jaw": 1.0},
             sides=5)

# Its eyes: big, fierce and golden, under its brows, each with a dark slit.
eyes = Skinned()


def ball(build, centre, axes, colour, weight, n=8, m=14):
    ax, ay, az = axes
    verts = []
    for k in range(n + 1):
        phi = math.pi * k / n
        for j in range(m):
            a = 2 * math.pi * j / m
            verts.append(tuple(centre + ax * (math.sin(phi) * math.cos(a)) + ay * (math.sin(phi) * math.sin(a))
                               + az * math.cos(phi)))
    faces = [(k * m + j, k * m + (j + 1) % m, (k + 1) * m + (j + 1) % m, (k + 1) * m + j) for k in range(n) for j in range(m)]
    build.put(verts, faces, [colour] * len(verts), weight)


for side in (-1, 1):
    t = 0.38
    wide, crown, _ = head_shape(t)
    centre = at_head(t, side * wide * 0.8, MOUTH + crown * 0.6)
    look = (ACROSS * side * 0.8 + FORWARD * 0.55 + HEAD_UP * 0.1).normalized()
    upright = (HEAD_UP - look * look.dot(HEAD_UP)).normalized()
    level = look.cross(upright)
    ball(eyes, centre, (level * 0.085, upright * 0.07, look * 0.06), EYE, {"head": 1.0})
    ball(eyes, centre + look * 0.05, (level * 0.012, upright * 0.06, look * 0.015), PUPIL, {"head": 1.0}, n=5, m=8)


# ---- Its wings: raised, the wrist high with a claw on it, three long
# fingers spreading out and down from it, and the skin between them (and
# back to its flank), scalloped between the fingertips.
SHOULDER = Vector((0.62, -0.5, 4.55))
ELBOW = Vector((1.8, 0.45, 5.9))
WRIST = Vector((2.55, -0.15, 7.6))
TIPS = [Vector((5.0, 0.35, 6.7)), Vector((5.3, 0.95, 4.5)), Vector((4.1, 1.3, 2.7))]
FLANK = Vector((0.8, 1.45, 3.05))  # where its wing's skin joins its side, by its hips
wings = Skinned()


def mirror(p, side):
    return Vector((p.x * side, p.y, p.z))


def spar(side, a, b, ra, rb, wa, wb, bow=0.0):
    a, b = mirror(a, side), mirror(b, side)
    mid = (a + b) / 2 + Vector((side * bow, bow * 0.3, bow * 0.5))
    samples = spline([(tuple(a), ra, ra), (tuple(mid), (ra + rb) / 2, (ra + rb) / 2), (tuple(b), rb, rb)], step=0.08)
    total = samples[-1][2]

    def weight(smp):
        t = smp[2] / total
        return {k: v for k, v in ((wa, 1 - t), (wb, t)) if v > 0} if wa != wb else {wa: 1.0}

    tube(body, samples, frames(samples, (0, 1, 0)), lambda smp, a_, p: c.vary(SPAR, 0.1, Vector(p) * 2), weight,
         around=10, start_cap=True, end_cap=True)
    return [Vector(smp[0]) for smp in samples]


def panel(side, corners, weights, sag=0.0, n=7, billow=0.12):
    """A triangle of its wing's skin, from the wrist (corners[0]) to two
    points, sagging between those two (scalloped) and billowing a little."""
    w0, a, b = (mirror(p, side) for p in corners)
    normal = (a - w0).cross(b - w0).normalized()
    verts, colours, ws = [], [], []
    index = {}
    for i in range(n + 1):
        for j in range(i + 1):
            u = (i - j) / n  # towards a
            v = j / n  # towards b
            p = w0 + (a - w0) * u + (b - w0) * v
            if i > 0:
                # The edge from a to b drawn in towards the wrist, most in the
                # middle; the skin billowing out between its bones.
                along_edge = j / i
                p = p + (w0 - p) * (sag * math.sin(math.pi * along_edge) * (i / n) ** 3)
                p = p + normal * side * billow * math.sin(math.pi * along_edge) * math.sin(math.pi * i / n * 0.9)
            index[i, j] = len(verts)
            verts.append(tuple(p))
            near_bone = min(u, v) / max(1e-6, u + v) if i else 0
            colours.append(c.vary(c.mix(VEIN, WING, smooth(near_bone * 4)), 0.08, p * 1.7))
            blend = {}
            for wd, k in ((weights[0], 1 - u - v), (weights[1], u), (weights[2], v)):
                for bone, x in wd.items():
                    blend[bone] = blend.get(bone, 0) + x * k
            ws.append({k: x for k, x in blend.items() if x > 1e-4} or {"body": 1.0})
    faces = []
    for i in range(n):
        for j in range(i + 1):
            faces.append((index[i, j], index[i + 1, j], index[i + 1, j + 1]))
            if j < i:
                faces.append((index[i, j], index[i + 1, j + 1], index[i, j + 1]))
    if side < 0:
        faces = [f[::-1] for f in faces]
    wings.put(verts, faces, colours, ws)


for side in (-1, 1):
    arm, fore = ("arm-l", "fore-l") if side > 0 else ("arm-r", "fore-r")
    spar(side, SHOULDER, ELBOW, 0.2, 0.14, arm, arm, bow=0.05)
    spar(side, ELBOW, WRIST, 0.14, 0.1, fore, fore, bow=-0.08)
    for tip, bow in zip(TIPS, (0.18, 0.25, 0.2)):
        spar(side, WRIST, tip, 0.08, 0.025, fore, fore, bow=bow)
    # The claw on its wrist, hooked forward.
    w = mirror(WRIST, side)
    cone(body, w, w + Vector((side * 0.05, -0.32, 0.38)), 0.08, HORN, {fore: 1.0}, tip_colour=CLAW, sides=8,
         bend=w + Vector((0, -0.05, 0.28)))
    fw, aw = {fore: 1.0}, {arm: 1.0}
    elbow_w = {arm: 0.5, fore: 0.5}
    panel(side, (WRIST, TIPS[0], TIPS[1]), (fw, fw, fw), sag=0.28)
    panel(side, (WRIST, TIPS[1], TIPS[2]), (fw, fw, fw), sag=0.3)
    panel(side, (WRIST, TIPS[2], FLANK), (fw, fw, {"body": 1.0}), sag=0.25)
    panel(side, (WRIST, FLANK, ELBOW), (fw, {"body": 1.0}, elbow_w), sag=0.0, billow=0.06)
    panel(side, (ELBOW, FLANK, SHOULDER), (elbow_w, {"body": 1.0}, aw), sag=0.0, billow=0.04)
    # (And a little skin in front of the elbow, from the shoulder to the wrist.)
    panel(side, (WRIST, ELBOW, SHOULDER), (fw, elbow_w, aw), sag=-0.12, n=4, billow=0.02)


# ---- Its skeleton ------------------------------------------------------------

# (All of it scaled to its height: to the tips of its horns, the top of it.)
top = max(v[2] for v in body.verts)
size = TALL / top
for build in (body, wings, eyes):
    build.verts = [tuple(x * size for x in v) for v in build.verts]

skeleton_data = bpy.data.armatures.new("dragon-skeleton")
skeleton = bpy.data.objects.new("dragon-skeleton", skeleton_data)
bpy.context.collection.objects.link(skeleton)
bpy.context.view_layer.objects.active = skeleton
skeleton.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bones = skeleton_data.edit_bones


def bone(name, head, tail, parent=None):
    b = bones.new(name)
    b.head, b.tail = Vector(head) * size, Vector(tail) * size
    if parent:
        b.parent = bones[parent]
    return b


def point_at(s):
    return Vector(on_spine(s)[0][0])


bone("body", point_at(mark[HIPS]), point_at(mark[NECK]))
for k in range(6):
    name, a, b = CHAIN[k]
    bone(name, point_at(a), point_at(b), "body" if k == 0 else f"tail-{k}")
for k in range(5):
    name, a, b = CHAIN[7 + k]
    bone(name, point_at(a), point_at(b), "body" if k == 0 else f"neck-{k}")
bone("head", head_at, head_at + FORWARD * HEAD_LONG * 0.5, "neck-5")
hinge = at_head(HINGE, 0, MOUTH)
bone("jaw", hinge, hinge + FORWARD * HEAD_LONG * 0.6, "head")
nose = at_head(1.0, 0, MOUTH)
bone("mouth", nose, nose + FORWARD * 0.3, "head")
for side, arm, fore in ((1, "arm-l", "fore-l"), (-1, "arm-r", "fore-r")):
    bone(arm, mirror(SHOULDER, side), mirror(ELBOW, side), "body")
    bone(fore, mirror(ELBOW, side), mirror(WRIST, side), arm)
bpy.ops.object.mode_set(mode="OBJECT")

def scaled(obj, build):
    """Where each of its points is on its scales, as its UVs (Skinned)."""
    for name, values in (("round", build.rounds), ("along", build.alongs)):
        layer = obj.data.uv_layers.new(name=name)
        for loop in obj.data.loops:
            layer.data[loop.index].uv = values[loop.vertex_index]
    return obj


made = [
    scaled(c.skinned("dragon", body.verts, body.faces, body.colours, body.weights, skeleton), body),
    c.skinned("dragon-wings", wings.verts, wings.faces, wings.colours, wings.weights, skeleton),
    c.skinned("dragon-eyes", eyes.verts, eyes.faces, eyes.colours, eyes.weights, skeleton),
]
print(f"dragon: {len(body.verts) + len(wings.verts)} points, made {top:.2f} m tall, scaled by {size:.3f}")

if out:
    for obj in made:
        obj.select_set(True)
    skeleton.select_set(True)
    c.export(out, use_selection=True, export_animations=False)
    print(f"Exported {out}")

if preview:
    # From the front, then (beside it) from its side and from behind.
    c.preview(preview, (-9, -12, 6), (0, 0, 4.2), (0.4, 0.7, -1), lens=30)
    for name, eye, at in (("legs", (-6, -7, 3.2), (0.6, -0.6, 2.8)),):
        bpy.context.scene.camera.location = eye
        bpy.context.scene.camera.rotation_euler = (Vector(at) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.render.filepath = preview.replace(".png", f"-{name}.png")
        bpy.ops.render.render(write_still=True)
    head_mid = (head_at + FORWARD * HEAD_LONG * 0.4) * size
    for name, eye, at in (("side", (-16, 0.5, 4.5), (0, 0.5, 3.8)), ("back", (6, 14, 7), (0, 0.5, 3.8)),
                          ("head", tuple(head_mid + Vector((-2.2, -1.2, 0.9))), tuple(head_mid)),
                          ("horns", tuple(head_mid + Vector((1.6, 1.4, 1.6))), tuple(head_mid))):
        bpy.context.scene.camera.location = eye
        bpy.context.scene.camera.rotation_euler = (Vector(at) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.render.filepath = preview.replace(".png", f"-{name}.png")
        bpy.ops.render.render(write_still=True)
