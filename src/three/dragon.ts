// The dragon in its cave (its model: art/blender/dragon.py), standing just
// in from the tunnel south, its head up by the roof. It watches you; the
// moment you come in, and again the moment you try to go on south past it,
// it throws its head back and breathes a great gout of fire across the
// mouth of the tunnel (and meanwhile puffs smoke, and a flicker of flame).
// Use the water and you throw it, up into its open mouth: its fire turns to
// steam, and it shakes its head, crossly, puffing smoke and steam, and lets
// you by. Once the water's no longer in use there (you've gone on, as in
// the original), it's breathing fire again.
//
// It has its own skeleton, and no clips: its bones are turned here, each on
// top of how it was made (its neck, to look and to aim, its jaw, its tail
// and its wings, swaying). The fire, the water and the steam are sprites.
// (With motion reduced, it's still: its head turned to the tunnel, its jaw
// open, and the fire, or the steam, hanging there.)

import {
  AdditiveBlending,
  type Bone,
  Color,
  DoubleSide,
  Group,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  NormalBlending,
  type Object3D,
  PointLight,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  Vector3,
} from "three";

import { puff } from "./smoke";

/** Where it stands [x, z] and its floor, which way it faces [x, z], and where its fire goes [x, y, z] (land.json). */
export interface DragonSpot {
  at: number[];
  facing: number[];
  fire: number[];
}

/** Its cave (land.json's hall): its middle, how far its wall is, and how tall it is. */
export interface DragonCave {
  x: number;
  z: number;
  r: number;
  tall: number;
}

const UP = new Vector3(0, 1, 0);
const ACROSS = new Vector3(1, 0, 0); // (its left, as it was made, facing +z)
const AHEAD = new Vector3(0, 0, 1);
// Its neck's bones, from its chest up to its head, and how much of a turn
// (round, then up or down) each takes.
const NECK = ["neck-1", "neck-2", "neck-3", "neck-4", "neck-5", "head"];
const TURNS = [0.06, 0.12, 0.18, 0.22, 0.22, 0.2];
const NODS = [0.04, 0.08, 0.12, 0.16, 0.2, 0.4];
const TAIL = ["tail-1", "tail-2", "tail-3", "tail-4", "tail-5", "tail-6"];
const TURN = 1.3; // radians it turns its head, at most, either way
const NOD = { up: -0.45, down: 1.0 }; // and up and down
const NEAR = 18; // metres: this near, it watches you
const FAR = 90; // metres: further off than this, it's left as it is

// Breathing fire: back, breathing in, then the fire, then its mouth closing.
const BREATHE_IN = 0.25; // seconds (quickly: no doubt the way is shut)
const FIRE = 1.8;
const AFTER = 0.6;
const JAW = 0.6; // radians its jaw opens, breathing fire
const TIP = 0.3; // and its head tips back
const AJAR = 0.05; // radians its jaw rests open, just showing its teeth (a little more as it breathes out)

const SPRITES = 220;
const FIRE_RATE = 75; // sprites a second, breathing fire
const FIRE_SPEED = 12; // metres a second, out of its mouth
const FIRE_LIFE = 1.15; // seconds
const STEAM_LIFE = 4;
const THROW = 0.9; // seconds, the water from your hand to its mouth
const SHAKE = 1.6; // seconds it shakes its head, doused
const FLAME = [new Color("#ffd27a"), new Color("#ffa030"), new Color("#ff5a14"), new Color("#6a1206")];
const STEAM = new Color("#e2dad2"); // (a little warmed by the cave)
const SMOKE = new Color("#8a8078");
const WATER = new Color("#a8d8ff");

type Kind = "off" | "fire" | "steam" | "smoke" | "water";

interface Sprit {
  sprite: Sprite;
  kind: Kind;
  at: Vector3;
  speed: Vector3;
  age: number;
  life: number;
  size: number;
  spin: number;
}

interface Joint {
  bone: Bone;
  rest: Quaternion;
  /** How it's turned in the model, as made (to turn it about the model's own axes). */
  model: Quaternion;
  turn: Quaternion;
}

/**
 * Its skin, scaly: rows of round scales, each overlapping the one behind
 * (towards its tail), a little lighter or darker than the next, and dark at
 * its edge, where it lies over the next. Where each point is on them comes
 * with its model (dragon.py's Skinned: its two sets of UVs, which glTF turns
 * upside down): which way round its tube, as a cosine and a sine; how far
 * along it, and how big round, in scales (round 0: none; more than 0, none
 * on its belly, where it has plates).
 */
function scaly(mesh: Mesh, material: MeshStandardMaterial) {
  const geometry = mesh.geometry;
  geometry.setAttribute("scaleRound", geometry.getAttribute("uv"));
  geometry.setAttribute("scaleAlong", geometry.getAttribute("uv1"));
  const skin = material.clone();
  skin.onBeforeCompile = (shader) => {
    shader.vertexShader = shader.vertexShader
      .replace(
        "#include <common>",
        `#include <common>
        attribute vec2 scaleRound;
        attribute vec2 scaleAlong;
        varying vec2 vRound;
        varying vec2 vAlong;`
      )
      .replace(
        "#include <begin_vertex>",
        `#include <begin_vertex>
        vRound = vec2(scaleRound.x, 1.0 - scaleRound.y);
        vAlong = vec2(scaleAlong.x, 1.0 - scaleAlong.y);`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec2 vRound;
        varying vec2 vAlong;
        float scaleHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
        float scaled() {
          float round = abs(vAlong.y);
          if (round < 0.05) return 1.0;
          // (Its rows close together: each scale well over the one behind.)
          vec2 p = vec2(atan(vRound.y, vRound.x) * round, vAlong.x * 1.35);
          // (The scale it's on: in this row or the next on, whichever's over it.)
          float row = floor(p.y);
          float d = 1.0;
          vec2 id = vec2(0.0);
          for (int k = 1; k >= 0; k--) {
            float y = row + float(k);
            float stagger = 0.5 * mod(y, 2.0);
            float x = floor(p.x - stagger) + 0.5 + stagger;
            for (int j = -1; j <= 1; j++) {
              vec2 centre = vec2(x + float(j), y);
              float e = length((p - centre) * vec2(1.0, 1.15)) / 0.74;
              if (e < 1.0 && d >= 1.0) { d = e; id = centre; }
            }
          }
          float shade = (0.9 + 0.18 * scaleHash(id)) * mix(1.08, 0.62, smoothstep(0.7, 1.0, d));
          // (Its belly's plates, smooth.)
          float belly = vAlong.y > 0.0 ? smoothstep(-0.3, -0.55, vRound.x) : 0.0;
          return mix(shade, 1.0, belly);
        }`
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        diffuseColor.rgb *= scaled();`
      );
  };
  return skin;
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};

export class Dragon {
  private model: Object3D;
  private joints = new Map<string, Joint>();
  private sprites: Sprit[] = [];
  private group = new Group();
  private light = new PointLight("#ff8a3a", 0, 26, 1.3);
  private fireAt: Vector3;
  private floor: number;
  /** Its head, and which way it points, in the model, as made. */
  private head = new Vector3();
  private ahead = new Vector3();
  /** Which way its mouth points, in its mouth bone's own frame. */
  private mouthAhead = new Vector3();
  private state: "watching" | "breathing" | "doused" | "sulking" = "watching";
  private time = 0;
  private since = 0; // seconds since its state changed (or it began breathing in)
  private next = Infinity; // seconds till it next breathes fire
  private look = { turn: 0, nod: 0 };
  private jaw = 0;
  private emitting = 0; // sprites owed
  private thrown = -1; // seconds since you threw the water (-1: not thrown)
  private puffIn = 3; // seconds till its next puff of smoke
  private wasHere = false;
  private shake = 0; // radians its head's shaken round, doused

  constructor(
    scene: Scene,
    source: Object3D,
    spot: DragonSpot,
    private cave: DragonCave,
    private reducedMotion: boolean,
    /** Its fire, roaring out (how loud, for how near you are). */
    private onRoar: (loudness: number) => void,
    /** And hissing out, doused. */
    private onHiss: (loudness: number) => void
  ) {
    this.model = source;
    const [x, z, floor] = spot.at;
    this.floor = floor;
    this.model.position.set(x, floor, z);
    this.model.rotation.y = Math.atan2(spot.facing[0], spot.facing[1]);
    this.fireAt = new Vector3(...spot.fire);
    this.model.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      o.frustumCulled = false; // (moved by its bones: its bounds don't follow)
      const material = o.material as MeshStandardMaterial;
      if (o.name === "dragon") o.material = scaly(o, material);
      else if (o.name.startsWith("dragon-eyes")) {
        o.material = new MeshBasicMaterial({ vertexColors: true });
      } else if (o.name.startsWith("dragon-wings")) {
        // (Thin: lit a little from behind, by the fire and the cave's light.)
        o.material = material.clone();
        Object.assign(o.material, { side: DoubleSide, emissive: new Color("#4a0c14") });
      }
    });
    scene.add(this.model);
    this.model.updateMatrixWorld(true);
    const facing = this.model.getWorldQuaternion(new Quaternion()).invert();
    this.model.traverse((o) => {
      if (!(o as Bone).isBone) return;
      const bone = o as Bone;
      this.joints.set(bone.name, {
        bone,
        rest: bone.quaternion.clone(),
        model: facing.clone().multiply(bone.getWorldQuaternion(new Quaternion())),
        turn: new Quaternion(),
      });
    });
    const head = this.joints.get("head")!.bone;
    const mouth = this.joints.get("mouth")!;
    this.head.copy(this.model.worldToLocal(head.getWorldPosition(new Vector3())));
    this.ahead
      .copy(this.model.worldToLocal(mouth.bone.getWorldPosition(new Vector3())))
      .sub(this.head)
      .normalize();
    this.mouthAhead.copy(this.ahead).applyQuaternion(mouth.model.clone().invert());

    const map = puff();
    for (let k = 0; k < SPRITES; k++) {
      const sprite = new Sprite(new SpriteMaterial({ map, transparent: true, depthWrite: false }));
      sprite.visible = false;
      this.group.add(sprite);
      this.sprites.push({
        sprite,
        kind: "off",
        at: new Vector3(),
        speed: new Vector3(),
        age: 0,
        life: 1,
        size: 1,
        spin: 0,
      });
    }
    scene.add(this.group, this.light);
    if (reducedMotion) this.still();
  }

  /** Doused: the water thrown from your hand (or, loading, it's doused already). */
  douse(hand?: Vector3) {
    if (this.state === "doused" || this.state === "sulking") return;
    if (!hand || this.reducedMotion) {
      this.state = "sulking";
      this.since = 0;
      for (const s of this.sprites) this.retire(s);
      if (this.reducedMotion) this.still();
      return;
    }
    // A splash of water, up in an arc to its mouth.
    const mouth = this.mouth();
    for (let k = 0; k < 26; k++) {
      const s = this.take();
      if (!s) break;
      const from = hand.clone().add(new Vector3((Math.random() - 0.5) * 0.15, (Math.random() - 0.5) * 0.1, 0));
      const to = mouth.clone().add(new Vector3((Math.random() - 0.5) * 0.5, (Math.random() - 0.5) * 0.4, 0));
      const flight = THROW * (0.85 + Math.random() * 0.3);
      // (Up, then down onto it: as much higher as gravity takes back.)
      s.speed.set((to.x - from.x) / flight, (to.y - from.y) / flight + 4.9 * flight, (to.z - from.z) / flight);
      this.start(s, "water", from, flight, 0.14 + Math.random() * 0.1);
    }
    this.thrown = 0;
  }

  /** The water no longer in use there: it's breathing fire again. */
  relight() {
    if (this.state !== "doused" && this.state !== "sulking") return;
    this.state = "watching";
    this.since = 0;
    this.next = Infinity;
    this.thrown = -1;
    for (const s of this.sprites) this.retire(s);
    if (this.reducedMotion) this.still();
  }

  /** You trying to go on south past it: it breathes its fire at the tunnel. */
  blaze() {
    if (this.state === "watching") this.next = 0;
    // (Or, its fire dying away, a fresh gout of it.)
    else if (this.state === "breathing" && this.since > BREATHE_IN + FIRE * 0.6) this.since = BREATHE_IN / 2;
  }

  get doused() {
    return this.state === "doused" || this.state === "sulking";
  }

  /** Each frame: where your eyes are, and whether you're in its cave. */
  update(dt: number, eye: Vector3, here: boolean) {
    const far = this.model.position.distanceTo(eye);
    this.model.visible = far < FAR * 1.5;
    if (this.reducedMotion || far > FAR) {
      this.light.intensity = this.reducedMotion && !this.doused && far < FAR ? 6 : 0;
      return;
    }
    this.time += dt;
    this.since += dt;
    const watching = here && far < NEAR;

    // Breathing fire across the tunnel's mouth, as you come in (or when you
    // try to go past it: blaze); meanwhile, now and then, a puff of smoke
    // and a flicker of flame.
    let target: Vector3 | undefined = watching ? eye : undefined;
    let wantsJaw = 0;
    let rear = 0; // (its head drawn back and up, breathing in)
    if (here && !this.wasHere) this.blaze();
    this.wasHere = here;
    if (this.state === "watching") {
      this.next -= dt;
      if (this.next <= 0) {
        this.state = "breathing";
        this.since = 0;
        this.next = Infinity;
      }
      this.puffIn -= dt;
      if (this.puffIn <= 0) {
        this.puffIn = 3 + Math.random() * 3;
        const mouth = this.mouth();
        for (let k = 0; k < 3; k++) this.puff(mouth, "smoke", 0.5);
        for (let k = 0; k < 4; k++) this.flicker(mouth);
      }
    }
    if (this.state === "breathing") {
      const t = this.since;
      target = this.fireAt;
      if (t < BREATHE_IN) {
        rear = ease(t / BREATHE_IN);
        wantsJaw = 0.15 * rear;
      } else if (t < BREATHE_IN + FIRE) {
        rear = 1 - ease((t - BREATHE_IN) / 0.25);
        wantsJaw = 1;
        if (t - dt < BREATHE_IN) this.onRoar(this.loudness(far));
        this.emitting += FIRE_RATE * dt;
        while (this.emitting >= 1) {
          this.emitting -= 1;
          this.breathe();
        }
      } else if (t > BREATHE_IN + FIRE + AFTER) {
        this.state = "watching";
        this.since = 0;
      }
    }
    // The water, landing in its mouth: the fire turns to steam.
    if (this.thrown >= 0) {
      this.thrown += dt;
      if (this.thrown >= THROW && this.state !== "doused") {
        this.state = "doused";
        this.since = 0;
        this.onHiss(this.loudness(far));
        for (const s of this.sprites) {
          if (s.kind === "fire") {
            s.speed.multiplyScalar(0.12);
            this.start(s, "steam", s.at, STEAM_LIFE * (0.6 + Math.random() * 0.4), 1 + Math.random());
          }
        }
        const mouth = this.mouth();
        for (let k = 0; k < 24; k++) this.puff(mouth, "steam", 2.4);
      }
    }
    let shake = 0;
    if (this.state === "doused") {
      // Shaking its head, crossly, its mouth shut tight, puffing steam.
      const t = this.since / SHAKE;
      shake = Math.sin(this.since * 14) * 0.35 * (1 - ease(t));
      target = undefined;
      if (Math.random() < dt * 10) this.puff(this.mouth(), "steam", 1.2);
      if (t >= 1) {
        this.state = "sulking";
        this.since = 0;
      }
    }
    if (this.state === "sulking") {
      // Its head lower, and now and then a puff of smoke from its nose.
      this.puffIn -= dt;
      if (this.puffIn <= 0) {
        this.puffIn = 2.5 + Math.random() * 3;
        const mouth = this.mouth();
        for (let k = 0; k < 5; k++) this.puff(mouth, "smoke", 0.6);
      }
    }

    this.aim(target, dt, rear, shake);
    this.jaw += (wantsJaw - this.jaw) * Math.min(1, dt * (wantsJaw > this.jaw ? 12 : 5));
    this.pose();
    this.move(dt);
    // Its fire's light, flickering, on the cave round it.
    const burning = this.sprites.reduce((n, s) => n + (s.kind === "fire" ? 1 : 0), 0) / (FIRE_RATE * FIRE_LIFE);
    this.light.intensity =
      14 * Math.min(1, burning) * (0.8 + 0.2 * Math.sin(this.time * 31) * Math.sin(this.time * 17));
    this.light.position.lerpVectors(this.mouth(), this.fireAt, 0.5);
  }

  /** How loud it is, from as far as you are. */
  private loudness(far: number) {
    return Math.max(0, Math.min(1, 1.4 - far / 30));
  }

  /** Its head turned to look at (or breathe fire at) a point, or back to
   * how it stands; drawn back, breathing in, or shaking. */
  private aim(target: Vector3 | undefined, dt: number, rear: number, shake: number) {
    const wants = { turn: 0, nod: this.state === "sulking" ? 0.25 : 0 };
    if (target) {
      const to = this.model.worldToLocal(target.clone()).sub(this.head);
      const turn = Math.atan2(to.x, to.z) - Math.atan2(this.ahead.x, this.ahead.z);
      wants.turn = MathUtils.clamp(Math.atan2(Math.sin(turn), Math.cos(turn)), -TURN, TURN);
      const level = (v: Vector3) => Math.atan2(v.y, Math.hypot(v.x, v.z));
      wants.nod = MathUtils.clamp(level(this.ahead) - level(to), NOD.up, NOD.down);
    }
    wants.nod -= rear * 0.45;
    const rate = Math.min(1, dt * (this.state === "breathing" ? 9 : 2));
    this.look.turn += (wants.turn - this.look.turn) * rate;
    this.look.nod += (wants.nod - this.look.nod) * rate;
    this.shake = shake;
  }

  /** Its bones turned: its neck as it looks, its jaw, its tail and wings swaying. */
  private pose() {
    for (const joint of this.joints.values()) joint.turn.identity();
    const turn = (name: string, axis: Vector3, angle: number) => {
      const joint = this.joints.get(name);
      if (joint) joint.turn.premultiply(new Quaternion().setFromAxisAngle(axis, angle));
    };
    const t = this.time;
    const breath = Math.sin(t * 1.3);
    // Breathing fire, its head tipped back, and its jaw dropped. (Its mouth
    // bone, where the fire comes from, isn't: the fire goes where it's aimed.)
    turn("head", ACROSS, -TIP * this.jaw);
    turn("mouth", ACROSS, TIP * this.jaw);
    NECK.forEach((name, k) => {
      turn(name, ACROSS, this.look.nod * NODS[k] + 0.012 * breath);
      turn(name, UP, this.look.turn * TURNS[k] + this.shake * NODS[k]);
    });
    turn("jaw", ACROSS, AJAR + 0.01 * breath + (JAW - AJAR) * this.jaw);
    TAIL.forEach((name, k) => turn(name, UP, 0.07 * Math.sin(t * 0.8 - k * 0.7) * (0.4 + k * 0.25)));
    for (const [name, side] of [
      ["arm-l", 1],
      ["arm-r", -1],
    ] as const) {
      turn(name, AHEAD, side * 0.04 * Math.sin(t * 0.6 + side));
    }
    for (const joint of this.joints.values()) {
      // (Turned about the model's own axes: into the bone's own frame, and back.)
      const inBone = joint.model.clone().invert().multiply(joint.turn).multiply(joint.model);
      joint.bone.quaternion.copy(joint.rest).multiply(inBone);
    }
    this.model.updateMatrixWorld(true);
  }

  /** Where its mouth is (open, between its jaws). */
  private mouth() {
    return this.joints
      .get("mouth")!
      .bone.getWorldPosition(new Vector3())
      .add(new Vector3(0, -0.35 * this.jaw, 0));
  }

  /** Which way it's pointing. */
  private mouthWay() {
    const q = this.joints.get("mouth")!.bone.getWorldQuaternion(new Quaternion());
    return this.mouthAhead.clone().applyQuaternion(q);
  }

  private take() {
    return this.sprites.find((s) => s.kind === "off");
  }

  private start(s: Sprit, kind: Kind, at: Vector3, life: number, size: number) {
    s.kind = kind;
    s.at.copy(at);
    s.age = 0;
    s.life = life;
    s.size = size;
    s.spin = (Math.random() - 0.5) * 2;
    s.sprite.visible = true;
    s.sprite.material.rotation = Math.random() * Math.PI * 2;
    s.sprite.material.blending = kind === "fire" ? AdditiveBlending : NormalBlending;
  }

  private retire(s: Sprit) {
    s.kind = "off";
    s.sprite.visible = false;
  }

  /** A puff of fire, out of its mouth. */
  private breathe() {
    const s = this.take();
    if (!s) return;
    const way = this.mouthWay();
    const spread = new Vector3(Math.random() - 0.5, Math.random() - 0.5, Math.random() - 0.5).multiplyScalar(0.3);
    s.speed.copy(
      way
        .add(spread)
        .normalize()
        .multiplyScalar(FIRE_SPEED * (0.85 + Math.random() * 0.3))
    );
    this.start(s, "fire", this.mouth().addScaledVector(s.speed, 0.02), FIRE_LIFE * (0.8 + Math.random() * 0.4), 0.6);
  }

  /** A little flicker of flame, from its nose. */
  private flicker(at: Vector3) {
    const s = this.take();
    if (!s) return;
    s.speed.set(Math.random() - 0.5, Math.random() - 0.2, Math.random() - 0.5).addScaledVector(this.mouthWay(), 2);
    this.start(s, "fire", at, 0.45 + Math.random() * 0.2, 0.15);
  }

  /** A puff of steam or smoke, from its mouth. */
  private puff(at: Vector3, kind: "steam" | "smoke", force: number) {
    const s = this.take();
    if (!s) return;
    s.speed.set(Math.random() - 0.5, Math.random() * 0.5, Math.random() - 0.5).multiplyScalar(force * 2);
    s.speed.addScaledVector(this.mouthWay(), force);
    this.start(
      s,
      kind,
      at,
      (kind === "steam" ? STEAM_LIFE : 3) * (0.6 + Math.random() * 0.4),
      0.5 + Math.random() * 0.4
    );
  }

  /** Each frame: its fire, water and steam, on their way. */
  private move(dt: number) {
    for (const s of this.sprites) {
      if (s.kind === "off") continue;
      s.age += dt;
      if (s.age >= s.life) {
        this.retire(s);
        continue;
      }
      const t = s.age / s.life;
      const { sprite } = s;
      const material = sprite.material;
      material.rotation += s.spin * dt;
      if (s.kind === "fire") {
        // Slowing, and rising as it goes; spreading out along the floor.
        s.speed.multiplyScalar(Math.exp(-1.6 * dt));
        s.speed.y += 2.2 * dt;
        s.at.addScaledVector(s.speed, dt);
        if (s.at.y < this.floor + 0.3) {
          s.at.y = this.floor + 0.3;
          s.speed.y = Math.abs(s.speed.y) * 0.15;
          s.speed.x *= 1.04;
          s.speed.z *= 1.04;
        }
        const k = Math.min(FLAME.length - 1.001, t * (FLAME.length - 1) * 1.15);
        material.color.copy(FLAME[Math.floor(k)]).lerp(FLAME[Math.floor(k) + 1], k % 1);
        material.opacity = 0.8 * Math.min(1, s.age / 0.05) * (1 - t) ** 1.2;
        sprite.scale.setScalar(s.size * (1 + 5 * ease(t * 1.3)));
      } else if (s.kind === "water") {
        s.speed.y -= 9.8 * dt;
        s.at.addScaledVector(s.speed, dt);
        material.color.copy(WATER);
        material.opacity = 0.85;
        sprite.scale.setScalar(s.size);
      } else {
        // Steam (white, rising, spreading, fading) or smoke (grey, thinner).
        s.speed.multiplyScalar(Math.exp(-1.4 * dt));
        s.speed.y += (1.1 - s.speed.y) * Math.min(1, dt * 0.8);
        s.at.addScaledVector(s.speed, dt);
        material.color.copy(s.kind === "steam" ? STEAM : SMOKE);
        material.opacity = (s.kind === "steam" ? 0.45 : 0.35) * Math.min(1, s.age / 0.3) * (1 - t) ** 1.5;
        sprite.scale.setScalar(s.size + (s.kind === "steam" ? 3 : 1.6) * ease(t));
      }
      // (Kept out of the rock: lifted off the floor, and fading as it
      // reaches the walls and the roof. A sprite into the rock is cut off
      // sharp, in stripes along its faces.)
      const half = sprite.scale.x / 2;
      sprite.position.copy(s.at);
      sprite.position.y = Math.max(s.at.y, this.floor + half * 0.9);
      const { x, z, r, tall } = this.cave;
      const out = Math.hypot(s.at.x - x, s.at.z - z);
      const wall = this.floor + Math.max(4, tall * 0.5);
      const roof = wall + (this.floor + tall - wall) * Math.sqrt(Math.max(0, 1 - (out / (r + 0.4)) ** 2));
      const room = Math.min(r - 0.2 - out, roof - 0.2 - sprite.position.y) / half;
      material.opacity *= Math.min(1, Math.max(0, room));
    }
  }

  /** With motion reduced: posed once, its head turned to where it breathes
   * its fire, and the fire hanging there (or, doused, the steam). */
  private still() {
    for (const s of this.sprites) this.retire(s);
    this.look = { turn: 0, nod: 0 };
    for (let k = 0; k < 60; k++) this.aim(this.doused ? undefined : this.fireAt, 0.1, 0, 0);
    this.jaw = this.doused ? 0 : 1;
    this.pose();
    if (this.doused) {
      const mouth = this.mouth();
      for (let k = 0; k < 6; k++) {
        const s = this.take()!;
        this.start(s, "steam", mouth.clone().add(new Vector3(0, k * 0.5, 0)), 1, 0.8 + k * 0.35);
        s.age = 0.3;
      }
    } else {
      const from = this.mouth();
      const way = this.fireAt.clone().sub(from);
      for (let k = 0; k < 30; k++) {
        const s = this.take()!;
        const t = k / 30;
        this.start(s, "fire", from.clone().addScaledVector(way, t), 1, 0.3);
        s.age = t * 0.7;
      }
    }
    this.move(0);
  }
}
