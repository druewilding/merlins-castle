// The river, flowing: flecks of foam on its water, all along it, carried
// downstream (a little faster in the middle, a little wandering), and coming
// round again from its start once they're past its end. And where things
// are along it, for being swept away in it (swept.ts).

import { BufferAttribute, BufferGeometry, Points, PointsMaterial, type Scene } from "three";

import { speck } from "./shafts";

export const FLOW = 3.2; // metres a second, the current
const FLECKS = 1800; // all along it
const WIDE = 7.2; // either side of its middle, where they are (its banks come up at 8.5)

export class River {
  /** Along it, to each of its points; and its whole length. */
  private readonly lengths: number[] = [0];
  readonly length: number;
  private readonly flecks: Points;
  private readonly spots: { s: number; out: number; pace: number; phase: number }[] = [];
  private time = 0;

  constructor(
    scene: Scene,
    /** Its middle, upstream to down ([x, z]), and its water's height. */
    private river: { line: number[][]; water: number },
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
        out: (Math.random() * 2 - 1) * WIDE,
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
    this.update(0);
  }

  get water() {
    return this.river.water;
  }

  /** Each frame: the foam carried along (faster in the middle than by the banks). */
  update(dt: number) {
    if (this.reducedMotion && this.time > 0) return;
    this.time += dt || 1e-6;
    const positions = this.flecks.geometry.attributes.position as BufferAttribute;
    this.spots.forEach((spot, k) => {
      const middle = 1 - 0.5 * (spot.out / WIDE) ** 2;
      spot.s += dt * FLOW * middle * (0.75 + 0.5 * spot.pace);
      if (spot.s > this.length) spot.s -= this.length;
      const [x, z] = this.at(spot.s, spot.out + 0.3 * Math.sin(this.time * 0.6 + spot.phase));
      positions.setXYZ(k, x, this.river.water + 0.02, z);
    });
    positions.needsUpdate = true;
  }

  /** A point along it (metres from its start), out from its middle: to its left, looking downstream (or its right, if less than 0). */
  at(s: number, out: number): [number, number] {
    const { line } = this.river;
    // (The segment it's on: halving.)
    let [low, high] = [1, line.length - 1];
    while (low < high) {
      const mid = (low + high) >> 1;
      if (this.lengths[mid] < s) low = mid + 1;
      else high = mid;
    }
    const k = low;
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
