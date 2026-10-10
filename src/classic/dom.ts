// Teletext DOM helpers: buttons, rows and wrapped teletext text.

import { type Colour, wrap } from "../engine/teletext";
import { type Attrs, type Child, h } from "../shared/dom";

export function button(label: string, colour: Colour, onClick: () => void, extra: Attrs = {}): HTMLElement {
  return h("button", { type: "button", class: `tt ${colour}`, onclick: onClick, ...extra }, label);
}

// A double-height teletext row of plain children.
export function row(colour: Colour, ...children: Child[]): HTMLElement {
  return h("div", { class: `row double ${colour}` }, h("span", { class: "inner" }, ...children));
}

// Render teletext text as wrapped double-height rows, exactly as PROCprint
// lays it out. `clickable` turns matching words into buttons, with a title.
export function teletext(
  text: string,
  colour: Colour = "white",
  clickable: Record<string, { onClick: () => void; title: string }> = {}
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
        inner.append(button(name, word.colour, action.onClick, { title: action.title }));
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
