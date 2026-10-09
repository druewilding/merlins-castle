import { defineConfig, type Plugin } from "vite";

import { buildArt } from "./scripts/build-art.js";

// While the dev server runs, any PNG saved into art/originals is turned into a
// web image straight away, and the page reloads to show it.
function artWatcher(): Plugin {
  return {
    name: "merlins-castle-art",
    apply: "serve",
    async configureServer(server) {
      await buildArt({ quiet: true });
      server.watcher.add("art/originals");
      const rebuild = async (file: string) => {
        if (!/[\\/]art[\\/]originals[\\/].*\.png$/.test(file)) return;
        const built = await buildArt({ quiet: true });
        if (built) {
          server.config.logger.info(`  🖼  ${built} new image(s) added to the game`, { timestamp: true });
          server.ws.send({ type: "full-reload" });
        }
      };
      server.watcher.on("add", rebuild);
      server.watcher.on("change", rebuild);
    },
  };
}

// Relative base: the same build works at druewilding.com/merlins-castle/ and
// at the root of a custom domain.
export default defineConfig({
  base: "./",
  plugins: [artWatcher()],
});
