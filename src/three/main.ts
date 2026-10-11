// Merlin's Castle in 3D: the whole land in grey boxes, built in Blender
// (art/blender/land.py), to walk from place to place. See PLAN-V3.md.
//
// L shows or hides the places' names. For checking by eye: ?at=x,z,yaw (yaw
// in degrees, 0 looks north) starts you somewhere else, already walking.

import "./style.css";

import {
  ACESFilmicToneMapping,
  Color,
  CylinderGeometry,
  DirectionalLight,
  Fog,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  PCFShadowMap,
  PointLight,
  Scene,
  SRGBColorSpace,
  Timer,
  Vector3,
  WebGLRenderer,
} from "three";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import daJson from "../../data/da.json";
import worldJson from "../../data/world.json";
import { messages } from "../engine/engine";
import { localise, type WorldText } from "../engine/localise";
import type { Direction, World } from "../engine/types";
import { LANGUAGE } from "../shared/strings";
import { DEATHS, LOST, placeAt, PLACES } from "./layout";
import landHeights from "./models/land.bin?url";
import landModel from "./models/land.glb?url";
import land from "./models/land.json";
import { type Box, type Circle, type Ground, type Hall, nearest, Player, type Walkable } from "./player";
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
// only if you've lit the lamp). It falls off gently: a light this close
// would otherwise blaze on any wall you walk up to.
const lamp = new PointLight("#ffb866", 0, 14, 0.6);
scene.add(lamp);
// And caves and rooms have their own light (torches, the dragon's fire,
// gold, a hearth), always on, so a lit room seen through a doorway is lit.
// A few lights go to the lit halls nearest you (always the same number of
// lights: changing it makes every material rebuild, a stutter).
const ROOM_LIGHTS = 4;
const roomLights = Array.from({ length: ROOM_LIGHTS }, () => new PointLight("#ffa24a", 0, 30, 1.2));
scene.add(...roomLights);
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
const halls = land.halls as Record<string, Hall & { tall: number; light?: string; glow?: number }>;
player.halls = new Map(Object.entries(halls));

// Solid things, and the obstacles (all closed, until the game can open them).
const circles: Circle[] = land.circles.map(([x, z, r]) => ({ x, z, r }));
const boxes: Box[] = land.boxes.map(([x, z, halfX, halfZ]) => ({ x, z, halfX, halfZ }));
type Obstacle = { box?: number[]; circle?: number[]; under?: boolean };
const obstacles = land.obstacles as Record<string, Obstacle>;
const underCircles: Circle[] = land.under.circles.map(([x, z, r, top]) => ({ x, z, r, top }));
const underBoxes: Box[] = land.under.boxes.map(([x, z, halfX, halfZ, top]) => ({ x, z, halfX, halfZ, top }));
// You bump into an obstacle in your way this far before it, so you can see
// what it is (and know there's something to do here).
const AHEAD = 5;
// One shape for each obstacle, with the names of every exit it blocks (a gate
// blocks the way through from both sides).
const shapes = new Map<string, Obstacle & { names: string[] }>();
for (const [exit, obstacle] of Object.entries(obstacles)) {
  const key = JSON.stringify(obstacle);
  const shape = shapes.get(key) ?? { ...obstacle, names: [] };
  shape.names.push(exit);
  shapes.set(key, shape);
}
function openObstacles(open: boolean) {
  for (const under of [false, true]) {
    const closed = open ? [] : [...shapes.values()].filter((shape) => Boolean(shape.under) === under);
    // The obstacles first, so you bump into them before any wall they stand in.
    player.solid(
      [
        ...closed.flatMap(({ circle, names }) =>
          circle ? [{ x: circle[0], z: circle[1], r: circle[2], names, ahead: AHEAD }] : []
        ),
        ...(under ? underCircles : circles),
      ],
      [
        ...closed.flatMap(({ box, names }) =>
          box ? [{ x: box[0], z: box[1], halfX: box[2], halfZ: box[3], names, ahead: AHEAD }] : []
        ),
        ...(under ? underBoxes : boxes),
      ],
      under
    );
  }
}
openObstacles(false);
const [west, east, south, north] = land.bounds;
player.bounds = { west, east, north: -north, south: -south };

// Mist where you'd get lost, and red where a way through kills you.
const mist = new MeshBasicMaterial({ color: "#f4f6f8", transparent: true, opacity: 0.55, depthWrite: false });
const danger = new MeshBasicMaterial({ color: "#d9503f", transparent: true, opacity: 0.5, depthWrite: false });
for (const { x, z, under } of LOST) {
  if (under) {
    // In the tunnel, where it runs out into the dark.
    const way = player.ways.reduce((a, b) => (nearest(a, x, z).d < nearest(b, x, z).d ? a : b));
    const cloud = new Mesh(new CylinderGeometry(3, 3, 3.4, 24, 1, true), mist);
    cloud.position.set(x, nearest(way, x, z).floor + 1.7, z);
    scene.add(cloud);
    continue;
  }
  const cloud = new Mesh(new CylinderGeometry(10, 10, 10, 24, 1, true), mist);
  cloud.position.set(x, (ground(x, z) ?? 0) + 5, z);
  scene.add(cloud);
}
for (const { x, z } of DEATHS) {
  const mark = new Mesh(new CylinderGeometry(3, 3, 6, 16, 1, true), danger);
  mark.position.set(x, (ground(x, z) ?? 0) + 3, z);
  scene.add(mark);
}

// A place's name, from its id (for now; PLAN-V3.md).
const name = (id: string) => id.replace(/-/g, " ").replace(/^./, (letter) => letter.toUpperCase());

const start = PLACES.get("grassy-bank")!;
const at = new URLSearchParams(location.search).get("at")?.split(",").map(Number);
if (at && at.length >= 2) player.place(at[0], at[1], ((at[2] ?? 0) * Math.PI) / 180);
else player.place(start.x, start.z + 12, 0);
let room = player.under?.hall ?? placeAt(player.position.x, player.position.z, "grassy-bank", player.halls);

// Walking into an obstacle, the original's words for it at the bottom of the
// screen: what it says when you try that exit (the way you were going
// through it: an obstacle only stops you going the way its exits go).
const english = worldJson as unknown as World;
const world = LANGUAGE === "da" ? localise(english, daJson as WorldText) : english;
const said = document.createElement("p");
said.className = "said";
said.setAttribute("aria-live", "polite");
root.append(said);
let quiet = 0;
player.onBump = (exit) => {
  const [id, direction] = exit.split(" ");
  const way = world.rooms[id]?.exits[direction as Direction];
  const words = way?.obstacle?.blocked ?? way?.message ?? messages(world).cantGo;
  // (A teletext colour code shows as a space.)
  said.textContent = words
    .replace(/\{\w+\}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  said.classList.add("shown");
  clearTimeout(quiet);
  quiet = window.setTimeout(() => said.classList.remove("shown"), 3500);
};

// While developing: the debug panel (the 0 key), and a handle for test scripts.
// The built game leaves all of this out.
if (import.meta.env.DEV) {
  Object.assign(window, { world: { player, scene, ground, walkable, renderer, places: PLACES } });
  const { debug } = await import("./debug");
  debug(
    {
      player,
      walkable,
      heights: { values: heights, ...land.ground },
      grid: land.walkable,
      scene,
      ground,
      obstacles: [...shapes.values()],
      ahead: AHEAD,
      fatal: (exit) => {
        const [id, direction] = exit.split(" ");
        const way = english.rooms[id]?.exits[direction as Direction];
        return Boolean(way?.fatal || way?.obstacle?.fatal);
      },
      openObstacles,
      room: () => room,
      name,
      // A fresh frame, read straight away (before the browser clears it).
      picture: () => {
        renderer.render(scene, player.camera);
        return renderer.domElement;
      },
    },
    () => (overlay.hidden = true)
  );
}

overlay.innerHTML = `
  <h1>Merlin's Castle</h1>
  <p class="start">Click to walk</p>
  <p class="keys">Mouse to look · WASD or arrows to walk · Shift to run · Space to jump · Ctrl or C to crouch · Esc to stop</p>
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

// From daylight (0) to lamplight (1) over the first few metres down; and
// in a building, the sky's light softens a little (the sun stays out: the
// roof's shadow keeps it off you, and outside the door it's still day).
let caveLit = 0;
let indoors = 0;
const litHalls = Object.values(halls).filter((hall) => hall.light);
function lightFor(depth: number, time: number, dt: number) {
  indoors += ((player.under?.indoor ? 1 : 0) - indoors) * Math.min(1, dt * 4);
  const under = Math.min(1, Math.max(0, (depth - 0.5) / 3));
  sunlight.intensity = 2.8 * (1 - under);
  skylight.intensity = 1.25 * (1 - Math.max(under * 0.92, indoors * 0.55));
  const flicker = reducedMotion ? 1 : 0.92 + 0.05 * Math.sin(time / 90) + 0.03 * Math.sin(time / 37);
  lamp.intensity = 3.5 * Math.max(under, indoors * 0.4) * flicker;
  lamp.position.set(player.position.x, player.position.y + 1.4, player.position.z);

  // The lit halls nearest you, each with its own light.
  const p = player.position;
  const away = (hall: (typeof litHalls)[number]) => Math.hypot(hall.x - p.x, hall.floor - p.y, hall.z - p.z) - hall.r;
  const nearest = litHalls.filter((hall) => away(hall) < 40).sort((a, b) => away(a) - away(b));
  roomLights.forEach((light, k) => {
    const hall = nearest[k];
    light.intensity = hall ? (hall.glow ?? 0) * 4 * flicker : 0;
    if (!hall) return;
    light.color.set(hall.light!);
    light.distance = hall.r * 1.8;
    light.position.set(hall.x, hall.floor + hall.tall * 0.6, hall.z);
  });

  const hall = player.under?.hall ? halls[player.under.hall] : undefined;
  caveLit += ((hall?.light ? 1 : 0) - caveLit) * Math.min(1, dt * 3);
  fog.color.copy(HAZE).lerp(DARK, under);
  fog.near = 40 - 38 * under;
  fog.far = 320 - 290 * under + 40 * caveLit;
}

const timer = new Timer();
renderer.setAnimationLoop((time) => {
  timer.update(time);
  const dt = Math.min(timer.getDelta(), 0.1);
  player.update(dt, reducedMotion);
  // Along a way underground, you're still where you set off from (PLAN-V3.md),
  // until you come into a hall.
  if (player.under?.hall) room = player.under.hall;
  else if (!player.inside) room = placeAt(player.position.x, player.position.z, room, player.halls);
  lightFor(player.depth, time, dt);
  here.textContent = name(room);
  // The sun's shadows follow you, so they're sharp wherever you are.
  sunlight.target.position.copy(player.position);
  sunlight.position.copy(player.position).addScaledVector(SUN, 200);
  renderer.render(scene, player.camera);
});
