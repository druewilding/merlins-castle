// The dragon in its cave: standing just in from the tunnel south, beside
// it, breathing its fire across its mouth (in front of what stops you going
// on), and leaving the ways across the cave clear, in from the west and on,
// south and north.

import { describe, expect, it } from "vitest";

import land from "../src/three/models/land.json";
import { world } from "./helpers";

const BODY = 0.35; // as in src/three/player.ts
const spot = land.dragon;
const [x, z] = spot.at;
const cave = land.halls["dragon-cave"];
const { box } = land.obstacles["dragon-cave south"] as { box: number[] };
// Its shape on the ground: the circles round where it stands (land.py's dragon_shape).
const dragon = land.under.circles.filter(([cx, cz]) => Math.hypot(cx - x, cz - z) < 6.5);

function clearance(px: number, pz: number) {
  return Math.min(...dragon.map(([cx, cz, r]) => Math.hypot(px - cx, pz - cz) - r));
}

describe("the dragon", () => {
  it("is what the water gets you past, going south", () => {
    expect(world.rooms["dragon-cave"].exits.south?.obstacle?.needs).toBe("water");
  });

  it("stands in its cave, nearer the tunnel south than the middle, clear of its walls", () => {
    expect(Math.hypot(x - cave.x, z - cave.z)).toBeLessThan(cave.r - 4);
    expect(z - cave.z).toBeGreaterThan(3); // (south: +z)
    expect(dragon.length).toBeGreaterThanOrEqual(4);
    for (const [cx, cz, r] of dragon) expect(Math.hypot(cx - cave.x, cz - cave.z) + r).toBeLessThan(cave.r);
  });

  it("breathes its fire across the mouth of the tunnel south, in front of what stops you", () => {
    const [fx, , fz] = spot.fire;
    expect(Math.abs(fx - box[0])).toBeLessThan(box[2]);
    expect(fz).toBeGreaterThan(cave.z + cave.r - 3);
    expect(fz).toBeLessThan(box[1] - box[3]);
  });

  it("leaves the way clear, in from the west, through the middle, and on south and north", () => {
    const legs = [
      [cave.x - cave.r, cave.z, cave.x, cave.z],
      [cave.x, cave.z, cave.x, cave.z + cave.r],
      [cave.x, cave.z, cave.x, cave.z - cave.r],
    ];
    for (const [x0, z0, x1, z1] of legs) {
      for (let t = 0; t <= 1; t += 0.05) {
        expect(clearance(x0 + (x1 - x0) * t, z0 + (z1 - z0) * t)).toBeGreaterThan(BODY + 0.5);
      }
    }
  });
});
