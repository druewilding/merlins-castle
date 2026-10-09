import { describe, expect, it } from "vitest";

import { EXIT_ORDER } from "../src/engine/types";
import { itemWidth, spotsFor } from "../src/illustrated/layout";
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
