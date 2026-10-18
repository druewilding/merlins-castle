// The 3D land must only let you go where the original does. With every
// obstacle closed (no ladder, no key, no axe…), you walk the land from a place
// and see which places you reach: a gap in the forest or the walls shows up
// here as a place you shouldn't be able to get to. The same underground, along
// the ways and through the halls. Obstacles only stop you going the way their
// exits go, as in the game: the drawbridge is up from the moat, but you can
// walk out of the courtyard.

import { describe, expect, it } from "vitest";

import layout from "../art/blender/layout.json";
import landBin from "../src/three/models/land.bin?inline";
import land from "../src/three/models/land.json";
import { wayThrough } from "../src/three/player";

const BODY = 0.35; // as in src/three/player.ts
const STEP = 0.5;
const AHEAD = 5; // as in src/three/main.ts: you bump into an obstacle this far before it, front and back

const [OX, OY] = layout.origin;
const places = Object.entries(layout.places).map(([id, [col, row]]) => ({
  id,
  x: (col - OX) * layout.spacing,
  z: (row - OY) * layout.spacing,
}));

// Vite hands the file over as a data: URL, in base64.
const file = Uint8Array.from(atob(landBin.split(",")[1]), (char) => char.charCodeAt(0));
const G = land.ground;
const heights = new Float32Array(file.buffer, 0, G.nx * G.ny);
const groundAt = (x: number, z: number) =>
  heights[Math.round((-z - G.y0) / G.step) * G.nx + Math.round((x - G.x0) / G.step)];
const W = land.walkable;
const mask = file.subarray(W.offset, W.offset + W.nx * W.ny);
const walkable = (x: number, z: number) => {
  const i = Math.floor((x - W.x0) / W.step);
  const j = Math.floor((-z - W.y0) / W.step);
  return i >= 0 && j >= 0 && i < W.nx && j < W.ny && mask[j * W.nx + i] === 1;
};

type Solid = { circle: number[] } | { box: number[] };
type Obstacle = Solid & { under?: boolean; names: string[] };
// One shape for each obstacle, with the names of every exit it blocks, and
// how far it reaches out.
const obstacles: Obstacle[] = [];
for (const [exit, obstacle] of Object.entries(land.obstacles) as [string, Solid & { under?: boolean }][]) {
  const same = obstacles.find(
    (other) =>
      JSON.stringify("box" in other ? other.box : other.circle) ===
      JSON.stringify(
        "box" in obstacle ? reaching(obstacle.box) : [...obstacle.circle.slice(0, 2), obstacle.circle[2] + AHEAD]
      )
  );
  if (same) same.names.push(exit);
  else if ("circle" in obstacle)
    obstacles.push({
      ...obstacle,
      circle: [...obstacle.circle.slice(0, 2), obstacle.circle[2] + AHEAD],
      names: [exit],
    });
  else obstacles.push({ ...obstacle, box: reaching(obstacle.box), names: [exit] });
}
function reaching([x, z, hx, hz]: number[]) {
  return hx < hz ? [x, z, hx + AHEAD, hz] : [x, z, hx, hz + AHEAD];
}
const within = (solid: Solid, x: number, z: number) => {
  if ("circle" in solid) return Math.hypot(x - solid.circle[0], z - solid.circle[1]) < solid.circle[2] + BODY;
  const [bx, bz, hx, hz] = solid.box;
  return Math.abs(x - bx) < hx + BODY && Math.abs(z - bz) < hz + BODY;
};

/**
 * Stepping to a spot among obstacles, going through some of them already (a
 * bit for each): those you're now going through, or undefined if one stops
 * you. Going into an obstacle's reach from a side its exits go from stops
 * you; from any other side, you go all the way through it.
 */
function crossing(shapes: Obstacle[]) {
  return (x: number, z: number, through: number) => {
    let next = 0;
    for (const [k, shape] of shapes.entries()) {
      if (!within(shape, x, z)) continue;
      const [ox, oz] = "box" in shape ? shape.box : shape.circle;
      if (!(through & (1 << k)) && wayThrough(shape.names, ox, oz, x, z)) return undefined;
      next |= 1 << k;
    }
    return next;
  };
}

function sorted(solids: Solid[]) {
  const buckets = new Map<string, Solid[]>();
  for (const solid of solids) {
    const [x, z, a, b = a] = "circle" in solid ? solid.circle : solid.box;
    for (let i = Math.floor((x - a - 1) / 8); i <= Math.floor((x + a + 1) / 8); i++) {
      for (let j = Math.floor((z - b - 1) / 8); j <= Math.floor((z + b + 1) / 8); j++) {
        const key = `${i},${j}`;
        buckets.set(key, [...(buckets.get(key) ?? []), solid]);
      }
    }
  }
  return (x: number, z: number) =>
    (buckets.get(`${Math.floor(x / 8)},${Math.floor(z / 8)}`) ?? []).some((solid) => within(solid, x, z));
}

const solidOnLand = sorted([...land.circles.map((circle) => ({ circle })), ...land.boxes.map((box) => ({ box }))]);
const free = (x: number, z: number) => walkable(x, z) && !solidOnLand(x, z);
// (The places in buildings and caves you only get into along a way: below.)
const outdoors = places.filter((place) => !(place.id in land.halls));
const onLand = obstacles.filter((obstacle) => !obstacle.under);
const crossOnLand = crossing(onLand);

function reachable(from: string) {
  const start = places.find((place) => place.id === from)!;
  const [west, east, south, north] = land.bounds;
  const nx = Math.round((east - west) / STEP);
  const nz = Math.round((north - south) / STEP);
  const seen = new Set<number>();
  const queue = [[Math.round((start.x - west) / STEP), Math.round((start.z + north) / STEP), 0]];
  const reached = new Set<string>();
  while (queue.length) {
    const [i, j, before] = queue.pop()!;
    if (i < 0 || j < 0 || i >= nx || j >= nz) continue;
    const x = west + i * STEP;
    const z = -north + j * STEP;
    if (!free(x, z)) continue;
    const through = crossOnLand(x, z, before);
    if (through === undefined) continue;
    const key = through * nx * nz + j * nx + i;
    if (seen.has(key)) continue;
    seen.add(key);
    for (const place of outdoors) if (Math.hypot(x - place.x, z - place.z) < 6) reached.add(place.id);
    queue.push([i + 1, j, through], [i - 1, j, through], [i, j + 1, through], [i, j - 1, through]);
  }
  return [...reached].sort();
}

describe("the 3D land, with every obstacle closed", () => {
  it("keeps the grassy bank's neighbours together, behind the wall, the river, the axe trees and the leaves", () => {
    expect(reachable("grassy-bank")).toEqual([
      "cave-entrance",
      "deep-river",
      "evergreen-glade",
      "grassy-bank",
      "mountain-path",
      "old-stone-wall",
    ]);
  });

  const fromTheOldWall = [
    "forest-crossroads",
    "forest-edge",
    "forest-witches",
    "moat",
    "old-wall",
    "river-south-bank",
    "rusty-gate",
  ];

  it("joins the old wall to the forest and the moat, over the bridge", () => {
    expect(reachable("old-wall")).toEqual(fromTheOldWall);
  });

  it("keeps the yellow flowers, the mossy steps and the tower behind the locked gate", () => {
    expect(reachable("yellow-flowers")).toEqual(["mossy-steps", "yellow-flowers"]);
  });

  it("lets you down from the mountain top, but not up through the dense trees", () => {
    expect(reachable("mountain")).toContain("mountain-path");
    expect(reachable("mountain-path")).not.toContain("mountain");
  });

  it("lets you out of the courtyard, but not back in over the drawbridge, nor past the witches", () => {
    expect(reachable("courtyard")).toEqual(["courtyard", "forest-edge", "forest-witches", "moat", "river-south-bank"]);
    expect(reachable("old-wall")).not.toContain("courtyard");
  });
});

// Merlin's trap: round its treasure, at the end of the path east from the
// mountain; you're caught as you come within its reach, where its net lies
// (on the path, so you're scooped up from right where you stand).
describe("Merlin's trap", () => {
  const { circle, reach } = land.obstacles["mountain east"] as { circle: number[]; reach: number };
  const [x, z, r] = circle;

  it("is round its treasure", () => {
    expect([x, z]).toEqual([land.trap.gold[0], land.trap.gold[2]]);
  });

  it("lays its net where you're caught, coming along the path from the mountain", () => {
    const [nx, nz] = land.trap.net;
    expect(Math.hypot(nx - x, nz - z)).toBeCloseTo(r + reach, 1);
    const mountain = places.find((place) => place.id === "mountain")!;
    expect(Math.hypot(nx - mountain.x, nz - mountain.z)).toBeLessThan(Math.hypot(x - mountain.x, z - mountain.z));
    expect(walkable(nx, nz)).toBe(true);
  });
});

describe("the deep hole", () => {
  const { box, reach } = land.obstacles["maze north"] as { box: number[]; reach: number };

  it("stops you both ways, at the hole itself", () => {
    expect(land.obstacles["treasure-room south"]).toEqual(land.obstacles["maze north"]);
    expect(box).toEqual(land.hole.box);
  });

  it("lets you walk right up to its edge (to slip in), and is right across the way", () => {
    expect(reach).toBeLessThan(1);
    expect(box[2]).toBeGreaterThan(land.ways["maze-treasure"].half);
  });

  it("goes down a long way, with a beam across its top, over your head", () => {
    expect(land.hole.floor - land.hole.bottom).toBeGreaterThan(50);
    expect(land.hole.beam - land.hole.floor).toBeGreaterThan(2.5);
  });
});

// Underground: where you can be is in a hall, or along a way (and from a
// way's mouth, out onto the land, which counts as reaching the place nearest).
const halls = Object.entries(land.halls);
const ways = Object.values(land.ways);
const CLIMB = 1.2; // as in src/three/player.ts

function nearest(points: number[][], x: number, z: number) {
  let best = { d: Infinity, floor: 0, beyond: false };
  for (let k = 0; k < points.length - 1; k++) {
    const [ax, az, af] = points[k];
    const [bx, bz, bf] = points[k + 1];
    const t = ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / ((bx - ax) ** 2 + (bz - az) ** 2);
    const tc = Math.max(0, Math.min(1, t));
    const d = Math.hypot(x - ax - tc * (bx - ax), z - az - tc * (bz - az));
    const beyond = (k === 0 && t < 0) || (k === points.length - 2 && t > 1);
    if (d < best.d) best = { d, floor: af + (bf - af) * tc, beyond };
  }
  return best;
}

type Hall = (typeof land.halls)[keyof typeof land.halls];
const inHall = (hall: Hall, x: number, z: number) =>
  "w" in hall
    ? Math.abs(x - hall.x) <= hall.w - BODY && Math.abs(z - hall.z) <= hall.d - BODY
    : Math.hypot(x - hall.x, z - hall.z) <= hall.r - BODY;

/** From a hall, or from a spot along a way: [x, z, floor]. */
function underground(from: string | number[], open: boolean) {
  const blocked = sorted(land.under.circles.map((circle) => ({ circle })));
  const cross = crossing(open ? [] : obstacles.filter((obstacle) => obstacle.under));
  // Every spot you could stand on, on every floor: x, z and the floor's height.
  const floorsAt = (x: number, z: number) => {
    const floors: { floor: number; hall?: string }[] = [];
    for (const [place, hall] of halls) {
      if (inHall(hall, x, z)) floors.push({ floor: hall.floor, hall: place });
    }
    for (const way of ways) {
      const n = nearest(way.points, x, z);
      if (!n.beyond && n.d <= way.half - BODY) floors.push({ floor: n.floor });
    }
    return blocked(x, z) ? [] : floors;
  };
  // From the hall's middle, or beside it if something stands there (the dungeon's
  // well) or it's in an obstacle's reach.
  const [x0, z0, floor0] =
    typeof from === "string" ? [land.halls[from as keyof typeof land.halls]].map((h) => [h.x, h.z, h.floor])[0] : from;
  const [dx, dz] = [
    [0, 0],
    [0, 2.5],
    [2.5, 0],
    [0, -2.5],
    [-2.5, 0],
  ].find(([dx, dz]) => floorsAt(x0 + dx, z0 + dz).length > 0 && cross(x0 + dx, z0 + dz, 0) === 0)!;
  const queue = [[Math.round((x0 + dx) / STEP), Math.round((z0 + dz) / STEP), floor0, 0]];
  const seen = new Set<string>();
  const reached = new Set<string>();
  while (queue.length) {
    const [i, j, floor, before] = queue.pop()!;
    const x = i * STEP;
    const z = j * STEP;
    const here = floorsAt(x, z).find((spot) => Math.abs(spot.floor - floor) < CLIMB);
    if (!here) continue;
    const through = cross(x, z, before);
    if (through === undefined) continue;
    const key = `${i},${j},${Math.round(here.floor)},${through}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if (here.hall) reached.add(here.hall);
    // At a way's mouth (an end on the ground, not in a hall): out onto the land.
    for (const way of ways) {
      for (const end of [way.points[0], way.points.at(-1)!]) {
        const mouth =
          Math.abs(groundAt(end[0], end[1]) - end[2]) < 0.6 && !halls.some(([, hall]) => inHall(hall, end[0], end[1]));
        // (Coming out, you're going through an obstacle in the mouth the free way.)
        if (mouth && Math.hypot(x - end[0], z - end[1]) < 1 && Math.abs(end[2] - here.floor) < CLIMB) {
          const outside = places.filter((place) => !(place.id in land.halls));
          reached.add(
            outside.reduce((a, b) => (Math.hypot(a.x - x, a.z - z) < Math.hypot(b.x - x, b.z - z) ? a : b)).id
          );
        }
      }
    }
    queue.push(
      [i + 1, j, here.floor, through],
      [i - 1, j, here.floor, through],
      [i, j + 1, here.floor, through],
      [i, j - 1, here.floor, through]
    );
  }
  return [...reached].sort();
}

describe("underground, with every obstacle closed", () => {
  // (Going north from the dark tunnels, the dragon's cave, the damp tunnels
  // and the treasure room is free: only the other way needs the water, the
  // broom, the key or the cake. And out of the dragon's cave past the leaves.)
  const pastTheDragon = ["cave-entrance", "dragon-cave", "giant"];

  it("keeps the trolls in their cave, and the deep hole between the treasure room and the maze", () => {
    expect(underground("trolls", false)).toEqual(["maze", "trolls"]);
    expect(underground("damp-tunnels", false)).toEqual(["damp-tunnels", "maze", ...pastTheDragon].sort());
    expect(underground("treasure-room", false)).toEqual(["oak-door", "treasure-room", ...pastTheDragon].sort());
  });

  it("keeps the giant's padlocked way south, and the leaves, the fire and the dark in your way", () => {
    expect(underground("giant", false)).toEqual(pastTheDragon);
    expect(underground("dragon-cave", false)).toEqual(pastTheDragon);
    expect(underground("dark-tunnels", false)).toEqual(["dark-tunnels", ...pastTheDragon].sort());
  });
});

describe("the long lamp tunnel", () => {
  const points = land.ways["lamp-tunnel"].points;
  const middle = points[Math.floor(points.length / 2)];

  it("is too dark to go into from either end without the lamp", () => {
    // A step from the land on to the top of each ramp.
    for (const [end, next] of [
      [points[0], points[1]],
      [points.at(-1)!, points.at(-2)!],
    ]) {
      const d = Math.hypot(next[0] - end[0], next[1] - end[1]);
      const [x, z] = [end[0] - (next[0] - end[0]) / d, end[1] - (next[1] - end[1]) / d];
      expect(crossOnLand(x, z, 0)).toBeUndefined();
    }
  });

  it("lets you walk out of either end", () => {
    expect(underground(middle, false)).toEqual(["cave-entrance", "old-wall"]);
  });

  it("joins the old wall and the cave entrance, with it", () => {
    expect(underground(middle, true)).toEqual(["cave-entrance", "old-wall"]);
  });
});

describe("the tower and the charcoal burner's hut", () => {
  it("lets you into the hut, and out again, by its door", () => {
    expect(underground("charcoal-hut", false)).toEqual(["charcoal-hut", "forest-crossroads"]);
  });

  it("keeps the snake at the tower's door, and shuts you in without the ring", () => {
    const outside = land.ways["tower-door"].points[0];
    expect(crossOnLand(outside[0], outside[1] + 1, 0)).toBeUndefined();
    expect(underground("tower", false)).toEqual(["tower"]);
    expect(underground("tower", true)).toEqual(["mossy-steps", "tower"]);
  });
});

describe("in the castle, with every obstacle closed", () => {
  it("lets you in from the courtyard to the grand hall and the coach house, and no further", () => {
    expect(underground("grand-hall", false)).toEqual(["courtyard", "grand-hall"]);
    expect(underground("coach-house", false)).toEqual(["coach-house", "courtyard"]);
  });

  it("keeps the goblins, Merlin, the old woman and the doors in the corridors, one way", () => {
    expect(underground("wizards-kitchen", false)).toEqual(["wizards-kitchen"]);
    expect(underground("merlins-lair", false)).toEqual(["merlins-lair"]);
    // West from the dungeon to the hall, and north and west from the small room.
    const outOfTheDungeon = ["courtyard", "dungeon", "grand-hall"];
    expect(underground("dungeon", false)).toEqual(outOfTheDungeon);
    expect(underground("small-room", false)).toEqual([...outOfTheDungeon, "merlins-lair", "small-room"].sort());
  });
});

describe("in the castle, with every obstacle open", () => {
  it("joins every room in the keep", () => {
    expect(underground("grand-hall", true)).toEqual([
      "courtyard",
      "dungeon",
      "grand-hall",
      "merlins-lair",
      "small-room",
      "wizards-kitchen",
    ]);
  });
});

describe("underground, with every obstacle open", () => {
  it("joins everything: the caves in the mountain, the dragon's tunnel up to the giant, and down to the chamber", () => {
    expect(underground("trolls", true)).toEqual([
      "beautiful-chamber",
      "cave-entrance",
      "damp-tunnels",
      "dark-tunnels",
      "dragon-cave",
      "giant",
      "maze",
      "oak-door",
      "treasure-room",
      "trolls",
    ]);
  });
});
