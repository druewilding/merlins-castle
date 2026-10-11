// You, walking: mouse (or a finger) to look, WASD or the arrow keys (or a
// thumb) to move. You follow the ground and are stopped by trees, rocks and
// walls, which the place's file marks with colliders.

import { Euler, type Object3D, PerspectiveCamera, Raycaster, Vector3 } from "three";

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
  circles: Circle[] = [];
  boxes: Box[] = [];
  bounds = 95;

  private keys = new Set<string>();
  private ray = new Raycaster();
  private down = new Vector3(0, -1, 0);
  private ground: Object3D[] = [];
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

  standOn(ground: Object3D[]) {
    this.ground = ground;
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
      this.position.x += (-sin * forward + cos * right) * scale;
      this.position.z += (-cos * forward - sin * right) * scale;
      this.bob += dt * speed * 1.6;
    }
    this.collide();
    const ground = this.groundAt(this.position.x, this.position.z);
    if (ground !== undefined) this.position.y += (ground - this.position.y) * Math.min(1, dt * 12);

    const bob = reducedMotion || length < 0.01 ? 0 : Math.sin(this.bob) * 0.04;
    this.camera.position.set(this.position.x, this.position.y + EYE + bob, this.position.z);
    this.camera.quaternion.setFromEuler(new Euler(this.pitch, this.yaw, 0, "YXZ"));
  }

  private axis(...codes: string[]) {
    return codes.some((code) => this.keys.has(code)) ? 1 : 0;
  }

  private groundAt(x: number, z: number): number | undefined {
    this.ray.set(new Vector3(x, 500, z), this.down);
    return this.ray.intersectObjects(this.ground, false)[0]?.point.y;
  }

  // Pushes you out of anything solid you've walked into.
  private collide() {
    const p = this.position;
    for (const c of this.circles) {
      const dx = p.x - c.x;
      const dz = p.z - c.z;
      const d = Math.hypot(dx, dz);
      const min = c.r + BODY;
      if (d < min && d > 0.0001) {
        p.x = c.x + (dx / d) * min;
        p.z = c.z + (dz / d) * min;
      }
    }
    for (const b of this.boxes) {
      const dx = p.x - b.x;
      const dz = p.z - b.z;
      const ox = b.halfX + BODY - Math.abs(dx);
      const oz = b.halfZ + BODY - Math.abs(dz);
      if (ox > 0 && oz > 0) {
        if (ox < oz) p.x += Math.sign(dx) * ox;
        else p.z += Math.sign(dz) * oz;
      }
    }
    p.x = Math.max(-this.bounds, Math.min(this.bounds, p.x));
    p.z = Math.max(-this.bounds, Math.min(this.bounds, p.z));
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
