// The drawbridge over the moat. Up, it stops you on the bank, short of the
// guards at the toll gate; paid the penny, it's lowered across the water
// (and you can't walk out onto it till it's down); it stays down while
// you're in the castle, however you came in; and coming out over it, it's
// raised again once you're off it, ready for the next penny.

import { Object3D, Scene } from "three";
import { describe, expect, it } from "vitest";

import { Drawbridge, type DrawbridgeSpot, RAISED, wantedDown } from "../src/three/drawbridge";
import { PLACES } from "../src/three/layout";
import land from "../src/three/models/land.json";
import { world } from "./helpers";

const BODY = 0.35; // as in src/three/player.ts
const GUARD = 0.38; // as in src/three/guards.ts
const FRAME = 1 / 60;
const spot = land.drawbridge as DrawbridgeSpot;
const [hingeX, hingeY, hingeZ] = spot.hinge;
const tip = hingeZ - spot.length; // (where it rests, on the landing)
const { box, reach } = land.obstacles["moat south"] as { box: number[]; reach: number };
const [, boxZ, , boxHalfZ] = box;

describe("the moat's drawbridge, up", () => {
  it("is what the penny opens, from the moat (and nothing stops you walking out of the courtyard)", () => {
    expect(world.rooms.moat.exits.south?.obstacle?.needs).toBe("penny");
    expect(world.rooms.courtyard.exits.north?.obstacle).toBeUndefined();
    expect(Object.keys(land.obstacles)).not.toContain("courtyard north");
  });

  it("stops you on the bank, just short of the guards, before the water", () => {
    expect(boxZ - boxHalfZ).toBeCloseTo(tip, 1); // (the water's edge, where the bridge comes down)
    const stopped = boxZ - boxHalfZ - reach - BODY;
    for (const [, z] of spot.guards) expect(stopped).toBeLessThan(z - GUARD);
    expect(stopped).toBeGreaterThan(tip - 4);
  });

  it("is right across the way, from the bank to the castle's wall", () => {
    expect(box[2]).toBeGreaterThan(spot.half);
    expect(boxZ + boxHalfZ).toBeGreaterThan(hingeZ - 1.5);
    expect(hingeZ).toBeLessThan(spot.castle[2]); // (outside the wall, at its foot)
  });

  it("stands against the gatehouse, under its chains' holes", () => {
    for (const [, y] of spot.anchors) {
      expect(hingeY + spot.length * Math.sin(RAISED)).toBeLessThan(y);
    }
  });
});

describe("the guards at the toll gate", () => {
  it("stand on the bank either side of the way onto it, leaving room between them", () => {
    const [[x0, z0], [x1, z1]] = spot.guards;
    expect(Math.sign(x0 - hingeX)).toBe(-Math.sign(x1 - hingeX));
    for (const z of [z0, z1]) expect(z + GUARD).toBeLessThan(tip);
    expect(Math.abs(x1 - x0) - 2 * GUARD).toBeGreaterThan(2 * BODY + 2);
  });
});

describe("when the drawbridge is down", () => {
  const bank = { x: hingeX, z: tip - 2 };
  const on = { x: hingeX, z: tip + 2 };

  it("is down while the penny's paid at the moat", () => {
    expect(wantedDown(spot, true, "moat", bank, false)).toBe(true);
    expect(wantedDown(spot, false, "moat", bank, false)).toBe(false);
  });

  it("stays down while you're anywhere in the castle (however you came in)", () => {
    const [west, east, north, south] = spot.castle;
    const inside = [...PLACES].filter(([, p]) => p.x > west && p.x < east && p.z > north && p.z < south);
    expect(inside.map(([id]) => id)).toEqual(expect.arrayContaining(["courtyard", "coach-house", "grand-hall"]));
    for (const [id] of inside) expect(wantedDown(spot, false, id, PLACES.get(id)!, false), id).toBe(true);
    for (const id of ["moat", "river-south-bank", "grassy-bank"]) {
      expect(wantedDown(spot, false, id, PLACES.get(id)!, true), id).toBe(false);
    }
  });

  it("coming out of the castle over it, stays down till you're off it, onto the landing", () => {
    expect(wantedDown(spot, false, "moat", on, true)).toBe(true);
    expect(wantedDown(spot, false, "moat", { x: hingeX, z: tip - 0.5 }, true)).toBe(false);
    // (Up, standing where it would come down doesn't bring it down.)
    expect(wantedDown(spot, false, "moat", on, false)).toBe(false);
  });
});

function bridge(reducedMotion = false) {
  const model = new Object3D();
  const heard: string[] = [];
  const drawbridge = new Drawbridge(
    new Scene(),
    model,
    spot,
    reducedMotion,
    (down) => heard.push(down ? "lowering" : "raising"),
    () => heard.push("landed")
  );
  const run = (seconds: number) => {
    for (let t = 0; t < seconds; t += FRAME) drawbridge.update(FRAME);
  };
  return { model, drawbridge, heard, run };
}

describe("the drawbridge, moving", () => {
  it("starts up", () => {
    const { model, drawbridge } = bridge();
    expect(model.rotation.x).toBeCloseTo(RAISED);
    expect(drawbridge.down).toBe(false);
  });

  it("paid, waits for the penny to be taken, then comes down slowly, landing with a bump (only then down)", () => {
    const { model, drawbridge, heard, run } = bridge();
    drawbridge.set(true, false, 1.2);
    run(1);
    expect(model.rotation.x).toBeCloseTo(RAISED);
    expect(heard).toEqual([]);
    run(3);
    expect(heard).toEqual(["lowering"]);
    expect(model.rotation.x).toBeGreaterThan(0.1);
    expect(model.rotation.x).toBeLessThan(RAISED - 0.1);
    expect(drawbridge.down).toBe(false);
    expect(drawbridge.lowering).toBe(true);
    run(5);
    expect(heard).toEqual(["lowering", "landed"]);
    expect(drawbridge.down).toBe(true);
    expect(model.rotation.x).toBeCloseTo(0);
  });

  it("goes back up again, wanted up", () => {
    const { model, drawbridge, heard, run } = bridge();
    drawbridge.set(true, true);
    expect(drawbridge.down).toBe(true);
    drawbridge.set(false);
    expect(drawbridge.down).toBe(false);
    expect(drawbridge.lowering).toBe(false);
    run(7);
    expect(heard).toEqual(["raising"]);
    expect(model.rotation.x).toBeCloseTo(RAISED);
  });

  it("loading, or with reduced motion, is where it's wanted at once", () => {
    const { drawbridge, heard } = bridge();
    drawbridge.set(true, true);
    expect(drawbridge.down).toBe(true);
    const still = bridge(true);
    still.drawbridge.set(true);
    still.run(FRAME);
    expect(still.drawbridge.down).toBe(true);
    expect(still.model.rotation.x).toBe(0);
    expect([...heard, ...still.heard]).toEqual([]);
  });
});
