// The lamp, lit: in use where it's dark (the long tunnel's mouths, the dark
// tunnels), its flame burns, and it lights the way. Carried, you hold it up
// by its handle, straight out in front of you, just under where you look,
// hanging and swinging as you walk and turn; dropped, it stands where it
// is, still burning (as in the original, dropping it doesn't stop it being
// in use), till you've gone on from there.

import {
  AdditiveBlending,
  Box3,
  Color,
  DoubleSide,
  Euler,
  Group,
  type Material,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  type Object3D,
  type PerspectiveCamera,
  type Scene,
  Sprite,
  SpriteMaterial,
  Vector3,
} from "three";

import { speck } from "./shafts";

// Where your hand is, holding it up (from your eyes, as you look), and how
// big it is in your hand (the one lying about is big, so you can spot it).
const HAND = new Vector3(0, -0.025, -0.45);
const HELD = 0.26;
const RAISE = 0.45; // seconds, lifting it up (or putting it away)
const DOWN = 0.35; // metres it comes up from, below where you hold it
// Swinging from your hand, like a pendulum: how quickly it settles.
const GRAVITY = 9.8;
const SETTLE = 3;
const SWAYS = 0.5; // (a hand holding it steadies it a little)
const SWING = 0.45; // radians, at most
const FLAME = new Color("#ffb458");
const GLEAM = new Color("#6b3f12");

/** The lamp's glass see-through, and its flame bright and unlit (and out, till it's lit), on its model. */
export function dressLamp(model: Object3D) {
  // (Its brass with a little sheen.)
  if (model instanceof Mesh) {
    model.material = new MeshStandardMaterial({ vertexColors: true, metalness: 0.35, roughness: 0.42 });
  }
  const glass = model.getObjectByName("lamp-glass");
  if (glass instanceof Mesh) {
    glass.material = new MeshStandardMaterial({
      vertexColors: true,
      transparent: true,
      opacity: 0.22,
      roughness: 0.1,
      side: DoubleSide,
      depthWrite: false,
    });
  }
  const flame = model.getObjectByName("lamp-flame");
  if (flame instanceof Mesh) {
    flame.material = new MeshBasicMaterial({ vertexColors: true, toneMapped: false });
    flame.visible = false;
  }
}

export class Lantern {
  private holder = new Group(); // at your hand: it hangs from there
  private held: Object3D;
  private halo: Sprite;
  // Lit, its glass glows with the flame, and its brass with the light the
  // flame throws round it (from inside it, it can't light its own outside).
  private glowing: MeshStandardMaterial;
  private gleaming: MeshStandardMaterial;
  private dull: { brass?: Material; glass?: Material } = {}; // (a lamp lying about, out)
  private up = 0; // 0 put away, 1 held up
  private lit = 0; // 0 out, 1 burning (fading in and out)
  private lying: Object3D | undefined; // (dropped, where it stands)
  private swing = { x: 0, z: 0, vx: 0, vz: 0 }; // its tilt (forward, and to the side), and how fast
  private hand = new Vector3();
  private was: Vector3 | undefined; // where your hand was, and how fast it was going
  private going = new Vector3();
  private facing = new Euler();
  /** Where its flame is, to light from. */
  readonly at = new Vector3();

  constructor(
    scene: Scene,
    model: Object3D,
    private camera: PerspectiveCamera,
    private reducedMotion: boolean
  ) {
    this.held = model.clone();
    // Hanging by the top of its handle.
    const top = new Box3().setFromObject(this.held).max.y;
    this.held.position.y = -top * HELD;
    this.held.scale.setScalar(HELD);
    this.held.traverse((node) => (node.castShadow = node.receiveShadow = false));
    const glass = this.held.getObjectByName("lamp-glass");
    this.glowing = (
      glass instanceof Mesh ? glass.material : new MeshStandardMaterial()
    ).clone() as MeshStandardMaterial;
    this.glowing.emissive = FLAME;
    this.gleaming = (
      this.held instanceof Mesh ? this.held.material : new MeshStandardMaterial()
    ).clone() as MeshStandardMaterial;
    this.gleaming.emissive = GLEAM;
    this.kindle(this.held, true);
    this.holder.add(this.held);
    this.holder.visible = false;
    this.halo = new Sprite(
      new SpriteMaterial({
        map: speck(),
        color: FLAME,
        blending: AdditiveBlending,
        transparent: true,
        depthWrite: false,
      })
    );
    this.halo.visible = false;
    scene.add(this.holder, this.halo);
  }

  /** How much it's lighting (0 to 1). */
  get light() {
    return this.lit;
  }

  /**
   * Each frame: lit and in your hand (held), or lit where it stands (lying,
   * its model), or out (neither). Where its flame is, then, for its light.
   */
  update(dt: number, time: number, held: boolean, lying: Object3D | undefined) {
    if (lying !== this.lying) {
      this.kindle(this.lying, false);
      this.lying = lying;
      this.kindle(lying, true);
    }
    const burning = held || Boolean(lying);
    this.lit += Math.sign(Number(burning) - this.lit) * Math.min(Math.abs(Number(burning) - this.lit), dt * 3);
    this.up += Math.sign(Number(held) - this.up) * Math.min(Math.abs(Number(held) - this.up), dt / RAISE);
    const flicker = this.reducedMotion ? 1 : 0.85 + 0.1 * Math.sin(time / 53) + 0.05 * Math.sin(time / 17);
    this.glowing.emissiveIntensity = 0.5 * flicker;
    this.gleaming.emissiveIntensity = 0.6 * flicker;

    // In your hand: rising into view, and swinging.
    this.holder.visible = this.up > 0;
    const flame = this.held.getObjectByName("lamp-flame");
    if (flame) flame.visible = this.up > 0;
    if (this.up > 0) {
      this.hang(dt);
      const t = this.up * this.up * (3 - 2 * this.up);
      this.holder.position.y -= DOWN * (1 - t);
      flame?.getWorldPosition(this.at);
    } else {
      this.was = undefined;
    }

    // Lying lit, its light (and a soft halo round its flame) there instead.
    const standing = lying?.getObjectByName("lamp-flame");
    if (standing && !held) standing.getWorldPosition(this.at);
    this.halo.visible = Boolean(standing) && !held;
    if (this.halo.visible) {
      this.halo.position.copy(this.at);
      this.halo.scale.setScalar(0.5 * flicker);
      this.halo.material.opacity = 0.45 * this.lit;
    }
  }

  /** At your hand, turned the way you face, and swinging from it as your hand moves. */
  private hang(dt: number) {
    this.hand.copy(HAND).applyQuaternion(this.camera.quaternion).add(this.camera.position);
    const yaw = this.facing.setFromQuaternion(this.camera.quaternion, "YXZ").y;
    this.holder.position.copy(this.hand);
    if (dt > 0 && this.was) {
      // (Your hand's speed up to now, and how fast that's changing: but not
      // the jump of being put somewhere else.)
      const going = this.hand.clone().sub(this.was).divideScalar(dt);
      const pushed = going.clone().sub(this.going).divideScalar(dt);
      this.going.copy(going);
      if (pushed.length() < 200) {
        // Forward, and to your right, as you face.
        const forward = (-Math.sin(yaw) * pushed.x - Math.cos(yaw) * pushed.z) * SWAYS;
        const right = (Math.cos(yaw) * pushed.x - Math.sin(yaw) * pushed.z) * SWAYS;
        const long = Math.max(0.1, -this.held.position.y);
        const s = this.swing;
        s.vx += (-(GRAVITY / long) * Math.sin(s.x) - (forward / long) * Math.cos(s.x) - SETTLE * s.vx) * dt;
        s.vz += (-(GRAVITY / long) * Math.sin(s.z) - (right / long) * Math.cos(s.z) - SETTLE * s.vz) * dt;
        s.x += s.vx * dt;
        s.z += s.vz * dt;
        // (Swung as far as it goes, it stops there.)
        if (Math.abs(s.x) > SWING) [s.x, s.vx] = [Math.sign(s.x) * SWING, 0];
        if (Math.abs(s.z) > SWING) [s.z, s.vz] = [Math.sign(s.z) * SWING, 0];
      }
    } else {
      this.going.set(0, 0, 0);
    }
    this.was = (this.was ?? new Vector3()).copy(this.hand);
    const swing = this.reducedMotion ? { x: 0, z: 0 } : this.swing;
    this.holder.rotation.set(swing.x, yaw, swing.z, "YXZ");
  }

  /** A lamp lit (its flame burning, its glass and brass glowing), or out again. */
  private kindle(model: Object3D | undefined, on: boolean) {
    if (!model) return;
    const flame = model.getObjectByName("lamp-flame");
    if (flame) flame.visible = on;
    const glass = model.getObjectByName("lamp-glass");
    if (on) {
      if (model instanceof Mesh) this.dull.brass = model.material as Material;
      if (glass instanceof Mesh) this.dull.glass = glass.material as Material;
    }
    if (model instanceof Mesh) model.material = on ? this.gleaming : (this.dull.brass ?? model.material);
    if (glass instanceof Mesh) glass.material = on ? this.glowing : (this.dull.glass ?? glass.material);
  }
}
