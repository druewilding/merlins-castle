// Translations of the world (data/da.json): every room, exit and object
// message, the objects' names, and the engine's own messages. The map, the
// objects and the rules stay exactly as they are; only the words change.

import type { Direction, Messages, RoomId, TeletextString, World } from "./types";

export interface WorldText {
  title: string;
  locale: string;
  messages: Messages;
  rooms: Record<
    RoomId,
    {
      description: TeletextString;
      firstVisitDescription?: TeletextString;
      crowdedDescription?: TeletextString;
      exits?: Partial<
        Record<Direction, { message?: TeletextString; useMessage?: TeletextString; blocked?: TeletextString }>
      >;
    }
  >;
  items: Record<string, { name: string; article: string; definite: string }>;
}

// The world in another language. Anything missing stays in English.
export function localise(world: World, text: WorldText): World {
  const result = structuredClone(world);
  result.title = text.title;
  result.locale = text.locale;
  result.messages = text.messages;
  for (const [id, room] of Object.entries(result.rooms)) {
    const words = text.rooms[id];
    if (!words) continue;
    room.description = words.description;
    if (room.firstVisitDescription)
      room.firstVisitDescription = words.firstVisitDescription ?? room.firstVisitDescription;
    if (room.crowdedDescription) room.crowdedDescription = words.crowdedDescription ?? room.crowdedDescription;
    for (const [direction, exit] of Object.entries(room.exits)) {
      const exitWords = words.exits?.[direction as Direction];
      if (!exit || !exitWords) continue;
      if (exit.message) exit.message = exitWords.message ?? exit.message;
      if (exit.obstacle) {
        exit.obstacle.useMessage = exitWords.useMessage ?? exit.obstacle.useMessage;
        exit.obstacle.blocked = exitWords.blocked ?? exit.obstacle.blocked;
      }
    }
  }
  for (const [id, item] of Object.entries(result.items)) {
    const words = text.items[id];
    if (words) Object.assign(item, words);
  }
  return result;
}
