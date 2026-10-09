import "./style.css";

import type { World } from "../engine/types";
import { takeHandoff } from "../shared/storage";
import { App } from "./app";

export function startClassic(root: HTMLElement, world: World): void {
  new App(root, world, takeHandoff());
}
