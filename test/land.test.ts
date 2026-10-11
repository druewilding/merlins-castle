// The 3D land must only let you go where the original does. With every
// obstacle closed (no ladder, no key, no axe…), you walk the land from a place
// and see which places you reach: a gap in the forest or the walls shows up
// here as a place you shouldn't be able to get to.

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
const W = land.walkable;
const mask = file.subarray(W.offset, W.offset + W.nx * W.ny);
const walkable = (x: number, z: number) => {
  const i = Math.floor((x - W.x0) / W.step);
  const j = Math.floor((-z - W.y0) / W.step);
  return i >= 0 && j >= 0 && i < W.nx && j < W.ny && mask[j * W.nx + i] === 1;
};

type Solid = { circle: number[] } | { box: number[] };
const solids: Solid[] = [
  ...land.circles.map((circle) => ({ circle })),
  ...land.boxes.map((box) => ({ box })),
  ...(Object.values(land.obstacles) as Solid[]),
];
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

const free = (x: number, z: number) =>
  walkable(x, z) &&
  !(buckets.get(`${Math.floor(x / 8)},${Math.floor(z / 8)}`) ?? []).some((solid) => {
    if ("circle" in solid) return Math.hypot(x - solid.circle[0], z - solid.circle[1]) < solid.circle[2] + BODY;
    const [bx, bz, hx, hz] = solid.box;
    return Math.abs(x - bx) < hx + BODY && Math.abs(z - bz) < hz + BODY;
  });

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

  it("keeps the courtyard behind the drawbridge, and the dragon behind the leaves", () => {
    expect(reachable("courtyard")).toEqual(["courtyard"]);
    expect(reachable("dragon-cave")).toEqual(["dragon-cave"]);
  });
});
