import daJson from "../data/da.json";
import worldJson from "../data/world.json";
import { localise, type WorldText } from "./engine/localise";
import type { World } from "./engine/types";
import { getMode } from "./shared/storage";
import { LANGUAGE, LOCALE, T } from "./shared/strings";

const english = worldJson as unknown as World;
const world = LANGUAGE === "da" ? localise(english, daJson as WorldText) : english;
const root = document.getElementById("app")!;
document.documentElement.lang = LOCALE;
document.title = T.title;

// Only the chosen version (and its styles) is loaded.
if (getMode() === "classic") {
  import("./classic/main").then(({ startClassic }) => startClassic(root, world));
} else {
  import("./illustrated/main").then(({ startIllustrated }) => startIllustrated(root, world));
}

// Works offline once visited (see scripts/service-worker.js). The installed
// app also fetches every picture and the music, ready for a journey.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
  if (matchMedia("(display-mode: standalone)").matches) {
    navigator.serviceWorker.ready.then((registration) => registration.active?.postMessage("cache-everything"));
  }
}
