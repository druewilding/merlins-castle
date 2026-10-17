// The rabbits by the witches' sign (their model: art/blender/rabbits.py):
// "Some rabbits warn you of some witches dancing in the West." They sit in
// the grass by it, turn to watch you as you come, and, near, shake their
// heads at you, now and then, each in its own time.
//
// Their clips are the Bunny's, named as they are there.

import {
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  LoopOnce,
  Mesh,
  type Object3D,
  type Scene,
  type Vector3,
} from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

import type { Ground } from "./player";

const WATCH = 25; // metres: this near, they turn to watch you
const WARN = 12; // metres: this near, they shake their heads at you
const SHAKES = [2.5, 6]; // seconds between one's head-shakes, between these
const TURN = 1.8; // radians a second, turning
const BLEND = 0.25; // seconds from one clip to the next
const SIZES = [1, 0.88, 0.94];

const between = ([a, b]: number[]) => a + Math.random() * (b - a);

class Rabbit {
  readonly model: Object3D;
  private mixer: AnimationMixer;
  private clips = new Map<string, AnimationAction>();
  private playing: AnimationAction | undefined;
  private wait = between(SHAKES);
  private yaw: number;

  constructor(
    scene: Scene,
    source: Object3D,
    animations: AnimationClip[],
    at: { x: number; z: number; yaw: number },
    n: number,
    ground: Ground
  ) {
    this.model = clone(source);
    this.model.traverse((o) => {
      if (o instanceof Mesh) {
        o.castShadow = true;
        o.frustumCulled = false; // (moved by its bones: its bounds don't follow)
      }
    });
    this.model.scale.multiplyScalar(SIZES[n % SIZES.length]);
    this.model.position.set(at.x, ground(at.x, at.z) ?? 0, at.z);
    this.yaw = at.yaw;
    this.model.rotation.y = at.yaw;
    scene.add(this.model);
    this.mixer = new AnimationMixer(this.model);
    for (const clip of animations) this.clips.set(clip.name, this.mixer.clipAction(clip));
    const no = this.clips.get("No");
    no?.setLoop(LoopOnce, 1);
    if (no) no.clampWhenFinished = true;
    this.play("Idle");
    if (this.playing) this.playing.time = Math.random() * this.playing.getClip().duration; // (not in step)
  }

  private play(name: string) {
    const next = this.clips.get(name);
    if (!next || next === this.playing) return;
    next.reset().play();
    if (this.playing) next.crossFadeFrom(this.playing, BLEND, false);
    this.playing = next;
  }

  update(dt: number, you: Vector3) {
    const at = this.model.position;
    const far = Math.hypot(you.x - at.x, you.z - at.z);
    if (far < WATCH) {
      let turn = Math.atan2(you.x - at.x, you.z - at.z) - this.yaw;
      turn = Math.atan2(Math.sin(turn), Math.cos(turn));
      this.yaw += Math.sign(turn) * Math.min(Math.abs(turn), TURN * dt);
      this.model.rotation.y = this.yaw;
    }
    this.wait -= dt;
    // (A head-shake plays out, then it's back to sitting.)
    const shaking = this.playing?.loop === LoopOnce && this.playing.isRunning();
    if (!shaking) this.play("Idle");
    if (far < WARN && this.wait <= 0 && !shaking) {
      this.play("No");
      this.wait = between(SHAKES);
    }
    this.mixer.update(dt);
  }
}

export class Rabbits {
  private rabbits: Rabbit[];

  constructor(
    scene: Scene,
    model: Object3D,
    animations: AnimationClip[],
    spots: { x: number; z: number; yaw: number }[],
    ground: Ground
  ) {
    this.rabbits = spots.map((spot, n) => new Rabbit(scene, model, animations, spot, n, ground));
  }

  /** Each frame: where you are (they watch you, and warn you). */
  update(dt: number, you: Vector3) {
    for (const rabbit of this.rabbits) rabbit.update(dt, you);
  }
}
