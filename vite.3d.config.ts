import { defineConfig } from "vite";

// Builds only the 3D version, into dist-3d/, to try it as the built game will
// be (no debug panel). Kept apart from the site's build until the 3D version
// is ready, so nothing of it is deployed, or stored by the offline cache.
//
//   npm run preview:3d   then open http://localhost:4174/3d.html
export default defineConfig({
  base: "./",
  assetsInclude: ["**/*.bin"],
  build: {
    outDir: "dist-3d",
    rollupOptions: { input: "3d.html" },
    chunkSizeWarningLimit: 1000, // three.js is most of it
  },
  preview: { port: 4174 },
});
