import { describe as group, expect, it } from "vitest";

import daJson from "../data/da.json";
import { act, describe, itemsSentence, messages, newGame } from "../src/engine/engine";
import { localise, type WorldText } from "../src/engine/localise";
import { parse, wrap } from "../src/engine/teletext";
import type { GameState } from "../src/engine/types";
import { world } from "./helpers";

const da = daJson as WorldText;
const dansk = localise(world, da);

// Every piece of text in a world, labelled by where it comes from.
function texts(w: typeof world): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [id, room] of Object.entries(w.rooms)) {
    out[`${id}.description`] = room.description;
    if (room.firstVisitDescription) out[`${id}.firstVisitDescription`] = room.firstVisitDescription;
    if (room.crowdedDescription) out[`${id}.crowdedDescription`] = room.crowdedDescription;
    for (const [direction, exit] of Object.entries(room.exits)) {
      if (exit?.message) out[`${id}.${direction}.message`] = exit.message;
      if (exit?.obstacle) {
        out[`${id}.${direction}.useMessage`] = exit.obstacle.useMessage;
        out[`${id}.${direction}.blocked`] = exit.obstacle.blocked;
      }
    }
  }
  for (const [id, item] of Object.entries(w.items)) out[`${id}.name`] = item.name;
  return out;
}

group("the Danish translation", () => {
  it("translates every room, exit and object", () => {
    const english = texts(world);
    const danish = texts(dansk);
    const untranslated = Object.keys(english).filter(
      (key) => danish[key] === english[key] && !["ring.name"].includes(key)
    );
    expect(untranslated).toEqual([]);
  });

  it("gives every object a Danish article and definite form", () => {
    for (const item of Object.values(dansk.items)) {
      expect(["en", "et", "noget"]).toContain(item.article);
      expect(item.definite).toBeTruthy();
    }
  });

  it("uses only teletext colours the BBC had", () => {
    for (const text of [...Object.values(texts(dansk)), ...Object.values(da.messages)]) {
      expect(() => parse(text)).not.toThrow();
    }
  });

  it("starts each red clue on a row of its own, as the original does", () => {
    for (const id of Object.keys(dansk.rooms).filter((id) => id.startsWith("clue-"))) {
      const rows = wrap(dansk.rooms[id].description).filter((row) => row.cells.length > 0);
      const clue = rows.findIndex((row) => row.colour === "red");
      expect(clue, id).toBeGreaterThan(0);
      expect(
        rows.slice(clue).every((row) => row.colour === "red"),
        id
      ).toBe(true);
    }
  });

  it("plays in Danish", () => {
    let state: GameState = newGame(dansk, () => 0);
    expect(describe(dansk, state).description).toContain("Du vågner");
    state = { ...state, itemLocations: { ...state.itemLocations, ladder: "grassy-bank", apple: "grassy-bank" } };
    expect(act(dansk, state, { type: "go", direction: "west" }).events).toEqual([]);
    const took = act(dansk, state, { type: "take", item: "ladder" });
    expect(took.events[0].text).toBe("Du har{red}en stige.");
    const dropped = act(dansk, took.state, { type: "drop", item: "ladder" });
    expect(dropped.events[0].text).toBe("Du lægger{red}stigen{white}fra dig.");
    expect(act(dansk, took.state, { type: "use", item: "ladder" }).events[0].text).toBe(messages(dansk).nothingHappens);
  });

  it("lists objects in Danish alphabetical order: z, æ, ø, å", () => {
    expect(itemsSentence(dansk, ["apple", "spell", "axe"])).toBe(
      "Du kan se en{red}trylleformular,{red}et{red}æble,{red}en{red}økse."
    );
  });

  it("leaves the English world as it was", () => {
    expect(world.items.ladder.name).toBe("ladder");
    expect(messages(world).cantGo).toBe("You can't go that way.");
  });
});
