// Walking into the mist at the edge of the world: "You are lost but you find
// a clue." (PLAN-V3.md: the mist thickens, the world fades.) Past its edge
// you stagger on a step or two, turning this way and that, round and round
// as you lose your bearings, while the mist comes down round you till
// there's nothing to see. The curtain (a misty one: the clue in it) comes
// up over the end of it (from a little before `ends`), the mist still
// thickening as the clue shows. With motion reduced, you stand still, and
// only the mist comes down.

import { Euler, type PerspectiveCamera, Quaternion, Vector3 } from "three";

import type { Ground } from "./player";

const STAGGER = 1.6; // seconds: on a little way, slowing
const ON = 1.5; // metres, on the land (less underground: a tunnel's narrow)
const ON_UNDER = 0.8;
const SPUN = 3; // seconds: turned round, by
const TURN = Math.PI * 1.4; // this far (and back and forth on the way)
const LURCH = 0.6; // radians: first, the other way, and back (in this many seconds)
const LURCHING = 1.2;
const THICK = [0.2, 4.4]; // seconds: the mist from nothing, to as thick as it gets (still coming in as the clue shows)
const ENDS = 3.4;

export class Lost {
  readonly ends = ENDS;
  /** How thick the mist is: 0 to 1. */
  mist = 0;
  private t = 0;
  private readonly from: Vector3;
  private readonly facing: Quaternion;
  private readonly yaw: number;
  private readonly pitch: number;
  private readonly ahead: Vector3;
  private readonly eye: number; // your eye above the ground
  private readonly way = Math.random() < 0.5 ? 1 : -1; // which way round you turn (after a lurch the other way)

  constructor(
    private camera: PerspectiveCamera,
    private ground: Ground,
    private under: boolean,
    private reducedMotion: boolean
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    const looking = new Euler().setFromQuaternion(this.facing, "YXZ");
    this.yaw = looking.y;
    this.pitch = looking.x;
    this.ahead = new Vector3(-Math.sin(this.yaw), 0, -Math.cos(this.yaw)).multiplyScalar(under ? ON_UNDER : ON);
    this.eye = this.from.y - (ground(this.from.x, this.from.z) ?? this.from.y);
  }

  /** Each frame (the mist thickening on after it ends). */
  update(dt: number) {
    this.t += dt;
    this.mist = smoother((this.t - THICK[0]) / (THICK[1] - THICK[0]));
    if (this.t >= ENDS + dt || this.reducedMotion) return;
    const t = Math.min(ENDS, this.t);
    // On a little way, slowing: on the land, over the ground; underground,
    // along the floor.
    const position = this.from.clone().addScaledVector(this.ahead, 1 - (1 - Math.min(1, t / STAGGER)) ** 2);
    const feet = this.under ? undefined : this.ground(position.x, position.z);
    if (feet !== undefined) position.y = feet + this.eye;
    position.y += -0.04 * Math.sin(Math.min(1, t / STAGGER) * Math.PI * 3);
    // A lurch one way, then round and round the other, this way and that
    // (more as it goes), unsteady.
    const grow = smoother(t / 1.2);
    const yaw =
      this.yaw +
      this.way *
        (TURN * smoother((t - LURCHING * 0.4) / (SPUN - LURCHING * 0.4)) -
          LURCH * Math.sin(Math.PI * Math.min(1, t / LURCHING)) +
          0.2 * Math.sin(t * 2.6) * grow * smoother((t - LURCHING) / 0.6) +
          0.12 * Math.sin(t * 5.3) * grow);
    const pitch = this.pitch * (1 - smoother(t / 1.5)) + 0.06 * Math.sin(t * 1.9) * grow;
    const roll = 0.07 * Math.sin(t * 2.2 + 1) * grow;
    const look = new Quaternion().setFromEuler(new Euler(pitch, yaw, roll, "YXZ"));
    this.camera.quaternion.slerpQuaternions(this.facing, look, smoother(t / 0.5));
    this.camera.position.copy(position);
  }
}

// (Gentle at both ends.)
const smoother = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * u * (u * (u * 6 - 15) + 10);
};
