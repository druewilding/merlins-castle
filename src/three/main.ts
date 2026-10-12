// Merlin's Castle in 3D: the whole land in grey boxes, built in Blender
// (art/blender/land.py), to walk from place to place. See PLAN-V3.md.
//
// For checking by eye: ?at=x,z,yaw (yaw in degrees, 0 looks north) starts
// you somewhere else, already walking.

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
  type Object3D,
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
import { effects, messages, score } from "../engine/engine";
import { localise, type WorldText } from "../engine/localise";
import { type Direction, EXIT_ORDER, type World } from "../engine/types";
import { h } from "../shared/dom";
import { leave3d, listSaves, nextSaveName, restart3d, saveGame, takeHandoff, type ThreeSave } from "../shared/storage";
import { LANGUAGE, savedDate, savedTime, T } from "../shared/strings";
import { Felling } from "./felling";
import { items as setUpItems } from "./items";
import { Ladder } from "./ladder";
import { DEATHS, LOST, placeAt, PLACES } from "./layout";
import itemModels from "./models/items.glb?url";
import landHeights from "./models/land.bin?url";
import landModel from "./models/land.glb?url";
import land from "./models/land.json";
import { type Box, type Circle, type Ground, type Hall, nearest, Player, type Walkable } from "./player";
import { sky } from "./sky";
import { Trees, type TreeSpots } from "./trees";

const english = worldJson as unknown as World;
const world = LANGUAGE === "da" ? localise(english, daJson as WorldText) : english;

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
// Top left: which place you're in, and your score (what's on the grassy bank).
const corner = document.createElement("div");
corner.className = "corner";
const here = document.createElement("div");
here.className = "here";
const scored = document.createElement("div");
scored.className = "score";
corner.append(here, scored);
root.append(overlay, corner);

// The land you see, and the heights of the ground you walk on.
const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
const [model, file, things] = await Promise.all([
  loader.loadAsync(landModel),
  fetch(landHeights).then(async (response) => response.arrayBuffer()),
  loader.loadAsync(itemModels),
]);
const heights = new Float32Array(file, 0, land.ground.nx * land.ground.ny);
model.scene.traverse((node) => {
  if (!(node instanceof Mesh)) return;
  node.castShadow = !["paths", "water"].includes(node.name);
  node.receiveShadow = node.name !== "water";
});
scene.add(model.scene);
const spots = land.trees as TreeSpots;
const trees = new Trees(scene, model.scene, spots);
const stump = model.scene.getObjectByName("stump") as Mesh;
stump.removeFromParent();
const felling = new Felling(scene, trees.models, spots.kinds, spots.dense, stump, reducedMotion);

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

// Solid things, and the obstacles: closed, until an object in use opens one.
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
type Shape = Obstacle & { names: string[] };
const shapes = new Map<string, Shape>();
const shapeOf = new Map<string, Shape>(); // by exit ("old-stone-wall west")
for (const [exit, obstacle] of Object.entries(obstacles)) {
  const key = JSON.stringify(obstacle);
  const shape = shapes.get(key) ?? { ...obstacle, names: [] };
  shape.names.push(exit);
  shapes.set(key, shape);
  shapeOf.set(exit, shape);
}
// The walls you climb with the ladder: walls, open or not (the obstacle is
// only the reach that bounces you back), so you climb over, not through.
const exitOf = (name: string) => {
  const [id, direction] = name.split(" ");
  return english.rooms[id]?.exits[direction as Direction];
};
const walls = new Set(
  [...shapes.values()].filter(
    (shape) =>
      shape.box &&
      shape.names.some((name) => {
        const exit = exitOf(name);
        return exit?.obstacle?.needs === "ladder" && !exit.fatal && !exit.obstacle.fatal;
      })
  )
);
// Gates that swing open: the rusty gate's two halves (on their hinges, each
// turning the way that swings it north), open while the key's in use there.
const gates = new Map<Shape, { leaves: [Object3D, number][]; open: number; wants: number }>();
const rusty = shapeOf.get("rusty-gate north");
const leaves = (["gate-west", "gate-east"] as const).map((name) => model.scene.getObjectByName(name));
if (rusty && leaves[0] && leaves[1]) {
  gates.set(rusty, {
    leaves: [
      [leaves[0], 1],
      [leaves[1], -1],
    ],
    open: 0,
    wants: 0,
  });
}
const SWING = 1.75; // radians, open
// The dense trees across the mountain path, which the axe fells (felling.ts).
const dense = shapeOf.get("mountain-path north");
let allOpen = false; // (the debug panel's "open every obstacle")
let opened = new Set<Shape>(); // by an object in use
function solidify() {
  for (const under of [false, true]) {
    const here = [...shapes.values()].filter((shape) => Boolean(shape.under) === under);
    const closed = allOpen ? [] : here.filter((shape) => !opened.has(shape));
    const plain = allOpen ? [] : here.filter((shape) => walls.has(shape));
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
        ...plain.map(({ box }) => ({ x: box![0], z: box![1], halfX: box![2], halfZ: box![3] })),
        ...(under ? underBoxes : boxes),
      ],
      under
    );
  }
  player.throughHere();
}
function openObstacles(open: boolean) {
  allOpen = open;
  solidify();
}
solidify();
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

// A game loaded, or carried on from another version (or another language).
const handoff = takeHandoff();
let saveName = handoff?.saveName ?? ""; // the position last saved or loaded

const start = PLACES.get("grassy-bank")!;
const at = new URLSearchParams(location.search).get("at")?.split(",").map(Number);
if (at && at.length >= 2) player.place(at[0], at[1], ((at[2] ?? 0) * Math.PI) / 180);
else player.place(start.x, start.z + 12, 0);
let room = player.under?.hall ?? placeAt(player.position.x, player.position.z, "grassy-bank", player.halls);

// Walking into an obstacle, the original's words for it at the bottom of the
// screen: what it says when you try that exit (the way you were going
// through it: an obstacle only stops you going the way its exits go).
const said = document.createElement("p");
said.className = "said";
said.setAttribute("aria-live", "polite");
root.append(said);
let quiet = 0;
function say(words: string) {
  // (A teletext colour code shows as a space.)
  said.textContent = words
    .replace(/\{\w+\}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  said.classList.add("shown");
  clearTimeout(quiet);
  quiet = window.setTimeout(() => said.classList.remove("shown"), 3500);
}
player.onBump = (exit) => {
  const [id, direction] = exit.split(" ");
  const way = world.rooms[id]?.exits[direction as Direction];
  say(way?.obstacle?.blocked ?? way?.message ?? messages(world).cantGo);
};

// The objects, lying where the game puts them, and the five slots you carry
// them in. Using one opens the ways out of the place it's for: the ladder
// leans against the wall, always in the same spot, where the path comes to
// it (for now, the one object that does anything).
const ladder = new Ladder(scene, things.scene.getObjectByName("ladder")!, ground, player, reducedMotion);
let leaning: string | undefined; // the exit the ladder's up for
const items = setUpItems({
  world,
  scene,
  player,
  models: things.scene,
  ground,
  walkable,
  root,
  say,
  changed: inUse,
  stays: (id) => {
    if (id !== "ladder" || !ladder.shown) return undefined;
    return { model: ladder.handOver()!, fallsTo: ladder.footing! };
  },
  begin: handoff ?? undefined,
});
let instantly = true; // (loading, what's in use is as it was: no gate swinging open, no chopping)
function inUse() {
  const { room: here, itemLocations } = items.state;
  const using = effects(world, items.state);
  // (Only the ways the 3D world can open so far: walls to climb, gates, the dense trees.)
  const exits = EXIT_ORDER.flatMap((direction) => {
    const needs = world.rooms[here].exits[direction]?.obstacle?.needs;
    const shape = shapeOf.get(`${here} ${direction}`);
    return needs && using.includes(needs) && shape && (walls.has(shape) || gates.has(shape) || shape === dense)
      ? [`${here} ${direction}`]
      : [];
  });
  opened = new Set(exits.map((exit) => shapeOf.get(exit)!));
  solidify();
  for (const [shape, gate] of gates) {
    gate.wants = opened.has(shape) ? 1 : 0;
    if (instantly) gate.open = gate.wants;
  }
  if (dense) felling.fell(opened.has(dense), player.position, instantly);
  const wall = exits.find((exit) => walls.has(shapeOf.get(exit)!));
  if (wall !== leaning) {
    ladder.away();
    if (wall) ladder.lean(shapeOf.get(wall)!.box!, wall, PLACES.get(here)!, itemLocations.ladder === "carried");
    leaning = wall;
  } else if (wall && itemLocations.ladder === "carried") ladder.show();
}

// A game loaded: you're where you were in it (or, saved in another version,
// somewhere to stand in its place), and what was in use there still is.
if (handoff && !at) {
  const [x, z, yaw] = handoff.three?.at ?? [...(items.arrival(handoff.state.room) ?? [start.x, start.z]), 0];
  player.place(x, z, yaw);
  room = handoff.state.room;
}
inUse();
instantly = false;

// At /3d?debug (on the dev server too): the debug panel (the 0 key), and a
// handle for test scripts. Otherwise none of it is even loaded.
const debugMode = new URLSearchParams(location.search).has("debug");
if (debugMode) {
  Object.assign(window, { world: { player, scene, ground, walkable, renderer, places: PLACES, items } });
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
  <p class="keys">Mouse to look · WASD or arrows to walk · Shift to run · Space to jump · Ctrl or C to crouch · E to take or use · 1–5 to choose · G to drop · Esc to stop</p>
  <p class="keys touch">Left thumb to walk · right thumb to look</p>`;
overlay.hidden = Boolean(at);

// Saving and loading (the same saves as the other versions, which they can
// load too), and going over to them, carrying on the same game.
const panel = h("div", { class: "panel", hidden: true });
const choice = (label: string, onclick: () => void) => h("button", { type: "button", onclick }, label);
const menu = h(
  "nav",
  { class: "menu" },
  choice(T.save, showSave),
  choice(T.load, showLoad),
  choice(T.illustrated, () => leave3d("illustrated", items.state, saveName)),
  choice(T.classic, () => leave3d("classic", items.state, saveName))
);
// (Clicking or typing here isn't walking: nor taking, using or dropping.)
for (const part of [menu, panel]) {
  for (const type of ["click", "touchend", "keydown", "keyup"]) part.addEventListener(type, (e) => e.stopPropagation());
}
overlay.append(menu, panel);

function where(): ThreeSave {
  const round = (v: number) => Math.round(v * 100) / 100;
  const { x, z } = player.position;
  return { at: [round(x), round(z), round(player.yaw)], ...items.saved() };
}

function showSave() {
  const input = h("input", {
    name: "save-name",
    maxlength: "24",
    autocomplete: "off",
    placeholder: T.namePlaceholder,
    "aria-label": T.nameLabel,
  }) as HTMLInputElement;
  // After a save (or a load), the next in the series, ready to type over.
  if (saveName)
    input.value = nextSaveName(
      saveName,
      listSaves().map((slot) => slot.name)
    );
  const save = (event: Event) => {
    event.preventDefault();
    const name = input.value.trim();
    if (!name) return;
    const ok = saveGame(name, items.state, where());
    if (ok) saveName = name;
    panel.replaceChildren(h("p", {}, ok ? T.savedAs(name) : T.cantSave));
  };
  panel.replaceChildren(
    h("h2", {}, T.saveTitle),
    h("form", { onsubmit: save }, input, h("button", { type: "submit" }, T.save))
  );
  panel.hidden = false;
  input.focus();
  input.select();
}

function showLoad() {
  const saves = listSaves();
  panel.replaceChildren(
    h("h2", {}, T.oldPositions),
    saves.length
      ? h(
          "ul",
          { class: "saves" },
          ...saves.map((slot) =>
            h(
              "li",
              {},
              h("button", { type: "button", onclick: () => restart3d(slot.state, slot.name, slot.three) }, slot.name),
              h("span", { class: "when" }, `${savedDate(slot.savedAt)}, ${savedTime(slot.savedAt)}`)
            )
          )
        )
      : h("p", {}, T.noSaves),
    h("p", { class: "note" }, saves.length ? T.loadingEnds : "")
  );
  panel.hidden = false;
}

overlay.addEventListener("click", () => {
  void renderer.domElement.requestPointerLock?.();
  overlay.hidden = true;
  panel.hidden = true;
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
  trees.update(player.position, player.yaw, player.camera);
  felling.update(dt);
  // Along a way underground, you're still where you set off from (PLAN-V3.md),
  // until you come into a hall.
  // (Climbing over a wall, you're where you were until you're over.)
  if (!player.busy) {
    if (player.under?.hall) room = player.under.hall;
    else if (!player.inside) room = placeAt(player.position.x, player.position.z, room, player.halls);
  }
  for (const gate of gates.values()) {
    gate.open += Math.sign(gate.wants - gate.open) * Math.min(Math.abs(gate.wants - gate.open), dt * 0.8);
    // (Slow to start and to stop, like a heavy old gate.)
    const swing = SWING * (gate.open * gate.open * (3 - 2 * gate.open));
    for (const [leaf, way] of gate.leaves) leaf.rotation.y = way * swing;
  }
  ladder.update((exit) => {
    if (items.go(exit.split(" ")[1] as Direction)) room = items.state.room;
  });
  lightFor(player.depth, time, dt);
  items.update(room);
  here.textContent = name(room);
  scored.textContent = T.score(score(world, items.state));
  // The sun's shadows follow you, so they're sharp wherever you are.
  sunlight.target.position.copy(player.position);
  sunlight.position.copy(player.position).addScaledVector(SUN, 200);
  renderer.render(scene, player.camera);
});
