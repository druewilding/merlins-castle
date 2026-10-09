// Tiny DOM helpers, plus rendering of wrapped teletext rows.

import { type Colour, wrap } from "../engine/teletext";

type Child = Node | string | false | null | undefined;
type Attrs = Record<string, string | boolean | ((event: Event) => void)>;

export function h(tag: string, attrs: Attrs = {}, ...children: Child[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (typeof value === "function") el.addEventListener(key.replace(/^on/, ""), value);
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false) el.setAttribute(key, value);
  }
  for (const child of children) if (child) el.append(child);
  return el;
}

export function button(label: string, colour: Colour, onClick: () => void, extra: Attrs = {}): HTMLElement {
  return h("button", { type: "button", class: `tt ${colour}`, onclick: onClick, ...extra }, label);
}

// A double-height teletext row of plain children.
export function row(colour: Colour, ...children: Child[]): HTMLElement {
  return h("div", { class: `row double ${colour}` }, h("span", { class: "inner" }, ...children));
}

// Render teletext text as wrapped double-height rows, exactly as PROCprint
// lays it out. `clickable` turns matching words into buttons.
export function teletext(
  text: string,
  colour: Colour = "white",
  clickable: Record<string, () => void> = {}
): HTMLElement[] {
  return wrap(text, colour).map((r) => {
    const inner = h("span", { class: "inner" });
    let current = r.colour;
    let word: { text: string; colour: Colour } | null = null;
    const flush = () => {
      if (!word) return;
      const action = clickable[word.text.replace(/[.,]$/, "")];
      if (action) {
        const name = word.text.replace(/[.,]$/, "");
        inner.append(button(name, word.colour, action, { title: `Take the ${name}` }));
        if (name !== word.text) inner.append(h("span", { class: word.colour }, word.text.slice(name.length)));
      } else {
        inner.append(h("span", { class: word.colour }, word.text));
      }
      word = null;
    };
    for (const cell of r.cells) {
      if ("colour" in cell || cell.char === " ") {
        flush();
        if ("colour" in cell) current = cell.colour;
        inner.append(" ");
      } else if (word && word.colour === current) {
        word.text += cell.char;
      } else {
        flush();
        word = { text: cell.char, colour: current };
      }
    }
    flush();
    return h("div", { class: "row double" }, inner);
  });
}
