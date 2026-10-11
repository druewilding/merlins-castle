// The objects: lying where the game puts them, taken by looking at one and
// pressing E, carried in five slots (1–5 picks one), and dropped with G.
// The engine stays the judge (PLAN-V3.md): taking and dropping are its
// `take` and `drop`, and what it says decides what happens.
//
// Only objects with a model (art/blender/items.py) are in the world so far.

import { Box3, type Object3D, Ray, type Scene, Vector3 } from "three";

import { act, newGame } from "../engine/engine";
import type { GameState, ItemId, RoomId, World } from "../engine/types";
import { artUrl } from "../illustrated/art";
import { T } from "../shared/strings";
import { placeAt, PLACES } from "./layout";
import { type Ground, type Hall, nearest, type Player, type Walkable } from "./player";

const SLOTS = 5;
// How far you can reach to take something (from your eyes).
const REACH = 8;
// A thin object is easier to point at with a little room round it.
const AIM_SLACK = 0.25;
// The ground you walk on is a little smoother than the ground you see; an
// object lies this far above it, so it never sinks in.
const LIFT = 0.04;
// Where objects start: the ground's checked every half metre, and in a hall
// they keep this far from its wall.
const FILL = 0.5;
const WALL = 1;

interface Lying {
  room: RoomId;
  model: Object3D;
  box: Box3;
}

export interface Items {
  /** Each frame: where you are, and what you're looking at. */
  update(room: RoomId): void;
  readonly state: GameState;
}

export function items(options: {
  world: World;
  scene: Scene;
  player: Player;
  models: Object3D;
  ground: Ground;
  walkable: Walkable;
  root: HTMLElement;
}): Items {
  const { world, scene, player, models, ground, walkable, root } = options;
  let state = newGame(world);
  const lying = new Map<ItemId, Lying>();
  const slots: ItemId[] = [];
  let held = 0; // the slot in your hand
  let aimed: ItemId | undefined;

  // ---- In the world ---------------------------------------------------------

  /** How long an object is, end to end, so it lies on the slope under it. */
  const lengthOf = (model: Object3D) => new Box3().setFromObject(model).getSize(new Vector3()).z;

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
    model.traverse((node) => {
      node.castShadow = true;
      node.receiveShadow = true;
    });
    scene.add(model);
    lying.set(id, { room, model, box: new Box3().setFromObject(model).expandByScalar(AIM_SLACK) });
  }

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
        const g = ground(x + along[0] * s + across[0] * w, z + along[1] * s + across[1] * w);
        if (g !== undefined) h = Math.max(h, g);
      }
      if (h > -Infinity) profile.push([s, h + LIFT]);
    }
    if (profile.length < 2) return { y: (ground(x, z) ?? 0) + LIFT, slope: 0 };
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
    const hall = player.halls.get(room);
    const half = lengthOf(models.getObjectByName(id)!) / 2;
    const area = hall
      ? { has: (x: number, z: number) => inHall(hall, x, z), somewhere: () => somewhereIn(hall) }
      : reachable(room);
    if (!area) return;
    const fits = area.has;
    for (let tries = 0; tries < 400; tries++) {
      const [x, z] = area.somewhere();
      const yaw = Math.random() * Math.PI * 2;
      const along = [Math.sin(yaw), Math.cos(yaw)];
      // All of it, every half metre along it, on a spot that fits.
      const n = Math.ceil((half * 2) / 0.5);
      const all = Array.from({ length: n + 1 }, (_, k) => -half + (k / n) * half * 2);
      if (all.every((d) => fits(x + along[0] * d, z + along[1] * d))) {
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
      has: (x: number, z: number) => reached.has(cell(x, z)),
      somewhere: () => spots[Math.floor(Math.random() * spots.length)],
    };
  }

  for (const [id, where] of Object.entries(state.itemLocations)) {
    if (where !== "carried" && models.getObjectByName(id)) start(id, where);
  }

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
    bar.replaceChildren(
      ...Array.from({ length: SLOTS }, (_, k) => {
        const id = slots[k];
        const slot = document.createElement("div");
        slot.className = `slot${k === held ? " held" : ""}${id && id === arriving ? " arriving" : ""}`;
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

  // ---- Taking and dropping --------------------------------------------------

  function take(id: ItemId) {
    const thing = lying.get(id)!;
    // You took it from where it lies, whichever place you're counted in.
    const result = act(world, { ...state, room: thing.room }, { type: "take", item: id });
    if (result.state.itemLocations[id] !== "carried") {
      flash();
      return;
    }
    state = { ...result.state, room: state.room };
    scene.remove(thing.model);
    lying.delete(id);
    slots.push(id);
    held = slots.length - 1;
    draw(id);
  }

  function drop() {
    const id = slots[held];
    if (!id) return;
    const result = act(world, state, { type: "drop", item: id });
    if (result.state.itemLocations[id] === "carried") return;
    state = result.state;
    slots.splice(held, 1);
    held = Math.min(held, Math.max(0, slots.length - 1));
    draw();
    // Laid down just in front of you, pointing the way you're looking.
    const yaw = player.yaw + Math.PI;
    const half = lengthOf(models.getObjectByName(id)!) / 2;
    const ahead = 0.8 + half;
    const x = player.position.x - Math.sin(player.yaw) * ahead;
    const z = player.position.z - Math.cos(player.yaw) * ahead;
    lay(id, state.room, x, z, yaw, player.under ? player.under.floor : undefined);
  }

  addEventListener("keydown", (event) => {
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === "KeyE" && aimed) take(aimed);
    else if (event.code === "KeyG") drop();
    else if (/^Digit[1-5]$/.test(event.code)) {
      held = Number(event.code.slice(5)) - 1;
      draw();
    }
  });

  // ---- Each frame -----------------------------------------------------------

  const ray = new Ray();
  const eye = new Vector3();
  const look = new Vector3();
  const hit = new Vector3();

  return {
    get state() {
      return state;
    },
    update(room) {
      // A new place: whatever was in use stays behind (as in the original).
      if (room !== state.room) state = { ...state, room, using: [] };

      player.camera.getWorldPosition(eye);
      player.camera.getWorldDirection(look);
      ray.set(eye, look);
      aimed = undefined;
      let nearest = REACH;
      for (const [id, thing] of lying) {
        if (!ray.intersectBox(thing.box, hit)) continue;
        const d = hit.distanceTo(eye);
        if (d < nearest) {
          nearest = d;
          aimed = id;
        }
      }
      aim.classList.toggle("on", Boolean(aimed));
      prompt.classList.toggle("shown", Boolean(aimed));
      if (aimed) {
        const key = document.createElement("kbd");
        key.textContent = "E";
        prompt.replaceChildren(key, ` ${T.take(the(aimed))}`);
      }
    },
  };
}
