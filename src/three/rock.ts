// The rock underground (in land.glb: "caves", their walls, roofs, floors and
// stalagmites, and "tunnel", the ways dug between them), as in the illustrated
// version's caves: its floors worn, grainy and blotched, with a few cracks;
// its walls and roofs knobbly, streaked down where water's run, and in faint
// layers; and all of it bumpy in the light. Drawn from
// where each bit of it is, in the world, so it costs nothing to download and
// never repeats; and fading out where it's too fine to see (far away), so it
// doesn't shimmer.

import { type Material, Mesh, type Object3D, type WebGLProgramParametersWithUniforms } from "three";

const CRACKS = 1.4; // cracks a metre, across its floors (its cells, between them, are its stones)
const GRAIN = 9; // lumps a metre, in its grain
const BLOTCHES = 0.6; // light and dark patches a metre
const KNOBS = 2.2; // knobs a metre, on its walls
const STREAKS = [5, 0.35]; // streaks a metre on its walls, across, and down them
const LAYERS = 2.5; // layers a metre, up its walls
// Metres deep (in the light): its grain, its floors' cracks and patches, and its walls' knobs.
const DEEP = [0.012, 0.025, 0.05, 0.14];

/** The rock's look, on the meshes that are rock underground. */
export function dressRock(land: Object3D) {
  for (const name of ["caves", "tunnel"]) {
    const mesh = land.getObjectByName(name);
    if (mesh instanceof Mesh) mesh.material = rocky(mesh.material as Material);
  }
}

function rocky(material: Material) {
  const own = material.clone();
  own.onBeforeCompile = (shader: WebGLProgramParametersWithUniforms) => {
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 rockAt;\nvarying vec3 rockNormal;")
      .replace(
        "#include <begin_vertex>",
        "#include <begin_vertex>\nrockAt = (modelMatrix * vec4(transformed, 1.0)).xyz;\nrockNormal = mat3(modelMatrix) * objectNormal;"
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
        varying vec3 rockAt;
        varying vec3 rockNormal;
        float rockHeight;
        float rockHash(vec3 p) {
          p = fract(p * 0.3183099 + 0.1) * 17.0;
          return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
        }
        float rockNoise(vec3 p) {
          vec3 i = floor(p), f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(
            mix(mix(rockHash(i), rockHash(i + vec3(1, 0, 0)), f.x),
                mix(rockHash(i + vec3(0, 1, 0)), rockHash(i + vec3(1, 1, 0)), f.x), f.y),
            mix(mix(rockHash(i + vec3(0, 0, 1)), rockHash(i + vec3(1, 0, 1)), f.x),
                mix(rockHash(i + vec3(0, 1, 1)), rockHash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
        }
        // How far from the nearest crack (between the rock's cells), in cells.
        float rockCrack(vec3 p) {
          vec3 i = floor(p), f = fract(p);
          float near = 8.0, next = 8.0;
          for (int z = -1; z <= 1; z++) for (int y = -1; y <= 1; y++) for (int x = -1; x <= 1; x++) {
            vec3 cell = vec3(x, y, z);
            vec3 seed = cell + vec3(rockHash(i + cell), rockHash(i + cell + 19.1), rockHash(i + cell + 47.3)) - f;
            float d = dot(seed, seed);
            if (d < near) { next = near; near = d; } else if (d < next) next = d;
          }
          return sqrt(next) - sqrt(near);
        }
        // Its light bent by how high the rock is, here and next to here (as three.js's bump maps are).
        vec3 rockBump(vec3 at, vec3 normal, float height, float facing) {
          vec3 across = dFdx(at), up = dFdy(at);
          vec3 r1 = cross(up, normal), r2 = cross(normal, across);
          float det = dot(across, r1) * facing;
          vec3 slope = sign(det) * (dFdx(height) * r1 + dFdy(height) * r2);
          return normalize(abs(det) * normal - slope);
        }`
      )
      .replace(
        "#include <color_fragment>",
        `#include <color_fragment>
        {
          // (Each finer pattern, faded out where it's finer than a few pixels.)
          float size = length(fwidth(rockAt));
          float grainSeen = 1.0 - smoothstep(0.25, 0.6, size * ${GRAIN}.0);
          float cracksSeen = 1.0 - smoothstep(0.05, 0.16, size * ${CRACKS});
          float grain = (rockNoise(rockAt * ${GRAIN}.0) * 0.6 + rockNoise(rockAt * ${GRAIN * 2.3}) * 0.4 - 0.5) * grainSeen;
          float blotch = rockNoise(rockAt * ${BLOTCHES}) * 0.6 + rockNoise(rockAt * ${BLOTCHES * 2.7}) * 0.4 - 0.5;
          // (Which way it faces: up, a floor, or a wall or roof. From its
          // normals, not from how it changes across the screen: that wavers a
          // little from pixel to pixel, and its bumps, from how their height
          // changes, made the wavering, between floor and wall, a speckle.)
          vec3 facing = normalize(rockNormal);
          facing *= sign(dot(facing, cameraPosition - rockAt)); // (the side of it you see)
          float floor = smoothstep(0.6, 0.9, facing.y);
          // Its floors: worn, with a few faint cracks, wandering.
          vec3 wander = vec3(rockNoise(rockAt * 1.7), rockNoise(rockAt * 1.7 + 31.0), rockNoise(rockAt * 1.7 + 67.0)) - 0.5;
          float crack = (1.0 - smoothstep(0.0, 0.045, rockCrack((rockAt + wander * 0.45) * ${CRACKS}))) * cracksSeen;
          float worn = 0.5 * grain + 0.55 * blotch - 0.15 * crack;
          float wornHeight = ${DEEP[0]} * grain - ${DEEP[1]} * 0.3 * crack + ${DEEP[2]} * blotch;
          // Its walls: knobbly (rounded lumps, crowded together, dark in the creases
          // between), streaked down, and in layers.
          float knob = 1.0 - abs(rockNoise(rockAt * ${KNOBS}) * 2.0 - 1.0);
          knob = 0.65 * knob + 0.35 * (1.0 - abs(rockNoise(rockAt * ${KNOBS * 2.3}) * 2.0 - 1.0));
          float streak = rockNoise(vec3(rockAt.x * ${STREAKS[0]}.0, rockAt.y * ${STREAKS[1]}, rockAt.z * ${STREAKS[0]}.0)) - 0.5;
          float layer = sin(rockAt.y * ${LAYERS} * 6.2832 + rockNoise(rockAt * 0.8) * 5.0) * 0.5;
          float rough = 0.4 * grain + 0.35 * blotch + 0.7 * (knob - 0.6) + 0.22 * streak + 0.1 * layer;
          float roughHeight = ${DEEP[0]} * grain + ${DEEP[3]} * knob;
          diffuseColor.rgb *= 1.0 + mix(rough, worn, floor);
          rockHeight = mix(roughHeight, wornHeight, floor);
        }`
      )
      .replace(
        "#include <normal_fragment_maps>",
        "#include <normal_fragment_maps>\nnormal = rockBump(-vViewPosition, normal, rockHeight, faceDirection);"
      );
  };
  own.customProgramCacheKey = () => "rock";
  return own;
}
