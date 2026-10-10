// Which picture to show for a death, a lost room or victory.

import type { Direction, RoomId } from "../engine/types";

const DEATHS: Record<string, string> = {
  "wizards-kitchen:east": "death-merlin-caught",
  "grand-hall:west": "death-goblins",
  "grand-hall:east": "death-goblins",
  "dungeon:south": "death-stone",
  "merlins-lair:north": "death-frog",
  "deep-river:south": "death-river",
  "mossy-steps:east": "death-ladder",
  "forest-witches:west": "death-witches",
  "mountain:east": "death-merlins-trap",
  "maze:north": "death-darkness",
  "treasure-room:south": "death-darkness",
  "dark-tunnels:south": "death-stumble",
  "giant:west": "death-mouse",
};

const LOST: Record<RoomId, string> = {
  "clue-silver": "lost-forest",
  "clue-ring": "lost-forest",
  "clue-rope": "lost-forest",
  "clue-mask": "lost-tunnels",
  "clue-plank": "lost-tunnels",
  "clue-spell": "lost-tunnels",
};

export const deathMoment = (room: RoomId, direction: Direction): string | undefined => DEATHS[`${room}:${direction}`];

export const lostMoment = (room: RoomId): string | undefined => LOST[room];
