// The title picture from the original program (MERLIN1: PROCtitle, PROCpic,
// PROCtop and PROCBIGST), drawn the same way on a MODE 1 screen: 320 × 256
// pixels, 40 × 32 characters, four colours. The castle is built from the
// program's own 8 × 8 characters (its VDU23 definitions), one tower at a time,
// each randomly black or white with a random height, so every castle is a
// little different.

const COLS = 40;
const ROWS = 32;

// MODE 1's colours, with colour 1 changed to blue (VDU19,1,4).
const BLACK = "#000";
const BLUE = "#00f";
const YELLOW = "#ff0";
const WHITE = "#fff";

// The program's own characters, VDU23,224 to 239: each is 8 rows of 8 bits.
const CASTLE: Record<number, number[]> = {
  224: [1, 3, 7, 15, 31, 63, 127, 255], // roof, left
  225: [128, 192, 224, 240, 248, 252, 254, 255], // roof, right
  226: [170, 85, 170, 85, 170, 85, 170, 85], // stone
  227: [16, 16, 16, 255, 16, 16, 16, 16], // window bars
  228: [1, 1, 1, 1, 1, 1, 1, 1], // flagpole
  229: [192, 240, 252, 255, 252, 240, 192, 0], // flag
  230: [240, 240, 240, 240, 15, 15, 15, 15], // chequer
  231: [240, 240, 240, 240, 240, 240, 240, 240], // right wall
  232: [255, 254, 252, 248, 240, 224, 192, 128], // arch, left
  233: [255, 127, 63, 31, 15, 7, 3, 1], // arch, right
  234: [128, 128, 128, 128, 128, 128, 128, 255], // window, bottom left
  235: [1, 1, 1, 1, 1, 1, 1, 255], // window, bottom right
  236: [255, 255, 255, 255, 255, 255, 255, 255], // solid
  237: [255, 255, 255, 0, 255, 255, 255, 255], // eaves
  238: [15, 15, 15, 15, 15, 15, 15, 15], // left wall
  239: [128, 128, 128, 128, 128, 128, 128, 128], // window, left
};

// The few letters of the BBC Micro's own font that the title needs, in
// English and Danish ("Merlins borg", "Af Anita Straker").
const FONT: Record<string, number[]> = {
  " ": [0, 0, 0, 0, 0, 0, 0, 0],
  "'": [24, 24, 48, 0, 0, 0, 0, 0],
  A: [60, 102, 102, 126, 102, 102, 102, 0],
  B: [124, 102, 102, 124, 102, 102, 124, 0],
  C: [60, 102, 96, 96, 96, 102, 60, 0],
  M: [99, 119, 127, 107, 107, 99, 99, 0],
  S: [60, 102, 96, 60, 6, 102, 60, 0],
  a: [0, 0, 60, 6, 62, 102, 62, 0],
  b: [96, 96, 124, 102, 102, 102, 124, 0],
  e: [0, 0, 60, 102, 126, 96, 60, 0],
  f: [28, 48, 48, 124, 48, 48, 48, 0],
  g: [0, 0, 62, 102, 102, 62, 6, 60],
  i: [24, 0, 56, 24, 24, 24, 60, 0],
  k: [96, 96, 102, 108, 120, 108, 102, 0],
  l: [56, 24, 24, 24, 24, 24, 60, 0],
  n: [0, 0, 124, 102, 102, 102, 102, 0],
  o: [0, 0, 60, 102, 102, 102, 60, 0],
  r: [0, 0, 108, 118, 96, 96, 96, 0],
  s: [0, 0, 62, 96, 60, 6, 124, 0],
  t: [48, 48, 124, 48, 48, 48, 28, 0],
  y: [0, 0, 102, 102, 102, 62, 6, 60],
};

// Where the towers stand, left to right in the order they're drawn
// (DATA 25,13,30,4,20,8,28,24,12,16). The last one is the gatehouse.
const TOWERS = [25, 13, 30, 4, 20, 8, 28, 24, 12, 16];

type Draw = (ctx: CanvasRenderingContext2D) => void;

// One character: `bg` paints the cell first, as text mode (VDU4) does;
// without it the character is drawn over what's there, as VDU5 does.
function char(bits: number[], col: number, row: number, fg: string, bg?: string): Draw {
  return (ctx) => {
    if (bg) {
      ctx.fillStyle = bg;
      ctx.fillRect(col * 8, row * 8, 8, 8);
    }
    ctx.fillStyle = fg;
    bits.forEach((byte, y) => {
      for (let x = 0; x < 8; x++) if (byte & (128 >> x)) ctx.fillRect(col * 8 + x, row * 8 + y, 1, 1);
    });
  };
}

const castle = (codes: number[], col: number, row: number, fg: string, bg?: string): Draw[] =>
  codes.map((code, i) => char(CASTLE[code], col + i, row, fg, bg));

// A row of text, in text mode (on blue).
const text = (s: string, col: number, row: number, fg: string): Draw[] =>
  [...s].map((c, i) => char(FONT[c] ?? FONT[" "], col + i, row, fg, BLUE));

// PROCtop and the rest of one tower, from PROCpic.
function tower(k: number, n: number, l: number, colour: string): Draw[] {
  const draws: Draw[] = [];
  const c = n + 2; // MOVE 32*(N%+2),1023-32*(L%-2)
  const r = l - 2;
  // Drawn at the graphics cursor (VDU5), so they don't cover what's behind.
  draws.push(...castle([228, 229], c, r, colour));
  draws.push(...castle([228], c, r + 1, colour));
  draws.push(...castle([224, 225], c, r + 2, colour));
  draws.push(...castle([224, 236, 236, 225], c - 1, r + 3, colour));
  // The rest in text mode (VDU4), on blue, so each tower stands in front of
  // the ones drawn before it.
  const rows = [
    [237, 237, 237, 237, 237, 237],
    [238, 230, 230, 230, 230, 231],
    [238, 230, 232, 233, 230, 231],
    [238, 230, 239, 228, 230, 231],
    [238, 230, 234, 235, 230, 231],
    [238, 226, 234, 235, 226, 231],
    [238, 226, 226, 226, 226, 231],
  ];
  let a = 0;
  if (k > 4) {
    rows.push([238, 226, 226, 226, 226, 231]);
    a = 1;
    if (k > 9) {
      rows.push([238, 226, 226, 226, 226, 231]);
      a = 2;
    }
  }
  rows.forEach((codes, i) => draws.push(...castle(codes, n, l + 2 + i, colour, BLUE)));
  // The tower's body down to the ground, with a barred window low down.
  // (A BBC BASIC FOR loop always runs at least once.)
  for (let i = a + l + 9; i <= Math.max(23 + a, a + l + 9); i++) {
    const window = i > 18 + a && i < 22 + a;
    draws.push(...castle(window ? [238, 226, 227, 227, 226, 231] : [238, 226, 226, 226, 226, 231], n, i, colour, BLUE));
  }
  return draws;
}

// The whole picture, as a list of steps: one per tower, then the gate and the
// title. `random` gives 0 to 1, like Math.random.
export function titleSteps(
  random: () => number = Math.random,
  name = "Merlin's Castle",
  byline = "By Anita Straker"
): Draw[][] {
  const steps: Draw[][] = [];
  // The border (PROCbox(0) and PROCbox(12)) and the white wall behind the towers.
  steps.push([
    (ctx) => {
      ctx.fillStyle = BLUE;
      ctx.fillRect(0, 0, COLS * 8, ROWS * 8);
      ctx.strokeStyle = WHITE;
      ctx.lineWidth = 1;
      ctx.strokeRect(0.5, 0.5, COLS * 8 - 1, ROWS * 8 - 1);
      ctx.strokeRect(3.5, 3.5, COLS * 8 - 7, ROWS * 8 - 7);
    },
    ...[15, 16, 17, 18].flatMap((row) => castle(Array<number>(36).fill(236), 2, row, WHITE, BLUE)),
  ]);
  let colour = WHITE;
  TOWERS.forEach((n, i) => {
    const k = i + 1;
    // L%=3+2*RND(5), except the gatehouse, which is always 13.
    const l = k === TOWERS.length ? 13 : 3 + 2 * (1 + Math.floor(random() * 5));
    // Z=RND(2): black or white.
    colour = random() < 0.5 ? BLACK : WHITE;
    steps.push(tower(k, n, l, colour));
  });
  // The gate, in the last tower's colour, with its studded door ("oo").
  const gate: Draw[] = [];
  for (let row = 17; row <= 20; row++) gate.push(...castle([236, 236, 236, 236], 17, row, colour, BLUE));
  gate.push(...castle([236, 232, 233, 236], 17, 21, colour, BLUE));
  for (let row = 22; row <= 25; row++) {
    gate.push(
      ...castle([236], 17, row, colour, BLUE),
      ...text("oo", 18, row, colour),
      ...castle([236], 20, row, colour, BLUE)
    );
  }
  steps.push(gate);
  // PROCBIGST: each letter made twice as tall, row by row, in yellow.
  const title: Draw[] = [];
  [...name].forEach((c, i) => {
    const g = FONT[c] ?? FONT[" "];
    title.push(char([0, g[0], g[0], g[1], g[1], g[2], g[2], g[3]], i + 2, 28, YELLOW, BLUE));
    title.push(char([g[3], g[4], g[4], g[5], g[5], g[6], g[6], g[7]], i + 2, 29, YELLOW, BLUE));
  });
  title.push(...text(byline, COLS - 2 - byline.length, 29, BLACK));
  steps.push(title);
  return steps;
}

// Draws the picture onto a canvas, one tower at a time as the BBC did, then
// calls onDone. Returns a function that stops it (for leaving the screen early).
export function drawTitle(
  canvas: HTMLCanvasElement,
  onDone?: () => void,
  delay = 100,
  name?: string,
  byline?: string
): () => void {
  canvas.width = COLS * 8;
  canvas.height = ROWS * 8;
  const ctx = canvas.getContext("2d")!;
  const steps = titleSteps(Math.random, name, byline);
  const instant = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let i = 0;
  let timer = 0;
  const next = () => {
    steps[i++].forEach((draw) => draw(ctx));
    if (i < steps.length) timer = window.setTimeout(next, instant ? 0 : delay);
    else onDone?.();
  };
  next();
  return () => clearTimeout(timer);
}
