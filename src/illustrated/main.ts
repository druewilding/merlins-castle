import "./style.css";

import type { World } from "../engine/types";
import { takeHandoff } from "../shared/storage";
import { IllustratedApp } from "./app";

export function startIllustrated(root: HTMLElement, world: World): void {
  new IllustratedApp(root, world, takeHandoff());
}
