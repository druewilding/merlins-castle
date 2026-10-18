// Walking at an obstacle in 3D, from every side: the real player (its keys,
// its steps, frame by frame) on flat open ground, with one obstacle in it.
// An obstacle stops you going the way its exits go, and only that way: from
// the other side you walk right through it (all the way, past its middle),
// and once you're past its middle you can't turn back through it. Except a
// way that kills you: come into it the free way, you can step back and forth
// in it; only walking into it again from its far side kills you.

import { Object3D, Scene } from "three";
import { describe, expect, it } from "vitest";

import { Plank } from "../src/three/plank";
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

/**
 * Walks (W held, or another key: A steps sideways) facing a way, for some
 * seconds or until `until` says stop; and each frame, anything else that
 * goes on (the plank, say).
 */
function walk(
  player: Player,
  facing: number,
  seconds: number,
  until = () => false,
  key = "KeyW",
  each = (_dt: number) => {}
) {
  const frame = () => {
    player.update(FRAME, true);
    each(FRAME);
  };
  player.yaw = facing;
  press("keydown", key);
  for (let t = 0; t < seconds && !until(); t += FRAME) frame();
  press("keyup", key);
  // (And stand still a moment: a bounce dies down.)
  for (let t = 0; t < 1; t += FRAME) frame();
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

// Merlin's trap: no object gets you past it, and there's nothing beyond it
// to have come from, so it catches you all round (as main.ts makes any way
// that only kills you), whichever way you come at its treasure.
describe("a way that only kills you (Merlin's trap, round its treasure)", () => {
  const trap = (): Circle => ({ x: 0, z: 0, r: 1, names: ["mountain east"], ahead: 2, allRound: true });

  it.each(Array.from({ length: 8 }, (_, k) => k * 45))("catches you coming at it from %s°", (degrees) => {
    const { player, bumps } = standIn({ circle: trap() });
    const a = (degrees * Math.PI) / 180;
    player.place(Math.sin(a) * 15, Math.cos(a) * 15, 0);
    walk(player, Math.atan2(Math.sin(a), Math.cos(a)), 8); // (facing its middle)
    expect(bumps).toContain("mountain east");
    expect(Math.hypot(player.position.x, player.position.z)).toBeGreaterThan(2);
  });
});

describe("a way that kills you (the witches: west only)", () => {
  const witches = (): Box => ({
    x: 0,
    z: 0,
    halfX: 1,
    halfZ: 5.5,
    names: ["forest-witches west"],
    ahead: AHEAD,
    fatal: true,
  });
  // (Facing the witches, more or less: a little north of west, so stepping
  // sideways (A) takes you south, and a little back west, towards its middle.)
  const ROUGHLY_WEST = WEST - 0.15;

  it("catches you walking into it from their clearing", () => {
    const { player, bumps } = standIn({ box: witches() });
    player.place(20, 0, WEST);
    walk(player, WEST, 6);
    expect(player.position.x).toBeGreaterThan(1);
    expect(bumps).toContain("forest-witches west");
  });

  it("lets you walk right through it from the crossroads", () => {
    const { player, bumps } = standIn({ box: witches() });
    player.place(-20, 0, EAST);
    walk(player, EAST, 10, () => player.position.x > 15);
    expect(player.position.x).toBeGreaterThan(15);
    expect(bumps).toEqual([]);
  });

  it("lets you step sideways, back towards its middle, just past it from the crossroads", () => {
    const { player, bumps } = standIn({ box: witches() });
    player.place(-20, 0, EAST);
    walk(player, EAST, 10, () => player.position.x > 0.5);
    walk(player, ROUGHLY_WEST, 1.5, () => false, "KeyA");
    walk(player, ROUGHLY_WEST, 1.5, () => false, "KeyD");
    expect(bumps).toEqual([]);
  });

  it("lets you turn back to the crossroads, past its middle", () => {
    const { player, bumps } = standIn({ box: witches() });
    player.place(-20, 0, EAST);
    walk(player, EAST, 10, () => player.position.x > 3);
    walk(player, WEST, 10, () => player.position.x < -15);
    expect(player.position.x).toBeLessThan(-15);
    expect(bumps).toEqual([]);
  });

  it("catches you once you've left it for their clearing and walk back into it", () => {
    const { player, bumps } = standIn({ box: witches() });
    player.place(-20, 0, EAST);
    walk(player, EAST, 10, () => player.position.x > 10);
    walk(player, WEST, 6);
    expect(player.position.x).toBeGreaterThan(1);
    expect(bumps).toContain("forest-witches west");
  });

  // The broom used, they've flown off (it's open); gone on to the
  // crossroads, it closes round you, just past its middle; come back over
  // its middle, you're still in it, going through it the free way.
  it("lets you step about in it when it closes round you, as the broom stops working", () => {
    const { player, bumps } = standIn({});
    player.place(-0.3, 0, WEST);
    player.solid([], [witches()]);
    player.throughHere();
    walk(player, EAST, 10, () => player.position.x > 0.4);
    walk(player, ROUGHLY_WEST, 1.5, () => false, "KeyA");
    walk(player, ROUGHLY_WEST, 1.5, () => false, "KeyD");
    expect(bumps).toEqual([]);
    walk(player, EAST, 10, () => player.position.x > 10);
    walk(player, WEST, 6);
    expect(bumps).toContain("forest-witches west");
  });

  it("still won't let you turn back through it once you're past its middle, if it doesn't kill you", () => {
    const { player, bumps } = standIn({ box: { ...witches(), fatal: false } });
    player.place(-20, 0, EAST);
    walk(player, EAST, 10, () => player.position.x > 0.5);
    walk(player, ROUGHLY_WEST, 1.5, () => false, "KeyA");
    expect(bumps).toContain("forest-witches west");
  });
});

// Which way kills you is the game's (src/three/main.ts): walking into the
// river from the north bank ("deep-river south") you're swept away; from the
// south bank ("river-south-bank north") you fall in, but get out safely.
describe("the deep river where it narrows (south: swept away; north: you get out)", () => {
  // As in land.json (round the narrows' middle), and as main.ts puts it.
  const river = (): Box => ({
    x: 0,
    z: 0,
    halfX: 13,
    halfZ: 3.2,
    names: ["deep-river south", "river-south-bank north"],
    ahead: 0.5,
    fatal: true,
  });
  const PLANK = 7; // metres long (items.glb)

  /**
   * The plank used, laid across from the bank you're on, the river open (as
   * main.ts does); across, it's no longer in use, and the river's back.
   */
  function withPlank(player: Player, south: boolean) {
    const half = PLANK / 2;
    const plank = new Plank(
      new Scene(),
      new Object3D(),
      () => 0,
      player,
      true,
      () => {},
      () => {}
    );
    player.solid([], []);
    plank.lay(
      south ? "deep-river south" : "river-south-bank north",
      [0, south ? -half : half],
      [0, south ? half : -half],
      true,
      true
    );
    const crossed: string[] = [];
    const each = (dt: number) =>
      plank.update(dt, (exit) => {
        crossed.push(exit);
        plank.away();
        player.solid([], [river()]);
        player.throughHere();
      });
    return { each, crossed };
  }

  it("sweeps you away walking into it from the north bank", () => {
    const { player, bumps } = standIn({ box: river() });
    player.place(0, -15, SOUTH);
    walk(player, SOUTH, 6);
    expect(player.position.z).toBeLessThan(-3.2);
    expect(bumps).toContain("deep-river south");
    expect(bumps).not.toContain("river-south-bank north");
  });

  it("only bumps you back walking into it from the south bank", () => {
    const { player, bumps } = standIn({ box: river() });
    player.place(0, 15, NORTH);
    walk(player, NORTH, 6);
    expect(player.position.z).toBeGreaterThan(3.2);
    expect(bumps).toContain("river-south-bank north");
    expect(bumps).not.toContain("deep-river south");
  });

  // (It takes you up before you're in the river's reach: you're never in it.)
  it("takes you across on the plank from the north bank", () => {
    const { player, bumps } = standIn({});
    const { each, crossed } = withPlank(player, true);
    player.place(0, -15, SOUTH);
    walk(player, SOUTH, 10, () => player.position.z > 4.5 && !player.busy, "KeyW", each);
    expect(crossed).toEqual(["deep-river south"]);
    expect(player.position.z).toBeGreaterThan(4.5);
    expect(bumps).toEqual([]);
  });

  it("takes you across on the plank from the south bank", () => {
    const { player, bumps } = standIn({});
    const { each, crossed } = withPlank(player, false);
    player.place(0, 15, NORTH);
    walk(player, NORTH, 10, () => player.position.z < -4.5 && !player.busy, "KeyW", each);
    expect(crossed).toEqual(["river-south-bank north"]);
    expect(player.position.z).toBeLessThan(-4.5);
    expect(bumps).toEqual([]);
  });

  // Off the plank's far end, you're already out of the river's reach: a step
  // back is walking into it from the bank you're on now.
  it("sweeps you away stepping back into it, across on the plank to the north bank", () => {
    const { player, bumps } = standIn({});
    const { each } = withPlank(player, false);
    player.place(0, 15, NORTH);
    walk(player, NORTH, 10, () => player.position.z < -4.5 && !player.busy, "KeyW", each);
    walk(player, SOUTH, 3, () => false, "KeyW", each);
    expect(player.position.z).toBeLessThan(-3.2);
    expect(bumps).toContain("deep-river south");
  });

  it("only bumps you back stepping back into it, across on the plank to the south bank", () => {
    const { player, bumps } = standIn({});
    const { each } = withPlank(player, true);
    player.place(0, -15, SOUTH);
    walk(player, SOUTH, 10, () => player.position.z > 4.5 && !player.busy, "KeyW", each);
    walk(player, NORTH, 3, () => false, "KeyW", each);
    expect(player.position.z).toBeGreaterThan(3.2);
    expect(bumps).toContain("river-south-bank north");
    expect(bumps).not.toContain("deep-river south");
  });
});
