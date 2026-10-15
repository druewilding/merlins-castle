// Merlin (his model: art/blender/merlin.py), for now just walking about the
// grassy bank: he strolls to somewhere near, stands a while, and now and
// then casts a spell. Come near and he stops, and turns to you.
//
// His clips are the Universal Animation Library's, named as they are there.

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

import type { Ground } from "./player";

const TALL = 1.15; // times the size he's made: tall, his face above yours, under his hat's brim
const WALK = 0.975 * TALL; // metres a second: as far as his walk carries him (so his feet don't slide)
const TURN = 2.5; // radians a second, turning
const RANGE = 7; // metres from his spot he wanders, at most
const STROLL = [2.5, 6]; // metres to the next place he walks to, between these
const PAUSE = [2, 5]; // seconds he stands there, between these
const SPELL = 0.25; // how often, coming to a stop, he casts a spell
const CASTING = 2.5; // seconds he holds the spell
const NEAR = 3; // metres: this near, he stops and turns to you
const BLEND = 0.3; // seconds from one clip to the next

const between = ([a, b]: number[]) => a + Math.random() * (b - a);

export class Merlin {
  private mixer: AnimationMixer;
  private clips = new Map<string, AnimationAction>();
  private playing: AnimationAction | undefined;
  private state: "standing" | "walking" | "casting" = "standing";
  private wait = between(PAUSE); // seconds, until he's done standing (or casting)
  private target = new Vector3();
  private yaw = 0; // which way he faces (0 is +z)

  constructor(
    scene: Scene,
    private model: Object3D,
    clips: AnimationClip[],
    private home: { x: number; z: number },
    private ground: Ground,
    /** Whether he could walk here (not in a tree, or off the land). */
    private clear: (x: number, z: number) => boolean
  ) {
    model.traverse((o) => {
      if (o instanceof Mesh) {
        o.castShadow = true;
        o.frustumCulled = false; // (moved by his bones: his bounds don't follow)
      }
    });
    model.scale.setScalar(TALL);
    model.position.set(home.x, ground(home.x, home.z) ?? 0, home.z);
    scene.add(model);
    this.mixer = new AnimationMixer(model);
    for (const clip of clips) this.clips.set(clip.name, this.mixer.clipAction(clip));
    // (Raising his hands, and lowering them: each once, held at its end.)
    for (const name of ["Spell_Simple_Enter", "Spell_Simple_Exit"]) {
      const once = this.clips.get(name);
      once?.setLoop(LoopOnce, 1);
      if (once) once.clampWhenFinished = true;
    }
    this.play("Idle_Loop");
  }

  private play(name: string) {
    const next = this.clips.get(name);
    if (!next || next === this.playing) return;
    next.reset().play();
    if (this.playing) next.crossFadeFrom(this.playing, BLEND, false);
    this.playing = next;
  }

  /** Somewhere near to stroll to, that he can get to in a straight line. */
  private pick(): boolean {
    const at = this.model.position;
    for (let tries = 0; tries < 12; tries++) {
      const a = Math.random() * Math.PI * 2;
      const d = between(STROLL);
      const x = at.x + Math.sin(a) * d;
      const z = at.z + Math.cos(a) * d;
      if (Math.hypot(x - this.home.x, z - this.home.z) > RANGE) continue;
      let ok = true;
      for (let s = 0.5; s <= d && ok; s += 0.5) ok = this.clear(at.x + Math.sin(a) * s, at.z + Math.cos(a) * s);
      if (!ok) continue;
      this.target.set(x, 0, z);
      return true;
    }
    return false;
  }

  /** Turns him towards a direction, a little each frame: how far he's still to turn. */
  private face(dx: number, dz: number, dt: number) {
    const want = Math.atan2(dx, dz);
    let turn = want - this.yaw;
    turn = Math.atan2(Math.sin(turn), Math.cos(turn));
    this.yaw += Math.sign(turn) * Math.min(Math.abs(turn), TURN * dt);
    this.model.rotation.y = this.yaw;
    return Math.abs(turn);
  }

  update(dt: number, you: Vector3) {
    const at = this.model.position;
    const near = Math.hypot(you.x - at.x, you.z - at.z) < NEAR;
    if (near && this.state === "walking") {
      this.state = "standing";
      this.wait = between(PAUSE);
    }
    if (this.state === "walking") {
      const dx = this.target.x - at.x;
      const dz = this.target.z - at.z;
      const left = Math.hypot(dx, dz);
      const off = this.face(dx, dz, dt);
      // (Turning on the spot first, if he's far off his way.)
      const step = off > 0.8 ? 0 : Math.min(left, WALK * dt);
      at.x += Math.sin(this.yaw) * step;
      at.z += Math.cos(this.yaw) * step;
      this.play(step > 0 ? "Walk_Formal_Loop" : "Idle_Loop");
      if (left < 0.05) {
        this.state = Math.random() < SPELL ? "casting" : "standing";
        this.wait = this.state === "casting" ? CASTING : between(PAUSE);
      }
    } else {
      if (near) this.face(you.x - at.x, you.z - at.z, dt);
      this.wait -= dt;
      if (this.state === "casting") {
        this.play(this.wait > CASTING - 0.6 ? "Spell_Simple_Enter" : "Spell_Simple_Idle_Loop");
        if (this.wait <= 0) {
          this.play("Spell_Simple_Exit");
          this.state = "standing";
          this.wait = between(PAUSE);
        }
      } else {
        // (After a spell, its end plays out before he stands at ease.)
        const ending = this.playing === this.clips.get("Spell_Simple_Exit") && this.playing?.isRunning();
        if (!ending) this.play("Idle_Loop");
        if (this.wait <= 0 && !near && this.pick()) this.state = "walking";
      }
    }
    at.y = this.ground(at.x, at.z) ?? at.y;
    this.mixer.update(dt);
  }
}
