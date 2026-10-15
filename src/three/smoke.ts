// The smoke of the charcoal burner's fire: puffs rising from it, drawn in
// to the hole at the top of the roof and up out of it, where the wind takes
// them, spreading and thinning as they go. (With motion reduced, they hang
// still in the air.)

import {
  Color,
  DataTexture,
  Group,
  LinearFilter,
  LinearMipmapLinearFilter,
  type Scene,
  Sprite,
  SpriteMaterial,
  type Texture,
  Vector3,
} from "three";

/** The fire (land.json): its middle [x, z] and floor, and the smoke hole over it, how high and how wide. */
export interface Hearth {
  fire: number[];
  hole: number;
  r: number;
}

const PUFFS = 70;
const LIFE = 18; // seconds, from the fire to gone
const RISE = 0.7; // metres a second
const WIND = new Vector3(0.6, 0, 0.25); // which way, and how hard, it drifts once it's out
const NEAR = new Color("#6e625a"); // in the hut, dim, warmed by the fire
const OUT = new Color("#d2cfca"); // out in the daylight
const FAR = 180; // metres: further off than this, it isn't worth moving

interface Puff {
  sprite: Sprite;
  age: number;
  angle: number; // where it wanders, round the column's middle
  out: number; // and how far out (of as far as it can)
  spin: number;
}

export class Smoke {
  private group = new Group();
  private puffs: Puff[] = [];
  private x: number;
  private z: number;
  private floor: number;
  private time = 0;

  constructor(
    scene: Scene,
    private hearth: Hearth,
    private reducedMotion: boolean
  ) {
    [this.x, this.z, this.floor] = hearth.fire;
    const map = puff();
    for (let k = 0; k < PUFFS; k++) {
      const material = new SpriteMaterial({ map, transparent: true, depthWrite: false });
      const sprite = new Sprite(material);
      this.group.add(sprite);
      this.puffs.push({
        sprite,
        age: (k / PUFFS) * LIFE,
        angle: Math.random() * Math.PI * 2,
        out: Math.sqrt(Math.random()),
        spin: (Math.random() - 0.5) * 0.4,
      });
    }
    this.place(0);
    scene.add(this.group);
  }

  /** Each frame: where your eyes are. */
  update(dt: number, eye: Vector3) {
    if (this.reducedMotion || Math.hypot(eye.x - this.x, eye.z - this.z) > FAR) return;
    this.time += dt;
    for (const puff of this.puffs) {
      puff.age += dt;
      if (puff.age > LIFE) {
        puff.age -= LIFE;
        puff.angle = Math.random() * Math.PI * 2;
        puff.out = Math.sqrt(Math.random());
        puff.sprite.material.rotation = Math.random() * Math.PI * 2;
      }
    }
    this.place(dt);
  }

  private place(dt: number) {
    const { hole, r } = this.hearth;
    const start = this.floor + 0.25;
    const inside = hole - start; // from the fire up to the hole
    for (const puff of this.puffs) {
      const { sprite, age } = puff;
      const up = age * RISE;
      const y = start + up;
      // In the hut, it wanders a little, drawn in to the hole as it rises;
      // out of it, the wind takes it, and it spreads.
      const t = Math.min(1, up / inside);
      const above = Math.max(0, y - hole);
      const reach = 0.3 + (r * 0.6 - 0.3) * t + above * 0.18;
      const sway = Math.sin(this.time * 0.6 + puff.angle * 3) * 0.08 * (1 - t * 0.5);
      const angle = puff.angle + this.time * puff.spin;
      const drift = Math.pow(above, 1.3) * 0.28;
      sprite.position.set(
        this.x + Math.cos(angle) * reach * puff.out + sway + WIND.x * drift,
        y,
        this.z + Math.sin(angle) * reach * puff.out + WIND.z * drift
      );
      sprite.scale.setScalar(0.45 + 0.5 * t + above * 0.4);
      sprite.material.rotation += puff.spin * dt * 0.5;
      sprite.material.color.copy(NEAR).lerp(OUT, Math.min(1, Math.max(0, (y - hole + 0.8) / 2)));
      // (Fading in off the fire, and out as it thins, high over the roof.)
      const born = Math.min(1, age / 1.5);
      const gone = 1 - Math.min(1, Math.max(0, (age / LIFE - 0.55) / 0.45));
      // (Thicker once it's out: indoors, a thin column is plenty.)
      sprite.material.opacity = (0.28 + 0.17 * Math.min(1, above)) * born * gone;
    }
  }
}

/**
 * A puff of smoke: soft, and a little uneven. (Worked out here, white all
 * over and only its alpha fading, rather than drawn on a canvas: a canvas's
 * nearly clear edges come out speckled with colour.)
 */
function puff(): Texture {
  const SIZE = 64;
  const data = new Uint8Array(SIZE * SIZE * 4).fill(255);
  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      // (Blobs, one over another: what shows through all of them.)
      let clear = 1;
      for (const [bx, by, size, alpha] of [
        [32, 32, 30, 0.55],
        [24, 28, 18, 0.35],
        [40, 36, 16, 0.35],
        [34, 22, 14, 0.3],
      ]) {
        clear *= 1 - alpha * Math.max(0, 1 - Math.hypot(x + 0.5 - bx, y + 0.5 - by) / size);
      }
      data[(y * SIZE + x) * 4 + 3] = Math.round((1 - clear) * 255);
    }
  }
  const texture = new DataTexture(data, SIZE, SIZE);
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
