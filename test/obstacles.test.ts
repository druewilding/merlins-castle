// Walking at an obstacle in 3D, from every side: the real player (its keys,
// its steps, frame by frame) on flat open ground, with one obstacle in it.
// An obstacle stops you going the way its exits go, and only that way: from
// the other side you walk right through it (all the way, past its middle),
// and once you're past its middle you can't turn back through it.

import { describe, expect, it } from "vitest";

import { type Box, type Circle, Player } from "../src/three/player";

// The player listens for keys on the window (each test's new player too),
// and for touches on the page.
type Listener = (event: { code: string; repeat: boolean }) => void;
const listening = new Map<string, Listener[]>();
Object.assign(globalThis, {
  addEventListener: (type: string, listener: Listener) =>
    listening.set(type, [...(listening.get(type) ?? []), listener]),
});
const press = (type: "keydown" | "keyup", code: string) =>
  listening.get(type)?.forEach((listener) => listener({ code, repeat: false }));

const AHEAD = 5; // as in src/three/main.ts
const FRAME = 1 / 60;
// Which way you face: 0 is north (-z).
const NORTH = 0;
const SOUTH = Math.PI;
const EAST = -Math.PI / 2;
const WEST = Math.PI / 2;

function standIn(obstacle: { circle?: Circle; box?: Box }) {
  const player = new Player(new EventTarget() as HTMLElement);
  player.standOn(
    () => 0,
    () => true
  );
  player.bounds = { west: -500, east: 500, north: -500, south: 500 };
  player.solid(obstacle.circle ? [obstacle.circle] : [], obstacle.box ? [obstacle.box] : []);
  const bumps: string[] = [];
  player.onBump = (exit) => bumps.push(exit);
  return { player, bumps };
}

/** Walks (W held) facing a way, for some seconds or until `until` says stop. */
function walk(player: Player, facing: number, seconds: number, until = () => false) {
  player.yaw = facing;
  press("keydown", "KeyW");
  for (let t = 0; t < seconds && !until(); t += FRAME) player.update(FRAME, true);
  press("keyup", "KeyW");
  // (And stand still a moment: a bounce dies down.)
  for (let t = 0; t < 1; t += FRAME) player.update(FRAME, true);
}

// Like the dense trees across the mountain path: one-way, going north.
const trees = (): Box => ({ x: 0, z: 0, halfX: 16, halfZ: 3.4, names: ["mountain-path north"], ahead: AHEAD });

describe("a one-way obstacle (the dense trees: north only)", () => {
  it("stops you going its way, before you reach it, and says why", () => {
    const { player, bumps } = standIn({ box: trees() });
    player.place(0, 20);
    walk(player, NORTH, 6);
    expect(player.position.z).toBeGreaterThan(3.4);
    expect(bumps).toContain("mountain-path north");
  });

  // However your steps fall about its middle (the step across it once
  // counted as turning back, and you were stuck there).
  it.each(Array.from({ length: 12 }, (_, k) => k / 100))(
    "lets you walk right through it the other way (starting %s m further off)",
    (offset) => {
      const { player, bumps } = standIn({ box: trees() });
      player.place(0, -20 - offset, SOUTH);
      walk(player, SOUTH, 10, () => player.position.z > 15);
      expect(player.position.z).toBeGreaterThan(15);
      expect(bumps).toEqual([]);
    }
  );

  it("won't let you turn back through it once you're past its middle", () => {
    const { player, bumps } = standIn({ box: trees() });
    player.place(0, -20, SOUTH);
    walk(player, SOUTH, 10, () => player.position.z > 1);
    walk(player, NORTH, 3);
    expect(player.position.z).toBeGreaterThan(0.5);
    expect(bumps).toContain("mountain-path north");
  });

  it("lets you go back the way you came before its middle", () => {
    const { player, bumps } = standIn({ box: trees() });
    player.place(0, -20, SOUTH);
    walk(player, SOUTH, 10, () => player.position.z > -1.5);
    walk(player, NORTH, 6);
    expect(player.position.z).toBeLessThan(-10);
    expect(bumps).toEqual([]);
  });

  it("stops you coming at it from the side, on the side it's shut from", () => {
    const { player, bumps } = standIn({ box: trees() });
    player.place(30, 2, WEST);
    walk(player, WEST, 10);
    expect(player.position.x).toBeGreaterThan(16);
    expect(bumps).toContain("mountain-path north");
  });
});

describe("a two-way obstacle (a gate, shut from both sides)", () => {
  const gate = (): Box => ({
    x: 0,
    z: 0,
    halfX: 3,
    halfZ: 0.3,
    names: ["rusty-gate north", "yellow-flowers south"],
    ahead: AHEAD,
  });

  it("stops you from the south", () => {
    const { player, bumps } = standIn({ box: gate() });
    player.place(0, 15);
    walk(player, NORTH, 6);
    expect(player.position.z).toBeGreaterThan(0.3);
    expect(bumps).toContain("rusty-gate north");
  });

  it("stops you from the north", () => {
    const { player, bumps } = standIn({ box: gate() });
    player.place(0, -15, SOUTH);
    walk(player, SOUTH, 6);
    expect(player.position.z).toBeLessThan(-0.3);
    expect(bumps).toContain("yellow-flowers south");
  });
});

describe("a round one-way obstacle (west only)", () => {
  const round = (): Circle => ({ x: 0, z: 0, r: 2, names: ["cave west"], ahead: AHEAD });

  it("stops you going west", () => {
    const { player, bumps } = standIn({ circle: round() });
    player.place(15, 0, WEST);
    walk(player, WEST, 6);
    expect(player.position.x).toBeGreaterThan(2);
    expect(bumps).toContain("cave west");
  });

  it.each(Array.from({ length: 12 }, (_, k) => k / 100))(
    "lets you walk right through it going east (starting %s m further off)",
    (offset) => {
      const { player, bumps } = standIn({ circle: round() });
      player.place(-15 - offset, 0, EAST);
      walk(player, EAST, 10, () => player.position.x > 12);
      expect(player.position.x).toBeGreaterThan(12);
      expect(bumps).toEqual([]);
    }
  );
});
