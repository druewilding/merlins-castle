// The locked doors across the ways south: the oak door, and the giant's iron
// gate, padlocked. Opening, its lock opens first (the padlock's shackle
// springs up and turns aside: click), then it swings open, away from you, on
// its hinge. Shutting, it swings back, closes with a bang, and locks again.

import type { Object3D } from "three";

const UNLOCK = 0.35; // seconds, its lock opening (or shutting)
const SWINGING = 1.3; // and it swinging open (or shut)
const SWING = 1.5; // radians, open (along the way's wall)
const LIFT = 0.045; // metres the shackle springs up
const ASIDE = 0.9; // radians it turns aside, on its long leg

/** Its sounds, as it goes. */
export interface DoorSounds {
  unlock(): void;
  open(): void;
  shut(): void;
  lock(): void;
}

export class Door {
  private locked = 1; // 1 locked, 0 its lock open
  private open = 0; // 0 shut, 1 open
  private wants = false;
  private readonly lifted: number; // where the shackle rests, locked

  constructor(
    /** The door itself, its origin on its hinge, swinging round it. */
    private leaf: Object3D,
    /** Its padlock's shackle (the gate's), if it has one. */
    private shackle: Object3D | undefined,
    private sounds: DoorSounds
  ) {
    this.lifted = shackle?.position.y ?? 0;
  }

  /** Open, or shut (instantly: as it was, loading, or out of sight, with no sound). */
  set(open: boolean, instantly = false) {
    if (instantly) {
      this.wants = open;
      this.locked = open ? 0 : 1;
      this.open = open ? 1 : 0;
      this.pose();
      return;
    }
    if (open && !this.wants && this.locked === 1) this.sounds.unlock();
    this.wants = open;
  }

  update(dt: number) {
    if (this.wants) {
      if (this.locked > 0) this.locked = Math.max(0, this.locked - dt / UNLOCK);
      else {
        if (this.open === 0) this.sounds.open();
        this.open = Math.min(1, this.open + dt / SWINGING);
      }
    } else if (this.open > 0) {
      this.open = Math.max(0, this.open - dt / SWINGING);
      if (this.open === 0) this.sounds.shut();
    } else if (this.locked < 1) {
      if (this.locked === 0) this.sounds.lock();
      this.locked = Math.min(1, this.locked + dt / UNLOCK);
    }
    this.pose();
  }

  private pose() {
    // (Slow to start and to stop, like a heavy old door; south, away from its hall.)
    this.leaf.rotation.y = -SWING * ease(this.open);
    if (!this.shackle) return;
    const lock = 1 - this.locked;
    this.shackle.position.y = this.lifted + LIFT * ease(lock * 2);
    this.shackle.rotation.y = ASIDE * ease(lock * 2 - 1);
  }
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
