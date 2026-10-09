import worldJson from "../data/world.json";
import type { World } from "./engine/types";
import { getMode } from "./shared/storage";

const world = worldJson as unknown as World;
const root = document.getElementById("app")!;

// Only the chosen version (and its styles) is loaded.
if (getMode() === "classic") {
  import("./classic/main").then(({ startClassic }) => startClassic(root, world));
} else {
  import("./illustrated/main").then(({ startIllustrated }) => startIllustrated(root, world));
}
