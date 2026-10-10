// Background music for the illustrated version: "The Path of the Goblin King"
// by Kevin MacLeod (incompetech.com), CC BY 4.0. It loops while you play,
// fades out when the game ends, and starts again from the top with each game.
//
// The volume is set through Web Audio rather than on the <audio> element,
// because iPhones and iPads ignore an element's volume, so fades wouldn't work.

import { musicOn } from "../shared/storage";
import { audioContext } from "./audio";

const URL = "music/the-path-of-the-goblin-king.mp3";
const VOLUME = 0.45;

export class Music {
  private readonly audio = new Audio();
  private gain: GainNode | null = null;
  private stopping = 0;
  private wanted = false; // a game is running that would like music

  constructor() {
    this.audio.loop = true;
    this.audio.preload = "none";
  }

  // On the title screen: start downloading, so the music is ready by Play.
  prepare() {
    if (!musicOn() || this.audio.src) return;
    this.audio.preload = "auto";
    this.audio.src = URL;
    // iPhones and iPads don't preload media, so fetch it too: this fills the
    // offline store (or the browser's cache), which the player then reads.
    fetch(URL).catch(() => {});
  }

  // A new game: play from the beginning.
  begin() {
    this.wanted = true;
    if (!musicOn()) return;
    this.audio.currentTime = 0;
    this.play();
  }

  // The game has ended (or you've left it): fade away and stop.
  end(ms = 3000) {
    this.wanted = false;
    this.fadeTo(0, ms);
  }

  // The music setting changed.
  setOn(on: boolean) {
    if (!on) this.fadeTo(0, 400);
    else if (this.wanted) this.play();
  }

  private play() {
    if (!this.audio.src) this.audio.src = URL;
    this.connect();
    this.audio.play().then(
      () => this.fadeTo(VOLUME, 2000),
      // Browsers only play sound after a click or key press (for example when
      // a game is carried over from Classic), so try again on the next one.
      () => this.retryOnInput()
    );
  }

  // Route the music through a gain node, the first time it plays.
  private connect() {
    if (this.gain) return;
    const context = audioContext();
    this.gain = context.createGain();
    this.gain.gain.value = 0;
    context.createMediaElementSource(this.audio).connect(this.gain).connect(context.destination);
  }

  private retryOnInput() {
    const retry = () => {
      window.removeEventListener("pointerdown", retry, true);
      window.removeEventListener("keydown", retry, true);
      if (this.wanted && musicOn()) this.play();
    };
    window.addEventListener("pointerdown", retry, true);
    window.addEventListener("keydown", retry, true);
  }

  private fadeTo(target: number, ms: number) {
    clearTimeout(this.stopping);
    if (!this.gain) {
      if (target === 0) this.audio.pause();
      return;
    }
    const { gain } = this.gain;
    const now = this.gain.context.currentTime;
    gain.cancelScheduledValues(now);
    gain.setValueAtTime(gain.value, now);
    gain.linearRampToValueAtTime(target, now + ms / 1000);
    if (target === 0) this.stopping = window.setTimeout(() => this.audio.pause(), ms);
  }
}
