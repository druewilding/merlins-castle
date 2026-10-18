// The deep, deep hole across the way from the maze to the treasure room:
// "You slip down a deep, deep hole." You step up to its edge and peer in,
// teeter there, your feet slip and you tip in: down and down, tumbling slowly
// round, the rock of its walls going by in your own faint glow (falling with
// you: main.ts), darker and darker. The curtain comes down over the end of
// it (from a little before `ends`).

import { Euler, type PerspectiveCamera, Quaternion, Vector3 } from "three";

/** The hole, from land.json: [x, z, half x, half z], the floor across it, its bottom, and its beam's underside. */
export interface HoleSpot {
  box: number[];
  floor: number;
  bottom: number;
  beam: number;
}

// The scene's beats, in seconds from walking into it.
const STEPPED = 0.6; // up to its edge, looking in
const SLIP = 1.7; // teetering there, till your feet go
const FALLEN = 2.5; // tipped in, over its middle
const ENDS = 6.5;

const EDGE = 0.3; // how far back from the edge you stand
const PEER = -0.75; // looking down into it (radians)
const TUMBLING = -1.15; // and down it, falling, nodding this far either way of that
const NODDING = 0.45;
const IN = 1.2; // metres down, fallen over into it
const FALLING = 6.5; // how fast you speed up, falling (m/s²)
const FASTEST = 15; // m/s
const TURNING = 0.7; // round, as you go down (radians a second)
const DARKER = 45; // metres down, your glow's as dim as it gets
const DIMMEST = 0.3;

export class Slipped {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3; // your eye, where you were when you came to it
  private readonly facing: Quaternion;
  private readonly yaw: number; // looking across it
  private readonly side: number; // which side of it you're on: 1 south (the maze's), -1 north
  private readonly edge: Vector3; // where you stand, at its edge
  private readonly middle: Vector3; // over its middle, fallen in
  private readonly eye = new Vector3();
  private readonly look = new Quaternion();
  private readonly euler = new Euler(0, 0, 0, "YXZ");
  /** How bright your glow is (0 to 1), falling: dimmer and dimmer, the further down. */
  glow = 1;

  constructor(
    private camera: PerspectiveCamera,
    private hole: HoleSpot,
    private reducedMotion: boolean,
    /** Your feet go. */
    private slip: () => void
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    const [x, z, halfX, halfZ] = hole.box;
    this.side = this.from.z > z ? 1 : -1;
    this.yaw = this.side > 0 ? 0 : Math.PI;
    const across = Math.max(-(halfX - 0.6), Math.min(halfX - 0.6, this.from.x - x));
    this.edge = new Vector3(x + across, this.from.y, z + this.side * (halfZ + EDGE));
    this.middle = new Vector3(x + across * 0.3, this.from.y - IN, z + this.side * 0.3);
  }

  /** Each frame (on behind the curtain, too). */
  update(dt: number) {
    const was = this.t;
    this.t += dt;
    const t = this.t;
    if (was < SLIP && t >= SLIP) this.slip();
    const still = this.reducedMotion;
    let pitch = PEER;
    let roll = 0;
    let yaw = this.yaw;
    if (t < STEPPED) {
      // Up to the edge, looking in.
      this.eye.lerpVectors(this.from, this.edge, ease(t / STEPPED));
    } else if (t < SLIP) {
      // Teetering: leaning out over it and back, wobbling.
      this.eye.copy(this.edge);
      if (!still) {
        const u = (t - STEPPED) / (SLIP - STEPPED);
        const sway = Math.sin(u * Math.PI * 3) * Math.sin(u * Math.PI);
        this.eye.z -= this.side * 0.12 * sway;
        this.eye.y += 0.03 * Math.sin(u * Math.PI * 5);
        roll = 0.1 * Math.sin(u * Math.PI * 4) * Math.sin(u * Math.PI);
        pitch += 0.15 * sway;
      }
    } else {
      // Your feet slip: you tip in, over its middle, and down and down,
      // tumbling slowly round.
      const u = ease((t - SLIP) / (FALLEN - SLIP));
      this.eye.lerpVectors(this.edge, this.middle, u);
      const falling = Math.max(0, t - SLIP - 0.2);
      const speeding = FASTEST / FALLING; // (seconds, till you're falling as fast as you will)
      const down =
        falling < speeding
          ? (FALLING * falling * falling) / 2
          : (FASTEST * speeding) / 2 + FASTEST * (falling - speeding);
      this.eye.y = Math.max(this.hole.bottom + 4, this.eye.y - down);
      pitch = PEER + (TUMBLING - PEER) * u;
      if (!still) {
        // (Drifting a little, about the middle: nodding, turning, rolling.)
        this.eye.x += 0.25 * Math.sin(falling * 1.3) * u;
        this.eye.z += 0.2 * Math.sin(falling * 0.9 + 1) * u;
        pitch += NODDING * Math.sin(falling * 1.2) * u;
        yaw += (TURNING * falling * falling) / (falling + 1);
        roll = 0.3 * Math.sin(falling * 0.8) * u;
      }
      const deep = Math.min(1, (this.hole.floor - this.eye.y) / DARKER);
      this.glow = 1 - (1 - DIMMEST) * deep;
    }
    this.camera.position.copy(this.eye);
    this.look.setFromEuler(this.euler.set(pitch, yaw, roll));
    // (Turning to it, at first, from however you were looking.)
    this.camera.quaternion.slerpQuaternions(this.facing, this.look, ease(t / (STEPPED * 0.8)));
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
