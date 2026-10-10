import { describe, expect, it } from "vitest";

import { EXIT_ORDER } from "../src/engine/types";
import { grow } from "../src/illustrated/hit";
import { itemWidth, placeThings, spotsFor } from "../src/illustrated/layout";
import { deathMoment, lostMoment } from "../src/illustrated/moments";
import { world } from "./helpers";

describe("object spots", () => {
  it("gives every object on the grassy bank its own spot", () => {
    const spots = spotsFor("grassy-bank", 20);
    const keys = new Set(spots.map((s) => `${s.x.toFixed(1)},${s.y.toFixed(1)}`));
    expect(keys.size).toBe(20);
  });

  it("puts a lone object in the middle of the floor", () => {
    const [spot] = spotsFor("charcoal-hut", 1);
    expect(spot.x).toBeGreaterThan(45);
    expect(spot.x).toBeLessThan(55);
    expect(spot.y).toBe(61);
  });

  it("keeps objects on the floor and inside the picture", () => {
    for (const spot of spotsFor("evergreen-glade", 25)) {
      expect(spot.x).toBeGreaterThan(5);
      expect(spot.x).toBeLessThan(95);
      expect(spot.y).toBeGreaterThan(40);
      expect(spot.y).toBeLessThan(75);
    }
  });

  it("keeps objects off the courtyard well", () => {
    for (const scale of [1, 1.7]) {
      for (const spot of spotsFor("courtyard", 20, scale)) {
        expect(spot.x > 36 && spot.x < 66 && spot.y < 70, `${spot.x},${spot.y}`).toBe(false);
      }
    }
  });

  it("finds a spot for every object, even on a phone", () => {
    const spots = spotsFor("courtyard", 20, 1.7);
    expect(new Set(spots.map((s) => `${s.x.toFixed(1)},${s.y.toFixed(1)}`)).size).toBe(20);
  });

  it("puts big objects behind small ones", () => {
    const [apple, ladder, ring] = placeThings("dragon-cave", ["apple", "ladder", "ring"], 1.7);
    expect(ladder.y).toBeLessThanOrEqual(apple.y);
    expect(ladder.y).toBeLessThanOrEqual(ring.y);
    const ids = ["water", "key", "rope", "ladder", "lamp", "apple"];
    const spots = placeThings("dragon-cave", ids, 1.7);
    const ladderY = spots[ids.indexOf("ladder")].y;
    expect(Math.min(...spots.map((s) => s.y))).toBe(ladderY);
  });

  it("draws a ladder bigger than a ring", () => {
    const spot = { x: 50, y: 60 };
    expect(itemWidth("ladder", spot)).toBeGreaterThan(itemWidth("ring", spot) * 2);
  });
});

describe("moments", () => {
  it("has a death picture for every way to die", () => {
    for (const [key, room] of Object.entries(world.rooms)) {
      for (const direction of EXIT_ORDER) {
        const exit = room.exits[direction];
        if (exit?.fatal || exit?.obstacle?.fatal)
          expect(deathMoment(key, direction), `${key} ${direction}`).toBeTruthy();
      }
    }
  });

  it("has a lost picture for every dead end", () => {
    for (const [key, room] of Object.entries(world.rooms)) {
      if (room.deadEnd) expect(lostMoment(key), key).toBeTruthy();
    }
  });
});

describe("clicking objects", () => {
  // A tiny ladder: two rails with rungs, and gaps between them.
  const ladder = Uint8Array.from(
    ["X...X", "XXXXX", "X...X", "X...X", "XXXXX", "X...X", "....."].join("").split(""),
    (c) => (c === "X" ? 1 : 0)
  );

  it("fills the gaps in a gappy object", () => {
    const hit = grow(ladder.slice(0, 25), 5, 1);
    expect(hit[2 * 5 + 2]).toBe(1); // between the rungs
  });

  it("doesn't spread far beyond it", () => {
    const big = new Uint8Array(20 * 20);
    big[10 * 20 + 10] = 1;
    const hit = grow(big, 20, 2);
    expect(hit[10 * 20 + 12]).toBe(1);
    expect(hit[10 * 20 + 13]).toBe(0);
    expect(hit[0]).toBe(0);
  });
});
