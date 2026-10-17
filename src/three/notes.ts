// The clues: a note on a post at each dead end (its post and board:
// art/blender/land.py), the clue written on it in your language, in ink, a
// little uneven, as if by hand. Looking at one and pressing E, it unrolls in
// front of you, big enough to read; E again (or a click, or Escape) rolls it
// up, and you carry on. (In the original, these were where you got lost, and
// the game ended: here there's nothing to stop you finding them all.)

import { CanvasTexture, Mesh, MeshStandardMaterial, PlaneGeometry, type Scene, SRGBColorSpace } from "three";

import type { Direction, World } from "../engine/types";
import { splitClue } from "../illustrated/text";
import { h } from "../shared/dom";

/** Where a note is (land.json): the exit that leads to its clue, its middle [x, y, z], which way it faces [x, z]. */
export interface NoteSpot {
  clue: string;
  at: number[];
  facing: number[];
  lean: number; // radians it leans back
  size: number[]; // across and up, in metres
}

const PX = 512; // the note's pixels across (its height in proportion)
const INK = "#3b2616";
const FONT = '"IM Fell English", Georgia, serif';

/** A clue's words: what the room it's in says, after "You are lost but you find a clue:". */
export function clueWords(world: World, exit: string) {
  const [id, direction] = exit.split(" ") as [string, Direction];
  const to = world.rooms[id]?.exits[direction]?.to;
  return splitClue((to && world.rooms[to]?.description) || "").clue;
}

/** Words broken into lines, none wider than `wide` pixels as `pen` writes them. */
function lines(pen: CanvasRenderingContext2D, words: string, wide: number) {
  const out: string[] = [];
  for (const word of words.split(/\s+/)) {
    const line = out.length ? `${out[out.length - 1]} ${word}` : word;
    if (out.length && pen.measureText(line).width <= wide) out[out.length - 1] = line;
    else out.push(word);
  }
  return out;
}

export class Notes {
  /** Each note, to look at: its paper, and its words. */
  readonly notes: { model: Mesh; words: string }[] = [];
  private readonly scroll = h("div", { class: "scroll", hidden: true, role: "dialog", "aria-live": "polite" });
  private readonly words = h("p", { class: "clue" });
  /** Whether one's unrolled. */
  open = false;
  /** Rolled up again. */
  onClose = () => {};

  constructor(scene: Scene, spots: NoteSpot[], world: World, root: HTMLElement, hint: Node) {
    for (const spot of spots) {
      const words = clueWords(world, spot.clue);
      const model = this.paint(spot, words);
      scene.add(model);
      this.notes.push({ model, words });
    }
    // (Its paper, between two rods: the lower one rolls down, unrolling it.)
    this.scroll.append(
      h(
        "div",
        { class: "paper" },
        h("div", { class: "rod" }),
        h("div", { class: "sheet" }, this.words, h("p", { class: "hint" }, hint)),
        h("div", { class: "rod lower" })
      )
    );
    root.append(this.scroll);
    // (While it's unrolled, a key or a click is for rolling it up, not
    // walking, jumping, taking or using: so it's caught first.)
    const roll = (event: Event) => {
      if (!this.open) return;
      if (
        event instanceof KeyboardEvent &&
        (event.repeat || !["KeyE", "Escape", "Space", "Enter"].includes(event.code))
      )
        return;
      event.stopImmediatePropagation();
      event.preventDefault();
      this.close();
    };
    addEventListener("keydown", roll, true);
    addEventListener("mousedown", roll, true);
    this.scroll.addEventListener("touchend", roll);
  }

  /** Unrolls a note's clue in front of you. */
  read(k: number) {
    this.words.textContent = this.notes[k].words;
    this.scroll.hidden = false;
    document.body.classList.add("reading");
    this.open = true;
  }

  /** Rolls it up again (and away). */
  close() {
    if (!this.open) return;
    this.open = false;
    this.scroll.hidden = true;
    document.body.classList.remove("reading");
    this.onClose();
  }

  /** A note's paper, the clue written on it, on its board. */
  private paint(spot: NoteSpot, words: string) {
    const [wide, tall] = spot.size;
    const canvas = document.createElement("canvas");
    canvas.width = PX;
    canvas.height = Math.round((PX * tall) / wide);
    const texture = new CanvasTexture(canvas);
    texture.colorSpace = SRGBColorSpace;
    texture.anisotropy = 4;
    // (Written once the page's own lettering can be had; else in Georgia.)
    void document.fonts
      .load(`italic 64px ${FONT}`)
      .catch(() => undefined)
      .then(() => {
        write(canvas, spot.clue, words);
        texture.needsUpdate = true;
      });
    const model = new Mesh(
      new PlaneGeometry(wide, tall),
      new MeshStandardMaterial({ map: texture, transparent: true, roughness: 0.95, depthWrite: false })
    );
    const [x, y, z] = spot.at;
    model.position.set(x, y, z);
    model.rotation.order = "YXZ";
    model.rotation.set(-spot.lean, Math.atan2(spot.facing[0], spot.facing[1]), 0);
    model.receiveShadow = true;
    return model;
  }
}

/** The paper, and the clue on it. */
function write(canvas: HTMLCanvasElement, clue: string, words: string) {
  const pen = canvas.getContext("2d")!;
  const H = canvas.height;
  // A seeded wobble, so each note's written the same each time.
  let seed = 11 + clue.length * 31;
  const wobble = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;
  // The paper: old, browned towards its edges, a little torn along them.
  const paper = pen.createRadialGradient(PX / 2, H / 2, H * 0.1, PX / 2, H / 2, PX * 0.62);
  paper.addColorStop(0, "#efe2c0");
  paper.addColorStop(1, "#c9ad78");
  pen.fillStyle = paper;
  pen.beginPath();
  const edge = (x: number, y: number) => pen.lineTo(x + wobble() * 4, y + wobble() * 4);
  pen.moveTo(6, 6);
  for (let x = 6; x <= PX - 6; x += 24) edge(x, 6);
  for (let y = 6; y <= H - 6; y += 24) edge(PX - 6, y);
  for (let x = PX - 6; x >= 6; x -= 24) edge(x, H - 6);
  for (let y = H - 6; y >= 6; y -= 24) edge(6, y);
  pen.fill();
  // A nail at the top, holding it to the board.
  pen.fillStyle = "#3a3632";
  pen.beginPath();
  pen.arc(PX / 2, 22, 7, 0, Math.PI * 2);
  pen.fill();
  // The words: as big as fit, a line at a time, each letter a little askew.
  pen.fillStyle = INK;
  pen.textBaseline = "middle";
  let size = 64;
  let written: string[] = [];
  for (; size > 16; size -= 2) {
    pen.font = `italic ${size}px ${FONT}`;
    written = lines(pen, words, PX * 0.82);
    if (written.length * size * 1.15 <= H * 0.72) break;
  }
  const top = H / 2 - ((written.length - 1) * size * 1.15) / 2 + 8;
  written.forEach((line, k) => {
    let x = (PX - pen.measureText(line).width) / 2;
    for (const letter of line) {
      pen.save();
      pen.translate(x, top + k * size * 1.15 + wobble() * size * 0.03);
      pen.rotate(wobble() * 0.05);
      pen.fillText(letter, 0, 0);
      pen.restore();
      x += pen.measureText(letter).width;
    }
  });
}
