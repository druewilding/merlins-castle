// Short sound effects: our own magical ones (npm run sounds makes them) and
// some from the Kenney sound packs (CC0). Which file plays for each moment,
// and how loud, is set in sounds.json; npm run art:build turns those files
// into MP3s in public/fx.

import { soundOn } from "../shared/storage";
import SOUNDS from "./sounds.json";

export type Sound = keyof typeof SOUNDS;

export class Sounds {
  private context: AudioContext | null = null;
  private readonly buffers = new Map<Sound, Promise<AudioBuffer | null>>();

  // Called from a click (Play), when the browser allows audio to start.
  load() {
    if (!this.context) this.context = new AudioContext();
    void this.context.resume();
    for (const name of Object.keys(SOUNDS) as Sound[]) {
      if (this.buffers.has(name)) continue;
      const context = this.context;
      this.buffers.set(
        name,
        fetch(`fx/${name}.mp3`)
          .then((response) => (response.ok ? response.arrayBuffer() : Promise.reject(new Error(response.statusText))))
          .then((data) => context.decodeAudioData(data))
          .catch(() => null)
      );
    }
  }

  play(name: Sound, delay = 0) {
    if (!soundOn()) return;
    this.load();
    const context = this.context!;
    void this.buffers.get(name)?.then((buffer) => {
      if (!buffer) return;
      const source = context.createBufferSource();
      const gain = context.createGain();
      gain.gain.value = SOUNDS[name].volume;
      source.buffer = buffer;
      source.connect(gain).connect(context.destination);
      source.start(context.currentTime + delay / 1000);
    });
  }
}
