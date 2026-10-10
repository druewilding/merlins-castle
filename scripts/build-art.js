// Turns the full-size originals in art/originals into web images in
// public/art, and records which images exist in
// src/illustrated/art-manifest.json so the game can fall back gracefully.
//
//   npm run art:build     (npm run art also does this first)
//
// Scenes, rooms and moments become 1536px-wide WebP. Objects are cropped to
// their outline, padded evenly onto a transparent square, and saved at 384px.
// Music in art/originals/music becomes a 128 kbps MP3 in public/music (this
// needs ffmpeg). Only new or changed originals are rebuilt, and web files
// whose original has gone (moved or deleted) are removed.

import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import sharp from "sharp";

const KINDS = ["scenes", "rooms", "items", "moments"];
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
      rmSync(`public/art/${kind}/${file}`);
      if (!quiet) console.log(`  removed public/art/${kind}/${file}`);
    }
  }
  built += buildMusic(quiet);
  writeFileSync("src/illustrated/art-manifest.json", JSON.stringify(manifest, null, 2) + "\n");
  if (!quiet) console.log(built ? `${built} file(s) built.` : "All web files are up to date.");
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
    if (existsSync(out) && statSync(out).mtimeMs >= statSync(src).mtimeMs) continue;
    const ffmpeg = spawnSync("ffmpeg", [
      "-loglevel",
      "error",
      "-y",
      "-i",
      src,
      "-codec:a",
      "libmp3lame",
      "-b:a",
      "128k",
      out,
    ]);
    if (ffmpeg.error || ffmpeg.status !== 0) {
      console.warn(`  couldn't convert ${src}: is ffmpeg installed? (brew install ffmpeg)`);
      continue;
    }
    built++;
    if (!quiet) console.log(`  built ${out}`);
  }
  for (const file of readdirSync("public/music").filter((f) => f.endsWith(".mp3"))) {
    if (ids.includes(file)) continue;
    rmSync(`public/music/${file}`);
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
