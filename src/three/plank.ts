// The plank in use: across the deep river where it narrows, always in the
// same spot, where the way comes down to it. Used, it's stood up on its end
// at the water's edge on your side, and tips over across the river to land
// on the far bank; walk onto it and you go across (it gives a little under
// you), and it comes back into your hands on the other side (it's carried,
// as in the original), unless you dropped it there: then it stays.

import { type Object3D, type Scene, Vector3 } from "three";

import type { Ground, Player } from "./player";

const TIPPING = 0.7; // seconds, falling over across the river
const CROSS = 1.6; // seconds, running from its end on this side to the far bank
const STRIDE = 1.3; // metres, running across it
// How near its end on your side you start across: from behind it, or on past
// it, and to either side (anywhere near it, coming at it from any side: but
// not walking away from the river).
const BEHIND = 2.2;
const PAST = 0.8;
const ASIDE = 1.8;
const SAG = 0.08; // metres it gives in the middle, as you cross
const OFF = 0.9; // metres on, off its far end, where you step down

export class Plank {
  private laid:
    | {
        exit: string;
        near: Vector3; // its end on your side (on the ground), and the far one
        far: Vector3;
        model?: Object3D; // (gone once you've dropped it there: it's lying there then)
        tipped: number; // 0 standing on its end, 1 down across the river
      }
    | undefined;
  private was = new Vector3(); // where you were last frame

  constructor(
    private scene: Scene,
    private model: Object3D,
    private ground: Ground,
    private player: Player,
    private reducedMotion: boolean,
    /** It lands across the river. */
    private thud: () => void,
    /** A footstep, running across it. */
    private step: () => void
  ) {}

  /** Whether you can see it across the river (it's not, once you've dropped it there). */
  get shown() {
    return Boolean(this.laid?.model);
  }

  /**
   * Across the narrows for an exit, from its end on your side ([x, z], on the
   * shore you're going from) to the far one: tipping over across it, or (as a
   * game's loaded) already down. Not shown, if it's been dropped there.
   */
  lay(exit: string, near: [number, number], far: [number, number], show: boolean, instantly: boolean) {
    this.away();
    const end = ([x, z]: [number, number]) => new Vector3(x, this.ground(x, z) ?? 0, z);
    this.laid = { exit, near: end(near), far: end(far), tipped: instantly || this.reducedMotion ? 1 : 0 };
    if (show) this.show();
  }

  /** Back across the river where it was (taken from there, it's still in use). */
  show() {
    const l = this.laid;
    if (!l || l.model) return;
    l.model = this.model.clone();
    l.model.traverse((node) => {
      node.castShadow = true;
      node.receiveShadow = true;
    });
    this.scene.add(l.model);
    this.place();
  }

  /** Takes it up (it's back in your hands, or you've left). */
  away() {
    if (this.laid?.model) this.scene.remove(this.laid.model);
    this.laid = undefined;
  }

  /** Dropped there: it stays, as an object lying in the place. */
  handOver(): Object3D | undefined {
    const model = this.laid?.model;
    if (this.laid) this.laid.model = undefined;
    return model;
  }

  /** Where it lies, and which way: for laying it down where it was. */
  get footing() {
    const l = this.laid;
    return (
      l && {
        x: (l.near.x + l.far.x) / 2,
        z: (l.near.z + l.far.z) / 2,
        yaw: Math.atan2(l.far.x - l.near.x, l.far.z - l.near.z),
      }
    );
  }

  /** Each frame: it tips over; then walk onto it and you go across, then over(exit) is called. */
  update(dt: number, over: (exit: string) => void) {
    const l = this.laid;
    const p = this.player.position;
    const moved = p.clone().sub(this.was);
    this.was.copy(p);
    if (!l) return;
    if (l.tipped < 1) {
      l.tipped = Math.min(1, l.tipped + dt / TIPPING);
      if (l.tipped === 1) this.thud();
      this.place();
      return;
    }
    if (this.player.busy) return;
    // Near its end on your side, and walking (but not away from the river).
    const length = l.near.distanceTo(l.far);
    const along = new Vector3(l.far.x - l.near.x, 0, l.far.z - l.near.z).normalize();
    const on = (p.x - l.near.x) * along.x + (p.z - l.near.z) * along.z;
    const aside = (p.x - l.near.x) * along.z - (p.z - l.near.z) * along.x;
    const going = moved.x * along.x + moved.z * along.z;
    const walking = Math.hypot(moved.x, moved.z);
    if (on < -BEHIND || on > PAST || Math.abs(aside) > ASIDE || walking < 0.001 || going < -0.5 * walking) return;
    this.player.follow(this.across(l, length, along), CROSS, () => over(l.exit));
  }

  // Onto it, running along it (giving a little under you, and a footstep at
  // each stride), and off its far end onto the bank. At the far end it comes
  // back into your hands.
  private across(l: NonNullable<Plank["laid"]>, length: number, along: Vector3) {
    const start = this.player.position.clone();
    const top = (u: number) => {
      const at = new Vector3().lerpVectors(l.near, l.far, u);
      at.y += 0.08 - SAG * Math.sin(u * Math.PI);
      return at;
    };
    const off = l.far.clone().addScaledVector(along, OFF);
    off.y = this.ground(off.x, off.z) ?? l.far.y;
    const strides = Math.max(2, Math.round(length / STRIDE));
    const at = new Vector3();
    let stepped = -1; // the last stride you've taken
    const footstep = (k: number) => {
      if (k > stepped) this.step();
      stepped = Math.max(stepped, k);
    };
    return (t: number) => {
      if (t < 0.15) {
        footstep(0);
        return at.lerpVectors(start, top(0), t / 0.15);
      }
      if (t < 0.9) {
        const u = (t - 0.15) / 0.75;
        footstep(1 + Math.floor(u * strides));
        at.copy(top(u));
        if (!this.reducedMotion) at.y += Math.abs(Math.sin(u * strides * Math.PI)) * 0.04;
        return at;
      }
      footstep(strides + 1);
      if (l.model && this.laid === l) this.away();
      return at.lerpVectors(top(1), off, (t - 0.9) / 0.1);
    };
  }

  // Where it is: standing on its near end, tipping over (faster and faster)
  // to lie across, its middle over the water. (Its middle and underside are
  // its origin, lying along z: items.py.)
  private place() {
    const l = this.laid;
    if (!l?.model) return;
    const u = l.tipped;
    const fall = u * u; // (falling: slowly at first, then fast)
    const up = (Math.PI / 2) * (1 - fall); // its angle up from lying flat
    const length = l.near.distanceTo(l.far);
    const yaw = Math.atan2(l.far.x - l.near.x, l.far.z - l.near.z);
    const rise = l.far.y - l.near.y;
    const flat = Math.atan2(rise, Math.hypot(l.far.x - l.near.x, l.far.z - l.near.z));
    const angle = flat + up;
    const along = new Vector3(Math.sin(yaw) * Math.cos(angle), Math.sin(angle), Math.cos(yaw) * Math.cos(angle));
    l.model.position.copy(l.near).addScaledVector(along, length / 2);
    l.model.rotation.set(0, yaw + Math.PI, 0, "YXZ");
    l.model.rotateX(angle);
  }
}
