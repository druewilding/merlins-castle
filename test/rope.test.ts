// The rope over the deep hole, and its exceptions. In the original, using
// it there says what crossing does ("You swing over a deep hole."), so in 3D
// those words wait till you swing over the hole's middle, not as it goes up
// (and only there: not for the goblins, tied up with it). And hung, it
// doesn't take you across till you choose to: walk up to the edge, and you
// catch it and swing over (not seeing it, holding on), landing clear of the
// hole on the far side.

import { type Object3D, Scene, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import land from "../src/three/models/land.json";
import type { Player } from "../src/three/player";
import { Rope, saidSwinging, SWUNG } from "../src/three/rope";
import { world } from "./helpers";

const FRAME = 1 / 60;
const WALK = 4; // metres a second
const BODY = 0.35; // as in src/three/player.ts
const hole = land.hole;
const [X, Z, , HALF_Z] = hole.box;

describe("the deep hole's words (said as you swing over it, not as the rope goes up)", () => {
  it("are the original's words for crossing, both ways", () => {
    expect(world.rooms.maze.exits.north?.obstacle?.useMessage).toBe("You swing over a deep hole.");
    expect(world.rooms["treasure-room"].exits.south?.obstacle?.useMessage).toBe("You pass safely over the hole.");
  });

  it("wait for the swing with the rope, from either side", () => {
    expect(saidSwinging(world, "rope", "maze")).toBe(true);
    expect(saidSwinging(world, "rope", "treasure-room")).toBe(true);
  });

  it("are said as it's used, for every other way an object opens (the goblins, too)", () => {
    expect(saidSwinging(world, "rope", "grand-hall")).toBe(false);
    for (const [room, place] of Object.entries(world.rooms)) {
      for (const [direction, exit] of Object.entries(place.exits)) {
        const needs = exit?.obstacle?.needs;
        if (!needs || SWUNG.includes(`${room} ${direction}`)) continue;
        expect(saidSwinging(world, needs, room), `${room} ${direction}`).toBe(false);
      }
    }
    expect(saidSwinging(world, "ladder", "maze")).toBe(false);
  });
});

// A player who only walks where it's put, and is taken along a path when told.
function standIn(z: number) {
  return {
    position: new Vector3(X, hole.floor, z),
    following: undefined as { path: (t: number) => Vector3; seconds: number; done: () => void } | undefined,
    get busy() {
      return Boolean(this.following);
    },
    follow(path: (t: number) => Vector3, seconds: number, done: () => void) {
      this.following = { path, seconds, done };
    },
  };
}

function hungOver(exit: string, from: number) {
  const scene = new Scene();
  const player = standIn(from);
  const said: string[] = [];
  const rope = new Rope(
    scene,
    hole,
    () => hole.floor,
    player as unknown as Player,
    false,
    () => {},
    (way) => said.push(way)
  );
  rope.hang(exit, true, true);
  const hanging = () => scene.getObjectByName("hanging") as Object3D;
  return { player, rope, said, hanging };
}

describe.each([
  ["maze north", 1],
  ["treasure-room south", -1],
])("the rope hung over the deep hole (%s)", (exit, side) => {
  const edge = Z + side * HALF_Z; // the hole's edge on your side

  it("takes you across only when you walk up to its edge, not as it goes up", () => {
    // (Hung from right at the edge, standing there: nothing, till you step away and come back.)
    const { player, rope } = hungOver(exit, edge + side * 0.3);
    for (let k = 0; k < 120; k++) rope.update(FRAME, () => {});
    expect(player.busy).toBe(false);
    for (let k = 0; k < 30; k++) {
      player.position.z += side * WALK * FRAME; // (back)
      rope.update(FRAME, () => {});
    }
    for (let k = 0; k < 60 && !player.busy; k++) {
      player.position.z -= side * WALK * FRAME; // (and up to it again)
      rope.update(FRAME, () => {});
    }
    expect(player.busy).toBe(true);
  });

  it("swings you over the hole, its words said over the middle, and lands you clear of it on the far side", () => {
    const { player, rope, said, hanging } = hungOver(exit, edge + side * 3);
    let over: string | undefined;
    for (let k = 0; k < 300 && !player.busy; k++) {
      player.position.z -= side * WALK * FRAME;
      rope.update(FRAME, (way) => (over = way));
    }
    expect(said).toEqual([]); // (not walking up to it)
    expect(hanging().visible).toBe(true);
    const { path, seconds, done } = player.following!;
    let saidAt: number | undefined;
    let deepest = Infinity;
    for (let t = 0; t <= 1; t = Math.min(1, t + FRAME / seconds)) {
      player.position.copy(path(t));
      rope.update(FRAME, (way) => (over = way));
      if (said.length && saidAt === undefined) saidAt = player.position.z;
      deepest = Math.min(deepest, player.position.y);
      // (Holding on, you don't see it.)
      if (t > 0.25 && t < 0.8) expect(hanging().visible).toBe(false);
      if (t === 1) break;
    }
    player.following = undefined;
    done();
    expect(said).toEqual([exit]);
    expect(Math.abs(saidAt! - Z)).toBeLessThan(0.5);
    expect(deepest).toBeLessThan(hole.floor - 0.5); // (dipping down into it)
    expect(over).toBe(exit);
    // On the far side, past its edge (and the reach of what's in the way there).
    expect((Z - player.position.z) * side).toBeGreaterThan(HALF_Z + BODY);
    expect(player.position.y).toBeCloseTo(hole.floor, 1);
  });
});
