// Domain model for Merlin's Castle. Static content (World) is loaded from
// data/world.json, generated from the original BBC BASIC by
// original/convert.py. GameState is the only thing that changes during play.

export type Direction = "north" | "east" | "south" | "west";

// The original checks exits in this order. When one item answers several
// obstacles in a room, the last match's use message wins.
export const EXIT_ORDER: Direction[] = ["south", "west", "north", "east"];

export type RoomId = string;
export type ItemId = string;

// ---- Static content -------------------------------------------------------

export interface World {
  title: string;
  author: string;
  year: number;
  startRoom: RoomId;
  homeRoom: RoomId; // items dropped here count towards the score (the grassy bank)
  carryLimit: number; // 5
  rooms: Record<RoomId, Room>;
  items: Record<ItemId, Item>;
}

// Text uses inline teletext colour codes, e.g. "a{green}grassy{green}bank{white}at".
// As on the BBC, each code takes up one space and the colour runs until the next
// code or the end of the screen row.
export type TeletextString = string;

export interface Room {
  description: TeletextString;
  firstVisitDescription?: TeletextString; // grassy bank: "You wake up on a grassy bank…"
  crowdedDescription?: TeletextString; // grassy bank with >12 items on it
  exits: Partial<Record<Direction, Exit>>;
  // "You are lost…" clue rooms. In the original every exit looped back; in
  // the remake arriving here ends the game.
  deadEnd?: true;
  image?: string;
}

export interface Exit {
  to: RoomId | null; // null: "You can't go that way." (after any obstacle)
  message?: TeletextString; // shown when passing through
  fatal?: true; // passing through kills you (the ladder slips, Merlin's trap)
  obstacle?: Obstacle;
}

export interface Obstacle {
  needs: ItemId; // item that must be in use to pass
  useMessage: TeletextString; // "The ladder leans against the wall."
  blocked: TeletextString; // "The wall is too high."
  fatal?: true; // trying without the item kills you
}

export interface Item {
  name: string;
  article: "a" | "an" | "some";
  score: number; // 3, or 11 for treasures (pearl, gold, emerald, ring, silver)
  startsIn: RoomId[]; // one chosen at random per game
  image?: string;
}

// ---- Runtime state --------------------------------------------------------

export type ItemLocation = RoomId | "carried";

export type GameStatus = "playing" | "won" | "dead" | "lost" | "quit";

export interface GameState {
  room: RoomId;
  itemLocations: Record<ItemId, ItemLocation>;
  // Items "used" in this room. Several can be in use at once, and they stay in
  // use even if dropped (original quirk). Cleared on entering any room.
  using: ItemId[];
  // Original C%: how many times the room has been shown (on arrival and after
  // a successful drop). Only the very first look uses firstVisitDescription.
  looks: number;
  status: GameStatus;
}

// ---- Commands and results -------------------------------------------------

export type Command =
  | { type: "go"; direction: Direction }
  | { type: "take"; item: ItemId | "all" }
  | { type: "drop"; item: ItemId | "all" }
  | { type: "use"; item: ItemId }
  | { type: "quit" };

// Tone maps to the original's message colours.
export type Tone =
  | "error" // red, with a beep: "You can't go that way."
  | "obstacle" // cyan: blocked and use messages
  | "pass" // green: messages when passing through
  | "item" // red: "You have a ladder."
  | "plain" // white: "You drop the ladder."
  | "victory"; // yellow: "You have solved the mystery of Merlin!"

export interface GameEvent {
  tone: Tone;
  text: TeletextString;
}

export interface TurnResult {
  state: GameState;
  events: GameEvent[];
}

// Engine surface (to implement):
//   newGame(world, random?): GameState
//   act(world, state, command): TurnResult
//   score(world, state): number          // sum of item scores at homeRoom
//   describe(world, state): { text, itemsHere, carried, exits }
