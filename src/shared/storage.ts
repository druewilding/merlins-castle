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

// A name for the next save after `last`: "Tower" -> "Tower 2" -> "Tower 3",
// skipping any already taken, and kept within `max` characters.
export function nextSaveName(last: string, taken: string[], max = 24): string {
  const match = /^(.*?)\s*(\d+)$/.exec(last.trim());
  const base = (match ? match[1] : last.trim()) || "";
  let n = match ? Number(match[2]) + 1 : 2;
  const named = (k: number) => `${base.slice(0, max - String(k).length - 1).trimEnd()} ${k}`.trim();
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

export type Mode = "illustrated" | "classic";

export function getMode(): Mode {
  return read<Mode>(MODE, "illustrated") === "classic" ? "classic" : "illustrated";
}

// Switch version by reloading the page. A game in progress is handed over
// through sessionStorage, so it carries on in the other version.
export function switchMode(mode: Mode, game?: GameState | null): void {
  write(MODE, mode);
  reloadWith(game);
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
export function switchLanguage(language: Language, game?: GameState | null): void {
  write(LANGUAGE, language);
  reloadWith(game);
}

function reloadWith(game?: GameState | null) {
  try {
    if (game) sessionStorage.setItem(HANDOFF, JSON.stringify(game));
  } catch {
    // The game just won't carry over.
  }
  location.reload();
}

export function takeHandoff(): GameState | null {
  try {
    const raw = sessionStorage.getItem(HANDOFF);
    sessionStorage.removeItem(HANDOFF);
    return raw ? (JSON.parse(raw) as GameState) : null;
  } catch {
    return null;
  }
}
