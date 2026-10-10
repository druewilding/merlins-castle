import { act, bestPossibleScore, describe, itemsSentence, newGame, score } from "../engine/engine";
import type { Colour } from "../engine/teletext";
import type { Command, Direction, GameEvent, GameState, ItemId, Tone, World } from "../engine/types";
import { h } from "../shared/dom";
import { bestScore, deleteSave, listSaves, recordScore, saveGame, switchMode } from "../shared/storage";
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
};

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

  private bar(label = "Press RETURN", onClick?: () => void): HTMLElement {
    return h(
      "div",
      { class: "bar" },
      onClick ? button(label, "white", onClick, { autofocus: true }) : h("span", { class: "white" }, label)
    );
  }

  private renderTitle(): Node[] {
    const next = () => this.go({ name: "menu" });
    // The original's title picture, drawn tower by tower (see title-picture.ts).
    const picture = h("canvas", { class: "title-picture", role: "img", "aria-label": "A castle of many towers" });
    // The original just waited for a key; this says so, once the castle is up.
    const prompt = this.bar("Press RETURN", next);
    prompt.style.visibility = "hidden";
    this.stopTitle = drawTitle(picture as HTMLCanvasElement, () => (prompt.style.visibility = ""));
    return [
      h(
        "button",
        {
          type: "button",
          class: "title-card",
          onclick: next,
          autofocus: true,
          "aria-label": "Merlin's Castle, by Anita Straker. Begin",
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
      row("blue", "            ", h("span", { class: "blue" }, "Choice Page")),
      row("white", ""),
      row("white", "You can:"),
      option("A", "start a new adventure", () => this.start()),
      option("B", "load your old position", () => this.go({ name: "load" })),
      option("C", "see the notes", () => this.go({ name: "notes", page: 0 })),
      option("D", "about this version", () => this.go({ name: "about" })),
      option("E", "the illustrated version", () => switchMode("illustrated")),
      row("white", ""),
      row("white", "Click or type a letter"),
    ];
  }

  private renderNotes(page: number): Node[] {
    const last = page + 1 === NOTES.length;
    return [
      ...NOTES[page].flatMap((line) => (line === "" ? [row("white", "")] : teletext(line))),
      this.bar(last ? "Back to the menu" : "Press RETURN", () => this.nextNotesPage(page)),
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
      ...teletext(
        `Written by Anita Straker for the BBC Micro in ${this.world.year}, published by ESM. Every room, object and message here comes from her original program.`
      ),
      row("white", ""),
      ...teletext("Remade with love for the web by Drue Wilding, who played it at school and never forgot it."),
      row("white", ""),
      row("white", "Play the original at ", link),
      this.bar("Back to the menu", () => this.go({ name: "menu" })),
    ];
  }

  private renderPlay(screen: Extract<Screen, { name: "play" }>): Node[] {
    const game = this.game!;
    const view = describe(this.world, game);
    const take = (item: ItemId) => () => this.command({ type: "take", item });
    const clickable = Object.fromEntries(view.itemsHere.map((id) => [this.world.items[id].name, take(id)]));
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
      parts.push(this.bar("Press RETURN", () => this.gameOver()));
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
      { class: "compass", "aria-label": "Directions" },
      ...(["north", "west", "east", "south"] as Direction[]).map((direction) =>
        view.exits.includes(direction)
          ? button(ARROWS[direction], "yellow", () => this.command({ type: "go", direction }), {
              class: `tt yellow arrow ${direction}`,
              "aria-label": `Go ${direction}`,
              title: `Go ${direction}`,
            })
          : h("span", { class: `arrow ${direction}` })
      )
    );

    const carrying = h(
      "ul",
      { class: "carrying", "aria-label": "Carrying" },
      ...view.carried.map((id) =>
        h(
          "li",
          {},
          h("span", { class: "red" }, this.world.items[id].name),
          button("use", "cyan", () => this.command({ type: "use", item: id })),
          button("drop", "white", () => this.command({ type: "drop", item: id }))
        )
      )
    );

    const actions = h(
      "div",
      { class: "actions" },
      view.itemsHere.length > 0 && button("Take all", "red", () => this.command({ type: "take", item: "all" })),
      view.carried.length > 0 && button("Drop all", "white", () => this.command({ type: "drop", item: "all" }))
    );

    // The status bar, in the style of the original's blue PROCbar.
    const status = h(
      "div",
      { class: "bar status" },
      h(
        "div",
        {},
        h("span", { class: "yellow" }, `Score ${view.score}`),
        button("Save", "white", () => this.go({ name: "play", events: [], prompt: "save" })),
        button("Quit", "white", () => this.go({ name: "play", events: [], prompt: "quit" })),
        button("Illustrated", "white", () => switchMode("illustrated", this.game))
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
      row("white", "Are you sure you want to quit?"),
      row(
        "white",
        button("Yes - quit", "red", () => this.command({ type: "quit" })),
        "   ",
        button("No - carry on", "green", () => this.go({ name: "play", events: [] }), { autofocus: true })
      )
    );
  }

  private renderSavePrompt(): HTMLElement {
    const input = h("input", {
      class: "tt yellow",
      name: "save-name",
      maxlength: "20",
      autocomplete: "off",
      "aria-label": "Name of your position file",
      autofocus: true,
    }) as HTMLInputElement;
    const save = (event: Event) => {
      event.preventDefault();
      const name = input.value.trim();
      if (!name || !this.game) return;
      const saved = saveGame(name, this.game);
      const text = saved ? `Your position is saved as{yellow}${name}.` : "Sorry, this browser won't let me save.";
      this.go({ name: "play", events: [{ tone: saved ? "pass" : "error", text }] });
    };
    return h(
      "form",
      { class: "prompt", onsubmit: save },
      row("white", "Name of your position file?"),
      row(
        "white",
        input,
        "  ",
        h("button", { type: "submit", class: "tt green" }, "Save"),
        "  ",
        button("Cancel", "white", () => this.go({ name: "play", events: [] }))
      )
    );
  }

  private renderLoad(): Node[] {
    const saves = listSaves();
    const rows: Node[] = [
      row("blue", "         ", h("span", { class: "blue" }, "Your old positions")),
      row("white", ""),
    ];
    if (!saves.length) rows.push(row("white", "There are no saved positions yet."));
    for (const slot of saves) {
      const when = new Date(slot.savedAt).toLocaleDateString(undefined, { day: "numeric", month: "short" });
      rows.push(
        row(
          "white",
          button(slot.name, "yellow", () => this.start(slot.state)),
          h("span", { class: "cyan" }, `  ${when}  `),
          this.deleting !== slot.name &&
            button("delete", "red", () => {
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
            "  Delete it?  ",
            button("yes", "red", () => {
              deleteSave(slot.name);
              this.deleting = null;
              this.render();
            }),
            "  ",
            button("keep", "green", () => {
              this.deleting = null;
              this.render();
            })
          )
        );
    }
    rows.push(this.bar("Back to the menu", () => this.go({ name: "menu" })));
    return rows;
  }

  private renderOver(best: number): Node[] {
    const yours = this.game ? score(this.world, this.game) : 0;
    const centre = (text: string, colour: Colour) =>
      row(colour, " ".repeat(Math.max(0, Math.floor((38 - text.length) / 2))), text);
    return [
      centre("Today's scores", "blue"),
      row("white", ""),
      centre(`Best possible score: ${bestPossibleScore(this.world)}`, "cyan"),
      row("white", ""),
      centre(`Best score so far: ${best}`, "red"),
      row("white", ""),
      centre(`Your score this time: ${yours}`, "blue"),
      this.bar("Press RETURN", () => this.go({ name: "menu" })),
    ];
  }
}
