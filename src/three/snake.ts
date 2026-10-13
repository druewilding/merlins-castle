// The snake coiled at the top of the mossy steps, guarding the tower's door
// (its model: art/blender/snake.py). It watches you, and comes near and it
// rears up, its mouth wide, its tongue flickering: it hisses at you. Use the
// apple and you throw it: the snake catches it in its jaws, lowers its head
// and slithers away south-west with it, round the stone waiting beside the
// door (land.py), and west down the knoll into the trees. Once
// the apple's no longer in use there (you've gone on, as in the original),
// it's back, coiled by the door, the next time you're not looking.
//
// The model lies dead straight, along its spine from the tip of its tail to
// its nose: each frame, it's bent along a curve (coiled, rearing, or the
// track it's slithering along), its head kept rigid from the hinge of its
// jaws forward.

import {
  BufferAttribute,
  BufferGeometry,
  type Camera,
  Frustum,
  Group,
  Matrix4,
  Mesh,
  type Object3D,
  Quaternion,
  type Scene,
  Sphere,
  Vector3,
} from "three";

import type { Ground } from "./player";

const UP = new Vector3(0, 1, 0);
const STEP = 0.03; // metres between the points along its spine
const PITCH = 0.2; // metres from one turn of its coil to the next
const COIL = 0.5; // the radius of its coil, round the outside
const NEAR = 7.5; // metres: this near, it rears up and hisses
const NECK = 0.6; // metres of its neck that curve up to its head, lifted off the ground
const FAR = 80; // metres: further off than this, it's left as it is
const SPEED = 3.4; // metres a second, slithering away
const APPLE = 0.65; // the apple's size in its jaws, for the one you carry (made big, to see in the grass)

type Point = { at: Vector3; grounded: number }; // grounded: 1 lying on the ground, 0 up in the air

/** A pose: where the back of its head is, which way it faces, and how far up its neck is. */
interface Pose {
  head: Vector3;
  facing: Vector3;
  raised: number;
}

/** A piece of it (the body, the lower jaw, the tongue), bent each frame. */
interface Piece {
  mesh: Mesh;
  along: Float32Array; // each point's distance along it, from the tip of its tail
  across: Float32Array; // and out to its right
  up: Float32Array; // and up
  normal: Float32Array; // (along, across, up) for each point
}

const smooth = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};

export class Snake {
  private pieces: Piece[] = [];
  private length = 0; // from the tip of its tail to its nose
  private hinge = 0; // and to the hinge of its jaws (its head is rigid from here)
  private mouth = 0; // the line of its mouth, above its middle
  private belly: number[] = []; // how far its belly is under its spine, every STEP along it
  private centre: Vector3; // the middle of its coil, on the ground
  private state: "guarding" | "feeding" | "leaving" | "away" = "guarding";
  private time = 0;
  private alert = 0; // 0 coiled and watching, 1 reared up hissing
  private fed = 0; // seconds since you threw the apple
  private flight = 1; // seconds the apple takes to reach it
  private from = new Vector3(); // where the apple left your hand
  private catchAt = new Vector3(); // and where its jaws catch it
  private lunge: Pose | undefined;
  private down: Pose | undefined; // its head lowered, before it goes
  private track: Vector3[] = []; // the way it slithers away, from the tip of its tail
  private gone = 0; // metres along it, slithering
  private apple: Group;
  private caught = false;
  private group = new Group();
  // (Scratch, so nothing new each frame.)
  private points: Vector3[] = [];
  private grounded: number[] = [];
  private tangents: Vector3[] = [];
  private ups: Vector3[] = [];
  private rights: Vector3[] = [];
  private frustum = new Frustum();
  private matrix = new Matrix4();

  constructor(
    scene: Scene,
    model: Object3D,
    appleModel: Object3D,
    private ground: Ground, // (or the top of a path on it)
    door: number[], // the middle of the obstacle in the doorway ([x, z, ...])
    private reducedMotion: boolean
  ) {
    // Its coil, out in front of the door, a little to the west of its middle.
    const [x, z] = door;
    this.centre = new Vector3(x - 0.3, 0, z + 2.5);
    this.centre.y = ground(this.centre.x, this.centre.z) ?? 0;

    model.updateMatrixWorld(true);
    for (const name of ["snake", "snake-jaw", "snake-tongue"]) {
      const source = model.getObjectByName(name) as Mesh;
      const geometry = source.geometry;
      const position = geometry.getAttribute("position");
      const normal = geometry.getAttribute("normal");
      const colour = geometry.getAttribute("color");
      const n = position.count;
      const piece: Piece = {
        mesh: new Mesh(new BufferGeometry(), source.material),
        along: new Float32Array(n),
        across: new Float32Array(n),
        up: new Float32Array(n),
        normal: new Float32Array(n * 3),
      };
      const normals = new Matrix4().copy(source.matrixWorld).invert().transpose();
      const p = new Vector3();
      const q = new Vector3();
      for (let i = 0; i < n; i++) {
        // (In three.js's axes, its nose is towards -z.)
        p.fromBufferAttribute(position, i).applyMatrix4(source.matrixWorld);
        q.fromBufferAttribute(normal, i).applyMatrix4(normals).normalize();
        piece.along[i] = -p.z;
        piece.across[i] = p.x;
        piece.up[i] = p.y;
        piece.normal.set([-q.z, q.x, q.y], i * 3);
      }
      const colours = new Float32Array(n * 4);
      for (let i = 0; i < n; i++) {
        colours.set([colour.getX(i), colour.getY(i), colour.getZ(i), colour.itemSize > 3 ? colour.getW(i) : 1], i * 4);
      }
      const g = piece.mesh.geometry;
      g.setAttribute("position", new BufferAttribute(new Float32Array(n * 3), 3));
      g.setAttribute("normal", new BufferAttribute(new Float32Array(n * 3), 3));
      g.setAttribute("color", new BufferAttribute(colours, 4));
      if (geometry.index) g.setIndex(Array.from(geometry.index.array));
      piece.mesh.castShadow = true;
      piece.mesh.receiveShadow = true;
      piece.mesh.frustumCulled = false; // (it's bent, so its box from the model is no use)
      this.pieces.push(piece);
      this.group.add(piece.mesh);
    }
    const [body, jaw] = this.pieces;
    this.length = Math.max(...body.along);
    this.hinge = Math.min(...jaw.along);
    this.mouth = Math.max(...jaw.up);
    // How far under its spine its belly is, along it (it lies on that).
    this.belly = Array.from({ length: Math.ceil(this.length / STEP) + 1 }, () => 0);
    body.along.forEach((s, i) => {
      const k = Math.round(s / STEP);
      if (s < this.hinge && k >= 0 && k < this.belly.length) this.belly[k] = Math.max(this.belly[k], -body.up[i]);
    });
    for (let k = 1; k < this.belly.length; k++) if (!this.belly[k]) this.belly[k] = this.belly[k - 1];

    const count = Math.ceil(this.length / STEP) + 1;
    for (let k = 0; k < count; k++) {
      this.points.push(new Vector3());
      this.grounded.push(0);
      this.tangents.push(new Vector3());
      this.ups.push(new Vector3());
      this.rights.push(new Vector3());
    }

    // The apple you throw: a copy of the one you carry, smaller (to fit its
    // jaws), its middle at its middle.
    this.apple = new Group();
    const copy = appleModel.clone();
    copy.position.set(0, -0.135, 0);
    copy.traverse((node) => (node.castShadow = true));
    this.apple.add(copy);
    this.apple.scale.setScalar(APPLE);
    this.apple.visible = false;
    scene.add(this.apple, this.group);
    this.pose(this.rest(new Vector3(this.centre.x, this.centre.y + 1.6, this.centre.z + 5)), 0, 0);
  }

  /** You've used the apple here: you throw it to it, from your hand. */
  feed(from: Vector3) {
    if (this.state !== "guarding") return;
    if (this.reducedMotion) return this.away();
    this.state = "feeding";
    this.fed = 0;
    this.caught = false;
    this.from.copy(from);
    const hiss = this.hissing(from);
    const facing = hiss.facing.clone();
    this.lunge = { head: hiss.head.clone().addScaledVector(facing, 0.28), facing, raised: 1 };
    this.catchAt
      .copy(this.lunge.head)
      .addScaledVector(facing, 0.15)
      .addScaledVector(UP, this.mouth - 0.01);
    this.flight = Math.min(1.4, Math.max(0.55, from.distanceTo(this.catchAt) / 7));
    this.apple.visible = true;
  }

  /** Gone (a game loaded with the apple in use here). */
  away() {
    this.state = "away";
    this.group.visible = false;
    this.apple.visible = false;
  }

  /** There, coiled by the door (a game loaded without it). */
  back() {
    this.state = "guarding";
    this.alert = 0;
    this.group.visible = true;
    this.apple.visible = false;
  }

  /**
   * Each frame: watching you (eye: where you're looking from), rearing up as
   * you come near; or catching the apple and going; or, gone, coming back
   * (guard: while it should be there) when you're not looking.
   */
  update(dt: number, eye: Vector3, camera: Camera, guard: boolean) {
    this.time += dt;
    if (this.state === "away") {
      if (!guard || this.seen(camera) || eye.distanceTo(this.centre) < 5) return;
      this.back();
    }
    if (this.state === "guarding") {
      if (eye.distanceTo(this.centre) > FAR) return; // (too far off to see it move)
      const near = eye.distanceTo(this.centre) < NEAR && eye.y > this.centre.y - 3;
      this.alert +=
        Math.sign(Number(near) - this.alert) * Math.min(Math.abs(Number(near) - this.alert), dt * (near ? 3 : 1));
      const a = smooth(this.alert);
      const rest = this.rest(eye);
      const hiss = this.hissing(eye);
      // Its mouth opens as it rears; its tongue flickers now and then, and
      // fast, hissing.
      const jaw = a * (0.16 + 0.03 * Math.sin(this.time * 3)); // (just parted: its tongue does the hissing)
      const flick = Math.sin(this.time * 2.1) > 0.75 ? 1 : 0;
      const tongue = a > 0.5 ? 0.6 + 0.4 * Math.sin(this.time * 23) : flick * (0.5 + 0.5 * Math.sin(this.time * 30));
      this.pose(this.blend(rest, hiss, a), jaw, tongue);
      return;
    }
    if (this.state === "feeding") return this.feeding(dt);
    if (this.state === "leaving") return this.leaving(dt);
  }

  // ---- What it does ------------------------------------------------------------

  private feeding(dt: number) {
    this.fed += dt;
    const t = this.fed;
    const T = this.flight;
    const lunge = this.lunge!;
    const hiss = { ...lunge, head: lunge.head.clone().addScaledVector(lunge.facing, -0.28) };
    if (t < T) {
      // The apple in the air, along an arc, turning over; the snake opens
      // its jaws wide for it, and strikes just as it comes.
      const u = t / T;
      const arc = Math.min(1.2, 0.12 * this.from.distanceTo(this.catchAt) + 0.3);
      this.apple.position.lerpVectors(this.from, this.catchAt, u).addScaledVector(UP, 4 * arc * u * (1 - u));
      this.apple.rotation.set(t * 7, t * 3, 0);
      const strike = smooth((t - (T - 0.22)) / 0.22);
      this.pose(this.blend(hiss, lunge, strike), 0.75 + 0.35 * smooth((t - (T - 0.5)) / 0.35), 0);
      return;
    }
    this.caught = true;
    // Caught: its jaws close on it, it draws back and down to the ground,
    // and it's straight off (quickly: the way's free).
    this.down ??= this.lowered();
    const back = smooth((t - T - 0.05) / 0.3);
    const lower = smooth((t - T - 0.1) / 0.4);
    const pose = this.blend(this.blend(lunge, hiss, back), this.down, lower);
    this.pose(pose, 1.1 - 0.75 * smooth((t - T) / 0.12), 0);
    if (t > T + 0.5) this.slither();
  }

  /** Off it goes, along its own body and then away south-west, round the stone, and west into the trees. */
  private slither() {
    this.state = "leaving";
    this.gone = 0;
    // From the tip of its tail to its nose, as it lies now...
    const lying = this.points.filter((_, k) => k * STEP < this.length).map((p) => p.clone());
    const nose = this.points[this.points.length - 1].clone();
    lying.push(nose);
    // ...and on: ahead, south-west, round the south of the stone that waits
    // to the west of the door (well clear of it: it's lumpy), and west down
    // the knoll among the trees.
    const ahead = this.down!.facing.clone().setY(0).normalize();
    const c = this.centre;
    const ways = [
      nose,
      nose.clone().addScaledVector(ahead, 0.7),
      new Vector3(c.x - 1.5, 0, c.z + 3.5),
      new Vector3(c.x - 4.7, 0, c.z + 6.3),
      new Vector3(c.x - 8.7, 0, c.z + 6.5),
      new Vector3(c.x - 13, 0, c.z + 6),
      new Vector3(c.x - 18, 0, c.z + 6),
      new Vector3(c.x - 24, 0, c.z + 6.5),
    ];
    const on: Vector3[] = [];
    for (let k = 0; k < ways.length - 1; k++) {
      const p0 = ways[Math.max(0, k - 1)];
      const [p1, p2] = [ways[k], ways[k + 1]];
      const p3 = ways[Math.min(ways.length - 1, k + 2)];
      const steps = Math.ceil(p1.distanceTo(p2) / 0.05);
      for (let i = 1; i <= steps; i++) on.push(catmullRom(p0, p1, p2, p3, i / steps));
    }
    // Winding from side to side as it goes (more, once it's under way), on
    // the ground.
    let travelled = 0;
    const winding = on.map((point, k) => {
      const last = k ? on[k - 1] : nose;
      travelled += point.distanceTo(last);
      const side = new Vector3().subVectors(point, last).cross(UP).normalize();
      const p = point
        .clone()
        .addScaledVector(side, 0.15 * smooth((travelled - 0.5) / 3) * Math.sin((travelled / 1.9) * 2 * Math.PI));
      p.y = this.ground(p.x, p.z) ?? nose.y;
      return p;
    });
    this.track = evenly([...lying, ...winding], STEP);
  }

  private leaving(dt: number) {
    this.gone = Math.min(this.gone + dt * SPEED * smooth(this.gone / 0.4 + 0.3), (this.track.length - 1) * STEP);
    const n = this.points.length;
    for (let k = 0; k < n; k++) {
      const u = k + this.gone / STEP; // (the track's points are a STEP apart)
      const i = Math.min(this.track.length - 2, Math.floor(u));
      this.points[k].lerpVectors(this.track[i], this.track[i + 1], Math.min(1, u - i));
      this.grounded[k] = 1;
    }
    this.bend(0.35, 0);
    if (this.track.length - 1 - this.gone / STEP < n) this.away();
  }

  // ---- Its poses ---------------------------------------------------------------

  /** Coiled, its head up a little, watching you. */
  private rest(eye: Vector3): Pose {
    const c = this.centre;
    const head = new Vector3(c.x + 0.12 + 0.02 * Math.sin(this.time * 0.9), c.y + 0.42, c.z + 0.3);
    return { head, facing: this.towards(eye, head, -0.12, 0.05), raised: 1 };
  }

  /** Reared up higher, drawn back to strike, its head turned to your eyes. */
  private hissing(eye: Vector3): Pose {
    const c = this.centre;
    const head = new Vector3(c.x + 0.05 + 0.015 * Math.sin(this.time * 5), c.y + 0.68, c.z + 0.12);
    return { head, facing: this.towards(eye, head, -0.6, 0.35), raised: 1 };
  }

  /** Its head down on the ground ahead of its coil, turned south-west to go. */
  private lowered(): Pose {
    const c = this.centre;
    const head = new Vector3(c.x - 0.2, c.y, c.z + 1);
    head.y = this.ground(head.x, head.z) ?? c.y;
    return { head, facing: new Vector3(-0.8, 0, 0.6).normalize(), raised: 0 };
  }

  /** Facing from its head to your eyes, turned no further than it can from the south, and tilted within reason. */
  private towards(eye: Vector3, head: Vector3, low: number, high: number) {
    const yaw = Math.max(-1.1, Math.min(1.1, Math.atan2(eye.x - head.x, eye.z - head.z)));
    const pitch = Math.max(low, Math.min(high, Math.atan2(eye.y - head.y, Math.hypot(eye.x - head.x, eye.z - head.z))));
    return new Vector3(Math.sin(yaw) * Math.cos(pitch), Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
  }

  private blend(a: Pose, b: Pose, t: number): Pose {
    return {
      head: a.head.clone().lerp(b.head, t),
      facing: a.facing.clone().lerp(b.facing, t).normalize(),
      raised: a.raised + (b.raised - a.raised) * t,
    };
  }

  /**
   * Bends it into a pose: its head where the pose puts it, its neck curving
   * up to it from the outside of its coil, which takes up the rest of it,
   * spiralling in to the tip of its tail.
   */
  private pose(pose: Pose, jaw: number, tongue: number) {
    const c = this.centre;
    const { head, facing, raised } = pose;
    // From its nose back: its head, straight...
    const line: Point[] = [];
    const nose = this.length - this.hinge;
    for (let s = nose; s > 0; s -= 0.02)
      line.push({ at: head.clone().addScaledVector(facing, s), grounded: 1 - raised });
    // ...its neck, from the back of its head down to its coil...
    const start = new Vector3(c.x + COIL, c.y, c.z);
    const out = new Vector3(0, 0, 1); // (the coil's way round, where its neck leaves it)
    const p1 = start
      .clone()
      .addScaledVector(out, 0.3)
      .addScaledVector(UP, 0.22 * raised);
    const p2 = head.clone().addScaledVector(facing, -0.35);
    p2.y = Math.max(p2.y, c.y);
    for (let i = 0; i <= 40; i++) {
      const t = 1 - i / 40;
      const at = bezier(start, p1, p2, head, t);
      line.push({ at, grounded: Math.max(1 - raised, 1 - smooth(t / 0.35)) });
    }
    // ...and round and round its coil, inwards.
    for (let a = 0; ; a += 0.05) {
      const r = Math.max(0.24, COIL - (PITCH * a) / (2 * Math.PI)); // (not so tight it bunches up, uncoiling)
      line.push({ at: new Vector3(c.x + Math.cos(-a) * r, c.y, c.z + Math.sin(-a) * r), grounded: 1 });
      if (a > 30) break;
    }
    // Every STEP along it, from the tip of its tail (some way round the
    // coil); measured back from its nose. (Past its nose, its last point or
    // two are on its nose.)
    const n = this.points.length;
    let i = 1;
    let along = 0; // from its nose to line[i - 1]
    for (let k = n - 1; k >= 0; k--) {
      const u = Math.max(0, this.length - k * STEP);
      let piece = line[i].at.distanceTo(line[i - 1].at);
      while (i < line.length - 1 && along + piece < u) {
        along += piece;
        i++;
        piece = line[i].at.distanceTo(line[i - 1].at);
      }
      const f = piece > 0 ? Math.min(1, (u - along) / piece) : 0;
      this.points[k].lerpVectors(line[i - 1].at, line[i].at, f);
      this.grounded[k] = line[i - 1].grounded + (line[i].grounded - line[i - 1].grounded) * f;
    }
    // (Its coil's height: on the ground, under it.)
    for (let j = 0; j < n; j++) {
      if (this.grounded[j] < 1) continue;
      const p = this.points[j];
      p.y = this.ground(p.x, p.z) ?? p.y;
    }
    this.bend(jaw, tongue);
  }

  /** Bends each piece along its spine (the points, every STEP from the tip of its tail). */
  private bend(jaw: number, tongue: number) {
    const n = this.points.length;
    const { points, tangents, ups, rights } = this;
    for (let k = 0; k < n; k++) {
      tangents[k].subVectors(points[Math.min(n - 1, k + 1)], points[Math.max(0, k - 1)]).normalize();
      // Its back up (or, where it goes straight up, as it was a little
      // further down it).
      const t = tangents[k];
      const up = ups[k].copy(UP).addScaledVector(t, -t.dot(UP));
      if (up.lengthSq() < 0.02 && k > 0) up.copy(ups[k - 1]).addScaledVector(t, -t.dot(ups[k - 1]));
      up.normalize();
      rights[k].crossVectors(t, up);
    }
    // The hinge of its jaws, and its head from there on, rigid.
    const h = Math.min(n - 2, this.hinge / STEP);
    const hi = Math.floor(h);
    const hf = h - hi;
    const hinge = new Vector3().lerpVectors(points[hi], points[hi + 1], hf);
    const ht = tangents[hi]
      .clone()
      .lerp(tangents[hi + 1], hf)
      .normalize();
    const hu = UP.clone().addScaledVector(ht, -ht.dot(UP));
    if (hu.lengthSq() < 0.02) hu.copy(ups[hi]);
    hu.normalize();
    const hr = new Vector3().crossVectors(ht, hu);
    // (Low down, it lifts its head a little, its neck curving up to it:
    // more, with the apple in its jaws, to clear the ground.)
    const raise = this.caught ? 0.07 : 0.01;
    const neck = (s: number) => raise * smooth((s - this.hinge + NECK) / NECK);
    const lift =
      this.grounded[hi] * (this.belly[Math.min(this.belly.length - 1, Math.round(this.hinge / STEP))] + raise);
    hinge.addScaledVector(UP, lift);

    const p = new Vector3();
    const o = new Vector3();
    this.pieces.forEach((piece, which) => {
      const position = piece.mesh.geometry.getAttribute("position") as BufferAttribute;
      const normal = piece.mesh.geometry.getAttribute("normal") as BufferAttribute;
      const count = piece.along.length;
      const opens = which === 1 ? jaw : 0;
      const [cos, sin] = [Math.cos(opens), Math.sin(opens)];
      for (let i = 0; i < count; i++) {
        let s = piece.along[i];
        let x = piece.across[i];
        let y = piece.up[i];
        let ns = piece.normal[i * 3];
        const nx = piece.normal[i * 3 + 1];
        let ny = piece.normal[i * 3 + 2];
        if (which === 1) {
          // The lower jaw, dropped open on its hinge.
          const u = s - this.hinge;
          const v = y - this.mouth;
          s = this.hinge + u * cos + v * sin;
          y = this.mouth - u * sin + v * cos;
          [ns, ny] = [ns * cos + ny * sin, -ns * sin + ny * cos];
        } else if (which === 2) {
          // The tongue, slid out (or in), flickering up and down.
          const out = (tongue - 1) * 0.16;
          const tip = Math.max(0, s - this.length + 0.06);
          s += out;
          y += tongue * tip * 0.5 * Math.sin(this.time * 40);
          if (tongue < 0.05) x *= 0.01; // (and out of sight)
        }
        if (s >= this.hinge) {
          const u = s - this.hinge;
          p.copy(hinge).addScaledVector(ht, u).addScaledVector(hr, x).addScaledVector(hu, y);
          o.set(0, 0, 0).addScaledVector(ht, ns).addScaledVector(hr, nx).addScaledVector(hu, ny);
        } else {
          const f = Math.max(0, Math.min(n - 1.001, s / STEP));
          const k = Math.floor(f);
          const g = f - k;
          const belly = this.belly[Math.min(this.belly.length - 1, Math.round(s / STEP))];
          const grounded = this.grounded[k] + (this.grounded[k + 1] - this.grounded[k]) * g;
          p.lerpVectors(points[k], points[k + 1], g).addScaledVector(UP, grounded * (belly + neck(s)));
          const t = tangents[k];
          const r = rights[k];
          const u = ups[k];
          p.addScaledVector(r, x).addScaledVector(u, y);
          o.set(0, 0, 0).addScaledVector(t, ns).addScaledVector(r, nx).addScaledVector(u, ny);
        }
        position.setXYZ(i, p.x, p.y, p.z);
        o.normalize();
        normal.setXYZ(i, o.x, o.y, o.z);
      }
      position.needsUpdate = true;
      normal.needsUpdate = true;
    });

    // The apple, caught: held in its jaws.
    if (this.caught && this.apple.visible) {
      this.apple.position
        .copy(hinge)
        .addScaledVector(ht, 0.17)
        .addScaledVector(hu, this.mouth - 0.015);
      this.matrix.makeBasis(hr, hu, ht.clone().negate());
      this.apple.quaternion.setFromRotationMatrix(this.matrix).multiply(new Quaternion().setFromAxisAngle(UP, 0.6));
    }
  }

  /** Whether you could see it from where you are (roughly: whether it's in view at all). */
  private seen(camera: Camera) {
    camera.updateMatrixWorld();
    this.matrix.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    this.frustum.setFromProjectionMatrix(this.matrix);
    return this.frustum.intersectsSphere(new Sphere(this.centre.clone().addScaledVector(UP, 0.4), 1.2));
  }
}

/** Points every step along a line, from its start. */
function evenly(line: Vector3[], step: number) {
  const out = [line[0].clone()];
  let i = 1;
  let along = 0; // to line[i - 1]
  for (let u = step; ; u += step) {
    let piece = line[i].distanceTo(line[i - 1]);
    while (along + piece < u && i < line.length - 1) {
      along += piece;
      i++;
      piece = line[i].distanceTo(line[i - 1]);
    }
    if (along + piece < u) return out;
    out.push(new Vector3().lerpVectors(line[i - 1], line[i], piece > 0 ? (u - along) / piece : 0));
  }
}

function bezier(a: Vector3, b: Vector3, c: Vector3, d: Vector3, t: number) {
  const u = 1 - t;
  return new Vector3()
    .addScaledVector(a, u * u * u)
    .addScaledVector(b, 3 * u * u * t)
    .addScaledVector(c, 3 * u * t * t)
    .addScaledVector(d, t * t * t);
}

function catmullRom(p0: Vector3, p1: Vector3, p2: Vector3, p3: Vector3, t: number) {
  const t2 = t * t;
  const t3 = t2 * t;
  return new Vector3()
    .addScaledVector(p0, -0.5 * t3 + t2 - 0.5 * t)
    .addScaledVector(p1, 1.5 * t3 - 2.5 * t2 + 1)
    .addScaledVector(p2, -1.5 * t3 + 2 * t2 + 0.5 * t)
    .addScaledVector(p3, 0.5 * t3 - 0.5 * t2);
}
