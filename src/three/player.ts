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
}

export interface Box {
  x: number;
  z: number;
  halfX: number;
  halfZ: number;
  names?: string[];
  /** Only on the sides you'd go through it from (along its thinner side), so not along a wall. */
  ahead?: number;
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
  return Math.hypot(x - hall.x, z - hall.z) <= hall.r - BODY;
}

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
export const JUMP_HEIGHT = 0.6; // metres, how high a jump lifts you (a game hop, more than a real one)
const FLY_HEIGHT = 35; // metres above the ground, flying
const WALK = 4.2; // metres a second
const RUN = WALK * 3; // the land is big, and the tunnel long
const BODY = 0.35; // your own radius, for bumping into things
const LOOK = 0.0022; // radians per pixel of mouse movement
const TOUCH_LOOK = 0.005;
const BOUNCE = 5; // metres a second, back off an obstacle, slowing to a stop in about half a metre

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

  ways: Way[] = [];
  halls = new Map<string, Hall>();
  /** Where you are underground, if you are. */
  under: Under | undefined;
  /** Called when you bounce off an obstacle, with the exit you were trying ("moat south"). */
  onBump: (exit: string) => void = () => {};

  private keys = new Set<string>();
  private ground: Ground = () => 0;
  private walkable: Walkable = () => true;
  private near = new Map<string, Near>();
  private nearUnder = new Map<string, Near>();
  private stick = { x: 0, y: 0 }; // the thumb's walking stick, -1 to 1
  private bob = 0;
  private knock = { x: 0, z: 0 }; // bouncing back off an obstacle
  // One-way obstacles you're going through the free way, until you're out of their reach.
  private passing = new Set<Circle | Box>();
  private wasInside = false;
  private flying = false;
  private lift = 0; // how high you are off the ground, jumping
  private rise = 0; // and how fast you're going up (or down)
  private eye = EYE; // lower, crouching

  constructor(private element: HTMLElement) {
    addEventListener("keydown", (event) => {
      this.keys.add(event.code);
      if (event.code === "Space" && !event.repeat) this.jump();
    });
    addEventListener("keyup", (event) => this.keys.delete(event.code));
    addEventListener("blur", () => this.keys.clear());
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
    near.clear();
    this.passing.clear();
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

  /** Puts you somewhere: in a hall underground, if the spot's in one. */
  place(x: number, z: number, yaw = 0) {
    this.under = this.hallAt(x, z);
    this.position.set(x, this.groundAt(x, z) ?? 0, z);
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
    if (this.flying || this.lift > 0 || this.jumpHeight <= 0) return;
    this.rise = Math.sqrt(2 * GRAVITY * this.jumpHeight);
  }

  turn(dx: number, dy: number) {
    this.yaw -= dx;
    this.pitch = Math.max(-1.4, Math.min(1.4, this.pitch - dy));
  }

  update(dt: number, reducedMotion: boolean) {
    const forward = this.axis("KeyW", "ArrowUp") - this.axis("KeyS", "ArrowDown") - this.stick.y;
    const right = this.axis("KeyD", "ArrowRight") - this.axis("KeyA", "ArrowLeft") + this.stick.x;
    // (Crouching on Ctrl, or C: Ctrl and W together closes the browser's tab.)
    const crouching = !this.flying && this.axis("ControlLeft", "ControlRight", "KeyC") > 0;
    const pace = this.keys.has("ShiftLeft") || this.keys.has("ShiftRight") ? RUN : WALK;
    const speed = pace * this.boost * (crouching ? CROUCHING : 1);
    const length = Math.min(1, Math.hypot(forward, right));
    if (this.flying) {
      this.flyAbout(dt, speed, forward, right);
      this.camera.position.set(this.position.x, this.position.y + EYE, this.position.z);
      this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
      return;
    }
    this.eye += ((crouching ? CROUCHED : EYE) - this.eye) * Math.min(1, dt * 10);
    if (this.rise !== 0 || this.lift > 0) {
      this.lift += this.rise * dt;
      this.rise -= GRAVITY * dt;
      if (this.lift <= 0) this.lift = this.rise = 0;
    }
    const bouncing = Math.hypot(this.knock.x, this.knock.z) > 0.5;
    if (bouncing) {
      this.step(this.knock.x * dt, this.knock.z * dt);
      const fade = Math.exp(-dt * 8);
      this.knock.x *= fade;
      this.knock.z *= fade;
    } else if (length > 0.01) {
      const scale = (speed * dt * length) / Math.hypot(forward, right);
      const sin = Math.sin(this.yaw);
      const cos = Math.cos(this.yaw);
      // Forward is -z when yaw is 0; right is +x.
      this.step((-sin * forward + cos * right) * scale, (-cos * forward - sin * right) * scale);
      this.bob += dt * speed * 1.6;
    }
    this.collide();
    const ground = this.groundAt(this.position.x, this.position.z);
    if (ground !== undefined) this.position.y += (ground - this.position.y) * Math.min(1, dt * 12);

    const bob = reducedMotion || length < 0.01 || bouncing || this.lift > 0 ? 0 : Math.sin(this.bob) * 0.04;
    this.camera.position.set(this.position.x, this.position.y + this.lift + this.eye + bob, this.position.z);
    this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
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
    for (const c of near.circles) {
      const dx = p.x - c.x;
      const dz = p.z - c.z;
      const d = Math.hypot(dx, dz);
      const min = c.r + (c.ahead ?? 0) + BODY;
      const exit = this.blocking(c, d < min, cameOut);
      if (exit === null) continue;
      if (d < min && d > 0.0001) {
        p.x = c.x + (dx / d) * min;
        p.z = c.z + (dz / d) * min;
        if (exit) this.bounce(exit, dx / d, dz / d);
      }
    }
    for (const b of near.boxes) {
      const reach = b.ahead ?? 0;
      const dx = p.x - b.x;
      const dz = p.z - b.z;
      const ox = b.halfX + (b.halfX < b.halfZ ? reach : 0) + BODY - Math.abs(dx);
      const oz = b.halfZ + (b.halfX < b.halfZ ? 0 : reach) + BODY - Math.abs(dz);
      const exit = this.blocking(b, ox > 0 && oz > 0, cameOut);
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
      const exit = wayThrough(thing.names, thing.x, thing.z, this.position.x, this.position.z);
      if (exit) return exit;
    }
    if (within) this.passing.add(thing);
    else this.passing.delete(thing);
    return null;
  }

  // Off an obstacle, the way you came (once, until you've stopped).
  private bounce(exit: string, nx: number, nz: number) {
    if (Math.hypot(this.knock.x, this.knock.z) > 0.5) return;
    this.knock = { x: nx * BOUNCE, z: nz * BOUNCE };
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
