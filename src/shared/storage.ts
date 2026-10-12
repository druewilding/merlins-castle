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
  three?: ThreeSave;
}

// Saved in the 3D version, also where you stood and where things lie (the
// other versions only need the game's state, and leave this be).
export interface ThreeSave {
  at: [x: number, z: number, yaw: number];
  slots: string[]; // what you carry, in your slots' order
  lying: Record<string, [x: number, z: number, yaw: number, floor?: number]>;
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

export function saveGame(name: string, state: GameState, three?: ThreeSave): boolean {
  const others = listSaves().filter((slot) => slot.name !== name);
  return write(SAVES, [{ name, savedAt: new Date().toISOString(), state, ...(three && { three }) }, ...others]);
}

// A name for the next save after `last`: "Tower" -> "Tower 2" -> "Tower 3",
// skipping any already taken, and kept within `max` characters.
export function nextSaveName(last: string, taken: string[], max = 24): string {
  const match = /^(.*?)\s*(\d+)$/.exec(last.trim());
  const base = (match ? match[1] : last.trim()) || "";
  // Counted exactly (BigInt), so even a huge number goes up by one.
  let n = match ? BigInt(match[2]) + 1n : 2n;
  const named = (k: bigint) => `${base.slice(0, max - String(k).length - 1).trimEnd()} ${k}`.trim();
  while (taken.includes(named(n))) n++;
  return named(n);
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

// ---- Which version to show ------------------------------------------------

// ---- Sound -----------------------------------------------------------------

// Music and sound effects are switched on and off separately. Both start from
// the single sound setting earlier versions had, so "off" stays off.
const SOUND = "merlins-castle:sound";
const MUSIC = "merlins-castle:music";
const EFFECTS = "merlins-castle:effects";

export function musicOn(): boolean {
  return read<boolean>(MUSIC, read<boolean>(SOUND, true));
}

export function setMusicOn(on: boolean): void {
  write(MUSIC, on);
}

export function effectsOn(): boolean {
  return read<boolean>(EFFECTS, read<boolean>(SOUND, true));
}

export function setEffectsOn(on: boolean): void {
  write(EFFECTS, on);
}

const MODE = "merlins-castle:mode";
const HANDOFF = "merlins-castle:handoff";
const HANDOFF_NAME = "merlins-castle:handoff-save-name";
const HANDOFF_3D = "merlins-castle:handoff-3d";

// A game carried over a reload, with the name it was last saved or loaded as
// (and, from the 3D version, where you were in it).
export interface Handoff {
  state: GameState;
  saveName: string;
  three?: ThreeSave;
}

export type Mode = "illustrated" | "classic";

export function getMode(): Mode {
  return read<Mode>(MODE, "illustrated") === "classic" ? "classic" : "illustrated";
}

// Switch version by reloading the page. A game in progress is handed over
// through sessionStorage, so it carries on in the other version.
export function switchMode(mode: Mode, game?: GameState | null, saveName = ""): void {
  write(MODE, mode);
  reloadWith(game, saveName);
}

// ---- Language -----------------------------------------------------------------

const LANGUAGE = "merlins-castle:language";

export type Language = "en" | "da";

// Chosen in the game, or else the browser's own language.
export function getLanguage(): Language {
  const chosen = read<Language | null>(LANGUAGE, null);
  if (chosen === "en" || chosen === "da") return chosen;
  return preferredLanguage(typeof navigator === "undefined" ? [] : navigator.languages);
}

// The first of the browser's languages (in its order of preference) that the
// game speaks, matched on the language part of the tag: "da-DK" is Danish.
export function preferredLanguage(tags: readonly string[]): Language {
  for (const tag of tags) {
    const language = tag.toLowerCase().split("-")[0];
    if (language === "en" || language === "da") return language;
  }
  return "en";
}

// Like switching version, the game carries on in the other language.
export function switchLanguage(language: Language, game?: GameState | null, saveName = ""): void {
  write(LANGUAGE, language);
  reloadWith(game, saveName);
}

// ---- The 3D version ----------------------------------------------------------

// The 3D version is its own page (/3d), a secret while it's being made: the
// other versions only show the way to it in a browser that has been there.
const FOUND_3D = "merlins-castle:found-3d";

export function found3d(): boolean {
  return read<boolean>(FOUND_3D, false);
}

export function find3d(): void {
  write(FOUND_3D, true);
}

// Going there, or back to the others (as the version chosen), the game
// carries on just the same.
export function goTo3d(game?: GameState | null, saveName = ""): void {
  handOver(game, saveName);
  location.assign("./3d");
}

export function leave3d(mode: Mode, game?: GameState | null, saveName = ""): void {
  write(MODE, mode);
  handOver(game, saveName);
  location.assign("./");
}

function reloadWith(game?: GameState | null, saveName = "") {
  handOver(game, saveName);
  location.reload();
}

function handOver(game?: GameState | null, saveName = "", three?: ThreeSave) {
  try {
    if (game) {
      sessionStorage.setItem(HANDOFF, JSON.stringify(game));
      sessionStorage.setItem(HANDOFF_NAME, saveName);
      if (three) sessionStorage.setItem(HANDOFF_3D, JSON.stringify(three));
    }
  } catch {
    // The game just won't carry over.
  }
}

export function takeHandoff(): Handoff | null {
  try {
    const raw = sessionStorage.getItem(HANDOFF);
    const saveName = sessionStorage.getItem(HANDOFF_NAME) ?? "";
    const three = sessionStorage.getItem(HANDOFF_3D);
    sessionStorage.removeItem(HANDOFF);
    sessionStorage.removeItem(HANDOFF_NAME);
    sessionStorage.removeItem(HANDOFF_3D);
    return raw
      ? { state: JSON.parse(raw) as GameState, saveName, ...(three && { three: JSON.parse(three) as ThreeSave }) }
      : null;
  } catch {
    return null;
  }
}
