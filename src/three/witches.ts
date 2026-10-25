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
// Use the broom and they stop dancing and fly off "to the moon", each on a
// broom of her own, up and away over the trees. Once it's no longer in use
// there (you've gone on), each is back in hiding the moment you're not
// looking (at her, flying still, or where she hides), ready to come out and
// dance again: even if you turn straight back.
//
// Walk into them (without the broom) and they catch you: they run at you
// and close round you, and, you down on the ground, dance round you
// (caught.ts plays it, from where you are).
//
// Their clips are the Universal Animation Libraries', named as they are there.

import {
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  Box3,
  type Camera,
  Frustum,
  Group,
  LoopOnce,
  type Material,
  Matrix4,
  Mesh,
  type Object3D,
  type Scene,
  Sphere,
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
// Flying off: each one a little after the one before (seconds), crouching
// to spring up; then how fast she rises and goes (metres a second, and more
// each second), and when she fades away, from and to (seconds from springing
// up: then she's gone).
const AFTER = 0.35;
const SPRING = 0.5;
const RISE = [1.2, 2.2];
const AWAY = [2.5, 3.5];
const FADING = [3.5, 7.5];
// Her broom, under her as she sits (in her model's metres: its middle, back
// from her hips, and how far up).
const SEAT = [0, -0.12, 0.5];
const HURRY = 0.7; // seconds she takes to fade, the broom no longer in use while you can still see her
const ROUND_YOU = 1.1; // radians a second, the ring turning as they dance round you, caught

export interface Ring {
  x: number;
  z: number;
  r: number;
}

type State = "hiding" | "coming" | "dancing" | "going" | "flying" | "flown";

class Witch {
  readonly model: Object3D;
  private mixer: AnimationMixer;
  private clips = new Map<string, AnimationAction>();
  private playing: AnimationAction | undefined;
  readonly broom = new Group();
  private materials: Material[] = []; // her own (so she fades alone)
  private fading = false;
  state: State = "hiding";
  yaw = 0; // which way she faces (0 is +z)
  // Flying off: how long since she was told to, which way, and how much of
  // her there's still to see at most (less and less, hurrying back).
  flight = { t: 0, heading: 0, swing: 0, most: 1 };

  constructor(
    scene: Scene,
    source: Object3D,
    animations: AnimationClip[],
    n: number,
    readonly hide: { x: number; z: number },
    broom: Object3D
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
    // Her broom: lying along under her, its twigs behind.
    const stick = broom.clone();
    stick.position.set(0, 0, 0);
    stick.rotation.set(0, Math.PI, 0); // (made with its twigs ahead)
    stick.traverse((o) => (o.castShadow = true));
    const middle = new Box3().setFromObject(stick).getCenter(new Vector3());
    stick.position.sub(middle);
    this.broom.add(stick);
    this.broom.position.set(SEAT[0], SEAT[2], SEAT[1]);
    this.broom.scale.setScalar(1 / this.model.scale.x);
    this.broom.visible = false;
    this.model.add(this.broom);
    this.model.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      const own = (m: Material) => {
        const copy = m.clone();
        // (See-through from the start, at no cost while she's all there:
        // turning it on as she fades would remake her shaders then, and the
        // scene would jolt.)
        copy.transparent = true;
        this.materials.push(copy);
        return copy;
      };
      o.material = Array.isArray(o.material) ? o.material.map(own) : own(o.material);
    });
    scene.add(this.model);
    this.mixer = new AnimationMixer(this.model);
    for (const clip of animations) this.clips.set(clip.name, this.mixer.clipAction(clip));
    const dance = this.clips.get("Dance_Loop");
    if (dance) dance.time = STARTS[n % STARTS.length] * dance.getClip().duration;
    const jump = this.clips.get("Jump_Start"); // (springing up onto her broom, once)
    jump?.setLoop(LoopOnce, 1);
    if (jump) jump.clampWhenFinished = true;
  }

  /** How much of her there is to see (1: all of her; 0: she's faded away). */
  fade(opacity: number) {
    const fading = opacity < 1;
    for (const m of this.materials) m.opacity = opacity;
    if (fading === this.fading) return;
    this.fading = fading;
    for (const m of this.materials) m.depthWrite = !fading;
    // (No shadow, fading: a shadow doesn't fade.)
    this.model.traverse((o) => {
      if (o instanceof Mesh) o.castShadow = !fading;
    });
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
  private frustum = new Frustum();
  private matrix = new Matrix4();
  private eye = new Vector3();

  constructor(
    scene: Scene,
    model: Object3D,
    animations: AnimationClip[],
    private ring: Ring,
    /** Where each hides (behind a tree, from the clearing). */
    hides: { x: number; z: number }[],
    /** Where you look from, as they hide (they peek out that way). */
    private from: { x: number; z: number },
    private ground: Ground,
    broom: Object3D,
    private reducedMotion: boolean
  ) {
    this.home = ring;
    this.witches = hides.map((hide, n) => new Witch(scene, model, animations, n, hide, broom));
    for (const witch of this.witches) this.hideNow(witch);
  }

  // Back behind her tree, crouching, peeking out at the clearing.
  private hideNow(witch: Witch) {
    witch.state = "hiding";
    witch.model.visible = true;
    witch.fade(1);
    witch.broom.visible = false;
    witch.model.position.set(witch.hide.x, 0, witch.hide.z);
    witch.yaw = Math.atan2(this.from.x - witch.hide.x, this.from.z - witch.hide.z);
    witch.model.rotation.y = witch.yaw;
    witch.play("Crouch_Idle_Loop");
  }

  /** You've used the broom here (you, where you are): they fly off, away from you. */
  flyOff(you: Vector3) {
    if (this.reducedMotion) return this.away();
    this.witches.forEach((witch, n) => {
      if (witch.state === "flying" || witch.state === "flown") return;
      const { x, z } = witch.model.position;
      const heading = Math.atan2(x - you.x, z - you.z) + (n - 1) * 0.35;
      witch.flight = { t: 0, heading, swing: n * 2.1, most: 1 };
      witch.state = "flying";
    });
  }

  /** Gone (a game loaded with the broom in use here). */
  away() {
    for (const witch of this.witches) {
      witch.state = "flown";
      witch.model.visible = false;
    }
  }

  /** They catch you, standing here: they close round you. */
  catch(x: number, z: number) {
    this.caught = true;
    this.ring = { x, z, r: CLOSE };
    for (const witch of this.witches) {
      if (witch.state === "flying" || witch.state === "flown") this.hideNow(witch); // (out from behind her tree)
      witch.state = "coming";
    }
  }

  /** You're free again (a new game): they're back in hiding, by their own ring. */
  free() {
    this.caught = false;
    this.ring = this.home;
    for (const witch of this.witches) this.hideNow(witch);
  }

  /** Whether, catching you, they've all closed round you. */
  get round() {
    return this.caught && this.witches.every((witch) => witch.state === "dancing");
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

  /**
   * Each frame: whether they're out (you're in their clearing); and, flown
   * off, whether they may come back (the broom's no longer in use there): they
   * do when you're not looking (camera: where you're looking from).
   */
  update(dt: number, out: boolean, camera: Camera, back: boolean) {
    if (back) this.seeing(camera);
    for (const witch of this.witches) {
      const away = witch.state === "flying" || witch.state === "flown";
      if (!back || !away) continue;
      // (Flying still, where you can see her, she fades away quickly first.
      // Back in the clearing, they're back however you're looking at her
      // tree: they'd be out from behind it before you could see anyway.)
      const { x, y, z } = witch.model.position;
      const flying = witch.state === "flying" && this.seen({ x, y: y + 0.9, z }, 1.5);
      if (flying) {
        witch.flight.most -= dt / HURRY;
        continue;
      }
      // (Out of sight, she's gone; and back behind her tree when that is too.)
      witch.state = "flown";
      witch.model.visible = false;
      if (out || !this.seen(witch.hide, 1.2)) this.hideNow(witch);
    }
    // (Catching you, the ring's still till they've all closed round you.)
    const round = this.witches.every((witch) => witch.state === "dancing");
    this.turned += (this.caught ? (round ? ROUND_YOU : 0) : SPIN) * dt;
    this.witches.forEach((witch, n) => {
      const at = witch.model.position;
      if (witch.state === "flown") return;
      // (Catching you, they're out, whatever: each dances as she gets to you.)
      const free = !this.caught && witch.state !== "flying";
      if (free && out && witch.state !== "dancing") witch.state = "coming";
      if (free && !out && witch.state !== "hiding") witch.state = "going";
      if (witch.state === "flying") return this.fly(witch, n, dt);
      if (witch.state === "coming") {
        const { x, z } = this.place(n);
        if (witch.run(x, z, dt)) witch.state = "dancing";
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

  // Flying off: stopping, then, each in turn, springing up onto her broom,
  // and up and away, swaying from side to side, faster and faster.
  private fly(witch: Witch, n: number, dt: number) {
    const flight = witch.flight;
    flight.t += dt;
    const s = flight.t - n * AFTER - SPRING; // (since she sprang up)
    // (Fading as she goes, or hurrying back.)
    const left = Math.min(1, Math.max(0, 1 - (s - FADING[0]) / (FADING[1] - FADING[0])));
    const opacity = Math.max(0, Math.min(left * left * (3 - 2 * left), flight.most));
    witch.fade(opacity);
    if (opacity <= 0) {
      witch.state = "flown";
      witch.model.visible = false;
      return;
    }
    if (s < -SPRING) witch.play("Idle_Loop");
    else if (s < 0) witch.play("Jump_Start");
    else {
      witch.broom.visible = true;
      witch.play("Sitting_Idle_Loop");
      const heading = flight.heading + 0.3 * Math.sin(s * 1.2 + flight.swing);
      witch.yaw = heading;
      witch.model.rotation.y = heading;
      const at = witch.model.position;
      const away = (AWAY[0] + AWAY[1] * s) * dt;
      at.x += Math.sin(heading) * away;
      at.z += Math.cos(heading) * away;
      at.y += (RISE[0] + RISE[1] * s) * dt + 0.25 * Math.cos(s * 3 + flight.swing) * dt;
    }
    witch.update(dt);
  }

  // What you can see, this frame.
  private seeing(camera: Camera) {
    camera.updateMatrixWorld();
    this.matrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.matrix);
    this.eye.copy(camera.position);
  }

  /** Whether you could see a spot (her, or where she hides) from where you are (roughly: whether it's in view at all). */
  private seen(at: { x: number; y?: number; z: number }, r: number) {
    const y = at.y ?? (this.ground(at.x, at.z) ?? 0) + 0.8;
    const near = Math.hypot(this.eye.x - at.x, this.eye.z - at.z) < 5;
    return near || this.frustum.intersectsSphere(new Sphere(new Vector3(at.x, y, at.z), r));
  }
}
