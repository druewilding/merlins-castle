// Climbing the ladder propped under the balcony: "The ladder slips and you
// fall." (PLAN-V3.md: deaths are short scenes from where you stand.) You
// step up to it and start to climb, looking up at the balcony; it judders,
// its foot slides out from under you, and as it goes the camera draws back
// so you see it come down, slowly, its top scraping down under the balcony
// until it lies on the ground (on the edge of the rise under the balcony,
// and down the slope from there). The curtain comes down over the end of it
// (from a little before `ends`).

import { Box3, type Object3D, type PerspectiveCamera, Quaternion, Vector3 } from "three";

import type { Ground } from "./player";

// The scene's beats, in seconds from walking into it.
const STEP_UP = 0.5; // to the foot of the ladder, turning to it
const CLIMBED = 2.1; // up a few rungs
const JUDDER = 2.6; // it shifts under you
const DOWN = 6.4; // slipping, slowly, to the ground
const ENDS = 6.9; // landed, and bounced

const UP_IT = 0.32; // how far up the ladder you get (of its length)
const EYE = 1.45; // your eye above the rung you stand on
const OFF = 0.35; // and out from the ladder
const JOLT = 0.04; // how far its foot slides as it judders (of the way out)
const SLID = 0.8; // metres past its length from the wall, its foot comes to rest
// Drawn back to watch, from the side away from the tower: how far round
// from straight out the way you came (radians), how far from the middle of
// where it falls, and how high above it (or the ground, if that's higher).
// The first of these from which you can see all of it (no hill in the way).
const ROUND = [0.8, 0.55, 1.05, 0.3, 1.3];
const AWAY = [8.5, 10.5];
const HIGH = [3, 4, 5, 6.5, 8];

export interface Propped {
  foot: Vector3;
  corner: Vector3; // where its top rests, under the balcony
  out: [number, number]; // out from the tower, towards its foot
  model: Object3D;
}

export class Fall {
  readonly ends = ENDS;
  private t = 0;
  private thudded = false;
  private readonly from: Vector3;
  private readonly facing: Quaternion;
  private readonly length: number;
  private readonly half: number; // half its thickness, lying flat
  private readonly wide: number; // half its width, rail to rail
  private readonly watch: Vector3;
  private readonly watching: Vector3; // what you look at, drawn back
  private readonly run: number; // how far out its foot is, propped (from under its top)
  private readonly look = new Vector3();
  private readonly at = new Vector3();

  constructor(
    private ladder: Propped,
    private camera: PerspectiveCamera,
    private ground: Ground,
    /** The tower's middle: you watch from the side away from it. */
    tower: { x: number; z: number },
    private reducedMotion: boolean,
    /** It hits the ground. */
    private thud: () => void
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
    this.wide = size.x / 2;
    const { corner, out } = ladder;
    this.run = Math.hypot(ladder.foot.x - corner.x, ladder.foot.z - corner.z);
    // Drawn back to watch, to the side away from the tower, looking between
    // where it comes to rest and the balcony it was propped under.
    const lying = this.pose(1);
    const middle = lying.foot.clone().lerp(lying.top, 0.5);
    this.watching = middle.clone().lerp(corner, 0.3);
    const side = [out[1], -out[0]];
    const towards = side[0] * (tower.x - corner.x) + side[1] * (tower.z - corner.z) > 0 ? -1 : 1;
    const propped = this.pose(0);
    const seen = [0, 0.25, 0.5, 0.75, 1].flatMap((f) => [
      lying.foot.clone().lerp(lying.top, f),
      propped.foot.clone().lerp(propped.top, f),
    ]);
    // (Nothing but air between here and there: the ground under the line all
    // the way, but for the last bit, where the ladder lies on it.)
    const sees = (from: Vector3, to: Vector3) => {
      for (let f = 0.04; f < 0.93; f += 0.03) {
        const p = from.clone().lerp(to, f);
        if (p.y < (ground(p.x, p.z) ?? 0) + 0.05) return false;
      }
      return true;
    };
    const spot = (high: number, round: number, away: number) => {
      const x = middle.x + (out[0] * Math.cos(round) + side[0] * towards * Math.sin(round)) * away;
      const z = middle.z + (out[1] * Math.cos(round) + side[1] * towards * Math.sin(round)) * away;
      return new Vector3(x, Math.max(ground(x, z) ?? 0, middle.y) + high, z);
    };
    const spots = HIGH.flatMap((high) => ROUND.flatMap((round) => AWAY.map((away) => spot(high, round, away))));
    this.watch = spots.find((watch) => seen.every((p) => sees(watch, p))) ?? spots[0];
  }

  /** Each frame. */
  update(dt: number) {
    this.t += dt;
    const t = this.t;
    const { corner, out } = this.ladder;
    // How far out its foot's slid: a little in the judder, then all the
    // way, slowly at first, faster and faster (slowed down, to see), till it's
    // on the ground.
    let down = 0;
    if (t > CLIMBED) down = JOLT * ease((t - CLIMBED) / (JUDDER - CLIMBED));
    if (t > JUDDER) {
      const u = Math.min(1, (t - JUDDER) / (DOWN - JUDDER));
      down = JOLT + (1 - JOLT) * u * u;
      if (!this.thudded && u >= 1) {
        this.thudded = true;
        this.thud();
      }
    }
    const { foot, top } = this.pose(down);
    // (And a little bounce, as it lands.)
    if (t > DOWN && !this.reducedMotion) {
      const bounce = Math.sin(Math.min(1, (t - DOWN) / 0.35) * Math.PI) * 0.1;
      foot.y += bounce;
      top.y += bounce;
    }
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
  }

  /**
   * Where it is, its foot slid down (0, propped) of the way out to where it
   * comes to rest (1): its foot on the ground, and the ladder leaning back
   * towards the tower as low as it can, without its top going past the wall
   * (so it slides down it) or any of it going into the ground (so it comes
   * to rest on the edge of the rise). Lying (down 1), its side's thickness
   * over the ground.
   */
  private pose(down: number) {
    const { corner, out } = this.ladder;
    const over = (this.half + 0.04) * down;
    const reach = this.run + (this.length + SLID - this.run) * down;
    const foot = new Vector3(corner.x + out[0] * reach, 0, corner.z + out[1] * reach);
    foot.y = this.under(foot) + over;
    // (Leaning back at an angle up from the ground: its top at a.)
    const at = (angle: number) =>
      foot
        .clone()
        .add(
          new Vector3(-out[0] * Math.cos(angle), Math.sin(angle), -out[1] * Math.cos(angle)).multiplyScalar(this.length)
        );
    const clear = (angle: number) => {
      const top = at(angle);
      for (let s = 0.3; s <= this.length; s += 0.2) {
        const p = foot.clone().lerp(top, s / this.length);
        if (p.y < this.under(p) + over) return false;
      }
      return true;
    };
    // Steep enough to stay on this side of the wall, and above the ground (the
    // higher it leans, the higher it is everywhere along it: so, halving).
    const wall = Math.acos(Math.min(1, reach / this.length));
    let [low, high] = [-0.6, Math.PI / 2];
    for (let k = 0; k < 16; k++) {
      const mid = (low + high) / 2;
      if (clear(mid)) high = mid;
      else low = mid;
    }
    return { foot, top: at(Math.max(wall, high)) };
  }

  /** The ground under it there: under either rail, whichever's higher (on a slope sideways, one is). */
  private under(p: Vector3) {
    const [ox, oz] = this.ladder.out;
    const at = (side: number) => this.ground(p.x + oz * side * this.wide, p.z - ox * side * this.wide) ?? 0;
    return Math.max(at(-1), at(0), at(1)) + 0.02;
  }

  // Stands it from foot to top (as Ladder.show does), rolling a little onto
  // one side as it slides, so it doesn't come down too neatly.
  private place(foot: Vector3, top: Vector3, down: number) {
    const { model, out } = this.ladder;
    model.position.lerpVectors(foot, top, 0.5);
    model.rotation.set(0, Math.atan2(-out[0], -out[1]), 0, "YXZ");
    model.rotateX(-Math.atan2(top.y - foot.y, Math.hypot(top.x - foot.x, top.z - foot.z)));
    model.rotateZ(0.12 * down * down);
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
