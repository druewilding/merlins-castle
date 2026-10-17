// The golden hour, as in the paintings: out of doors, everything bathed in
// the low sun's warm light (the lights a little golden, the shadows a warm
// olive, not grey), and a soft glow spilling in from the sun's side when you
// look towards it. Drawn over the whole picture, before it's tone mapped;
// underground and in the dark, none of it (amount).

import {
  HalfFloatType,
  type PerspectiveCamera,
  type Scene,
  ShaderMaterial,
  Vector2,
  Vector3,
  type WebGLRenderer,
  WebGLRenderTarget,
} from "three";
import { EffectComposer } from "three/examples/jsm/postprocessing/EffectComposer.js";
import { OutputPass } from "three/examples/jsm/postprocessing/OutputPass.js";
import { RenderPass } from "three/examples/jsm/postprocessing/RenderPass.js";
import { ShaderPass } from "three/examples/jsm/postprocessing/ShaderPass.js";

const WARM = "vec3(1.12, 1.0, 0.78)"; // the light, golden
const OLIVE = "vec3(0.022, 0.018, 0.002)"; // the shadows lifted, warmly
const SUNGLOW = "vec3(0.2, 0.13, 0.04)"; // and the glow from the sun's side
const SPREAD = 2.6; // (how quickly the glow fades, away from the sun: larger, quicker)

export class Golden {
  private composer: EffectComposer;
  private grade: ShaderPass;
  private ahead = new Vector3();
  private sunAt = new Vector3();

  constructor(
    renderer: WebGLRenderer,
    scene: Scene,
    private camera: PerspectiveCamera,
    private sun: Vector3
  ) {
    // (Kept smooth-edged, as drawn straight to the screen.)
    this.composer = new EffectComposer(renderer, new WebGLRenderTarget(1, 1, { type: HalfFloatType, samples: 4 }));
    this.composer.addPass(new RenderPass(scene, camera));
    this.grade = new ShaderPass(
      new ShaderMaterial({
        uniforms: {
          tDiffuse: { value: null },
          amount: { value: 1 },
          sun: { value: new Vector2() },
          facing: { value: 0 },
          aspect: { value: 1 },
        },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform sampler2D tDiffuse;
          uniform float amount;
          uniform vec2 sun;
          uniform float facing;
          uniform float aspect;
          varying vec2 vUv;
          void main() {
            vec4 colour = texture2D(tDiffuse, vUv);
            float bright = dot(colour.rgb, vec3(0.2126, 0.7152, 0.0722));
            vec3 golden = colour.rgb * ${WARM} + ${OLIVE} * (1.0 - smoothstep(0.0, 0.5, bright));
            float glow = exp(-length((vUv - sun) * vec2(aspect, 1.0)) * ${SPREAD.toFixed(2)}) * facing;
            golden += ${SUNGLOW} * glow;
            gl_FragColor = vec4(mix(colour.rgb, golden, amount), colour.a);
          }
        `,
      })
    );
    this.composer.addPass(this.grade);
    this.composer.addPass(new OutputPass());
  }

  setSize(width: number, height: number, pixelRatio: number) {
    this.composer.setPixelRatio(pixelRatio);
    this.composer.setSize(width, height);
    this.grade.uniforms.aspect.value = width / height;
  }

  /** The picture, as golden as it is out of doors here (0 to 1). */
  render(amount: number) {
    const u = this.grade.uniforms;
    u.amount.value = amount;
    // Where the sun is on the screen (or off it, to the side it's on), and
    // how much you're looking its way (behind you, no glow).
    this.camera.getWorldDirection(this.ahead);
    const towards = this.ahead.dot(this.sun);
    u.facing.value = Math.max(0, Math.min(1, towards / 0.7)) ** 2;
    if (towards > 0.01) {
      this.sunAt.copy(this.camera.position).addScaledVector(this.sun, 1000).project(this.camera);
      u.sun.value.set(this.sunAt.x * 0.5 + 0.5, this.sunAt.y * 0.5 + 0.5);
    }
    this.composer.render();
  }
}
