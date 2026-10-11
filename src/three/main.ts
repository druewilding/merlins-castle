// Merlin's Castle in 3D: the first step. One place, the grassy bank, built
// in Blender (art/blender/grassy-bank.py) to walk around in. See PLAN-V3.md.
//
// For checking by eye: ?at=x,z,yaw (yaw in degrees, 0 looks north) starts you
// somewhere else, already walking.

import "./style.css";

import {
  ACESFilmicToneMapping,
  Color,
  DirectionalLight,
  Fog,
  HemisphereLight,
  type Material,
  Mesh,
  type MeshStandardMaterial,
  type Object3D,
  PCFShadowMap,
  Scene,
  SRGBColorSpace,
  Timer,
  Vector3,
  WebGLRenderer,
} from "three";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import grassyBank from "./models/grassy-bank.glb?url";
import { type Box, type Circle, Player } from "./player";
import { sky } from "./sky";

const HAZE = new Color("#d9dcc4");
// Where the light comes from: low in the west, a little north, as in the paintings.
const SUN = new Vector3(-0.75, 0.42, -0.5).normalize();
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

const root = document.getElementById("world")!;
const renderer = new WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = SRGBColorSpace;
renderer.toneMapping = ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = PCFShadowMap;
root.append(renderer.domElement);

const scene = new Scene();
scene.fog = new Fog(HAZE, 30, 260);
scene.add(sky(SUN, HAZE));
scene.add(new HemisphereLight("#cfe2ff", "#6d7a3c", 1.25));

const sunlight = new DirectionalLight("#ffdcae", 2.8);
sunlight.castShadow = true;
sunlight.shadow.mapSize.set(2048, 2048);
Object.assign(sunlight.shadow.camera, { left: -45, right: 45, top: 45, bottom: -45, near: 1, far: 300 });
sunlight.shadow.bias = -0.0004;
sunlight.shadow.normalBias = 0.04;
scene.add(sunlight, sunlight.target);

const player = new Player(renderer.domElement);
const overlay = document.createElement("div");
overlay.className = "overlay";
overlay.innerHTML = "<h1>Merlin's Castle</h1><p>Loading the grassy bank…</p>";
root.append(overlay);

const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const place = await loader.loadAsync(grassyBank);
const ground: Object3D[] = [];
const circles: Circle[] = [];
const boxes: Box[] = [];
let start = { x: 0, z: 0 };

place.scene.traverse((node) => {
  if (node.name.startsWith("col-box")) {
    boxes.push({ x: node.position.x, z: node.position.z, halfX: node.scale.x, halfZ: node.scale.z });
  } else if (node.name.startsWith("col-")) {
    circles.push({ x: node.position.x, z: node.position.z, r: node.scale.x });
  } else if (node.name === "start") {
    start = { x: node.position.x, z: node.position.z };
  }
  if (!(node instanceof Mesh)) return;
  if (node.name.startsWith("far-")) {
    // Far-off things are painted into the haze themselves, so the fog doesn't swallow them.
    const material = (node.material as Material).clone() as MeshStandardMaterial;
    material.fog = false;
    const mountain = node.name === "far-mountain";
    material.color = new Color(mountain ? "#b4b0c6" : "#b9c4b4");
    // Lifting the shadows towards the sky's colour: the haze of distance.
    material.emissive = new Color(mountain ? "#7d7f99" : "#3c4a3a");
    node.material = material;
    return;
  }
  node.castShadow = !["ground", "paths", "flowers"].includes(node.name);
  node.receiveShadow = true;
  if (node.name === "ground") ground.push(node);
});
scene.add(place.scene);
player.standOn(ground);
player.circles = circles;
player.boxes = boxes;

// For checking by script while developing.
if (import.meta.env.DEV) Object.assign(window, { world: { player, scene } });

const at = new URLSearchParams(location.search).get("at")?.split(",").map(Number);
if (at && at.length >= 2) player.place(at[0], at[1], ((at[2] ?? 0) * Math.PI) / 180);
else player.place(start.x, start.z, 0);

overlay.innerHTML = `
  <h1>Merlin's Castle</h1>
  <p class="start">Click to walk</p>
  <p class="keys">Mouse to look · WASD or arrows to walk · Shift to run · Esc to stop</p>
  <p class="keys touch">Left thumb to walk · right thumb to look</p>`;
overlay.hidden = Boolean(at);
overlay.addEventListener("click", () => {
  void renderer.domElement.requestPointerLock?.();
  overlay.hidden = true;
});
overlay.addEventListener("touchend", () => (overlay.hidden = true));
document.addEventListener("pointerlockchange", () => {
  if (!player.locked && !matchMedia("(pointer: coarse)").matches) overlay.hidden = false;
});

function resize() {
  renderer.setSize(innerWidth, innerHeight);
  player.camera.aspect = innerWidth / innerHeight;
  player.camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();

const timer = new Timer();
renderer.setAnimationLoop((time) => {
  timer.update(time);
  const dt = Math.min(timer.getDelta(), 0.1);
  player.update(dt, reducedMotion);
  // The sun's shadows follow you, so they're sharp wherever you are.
  sunlight.target.position.copy(player.position);
  sunlight.position.copy(player.position).addScaledVector(SUN, 150);
  renderer.render(scene, player.camera);
});
