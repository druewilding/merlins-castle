// Short sound effects, for the illustrated version and the 3D one: our own
// magical ones (npm run sounds makes them) and some from the Kenney sound
// packs (CC0). Which file plays for each moment, and how loud, is set in
// src/shared/sounds.json (and the 3D version's own, its footsteps, in
// src/three/sounds.json); npm run art:build turns those files into MP3s.
// A sound can have a few takes (a list of files), and plays one of them,
// never the same one twice running, so footsteps don't sound like a machine.

import { audioContext } from "./audio";
import SHARED from "./sounds.json";
import { effectsOn } from "./storage";

/** How a sounds.json lists a sound: its file (or takes), and how loud. */
type Listed<Name extends string> = Record<Name, { file: string | string[]; volume: number }>;

/** The sound effects both versions have. */
export type Shared = keyof typeof SHARED;

export class Sounds<Name extends string = Shared> {
  private context: AudioContext | null = null;
  private readonly buffers = new Map<Name, Promise<(AudioBuffer | null)[]>>();
  private readonly last = new Map<Name, number>();

  /**
   * The sounds, and where each one's MP3 is: by default public/fx (the shared
   * ones, fx/<name>.mp3, or fx/<name>-<take>.mp3 for one with takes).
   */
  constructor(
    private readonly list = SHARED as Listed<Name>,
    private readonly url = (file: string) => `fx/${file}`
  ) {}

  // Called from a click (Play), when the browser allows audio to start.
  load() {
    this.context = audioContext();
    for (const name of Object.keys(this.list) as Name[]) {
      if (this.buffers.has(name)) continue;
      const context = this.context;
      this.buffers.set(
        name,
        Promise.all(
          mp3s(name, this.list[name].file).map((file) =>
            fetch(this.url(file))
              .then((response) =>
                response.ok ? response.arrayBuffer() : Promise.reject(new Error(response.statusText))
              )
              .then((data) => context.decodeAudioData(data))
              .catch(() => null)
          )
        )
      );
    }
  }

  /**
   * Plays a sound, after delay milliseconds: at volume (times its own), and
   * at rate (1 as it is; a little more is higher and quicker).
   */
  play(name: Name, { delay = 0, volume = 1, rate = 1 } = {}) {
    if (!effectsOn()) return;
    this.load();
    const context = this.context!;
    void this.buffers.get(name)?.then((buffers) => {
      const takes = buffers.flatMap((buffer, k) =>
        buffer && (buffers.length < 2 || k !== this.last.get(name)) ? [k] : []
      );
      if (!takes.length) return;
      const take = takes[Math.floor(Math.random() * takes.length)];
      this.last.set(name, take);
      const source = context.createBufferSource();
      const gain = context.createGain();
      gain.gain.value = this.list[name].volume * volume;
      source.buffer = buffers[take];
      source.playbackRate.value = rate;
      source.connect(gain).connect(context.destination);
      source.start(context.currentTime + delay / 1000);
    });
  }
}

/** The MP3s a sound is made into: <name>.mp3, or <name>-0.mp3, <name>-1.mp3… for one with takes. */
export function mp3s(name: string, file: string | string[]) {
  return typeof file === "string" ? [`${name}.mp3`] : file.map((_, k) => `${name}-${k}.mp3`);
}
