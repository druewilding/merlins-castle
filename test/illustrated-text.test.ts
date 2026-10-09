import { describe, expect, it } from "vitest";

import { plainText, segments } from "../src/illustrated/text";
import { world } from "./helpers";

describe("illustrated text", () => {
  it("highlights a phrase between colour codes", () => {
    expect(segments(world.rooms["grassy-bank"].firstVisitDescription!).slice(0, 3)).toEqual([
      { text: "You wake up on a ", colour: null },
      { text: "grassy bank", colour: "green" },
      {
        text: " at a cross-roads. It is warm and the bees are humming. There is a feeling of magic and mystery all around you.",
        colour: null,
      },
    ]);
  });

  it("ends a highlight at the end of a phrase", () => {
    const segs = segments(world.rooms["coach-house"].description);
    expect(segs[1]).toEqual({ text: "ancient coach house.", colour: "yellow" });
    expect(segs[2].colour).toBeNull();
  });

  it("highlights each phrase in a room with several", () => {
    const highlighted = segments(world.rooms["dragon-cave"].description).filter((s) => s.colour);
    expect(highlighted).toEqual([
      { text: "large cave.", colour: "cyan" },
      { text: "splendid dragon", colour: "red" },
    ]);
  });

  it("colours a whole clue", () => {
    expect(segments(world.rooms["clue-mask"].description)).toEqual([
      { text: "You are lost but you find a clue: ", colour: null },
      { text: "A mask hides you from goblins.", colour: "red" },
    ]);
  });

  it("reads naturally as plain text", () => {
    for (const room of Object.values(world.rooms)) {
      const text = plainText(room.description);
      expect(text).not.toMatch(/\s{2}|^\s|\s$|\{/);
    }
  });
});
