// Turns the original teletext strings into highlighted phrases for the
// illustrated version.
//
// On the BBC a colour code stood for a space and coloured the rest of the
// screen row. In flowing serif text that would colour half a sentence, so here
// a highlight runs until the next colour code or the end of the phrase (a
// word ending in . , ! or ?): "a{green}grassy{green}bank{white}at" highlights
// "grassy bank".

import type { Colour } from "../engine/teletext";

export interface Segment {
  text: string;
  colour: Colour | null;
}

export function segments(text: string): Segment[] {
  const out: Segment[] = [];
  const push = (part: string, colour: Colour | null) => {
    if (!part) return;
    const last = out.at(-1);
    if (last && last.colour === colour) last.text += part;
    else out.push({ text: part, colour });
  };

  let colour: Colour | null = null;
  for (const part of text.split(/(\{\w+\})/)) {
    const code = part.match(/^\{(\w+)\}$/);
    if (code) {
      colour = code[1] === "white" ? null : (code[1] as Colour);
      push(" ", colour);
      continue;
    }
    let rest = part;
    if (colour) {
      const phrase = rest.match(/^(.*?[.,!?])(?=\s|$)/);
      if (phrase) {
        push(phrase[1], colour);
        rest = rest.slice(phrase[1].length);
        colour = null;
      } else {
        push(rest, colour);
        rest = "";
      }
    }
    push(rest, null);
  }

  // Tidy spaces: no doubles, nothing at the ends, and spaces belong to the
  // plain text rather than starting or ending a highlight.
  const tidy: Segment[] = [];
  for (const seg of out) {
    let text = seg.text.replace(/\s+/g, " ");
    if (seg.colour) {
      const lead = text.match(/^ */)![0];
      const trail = text.match(/ *$/)![0];
      text = text.trim();
      if (lead) pushTo(tidy, " ", null);
      pushTo(tidy, text, seg.colour);
      if (trail) pushTo(tidy, " ", null);
    } else {
      pushTo(tidy, text, null);
    }
  }
  if (tidy.length) {
    tidy[0].text = tidy[0].text.trimStart();
    tidy[tidy.length - 1].text = tidy[tidy.length - 1].text.trimEnd();
  }
  return tidy.filter((seg) => seg.text);
}

function pushTo(list: Segment[], text: string, colour: Colour | null) {
  if (!text) return;
  const last = list.at(-1);
  if (last && last.colour === colour) last.text = (last.text + text).replace(/ {2,}/g, " ");
  else list.push({ text, colour });
}

export const plainText = (text: string) =>
  segments(text)
    .map((seg) => seg.text)
    .join("");
