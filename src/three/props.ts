// What's furnished many times over (bookcases full of books, candle stands):
// each kind once in land.glb ("prop-<kind>", at the origin), stamped
// wherever land.json says one stands (props in art/blender/land.py).

import { InstancedMesh, Matrix4, type Mesh, type Object3D, Quaternion, type Scene, Vector3 } from "three";

/** Where they stand: [kind, x, y, z, yaw]. */
export interface PropSpots {
  kinds: string[];
  at: number[][];
}

export function stampProps(scene: Scene, land: Object3D, spots: PropSpots) {
  const matrix = new Matrix4();
  const turn = new Quaternion();
  const up = new Vector3(0, 1, 0);
  const one = new Vector3(1, 1, 1);
  spots.kinds.forEach((kind, k) => {
    const model = land.getObjectByName(`prop-${kind}`) as Mesh;
    model.removeFromParent();
    const here = spots.at.filter(([of]) => of === k);
    const many = new InstancedMesh(model.geometry, model.material, here.length);
    here.forEach(([, x, y, z, yaw], i) => {
      many.setMatrixAt(i, matrix.compose(new Vector3(x, y, z), turn.setFromAxisAngle(up, yaw), one));
    });
    many.computeBoundingSphere();
    many.castShadow = true;
    many.receiveShadow = true;
    scene.add(many);
  });
}
