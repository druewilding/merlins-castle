// You, walking: mouse (or a finger) to look, WASD or the arrow keys (or a
// thumb) to move. You follow the ground and are stopped by trees, rocks and
// walls, which the place's file marks with colliders.

import { Euler, PerspectiveCamera, Vector3 } from "three";

export interface Circle {
  x: number;
  z: number;
  r: number;
  /** An obstacle's names (the exits it blocks): walking into it bounces you back. */
  names?: string[];
  /** How far before an obstacle in your way you bump into it. */
  ahead?: number;
  /** No far side to have come from (a way that kills you): it stops you all round. */
  allRound?: boolean;
  /**
   * Going through it kills you: come into it the free way, you can step back
   * and forth in it (only walking into it again from its far side does), until
   * you're in the place it goes from (isIn).
   */
  fatal?: boolean;
  /** The height of its top, if it's low enough to climb onto. */
  top?: number;
  /** The height of its underside, if it's a slab you can walk under (once it's over your head). */
  bottom?: number;
}

export interface Box {
  x: number;
  z: number;
  halfX: number;
  halfZ: number;
  names?: string[];
  /** All round it (rounded at its corners): you're this near it, at most, before you bump into it. */
  ahead?: number;
  /** No far side to have come from (a way that kills you): it stops you all round. */
  allRound?: boolean;
  /**
   * Going through it kills you: come into it the free way, you can step back
   * and forth in it (only walking into it again from its far side does), until
   * you're in the place it goes from (isIn).
   */
  fatal?: boolean;
  top?: number;
}

/** The height of the ground at a spot, or undefined off the edge. */
export type Ground = (x: number, z: number) => number | undefined;

/** Whether you can stand at a spot: not in the forest, the river or the moat. */
export type Walkable = (x: number, z: number) => boolean;

/** A way underground (a tunnel): points [x, z, floor height], and half its width. */
export interface Way {
  half: number;
  points: number[][];
  /** A corridor in a building, rather than a tunnel. */
  indoor?: boolean;
}

/**
 * A hall underground (a cavern, round) or a room in a building (with half
 * its width w and depth d): flat-floored. Being in one is being in its place.
 */
export interface Hall {
  x: number;
  z: number;
  floor: number;
  r: number;
  tall: number;
  w?: number;
  d?: number;
  indoor?: boolean;
}

/** Whether a spot is in a hall, with room for you. */
function inHall(hall: Hall, x: number, z: number) {
  if (hall.w !== undefined && hall.d !== undefined) {
    return Math.abs(x - hall.x) <= hall.w - BODY && Math.abs(z - hall.z) <= hall.d - BODY;
  }
  return Math.hypot(x - hall.x, z - hall.z) <= hall.r - (hall.indoor ? 0 : CAVE_DOORWAY) - BODY;
}

// How far in from a cave's edge its door frames stand (in front of its lumpy
// wall): you stay inside them, or at a doorway's corner you'd step round
// behind its frame.
const CAVE_DOORWAY = 0.5;

/**
 * Where you are when you're off the land (underground, or indoors): the
 * height of the floor, the hall you're in if you're in one, and whether
 * there's a building round you.
 */
export interface Under {
  floor: number;
  hall?: string;
  indoor?: boolean;
}

/**
 * Which of an obstacle's exits you'd be going through it by, from a spot: its
 * names say which way they go ("moat south" is from its north side). From a
 * side with no name, it isn't in your way: a one-way exit.
 */
export function wayThrough(names: string[], ox: number, oz: number, x: number, z: number) {
  return names.find((name) => {
    const direction = name.split(" ")[1];
    if (direction === "north") return z > oz;
    if (direction === "south") return z < oz;
    if (direction === "east") return x < ox;
    return x > ox;
  });
}

/** An obstacle, the same however often it's put back: its exits, and where it is. */
function same(thing: Circle | Box) {
  return `${thing.names?.join() ?? ""} ${thing.x} ${thing.z}`;
}

/** Whether a spot is in a solid thing, or an obstacle's reach (and so far round it). */
function touching(thing: Circle | Box, x: number, z: number, margin: number) {
  const reach = thing.ahead ?? 0;
  if ("r" in thing) return Math.hypot(x - thing.x, z - thing.z) < thing.r + reach + margin;
  if (reach) return outside(thing, x, z).d < reach + margin;
  return Math.abs(x - thing.x) < thing.halfX + margin && Math.abs(z - thing.z) < thing.halfZ + margin;
}

/**
 * How far a spot is outside a box (less than 0 inside it), and which way is
 * straight out of it from there: from the nearest point on it (or, inside,
 * out through the nearest side).
 */
function outside(box: Box, x: number, z: number) {
  const dx = x - box.x;
  const dz = z - box.z;
  const ex = Math.abs(dx) - box.halfX;
  const ez = Math.abs(dz) - box.halfZ;
  if (ex < 0 && ez < 0) {
    return ex > ez ? { d: ex, nx: Math.sign(dx) || 1, nz: 0 } : { d: ez, nx: 0, nz: Math.sign(dz) || 1 };
  }
  const ox = Math.max(ex, 0) * Math.sign(dx);
  const oz = Math.max(ez, 0) * Math.sign(dz);
  const d = Math.hypot(ox, oz);
  return { d, nx: ox / d, nz: oz / d };
}

/** How far a spot is from the middle of a way, its floor there, and whether it's past an end. */
export function nearest(way: Way, x: number, z: number) {
  let best = { d: Infinity, floor: 0, beyond: false };
  const last = way.points.length - 2;
  for (let k = 0; k <= last; k++) {
    const [ax, az, af] = way.points[k];
    const [bx, bz, bf] = way.points[k + 1];
    const dx = bx - ax;
    const dz = bz - az;
    const t = ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz);
    const tc = Math.max(0, Math.min(1, t));
    const d = Math.hypot(x - ax - tc * dx, z - az - tc * dz);
    if (d < best.d) best = { d, floor: af + (bf - af) * tc, beyond: (k === 0 && t < 0) || (k === last && t > 1) };
  }
  return best;
}

/** How near the ground a tunnel's floor must be, at its mouth, to step in or out. */
const LIP = 0.6;
/** How much a floor can rise or fall in one step: more, and it's another floor (above or below). */
const CLIMB = 1.2;

const CELL = 16; // metres, for finding the solid things near you

interface Near {
  circles: Circle[];
  boxes: Box[];
}

const EYE = 1.65; // metres above the ground
const CROUCHED = 1.1; // the eye's height, crouching
const CROUCHING = 0.5; // how much of your speed you have, crouching
const GRAVITY = 9.8; // metres a second, each second
const STEP = 0.4; // metres: you walk up (and down) anything this high, like a stair
const ROOF = 3.2; // a way's floor to its roof (TUNNEL_TALL in art/blender/land.py)
const HEADROOM = 0.15; // how close your eye comes to a roof, jumping
const PROPS = 2.95; // along a way, its timber props' beams (PROP_TALL in art/blender/land.py): a jump stops under them
export const JUMP_HEIGHT = 1.0; // metres, how high a jump lifts you (a game leap, well over a real one)
const FLY_HEIGHT = 35; // metres above the ground, flying
const WALK = 4.2; // metres a second
const RUN = WALK * 3; // the land is big, and the tunnel long
const BODY = 0.35; // your own radius, for bumping into things
const LOOK = 0.0022; // radians per pixel of mouse movement
const TOUCH_LOOK = 0.005;
// Bumping into an obstacle: a soft nudge back off it, easing out and to a
// stop (walking on, you're slow at first, then back to speed), and not
// again while you push on: only once you've stepped back from it.
const NUDGE = 0.18; // metres
const NUDGING = 0.4; // seconds
const EASING_IN = 0.6; // seconds after, walking on into it comes back to speed
const AGAIN = 0.5; // metres back from where you bumped into it, before another
// Footsteps a second, at full speed (slower, going slower: crouching, or
// pushing along a wall), and none walking on into one.
const WALKING_STEPS = 2.1;
const RUNNING_STEPS = 3.2;

export class Player {
  readonly camera = new PerspectiveCamera(70, 1, 0.1, 3000);
  readonly position = new Vector3();
  yaw = 0; // 0 looks north (-z)
  pitch = 0;
  /** West, east, north and south edges, in three.js's x and z. */
  bounds = { west: -95, east: 95, north: -95, south: 95 };
  /** How high a jump lifts you, in metres. */
  jumpHeight = JUMP_HEIGHT;
  // For the debug panel: flying, walking through anything, and going faster.
  ghost = false;
  boost = 1;
  /** Held still while a scene plays out (falling off the ladder): no walking, jumping or looking, and the camera isn't yours. */
  held = false;

  ways: Way[] = [];
  halls = new Map<string, Hall>();
  /** Where you are underground, if you are. */
  under: Under | undefined;
  /** Called when you bounce off an obstacle, with the exit you were trying ("moat south"). */
  onBump: (exit: string) => void = () => {};
  /** Whether you're in the place an exit goes from ("giant west": in the giant's cave). */
  isIn: (exit: string) => boolean = () => false;
  /** Called at each footstep (and landing from a jump), walking or running, and how loud (1 is a step at full speed). */
  onStep: (kind: "walk" | "run", loudness: number) => void = () => {};

  private keys = new Set<string>();
  private ground: Ground = () => 0;
  private walkable: Walkable = () => true;
  private near = new Map<string, Near>();
  /** Solid things that move about (Merlin): wherever they are, each frame. */
  readonly movers: Circle[] = [];
  private nearUnder = new Map<string, Near>();
  private stick = { x: 0, y: 0 }; // the thumb's walking stick, -1 to 1
  private bob = 0;
  private strides = 0; // footsteps taken (the next one at the next whole number)
  // Nudged back off an obstacle: which way, how far into it, and where from (none yet: armed).
  private knock = { x: 0, z: 0, t: NUDGING + EASING_IN, from: undefined as { x: number; z: number } | undefined };
  // One-way obstacles you're going through the free way, until you're out of their reach.
  private passing = new Set<Circle | Box>();
  private before = new Vector3(); // where you were, before this step
  // Turned back at an obstacle you'd come over: what, and where (said once,
  // not again till you've stepped back from there).
  private turned: { thing: Circle | Box; x: number; z: number } | undefined;
  private wasInside = false;
  private flying = false;
  private lift = 0; // how high you are off the ground, jumping
  private rise = 0; // and how fast you're going up (or down)
  private eye = EYE; // lower, crouching
  // Being taken along a path (climbing a ladder), your feet at path(0 to 1).
  private following: { path: (t: number) => Vector3; seconds: number; t: number; done: () => void } | undefined;

  constructor(private element: HTMLElement) {
    addEventListener("keydown", (event) => {
      this.keys.add(event.code);
      if (event.code === "Space" && !event.repeat && !this.held) this.jump();
    });
    // (Letting go is heard first, before anything else: over the ending, or a
    // menu, which keep their keys to themselves. Or a key would stay down.)
    addEventListener("keyup", (event) => this.keys.delete(event.code), true);
    addEventListener("blur", () => this.letGo());
    addEventListener("mousemove", (event) => {
      if (document.pointerLockElement !== element) return;
      this.turn(event.movementX * LOOK, event.movementY * LOOK);
    });
    this.touch();
  }

  get inside() {
    return this.under !== undefined;
  }

  get locked() {
    return document.pointerLockElement === this.element;
  }

  standOn(ground: Ground, walkable: Walkable) {
    this.ground = ground;
    this.walkable = walkable;
  }

  /** The solid things on the land (or underground), sorted into squares so only those near you are checked. */
  solid(circles: Circle[], boxes: Box[], under = false) {
    const near = under ? this.nearUnder : this.near;
    // (What you were going through, the free way, you still are: the same
    // obstacle, put back, when what's open changes, as you come out of the
    // tower past the snake, say.)
    const old = new Set([...near.values()].flatMap((found) => [...found.circles, ...found.boxes]));
    const going = new Set([...this.passing].filter((thing) => old.has(thing)).map(same));
    for (const thing of old) this.passing.delete(thing);
    for (const thing of [...circles, ...boxes]) if (going.has(same(thing))) this.passing.add(thing);
    near.clear();
    // Adds a thing to every square it (or you, touching it) could be in.
    const file = (x0: number, x1: number, z0: number, z1: number, add: (found: Near) => void) => {
      for (let i = Math.floor((x0 - 1) / CELL); i <= Math.floor((x1 + 1) / CELL); i++) {
        for (let j = Math.floor((z0 - 1) / CELL); j <= Math.floor((z1 + 1) / CELL); j++) {
          let found = near.get(`${i},${j}`);
          if (!found) near.set(`${i},${j}`, (found = { circles: [], boxes: [] }));
          add(found);
        }
      }
    };
    for (const c of circles) {
      const r = c.r + (c.ahead ?? 0);
      file(c.x - r, c.x + r, c.z - r, c.z + r, (found) => found.circles.push(c));
    }
    for (const b of boxes) {
      const a = b.ahead ?? 0;
      file(b.x - b.halfX - a, b.x + b.halfX + a, b.z - b.halfZ - a, b.z + b.halfZ + a, (found) => found.boxes.push(b));
    }
  }

  /**
   * Whether nothing solid stands at a spot, on the land or underground, nor
   * any obstacle's reach (where you'd be bounced back): somewhere you could be.
   */
  clear(x: number, z: number, under = false, margin = BODY) {
    const near = (under ? this.nearUnder : this.near).get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
    return !near || ![...near.circles, ...near.boxes].some((thing) => touching(thing, x, z, margin));
  }

  /**
   * Whether a spot is in something solid (a rock, a post, the hut's fire, an
   * obstacle: not its reach round it), on the land or underground. Not in
   * something low enough to stand on (a step, a table): that's a top to put
   * things on.
   */
  inSolid(x: number, z: number, under = false) {
    const near = (under ? this.nearUnder : this.near).get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
    return (
      !!near &&
      [...near.circles, ...near.boxes].some(
        (thing) => thing.top === undefined && touching({ ...thing, ahead: 0 }, x, z, 0)
      )
    );
  }

  /** No keys down (a game started afresh, say): you stop. */
  letGo() {
    this.keys.clear();
  }

  /**
   * Whether nothing solid stands between two spots (a wall, a rock: not an
   * obstacle's reach round it), on the land or underground: for reaching
   * from one to the other. (Not quite all the way: what you reach for may
   * lie against something solid, or on it.) Reaching from as high as
   * `high`, nothing under it is in the way, nor any slab over it: into the
   * tower's chest, say, over its side and under the stairs.
   */
  between(ax: number, az: number, bx: number, bz: number, under = false, high = Infinity) {
    const long = Math.hypot(bx - ax, bz - az);
    const clear = (thing: Circle | Box) =>
      (thing.top ?? Infinity) < high || ("bottom" in thing && (thing.bottom ?? -Infinity) >= high);
    for (let s = 0; s < long - 0.4; s += 0.1) {
      const x = ax + ((bx - ax) * s) / long;
      const z = az + ((bz - az) * s) / long;
      const near = (under ? this.nearUnder : this.near).get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
      if (
        near &&
        [...near.circles, ...near.boxes].some((thing) => !clear(thing) && touching({ ...thing, ahead: 0 }, x, z, 0))
      ) {
        return false;
      }
    }
    return true;
  }

  /** Puts you somewhere: in a hall underground, if the spot's in one. */
  place(x: number, z: number, yaw = 0, floor?: number) {
    // (On a floor underground or indoors, if it says: a hall's, or a way's.)
    this.under = floor === undefined ? this.hallAt(x, z) : (this.underAt(x, z, floor) ?? this.hallAt(x, z));
    this.position.set(x, this.groundAt(x, z) ?? 0, z);
    this.lift = this.rise = 0;
    // (Not climbing any more, or going through anything: somewhere new.)
    this.following = undefined;
    this.knock = { x: 0, z: 0, t: NUDGING + EASING_IN, from: undefined };
    this.passing.clear();
    this.yaw = yaw;
    this.pitch = 0;
  }

  get fly() {
    return this.flying;
  }

  /** Flying: straight up high over the land, and (flying no more) straight back down onto it. */
  set fly(on: boolean) {
    if (on === this.flying) return;
    this.flying = on;
    const { x, z } = this.position;
    if (on) {
      this.under = undefined;
      this.position.y = (this.ground(x, z) ?? 0) + FLY_HEIGHT;
    } else {
      this.under = this.hallAt(x, z);
      this.position.y = this.groundAt(x, z) ?? 0;
    }
    this.lift = this.rise = 0;
  }

  /** Up off the ground, if you're on it. */
  jump() {
    if (this.following || this.flying || this.lift > 0 || this.jumpHeight <= 0) return;
    this.rise = Math.sqrt(2 * GRAVITY * this.jumpHeight);
  }

  turn(dx: number, dy: number) {
    this.yaw -= dx;
    this.pitch = Math.max(-1.4, Math.min(1.4, this.pitch - dy));
  }

  /** Takes you along a path (up a ladder and over), your feet at path(0 to 1), then calls done. */
  follow(path: (t: number) => Vector3, seconds: number, done: () => void) {
    this.following = { path, seconds, t: 0, done };
    this.lift = this.rise = 0;
    this.knock = { x: 0, z: 0, t: NUDGING + EASING_IN, from: undefined };
  }

  /** Whether you're being taken along a path, not walking. */
  get busy() {
    return Boolean(this.following) || this.held;
  }

  update(dt: number, reducedMotion: boolean) {
    if (this.held) return;
    if (this.following) return this.along(dt);
    const forward = this.axis("KeyW", "ArrowUp") - this.axis("KeyS", "ArrowDown") - this.stick.y;
    const right = this.axis("KeyD", "ArrowRight") - this.axis("KeyA", "ArrowLeft") + this.stick.x;
    // (Crouching on Ctrl, or C: Ctrl and W together closes the browser's tab.)
    const crouching = !this.flying && this.axis("ControlLeft", "ControlRight", "KeyC") > 0;
    const running = this.keys.has("ShiftLeft") || this.keys.has("ShiftRight");
    const pace = running ? RUN : WALK;
    const speed = pace * this.boost * (crouching ? CROUCHING : 1);
    const length = Math.min(1, Math.hypot(forward, right));
    if (this.flying) {
      this.flyAbout(dt, speed, forward, right);
      this.camera.position.set(this.position.x, this.position.y + EYE, this.position.z);
      this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
      return;
    }
    this.eye += ((crouching ? CROUCHED : EYE) - this.eye) * Math.min(1, dt * 10);
    this.before.copy(this.position);
    // (The nudge: fastest halfway, so it eases out and to a stop. Stepped
    // back from where it was, you'd be nudged again.)
    const k = this.knock;
    if (k.from && Math.hypot(this.position.x - k.from.x, this.position.z - k.from.z) > AGAIN) k.from = undefined;
    const eased = (t: number) => (1 - Math.cos(Math.PI * Math.min(1, Math.max(0, t)))) / 2;
    const back = eased((k.t - NUDGING) / EASING_IN); // (walking on into it: none at first, then all)
    if (k.t < NUDGING + EASING_IN) {
      const was = eased(k.t / NUDGING);
      k.t = Math.min(NUDGING + EASING_IN, k.t + dt);
      const moved = NUDGE * (eased(k.t / NUDGING) - was);
      if (moved > 0) this.step(k.x * moved, k.z * moved);
    }
    if (length > 0.01) {
      const scale = (speed * dt * length) / Math.hypot(forward, right);
      const sin = Math.sin(this.yaw);
      const cos = Math.cos(this.yaw);
      // Forward is -z when yaw is 0; right is +x.
      let dx = (-sin * forward + cos * right) * scale;
      let dz = (-cos * forward - sin * right) * scale;
      // (Nudged, walking on into it comes back slowly: along it, or away, you're free.)
      const into = -(dx * k.x + dz * k.z);
      if (into > 0) {
        const held = into * (1 - back);
        dx += k.x * held;
        dz += k.z * held;
      }
      this.step(dx, dz);
      this.bob += dt * speed * 1.6;
    }
    this.collide();
    // Holding Space, you hop again as soon as you land (a bunny hop).
    if (this.keys.has("Space") && this.lift === 0 && this.rise === 0) this.jump();
    const landing = this.lift > 0;
    this.upAndDown(dt);
    this.footsteps(dt, running, length, pace, landing && this.lift === 0);

    const bob =
      reducedMotion || length < 0.01 || this.knock.t < NUDGING || this.lift > 0 ? 0 : Math.sin(this.bob) * 0.04;
    this.camera.position.set(this.position.x, this.position.y + this.lift + this.eye + bob, this.position.z);
    this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
  }

  // A footstep each time you've gone a stride (how fast you're really going,
  // on the ground), and one as you land. Setting off, the first comes soon.
  private footsteps(dt: number, running: boolean, length: number, pace: number, landed: boolean) {
    const kind = running ? "run" : "walk";
    if (landed) {
      this.onStep(kind, 1.3);
      this.strides = Math.floor(this.strides) + 0.3;
      return;
    }
    const going = Math.hypot(this.position.x - this.before.x, this.position.z - this.before.z) / dt;
    if (length < 0.01 || this.lift > 0 || going < 0.3) {
      if (this.lift === 0) this.strides = Math.floor(this.strides) + 0.7;
      return;
    }
    const share = Math.min(1, going / (pace * this.boost));
    const was = this.strides;
    this.strides += dt * (running ? RUNNING_STEPS : WALKING_STEPS) * share;
    if (Math.floor(this.strides) > Math.floor(was)) this.onStep(kind, 0.4 + 0.6 * share);
  }

  private along(dt: number) {
    const f = this.following!;
    f.t = Math.min(1, f.t + dt / f.seconds);
    this.position.copy(f.path(f.t));
    this.camera.position.set(this.position.x, this.position.y + this.eye, this.position.z);
    this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
    if (f.t < 1) return;
    this.following = undefined;
    f.done();
    // (After done(): that can close obstacles again, which starts them afresh.)
    this.throughHere();
  }

  /**
   * In an obstacle's reach where you stand (landed over a wall, or it's just
   * closed behind you), you're going through it the free way: no bounce.
   */
  throughHere() {
    const { x, z } = this.position;
    const near = (this.under ? this.nearUnder : this.near).get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
    for (const thing of [...(near?.circles ?? []), ...(near?.boxes ?? [])]) {
      if (thing.names && !thing.allRound && touching(thing, x, z, BODY)) this.passing.add(thing);
    }
  }

  // What you're standing on (the ground, a floor, or a table or a step you've
  // climbed onto), and how high you are above it: jumping, or falling off.
  private upAndDown(dt: number) {
    const p = this.position;
    const ground = this.groundAt(p.x, p.z);
    if (ground === undefined) return;
    const feet = p.y + this.lift;
    const surface = Math.max(ground, this.topUnder(feet));
    if (this.lift > 0 || this.rise > 0) {
      const next = feet + this.rise * dt;
      this.rise -= GRAVITY * dt;
      p.y = surface;
      this.lift = Math.max(0, next - surface);
      if (this.lift === 0) this.rise = 0; // landed
    } else if (surface < p.y - STEP - Math.hypot(p.x - this.before.x, p.z - this.before.z)) {
      // Off the edge (a drop steeper than you went along): falling. (Not
      // down a slope, however fast: running down a steep ramp into a tunnel,
      // you'd fly off it, up into its roof.)
      this.lift = p.y - surface;
      p.y = surface;
    } else {
      // Up a slope or a step, or down one (not ever far behind it).
      p.y = Math.min(p.y + (surface - p.y) * Math.min(1, dt * 12), surface + 0.1);
    }
    // Under a roof, a jump stops at it: jumping where a tunnel drops away
    // steeply, the roof drops with the floor, and would leave you behind.
    // (Or under a slab, at its underside.)
    if (this.under && this.lift > 0) {
      const tall = this.under.hall ? (this.halls.get(this.under.hall)?.tall ?? ROOF) : PROPS;
      const roof = Math.min(this.under.floor + tall, this.slabOver(p.x, p.z, p.y + this.eye));
      const most = Math.max(0, roof - HEADROOM - this.eye - p.y);
      if (this.lift > most) {
        this.lift = most;
        this.rise = Math.min(this.rise, 0);
      }
    }
  }

  // The top of the highest thing under you that you could stand on (up to a
  // step above your feet).
  private topUnder(feet: number) {
    return this.topAt(this.position.x, this.position.z, feet + STEP, !!this.under);
  }

  // The underside of the lowest slab over your head (standing, or jumping).
  private slabOver(x: number, z: number, head: number) {
    const near = this.nearUnder.get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
    let lowest = Infinity;
    for (const c of near?.circles ?? []) {
      if (c.bottom !== undefined && c.bottom >= head && Math.hypot(x - c.x, z - c.z) < c.r + BODY)
        lowest = Math.min(lowest, c.bottom);
    }
    return lowest;
  }

  /**
   * The top of the highest thing at a spot you could stand on (or, off the
   * land, put something on: a step, a table, the chest's tray), up to a
   * height: off the land unless not (on it, a toadstool to jump onto).
   */
  topAt(x: number, z: number, most = Infinity, under = true) {
    const near = (under ? this.nearUnder : this.near).get(`${Math.floor(x / CELL)},${Math.floor(z / CELL)}`);
    let best = -Infinity;
    for (const c of near?.circles ?? []) {
      if (c.top !== undefined && c.top <= most && Math.hypot(x - c.x, z - c.z) < c.r) best = Math.max(best, c.top);
    }
    for (const b of near?.boxes ?? []) {
      if (b.top !== undefined && b.top <= most && Math.abs(x - b.x) < b.halfX && Math.abs(z - b.z) < b.halfZ)
        best = Math.max(best, b.top);
    }
    return best;
  }

  // Flying: forward is wherever you look (up or down, too).
  private flyAbout(dt: number, speed: number, forward: number, right: number) {
    const look = new Vector3(0, 0, -1).applyEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
    const side = new Vector3(Math.cos(this.yaw), 0, -Math.sin(this.yaw));
    const move = look.multiplyScalar(forward).addScaledVector(side, right);
    if (move.lengthSq() > 0.0001) this.position.addScaledVector(move.normalize(), speed * 1.5 * dt);
    // Flying is over the land, unless you're between a hall's floor and its
    // roof: then you're in it, with its light (and not under the sun).
    const p = this.position;
    const hall = this.hallAt(p.x, p.z);
    const tall = hall?.hall ? (this.halls.get(hall.hall)?.tall ?? 0) : 0;
    this.under = hall && p.y > hall.floor - 0.5 && p.y < hall.floor + tall ? hall : undefined;
    const ground = this.groundAt(this.position.x, this.position.z) ?? 0;
    this.position.y = Math.max(this.position.y, ground);
    this.keepInside();
  }

  // Moves you, unless it would take you into the forest or the water (or a
  // tunnel's wall): then you slide along the edge, as far as you can.
  private step(dx: number, dz: number) {
    const p = this.position;
    if (this.ghost) {
      p.set(p.x + dx, p.y, p.z + dz);
      // Off the land, still follow the floor (up and down stairs), where there is one.
      if (this.under) this.under = this.underAt(p.x, p.z, this.under.floor) ?? this.under;
      return;
    }
    for (const [x, z] of [
      [p.x + dx, p.z + dz],
      [p.x + dx, p.z],
      [p.x, p.z + dz],
    ]) {
      const where = this.fits(x, z);
      if (where === false) continue;
      p.x = x;
      p.z = z;
      this.under = where;
      return;
    }
  }

  // Whether you can stand somewhere, and if so whether that's on the land
  // (undefined) or underground.
  private fits(x: number, z: number): Under | undefined | false {
    const onLand = () =>
      this.walkable(x, z) &&
      this.walkable(x + BODY, z) &&
      this.walkable(x - BODY, z) &&
      this.walkable(x, z + BODY) &&
      this.walkable(x, z - BODY);
    const nearGround = (floor: number) => Math.abs(floor - (this.ground(x, z) ?? floor)) < LIP;
    if (this.under) {
      const floor = this.under.floor;
      const here = this.underAt(x, z, floor);
      if (here) return here;
      // Out of a way's end, at a mouth, onto the land.
      const out = this.ways.some((way) => {
        const n = nearest(way, x, z);
        return n.beyond && n.d <= way.half && Math.abs(n.floor - floor) < CLIMB && nearGround(n.floor);
      });
      return out && onLand() ? undefined : false;
    }
    // Into a way, at the top of its ramp.
    for (const way of this.ways) {
      const n = nearest(way, x, z);
      if (!n.beyond && n.d <= way.half - BODY && nearGround(n.floor)) return { floor: n.floor, indoor: way.indoor };
    }
    return onLand() ? undefined : false;
  }

  /** The hall a spot is in, if any (for being put straight into one). */
  hallAt(x: number, z: number): Under | undefined {
    for (const [place, hall] of this.halls) {
      if (inHall(hall, x, z)) return { floor: hall.floor, hall: place, indoor: hall.indoor };
    }
    return undefined;
  }

  // Where you'd be underground at a spot, going on from a floor: in a hall,
  // or in a way (the one nearest that floor, where they cross).
  private underAt(x: number, z: number, floor: number): Under | undefined {
    for (const [place, hall] of this.halls) {
      if (Math.abs(hall.floor - floor) < CLIMB && inHall(hall, x, z)) {
        return { floor: hall.floor, hall: place, indoor: hall.indoor };
      }
    }
    let best: Under | undefined;
    for (const way of this.ways) {
      const n = nearest(way, x, z);
      if (n.beyond || n.d > way.half - BODY || Math.abs(n.floor - floor) >= CLIMB) continue;
      if (!best || Math.abs(n.floor - floor) < Math.abs(best.floor - floor)) {
        best = { floor: n.floor, indoor: way.indoor };
      }
    }
    return best;
  }

  private axis(...codes: string[]) {
    return codes.some((code) => this.keys.has(code)) ? 1 : 0;
  }

  private groundAt(x: number, z: number): number | undefined {
    return this.under ? this.under.floor : this.ground(x, z);
  }

  /** The floor underground at a spot, going on from where you stand (or nothing: not a way or a hall). */
  floorAt(x: number, z: number) {
    return this.underAt(x, z, this.position.y)?.floor;
  }

  /** How far below the land you are: 0 on it, more the deeper you go. */
  get depth() {
    return Math.max(0, (this.ground(this.position.x, this.position.z) ?? 0) - this.position.y);
  }

  // Pushes you out of anything solid you've walked into.
  private collide() {
    const p = this.position;
    if (this.ghost) return this.keepInside();
    const square = `${Math.floor(p.x / CELL)},${Math.floor(p.z / CELL)}`;
    const near = (this.under ? this.nearUnder : this.near).get(square) ?? { circles: [], boxes: [] };
    // Coming up out of a tunnel, you're going through its mouth the free way.
    const cameOut = this.wasInside && !this.under;
    this.wasInside = this.inside;
    // (Anything you're above, or a step below, you go over, not into.)
    const feet = p.y + this.lift;
    const below = (thing: Circle | Box) => thing.top !== undefined && feet >= thing.top - STEP;
    // (And a slab over your head, you go under.)
    const over = (thing: Circle) => thing.bottom !== undefined && feet + this.eye + HEADROOM <= thing.bottom;
    for (const c of [...near.circles, ...this.movers]) {
      if (below(c) || over(c)) continue;
      const dx = p.x - c.x;
      const dz = p.z - c.z;
      const d = Math.hypot(dx, dz);
      const min = c.r + (c.ahead ?? 0) + BODY;
      const exit = this.blocking(c, d < min, cameOut);
      if (exit === null && d < min) this.turnedBack(c);
      if (exit === null) continue;
      if (d < min && d > 0.0001) {
        p.x = c.x + (dx / d) * min;
        p.z = c.z + (dz / d) * min;
        if (exit) this.bounce(exit, dx / d, dz / d);
      }
    }
    for (const b of near.boxes) {
      if (below(b)) continue;
      const reach = b.ahead ?? 0;
      if (reach) {
        // An obstacle: its reach all round it, rounded at its corners; out
        // of it straight away from it.
        const out = outside(b, p.x, p.z);
        const min = reach + BODY;
        const exit = this.blocking(b, out.d < min, cameOut);
        if (exit === null && out.d < min) this.turnedBack(b);
        if (exit === null || out.d >= min) continue;
        p.x += out.nx * (min - out.d);
        p.z += out.nz * (min - out.d);
        if (exit) this.bounce(exit, out.nx, out.nz);
        continue;
      }
      const dx = p.x - b.x;
      const dz = p.z - b.z;
      const ox = b.halfX + BODY - Math.abs(dx);
      const oz = b.halfZ + BODY - Math.abs(dz);
      const exit = this.blocking(b, ox > 0 && oz > 0, cameOut);
      if (exit === null && ox > 0 && oz > 0) this.turnedBack(b);
      if (exit === null) continue;
      if (ox > 0 && oz > 0) {
        // Out the side you came in by (so coming at an obstacle from the side, you slide off it).
        const alongX = ox < oz;
        if (alongX) p.x += Math.sign(dx) * ox;
        else p.z += Math.sign(dz) * oz;
        if (exit) this.bounce(exit, alongX ? Math.sign(dx) : 0, alongX ? 0 : Math.sign(dz));
      }
    }
    this.keepInside();
  }

  // What a solid thing does to you: an obstacle in your way blocks you (and
  // says which exit you were trying); one you're going through the free way
  // doesn't (null), all the way through, even past its middle; anything else
  // just blocks you ("").
  private blocking(thing: Circle | Box, within: boolean, cameOut: boolean): string | null {
    if (!thing.names) return "";
    if (!this.passing.has(thing) && !(cameOut && within)) {
      const exit = thing.allRound
        ? thing.names[0]
        : wayThrough(thing.names, thing.x, thing.z, this.position.x, this.position.z);
      if (exit) return exit;
    }
    if (within) this.passing.add(thing);
    else this.passing.delete(thing);
    return null;
  }

  // Going through an obstacle the free way, once you're past its middle you
  // can't turn back through it: a step back towards it stops, and it says why
  // (no bounce: you're already in its reach, maybe right by it, landed over a wall).
  // One that kills you, you can step back through, until you're in the place
  // it goes from: then a step back towards it is going that way.
  private turnedBack(thing: Circle | Box) {
    const p = this.position;
    const exit = thing.names && wayThrough(thing.names, thing.x, thing.z, p.x, p.z);
    if (!exit || (thing.fatal && !this.isIn(exit))) return;
    const b = this.before;
    // (Not the step across its middle, going on: only one back, on this side.)
    if (wayThrough(thing.names!, thing.x, thing.z, b.x, b.z) !== exit) return;
    if ("r" in thing) {
      if (Math.hypot(p.x - thing.x, p.z - thing.z) >= Math.hypot(b.x - thing.x, b.z - thing.z)) return;
      p.x = b.x;
      p.z = b.z;
    } else if (/ (east|west)$/.test(exit)) {
      // (Across it the way its exit goes, east or west: not by its shape. The
      // moat's, from the bank to the wall, is longer than it's wide.)
      if (Math.abs(p.x - thing.x) >= Math.abs(b.x - thing.x)) return;
      p.x = b.x;
    } else {
      if (Math.abs(p.z - thing.z) >= Math.abs(b.z - thing.z)) return;
      p.z = b.z;
    }
    const was = this.turned;
    if (was?.thing === thing && Math.hypot(p.x - was.x, p.z - was.z) < AGAIN) return;
    this.turned = { thing, x: p.x, z: p.z };
    this.onBump(exit);
  }

  // Off an obstacle, the way you came (once, until you've stopped).
  private bounce(exit: string, nx: number, nz: number) {
    if (this.knock.from) return;
    this.knock = { x: nx, z: nz, t: 0, from: { x: this.position.x, z: this.position.z } };
    this.onBump(exit);
  }

  // The edge of the world.
  private keepInside() {
    const p = this.position;
    p.x = Math.max(this.bounds.west, Math.min(this.bounds.east, p.x));
    p.z = Math.max(this.bounds.north, Math.min(this.bounds.south, p.z));
  }

  // On a touch screen: the left half is a walking stick, the right half looks.
  private touch() {
    const fingers = new Map<number, { x: number; y: number; walk: boolean }>();
    this.element.addEventListener(
      "touchstart",
      (event) => {
        for (const t of Array.from(event.changedTouches)) {
          fingers.set(t.identifier, { x: t.clientX, y: t.clientY, walk: t.clientX < innerWidth / 2 });
        }
        event.preventDefault();
      },
      { passive: false }
    );
    this.element.addEventListener(
      "touchmove",
      (event) => {
        for (const t of Array.from(event.changedTouches)) {
          const f = fingers.get(t.identifier);
          if (!f) continue;
          if (f.walk) {
            this.stick.x = Math.max(-1, Math.min(1, (t.clientX - f.x) / 60));
            this.stick.y = Math.max(-1, Math.min(1, (t.clientY - f.y) / 60));
          } else {
            this.turn((t.clientX - f.x) * TOUCH_LOOK, (t.clientY - f.y) * TOUCH_LOOK);
            f.x = t.clientX;
            f.y = t.clientY;
          }
        }
        event.preventDefault();
      },
      { passive: false }
    );
    const end = (event: TouchEvent) => {
      for (const t of Array.from(event.changedTouches)) {
        if (fingers.get(t.identifier)?.walk) this.stick = { x: 0, y: 0 };
        fingers.delete(t.identifier);
      }
    };
    this.element.addEventListener("touchend", end);
    this.element.addEventListener("touchcancel", end);
  }
}
