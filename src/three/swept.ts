// Walking into the deep river: "You are swept away by the current." (PLAN-V3.md:
// deaths are short scenes from where you stand.) You wade down the bank into
// the water, up to your neck; the current takes you, turns you downstream
// and carries you off, faster and faster, bobbing up and down and turning
// round in it, going under (twice), with flecks of foam rushing past on
// the water round you. Then done(): the curtain.

import {
  BufferAttribute,
  BufferGeometry,
  Euler,
  type PerspectiveCamera,
  Points,
  PointsMaterial,
  Quaternion,
  type Scene,
  Vector3,
} from "three";

import type { Ground } from "./player";
import { speck } from "./shafts";

// The scene's beats, in seconds from walking in.
const WADE = 1.8; // down the bank, into the water
const TURNED = 1.6; // after that, the current's turned you downstream
const AFTER = 7.2; // carried off, then the curtain

const IN = 3; // metres from the river's middle you wade out to
const NECK = 0.28; // your eyes above the water, swept along
const FAST = 4.5; // metres a second, the current at its fastest
const SPEEDING = 1.5; // seconds for it to get you up to that
// Going under: when (seconds after the current takes you), for how long, and how deep (your eyes).
const DUNKS = [
  { at: 2.5, for: 0.7, deep: 0.55 },
  { at: 4.6, for: 0.55, deep: 0.45 },
];
const FLECKS = 160; // of foam, on the water round you
const RUSHING = 1.6; // metres a second faster than you (you drag)
const WIDE = 7; // from the river's middle, either side, where they are

export class Swept {
  private t = 0;
  private readonly from: Vector3;
  private readonly facing: Quaternion;
  private readonly eye: number; // your eye above the ground, standing
  private readonly lengths: number[] = [0]; // along the river, to each of its points
  private readonly start: number; // along the river, where you wade in
  private side = 1; // which side of its middle you're on (1: its left, looking downstream)
  private readonly wadeTo: Vector3;
  private along = 0; // how far the current's carried you
  private readonly look = new Quaternion();
  private readonly flecks: Points;
  private readonly spots: { s: number; out: number; pace: number }[] = []; // along the river, and out from its middle

  constructor(
    private scene: Scene,
    private camera: PerspectiveCamera,
    private ground: Ground,
    /** The river's middle, upstream to down ([x, z]), and its water's height. */
    private river: { line: number[][]; water: number },
    private reducedMotion: boolean,
    private done: () => void
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    this.eye = this.from.y - (ground(this.from.x, this.from.z) ?? 0);
    const { line } = river;
    for (let k = 1; k < line.length; k++) {
      this.lengths.push(this.lengths[k - 1] + Math.hypot(line[k][0] - line[k - 1][0], line[k][1] - line[k - 1][1]));
    }
    // Where you're nearest its middle.
    let best = { d: Infinity, s: 0 };
    for (let k = 1; k < line.length; k++) {
      const [ax, az] = line[k - 1];
      const [bx, bz] = line[k];
      const long = Math.hypot(bx - ax, bz - az);
      const u = Math.max(0, Math.min(1, ((this.from.x - ax) * (bx - ax) + (this.from.z - az) * (bz - az)) / long ** 2));
      const d = Math.hypot(this.from.x - (ax + (bx - ax) * u), this.from.z - (az + (bz - az) * u));
      if (d < best.d) best = { d, s: this.lengths[k - 1] + u * long };
    }
    this.start = best.s;
    // And which side of it you're on: the one nearer you.
    const near = (side: number) => {
      this.side = side;
      const [x, z] = this.at(this.start, IN);
      return Math.hypot(x - this.from.x, z - this.from.z);
    };
    this.side = near(1) < near(-1) ? 1 : -1;
    const [x, z] = this.at(this.start, IN);
    this.wadeTo = new Vector3(x, river.water + NECK, z);
    // The foam: anywhere on the water round where you go in.
    for (let k = 0; k < FLECKS; k++) {
      this.spots.push({
        s: this.start + (Math.random() - 0.3) * 24,
        out: (Math.random() * 2 - 1) * WIDE,
        pace: Math.random(),
      });
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(new Float32Array(FLECKS * 3), 3));
    this.flecks = new Points(
      geometry,
      new PointsMaterial({
        size: 0.14,
        map: speck(),
        color: "#eef7f8",
        transparent: true,
        opacity: 0.75,
        depthWrite: false,
      })
    );
    this.flecks.frustumCulled = false;
    scene.add(this.flecks);
  }

  /** Gone (the game starting again). */
  dispose() {
    this.scene.remove(this.flecks);
    this.flecks.geometry.dispose();
  }

  /** Each frame; false once it's over. */
  update(dt: number) {
    if (this.t >= AFTER) return false;
    this.t += dt;
    const t = this.t;
    const calm = this.reducedMotion ? 0.3 : 1;
    const position = new Vector3();
    let heading: Quaternion;
    if (t < WADE) {
      // Down the bank and in: your feet on the ground till it's under the
      // water, then up to your neck in it.
      const u = ease(t / WADE);
      position.lerpVectors(this.from, this.wadeTo, u);
      const feet = this.ground(position.x, position.z) ?? this.river.water;
      position.y = Math.max(feet + this.eye, this.river.water + NECK);
      if (!this.reducedMotion) position.y += Math.abs(Math.sin(u * Math.PI * 4)) * 0.04 * (1 - u);
      // Looking where you're going, a little down at the water.
      heading = this.towards(this.wadeTo.clone().sub(this.from).setY(0), -0.25);
      this.look.slerpQuaternions(this.facing, heading, ease(t / 0.6));
    } else {
      // The current: slow at first, then fast, and drawing you out into the middle.
      const s = t - WADE;
      this.along += dt * FAST * Math.min(1, s / SPEEDING) ** 2;
      const out = IN * (1 - ease(s / 3)) + 0.8 * Math.sin(s * 0.9) * calm;
      const [x, z] = this.at(this.start + this.along, out);
      // Bobbing up and down in it, and going under.
      const bob = (0.1 * Math.sin(s * 2.7) + 0.05 * Math.sin(s * 5.9 + 1)) * calm;
      const under = this.reducedMotion
        ? 0
        : DUNKS.reduce((d, dunk) => {
            const u = (s - dunk.at) / dunk.for;
            return u > 0 && u < 1 ? Math.max(d, dunk.deep * Math.sin(u * Math.PI)) : d;
          }, 0);
      position.set(x, this.river.water + NECK + bob - under, z);
      // Turned round to face downstream, and turning round in it, tipping as you go.
      const [ax, az] = this.at(this.start + this.along, 0);
      const [bx, bz] = this.at(this.start + this.along + 1, 0);
      const spin = (0.55 * Math.sin(s * 0.8) + 0.2 * Math.sin(s * 2.3)) * calm;
      const tip = (-0.04 + 0.1 * Math.sin(s * 1.9)) * calm;
      const roll = 0.14 * Math.sin(s * 1.3) * calm;
      const down = this.towards(new Vector3(bx - ax, 0, bz - az), tip, spin, roll);
      const wading = this.towards(this.wadeTo.clone().sub(this.from).setY(0), -0.25);
      heading = wading.slerp(down, ease(s / TURNED));
      this.look.copy(heading);
    }
    this.camera.position.copy(position);
    this.camera.quaternion.copy(this.look);
    this.foam(dt);
    if (t >= AFTER) this.done();
    return true;
  }

  // The foam, carried along a little faster than you are (and from behind
  // you, upstream, once it's gone on ahead).
  private foam(dt: number) {
    const you = this.start + this.along;
    const speed = this.t < WADE ? 0 : FAST * Math.min(1, (this.t - WADE) / SPEEDING) ** 2;
    const positions = this.flecks.geometry.attributes.position as BufferAttribute;
    this.spots.forEach((spot, k) => {
      spot.s += dt * (speed + RUSHING * (0.6 + 0.8 * spot.pace));
      if (spot.s > you + 16) spot.s = you - 8 - Math.random() * 4;
      const [x, z] = this.at(spot.s, spot.out);
      positions.setXYZ(k, x, this.river.water + 0.02, z);
    });
    positions.needsUpdate = true;
  }

  // A point along the river (metres from its start), out from its middle to your side.
  private at(s: number, out: number): [number, number] {
    const { line } = this.river;
    let k = 1;
    while (k < line.length - 1 && this.lengths[k] < s) k++;
    const [ax, az] = line[k - 1];
    const [bx, bz] = line[k];
    const long = this.lengths[k] - this.lengths[k - 1];
    const u = Math.max(0, Math.min(1, (s - this.lengths[k - 1]) / long));
    // (Its left, looking downstream along [dx, dz], is [dz, -dx].)
    const dx = (bx - ax) / long;
    const dz = (bz - az) / long;
    return [ax + (bx - ax) * u + dz * out * this.side, az + (bz - az) * u - dx * out * this.side];
  }

  // Looking along a direction on the ground, tipped up (or down), turned and rolled.
  private towards(direction: Vector3, pitch: number, turn = 0, roll = 0) {
    const yaw = Math.atan2(-direction.x, -direction.z) + turn;
    return new Quaternion().setFromEuler(new Euler(pitch, yaw, roll, "YXZ"));
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
