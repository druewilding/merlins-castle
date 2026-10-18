// The drawbridge over the moat (its model: art/blender/land.py), on its
// chains up to the gatehouse: up, till the penny's paid at the toll gate,
// when it's lowered across the water (straight away, its chains paying out,
// and down onto the landing with a bump); and raised again once you've come out
// of the castle and off it. main.ts says when it's wanted down.
//
// It turns on its hinge at the foot of the castle's wall (its model's
// origin), its deck along -z from there; its chains (drawn here: a link for
// each 19 cm, from its holes in the gatehouse to the rings near the
// bridge's tip) are as long as they need to be, the rest wound in.

import {
  InstancedMesh,
  Matrix4,
  MeshStandardMaterial,
  type Object3D,
  Quaternion,
  type Scene,
  TorusGeometry,
  Vector3,
} from "three";

import { PLACES } from "./layout";

export interface DrawbridgeSpot {
  /** Its hinge [x, y, z], at its deck. */
  hinge: number[];
  /** How long it is, and half how wide. */
  length: number;
  half: number;
  /** How far in from its tip its chains are fixed. */
  chain: number;
  /** The chains' holes in the gatehouse, [x, y, z]. */
  anchors: number[][];
  /** Where the guards stand, [x, z] (on the bank, beside the landing). */
  guards: number[][];
  /** The castle's walls: [west, east, north, south]. */
  castle: number[];
}

export const RAISED = 1.52; // radians up from lying across the moat: all but upright, against the gatehouse
const MOVING = 2; // seconds, from up to down (or back): quick, so there's no waiting about
const BUMP = 0.035; // radians it bounces back up, landing
const LINK = 0.19; // metres from one link to the next
const RING = 0.07; // how far up off its deck the chains are fixed

/**
 * Whether it's wanted down: while the penny's paid here (in use at the toll
 * gate); while you're in the castle (however you came in: you can always
 * walk out); and, coming out over it, till you're off it (onto the landing).
 */
export function wantedDown(
  spot: DrawbridgeSpot,
  paid: boolean,
  here: string,
  you: { x: number; z: number },
  lowering: boolean
) {
  if (paid) return true;
  const [west, east, north, south] = spot.castle;
  const place = PLACES.get(here);
  if (place && place.x > west && place.x < east && place.z > north && place.z < south) return true;
  const [x, , z] = spot.hinge;
  return here === "moat" && lowering && Math.abs(you.x - x) < spot.half + 0.6 && you.z > z - spot.length - 0.4;
}

/** How far it's come, from 0 to 1: slow to start, slow to stop, as a heavy bridge on its chains would. */
const eased = (t: number) => t * t * (3 - 2 * t);

export class Drawbridge {
  private from = RAISED;
  private to = RAISED;
  private t = 1; // of the way from one to the other
  private bumping = 1; // of its bounce, landing (1: done)
  private links: InstancedMesh;
  private ends: [Vector3, Vector3][] = [];

  constructor(
    scene: Scene,
    private model: Object3D,
    private spot: DrawbridgeSpot,
    private reducedMotion: boolean,
    /** It starts to move (lowering or raising). */
    private moving: (down: boolean) => void,
    /** It's come down onto the landing. */
    private landed: () => void
  ) {
    model.rotation.x = RAISED;
    const iron = new MeshStandardMaterial({ color: "#37342f", metalness: 0.6, roughness: 0.55 });
    // (Each link an oval ring, along x.)
    const link = new TorusGeometry(0.06, 0.016, 5, 10);
    link.scale(1.6, 1, 1);
    const most = Math.ceil(Math.hypot(spot.length + 1, spot.anchors[0][1] + 1) / LINK) + 2;
    this.links = new InstancedMesh(link, iron, most * spot.anchors.length);
    this.links.castShadow = true;
    this.links.frustumCulled = false;
    scene.add(this.links);
    for (const [x, y, z] of spot.anchors) this.ends.push([new Vector3(x, y, z), new Vector3()]);
    this.chains();
  }

  /** Its angle up from the water, now. */
  get angle() {
    const at = this.from + (this.to - this.from) * eased(this.t);
    return at + BUMP * Math.sin(Math.PI * this.bumping) * (1 - this.bumping);
  }

  /** Whether it's right down, across the moat (and still): to walk on. */
  get down() {
    return this.to === 0 && this.t >= 1;
  }

  /** Whether it's down, or coming down. */
  get lowering() {
    return this.to === 0;
  }

  /** Wanted down, or up: now (loading), or in its own time. */
  set(down: boolean, now = false) {
    const to = down ? 0 : RAISED;
    if (now || this.reducedMotion) {
      this.from = this.to = to;
      this.t = this.bumping = 1;
      return;
    }
    if (to === this.to) return;
    // (From wherever it's got to.)
    this.from = this.angle;
    this.to = to;
    this.t = 0;
    this.bumping = 1;
  }

  update(dt: number) {
    if (this.t < 1) {
      if (this.t === 0) this.moving(this.to === 0);
      this.t = Math.min(1, this.t + (dt * RAISED) / (MOVING * Math.max(0.2, Math.abs(this.to - this.from))));
      if (this.t >= 1 && this.to === 0) {
        this.bumping = 0;
        this.landed();
      }
    } else if (this.bumping < 1) this.bumping = Math.min(1, this.bumping + dt / 0.5);
    this.model.rotation.x = this.angle;
    this.chains();
  }

  /** Each chain, from its hole to its ring on the bridge, taut. */
  private chains() {
    this.model.updateMatrixWorld();
    const { half, length, chain } = this.spot;
    const along = new Vector3();
    const turn = new Quaternion();
    const twist = new Quaternion();
    const place = new Matrix4();
    const one = new Vector3(1, 1, 1);
    const at = new Vector3();
    let n = 0;
    for (const [hole, ring] of this.ends) {
      ring.set(Math.sign(hole.x) * (half - 0.15), RING, -(length - chain));
      this.model.localToWorld(ring);
      along.subVectors(ring, hole);
      const long = along.length();
      along.normalize();
      turn.setFromUnitVectors(new Vector3(1, 0, 0), along);
      const count = Math.max(1, Math.floor(long / LINK));
      for (let k = 0; k <= count && n < this.links.count; k++) {
        // (Every other link turned a quarter round, as they hang in a chain.)
        twist.setFromAxisAngle(along, k % 2 ? Math.PI / 2 : 0).multiply(turn);
        at.copy(ring).addScaledVector(along, -k * LINK);
        this.links.setMatrixAt(n++, place.compose(at, twist, one));
      }
    }
    for (let k = n; k < this.links.count; k++) this.links.setMatrixAt(k, place.makeScale(0, 0, 0));
    this.links.instanceMatrix.needsUpdate = true;
  }
}
