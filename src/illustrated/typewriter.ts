// Reveals text letter by letter. The full text is always in the page for
// screen readers; the typed copy is hidden from them.

import { h } from "../shared/dom";
import type { Segment } from "./text";

const LETTERS_PER_SECOND = 100;

export class Typewriter {
  private shown = 0;
  private total: number;
  private frame = 0;
  private started = 0;
  private typed: HTMLElement;

  constructor(
    el: HTMLElement,
    private segs: Segment[]
  ) {
    this.total = segs.reduce((sum, seg) => sum + seg.text.length, 0);
    this.typed = h("span", { "aria-hidden": "true" });
    el.replaceChildren(h("span", { class: "sr-only" }, segs.map((s) => s.text).join("")), this.typed);
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) this.finish();
    else {
      this.render(0);
      this.frame = requestAnimationFrame(this.step);
    }
  }

  get done(): boolean {
    return this.shown >= this.total;
  }

  finish(): void {
    cancelAnimationFrame(this.frame);
    this.render(this.total);
  }

  stop(): void {
    cancelAnimationFrame(this.frame);
  }

  private step = (time: number) => {
    this.started ||= time;
    const count = Math.min(this.total, Math.floor(((time - this.started) / 1000) * LETTERS_PER_SECOND));
    if (count !== this.shown) this.render(count);
    if (count < this.total) this.frame = requestAnimationFrame(this.step);
  };

  // Unrevealed letters are laid out but invisible, so lines never jump.
  private render(count: number) {
    this.shown = count;
    let left = count;
    this.typed.replaceChildren(
      ...this.segs.map((seg) => {
        const seen = seg.text.slice(0, Math.max(0, left));
        left -= seg.text.length;
        return h(
          "span",
          { class: seg.colour ? `hl ${seg.colour}` : "" },
          seen,
          seen.length < seg.text.length && h("span", { class: "ghost" }, seg.text.slice(seen.length))
        );
      })
    );
  }
}
