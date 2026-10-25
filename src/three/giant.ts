// The giant in his cave (his model: art/blender/giant.py), crouching in front
// of the way west (land.py), as in its picture, watching you as you go about,
// hungry. Walking into the way, he shakes his head at you.
// Given a cake (thrown from your hand), he catches it, stands up, eats it in
// three big bites, nods, and goes and sits on his boulder beside the way (and
// lets you by); and once you've gone, he's back where he was.
//
// His clips are the Universal Animation Libraries', named as they are there.
// None of them eats: his hand's lifted to his mouth here, on top of his
// standing clip (reach).

import {
  type AnimationAction,
  type AnimationClip,
  AnimationMixer,
  Group,
  LoopOnce,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  SkinnedMesh,
  Vector3,
} from "three";

/** The giant (land.json): where he crouches [x, z] and his floor, where he sits [x, z] and which way he faces there [x, z], and how big he is. */
export interface GiantPlace {
  crouching: number[];
  sitting: number[];
  facing: number[];
  size: number;
}

const WATCH = 16; // metres: this near, he watches you
const FAR = 45; // metres: further off than this, he isn't drawn
const BLEND = 0.5; // seconds from one clip to the next
const FLIGHT = [0.6, 1.2]; // seconds the cake takes to reach his hand, at least and at most
const BITES = 3; // he eats it in this many bites...
const BITE = [0.5, 0.35, 0.55]; // ...each: seconds lifting it to his mouth, at it (a bite, halfway), and lowering it
const MOUTH = [0.12, -0.03]; // where his mouth is from his head's bone: forward, and up (at the model's size)
const WALK = 1.15; // metres a second he walks (at the model's size: his strides are as big as he is)
const TURNING = 2; // radians a second he turns
const TURN = 0.9; // radians his head turns, at most, either way
const SHAKE = [1.4, 13, 0.35]; // seconds he shakes his head, how fast (radians a second), and how far (radians)
const GLANCE = [1.5, 4]; // seconds between his glances, now to one side, now back to you
const BLINK = [2.5, 6]; // seconds between his blinks
const SHUT = 0.15; // seconds a blink takes
const HANDS = 1.3; // times bigger his hands are (by their bones: so his fingers bend where their joints are)
const FINGERS = 0.85; // and how long their middle and end joints are, pulled in towards his knuckles
const CAKE = 2.0; // the cake in his hand, times the one you carry (growing as it flies to him: a cake for a giant)
const UP = new Vector3(0, 1, 0);

type Doing = "waiting" | "catching" | "eating" | "nodding" | "walking" | "turning" | "sitting down" | "sitting";

export class Giant {
  private model: Object3D;
  private head: Object3D | undefined;
  private hand: Object3D | undefined;
  private knuckle: Object3D | undefined;
  /** His left arm (upper, fore, hand), which eats; and as his clip has it (before it's lifted). */
  private arm: Object3D[];
  private armPosed: Quaternion[] = [new Quaternion(), new Quaternion()];
  private hands: Object3D[];
  private fingers: [Object3D, Vector3][];
  private mixer: AnimationMixer;
  private clips: Map<string, AnimationAction>;
  private playing: AnimationAction | undefined;
  private doing: Doing = "waiting";
  private time = 0; // seconds into what he's doing
  private crouch: Vector3;
  private seat: Vector3;
  private yaw: number;
  private crouchYaw: number;
  private seatYaw: number;
  /** Which way his face looks, in his head's own frame. */
  private face: Vector3;
  /** His head, as his clip has it (before it's turned to you). */
  private posed = new Quaternion();
  private look = { turn: 0, up: 0 };
  private glance = { turn: 0, up: 0, for: 0 };
  private shaking = SHAKE[0];
  private shut: (amount: number) => void = () => {};
  private lids = { wait: BLINK[0], at: -1 };
  private cake = new Group();
  private from = new Vector3();
  private bitten = 0;

  constructor(
    scene: Scene,
    source: Object3D,
    clips: AnimationClip[],
    cakeModel: Object3D,
    place: GiantPlace,
    private reducedMotion: boolean,
    private munch: () => void
  ) {
    const {
      crouching: [x, z, floor],
      sitting: [sx, sz],
      facing: [fx, fz],
      size,
    } = place;
    this.model = source.getObjectByName("giant")!;
    // (Which way his face looks, in his head's own frame: as he's made, in
    // his bind pose, his face looks ahead, +z.)
    this.model.traverse((o) => {
      if (o instanceof SkinnedMesh) o.skeleton.pose();
    });
    this.model.updateMatrixWorld(true);
    this.face = new Vector3(0, 0, 1).applyQuaternion(
      this.model.getObjectByName("Head")?.getWorldQuaternion(new Quaternion()).invert() ?? new Quaternion()
    );
    this.model.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      o.castShadow = true;
      o.frustumCulled = false; // (moved by his bones: his bounds don't follow)
      const blink = o.morphTargetDictionary?.blink;
      const influences = o.morphTargetInfluences;
      if (blink !== undefined && influences) this.shut = (amount) => (influences[blink] = amount);
    });
    this.crouch = new Vector3(x, floor, z);
    this.seat = new Vector3(sx, floor, sz);
    this.crouchYaw = Math.PI / 2; // (facing east, into his cave, across the way west)
    this.seatYaw = Math.atan2(fx, fz);
    this.yaw = this.crouchYaw;
    this.model.scale.setScalar(size);
    scene.add(this.model);
    this.head = this.model.getObjectByName("Head");
    this.hand = this.model.getObjectByName("hand_l");
    this.knuckle = this.model.getObjectByName("middle_01_l");
    this.arm = ["upperarm_l", "lowerarm_l", "hand_l"].flatMap((name) => this.model.getObjectByName(name) ?? []);
    this.hands = ["hand_l", "hand_r"].flatMap((name) => this.model.getObjectByName(name) ?? []);
    this.fingers = ["thumb", "index", "middle", "ring", "pinky"].flatMap((finger) =>
      ["02", "03", "04_leaf"].flatMap((joint) =>
        ["l", "r"].flatMap((side) => {
          const bone = this.model.getObjectByName(`${finger}_${joint}_${side}`);
          return bone ? [[bone, bone.position.clone().multiplyScalar(FINGERS)] as [Object3D, Vector3]] : [];
        })
      )
    );
    this.mixer = new AnimationMixer(this.model);
    this.clips = new Map(clips.map((clip) => [clip.name, this.mixer.clipAction(clip)]));
    for (const name of ["Yes", "Sitting_Enter"]) {
      const once = this.clips.get(name);
      once?.setLoop(LoopOnce, 1);
      if (once) once.clampWhenFinished = true;
    }
    // The cake he's given: a copy of the one you carry, its middle at its middle.
    const copy = cakeModel.clone();
    copy.position.set(0, -0.1, 0);
    copy.traverse((node) => (node.castShadow = true));
    this.cake.add(copy);
    this.cake.visible = false;
    scene.add(this.cake);
    this.back();
  }

  /** Whether he's had his cake (and isn't in the way). */
  get fed() {
    return this.doing !== "waiting";
  }

  private play(name: string, now = false) {
    const next = this.clips.get(name);
    if (!next || next === this.playing) return;
    next.reset().play();
    if (this.playing && !now) next.crossFadeFrom(this.playing, BLEND, false);
    else this.playing?.stop();
    this.playing = next;
  }

  private placed(at: Vector3, yaw: number) {
    this.model.position.copy(at);
    this.yaw = yaw;
    this.model.rotation.y = yaw;
  }

  /** Straight to it, still: a clip's first frame, his hands and head shaped. */
  private pose(name: string) {
    this.play(name, true);
    this.mixer.update(0);
    this.shape();
    this.posed.copy(this.head?.quaternion ?? this.posed);
  }

  /** Crouching in front of the way, hungry (a game loaded without the cake in use here, or you've gone). */
  back() {
    if (this.doing === "waiting" && this.playing) return;
    this.doing = "waiting";
    this.cake.visible = false;
    this.placed(this.crouch, this.crouchYaw);
    this.pose("Crouch_Idle_Loop");
  }

  /** Sitting on his boulder, fed (a game loaded with the cake in use here). */
  away() {
    this.doing = "sitting";
    this.cake.visible = false;
    this.placed(this.seat, this.seatYaw);
    this.pose("Sitting_Idle_Loop");
  }

  /** You've used the cake here: you throw it to him, from your hand. */
  feed(from: Vector3) {
    if (this.doing !== "waiting") return;
    if (this.reducedMotion) return this.away();
    this.doing = "catching";
    this.time = 0;
    this.bitten = 0;
    this.from.copy(from);
    this.cake.scale.setScalar(1);
    this.cake.position.copy(from);
    this.cake.visible = true;
    this.play("Idle_Loop");
  }

  /** Walking into the way, with no cake: he shakes his head at you. */
  refuse() {
    if (this.doing === "waiting") this.shaking = 0;
  }

  /** Each frame: your eyes, and whether you're in his cave. */
  update(dt: number, eye: Vector3, here: boolean) {
    const far = this.model.position.distanceTo(eye);
    this.model.visible = here || far < FAR;
    if (!this.model.visible) return;
    if (this.reducedMotion) return;
    this.time += dt;
    this.act(dt);
    // (The mixer only sets a bone when its clip moves it: held still, the
    // head would keep the turn it was given last frame, and turn again.)
    this.head?.quaternion.copy(this.posed);
    this.arm.slice(0, 2).forEach((bone, k) => bone.quaternion.copy(this.armPosed[k]));
    this.mixer.update(dt);
    this.shape();
    this.posed.copy(this.head?.quaternion ?? this.posed);
    this.arm.slice(0, 2).forEach((bone, k) => this.armPosed[k].copy(bone.quaternion));
    if (this.doing === "eating") this.reach(this.lifted());
    const watching = here && far < WATCH && (this.doing === "waiting" || this.doing === "sitting");
    this.watch(eye, watching, dt);
    this.blink(dt);
    this.hold();
  }

  /** What he's doing, and on to the next thing, when it's done. */
  private act(dt: number) {
    const clip = this.playing?.getClip().duration ?? 1;
    if (this.doing === "catching") {
      // The cake in the air, along an arc, turning over, into his hand (as he stands up).
      const flight = Math.min(FLIGHT[1], Math.max(FLIGHT[0], this.from.distanceTo(this.palm()) / 8));
      const u = Math.min(1, this.time / flight);
      this.cake.position.lerpVectors(this.from, this.palm(), u).addScaledVector(UP, 3 * u * (1 - u));
      this.cake.rotation.set(this.time * 6, this.time * 2, 0);
      this.cake.scale.setScalar(1 + (CAKE - 1) * u);
      if (u >= 1) {
        this.doing = "eating";
        this.time = 0;
      }
    } else if (this.doing === "eating") {
      // A bite each time his hand's at his mouth, the cake smaller each time;
      // the last, and it's gone.
      const each = BITE[0] + BITE[1] + BITE[2];
      const bites = Math.min(BITES, Math.floor((this.time - BITE[0] - BITE[1] / 2) / each + 1));
      if (bites > this.bitten) {
        this.bitten = bites;
        this.munch();
        this.cake.scale.setScalar(CAKE * Math.cbrt(1 - bites / BITES));
        this.cake.visible = bites < BITES;
      }
      if (this.time > each * BITES) this.next("nodding", "Yes");
    } else if (this.doing === "nodding") {
      if (this.time > clip) this.next("walking", "Walk_Loop");
    } else if (this.doing === "walking") {
      // Over to his boulder, turning to go that way.
      const to = this.seat.clone().sub(this.model.position).setY(0);
      const step = WALK * this.model.scale.x * dt;
      this.turnTo(Math.atan2(to.x, to.z), dt);
      if (to.length() <= step) {
        this.model.position.copy(this.seat);
        this.next("turning", "Idle_Loop");
      } else this.model.position.addScaledVector(to.normalize(), step);
    } else if (this.doing === "turning") {
      // Round, his back to it, and down he sits.
      if (this.turnTo(this.seatYaw, dt)) this.next("sitting down", "Sitting_Enter");
    } else if (this.doing === "sitting down") {
      if (this.time > clip) this.next("sitting", "Sitting_Idle_Loop");
    }
  }

  private next(doing: Doing, clip: string) {
    this.doing = doing;
    this.time = 0;
    this.play(clip);
  }

  /** Turned towards a way (radians round), as fast as he turns; and whether he's facing it. */
  private turnTo(yaw: number, dt: number) {
    const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
    const off = wrap(yaw - this.yaw);
    const step = TURNING * dt;
    this.yaw = Math.abs(off) <= step ? yaw : this.yaw + Math.sign(off) * step;
    this.model.rotation.y = this.yaw;
    return this.yaw === yaw;
  }

  /** The middle of his right hand's palm, where he holds the cake. */
  private palm() {
    this.model.updateMatrixWorld(true);
    const wrist = this.hand?.getWorldPosition(new Vector3()) ?? this.model.position.clone();
    const knuckle = this.knuckle?.getWorldPosition(new Vector3()) ?? wrist;
    return wrist.lerp(knuckle, 0.6);
  }

  /** The cake in his hand, eating it (upright, its cut towards him). */
  private hold() {
    if (this.doing !== "eating" || !this.cake.visible) return;
    this.cake.position.copy(this.palm());
    this.cake.rotation.set(0, this.yaw + Math.PI / 2, 0);
  }

  /** How far his hand's lifted to his mouth, eating (0 to 1): up, a bite, and down, each time. */
  private lifted() {
    const each = BITE[0] + BITE[1] + BITE[2];
    const t = this.time % each;
    const ease = (u: number) => u * u * (3 - 2 * u);
    if (this.time >= each * BITES) return 0;
    if (t < BITE[0]) return ease(t / BITE[0]);
    if (t < BITE[0] + BITE[1]) return 1;
    return ease(1 - (t - BITE[0] - BITE[1]) / BITE[2]);
  }

  /**
   * His left arm turned (as much as lift, 0 to 1) to bring the cake in his
   * hand to his mouth: his elbow bent and down by his side, his forearm up
   * to it (two bones, each turned the least way that gets it there).
   */
  private reach(lift: number) {
    const [upper, fore, hand] = this.arm;
    if (!upper || !fore || !hand || !this.head || lift <= 0) return;
    this.model.updateMatrixWorld(true);
    const size = this.model.scale.x;
    const facing = new Quaternion().setFromAxisAngle(UP, this.yaw);
    const ahead = new Vector3(0, 0, 1).applyQuaternion(facing);
    // (His mouth, and the cake's middle in front of it: its edge at his lips.)
    const mouth = this.head
      .getWorldPosition(new Vector3())
      .addScaledVector(ahead, MOUTH[0] * size)
      .addScaledVector(UP, MOUTH[1] * size);
    const target = mouth.addScaledVector(ahead, 0.3).addScaledVector(UP, -0.1);
    const shoulder = upper.getWorldPosition(new Vector3());
    const elbow = fore.getWorldPosition(new Vector3());
    const wrist = this.palm();
    const a = elbow.distanceTo(shoulder);
    const b = wrist.distanceTo(elbow);
    const to = target.clone().sub(shoulder);
    const d = Math.min(a + b - 1e-3, Math.max(Math.abs(a - b) + 1e-3, to.length()));
    const way = to.normalize();
    // (Its elbow down, and out to his left.)
    const pole = new Vector3(0.6, -1, 0).applyQuaternion(facing);
    pole.addScaledVector(way, -pole.dot(way)).normalize();
    const cos = (a * a + d * d - b * b) / (2 * a * d);
    const bent = shoulder
      .clone()
      .addScaledVector(way, a * cos)
      .addScaledVector(pole, a * Math.sqrt(Math.max(0, 1 - cos * cos)));
    const turn = (bone: Object3D, from: Vector3, to: Vector3) => {
      const world = bone.getWorldQuaternion(new Quaternion());
      const wanted = new Quaternion().setFromUnitVectors(from.normalize(), to.normalize()).multiply(world);
      world.slerp(wanted, lift);
      bone.quaternion.copy(bone.parent!.getWorldQuaternion(new Quaternion()).invert().multiply(world));
      bone.updateMatrixWorld(true);
    };
    turn(upper, elbow.clone().sub(shoulder), bent.clone().sub(shoulder));
    const now = fore.getWorldPosition(new Vector3());
    turn(fore, this.palm().sub(now), shoulder.clone().addScaledVector(way, d).sub(now));
  }

  /** His hands and head as big as they are (each frame, after his clip: his clips set every bone's size). */
  private shape() {
    for (const hand of this.hands) hand.scale.setScalar(HANDS);
    for (const [bone, at] of this.fingers) bone.position.copy(at);
  }

  /** Now and then, a blink (and sometimes another, straight after). */
  private blink(dt: number) {
    const { lids } = this;
    if (lids.at < 0) {
      lids.wait -= dt;
      if (lids.wait > 0) return;
      lids.at = 0;
    }
    lids.at += dt;
    this.shut(Math.sin(Math.PI * Math.min(1, lids.at / SHUT)));
    if (lids.at < SHUT) return;
    this.shut(0);
    lids.at = -1;
    lids.wait = Math.random() < 0.2 ? 0.12 : BLINK[0] + Math.random() * (BLINK[1] - BLINK[0]);
  }

  /** His head turned to you (as far as it can turn), now and then glancing aside; or shaking, no. */
  private watch(eye: Vector3, watching: boolean, dt: number) {
    const { head, model, look, glance } = this;
    if (!head?.parent) return;
    glance.for -= dt;
    if (glance.for <= 0) {
      const aside = Math.random() < 0.4;
      glance.turn = aside ? Math.sign(Math.random() - 0.5) * (0.25 + Math.random() * 0.3) : 0;
      glance.up = aside ? (Math.random() - 0.5) * 0.2 : 0;
      glance.for = GLANCE[0] + Math.random() * (GLANCE[1] - GLANCE[0]);
    }
    model.updateMatrixWorld(true);
    // Where his face looks, as his clip has it; and how far round and up it
    // turns from there to look at you (as far round as his neck goes), give
    // or take a glance. (Not watching, as his clip has it.)
    const at = head.getWorldPosition(new Vector3());
    const world = head.getWorldQuaternion(new Quaternion());
    const facing = this.face.clone().applyQuaternion(world);
    const to = eye.clone().sub(at);
    const wrap = (a: number) => Math.atan2(Math.sin(a), Math.cos(a));
    const round = this.yaw + Math.max(-TURN, Math.min(TURN, wrap(Math.atan2(to.x, to.z) - this.yaw + glance.turn)));
    const up = Math.max(-0.6, Math.min(0.5, Math.atan2(to.y, Math.hypot(to.x, to.z)) + glance.up));
    const wants = watching
      ? { turn: wrap(round - Math.atan2(facing.x, facing.z)), up: up - Math.asin(Math.max(-1, Math.min(1, facing.y))) }
      : { turn: 0, up: 0 };
    const ease = Math.min(1, dt * 3);
    look.turn += (wants.turn - look.turn) * ease;
    look.up += (wants.up - look.up) * ease;
    // (And shaking his head at you: no, side to side, dying away.)
    this.shaking += dt;
    const fading = Math.max(0, 1 - this.shaking / SHAKE[0]);
    const shake = Math.sin(this.shaking * SHAKE[1]) * SHAKE[2] * fading;
    // (On top of what his clip does: up, about his face's own side, then
    // round; and back into the head's parent's frame.)
    const side = facing.clone().cross(UP).normalize();
    const wanted = new Quaternion()
      .setFromAxisAngle(UP, look.turn + shake)
      .multiply(new Quaternion().setFromAxisAngle(side, look.up))
      .multiply(world);
    head.quaternion.copy(head.parent.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
  }
}
