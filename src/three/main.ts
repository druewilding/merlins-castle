// Merlin's Castle in 3D: the whole land in grey boxes, built in Blender
// (art/blender/land.py), to walk from place to place. See PLAN-V3.md.
//
// For checking by eye: ?at=x,z,yaw (yaw in degrees, 0 looks north) starts
// you somewhere else, already walking.

import "./style.css";

import {
  ACESFilmicToneMapping,
  AdditiveBlending,
  Color,
  CylinderGeometry,
  DirectionalLight,
  DoubleSide,
  Fog,
  HemisphereLight,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  type Object3D,
  PCFShadowMap,
  PMREMGenerator,
  PointLight,
  Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  Timer,
  Vector3,
  WebGLRenderer,
} from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

import daJson from "../../data/da.json";
import worldJson from "../../data/world.json";
import { bestPossibleScore, effects, messages, newGame, score } from "../engine/engine";
import { localise, type WorldText } from "../engine/localise";
import { type Direction, EXIT_ORDER, type GameState, type World } from "../engine/types";
import { h } from "../shared/dom";
import { Sounds } from "../shared/sounds";
import {
  find3d,
  leave3d,
  listSaves,
  nextSaveName,
  recordScore,
  saveGame,
  takeHandoff,
  type ThreeSave,
} from "../shared/storage";
import { LANGUAGE, savedDate, savedTime, T } from "../shared/strings";
import { Fall } from "./fall";
import { Felling } from "./felling";
import { items as setUpItems, onPaths } from "./items";
import { Ladder } from "./ladder";
import { DEATHS, LOST, placeAt, PLACES } from "./layout";
import itemModels from "./models/items.glb?url";
import landHeights from "./models/land.bin?url";
import landModel from "./models/land.glb?url";
import land from "./models/land.json";
import snakeModel from "./models/snake.glb?url";
import { type Box, type Circle, type Ground, type Hall, nearest, Player, type Walkable, wayThrough } from "./player";
import { Shafts, speck, type Window } from "./shafts";
import { sky } from "./sky";
import { Snake } from "./snake";
import OWN_SOUNDS from "./sounds.json";
import { Swept } from "./swept";
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
const SKY = new Color("#cfe2ff");
const SKY_GROUND = new Color("#6d7a3c");
const skylight = new HemisphereLight(SKY, SKY_GROUND, 1.25);
// In the dark (the tower), what little of the sky's light there is is cold,
// and a dark haze hangs in the air (thinning as you climb to the window).
const COLD = new Color("#7d8fb8");
const COLD_GROUND = new Color("#1c1d22");
const GLOOM = new Color("#07080b");
scene.add(skylight);

// Underground, the daylight fades and a warm lamp glow takes over (one day,
// only if you've lit the lamp). It falls off gently: a light this close
// would otherwise blaze on any wall you walk up to. (Warm, but only a little:
// any more and the grey rock of the tunnels looks like brown earth.)
const lamp = new PointLight("#ffdcb4", 0, 14, 0.6);
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
// The sound effects, as in the illustrated version (from public/fx), and
// the 3D version's own, its footsteps and its scenes' sounds (src/three/fx:
// only it downloads them). Each footstep a little higher or lower than the
// last, so no two are quite the same.
const sounds = new Sounds();
const fx = import.meta.glob<string>("./fx/*.mp3", { eager: true, query: "?url", import: "default" });
const ownSounds = new Sounds(OWN_SOUNDS, (file) => fx[`./fx/${file}`]);
player.onStep = (kind, loudness) => ownSounds.play(kind, { volume: loudness, rate: 0.92 + Math.random() * 0.16 });
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
const [model, file, things, snaky] = await Promise.all([
  loader.loadAsync(landModel),
  fetch(landHeights).then(async (response) => response.arrayBuffer()),
  loader.loadAsync(itemModels),
  loader.loadAsync(snakeModel),
]);
const heights = new Float32Array(file, 0, land.ground.nx * land.ground.ny);
// The tower's inside, its own material: dark seen from outside, as it is
// once you're in (in there, the sky's light is dim: lightFor).
const towerInside = model.scene.getObjectByName("tower-inside");
const insideLook = towerInside instanceof Mesh ? (towerInside.material = towerInside.material.clone()) : undefined;
// The tower's cobwebs: faint, and see-through (not lit: pale threads, even in the dark).
const cobwebs = model.scene.getObjectByName("cobwebs");
if (cobwebs instanceof Mesh) {
  cobwebs.material = new MeshBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.3,
    side: DoubleSide,
    depthWrite: false,
  });
  cobwebs.castShadow = false;
  cobwebs.receiveShadow = false;
}
// The emerald, glassy: a little room's lights caught in its facets (its own,
// not the scene's), and a glow from within, so it shines even in the tower.
const emerald = things.scene.getObjectByName("emerald");
if (emerald instanceof Mesh) {
  const pmrem = new PMREMGenerator(renderer);
  emerald.material = new MeshPhysicalMaterial({
    vertexColors: true,
    flatShading: true,
    roughness: 0.12,
    metalness: 0.9, // (its reflections green, as in its picture: white only in a thin coat over them)
    clearcoat: 0.2,
    clearcoatRoughness: 0.05,
    envMap: pmrem.fromScene(new RoomEnvironment(), 0.02).texture,
    envMapIntensity: 0.55,
    emissive: new Color("#0f7a38"),
    emissiveIntensity: 1.0,
  });
  pmrem.dispose();
}
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
// And exactly as it's drawn: flat triangles, each square split from its first
// corner to its third, as Blender splits it (drawn_height in land.py). On a
// sharp rise that's quite different: for laying something right on it.
const drawn: Ground = (x, z) => {
  const i = (x - x0) / step;
  const j = (-z - y0) / step;
  if (i < 0 || j < 0 || i >= nx - 1 || j >= ny - 1) return undefined;
  const i0 = Math.floor(i);
  const j0 = Math.floor(j);
  const fi = i - i0;
  const fj = j - j0;
  const h = (a: number, b: number) => heights[(j0 + b) * nx + i0 + a];
  return fi > fj
    ? h(0, 0) + fi * (h(1, 0) - h(0, 0)) + fj * (h(1, 1) - h(1, 0))
    : h(0, 0) + fj * (h(0, 1) - h(0, 0)) + fi * (h(1, 1) - h(0, 1));
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
// (A lit hall has a light of its own; a dark one, only what comes in: lights
// at its windows, and its windows' shafts of light.)
type Fixture = { at: number[]; colour: string; glow: number; reach: number };
const halls = land.halls as Record<
  string,
  Hall & { tall: number; light?: string; glow?: number; lights?: Fixture[]; dark?: boolean; windows?: Window[] }
>;
player.halls = new Map(Object.entries(halls));

// Solid things, and the obstacles: closed, until an object in use opens one.
const circles: Circle[] = land.circles.map(([x, z, r]) => ({ x, z, r }));
const boxes: Box[] = land.boxes.map(([x, z, halfX, halfZ]) => ({ x, z, halfX, halfZ }));
type Obstacle = { box?: number[]; circle?: number[]; under?: boolean; reach?: number; allRound?: boolean };
const obstacles = land.obstacles as Record<string, Obstacle>;
const underCircles: Circle[] = land.under.circles.map(([x, z, r, top, bottom]) => ({ x, z, r, top, bottom }));
const underBoxes: Box[] = land.under.boxes.map(([x, z, halfX, halfZ, top]) => ({ x, z, halfX, halfZ, top }));
// You bump into an obstacle in your way this far before it (all round it), so
// you can see what it is (and know there's something to do here): unless it
// says how far itself (land.json), as the stone in the tower does.
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
// The chest in the tower, its lid opening as you come up to it (and the
// emerald in it, items.ts), and shutting as you go.
const lid = model.scene.getObjectByName("chest-lid");
const [chestX, chestZ] = land.chest;
let lidOpen = 0;
const LID = 1.9; // radians, open (back against the wall)
const CRACK = 0.07; // and shut, it rests a crack open: the emerald's glow shows through
// The emerald's own glow, wherever it lies: a little green light, breathing
// (in the chest, mostly kept in by its lid, but through the crack), and a
// soft halo round it, which the chest's sides and lid hide.
const GEM = new Color("#46ff8c");
const gemLight = new PointLight(GEM, 0, 2.6, 1.4);
const halo = new Sprite(
  new SpriteMaterial({ map: speck(), color: GEM, blending: AdditiveBlending, transparent: true, depthWrite: false })
);
halo.scale.setScalar(0.45);
scene.add(gemLight, halo);
const gemAt = new Vector3();
let gemGlow = 0; // 1 lying there, 0 carried
// The stone, rolling from beside the tower's door across it, once you're in,
// and back with the ring: turning as it goes.
const stone = model.scene.getObjectByName("stone");
const { r: STONE_R, aside, door } = land.stone;
let rolled: number | undefined; // 0 beside the door, 1 across it
const ROLL = 0.45; // of the way, a second
// The dense trees across the mountain path, which the axe fells (felling.ts).
const dense = shapeOf.get("mountain-path north");
// The snake coiled at the top of the mossy steps, which takes the apple (snake.ts).
const guarded = shapeOf.get("mossy-steps north");
const snake = new Snake(
  scene,
  snaky.scene,
  things.scene.getObjectByName("apple")!,
  onPaths(ground, land.paths, land.steps),
  (guarded!.circle ?? guarded!.box)!,
  reducedMotion
);
// The enormous stone that shuts you in the tower, which the ring rolls away.
const shut = shapeOf.get("tower south");
let allOpen = false; // (the debug panel's "open every obstacle")
let opened = new Set<Shape>(); // by an object in use
// A way that kills you even with the object (the balcony) has no far side
// you could have come from: it stops you from every side.
const deadly = (names: string[]) => names.every((name) => exitOf(name)?.fatal);
function solidify() {
  for (const under of [false, true]) {
    const here = [...shapes.values()].filter((shape) => Boolean(shape.under) === under);
    const closed = allOpen ? [] : here.filter((shape) => !opened.has(shape));
    const plain = allOpen ? [] : here.filter((shape) => walls.has(shape));
    // The obstacles first, so you bump into them before any wall they stand in.
    player.solid(
      [
        ...closed.flatMap(({ circle, names, reach = AHEAD, allRound }) =>
          circle
            ? [{ x: circle[0], z: circle[1], r: circle[2], names, ahead: reach, allRound: allRound || deadly(names) }]
            : []
        ),
        ...(under ? underCircles : circles),
      ],
      [
        ...closed.flatMap(({ box, names, reach = AHEAD, allRound }) =>
          box
            ? [
                {
                  x: box[0],
                  z: box[1],
                  halfX: box[2],
                  halfZ: box[3],
                  names,
                  ahead: reach,
                  allRound: allRound || deadly(names),
                },
              ]
            : []
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
find3d(); // (from now on, the other versions show the way back here)
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
// (A teletext colour code shows as a space.)
const plain = (words: string) =>
  words
    .replace(/\{\w+\}/g, " ")
    .replace(/\s+/g, " ")
    .trim();
function say(words: string) {
  said.textContent = plain(words);
  said.classList.add("shown");
  clearTimeout(quiet);
  quiet = window.setTimeout(() => said.classList.remove("shown"), 3500);
}
// Going through a way that says so ("You have climbed over."): said as you
// commit to it (past the middle of what was in the way: at the top of the
// wall, climbing over), not once you're through. (Not one that kills you: that's for when
// dying is done.)
let told: string | undefined; // the exit whose words were said, on the way through it
function tell(exit: string) {
  const [id, direction] = exit.split(" ");
  const way = world.rooms[id]?.exits[direction as Direction];
  if (way?.message && !way.fatal) say(way.message);
  told = exit;
}
player.onBump = (exit) => {
  if (dying(exit)) return;
  const [id, direction] = exit.split(" ");
  const way = world.rooms[id]?.exits[direction as Direction];
  // (In use, but the 3D world can't open it yet, with no model for it: the plank. Nothing to say.)
  const needs = way?.obstacle?.needs;
  if (needs && effects(world, items.state).includes(needs)) return;
  say(way?.obstacle?.blocked ?? way?.message ?? messages(world).cantGo);
  sounds.play("blocked");
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
  paths: land.paths,
  steps: land.steps,
  root,
  say,
  sound: (name) => sounds.play(name),
  changed: inUse,
  stays: (id) => {
    if (id !== "ladder" || !ladder.shown) return undefined;
    return { model: ladder.handOver()!, fallsTo: ladder.footing! };
  },
  begin: handoff ?? undefined,
  starts: { emerald: { room: "tower", at: land.chest as [number, number, number] } },
  reducedMotion,
});
let parting = false; // (the dense trees, for you coming down from the mountain)
let instantly = true; // (loading, what's in use is as it was: no gate swinging open, no chopping)
function inUse() {
  const { room: here, itemLocations } = items.state;
  const using = effects(world, items.state);
  // (Only the ways the 3D world can open so far: walls to climb, gates, the dense trees, the snake.)
  const exits = EXIT_ORDER.flatMap((direction) => {
    const needs = world.rooms[here].exits[direction]?.obstacle?.needs;
    const shape = shapeOf.get(`${here} ${direction}`);
    return needs &&
      using.includes(needs) &&
      shape &&
      (walls.has(shape) || gates.has(shape) || shape === dense || shape === guarded || shape === shut)
      ? [`${here} ${direction}`]
      : [];
  });
  opened = new Set(exits.map((exit) => shapeOf.get(exit)!));
  solidify();
  for (const [shape, gate] of gates) {
    const wants = opened.has(shape) ? 1 : 0;
    // (Creaking on its rusty hinges, as it swings open.)
    if (wants > gate.wants && !instantly) ownSounds.play("creak");
    gate.wants = wants;
    if (instantly) gate.open = gate.wants;
  }
  if (dense) felling.fell(opened.has(dense), instantly);
  // The apple thrown to the snake, from your hand (or, loading, it's gone,
  // or there).
  if (guarded && opened.has(guarded)) {
    if (instantly) snake.away();
    else snake.feed(player.camera.localToWorld(new Vector3(0.15, -0.25, -0.4)));
  } else if (instantly && here !== "tower") snake.back();
  const wall = exits.find((exit) => walls.has(shapeOf.get(exit)!));
  // (Or propped under the balcony, at the mossy steps: "propped up ready",
  // but it slips, so it opens nothing.)
  const balcony = here === "mossy-steps" && using.includes("ladder") ? "mossy-steps east" : undefined;
  const up = wall ?? balcony;
  if (up !== leaning) {
    ladder.away();
    const carried = itemLocations.ladder === "carried";
    if (wall) ladder.lean(shapeOf.get(wall)!.box!, wall, PLACES.get(here)!, carried);
    else if (balcony) ladder.prop(land.balcony.top, land.balcony.out, balcony, carried);
    leaning = up;
  } else if (up && itemLocations.ladder === "carried") ladder.show();
}

// A game loaded: you're where you were in it (or, saved in another version,
// somewhere to stand in its place), and what was in use there still is.
function arrive(game: { state: GameState; three?: ThreeSave }) {
  const [x, z, yaw, floor] = game.three?.at ?? [...(items.arrival(game.state.room) ?? [start.x, start.z]), 0];
  player.place(x, z, yaw, floor);
  room = game.state.room;
}
if (handoff && !at) arrive(handoff);

// Dying: walking into a way that kills you, its scene plays out (climbing
// the ladder propped under the balcony, fall.ts; wading into the deep river,
// swept.ts); then a curtain falls, with the original's words, and after it
// your score, as in the illustrated version.
const BALCONY = "mossy-steps east";
const RIVER = "deep-river south";
let playing: { update(dt: number): boolean; dispose?(): void } | undefined; // the scene
const ending = h("div", { class: "ending", hidden: true });
// (Clicking or typing here isn't walking: nor taking, using or dropping.)
for (const type of ["click", "touchend", "keydown", "keyup"]) ending.addEventListener(type, (e) => e.stopPropagation());
root.append(ending);
// Under the water (swept away in the river): murky.
const murky = h("div", { class: "murky" });
root.append(murky);

/** Each way that kills you that has a scene: it, ending with done(), or nothing (nothing to see there now). */
const scenes: Record<string, (done: () => void) => { update(dt: number): boolean; dispose?(): void } | undefined> = {
  [BALCONY]: (done) => {
    const propped = ladder.propped(BALCONY);
    // (Dropped there, it's still up, as an object lying in the place.)
    const model = propped?.model ?? items.lyingAt("ladder");
    if (!propped || !model || !effects(world, items.state).includes("ladder")) return undefined;
    return new Fall(
      { ...propped, model },
      player.camera,
      drawn,
      player.halls.get("tower")!,
      reducedMotion,
      () => ownSounds.play("thud"),
      done
    );
  },
  // (Not with the plank across it: the way's open then.)
  [RIVER]: (done) =>
    effects(world, items.state).includes("plank")
      ? undefined
      : new Swept(scene, player.camera, drawn, land.river, reducedMotion, done),
};

/** Walking into a way that kills you: its scene (and true), or nothing to see (false). */
function dying(exit: string) {
  const [id, direction] = exit.split(" ") as [string, Direction];
  const way = world.rooms[id]?.exits[direction];
  // (The words: the way's own, going through it, or its obstacle's, in the way.)
  const words = (way?.fatal ? way.message : way?.obstacle?.blocked) ?? "";
  const scene = scenes[exit]?.(() => curtain(words));
  if (!scene) return false;
  items.go(direction); // (the engine: you're dead)
  player.held = true;
  document.body.classList.add("scene");
  playing = scene;
  return true;
}

// The curtain, red: the words, and Continue.
function curtain(words: string) {
  document.exitPointerLock?.();
  const go = h("button", { type: "button", class: "pill", onclick: over }, T.continue);
  ending.replaceChildren(h("div", { class: "curtain" }, h("p", { class: "last-words" }, plain(words)), go));
  ending.hidden = false;
  go.focus({ preventScroll: true });
}

// Then your score: play again, load a game, or back to the start.
function over() {
  const yours = score(world, items.state);
  const best = recordScore(yours);
  const again = h("button", { type: "button", class: "pill", onclick: () => newStart(true) }, T.playAgain);
  ending.replaceChildren(
    h(
      "div",
      { class: "over" },
      h(
        "div",
        { class: "card" },
        h("h2", {}, T.adventureOver),
        h("p", { class: "yours" }, T.yourScore(yours)),
        h("p", {}, T.bestSoFar(best)),
        h("p", {}, T.bestPossible(bestPossibleScore(world))),
        h(
          "div",
          { class: "buttons" },
          again,
          listSaves().length > 0 &&
            h(
              "button",
              {
                type: "button",
                class: "pill quiet",
                onclick: () => {
                  newStart(false);
                  showLoad();
                },
              },
              T.loadAGame
            )
        ),
        h("nav", { class: "links" }, h("button", { type: "button", onclick: () => newStart(false) }, T.mainMenu))
      )
    )
  );
  again.focus({ preventScroll: true });
}

/** A new game: straight into it, or to the start screen (to play, or load). */
function newStart(playing: boolean) {
  saveName = "";
  restart({ state: newGame(world) });
  if (playing) return resume();
  overlay.querySelector(".play")!.textContent = T.play;
  panel.hidden = true;
  overlay.hidden = false;
}
inUse();
instantly = false;
let lastRoom = room; // (where you were last frame)
const was = player.position.clone(); // (and just where)

// At /3d?debug (on the dev server too): the debug panel (the 0 key), and a
// handle for test scripts. Otherwise none of it is even loaded.
const debugMode = new URLSearchParams(location.search).has("debug");
if (debugMode) {
  Object.assign(window, {
    world: { player, scene, ground, walkable, renderer, places: PLACES, items, snake, restart, drawn },
  });
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
  <button type="button" class="play">${handoff ? T.continue : T.play}</button>
  <p class="keys">Mouse to look · WASD to walk · Shift to run · Space to jump · C to crouch · E to take or use · 1–5 to choose · G to drop · Esc to stop</p>
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
  // (Underground, or indoors, the floor you're on too: or you'd come back up
  // on the land over it.)
  const floor = player.under?.floor;
  const at: ThreeSave["at"] = [round(x), round(z), round(player.yaw)];
  if (floor !== undefined) at.push(round(floor));
  return { at, ...items.saved() };
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
    if (!saveGame(name, items.state, where())) {
      panel.replaceChildren(h("p", {}, T.cantSave));
      return;
    }
    // Saved: straight back into the game, saying so there.
    saveName = name;
    resume();
    say(T.savedAs(name));
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
              h("button", { type: "button", onclick: () => load(slot) }, slot.name),
              h("span", { class: "when" }, `${savedDate(slot.savedAt)}, ${savedTime(slot.savedAt)}`)
            )
          )
        )
      : h("p", {}, T.noSaves),
    h("p", { class: "note" }, saves.length ? T.loadingEnds : "")
  );
  panel.hidden = false;
}

// Loading: the game as it was, right here (no starting the page again, so
// the click on its name hands the mouse straight back to the game).
function load(slot: { name: string; state: GameState; three?: ThreeSave }) {
  saveName = slot.name;
  restart(slot);
  resume();
  say(T.loadedAs(slot.name));
}

// A game (loaded, or new) right here: no starting the page again.
function restart(game: { state: GameState; three?: ThreeSave }) {
  items.restart(game);
  // (Out of any scene, and the ladder put up afresh if it's up: it may have fallen.)
  playing?.dispose?.();
  playing = undefined;
  player.held = false;
  document.body.classList.remove("scene");
  ending.hidden = true;
  ending.replaceChildren();
  ladder.away();
  leaning = undefined;
  arrive(game);
  instantly = true; // (what's in use is as it was: no gate swinging open, no chopping)
  inUse();
  instantly = false;
  parting = false;
  told = undefined;
  lastRoom = room;
  was.copy(player.position);
}

function resume() {
  // (A click: the browser lets sound start now.)
  sounds.load();
  ownSounds.load();
  // Once you've walked (or loaded), the way back in carries on the game.
  overlay.querySelector(".play")!.textContent = T.continue;
  // (If the browser won't take the mouse after all, the menu's back, to click.)
  Promise.resolve(renderer.domElement.requestPointerLock?.()).catch(() => (overlay.hidden = false));
  overlay.hidden = true;
  panel.hidden = true;
}
overlay.addEventListener("click", resume);
overlay.addEventListener("touchend", () => {
  sounds.load();
  ownSounds.load();
  overlay.querySelector(".play")!.textContent = T.continue;
  overlay.hidden = true;
});
// With the debug panel open, clicking the world looks around again.
renderer.domElement.addEventListener("click", () => {
  if (document.body.classList.contains("debugging")) void renderer.domElement.requestPointerLock?.();
});
document.addEventListener("pointerlockchange", () => {
  const debugging = document.body.classList.contains("debugging");
  // (Not in a scene, or once you've died: that has its own screen.)
  if (!player.locked && !debugging && !player.held && !matchMedia("(pointer: coarse)").matches) overlay.hidden = false;
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
let gloom = 0; // in a dark hall: 1
let murk = 0; // and down in it, where its haze is: 1
let dark = 0; // how dark it is round you (in a dark hall, or deep underground): 1
// The lights in the halls: a lit hall's own, in its middle, up towards its
// roof, flickering (torches, fire); a dark one's, coming in at its windows
// and cracks, steady (daylight).
const fixtures = Object.values(halls).flatMap((hall) =>
  hall.lights
    ? hall.lights.map(({ at: [x, y, z], colour, glow, reach }) => ({ x, y, z, colour, glow, reach, flickers: false }))
    : hall.light
      ? [
          {
            x: hall.x,
            y: hall.floor + hall.tall * 0.6,
            z: hall.z,
            colour: hall.light,
            glow: hall.glow ?? 0,
            reach: hall.r * 1.8,
            flickers: true,
          },
        ]
      : []
);
const darkHall = Object.values(halls).find((hall) => hall.dark);
const shafts = darkHall?.windows && new Shafts(scene, darkHall, darkHall.windows, reducedMotion);
function lightFor(depth: number, time: number, dt: number) {
  indoors += ((player.under?.indoor ? 1 : 0) - indoors) * Math.min(1, dt * 4);
  const hall = player.under?.hall ? halls[player.under.hall] : undefined;
  gloom += ((hall?.dark ? 1 : 0) - gloom) * Math.min(1, dt * 2);
  const p = player.position;
  // (Climbing towards the top window, out of the haze: the view from it clear.)
  const climbed = hall?.dark ? Math.min(1, Math.max(0, (p.y - hall.floor) / (hall.tall * 0.6))) : 0;
  murk += ((hall?.dark ? 1 - climbed * climbed * (3 - 2 * climbed) : 0) - murk) * Math.min(1, dt * 2);
  const under = Math.min(1, Math.max(0, (depth - 0.5) / 3));
  dark = Math.max(gloom, under);
  sunlight.intensity = 2.8 * (1 - under);
  skylight.intensity = 1.25 * (1 - Math.max(under * 0.92, indoors * 0.55, gloom * 0.8));
  skylight.color.copy(SKY).lerp(COLD, gloom);
  skylight.groundColor.copy(SKY_GROUND).lerp(COLD_GROUND, gloom);
  const flicker = reducedMotion ? 1 : 0.92 + 0.05 * Math.sin(time / 90) + 0.03 * Math.sin(time / 37);
  lamp.intensity = 3.5 * Math.max(under, indoors * 0.4) * flicker * (1 - gloom);
  lamp.position.set(player.position.x, player.position.y + 1.4, player.position.z);

  // The halls' lights nearest you.
  const away = (light: (typeof fixtures)[number]) =>
    Math.hypot(light.x - p.x, light.y - p.y, light.z - p.z) - light.reach / 1.8;
  const nearest = fixtures.filter((light) => away(light) < 40).sort((a, b) => away(a) - away(b));
  roomLights.forEach((light, k) => {
    const fixture = nearest[k];
    light.intensity = fixture ? fixture.glow * 4 * (fixture.flickers ? flicker : 1) : 0;
    if (!fixture) return;
    light.color.set(fixture.colour);
    light.distance = fixture.reach;
    light.position.set(fixture.x, fixture.y, fixture.z);
  });

  caveLit += ((hall?.light ? 1 : 0) - caveLit) * Math.min(1, dt * 3);
  fog.color.copy(HAZE).lerp(DARK, under).lerp(GLOOM, murk);
  fog.near = (40 - 38 * under) * (1 - murk) + 1.5 * murk;
  fog.far = (320 - 290 * under + 40 * caveLit) * (1 - murk) + 22 * murk;
  shafts?.update(dt, gloom, player.camera.position);
  insideLook?.color.setScalar(0.25 + 0.75 * gloom);
}

const timer = new Timer();
renderer.setAnimationLoop((time) => {
  timer.update(time);
  const dt = Math.min(timer.getDelta(), 0.1);
  player.update(dt, reducedMotion);
  playing?.update(dt);
  murky.classList.toggle("under", Boolean(playing) && player.camera.position.y < land.river.water);
  trees.update(player.position, player.yaw, player.camera);
  // Coming down from the mountain to the dense trees, they part for you
  // (going up, they don't), until you're clear of them.
  if (dense?.box) {
    const [x, z, halfX, halfZ] = dense.box;
    const { x: px, z: pz } = player.position;
    const near = Math.abs(px - x) < halfX + 2 && pz > z - halfZ - 18 && pz < z + halfZ + 15;
    if (!near) parting = false;
    else if (room === "mountain") parting = true;
  }
  felling.update(dt, player.position, parting);
  // (The snake's back by the door once the apple's no longer in use there,
  // but not while you're in the tower: you'd come out through it.)
  snake.update(dt, player.camera.position, player.camera, room !== "tower" && !(guarded && opened.has(guarded)));
  // Along a way underground, you're still where you set off from (PLAN-V3.md),
  // until you come into a hall.
  // (Climbing over a wall, you're where you were until you're over.)
  if (!player.busy) {
    if (player.under?.hall) room = player.under.hall;
    else if (!player.inside) room = placeAt(player.position.x, player.position.z, room, player.halls);
  }
  if (stone) {
    const wants = room === "tower" && shut && !opened.has(shut) && !allOpen ? 1 : 0;
    rolled =
      rolled === undefined ? wants : rolled + Math.sign(wants - rolled) * Math.min(Math.abs(wants - rolled), dt * ROLL);
    const t = rolled * rolled * (3 - 2 * rolled);
    stone.position.set(
      ...(([0, 2, 1] as const).map((k) => aside[k] + (door[k] - aside[k]) * t) as [number, number, number])
    );
    stone.rotation.z = (-(door[0] - aside[0]) * t) / STONE_R;
  }
  // (Fading as you pick it up, and in as you put it down: where it was, meanwhile.)
  const gem = items.lyingAt("emerald");
  gemGlow += Math.sign(Number(Boolean(gem)) - gemGlow) * Math.min(Math.abs(Number(Boolean(gem)) - gemGlow), dt * 3);
  if (gem) gem.getWorldPosition(gemAt).y += 0.1;
  const breath = reducedMotion ? 1 : 0.85 + 0.15 * Math.sin(time / 700);
  const kept = Math.hypot(gemAt.x - chestX, gemAt.z - chestZ) < 0.8 ? 0.18 + 0.82 * lidOpen : 1;
  // (Only a glimmer in daylight: it shows in the dark.)
  gemLight.position.copy(gemAt);
  gemLight.intensity = gemGlow * breath * kept * (0.15 + 1.0 * dark);
  // (The halo a little towards you, so the ground doesn't cut it off.)
  halo.position.copy(gemAt).addScaledVector(player.camera.position.clone().sub(gemAt).normalize(), 0.15);
  halo.visible = gemGlow > 0.01;
  halo.material.opacity = gemGlow * breath * (0.05 + 0.3 * dark);
  if (lid) {
    const near =
      player.under?.hall === "tower" && Math.hypot(player.position.x - chestX, player.position.z - chestZ) < 2.5;
    lidOpen += Math.sign(Number(near) - lidOpen) * Math.min(Math.abs(Number(near) - lidOpen), dt * 1.5);
    lid.rotation.x = -(CRACK + (LID - CRACK) * (lidOpen * lidOpen * (3 - 2 * lidOpen)));
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
  // Through what was in the way (over the wall, through the felled trees or
  // an open gate): its words as you pass its middle (the top of the wall).
  for (const shape of opened) {
    const [x, z, halfX, halfZ] = shape.box ?? shape.circle!;
    const p = player.position;
    const near = shape.box
      ? Math.abs(p.x - x) < halfX + 2 && Math.abs(p.z - z) < halfZ + 2
      : Math.hypot(p.x - x, p.z - z) < halfX + 2;
    for (const exit of shape.names) {
      if (!exit.startsWith(`${room} `) || !near || exit === told) continue;
      if (wayThrough([exit], x, z, was.x, was.z) && !wayThrough([exit], x, z, p.x, p.z)) tell(exit);
    }
  }
  was.copy(player.position);
  // Into a new place: the words for the way you came, if they weren't said
  // as you went.
  if (room !== lastRoom) {
    const exit = EXIT_ORDER.map((direction) => `${lastRoom} ${direction}`).find(
      (exit) => world.rooms[lastRoom].exits[exit.split(" ")[1] as Direction]?.to === room
    );
    if (exit && exit !== told) tell(exit);
    told = undefined;
    lastRoom = room;
  }
  lightFor(player.depth, time, dt);
  items.update(room);
  here.textContent = name(room);
  scored.textContent = T.score(score(world, items.state));
  // The sun's shadows follow you, so they're sharp wherever you are.
  sunlight.target.position.copy(player.position);
  sunlight.position.copy(player.position).addScaledVector(SUN, 200);
  renderer.render(scene, player.camera);
});
