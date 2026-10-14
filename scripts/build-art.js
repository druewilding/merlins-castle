// Turns the full-size originals in art/originals into web images in
// public/art, and records which images exist in
// src/illustrated/art-manifest.json so the game can fall back gracefully.
//
//   npm run art:build     (npm run art also does this first)
//
// Scenes, rooms, moments and effects become 1536px-wide WebP. Objects are cropped to
// their outline, padded evenly onto a transparent square, and saved at 384px.
// Music in art/originals/music becomes a 128 kbps MP3 in public/music, and the
// sound effects chosen in src/shared/sounds.json and src/three/sounds.json
// (from art/originals/fx) become MP3s (both need ffmpeg). Only new or changed originals are rebuilt, and web files
// whose original has gone (moved or deleted) are removed.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const KINDS = ["scenes", "rooms", "items", "moments", "effects"];
const ITEM_SIZE = 384;
const ITEM_MARGIN = 0.06;

export async function buildArt({ quiet = false } = {}) {
  // The originals aren't in git, so a fresh checkout (like the GitHub build)
  // has none. Keep the committed images and manifest as they are.
  if (!existsSync("art/originals")) return 0;
  const manifest = {};
  let built = 0;
  for (const kind of KINDS) {
    manifest[kind] = [];
    const dir = `art/originals/${kind}`;
    if (!existsSync(dir)) continue;
    mkdirSync(`public/art/${kind}`, { recursive: true });
    for (const file of readdirSync(dir)
      .filter((f) => f.endsWith(".png"))
      .sort()) {
      const id = file.replace(/\.png$/, "");
      const src = `${dir}/${file}`;
      const out = `public/art/${kind}/${id}.webp`;
      manifest[kind].push(id);
      if (existsSync(out) && statSync(out).mtimeMs >= statSync(src).mtimeMs) continue;
      if (kind === "items") await buildItem(src, out);
      else await sharp(src).resize({ width: 1536, withoutEnlargement: true }).webp({ quality: 80 }).toFile(out);
      built++;
      if (!quiet) console.log(`  built ${out}`);
    }
    for (const file of readdirSync(`public/art/${kind}`).filter((f) => f.endsWith(".webp"))) {
      if (manifest[kind].includes(file.replace(/\.webp$/, ""))) continue;
      rmSync(`public/art/${kind}/${file}`, { force: true });
      if (!quiet) console.log(`  removed public/art/${kind}/${file}`);
    }
  }
  built += buildMusic(quiet);
  built += buildSounds(quiet);
  writeFileSync("src/illustrated/art-manifest.json", JSON.stringify(manifest, null, 2) + "\n");
  if (!quiet) console.log(built ? `${built} file(s) built.` : "All web files are up to date.");
  return built;
}

function mp3(src, out, bitrate) {
  const ffmpeg = spawnSync("ffmpeg", [
    "-loglevel",
    "error",
    "-y",
    "-i",
    src,
    "-codec:a",
    "libmp3lame",
    "-b:a",
    bitrate,
    out,
  ]);
  if (ffmpeg.error || ffmpeg.status !== 0) {
    console.warn(`  couldn't convert ${src}: is ffmpeg installed? (brew install ffmpeg)`);
    return false;
  }
  return true;
}

const newer = (out, ...srcs) => existsSync(out) && srcs.every((src) => statSync(out).mtimeMs >= statSync(src).mtimeMs);

// The sound effects: both versions' in public/fx, and the 3D version's own
// (its footsteps) in src/three/fx, where only the 3D version's build picks
// them up. A sound with takes (a list of files) becomes <name>-0.mp3 and so on.
const SOUND_LISTS = [
  { list: "src/shared/sounds.json", dir: "public/fx" },
  { list: "src/three/sounds.json", dir: "src/three/fx" },
];

function buildSounds(quiet) {
  if (!existsSync("art/originals/fx")) return 0;
  let built = 0;
  for (const { list, dir } of SOUND_LISTS) {
    const sounds = JSON.parse(readFileSync(list, "utf8"));
    mkdirSync(dir, { recursive: true });
    const wanted = new Set();
    for (const [name, { file }] of Object.entries(sounds)) {
      const files = typeof file === "string" ? [file] : file;
      files.forEach((file, k) => {
        const src = `art/originals/fx/${file}`;
        const out = `${dir}/${typeof sounds[name].file === "string" ? name : `${name}-${k}`}.mp3`;
        wanted.add(out);
        if (!existsSync(src)) {
          console.warn(`  sound "${name}": ${src} doesn't exist`);
          return;
        }
        if (newer(out, src, list)) return;
        if (!mp3(src, out, "96k")) return;
        built++;
        if (!quiet) console.log(`  built ${out} (${file})`);
      });
    }
    for (const file of readdirSync(dir).filter((f) => f.endsWith(".mp3"))) {
      if (wanted.has(`${dir}/${file}`)) continue;
      rmSync(`${dir}/${file}`, { force: true }); // (force: the dev server may be building at the same time)
      if (!quiet) console.log(`  removed ${dir}/${file}`);
    }
  }
  return built;
}

function buildMusic(quiet) {
  const dir = "art/originals/music";
  if (!existsSync(dir)) return 0;
  mkdirSync("public/music", { recursive: true });
  const ids = readdirSync(dir).filter((f) => f.endsWith(".mp3"));
  let built = 0;
  for (const file of ids) {
    const src = `${dir}/${file}`;
    const out = `public/music/${file}`;
    if (newer(out, src)) continue;
    if (!mp3(src, out, "128k")) continue;
    built++;
    if (!quiet) console.log(`  built ${out}`);
  }
  for (const file of readdirSync("public/music").filter((f) => f.endsWith(".mp3"))) {
    if (ids.includes(file)) continue;
    rmSync(`public/music/${file}`, { force: true });
    if (!quiet) console.log(`  removed public/music/${file}`);
  }
  return built;
}

// sharp always resizes before extending within one pipeline, so pad first and
// resize in a second pass.
async function buildItem(src, out) {
  const { data, info } = await sharp(src).ensureAlpha().trim().png().toBuffer({ resolveWithObject: true });
  const side = Math.round(Math.max(info.width, info.height) * (1 + ITEM_MARGIN * 2));
  const x = side - info.width;
  const y = side - info.height;
  const padded = await sharp(data)
    .extend({
      top: Math.floor(y / 2),
      bottom: Math.ceil(y / 2),
      left: Math.floor(x / 2),
      right: Math.ceil(x / 2),
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    })
    .png()
    .toBuffer();
  await sharp(padded).resize(ITEM_SIZE, ITEM_SIZE).webp({ quality: 88, alphaQuality: 100 }).toFile(out);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await buildArt();
