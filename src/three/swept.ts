// Walking into the deep river: "You are swept away by the current." (PLAN-V3.md:
// deaths are short scenes from where you stand.) You wade down the bank into
// the water, up to your neck; the current takes you, slowly turning you to
// face downstream, and carries you off with its foam, bobbing up and down,
// turning round in it, and going under (twice). It goes on carrying you as
// the curtain falls (from a little before `ends`), then stops there, still
// (behind the curtain by then; or you'd be carried on into the rocks where
// the river goes under).

import { Euler, type PerspectiveCamera, Quaternion, Vector3 } from "three";

import type { Ground } from "./player";
import { FLOW, type River } from "./river";

// The scene's beats, in seconds from walking in.
const WADE = 1.8; // down the bank, into the water
const TURNING = 1.2; // from this, the current turns you downstream…
const TURNED = 4.6; // …slowly, till this
const ENDS = 7.4; // carried off: the curtain comes down over the end of it, and there it stops

const IN = 3; // metres from the river's middle you wade out to
const NECK = 0.28; // your eyes above the water, swept along
const FAST = FLOW * 1.15; // metres a second, at your fastest (a little faster than its foam)
const SPEEDING = 1.8; // seconds for it to get you up to that
const LOOKING_DOWN = -0.25; // at the water, wading in
// Going under: when (seconds after the current takes you), for how long, and how deep (your eyes).
const DUNKS = [
  { at: 2.6, for: 0.7, deep: 0.55 },
  { at: 4.7, for: 0.55, deep: 0.45 },
];

export class Swept {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3;
  private readonly facing: Quaternion;
  private readonly eye: number; // your eye above the ground, standing
  private readonly start: number; // along the river, where you wade in
  private readonly side: number; // which side of its middle you're on (1: its left, looking downstream)
  private readonly wadeTo: Vector3;
  private readonly wading: number; // which way you wade in (a yaw)
  private along = 0; // how far the current's carried you

  constructor(
    private camera: PerspectiveCamera,
    private ground: Ground,
    private river: River,
    private reducedMotion: boolean
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    this.eye = this.from.y - (ground(this.from.x, this.from.z) ?? 0);
    this.start = river.nearest(this.from.x, this.from.z);
    // (Which side of its middle you're on: the one nearer you.)
    const near = (side: number) => {
      const [x, z] = river.at(this.start, IN * side);
      return Math.hypot(x - this.from.x, z - this.from.z);
    };
    this.side = near(1) < near(-1) ? 1 : -1;
    const [x, z] = river.at(this.start, IN * this.side);
    this.wadeTo = new Vector3(x, river.water + NECK, z);
    this.wading = yawOf(this.wadeTo.x - this.from.x, this.wadeTo.z - this.from.z);
  }

  /** Each frame (till it ends). */
  update(dt: number) {
    if (this.t >= ENDS) return;
    this.t = Math.min(ENDS, this.t + dt);
    const t = this.t;
    const s = Math.max(0, t - WADE); // since the current took you
    const calm = this.reducedMotion ? 0.3 : 1;
    // (Bobbing, turning round and tipping grow on you as it takes you.)
    const grow = smoother(s / 2.5) * calm;
    const position = new Vector3();
    if (t < WADE) {
      // Down the bank and in: your feet on the ground till it's under the
      // water, then up to your neck in it.
      const u = ease(t / WADE);
      position.lerpVectors(this.from, this.wadeTo, u);
      const feet = this.ground(position.x, position.z) ?? this.river.water;
      position.y = Math.max(feet + this.eye, this.river.water + NECK);
      if (!this.reducedMotion) position.y += Math.abs(Math.sin(u * Math.PI * 4)) * 0.04 * (1 - u);
    } else {
      // The current: slow at first, then fast, and drawing you out into the middle.
      this.along += dt * FAST * Math.min(1, s / SPEEDING) ** 2;
      const out = IN * (1 - smoother(s / 3.5)) + 0.8 * Math.sin(s * 0.9) * grow;
      const [x, z] = this.river.at(this.start + this.along, out * this.side);
      const bob = (0.1 * Math.sin(s * 2.7) + 0.05 * Math.sin(s * 5.9 + 1)) * grow;
      const under = this.reducedMotion
        ? 0
        : DUNKS.reduce((d, dunk) => {
            const u = (s - dunk.at) / dunk.for;
            return u > 0 && u < 1 ? Math.max(d, dunk.deep * Math.sin(u * Math.PI)) : d;
          }, 0);
      position.set(x, this.river.water + NECK + bob - under, z);
    }
    // Which way you look: where you're wading, slowly turning (from as the
    // water takes you) to face downstream, and turning round in it, tipping
    // and rolling as you go.
    const [ax, az] = this.river.at(this.start + this.along, 0);
    const [bx, bz] = this.river.at(this.start + this.along + 2, 0);
    const turned = smoother((t - TURNING) / (TURNED - TURNING));
    const yaw =
      this.wading +
      across(this.wading, yawOf(bx - ax, bz - az)) * turned +
      (0.5 * Math.sin(s * 0.8) + 0.18 * Math.sin(s * 2.3)) * grow;
    const pitch = LOOKING_DOWN * (1 - turned) + (-0.03 + 0.09 * Math.sin(s * 1.9)) * grow;
    const roll = 0.13 * Math.sin(s * 1.3) * grow;
    const look = new Quaternion().setFromEuler(new Euler(pitch, yaw, roll, "YXZ"));
    // (From where you were looking, at first.)
    this.camera.quaternion.slerpQuaternions(this.facing, look, smoother(t / 0.8));
    this.camera.position.copy(position);
  }
}

// The yaw that looks along [x, z] (0 looks north, -z).
const yawOf = (x: number, z: number) => Math.atan2(-x, -z);

// The turn from one yaw to another, the short way round.
const across = (from: number, to: number) => {
  const d = (to - from) % (Math.PI * 2);
  return d > Math.PI ? d - Math.PI * 2 : d < -Math.PI ? d + Math.PI * 2 : d;
};

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};

// (Gentler still, at both ends.)
const smoother = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * u * (u * (u * 6 - 15) + 10);
};
