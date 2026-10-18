// Merlin's trap, east of the mountain: "Oh dear! Merlin's trap is that way."
// (PLAN-V3.md: deaths are short scenes from where you stand.) A pile of
// treasure where the path ends, an old oak leaning over it (land.py), and,
// hidden on the path in front of it (unseen till it's sprung), a net, its
// rope running up into the oak's leaves. The gold glints now and then, catching the light, to tempt you
// on. Come near the treasure and the net springs up round you and lifts
// you off your feet: you dangle there, swinging gently under the oak and
// slowly turning round and round, looking down at the gold, as the curtain
// falls (from a little before `ends`); and on swinging and swaying there,
// gently, behind it, till you start again.

import {
  AdditiveBlending,
  CatmullRomCurve3,
  CylinderGeometry,
  DataTexture,
  Euler,
  Group,
  LinearFilter,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  type Object3D,
  type PerspectiveCamera,
  PMREMGenerator,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  TubeGeometry,
  Vector3,
  type WebGLRenderer,
} from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import type { Ground } from "./player";

/**
 * Where the net lies [x, z], its treasure [x, y, z] and the jewels in it [x, y, z, kind], and where its rope's
 * tied [x, y, z], up in the oak (land.json).
 */
export interface TrapSpot {
  net: number[];
  gold: number[];
  jewels: (number | string)[][];
  hook: number[];
}

// The net: a bag of rope, gathered at its top into a knot (where the rope's
// tied on), in a diamond mesh (two sets of strands, twisting round it, each
// way). Lying, it's spread flat on the ground round its knot.
const R = 1.0; // metres, the bag round (from its middle)
const GATHER = 0.35; // its knot, above the bag
const FLAT = 1.3; // metres across, from its knot, lying
const STRANDS = 10; // each way round
const TWIST = Math.PI * 1.1; // how far round each strand goes, from the bottom to the knot
const POINTS = 22; // along each strand
const TOPMOST = 0.8; // of the way round from its bottom, where the bag closes in to its knot
const CORD = 0.007; // metres, a strand's thickness (from its middle)
const ROPE = 0.025; // and the rope's
const COLOUR = "#a68d62"; // old rope

// The gold's glints: how many, how big (metres), over how much of the heap
// (metres round, and up), and how long each one's twinkle takes, now and
// then (seconds, at most). And the jewels', each in its own colour.
const GLINTS = 14;
const GLINT = 0.45;
const HEAP = [0.9, 0.45];
const TWINKLE = 2.6;
const JEWEL_GLINT = 0.3;
const SPARKLE: Record<string, string> = { gold: "#fff3c4", ruby: "#ff8a9a", emerald: "#8affbe" };

// The scene's beats, in seconds from walking into it.
const SPRING = 0.35; // the net springs up…
const LIFTED = 1.1; // …and you're up in it
const ENDS = 6;

const HANG = 1.6; // metres, the bag's bottom above the ground, lifted
const EYE = 0.15; // your eye below the bag's middle, curled up in it
const GRAVITY = 9.8;
const DAMPING = 0.12; // how quickly it settles…
const SWAYING = 0.07; // …to swinging this far (radians), and on
const PUSH = 0.45; // radians a second, swinging on the way you were going
const ASIDE = 0.12; // and from side to side
const TURNING = 0.4; // radians a second, turning round on the rope
const LOOK_DOWN = -0.3; // radians, at the treasure (and the ground)
const LOOKING = 3; // how quickly you turn to look (the larger, the quicker)

/**
 * The treasure, shining (in land.glb: "treasure", its gold, and "jewels"): the
 * gold metal, catching a little room's light (its own, not the scene's), and
 * the rubies and emeralds glassy, with a gleam on them.
 */
export function dressTreasure(land: Object3D, renderer: WebGLRenderer) {
  const pmrem = new PMREMGenerator(renderer);
  const room = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  pmrem.dispose();
  const gold = land.getObjectByName("treasure");
  if (gold instanceof Mesh) {
    gold.material = new MeshStandardMaterial({
      vertexColors: true,
      flatShading: true,
      metalness: 1,
      roughness: 0.42,
      envMap: room,
      envMapIntensity: 0.42,
    });
  }
  const jewels = land.getObjectByName("jewels");
  if (jewels instanceof Mesh) {
    jewels.material = new MeshPhysicalMaterial({
      vertexColors: true,
      flatShading: true,
      metalness: 0.3,
      roughness: 0.1,
      clearcoat: 1,
      clearcoatRoughness: 0.05,
      envMap: room,
      envMapIntensity: 0.4,
    });
  }
}

/** The net and its rope: hidden, lying in wait, or (`spring`, `hang`) up round you. */
export class Net {
  readonly group = new Group(); // at its knot
  private readonly bag: Mesh;
  private readonly rope: Mesh;
  readonly hook: Vector3;
  readonly lying: Vector3;
  private readonly tilt = new Quaternion();
  private readonly turn = new Quaternion();
  private readonly up = new Vector3(0, 1, 0);
  private readonly glints: { sprite: Sprite; size: number; phase: number; every: number }[] = [];
  private time = 0;

  constructor(scene: Scene, spot: TrapSpot, ground: Ground) {
    const [x, z] = spot.net;
    this.lying = new Vector3(x, (ground(x, z) ?? 0) + 0.04, z);
    this.hook = new Vector3(...spot.hook);
    const material = new MeshStandardMaterial({ color: COLOUR, roughness: 1 });
    // Each strand, both lying flat and up as a bag (the same points, so the
    // one turns into the other).
    const flat = [];
    const bag = [];
    for (const way of [1, -1]) {
      for (let n = 0; n < STRANDS; n++) {
        const lies = [];
        const hangs = [];
        for (let i = 0; i <= POINTS; i++) {
          const w = 0.04 + (0.96 * i) / POINTS; // from the bottom (0) to the knot (1)
          const round = (n / STRANDS) * Math.PI * 2 + way * w * TWIST;
          const along = Math.min(1, w / TOPMOST); // round the bag, to where it closes in
          const a = along * TOPMOST * Math.PI; // (from its bottom)
          const gathered = Math.max(0, (w - TOPMOST) / (1 - TOPMOST)); // then in to the knot
          const r = R * Math.sin(a) * (1 - gathered);
          const y = -GATHER - R - R * Math.cos(a) * (1 - gathered) + (GATHER + R + R * Math.cos(a)) * gathered;
          hangs.push(new Vector3(Math.sin(round) * r, y, Math.cos(round) * r));
          // (Lying, its bottom's spread out round the edge, its knot in the middle.)
          const out = FLAT * (1 - w);
          lies.push(new Vector3(Math.sin(round) * out, 0.01 * Math.sin(i * 1.7 + n), Math.cos(round) * out));
        }
        flat.push(new TubeGeometry(new CatmullRomCurve3(lies), POINTS * 2, CORD, 4));
        bag.push(new TubeGeometry(new CatmullRomCurve3(hangs), POINTS * 2, CORD, 4));
      }
    }
    const geometry = mergeGeometries(flat)!;
    const up = mergeGeometries(bag)!;
    geometry.morphAttributes.position = [up.getAttribute("position")];
    geometry.morphAttributes.normal = [up.getAttribute("normal")];
    this.bag = new Mesh(geometry, material);
    this.bag.morphTargetInfluences = [0];
    this.bag.frustumCulled = false; // (its bounds are lying flat)
    this.group.add(this.bag);
    // The rope, from its knot up to the oak (along y, from 0 to 1, stretched).
    const rope = new CylinderGeometry(ROPE, ROPE, 1, 5, 1, true).translate(0, 0.5, 0);
    this.rope = new Mesh(rope, material);
    scene.add(this.group, this.rope);
    // The glints, each in its own spot on the heap (or on a jewel, in its
    // colour), twinkling in its own time.
    const map = star();
    const sparkle = Object.fromEntries(
      Object.entries(SPARKLE).map(([kind, color]) => [
        kind,
        new SpriteMaterial({ map, color, blending: AdditiveBlending, depthWrite: false, transparent: true }),
      ])
    );
    const twinkling = (at: Vector3, kind: string, size: number) => {
      const n = this.glints.length;
      const sprite = new Sprite(sparkle[kind]);
      sprite.position.copy(at);
      sprite.scale.setScalar(0);
      scene.add(sprite);
      this.glints.push({ sprite, size, phase: n * 1.37, every: TWINKLE * (0.6 + 0.4 * ((n * 0.41) % 1)) });
    };
    const [gx, gy, gz] = spot.gold;
    for (let n = 0; n < GLINTS; n++) {
      const a = (n / GLINTS) * Math.PI * 2 + 0.7 * Math.sin(n * 2.3);
      const out = HEAP[0] * (0.25 + 0.75 * ((n * 0.618) % 1));
      twinkling(
        new Vector3(gx + Math.sin(a) * out, gy + HEAP[1] * (1 - out / HEAP[0]) + 0.1, gz + Math.cos(a) * out),
        "gold",
        GLINT
      );
    }
    for (const [x, y, z, kind] of spot.jewels) {
      twinkling(new Vector3(Number(x), Number(y) + 0.05, Number(z)), String(kind), JEWEL_GLINT);
    }
    this.reset();
  }

  /** Each frame: the gold glinting (with motion reduced, just shining softly). */
  update(dt: number, reducedMotion: boolean) {
    this.time += dt;
    for (const { sprite, size, phase, every } of this.glints) {
      const t = ((this.time + phase) % every) / every; // (a twinkle, then a while with none)
      const k = reducedMotion ? 0.4 : Math.max(0, Math.sin(Math.min(1, t * 4) * Math.PI)) ** 2;
      sprite.scale.setScalar(size * k);
      sprite.material.rotation = this.time * 0.5;
    }
  }

  /** Lying in wait (a new game). */
  reset() {
    this.spring(0, this.lying);
    this.show(false);
  }

  /** Whether it's to be seen (sprung). */
  show(shown: boolean) {
    this.group.visible = this.rope.visible = shown;
  }

  /** How far it's sprung up into a bag (0 to 1), its knot at `at`, hanging straight. */
  spring(k: number, at: Vector3) {
    this.bag.morphTargetInfluences![0] = k;
    this.hang(at, 0);
  }

  /** Its knot at `at`, hanging from the oak, turned round on its rope by `round`. */
  hang(at: Vector3, round: number) {
    this.group.position.copy(at);
    const down = this.hook.clone().sub(at);
    const length = down.length();
    this.tilt.setFromUnitVectors(this.up, down.normalize());
    this.group.quaternion.copy(this.tilt).multiply(this.turn.setFromAxisAngle(this.up, round));
    this.rope.position.copy(at);
    this.rope.quaternion.copy(this.tilt);
    this.rope.scale.set(1, length, 1);
  }
}

export class Trapped {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3; // your eye, where you were caught
  private readonly yaw: number; // which way you were looking
  private readonly floor: number;
  private readonly length: number; // the rope, from the oak to the knot, lifted
  private readonly knot = new Vector3();
  private readonly eye = new Vector3();
  private readonly look = new Quaternion();
  // Swinging on the rope: how far (radians, towards x and towards z), and how fast.
  private swing = { x: 0, z: 0, vx: 0, vz: 0 };

  constructor(
    private camera: PerspectiveCamera,
    ground: Ground,
    private net: Net,
    private reducedMotion: boolean,
    private sprung: () => void
  ) {
    this.from = camera.position.clone();
    const ahead = new Vector3(0, 0, -1).applyQuaternion(camera.quaternion);
    this.yaw = Math.atan2(-ahead.x, -ahead.z);
    this.floor = ground(net.lying.x, net.lying.z) ?? net.lying.y;
    this.length = net.hook.y - (this.floor + HANG + 2 * R + GATHER);
    // (Swinging on, the way you were walking.)
    if (!reducedMotion) {
      const along = Math.hypot(ahead.x, ahead.z) || 1;
      this.swing.vx = (PUSH * ahead.x - ASIDE * ahead.z) / along;
      this.swing.vz = (PUSH * ahead.z + ASIDE * ahead.x) / along;
    }
  }

  /** Each frame (till it ends). */
  update(dt: number) {
    const was = this.t;
    this.t += dt;
    const t = this.t;
    if (was < SPRING && t >= SPRING) this.sprung();
    const net = this.net;
    const s = this.swing;
    // Springing up round you, and up off the ground (a little past, then back).
    const k = ease((t - SPRING) / (LIFTED - SPRING));
    const lift = this.reducedMotion ? k : over((t - SPRING) / (LIFTED - SPRING));
    if (t >= LIFTED && !this.reducedMotion) {
      // Swinging, slowing, under the oak.
      const g = GRAVITY / this.length;
      // (Settling to a gentle sway: slowed, swinging further than that, and
      // kept going, less far.)
      const far = Math.hypot(s.x, s.z, Math.hypot(s.vx, s.vz) / Math.sqrt(g));
      const damping = DAMPING * Math.max(-1, Math.min(1, (far - SWAYING) / SWAYING));
      s.vx += (-g * Math.sin(s.x) - damping * s.vx) * dt;
      s.vz += (-g * Math.sin(s.z) - damping * s.vz) * dt;
      s.x += s.vx * dt;
      s.z += s.vz * dt;
    }
    const lifted = this.length * Math.cos(Math.hypot(s.x, s.z));
    this.knot.set(
      net.hook.x + this.length * Math.sin(s.x),
      net.hook.y - lifted,
      net.hook.z + this.length * Math.sin(s.z)
    );
    this.knot.lerpVectors(net.lying, this.knot, lift);
    const round = this.reducedMotion ? 0 : TURNING * Math.max(0, t - LIFTED) + 0.25 * Math.sin(t * 0.9);
    net.show(t >= SPRING);
    net.spring(k, this.knot);
    net.hang(this.knot, round);
    // You, curled up in the bottom of it: scooped up into it as it closes.
    this.eye
      .set(0, -GATHER - R - EYE, 0)
      .applyQuaternion(net.group.quaternion)
      .add(this.knot);
    this.camera.position.lerpVectors(this.from, this.eye, ease((t - SPRING) / (LIFTED - SPRING) / 0.8));
    // Looking down at the treasure, and round, as you turn.
    const yaw = this.yaw + round;
    this.look.setFromEuler(new Euler(LOOK_DOWN * k, yaw, (s.x + s.z) * 0.3, "YXZ"));
    this.camera.quaternion.slerp(this.look, 1 - Math.exp(-dt * LOOKING));
  }
}

// A four-pointed star of light, soft at its middle.
function star() {
  const SIZE = 64;
  const data = new Uint8Array(SIZE * SIZE * 4);
  for (let j = 0; j < SIZE; j++) {
    for (let i = 0; i < SIZE; i++) {
      const x = Math.abs((i + 0.5) / SIZE - 0.5) * 2;
      const y = Math.abs((j + 0.5) / SIZE - 0.5) * 2;
      const rays = Math.max(0, 1 - x * 12) * (1 - y) + Math.max(0, 1 - y * 12) * (1 - x);
      const middle = Math.max(0, 1 - Math.hypot(x, y) * 2.5) ** 2;
      const k = Math.min(1, rays + middle);
      data.set([255, 255, 255, Math.round(k * 255)], (j * SIZE + i) * 4);
    }
  }
  const texture = new DataTexture(data, SIZE, SIZE);
  texture.magFilter = texture.minFilter = LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};

// (Up, a little past, and back: springing up, on the rope.)
const over = (t: number) => {
  const u = Math.min(1, Math.max(0, t)) - 1;
  return 1 + 2.2 * u * u * u + 1.2 * u * u;
};
