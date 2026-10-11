// You, walking: mouse (or a finger) to look, WASD or the arrow keys (or a
// thumb) to move. You follow the ground and are stopped by trees, rocks and
// walls, which the place's file marks with colliders.

import { Euler, PerspectiveCamera, Vector3 } from "three";

export interface Circle {
  x: number;
  z: number;
  r: number;
}

export interface Box {
  x: number;
  z: number;
  halfX: number;
  halfZ: number;
}

/** The height of the ground at a spot, or undefined off the edge. */
export type Ground = (x: number, z: number) => number | undefined;

/** Whether you can stand at a spot: not in the forest, the river or the moat. */
export type Walkable = (x: number, z: number) => boolean;

const CELL = 16; // metres, for finding the solid things near you

interface Near {
  circles: Circle[];
  boxes: Box[];
}

const EYE = 1.65; // metres above the ground
const WALK = 4.2; // metres a second
const RUN = 8;
const BODY = 0.35; // your own radius, for bumping into things
const LOOK = 0.0022; // radians per pixel of mouse movement
const TOUCH_LOOK = 0.005;

export class Player {
  readonly camera = new PerspectiveCamera(70, 1, 0.1, 3000);
  readonly position = new Vector3();
  yaw = 0; // 0 looks north (-z)
  pitch = 0;
  /** West, east, north and south edges, in three.js's x and z. */
  bounds = { west: -95, east: 95, north: -95, south: 95 };

  private keys = new Set<string>();
  private ground: Ground = () => 0;
  private walkable: Walkable = () => true;
  private near = new Map<string, Near>();
  private stick = { x: 0, y: 0 }; // the thumb's walking stick, -1 to 1
  private bob = 0;

  constructor(private element: HTMLElement) {
    addEventListener("keydown", (event) => this.keys.add(event.code));
    addEventListener("keyup", (event) => this.keys.delete(event.code));
    addEventListener("blur", () => this.keys.clear());
    addEventListener("mousemove", (event) => {
      if (document.pointerLockElement !== element) return;
      this.turn(event.movementX * LOOK, event.movementY * LOOK);
    });
    this.touch();
  }

  get locked() {
    return document.pointerLockElement === this.element;
  }

  standOn(ground: Ground, walkable: Walkable) {
    this.ground = ground;
    this.walkable = walkable;
  }

  /** The solid things, sorted into squares so only those near you are checked. */
  solid(circles: Circle[], boxes: Box[]) {
    this.near.clear();
    // Adds a thing to every square it (or you, touching it) could be in.
    const file = (x0: number, x1: number, z0: number, z1: number, add: (found: Near) => void) => {
      for (let i = Math.floor((x0 - 1) / CELL); i <= Math.floor((x1 + 1) / CELL); i++) {
        for (let j = Math.floor((z0 - 1) / CELL); j <= Math.floor((z1 + 1) / CELL); j++) {
          let found = this.near.get(`${i},${j}`);
          if (!found) this.near.set(`${i},${j}`, (found = { circles: [], boxes: [] }));
          add(found);
        }
      }
    };
    for (const c of circles) file(c.x - c.r, c.x + c.r, c.z - c.r, c.z + c.r, (found) => found.circles.push(c));
    for (const b of boxes) {
      file(b.x - b.halfX, b.x + b.halfX, b.z - b.halfZ, b.z + b.halfZ, (found) => found.boxes.push(b));
    }
  }

  place(x: number, z: number, yaw = 0) {
    this.position.set(x, this.groundAt(x, z) ?? 0, z);
    this.yaw = yaw;
    this.pitch = 0;
  }

  turn(dx: number, dy: number) {
    this.yaw -= dx;
    this.pitch = Math.max(-1.4, Math.min(1.4, this.pitch - dy));
  }

  update(dt: number, reducedMotion: boolean) {
    const forward = this.axis("KeyW", "ArrowUp") - this.axis("KeyS", "ArrowDown") - this.stick.y;
    const right = this.axis("KeyD", "ArrowRight") - this.axis("KeyA", "ArrowLeft") + this.stick.x;
    const speed = this.keys.has("ShiftLeft") || this.keys.has("ShiftRight") ? RUN : WALK;
    const length = Math.min(1, Math.hypot(forward, right));
    if (length > 0.01) {
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

    const bob = reducedMotion || length < 0.01 ? 0 : Math.sin(this.bob) * 0.04;
    this.camera.position.set(this.position.x, this.position.y + EYE + bob, this.position.z);
    this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
  }

  // Moves you, unless it would take you into the forest or the water: then
  // you slide along the edge, as far as you can.
  private step(dx: number, dz: number) {
    const p = this.position;
    const fits = (x: number, z: number) =>
      this.walkable(x, z) &&
      this.walkable(x + BODY, z) &&
      this.walkable(x - BODY, z) &&
      this.walkable(x, z + BODY) &&
      this.walkable(x, z - BODY);
    if (fits(p.x + dx, p.z + dz)) p.set(p.x + dx, p.y, p.z + dz);
    else if (fits(p.x + dx, p.z)) p.x += dx;
    else if (fits(p.x, p.z + dz)) p.z += dz;
  }

  private axis(...codes: string[]) {
    return codes.some((code) => this.keys.has(code)) ? 1 : 0;
  }

  private groundAt(x: number, z: number): number | undefined {
    return this.ground(x, z);
  }

  // Pushes you out of anything solid you've walked into.
  private collide() {
    const p = this.position;
    const near = this.near.get(`${Math.floor(p.x / CELL)},${Math.floor(p.z / CELL)}`) ?? { circles: [], boxes: [] };
    for (const c of near.circles) {
      const dx = p.x - c.x;
      const dz = p.z - c.z;
      const d = Math.hypot(dx, dz);
      const min = c.r + BODY;
      if (d < min && d > 0.0001) {
        p.x = c.x + (dx / d) * min;
        p.z = c.z + (dz / d) * min;
      }
    }
    for (const b of near.boxes) {
      const dx = p.x - b.x;
      const dz = p.z - b.z;
      const ox = b.halfX + BODY - Math.abs(dx);
      const oz = b.halfZ + BODY - Math.abs(dz);
      if (ox > 0 && oz > 0) {
        if (ox < oz) p.x += Math.sign(dx) * ox;
        else p.z += Math.sign(dz) * oz;
      }
    }
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
