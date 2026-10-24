// The trolls in their cave (their model: art/blender/trolls.py), sitting on
// boulders round the north of it, two either side of the way north (land.py),
// one with its drum on the floor beside it, each its own look. Come near,
// they take turns to lean forward with their hands out, asking you for a
// tune, and watch you as you go about.
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
  type Material,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  SkinnedMesh,
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

const ASK = 11; // metres: this near, they ask you for a tune...
const TURNS = [3.5, 6.5]; // ...one at a time, each for between these many seconds
const FAR = 45; // metres: further off than this, they aren't drawn
const BLEND = 0.4; // seconds from one clip to the next
const UP = [0, 0.45, 0.2, 0.7]; // seconds after you play, each gets up
const STEP = 0.45; // metres (at its size) each steps forward off its boulder, getting up
const DRUM = [0.7, 0.2]; // the drum, beside its troll: how far to its side, and forward (at its size)
const TURN = 1.0; // radians their heads turn, at most, either way
const GLANCE = [1.5, 4]; // seconds between their glances, now to one side, now back to you
const BLINK = [3, 7]; // seconds between their blinks (and now and then, straight after, another)
const SHUT = 0.15; // seconds a blink takes, shutting and opening
const HANDS = 1.65; // times bigger their hands are (by their bones: so their fingers bend where their joints are)
// Radians their forearms are lifted at the elbow, sitting, and more for the
// fatter ones: their hands are bigger, and their thighs and bellies, than the
// clips' (made for the kit's hero), so they'd rest in their laps, not on them.
const LAP = [0.14, 0.08];
// And radians their upper arms are swung out from their shoulders, dancing
// (more for the fatter ones), so their fists clear their bellies.
const SPREAD = [0.1, 0.07];
// Each its own look (art/blender/trolls.py makes the pieces, and previews
// these): its hair (troll-hair-0..2), a beard or not, its shape (its body's
// shape keys, 0 to 1), how big its head is, and its skin's and its moss's tints.
const LOOKS = [
  { hair: 0, beard: false, keys: { belly: 0.2 }, head: 1.0, skin: "#ffffff", moss: "#ffffff" },
  { hair: 1, beard: true, keys: { belly: 1, fat: 1, "big-ears": 0.6 }, head: 1.08, skin: "#c9cbc4", moss: "#d8cf8a" },
  { hair: 2, beard: false, keys: { "long-nose": 1 }, head: 0.94, skin: "#c8e29a", moss: "#8fa86e" },
  {
    hair: 1,
    beard: false,
    keys: { belly: 0.6, fat: 1, "big-ears": 1, "long-nose": 0.4 },
    head: 1.04,
    skin: "#ffc4a4",
    moss: "#e8b866",
  },
];
const TWINKLES = 36;
const SPELL = 1.8; // seconds the spell's twinkles last
const GOLD = new Color("#ffe08a");
const GREEN = new Color("#b6ff8a");
const Y = new Vector3(0, 1, 0);

interface Troll {
  model: Object3D;
  head: Object3D | undefined;
  hands: Object3D[];
  /** Its upper arms, forearms and hands, its left then its right; how far its forearms are lifted sitting, and
   * its upper arms swung out dancing (and how far they are now). */
  arms: [Object3D, Object3D, Object3D][];
  /** Its arms as its clip has them (before they're lifted, or swung out). */
  armsPosed: Quaternion[];
  lapLift: number;
  lap: number;
  spreadOut: number;
  spread: number;
  /** How big its head is (on top of what its clip has it). */
  headSize: number;
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
  /** Which way its face looks, in its head's own frame. */
  face: Vector3;
  look: { turn: number; up: number };
  /** A glance aside (radians round, and up), and for how much longer. */
  glance: { turn: number; up: number; for: number };
  /** Its eyelids (its body's shape key "blink", 0 open to 1 shut): seconds till it blinks, and how far into one it is. */
  lids: { shut: (amount: number) => void; wait: number; at: number };
}

interface Twinkle {
  sprite: Sprite;
  angle: number;
  out: number;
}

export class Trolls {
  private trolls: Troll[] = [];
  private twinkles: Twinkle[] = [];
  private asker = 0; // (which of them is asking you for a tune)
  private asking = 0; // (and for how much longer)
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
      // (Which way its face looks, in its head's own frame: as it's made, in
      // its bind pose, its face looks ahead, +z.)
      model.traverse((o) => {
        if (o instanceof SkinnedMesh) o.skeleton.pose();
      });
      model.updateMatrixWorld(true);
      const face = new Vector3(0, 0, 1).applyQuaternion(
        model.getObjectByName("Head")?.getWorldQuaternion(new Quaternion()).invert() ?? new Quaternion()
      );
      const look = LOOKS[k % LOOKS.length];
      const tinted = (material: Material, tint: string) => {
        const own = material.clone() as Material & { color: Color };
        own.color.set(tint);
        return own;
      };
      let shut = (_amount: number) => {};
      model.traverse((o) => {
        if (!(o instanceof Mesh)) return;
        o.castShadow = true;
        o.frustumCulled = false; // (moved by their bones: their bounds don't follow)
        // Its own hair (or a beard), shape, skin and moss.
        if (o.name.startsWith("troll-hair")) o.visible = o.name === `troll-hair-${look.hair}`;
        if (o.name === "troll-beard") o.visible = look.beard;
        for (const [key, amount] of Object.entries(look.keys)) {
          const at = o.morphTargetDictionary?.[key];
          if (at !== undefined && o.morphTargetInfluences) o.morphTargetInfluences[at] = amount;
        }
        if (o.name.startsWith("troll-")) o.material = tinted(o.material as Material, look.moss);
        else if (o.name.startsWith("SuperHero")) o.material = tinted(o.material as Material, look.skin);
        const blink = o.morphTargetDictionary?.blink;
        const influences = o.morphTargetInfluences;
        if (blink !== undefined && influences) shut = (amount) => (influences[blink] = amount);
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
        hands: ["hand_l", "hand_r"].flatMap((name) => model.getObjectByName(name) ?? []),
        arms: ["l", "r"].flatMap((side) => {
          const [upper, fore, hand] = ["upperarm", "lowerarm", "hand"].map((bone) =>
            model.getObjectByName(`${bone}_${side}`)
          );
          return upper && fore && hand ? [[upper, fore, hand] as [Object3D, Object3D, Object3D]] : [];
        }),
        armsPosed: [0, 1, 2, 3, 4, 5].map(() => new Quaternion()),
        lapLift: LAP[0] + ("fat" in look.keys ? LAP[1] : 0),
        lap: LAP[0] + ("fat" in look.keys ? LAP[1] : 0),
        spreadOut: SPREAD[0] + ("fat" in look.keys ? SPREAD[1] : 0),
        spread: 0,
        headSize: look.head,
        posed: new Quaternion(),
        mixer,
        clips: actions,
        playing: undefined,
        yaw,
        seat: model.position.clone(),
        ahead: new Vector3(fx, 0, fz).multiplyScalar(STEP * size),
        rising: 0,
        standing: 0,
        face,
        look: { turn: 0, up: 0 },
        glance: { turn: 0, up: 0, for: 0 },
        lids: { shut, wait: BLINK[0] * Math.random(), at: -1 },
      };
      this.play(troll, "Sitting_Idle_Loop", true);
      // (Not in step with each other.)
      mixer.update(k * 1.7);
      this.shape(troll);
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

  /** Its hands and head as big as they are (each frame, after its clip: its clips set every bone's size). */
  private shape(troll: Troll) {
    for (const hand of troll.hands) hand.scale.setScalar(HANDS);
    troll.head?.scale.setScalar(troll.headSize);
    // (Its arms as its clip has them, kept to put back before
    // the next frame of it: the mixer only sets a bone when its clip moves it,
    // and they'd be lifted again on top of the last lift.)
    troll.arms.flat().forEach((bone, k) => troll.armsPosed[k].copy(bone.quaternion));
    // Its upper arms swung out from its shoulders (towards its left, and its right).
    if (troll.spread > 0.001) {
      const facing = troll.model.getWorldQuaternion(new Quaternion());
      troll.arms.forEach(([upper, fore], side) => {
        const shoulder = upper.getWorldPosition(new Vector3());
        const along = fore.getWorldPosition(new Vector3()).sub(shoulder).normalize();
        const out = new Vector3(side ? -1 : 1, 0, 0).applyQuaternion(facing);
        const across = along.cross(out).normalize();
        const wanted = new Quaternion()
          .setFromAxisAngle(across, troll.spread)
          .multiply(upper.getWorldQuaternion(new Quaternion()));
        upper.quaternion.copy(upper.parent!.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
      });
    }
    if (troll.lap < 0.001) return;
    // Its forearms lifted at the elbow (turned up, towards straight up), and
    // its hands turned back as much, so they still lie flat on its lap.
    for (const [, fore, hand] of troll.arms) {
      const elbow = fore.getWorldPosition(new Vector3());
      const along = hand.getWorldPosition(new Vector3()).sub(elbow).normalize();
      const across = along.cross(Y).normalize();
      for (const [bone, angle] of [
        [fore, troll.lap],
        [hand, -troll.lap],
      ] as const) {
        const wanted = new Quaternion()
          .setFromAxisAngle(across, angle)
          .multiply(bone.getWorldQuaternion(new Quaternion()));
        bone.quaternion.copy(bone.parent!.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
      }
    }
  }

  /** Its arms put back as its clip had them (before the next frame of it). */
  private unshape(troll: Troll) {
    troll.arms.flat().forEach((bone, k) => bone.quaternion.copy(troll.armsPosed[k]));
  }

  /** The harp played: up they get, one after another, and dance (or, loading, they're dancing). */
  dance(instantly: boolean) {
    if (this.dancing) return;
    this.dancing = true;
    this.trolls.forEach((troll, k) => {
      if (instantly || this.reducedMotion) {
        this.play(troll, "Dance_Loop", true);
        this.unshape(troll);
        troll.mixer.update(k * 0.6);
        troll.lap = 0;
        troll.spread = troll.spreadOut;
        this.shape(troll);
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
      this.unshape(troll);
      troll.mixer.update(k * 1.7);
      troll.lap = troll.lapLift;
      troll.spread = 0;
      this.shape(troll);
    });
  }

  /** Walking into the way, unplayed to: a swirl of twinkles round your head. */
  spell(eye: Object3D) {
    this.spellAge = 0;
    eye.localToWorld(this.spellAt.set(0, 0, -1.3));
  }

  /** Each frame: your eyes, and whether you're in their cave. */
  update(dt: number, eye: Vector3, here: boolean) {
    // (Taking turns to ask.)
    this.asking -= dt;
    if (this.asking <= 0) {
      this.asker = (this.asker + 1 + Math.floor(Math.random() * (this.trolls.length - 1))) % this.trolls.length;
      this.asking = TURNS[0] + Math.random() * (TURNS[1] - TURNS[0]);
    }
    for (const [k, troll] of this.trolls.entries()) {
      const far = troll.model.position.distanceTo(eye);
      troll.model.visible = here || far < FAR;
      if (!troll.model.visible) continue;
      if (this.dancing) this.rise(troll, dt);
      // Sitting, one of them asks you for a tune when you're near: its hands out.
      else this.play(troll, here && far < ASK && k === this.asker ? "Sitting_Talking_Loop" : "Sitting_Idle_Loop");
      if (this.reducedMotion) continue;
      // (Its forearms lifted while it sits, and let down again, getting up.)
      const sitting =
        troll.playing?.getClip().name !== "Sitting_Exit" && troll.playing?.getClip().name !== "Dance_Loop";
      troll.lap += ((sitting ? troll.lapLift : 0) - troll.lap) * Math.min(1, dt * 4);
      // (And its upper arms swung out while it dances.)
      const dancing = troll.playing?.getClip().name === "Dance_Loop";
      troll.spread += ((dancing ? troll.spreadOut : 0) - troll.spread) * Math.min(1, dt * 4);
      // (The mixer only sets a bone when its clip moves it: held still, the
      // head would keep the turn it was given last frame, and turn again.)
      troll.head?.quaternion.copy(troll.posed);
      this.unshape(troll);
      troll.mixer.update(dt);
      this.shape(troll);
      troll.posed.copy(troll.head?.quaternion ?? troll.posed);
      if (!this.dancing) this.watch(troll, eye, here && far < ASK * 1.5, dt);
      this.blink(troll, dt);
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

  /** Now and then, a blink (and sometimes another, straight after). */
  private blink(troll: Troll, dt: number) {
    const { lids } = troll;
    if (lids.at < 0) {
      lids.wait -= dt;
      if (lids.wait > 0) return;
      lids.at = 0;
    }
    lids.at += dt;
    lids.shut(Math.sin(Math.PI * Math.min(1, lids.at / SHUT)));
    if (lids.at < SHUT) return;
    lids.shut(0);
    lids.at = -1;
    lids.wait = Math.random() < 0.2 ? 0.12 : BLINK[0] + Math.random() * (BLINK[1] - BLINK[0]);
  }

  /** Its head turned to you (as far as it can turn), now and then glancing aside. */
  private watch(troll: Troll, eye: Vector3, watching: boolean, dt: number) {
    const { head, model, look, glance } = troll;
    if (!head?.parent) return;
    glance.for -= dt;
    if (glance.for <= 0) {
      const aside = Math.random() < 0.45;
      glance.turn = aside ? Math.sign(Math.random() - 0.5) * (0.25 + Math.random() * 0.3) : 0;
      glance.up = aside ? (Math.random() - 0.5) * 0.2 : 0;
      glance.for = GLANCE[0] + Math.random() * (GLANCE[1] - GLANCE[0]);
    }
    model.updateMatrixWorld(true);
    // Where its face looks, as its clip has it; and how far round and up it
    // turns from there to look at you (as far round as its neck goes), give
    // or take a glance. (Not near, as its clip has it.)
    const at = head.getWorldPosition(new Vector3());
    const world = head.getWorldQuaternion(new Quaternion());
    const facing = troll.face.clone().applyQuaternion(world);
    const to = eye.clone().sub(at);
    const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
    const round = troll.yaw + Math.max(-TURN, Math.min(TURN, wrap(Math.atan2(to.x, to.z) - troll.yaw + glance.turn)));
    const up = Math.max(-0.4, Math.min(0.5, Math.atan2(to.y, Math.hypot(to.x, to.z)) + glance.up));
    const wants = watching
      ? { turn: wrap(round - Math.atan2(facing.x, facing.z)), up: up - Math.asin(Math.max(-1, Math.min(1, facing.y))) }
      : { turn: 0, up: 0 };
    const ease = Math.min(1, dt * 3);
    look.turn += (wants.turn - look.turn) * ease;
    look.up += (wants.up - look.up) * ease;
    // (On top of what its clip does: up, about its face's own side, then
    // round; and back into the head's parent's frame.)
    const side = facing.clone().cross(Y).normalize();
    const wanted = new Quaternion()
      .setFromAxisAngle(Y, look.turn)
      .multiply(new Quaternion().setFromAxisAngle(side, look.up))
      .multiply(world);
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
