// The maze's stone: the Medieval Village MegaKit's uneven stone (by
// Quaternius, CC0), on its walls and, as flagstones, on its floor. land.glb
// has them only shaded (mossy at the walls' foot); the stone goes on here,
// by where each face is and which way it faces, so it lies the same way
// right along a wall and across the floor, wherever the pieces join.

import {
  BufferAttribute,
  Color,
  Mesh,
  MeshStandardMaterial,
  type Object3D,
  RepeatWrapping,
  SRGBColorSpace,
  TextureLoader,
  type WebGLRenderer,
} from "three";

import stoneUrl from "./textures/stone.jpg?url";
import stoneNormalUrl from "./textures/stone-normal.jpg?url";

const WALL_REPEAT = 2.4; // metres, across the stone once, on the walls
const FLOOR_REPEAT = 3.2; // (and bigger flags on the floor)

/** The stone on the maze's walls and floor (in land.glb: "maze" and "maze-floor"). */
export function dressMaze(land: Object3D, renderer: WebGLRenderer) {
  const loader = new TextureLoader();
  const stone = loader.load(stoneUrl);
  stone.colorSpace = SRGBColorSpace;
  const normal = loader.load(stoneNormalUrl);
  for (const texture of [stone, normal]) {
    texture.wrapS = texture.wrapT = RepeatWrapping;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  }
  const walls = land.getObjectByName("maze");
  if (walls instanceof Mesh) {
    mapped(walls, WALL_REPEAT);
    walls.material = new MeshStandardMaterial({
      vertexColors: true,
      color: new Color(1.5, 1.45, 1.35), // (the kit's stone is dark, for a sunny mountain top)
      map: stone,
      normalMap: normal,
      roughness: 0.9,
    });
  }
  const floor = land.getObjectByName("maze-floor");
  if (floor instanceof Mesh) {
    mapped(floor, FLOOR_REPEAT);
    floor.material = new MeshStandardMaterial({
      vertexColors: true,
      color: new Color(1.6, 1.45, 1.2), // (warmer, sunlit)
      map: stone,
      normalMap: normal,
      roughness: 0.95,
    });
    floor.castShadow = false;
  }
}

/** Where on the stone each corner is: from above, or from the side it faces. */
function mapped(mesh: Mesh, repeat: number) {
  mesh.updateWorldMatrix(true, false);
  const geometry = mesh.geometry;
  const at = geometry.getAttribute("position");
  const facing = geometry.getAttribute("normal");
  const uv = new Float32Array(at.count * 2);
  const e = mesh.matrixWorld.elements; // (it's only moved, if at all)
  for (let i = 0; i < at.count; i++) {
    const x = at.getX(i) + e[12];
    const y = at.getY(i) + e[13];
    const z = at.getZ(i) + e[14];
    const [nx, ny, nz] = [Math.abs(facing.getX(i)), Math.abs(facing.getY(i)), Math.abs(facing.getZ(i))];
    const [u, v] = ny > 0.7 ? [x, -z] : nx > nz ? [z, y] : [x, y];
    uv[i * 2] = u / repeat;
    uv[i * 2 + 1] = v / repeat;
  }
  geometry.setAttribute("uv", new BufferAttribute(uv, 2));
}
