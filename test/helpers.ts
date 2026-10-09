import worldJson from "../data/world.json";
import { act } from "../src/engine/engine";
import type { Command, Direction, GameEvent, GameState, World } from "../src/engine/types";

export const world = worldJson as unknown as World;

// Every item starts in the first of its possible rooms.
export const firstChoice = () => 0;

const DIRECTIONS: Record<string, Direction> = { N: "north", E: "east", S: "south", W: "west" };

// "N", "take ladder", "use ladder", "drop all" → Command
export function parseStep(step: string): Command {
  if (DIRECTIONS[step]) return { type: "go", direction: DIRECTIONS[step] };
  const [verb, item] = step.split(" ");
  if (verb === "take" || verb === "drop") return { type: verb, item };
  if (verb === "use") return { type: "use", item };
  if (verb === "quit") return { type: "quit" };
  throw new Error(`Can't parse step: ${step}`);
}

export function play(state: GameState, steps: string[]): { state: GameState; events: GameEvent[] } {
  const events: GameEvent[] = [];
  for (const step of steps) {
    const result = act(world, state, parseStep(step));
    state = result.state;
    events.push(...result.events);
  }
  return { state, events };
}

export const texts = (events: GameEvent[]) => events.map((e) => e.text);
