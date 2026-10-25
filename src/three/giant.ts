// The giant in his cave (his model: art/blender/giant.py), sitting on his
// boulder beside the way west (land.py), hungry, watching you as you go
// about. Walking into the way, he shakes his head at you.
// Given a cake (thrown from your hand), he catches it, eats it in one big
// gulp, and nods, smiling broadly (and lets you by); and once you've gone,
// he's hungry again.
// Walking into the way with no cake, he turns you into a mouse (mouse.ts):
// he points at you, poof, and then leans down to peer at you, beaming
// (enchant).
//
// His clip is the Universal Animation Libraries', named as it is there. It
// doesn't eat: his hand's lifted to his mouth here, on top of it (reach).

import {
  type AnimationClip,
  AnimationMixer,
  Group,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  SkinnedMesh,
  Vector3,
} from "three";

/** The giant (land.json): where he sits [x, z] and his floor, which way he faces [x, z], and how big he is. */
export interface GiantPlace {
  at: number[];
  facing: number[];
  size: number;
}

const WATCH = 16; // metres: this near, he watches you
const FAR = 45; // metres: further off than this, he isn't drawn
// How quickly his body and arms follow his clip (each second, of the way to
// where it has them): its keys are few, with straight turns between them, and
// the little kinks at each, three times bigger on him, shook his hands.
const STEADY = 6;
const FLIGHT = [0.6, 1.2]; // seconds the cake takes to reach his hand, at least and at most
const BITES = 1; // he eats it in this many bites (one gulp)...
const BITE = [0.6, 0.3, 0.5]; // ...each: seconds lifting it to his mouth, at it (a bite, halfway), and lowering it
const MOUTH = [0.12, -0.03]; // where his mouth is from his head's bone: forward, and up (at the model's size)
const TURN = 0.9; // radians his head turns, at most, either way
const SHAKE = [1.4, 13, 0.35]; // seconds he shakes his head (no), how fast (radians a second), and how far (radians)
const NOD = [1.2, 9, 0.18]; // and nods (yes, fed)
const GLANCE = [1.5, 4]; // seconds between his glances, now to one side, now back to you
const BLINK = [2.5, 6]; // seconds between his blinks
const SHUT = 0.15; // seconds a blink takes
const HANDS = 1.3; // times bigger his hands are (by their bones: so his fingers bend where their joints are)
const FINGERS = 0.85; // and how long their middle and end joints are, pulled in towards his knuckles
const CAKE = 2.0; // the cake in his hand, times the one you carry (growing as it flies to him: a cake for a giant)
const CAKE_SIZE = [0.23, 0.1]; // the one you carry: its radius, and half its height (metres)
const PALM = 0.025; // how far over his palm's middle its top is (at the model's size): the cake sits on it
// Turning you into a mouse, in seconds from walking into the way:
const POINT = [0, 0.3, 0.6, 1.2]; // his hand lifted to point at you, pointing, held there till, and put down again
const LEAN = [0.9, 2.3, 0.75]; // leaning down to peer at you, from, till, and how far (radians, his back bent)
const UP = new Vector3(0, 1, 0);

type Doing = "hungry" | "catching" | "eating" | "fed" | "enchanting";

/** An arm: its bones (upper, fore, hand), its middle finger's knuckle, and which way its elbow goes out (1, his left; -1, his right). */
interface Arm {
  bones: Object3D[];
  knuckle: Object3D | undefined;
  out: number;
}

export class Giant {
  private model: Object3D;
  private head: Object3D | undefined;
  /** His left arm, which eats; and his right, which points. */
  private left: Arm;
  private right: Arm;
  private spine: Object3D[];
  /** His back's, neck's and arms' bones; as his clip has them (put back before the next frame of it); and as they are, steadied. */
  private arms: Object3D[];
  private armsPosed: Quaternion[];
  private armsSteady: Quaternion[];
  private hands: Object3D[];
  private fingers: [Object3D, Vector3][];
  private mixer: AnimationMixer;
  private doing: Doing = "hungry";
  private time = 0; // seconds into what he's doing
  private yaw: number;
  /** Which way his face looks, in his head's own frame. */
  private face: Vector3;
  /** His head, as his clip has it (before it's turned to you). */
  private posed = new Quaternion();
  private look = { turn: 0, up: 0 };
  private glance = { turn: 0, up: 0, for: 0 };
  private shaking = SHAKE[0];
  private nodding = NOD[0];
  private shut: (amount: number) => void = () => {};
  /** His broad smile (the shape key "smile", 0 to 1, on his body and beard), fed; and how far into it he is. */
  private beams: ((amount: number) => void)[] = [];
  private smiling = 0;
  private lids = { wait: BLINK[0], at: -1 };
  private cake = new Group();
  private from = new Vector3();
  private bitten = 0;
  /** Peering at you, turning you into a mouse (0 to 1): his face turned straight to you, the shortest way (no twist, bent over). */
  private peering = 0;

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
      at: [x, z, floor],
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
      const smile = o.morphTargetDictionary?.smile;
      if (smile !== undefined && influences) this.beams.push((amount) => (influences[smile] = amount));
    });
    this.yaw = Math.atan2(fx, fz);
    this.model.position.set(x, floor, z);
    this.model.rotation.y = this.yaw;
    this.model.scale.setScalar(size);
    scene.add(this.model);
    this.head = this.model.getObjectByName("Head");
    const arm = (side: string, out: number) => ({
      bones: ["upperarm", "lowerarm", "hand"].flatMap((bone) => this.model.getObjectByName(`${bone}_${side}`) ?? []),
      knuckle: this.model.getObjectByName(`middle_01_${side}`),
      out,
    });
    this.left = arm("l", 1);
    this.right = arm("r", -1);
    this.spine = ["spine_01", "spine_02", "spine_03"].flatMap((name) => this.model.getObjectByName(name) ?? []);
    this.arms = [
      "spine_01",
      "spine_02",
      "spine_03",
      "neck_01",
      ...["l", "r"].flatMap((side) => ["clavicle", "upperarm", "lowerarm", "hand"].map((bone) => `${bone}_${side}`)),
    ].flatMap((name) => this.model.getObjectByName(name) ?? []);
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
    const sitting = clips.find((clip) => clip.name === "Sitting_Idle_Loop");
    if (sitting) this.mixer.clipAction(sitting).play();
    // The cake he's given: a copy of the one you carry, its middle at its middle.
    const copy = cakeModel.clone();
    copy.position.set(0, -0.1, 0);
    copy.traverse((node) => (node.castShadow = true));
    this.cake.add(copy);
    this.cake.visible = false;
    scene.add(this.cake);
    this.mixer.update(0);
    this.shape();
    this.posed.copy(this.head?.quaternion ?? this.posed);
    this.armsPosed = this.arms.map((bone) => bone.quaternion.clone());
    this.armsSteady = this.arms.map((bone) => bone.quaternion.clone());
  }

  private beam(amount: number) {
    for (const beam of this.beams) beam(amount);
  }

  /** Hungry again (a game loaded without the cake in use here, or you've gone): but not while he's turning you into a mouse. */
  hungry() {
    if (this.doing === "enchanting") return;
    this.doing = "hungry";
    this.cake.visible = false;
    this.beam((this.smiling = 0));
  }

  /** Fed (a game loaded with the cake in use here). */
  fed() {
    this.doing = "fed";
    this.cake.visible = false;
    this.beam((this.smiling = 1));
  }

  /** You've used the cake here: you throw it to him, from your hand. */
  feed(from: Vector3) {
    if (this.doing !== "hungry") return;
    if (this.reducedMotion) return this.fed();
    this.doing = "catching";
    this.time = 0;
    this.bitten = 0;
    this.from.copy(from);
    this.cake.scale.setScalar(1);
    this.cake.position.copy(from);
    this.cake.visible = true;
  }

  /** Himself again, a new game (sitting up, and hungry). */
  reset() {
    this.doing = "hungry";
    this.head?.quaternion.copy(this.posed);
    this.arms.forEach((bone, k) => bone.quaternion.copy(this.armsPosed[k]));
    this.peering = 0;
    this.hungry();
  }

  /** Walking into the way with no cake: he turns you into a mouse (pointing at you, then leaning down to peer at you, beaming). */
  enchant() {
    this.doing = "enchanting";
    this.time = 0;
    this.cake.visible = false;
  }

  /** Where his face is (between his eyes, about). */
  faceAt() {
    this.model.updateMatrixWorld(true);
    return this.head?.localToWorld(this.face.clone().multiplyScalar(0.1)) ?? this.model.position.clone();
  }

  /** Walking into the way, with no cake: he shakes his head at you. */
  refuse() {
    if (this.doing === "hungry") this.shaking = 0;
  }

  /** Each frame: your eyes, and whether you're in his cave. */
  update(dt: number, eye: Vector3, here: boolean) {
    const far = this.model.position.distanceTo(eye);
    this.model.visible = here || far < FAR;
    if (!this.model.visible) return;
    if (this.reducedMotion) return this.still(eye);
    this.time += dt;
    this.act();
    // (The mixer only sets a bone when its clip moves it: held still, his head
    // and arms would keep the turn they were given last frame, and turn again.)
    this.head?.quaternion.copy(this.posed);
    this.arms.forEach((bone, k) => bone.quaternion.copy(this.armsPosed[k]));
    this.mixer.update(dt);
    this.shape();
    this.posed.copy(this.head?.quaternion ?? this.posed);
    // His back and arms steadied: following his clip, but smoothly.
    const steady = Math.min(1, dt * STEADY);
    this.arms.forEach((bone, k) => {
      this.armsPosed[k].copy(bone.quaternion);
      bone.quaternion.copy(this.armsSteady[k].slerp(this.armsPosed[k], steady));
    });
    if (this.doing === "eating") this.reach(this.lifted());
    if (this.doing === "enchanting") this.enchanting(eye);
    this.watch(eye, here && far < WATCH && this.doing !== "eating", dt);
    // Fed, he smiles broadly (as soon as it's gone down); and turning you
    // into a mouse, pleased with himself.
    const beaming =
      this.doing === "fed" ||
      (this.doing === "eating" && this.bitten >= BITES) ||
      (this.doing === "enchanting" && this.time > POINT[1]);
    this.smiling += ((beaming ? 1 : 0) - this.smiling) * Math.min(1, dt * 3);
    this.beam(this.smiling);
    this.blink(dt);
    this.hold();
  }

  /** Catching the cake, and eating it. */
  private act() {
    if (this.doing === "catching") {
      // The cake in the air, along an arc, turning over, into his hand.
      const flight = Math.min(FLIGHT[1], Math.max(FLIGHT[0], this.from.distanceTo(this.held()) / 8));
      const u = Math.min(1, this.time / flight);
      this.cake.position.lerpVectors(this.from, this.held(), u).addScaledVector(UP, 3 * u * (1 - u));
      this.cake.rotation.set(this.time * 6, this.time * 2, 0);
      this.cake.scale.setScalar(1 + (CAKE - 1) * u);
      if (u >= 1) {
        this.doing = "eating";
        this.time = 0;
      }
    } else if (this.doing === "eating") {
      // A bite each time his hand's at his mouth, the cake smaller each time;
      // the last, and it's gone, and he nods.
      const each = BITE[0] + BITE[1] + BITE[2];
      const bites = Math.min(BITES, Math.floor((this.time - BITE[0] - BITE[1] / 2) / each + 1));
      if (bites > this.bitten) {
        this.bitten = bites;
        this.munch();
        this.cake.scale.setScalar(CAKE * Math.cbrt(1 - bites / BITES));
        this.cake.visible = bites < BITES;
      }
      if (this.time > each * BITES) {
        this.doing = "fed";
        this.nodding = 0;
      }
    }
  }

  /** Turning you into a mouse: pointing at you, and leaning down to peer at you. */
  private enchanting(eye: Vector3) {
    const ease = (u: number) => {
      const v = Math.min(1, Math.max(0, u));
      return v * v * (3 - 2 * v);
    };
    const t = this.time;
    const [lift, pointed, held, down] = POINT;
    const pointing = t < held ? ease((t - lift) / (pointed - lift)) : ease(1 - (t - held) / (down - held));
    const leaned = ease((t - LEAN[0]) / (LEAN[1] - LEAN[0]));
    this.lean(LEAN[2] * leaned, eye);
    this.peering = leaned;
    if (pointing > 0) {
      const [upper] = this.right.bones;
      const shoulder = upper.getWorldPosition(new Vector3());
      this.bend(
        this.right,
        pointing,
        shoulder.addScaledVector(eye.clone().sub(shoulder).normalize(), 0.95 * this.long(this.right))
      );
    }
  }

  /** With reduced motion, turning you into a mouse: leaning down to peer at you, beaming, at once (as his clip has him, still, and bent). */
  private still(eye: Vector3) {
    if (this.doing !== "enchanting") return;
    this.head?.quaternion.copy(this.posed);
    this.arms.forEach((bone, k) => bone.quaternion.copy(this.armsPosed[k]));
    this.lean(LEAN[2], eye);
    this.peering = 1;
    this.glance.turn = this.glance.up = 0;
    this.glance.for = Infinity;
    this.watch(eye, true, 1);
    this.beam((this.smiling = 1));
  }

  /** His back bent forward, towards you (radians, all told), on top of his clip. */
  private lean(by: number, eye: Vector3) {
    this.model.updateMatrixWorld(true);
    const to = eye.clone().sub(this.model.position).setY(0).normalize();
    const bend = new Quaternion().setFromAxisAngle(UP.clone().cross(to).normalize(), by / this.spine.length);
    for (const bone of this.spine) {
      const world = bone.getWorldQuaternion(new Quaternion()).premultiply(bend);
      bone.quaternion.copy(bone.parent!.getWorldQuaternion(new Quaternion()).invert().multiply(world));
      bone.updateMatrixWorld(true);
    }
  }

  /** The middle of an arm's palm (his left's, where he holds the cake). */
  private palm(arm = this.left) {
    this.model.updateMatrixWorld(true);
    const wrist = arm.bones[2]?.getWorldPosition(new Vector3()) ?? this.model.position.clone();
    const knuckle = arm.knuckle?.getWorldPosition(new Vector3()) ?? wrist;
    return wrist.lerp(knuckle, 0.6);
  }

  /** How long an arm is, shoulder to palm. */
  private long(arm: Arm) {
    const [upper, fore] = arm.bones;
    const elbow = fore.getWorldPosition(new Vector3());
    return upper.getWorldPosition(new Vector3()).distanceTo(elbow) + elbow.distanceTo(this.palm(arm));
  }

  /** Where the cake's middle is, held: sitting on his palm. */
  private held() {
    return this.palm().addScaledVector(UP, CAKE_SIZE[1] * this.cake.scale.x + PALM * this.model.scale.x);
  }

  /** The cake in his hand, eating it (upright, its cut towards him). */
  private hold() {
    if (this.doing !== "eating" || !this.cake.visible) return;
    this.cake.position.copy(this.held());
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

  /** His left arm turned (as much as lift, 0 to 1) to bring the cake in his hand to his mouth. */
  private reach(lift: number) {
    if (!this.head || lift <= 0) return;
    this.model.updateMatrixWorld(true);
    const size = this.model.scale.x;
    const ahead = new Vector3(0, 0, 1).applyAxisAngle(UP, this.yaw);
    // (His mouth; the cake's middle in front of it, its edge at his lips; and his palm under it.)
    const mouth = this.head
      .getWorldPosition(new Vector3())
      .addScaledVector(ahead, MOUTH[0] * size)
      .addScaledVector(UP, MOUTH[1] * size);
    const target = mouth
      .addScaledVector(ahead, CAKE_SIZE[0] * this.cake.scale.x + 0.04)
      .addScaledVector(UP, -(CAKE_SIZE[1] * this.cake.scale.x + PALM * size));
    this.bend(this.left, lift, target);
  }

  /**
   * An arm turned (as much as lift, 0 to 1) to bring its palm to target:
   * its elbow bent, down and out to his side (two bones, each turned the
   * least way that gets it there).
   */
  private bend(arm: Arm, lift: number, target: Vector3) {
    const [upper, fore, hand] = arm.bones;
    if (!upper || !fore || !hand || lift <= 0) return;
    this.model.updateMatrixWorld(true);
    const facing = new Quaternion().setFromAxisAngle(UP, this.yaw);
    const shoulder = upper.getWorldPosition(new Vector3());
    const elbow = fore.getWorldPosition(new Vector3());
    const wrist = this.palm(arm);
    const a = elbow.distanceTo(shoulder);
    const b = wrist.distanceTo(elbow);
    const to = target.clone().sub(shoulder);
    const d = Math.min(a + b - 1e-3, Math.max(Math.abs(a - b) + 1e-3, to.length()));
    const way = to.normalize();
    // (Its elbow down, and out to his side.)
    const pole = new Vector3(0.6 * arm.out, -1, 0).applyQuaternion(facing);
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
    turn(fore, this.palm(arm).sub(now), shoulder.clone().addScaledVector(way, d).sub(now));
  }

  /** His hands as big as they are (each frame, after his clip: his clips set every bone's size). */
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

  /** His head turned to you (as far as it can turn), now and then glancing aside; or shaking, no; or nodding, yes. */
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
    const up = Math.max(
      this.doing === "enchanting" ? -1 : -0.6,
      Math.min(0.5, Math.atan2(to.y, Math.hypot(to.x, to.z)) + glance.up)
    );
    const wants = watching
      ? { turn: wrap(round - Math.atan2(facing.x, facing.z)), up: up - Math.asin(Math.max(-1, Math.min(1, facing.y))) }
      : { turn: 0, up: 0 };
    const ease = Math.min(1, dt * 3);
    look.turn += (wants.turn - look.turn) * ease;
    look.up += (wants.up - look.up) * ease;
    // (And shaking his head at you, side to side, or nodding, up and down,
    // dying away.)
    this.shaking += dt;
    this.nodding += dt;
    const swing = ([long, fast, far]: number[], t: number) => Math.sin(t * fast) * far * Math.max(0, 1 - t / long);
    const shake = swing(SHAKE, this.shaking);
    const nod = swing(NOD, this.nodding);
    // (On top of what his clip does: up, about his face's own side, then
    // round; and back into the head's parent's frame.)
    const side = facing.clone().cross(UP).normalize();
    const wanted = new Quaternion()
      .setFromAxisAngle(UP, look.turn + shake)
      .multiply(new Quaternion().setFromAxisAngle(side, look.up + nod));
    // (Bent over, peering down at you, turning round and then up twists his
    // face: so, straight to you.)
    if (this.peering > 0) wanted.slerp(new Quaternion().setFromUnitVectors(facing, to.normalize()), this.peering);
    wanted.multiply(world);
    head.quaternion.copy(head.parent.getWorldQuaternion(new Quaternion()).invert().multiply(wanted));
  }
}
