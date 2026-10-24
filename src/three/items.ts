// The objects: lying where the game puts them, taken by looking at one and
// pressing E, carried in five slots (1–5 picks the one in your hand), used
// with E when you're not looking at one (or a click) and dropped with G. The engine stays the judge (PLAN-V3.md):
// these are its `take`, `use` and `drop`, and what it says decides what
// happens. An object in use (opening a way out of the place) has a tick.
// Looking at a clue's note instead, E reads it (notes.ts).
//
// Only objects with a model (art/blender/items.py) are in the world so far.

import { Box3, Matrix4, type Mesh, type Object3D, Ray, type Scene, Vector3 } from "three";

import { act, effects, newGame } from "../engine/engine";
import { type Direction, EXIT_ORDER, type GameState, type ItemId, type RoomId, type World } from "../engine/types";
import { artUrl } from "../illustrated/art";
import type { Shared } from "../shared/sounds";
import type { ThreeSave } from "../shared/storage";
import { T } from "../shared/strings";
import { Glow } from "./glow";
import { placeAt, PLACES } from "./layout";
import { type Ground, type Hall, nearest, type Player, type Walkable } from "./player";

const SLOTS = 5;
// How far you can reach to take something (from your eyes).
const REACH = 10;
// A thin object is easier to point at with a little room round it.
const AIM_SLACK = 0.25;
// The ground you walk on is a little smoother than the ground you see; an
// object lies this far above it, so it never sinks in.
const LIFT = 0.04;
// Where objects start: the ground's checked every half metre, and in a hall
// they keep this far from its wall.
const FILL = 0.5;
const WALL = 1;
// Stuck: nothing taken and no obstacle overcome for this long (seconds).
// Then each object you've never held hops, and glows, to catch your eye, as
// you come to see it (this near, on the screen, nothing in the way): twice
// over, a hop and a little one. Not again till you've looked away and back.
const STUCK = 60;
const NOTICE = 15;
const HOPS = [
  [0, 0.28, 0.25], // [from (seconds), how long, how high (metres)]
  [0.28, 0.2, 0.1],
  [0.75, 0.28, 0.25],
  [1.03, 0.2, 0.1],
];
const GLOWS = 1.6; // and its glow, for this long
const AGAIN = 3; // and at least this long before it hops again

/** The ground an object covers: its middle, which way it lies, half its length and half its width. */
interface Footprint {
  x: number;
  z: number;
  yaw: number;
  half: number;
  wide: number;
}

interface Lying {
  room: RoomId;
  model: Object3D;
  box: Box3; // its own size, turned and tilted with it (to point at)
  footprint?: Footprint;
  floor?: number; // (on a floor, underground or indoors, not the ground)
  // Dropped where it was in use (the ladder against the wall): once you've
  // left, it's lying on the ground here.
  fallsTo?: Footing;
}

/** A path (land.json): its line [x, z], how far either side of it it goes, and how far up off the ground. */
export interface Path {
  points: number[][];
  half: number;
  lift: number;
}

/** A step on the land (land.json): [x, z, half x, half z, top]. */
export type Step = number[];

/** A floor over the ground (land.json: the maze's paving): [x, z, half x, half z, how far up]. */
export type Floor = number[];

/** The ground, or the top of a path lying on it (or of a step, or a floor). */
export function onPaths(ground: Ground, paths: Path[], steps: Step[] = [], floors: Floor[] = []): Ground {
  return (x, z) => {
    const g = ground(x, z);
    if (g === undefined) return undefined;
    let top = -Infinity;
    for (const [sx, sz, halfX, halfZ, high] of steps) {
      if (Math.abs(x - sx) <= halfX && Math.abs(z - sz) <= halfZ) top = Math.max(top, high);
    }
    let lift = 0;
    for (const [fx, fz, halfX, halfZ, up] of floors) {
      if (Math.abs(x - fx) <= halfX && Math.abs(z - fz) <= halfZ) lift = Math.max(lift, up);
    }
    for (const path of paths) {
      for (let k = 0; k < path.points.length - 1; k++) {
        const [ax, az] = path.points[k];
        const [bx, bz] = path.points[k + 1];
        const t = Math.max(
          0,
          Math.min(1, ((x - ax) * (bx - ax) + (z - az) * (bz - az)) / ((bx - ax) ** 2 + (bz - az) ** 2 || 1))
        );
        if (Math.hypot(x - ax - t * (bx - ax), z - az - t * (bz - az)) <= path.half) lift = Math.max(lift, path.lift);
      }
    }
    return Math.max(g + lift, top);
  };
}

/** Where an object stands, and which way it lies when it falls (and on what floor, underground). */
export interface Footing {
  x: number;
  z: number;
  yaw: number;
  floor?: number;
}

// Where a dropped object can go, nearest first: aside (to your right, or
// left) and on, in metres, from just in front of you.
const NUDGES = [[0, 0]];
for (let r = 0.3; r <= 3; r += 0.3) NUDGES.push([r, 0], [-r, 0], [0, r], [r, r], [-r, r]);
// How far apart objects lie, at least.
const APART = 0.1;
// How near you an object's middle lands, at least, dropped at your feet.
const NEAREST = 0.7;

/** Whether two objects would lie on each other: any point of one under the other. */
function overlap(a: Footprint, b: Footprint) {
  return covered(a).some(([x, z]) => under(b, x, z)) || covered(b).some(([x, z]) => under(a, x, z));
}

function under(f: Footprint, x: number, z: number) {
  const dx = x - f.x;
  const dz = z - f.z;
  const along = dx * Math.sin(f.yaw) + dz * Math.cos(f.yaw);
  const across = dx * Math.cos(f.yaw) - dz * Math.sin(f.yaw);
  return Math.abs(along) <= f.half + APART && Math.abs(across) <= f.wide + APART;
}

/** Points all over an object's footprint, every 20 cm or so. */
function covered(f: Footprint) {
  const points: [number, number][] = [];
  const n = Math.max(1, Math.ceil((f.half * 2) / 0.2));
  const m = Math.max(1, Math.ceil((f.wide * 2) / 0.2));
  for (let i = 0; i <= n; i++) {
    for (let j = 0; j <= m; j++) {
      const along = -f.half + (i / n) * f.half * 2;
      const across = -f.wide + (j / m) * f.wide * 2;
      points.push([
        f.x + Math.sin(f.yaw) * along + Math.cos(f.yaw) * across,
        f.z + Math.cos(f.yaw) * along - Math.sin(f.yaw) * across,
      ]);
    }
  }
  return points;
}

export interface Items {
  /** Each frame: where you are, and what you're looking at. */
  update(room: RoomId): void;
  /** Going through an exit (over the wall): whether the engine let you. */
  go(direction: Direction): boolean;
  readonly state: GameState;
  /** What a save needs besides the game's state: what you carry, and where everything lies. */
  saved(): Omit<ThreeSave, "at">;
  /** Somewhere to stand in a place (arriving in it from a save that doesn't say where). */
  arrival(room: RoomId): [number, number] | undefined;
  /** An object lying in the world (not carried): its model, where it lies. */
  lyingAt(id: ItemId): Object3D | undefined;
  /** Every object lying in the world: their models. */
  lying(): Object3D[];
  /** A game loaded: what you carry, and where everything lies, as it was in it. */
  restart(game: { state: GameState; three?: ThreeSave }): void;
}

export function items(options: {
  world: World;
  scene: Scene;
  player: Player;
  models: Object3D;
  ground: Ground;
  walkable: Walkable;
  /** The paths, a little above the ground (land.json): what lies on one lies on top of it. And the steps. */
  paths: Path[];
  steps: Step[];
  /** And the floors over the ground (the maze's paving). */
  floors?: Floor[];
  root: HTMLElement;
  /** Words at the bottom of the screen ("Nothing happens."). */
  say: (words: string) => void;
  /** A sound effect, as in the illustrated version (taking, dropping, using). */
  sound: (name: Shared) => void;
  /** What's in use has changed: an object used, or the place left. */
  changed: () => void;
  /** Dropping an object where it's in use, it stays as it is (the ladder against the wall): its model, if so (and its own box, if it's not as it lies). */
  stays: (id: ItemId) => { model: Object3D; fallsTo: Footing; box?: Box3 } | undefined;
  /** A game loaded (or carried on from another version), and, saved in 3D, where things lie. */
  begin?: { state: GameState; three?: ThreeSave };
  /** Where an object always starts in a place, rather than anywhere in it (the emerald, in the tower's chest): [x, z, floor]. */
  starts?: Partial<Record<ItemId, { room: RoomId; at: [number, number, number] }>>;
  /** The clues' notes (notes.ts): looked at, E reads one (its number). */
  notes?: Mesh[];
  read?: (k: number) => void;
  /** Whether what an object does here is said only as you go through (the rope over the deep hole: as you swing across), not as you use it. */
  saidGoing?: (id: ItemId, room: RoomId) => boolean;
  reducedMotion: boolean;
}): Items {
  const { world, scene, player, models, ground, walkable, root, say, sound, changed, stays, begin } = options;
  const glow = new Glow(options.reducedMotion); // round what you're pointing at
  let state = begin?.state ?? newGame(world);
  const lying = new Map<ItemId, Lying>();
  const slots: (ItemId | undefined)[] = []; // (with gaps: each stays in its slot)
  let held = 0; // the slot in your hand
  const carrying = () => slots.some(Boolean);
  const free = () => slots.findIndex((id) => !id); // (there's always one: you can only take five)
  let aimed: ItemId | undefined;
  let reading: number | undefined; // (or the note you're looking at)
  const notes = options.notes ?? [];
  for (const note of notes) note.geometry.computeBoundingBox();
  const eye = new Vector3(); // where you're looking from, and which way
  const look = new Vector3();

  // ---- In the world ---------------------------------------------------------

  /**
   * An object's box, as it comes (lying along z): to point at, turned and
   * tilted with it. (A box squared to north and south round it, turned or
   * tilted, would be bigger than it is, and in front of what's beside it.)
   */
  const boxOf = (id: ItemId) => new Box3().setFromObject(models.getObjectByName(id)!);

  /**
   * Lays an object down at x, z, turned to yaw, on a floor or on the ground.
   * On the ground it rests as a stiff thing would: on the highest bumps under
   * it, tipped towards the side its middle is over (over a mound, it balances
   * on top with its ends in the air; over a hollow, it bridges it).
   */
  function lay(id: ItemId, room: RoomId, x: number, z: number, yaw: number, floor?: number) {
    const model = models.getObjectByName(id)!.clone();
    const size = new Box3().setFromObject(model).getSize(new Vector3());
    const half = size.z / 2;
    const { y, slope } = floor === undefined ? resting(x, z, yaw, half, size.x / 2) : { y: floor, slope: 0 };
    model.position.set(x, y, z);
    model.rotation.set(0, yaw, 0, "YXZ");
    model.rotateX(-Math.atan(slope));
    // (Lying flat, a few centimetres up, its shadow would be a sliver beside
    // it, drawn in steps by the sun's shadow map: none, then. It still has
    // the trees' shadows on it.)
    model.traverse((node) => {
      node.castShadow = false;
      node.receiveShadow = true;
    });
    scene.add(model);
    lying.set(id, {
      room,
      model,
      box: boxOf(id),
      footprint: { x, z, yaw, half, wide: size.x / 2 },
      floor,
    });
  }

  /** The hall (or room) a thing lies in, if any: on its floor (or a step), and within its walls. */
  function hallOf(thing: Lying) {
    if (thing.floor === undefined) return undefined;
    const { x, z } = thing.model.position;
    for (const [place, hall] of player.halls) {
      if (thing.floor < hall.floor - 0.5 || thing.floor > hall.floor + hall.tall) continue;
      const within =
        hall.w !== undefined && hall.d !== undefined
          ? Math.abs(x - hall.x) <= hall.w && Math.abs(z - hall.z) <= hall.d
          : Math.hypot(x - hall.x, z - hall.z) <= hall.r;
      if (within) return place;
    }
    return undefined;
  }

  /** The ground, or the top of a path lying on it. */
  const surface = onPaths(ground, options.paths, options.steps, options.floors);

  /** The line an object rests on, along its length: the ground's upper hull, under its middle. */
  function resting(x: number, z: number, yaw: number, half: number, wide: number) {
    const along = [Math.sin(yaw), Math.cos(yaw)];
    const across = [along[1], -along[0]];
    const n = Math.max(2, Math.ceil((half * 2) / 0.25));
    const profile: [number, number][] = [];
    for (let k = 0; k <= n; k++) {
      const s = -half + (k / n) * half * 2;
      let h = -Infinity;
      for (const w of [-wide, 0, wide]) {
        const g = surface(x + along[0] * s + across[0] * w, z + along[1] * s + across[1] * w);
        if (g !== undefined) h = Math.max(h, g);
      }
      if (h > -Infinity) profile.push([s, h + LIFT]);
    }
    if (profile.length < 2) return { y: (surface(x, z) ?? 0) + LIFT, slope: 0 };
    // The upper hull: the bumps a straight edge would touch.
    const hull: [number, number][] = [];
    for (const p of profile) {
      while (hull.length >= 2) {
        const [a, b] = [hull[hull.length - 2], hull[hull.length - 1]];
        if ((b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) < 0) break;
        hull.pop();
      }
      hull.push(p);
    }
    let k = 0;
    while (k < hull.length - 2 && hull[k + 1][0] < 0) k++;
    const [[s0, h0], [s1, h1]] = [hull[k], hull[k + 1]];
    const slope = (h1 - h0) / (s1 - s0);
    return { y: h0 - s0 * slope, slope };
  }

  /**
   * Where an object starts: anywhere in its place you can get to, a new spot
   * every game, so you have to go and look for it. On the land, the ground
   * you can walk to from the place's middle without going through anything
   * (nor into an obstacle's reach, nor down a tunnel's mouth); in a hall,
   * anywhere on its floor, clear of its walls and what stands in it.
   */
  function start(id: ItemId, room: RoomId) {
    const fixed = options.starts?.[id];
    if (fixed?.room === room) return lay(id, room, fixed.at[0], fixed.at[1], 0, fixed.at[2]);
    const hall = player.halls.get(room);
    const size = new Box3().setFromObject(models.getObjectByName(id)!).getSize(new Vector3());
    const half = size.z / 2;
    const wide = size.x / 2;
    const area = hall
      ? { has: (x: number, z: number) => inHall(hall, x, z), somewhere: () => somewhereIn(hall) }
      : reachable(room);
    if (!area) return;
    const fits = area.has;
    for (let tries = 0; tries < 400; tries++) {
      const [x, z] = area.somewhere();
      const yaw = Math.random() * Math.PI * 2;
      const along = [Math.sin(yaw), Math.cos(yaw)];
      const across = [along[1], -along[0]];
      // All of it, every half metre along it and out to its sides (the axe's
      // head, say), on a spot that fits: never in the hut's fire, or a wall.
      const n = Math.ceil((half * 2) / 0.5);
      const all = Array.from({ length: n + 1 }, (_, k) => -half + (k / n) * half * 2);
      const sides = [-wide, 0, wide];
      if (
        all.every((d) => sides.every((w) => fits(x + along[0] * d + across[0] * w, z + along[1] * d + across[1] * w)))
      ) {
        lay(id, room, x, z, yaw, hall?.floor);
        return;
      }
    }
  }

  /** In a hall, a little way in from its wall, and clear of what stands in it. */
  function inHall(hall: Hall, x: number, z: number) {
    const inside =
      hall.w !== undefined && hall.d !== undefined
        ? Math.abs(x - hall.x) <= hall.w - WALL && Math.abs(z - hall.z) <= hall.d - WALL
        : Math.hypot(x - hall.x, z - hall.z) <= hall.r - WALL;
    return inside && player.clear(x, z, true, 0.3);
  }

  function somewhereIn(hall: Hall) {
    if (hall.w !== undefined && hall.d !== undefined) {
      return [hall.x + (Math.random() * 2 - 1) * hall.w, hall.z + (Math.random() * 2 - 1) * hall.d];
    }
    const angle = Math.random() * Math.PI * 2;
    const out = Math.sqrt(Math.random()) * hall.r;
    return [hall.x + Math.cos(angle) * out, hall.z + Math.sin(angle) * out];
  }

  /** The ground in a place you can walk to from its middle, half a metre at a time. */
  function reachable(room: RoomId) {
    const centre = PLACES.get(room);
    if (!centre) return undefined;
    const cell = (x: number, z: number) => `${Math.round(x / FILL)},${Math.round(z / FILL)}`;
    const open = (x: number, z: number) =>
      walkable(x, z) &&
      player.clear(x, z, false, 0.3) &&
      placeAt(x, z, "", player.halls) === room &&
      !player.ways.some((way) => !way.indoor && nearest(way, x, z).d < way.half + 1.5);
    // From the open spot nearest the middle.
    let first: [number, number] | undefined;
    for (let r = 0; r < 10 && !first; r += FILL) {
      for (let a = 0; a < 16 && !first; a++) {
        const x = centre.x + Math.cos((a * Math.PI) / 8) * r;
        const z = centre.z + Math.sin((a * Math.PI) / 8) * r;
        if (open(x, z)) first = [Math.round(x / FILL) * FILL, Math.round(z / FILL) * FILL];
      }
    }
    if (!first) return undefined;
    const from = first;
    const reached = new Map<string, [number, number]>();
    const queue = [first];
    while (queue.length) {
      const [x, z] = queue.pop()!;
      const key = cell(x, z);
      if (reached.has(key) || !open(x, z)) continue;
      reached.set(key, [x, z]);
      queue.push([x + FILL, z], [x - FILL, z], [x, z + FILL], [x, z - FILL]);
    }
    const spots = [...reached.values()];
    return {
      first: from,
      has: (x: number, z: number) => reached.has(cell(x, z)),
      somewhere: () => spots[Math.floor(Math.random() * spots.length)],
    };
  }

  /** In a hall, the clear spot nearest its middle; on the land, the open ground nearest the place's middle. */
  function arrival(room: RoomId): [number, number] | undefined {
    const hall = player.halls.get(room);
    if (!hall) return reachable(room)?.first;
    for (let r = 0; r < hall.r; r += FILL) {
      for (let a = 0; a < 16; a++) {
        const x = hall.x + Math.cos((a * Math.PI) / 8) * r;
        const z = hall.z + Math.sin((a * Math.PI) / 8) * r;
        if (player.clear(x, z, true, 0.5)) return [x, z];
      }
    }
    return [hall.x, hall.z];
  }

  /** A game, from the start or loaded: what you carry, and where everything lies. */
  function layOut(three?: ThreeSave) {
    for (const thing of lying.values()) scene.remove(thing.model);
    lying.clear();
    aimed = undefined;
    // What you carry: in the slots it was in, if it's known.
    const carried = (Object.keys(state.itemLocations) as ItemId[]).filter(
      (id) => state.itemLocations[id] === "carried"
    );
    slots.splice(0, slots.length, ...Array.from({ length: SLOTS }, () => undefined));
    (three?.slots ?? []).forEach((id, k) => {
      if (k < SLOTS && carried.includes(id as ItemId)) slots[k] = id as ItemId;
    });
    for (const id of carried) if (!slots.includes(id)) slots[free()] = id;
    held = 0;
    // Where they lie: where they lay when the game was saved, or anywhere in
    // their places (as in a new game, or one saved in another version).
    for (const [id, where] of Object.entries(state.itemLocations) as [ItemId, string][]) {
      if (where === "carried" || !models.getObjectByName(id)) continue;
      const spot = three?.lying[id];
      if (spot) lay(id, where, spot[0], spot[1], spot[2], spot[3]);
      else start(id, where);
    }
  }
  layOut(begin?.three);

  // ---- On the screen --------------------------------------------------------

  const aim = document.createElement("div");
  aim.className = "aim";
  const prompt = document.createElement("p");
  prompt.className = "prompt";
  const bar = document.createElement("div");
  bar.className = "slots";
  bar.setAttribute("aria-label", T.carrying);
  root.append(aim, prompt, bar);

  const the = (id: ItemId) => T.theItem(world.items[id].name, world.items[id].definite);

  function draw(arriving?: ItemId) {
    bar.classList.remove("shake"); // (or the new slots would shake again)
    bar.replaceChildren(
      ...Array.from({ length: SLOTS }, (_, k) => {
        const id = slots[k];
        const slot = document.createElement("div");
        slot.className = `slot${k === held ? " held" : ""}${id && id === arriving ? " arriving" : ""}`;
        if (id && effects(world, state).includes(id)) slot.classList.add("in-use");
        const key = document.createElement("span");
        key.className = "key";
        key.textContent = String(k + 1);
        slot.append(key);
        if (!id) return slot;
        slot.title = world.items[id].name;
        const url = artUrl("items", id);
        if (url) {
          const image = document.createElement("img");
          image.src = url;
          image.alt = world.items[id].name;
          slot.append(image);
        } else {
          slot.append(world.items[id].name);
        }
        return slot;
      })
    );
  }
  draw();

  /** Your slots flash: you can't carry any more. */
  function flash() {
    bar.classList.remove("full");
    void bar.offsetWidth;
    bar.classList.add("full");
  }

  /** The slot in your hand shakes (or all of them, empty-handed): nothing happens. */
  function shake() {
    const slot = carrying() ? bar.children[held] : bar;
    bar.classList.remove("shake");
    slot?.classList.remove("shake");
    void (slot as HTMLElement | undefined)?.offsetWidth;
    slot?.classList.add("shake");
  }

  // ---- Taking and dropping --------------------------------------------------

  function take(id: ItemId) {
    const thing = lying.get(id)!;
    // You took it from where it lies, whichever place you're counted in.
    const result = act(world, { ...state, room: thing.room }, { type: "take", item: id });
    if (result.state.itemLocations[id] !== "carried") {
      say(result.events.at(-1)?.text ?? ""); // ("You're carrying too much.")
      flash();
      sound("refuse");
      return;
    }
    // (The first time you've found it, a twinkle.)
    if (!state.found?.includes(id)) sound("discover");
    sound("take");
    stuck = 0;
    state = { ...result.state, room: state.room };
    scene.remove(thing.model);
    lying.delete(id);
    // Into the slot in your hand if it's empty (and it stays in your hand),
    // or else the first empty one.
    slots[slots[held] ? free() : held] = id;
    draw(id);
  }

  function use() {
    if (!carrying()) {
      say(T.carryingNothing);
      shake();
      sound("nothing");
      return;
    }
    const id = slots[held];
    if (!id) {
      shake(); // (an empty hand)
      sound("nothing");
      return;
    }
    const already = effects(world, state).includes(id);
    const result = act(world, state, { type: "use", item: id });
    state = result.state;
    if (effects(world, state).includes(id)) {
      if (!already) stuck = 0; // (a way opened)
      // (What it does here, if it opens a way: "The ladder leans against the wall.")
      const opens = EXIT_ORDER.some((d) => world.rooms[state.room].exits[d]?.obstacle?.needs === id);
      if (opens && !options.saidGoing?.(id, state.room)) say(result.events.at(-1)?.text ?? "");
      sound("effect");
      draw();
      changed();
      return;
    }
    say(result.events.at(-1)?.text ?? "");
    shake();
    sound("nothing");
  }

  function drop() {
    const id = slots[held];
    if (!id) return;
    const inUse = effects(world, state).includes(id);
    const result = act(world, state, { type: "drop", item: id });
    if (result.state.itemLocations[id] === "carried") return;
    state = result.state;
    sound("drop");
    // (The last treasure on the grassy bank: you've won.)
    if (state.status === "won") sound("victory");
    slots[held] = undefined;
    // On to the next thing you carry (round from the last slot to the first),
    // so G again drops that: or, carrying nothing now, back to the first slot.
    held = Array.from({ length: SLOTS }, (_, k) => (held + k) % SLOTS).find((k) => slots[k]) ?? 0;
    draw();
    // (Something with no model yet, carried over from another version, is
    // just dropped, where you can't see it.)
    if (!models.getObjectByName(id)) return;
    // Still in use, it stays as it is (against the wall), lying in the place.
    const staying = inUse ? stays(id) : undefined;
    changed();
    if (staying) {
      const { model, fallsTo, box } = staying;
      lying.set(id, {
        room: state.room,
        model,
        box: box ?? boxOf(id),
        fallsTo,
      });
      return;
    }
    // Its middle where you're pointing, lying the way you're looking (its
    // handle towards you: the axe's, the key's bow), or nudged aside (or on a
    // little) off anything already lying there.
    const yaw = player.yaw;
    const size = new Box3().setFromObject(models.getObjectByName(id)!).getSize(new Vector3());
    const side = [Math.cos(player.yaw), -Math.sin(player.yaw)];
    const forward = [-Math.sin(player.yaw), -Math.cos(player.yaw)];
    const [px, pz, floor] = pointedAt();
    const spots = NUDGES.map(([aside, on]) => ({
      x: px + forward[0] * on + side[0] * aside,
      z: pz + forward[1] * on + side[1] * aside,
      yaw,
      half: size.z / 2,
      wide: size.x / 2,
    }));
    // (All of it somewhere you could reach to take it again: not in the
    // hut's fire, say, or a sack, or a wall. Or, if nowhere round where
    // you're pointing will do, at your feet.)
    const taken = [...lying.values()].flatMap((thing) => (thing.footprint ? [thing.footprint] : []));
    const free = (spot: Footprint) =>
      covered(spot).every(([x, z]) => open(x, z)) && !taken.some((other) => overlap(spot, other));
    const spot = spots.find(free);
    const { x, z } = spot ?? player.position;
    lay(id, state.room, x, z, yaw, spot ? floor : player.under?.floor);
  }

  /**
   * Whether a spot's open, for something to lie on (or your gaze to go over):
   * on the land, the ground you could walk on; off it, a hall's floor or a
   * way's. Not in anything solid there (the hut's fire, a rock, a wall).
   */
  function open(x: number, z: number) {
    const { under } = player;
    if (!under) return walkable(x, z) && player.clear(x, z, false, 0.05);
    const floor =
      Boolean(player.hallAt(x, z)) ||
      player.ways.some((way) => {
        const there = nearest(way, x, z);
        return there.d < way.half - 0.2 && Math.abs(there.floor - under.floor) < 1;
      });
    return floor && !player.inSolid(x, z, true);
  }

  /**
   * Where you're pointing, on the ground (or the floor, or the top of a step
   * or a table, or the chest's tray, coming down onto it): along your gaze
   * until it meets it, as far as you can reach, and not past anything you
   * couldn't walk past (a wall, the forest, the water, an obstacle), nor
   * right under you. Off the land, how high that is.
   */
  function pointedAt(): [number, number, number | undefined] {
    player.camera.getWorldPosition(eye);
    player.camera.getWorldDirection(look);
    const { position: me, under } = player;
    // (What your gaze was already over, a step before: not what it goes into
    // the side of, or under.)
    const floorAt = (x: number, z: number, over: number) =>
      under ? Math.max(under.floor, player.topAt(x, z, over)) : undefined;
    let spot: [number, number, number | undefined] = [me.x, me.z, under?.floor];
    let was = eye.y;
    for (let d = 0.1; d <= REACH; d += 0.1) {
      const x = eye.x + look.x * d;
      const z = eye.z + look.z * d;
      if (!open(x, z)) break;
      const floor = floorAt(x, z, was);
      spot = [x, z, floor];
      was = eye.y + look.y * d;
      if (was <= (floor ?? ground(x, z) ?? -Infinity)) break;
    }
    // (At least a little way in front of you.)
    const away = Math.hypot(spot[0] - me.x, spot[1] - me.z);
    if (away < NEAREST) {
      const forward = [-Math.sin(player.yaw), -Math.cos(player.yaw)];
      const [x, z] = [me.x + forward[0] * NEAREST, me.z + forward[1] * NEAREST];
      spot = [x, z, floorAt(x, z, me.y + 0.45)];
    }
    return spot;
  }

  /** Leaving a place, what was in use there falls where it stood. */
  function settle() {
    for (const [id, thing] of lying) {
      if (!thing.fallsTo) continue;
      scene.remove(thing.model);
      lying.delete(id);
      const { x, z, yaw, floor } = thing.fallsTo;
      lay(id, thing.room, x, z, yaw, floor);
    }
  }

  // A click uses the object in your hand (while you're looking about, not
  // clicking to start).
  addEventListener("mousedown", (event) => {
    if (event.button === 0 && document.pointerLockElement && !player.busy) use();
  });

  addEventListener("keydown", (event) => {
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    // (Climbing, you can get the next thing ready in your hand, but not take or drop.)
    if (/^Digit[1-5]$/.test(event.code)) {
      held = Number(event.code.slice(5)) - 1;
      draw();
    } else if (player.busy) return;
    // E takes what you're looking at (or reads it), or else uses what's in your hand.
    else if (event.code === "KeyE") {
      if (reading !== undefined) options.read?.(reading);
      else if (aimed) take(aimed);
      else use();
    } else if (event.code === "KeyG") drop();
  });

  // ---- Each frame -----------------------------------------------------------

  // Catching your eye (stuck): how long since you last took something or
  // overcame an obstacle; the objects in sight; and those hopping (from
  // where, and how long since they started).
  let stuck = 0;
  let then = performance.now();
  const inSight = new Set<ItemId>();
  const hopping = new Map<ItemId, { model: Object3D; y: number; t: number }>();
  const seen = new Vector3();

  function nudge() {
    const now = performance.now();
    const dt = Math.min(0.1, (now - then) / 1000); // (not counting while paused)
    then = now;
    stuck += dt;
    for (const [id, hop] of hopping) {
      const t = (hop.t += dt);
      // (Taken, or dropped somewhere new: it's not hopping any more.)
      if (lying.get(id)?.model !== hop.model) {
        hopping.delete(id);
        continue;
      }
      const up = HOPS.find(([from, long]) => t >= from && t < from + long);
      hop.model.position.y =
        hop.y + (up && !options.reducedMotion ? up[2] * Math.sin((Math.PI * (t - up[0])) / up[1]) : 0);
      if (t >= GLOWS + AGAIN) hopping.delete(id);
    }
    if (stuck < STUCK) {
      inSight.clear();
      return;
    }
    // Each you've never held, coming into sight: it hops.
    for (const [id, thing] of lying) {
      const { x, z } = thing.model.position;
      const y = hopping.get(id)?.y ?? thing.model.position.y;
      seen.set(x, y, z).project(player.camera);
      const sees =
        !state.found?.includes(id) &&
        hallOf(thing) === player.under?.hall &&
        Math.hypot(x - eye.x, y - eye.y, z - eye.z) <= NOTICE &&
        Math.abs(seen.x) < 0.9 &&
        Math.abs(seen.y) < 0.9 &&
        seen.z < 1 &&
        player.between(eye.x, eye.z, x, z, Boolean(player.under), Math.max(eye.y, y));
      if (sees && !inSight.has(id) && !hopping.has(id)) hopping.set(id, { model: thing.model, y, t: 0 });
      if (sees) inSight.add(id);
      else inSight.delete(id);
    }
  }

  /** The nearest object hopping (still glowing), if any. */
  function hopper() {
    let best: Object3D | undefined;
    for (const { model, t } of hopping.values()) {
      if (t < GLOWS && (!best || model.position.distanceTo(eye) < best.position.distanceTo(eye))) best = model;
    }
    return best;
  }

  const ray = new Ray();
  const mine = new Ray();
  const roomy = new Box3();
  const on = new Vector3();
  const inverse = new Matrix4();
  const hit = new Vector3();
  const front = new Vector3();

  /**
   * How near your gaze comes to something (its box, square to it: 0 if it
   * hits it), and how far off: or nothing, out of reach, or from the far
   * side of a wall from [x, z] (where it's seen from).
   */
  function gaze(model: Object3D, box: Box3, x: number, z: number) {
    // (Your gaze, as the object sees it: then its box is square to it.)
    model.updateMatrixWorld();
    mine.copy(ray).applyMatrix4(inverse.copy(model.matrixWorld).invert());
    const room = roomy.copy(box).expandByScalar(AIM_SLACK);
    if (!mine.intersectBox(room, hit)) return undefined;
    // On through the room round it, how near it comes to it (0: it hits it).
    // (From where it comes into that room, or from your eye if you're in it.)
    const from = room.containsPoint(mine.origin) ? 0 : mine.origin.distanceTo(hit);
    let miss = Infinity;
    let at = 0;
    for (let s = 0; s < 8 && miss > 0; s += 0.02) {
      mine.at(from + s, on);
      if (s > 0 && !room.containsPoint(on)) break;
      const m = box.distanceToPoint(on);
      if (m < miss) [miss, at] = [m, s];
    }
    const d = from + at;
    if (d > REACH || !player.between(eye.x, eye.z, x, z, Boolean(player.under), Math.max(eye.y, model.position.y)))
      return undefined;
    return { miss, d };
  }

  return {
    get state() {
      return state;
    },
    saved() {
      const spots: ThreeSave["lying"] = {};
      for (const [id, thing] of lying) {
        const { x, z, yaw } = thing.fallsTo ?? thing.footprint!;
        const round = (v: number) => Math.round(v * 100) / 100;
        const floor = thing.fallsTo ? thing.fallsTo.floor : thing.floor;
        spots[id] = floor === undefined ? [round(x), round(z), round(yaw)] : [round(x), round(z), round(yaw), floor];
      }
      return { slots: slots.map((id) => id ?? null), lying: spots };
    },
    arrival,
    lyingAt: (id) => lying.get(id)?.model,
    lying: () => [...lying.values()].map((thing) => thing.model),
    restart(game) {
      for (const { model, y } of hopping.values()) model.position.y = y;
      hopping.clear();
      inSight.clear();
      stuck = 0;
      state = game.state;
      layOut(game.three);
      glow.show(undefined);
      draw();
    },
    go(direction) {
      const result = act(world, state, { type: "go", direction });
      const went = result.state.room !== state.room;
      if (went && world.rooms[state.room].exits[direction]?.obstacle) stuck = 0; // (an obstacle overcome)
      state = result.state;
      if (went) settle();
      draw();
      changed();
      return went;
    },
    update(room) {
      // A new place: whatever was in use stays behind (as in the original).
      if (room !== state.room) {
        state = { ...state, room, using: [] };
        settle();
        draw();
        changed();
      }

      player.camera.getWorldPosition(eye);
      player.camera.getWorldDirection(look);
      ray.set(eye, look);
      // What you're looking at: the nearest thing your gaze hits; or, if it
      // hits none, the thing it passes closest to (within a little room round
      // each). Not just the first room round something it comes to: lying
      // side by side, the room round one would cover the next.
      aimed = undefined;
      reading = undefined;
      let best = { miss: AIM_SLACK, d: REACH };
      // (Is it nearer your gaze than the best so far?)
      const better = (gazed: { miss: number; d: number } | undefined) =>
        gazed &&
        (gazed.miss < best.miss - 0.01 || (Math.abs(gazed.miss - best.miss) <= 0.01 && gazed.d < best.d)) &&
        (best = gazed);
      for (const [id, thing] of lying) {
        // (Not through a wall: what's in a hall or a room only from in it,
        // and from in one only what's in it.)
        if (hallOf(thing) !== player.under?.hall) continue;
        // (Nor through anything solid: from the far side of a wall.)
        const { x, z } = thing.model.position;
        if (better(gaze(thing.model, thing.box, x, z))) aimed = id;
      }
      // And the notes (from their side of a wall: in front of them, along
      // the way, in the dead end of a tunnel).
      notes.forEach((note, k) => {
        if (player.under?.hall) return;
        front.set(0, 0, 1).applyQuaternion(note.quaternion).add(note.position);
        if (better(gaze(note, note.geometry.boundingBox!, front.x, front.z))) {
          aimed = undefined;
          reading = k;
        }
      });
      nudge();
      glow.show(aimed ? lying.get(aimed)?.model : hopper());
      glow.update(performance.now() / 1000);
      const pointing = Boolean(aimed) || reading !== undefined;
      aim.classList.toggle("on", pointing);
      prompt.classList.toggle("shown", pointing);
      if (pointing) {
        const key = document.createElement("kbd");
        key.textContent = "E";
        prompt.replaceChildren(key, ` ${aimed ? T.take(the(aimed)) : T.readNote}`);
      }
    },
  };
}
