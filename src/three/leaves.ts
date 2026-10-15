// The pile of leaves filling the dragon's mouth (land.json's leaves), which
// the broom sweeps away. Used, it leaps out of your hand and flies to the
// pile (a witch's broom), sweeps it in quick strokes, side to side, the leaves
// flying up and out into heaps either side of the mouth (as in the picture of
// it swept: a few left lying on the path), and flies back into your hand.
// Otherwise the wind blows them, back into the mouth (or away out of it): they
// lie as the way is for you, wherever you are (main.ts). With motion reduced,
// they're swept (or back) at once.

import {
  Box3,
  BufferGeometry,
  Color,
  DoubleSide,
  Float32BufferAttribute,
  Group,
  InstancedMesh,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
  type PerspectiveCamera,
  Quaternion,
  type Scene,
  Vector3,
} from "three";

import type { Ground } from "./player";

const COUNT = 560; // leaves, on the pile
const STRAYS = 0.06; // of them, swept out onto the path rather than into a heap
const LEAF = 0.32; // metres long (big, to see from a way off), and wide
const LEAF_WIDE = 0.2;
// Half the pile's length (along the way), half its width, and its height; and a heap's.
const PILE = { along: 2.1, across: 1.9, tall: 1.65 };
const HEAP = { along: 1.0, across: 1.15, tall: 0.75 };
const OUT = 0.45; // seconds: the broom flying from your hand to the pile
const STROKES = 4; // sweeping it, side to side, the front of the pile and then the back
const STROKE = 0.3; // seconds each (most of it sweeping: then lifted, over to the next)
const SWEEPING = 0.7;
const BACK = 0.4; // seconds: and back into your hand
const FLIGHT = [0.5, 0.8]; // seconds, a leaf flying into its heap (at least, and at most)
const BLOWN = 1.2; // seconds: the wind blowing them all back (each starting up to half of it after the first)
const FADE = 0.45; // the pile's size (of its full size), from where it fades away
const MOUTH = 3.2; // metres out from the pile's middle: just out of the mouth
const LEAN = 0.55; // radians: the broom's handle, leaning back from upright, sweeping
const COLOURS = ["#c4561d", "#d9822b", "#e0a33a", "#a8401b", "#8a4a22", "#b86a2a", "#7a3b18", "#d46f24"];

interface Leaf {
  pile: Vector3; // where it lies on the pile, from its middle (at its full size)
  pileTurn: Quaternion;
  heap: number; // which heap it's swept into (or -1: out onto the path)
  rest: Vector3; // where it lies there: from the heap's middle (at its full size), or on the path
  restTurn: Quaternion;
  launch: number; // seconds into the sweep that it's swept off the pile
  flight: number; // and how long it flies
  blown: number; // seconds after the wind gets up that it's blown back
  through: Vector3; // it flies out of the mouth through here (so not through its walls), from the pile's middle
  tumble: Vector3; // it turns about this, flying, this many times
  spins: number;
  from: number; // how far it was (0 on the pile, 1 swept), when it was last swept or blown
  at: number; // and how far it is now
}

export class Leaves {
  private leaves: Leaf[] = [];
  private mesh: InstancedMesh;
  private pileCore: Mesh;
  private heapCores: Mesh[];
  private centre: Vector3; // the pile's middle, on the floor
  private heaps: Vector3[]; // and each heap's
  private out: Vector3; // which way is out of the mouth, and across it
  private across: Vector3;
  private broom = new Group(); // its twigs' tip at its middle, its handle up along y
  private swept = false;
  private broomed = false; // (swept by the broom, not blown)
  private time = 0; // since it was swept, or the wind got up
  private still = false; // (and they've settled)
  private stroke = -1; // the stroke the broom's on (for its swish)
  private matrix = new Matrix4();
  private turn = new Quaternion();

  constructor(
    scene: Scene,
    at: [number, number],
    heaps: [number, number][],
    broom: Object3D,
    /** The floor: the way's in the mouth, and the ground outside. */
    private floor: Ground,
    private camera: PerspectiveCamera,
    private reducedMotion: boolean,
    /** The broom's swish, each stroke. */
    private swish: () => void
  ) {
    const [x, z] = at;
    this.centre = new Vector3(x, floor(x, z) ?? 0, z);
    this.heaps = heaps.map(([hx, hz]) => new Vector3(hx, floor(hx, hz) ?? 0, hz));
    const middle = this.heaps.reduce((sum, heap) => sum.add(heap), new Vector3()).divideScalar(this.heaps.length);
    this.out = middle.clone().sub(this.centre).setY(0).normalize();
    this.across = new Vector3(-this.out.z, 0, this.out.x);
    const material = new MeshStandardMaterial({
      vertexColors: true,
      side: DoubleSide,
      flatShading: true,
      roughness: 0.9,
    });
    const coreMaterial = new MeshStandardMaterial({ vertexColors: true, flatShading: true, roughness: 0.95 });

    // The heaps either side (which side of the mouth each is).
    const sides = this.heaps.map((heap) => Math.sign(heap.clone().sub(this.centre).dot(this.across)) || 1);
    const random = seeded(17);
    const up = new Vector3(0, 1, 0);
    for (let i = 0; i < COUNT; i++) {
      const [pile, pileTurn] = onDome(PILE, random);
      const side = Math.sign(pile.dot(this.across)) || 1;
      const deep = -pile.dot(this.out); // how far in, from the pile's middle
      const stray = random() < STRAYS;
      const heap = stray ? -1 : Math.max(0, sides.indexOf(side));
      let rest: Vector3;
      let restTurn: Quaternion;
      if (stray) {
        // Lying on the path, out of the mouth.
        const along = 1.5 + random() * 4;
        const aside = (random() - 0.5) * 2.6;
        rest = this.centre.clone().addScaledVector(this.out, along).addScaledVector(this.across, aside);
        rest.y = (floor(rest.x, rest.z) ?? this.centre.y) + 0.02;
        restTurn = new Quaternion()
          .setFromAxisAngle(up, random() * Math.PI * 2)
          .premultiply(new Quaternion().setFromAxisAngle(this.across, (random() - 0.5) * 0.3));
      } else [rest, restTurn] = onDome(HEAP, random);
      // Swept off in the stroke that sweeps its side of the pile, the front of it first.
      const stroke = (deep > 0.55 ? 2 : 0) + (side > 0 ? 1 : 0);
      this.leaves.push({
        pile,
        pileTurn,
        heap,
        rest,
        restTurn,
        launch: OUT + stroke * STROKE + 0.05 + random() * 0.22,
        flight: FLIGHT[0] + random() * (FLIGHT[1] - FLIGHT[0]),
        blown: random() * BLOWN * 0.5,
        through: this.out
          .clone()
          .multiplyScalar(MOUTH + random() * 0.6)
          .addScaledVector(this.across, side * (0.4 + random() * 0.8))
          .setY(1.0 + random() * 0.8),
        tumble: new Vector3(random() - 0.5, random() - 0.5, random() - 0.5).normalize(),
        spins: 1 + Math.floor(random() * 2),
        from: 0,
        at: 0,
      });
    }
    this.mesh = new InstancedMesh(leaf(), material, COUNT);
    const colour = new Color();
    this.leaves.forEach((_, i) => {
      colour.set(COLOURS[Math.floor(random() * COLOURS.length)]).multiplyScalar(0.85 + random() * 0.3);
      this.mesh.setColorAt(i, colour);
    });
    this.mesh.castShadow = true;
    this.mesh.receiveShadow = true;
    this.mesh.frustumCulled = false;
    // Under them, so you can't see through: the pile's (and heaps') leafy
    // insides, flattening as they're swept off it (and growing, swept on).
    // (The pile's own, to fade away: see draw.)
    this.pileCore = new Mesh(dome(PILE, random), coreMaterial.clone());
    (this.pileCore.material as MeshStandardMaterial).transparent = true;
    this.pileCore.position.copy(this.centre);
    this.heapCores = this.heaps.map((heap) => {
      const core = new Mesh(dome(HEAP, random), coreMaterial);
      core.position.copy(heap);
      return core;
    });
    for (const core of [this.pileCore, ...this.heapCores]) {
      core.castShadow = true;
      core.receiveShadow = true;
    }
    scene.add(this.mesh, this.pileCore, ...this.heapCores);

    // The broom, standing on its twigs' tip.
    const model = broom.clone();
    model.position.set(0, 0, 0);
    model.rotation.set(Math.PI / 2, 0, 0);
    model.traverse((node) => (node.castShadow = true));
    const box = new Box3().setFromObject(model);
    const tip = box.getCenter(new Vector3());
    model.position.set(-tip.x, -box.min.y - 0.05, -tip.z);
    this.broom.add(model);
    this.broom.visible = false;
    scene.add(this.broom);
    this.draw();
  }

  /** Swept (by the broom, or else blown away), or blown back (or `now`, as they'd end up). */
  sweep(swept: boolean, now = false, broom = false) {
    if (swept === this.swept) return;
    this.swept = swept;
    this.broomed = swept && broom;
    this.time = now || this.reducedMotion ? 1000 : 0;
    this.still = false;
    this.stroke = -1;
    for (const leaf of this.leaves) leaf.from = leaf.at;
  }

  /** Each frame: the broom sweeping, and the leaves flying. */
  update(dt: number) {
    if (this.still) return;
    this.time += dt;
    let moving = false;
    for (const leaf of this.leaves) {
      const t = this.broomed ? (this.time - leaf.launch) / leaf.flight : (this.time - leaf.blown) / (BLOWN * 0.5);
      const towards = this.swept ? 1 : 0;
      leaf.at = leaf.from + (towards - leaf.from) * Math.min(1, Math.max(0, t));
      if (t < 1) moving = true;
    }
    const sweeping = this.broomed && this.time < OUT + STROKES * STROKE + BACK;
    this.fly(sweeping);
    this.still = !moving && !sweeping;
    this.draw();
  }

  /** Whether you're in the mouth, past where the pile's front would be (coming out of it). */
  inMouth(p: Vector3) {
    const d = p.clone().sub(this.centre);
    return d.dot(this.out) < PILE.along + 1 && Math.abs(d.dot(this.across)) < PILE.across + 1;
  }

  // How big the pile is (0, swept away, to 1), and each heap.
  private sizes() {
    let pile = 0;
    const heaps = this.heaps.map(() => [0, 0]);
    for (const leaf of this.leaves) {
      pile += 1 - leaf.at;
      if (leaf.heap >= 0) {
        heaps[leaf.heap][0] += leaf.at ** 3; // (as they land)
        heaps[leaf.heap][1]++;
      }
    }
    return { pile: pile / this.leaves.length, heaps: heaps.map(([on, all]) => on / Math.max(1, all)) };
  }

  // Where a leaf lies on the pile (or a heap), as big as it is now: flatter,
  // and a little narrower.
  private on(centre: Vector3, from: Vector3, size: number, into: Vector3) {
    const wide = 0.6 + 0.4 * size;
    return into.set(centre.x + from.x * wide, centre.y + from.y * size, centre.z + from.z * wide);
  }

  private draw() {
    const sizes = this.sizes();
    const start = new Vector3();
    const end = new Vector3();
    const through = new Vector3();
    const one = new Vector3(1, 1, 1);
    this.leaves.forEach((leaf, i) => {
      this.on(this.centre, leaf.pile, sizes.pile, start);
      if (leaf.heap >= 0) this.on(this.heaps[leaf.heap], leaf.rest, sizes.heaps[leaf.heap], end);
      else end.copy(leaf.rest);
      const e = 1 - (1 - leaf.at) ** 2; // (fast off the pile, slowing as it lands)
      through.copy(this.centre).add(leaf.through);
      flight(start, through, end, e);
      this.turn.copy(leaf.pileTurn).slerp(leaf.restTurn, e);
      this.turn.premultiply(new Quaternion().setFromAxisAngle(leaf.tumble, leaf.spins * Math.PI * 2 * e));
      this.matrix.compose(start, this.turn, one);
      this.mesh.setMatrixAt(i, this.matrix);
    });
    this.mesh.instanceMatrix.needsUpdate = true;
    const grow = (core: Mesh, size: number) => {
      core.visible = size > 0.03;
      core.scale.set(0.6 + 0.4 * size, Math.max(size, 0.01), 0.6 + 0.4 * size);
    };
    // The pile, once it's this small, keeps its shape (not flattening to a
    // disc), shrinking all over as it fades away.
    grow(this.pileCore, Math.max(sizes.pile, FADE));
    const fade = Math.min(1, sizes.pile / FADE);
    this.pileCore.scale.multiplyScalar(0.3 + 0.7 * fade);
    (this.pileCore.material as MeshStandardMaterial).opacity = fade;
    this.pileCore.visible = fade > 0.02;
    this.pileCore.castShadow = fade > 0.5;
    this.heapCores.forEach((core, k) => grow(core, sizes.heaps[k]));
  }

  // The broom: out of your hand to the pile, its strokes, and back.
  private fly(sweeping: boolean) {
    this.broom.visible = sweeping && !this.reducedMotion;
    if (!this.broom.visible) return;
    const hand = this.camera.localToWorld(new Vector3(0.2, -0.35, -0.6));
    const t = this.time;
    const done = OUT + STROKES * STROKE;
    const strokes = [...Array(STROKES).keys()].map((k) => this.strokeOf(k));
    let at: Vector3;
    let turn: Quaternion;
    let size = 1;
    if (t < OUT) {
      const e = smooth(t / OUT);
      const [a, , q] = strokes[0];
      at = hand.clone().lerp(a, e);
      at.y += 1.2 * 4 * e * (1 - e);
      const yaw = Math.atan2(a.x - hand.x, a.z - hand.z);
      turn = upright(yaw, 1.3).slerp(q, e);
      size = 0.35 + 0.65 * e;
    } else if (t < done) {
      const k = Math.min(STROKES - 1, Math.floor((t - OUT) / STROKE));
      const u = (t - OUT) / STROKE - k;
      if (k !== this.stroke) {
        this.stroke = k;
        this.swish();
      }
      const [a, b, q, yaw] = strokes[k];
      if (u < SWEEPING) {
        const w = smooth(u / SWEEPING);
        at = a.clone().lerp(b, w);
        at.y = this.surface(at);
        turn = upright(yaw, LEAN + 0.25 * Math.sin(Math.PI * w)); // (flicking, as it goes)
      } else {
        const w = smooth((u - SWEEPING) / (1 - SWEEPING));
        const [next, , nextTurn] = strokes[Math.min(STROKES - 1, k + 1)];
        at = b.clone().lerp(k + 1 < STROKES ? next : b, w);
        at.y = this.surface(at) + 0.45 * Math.sin(Math.PI * w);
        turn = q.clone().slerp(nextTurn, w);
      }
    } else {
      const e = smooth((t - done) / BACK);
      const [, b, q] = strokes[STROKES - 1];
      at = b.clone().lerp(hand, e);
      at.y += 1.0 * 4 * e * (1 - e);
      turn = q;
      size = 1 - 0.7 * e;
    }
    this.broom.position.copy(at);
    this.broom.quaternion.copy(turn);
    this.broom.scale.setScalar(size);
  }

  // A stroke: from where it starts, across and out towards that side's heap;
  // and the broom upright, facing that way.
  private strokeOf(k: number): [Vector3, Vector3, Quaternion, number] {
    const side = k % 2 === 0 ? -1 : 1;
    const deep = k < 2 ? 0 : 1.1;
    const a = this.centre
      .clone()
      .addScaledVector(this.out, -deep)
      .addScaledVector(this.across, -side * 0.3);
    const b = this.centre
      .clone()
      .addScaledVector(this.out, 1.4 - deep)
      .addScaledVector(this.across, side * 1.9);
    const yaw = Math.atan2(b.x - a.x, b.z - a.z);
    a.y = this.surface(a);
    b.y = this.surface(b);
    return [a, b, upright(yaw, LEAN), yaw];
  }

  // The top of the pile (as big as it is now), or the floor.
  private surface(p: Vector3) {
    const size = this.sizes().pile;
    const wide = 0.6 + 0.4 * size;
    const d = p.clone().sub(this.centre);
    const along = d.dot(this.out) / (PILE.along * wide);
    const across = d.dot(this.across) / (PILE.across * wide);
    const top = this.centre.y + PILE.tall * size * Math.sqrt(Math.max(0, 1 - along ** 2 - across ** 2));
    return Math.max(this.floor(p.x, p.z) ?? this.centre.y, top);
  }
}

// Along a smooth curve from the pile, through a point out of the mouth, to
// where it comes to rest: e of the way (into `start`).
function flight(start: Vector3, through: Vector3, end: Vector3, e: number) {
  const out = through.clone().sub(start);
  const on = end.clone().sub(through);
  const middle = end.clone().sub(start).multiplyScalar(0.5); // (its way, through it)
  const split = out.length() / (out.length() + on.length() || 1);
  if (e < split) hermite(start, through, out, middle, e / split, start);
  else hermite(through.clone(), end, middle, on, (e - split) / (1 - split), start);
}

// A cubic from a to b, leaving a this way (ta) and arriving at b this way (tb).
function hermite(a: Vector3, b: Vector3, ta: Vector3, tb: Vector3, t: number, into: Vector3) {
  const t2 = t * t;
  const t3 = t2 * t;
  const [h00, h10, h01, h11] = [2 * t3 - 3 * t2 + 1, t3 - 2 * t2 + t, -2 * t3 + 3 * t2, t3 - t2];
  return into.set(
    h00 * a.x + h10 * ta.x + h01 * b.x + h11 * tb.x,
    h00 * a.y + h10 * ta.y + h01 * b.y + h11 * tb.y,
    h00 * a.z + h10 * ta.z + h01 * b.z + h11 * tb.z
  );
}

// The broom upright, facing this way (yaw), its handle leaning back.
function upright(yaw: number, lean: number) {
  return new Quaternion()
    .setFromAxisAngle(new Vector3(0, 1, 0), yaw)
    .multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), -lean));
}

// A point on a dome's surface (from its middle, on the floor), and a leaf
// lying on it there, turned any way round. Spread evenly over it.
function onDome(size: typeof PILE, random: () => number): [Vector3, Quaternion] {
  const u = random() * Math.PI * 2;
  const phi = Math.asin(random());
  const lump = lumpy(u, phi);
  const p = new Vector3(
    Math.cos(u) * Math.cos(phi) * size.along * lump,
    Math.sin(phi) * size.tall * lump + 0.03,
    Math.sin(u) * Math.cos(phi) * size.across * lump
  );
  const normal = new Vector3(
    (Math.cos(u) * Math.cos(phi)) / size.along,
    Math.sin(phi) / size.tall,
    (Math.sin(u) * Math.cos(phi)) / size.across
  ).normalize();
  const turn = new Quaternion()
    .setFromUnitVectors(new Vector3(0, 1, 0), normal)
    .multiply(new Quaternion().setFromAxisAngle(new Vector3(0, 1, 0), random() * Math.PI * 2))
    .multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), (random() - 0.5) * 0.6));
  return [p, turn];
}

// (Lumpy, not a smooth dome.)
const lumpy = (u: number, phi: number) =>
  1 + 0.07 * Math.sin(3 * u + 1.3) * Math.sin(2 * phi + 0.5) + 0.04 * Math.sin(5 * u + 2) * Math.cos(phi);

// A dome's surface, from its rim (a little under the floor) up, in dark leafy colours.
function dome(size: typeof PILE, random: () => number) {
  const AROUND = 28;
  const UP = 10;
  const positions: number[] = [];
  const colours: number[] = [];
  const colour = new Color();
  const point = (u: number, phi: number) => {
    const lump = lumpy(u, phi);
    return [
      Math.cos(u) * Math.cos(phi) * size.along * lump * 0.97,
      Math.sin(phi) * size.tall * lump * 0.97,
      Math.sin(u) * Math.cos(phi) * size.across * lump * 0.97,
    ];
  };
  for (let j = 0; j < UP; j++) {
    for (let i = 0; i < AROUND; i++) {
      const u0 = (i / AROUND) * Math.PI * 2;
      const u1 = ((i + 1) / AROUND) * Math.PI * 2;
      const p0 = -0.15 + (j / UP) * (Math.PI / 2 + 0.15);
      const p1 = -0.15 + ((j + 1) / UP) * (Math.PI / 2 + 0.15);
      const [a, b, c, d] = [point(u0, p0), point(u1, p0), point(u1, p1), point(u0, p1)];
      for (const corner of [a, c, b, a, d, c]) {
        positions.push(...corner);
        colour.set(COLOURS[Math.floor(random() * COLOURS.length)]).multiplyScalar(0.55 + random() * 0.2);
        colours.push(colour.r, colour.g, colour.b);
      }
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new Float32BufferAttribute(colours, 3));
  geometry.computeVertexNormals();
  return geometry;
}

// A leaf, lying flat along z: pointed, folded a little along its middle, its
// edges curling up. (Lighter down its middle: its own colour is the instance's.)
function leaf() {
  const STEPS = 5;
  const positions: number[] = [];
  const colours: number[] = [];
  const row = (k: number) => {
    const t = k / STEPS;
    const z = (t - 0.5) * LEAF;
    const half = (LEAF_WIDE / 2) * Math.sin(Math.PI * t) ** 0.8;
    return {
      middle: [0, 0.012, z],
      left: [-half, 0.02 + half * 0.25, z],
      right: [half, 0.02 + half * 0.25, z],
    };
  };
  for (let k = 0; k < STEPS; k++) {
    const a = row(k);
    const b = row(k + 1);
    for (const [p, q, r] of [
      [a.middle, b.middle, a.left],
      [a.left, b.middle, b.left],
      [a.middle, a.right, b.middle],
      [a.right, b.right, b.middle],
    ]) {
      for (const corner of [p, q, r]) {
        positions.push(...corner);
        const shade = corner[0] === 0 ? 1 : 0.8;
        colours.push(shade, shade, shade);
      }
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new Float32BufferAttribute(positions, 3));
  geometry.setAttribute("color", new Float32BufferAttribute(colours, 3));
  geometry.computeVertexNormals();
  return geometry;
}

const smooth = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};

// Random numbers, the same every time (so the pile's always the same).
function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}
