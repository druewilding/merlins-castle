// The deep, deep hole across the way from the maze to the treasure room:
// "You slip down a deep, deep hole." You step up to its edge and peer in,
// wobble, your feet slip and you tip in: down and down, tumbling slowly
// round, the rock of its walls going by in your own faint glow (falling with
// you: main.ts), darker and darker; slowing at the bottom, softly, to a stop.
// The curtain comes down over the end of it (from a little before `ends`).

import { Euler, type PerspectiveCamera, Quaternion, Vector3 } from "three";

/** The hole, from land.json: [x, z, half x, half z], the floor across it, its bottom, and its beam's underside. */
export interface HoleSpot {
  box: number[];
  floor: number;
  bottom: number;
  beam: number;
}

// The scene's beats, in seconds from walking into it.
const STEPPED = 0.35; // up to its edge, looking in
const SLIP = 0.9; // a wobble there, and your feet go
const FALLEN = 1.7; // tipped in, over its middle
const ENDS = 6.5;

const EDGE = 0.1; // how far back from the edge you stand
const PEER = -0.75; // looking down into it (radians)
const TUMBLING = -1.15; // and down it, falling, nodding this far either way of that
const NODDING = 0.45;
const IN = 1.2; // metres down, fallen over into it
const FALLING = 8; // how fast you speed up, falling (m/s²)
const FASTEST = 16; // m/s
const SLOWING = 6; // and slow down, coming to the bottom (m/s²)
const LANDED = 1.3; // your eye over its bottom, come to a stop
const RESTING = -0.35; // looking at the foot of its wall, stopped
const TURNING = 0.7; // round, as you go down (radians a second)
const DIMMEST = 0.3; // your glow, at the bottom

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
  private readonly drop: number; // how far down it you fall, from its middle
  // Falling: how far, how fast, and turning round (by how fast).
  private fallen = 0;
  private speed = 0;
  private slowed: number | undefined; // how fast you were going when you started to slow down
  private turned = 0;
  private tumbled = 0;
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
    this.drop = this.middle.y - (hole.bottom + LANDED);
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
      // A wobble, leaning out over it.
      this.eye.copy(this.edge);
      if (!still) {
        const u = (t - STEPPED) / (SLIP - STEPPED);
        const sway = Math.sin(u * Math.PI * 2) * Math.sin(u * Math.PI);
        this.eye.z -= this.side * 0.05 * sway;
        roll = 0.04 * sway;
        pitch += 0.08 * sway;
      }
    } else {
      // Your feet slip: you tip in, over its middle, and down and down,
      // tumbling slowly round; slowing at the bottom to a stop, and the
      // tumbling with it.
      const u = ease((t - SLIP) / (FALLEN - SLIP));
      if (t > SLIP + 0.2) {
        const accelerating = Math.min(FASTEST, this.speed + FALLING * dt);
        const stopping = Math.sqrt(2 * SLOWING * Math.max(0, this.drop - this.fallen));
        if (stopping < accelerating) this.slowed ??= this.speed;
        this.speed = Math.min(accelerating, stopping);
        this.fallen = Math.min(this.drop, this.fallen + this.speed * dt);
      }
      // (How wild it is: all the way, falling, and less and less, slowing down.)
      const wild = this.slowed ? ease(this.speed / this.slowed) : 1;
      this.eye.lerpVectors(this.edge, this.middle, u);
      this.eye.y -= this.fallen;
      pitch = PEER + (TUMBLING - PEER) * u;
      if (!still) {
        // (Drifting a little, about the middle: nodding, turning, rolling.)
        this.tumbled += dt * wild;
        this.turned += TURNING * Math.min(1, this.tumbled / 1.5) * wild * dt;
        const k = this.tumbled;
        this.eye.x += 0.25 * Math.sin(k * 1.3) * u * wild;
        this.eye.z += 0.2 * Math.sin(k * 0.9 + 1) * u * wild;
        pitch += NODDING * Math.sin(k * 1.2) * u;
        yaw += this.turned;
        roll = 0.3 * Math.sin(k * 0.8) * u * wild;
      }
      pitch = RESTING + (pitch - RESTING) * wild;
      this.glow = 1 - (1 - DIMMEST) * (this.fallen / this.drop);
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
