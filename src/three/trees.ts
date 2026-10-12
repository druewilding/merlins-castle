// The trees: each kind once in land.glb ("tree-<kind>", and simpler
// "tree-<kind>-far" and "-distant"), stamped wherever land.json says one
// grows. Near you they're drawn in full; further off, simpler (casting
// shadows as far as the sun's shadows reach); and beyond that, simpler still,
// and only the ones you're facing.

import {
  Color,
  InstancedMesh,
  MathUtils,
  Matrix4,
  type Mesh,
  type Object3D,
  type PerspectiveCamera,
  Quaternion,
  type Scene,
  Vector3,
} from "three";

/** Where they grow: [kind, x, y, z, yaw, scale] (the dense trees on their own, for the axe: felling.ts). */
export interface TreeSpots {
  kinds: string[];
  at: number[][];
  dense: number[][];
}

const NEAR = 35; // metres: drawn in full, nearer than this
const SHADOWED = 70; // and casting shadows, nearer than this (the sun's reach 60 m)
const MOVED = 3; // sorted again each time you've gone this far
const TURNED = 0.15; // or turned this far (radians)
const SLACK = 0.4; // the far ones drawn this far (radians) outside the view, for turning in between

interface Kind {
  near: InstancedMesh;
  mid: InstancedMesh;
  far: InstancedMesh;
  trees: number[]; // which trees are of this kind
}

export class Trees {
  /** Each kind, in full. */
  readonly models = new Map<string, Mesh>();
  private kinds: Kind[] = [];
  private x: Float32Array;
  private z: Float32Array;
  private matrices: Float32Array;
  private colours: Float32Array;
  private sortedAt = new Vector3(Infinity, 0, 0);
  private sortedYaw = 0;

  constructor(scene: Scene, land: Object3D, spots: TreeSpots) {
    const all = spots.at;
    this.x = new Float32Array(all.length);
    this.z = new Float32Array(all.length);
    this.matrices = new Float32Array(all.length * 16);
    this.colours = new Float32Array(all.length * 3);
    const matrix = new Matrix4();
    const turn = new Quaternion();
    const up = new Vector3(0, 1, 0);
    const colour = new Color();
    const trees: number[][] = spots.kinds.map(() => []);
    all.forEach(([kind, x, y, z, yaw, scale], i) => {
      this.x[i] = x;
      this.z[i] = z;
      matrix.compose(new Vector3(x, y, z), turn.setFromAxisAngle(up, yaw), new Vector3(scale, scale, scale));
      matrix.toArray(this.matrices, i * 16);
      // Each a little lighter or darker than the next.
      const shade = 0.9 + 0.12 * Math.sin(i * 12.9898);
      colour.setRGB(shade, shade, shade * 0.97).toArray(this.colours, i * 3);
      trees[kind].push(i);
    });
    spots.kinds.forEach((kind, k) => {
      const full = land.getObjectByName(`tree-${kind}`) as Mesh;
      const simple = land.getObjectByName(`tree-${kind}-far`) as Mesh;
      const simplest = land.getObjectByName(`tree-${kind}-distant`) as Mesh;
      for (const mesh of [full, simple, simplest]) mesh.removeFromParent();
      this.models.set(kind, full);
      const count = trees[k].length;
      const made = (mesh: Mesh, shadows: boolean) => {
        const many = new InstancedMesh(mesh.geometry, mesh.material, count);
        many.castShadow = shadows;
        many.receiveShadow = true;
        // (They're everywhere: always drawn, rather than worked out where they all are.)
        many.frustumCulled = false;
        many.count = 0;
        many.setColorAt(0, colour);
        scene.add(many);
        return many;
      };
      this.kinds.push({ near: made(full, true), mid: made(simple, true), far: made(simplest, false), trees: trees[k] });
    });
  }

  /** Each frame: once you've moved or turned a little, which trees are near you (in full) and which far. */
  update(at: Vector3, yaw: number, camera: PerspectiveCamera) {
    const turned = Math.abs(Math.atan2(Math.sin(yaw - this.sortedYaw), Math.cos(yaw - this.sortedYaw)));
    if (Math.hypot(at.x - this.sortedAt.x, at.z - this.sortedAt.z) < MOVED && turned < TURNED) return;
    this.sortedAt.copy(at);
    this.sortedYaw = yaw;
    // Half the view across, and which way you're facing (0 is north, -z).
    const half = Math.atan(Math.tan(MathUtils.degToRad(camera.fov) / 2) * camera.aspect) + SLACK;
    const seen = Math.cos(Math.min(Math.PI, half));
    const ahead = [-Math.sin(yaw), -Math.cos(yaw)];
    for (const kind of this.kinds) {
      for (const many of [kind.near, kind.mid, kind.far]) many.count = 0;
      for (const i of kind.trees) {
        const dx = this.x[i] - at.x;
        const dz = this.z[i] - at.z;
        const d = Math.hypot(dx, dz);
        if (d >= SHADOWED && (dx * ahead[0] + dz * ahead[1]) / d < seen) continue;
        const many = d < NEAR ? kind.near : d < SHADOWED ? kind.mid : kind.far;
        const n = many.count++;
        many.instanceMatrix.array.set(this.matrices.subarray(i * 16, i * 16 + 16), n * 16);
        many.instanceColor!.array.set(this.colours.subarray(i * 3, i * 3 + 3), n * 3);
      }
      for (const many of [kind.near, kind.mid, kind.far]) {
        many.instanceMatrix.needsUpdate = true;
        many.instanceColor!.needsUpdate = true;
      }
    }
  }
}
