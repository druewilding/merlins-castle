// Going on west past the giant without giving him a cake: "The giant turns
// you into a mouse." You turn to look up at him; he lifts his hand and points
// at you, and poof: a puff of glittering smoke, and the world shoots up round
// you as you shrink to the floor. Squeak! You scurry across the floor to his
// feet; and up there, huge, the giant leans down to peer at you, beaming,
// and chuckles (giant.ts). The curtain comes down over the end of it (from a
// little before `ends`), and he goes on peering at you behind it.

import {
  AdditiveBlending,
  CanvasTexture,
  Color,
  Euler,
  type PerspectiveCamera,
  Quaternion,
  type Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  type Texture,
  Vector3,
} from "three";

import type { Giant, GiantPlace } from "./giant";
import { puff } from "./smoke";

// The scene's beats, in seconds from walking into it.
const POOF = 1.15; // as he points at you: a puff of smoke
const SHRUNK = 1.6; // and you're a mouse
const SQUEAK = 1.8;
const SCURRY = [2, 3]; // scurrying to his feet, from and till
const CHUCKLES = [3.1, 5]; // and he chuckles, leaning down to peer at you
const ENDS = 7.5;

const EYE = 1.65; // your eye above the floor (as in player.ts)
const MOUSE = 0.12; // and a mouse's
const NEAR = 2.4; // metres from the middle of his seat you scurry to (at his size: before his feet)
const SCAMPERS = 9; // little steps a second, scurrying
const FOLLOW = 1.5; // how quickly you look round as his face moves (each second, of the way to it)

export class Shrunk {
  readonly ends = ENDS;
  private t = 0;
  private readonly from: Vector3; // your eye, where you were when you came to it
  private readonly facing: Quaternion;
  private readonly floor: number;
  private readonly to: Vector3; // where you scurry to, at his feet
  private readonly seen = new Vector3(); // where you're looking: his face, a little behind it
  private readonly eye = new Vector3();
  private readonly look = new Quaternion();
  private readonly euler = new Euler(0, 0, 0, "YXZ");

  constructor(
    private camera: PerspectiveCamera,
    private giant: Giant,
    place: GiantPlace,
    private poof: Poof,
    private reducedMotion: boolean,
    private play: (sound: "poof" | "squeak" | "chuckle") => void
  ) {
    this.from = camera.position.clone();
    this.facing = camera.quaternion.clone();
    this.floor = this.from.y - EYE;
    this.seen.copy(giant.faceAt());
    const [x, z] = place.at;
    const off = new Vector3(this.from.x - x, 0, this.from.z - z);
    this.to = new Vector3(x, 0, z).addScaledVector(off, (NEAR * place.size) / 3.2 / off.length());
    giant.enchant();
  }

  /** Each frame (on behind the curtain, too: him peering). */
  update(dt: number) {
    const was = this.t;
    this.t += dt;
    const t = this.t;
    const still = this.reducedMotion;
    const crossed = (beat: number) => was < beat && t >= beat;
    if (crossed(POOF)) {
      this.play("poof");
      this.poof.start(this.from.clone().setY(this.floor));
    }
    if (crossed(SQUEAK)) this.play("squeak");
    for (const beat of CHUCKLES) {
      if (crossed(beat)) {
        this.play("chuckle");
        this.giant.chuckle();
      }
    }
    this.poof.update(dt, still);

    // Shrinking: slowly at first, then all at once, down to the floor (with
    // a wobble on the way); and then scurrying across to his feet, pitter
    // patter.
    const s = Math.min(1, Math.max(0, (t - POOF) / (SHRUNK - POOF)));
    const scurried = Math.min(1, Math.max(0, (t - SCURRY[0]) / (SCURRY[1] - SCURRY[0])));
    this.eye.lerpVectors(this.from, this.to, ease(scurried));
    this.eye.y = this.floor + EYE - (EYE - MOUSE) * s * s * (3 - 2 * s);
    if (!still && scurried > 0 && scurried < 1) this.eye.y += 0.015 * Math.abs(Math.sin(t * SCAMPERS * Math.PI));

    // Looking up at his face (wherever it goes, following it smoothly).
    this.seen.lerp(this.giant.faceAt(), Math.min(1, dt * FOLLOW));
    const to = this.seen.clone().sub(this.eye);
    const wobble = still ? 0 : 0.25 * Math.sin(Math.PI * s) * Math.sin(t * 18);
    this.look.setFromEuler(this.euler.set(Math.atan2(to.y, Math.hypot(to.x, to.z)), Math.atan2(-to.x, -to.z), wobble));
    this.camera.position.copy(this.eye);
    // (Turning to him, at first, from however you were looking.)
    this.camera.quaternion.slerpQuaternions(this.facing, this.look, ease(t / 0.5));
  }
}

const PUFFS = 14;
const SPARKLES = 12;
const LASTS = 1.6; // seconds the puff lasts, billowing and fading
const COLOURS = ["#e6d8ff", "#f6dcf4", "#ffffff", "#d6e4ff"];

/** A puff of glittering smoke round you, the spell taking hold. */
export class Poof {
  private readonly puffs: { sprite: Sprite; way: Vector3; size: number }[] = [];
  private readonly sparkles: { sprite: Sprite; angle: number; rise: number; out: number }[] = [];
  private readonly at = new Vector3();
  private age = LASTS;

  constructor(scene: Scene) {
    const smoke = puff();
    for (let n = 0; n < PUFFS; n++) {
      const sprite = this.sprite(smoke, COLOURS[n % COLOURS.length]);
      // (All round you, low down and up to above your head.)
      const angle = (n / PUFFS) * Math.PI * 2;
      const way = new Vector3(Math.cos(angle), 0.15 + (n % 4) * 0.45, Math.sin(angle));
      this.puffs.push({ sprite, way, size: 1 + 0.3 * ((n * 7) % 3) });
      scene.add(sprite);
    }
    const glint = sparkle();
    for (let n = 0; n < SPARKLES; n++) {
      const sprite = this.sprite(glint, "#fff3c0");
      sprite.material.blending = AdditiveBlending;
      sprite.renderOrder = 11;
      this.sparkles.push({
        sprite,
        angle: (n / SPARKLES) * Math.PI * 2,
        rise: 0.4 + (n % 3) * 0.5,
        out: 0.5 + (n % 2) * 0.4,
      });
      scene.add(sprite);
    }
  }

  private sprite(map: Texture, colour: string) {
    const sprite = new Sprite(
      new SpriteMaterial({ map, color: new Color(colour), transparent: true, depthWrite: false, fog: false })
    );
    sprite.renderOrder = 10;
    sprite.visible = false;
    return sprite;
  }

  /** Poof: round your feet. */
  start(feet: Vector3) {
    this.at.copy(feet);
    this.age = 0;
  }

  /** Each frame: billowing out and fading (or, still, only fading). */
  update(dt: number, still: boolean) {
    this.age += dt;
    const u = Math.min(1, this.age / LASTS);
    const there = u < 1;
    // (Bursting out quickly, then slowing; there at once, then fading.)
    const out = still ? 0.6 : 1 - (1 - u) ** 3;
    const fade = Math.min(1, this.age / 0.08) * (1 - u) ** 1.5;
    for (const { sprite, way, size } of this.puffs) {
      sprite.visible = there;
      sprite.position
        .copy(this.at)
        .add({ x: way.x * (0.3 + out), y: way.y * (0.6 + 0.6 * out), z: way.z * (0.3 + out) });
      sprite.scale.setScalar(size * (0.7 + out));
      sprite.material.opacity = 0.85 * fade;
      sprite.material.rotation = still ? 0 : way.y + u * 1.5;
    }
    for (const [n, { sprite, angle, rise, out: far }] of this.sparkles.entries()) {
      sprite.visible = there;
      const round = angle + (still ? 0 : u * 4);
      const r = far * (0.4 + out);
      sprite.position.set(
        this.at.x + r * Math.cos(round),
        this.at.y + rise + (still ? 0 : u * 0.8),
        this.at.z + r * Math.sin(round)
      );
      const twinkle = still ? 1 : 0.6 + 0.4 * Math.sin(this.age * 30 + n * 2.3);
      sprite.scale.setScalar(0.18 * twinkle);
      sprite.material.opacity = fade;
    }
  }

  hide() {
    this.age = LASTS;
    for (const { sprite } of [...this.puffs, ...this.sparkles]) sprite.visible = false;
  }
}

// A glint: four long, thin points of light from a bright middle.
function sparkle() {
  const S = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = S;
  const g = canvas.getContext("2d")!;
  const glow = g.createRadialGradient(S / 2, S / 2, 0, S / 2, S / 2, S / 2);
  glow.addColorStop(0, "rgba(255, 255, 255, 1)");
  glow.addColorStop(0.15, "rgba(255, 250, 220, 0.6)");
  glow.addColorStop(1, "rgba(255, 240, 200, 0)");
  g.fillStyle = glow;
  g.fillRect(0, 0, S, S);
  g.fillStyle = "rgba(255, 255, 255, 0.9)";
  g.beginPath();
  for (let i = 0; i < 8; i++) {
    const r = i % 2 ? 3 : S / 2;
    const a = (i * Math.PI) / 4;
    g.lineTo(S / 2 + r * Math.cos(a), S / 2 + r * Math.sin(a));
  }
  g.closePath();
  g.fill();
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

const ease = (t: number) => {
  const u = Math.min(1, Math.max(0, t));
  return u * u * (3 - 2 * u);
};
