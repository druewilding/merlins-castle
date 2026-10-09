// Helps make the game's images in ChatGPT, one at a time.
//
//   npm run art              the next image to make: what to attach, what to
//                            paste (copied to the clipboard), where to save it
//   npm run art -- <id>      the same for a particular image, e.g. moat
//   npm run art:status       everything, made (✓) or not (·)
//
// It also builds web versions of any new originals (see build-art.js).

import { spawnSync } from "node:child_process";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { platform } from "node:process";

import { buildArt } from "./build-art.js";

const KINDS = ["scenes", "rooms", "items", "moments"];

// Rooms in the order a player explores them, from the grassy bank outwards.
const ROOM_ORDER = [
  "grassy-bank",
  "dragon-cave",
  "merlins-lair",
  "mountain-path",
  "evergreen-glade",
  "deep-river",
  "old-stone-wall",
  "grassy-bank-sleeping",
  "old-wall",
  "rusty-gate",
  "yellow-flowers",
  "mossy-steps",
  "tower",
  "forest-crossroads",
  "charcoal-hut",
  "forest-edge",
  "forest-witches",
  "cave-entrance",
  "dark-tunnels",
  "beautiful-chamber",
  "mountain",
  "maze",
  "trolls",
  "oak-door",
  "treasure-room",
  "giant",
  "damp-tunnels",
  "river-south-bank",
  "moat",
  "courtyard",
  "coach-house",
  "grand-hall",
  "wizards-kitchen",
  "dungeon",
  "small-room",
];

const REFERENCE = {
  style: (images) =>
    `The ${images} a **style reference only**: match the painting style, brushwork, level of detail and camera angle, but create a completely new scene with the lighting described below. Don't copy the content, layout or colours.`,
  object: (images) =>
    `The ${images} a **style reference only**: match the painting style, brushwork and level of detail, but create a single new object as described below. Don't copy the content.`,
};

const world = JSON.parse(readFileSync("data/world.json", "utf8"));
const style = readFileSync("art/STYLE.md", "utf8");

function readPrompt(kind, id) {
  const text = readFileSync(`art/prompts/${kind}/${id}.md`, "utf8");
  const [, header, body] = text.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/) ?? [];
  if (!header) throw new Error(`${kind}/${id}.md has no header`);
  const field = (name) => header.match(new RegExp(`^${name}: (.*)$`, "m"))?.[1].trim();
  const attach = [...header.matchAll(/^ {2}- (.*)$/gm)].map((m) => m[1].trim());
  const prompt = quoteAfter(body, /^## Prompt$/m);
  if (!prompt) throw new Error(`${kind}/${id}.md has no prompt`);
  return { kind, id, style: field("style"), reference: field("reference"), attach, prompt };
}

// The first blockquote after a heading, unwrapped into plain paragraphs.
function quoteAfter(text, heading) {
  const start = text.search(heading);
  if (start < 0) return "";
  const lines = text.slice(start).split("\n").slice(1);
  const quote = [];
  for (const line of lines) {
    if (line.startsWith(">")) quote.push(line.replace(/^> ?/, ""));
    else if (quote.length) break;
  }
  return unwrap(quote);
}

function unwrap(lines) {
  const out = [];
  for (const line of lines) {
    if (line.trim() === "") out.push("");
    else if (line.startsWith("- ") || out.length === 0 || out.at(-1) === "") out.push(line);
    else out[out.length - 1] += " " + line.trim();
  }
  return out
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const styleBlock = (name) => quoteAfter(style, new RegExp(`^## ${name} style block$`, "m"));

function allImages() {
  const prompts = Object.fromEntries(
    KINDS.map((kind) => [
      kind,
      readdirSync(`art/prompts/${kind}`)
        .filter((file) => file.endsWith(".md") && file !== "README.md")
        .map((file) => file.replace(/\.md$/, "")),
    ])
  );
  const ordered = [...prompts.scenes.map((id) => ["scenes", id])];
  const itemsPlaced = new Set();
  for (const room of ROOM_ORDER) {
    if (prompts.rooms.includes(room)) ordered.push(["rooms", room]);
    // Each object comes just after the room it can first be found in.
    for (const id of prompts.items) {
      if (!itemsPlaced.has(id) && world.items[id]?.startsIn[0] === room) {
        ordered.push(["items", id]);
        itemsPlaced.add(id);
      }
    }
  }
  const listed = new Set(ordered.map(([kind, id]) => `${kind}/${id}`));
  for (const kind of ["rooms", "items", "moments"]) {
    for (const id of prompts[kind].sort()) if (!listed.has(`${kind}/${id}`)) ordered.push([kind, id]);
  }
  return ordered.map(([kind, id]) => ({ kind, id, made: existsSync(`art/originals/${kind}/${id}.png`) }));
}

function status(images) {
  for (const kind of KINDS) {
    const ofKind = images.filter((image) => image.kind === kind);
    console.log(`\n${kind} (${ofKind.filter((i) => i.made).length}/${ofKind.length})`);
    for (const image of ofKind) console.log(`  ${image.made ? "✓" : "·"} ${image.id}`);
  }
  console.log(`\n${images.filter((i) => i.made).length} of ${images.length} images made`);
}

function copy(text) {
  const command = platform === "darwin" ? "pbcopy" : platform === "win32" ? "clip" : "xclip";
  const args = command === "xclip" ? ["-selection", "clipboard"] : [];
  return spawnSync(command, args, { input: text }).status === 0;
}

// Up to two rooms next to this one that are already painted, so things seen
// from both (the old stone wall from the grassy bank) match.
function paintedNeighbours(id) {
  const room = world.rooms[id];
  if (!room) return [];
  const ids = [...new Set(Object.values(room.exits).map((exit) => exit.to))].filter((to) => to && to !== id);
  return ids
    .map((to) => ({ id: to, file: `art/originals/rooms/${to}.png` }))
    .filter((n) => existsSync(n.file) && !n.file.endsWith("/grassy-bank.png"))
    .slice(0, 2);
}

function show(image, images) {
  const prompt = readPrompt(image.kind, image.id);
  const neighbours = image.kind === "rooms" && prompt.reference === "style" ? paintedNeighbours(image.id) : [];
  // Neighbours are attached to be matched, not as style references.
  const style = prompt.attach.filter((file) => existsSync(file) && !neighbours.some((n) => n.file === file));
  const skipped = prompt.attach.filter((file) => !existsSync(file));
  const attach = [...style, ...neighbours.map((n) => n.file)];
  const parts = [];
  if (REFERENCE[prompt.reference]) {
    const which = !neighbours.length
      ? style.length > 1
        ? "attached images are"
        : "attached image is"
      : style.length > 1
        ? `first ${style.length} attached images are`
        : "first attached image is";
    parts.push(REFERENCE[prompt.reference](which));
  }
  if (neighbours.length) {
    parts.push(
      `The last ${neighbours.length > 1 ? `${neighbours.length} images show neighbouring places` : "image shows a neighbouring place"} in the same world (${neighbours.map((n) => n.id).join(", ")}). If this scene's description mentions something that also appears there, such as a wall, a path, a river or a mountain, it must look the same. Don't bring in anything from them that this description doesn't mention.`
    );
  }
  if (prompt.style !== "none") parts.push(styleBlock(prompt.style[0].toUpperCase() + prompt.style.slice(1)));
  parts.push(prompt.prompt);
  const text = parts.join("\n\n");
  const done = images.filter((i) => i.made).length;
  const save = `art/originals/${image.kind}/${image.id}.png`;

  console.log(`\n✨ ${image.kind}/${image.id}   (${done} of ${images.length} made)\n`);
  console.log("1. Start a new chat in ChatGPT.");
  if (attach.length) {
    console.log(`2. Attach ${attach.length === 1 ? "this image" : `these ${attach.length} images, in this order`}:`);
    for (const file of attach) console.log(`     ${file}`);
    if (platform === "darwin" && !process.env.ART_NO_FINDER) spawnSync("open", ["-R", ...attach]);
  } else {
    console.log("2. Don't attach anything.");
  }
  for (const file of skipped) console.log(`     (${file} isn't made yet, so skip it)`);
  const copied = copy(text);
  console.log(`3. Paste this${copied ? " (it's on your clipboard)" : ""}:\n`);
  console.log(text.replace(/^/gm, "     "));
  console.log(`\n4. Save the result as ${save}`);
  if (image.made) console.log("\n   (This one is already made. Saving again replaces it.)");
}

// Turn any newly saved originals into web images first, so they show up in the game.
const built = await buildArt({ quiet: true });
if (built) console.log(`\n🖼  ${built} new image(s) added to the game.`);

const images = allImages();
const arg = process.argv[2];

if (arg === "--list") {
  status(images);
} else if (arg) {
  const image = images.find((i) => i.id === arg || `${i.kind}/${i.id}` === arg);
  if (!image) {
    console.error(`No prompt called "${arg}". Try: npm run art:status`);
    process.exit(1);
  }
  show(image, images);
} else {
  const next = images.find((i) => !i.made);
  if (next) show(next, images);
  else console.log("\n🎉 Every image is made!");
}
