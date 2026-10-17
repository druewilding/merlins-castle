// The witches in the forest (their model: art/blender/witches.py), on the
// way west to the crossroads ("Some rabbits warn you of some witches dancing
// in the West"). While you're elsewhere, they hide, crouching behind the
// trees west of their clearing, almost out of sight. Come into the clearing
// (from any way, the crossroads too) and they run out and dance in a ring,
// across the way west. Gone, they slip back into hiding.
//
// The three of them are made from the one model: each wears her own robe
// and hat (witch-robe-n, witch-hat-n), the others hidden.
//
// Walk into them (without the broom) and they catch you: they run at you,
// close round you, throw their ropes over you, and dance round you, tied
// up (caught.ts plays it, from where you are).
//
// Their clips are the Universal Animation Libraries', named as they are there.

import {
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  LoopOnce,
  Mesh,
  type Object3D,
  type Scene,
  Vector3,
} from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

import type { Ground } from "./player";

const RUN = 3.2; // metres a second, running out (and back)
const TURN = 5; // radians a second, turning
const SPIN = 0.45; // radians a second, the ring turning as they dance round it
const BLEND = 0.3; // seconds from one clip to the next
const SIZES = [1, 0.94, 0.97]; // each witch's size, from the model's
const FACE = 1.5; // metres up, her face (standing, at the model's size)
const STARTS = [0, 0.37, 0.71]; // how far into her dance each one is (of its length): not in step
const CLOSE = 1.2; // metres from you, closed round you, catching you
const ROUND_YOU = 1.1; // radians a second, the ring turning as they dance round you, tied up

export interface Ring {
  x: number;
  z: number;
  r: number;
}

type State = "hiding" | "coming" | "tying" | "dancing" | "going";

class Witch {
  readonly model: Object3D;
  private mixer: AnimationMixer;
  private clips = new Map<string, AnimationAction>();
  private playing: AnimationAction | undefined;
  state: State = "hiding";
  yaw = 0; // which way she faces (0 is +z)

  constructor(
    scene: Scene,
    source: Object3D,
    animations: AnimationClip[],
    n: number,
    readonly hide: { x: number; z: number }
  ) {
    this.model = clone(source);
    this.model.traverse((o) => {
      // (Only her own robe and hat.)
      const theirs = /^witch-(robe|hat)-(\d)/.exec(o.name);
      if (theirs && Number(theirs[2]) !== n) o.visible = false;
      if (o instanceof Mesh) {
        o.castShadow = true;
        o.frustumCulled = false; // (moved by her bones: her bounds don't follow)
      }
    });
    this.model.scale.setScalar(SIZES[n % SIZES.length]);
    scene.add(this.model);
    this.mixer = new AnimationMixer(this.model);
    for (const clip of animations) this.clips.set(clip.name, this.mixer.clipAction(clip));
    const dance = this.clips.get("Dance_Loop");
    if (dance) dance.time = STARTS[n % STARTS.length] * dance.getClip().duration;
    const rope = this.clips.get("OverhandThrow");
    rope?.setLoop(LoopOnce, 1);
    if (rope) rope.clampWhenFinished = true;
  }

  /** Whether what she's doing once (throwing her rope) is done. */
  get done() {
    return this.playing?.loop === LoopOnce && !this.playing.isRunning();
  }

  play(name: string) {
    const next = this.clips.get(name);
    if (!next || next === this.playing) return;
    const time = next.time;
    next.reset().play();
    if (name === "Dance_Loop") next.time = time; // (each in her own place in it)
    if (this.playing) next.crossFadeFrom(this.playing, BLEND, false);
    this.playing = next;
  }

  /** Turns her towards a direction, a little each frame: how far she's still to turn. */
  face(dx: number, dz: number, dt: number) {
    let turn = Math.atan2(dx, dz) - this.yaw;
    turn = Math.atan2(Math.sin(turn), Math.cos(turn));
    this.yaw += Math.sign(turn) * Math.min(Math.abs(turn), TURN * dt);
    this.model.rotation.y = this.yaw;
    return Math.abs(turn);
  }

  /** Runs her towards a spot: whether she's there. */
  run(x: number, z: number, dt: number) {
    const at = this.model.position;
    const dx = x - at.x;
    const dz = z - at.z;
    const left = Math.hypot(dx, dz);
    if (left < 0.1) return true;
    const off = this.face(dx, dz, dt);
    const step = off > 1 ? 0 : Math.min(left, RUN * dt);
    at.x += (dx / left) * step;
    at.z += (dz / left) * step;
    this.play("Jog_Fwd_Loop");
    return false;
  }

  update(dt: number) {
    this.mixer.update(dt);
  }
}

export class Witches {
  private witches: Witch[];
  private turned = 0; // radians the ring's turned, as they dance round it
  private spot = new Vector3();
  private readonly home: Ring; // their own ring, across the way west
  private caught = false;

  constructor(
    scene: Scene,
    model: Object3D,
    animations: AnimationClip[],
    private ring: Ring,
    /** Where each hides (behind a tree, from the clearing). */
    hides: { x: number; z: number }[],
    /** Where you look from, as they hide (they peek out that way). */
    private from: { x: number; z: number },
    private ground: Ground
  ) {
    this.home = ring;
    this.witches = hides.map((hide, n) => new Witch(scene, model, animations, n, hide));
    for (const witch of this.witches) this.hideNow(witch);
  }

  // Back behind her tree, crouching, peeking out at the clearing.
  private hideNow(witch: Witch) {
    witch.state = "hiding";
    witch.model.position.set(witch.hide.x, 0, witch.hide.z);
    witch.yaw = Math.atan2(this.from.x - witch.hide.x, this.from.z - witch.hide.z);
    witch.model.rotation.y = witch.yaw;
    witch.play("Crouch_Idle_Loop");
  }

  /** They catch you, standing here: they close round you. */
  catch(x: number, z: number) {
    this.caught = true;
    this.ring = { x, z, r: CLOSE };
    for (const witch of this.witches) witch.state = "coming";
  }

  /** You're free again (a new game): they're back in hiding, by their own ring. */
  free() {
    this.caught = false;
    this.ring = this.home;
    for (const witch of this.witches) this.hideNow(witch);
  }

  /** Where each one's face is now (standing up straight). */
  faces() {
    return this.witches.map((witch) =>
      witch.model.position.clone().setY(witch.model.position.y + FACE * witch.model.scale.y)
    );
  }

  /** Her place in the ring, as it's turned now. */
  private place(n: number) {
    const a = this.turned + (n / this.witches.length) * Math.PI * 2;
    const { x, z, r } = this.ring;
    return this.spot.set(x + Math.sin(a) * r, 0, z + Math.cos(a) * r);
  }

  /** Each frame: whether they're out (you're in their clearing). */
  update(dt: number, out: boolean) {
    // (Catching you, the ring's still till they've all thrown their ropes.)
    const tied = this.witches.every((witch) => witch.state === "dancing");
    this.turned += (this.caught ? (tied ? ROUND_YOU : 0) : SPIN) * dt;
    this.witches.forEach((witch, n) => {
      const at = witch.model.position;
      // (Catching you, they're out, whatever: each throws her rope as she gets to you.)
      if (!this.caught && out && witch.state !== "dancing") witch.state = "coming";
      if (!this.caught && !out && witch.state !== "hiding") witch.state = "going";
      if (witch.state === "coming") {
        const { x, z } = this.place(n);
        if (witch.run(x, z, dt)) witch.state = this.caught ? "tying" : "dancing";
      } else if (witch.state === "tying") {
        const { x, z } = this.place(n);
        at.x = x;
        at.z = z;
        witch.face(this.ring.x - x, this.ring.z - z, dt);
        witch.play("OverhandThrow");
        if (witch.done) witch.state = "dancing";
      } else if (witch.state === "dancing") {
        // Round the ring, facing in, dancing.
        const { x, z } = this.place(n);
        at.x = x;
        at.z = z;
        witch.face(this.ring.x - x, this.ring.z - z, dt);
        witch.play("Dance_Loop");
      } else if (witch.state === "going") {
        if (witch.run(witch.hide.x, witch.hide.z, dt)) this.hideNow(witch);
      }
      at.y = this.ground(at.x, at.z) ?? at.y;
      witch.update(dt);
    });
  }
}
