// Merlin's Castle in 3D: the whole land in grey boxes, built in Blender
// (art/blender/land.py), to walk from place to place. See PLAN-V3.md.
//
// L shows or hides the places' names. For checking by eye: ?at=x,z,yaw (yaw
// in degrees, 0 looks north) starts you somewhere else, already walking.

import "./style.css";

import {
  ACESFilmicToneMapping,
  CanvasTexture,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Fog,
  Group,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  PCFShadowMap,
  PointLight,
  Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  Timer,
  Vector3,
  WebGLRenderer,
} from "three";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import { DEATHS, LOST, placeAt, PLACES } from "./layout";
import landHeights from "./models/land.bin?url";
import landModel from "./models/land.glb?url";
import land from "./models/land.json";
import { type Box, type Circle, type Ground, Player, type Walkable } from "./player";
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
const fog = new Fog(HAZE, 40, 320);
scene.fog = fog;
scene.add(sky(SUN, HAZE));
const skylight = new HemisphereLight("#cfe2ff", "#6d7a3c", 1.25);
scene.add(skylight);

// Underground, the daylight fades and a warm lamp glow takes over (one day,
// only if you've lit the lamp).
const lamp = new PointLight("#ffb866", 0, 16, 1.6);
scene.add(lamp);
const DARK = new Color("#0b0806");

const sunlight = new DirectionalLight("#ffdcae", 2.8);
sunlight.castShadow = true;
sunlight.shadow.mapSize.set(2048, 2048);
Object.assign(sunlight.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 1, far: 400 });
sunlight.shadow.bias = -0.0004;
sunlight.shadow.normalBias = 0.05;
scene.add(sunlight, sunlight.target);

const player = new Player(renderer.domElement);
const overlay = document.createElement("div");
overlay.className = "overlay";
overlay.innerHTML = "<h1>Merlin's Castle</h1><p>Loading the land…</p>";
const here = document.createElement("div");
here.className = "here";
root.append(overlay, here);

// The land you see, and the heights of the ground you walk on.
const [model, file] = await Promise.all([
  new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(landModel),
  fetch(landHeights).then(async (response) => response.arrayBuffer()),
]);
const heights = new Float32Array(file, 0, land.ground.nx * land.ground.ny);
model.scene.traverse((node) => {
  if (!(node instanceof Mesh)) return;
  node.castShadow = !["paths", "water"].includes(node.name);
  node.receiveShadow = node.name !== "water";
});
scene.add(model.scene);

// The heights are in Blender's axes (y is north), on a grid; in between, blend.
const { x0, y0, step, nx, ny } = land.ground;
const ground: Ground = (x, z) => {
  const i = (x - x0) / step;
  const j = (-z - y0) / step;
  if (i < 0 || j < 0 || i >= nx - 1 || j >= ny - 1) return undefined;
  const i0 = Math.floor(i);
  const j0 = Math.floor(j);
  const fi = i - i0;
  const fj = j - j0;
  const h = (a: number, b: number) => heights[(j0 + b) * nx + i0 + a];
  return (h(0, 0) * (1 - fi) + h(1, 0) * fi) * (1 - fj) + (h(0, 1) * (1 - fi) + h(1, 1) * fi) * fj;
};
// Where you can stand, a square metre at a time (again in Blender's axes).
const mask = land.walkable;
const standable = new Uint8Array(file, mask.offset, mask.nx * mask.ny);
const walkable: Walkable = (x, z) => {
  const i = Math.floor((x - mask.x0) / mask.step);
  const j = Math.floor((-z - mask.y0) / mask.step);
  return i >= 0 && j >= 0 && i < mask.nx && j < mask.ny && standable[j * mask.nx + i] === 1;
};
player.standOn(ground, walkable);
player.ways = Object.values(land.ways);

// Solid things, and the obstacles (all closed, until the game can open them).
const circles: Circle[] = land.circles.map(([x, z, r]) => ({ x, z, r }));
const boxes: Box[] = land.boxes.map(([x, z, halfX, halfZ]) => ({ x, z, halfX, halfZ }));
const obstacles = land.obstacles as Record<string, { box?: number[]; circle?: number[] }>;
function openObstacles(open: boolean) {
  const closed = open ? [] : Object.values(obstacles);
  player.solid(
    [...circles, ...closed.flatMap(({ circle }) => (circle ? [{ x: circle[0], z: circle[1], r: circle[2] }] : []))],
    [...boxes, ...closed.flatMap(({ box }) => (box ? [{ x: box[0], z: box[1], halfX: box[2], halfZ: box[3] }] : []))]
  );
}
openObstacles(false);
const [west, east, south, north] = land.bounds;
player.bounds = { west, east, north: -north, south: -south };

// Mist where you'd get lost, and red where a way through kills you.
const mist = new MeshBasicMaterial({ color: "#f4f6f8", transparent: true, opacity: 0.55, depthWrite: false });
const danger = new MeshBasicMaterial({ color: "#d9503f", transparent: true, opacity: 0.5, depthWrite: false });
for (const { x, z } of LOST) {
  const cloud = new Mesh(new CylinderGeometry(10, 10, 10, 24, 1, true), mist);
  cloud.position.set(x, (ground(x, z) ?? 0) + 5, z);
  scene.add(cloud);
}
for (const { x, z } of DEATHS) {
  const mark = new Mesh(new CylinderGeometry(3, 3, 6, 16, 1, true), danger);
  mark.position.set(x, (ground(x, z) ?? 0) + 3, z);
  scene.add(mark);
}

// The places' names, floating over them: for finding your way while the
// world is grey.
const name = (id: string) => id.replace(/-/g, " ").replace(/^./, (letter) => letter.toUpperCase());
const labels = new Group();
for (const [id, { x, z }] of PLACES) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;
  const pen = canvas.getContext("2d")!;
  pen.font = "600 48px Cinzel, Georgia, serif";
  pen.textAlign = "center";
  pen.textBaseline = "middle";
  pen.lineWidth = 8;
  pen.strokeStyle = "rgba(20, 14, 8, 0.85)";
  pen.fillStyle = "#f6ecd2";
  pen.strokeText(name(id), 256, 48);
  pen.fillText(name(id), 256, 48);
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  const label = new Sprite(new SpriteMaterial({ map: texture, depthTest: false, fog: false }));
  label.scale.set(12, 2.25, 1);
  label.position.set(x, (ground(x, z) ?? 0) + 9, z);
  labels.add(label);
}
scene.add(labels);
let showLabels = true;
addEventListener("keydown", (event) => {
  if (event.code === "KeyL") showLabels = !showLabels;
});

const start = PLACES.get("grassy-bank")!;
const at = new URLSearchParams(location.search).get("at")?.split(",").map(Number);
if (at && at.length >= 2) player.place(at[0], at[1], ((at[2] ?? 0) * Math.PI) / 180);
else player.place(start.x, start.z + 12, 0);
let room = placeAt(player.position.x, player.position.z, "grassy-bank");

// While developing: the debug panel (the 0 key), and a handle for test scripts.
// The built game leaves all of this out.
if (import.meta.env.DEV) {
  Object.assign(window, { world: { player, scene, ground, walkable } });
  const { debug } = await import("./debug");
  debug(
    {
      player,
      walkable,
      heights: { values: heights, ...land.ground },
      grid: land.walkable,
      obstacles,
      openObstacles,
      room: () => room,
      name,
    },
    () => (overlay.hidden = true)
  );
}

overlay.innerHTML = `
  <h1>Merlin's Castle</h1>
  <p class="start">Click to walk</p>
  <p class="keys">Mouse to look · WASD or arrows to walk · Shift to run · L for names · Esc to stop</p>
  <p class="keys touch">Left thumb to walk · right thumb to look</p>`;
overlay.hidden = Boolean(at);
overlay.addEventListener("click", () => {
  void renderer.domElement.requestPointerLock?.();
  overlay.hidden = true;
});
overlay.addEventListener("touchend", () => (overlay.hidden = true));
// With the debug panel open, clicking the world looks around again.
renderer.domElement.addEventListener("click", () => {
  if (document.body.classList.contains("debugging")) void renderer.domElement.requestPointerLock?.();
});
document.addEventListener("pointerlockchange", () => {
  const debugging = document.body.classList.contains("debugging");
  if (!player.locked && !debugging && !matchMedia("(pointer: coarse)").matches) overlay.hidden = false;
});

function resize() {
  renderer.setSize(innerWidth, innerHeight);
  player.camera.aspect = innerWidth / innerHeight;
  player.camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();

// From daylight (0) to lamplight (1) over the first few metres down.
function lightFor(depth: number, time: number) {
  const under = Math.min(1, Math.max(0, (depth - 0.5) / 3));
  sunlight.intensity = 2.8 * (1 - under);
  skylight.intensity = 1.25 * (1 - under * 0.92);
  const flicker = reducedMotion ? 1 : 0.92 + 0.05 * Math.sin(time / 90) + 0.03 * Math.sin(time / 37);
  lamp.intensity = 14 * under * flicker;
  lamp.position.set(player.position.x + 0.3, player.position.y + 1.4, player.position.z);
  fog.color.copy(HAZE).lerp(DARK, under);
  fog.near = 40 - 38 * under;
  fog.far = 320 - 290 * under;
}

const timer = new Timer();
renderer.setAnimationLoop((time) => {
  timer.update(time);
  const dt = Math.min(timer.getDelta(), 0.1);
  player.update(dt, reducedMotion);
  // Under the land, you're still where you set off from (PLAN-V3.md).
  if (!player.inside) room = placeAt(player.position.x, player.position.z, room);
  lightFor(player.depth, time);
  labels.visible = showLabels && !player.inside; // they'd show through the tunnel's walls
  here.textContent = name(room);
  // The sun's shadows follow you, so they're sharp wherever you are.
  sunlight.target.position.copy(player.position);
  sunlight.position.copy(player.position).addScaledVector(SUN, 200);
  renderer.render(scene, player.camera);
});
