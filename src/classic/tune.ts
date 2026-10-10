// The victory tune from the original program (MERLIN2, PROCtune and its DATA
// at lines 17675-17760), played the way the BBC Micro played it: three
// square-wave voices shaped by the program's three ENVELOPEs.
//
// Each chord is three notes and a length. A note is a letter, then "#" (sharp)
// or "&" (flat), then an octave: 2, 3, 5, 6 or 7 (none means the octave
// between 3 and 5). "R" is a rest, but the original's SOUND commands ignore
// the volume it sets, so a "rest" actually replays the last pitch worked out.
// That quirk is part of how the tune sounded, so it's kept.

const DATA = `
F5,F3,R,1,F5,A3,R,1,F5,C,R,1,R,A3,R,1,F5,F3,R,1,R,A3,R,1,F5,C,R,1,R,A3,R,1
F5,F3,R,1,E5,F3,R,1,D5,F3,R,1,C5,F3,R,1,B&,R,R,1,A,R,R,1,G,R,R,1,F,R,R,1
E,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1,G,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1
C5,E3,R,4,B&,R,R,2,R,R,R,2
G5,E3,R,1,G5,B&3,R,1,G5,C,R,1,R,B&3,R,1,G5,E3,R,1,R,B&3,R,1,G5,C,R,1,R,B&3,R,1
G5,E3,R,1,F5,E3,R,1,E5,E3,R,1,D5,E3,R,1,C5,R,R,1,B&,R,R,1,A,R,R,1,G,R,R,1
F,A3,R,1,R,C,R,1,E,G3,R,1,R,C,R,1,F,F3,R,1,R,C,R,1,G,E3,R,1,R,C,R,1
A,F3,R,3,R,R,R,1,C5,R,R,1,A,R,R,1,C5,R,R,1,A,R,R,1
F,A3,R,1,R,C,R,1,R,A3,R,1,R,C,R,1,G,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1
G,B&3,R,1,R,C,R,1,F,A3,R,1,R,C,R,1,F5,R,R,1,C5,R,R,1,F5,R,R,1,C5,R,R,1
A,F3,R,1,R,C,R,1,R,F3,R,1,R,C,R,1,B&,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1
B&,G3,R,1,R,C,R,1,A,F3,R,1,R,C,R,1,A5,R,R,1,F5,R,R,1,A5,R,R,1,F5,R,R,1
D5,B3,F3,1,R,B3,F3,1,D5,B3,F3,1,R,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,E5,B3,F3,1,F5,B3,F3,1
G5,C,E3,1,R,C,E3,1,G5,C,E3,1,R,C,E3,1,A5,C,E3,1,G5,C,E3,1,F5,C,E3,1,E5,C,E3,1
C#5,B3,F3,1,D5,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,C#5,B3,F3,1,D5,B3,F3,1,E5,B3,F3,1,F5,B3,F3,1
A5,C,E3,1,G5,C,E3,1,A5,C,E3,1,G5,C,E3,1,A5,C,E3,1,G5,C,E3,1,F5,C,E3,1,E5,C,E3,1
D5,R,R,2,E5,F3,R,1,F5,F3,R,1,C5,G3,R,1,R,G3,R,1,B,G2,R,1,R,R,R,1
C5,C5,C3,5`;

const LETTERS: Record<string, number> = { C: 101, D: 109, E: 117, F: 121, G: 129, A: 137, B: 145 };
const OCTAVES: Record<string, number> = { "2": -96, "3": -48, "5": 48, "6": 96, "7": 144 };

export interface Chord {
  pitches: [number, number, number]; // BBC pitch numbers: 4 to a semitone, 53 is middle C
  length: number; // in twentieths of a second
}

// PROCtune's loop, step by step, including the pitch that carries over.
export function chords(): Chord[] {
  const items = DATA.trim().split(/[\s,]+/);
  const result: Chord[] = [];
  let p = 0;
  for (let i = 0; i + 3 < items.length; i += 4) {
    const pitches = items.slice(i, i + 3).map((note) => {
      if (LETTERS[note[0]]) p = LETTERS[note[0]];
      if (note[1] === "#") p += 4;
      if (note[1] === "&") p -= 4;
      p += OCTAVES[note.at(-1)!] ?? 0;
      return p;
    }) as Chord["pitches"];
    const dur = Number(items[i + 3]);
    result.push({ pitches, length: dur * 3 });
    if (dur === 5) break;
  }
  return result;
}

// ENVELOPE n, step, (3 pitch changes, 3 counts), attack, decay, sustain,
// release rates, attack level, decay level; amplitude 0-126, steps of 1cs.
interface Envelope {
  attack: number;
  decay: number;
  sustain: number;
  release: number;
  peak: number;
  hold: number;
}
const ENVELOPES: Envelope[] = [
  { attack: 127, decay: -1, sustain: -1, release: -1, peak: 126, hold: 0 }, // 1: a pluck that dies away
  { attack: 127, decay: -2, sustain: -1, release: -15, peak: 126, hold: 50 }, // 2: fades, then sinks
  { attack: 60, decay: 0, sustain: 0, release: -66, peak: 126, hold: 126 }, // 3: a held organ note
];
// SOUND1 uses envelope 3, SOUND2 envelope 2 and SOUND3 envelope 1.
const CHANNEL_ENVELOPES = [ENVELOPES[2], ENVELOPES[1], ENVELOPES[0]];

// The amplitude for each centisecond of a note, then its release.
function amplitudes(env: Envelope, centiseconds: number, release: boolean): number[] {
  const out: number[] = [];
  let amp = 0;
  let phase: "attack" | "decay" | "sustain" = "attack";
  for (let t = 0; t < centiseconds; t++) {
    if (phase === "attack") {
      amp = Math.min(env.peak, amp + env.attack);
      if (amp >= env.peak) phase = "decay";
    } else if (phase === "decay") {
      amp = env.decay < 0 ? Math.max(env.hold, amp + env.decay) : Math.min(env.hold, amp + env.decay);
      if (amp === env.hold) phase = "sustain";
    } else amp = Math.max(0, amp + env.sustain);
    out.push(amp);
  }
  while (release && amp > 0) out.push((amp = Math.max(0, amp + env.release)));
  return out;
}

// The sound chip has 16 volume levels, 2dB apart.
const gainOf = (amp: number) => {
  const level = Math.round(amp / 8.4);
  return level === 0 ? 0 : 10 ** (-(15 - level) / 10);
};
const frequencyOf = (pitch: number) => 261.63 * 2 ** ((pitch - 53) / 48);

let playing: AudioContext | null = null;

// Plays the tune once; returns how long it lasts, in seconds.
export function playTune(volume = 0.12): number {
  stopTune();
  const context = new AudioContext();
  playing = context;
  const master = context.createGain();
  master.gain.value = volume;
  master.connect(context.destination);
  const tune = chords();
  const start = context.currentTime + 0.1;
  let end = start;
  for (let channel = 0; channel < 3; channel++) {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = "square";
    gain.gain.value = 0;
    oscillator.connect(gain).connect(master);
    let time = start;
    tune.forEach((chord, i) => {
      oscillator.frequency.setValueAtTime(frequencyOf(chord.pitches[channel]), time);
      const steps = amplitudes(CHANNEL_ENVELOPES[channel], chord.length * 5, i === tune.length - 1);
      steps.forEach((amp, step) => gain.gain.setValueAtTime(gainOf(amp), time + step / 100));
      time += chord.length / 20;
      end = Math.max(end, time + (steps.length - chord.length * 5) / 100);
    });
    gain.gain.setValueAtTime(0, end);
    oscillator.start(start);
    oscillator.stop(end + 0.05);
  }
  return end - start;
}

export function stopTune() {
  void playing?.close();
  playing = null;
}
