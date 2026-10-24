// The trolls in their cave: sitting round the north of it, two either side of
// the way north, facing in, with no rocks crowding them, and leaving the ways
// across the cave clear, in from the east and on north.

import { describe, expect, it } from "vitest";

import land from "../src/three/models/land.json";
import { world } from "./helpers";

const BODY = 0.35; // as in src/three/player.ts
const RADIUS = 0.75; // a troll's, at the model's size (land.py's TROLL_BODY)
const cave = land.halls.trolls;
const { sitting, drum } = land.trolls;
const { box } = land.obstacles["trolls north"] as { box: number[] };
const trolls = sitting.map(({ at: [x, z], size }) => [x, z, RADIUS * size]);

function clearance(px: number, pz: number) {
  return Math.min(...trolls.map(([cx, cz, r]) => Math.hypot(px - cx, pz - cz) - r));
}

describe("the trolls", () => {
  it("are what the harp gets you past, going north", () => {
    expect(world.rooms.trolls.exits.north?.obstacle?.needs).toBe("harp");
  });

  it("are four, sitting round the north of their cave, clear of its walls, solid", () => {
    expect(trolls).toHaveLength(4);
    for (const [x, z, r] of trolls) {
      expect(z).toBeLessThan(cave.z - 3); // (north: -z)
      expect(Math.hypot(x - cave.x, z - cave.z) + r).toBeLessThan(cave.r);
      expect(land.under.circles.some(([cx, cz, cr]) => cx === x && cz === z && Math.abs(cr - r) < 0.01)).toBe(true);
    }
  });

  it("sit two either side of the way north, facing in", () => {
    expect(trolls.filter(([x]) => x < cave.x)).toHaveLength(2);
    expect(trolls.filter(([x]) => x > cave.x)).toHaveLength(2);
    for (const {
      at: [x, z],
      facing: [fx, fz],
    } of sitting) {
      expect(fx * (cave.x - x) + fz * (cave.z - z)).toBeGreaterThan(0);
    }
    // (And what stops you is in the way north, between them.)
    expect(Math.abs(box[0] - cave.x)).toBeLessThan(0.01);
    expect(box[1]).toBeLessThan(Math.min(...trolls.map(([, z]) => z)));
  });

  it("have one of them with the drum", () => {
    expect(sitting[drum]).toBeDefined();
  });

  it("have no stalagmites crowding them", () => {
    const rocks = land.under.circles.filter(
      ([x, z]) => Math.hypot(x - cave.x, z - cave.z) < cave.r + 1 && !trolls.some(([tx, tz]) => tx === x && tz === z)
    );
    for (const [x, z, r] of rocks) expect(clearance(x, z) - r).toBeGreaterThan(0.5);
  });

  it("leave the way clear, in from the east, through the middle, and on north", () => {
    const legs = [
      [cave.x + cave.r, cave.z, cave.x, cave.z],
      [cave.x, cave.z, cave.x, cave.z - cave.r],
    ];
    for (const [x0, z0, x1, z1] of legs) {
      for (let t = 0; t <= 1; t += 0.05) {
        expect(clearance(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t)).toBeGreaterThan(BODY + 0.5);
      }
    }
  });
});
