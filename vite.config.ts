import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

import { defineConfig, type Plugin } from "vite";

import { buildArt } from "./scripts/build-art.js";

// While the dev server runs, any PNG (or MP3) saved into art/originals is
// turned into a web file straight away, and the page reloads to show it.
function artWatcher(): Plugin {
  return {
    name: "merlins-castle-art",
    apply: "serve",
    async configureServer(server) {
      await buildArt({ quiet: true });
      server.watcher.add("art/originals");
      server.watcher.add("src/illustrated/sounds.json");
      const rebuild = async (file: string) => {
        if (!/[\\/]art[\\/]originals[\\/].*\.(png|mp3|ogg|wav)$|sounds\.json$/.test(file)) return;
        const built = await buildArt({ quiet: true });
        if (built) {
          server.config.logger.info(`  🖼  ${built} new file(s) added to the game`, { timestamp: true });
          server.ws.send({ type: "full-reload" });
        }
      };
      server.watcher.on("add", rebuild);
      server.watcher.on("change", rebuild);
    },
  };
}

// After a build, writes dist/sw.js: the service worker from
// scripts/service-worker.js, told which files make up the game. The game's
// own files are stored on the first visit; pictures and music as they're met
// (or all at once in the installed app), each with a fingerprint so an update
// only replaces what changed.
function offline(): Plugin {
  let outDir = "dist";
  return {
    name: "merlins-castle-offline",
    apply: "build",
    configResolved(config) {
      outDir = config.build.outDir;
    },
    closeBundle() {
      const files = (dir: string): string[] =>
        readdirSync(dir).flatMap((name) => {
          const path = join(dir, name);
          return statSync(path).isDirectory() ? files(path) : [path];
        });
      const hash = (data: Buffer | string) => createHash("sha256").update(data).digest("hex").slice(0, 12);
      const core: string[] = ["./"];
      const media: Record<string, string> = {};
      let all = "";
      for (const path of files(outDir).sort()) {
        const url = "./" + relative(outDir, path).split("\\").join("/");
        if (url === "./sw.js" || url === "./social.jpg") continue;
        // The 3D version isn't stored for offline play: it's only fetched by
        // those who open 3d.html, and changing it doesn't touch the game's version.
        if (url === "./3d.html" || url.startsWith("./3d/")) continue;
        const fingerprint = hash(readFileSync(path));
        all += url + fingerprint;
        if (/^\.\/(art|music)\//.test(url)) media[url] = fingerprint;
        else core.push(url);
      }
      const worker = readFileSync("scripts/service-worker.js", "utf8")
        .replace("__VERSION__", hash(all))
        .replace("__CORE__", JSON.stringify(core))
        .replace("__MEDIA__", JSON.stringify(media));
      writeFileSync(join(outDir, "sw.js"), worker);
    },
  };
}

// Everything that only the 3D version uses goes in dist/3d/, so it's easy to
// keep apart (see offline() above).
const for3d = (names: readonly string[] = []) => names.some((name) => /(^|\/)(src\/three\/|3d[.-])/.test(name));

// Relative base: the same build works at merlinscastle.net and under a path
// (as it once did at druewilding.com/merlins-castle/).
export default defineConfig({
  base: "./",
  // The 3D land's heights and where you can stand (src/three/models/land.bin).
  assetsInclude: ["**/*.bin"],
  plugins: [artWatcher(), offline()],
  build: {
    // three.js is most of the 3D version's code.
    chunkSizeWarningLimit: 1000,
    rolldownOptions: {
      // The game, and the 3D version in the making (not linked from anywhere yet).
      input: { index: "index.html", "3d": "3d.html" },
      output: {
        entryFileNames: (chunk) => (chunk.name === "3d" ? "3d/[name]-[hash].js" : "assets/[name]-[hash].js"),
        chunkFileNames: (chunk) => (for3d(chunk.moduleIds) ? "3d/[name]-[hash].js" : "assets/[name]-[hash].js"),
        assetFileNames: (asset) =>
          for3d([...asset.names, ...asset.originalFileNames])
            ? "3d/[name]-[hash][extname]"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
});
