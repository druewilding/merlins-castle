// The lonely flute in the beautiful chamber (its model: art/blender/land.py),
// floating over its pedestal in a soft glow, bobbing and slowly turning, playing its tune
// round and round (scripts/make-sounds.js). Music notes drift up off it,
// glowing, swirling out as they rise, and fade. You hear it faintly from the
// dark tunnels, coming nearer, louder in the room, from where it is (to your
// left, or your right). (With motion reduced, it floats still, and its notes
// glow and fade where they appear.)

import {
  AdditiveBlending,
  Color,
  DataTexture,
  LinearFilter,
  LinearMipmapLinearFilter,
  type Mesh,
  MeshStandardMaterial,
  type Object3D,
  type PerspectiveCamera,
  type Scene,
  Sprite,
  SpriteMaterial,
  type Texture,
  Vector3,
} from "three";

import { audioContext } from "../shared/audio";
import { effectsOn } from "../shared/storage";

const BOB = 0.06; // metres up and down
const TURN = 0.2; // radians a second, round
const TILT = 0.12; // radians, its head up and down, as if someone were playing it
const NOTES = 14;
const EVERY = 0.55; // seconds between notes
const LIFE = 4.5; // seconds, from the flute to gone
const RISE = 0.28; // metres a second
const GLOW = new Color("#c9c2ff"); // lilac, as in its picture
const SEEN = 40; // metres: further off than this, its notes aren't worth moving
// How loud, how far from it: as loud as it gets out to NEAR metres, then
// fainter and fainter (faint in the tunnels), and gone past HEARD.
const NEAR = 9;
const HEARD = 50;

interface Note {
  sprite: Sprite;
  age: number;
  from: Vector3;
  angle: number; // where it swirls, round its way up
  spin: number; // radians a second
  size: number;
}

export class Flute {
  private time = 0;
  private next = 0;
  private notes: Note[] = [];
  private readonly rest: Vector3;
  private readonly at = new Vector3();
  private readonly toward = new Vector3();
  private gain: GainNode | undefined;
  private pan: StereoPannerNode | undefined;
  private volume = 0;
  private readonly halo: Sprite;

  constructor(
    scene: Scene,
    private model: Object3D,
    shine: Texture,
    private reducedMotion: boolean
  ) {
    (model as Mesh).material = new MeshStandardMaterial({
      vertexColors: true,
      flatShading: true,
      metalness: 1,
      roughness: 0.22,
      envMap: shine,
      envMapIntensity: 0.9,
      emissive: GLOW,
      emissiveIntensity: 0.08,
    });
    this.rest = model.position.clone();
    this.halo = new Sprite(
      new SpriteMaterial({
        map: glow(),
        color: GLOW,
        transparent: true,
        opacity: 0.3,
        depthWrite: false,
        toneMapped: false,
      })
    );
    this.halo.scale.setScalar(1.7);
    this.halo.position.copy(this.rest);
    scene.add(this.halo);
    const maps = [note(false), note(true)];
    for (let k = 0; k < NOTES; k++) {
      const sprite = new Sprite(
        new SpriteMaterial({
          map: maps[k % 2],
          color: GLOW,
          transparent: true,
          opacity: 0,
          depthWrite: false,
          blending: AdditiveBlending,
          toneMapped: false,
        })
      );
      sprite.visible = false;
      scene.add(sprite);
      this.notes.push({ sprite, age: LIFE, from: new Vector3(), angle: 0, spin: 0, size: 0 });
    }
  }

  /** Starts its tune, round and round, silent till you come near (once sound can start: after a click). */
  play(tune: Promise<AudioBuffer | null>, volume: number) {
    if (this.gain) return;
    const context = audioContext();
    const gain = (this.gain = context.createGain());
    const pan = (this.pan = context.createStereoPanner());
    gain.gain.value = 0;
    this.volume = volume;
    void tune.then((buffer) => {
      if (!buffer) return;
      const source = context.createBufferSource();
      source.buffer = buffer;
      source.loop = true;
      source.connect(gain).connect(pan).connect(context.destination);
      source.start();
    });
  }

  /** Each frame: your camera, and whether you're underground (it can't be heard up on the land). */
  update(dt: number, camera: PerspectiveCamera, underground: boolean) {
    this.time += dt;
    const far = camera.position.distanceTo(this.rest);
    // Floating, bobbing and turning.
    if (!this.reducedMotion) {
      this.model.position.y = this.rest.y + BOB * Math.sin(this.time * 1.1);
      this.model.rotation.set(0, this.time * TURN, TILT * Math.sin(this.time * 0.6), "YZX");
      this.halo.position.y = this.model.position.y;
      this.halo.material.opacity = 0.3 + 0.06 * Math.sin(this.time * 1.7);
    }
    // How it sounds from here.
    if (this.gain && this.pan) {
      const loud = underground && effectsOn() ? loudness(far) : 0;
      const now = this.gain.context.currentTime;
      this.gain.gain.setTargetAtTime(this.volume * loud, now, 0.15);
      this.toward.copy(this.rest).sub(camera.position).applyQuaternion(camera.quaternion.clone().invert());
      this.pan.pan.setTargetAtTime((0.6 * this.toward.x) / Math.max(far, 0.1), now, 0.15);
    }
    // Its notes, drifting off it.
    if (far > SEEN) {
      for (const note of this.notes) note.sprite.visible = false;
      return;
    }
    this.next -= dt;
    if (this.next <= 0) {
      this.next += EVERY * (0.7 + 0.6 * Math.random());
      const note = this.notes.find((note) => note.age >= LIFE);
      if (note) {
        // (From along its foot half, where the keys are.)
        this.model.localToWorld(this.at.set(-0.5 * Math.random() - 0.05, 0.04, 0));
        note.from.copy(this.at);
        note.age = 0;
        note.angle = Math.random() * Math.PI * 2;
        note.spin = (0.5 + 0.5 * Math.random()) * (Math.random() < 0.5 ? -1 : 1);
        note.size = 0.12 + 0.08 * Math.random();
      }
    }
    for (const note of this.notes) {
      note.age += dt;
      const { sprite, age } = note;
      sprite.visible = age < LIFE;
      if (!sprite.visible) continue;
      const out = this.reducedMotion ? 0 : 0.15 + 0.6 * (age / LIFE);
      const angle = note.angle + note.spin * age;
      sprite.position.set(
        note.from.x + out * Math.cos(angle),
        note.from.y + (this.reducedMotion ? 0.15 : RISE * age),
        note.from.z + out * Math.sin(angle)
      );
      sprite.material.opacity = fade(age / 0.4) * fade((LIFE - age) / 1.5);
      sprite.scale.setScalar(note.size * (1 + 0.15 * Math.sin(this.time * 6 + note.angle)));
    }
  }
}

/** How loud it is (1 as loud as it gets), so far off (metres). */
export function loudness(far: number) {
  return Math.min(1, (NEAR / far) ** 2) * fade((HEARD - far) / 10);
}

/** Smoothly from 0 to 1, as t goes from 0 to 1. */
function fade(t: number) {
  const s = Math.min(1, Math.max(0, t));
  return s * s * (3 - 2 * s);
}

/**
 * A soft round glow, white (tinted by its sprite), fading out from its
 * middle. (Worked out here, only its alpha fading, as smoke.ts's puff is: a
 * canvas's nearly clear edges come out speckled with colour.)
 */
function glow(): Texture {
  return worked(64, (x, y) => {
    const out = Math.min(1, Math.hypot(x - 32, y - 32) / 32);
    return (1 - out) ** 2.2;
  });
}

/**
 * A music note, glowing, white (tinted by its sprite): a quaver, or two
 * beamed. (Drawn on a canvas, crisp, then its glow worked out round it.)
 */
function note(beamed: boolean): Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const pen = canvas.getContext("2d")!;
  pen.fillStyle = pen.strokeStyle = "#ffffff";
  pen.lineWidth = 4;
  const head = (x: number, y: number) => {
    pen.beginPath();
    pen.ellipse(x, y, 7.5, 5.5, -0.4, 0, Math.PI * 2);
    pen.fill();
  };
  const stem = (x: number, y: number) => {
    pen.beginPath();
    pen.moveTo(x + 6, y - 2);
    pen.lineTo(x + 6, 13);
    pen.stroke();
  };
  if (beamed) {
    head(19, 48);
    head(44, 43);
    stem(19, 48);
    stem(44, 43);
    pen.lineWidth = 6;
    pen.beginPath();
    pen.moveTo(23, 13);
    pen.lineTo(52, 10);
    pen.stroke();
  } else {
    head(26, 48);
    stem(26, 48);
    pen.beginPath();
    pen.moveTo(32, 13);
    pen.quadraticCurveTo(48, 20, 45, 37);
    pen.stroke();
  }
  const drawn = pen.getImageData(0, 0, size, size).data;
  const ink = (x: number, y: number) =>
    x < 0 || y < 0 || x >= size || y >= size ? 0 : drawn[(Math.floor(y) * size + Math.floor(x)) * 4 + 3] / 255;
  // (Its glow: how much ink is near, within a few pixels.)
  const near: [number, number, number][] = [];
  for (let dy = -5; dy <= 5; dy++) {
    for (let dx = -5; dx <= 5; dx++) {
      const far = Math.hypot(dx, dy);
      if (far <= 5) near.push([dx, dy, 1 - far / 6]);
    }
  }
  const weight = near.reduce((sum, [, , w]) => sum + w, 0);
  return worked(size, (x, y) => {
    const glowing = near.reduce((sum, [dx, dy, w]) => sum + w * ink(x + dx, y + dy), 0) / weight;
    return Math.max(ink(x, y), Math.min(1, 1.6 * glowing) * 0.55);
  });
}

/** A texture, white, size pixels across, its alpha at each pixel (x, y from its top left). */
function worked(size: number, alpha: (x: number, y: number) => number): Texture {
  const data = new Uint8Array(size * size * 4).fill(255);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      // (Its rows from the bottom up, as a texture's are.)
      data[((size - 1 - y) * size + x) * 4 + 3] = Math.round(alpha(x, y) * 255);
    }
  }
  const texture = new DataTexture(data, size, size);
  texture.magFilter = LinearFilter;
  texture.minFilter = LinearMipmapLinearFilter;
  texture.generateMipmaps = true;
  texture.needsUpdate = true;
  return texture;
}
