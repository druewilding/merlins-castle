// The ring used in the tower, shut in by the enormous stone ("The stone
// rolls aside."): you hold it up in front of you, and its stone flashes;
// a stream of purple sparkles pours from it to the stone, and swirls round
// over it, wrapping it in a purple glow; the stone trembles, and rolls aside
// (main.ts rolls it, once `holding` lets it go), the glow and the sparkles
// going with it, and fading. (With motion reduced, the sparkles don't fly:
// they twinkle round the stone where they are, and it doesn't tremble.)

import {
  AdditiveBlending,
  Color,
  DataTexture,
  LinearFilter,
  LinearMipmapLinearFilter,
  type Object3D,
  type PerspectiveCamera,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  type Texture,
  Vector3,
} from "three";

// Its beats, in seconds from using it.
const RAISED = 0.35; // the ring up in front of you
const FLASH = 0.3; // its stone flashing
const STREAM = [0.35, 1.3]; // the sparkles setting off, from the first to the last
const FLIGHT = 0.75; // seconds each takes to reach the stone
const TREMBLE = [1.2, 2.0]; // the stone trembling, from and till
const ROLLS = 2.0; // and it rolls
const LOWERED = [2.2, 2.6]; // the ring put away
const FADES = [3.0, 4.2]; // the glow and the sparkles fading, from and till

const SPARKLES = 40;
const PURPLE = new Color("#b77cff"); // as its stone
const HAND = new Vector3(0.1, -0.12, -0.45); // where you hold it, from your eye
const HELD = 0.22; // its size in your hand (it's made big, to be spotted on the ground)
const UP = new Vector3(0, 1, 0);
const SHAKE = 0.035; // metres the stone trembles
// (Holding it up, its stone on top, facing you: it's made lying down, flat,
// its stone towards +x. Stood up on its edge, then turned stone up.)
const UPRIGHT = new Quaternion()
  .setFromAxisAngle(new Vector3(0, 0, 1), Math.PI / 2)
  .multiply(new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), Math.PI / 2));

interface Sparkle {
  sprite: Sprite;
  leaves: number; // seconds from using it
  bulge: Vector3; // which way its path bows out
  angle: number; // round the stone, once there
  out: number; // how far out from the middle of its face, of its radius
  spin: number; // radians a second, round it
  size: number;
}

export class Charm {
  /** Whether the stone should stay where it is, for now (the magic taking hold). */
  holding = false;
  /** How far the stone's shaken from where it is (add it to its place). */
  readonly shake = new Vector3();
  private t = FADES[1];
  private readonly ring: Object3D;
  private readonly flash: Sprite;
  private readonly halo: Sprite;
  private readonly sparkles: Sparkle[] = [];
  private readonly from = new Vector3();
  private readonly at = new Vector3();
  private readonly face = new Vector3(); // the middle of its side towards you
  private readonly across = new Vector3();

  constructor(
    scene: Scene,
    ring: Object3D,
    private readonly radius: number, // the stone's
    private readonly reducedMotion: boolean
  ) {
    this.ring = ring.clone();
    this.ring.visible = false;
    this.ring.traverse((node) => (node.castShadow = node.receiveShadow = false));
    scene.add(this.ring);
    const glowing = (map: Texture, opacity = 1) =>
      new Sprite(
        new SpriteMaterial({
          map,
          color: PURPLE,
          transparent: true,
          opacity,
          blending: AdditiveBlending,
          depthWrite: false,
          toneMapped: false,
        })
      );
    this.flash = glowing(glow());
    this.halo = glowing(glow());
    this.flash.visible = this.halo.visible = false;
    scene.add(this.flash, this.halo);
    const star = sparkle();
    for (let k = 0; k < SPARKLES; k++) {
      const sprite = glowing(star);
      sprite.visible = false;
      scene.add(sprite);
      this.sparkles.push({
        sprite,
        leaves: STREAM[0] + ((STREAM[1] - STREAM[0]) * k) / (SPARKLES - 1),
        bulge: new Vector3(),
        angle: 0,
        out: 0,
        spin: 0,
        size: 0,
      });
    }
  }

  /** The ring used, from your hand. */
  cast() {
    this.t = 0;
    this.holding = true;
    for (const sparkle of this.sparkles) {
      sparkle.bulge.set(Math.random() * 2 - 1, Math.random() * 1.2, Math.random() * 2 - 1);
      sparkle.angle = Math.random() * Math.PI * 2;
      sparkle.out = 0.2 + Math.random() * 0.7;
      sparkle.spin = (1.2 + Math.random()) * (Math.random() < 0.8 ? 1 : -1);
      sparkle.size = 0.2 + Math.random() * 0.25;
    }
  }

  /** All gone at once (starting again). */
  stop() {
    this.t = FADES[1];
    this.holding = false;
    this.shake.set(0, 0, 0);
    this.ring.visible = this.flash.visible = this.halo.visible = false;
    for (const { sprite } of this.sparkles) sprite.visible = false;
  }

  /** Each frame: your camera, and the stone's middle (where it is now, not shaken). */
  update(dt: number, camera: PerspectiveCamera, stone: Vector3) {
    if (this.t >= FADES[1]) return;
    const was = this.t;
    this.t += dt;
    const t = this.t;
    if (was < ROLLS && t >= ROLLS) this.holding = false;
    if (t >= FADES[1]) return this.stop();
    // The ring, up in front of you, and put away again.
    const up = ease(t / RAISED) * (1 - ease((t - LOWERED[0]) / (LOWERED[1] - LOWERED[0])));
    this.ring.visible = up > 0.01;
    camera.localToWorld(this.from.copy(HAND).add(this.at.set(0, -0.15 * (1 - up), 0)));
    this.ring.position.copy(this.from);
    this.ring.quaternion.copy(camera.quaternion).multiply(UPRIGHT);
    this.ring.scale.setScalar(HELD * Math.max(0.01, up));
    // (Its stone, where the light comes from: on top of it.)
    camera.localToWorld(this.from.copy(HAND).add(this.at.set(0, 0.035 - 0.15 * (1 - up), 0)));
    // Its stone flashing, and glowing on while the sparkles pour out.
    const flash = Math.max(Math.sin(Math.min(1, t / FLASH) * Math.PI), 0.4 * (t < STREAM[1] + 0.2 ? 1 : 0)) * up;
    this.flash.visible = flash > 0.01;
    this.flash.position.copy(this.from);
    this.flash.scale.setScalar(0.04 + 0.12 * flash);
    this.flash.material.opacity = flash;
    // The stone trembling, as the magic takes hold.
    const shaking =
      this.reducedMotion || t < TREMBLE[0] || t > TREMBLE[1]
        ? 0
        : Math.sin(((t - TREMBLE[0]) / (TREMBLE[1] - TREMBLE[0])) * Math.PI);
    this.shake.set(Math.sin(t * 53) * SHAKE * shaking, Math.abs(Math.sin(t * 37)) * SHAKE * 0.4 * shaking, 0);
    // (Its side towards you: the glow and the sparkles on it, not inside it.)
    this.across.set(camera.position.x - stone.x, 0, camera.position.z - stone.z).normalize();
    this.face.copy(stone).addScaledVector(this.across, this.radius);
    this.across.set(-this.across.z, 0, this.across.x);
    // The glow round it, and fading.
    const fading = 1 - ease((t - FADES[0]) / (FADES[1] - FADES[0]));
    const glowing = ease((t - STREAM[0] - FLIGHT) / 0.6) * fading;
    this.halo.visible = glowing > 0.01;
    this.halo.position.copy(this.face);
    this.halo.scale.setScalar(this.radius * (2.2 + (this.reducedMotion ? 0 : 0.12 * Math.sin(t * 5))));
    this.halo.material.opacity = 0.4 * glowing;
    // The sparkles: from the ring to the stone, then round and round over its side.
    for (const sparkle of this.sparkles) {
      const { sprite } = sparkle;
      const age = t - sparkle.leaves;
      sprite.visible = age > 0;
      if (!sprite.visible) continue;
      const round = sparkle.angle + (this.reducedMotion ? 0 : sparkle.spin * Math.max(0, age - FLIGHT));
      this.at
        .copy(this.face)
        .addScaledVector(this.across, Math.cos(round) * this.radius * sparkle.out)
        .addScaledVector(UP, Math.sin(round) * this.radius * sparkle.out);
      if (this.reducedMotion) {
        sprite.position.copy(this.at);
        sprite.material.opacity = ease(age / 0.3) * fading;
      } else if (age < FLIGHT) {
        // (Along a curve, bowing out, quicker as it goes.)
        const f = (age / FLIGHT) ** 1.4;
        sprite.position.lerpVectors(this.from, this.at, f).addScaledVector(sparkle.bulge, Math.sin(f * Math.PI) * 0.8);
        sprite.material.opacity = ease(age / 0.15);
      } else {
        sprite.position.copy(this.at);
        sprite.material.opacity = fading;
      }
      const near = age < FLIGHT && !this.reducedMotion ? 0.35 + 0.65 * (age / FLIGHT) : 1;
      sprite.scale.setScalar(sparkle.size * near * (0.8 + 0.2 * Math.sin(t * 9 + sparkle.angle * 5)));
    }
  }
}

function ease(t: number) {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
}

/** A soft round glow, white (tinted by its sprite). */
function glow(): Texture {
  return worked(64, (x, y) => (1 - Math.min(1, Math.hypot(x - 31.5, y - 31.5) / 32)) ** 2);
}

/** A glint, white: four thin points of light from a bright middle, in a soft glow. */
function sparkle(): Texture {
  return worked(64, (x, y) => {
    const dx = Math.abs(x - 31.5) / 32;
    const dy = Math.abs(y - 31.5) / 32;
    const r = Math.hypot(dx, dy);
    const points = Math.max(Math.max(0, 1 - dy / 0.06) * (1 - dx) ** 2, Math.max(0, 1 - dx / 0.06) * (1 - dy) ** 2);
    return Math.min(1, Math.max(points, 0.5 * Math.max(0, 1 - r) ** 3));
  });
}

/**
 * A texture, white, its alpha at each pixel. (Worked out, not drawn on a
 * canvas: a canvas's nearly clear edges come out speckled with colour.)
 */
function worked(size: number, alpha: (x: number, y: number) => number): Texture {
  const data = new Uint8Array(size * size * 4).fill(255);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) data[(y * size + x) * 4 + 3] = Math.round(alpha(x, y) * 255);
  }
  const texture = new DataTexture(data, size, size);
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
