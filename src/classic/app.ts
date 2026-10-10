import { act, bestPossibleScore, describe, itemsSentence, newGame, score } from "../engine/engine";
import type { Colour } from "../engine/teletext";
import type { Command, Direction, GameEvent, GameState, ItemId, Tone, World } from "../engine/types";
import { h } from "../shared/dom";
import { bestScore, deleteSave, listSaves, recordScore, saveGame, switchLanguage, switchMode } from "../shared/storage";
import { LANGUAGE, T } from "../shared/strings";
import { button, row, teletext } from "./dom";
import { NOTES } from "./notes";
import { drawTitle } from "./title-picture";
import { beep, playTune, stopTune } from "./tune";

type Screen =
  | { name: "title" }
  | { name: "menu" }
  | { name: "notes"; page: number }
  | { name: "about" }
  | { name: "play"; events: GameEvent[]; prompt?: "quit" | "save" }
  | { name: "load" }
  | { name: "over"; best: number };

const TONE_COLOURS: Record<Tone, Colour> = {
  error: "red",
  obstacle: "cyan",
  pass: "green",
  item: "red",
  plain: "white",
  victory: "yellow",
};

const ARROWS: Record<Direction, string> = { north: "↑", south: "↓", east: "→", west: "←" };

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

// Centred on the 38-column teletext row.
const centred = (text: string) => " ".repeat(Math.max(0, Math.floor((38 - text.length) / 2)));

export class App {
  private screen: Screen = { name: "title" };
  private stopTitle: (() => void) | null = null;
  private game: GameState | null = null;
  private deleting: string | null = null; // the save waiting for "delete? yes"

  constructor(
    private root: HTMLElement,
    private world: World,
    handoff: GameState | null = null
  ) {
    document.addEventListener("keydown", (event) => this.onKey(event));
    if (handoff) this.start(handoff);
    else this.render();
  }

  private go(screen: Screen) {
    this.screen = screen;
    this.deleting = null;
    this.render();
  }

  // ---- Input --------------------------------------------------------------

  private onKey(event: KeyboardEvent) {
    if (event.target instanceof HTMLInputElement || event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.length === 1 ? event.key.toLowerCase() : event.key;
    const screen = this.screen;
    const enter = key === "Enter" || key === " ";

    if (screen.name === "title" && (enter || key.length === 1)) this.go({ name: "menu" });
    else if (screen.name === "menu") {
      const choice = {
        a: () => this.start(),
        b: () => this.go({ name: "load" }),
        c: () => this.go({ name: "notes", page: 0 }),
        d: () => this.go({ name: "about" }),
        e: () => switchMode("illustrated"),
        f: () => this.otherLanguage(),
      }[key];
      choice?.();
    } else if (screen.name === "notes" && enter) this.nextNotesPage(screen.page);
    else if (
      (screen.name === "about" || screen.name === "over" || screen.name === "load") &&
      (enter || key === "Escape")
    ) {
      this.go({ name: "menu" });
    } else if (screen.name === "play" && this.game) {
      if (this.game.status !== "playing") {
        if (enter) this.gameOver();
      } else if (!screen.prompt && KEY_DIRECTIONS[key]) {
        event.preventDefault();
        this.command({ type: "go", direction: KEY_DIRECTIONS[key] });
      } else if (key === "Escape" && screen.prompt) {
        this.go({ name: "play", events: [] });
      }
    } else return;
    if (enter) event.preventDefault();
  }

  private command(command: Command) {
    if (!this.game) return;
    const result = act(this.world, this.game, command);
    // As in the original, the tune plays when you solve the mystery.
    if (result.state.status === "won" && this.game.status !== "won") playTune();
    else if (result.events.some((event) => event.tone === "error")) beep();
    this.game = result.state;
    this.go({ name: "play", events: result.events });
  }

  private start(state = newGame(this.world)) {
    stopTune();
    this.game = state;
    this.go({ name: "play", events: [] });
  }

  private gameOver() {
    const best = this.game ? recordScore(score(this.world, this.game)) : bestScore();
    this.go({ name: "over", best });
  }

  // English and Danish swap places; a game in progress carries on.
  private otherLanguage() {
    switchLanguage(LANGUAGE === "da" ? "en" : "da", this.game?.status === "playing" ? this.game : null);
  }

  private nextNotesPage(page: number) {
    if (page + 1 < NOTES.length) this.go({ name: "notes", page: page + 1 });
    else this.go({ name: "menu" });
  }

  // ---- Rendering ----------------------------------------------------------

  private render() {
    const screen = this.screen;
    this.stopTitle?.();
    this.stopTitle = null;
    const content = (() => {
      switch (screen.name) {
        case "title":
          return this.renderTitle();
        case "menu":
          return this.renderMenu();
        case "notes":
          return this.renderNotes(screen.page);
        case "about":
          return this.renderAbout();
        case "play":
          return this.renderPlay(screen);
        case "load":
          return this.renderLoad();
        case "over":
          return this.renderOver(screen.best);
      }
    })();
    this.root.replaceChildren(h("main", { class: `screen ${screen.name}` }, ...content));
    this.root.querySelector<HTMLElement>("[autofocus]")?.focus();
  }

  private bar(label = T.pressReturn, onClick?: () => void): HTMLElement {
    return h(
      "div",
      { class: "bar" },
      onClick ? button(label, "white", onClick, { autofocus: true }) : h("span", { class: "white" }, label)
    );
  }

  private renderTitle(): Node[] {
    const next = () => this.go({ name: "menu" });
    // The original's title picture, drawn tower by tower (see title-picture.ts).
    const picture = h("canvas", { class: "title-picture", role: "img", "aria-label": T.titlePicture });
    // The original just waited for a key; this says so, once the castle is up.
    const prompt = this.bar(T.pressReturn, next);
    prompt.style.visibility = "hidden";
    this.stopTitle = drawTitle(
      picture as HTMLCanvasElement,
      () => (prompt.style.visibility = ""),
      undefined,
      T.title,
      T.titleByline
    );
    return [
      h(
        "button",
        {
          type: "button",
          class: "title-card",
          onclick: next,
          autofocus: true,
          "aria-label": T.titleLabel,
        },
        picture
      ),
      prompt,
    ];
  }

  private renderMenu(): Node[] {
    const option = (letter: string, label: string, action: () => void) =>
      row(
        "white",
        "     ",
        h(
          "button",
          { type: "button", class: "tt option", onclick: action },
          h("span", { class: "blue" }, letter),
          "  ",
          label
        )
      );
    return [
      row("blue", centred(T.choicePage), h("span", { class: "blue" }, T.choicePage)),
      row("white", ""),
      row("white", T.youCan),
      option("A", T.menu[0], () => this.start()),
      option("B", T.menu[1], () => this.go({ name: "load" })),
      option("C", T.menu[2], () => this.go({ name: "notes", page: 0 })),
      option("D", T.menu[3], () => this.go({ name: "about" })),
      option("E", T.menu[4], () => switchMode("illustrated")),
      option("F", T.menu[5], () => this.otherLanguage()),
      row("white", ""),
      row("white", T.clickOrType),
    ];
  }

  private renderNotes(page: number): Node[] {
    const last = page + 1 === NOTES.length;
    return [
      ...NOTES[page].flatMap((line) => (line === "" ? [row("white", "")] : teletext(line))),
      this.bar(last ? T.backToMenu : T.pressReturn, () => this.nextNotesPage(page)),
    ];
  }

  private renderAbout(): Node[] {
    const link = h(
      "a",
      { class: "tt cyan", href: "https://bbcmicro.co.uk/game.php?id=2164", target: "_blank", rel: "noopener" },
      "bbcmicro.co.uk"
    );
    return [
      ...teletext(`{yellow}${this.world.title}`),
      ...T.classicAbout(this.world.year).flatMap((paragraph) => [...teletext(paragraph), row("white", "")]),
      row("white", T.playOriginalAt, link),
      this.bar(T.backToMenu, () => this.go({ name: "menu" })),
    ];
  }

  private renderPlay(screen: Extract<Screen, { name: "play" }>): Node[] {
    const game = this.game!;
    const view = describe(this.world, game);
    const take = (item: ItemId) => () => this.command({ type: "take", item });
    const clickable = Object.fromEntries(
      view.itemsHere.map((id) => {
        const item = this.world.items[id];
        return [item.name, { onClick: take(id), title: T.take(T.theItem(item.name, item.definite)) }];
      })
    );
    const playing = game.status === "playing";

    const parts: Node[] = [h("section", { class: "scene", "aria-live": "polite" }, ...teletext(view.description))];
    if (view.itemsHere.length) {
      parts.push(
        h(
          "section",
          { class: "items" },
          ...teletext(itemsSentence(this.world, view.itemsHere), "red", playing ? clickable : {})
        )
      );
    }
    parts.push(
      h(
        "section",
        { class: "messages", "aria-live": "assertive" },
        ...screen.events.flatMap((event) => teletext(event.text, TONE_COLOURS[event.tone]))
      )
    );

    if (!playing) {
      parts.push(this.bar(T.pressReturn, () => this.gameOver()));
    } else if (screen.prompt === "quit") {
      parts.push(this.renderQuitPrompt());
    } else if (screen.prompt === "save") {
      parts.push(this.renderSavePrompt());
    } else {
      parts.push(this.renderControls(view));
    }
    return parts;
  }

  private renderControls(view: ReturnType<typeof describe>): HTMLElement {
    const compass = h(
      "nav",
      { class: "compass", "aria-label": T.directions },
      ...(["north", "west", "east", "south"] as Direction[]).map((direction) =>
        view.exits.includes(direction)
          ? button(ARROWS[direction], "yellow", () => this.command({ type: "go", direction }), {
              class: `tt yellow arrow ${direction}`,
              "aria-label": T.go[direction],
              title: T.go[direction],
            })
          : h("span", { class: `arrow ${direction}` })
      )
    );

    const carrying = h(
      "ul",
      { class: "carrying", "aria-label": T.carrying },
      ...view.carried.map((id) =>
        h(
          "li",
          {},
          h("span", { class: "red" }, this.world.items[id].name),
          button(T.use_, "cyan", () => this.command({ type: "use", item: id })),
          button(T.drop_, "white", () => this.command({ type: "drop", item: id }))
        )
      )
    );

    const actions = h(
      "div",
      { class: "actions" },
      view.itemsHere.length > 0 && button(T.takeAll, "red", () => this.command({ type: "take", item: "all" })),
      view.carried.length > 0 && button(T.dropAll, "white", () => this.command({ type: "drop", item: "all" }))
    );

    // The status bar, in the style of the original's blue PROCbar.
    const status = h(
      "div",
      { class: "bar status" },
      h(
        "div",
        {},
        h("span", { class: "yellow" }, T.score(view.score)),
        button(T.save, "white", () => this.go({ name: "play", events: [], prompt: "save" })),
        button(T.quit, "white", () => this.go({ name: "play", events: [], prompt: "quit" })),
        button(T.illustrated, "white", () => switchMode("illustrated", this.game))
      )
    );

    return h(
      "section",
      { class: "controls" },
      h("div", { class: "hands" }, compass, h("div", {}, carrying, actions)),
      status
    );
  }

  private renderQuitPrompt(): HTMLElement {
    return h(
      "section",
      { class: "prompt" },
      row("white", T.sureQuit),
      row(
        "white",
        button(T.yesQuitTt, "red", () => this.command({ type: "quit" })),
        "   ",
        button(T.noCarryOnTt, "green", () => this.go({ name: "play", events: [] }), { autofocus: true })
      )
    );
  }

  private renderSavePrompt(): HTMLElement {
    const input = h("input", {
      class: "tt yellow",
      name: "save-name",
      maxlength: "20",
      autocomplete: "off",
      "aria-label": T.fileLabel,
      autofocus: true,
    }) as HTMLInputElement;
    const save = (event: Event) => {
      event.preventDefault();
      const name = input.value.trim();
      if (!name || !this.game) return;
      const saved = saveGame(name, this.game);
      const text = saved ? T.savedAsTt(name) : T.cantSave;
      this.go({ name: "play", events: [{ tone: saved ? "pass" : "error", text }] });
    };
    return h(
      "form",
      { class: "prompt", onsubmit: save },
      row("white", T.fileName),
      row(
        "white",
        input,
        "  ",
        h("button", { type: "submit", class: "tt green" }, T.save),
        "  ",
        button(T.cancel, "white", () => this.go({ name: "play", events: [] }))
      )
    );
  }

  private renderLoad(): Node[] {
    const saves = listSaves();
    const rows: Node[] = [
      row("blue", centred(T.oldPositions), h("span", { class: "blue" }, T.oldPositions)),
      row("white", ""),
    ];
    if (!saves.length) rows.push(row("white", T.noSaves));
    for (const slot of saves) {
      const when = new Date(slot.savedAt).toLocaleDateString(LANGUAGE, { day: "numeric", month: "short" });
      rows.push(
        row(
          "white",
          button(slot.name, "yellow", () => this.start(slot.state)),
          h("span", { class: "cyan" }, `  ${when}  `),
          this.deleting !== slot.name &&
            button(T.deleteTt, "red", () => {
              this.deleting = slot.name;
              this.render();
            })
        )
      );
      // Deleting can't be undone, so it asks first, on the line below.
      if (this.deleting === slot.name)
        rows.push(
          row(
            "red",
            `  ${T.deleteItTt}  `,
            button(T.yesTt, "red", () => {
              deleteSave(slot.name);
              this.deleting = null;
              this.render();
            }),
            "  ",
            button(T.keepTt, "green", () => {
              this.deleting = null;
              this.render();
            })
          )
        );
    }
    rows.push(this.bar(T.backToMenu, () => this.go({ name: "menu" })));
    return rows;
  }

  private renderOver(best: number): Node[] {
    const yours = this.game ? score(this.world, this.game) : 0;
    const centre = (text: string, colour: Colour) => row(colour, centred(text), text);
    return [
      centre(T.todaysScores, "blue"),
      row("white", ""),
      centre(T.bestPossible(bestPossibleScore(this.world)), "cyan"),
      row("white", ""),
      centre(T.bestSoFar(best), "red"),
      row("white", ""),
      centre(T.yourScore(yours), "blue"),
      this.bar(T.pressReturn, () => this.go({ name: "menu" })),
    ];
  }
}
