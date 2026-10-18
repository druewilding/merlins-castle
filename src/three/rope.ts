// The rope in use: tied round the middle of the beam across the deep hole
// (between the maze and the treasure room), always in the same spot. Used,
// it swings down from your side of the hole, and hangs there, swaying, ready:
// walk up to the edge and you catch it and swing across, dipping down into
// the hole and up again, and let go on the far side. It comes back into your
// hands there (it's carried, as in the original), unless you dropped it
// hanging: then it stays.

import {
  Box3,
  BufferAttribute,
  BufferGeometry,
  Color,
  Group,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  type Scene,
  TorusGeometry,
  Vector3,
} from "three";

import type { Footing } from "./items";
import type { Player } from "./player";

/** The hole, from land.json: [x, z, half x, half z], the floor across it, its bottom, and its beam's underside. */
interface Hole {
  box: number[];
  floor: number;
  beam: number;
}

const LENGTH = 2.1; // metres, from the beam down to its end
const THICK = 0.03; // its radius (as the coil's: art/blender/items.py)
const TWIST = 0.075; // metres along it, for a strand to go once round it
const BEAM = [0.3, 0.32]; // the beam's height and thickness (land.py)
const STRAND = new Color("#c99a5a");
const GROOVE = new Color("#7c5730");

const GRIP = 2.0; // your hands over your feet, hanging on (reaching up)
const CATCH = 0.05; // how far back from the edge your hands catch it
const BEHIND = 0.3; // and how far behind them you are (so you see it, in front of you)
const NEAR = 0.7; // walking towards the hole this near its edge, you catch it
const SWING = 2.2; // seconds, from catching it to landing on the far side
const CAUGHT = 0.18; // (of that: reaching out and catching it)
const LET_GO = 0.82; // (swinging across, till you let go)
const LAND = 0.8; // metres past the far edge, where you land
const SETTLING = 0.6; // how fast its swinging dies away, hanging (per second)
const SWAY = 0.015; // and how far it sways once it has (radians)
const GRAVITY = 9.8;

export class Rope {
  private hung:
    | {
        exit: string;
        side: number; // which side of the hole you hung it from: 1 south (the maze's), -1 north
        model?: Group; // (gone once you've dropped it there: it's lying there then)
        angle: number; // swinging, towards the south (radians), and how fast
        speed: number;
        held: boolean; // you're swinging on it
        armed: boolean; // you've stepped away since it went up, so walking in swings
      }
    | undefined;
  private readonly pivot: Vector3;
  private readonly geometry: BufferGeometry;
  private readonly knot: TorusGeometry;
  private readonly material = new MeshStandardMaterial({ vertexColors: true, roughness: 0.95 });
  private readonly bound = new MeshStandardMaterial({ color: STRAND.clone().lerp(GROOVE, 0.35), roughness: 0.95 });
  private was = new Vector3(); // where you were last frame
  private time = 0;

  constructor(
    private scene: Scene,
    private hole: Hole,
    /** The way's floor across the hole, at x, z. */
    private floor: (x: number, z: number) => number,
    private player: Player,
    private reducedMotion: boolean,
    /** You catch hold of it. */
    private caught: () => void
  ) {
    const [x, z] = hole.box;
    this.pivot = new Vector3(x, hole.beam, z);
    this.geometry = strands(LENGTH);
    this.knot = new TorusGeometry((BEAM[1] + BEAM[0]) / 4 + THICK, THICK, 8, 24);
  }

  /** Whether you can see it hanging (it's not, once you've dropped it there). */
  get shown() {
    return Boolean(this.hung?.model);
  }

  /** Over the hole for an exit, from your side: swinging down from it, or (as a game's loaded) hanging still. */
  hang(exit: string, show: boolean, instantly: boolean) {
    this.away();
    const side = exit === "maze north" ? 1 : -1;
    const angle = instantly || this.reducedMotion ? 0 : side * 0.9;
    this.hung = { exit, side, angle, speed: 0, held: false, armed: false };
    if (show) this.show();
  }

  /** Back where it was (taken from there, it's still in use). */
  show() {
    const h = this.hung;
    if (!h || h.model) return;
    // (Its middle at the edge on your side, for pointing at it: past it, the
    // hole's in the way, as anything solid would be.)
    const [, , , halfZ] = this.hole.box;
    const model = new Group();
    model.position.set(this.pivot.x, this.floor(this.pivot.x, this.pivot.z), this.pivot.z + h.side * halfZ);
    const tied = new Group();
    tied.position.copy(this.pivot).sub(model.position);
    model.add(tied);
    // Round the beam, twice, and hanging down from it.
    for (const dx of [-0.035, 0.035]) {
      const turn = new Mesh(this.knot, this.bound);
      turn.rotation.y = Math.PI / 2;
      turn.position.set(dx, BEAM[0] / 2, 0);
      tied.add(turn);
    }
    const hanging = new Mesh(this.geometry, this.material);
    hanging.name = "hanging";
    tied.add(hanging);
    this.scene.add(model);
    h.model = model;
    this.place();
  }

  /** Takes it down (it's back in your hands, or you've left). */
  away() {
    if (this.hung?.model) this.scene.remove(this.hung.model);
    this.hung = undefined;
  }

  /** Dropped there: it stays, as an object lying in the place (and the box round it, as it hangs, to point at). */
  handOver(): { model: Group; box: Box3 } | undefined {
    const model = this.hung?.model;
    if (!model) return undefined;
    this.hung!.model = undefined;
    // (Its box as it is, round its middle: a thing's box is its own, turned with it.)
    model.updateMatrixWorld();
    const inverse = new Matrix4().copy(model.matrixWorld).invert();
    const box = new Box3().setFromObject(model).applyMatrix4(inverse);
    return { model, box };
  }

  /** Where it falls when you leave (dropped there): on your side of the hole, back from its edge. */
  get footing(): Footing | undefined {
    const h = this.hung;
    if (!h) return undefined;
    const [x, z, , halfZ] = this.hole.box;
    const at = { x, z: z + h.side * (halfZ + 1.2) };
    return { ...at, yaw: Math.PI / 2, floor: this.floor(at.x, at.z) };
  }

  /** Each frame: it swings and settles; walk up to the edge and you swing across, then over(exit) is called. */
  update(dt: number, over: (exit: string) => void) {
    this.time += dt;
    const p = this.player.position;
    const moved = p.clone().sub(this.was);
    this.was.copy(p);
    const h = this.hung;
    if (!h) return;
    if (!h.held) {
      // (A pendulum, about the beam: slowing, as a rope would.)
      const g = GRAVITY / (LENGTH * 0.6);
      h.speed += (-g * Math.sin(h.angle) - SETTLING * 2 * h.speed) * dt;
      h.angle += h.speed * dt;
    }
    this.place();
    if (!h.model || h.held || this.player.busy) return;
    // Walking towards the hole, near its edge on your side, you catch it.
    const [x, z, halfX, halfZ] = this.hole.box;
    const out = (p.z - z) * h.side - halfZ; // how far from the edge
    const near = out < NEAR && out > -0.2 && Math.abs(p.x - x) < halfX;
    if (!near) h.armed = true;
    const going = -moved.z * h.side;
    if (!near || !h.armed || going <= 0.2 * Math.hypot(moved.x, moved.z)) return;
    h.held = true;
    this.caught();
    this.player.follow(this.across(h), SWING, () => over(h.exit));
  }

  // Reaching out, it comes to your hands; swinging on it (as it would,
  // slowest at either end), down into the hole and up the other side; and
  // letting go, onto the far side. There it comes back into your hands.
  private across(h: NonNullable<Rope["hung"]>) {
    const [x, z, , halfZ] = this.hole.box;
    const start = this.player.position.clone();
    const grip = new Vector3(x, 0, z + h.side * (halfZ + CATCH + BEHIND));
    grip.y = this.floor(grip.x, grip.z);
    const hands = new Vector3(x, grip.y + GRIP, z + h.side * (halfZ + CATCH));
    const reach = hands.distanceTo(this.pivot);
    const widest = Math.asin(Math.min(1, Math.abs(hands.z - this.pivot.z) / reach)); // (towards you)
    const from = h.angle;
    const land = new Vector3(x, 0, z - h.side * (halfZ + LAND));
    land.y = this.floor(land.x, land.z);
    const feet = (angle: number) =>
      new Vector3(
        x,
        this.pivot.y - reach * Math.cos(angle) - GRIP,
        this.pivot.z + reach * Math.sin(angle) + h.side * BEHIND
      );
    const at = new Vector3();
    return (t: number) => {
      if (t < CAUGHT) {
        const u = ease(t / CAUGHT);
        h.angle = from + (h.side * widest - from) * u;
        return at.lerpVectors(start, grip, u);
      }
      if (t < LET_GO) {
        h.angle = h.side * widest * Math.cos((Math.PI * (t - CAUGHT)) / (LET_GO - CAUGHT));
        return at.copy(feet(h.angle));
      }
      // Let go: it swings back, and you step down onto the far side.
      if (h.held) {
        h.held = false;
        h.speed = 0;
      }
      if (t > 0.92 && this.hung === h) this.away();
      const u = ease((t - LET_GO) / (1 - LET_GO));
      at.lerpVectors(feet(-h.side * widest), land, u);
      at.y += Math.sin(u * Math.PI) * 0.15;
      return at;
    };
  }

  // Hanging from the beam, swung (and, still, swaying a little).
  private place() {
    const h = this.hung;
    const hanging = h?.model?.getObjectByName("hanging");
    if (!h || !hanging) return;
    const sway = h.held || this.reducedMotion ? 0 : SWAY * Math.sin(this.time * 1.1);
    // (Turned about the beam, x: its foot towards +z by angle.)
    hanging.rotation.x = -(h.angle + sway);
  }
}

// A length of rope, hanging straight down from 0: its three strands twisted
// round it, bulging (and lighter) where they are, and its end bound.
function strands(length: number) {
  const SIDES = 12;
  const rings = Math.round(length / 0.01) + 1;
  const position = new Float32Array(rings * SIDES * 3);
  const colour = new Float32Array(rings * SIDES * 3);
  const shade = new Color();
  for (let k = 0; k < rings; k++) {
    const along = (k / (rings - 1)) * length;
    for (let j = 0; j < SIDES; j++) {
      const a = (2 * Math.PI * j) / SIDES;
      const crest = Math.cos(3 * a - (2 * Math.PI * along) / TWIST);
      // (Bound round, near its end: no strands there.)
      const bound = along > length - 0.07 && along < length - 0.02;
      const r = THICK * (bound ? 1.12 : 1 + 0.1 * crest);
      const i = (k * SIDES + j) * 3;
      position.set([Math.cos(a) * r, -along, Math.sin(a) * r], i);
      shade.lerpColors(GROOVE, STRAND, bound ? 0.25 : 0.5 + 0.5 * crest);
      colour.set([shade.r, shade.g, shade.b], i);
    }
  }
  const index: number[] = [];
  for (let k = 0; k < rings - 1; k++) {
    for (let j = 0; j < SIDES; j++) {
      const a = k * SIDES + j;
      const b = k * SIDES + ((j + 1) % SIDES);
      index.push(a, a + SIDES, b, b, a + SIDES, b + SIDES);
    }
  }
  // (Closed at its end.)
  const last = (rings - 1) * SIDES;
  for (let j = 1; j < SIDES - 1; j++) index.push(last, last + j, last + j + 1);
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(position, 3));
  geometry.setAttribute("color", new BufferAttribute(colour, 3));
  geometry.setIndex(index);
  geometry.computeVertexNormals();
  return geometry;
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
