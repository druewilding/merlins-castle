// Background music for the illustrated version: "The Path of the Goblin King"
// by Kevin MacLeod (incompetech.com), CC BY 4.0. It loops while you play,
// fades out when the game ends, and starts again from the top with each game.

import { soundOn } from "../shared/storage";

const URL = "music/the-path-of-the-goblin-king.mp3";
const VOLUME = 0.45;

export class Music {
  private readonly audio = new Audio();
  private fade = 0;
  private wanted = false; // a game is running that would like music

  constructor() {
    this.audio.loop = true;
    this.audio.preload = "none";
    this.audio.volume = 0;
  }

  // A new game: play from the beginning.
  begin() {
    this.wanted = true;
    if (!soundOn()) return;
    this.audio.currentTime = 0;
    this.play();
  }

  // The game has ended (or you've left it): fade away and stop.
  end(ms = 3000) {
    this.wanted = false;
    this.fadeTo(0, ms);
  }

  // The sound setting changed.
  setOn(on: boolean) {
    if (!on) this.fadeTo(0, 400);
    else if (this.wanted) this.play();
  }

  private play() {
    if (!this.audio.src) this.audio.src = URL;
    this.audio.play().then(
      () => this.fadeTo(VOLUME, 2000),
      // Browsers only play sound after a click or key press (for example when
      // a game is carried over from Classic), so try again on the next one.
      () => this.retryOnInput()
    );
  }

  private retryOnInput() {
    const retry = () => {
      window.removeEventListener("pointerdown", retry, true);
      window.removeEventListener("keydown", retry, true);
      if (this.wanted && soundOn()) this.play();
    };
    window.addEventListener("pointerdown", retry, true);
    window.addEventListener("keydown", retry, true);
  }

  private fadeTo(target: number, ms: number) {
    cancelAnimationFrame(this.fade);
    const from = this.audio.volume;
    const startedAt = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - startedAt) / ms);
      this.audio.volume = from + (target - from) * t;
      if (t < 1) this.fade = requestAnimationFrame(step);
      else if (target === 0) this.audio.pause();
    };
    this.fade = requestAnimationFrame(step);
  }
}
