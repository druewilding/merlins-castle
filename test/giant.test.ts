// The giant in his cave: crouching in the way west, in front of it, facing
// in, so you bump into him, seeing him (not into the way behind him); and his boulder
// north of it, where he goes and sits, with no rocks in his way there, and
// leaving the ways across the cave clear once he's sitting.

import { describe, expect, it } from "vitest";

import land from "../src/three/models/land.json";
import { world } from "./helpers";

const BODY = 0.35; // as in src/three/player.ts
const RADIUS = 0.6; // his, sitting, at the model's size (land.py's GIANT_BODY)
const cave = land.halls.giant;
const {
  crouching: [cx, cz],
  sitting: [sx, sz],
  facing: [fx, fz],
  size,
} = land.giant;
const { box, reach } = land.obstacles["giant west"] as { box: number[]; reach: number };
const seat = RADIUS * size;

describe("the giant", () => {
  it("is what the cake gets you past, going west", () => {
    expect(world.rooms.giant.exits.west?.obstacle?.needs).toBe("cake");
  });

  it("crouches in the way west, in his cave, clear of its wall", () => {
    expect(Math.abs(cz - cave.z)).toBeLessThan(0.01);
    expect(cx).toBeLessThan(cave.x - cave.r / 2);
    expect(Math.hypot(cx - cave.x, cz - cave.z) + 2).toBeLessThan(cave.r);
  });

  it("stops you in front of him, going west, far enough off to see his face", () => {
    // (Where you bump into what's in the way: its east side, and its reach.)
    const bumped = box[0] + box[2] + reach + BODY;
    expect(bumped).toBeGreaterThan(cx + 3);
    expect(bumped).toBeLessThan(cx + 4.5);
  });

  it("sits on his boulder north of the way, facing in, clear of the wall, solid", () => {
    expect(sz).toBeLessThan(cave.z - 2); // (north: -z)
    expect(Math.hypot(sx - cave.x, sz - cave.z) + seat).toBeLessThan(cave.r);
    expect(fx * (cave.x - sx) + fz * (cave.z - sz)).toBeGreaterThan(0.9);
    expect(land.under.circles.some(([x, z, r]) => x === sx && z === sz && Math.abs(r - seat) < 0.01)).toBe(true);
  });

  it("has no stalagmites where he crouches, walks, or sits", () => {
    const rocks = land.under.circles.filter(
      ([x, z]) => Math.hypot(x - cave.x, z - cave.z) < cave.r + 1 && !(x === sx && z === sz)
    );
    for (let t = 0; t <= 1; t += 0.05) {
      const [x, z] = [cx + (sx - cx) * t, cz + (sz - cz) * t];
      for (const [rx, rz, r] of rocks) expect(Math.hypot(rx - x, rz - z) - r).toBeGreaterThan(seat + 1);
    }
  });

  it("leaves the ways clear, sitting: in from the east, and on south and west", () => {
    const legs = [
      [cave.x + cave.r, cave.z, cave.x, cave.z],
      [cave.x, cave.z, cave.x, cave.z + cave.r],
      [cave.x, cave.z, cave.x - cave.r, cave.z],
    ];
    for (const [x0, z0, x1, z1] of legs) {
      for (let t = 0; t <= 1; t += 0.05) {
        const [x, z] = [x0 + (x1 - x0) * t, z0 + (z1 - z0) * t];
        expect(Math.hypot(x - sx, z - sz) - seat).toBeGreaterThan(BODY + 0.5);
      }
    }
  });
});
