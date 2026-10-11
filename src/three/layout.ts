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

/** Where you get lost in the mist above ground (underground comes later). */
export const LOST = entries(layout.lost)
  .filter(([exit]) => !underground(exit))
  .map(([exit, cr]) => ({ exit, ...spot(cr) }));
export const DEATHS = entries(layout.deaths).map(([exit, cr]) => ({ exit, ...spot(cr) }));

/** How near a place's middle you have to be to be in it. */
const REACH = 17;

/**
 * The place you're in. Between places, along a path or a tunnel, you're
 * still in the one you came from, as PLAN-V3.md says.
 */
export function placeAt(x: number, z: number, current: RoomId): RoomId {
  let best = current;
  let nearest = REACH;
  for (const [id, p] of PLACES) {
    const d = Math.hypot(x - p.x, z - p.z);
    if (d < nearest) {
      nearest = d;
      best = id;
    }
  }
  return best;
}
