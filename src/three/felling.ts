// The dense trees across the mountain path (land.json's trees.dense), which
// the axe fells: a few blows (each tree shudders), then over they go, the
// nearest first, away from the path, leaving stumps. When the axe is no longer
// in use there (you've gone on, as in the original), they spring back up.

import { InstancedMesh, Matrix4, type Mesh, Quaternion, type Scene, Vector3 } from "three";

const CHOPS = 3; // blows of the axe before the first one falls
const CHOP = 0.3; // seconds between them
const STAGGER = 0.1; // seconds between one tree falling and the next
const FALL = 1.1; // seconds, from standing to lying
const DOWN = 1.4; // radians, lying (on the slope at the foot of the mountain)
const RISE = 0.7; // seconds, springing back up
const STUMP = 0.26; // a stump's size, for a tree's
const STUMP_TALL = 0.62; // the stump model's height, at its own size
const SUNK = 0.3; // the trees stand sunk this far into the ground (land.py)

interface Felled {
  at: Vector3;
  yaw: Quaternion;
  scale: number;
  axis: Vector3; // it falls turning about this
  mesh: InstancedMesh;
  slot: number;
  order: number; // which falls first (0), and next
  angle: number; // how far over, now
  from: number; // and when it began springing back up
}

export class Felling {
  private trees: Felled[] = [];
  private stumps: InstancedMesh;
  private down = false;
  private time = 0; // since they began to fall, or to rise
  private still = true; // (and they've finished)
  private matrix = new Matrix4();
  private turn = new Quaternion();

  constructor(
    scene: Scene,
    models: Map<string, Mesh>,
    kinds: string[],
    dense: number[][],
    stump: Mesh,
    private reducedMotion: boolean
  ) {
    const up = new Vector3(0, 1, 0);
    // They fall away from the path's middle: east, or west (and a little either way).
    const middle = dense.reduce((sum, [, x]) => sum + x, 0) / dense.length;
    const counts = new Map<number, number>();
    for (const [kind] of dense) counts.set(kind, (counts.get(kind) ?? 0) + 1);
    const meshes = new Map(
      [...counts].map(([kind, count]) => {
        const model = models.get(kinds[kind])!;
        const many = new InstancedMesh(model.geometry, model.material, count);
        many.castShadow = true;
        many.receiveShadow = true;
        many.frustumCulled = false;
        many.count = 0;
        scene.add(many);
        return [kind, many];
      })
    );
    dense.forEach(([kind, x, y, z, yaw, scale], i) => {
      const mesh = meshes.get(kind)!;
      const away = new Vector3(Math.sign(x - middle) || 1, 0, Math.sin(i * 7.1) * 0.3).normalize();
      this.trees.push({
        at: new Vector3(x, y, z),
        yaw: new Quaternion().setFromAxisAngle(up, yaw),
        scale,
        axis: new Vector3().crossVectors(up, away).normalize(),
        mesh,
        slot: mesh.count++,
        order: i,
        angle: 0,
        from: 0,
      });
    });
    this.stumps = new InstancedMesh(stump.geometry, stump.material, dense.length);
    this.stumps.castShadow = true;
    this.stumps.receiveShadow = true;
    this.stumps.frustumCulled = false;
    scene.add(this.stumps);
    this.draw();
  }

  /** Felled (the axe in use there), the nearest to `by` first; or standing again. */
  fell(down: boolean, by: Vector3) {
    if (down === this.down) return;
    this.down = down;
    this.time = 0;
    this.still = false;
    const near = [...this.trees].sort((a, b) => a.at.distanceTo(by) - b.at.distanceTo(by));
    near.forEach((tree, k) => {
      tree.order = k;
      tree.from = tree.angle;
    });
  }

  update(dt: number) {
    if (this.still) return;
    this.time += dt;
    for (const tree of this.trees) tree.angle = this.down ? this.falling(tree) : this.rising(tree);
    this.draw();
    this.still = this.time > (this.down ? CHOPS * CHOP + this.trees.length * STAGGER + FALL + 1.5 : RISE);
  }

  // Shuddering at each blow, then falling faster and faster, and a little bounce.
  private falling(tree: Felled) {
    const t = this.time - CHOPS * CHOP - tree.order * STAGGER;
    if (t < 0) {
      if (this.reducedMotion || this.time > CHOPS * CHOP) return 0;
      const since = this.time % CHOP;
      return 0.035 * Math.exp(-since * 12) * Math.sin(since * 40);
    }
    if (t < FALL) return DOWN * (t / FALL) ** 2;
    if (this.reducedMotion) return DOWN;
    return DOWN - 0.08 * Math.exp(-(t - FALL) * 6) * Math.abs(Math.sin((t - FALL) * 14));
  }

  // Back up, overshooting a little and settling (from wherever it had got to).
  private rising(tree: Felled) {
    const u = Math.min(1, this.time / RISE);
    if (this.reducedMotion) return tree.from * (1 - u * u * (3 - 2 * u));
    const c = 1.70158;
    const back = 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2;
    return tree.from * (1 - back);
  }

  private draw() {
    const size = new Vector3();
    const at = new Vector3();
    for (const [k, tree] of this.trees.entries()) {
      // It goes over from the top of its stump (where the axe cut it), and
      // slides off it as it falls, so it lies beside it.
      const cut = SUNK + STUMP_TALL * tree.scale * STUMP * 0.85;
      const over = Math.max(0, tree.angle) / DOWN;
      this.turn.setFromAxisAngle(tree.axis, tree.angle);
      at.set(0, cut * (over - 1), 0).applyQuaternion(this.turn);
      at.add(tree.at).setY(at.y + cut);
      this.turn.multiply(tree.yaw);
      this.matrix.compose(at, this.turn, size.setScalar(tree.scale));
      tree.mesh.setMatrixAt(tree.slot, this.matrix);
      // Its stump, once it's going over (standing on the ground).
      const stump = tree.angle > 0.05 ? tree.scale * STUMP : 0;
      at.copy(tree.at).setY(tree.at.y + SUNK - 0.05);
      this.matrix.compose(at, tree.yaw, size.setScalar(stump));
      this.stumps.setMatrixAt(k, this.matrix);
    }
    for (const tree of this.trees) tree.mesh.instanceMatrix.needsUpdate = true;
    this.stumps.instanceMatrix.needsUpdate = true;
  }
}
