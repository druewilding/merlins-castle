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
import { PLACES } from "./layout";
import type { Ground, Player, Walkable } from "./player";

const SLOTS = 5;
// How far you can reach to take something (from your eyes).
const REACH = 3.5;
// A thin object is easier to point at with a little room round it.
const AIM_SLACK = 0.25;

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

  /** Lays an object down at x, z, turned to yaw, on the ground or a floor. */
  function lay(id: ItemId, room: RoomId, x: number, z: number, yaw: number, floor?: number) {
    const model = models.getObjectByName(id)!.clone();
    const half = lengthOf(model) / 2;
    const ax = x - Math.sin(yaw) * half;
    const az = z - Math.cos(yaw) * half;
    const bx = x + Math.sin(yaw) * half;
    const bz = z + Math.cos(yaw) * half;
    const ya = floor ?? ground(ax, az) ?? 0;
    const yb = floor ?? ground(bx, bz) ?? 0;
    model.position.set(x, (ya + yb) / 2, z);
    // Along its length, tipped to lie on the slope.
    model.rotation.set(0, yaw, 0, "YXZ");
    model.rotateX(-Math.atan2(yb - ya, half * 2));
    model.traverse((node) => {
      node.castShadow = true;
      node.receiveShadow = true;
    });
    scene.add(model);
    lying.set(id, { room, model, box: new Box3().setFromObject(model).expandByScalar(AIM_SLACK) });
  }

  /** Where an object starts in a place: near its middle, all of it on ground you can walk on. */
  function start(id: ItemId, room: RoomId) {
    const hall = player.halls.get(room);
    const centre = hall ?? PLACES.get(room);
    if (!centre) return;
    const half = lengthOf(models.getObjectByName(id)!) / 2;
    // A turn and a distance from the object's name, so it's the same every time.
    const seed = [...id].reduce((sum, letter) => sum * 31 + letter.charCodeAt(0), 7);
    for (let k = 0; k < 24; k++) {
      const angle = seed + k * 2.4;
      const out = hall ? Math.min(3, hall.r * 0.4) : 4 + (k % 4) * 2;
      const x = centre.x + Math.cos(angle) * out;
      const z = centre.z + Math.sin(angle) * out;
      const yaw = angle + Math.PI / 2;
      const ends = [-half, 0, half].map((d) => [x + Math.sin(yaw) * d, z + Math.cos(yaw) * d]);
      if (hall || ends.every(([ex, ez]) => walkable(ex, ez))) {
        lay(id, room, x, z, yaw, hall?.floor);
        return;
      }
    }
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
