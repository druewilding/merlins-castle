// The rules of Merlin's Castle, ported from PROCask, PROCmove, PROCget,
// PROCdrop, PROCuse and PROCscore in the original MERLIN2 program.

import {
  type Command,
  type Direction,
  EXIT_ORDER,
  type GameEvent,
  type GameState,
  type ItemId,
  type Messages,
  type TeletextString,
  type TurnResult,
  type World,
} from "./types";

export type Random = () => number;

const MESSAGES: Messages = {
  cantGo: "You can't go that way.",
  impossible: "That's impossible.",
  carryingTooMuch: "You're carrying too much.",
  alreadyGot: "You've already got it.",
  notHere: "It's not here.",
  nothingHere: "There's nothing here.",
  allTaken: "All taken.",
  youHave: "You have{red}%a.",
  notTaken: "You haven't taken that.",
  youDrop: "You drop the{red}%d.",
  allDropped: "All dropped.",
  notPossible: "That's not possible",
  haventGot: "You haven't got that.",
  nothingHappens: "Nothing happens.",
  victory: "You have solved the mystery of Merlin!",
  youCanSee: "You can see ",
};

// The engine's messages in the world's language.
export function messages(world: World): Messages {
  return world.messages ?? MESSAGES;
}

export function newGame(world: World, random: Random = Math.random): GameState {
  const itemLocations: GameState["itemLocations"] = {};
  for (const [id, item] of Object.entries(world.items)) {
    itemLocations[id] = item.startsIn[Math.floor(random() * item.startsIn.length)];
  }
  return { room: world.startRoom, itemLocations, using: [], looks: 1, status: "playing", found: [] };
}

export function score(world: World, state: GameState): number {
  return itemsIn(world, state, world.homeRoom).reduce((sum, id) => sum + world.items[id].score, 0);
}

export function bestPossibleScore(world: World): number {
  return Object.values(world.items).reduce((sum, item) => sum + item.score, 0);
}

export function itemsIn(world: World, state: GameState, location: string): ItemId[] {
  return Object.keys(world.items).filter((id) => state.itemLocations[id] === location);
}

export function carried(world: World, state: GameState): ItemId[] {
  return itemsIn(world, state, "carried");
}

// Objects in use that open a way out of this room, in the order they were
// used. Not in the original: the illustrated version paints them in.
export function effects(world: World, state: GameState): ItemId[] {
  const needed = Object.values(world.rooms[state.room].exits).map((exit) => exit?.obstacle?.needs);
  return state.using.filter((id) => needed.includes(id));
}

export function itemLabel(world: World, id: ItemId): string {
  const item = world.items[id];
  return `${item.article} ${item.name}`;
}

export interface View {
  description: TeletextString;
  itemsHere: ItemId[];
  carried: ItemId[];
  exits: Direction[];
  score: number;
}

export function describe(world: World, state: GameState): View {
  const room = world.rooms[state.room];
  let description = room.description;
  if (state.looks === 1 && room.firstVisitDescription) description = room.firstVisitDescription;
  if (state.looks > 1 && room.crowdedDescription && itemsIn(world, state, world.homeRoom).length > 12) {
    description = room.crowdedDescription;
  }
  return {
    description,
    itemsHere: itemsIn(world, state, state.room),
    carried: carried(world, state),
    exits: EXIT_ORDER.filter((d) => room.exits[d]),
    score: score(world, state),
  };
}

// Objects in alphabetical order, for listing. (The original listed them in
// the order of its DATA statements.)
export function byName(world: World, ids: ItemId[]): ItemId[] {
  return [...ids].sort((a, b) => world.items[a].name.localeCompare(world.items[b].name, world.locale ?? "en"));
}

// "You can see a{red}cake,{red}a{red}ladder." — the original builds the list
// with red control codes in place of spaces, and prints it all in red.
export function itemsSentence(world: World, ids: ItemId[], prefix = messages(world).youCanSee): TeletextString {
  const parts = byName(world, ids).map((id) => `${world.items[id].article}{red}${world.items[id].name}`);
  return `${prefix}${parts.join(",{red}")}.`;
}

export function act(world: World, state: GameState, command: Command): TurnResult {
  if (state.status !== "playing") return { state, events: [] };
  const turn = new Turn(world, structuredClone(state));
  switch (command.type) {
    case "go":
      turn.go(command.direction);
      break;
    case "take":
      if (command.item === "all") turn.takeAll();
      else turn.take(command.item);
      break;
    case "drop":
      if (command.item === "all") turn.dropAll();
      else turn.drop(command.item);
      break;
    case "use":
      turn.use(command.item);
      break;
    case "quit":
      turn.state.status = "quit";
      break;
  }
  turn.checkVictory();
  return { state: turn.state, events: turn.events };
}

class Turn {
  events: GameEvent[] = [];
  private text: Messages;

  constructor(
    private world: World,
    public state: GameState
  ) {
    this.text = messages(world);
  }

  // A message about an object: "%a" with its article, "%d" its definite form.
  private withItem(message: TeletextString, id: ItemId): TeletextString {
    const item = this.world.items[id];
    return message.replace("%a", itemLabel(this.world, id)).replace("%d", item.definite ?? item.name);
  }

  private say(tone: GameEvent["tone"], text: TeletextString) {
    this.events.push({ tone, text });
  }

  go(direction: Direction) {
    const exit = this.world.rooms[this.state.room].exits[direction];
    const obstacle = exit?.obstacle;
    if (obstacle && !this.state.using.includes(obstacle.needs)) {
      this.say("obstacle", obstacle.blocked);
      if (obstacle.fatal) this.state.status = "dead";
      return;
    }
    if (exit?.message) this.say("pass", exit.message);
    if (exit?.fatal) {
      this.state.status = "dead";
      return;
    }
    if (!exit?.to) {
      this.say("error", this.text.cantGo);
      return;
    }
    this.state.room = exit.to;
    this.state.using = [];
    this.state.looks++;
    if (this.world.rooms[exit.to].deadEnd) this.state.status = "lost";
  }

  take(id: ItemId) {
    const location = this.state.itemLocations[id];
    if (location === undefined) return this.say("error", this.text.impossible);
    if (location === this.state.room) {
      if (this.carriedCount() >= this.world.carryLimit) return this.say("error", this.text.carryingTooMuch);
      this.state.itemLocations[id] = "carried";
      this.markFound(id);
      return this.say("item", this.withItem(this.text.youHave, id));
    }
    if (location === "carried") return this.say("error", this.text.alreadyGot);
    this.say("error", this.text.notHere);
  }

  takeAll() {
    const here = itemsIn(this.world, this.state, this.state.room);
    if (this.carriedCount() + here.length > this.world.carryLimit) return this.say("error", this.text.carryingTooMuch);
    if (here.length === 0) return this.say("error", this.text.nothingHere);
    for (const id of here) {
      this.state.itemLocations[id] = "carried";
      this.markFound(id);
    }
    this.say("item", this.text.allTaken);
  }

  private markFound(id: ItemId) {
    this.state.found ??= [];
    if (!this.state.found.includes(id)) this.state.found.push(id);
  }

  drop(id: ItemId) {
    if (this.state.itemLocations[id] !== "carried") return this.say("error", this.text.notTaken);
    // Quirk: dropping does not stop the item being "in use".
    this.state.itemLocations[id] = this.state.room;
    this.state.looks++;
    this.say("plain", this.withItem(this.text.youDrop, id));
  }

  // Quirk: always says "All dropped.", even when carrying nothing.
  dropAll() {
    for (const id of carried(this.world, this.state)) this.state.itemLocations[id] = this.state.room;
    this.state.looks++;
    this.say("plain", this.text.allDropped);
  }

  use(id: ItemId) {
    const location = this.state.itemLocations[id];
    if (location === undefined) return this.say("error", this.text.notPossible);
    if (location !== "carried") return this.say("error", this.text.haventGot);
    // Using an object again makes it the most recent (for effects()).
    this.state.using = [...this.state.using.filter((other) => other !== id), id];
    let message = this.text.nothingHappens;
    for (const direction of EXIT_ORDER) {
      const obstacle = this.world.rooms[this.state.room].exits[direction]?.obstacle;
      if (obstacle?.needs === id) message = obstacle.useMessage;
    }
    this.say("obstacle", message);
  }

  checkVictory() {
    const { world, state } = this;
    if (state.status !== "playing" || state.room !== world.homeRoom) return;
    if (itemsIn(world, state, world.homeRoom).length !== Object.keys(world.items).length) return;
    state.status = "won";
    this.say("victory", this.text.victory);
  }

  private carriedCount() {
    return carried(this.world, this.state).length;
  }
}
