// The dense trees across the mountain path (land.json's trees.dense), which
// the axe fells: one blow (they all shudder), then over they all go together,
// away from the path, leaving stumps. When the axe is no longer in use there
// (you've gone on, as in the original), they spring back up. And coming down
// from the mountain, the ones round you slide aside to let you out, and close
// again behind you (they keep people out of the mountain, not in: PLAN-V3.md).

import { InstancedMesh, Matrix4, type Mesh, Quaternion, type Scene, Vector3 } from "three";

const CHOP = 0.3; // seconds, the blow of the axe (they shudder), before they fall
const LAG = 0.15; // seconds: each falls up to this much after the first, not all in step
const FALL = 1.1; // seconds, from standing to lying
const DOWN = 1.4; // radians, lying (on the slope at the foot of the mountain)
const RISE = 0.7; // seconds, springing back up
const STUMP = 0.26; // a stump's size, for a tree's
const STUMP_TALL = 0.62; // the stump model's height, at its own size
const SUNK = 0.3; // the trees stand sunk this far into the ground (land.py)
const CLEAR = 3.5; // metres: parting, they slide this far either side of you
const NEAR = 3; // metres, ahead or behind: the ones this near you are right out of the way
const FAR = 9; // and the ones this far, back in place
const SLIDE = 9; // how quickly they slide (the larger, the quicker)

interface Felled {
  at: Vector3;
  yaw: Quaternion;
  scale: number;
  axis: Vector3; // it falls turning about this
  mesh: InstancedMesh;
  slot: number;
  lag: number; // seconds after the first that it falls
  angle: number; // how far over, now
  aside: number; // and how far it's slid aside (east, or west), parting
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
        lag: (0.5 + 0.5 * Math.sin(i * 12.9898)) * LAG,
        angle: 0,
        aside: 0,
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

  /** Felled (the axe in use there), or standing again (or `now`, as they'd end up). */
  fell(down: boolean, now = false) {
    if (down === this.down) return;
    this.down = down;
    this.time = now ? 1000 : 0;
    this.still = false;
    for (const tree of this.trees) tree.from = tree.angle;
  }

  /** Each frame: falling or rising; and parting round you (at `me`), coming down from the mountain. */
  update(dt: number, me: Vector3, parting: boolean) {
    const slid = this.part(dt, me, parting && !this.down);
    if (this.still && !slid) return;
    if (!this.still) {
      this.time += dt;
      for (const tree of this.trees) tree.angle = this.down ? this.falling(tree) : this.rising(tree);
      this.still = this.time > (this.down ? CHOP + LAG + FALL + 1.5 : RISE);
    }
    this.draw();
  }

  // The ones near you slide out of your way, either side; the rest slide back.
  // Whether any moved.
  private part(dt: number, me: Vector3, parting: boolean) {
    let moved = false;
    for (const tree of this.trees) {
      const dx = tree.at.x - me.x;
      const near = Math.min(1, Math.max(0, (FAR - Math.abs(tree.at.z - me.z)) / (FAR - NEAR)));
      const want = parting ? (Math.sign(dx) || 1) * Math.max(0, CLEAR - Math.abs(dx)) * near : 0;
      if (Math.abs(want - tree.aside) < 0.001) continue;
      tree.aside += (want - tree.aside) * Math.min(1, dt * SLIDE);
      moved = true;
    }
    return moved;
  }

  // Shuddering at the blow, then falling faster and faster, and a little bounce.
  private falling(tree: Felled) {
    const t = this.time - CHOP - tree.lag;
    if (t < 0) {
      if (this.reducedMotion || this.time > CHOP) return 0;
      return 0.035 * Math.exp(-this.time * 12) * Math.sin(this.time * 40);
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
      at.x += tree.aside;
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
