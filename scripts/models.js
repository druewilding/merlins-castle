// Builds the 3D places: runs each script in art/blender/ in Blender, with no
// window, and writes the .glb files the 3D version loads.
//
//   npm run models                          every place
//   npm run models -- grassy-bank           one place
//   npm run models -- grassy-bank --preview also renders a picture of it
//                                           (art/blender/previews/)
//
// Blender is found at its usual place on a Mac, or set BLENDER to its path.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { resolve } from "node:path";

const BLENDER =
  process.env.BLENDER ??
  ["/Applications/Blender.app/Contents/MacOS/Blender", "blender"].find(
    (path) => path === "blender" || existsSync(path)
  );

const args = process.argv.slice(2);
const preview = args.includes("--preview");
const wanted = args.filter((arg) => !arg.startsWith("--"));
const places = readdirSync("art/blender")
  .filter((file) => file.endsWith(".py") && file !== "common.py")
  .map((file) => file.replace(/\.py$/, ""))
  .filter((place) => !wanted.length || wanted.includes(place));

if (!places.length) {
  console.error(`No place called ${wanted.join(", ")} in art/blender/`);
  process.exit(1);
}

mkdirSync("src/three/models", { recursive: true });
if (preview) mkdirSync("art/blender/previews", { recursive: true });

for (const place of places) {
  const out = resolve(`src/three/models/${place}.glb`);
  const extra = preview ? [`--preview=${resolve(`art/blender/previews/${place}.png`)}`] : [];
  console.log(`🏗  ${place}`);
  const started = Date.now();
  const run = spawnSync(
    BLENDER,
    ["--background", "--factory-startup", "--python", `art/blender/${place}.py`, "--", out, ...extra],
    {
      encoding: "utf8",
    }
  );
  const log = `${run.stdout ?? ""}${run.stderr ?? ""}`;
  if (run.status !== 0 || /Traceback|Error:/.test(log)) {
    console.error(log);
    console.error(`✋ ${place} failed`);
    process.exit(1);
  }
  console.log(`   ${out.replace(`${resolve(".")}/`, "")} in ${((Date.now() - started) / 1000).toFixed(0)}s`);
}
