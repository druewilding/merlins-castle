// The illustrated version: a painted scene, objects you can see and click,
// a storybook text panel, 5 slots for what you carry, and a compass.

import { act, bestPossibleScore, byName, carried, describe, itemsIn, messages, newGame, score } from "../engine/engine";
import type { Command, Direction, GameEvent, GameState, ItemId, World } from "../engine/types";
import { h } from "../shared/dom";
import {
  deleteSave,
  effectsOn,
  listSaves,
  musicOn,
  recordScore,
  saveGame,
  setEffectsOn,
  setMusicOn,
  switchLanguage,
  switchMode,
} from "../shared/storage";
import { LANGUAGE, T } from "../shared/strings";
import { artUrl, preload } from "./art";
import { loadMask, thingAt } from "./hit";
import { itemWidth, placeThings } from "./layout";
import { deathMoment, lostMoment } from "./moments";
import { Music } from "./music";
import { NOTES } from "./notes";
import { Sounds } from "./sounds";
import { plainText, segments } from "./text";
import { Typewriter } from "./typewriter";

const COMPASS: { direction: Direction; label: string }[] = (["north", "west", "east", "south"] as Direction[]).map(
  (direction) => ({ direction, label: T.compass[direction] })
);

const KEY_DIRECTIONS: Record<string, Direction> = {
  ArrowUp: "north",
  ArrowDown: "south",
  ArrowLeft: "west",
  ArrowRight: "east",
  n: "north",
  s: "south",
  e: "east",
  w: "west",
  ø: "east", // Danish: øst and vest
  v: "west",
};

const SLOTS = 5;

type Mode = "title" | "play" | "over";

export class IllustratedApp {
  private mode: Mode = "title";
  private game: GameState | null = null;
  private events: GameEvent[] = [];
  private slotOrder: ItemId[] = [];
  private busy = false;
  private typewriter: Typewriter | null = null;
  private typedFor = "";
  private sceneUrl: string | null | undefined = undefined;
  private ending: string | null = null; // the moment picture after the game ends
  private opened: Direction[] = []; // ways out just opened by using an object
  private dragged = false;
  private readonly music = new Music();
  private readonly sounds = new Sounds();

  private readonly stage = h("div", { class: "stage" });
  private readonly sceneImg = h("img", { class: "scene-img", alt: "" }) as HTMLImageElement;
  private readonly placeholder = h("div", { class: "placeholder" });
  private readonly things = h("div", { class: "things" });
  private readonly fader = h("div", { class: "fader" });
  private readonly topbar = h("header", { class: "topbar" });
  private readonly compass = h("nav", { class: "compass", "aria-label": T.directions });
  private readonly description = h("p", { class: "description" });
  private readonly seeing = h("p", { class: "seeing" });
  private readonly messages = h("div", { class: "messages", "aria-live": "polite" });
  private readonly slots = h("div", { class: "slots", "aria-label": T.carrying });
  private readonly handsActions = h("div", { class: "hands-actions" });
  private readonly panel = h(
    "section",
    { class: "panel" },
    h("div", { class: "words" }, this.description, this.seeing, this.messages),
    this.compass,
    h("div", { class: "hands" }, this.handsActions, this.slots)
  );
  private readonly overlay = h("div", { class: "overlay" });
  private readonly app: HTMLElement;

  constructor(
    root: HTMLElement,
    private world: World,
    handoff: GameState | null = null
  ) {
    this.stage.append(this.sceneImg, this.placeholder, motes(), this.things);
    // The ways out on wide screens sit just above the text panel.
    new ResizeObserver(() =>
      document.documentElement.style.setProperty("--panel-h", `${this.panel.offsetHeight}px`)
    ).observe(this.panel);
    this.things.addEventListener("pointermove", (event) => this.hover(event));
    this.things.addEventListener("pointerleave", () => this.hover(null));
    this.things.addEventListener("click", (event) => this.clickThings(event));
    this.app = h("div", { class: "mc" }, this.stage, this.topbar, this.panel, this.overlay, this.fader);
    root.replaceChildren(this.app);
    document.addEventListener("keydown", (event) => this.onKey(event));
    if (handoff) void this.start(handoff);
    else this.showTitle();
  }

  // ---- Screens --------------------------------------------------------------

  private setMode(mode: Mode) {
    this.mode = mode;
    this.app.className = `mc mc--${mode}`;
  }

  private showTitle() {
    this.setMode("title");
    this.ending = null;
    this.music.end(1200);
    this.music.prepare();
    this.things.replaceChildren();
    void this.setScene(artUrl("scenes", "title"), false);
    const saves = listSaves().length > 0;
    this.overlay.replaceChildren(
      h(
        "div",
        { class: "title-screen" },
        h("h1", {}, T.title),
        h("p", { class: "by" }, T.by(this.world.author)),
        h(
          "div",
          { class: "buttons" },
          h("button", { type: "button", class: "pill", autofocus: true, onclick: () => void this.start() }, T.play),
          saves && h("button", { type: "button", class: "pill quiet", onclick: () => this.showLoad() }, T.loadAGame)
        ),
        h(
          "nav",
          { class: "links" },
          link(T.notes, () => this.showNotes()),
          link(T.about, () => this.showAbout()),
          link(T.language, () => this.showLanguage()),
          link(T.classicVersion, () => switchMode("classic"))
        )
      )
    );
    this.focusAutofocus();
  }

  private async start(state: GameState = newGame(this.world)) {
    this.game = state;
    this.events = [];
    this.ending = null;
    this.slotOrder = carried(this.world, state);
    // Saves from before objects were remembered as found: count what you carry.
    state.found ??= [...this.slotOrder];
    this.typedFor = "";
    this.overlay.replaceChildren();
    this.setMode("play");
    this.music.begin();
    this.sounds.load();
    await this.transition(() => this.render());
  }

  private showOver() {
    const game = this.game!;
    if (game.status !== "won") this.music.end(1500);
    const yours = score(this.world, game);
    const best = recordScore(yours);
    this.setMode("over");
    const heading = game.status === "won" ? T.solved : T.adventureOver;
    this.overlay.replaceChildren(
      h(
        "div",
        { class: "over-screen" },
        h(
          "div",
          { class: "card" },
          h("h2", {}, heading),
          h("p", { class: "yours" }, T.yourScore(yours)),
          h("p", {}, T.bestSoFar(best)),
          h("p", {}, T.bestPossible(bestPossibleScore(this.world))),
          h(
            "div",
            { class: "buttons" },
            h(
              "button",
              { type: "button", class: "pill", autofocus: true, onclick: () => void this.start() },
              T.playAgain
            ),
            listSaves().length > 0 &&
              h("button", { type: "button", class: "pill quiet", onclick: () => this.showLoad() }, T.loadAGame)
          ),
          h(
            "nav",
            { class: "links" },
            link(T.mainMenu, () => this.showTitle())
          )
        )
      )
    );
    this.focusAutofocus();
  }

  // ---- Playing --------------------------------------------------------------

  private command(command: Command): void {
    const before = this.game!;
    const result = act(this.world, before, command);
    this.game = result.state;
    this.events = result.events;
    if (command.type === "go" && result.state.status === "dead") {
      this.ending = deathMoment(before.room, command.direction) ?? null;
    } else if (result.state.status === "lost") {
      this.ending = lostMoment(result.state.room) ?? null;
    } else if (result.state.status === "won") {
      this.ending = "victory";
    }
  }

  private async go(direction: Direction) {
    if (!this.playing() || this.busy) return;
    this.busy = true;
    const room = this.game!.room;
    this.command({ type: "go", direction });
    const moved = this.game!.room !== room;
    if (moved) this.sounds.play("step");
    else if (this.game!.status === "playing") this.sounds.play("blocked");
    if (moved || this.game!.status !== "playing") await this.transition(() => this.render(), moved ? 600 : 1200);
    else this.render();
    this.busy = false;
  }

  private async take(id: ItemId, from?: Element) {
    if (!this.playing() || this.busy) return;
    this.busy = true;
    const fromRect = (from ?? this.things.querySelector(`[data-item="${id}"]`))?.getBoundingClientRect();
    const foundBefore = this.game!.found ?? [];
    this.command({ type: "take", item: id });
    const took = this.game!.itemLocations[id] === "carried";
    const firstTime = took && !foundBefore.includes(id);
    if (!took) this.sounds.play("refuse");
    if (firstTime) this.sounds.play("discover");
    if (took) this.slotOrder.push(id);
    if (took) this.render(id);
    else this.render();
    if (took && fromRect) await this.flyToSlot(id, fromRect, firstTime);
    if (took) this.sounds.play("take");
    this.revealSlot(id);
    this.busy = false;
  }

  private async takeAll() {
    if (!this.playing() || this.busy) return;
    this.busy = true;
    const here = itemsIn(this.world, this.game!, this.game!.room);
    const rects = new Map(
      here.map((id) => [id, this.things.querySelector(`[data-item="${id}"]`)?.getBoundingClientRect()])
    );
    const foundBefore = this.game!.found ?? [];
    this.command({ type: "take", item: "all" });
    const taken = here.filter((id) => this.game!.itemLocations[id] === "carried");
    if (!taken.length) this.sounds.play("refuse");
    if (taken.some((id) => !foundBefore.includes(id))) this.sounds.play("discover");
    this.slotOrder.push(...taken);
    this.render(...taken);
    await Promise.all(
      taken.map((id, i) => {
        const rect = rects.get(id);
        return rect ? delay(i * 70).then(() => this.flyToSlot(id, rect, false)) : Promise.resolve();
      })
    );
    if (taken.length) this.sounds.play("take");
    taken.forEach((id) => this.revealSlot(id));
    this.busy = false;
  }

  private async drop(id: ItemId) {
    if (!this.playing() || this.busy) return;
    this.busy = true;
    const fromRect = this.slotImage(id)?.getBoundingClientRect();
    this.command({ type: "drop", item: id });
    this.slotOrder = this.slotOrder.filter((other) => other !== id);
    this.render();
    await this.flyToScene([id], fromRect ? new Map([[id, fromRect]]) : new Map());
    this.sounds.play("drop");
    await this.afterDrop();
    this.busy = false;
  }

  private async dropAll() {
    if (!this.playing() || this.busy) return;
    this.busy = true;
    const ids = [...this.slotOrder];
    const rects = new Map(ids.map((id) => [id, this.slotImage(id)?.getBoundingClientRect()]));
    this.command({ type: "drop", item: "all" });
    this.slotOrder = [];
    this.render();
    await this.flyToScene(ids, rects);
    this.sounds.play("drop");
    await this.afterDrop();
    this.busy = false;
  }

  // Dropping the last object on the grassy bank wins the game.
  private async afterDrop() {
    if (this.game!.status !== "won") return;
    // The music steps aside so the victory fanfare rings out on its own.
    this.music.end(600);
    this.sounds.play("victory", 300);
    await this.transition(() => this.render(), 1600);
  }

  private async use(id: ItemId) {
    if (!this.playing() || this.busy) return;
    this.command({ type: "use", item: id });
    // Any way out here that needed this object glows, so you know where to go.
    const exits = this.world.rooms[this.game!.room].exits;
    this.opened = COMPASS.map((c) => c.direction).filter((d) => exits[d]?.obstacle?.needs === id);
    // The engine says "Nothing happens." when no way here needs this object.
    this.sounds.play(this.events.at(-1)?.text === messages(this.world).nothingHappens ? "nothing" : "effect");
    this.render();
  }

  private quit() {
    this.closeDialog();
    this.command({ type: "quit" });
    this.showOver();
  }

  private continueAfterEnding() {
    if (this.mode === "play" && this.game && this.game.status !== "playing") this.showOver();
  }

  private playing() {
    return this.mode === "play" && this.game?.status === "playing";
  }

  // ---- Rendering ------------------------------------------------------------

  private render(...arriving: ItemId[]) {
    const game = this.game!;
    const view = describe(this.world, game);
    const ended = game.status !== "playing";

    void this.setScene(this.sceneFor(game), true);
    this.renderTopbar(view.score);
    this.renderThings(ended ? [] : view.itemsHere);
    this.renderText(view.description, ended ? [] : view.itemsHere);
    this.renderCompass(ended ? [] : view.exits);
    this.compass.hidden = ended;
    this.renderSlots(arriving);
    const action = !ended && this.slotOrder.length > 1 ? link(T.dropAll, () => void this.dropAll()) : null;
    this.handsActions.replaceChildren(...(action ? [action] : []));
    if (ended && !this.overlay.querySelector(".curtain")) this.dropCurtain();
    preload(view.exits.map((d) => artUrl("rooms", this.world.rooms[game.room].exits[d]?.to ?? undefined)));
  }

  // When the game ends, a curtain falls over the scene, with the last words
  // and a Continue button in the middle. Winning gets no dark curtain.
  private dropCurtain() {
    const game = this.game!;
    // The music fades with the falling curtain (after a win it has already gone).
    if (game.status !== "won") this.music.end(3000);
    const last = game.status === "dead" ? this.events.at(-1) : undefined;
    this.overlay.replaceChildren(
      h(
        "div",
        { class: game.status === "won" ? "curtain bright" : "curtain" },
        last && h("p", { class: "last-words" }, plainText(last.text)),
        h(
          "button",
          { type: "button", class: "pill", autofocus: true, onclick: () => this.continueAfterEnding() },
          T.continue
        )
      )
    );
    this.focusAutofocus();
  }

  private sceneFor(game: GameState): string | null {
    if (game.status !== "playing") {
      if (this.ending) return artUrl("moments", this.ending) ?? artUrl("rooms", game.room);
      return artUrl("rooms", game.room);
    }
    // On later visits a figure lies sleeping on the grassy bank.
    if (game.room === "grassy-bank" && game.looks > 1) {
      return artUrl("rooms", "grassy-bank-sleeping") ?? artUrl("rooms", "grassy-bank");
    }
    return artUrl("rooms", game.room);
  }

  private renderTopbar(points: number) {
    this.topbar.replaceChildren(
      h("span", { class: "score" }, T.score(points)),
      link(T.save, () => this.showSave()),
      link(T.load, () => this.showLoad()),
      link(T.quit, () => this.showQuit()),
      link(T.sound, () => this.showSound()),
      link(T.language, () => this.showLanguage()),
      link(T.classic, () => switchMode("classic", this.game))
    );
  }

  private renderThings(ids: ItemId[]) {
    const room = this.game!.room;
    const scale = Number(getComputedStyle(this.things).getPropertyValue("--thing-scale")) || 1;
    const spots = placeThings(room, ids, scale);
    const existing = new Map(
      [...this.things.children].map((el) => [(el as HTMLElement).dataset.item!, el as HTMLElement])
    );
    const keep = new Set<HTMLElement>();
    ids.forEach((id, i) => {
      const spot = spots[i];
      let el = existing.get(id);
      if (!el || el.dataset.room !== room) {
        el = this.thingElement(id);
        el.dataset.room = room;
        // Each object breathes at its own pace, so they don't pulse in step.
        el.style.animationDelay = `${-Math.random() * 2.6}s`;
        this.things.append(el);
      }
      el.style.left = `${spot.x}%`;
      el.style.top = `${spot.y}%`;
      el.style.width = `calc(${itemWidth(id, spot)}% * var(--thing-scale))`;
      el.style.zIndex = String(Math.round(spot.y * 10));
      el.classList.toggle("in-use", this.game!.using.includes(id));
      keep.add(el);
    });
    for (const el of existing.values()) if (!keep.has(el)) el.remove();
  }

  // Pointer clicks on objects are worked out here, from the painted pixels,
  // so see-through corners don't get in the way. The buttons themselves still
  // take keyboard clicks.
  private thingUnder(event: MouseEvent) {
    return thingAt([...this.things.children] as HTMLElement[], event.clientX, event.clientY);
  }

  private hover(event: PointerEvent | null) {
    const hot = event && this.thingUnder(event);
    for (const el of this.things.children) el.classList.toggle("hot", el === hot);
    this.things.style.cursor = hot ? "pointer" : "";
    this.things.title = hot?.title ?? "";
  }

  private clickThings(event: MouseEvent) {
    if (event.target !== this.things) return;
    const el = this.thingUnder(event);
    if (el) void this.take(el.dataset.item!, el);
  }

  private thingElement(id: ItemId): HTMLElement {
    const item = this.world.items[id];
    const url = artUrl("items", id);
    if (url) loadMask(url);
    return h(
      "button",
      {
        type: "button",
        class: url ? "thing" : "thing token",
        "data-item": id,
        title: T.take(this.the(id)),
        "aria-label": T.take(`${item.article} ${item.name}`),
        onclick: (event) => void this.take(id, event.currentTarget as Element),
      },
      url ? h("img", { src: url, alt: "", draggable: "false" }) : item.name
    );
  }

  private renderText(description: string, itemsHere: ItemId[]) {
    // Type the description only when it changes (a new room or a new look).
    const key = `${this.game!.room}:${description}`;
    if (key !== this.typedFor) {
      this.typedFor = key;
      this.typewriter?.stop();
      this.typewriter = new Typewriter(this.description, segments(description));
    }

    this.seeing.replaceChildren();
    if (itemsHere.length) {
      const sorted = byName(this.world, itemsHere);
      // Each name stays on the same line as the comma or full stop after it.
      const names = sorted.flatMap((id, i) => {
        const item = this.world.items[id];
        const name = h("button", { type: "button", class: "name", onclick: () => void this.take(id) }, item.name);
        const after = i === sorted.length - 1 ? "." : ",";
        return [`${item.article} `, h("span", { class: "nowrap" }, name, after), i === sorted.length - 1 ? "" : " "];
      });
      this.seeing.append(messages(this.world).youCanSee, ...names);
      if (itemsHere.length > 1)
        this.seeing.append(
          " ",
          link(T.takeAll, () => void this.takeAll())
        );
    }

    this.messages.replaceChildren(
      ...this.events.map((event, i) => {
        // The last message before dying is the fatal one.
        const fatal = this.game!.status === "dead" && i === this.events.length - 1;
        return h("p", { class: `message ${fatal ? "fatal" : event.tone}` }, plainText(event.text));
      })
    );
  }

  private renderCompass(exits: Direction[]) {
    // The glow plays once, so it's not restarted by the next render.
    const opened = this.opened;
    this.opened = [];
    this.compass.replaceChildren(
      ...COMPASS.map(({ direction, label }) =>
        h(
          "button",
          {
            type: "button",
            class: opened.includes(direction) ? `${direction} opened` : direction,
            disabled: !exits.includes(direction),
            "aria-label": T.go[direction],
            title: T.go[direction],
            onclick: () => void this.go(direction),
          },
          label
        )
      )
    );
  }

  private renderSlots(arriving: ItemId[] = []) {
    const using = this.game!.using;
    this.slots.replaceChildren(
      ...Array.from({ length: SLOTS }, (_, i) => {
        const id = this.slotOrder[i];
        if (!id || this.game!.status !== "playing") {
          const content = id ? this.slotContent(id) : null;
          return h(
            "div",
            { class: "slot" },
            h("div", { class: "slot-btn empty" }, content),
            h("span", { class: "drop-btn", "aria-hidden": "true" })
          );
        }
        const slot = h(
          "button",
          {
            type: "button",
            class: `slot-btn${using.includes(id) ? " in-use" : ""}${arriving.includes(id) ? " arriving" : ""}`,
            "data-item": id,
            title: `${T.use(this.the(id))} (${i + 1})`,
            "aria-label": T.use(this.the(id)),
            "aria-pressed": using.includes(id) ? "true" : "false",
            onclick: () => {
              if (this.dragged) this.dragged = false;
              else void this.use(id);
            },
            onpointerdown: (event) => this.startDrag(id, event as PointerEvent),
          },
          this.slotContent(id)
        );
        return h(
          "div",
          { class: "slot" },
          slot,
          h(
            "button",
            {
              type: "button",
              class: "drop-btn",
              onclick: () => void this.drop(id),
              "aria-label": T.drop(this.the(id)),
            },
            T.dropUnder
          )
        );
      })
    );
  }

  private slotContent(id: ItemId) {
    const url = artUrl("items", id);
    return url
      ? h("img", { src: url, alt: "", draggable: "false" })
      : h("span", { class: "slot-name" }, this.world.items[id].name);
  }

  private slotImage(id: ItemId) {
    return this.slots.querySelector(`[data-item="${id}"]`)?.firstElementChild ?? undefined;
  }

  private revealSlot(id: ItemId) {
    this.slots.querySelector(`[data-item="${id}"]`)?.classList.remove("arriving");
  }

  // ---- Scene changes and animation -----------------------------------------

  private async setScene(url: string | null, wait: boolean) {
    if (url === this.sceneUrl) return;
    this.sceneUrl = url;
    this.placeholder.hidden = Boolean(url);
    if (url) {
      this.sceneImg.src = url;
      if (wait) await this.sceneImg.decode().catch(() => undefined);
    } else {
      this.sceneImg.removeAttribute("src");
    }
  }

  // Fade through black, change the scene while it's dark, fade back in.
  private async transition(change: () => void, duration = 600) {
    const half = reducedMotion() ? 0 : duration / 2;
    await this.fader.animate([{ opacity: 0 }, { opacity: 1 }], { duration: half * 0.8, fill: "forwards" }).finished;
    change();
    if (this.sceneUrl) await this.sceneImg.decode().catch(() => undefined);
    await this.fader.animate([{ opacity: 1 }, { opacity: 0 }], { duration: half * 1.2, fill: "forwards" }).finished;
  }

  // The first time an object is picked up in a game, it rises to the middle of
  // the screen, then whooshes into its slot. After that it goes straight there.
  private async flyToSlot(id: ItemId, from: DOMRect, pause: boolean) {
    const target = this.slots.querySelector(`[data-item="${id}"]`)?.getBoundingClientRect();
    if (!target || reducedMotion()) return;
    const flyer = this.flyer(id, from);
    const size = Math.max(from.width, from.height);
    const centreScale = (Math.min(window.innerWidth, window.innerHeight) * 0.32) / size;
    const slotScale = (target.width * 0.8) / size;
    const at = (rect: { x: number; y: number }, scale: number) =>
      `translate(${rect.x - (from.x + from.width / 2)}px, ${rect.y - (from.y + from.height / 2)}px) scale(${scale})`;
    const centre = { x: window.innerWidth / 2, y: window.innerHeight * 0.4 };
    const slot = { x: target.x + target.width / 2, y: target.y + target.height / 2 };
    if (pause) {
      const spotlight = h("div", { class: "spotlight" });
      spotlight.style.setProperty("--y", `${centre.y}px`);
      document.body.insertBefore(spotlight, flyer);
      spotlight.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 420, fill: "forwards" });
      await flyer.animate(
        [
          { transform: at({ x: from.x + from.width / 2, y: from.y + from.height / 2 }, 1) },
          { transform: at(centre, centreScale) },
        ],
        {
          duration: 420,
          easing: "cubic-bezier(.2,.7,.2,1)",
          fill: "forwards",
        }
      ).finished;
      await delay(500);
      spotlight
        .animate([{ opacity: 1 }, { opacity: 0 }], { duration: 380, fill: "forwards" })
        .finished.then(() => spotlight.remove());
      await flyer.animate([{ transform: at(centre, centreScale) }, { transform: at(slot, slotScale), opacity: 0.9 }], {
        duration: 380,
        easing: "cubic-bezier(.5,0,.3,1)",
        fill: "forwards",
      }).finished;
    } else {
      await flyer.animate([{ transform: "none" }, { transform: at(slot, slotScale) }], {
        duration: 280,
        easing: "cubic-bezier(.4,0,.2,1)",
        fill: "forwards",
      }).finished;
    }
    flyer.remove();
  }

  // Dropped objects fly from their slots down to their spots in the scene.
  private async flyToScene(ids: ItemId[], from: Map<ItemId, DOMRect | undefined>) {
    if (reducedMotion()) return;
    await Promise.all(
      ids.map(async (id) => {
        const start = from.get(id);
        const el = this.things.querySelector<HTMLElement>(`[data-item="${id}"]`);
        if (!start || !el) return;
        const end = el.getBoundingClientRect();
        el.style.visibility = "hidden";
        const flyer = this.flyer(id, start);
        const scale = Math.max(end.width, end.height) / Math.max(start.width, start.height);
        const dx = end.x + end.width / 2 - (start.x + start.width / 2);
        const dy = end.y + end.height / 2 - (start.y + start.height / 2);
        await flyer.animate([{ transform: "none" }, { transform: `translate(${dx}px, ${dy}px) scale(${scale})` }], {
          duration: 300,
          easing: "cubic-bezier(.3,0,.2,1)",
          fill: "forwards",
        }).finished;
        flyer.remove();
        el.style.visibility = "";
      })
    );
  }

  private flyer(id: ItemId, rect: DOMRect): HTMLElement {
    const url = artUrl("items", id);
    const flyer = url
      ? h("img", { src: url, alt: "", class: "flyer" })
      : h("div", { class: "flyer token" }, this.world.items[id].name);
    Object.assign(flyer.style, {
      left: `${rect.x}px`,
      top: `${rect.y}px`,
      width: `${rect.width}px`,
      height: url ? `${rect.height}px` : "auto",
    });
    document.body.append(flyer);
    return flyer;
  }

  // Drag an object out of its slot and let go over the scene to drop it.
  private startDrag(id: ItemId, down: PointerEvent) {
    if (!this.playing() || this.busy || down.button !== 0) return;
    const source = down.currentTarget as HTMLElement;
    let ghost: HTMLElement | null = null;
    const move = (event: PointerEvent) => {
      if (!ghost && Math.hypot(event.clientX - down.clientX, event.clientY - down.clientY) < 8) return;
      if (!ghost) {
        const rect = (source.firstElementChild ?? source).getBoundingClientRect();
        ghost = this.flyer(id, rect);
        ghost.classList.add("dragging");
        source.classList.add("arriving");
      }
      ghost.style.transform = `translate(${event.clientX - down.clientX}px, ${event.clientY - down.clientY}px)`;
    };
    const up = (event: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      if (!ghost) return;
      this.dragged = true;
      ghost.remove();
      source.classList.remove("arriving");
      const target = document.elementFromPoint(event.clientX, event.clientY);
      if (target && this.stage.contains(target) && !target.closest(".panel")) void this.drop(id);
      setTimeout(() => (this.dragged = false), 0);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }

  // ---- Dialogs --------------------------------------------------------------

  private dialog(...children: (Node | false | null)[]): HTMLDialogElement {
    this.closeDialog();
    const dialog = h("dialog", { class: "card dialog" }, ...children) as HTMLDialogElement;
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
    return dialog;
  }

  private closeDialog() {
    document.querySelector<HTMLDialogElement>("dialog.dialog")?.close();
  }

  private showQuit() {
    if (!this.playing()) return;
    this.dialog(
      h("h2", {}, T.giveUp),
      h(
        "div",
        { class: "buttons" },
        h("button", { type: "button", class: "pill quiet", onclick: () => this.quit() }, T.yesQuit),
        h("button", { type: "button", class: "pill", autofocus: true, onclick: () => this.closeDialog() }, T.noCarryOn)
      )
    );
  }

  private showSave() {
    if (!this.playing()) return;
    const input = h("input", {
      name: "save-name",
      maxlength: "24",
      autocomplete: "off",
      placeholder: T.namePlaceholder,
      "aria-label": T.nameLabel,
      autofocus: true,
    }) as HTMLInputElement;
    const save = (event: Event) => {
      event.preventDefault();
      const name = input.value.trim();
      if (!name) return;
      const ok = saveGame(name, this.game!);
      this.events = [ok ? { tone: "pass", text: T.savedAs(name) } : { tone: "error", text: T.cantSave }];
      this.closeDialog();
      this.render();
    };
    this.dialog(
      h("h2", {}, T.saveTitle),
      h(
        "form",
        { onsubmit: save },
        input,
        h(
          "div",
          { class: "buttons" },
          h("button", { type: "submit", class: "pill" }, T.save),
          h("button", { type: "button", class: "pill quiet", onclick: () => this.closeDialog() }, T.cancel)
        )
      )
    );
  }

  private showLoad() {
    const saves = listSaves();
    const list = h("ul", { class: "saves" });
    const fill = () =>
      list.replaceChildren(
        ...listSaves().map((slot) =>
          h(
            "li",
            {},
            h(
              "button",
              {
                type: "button",
                class: "save-name",
                onclick: () => {
                  this.closeDialog();
                  void this.start(slot.state);
                },
              },
              slot.name
            ),
            h(
              "span",
              { class: "when" },
              new Date(slot.savedAt).toLocaleDateString(LANGUAGE, { day: "numeric", month: "short" })
            ),
            h(
              "span",
              { class: "actions" },
              link(T.delete, (event) => confirmDelete(event, slot.name))
            )
          )
        )
      );
    // Deleting can't be undone, so it asks first, in place of the Delete link.
    const confirmDelete = (event: Event, name: string) => {
      const actions = (event.currentTarget as HTMLElement).parentElement!;
      const no = link(T.keep, () => fill());
      actions.replaceChildren(
        h("span", { class: "ask" }, T.deleteAsk),
        link(T.yes, () => {
          deleteSave(name);
          fill();
        }),
        no
      );
      no.focus();
    };
    fill();
    // On the score screen, the save list takes the score card's place.
    if (this.mode === "over") this.overlay.hidden = true;
    const dialog = this.dialog(
      h("h2", {}, T.oldPositions),
      saves.length ? list : h("p", {}, T.noSaves),
      this.playing() && saves.length > 0 && h("p", { class: "note" }, T.loadingEnds),
      h(
        "div",
        { class: "buttons" },
        // Focus starts here, not on the first save, whose focus ring looks
        // like a box to type in.
        h(
          "button",
          { type: "button", class: "pill quiet", autofocus: true, onclick: () => this.closeDialog() },
          T.close
        )
      )
    );
    dialog.addEventListener("close", () => (this.overlay.hidden = false));
  }

  // Music and sound effects, each switched on or off on its own.
  private showSound() {
    const toggle = (label: string, isOn: () => boolean, set: (on: boolean) => void) => {
      const choice = (on: boolean) =>
        h(
          "button",
          {
            type: "button",
            class: "choice",
            "aria-pressed": String(isOn() === on),
            onclick: () => {
              set(on);
              buttons.forEach((b, i) => b.setAttribute("aria-pressed", String(isOn() === (i === 0))));
            },
          },
          on ? T.on : T.off
        );
      const buttons = [choice(true), choice(false)];
      return h(
        "li",
        {},
        h("span", { class: "setting" }, label),
        h("span", { class: "choices", role: "group", "aria-label": label }, ...buttons)
      );
    };
    this.dialog(
      h("h2", {}, T.sound),
      h(
        "ul",
        { class: "settings" },
        toggle(T.music, musicOn, (on) => {
          setMusicOn(on);
          this.music.setOn(on);
        }),
        toggle(T.soundEffects, effectsOn, (on) => {
          setEffectsOn(on);
          if (on) this.sounds.play("take");
        })
      ),
      h(
        "div",
        { class: "buttons" },
        h(
          "button",
          { type: "button", class: "pill quiet", autofocus: true, onclick: () => this.closeDialog() },
          T.close
        )
      )
    );
  }

  // English or Danish. Choosing reloads the page, and a game carries on.
  private showLanguage() {
    const choice = (language: "en" | "da", label: string) =>
      h(
        "button",
        {
          type: "button",
          class: "choice",
          lang: language,
          "aria-pressed": String(LANGUAGE === language),
          onclick: () => {
            if (language !== LANGUAGE) switchLanguage(language, this.playing() ? this.game : null);
          },
        },
        label
      );
    this.dialog(
      h("h2", {}, "Language \u00b7 Sprog"),
      h("div", { class: "languages" }, h("span", { class: "choices" }, choice("en", "English"), choice("da", "Dansk"))),
      h(
        "div",
        { class: "buttons" },
        h(
          "button",
          { type: "button", class: "pill quiet", autofocus: true, onclick: () => this.closeDialog() },
          T.close
        )
      )
    );
  }

  private showNotes() {
    this.dialog(
      h("h2", {}, T.notes),
      ...NOTES.map((paragraph) => h("p", {}, paragraph)),
      h(
        "div",
        { class: "buttons" },
        h("button", { type: "button", class: "pill", autofocus: true, onclick: () => this.closeDialog() }, T.close)
      )
    );
  }

  private showAbout() {
    this.dialog(
      h("h2", {}, T.about),
      ...T.aboutText(this.world.author, this.world.year).map((paragraph) => h("p", {}, paragraph)),
      h(
        "p",
        {},
        T.playOriginal,
        h(
          "a",
          { href: "https://bbcmicro.co.uk/game.php?id=2164", target: "_blank", rel: "noopener" },
          "bbcmicro.co.uk"
        ),
        "."
      ),
      h(
        "p",
        { class: "note" },
        T.musicCredit[0],
        h("a", { href: "https://incompetech.com", target: "_blank", rel: "noopener" }, "incompetech.com"),
        T.musicCredit[1],
        h(
          "a",
          { href: "https://creativecommons.org/licenses/by/4.0/", target: "_blank", rel: "noopener" },
          "Creative Commons: By Attribution 4.0"
        ),
        "."
      ),
      h(
        "div",
        { class: "buttons" },
        h("button", { type: "button", class: "pill", autofocus: true, onclick: () => this.closeDialog() }, T.close)
      )
    );
  }

  // ---- Keyboard -------------------------------------------------------------

  private onKey(event: KeyboardEvent) {
    if (document.querySelector("dialog[open]") || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target instanceof HTMLInputElement) return;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;

    if (this.mode !== "play") return;
    if ((key === "Enter" || key === " ") && this.typewriter && !this.typewriter.done) {
      event.preventDefault();
      this.typewriter.finish();
    } else if (KEY_DIRECTIONS[key] && this.playing()) {
      event.preventDefault();
      void this.go(KEY_DIRECTIONS[key]);
    } else if (/^[1-5]$/.test(key) && this.playing()) {
      const id = this.slotOrder[Number(key) - 1];
      if (id) void this.use(id);
    }
  }

  // "the ladder" in English, "stigen" in Danish.
  private the(id: ItemId): string {
    const item = this.world.items[id];
    return T.theItem(item.name, item.definite);
  }

  private focusAutofocus() {
    requestAnimationFrame(() => this.app.querySelector<HTMLElement>("[autofocus]")?.focus());
  }
}

function link(label: string, onClick: (event: Event) => void): HTMLElement {
  return h("button", { type: "button", class: "link", onclick: onClick }, label);
}

function motes(): HTMLElement {
  const layer = h("div", { class: "motes", "aria-hidden": "true" });
  for (let i = 0; i < 16; i++) {
    const mote = h("span", { class: i % 3 ? "mote" : "mote violet" });
    Object.assign(mote.style, {
      left: `${15 + Math.random() * 70}%`,
      top: `${20 + Math.random() * 45}%`,
      animationDelay: `${-Math.random() * 14}s`,
      animationDuration: `${10 + Math.random() * 8}s`,
    });
    layer.append(mote);
  }
  return layer;
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
