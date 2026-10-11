// The 3D land must only let you go where the original does. With every
// obstacle closed (no ladder, no key, no axe…), you walk the land from a place
// and see which places you reach: a gap in the forest or the walls shows up
// here as a place you shouldn't be able to get to. The same underground, along
// the ways and through the halls.

import { describe, expect, it } from "vitest";

import layout from "../art/blender/layout.json";
import landBin from "../src/three/models/land.bin?inline";
import land from "../src/three/models/land.json";

const BODY = 0.35; // as in src/three/player.ts
const STEP = 0.5;

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
type Obstacle = Solid & { under?: boolean };
const obstacles = Object.values(land.obstacles) as Obstacle[];

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
    (buckets.get(`${Math.floor(x / 8)},${Math.floor(z / 8)}`) ?? []).some((solid) => {
      if ("circle" in solid) return Math.hypot(x - solid.circle[0], z - solid.circle[1]) < solid.circle[2] + BODY;
      const [bx, bz, hx, hz] = solid.box;
      return Math.abs(x - bx) < hx + BODY && Math.abs(z - bz) < hz + BODY;
    });
}

const solidOnLand = sorted([
  ...land.circles.map((circle) => ({ circle })),
  ...land.boxes.map((box) => ({ box })),
  ...obstacles.filter((obstacle) => !obstacle.under),
]);
const free = (x: number, z: number) => walkable(x, z) && !solidOnLand(x, z);

function reachable(from: string) {
  const start = places.find((place) => place.id === from)!;
  const [west, east, south, north] = land.bounds;
  const nx = Math.round((east - west) / STEP);
  const nz = Math.round((north - south) / STEP);
  const seen = new Uint8Array(nx * nz);
  const queue = [[Math.round((start.x - west) / STEP), Math.round((start.z + north) / STEP)]];
  const reached = new Set<string>();
  while (queue.length) {
    const [i, j] = queue.pop()!;
    if (i < 0 || j < 0 || i >= nx || j >= nz || seen[j * nx + i]) continue;
    seen[j * nx + i] = 1;
    const x = west + i * STEP;
    const z = -north + j * STEP;
    if (!free(x, z)) continue;
    for (const place of places) if (Math.hypot(x - place.x, z - place.z) < 6) reached.add(place.id);
    queue.push([i + 1, j], [i - 1, j], [i, j + 1], [i, j - 1]);
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

  it("joins the old wall to the forest and the moat, over the bridge", () => {
    expect(reachable("old-wall")).toEqual([
      "charcoal-hut",
      "forest-crossroads",
      "forest-edge",
      "forest-witches",
      "moat",
      "old-wall",
      "river-south-bank",
      "rusty-gate",
    ]);
  });

  it("keeps the yellow flowers, the mossy steps and the tower behind the locked gate", () => {
    expect(reachable("yellow-flowers")).toEqual(["mossy-steps", "tower", "yellow-flowers"]);
  });

  it("keeps the mountain top above the dense trees", () => {
    expect(reachable("mountain")).not.toContain("mountain-path");
  });

  it("keeps the courtyard behind the drawbridge", () => {
    expect(reachable("courtyard")).toEqual(["courtyard"]);
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

function underground(from: string, open: boolean) {
  const blocked = sorted(
    open ? [] : [...obstacles.filter((obstacle) => obstacle.under), ...land.under.circles.map((circle) => ({ circle }))]
  );
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
  // From the hall's middle, or beside it if something stands there (the dungeon's well).
  const hall = land.halls[from as keyof typeof land.halls];
  const [dx, dz] = [
    [0, 0],
    [0, 2.5],
    [2.5, 0],
    [0, -2.5],
    [-2.5, 0],
  ].find(([dx, dz]) => floorsAt(hall.x + dx, hall.z + dz).length > 0)!;
  const queue = [[Math.round((hall.x + dx) / STEP), Math.round((hall.z + dz) / STEP), hall.floor]];
  const seen = new Set<string>();
  const reached = new Set<string>();
  while (queue.length) {
    const [i, j, floor] = queue.pop()!;
    const x = i * STEP;
    const z = j * STEP;
    const here = floorsAt(x, z).find((spot) => Math.abs(spot.floor - floor) < CLIMB);
    if (!here) continue;
    const key = `${i},${j},${Math.round(here.floor)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    if (here.hall) reached.add(here.hall);
    // At a way's mouth (an end on the ground, not in a hall): out onto the land.
    for (const way of ways) {
      for (const end of [way.points[0], way.points.at(-1)!]) {
        const mouth =
          Math.abs(groundAt(end[0], end[1]) - end[2]) < 0.6 && !halls.some(([, hall]) => inHall(hall, end[0], end[1]));
        if (mouth && Math.hypot(x - end[0], z - end[1]) < 1 && Math.abs(end[2] - here.floor) < CLIMB) {
          const outside = places.filter((place) => !(place.id in land.halls));
          reached.add(
            outside.reduce((a, b) => (Math.hypot(a.x - x, a.z - z) < Math.hypot(b.x - x, b.z - z) ? a : b)).id
          );
        }
      }
    }
    queue.push([i + 1, j, here.floor], [i - 1, j, here.floor], [i, j + 1, here.floor], [i, j - 1, here.floor]);
  }
  return [...reached].sort();
}

describe("underground, with every obstacle closed", () => {
  it("lets you into the caves from the maze, but no further than the trolls and the damp tunnels", () => {
    expect(underground("trolls", false)).toEqual(["maze", "trolls"]);
    expect(underground("damp-tunnels", false)).toEqual(["damp-tunnels", "maze"]);
  });

  it("keeps the deep hole between the treasure room and the maze, and the giant in his cave", () => {
    expect(underground("treasure-room", false)).toEqual(["oak-door", "treasure-room"]);
    expect(underground("giant", false)).toEqual(["dragon-cave", "giant"]);
  });

  it("keeps the leaves in the dragon's way, and its fire, and the dark", () => {
    expect(underground("dragon-cave", false)).toEqual(["dragon-cave", "giant"]);
    expect(underground("dark-tunnels", false)).toEqual(["dark-tunnels"]);
  });
});

describe("in the castle, with every obstacle closed", () => {
  it("lets you in from the courtyard to the grand hall and the coach house, and no further", () => {
    expect(underground("grand-hall", false)).toEqual(["courtyard", "grand-hall"]);
    expect(underground("coach-house", false)).toEqual(["coach-house", "courtyard"]);
  });

  it("keeps the goblins, Merlin, the old woman and the doors in the corridors", () => {
    for (const room of ["wizards-kitchen", "dungeon", "small-room", "merlins-lair"]) {
      expect(underground(room, false)).toEqual([room]);
    }
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
