import "./style.css";

import worldJson from "../data/world.json";
import type { World } from "./engine/types";
import { App } from "./ui/app";

new App(document.getElementById("app")!, worldJson as unknown as World);
