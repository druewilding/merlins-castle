// The giant in his cave: sitting on his boulder beside the way west, north of
// it, facing in, where you bump into what's in the way (him by you); with no
// rocks crowding him, and leaving the ways across the cave clear, and the way
// west itself.

import { describe, expect, it } from "vitest";

import land from "../src/three/models/land.json";
import { world } from "./helpers";

const BODY = 0.35; // as in src/three/player.ts
const RADIUS = 0.6; // his, sitting, at the model's size (land.py's GIANT_BODY)
const cave = land.halls.giant;
const {
  at: [x, z],
  facing: [fx, fz],
  size,
} = land.giant;
const { box, reach } = land.obstacles["giant west"] as { box: number[]; reach: number };
const r = RADIUS * size;

function clearance(px: number, pz: number) {
  return Math.hypot(px - x, pz - z) - r;
}

describe("the giant", () => {
  it("is what the cake gets you past, going west", () => {
    expect(world.rooms.giant.exits.west?.obstacle?.needs).toBe("cake");
  });

  it("sits beside the way west, north of it, facing in, clear of the wall, solid", () => {
    expect(z).toBeLessThan(cave.z - 2); // (north: -z)
    expect(x).toBeLessThan(cave.x - cave.r / 2);
    expect(Math.hypot(x - cave.x, z - cave.z) + r).toBeLessThan(cave.r);
    expect(fx * (cave.x - x) + fz * (cave.z - z)).toBeGreaterThan(0.9);
    expect(land.under.circles.some(([cx, cz, cr]) => cx === x && cz === z && Math.abs(cr - r) < 0.01)).toBe(true);
  });

  it("is in view, by you, when you bump into what's in the way west", () => {
    const bumped = box[0] + box[2] + reach + BODY;
    expect(Math.hypot(bumped - x, cave.z - z)).toBeLessThan(6);
    expect(Math.atan2(cave.z - z, bumped - x)).toBeLessThan(0.9); // (radians off straight ahead, going west)
  });

  it("has no stalagmites crowding him", () => {
    const rocks = land.under.circles.filter(
      ([cx, cz]) => Math.hypot(cx - cave.x, cz - cave.z) < cave.r + 1 && !(cx === x && cz === z)
    );
    for (const [cx, cz, cr] of rocks) expect(clearance(cx, cz) - cr).toBeGreaterThan(1);
  });

  it("leaves the ways clear: in from the east, on south, and west past him", () => {
    const legs = [
      [cave.x + cave.r, cave.z, cave.x, cave.z],
      [cave.x, cave.z, cave.x, cave.z + cave.r],
      [cave.x, cave.z, cave.x - cave.r - 1, cave.z],
    ];
    for (const [x0, z0, x1, z1] of legs) {
      for (let t = 0; t <= 1; t += 0.05) {
        expect(clearance(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t)).toBeGreaterThan(BODY + 0.5);
      }
    }
  });
});
