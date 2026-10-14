// Climbing the ladder propped under the balcony: "The ladder slips and you
// fall." (PLAN-V3.md: deaths are short scenes from where you stand.) You
// step up to it and start to climb, looking up at the balcony; it judders,
// its foot slides out from under you, and as it goes the camera draws back
// so you see it come down, slowly, its top scraping down under the balcony
// until it lies on the ground. Then done(): the curtain.

import { Box3, type Object3D, type PerspectiveCamera, Quaternion, Vector3 } from "three";

import type { Ground } from "./player";

// The scene's beats, in seconds from walking into it.
const STEP_UP = 0.5; // to the foot of the ladder, turning to it
const CLIMBED = 2.1; // up a few rungs
const JUDDER = 2.6; // it shifts under you
const DOWN = 6.4; // slipping, slowly, to the ground
const AFTER = 7.6; // a moment lying there, then the curtain

const UP_IT = 0.32; // how far up the ladder you get (of its length)
const EYE = 1.45; // your eye above the rung you stand on
const OFF = 0.35; // and out from the ladder
const JOLT = 0.07; // how far its top drops as it judders (of the way down)
// Drawn back to watch, from the side away from the tower: how far from the
// middle of where it falls (to the side, and out the way you came), and how high.
const ASIDE = 6;
const BACK = 6;
const WATCHING_HEIGHT = 3; // above where it lies (or the ground, if that's higher)

export interface Propped {
  foot: Vector3;
  corner: Vector3; // where its top rests, under the balcony
  out: [number, number]; // out from the tower, towards its foot
  model: Object3D;
}

export class Fall {
  private t = 0;
  private thudded = false;
  private readonly from: Vector3;
  private readonly facing: Quaternion;
  private readonly length: number;
  private readonly half: number; // half its thickness, lying flat
  private readonly watch: Vector3;
  private readonly watching: Vector3; // what you look at, drawn back
  private readonly lowest: number; // how high its top comes to rest
  private readonly standing: Vector3; // from its top down to its foot, propped
  private readonly lying: Vector3; // and lying on the ground
  private readonly look = new Vector3();
  private readonly at = new Vector3();

  constructor(
    private ladder: Propped,
    private camera: PerspectiveCamera,
    private ground: Ground,
    /** The tower's middle: you watch from the side away from it. */
    tower: { x: number; z: number },
    private reducedMotion: boolean,
    /** Its foot slides (the judder), and it hits the ground. */
    private sounds: { slip: () => void; thud: () => void },
    private done: () => void
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    // (Its size as it was made, lying along z: before it was stood up.)
    const { rotation } = ladder.model;
    const was = rotation.clone();
    rotation.set(0, 0, 0);
    ladder.model.updateMatrixWorld();
    const size = new Box3().setFromObject(ladder.model).getSize(new Vector3());
    rotation.copy(was);
    this.length = size.z;
    this.half = size.y / 2;
    const { corner, out } = ladder;
    // Lying, its top on the ground under the balcony, and the rest of it out
    // from there on the highest bumps of the ground (or it'd sink into the hill).
    const groundAt = (d: number) => ground(corner.x + out[0] * d, corner.z + out[1] * d) ?? 0;
    this.lowest = groundAt(0) + this.half + 0.03;
    let slope = -Infinity;
    for (let d = 0.5; d <= this.length; d += 0.25) slope = Math.max(slope, (groundAt(d) + this.half - this.lowest) / d);
    this.lying = new Vector3(out[0], slope, out[1]).normalize();
    this.standing = ladder.foot.clone().sub(corner).normalize();
    // Drawn back to watch, to the side away from the tower, looking between
    // where it comes to rest and the balcony it was propped under.
    const middle = new Vector3(corner.x, this.lowest, corner.z).addScaledVector(this.lying, this.length / 2);
    this.watching = middle.clone().lerp(corner, 0.3);
    const side = [out[1], -out[0]];
    const towards = side[0] * (tower.x - corner.x) + side[1] * (tower.z - corner.z) > 0 ? -1 : 1;
    const x = middle.x + side[0] * ASIDE * towards + out[0] * BACK;
    const z = middle.z + side[1] * ASIDE * towards + out[1] * BACK;
    this.watch = new Vector3(x, Math.max(ground(x, z) ?? 0, middle.y) + WATCHING_HEIGHT, z);
  }

  /** Each frame; false once it's over. */
  update(dt: number) {
    if (this.t >= AFTER) return false;
    this.t += dt;
    const t = this.t;
    const { corner, out } = this.ladder;
    // How far down it's come: a little in the judder, then all the way,
    // slowly at first, faster and faster (slowed down to see), to the ground.
    let down = 0;
    if (t > CLIMBED) down = JOLT * ease((t - CLIMBED) / (JUDDER - CLIMBED));
    if (t > JUDDER) {
      const u = Math.min(1, (t - JUDDER) / (DOWN - JUDDER));
      down = JOLT + (1 - JOLT) * u * u;
      if (!this.thudded && u >= 1) {
        this.thudded = true;
        this.sounds.thud();
      }
    }
    if (t > CLIMBED && t - dt <= CLIMBED) this.sounds.slip();
    // (And a little bounce, as it lands.)
    const bounce = t > DOWN && !this.reducedMotion ? Math.sin(Math.min(1, (t - DOWN) / 0.35) * Math.PI) * 0.12 : 0;
    const top = new Vector3(corner.x, corner.y + (this.lowest - corner.y) * down + bounce, corner.z);
    // Its foot, sliding out as it comes down, till it lies on the ground.
    const foot = top
      .clone()
      .addScaledVector(new Vector3().lerpVectors(this.standing, this.lying, down).normalize(), this.length);
    this.place(foot, top, down);

    // You: up to it and up it, riding it as it goes, then drawn back to watch.
    const along = (f: number) =>
      new Vector3().lerpVectors(foot, top, f).add(new Vector3(out[0] * OFF, EYE, out[1] * OFF));
    const climbing = Math.min(1, Math.max(0, (t - STEP_UP) / (CLIMBED - STEP_UP)));
    const rungs = Math.round((this.length * UP_IT) / 0.3);
    const rider = along(0.04 + (UP_IT - 0.04) * ease(climbing));
    if (!this.reducedMotion) rider.y += Math.abs(Math.sin(climbing * rungs * Math.PI)) * 0.05;
    if (t < STEP_UP) rider.lerpVectors(this.from, rider, ease(t / STEP_UP));
    // (Shaken, as it judders, and as it starts to go.)
    if (!this.reducedMotion && t > CLIMBED && t < JUDDER + 0.6) {
      const shake = 0.025 * Math.sin(t * 61) * Math.sin(t * 7.3);
      rider.x += shake * out[1];
      rider.z -= shake * out[0];
      rider.y += shake * 0.6;
    }
    const back = ease((t - JUDDER - 0.3) / 2.4);
    this.at.lerpVectors(rider, this.watch, back);
    // Looking up the ladder to the balcony; drawn back, at the whole ladder.
    this.look.lerpVectors(new Vector3(corner.x, corner.y + 0.6, corner.z), this.watching, back);
    this.camera.position.copy(this.at);
    this.camera.lookAt(this.look);
    if (t < STEP_UP) {
      const turned = this.camera.quaternion.clone();
      this.camera.quaternion.slerpQuaternions(this.facing, turned, ease(t / STEP_UP));
    }
    if (t >= AFTER) this.done();
    return true;
  }

  // Stands it from foot to top (as Ladder.show does), turning a little on
  // itself as it slides, so it doesn't come down too neatly.
  private place(foot: Vector3, top: Vector3, down: number) {
    const { model, out } = this.ladder;
    model.position.lerpVectors(foot, top, 0.5);
    model.rotation.set(0, Math.atan2(-out[0], -out[1]) + 0.12 * down * down, 0, "YXZ");
    model.rotateX(-Math.atan2(top.y - foot.y, Math.hypot(top.x - foot.x, top.z - foot.z)));
    model.rotateZ(0.18 * down * down);
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
