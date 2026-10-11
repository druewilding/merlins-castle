// The debug panel, for finding your way round while building: fly, walk
// through anything, open every obstacle, go faster, and jump anywhere on a
// map. Opened with the 0 key (on the number row or the number pad, so it
// works whatever the keyboard's language). P copies what you're looking at
// to the clipboard, for pasting into a chat.
//
// Only on the dev server: main.ts loads this behind import.meta.env.DEV, so
// the built game doesn't contain it at all.

import "./debug.css";

import type { RoomId } from "../engine/types";
import { DEATHS, LOST, PLACES } from "./layout";
import type { Player, Walkable } from "./player";

export interface DebugWorld {
  player: Player;
  walkable: Walkable;
  /** The ground's heights, a grid in Blender's axes (y is north). */
  heights: { values: Float32Array; x0: number; y0: number; step: number; nx: number; ny: number };
  /** The walkability map's grid, the same way round. */
  grid: { x0: number; y0: number; step: number; nx: number; ny: number };
  obstacles: Record<string, { box?: number[]; circle?: number[] }>;
  openObstacles: (open: boolean) => void;
  room: () => RoomId;
  name: (id: RoomId) => string;
  /** Draws what you're looking at, and gives back the canvas it's on. */
  picture: () => HTMLCanvasElement;
}

export function debug(world: DebugWorld, onOpen: () => void) {
  const { player } = world;
  const panel = document.createElement("aside");
  panel.className = "debug";
  panel.hidden = true;
  panel.innerHTML = `
    <header><strong>Debug</strong><span>0 to close</span></header>
    <p class="debug-where"></p>
    <label><input type="checkbox" id="debug-fly" /> Fly <kbd>F</kbd> <small>Space up, C down</small></label>
    <label><input type="checkbox" id="debug-ghost" /> Walk through anything <kbd>N</kbd></label>
    <label><input type="checkbox" id="debug-open" /> Open every obstacle <kbd>O</kbd></label>
    <p class="debug-hint">Copy a picture of what you see <kbd>P</kbd></p>
    <label class="debug-speed">Speed <kbd>,</kbd><input type="range" id="debug-speed" min="1" max="10" step="1" value="1" /><kbd>.</kbd><output>1×</output></label>
    <canvas class="debug-map" aria-label="Map: click to jump there"></canvas>
    <div class="debug-places"></div>`;
  document.body.append(panel);

  const where = panel.querySelector<HTMLElement>(".debug-where")!;
  const fly = panel.querySelector<HTMLInputElement>("#debug-fly")!;
  const ghost = panel.querySelector<HTMLInputElement>("#debug-ghost")!;
  const open = panel.querySelector<HTMLInputElement>("#debug-open")!;
  const speed = panel.querySelector<HTMLInputElement>("#debug-speed")!;
  const speedShown = panel.querySelector("output")!;
  fly.addEventListener("change", () => (player.fly = fly.checked));
  ghost.addEventListener("change", () => (player.ghost = ghost.checked));
  open.addEventListener("change", () => world.openObstacles(open.checked));
  speed.addEventListener("input", () => {
    player.boost = Number(speed.value);
    speedShown.textContent = `${speed.value}×`;
  });
  // Keys pressed in the panel move you, not its controls.
  for (const input of [fly, ghost, open, speed]) input.addEventListener("keydown", (event) => event.preventDefault());

  // The same, from the keyboard, with the panel open or not (the mouse is
  // usually busy looking round). By the key's place, whatever the language.
  const note = document.createElement("p");
  note.className = "debug-note";
  note.hidden = true;
  document.body.append(note);
  let hideNote = 0;
  const say = (text: string) => {
    note.textContent = text;
    note.hidden = false;
    clearTimeout(hideNote);
    hideNote = window.setTimeout(() => (note.hidden = true), 1400);
  };
  const flip = (box: HTMLInputElement, on: string, off: string) => {
    box.checked = !box.checked;
    box.dispatchEvent(new Event("change"));
    say(box.checked ? on : off);
  };
  const faster = (by: number) => {
    speed.value = String(Number(speed.value) + by);
    speed.dispatchEvent(new Event("input"));
    say(`Speed ${speed.value}×`);
  };
  addEventListener("keydown", (event) => {
    if (event.repeat || event.ctrlKey || event.metaKey || event.altKey) return;
    if (event.code === "KeyF") flip(fly, "Flying", "Walking");
    else if (event.code === "KeyN") flip(ghost, "Walking through anything", "Bumping into things");
    else if (event.code === "KeyO") flip(open, "Every obstacle open", "Obstacles closed");
    else if (event.code === "Comma") faster(-1);
    else if (event.code === "Period") faster(1);
    else if (event.code === "KeyP") copyPicture();
  });

  // What you're looking at, to the clipboard: with where you are written in
  // the corner, so whoever sees it knows where it was taken.
  function caption() {
    const p = player.position;
    const compass = ["north", "north-west", "west", "south-west", "south", "south-east", "east", "north-east"];
    const turn = (((player.yaw / (Math.PI * 2)) % 1) + 1) % 1;
    const facing = compass[Math.round(turn * 8) % 8];
    const under = player.inside ? (player.under?.indoor ? " (indoors)" : " (underground)") : "";
    return `${world.name(world.room())}${under} · x ${p.x.toFixed(1)} · z ${p.z.toFixed(1)} · height ${p.y.toFixed(1)} · facing ${facing}`;
  }
  function copyPicture() {
    const shot = world.picture();
    const copy = document.createElement("canvas");
    copy.width = shot.width;
    copy.height = shot.height;
    const pen = copy.getContext("2d")!;
    pen.drawImage(shot, 0, 0);
    const size = Math.round(copy.height / 40);
    pen.font = `${size}px system-ui, sans-serif`;
    const text = caption();
    pen.fillStyle = "rgba(0, 0, 0, 0.6)";
    pen.fillRect(0, copy.height - size * 1.8, pen.measureText(text).width + size * 1.2, size * 1.8);
    pen.fillStyle = "#fff";
    pen.fillText(text, size * 0.6, copy.height - size * 0.55);
    // The picture is promised, not handed over, so Safari still counts the
    // key press as what asked for the copy.
    const png = new Promise<Blob>((resolve, reject) =>
      copy.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("no picture"))), "image/png")
    );
    navigator.clipboard
      .write([new ClipboardItem({ "image/png": png })])
      .then(() => say("Picture copied: paste it anywhere"))
      .catch((error: Error) => say(`Couldn't copy the picture (${error.message})`));
  }

  // The map: a pixel for every square metre, north at the top.
  const { grid } = world;
  const canvas = panel.querySelector<HTMLCanvasElement>(".debug-map")!;
  canvas.width = grid.nx;
  canvas.height = grid.ny;
  const pen = canvas.getContext("2d")!;
  const land = drawLand();
  const toMap = (x: number, z: number) => [x - grid.x0, grid.ny - (-z - grid.y0)];
  const fromMap = (mx: number, my: number) => ({ x: grid.x0 + mx, z: -(grid.y0 + grid.ny - my) });
  let hovering: RoomId | undefined;

  function drawLand() {
    const image = pen.createImageData(grid.nx, grid.ny);
    const { values, x0, y0, step, nx } = world.heights;
    for (let j = 0; j < grid.ny; j++) {
      for (let i = 0; i < grid.nx; i++) {
        const x = grid.x0 + (i + 0.5) * grid.step;
        const y = grid.y0 + (j + 0.5) * grid.step;
        const h = values[Math.round((y - y0) / step) * nx + Math.round((x - x0) / step)] ?? 0;
        const standable = world.walkable(x, -y);
        let colour = standable ? [120, 168, 70] : [40, 70, 42];
        if (h < -1) colour = [60, 120, 170];
        else if (h > 6) colour = standable ? [150, 144, 132] : [70, 84, 66];
        const light = 1 + Math.max(-0.2, Math.min(0.25, h / 120));
        const k = ((grid.ny - 1 - j) * grid.nx + i) * 4;
        image.data.set([colour[0] * light, colour[1] * light, colour[2] * light, 255], k);
      }
    }
    return image;
  }

  function drawMap() {
    pen.putImageData(land, 0, 0);
    pen.lineWidth = 2;
    // Obstacles, orange while closed.
    pen.strokeStyle = open.checked ? "rgba(255,170,60,0.35)" : "#ff9a2e";
    for (const { box, circle } of Object.values(world.obstacles)) {
      pen.beginPath();
      if (box) {
        const [mx, my] = toMap(box[0], box[1]);
        pen.rect(mx - box[2], my - box[3], box[2] * 2, box[3] * 2);
      }
      if (circle) {
        const [mx, my] = toMap(circle[0], circle[1]);
        pen.arc(mx, my, circle[2], 0, Math.PI * 2);
      }
      pen.stroke();
    }
    // Ways underground, dotted.
    pen.strokeStyle = "#d9a066";
    pen.lineWidth = 2;
    pen.setLineDash([3, 3]);
    for (const way of player.ways) {
      pen.beginPath();
      way.points.forEach(([x, z], k) => {
        const [mx, my] = toMap(x, z);
        if (k) pen.lineTo(mx, my);
        else pen.moveTo(mx, my);
      });
      pen.stroke();
    }
    pen.setLineDash([]);
    // And the halls they join.
    pen.fillStyle = "rgba(217, 160, 102, 0.35)";
    for (const hall of player.halls.values()) {
      const [mx, my] = toMap(hall.x, hall.z);
      pen.beginPath();
      if (hall.w !== undefined && hall.d !== undefined) pen.rect(mx - hall.w, my - hall.d, hall.w * 2, hall.d * 2);
      else pen.arc(mx, my, hall.r, 0, Math.PI * 2);
      pen.fill();
      pen.stroke();
    }
    pen.textAlign = "center";
    const dot = (x: number, z: number, colour: string, r: number) => {
      const [mx, my] = toMap(x, z);
      pen.fillStyle = colour;
      pen.beginPath();
      pen.arc(mx, my, r, 0, Math.PI * 2);
      pen.fill();
    };
    for (const { x, z } of LOST) dot(x, z, "rgba(255,255,255,0.75)", 8);
    for (const { x, z } of DEATHS) dot(x, z, "#e0614f", 4);
    for (const [id, { x, z }] of PLACES) dot(x, z, id === world.room() ? "#ffd75a" : "#fff7e2", 3.5);
    // Names only for where you are and where the mouse is: they'd crowd otherwise.
    for (const id of new Set([world.room(), hovering].filter(Boolean) as RoomId[])) {
      const { x, z } = PLACES.get(id)!;
      const [mx, my] = toMap(x, z);
      pen.font = "bold 12px system-ui, sans-serif";
      pen.fillStyle = "#fff7e2";
      pen.strokeStyle = "rgba(0,0,0,0.8)";
      pen.lineWidth = 3;
      pen.strokeText(world.name(id), mx, my - 7);
      pen.fillText(world.name(id), mx, my - 7);
    }
    // You, and which way you face.
    const [px, py] = toMap(player.position.x, player.position.z);
    pen.save();
    pen.translate(px, py);
    pen.rotate(-player.yaw);
    pen.fillStyle = "#ff3b6b";
    pen.strokeStyle = "#fff";
    pen.lineWidth = 1.5;
    pen.beginPath();
    pen.moveTo(0, -9);
    pen.lineTo(6, 6);
    pen.lineTo(0, 3);
    pen.lineTo(-6, 6);
    pen.closePath();
    pen.fill();
    pen.stroke();
    pen.restore();
  }

  // Jumping: to the spot clicked (in a cave, if it's over one), or the
  // nearest place you can stand.
  function jump(x: number, z: number, yaw = player.yaw) {
    if (!player.fly && !player.ghost && !world.walkable(x, z) && !player.hallAt(x, z)) {
      search: for (let r = 1; r < 40; r++) {
        for (let a = 0; a < 16; a++) {
          const tx = x + Math.cos((a * Math.PI) / 8) * r;
          const tz = z + Math.sin((a * Math.PI) / 8) * r;
          if (world.walkable(tx, tz)) {
            x = tx;
            z = tz;
            break search;
          }
        }
      }
    }
    const height = player.position.y;
    player.place(x, z, yaw);
    if (!player.fly) return;
    if (player.inside)
      player.fly = fly.checked = false; // into a cave: walk
    else player.position.y = Math.max(height, player.position.y);
  }
  const spotAt = (event: MouseEvent) => {
    const box = canvas.getBoundingClientRect();
    return fromMap(
      ((event.clientX - box.left) / box.width) * grid.nx,
      ((event.clientY - box.top) / box.height) * grid.ny
    );
  };
  canvas.addEventListener("click", (event) => {
    const spot = spotAt(event);
    jump(spot.x, spot.z);
  });
  // The place under the mouse, named on the map.
  canvas.addEventListener("mousemove", (event) => {
    const spot = spotAt(event);
    hovering = [...PLACES].find(([, p]) => Math.hypot(p.x - spot.x, p.z - spot.z) < 14)?.[0];
    drawMap();
  });
  canvas.addEventListener("mouseleave", () => {
    hovering = undefined;
    drawMap();
  });

  const list = panel.querySelector(".debug-places")!;
  for (const [id, { x, z }] of PLACES) {
    const button = document.createElement("button");
    button.textContent = world.name(id);
    // Into the middle of a cave or a room; just south of anywhere else.
    const hall = player.halls.get(id);
    button.addEventListener("click", () => (hall ? jump(hall.x, hall.z, 0) : jump(x, z + 6, 0)));
    list.append(button);
  }

  // Frames a second, counted while the panel is open.
  let frames = 0;
  let since = performance.now();
  let fps = 0;
  function tick() {
    if (panel.hidden) return;
    frames++;
    const now = performance.now();
    if (now - since > 500) {
      fps = Math.round((frames * 1000) / (now - since));
      frames = 0;
      since = now;
      const p = player.position;
      where.textContent = `${world.name(world.room())}${player.inside ? " (underground)" : ""} · x ${p.x.toFixed(0)} · z ${p.z.toFixed(0)} · height ${p.y.toFixed(1)} · ${fps} fps`;
      drawMap();
    }
    requestAnimationFrame(tick);
  }

  addEventListener("keydown", (event) => {
    if (event.code !== "Digit0" && event.code !== "Numpad0") return;
    panel.hidden = !panel.hidden;
    document.body.classList.toggle("debugging", !panel.hidden);
    if (!panel.hidden) {
      onOpen();
      document.exitPointerLock();
      drawMap();
      requestAnimationFrame(tick);
    }
  });
}
