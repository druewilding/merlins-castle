// A soft golden glow round the object you're pointing at (the one E would take):
// a shell of it, a few pixels bigger all round on the screen (so it hugs the
// thin key, and still shows round something far off), drawn behind it, so
// only its rim shows round the object's edges. It pulses gently (unless
// motion is reduced).

import { BackSide, BufferGeometry, Color, type Material, Mesh, type Object3D, ShaderMaterial, Vector2 } from "three";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

const WIDTH = 3; // pixels (CSS pixels), round the object
const STRENGTH = 0.4; // how strong it is (0 to 1)
const PULSE = 0.1; // and how far it pulses, either side
const GOLD = "#ffd84a";

export class Glow {
  private shells = new Map<BufferGeometry, BufferGeometry>(); // each shape's shell, made once
  private material: ShaderMaterial;
  private showing: Mesh[] = [];
  private on: Object3D | undefined;

  constructor(private reducedMotion: boolean) {
    this.material = new ShaderMaterial({
      uniforms: {
        width: { value: WIDTH },
        screen: { value: new Vector2(innerWidth, innerHeight) },
        colour: { value: new Color(GOLD) },
        strength: { value: STRENGTH },
      },
      // Out along its (smoothed) normals, as they look on the screen: a shell
      // all round it, with no gaps at the corners.
      vertexShader: `
        uniform float width;
        uniform vec2 screen;
        void main() {
          vec4 at = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          vec2 out_ = (projectionMatrix * vec4(normalMatrix * normal, 0.0)).xy;
          if (dot(out_, out_) > 1e-8) at.xy += normalize(out_) * width * 2.0 / screen * at.w;
          gl_Position = at;
        }`,
      fragmentShader: `
        uniform vec3 colour;
        uniform float strength;
        void main() {
          gl_FragColor = vec4(colour, strength);
        }`,
      side: BackSide,
      transparent: true,
      depthWrite: false,
    });
  }

  /** Glowing round this object, or none. */
  show(model: Object3D | undefined) {
    if (model === this.on) return;
    for (const shell of this.showing) shell.removeFromParent();
    this.showing = [];
    this.on = model;
    model?.traverse((node) => {
      if (!(node instanceof Mesh) || this.showing.includes(node)) return;
      const shell = new Mesh(this.shellOf(node.geometry as BufferGeometry), this.material as Material);
      shell.renderOrder = -1;
      node.add(shell);
      this.showing.push(shell);
    });
  }

  /** Each frame: the pulse. */
  update(time: number) {
    if (!this.on) return;
    (this.material.uniforms.screen.value as Vector2).set(innerWidth, innerHeight);
    if (!this.reducedMotion) this.material.uniforms.strength.value = STRENGTH + PULSE * Math.sin(time * 4);
  }

  // Its corners joined up (its faces each have their own corners, to look
  // flat), so the normals there point out between the faces.
  private shellOf(geometry: BufferGeometry) {
    let shell = this.shells.get(geometry);
    if (!shell) {
      const shape = new BufferGeometry();
      shape.setAttribute("position", geometry.getAttribute("position"));
      if (geometry.index) shape.setIndex(geometry.index);
      shell = mergeVertices(shape);
      shell.computeVertexNormals();
      this.shells.set(geometry, shell);
    }
    return shell;
  }
}
