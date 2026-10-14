// The river, flowing: flecks of foam on its water, all along it, carried
// downstream (a little faster in the middle, a little wandering, and fast
// through the narrows, where the way crosses), and coming round again from
// its start once they're past its end. And where things are along it, for
// being swept away in it (swept.ts).

import { BufferAttribute, BufferGeometry, Points, PointsMaterial, type Scene, Vector3 } from "three";

import { speck } from "./shafts";

export const FLOW = 3.2; // metres a second, the current
const FLECKS = 1800; // all along it
const IN_FROM_BANKS = 1.3; // metres in from where its banks come up (at its usual width): where the foam is
const NEAR = 1.5; // metres from your eyes, a fleck's hidden
const RAPIDS = 0.5; // how much faster it flows where it's narrower (1: all of it, as much water through less room)

export class River {
  /** Along it, to each of its points; and its whole length. */
  private readonly lengths: number[] = [0];
  readonly length: number;
  private readonly flecks: Points;
  // (Out from its middle: a share of the way to its edge, -1 to 1.)
  private readonly spots: { s: number; out: number; pace: number; phase: number }[] = [];
  private time = 0;

  constructor(
    scene: Scene,
    /** Its middle, upstream to down ([x, z, and how wide it is there, of its usual width]), its water's height, and how far its banks are from its middle (at its usual width). */
    private river: { line: number[][]; water: number; bank: number },
    private reducedMotion: boolean
  ) {
    const { line } = river;
    for (let k = 1; k < line.length; k++) {
      this.lengths.push(this.lengths[k - 1] + Math.hypot(line[k][0] - line[k - 1][0], line[k][1] - line[k - 1][1]));
    }
    this.length = this.lengths.at(-1)!;
    for (let k = 0; k < FLECKS; k++) {
      this.spots.push({
        s: Math.random() * this.length,
        out: Math.random() * 2 - 1,
        pace: Math.random(),
        phase: Math.random() * Math.PI * 2,
      });
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(new Float32Array(FLECKS * 3), 3));
    this.flecks = new Points(
      geometry,
      new PointsMaterial({
        size: 0.16,
        map: speck(),
        color: "#eef7f8",
        transparent: true,
        opacity: 0.7,
        depthWrite: false,
      })
    );
    this.flecks.frustumCulled = false;
    scene.add(this.flecks);
    this.update(0, new Vector3(0, -1000, 0));
  }

  get water() {
    return this.river.water;
  }

  /** Each frame: the foam carried along (faster in the middle than by the banks); none right in front of your eyes (a big blur). */
  update(dt: number, eye: Vector3) {
    // (With reduced motion, still: but none right in front of your eyes, still.)
    if (this.reducedMotion) dt = 0;
    this.time += dt;
    const positions = this.flecks.geometry.attributes.position as BufferAttribute;
    this.spots.forEach((spot, k) => {
      const middle = 1 - 0.5 * spot.out ** 2;
      const wide = this.wide(spot.s);
      spot.s += dt * FLOW * wide ** -RAPIDS * middle * (0.75 + 0.5 * spot.pace);
      if (spot.s > this.length) spot.s -= this.length;
      const [x, z] = this.at(
        spot.s,
        spot.out * this.half(spot.s) + 0.3 * wide * Math.sin(this.time * 0.6 + spot.phase)
      );
      const y = this.river.water + 0.02;
      const close = Math.hypot(x - eye.x, y - eye.y, z - eye.z) < NEAR;
      positions.setXYZ(k, x, close ? y - 50 : y, z);
    });
    positions.needsUpdate = true;
  }

  /** How wide it is (metres along it), of its usual width. */
  wide(s: number) {
    const { line } = this.river;
    const k = this.segment(s);
    const u = Math.max(0, Math.min(1, (s - this.lengths[k - 1]) / (this.lengths[k] - this.lengths[k - 1])));
    return line[k - 1][2] + (line[k][2] - line[k - 1][2]) * u;
  }

  /** How far from its middle there's open water (metres along it), well in from its banks. */
  half(s: number) {
    return (this.river.bank - IN_FROM_BANKS) * this.wide(s);
  }

  // The segment s is on (from its point k - 1 to k): halving.
  private segment(s: number) {
    let [low, high] = [1, this.river.line.length - 1];
    while (low < high) {
      const mid = (low + high) >> 1;
      if (this.lengths[mid] < s) low = mid + 1;
      else high = mid;
    }
    return low;
  }

  /** A point along it (metres from its start), out from its middle: to its left, looking downstream (or its right, if less than 0). */
  at(s: number, out: number): [number, number] {
    const { line } = this.river;
    const k = this.segment(s);
    const [ax, az] = line[k - 1];
    const [bx, bz] = line[k];
    const long = this.lengths[k] - this.lengths[k - 1];
    const u = Math.max(0, Math.min(1, (s - this.lengths[k - 1]) / long));
    // (Its left, looking downstream along [dx, dz], is [dz, -dx].)
    const dx = (bx - ax) / long;
    const dz = (bz - az) / long;
    return [ax + (bx - ax) * u + dz * out, az + (bz - az) * u - dx * out];
  }

  /** How far along it the nearest point of its middle is to [x, z]. */
  nearest(x: number, z: number) {
    const { line } = this.river;
    let best = { d: Infinity, s: 0 };
    for (let k = 1; k < line.length; k++) {
      const [ax, az] = line[k - 1];
      const [bx, bz] = line[k];
      const long = Math.hypot(bx - ax, bz - az);
      const u = Math.max(0, Math.min(1, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / long ** 2));
      const d = Math.hypot(x - (ax + (bx - ax) * u), z - (az + (bz - az) * u));
      if (d < best.d) best = { d, s: this.lengths[k - 1] + u * long };
    }
    return best.s;
  }
}
