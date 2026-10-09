import { describe, expect, it } from "vitest";

import { describe as view } from "../src/engine/engine";
import { newGame } from "../src/engine/engine";
import { parse, type Row, wrap } from "../src/engine/teletext";
import { firstChoice, world } from "./helpers";

const rowText = (row: Row) =>
  row.cells
    .map((c) => ("char" in c ? c.char : " "))
    .join("")
    .trimEnd();

describe("teletext", () => {
  it("parses colour codes into single cells", () => {
    expect(parse("a{red}b")).toEqual([{ char: "a" }, { colour: "red" }, { char: "b" }]);
    expect(() => parse("{tartan}")).toThrow("Unknown colour");
  });

  it("wraps the opening text exactly as on the BBC Micro screenshot", () => {
    const rows = wrap(view(world, newGame(world, firstChoice)).description);
    expect(rows.map(rowText)).toEqual([
      "You wake up on a grassy bank at a",
      "cross-roads. It is warm and the bees",
      "are humming. There is a feeling of",
      "magic and mystery all around you.",
    ]);
  });

  it("starts a row in the colour it broke on", () => {
    const rows = wrap(world.rooms["coach-house"].description);
    expect(rows.map(rowText)[0]).toBe("You are in an ancient coach house.");
    expect(rows.map((r) => r.colour)).toEqual(["white", "white", "white", "white"]);
    const broken = wrap("x".repeat(30) + " abcdefg{cyan}hijk lmn");
    expect(broken.map((r) => r.colour)).toEqual(["white", "cyan"]);
    expect(broken.map(rowText)).toEqual(["x".repeat(30) + " abcdefg", "hijk lmn"]);
  });
});
