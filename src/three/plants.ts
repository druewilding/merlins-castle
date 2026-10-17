// What grows on the ground: grass, flowers, ferns, bushes and stones, as in
// the paintings. Each kind is once in land.glb ("plant-<kind>"), and
// scattered round you by what grows where (land.json's growth, a square
// metre at a time: land.py), the same each time you come by. Near you only
// (the small things nearer than the big ones): further off they shrink away
// into the ground, so they grow up out of it as you come (no popping), and
// the grass sways in the wind. None over an object lying on the ground.

import {
  BufferAttribute,
  Color,
  DoubleSide,
  InstancedMesh,
  Matrix4,
  type Mesh,
  type MeshStandardMaterial,
  type Object3D,
  Quaternion,
  type Scene,
  Vector3,
  type WebGLProgramParametersWithUniforms,
} from "three";

import type { Ground, Walkable } from "./player";

/** What grows where (land.json): its offset in land.bin, on the walkable mask's grid. */
export interface Growth {
  x0: number;
  y0: number;
  step: number;
  nx: number;
  ny: number;
  offset: number;
}

interface Sort {
  models: string[];
  far: number; // metres: grown, nearer than this (and fading out, the last quarter of it)
  size: [number, number]; // how much bigger or smaller than it comes
  sway?: number; // in the wind
  up?: number; // lit as the ground is (its normals pointing up): 1 all of it, 0 none
  wild?: boolean; // only where you can't walk (you'd walk through it)
  shadows?: boolean;
  low?: boolean; // on the mountain too (it grows at any height)
}

const SORTS = {
  grass: { models: ["grass"], far: 26, size: [0.75, 1.3], sway: 1, up: 1 },
  short: { models: ["grass-short"], far: 26, size: [0.8, 1.4], sway: 0.6, up: 1 },
  daisy: { models: ["daisy"], far: 40, size: [0.85, 1.25], sway: 0.4, up: 1 },
  buttercup: { models: ["buttercup"], far: 40, size: [0.85, 1.2], sway: 0.6, up: 1 },
  foxglove: { models: ["foxglove"], far: 55, size: [0.8, 1.25], sway: 0.25, up: 0.7 },
  fern: { models: ["fern"], far: 38, size: [0.35, 0.6], sway: 0.25, up: 0.5 },
  leafy: { models: ["leafy"], far: 40, size: [0.35, 0.55], sway: 0.15, up: 0.5 },
  pebble: { models: ["pebble-1", "pebble-2"], far: 24, size: [0.15, 0.35], low: true },
  grit: { models: ["pebble-1", "pebble-2"], far: 18, size: [0.05, 0.13], low: true },
  stone: { models: ["boulder-2", "boulder-3"], far: 40, size: [0.35, 0.6], low: true },
  boulder: {
    models: ["boulder-1", "boulder-2", "boulder-3", "boulder-4"],
    far: 75,
    size: [0.9, 2],
    wild: true,
    shadows: true,
    low: true,
  },
  bush: { models: ["bush-1", "bush-2", "bush-3"], far: 75, size: [0.75, 1.25], wild: true, shadows: true },
} satisfies Record<string, Sort>;
type Name = keyof typeof SORTS;

// How many of each, a square metre: on each kind of ground (land.py's
// GROUND), and with each mix of flowers and plants (MIXES).
const GROUNDS: Record<number, Partial<Record<Name, number>>> = {
  1: { grass: 2.2, short: 2.2, pebble: 0.01 }, // meadow
  2: { grass: 2.6, short: 2, pebble: 0.15, stone: 0.012, leafy: 0.03 }, // by a path
  3: { grass: 0.5, short: 0.5, fern: 0.07, leafy: 0.04, bush: 0.02, boulder: 0.006 }, // the forest
  4: { grass: 3, short: 1, leafy: 0.04, pebble: 0.05, stone: 0.01 }, // the river's banks
  5: { grass: 3, short: 1, fern: 0.1, leafy: 0.08, foxglove: 0.12, stone: 0.03, pebble: 0.1 }, // the old stone wall
  6: { grit: 0.35, pebble: 0.015 }, // on a path
};
const PATH = 6;
const ON_THE_PATH = 0.03; // metres: (paths lie a little above the ground: land.py)
const MIXES: Record<number, Partial<Record<Name, number>>> = {
  1: { daisy: 0.35, buttercup: 0.15, foxglove: 0.015 }, // the meadows
  2: { buttercup: 0.8, daisy: 0.1 }, // the yellow flowers
  3: { fern: 0.12, stone: 0.02, daisy: 0.03 }, // the mossy steps
  4: { fern: 0.08, daisy: 0.04 }, // under the firs
  5: { foxglove: 0.04, fern: 0.05, daisy: 0.1, buttercup: 0.05 }, // the woods
  6: { daisy: 0.3, buttercup: 0.2, fern: 0.03 }, // the mountain top, round the maze
};
const MOUNTAIN_TOP = 6; // (where they grow high up, as nowhere else)
const FLOWERS = new Set<Name>(["daisy", "buttercup", "foxglove"]);
const IN_THE_FOREST = 0.3; // fewer flowers under the trees

const CHUNK = 8; // metres: scattered a square this big at a time
const MOVED = 2; // gathered again each time you've gone this far
const CLEARS = 12; // objects lying on the ground, at most, that nothing grows over

interface Piece {
  sort: Sort;
  many: InstancedMesh;
}

export class Plants {
  private pieces: Piece[] = [];
  private bySort = new Map<Name, number[]>(); // each sort's pieces (one a model)
  private chunks = new Map<number, { matrices: number[][]; colours: number[][] }>();
  private filledAt = new Vector3(Infinity, 0, 0);
  private readonly time = { value: 0 };
  private readonly clear = { value: Array.from({ length: CLEARS }, () => new Vector3()) };
  private readonly grid: Uint8Array;

  constructor(
    scene: Scene,
    land: Object3D,
    file: ArrayBuffer,
    private growth: Growth,
    private ground: Ground,
    private walkable: Walkable,
    /** Fewer of everything (a phone). */
    private sparse: boolean
  ) {
    this.grid = new Uint8Array(file, growth.offset, growth.nx * growth.ny);
    // (Each model once, though some sorts share one.)
    const meshes = new Map<string, Mesh>();
    const named = (model: string) => {
      if (!meshes.has(model)) {
        const mesh = land.getObjectByName(`plant-${model}`) as Mesh;
        mesh.removeFromParent();
        meshes.set(model, mesh);
      }
      return meshes.get(model)!;
    };
    for (const [name, sort] of Object.entries(SORTS) as [Name, Sort][]) {
      const pieces: number[] = [];
      for (const model of sort.models) {
        pieces.push(this.pieces.length);
        this.pieces.push({ sort, many: this.made(scene, named(model), sort, 64) });
      }
      this.bySort.set(name, pieces);
    }
  }

  /** Each frame: the wind, what's lying on the ground, and (once you've moved a little) what grows round you. */
  update(dt: number, at: Vector3, lying: Object3D[]) {
    this.time.value += dt;
    const near = lying
      .map((model) => model.position)
      .filter((p) => Math.hypot(p.x - at.x, p.z - at.z) < 40)
      .slice(0, CLEARS);
    this.clear.value.forEach((spot, k) => {
      const p = near[k];
      spot.set(p?.x ?? 0, p?.z ?? 0, p ? 0.9 : 0);
    });
    if (Math.hypot(at.x - this.filledAt.x, at.z - this.filledAt.z) < MOVED) return;
    this.filledAt.copy(at);
    this.fill(at);
  }

  // Gathers what grows near enough you to be seen, chunk by chunk.
  private fill(at: Vector3) {
    const counts = this.pieces.map(() => 0);
    const reach = Math.max(...this.pieces.map((piece) => piece.sort.far)) + CHUNK + MOVED;
    const [ci, cj] = [Math.floor(at.x / CHUNK), Math.floor(at.z / CHUNK)];
    const span = Math.ceil(reach / CHUNK);
    const gathered: { chunk: ReturnType<Plants["chunk"]>; d: number }[] = [];
    for (let i = ci - span; i <= ci + span; i++) {
      for (let j = cj - span; j <= cj + span; j++) {
        const d = Math.hypot((i + 0.5) * CHUNK - at.x, (j + 0.5) * CHUNK - at.z) - CHUNK * 0.71;
        if (d < reach) gathered.push({ chunk: this.chunk(i, j), d });
      }
    }
    this.pieces.forEach((piece, k) => {
      const far = piece.sort.far + MOVED;
      const wanted = gathered.reduce((n, { chunk, d }) => (d < far ? n + chunk.matrices[k].length / 16 : n), 0);
      if (wanted > piece.many.instanceMatrix.count) this.grow(piece, Math.ceil(wanted * 1.5));
      const matrices = piece.many.instanceMatrix.array as Float32Array;
      const colours = piece.many.instanceColor!.array as Float32Array;
      for (const { chunk, d } of gathered) {
        if (d >= far) continue;
        matrices.set(chunk.matrices[k], counts[k] * 16);
        colours.set(chunk.colours[k], counts[k] * 3);
        counts[k] += chunk.matrices[k].length / 16;
      }
      piece.many.count = counts[k];
      piece.many.instanceMatrix.needsUpdate = true;
      piece.many.instanceColor!.needsUpdate = true;
    });
    // (Forgetting the chunks far behind you.)
    if (this.chunks.size > 4 * gathered.length) this.chunks.clear();
  }

  // What grows in a chunk, the same each time (by where it is).
  private chunk(i: number, j: number) {
    const key = (i + 1000) * 4096 + j + 1000;
    const known = this.chunks.get(key);
    if (known) return known;
    const matrices: number[][] = this.pieces.map(() => []);
    const colours: number[][] = this.pieces.map(() => []);
    const { x0, y0, step, nx, ny } = this.growth;
    const matrix = new Matrix4();
    const turn = new Quaternion();
    const up = new Vector3(0, 1, 0);
    const where = new Vector3();
    const scale = new Vector3();
    const tint = new Color();
    for (let x = i * CHUNK; x < (i + 1) * CHUNK; x += step) {
      for (let z = j * CHUNK; z < (j + 1) * CHUNK; z += step) {
        // (The grid's in Blender's axes: y is north, -z.)
        const gi = Math.floor((x + step / 2 - x0) / step);
        const gj = Math.floor((-z - step / 2 - y0) / step);
        if (gi < 0 || gj < 0 || gi >= nx || gj >= ny) continue;
        const g = this.grid[gj * nx + gi];
        if (!g) continue;
        const kind = g & 7;
        const random = randoms(gi * 7919 + gj * 104729);
        const flowery = clumped(x, z);
        const here = { ...GROUNDS[kind] };
        for (const [name, n] of Object.entries(kind === PATH ? {} : (MIXES[g >> 3] ?? {})) as [Name, number][]) {
          const fewer = kind === 3 && FLOWERS.has(name) ? IN_THE_FOREST : 1;
          here[name] = (here[name] ?? 0) + n * fewer * (FLOWERS.has(name) ? flowery : 1);
        }
        for (const [name, density] of Object.entries(here) as [Name, number][]) {
          const sort: Sort = SORTS[name];
          let n = Math.floor(density * (this.sparse ? 0.5 : 1) + random());
          while (n-- > 0) {
            const px = x + random() * step;
            const pz = z + random() * step;
            const pieces = this.bySort.get(name)!;
            const k = pieces[Math.floor(random() * pieces.length)];
            const y = this.ground(px, pz);
            const yaw = random() * Math.PI * 2;
            const size = sort.size[0] + (sort.size[1] - sort.size[0]) * random();
            const shade = 0.85 + 0.25 * random();
            if (y === undefined || (sort.wild && this.walkable(px, pz))) continue;
            // (Thinning out up the mountain, where the ground turns to rock: but
            // for the meadow on its top.)
            if (!sort.low && g >> 3 !== MOUNTAIN_TOP && random() < (y - 8) / 8) continue;
            matrix.compose(
              where.set(px, y + (kind === PATH ? ON_THE_PATH : -0.03), pz),
              turn.setFromAxisAngle(up, yaw),
              scale.setScalar(size)
            );
            matrices[k].push(...matrix.elements);
            tint.setRGB(shade, shade * (0.97 + 0.06 * random()), shade * 0.95);
            colours[k].push(tint.r, tint.g, tint.b);
          }
        }
      }
    }
    const chunk = { matrices, colours };
    this.chunks.set(key, chunk);
    return chunk;
  }

  // One model, many times over: shrinking away into the ground further off,
  // swaying in the wind, and not over anything lying on the ground.
  private made(scene: Scene, mesh: Mesh, sort: Sort, count: number) {
    const geometry = mesh.geometry.clone();
    const up = sort.up ?? 0;
    if (up) {
      const normals = geometry.getAttribute("normal") as BufferAttribute;
      const n = new Vector3();
      for (let k = 0; k < normals.count; k++) {
        n.fromBufferAttribute(normals, k)
          .lerp(new Vector3(0, 1, 0), up)
          .normalize();
        normals.setXYZ(k, n.x, n.y, n.z);
      }
    }
    const material = (mesh.material as MeshStandardMaterial).clone();
    // (Thin things, seen from both sides: lit as from the front, both sides.)
    const thin = Boolean(sort.sway);
    if (thin) material.side = DoubleSide;
    material.onBeforeCompile = (shader: WebGLProgramParametersWithUniforms) => {
      Object.assign(shader.uniforms, {
        plantFar: { value: sort.far },
        plantSway: { value: sort.sway ?? 0 },
        plantTime: this.time,
        plantClear: this.clear,
      });
      shader.vertexShader = shader.vertexShader
        .replace(
          "#include <common>",
          `#include <common>
          uniform float plantFar;
          uniform float plantSway;
          uniform float plantTime;
          uniform vec3 plantClear[${CLEARS}];`
        )
        .replace(
          "#include <begin_vertex>",
          `#include <begin_vertex>
          vec3 plantAt = (modelMatrix * instanceMatrix * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
          float grown = smoothstep(plantFar, plantFar * 0.75, distance(plantAt, cameraPosition));
          for (int k = 0; k < ${CLEARS}; k++) {
            if (plantClear[k].z > 0.0) {
              grown *= smoothstep(plantClear[k].z * 0.5, plantClear[k].z, distance(plantAt.xz, plantClear[k].xy));
            }
          }
          float high = max(transformed.y, 0.0);
          float gust = sin(plantTime * 1.3 + plantAt.x * 0.15 + plantAt.z * 0.1);
          float wave = sin(plantTime * 1.9 + plantAt.x * 0.9 + plantAt.z * 0.7);
          transformed.xz += plantSway * high * high * vec2(0.12 + 0.12 * gust + 0.06 * wave, 0.05 * wave);
          transformed *= grown;`
        );
      if (thin) {
        // (Undoing three.js's turning the normal round, seen from behind.)
        shader.fragmentShader = shader.fragmentShader.replace(
          "#include <normal_fragment_begin>",
          `#include <normal_fragment_begin>
          normal *= faceDirection;`
        );
      }
    };
    material.customProgramCacheKey = () => `plant ${thin}`;
    const many = new InstancedMesh(geometry, material, count);
    many.count = 0;
    many.castShadow = Boolean(sort.shadows);
    many.receiveShadow = true;
    many.frustumCulled = false;
    many.setColorAt(0, new Color());
    scene.add(many);
    return many;
  }

  // More room for one of them.
  private grow(piece: Piece, count: number) {
    const old = piece.many;
    const many = new InstancedMesh(old.geometry, old.material, count);
    Object.assign(many, { castShadow: old.castShadow, receiveShadow: true, frustumCulled: false });
    many.setColorAt(0, new Color());
    old.parent!.add(many);
    old.removeFromParent();
    old.dispose();
    piece.many = many;
  }
}

// Numbers from 0 to 1, the same each time from the same seed.
function randoms(seed: number) {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Flowers grow in clumps: more here, fewer there (0 to about 2.5, and 1 on
// the whole), smoothly, across a few metres.
function clumped(x: number, z: number) {
  const s = 7;
  const [i, j] = [Math.floor(x / s), Math.floor(z / s)];
  const [u, v] = [x / s - i, z / s - j];
  const at = (a: number, b: number) => randoms((i + a) * 92821 + (j + b) * 68917)();
  const su = u * u * (3 - 2 * u);
  const sv = v * v * (3 - 2 * v);
  const n = (at(0, 0) * (1 - su) + at(1, 0) * su) * (1 - sv) + (at(0, 1) * (1 - su) + at(1, 1) * su) * sv;
  return Math.max(0, n * 3.2 - 0.7) ** 1.3;
}
