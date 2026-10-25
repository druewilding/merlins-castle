// The flute in the beautiful chamber, playing: loud in the room, faint at the
// crossroads in the dark tunnels (where, in the original, you hear music),
// and not heard at all as far off as the dragon's cave.

import { describe, expect, it } from "vitest";

import { loudness } from "../src/three/flute";
import land from "../src/three/models/land.json";

const EYE = 1.65; // as in src/three/player.ts
const chamber = land.halls["beautiful-chamber"];
const flute = [chamber.x, chamber.floor + 1.4, chamber.z]; // (over its pedestal: land.py)

function heard(place: keyof typeof land.halls, dx = 0, dz = 0) {
  const { x, z, floor } = land.halls[place];
  return loudness(Math.hypot(x + dx - flute[0], floor + EYE - flute[1], z + dz - flute[2]));
}

describe("the flute", () => {
  it("is loud all over its chamber", () => {
    expect(heard("beautiful-chamber")).toBe(1);
    for (const [dx, dz] of [
      [chamber.r - 1, 0],
      [0, -(chamber.r - 1)],
      [-(chamber.r - 1), 0],
    ]) {
      expect(heard("beautiful-chamber", dx, dz)).toBeGreaterThan(0.5);
    }
  });

  it("is faint at the crossroads in the dark tunnels", () => {
    expect(heard("dark-tunnels")).toBeGreaterThan(0.03);
    expect(heard("dark-tunnels")).toBeLessThan(0.15);
  });

  it("is louder the nearer you come", () => {
    for (let far = 1; far < 60; far++) expect(loudness(far + 1)).toBeLessThanOrEqual(loudness(far));
  });

  it("isn't heard from the dragon's cave", () => {
    expect(heard("dragon-cave")).toBe(0);
  });
});
