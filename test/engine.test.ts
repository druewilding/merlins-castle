import { describe as context, expect, it } from "vitest";

import { act, bestPossibleScore, describe, itemsSentence, newGame, score } from "../src/engine/engine";
import { EXIT_ORDER, type GameState } from "../src/engine/types";
import { firstChoice, play, texts, world } from "./helpers";

const start = () => newGame(world, firstChoice);

// A game with chosen objects carried and everything else on the bank's
// opposite side of the world, so tests don't trip over randomness.
function carrying(items: string[], room = "grassy-bank"): GameState {
  const state = start();
  for (const id of Object.keys(world.items)) state.itemLocations[id] = "charcoal-hut";
  for (const id of items) state.itemLocations[id] = "carried";
  return { ...state, room, looks: 2 };
}

context("the world", () => {
  it("has 40 rooms and 20 objects worth 100 points", () => {
    expect(Object.keys(world.rooms)).toHaveLength(40);
    expect(Object.keys(world.items)).toHaveLength(20);
    expect(bestPossibleScore(world)).toBe(100);
  });

  it("only refers to rooms and objects that exist", () => {
    for (const [key, room] of Object.entries(world.rooms)) {
      for (const exit of Object.values(room.exits)) {
        if (exit.to) expect(world.rooms, key).toHaveProperty([exit.to]);
        if (exit.obstacle) expect(world.items, key).toHaveProperty([exit.obstacle.needs]);
      }
    }
    for (const item of Object.values(world.items)) {
      for (const room of item.startsIn) expect(world.rooms).toHaveProperty([room]);
    }
  });

  it("has no exits from the lost rooms", () => {
    const lost = Object.entries(world.rooms).filter(([, room]) => room.deadEnd);
    expect(lost.map(([key]) => key)).toEqual([
      "clue-spell",
      "clue-silver",
      "clue-mask",
      "clue-ring",
      "clue-plank",
      "clue-rope",
    ]);
    for (const [, room] of lost) expect(room.exits).toEqual({});
  });
});

context("starting a new adventure", () => {
  it("wakes up on the grassy bank", () => {
    expect(describe(world, start()).description).toMatch(/^You wake up on a\{green\}grassy\{green\}bank/);
  });

  it("puts each object in one of its possible rooms", () => {
    expect(newGame(world, () => 0).itemLocations.ladder).toBe("grassy-bank");
    expect(newGame(world, () => 0.99).itemLocations.ladder).toBe("old-stone-wall");
    expect(newGame(world, () => 0.5).itemLocations.pearl).toBe("merlins-lair");
  });

  it("lists the objects you can see", () => {
    expect(itemsSentence(world, describe(world, start()).itemsHere)).toBe("You can see a{red}ladder.");
    expect(itemsSentence(world, ["cake", "water"])).toBe("You can see a{red}cake,{red}some{red}water.");
  });
});

context("moving around", () => {
  it("shows a sleeping figure when you return to the bank", () => {
    const { state } = play(start(), ["N", "S"]);
    expect(describe(world, state).description).toBe(
      "You are standing at a cross-roads. On a{green}grassy{green}bank{white}a figure lies sleeping."
    );
  });

  it("shortens the bank's description once more than 12 objects are there", () => {
    const state = carrying([]);
    const ids = Object.keys(world.items);
    ids.slice(0, 13).forEach((id) => (state.itemLocations[id] = "grassy-bank"));
    expect(describe(world, state).description).toBe("You are by a{green}grassy{green}bank.");
  });

  it("only offers the real exits, in the original's order", () => {
    expect(describe(world, start()).exits).toEqual(EXIT_ORDER);
    expect(describe(world, { ...start(), room: "charcoal-hut" }).exits).toEqual(["north"]);
  });

  it("won't go where there's no exit", () => {
    const { events } = play({ ...start(), room: "charcoal-hut" }, ["S"]);
    expect(events).toEqual([{ tone: "error", text: "You can't go that way." }]);
  });

  it("ends the game when you get lost", () => {
    const { state } = play({ ...start(), room: "evergreen-glade" }, []);
    const result = act(world, { ...state, room: "mountain" }, { type: "go", direction: "east" });
    expect(result.state.status).toBe("dead");
    expect(texts(result.events)).toEqual(["Oh dear! Merlin's trap is that way."]);

    const lost = play({ ...start(), room: "dark-tunnels" }, ["W"]).state;
    expect(lost.room).toBe("clue-mask");
    expect(lost.status).toBe("lost");
  });
});

context("obstacles", () => {
  it("blocks you until you use the right object", () => {
    const { state, events } = play(carrying(["ladder"], "old-stone-wall"), ["W", "use ladder", "W"]);
    expect(texts(events)).toEqual([
      "The wall is too high.",
      "The ladder leans against the wall.",
      "You have climbed over.",
    ]);
    expect(state.room).toBe("old-wall");
  });

  it("forgets what you were using when you change room", () => {
    const { events } = play(carrying(["ladder"], "old-stone-wall"), ["use ladder", "E", "W", "W"]);
    expect(texts(events).at(-1)).toBe("The wall is too high.");
  });

  it("can kill you if you try without the object", () => {
    const { state, events } = play(carrying([], "deep-river"), ["S"]);
    expect(texts(events)).toEqual(["You are swept away by the current."]);
    expect(state.status).toBe("dead");
  });

  it("can kill you even with the object (the balcony)", () => {
    const { state, events } = play(carrying(["ladder"], "mossy-steps"), ["use ladder", "E"]);
    expect(texts(events)).toEqual(["The ladder is propped up ready.", "The ladder slips and you fall."]);
    expect(state.status).toBe("dead");
  });

  it("says nothing happens when the object doesn't help here", () => {
    const { events } = play(carrying(["harp"]), ["use harp"]);
    expect(texts(events)).toEqual(["Nothing happens."]);
  });

  it("lets you through after using and then dropping the object (original quirk)", () => {
    const { state } = play(carrying(["ladder"], "old-stone-wall"), ["use ladder", "drop ladder", "W"]);
    expect(state.room).toBe("old-wall");
  });

  it("does nothing once the game is over", () => {
    const dead = play(carrying([], "deep-river"), ["S"]).state;
    expect(act(world, dead, { type: "go", direction: "north" })).toEqual({ state: dead, events: [] });
  });
});

context("taking and dropping", () => {
  it("takes and drops objects", () => {
    const { state, events } = play(start(), ["take ladder", "drop ladder"]);
    expect(texts(events)).toEqual(["You have{red}a ladder.", "You drop the{red}ladder."]);
    expect(state.itemLocations.ladder).toBe("grassy-bank");
  });

  it("explains what went wrong", () => {
    const { events } = play(start(), ["take emerald", "take ladder", "take ladder", "drop emerald", "use emerald"]);
    expect(texts(events)).toEqual([
      "It's not here.",
      "You have{red}a ladder.",
      "You've already got it.",
      "You haven't taken that.",
      "You haven't got that.",
    ]);
  });

  it("only lets you carry 5 objects", () => {
    const state = carrying(["cake", "water", "mask", "key", "spell"]);
    state.itemLocations.ladder = "grassy-bank";
    const { events } = play(state, ["take ladder", "take all"]);
    expect(texts(events)).toEqual(["You're carrying too much.", "You're carrying too much."]);
  });

  it("takes all or nothing", () => {
    const state = carrying([], "cave-entrance");
    ["cake", "apple", "harp"].forEach((id) => (state.itemLocations[id] = "cave-entrance"));
    const { state: after, events } = play(state, ["take all", "take all"]);
    expect(texts(events)).toEqual(["All taken.", "There's nothing here."]);
    expect(describe(world, after).carried).toEqual(["cake", "apple", "harp"]);
  });

  it("says all dropped even when carrying nothing (original quirk)", () => {
    expect(texts(play(carrying([]), ["drop all"]).events)).toEqual(["All dropped."]);
  });
});

context("scoring", () => {
  it("scores 3 per object and 11 per treasure on the grassy bank", () => {
    const { state } = play(carrying(["harp", "pearl"]), ["drop harp"]);
    expect(score(world, state)).toBe(3);
    expect(score(world, play(state, ["drop pearl"]).state)).toBe(14);
    expect(score(world, play(state, ["take harp"]).state)).toBe(0);
  });

  it("doesn't count objects dropped elsewhere", () => {
    expect(score(world, play(carrying(["harp"], "trolls"), ["drop harp"]).state)).toBe(0);
  });
});
