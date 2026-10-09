// localStorage persistence: named save slots and the best score ever.
// Storage can be missing or throw (private windows, blocked site data), so
// every access falls back quietly.

import type { GameState } from "../engine/types";

const SAVES = "merlins-castle:saves";
const BEST = "merlins-castle:best";

export interface SaveSlot {
  name: string;
  savedAt: string;
  state: GameState;
}

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function listSaves(): SaveSlot[] {
  return read<SaveSlot[]>(SAVES, []);
}

export function saveGame(name: string, state: GameState): boolean {
  const others = listSaves().filter((slot) => slot.name !== name);
  return write(SAVES, [{ name, savedAt: new Date().toISOString(), state }, ...others]);
}

export function deleteSave(name: string): void {
  write(
    SAVES,
    listSaves().filter((slot) => slot.name !== name)
  );
}

export function bestScore(): number {
  return read<number>(BEST, 0);
}

export function recordScore(score: number): number {
  const best = Math.max(bestScore(), score);
  write(BEST, best);
  return best;
}
