import { describe, expect, it } from "vitest";

import { titleSteps } from "../src/classic/title-picture";
import { chords } from "../src/classic/tune";

describe("the victory tune", () => {
  const tune = chords();

  it("has every chord, ending on the long final one", () => {
    expect(tune).toHaveLength(129);
    expect(tune.at(-1)).toEqual({ pitches: [149, 149, 53], length: 15 });
  });

  it("reads notes as the original does", () => {
    // F5, F3, then a rest that repeats the last pitch (F3).
    expect(tune[0]).toEqual({ pitches: [169, 73, 73], length: 3 });
    // A rest in the melody carries over the bass from the chord before.
    expect(tune[1].pitches).toEqual([169, 89, 89]);
    expect(tune[3].pitches[0]).toEqual(tune[2].pitches[2]);
  });

  it("understands sharps and flats", () => {
    const pitches = tune.flatMap((chord) => chord.pitches);
    expect(pitches).toContain(141); // B flat
    expect(pitches).toContain(153); // C sharp, an octave up
  });
});

describe("the title picture", () => {
  it("is drawn in steps: the wall, ten towers one by one, the gate, then the title", () => {
    expect(titleSteps(() => 0.3)).toHaveLength(13);
  });
});
