// The ladder in use: leaning against a wall (an obstacle's box) where it
// always goes, by the place's middle (where the path comes to the wall), and walk into it to climb up it, over the wall and down the
// other side. It comes back into your hands at the top (it's carried, as in
// the original), unless you dropped it against the wall: then it stays.

import { Box3, type Object3D, type Scene, Vector3 } from "three";

import type { Direction } from "../engine/types";
import type { Ground, Player } from "./player";

const WALL_HIGH = 4.5; // the old stone wall above the ground (WALL in art/blender/land.py)
const OVER = 0.45; // how far the ladder reaches up past the top of the wall
const CLIMB = 2.6; // seconds, from the foot of the ladder to the ground on the other side
const BODY = 0.3; // your feet are this far out from the ladder (and the wall), climbing

// Which way is out of the wall, towards you, when the exit goes the other way.
const OUT: Record<Direction, [number, number]> = { west: [1, 0], east: [-1, 0], north: [0, 1], south: [0, -1] };

interface Leaning {
  exit: string; // "old-stone-wall west"
  foot: Vector3;
  corner: Vector3; // where it rests on the top of the wall
  out: [number, number];
  along: [number, number];
  centre: [number, number]; // the wall's middle line, level with the ladder
  thick: number; // half the wall's thickness
  model?: Object3D; // (gone once you've dropped it against the wall: it's lying there then)
  armed: boolean; // you've stepped away since it went up, so walking in climbs
}

export class Ladder {
  private leaning: Leaning | undefined;

  constructor(
    private scene: Scene,
    private model: Object3D,
    private ground: Ground,
    private player: Player,
    private reducedMotion: boolean
  ) {}

  get up() {
    return Boolean(this.leaning);
  }

  /** Whether you can see it against the wall (it's not, once you've dropped it there). */
  get shown() {
    return Boolean(this.leaning?.model);
  }

  /** Leans against a wall ([x, z, halfX, halfZ]) for an exit ("old-stone-wall west"), at the point nearest `by`. */
  lean([x, z, halfX, halfZ]: number[], exit: string, by: { x: number; z: number }, show: boolean) {
    this.away();
    const out = OUT[exit.split(" ")[1] as Direction];
    const along: [number, number] = [out[1] ? 1 : 0, out[0] ? 1 : 0];
    const thick = out[0] ? halfX : halfZ;
    const long = out[0] ? halfZ : halfX;
    const s = Math.max(-long + 1.5, Math.min(long - 1.5, (by.x - x) * along[0] + (by.z - z) * along[1]));
    const centre: [number, number] = [x + along[0] * s, z + along[1] * s];
    const top = (this.ground(...centre) ?? 0) + WALL_HIGH;
    const face = [centre[0] + out[0] * thick, centre[1] + out[1] * thick];
    // How far out its foot goes, so it rests on the top's edge (the ground at
    // the foot decides how far up that is).
    const length = this.lengthOf(this.model) - OVER;
    let run = 1.6;
    let foot = new Vector3();
    for (let k = 0; k < 3; k++) {
      foot = new Vector3(face[0] + out[0] * run, 0, face[1] + out[1] * run);
      foot.y = this.ground(foot.x, foot.z) ?? 0;
      run = Math.sqrt(Math.max(0.25, length ** 2 - (top - foot.y) ** 2));
    }
    const corner = new Vector3(face[0], top, face[1]);
    this.leaning = { exit, foot, corner, out, along, centre, thick, armed: false };
    if (show) this.show();
  }

  /** Back against the wall where it was (taken from there, it's still in use). */
  show() {
    const l = this.leaning;
    if (!l || l.model) return;
    const { foot, corner, out } = l;
    const ladder = this.model.clone();
    const up = corner.clone().sub(foot).normalize();
    ladder.position.copy(foot).addScaledVector(up, this.lengthOf(this.model) / 2);
    ladder.rotation.set(0, Math.atan2(-out[0], -out[1]), 0, "YXZ");
    ladder.rotateX(-Math.atan2(corner.y - foot.y, Math.hypot(corner.x - foot.x, corner.z - foot.z)));
    ladder.traverse((node) => {
      node.castShadow = true;
      node.receiveShadow = true;
    });
    this.scene.add(ladder);
    l.model = ladder;
  }

  /** Takes it down (it's back in your hands, or you've left). */
  away() {
    if (this.leaning?.model) this.scene.remove(this.leaning.model);
    this.leaning = undefined;
  }

  /** Dropped against the wall: it stays there, as an object lying in the place. */
  handOver(): Object3D | undefined {
    const model = this.leaning?.model;
    if (this.leaning) this.leaning.model = undefined;
    return model;
  }

  /** Where its foot is, and which way it faces: for laying it down where it stood. */
  get footing() {
    const l = this.leaning;
    return l && { x: l.foot.x, z: l.foot.z, yaw: Math.atan2(l.along[0], l.along[1]) };
  }

  /** Each frame: walk into it and you climb over (starting(exit) as you set off), then over(exit) is called. */
  update(over: (exit: string) => void, starting: (exit: string) => void = () => {}) {
    const l = this.leaning;
    if (!l || this.player.busy) return;
    const p = this.player.position;
    const fromFace = (p.x - l.corner.x) * l.out[0] + (p.z - l.corner.z) * l.out[1];
    const sideways = (p.x - l.foot.x) * l.along[0] + (p.z - l.foot.z) * l.along[1];
    const run = Math.hypot(l.foot.x - l.corner.x, l.foot.z - l.corner.z);
    const onIt = fromFace > 0 && fromFace < run + 0.3 && Math.abs(sideways) < 0.7;
    if (!onIt) l.armed = true;
    if (!onIt || !l.armed) return;
    starting(l.exit);
    this.player.follow(this.climb(l), CLIMB, () => over(l.exit));
  }

  // Up the ladder (a little bob at each rung), across the top and down the far side.
  private climb(l: Leaning) {
    const [ox, oz] = l.out;
    const start = this.player.position.clone();
    const away = (v: Vector3, d: number) => new Vector3(v.x + ox * d, v.y, v.z + oz * d);
    const bottom = away(l.foot.clone().lerp(l.corner, 0.08), BODY);
    const top = away(l.corner, BODY);
    const across = new Vector3(
      l.centre[0] - ox * (l.thick + BODY),
      l.corner.y + 0.1,
      l.centre[1] - oz * (l.thick + BODY)
    );
    const land = new Vector3(l.centre[0] - ox * (l.thick + 1.2), 0, l.centre[1] - oz * (l.thick + 1.2));
    land.y = this.ground(land.x, land.z) ?? 0;
    const rungs = Math.round(l.foot.distanceTo(l.corner) / 0.3);
    const at = new Vector3();
    return (t: number) => {
      if (t < 0.1) return at.lerpVectors(start, bottom, t / 0.1);
      if (t < 0.65) {
        const u = (t - 0.1) / 0.55;
        at.lerpVectors(bottom, top, u);
        if (!this.reducedMotion) at.y += Math.abs(Math.sin(u * rungs * Math.PI)) * 0.06;
        return at;
      }
      // At the top it comes back into your hands.
      if (l.model && this.leaning === l) this.away();
      if (t < 0.82) return at.lerpVectors(top, across, (t - 0.65) / 0.17);
      // Then down, falling the last bit.
      const u = (t - 0.82) / 0.18;
      at.lerpVectors(across, land, u);
      at.y = across.y + (land.y - across.y) * u * u;
      return at;
    };
  }

  private lengthOf(model: Object3D) {
    return new Box3().setFromObject(model).getSize(new Vector3()).z;
  }
}
