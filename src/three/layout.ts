// Where every place is in the 3D world, from art/blender/layout.json (which
// the Blender scripts read too), and which place you're standing in.

import layout from "../../art/blender/layout.json";
import type { RoomId } from "../engine/types";

export interface Spot {
  x: number;
  z: number;
}

const [OX, OY] = layout.origin;

/** A [column, row] on the grid, in three.js's x and z (north is -z). */
export function spot([col, row]: number[]): Spot {
  return { x: (col - OX) * layout.spacing, z: (row - OY) * layout.spacing };
}

// The layout's lists, without their "_" notes.
const entries = (record: object) => (Object.entries(record) as [string, number[]][]).filter(([key]) => key !== "_");

export const PLACES = new Map<RoomId, Spot>(entries(layout.places).map(([id, cr]) => [id, spot(cr)]));
const CAVES = new Set(layout.kinds.cave);
const underground = (exit: string) => CAVES.has(exit.split(" ")[0]);

/** Where you get lost in the mist: above ground, or along a way underground. */
export const LOST = entries(layout.lost).map(([exit, cr]) => ({ exit, under: underground(exit), ...spot(cr) }));
export const DEATHS = entries(layout.deaths).map(([exit, cr]) => ({ exit, ...spot(cr) }));

/** How near a place's middle you have to be to be in it. */
const REACH = 17;
/**
 * Places that reach further, metres ahead of their neighbours: the grassy
 * bank, where everything's brought back to count, so you needn't go right up
 * to it (you're on it two thirds of the way from the places round it).
 */
const PULL: Record<RoomId, number> = { "grassy-bank": 12 };

/**
 * The place you're in, on the land. Between places, along a path or a
 * tunnel, you're still in the one you came from, as PLAN-V3.md says. Places
 * you can only be in through a door or a cave's mouth (`inside`) don't count.
 */
export function placeAt(x: number, z: number, current: RoomId, inside: { has(id: string): boolean }): RoomId {
  let best = current;
  // (Out of one of those, on its doorstep, you're in the nearest place, however
  // far its middle: not still inside.)
  let nearest = inside.has(current) ? Infinity : REACH;
  for (const [id, p] of PLACES) {
    if (inside.has(id)) continue;
    const d = Math.hypot(x - p.x, z - p.z) - (PULL[id] ?? 0);
    if (d < nearest) {
      nearest = d;
      best = id;
    }
  }
  return best;
}
