// The trolls in their cave (their model: art/blender/trolls.py), sitting on
// boulders round the north of it, two either side of the way north (land.py),
// one with its drum on the floor beside it. Come near, they lean forward with
// their hands out, asking you for a tune, and watch you as you go about.
// Played one on the harp, they get up, one after another, and dance (and
// let you by). Walking into the way before that, they cast a spell on you: a
// swirl of twinkles round your head (and the way stays shut).
//
// Their clips are the Universal Animation Libraries', named as they are there.

import {
  AdditiveBlending,
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  Color,
  LoopOnce,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  Vector3,
} from "three";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";

import { puff } from "./smoke";

/** One troll (land.json): where it sits [x, z] and its floor, which way it faces [x, z], and how big it is. */
export interface TrollSpot {
  at: number[];
  facing: number[];
  size: number;
}

/** The trolls (land.json): each where it sits, and which of them has the drum. */
export interface TrollsPlace {
  sitting: TrollSpot[];
  drum: number;
}

const ASK = 11; // metres: this near, they ask you for a tune
const FAR = 45; // metres: further off than this, they aren't drawn
const BLEND = 0.4; // seconds from one clip to the next
const UP = [0, 0.45, 0.2, 0.7]; // seconds after you play, each gets up
const STEP = 0.45; // metres (at its size) each steps forward off its boulder, getting up
const DRUM = [0.7, 0.2]; // the drum, beside its troll: how far to its side, and forward (at its size)
const TURN = 1.0; // radians their heads turn, at most, either way
const LIFT = 0.12; // radians their heads are lifted, looking up to you
const TWINKLES = 36;
const SPELL = 1.8; // seconds the spell's twinkles last
const GOLD = new Color("#ffe08a");
const GREEN = new Color("#b6ff8a");
const Y = new Vector3(0, 1, 0);
const X = new Vector3(1, 0, 0);

interface Troll {
  model: Object3D;
  head: Object3D | undefined;
  /** Its head, as its clip has it (before it's turned to you). */
  posed: Quaternion;
  mixer: AnimationMixer;
  clips: Map<string, AnimationAction>;
  playing: AnimationAction | undefined;
  yaw: number;
  /** Where it sits, and the step forward it takes off its boulder, getting up. */
  seat: Vector3;
  ahead: Vector3;
  /** Seconds till it gets up (dancing), and till it's up and can dance. */
  rising: number;
  standing: number;
  look: { turn: number; up: number };
}

interface Twinkle {
  sprite: Sprite;
  angle: number;
  out: number;
}

export class Trolls {
  private trolls: Troll[] = [];
  private twinkles: Twinkle[] = [];
  private spellAge = SPELL;
  private spellAt = new Vector3();
  /** Whether they're up and dancing (or getting up to), the harp played. */
  dancing = false;

  constructor(
    scene: Scene,
    source: Object3D,
    clips: AnimationClip[],
    place: TrollsPlace,
    private reducedMotion: boolean
  ) {
    const body = source.getObjectByName("troll")!;
    place.sitting.forEach(({ at: [x, z, floor], facing: [fx, fz], size }, k) => {
      const model = clone(body);
      model.traverse((o) => {
        if (o instanceof Mesh) {
          o.castShadow = true;
          o.frustumCulled = false; // (moved by their bones: their bounds don't follow)
        }
      });
      const yaw = Math.atan2(fx, fz);
      model.scale.setScalar(size);
      model.position.set(x, floor, z);
      model.rotation.y = yaw;
      scene.add(model);
      const mixer = new AnimationMixer(model);
      const actions = new Map(clips.map((clip) => [clip.name, mixer.clipAction(clip)]));
      const exit = actions.get("Sitting_Exit");
      exit?.setLoop(LoopOnce, 1);
      if (exit) exit.clampWhenFinished = true;
      const troll: Troll = {
        model,
        head: model.getObjectByName("Head"),
        posed: new Quaternion(),
        mixer,
        clips: actions,
        playing: undefined,
        yaw,
        seat: model.position.clone(),
        ahead: new Vector3(fx, 0, fz).multiplyScalar(STEP * size),
        rising: 0,
        standing: 0,
        look: { turn: 0, up: 0 },
      };
      this.play(troll, "Sitting_Idle_Loop", true);
      // (Not in step with each other.)
      mixer.update(k * 1.7);
      troll.posed.copy(troll.head?.quaternion ?? troll.posed);
      this.trolls.push(troll);
    });
    // The drum, on the floor beside the one with it.
    const drum = source.getObjectByName("troll-drum");
    const drummer = place.sitting[place.drum];
    if (drum && drummer) {
      const {
        at: [x, z, floor],
        facing: [fx, fz],
        size,
      } = drummer;
      drum.position.set(x + (fz * DRUM[0] + fx * DRUM[1]) * size, floor, z + (-fx * DRUM[0] + fz * DRUM[1]) * size);
      drum.rotation.y = Math.atan2(fx, fz);
      drum.traverse((o) => (o.castShadow = o.receiveShadow = true));
      scene.add(drum);
    }
    // The spell's twinkles: a pool of them, hidden till it's cast.
    const map = puff();
    for (let k = 0; k < TWINKLES; k++) {
      const sprite = new Sprite(
        new SpriteMaterial({
          map,
          color: k % 3 ? GOLD : GREEN,
          transparent: true,
          blending: AdditiveBlending,
          depthWrite: false,
        })
      );
      sprite.visible = false;
      scene.add(sprite);
      this.twinkles.push({ sprite, angle: (2 * Math.PI * k) / TWINKLES, out: 0.35 + Math.random() * 0.3 });
    }
  }

  private play(troll: Troll, name: string, now = false) {
    const next = troll.clips.get(name);
    if (!next || next === troll.playing) return;
    next.reset().play();
    if (troll.playing && !now) next.crossFadeFrom(troll.playing, BLEND, false);
    else troll.playing?.stop();
    troll.playing = next;
  }

  /** The harp played: up they get, one after another, and dance (or, loading, they're dancing). */
  dance(instantly: boolean) {
    if (this.dancing) return;
    this.dancing = true;
    this.trolls.forEach((troll, k) => {
      if (instantly || this.reducedMotion) {
        this.play(troll, "Dance_Loop", true);
        troll.mixer.update(k * 0.6);
        troll.rising = troll.standing = 0;
        this.stepTo(troll, 1);
      } else {
        troll.rising = UP[k % UP.length];
        troll.standing = 0;
      }
    });
  }

  /** Back on their boulders (the harp no longer played: you've gone). */
  sit() {
    if (!this.dancing) return;
    this.dancing = false;
    this.trolls.forEach((troll, k) => {
      troll.rising = troll.standing = 0;
      this.stepTo(troll, 0);
      this.play(troll, "Sitting_Idle_Loop", true);
      troll.mixer.update(k * 1.7);
    });
  }

  /** Walking into the way, unplayed to: a swirl of twinkles round your head. */
  spell(eye: Object3D) {
    this.spellAge = 0;
    eye.localToWorld(this.spellAt.set(0, 0, -1.3));
  }

  /** Each frame: your eyes, and whether you're in their cave. */
  update(dt: number, eye: Vector3, here: boolean) {
    for (const troll of this.trolls) {
      const far = troll.model.position.distanceTo(eye);
      troll.model.visible = here || far < FAR;
      if (!troll.model.visible) continue;
      if (this.dancing) this.rise(troll, dt);
      // Sitting, they ask you for a tune when you're near: their hands out.
      else this.play(troll, here && far < ASK ? "Sitting_Talking_Loop" : "Sitting_Idle_Loop");
      if (this.reducedMotion) continue;
      // (The mixer only sets a bone when its clip moves it: held still, the
      // head would keep the turn it was given last frame, and turn again.)
      troll.head?.quaternion.copy(troll.posed);
      troll.mixer.update(dt);
      troll.posed.copy(troll.head?.quaternion ?? troll.posed);
      if (!this.dancing) this.watch(troll, eye, here && far < ASK * 1.5, dt);
    }
    this.twinkle(dt);
  }

  /** Getting up, then dancing. */
  private rise(troll: Troll, dt: number) {
    const doing = troll.playing?.getClip().name;
    if (doing === "Sitting_Idle_Loop" || doing === "Sitting_Talking_Loop") {
      troll.rising -= dt;
      if (troll.rising <= 0) {
        this.play(troll, "Sitting_Exit");
        troll.standing = (troll.playing?.getClip().duration ?? 0) - BLEND;
      }
    } else if (doing === "Sitting_Exit") {
      troll.standing -= dt;
      // (Stepping forward off its boulder as it gets up.)
      const up = (troll.playing?.getClip().duration ?? 1) - BLEND;
      const t = Math.min(1, 1 - troll.standing / up);
      this.stepTo(troll, t * t * (3 - 2 * t));
      if (troll.standing <= 0) this.play(troll, "Dance_Loop");
    }
  }

  /** How far it's stepped forward off its boulder (0 to 1). */
  private stepTo(troll: Troll, step: number) {
    troll.model.position.copy(troll.seat).addScaledVector(troll.ahead, step);
  }

  /** Its head turned to you (as far as it can turn). */
  private watch(troll: Troll, eye: Vector3, watching: boolean, dt: number) {
    const { head, model, look } = troll;
    if (!head?.parent) return;
    model.updateMatrixWorld(true);
    const at = head.getWorldPosition(new Vector3());
    const dx = eye.x - at.x;
    const dz = eye.z - at.z;
    let turn = Math.atan2(dx, dz) - troll.yaw;
    turn = Math.atan2(Math.sin(turn), Math.cos(turn));
    const wants = {
      turn: watching ? Math.max(-TURN, Math.min(TURN, turn)) : 0,
      up: watching ? LIFT + Math.max(-0.3, Math.min(0.35, Math.atan2(eye.y - at.y, Math.hypot(dx, dz)))) : 0,
    };
    const ease = Math.min(1, dt * 3);
    look.turn += (wants.turn - look.turn) * ease;
    look.up += (wants.up - look.up) * ease;
    // (Turned in the troll's own frame, on top of what its clip does: round,
    // then up, and back into the head's parent's.)
    const facing = model.getWorldQuaternion(new Quaternion());
    const turned = new Quaternion()
      .setFromAxisAngle(Y, look.turn)
      .multiply(new Quaternion().setFromAxisAngle(X, -look.up));
    const world = head.getWorldQuaternion(new Quaternion());
    const wanted = facing.clone().multiply(turned).multiply(facing.clone().invert()).multiply(world);
    head.quaternion.copy(head.parent.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
  }

  /** The spell's twinkles: round and round in front of you, rising, and fading. */
  private twinkle(dt: number) {
    const live = this.spellAge < SPELL;
    this.spellAge += dt;
    const t = Math.min(1, this.spellAge / SPELL);
    for (const [k, twinkle] of this.twinkles.entries()) {
      const { sprite } = twinkle;
      sprite.visible = live;
      if (!live) continue;
      // (With motion reduced, they hang still round you, and fade.)
      const spin = this.reducedMotion ? 0 : this.spellAge * 3;
      const a = twinkle.angle + spin;
      const r = twinkle.out * (0.6 + 0.4 * Math.sin(t * Math.PI));
      const up = (this.reducedMotion ? 0.5 : t) * 0.5 + 0.15 * Math.sin(k * 1.7);
      sprite.position.set(
        this.spellAt.x + Math.cos(a) * r,
        this.spellAt.y - 0.2 + up,
        this.spellAt.z + Math.sin(a) * r
      );
      const flicker = this.reducedMotion ? 1 : 0.6 + 0.4 * Math.sin(this.spellAge * 18 + k * 2.3);
      sprite.material.opacity = Math.sin(Math.PI * t) * flicker;
      sprite.scale.setScalar(0.035 + 0.025 * Math.sin(Math.PI * t));
    }
  }
}
