// The objects: lying where the game puts them, taken by looking at one and
// pressing E, carried in five slots (1–5 picks the one in your hand), used
// with E when you're not looking at one (or a click) and dropped with G. The engine stays the judge (PLAN-V3.md):
// these are its `take`, `use` and `drop`, and what it says decides what
// happens. An object in use (opening a way out of the place) has a tick.
//
// Only objects with a model (art/blender/items.py) are in the world so far.

import { Box3, type Object3D, Ray, type Scene, Vector3 } from "three";

import { act, effects, newGame } from "../engine/engine";
import type { Direction, GameState, ItemId, RoomId, World } from "../engine/types";
import { artUrl } from "../illustrated/art";
import { T } from "../shared/strings";
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
  box: Box3;
  footprint?: Footprint;
  // Dropped where it was in use (the ladder against the wall): once you've
  // left, it's lying on the ground here.
  fallsTo?: Footing;
}

/** Where an object stands, and which way it lies when it falls. */
export interface Footing {
  x: number;
  z: number;
  yaw: number;
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
}

export function items(options: {
  world: World;
  scene: Scene;
  player: Player;
  models: Object3D;
  ground: Ground;
  walkable: Walkable;
  root: HTMLElement;
  /** Words at the bottom of the screen ("Nothing happens."). */
  say: (words: string) => void;
  /** What's in use has changed: an object used, or the place left. */
  changed: () => void;
  /** Dropping an object where it's in use, it stays as it is (the ladder against the wall): its model, if so. */
  stays: (id: ItemId) => { model: Object3D; fallsTo: Footing } | undefined;
}): Items {
  const { world, scene, player, models, ground, walkable, root, say, changed, stays } = options;
  let state = newGame(world);
  const lying = new Map<ItemId, Lying>();
  const slots: ItemId[] = [];
  let held = 0; // the slot in your hand
  let aimed: ItemId | undefined;
  const eye = new Vector3(); // where you're looking from, and which way
  const look = new Vector3();

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
    lying.set(id, {
      room,
      model,
      box: new Box3().setFromObject(model).expandByScalar(AIM_SLACK),
      footprint: { x, z, yaw, half, wide: size.x / 2 },
    });
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
    const slot = slots.length ? bar.children[held] : bar;
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

  function use() {
    if (!slots.length) {
      say(T.carryingNothing);
      shake();
      return;
    }
    const id = slots[held];
    if (!id) return;
    const result = act(world, state, { type: "use", item: id });
    state = result.state;
    if (effects(world, state).includes(id)) {
      draw();
      changed();
      return;
    }
    say(result.events.at(-1)?.text ?? "");
    shake();
  }

  function drop() {
    const id = slots[held];
    if (!id) return;
    const inUse = effects(world, state).includes(id);
    const result = act(world, state, { type: "drop", item: id });
    if (result.state.itemLocations[id] === "carried") return;
    state = result.state;
    slots.splice(held, 1);
    held = Math.min(held, Math.max(0, slots.length - 1));
    draw();
    // Still in use, it stays as it is (against the wall), lying in the place.
    const staying = inUse ? stays(id) : undefined;
    changed();
    if (staying) {
      const { model, fallsTo } = staying;
      lying.set(id, {
        room: state.room,
        model,
        box: new Box3().setFromObject(model).expandByScalar(AIM_SLACK),
        fallsTo,
      });
      return;
    }
    // Its middle where you're pointing, lying the way you're looking, or
    // nudged aside (or on a little) off anything already lying there.
    const yaw = player.yaw + Math.PI;
    const size = new Box3().setFromObject(models.getObjectByName(id)!).getSize(new Vector3());
    const side = [Math.cos(player.yaw), -Math.sin(player.yaw)];
    const forward = [-Math.sin(player.yaw), -Math.cos(player.yaw)];
    const [px, pz] = pointedAt();
    const spots = NUDGES.map(([aside, on]) => ({
      x: px + forward[0] * on + side[0] * aside,
      z: pz + forward[1] * on + side[1] * aside,
      yaw,
      half: size.z / 2,
      wide: size.x / 2,
    }));
    const taken = [...lying.values()].flatMap((thing) => (thing.footprint ? [thing.footprint] : []));
    const { x, z } = spots.find((spot) => !taken.some((other) => overlap(spot, other))) ?? spots[0];
    lay(id, state.room, x, z, yaw, player.under ? player.under.floor : undefined);
  }

  /**
   * Where you're pointing, on the ground (or the floor): along your gaze until
   * it meets it, as far as you can reach, and not past anything you couldn't
   * walk past (a wall, the forest, the water, an obstacle), nor right under you.
   */
  function pointedAt(): [number, number] {
    player.camera.getWorldPosition(eye);
    player.camera.getWorldDirection(look);
    const { position: me, under } = player;
    const open = under
      ? (x: number, z: number) =>
          Boolean(player.hallAt(x, z)) ||
          player.ways.some((way) => {
            const there = nearest(way, x, z);
            return there.d < way.half - 0.2 && Math.abs(there.floor - under.floor) < 1;
          })
      : (x: number, z: number) => walkable(x, z) && player.clear(x, z, false, 0.05);
    let spot: [number, number] = [me.x, me.z];
    for (let d = 0.1; d <= REACH; d += 0.1) {
      const x = eye.x + look.x * d;
      const z = eye.z + look.z * d;
      if (!open(x, z)) break;
      spot = [x, z];
      if (eye.y + look.y * d <= (under ? under.floor : (ground(x, z) ?? -Infinity))) break;
    }
    // (At least a little way in front of you.)
    const away = Math.hypot(spot[0] - me.x, spot[1] - me.z);
    if (away < NEAREST) {
      const forward = [-Math.sin(player.yaw), -Math.cos(player.yaw)];
      spot = [me.x + forward[0] * NEAREST, me.z + forward[1] * NEAREST];
    }
    return spot;
  }

  /** Leaving a place, what was in use there falls where it stood. */
  function settle() {
    for (const [id, thing] of lying) {
      if (!thing.fallsTo) continue;
      scene.remove(thing.model);
      lying.delete(id);
      const { x, z, yaw } = thing.fallsTo;
      lay(id, thing.room, x, z, yaw);
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
    // E takes what you're looking at, or else uses what's in your hand.
    else if (event.code === "KeyE") {
      if (aimed) take(aimed);
      else use();
    } else if (event.code === "KeyG") drop();
  });

  // ---- Each frame -----------------------------------------------------------

  const ray = new Ray();
  const hit = new Vector3();

  return {
    get state() {
      return state;
    },
    go(direction) {
      const result = act(world, state, { type: "go", direction });
      const went = result.state.room !== state.room;
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
