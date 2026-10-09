// Teletext text layout, ported from PROCprint in MERLIN2.
//
// Each colour code ("{red}") occupies one character cell, shown as a space,
// and colours everything after it on the same row. Text wraps at 38
// characters, breaking at a space or a colour code. The next row starts in the
// colour of the code it broke at, or white if it broke at a space.

export const COLOURS = ["red", "green", "yellow", "blue", "magenta", "cyan", "white"] as const;
export type Colour = (typeof COLOURS)[number];

export type Cell = { char: string } | { colour: Colour };

export interface Row {
  colour: Colour; // colour at the start of the row
  cells: Cell[];
}

const WIDTH = 38;

export function parse(text: string): Cell[] {
  const cells: Cell[] = [];
  const re = /\{(\w+)\}|([^{])/g;
  for (const match of text.matchAll(re)) {
    if (match[1]) {
      if (!(COLOURS as readonly string[]).includes(match[1])) throw new Error(`Unknown colour: ${match[1]}`);
      cells.push({ colour: match[1] as Colour });
    } else {
      cells.push({ char: match[2] });
    }
  }
  return cells;
}

const isBreak = (cell: Cell) => "colour" in cell || cell.char === " ";
const breakColour = (cell: Cell): Colour => ("colour" in cell ? cell.colour : "white");

export function wrap(text: string, colour: Colour = "white"): Row[] {
  let rest = parse(text + " "); // the original always appends a space
  const rows: Row[] = [];
  for (;;) {
    let line = rest.slice(0, WIDTH);
    rest = rest.slice(WIDTH);
    const next = rest[0];
    let nextColour: Colour | undefined;
    if (next === undefined) {
      nextColour = undefined;
    } else if (isBreak(next)) {
      nextColour = breakColour(next);
      rest = rest.slice(1);
    } else {
      let at = line.length - 1;
      while (at >= 0 && !isBreak(line[at])) at--;
      if (at < 0) at = line.length; // one enormous word: just cut it
      if (at < line.length) nextColour = breakColour(line[at]);
      rest = [...line.slice(at + 1), ...rest];
      line = line.slice(0, at);
    }
    rows.push({ colour, cells: line });
    if (nextColour === undefined) return rows;
    colour = nextColour;
  }
}
