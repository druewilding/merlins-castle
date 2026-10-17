// Walking into the witches: "The witches catch you and tie you up."
// (PLAN-V3.md: deaths are short scenes from where you stand.) They break
// off their dance and run at you, close round you and throw their ropes over
// you (witches.ts); you look to the one nearest in front of you as they come.
// Tied, you sink to the ground, and they dance round you, one after another
// going by in front of you, as the curtain falls (from a little before `ends`).

import { Matrix4, type PerspectiveCamera, Quaternion, Vector3 } from "three";

import type { Ground } from "./player";
import type { Witches } from "./witches";

// The scene's beats, in seconds from walking into them.
const TIED = 3.6; // their ropes thrown: you go down…
const DOWN = 4.6; // …till you're sitting on the ground
const ENDS = 8;

const SITTING = 0.85; // your eye above the ground, tied up
const FLINCH = 0.25; // metres you step back, as they come
const LOOKING = 3; // how quickly you turn to look at her (the larger, the quicker)

export class Caught {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3;
  private readonly back: Vector3; // which way's back, from them
  private readonly eye: number; // your eye above the ground, standing
  private readonly her: number; // which of them you look at
  private readonly up = new Vector3(0, 1, 0);
  private readonly turn = new Matrix4();
  private readonly look = new Quaternion();
  private ahead: Vector3 | undefined; // where you look, tied up

  constructor(
    private camera: PerspectiveCamera,
    private ground: Ground,
    private witches: Witches,
    private reducedMotion: boolean
  ) {
    this.from = camera.position.clone();
    this.eye = this.from.y - (ground(this.from.x, this.from.z) ?? 0);
    // (The one nearest straight ahead of you.)
    const ahead = new Vector3(0, 0, -1).applyQuaternion(camera.quaternion).setY(0).normalize();
    const faces = witches.faces();
    const straight = (face: Vector3) => face.clone().sub(this.from).setY(0).normalize().dot(ahead);
    this.her = faces.reduce((best, face, n) => (straight(face) > straight(faces[best]) ? n : best), 0);
    this.back = ahead.clone().negate();
    witches.catch(this.from.x, this.from.z);
  }

  /** Each frame (till it ends). */
  update(dt: number) {
    if (this.t >= ENDS) return;
    this.t = Math.min(ENDS, this.t + dt);
    const t = this.t;
    const calm = this.reducedMotion ? 0 : 1;
    // A step back as they come (then held where you are by their ropes), and
    // down to the ground, tied.
    const position = this.from.clone().addScaledVector(this.back, FLINCH * ease(t / 1.2) * (1 - ease((t - 2) / 1.5)));
    const floor = this.ground(position.x, position.z) ?? this.from.y - this.eye;
    const down = ease((t - TIED) / (DOWN - TIED));
    position.y = floor + this.eye + (SITTING - this.eye) * down;
    // (Struggling a little in their ropes, sat there.)
    position.x += 0.03 * Math.sin(t * 7.3) * down * calm;
    position.z += 0.02 * Math.sin(t * 5.1 + 1) * down * calm;
    this.camera.position.copy(position);
    // Looking at her, turning to her, a little at a time; then, tied up,
    // ahead of you, at them going by.
    const face = this.witches.faces()[this.her];
    if (t >= TIED) this.ahead ??= face.clone();
    this.turn.lookAt(position, this.ahead ?? face, this.up);
    this.look.setFromRotationMatrix(this.turn);
    this.camera.quaternion.slerp(this.look, 1 - Math.exp(-dt * LOOKING));
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
