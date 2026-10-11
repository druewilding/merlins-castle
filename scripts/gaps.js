// Finds gaps in the 3D land: places where you can see the sky through
// something that should be solid (a hole in the ground round a building, a
// slit between a tunnel's roof and its walls, a crack under a doorstep).
//
//   npm run gaps                       the whole land
//   npm run gaps -- --near=x,z,r       only within r metres of a spot (x, z as
//                                      in the debug panel), to check a fix
//   npm run gaps -- --look=x,z,eye,yaw,pitch
//                                      just a picture of one view (yaw 0 is
//                                      north, π/2 west), in gaps/look.png
//
// It starts its own dev server, opens the land in a browser with no window,
// paints the sky magenta and looks round from every few metres along every
// tunnel and corridor, in every hall and room, at every place, and round
// every doorway, tunnel mouth and building. For every magenta pixel it
// follows the ray back into the world: if the ray had to go through solid
// earth (or, indoors, a wall or a roof) to reach the sky, that's a gap.
// Seeing the sky out of a tunnel's mouth or a door is fine.
//
// Writes gaps/index.html: the worst first, each with where you'd stand, and
// a picture with the gaps left magenta and the real sky painted blue.

import { mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

import { webkit } from "playwright";
import { createServer } from "vite";

const near = process.argv
  .find((arg) => arg.startsWith("--near="))
  ?.slice(7)
  .split(",")
  .map(Number);
const look = process.argv
  .find((arg) => arg.startsWith("--look="))
  ?.slice(7)
  .split(",")
  .map(Number);
const land = JSON.parse(readFileSync("src/three/models/land.json", "utf8"));
const OUT = "gaps";
const SCAN = { width: 400, height: 250 }; // small, to look from thousands of spots quickly
const PICTURE = { width: 960, height: 600 };
const FEW = 3; // gap pixels in a view worth reporting (fewer is noise)

const server = await createServer({ logLevel: "error", server: { port: 5190 } });
await server.listen();
const browser = await webkit.launch();
try {
  const page = await browser.newPage({ viewport: SCAN });
  page.on("pageerror", (error) => console.error("page:", error.message));
  await page.goto(`${server.resolvedUrls.local[0]}3d?debug&at=0,0,0`);
  await page.waitForFunction(() => window.world?.renderer, null, { timeout: 60_000 });
  await page.evaluate(install, { ways: land.ways, halls: land.halls });

  if (look) {
    const [x, z, eye, yaw, pitch] = look;
    const inside = await page.evaluate(([x, eye, z]) => window.gaps.inside(x, eye, z), [x, eye, z]);
    const view = { name: "look", x, z, eye, yaw, pitch, inside };
    await page.setViewportSize(PICTURE);
    const { png, through } = await page.evaluate(([view, size]) => window.gaps.picture(view, size), [view, PICTURE]);
    mkdirSync(OUT, { recursive: true });
    writeFileSync(`${OUT}/look.png`, Buffer.from(png.split(",")[1], "base64"));
    console.log(`${OUT}/look.png${through ? `: a gap through x ${through[0]}, y ${through[1]}, z ${through[2]}` : ""}`);
    await browser.close();
    await server.close();
    process.exit(0);
  }

  let spots = await page.evaluate(() => window.gaps.spots());
  if (near) spots = spots.filter(({ x, z }) => Math.hypot(x - near[0], z - near[1]) <= near[2]);
  console.log(`Looking round from ${spots.length} spots…`);

  // Every view of every spot, a chunk at a time (so there's news as it goes).
  const found = [];
  const CHUNK = 40;
  for (let k = 0; k < spots.length; k += CHUNK) {
    const chunk = spots.slice(k, k + CHUNK);
    found.push(...(await page.evaluate(([chunk, size]) => window.gaps.scan(chunk, size), [chunk, SCAN])));
    process.stdout.write(`\r  ${Math.min(k + CHUNK, spots.length)} / ${spots.length}, ${found.length} views with gaps`);
  }
  process.stdout.write("\n");

  // The worst view at each spot, and only one spot from each little cluster
  // (one hole is seen from all round it).
  found.sort((a, b) => b.gaps - a.gaps);
  const worst = [];
  for (const view of found) {
    if (view.gaps < FEW) break;
    if (worst.some((other) => Math.hypot(other.x - view.x, other.z - view.z) < 5)) continue;
    worst.push(view);
  }

  rmSync(OUT, { recursive: true, force: true });
  mkdirSync(OUT, { recursive: true });
  await page.setViewportSize(PICTURE);
  for (const [n, view] of worst.slice(0, 60).entries()) {
    const { png } = await page.evaluate(([view, size]) => window.gaps.picture(view, size), [view, PICTURE]);
    writeFileSync(`${OUT}/${n + 1}.png`, Buffer.from(png.split(",")[1], "base64"));
  }
  writeFileSync(`${OUT}/index.html`, report(worst.slice(0, 60), worst.length));

  if (!worst.length) console.log("No gaps found. 🎉");
  else {
    console.log(`${worst.length} places with gaps; the worst:`);
    for (const view of worst.slice(0, 10)) console.log(`  ${describe(view)}  (${view.gaps} pixels)`);
    console.log(`Pictures of each: ${OUT}/index.html`);
  }
} finally {
  await browser.close();
  await server.close();
}

function describe({ name, x, z, eye, yaw, pitch, through }) {
  const compass = ["north", "north-west", "west", "south-west", "south", "south-east", "east", "north-east"];
  const facing = compass[Math.round(((((yaw / (Math.PI * 2)) % 1) + 1) % 1) * 8) % 8];
  const look = pitch < -0.2 ? ", looking down" : pitch > 0.2 ? ", looking up" : "";
  const where = through ? ` · through x ${through[0]}, y ${through[1]}, z ${through[2]}` : "";
  return `${name} · x ${x.toFixed(1)} · z ${z.toFixed(1)} · eye ${eye.toFixed(1)} · facing ${facing}${look}${where}`;
}

function report(views, total) {
  const rows = views
    .map(
      (view, n) => `
    <figure>
      <img src="${n + 1}.png" alt="" width="${PICTURE.width / 2}" height="${PICTURE.height / 2}">
      <figcaption><b>${n + 1}.</b> ${describe(view)} <span>${view.gaps} gap pixels</span></figcaption>
    </figure>`
    )
    .join("");
  return `<!doctype html>
<meta charset="utf-8">
<title>Gaps in the land</title>
<style>
  body { margin: 2rem; font: 15px/1.5 system-ui, sans-serif; background: #1d1a17; color: #f3ead6; }
  main { display: grid; grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); gap: 1.5rem; }
  figure { margin: 0; }
  img { width: 100%; height: auto; border-radius: 6px; }
  span { opacity: 0.6; }
</style>
<h1>Gaps in the land</h1>
<p>${total ? `${total} places, the worst first${total > views.length ? ` (the first ${views.length})` : ""}` : "None found."}.
Magenta: sky seen through something solid. Blue: sky you should see.</p>
<main>${rows}</main>`;
}

// In the page: where to look from, and what's a gap. (Run in the browser, so
// it can't use anything from this file.)
function install({ ways, halls }) {
  const { player, ground, walkable, renderer, scene, places } = window.world;
  const camera = player.camera;
  const gl = renderer.getContext();
  const TALL = 3.2; // a tunnel's height (TUNNEL_TALL in art/blender/land.py)
  const EYE = 1.65; // as in src/three/player.ts
  const allWays = Object.entries(ways).map(([name, way]) => {
    const xs = way.points.map((p) => p[0]);
    const zs = way.points.map((p) => p[1]);
    const m = way.half + 1.5;
    return { name, ...way, box: [Math.min(...xs) - m, Math.max(...xs) + m, Math.min(...zs) - m, Math.max(...zs) + m] };
  });
  const allHalls = Object.entries(halls).map(([name, hall]) => ({ name, ...hall }));

  // Only the world: no sky, no mist, no names, no debug markers; and no
  // drawing every frame behind our backs.
  renderer.setAnimationLoop(null);
  renderer.setClearColor(0xff00ff, 1);
  scene.traverse((thing) => {
    const material = thing.material;
    if (thing.isSprite || material?.transparent || material?.isShaderMaterial) thing.visible = false;
  });

  function nearest(way, x, z) {
    let best = { d: Infinity, floor: 0, beyond: false };
    const last = way.points.length - 2;
    for (let k = 0; k <= last; k++) {
      const [ax, az, af] = way.points[k];
      const [bx, bz, bf] = way.points[k + 1];
      const dx = bx - ax;
      const dz = bz - az;
      const t = ((x - ax) * dx + (z - az) * dz) / (dx * dx + dz * dz);
      const tc = Math.max(0, Math.min(1, t));
      const d = Math.hypot(x - ax - tc * dx, z - az - tc * dz);
      if (d < best.d) best = { d, floor: af + (bf - af) * tc, beyond: (k === 0 && t < 0) || (k === last && t > 1) };
    }
    return best;
  }
  const inHall = (hall, x, z, margin = 0) =>
    hall.w !== undefined
      ? Math.abs(x - hall.x) <= hall.w + margin && Math.abs(z - hall.z) <= hall.d + margin
      : Math.hypot(x - hall.x, z - hall.z) <= hall.r + margin;
  const nearWay = (way, x, z) => x >= way.box[0] && x <= way.box[1] && z >= way.box[2] && z <= way.box[3];

  // What's at a point: open (in a hall, or in a way up to its roof, or up
  // to the sky where its ramp is open, and whether that's roofed), or not.
  function openAt(x, y, z, g) {
    for (const hall of allHalls) {
      if (inHall(hall, x, z) && y >= hall.floor - 0.1 && y <= hall.floor + hall.tall + 0.1) return { roofed: true };
    }
    for (const way of allWays) {
      if (!nearWay(way, x, z)) continue;
      const n = nearest(way, x, z);
      // (A little past its walls: a ray through a pixel at a wall's edge, out
      // of a door, lands just outside it.)
      if (n.beyond || n.d > way.half + 0.3) continue;
      const roofed = way.indoor || n.floor + TALL <= g - 0.4;
      if (y >= n.floor - 0.1 && (!roofed || y <= n.floor + TALL + 0.3)) return { roofed };
    }
    return undefined;
  }
  // Whether it's just out of the end of a way (out of a door, or a tunnel's
  // mouth), not through its side.
  const outOfAnEnd = (x, z) =>
    allWays.some((way) => {
      if (!nearWay(way, x, z)) return false;
      const n = nearest(way, x, z);
      return n.beyond && n.d <= way.half + 0.3;
    });

  // Where the sky seen along a ray went through something solid, if it did. Through
  // the earth, always; and from indoors or underground, out through a wall
  // or a roof (not out of a door, a mouth or the open top of a ramp: from
  // there on, you're outdoors).
  function throughSolid(spot, dx, dy, dz) {
    let indoors = spot.inside;
    let roofed = true;
    for (let t = 0.3; t < 60; t += 0.35) {
      const [x, y, z] = [spot.x + dx * t, spot.eye + dy * t, spot.z + dz * t];
      const g = ground(x, z);
      if (g === undefined || y > g + 15) return false;
      const open = openAt(x, y, z, g);
      if (open) {
        roofed = open.roofed;
        continue;
      }
      if (y < g - 0.3) return [x, y, z];
      if (indoors) {
        if (roofed && !outOfAnEnd(x, z)) return [x, y, z];
        indoors = false;
      }
    }
    return false;
  }

  // Where to look from: [name, x, z, eye height, indoors or underground].
  function spots() {
    const out = [];
    const add = (name, x, z, floor, inside) => out.push({ name, x, z, eye: floor + EYE, inside });
    const onLand = (name, x, z) => {
      if (walkable(x, z) && ground(x, z) !== undefined) add(name, x, z, ground(x, z), false);
    };
    for (const way of allWays) {
      for (let k = 0; k < way.points.length - 1; k++) {
        const [ax, az, af] = way.points[k];
        const [bx, bz, bf] = way.points[k + 1];
        const n = Math.max(1, Math.round(Math.hypot(bx - ax, bz - az) / 3));
        for (let i = 0; i <= n; i++) {
          if (i === n && k < way.points.length - 2) continue; // (the next segment starts there)
          const t = i / n;
          add(way.name, ax + (bx - ax) * t, az + (bz - az) * t, af + (bf - af) * t, true);
        }
      }
      // Round its ends, where they come up onto the land.
      for (const [x, z, floor] of [way.points[0], way.points.at(-1)]) {
        if (Math.abs(floor - (ground(x, z) ?? floor)) > 0.6 || allHalls.some((hall) => inHall(hall, x, z))) continue;
        for (let a = 0; a < 8; a++) onLand(`by ${way.name}`, x + Math.cos(a * 0.785) * 6, z + Math.sin(a * 0.785) * 6);
      }
    }
    for (const hall of allHalls) {
      add(hall.name, hall.x, hall.z, hall.floor, true);
      const r = (hall.w !== undefined ? Math.min(hall.w, hall.d) : hall.r) * 0.6;
      for (let a = 0; a < 4; a++)
        add(hall.name, hall.x + Math.cos(a * 1.57) * r, hall.z + Math.sin(a * 1.57) * r, hall.floor, true);
      if (hall.indoor) {
        // Round the building it's in.
        const out = (hall.w !== undefined ? Math.max(hall.w, hall.d) : hall.r) + 3;
        for (let a = 0; a < 12; a++)
          onLand(`by ${hall.name}`, hall.x + Math.cos(a * 0.524) * out, hall.z + Math.sin(a * 0.524) * out);
      }
    }
    for (const [name, { x, z }] of places) {
      if (name in halls) continue;
      onLand(name, x, z);
      for (let a = 0; a < 4; a++) onLand(name, x + Math.cos(a * 1.57) * 8, z + Math.sin(a * 1.57) * 8);
    }
    return out;
  }

  // Looks one way from a spot, and counts the gap pixels (and gives back
  // which pixels are sky, and which are gaps, if asked).
  function look(spot, yaw, pitch, { width, height }, keep) {
    camera.position.set(spot.x, spot.eye, spot.z);
    camera.rotation.set(pitch, yaw, 0, "YXZ");
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
    camera.updateMatrixWorld();
    renderer.setSize(width, height, false);
    renderer.render(scene, camera);
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    const tan = Math.tan((camera.fov * Math.PI) / 360);
    const [cp, sp, cy, sy] = [Math.cos(pitch), Math.sin(pitch), Math.cos(yaw), Math.sin(yaw)];
    const kinds = keep ? new Uint8Array(width * height) : undefined; // 1 sky, 2 gap
    let gaps = 0;
    let through; // where (one of) the gaps is
    for (let j = 0; j < height; j++) {
      for (let i = 0; i < width; i++) {
        const k = (j * width + i) * 4;
        if (!(pixels[k] > 200 && pixels[k + 1] < 60 && pixels[k + 2] > 200)) continue;
        // The ray through this pixel (j counts up from the bottom).
        const nx = ((2 * (i + 0.5)) / width - 1) * tan * camera.aspect;
        const ny = ((2 * (j + 0.5)) / height - 1) * tan;
        const y1 = ny * cp + sp;
        const z1 = ny * sp - cp;
        let [dx, dy, dz] = [nx * cy + z1 * sy, y1, -nx * sy + z1 * cy];
        const length = Math.hypot(dx, dy, dz);
        [dx, dy, dz] = [dx / length, dy / length, dz / length];
        // (Outdoors, only rays going down can have passed through the ground.)
        const gap = (spot.inside || dy < 0.02) && throughSolid(spot, dx, dy, dz);
        if (gap) {
          gaps++;
          if (gaps % 7 === 1) through = gap.map((v) => Math.round(v * 10) / 10);
        }
        if (kinds) kinds[j * width + i] = gap ? 2 : 1;
      }
    }
    return { gaps, through, pixels, kinds };
  }

  window.gaps = {
    spots,
    inside: (x, y, z) => openAt(x, y, z, ground(x, z) ?? 0)?.roofed ?? false,
    scan(chunk, size) {
      const found = [];
      for (const spot of chunk) {
        const pitches = spot.inside ? [-0.45, -0.1, 0.3] : [-0.45, -0.15];
        for (let a = 0; a < 8; a++) {
          for (const pitch of pitches) {
            const yaw = (a * Math.PI) / 4;
            const { gaps, through } = look(spot, yaw, pitch, size, false);
            if (gaps) found.push({ ...spot, yaw, pitch, gaps, through });
          }
        }
      }
      return found;
    },
    // A picture of one view: the gaps magenta, the sky that should be there blue.
    picture(view, size) {
      const { pixels, kinds, through } = look(view, view.yaw, view.pitch, size, true);
      const canvas = document.createElement("canvas");
      canvas.width = size.width;
      canvas.height = size.height;
      const pen = canvas.getContext("2d");
      const image = pen.createImageData(size.width, size.height);
      for (let j = 0; j < size.height; j++) {
        for (let i = 0; i < size.width; i++) {
          const from = ((size.height - 1 - j) * size.width + i) * 4; // (upside down, from the GPU)
          const to = (j * size.width + i) * 4;
          const kind = kinds[(size.height - 1 - j) * size.width + i];
          const colour =
            kind === 1
              ? [188, 212, 238]
              : kind === 2
                ? [255, 0, 255]
                : [pixels[from], pixels[from + 1], pixels[from + 2]];
          image.data.set([...colour, 255], to);
        }
      }
      pen.putImageData(image, 0, 0);
      return { png: canvas.toDataURL("image/png"), through };
    },
  };
}
