// In a dark hall (the tower, dark and musty): shafts of daylight slanting
// in at its windows and down across the room, and dust hanging in the air,
// drifting, that glints where it's in one. Faint, and only while you're in it.

import {
  AdditiveBlending,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  Points,
  PointsMaterial,
  type Scene,
  Vector3,
} from "three";

/** A window's inside face (land.json): its middle [x, z], sill and lintel, width, and which way is in. */
export interface Window {
  x: number;
  z: number;
  sill: number;
  lintel: number;
  wide: number;
  in: number[];
}

const MOTES = 320;
const BEAM = "#eef3ff"; // daylight, a little cool
const DUST = "#ffe6b8"; // and dust, a little warm in it
const FAINT = 0.2; // how bright a mote is out of the light
const DRIFT = 0.04; // metres a second, about

interface Shaft {
  from: Vector3; // the middle of the window
  along: Vector3; // down into the room
  length: number;
  half: number; // half its width (and height), at the window: it spreads a little
  material: MeshBasicMaterial;
}

export class Shafts {
  private group = new Group();
  private shafts: Shaft[] = [];
  private motes: Float32Array;
  private drift: Float32Array;
  private colours: Float32Array;
  private dust: Points;
  private dustMaterial: PointsMaterial;
  private time = 0;
  private dustColour = new Color(DUST);

  constructor(
    scene: Scene,
    private hall: { x: number; z: number; floor: number; r: number; tall: number },
    windows: Window[],
    private reducedMotion: boolean
  ) {
    // Each shaft: from the window's inside face, in and down (more from a
    // high window, so it reaches the floor), spreading a little, fading out.
    for (const w of windows) {
      const material = new MeshBasicMaterial({
        vertexColors: true,
        transparent: true,
        blending: AdditiveBlending,
        depthWrite: false,
        side: DoubleSide,
        fog: false,
      });
      const up = (w.sill + w.lintel) / 2 - hall.floor;
      const along = new Vector3(w.in[0], -Math.min(1.1, 0.25 + up * 0.11), w.in[1]).normalize();
      const length = Math.min(9, up / -along.y + 1);
      const from = new Vector3(w.x, (w.sill + w.lintel) / 2, w.z).addScaledVector(along, 0.05);
      const across = new Vector3(-w.in[1], 0, w.in[0]);
      const tall = (w.lintel - w.sill) / 2;
      const shaft = { from, along, length, half: Math.max(w.wide / 2, tall), material };
      this.shafts.push(shaft);
      const far = from.clone().addScaledVector(along, length);
      const corners = (centre: Vector3, spread: number) =>
        [
          [-1, -1],
          [1, -1],
          [1, 1],
          [-1, 1],
        ].map(([a, b]) =>
          centre
            .clone()
            .addScaledVector(across, (a * w.wide * spread) / 2)
            .add(new Vector3(0, b * tall * spread, 0))
        );
      // (Three, one inside another, each faint: brightest in its core, and
      // soft at its edges, not a torch's beam.)
      const strength = w.wide > 1 ? 0.035 : 0.03;
      const positions: number[] = [];
      const colours: number[] = [];
      const { r, g, b } = new Color(BEAM);
      for (const size of [1, 0.7, 0.4]) {
        const near = corners(from, size);
        const wide = corners(far, 1.7 * size);
        for (let k = 0; k < 4; k++) {
          // Each side: a quad from the window's edge to the far end's.
          const quad = [near[k], near[(k + 1) % 4], wide[(k + 1) % 4], near[k], wide[(k + 1) % 4], wide[k]];
          const alpha = [strength, strength, 0, strength, 0, 0];
          quad.forEach((p, i) => {
            positions.push(p.x, p.y, p.z);
            colours.push(r, g, b, alpha[i]);
          });
        }
      }
      const geometry = new BufferGeometry();
      geometry.setAttribute("position", new BufferAttribute(new Float32Array(positions), 3));
      geometry.setAttribute("color", new BufferAttribute(new Float32Array(colours), 4));
      this.group.add(new Mesh(geometry, material));
    }

    // The dust: anywhere in the room, up to its roof.
    this.motes = new Float32Array(MOTES * 3);
    this.drift = new Float32Array(MOTES * 3);
    this.colours = new Float32Array(MOTES * 4);
    for (let k = 0; k < MOTES; k++) {
      const [x, y, z] = this.somewhere();
      this.motes.set([x, y, z], k * 3);
      this.drift.set(
        [(Math.random() - 0.5) * DRIFT, (Math.random() - 0.6) * DRIFT * 0.5, (Math.random() - 0.5) * DRIFT],
        k * 3
      );
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute("position", new BufferAttribute(this.motes, 3));
    geometry.setAttribute("color", new BufferAttribute(this.colours, 4));
    this.dustMaterial = new PointsMaterial({
      size: 0.05,
      map: speck(),
      vertexColors: true,
      transparent: true,
      blending: AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    this.dust = new Points(geometry, this.dustMaterial);
    this.dust.frustumCulled = false;
    this.group.add(this.dust);
    this.group.visible = false;
    scene.add(this.group);
  }

  /** Each frame: how far you're in it (0 to 1, fading in and out as you go in and out), and where your eyes are. */
  update(dt: number, here: number, eye: Vector3) {
    this.group.visible = here > 0.01;
    if (!this.group.visible) return;
    this.time += dt;
    // (Each shaft fading as you come up to its window: in it, it's gone, as
    // a shaft of light is once you're standing in it.)
    for (const { from, material } of this.shafts) {
      material.opacity = here * Math.min(1, Math.max(0, (eye.distanceTo(from) - 1.5) / 2.5));
    }
    const { r, g, b } = this.dustColour;
    const { x: hx, z: hz, r: R } = this.hall;
    for (let k = 0; k < MOTES; k++) {
      const i = k * 3;
      if (!this.reducedMotion) {
        // Drifting, with a little sway, and (out of the room) back in somewhere new.
        const sway = Math.sin(this.time * 0.4 + k) * 0.01;
        this.motes[i] += (this.drift[i] + sway) * dt;
        this.motes[i + 1] += this.drift[i + 1] * dt;
        this.motes[i + 2] += (this.drift[i + 2] - sway) * dt;
        const y = this.motes[i + 1];
        if (
          Math.hypot(this.motes[i] - hx, this.motes[i + 2] - hz) > R - 0.3 ||
          y < this.hall.floor + 0.1 ||
          y > this.hall.floor + this.hall.tall - 0.2
        ) {
          this.motes.set(this.somewhere(), i);
        }
      }
      const lit = this.inLight(this.motes[i], this.motes[i + 1], this.motes[i + 2]);
      // (Not right in front of your eyes, a big blur.)
      const near = Math.min(
        1,
        Math.max(
          0,
          (Math.hypot(this.motes[i] - eye.x, this.motes[i + 1] - eye.y, this.motes[i + 2] - eye.z) - 0.4) / 0.8
        )
      );
      const glint = (FAINT + (1 - FAINT) * lit) * here * near;
      this.colours.set([r, g, b, glint], k * 4);
    }
    this.dust.geometry.attributes.position.needsUpdate = true;
    this.dust.geometry.attributes.color.needsUpdate = true;
  }

  // Somewhere in the room's air.
  private somewhere(): [number, number, number] {
    const a = Math.random() * Math.PI * 2;
    const out = Math.sqrt(Math.random()) * (this.hall.r - 0.4);
    return [
      this.hall.x + Math.cos(a) * out,
      this.hall.floor + 0.2 + Math.random() * (this.hall.tall - 0.5),
      this.hall.z + Math.sin(a) * out,
    ];
  }

  // How much a spot's in a shaft of light: 1 at its middle near the window, fading out along it and to its sides.
  private inLight(x: number, y: number, z: number) {
    let best = 0;
    for (const { from, along, length, half } of this.shafts) {
      const dx = x - from.x;
      const dy = y - from.y;
      const dz = z - from.z;
      const t = dx * along.x + dy * along.y + dz * along.z;
      if (t < 0 || t > length) continue;
      const off = Math.hypot(dx - along.x * t, dy - along.y * t, dz - along.z * t);
      const reach = half * (1 + (0.7 * t) / length);
      if (off < reach) best = Math.max(best, (1 - off / reach) * (1 - t / length));
    }
    return best;
  }
}

/** A speck of dust: round, and soft at its edge. */
function speck() {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 32;
  const context = canvas.getContext("2d")!;
  const glow = context.createRadialGradient(16, 16, 0, 16, 16, 16);
  glow.addColorStop(0, "rgba(255,255,255,1)");
  glow.addColorStop(0.4, "rgba(255,255,255,0.6)");
  glow.addColorStop(1, "rgba(255,255,255,0)");
  context.fillStyle = glow;
  context.fillRect(0, 0, 32, 32);
  return new CanvasTexture(canvas);
}
