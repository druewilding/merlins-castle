// Where objects sit in a scene. Positions are percentages of the scene image,
// for the bottom-centre of each object, so they rest on the floor.

import type { ItemId, RoomId } from "../engine/types";

export interface Spot {
  x: number;
  y: number;
}

interface Zone {
  x0: number;
  x1: number;
  y0: number;
  y1: number;
}

// The open floor where objects can rest. Most rooms use the middle; rooms
// whose middle is taken (by a dragon, say) get their own zone.
const DEFAULT_ZONE: Zone = { x0: 24, x1: 76, y0: 54, y1: 68 };
const ROOM_ZONES: Partial<Record<RoomId, Zone>> = {
  "grassy-bank": { x0: 10, x1: 88, y0: 53, y1: 74 },
  "dragon-cave": { x0: 8, x1: 40, y0: 50, y1: 66 },
  "merlins-lair": { x0: 26, x1: 74, y0: 60, y1: 72 },
  courtyard: { x0: 14, x1: 86, y0: 66, y1: 74 },
};

// Roughly how far apart neighbouring spots are, so objects don't pile up.
const SPACING_X = 8.5;
const SPACING_Y = 7;

// Spots fill from the middle of the zone outwards, then are drawn back to front.
// Bigger objects (on small screens) need spots further apart.
export function spotsFor(room: RoomId, count: number, scale = 1): Spot[] {
  const zone = ROOM_ZONES[room] ?? DEFAULT_ZONE;
  const columns = Math.max(4, Math.round((zone.x1 - zone.x0) / (SPACING_X * scale)));
  const rows = Math.max(2, Math.round((zone.y1 - zone.y0) / (SPACING_Y * scale)) + 1);
  const grid: Spot[] = [];
  const dx = (zone.x1 - zone.x0) / (columns - 0.5);
  const dy = (zone.y1 - zone.y0) / (rows - 1);
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < columns; col++) {
      grid.push({ x: zone.x0 + dx * (col + (row % 2 ? 0.5 : 0)), y: zone.y0 + dy * row });
    }
  }
  const cx = (zone.x0 + zone.x1) / 2;
  const cy = (zone.y0 + zone.y1) / 2;
  grid.sort((a, b) => Math.hypot((a.x - cx) / 2, a.y - cy) - Math.hypot((b.x - cx) / 2, b.y - cy));
  const spots = Array.from({ length: count }, (_, i) => {
    const spot = grid[i % grid.length];
    const layer = Math.floor(i / grid.length);
    return { x: spot.x + layer * 1.5, y: spot.y - layer * 1.5 };
  });
  return spots;
}

// How big each object looks, relative to an ordinary one.
const SCALE: Partial<Record<ItemId, number>> = {
  ladder: 1.9,
  plank: 1.7,
  broom: 1.6,
  axe: 1.2,
  harp: 1.1,
  cake: 1.1,
  rope: 1,
  lamp: 1,
  mirror: 0.9,
  spell: 0.9,
  mask: 0.9,
  gold: 0.9,
  key: 0.8,
  water: 0.8,
  pearl: 0.8,
  silver: 0.8,
  apple: 0.7,
  emerald: 0.7,
  ring: 0.6,
  penny: 0.6,
};

// Width as a percentage of the scene. Objects further back look a little smaller.
export function itemWidth(id: ItemId, spot: Spot): number {
  const depth = 0.85 + ((spot.y - 50) / 20) * 0.3;
  return 6.5 * (SCALE[id] ?? 1) * depth;
}

// Where each of these objects goes. Big objects take the spots at the back, so
// they never hide small ones behind them.
export function placeThings(room: RoomId, ids: ItemId[], scale = 1): Spot[] {
  const spots = spotsFor(room, ids.length, scale).sort((a, b) => a.y - b.y || a.x - b.x);
  const bigFirst = ids.map((id, i) => ({ id, i })).sort((a, b) => (SCALE[b.id] ?? 1) - (SCALE[a.id] ?? 1));
  const placed: Spot[] = [];
  bigFirst.forEach(({ i }, rank) => (placed[i] = spots[rank]));
  return placed;
}
