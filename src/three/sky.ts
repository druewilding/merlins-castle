// The sky: a great dome, deep blue above and warm gold near the low summer
// sun in the west, as in the paintings.

import { BackSide, Color, Mesh, ShaderMaterial, SphereGeometry, type Vector3 } from "three";

export function sky(sun: Vector3, horizon: Color): Mesh {
  const material = new ShaderMaterial({
    side: BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      sun: { value: sun.clone().normalize() },
      top: { value: new Color("#4f86c9") },
      horizon: { value: horizon },
      glow: { value: new Color("#ffc46a") },
    },
    vertexShader: /* glsl */ `
      varying vec3 direction;
      void main() {
        direction = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 sun;
      uniform vec3 top;
      uniform vec3 horizon;
      uniform vec3 glow;
      varying vec3 direction;
      void main() {
        float up = max(direction.y, 0.0);
        vec3 colour = mix(horizon, top, pow(up, 0.55));
        float toward = max(dot(direction, sun), 0.0);
        // (A wide warm glow round the sun, low in the sky, and the sun itself.)
        float low = 1.0 - smoothstep(0.0, 0.6, up);
        colour = mix(colour, glow, pow(toward, 3.0) * 0.55 * low + pow(toward, 12.0) * 0.6 + pow(toward, 600.0));
        gl_FragColor = vec4(colour, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  });
  const dome = new Mesh(new SphereGeometry(2500, 32, 16), material);
  dome.renderOrder = -1;
  dome.frustumCulled = false;
  return dome;
}
