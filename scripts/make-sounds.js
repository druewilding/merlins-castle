// Makes the game's magical sound effects (bell twinkles, harp glissandos and
// soft wooden knocks) from scratch, as WAV files in art/originals/fx/merlin.
// They're all in C major pentatonic, so they sit happily together.
//
//   node scripts/make-sounds.js
//
// Then point src/illustrated/sounds.json at them, e.g.
//   "discover": { "file": "merlin/discover.wav", "volume": 0.7 }

import { mkdirSync, writeFileSync } from "node:fs";

const RATE = 44100;
const OUT = "art/originals/fx/merlin";

// Notes by name, e.g. note("C6").
const SEMITONES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const note = (name) => 440 * 2 ** ((SEMITONES[name[0]] + 12 * (Number(name.slice(1)) + 1) - 69) / 12);
const PENTATONIC = ["C", "D", "E", "G", "A"];

// A seeded random, so the sounds come out the same every time.
let seed = 7;
const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;

// Every note fades out over its last 40ms, so nothing ends with a click.
function release(out) {
  const fade = Math.min(out.length, Math.round(0.04 * RATE));
  for (let i = 0; i < fade; i++) out[out.length - 1 - i] *= i / fade;
  return out;
}

class Track {
  constructor(seconds) {
    this.left = new Float32Array(Math.ceil(seconds * RATE));
    this.right = new Float32Array(this.left.length);
  }

  add(at, samples, pan = 0) {
    const start = Math.round(at * RATE);
    const l = Math.cos(((pan + 1) * Math.PI) / 4);
    const r = Math.sin(((pan + 1) * Math.PI) / 4);
    for (let i = 0; i < samples.length && start + i < this.left.length; i++) {
      this.left[start + i] += samples[i] * l;
      this.right[start + i] += samples[i] * r;
    }
  }
}

// A bell or celesta: a few inharmonic partials with a soft attack, each
// fading at its own rate.
function bell(freq, seconds, amp = 1) {
  const partials = [
    [1, 1, 1],
    [2, 0.45, 0.6],
    [3, 0.2, 0.4],
    [4.2, 0.12, 0.3],
    [5.4, 0.06, 0.2],
  ];
  const out = new Float32Array(Math.ceil(seconds * RATE));
  for (let i = 0; i < out.length; i++) {
    const t = i / RATE;
    const attack = Math.min(1, t / 0.004);
    let v = 0;
    for (const [ratio, a, decay] of partials) {
      v += a * Math.sin(2 * Math.PI * freq * ratio * t) * Math.exp(-t / (seconds * decay * 0.35));
    }
    out[i] = v * attack * amp * 0.5;
  }
  return release(out);
}

// A harp string (Karplus-Strong): a burst of noise in a tuned, softening loop.
function pluck(freq, seconds, amp = 1) {
  const out = new Float32Array(Math.ceil(seconds * RATE));
  const period = Math.round(RATE / freq);
  // Smoothing the starting noise makes a softer, rounder pluck.
  let loop = Float32Array.from({ length: period }, () => random() * 2 - 1);
  for (let pass = 0; pass < 4; pass++) loop = loop.map((v, i) => (v + loop[(i + 1) % period]) / 2);
  for (let i = 0, p = 0; i < out.length; i++) {
    const next = (p + 1) % period;
    const v = loop[p];
    loop[p] = 0.996 * 0.5 * (loop[p] + loop[next]);
    out[i] = v * amp * 0.6 * Math.min(1, i / (0.003 * RATE));
    p = next;
  }
  return release(out);
}

// A soft wooden knock, like a marimba: a low tone with its fourth harmonic,
// fading fast.
function knock(freq, seconds, amp = 1, bend = 0) {
  const out = new Float32Array(Math.ceil(seconds * RATE));
  let phase = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / RATE;
    phase += (2 * Math.PI * freq * (1 - bend * Math.min(1, t / seconds))) / RATE;
    const attack = Math.min(1, t / 0.006);
    const v =
      Math.sin(phase) * Math.exp(-t / (seconds * 0.3)) + 0.25 * Math.sin(4 * phase) * Math.exp(-t / (seconds * 0.08));
    out[i] = v * attack * amp * 0.7;
  }
  return release(out);
}

// A little room around everything (a few comb filters and all-passes).
function reverb(track, wet) {
  for (const channel of [track.left, track.right]) {
    const dry = Float32Array.from(channel);
    const sum = new Float32Array(channel.length);
    const combs = channel === track.left ? [1116, 1188, 1277, 1356] : [1139, 1211, 1300, 1379];
    for (const length of combs) {
      const buffer = new Float32Array(length);
      for (let i = 0, p = 0; i < channel.length; i++, p = (p + 1) % length) {
        const out = buffer[p];
        buffer[p] = dry[i] + out * 0.8;
        sum[i] += out / combs.length;
      }
    }
    for (const length of [556, 441]) {
      const buffer = new Float32Array(length);
      for (let i = 0, p = 0; i < sum.length; i++, p = (p + 1) % length) {
        const delayed = buffer[p];
        buffer[p] = sum[i] + delayed * 0.5;
        sum[i] = delayed - sum[i];
      }
    }
    for (let i = 0; i < channel.length; i++) channel[i] = dry[i] + sum[i] * wet;
  }
}

function save(name, track, wet = 0.25) {
  reverb(track, wet);
  // Fade out the very end, and bring the loudest moment up to just below full.
  const fade = Math.round(0.05 * RATE);
  let peak = 0;
  for (const channel of [track.left, track.right]) {
    for (let i = 0; i < fade; i++) channel[channel.length - 1 - i] *= i / fade;
    for (const v of channel) peak = Math.max(peak, Math.abs(v));
  }
  const gain = 0.9 / peak;
  const frames = track.left.length;
  const wav = Buffer.alloc(44 + frames * 4);
  wav.write("RIFF", 0);
  wav.writeUInt32LE(36 + frames * 4, 4);
  wav.write("WAVEfmt ", 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(2, 22);
  wav.writeUInt32LE(RATE, 24);
  wav.writeUInt32LE(RATE * 4, 28);
  wav.writeUInt16LE(4, 32);
  wav.writeUInt16LE(16, 34);
  wav.write("data", 36);
  wav.writeUInt32LE(frames * 4, 40);
  for (let i = 0; i < frames; i++) {
    wav.writeInt16LE(Math.round(track.left[i] * gain * 32767), 44 + i * 4);
    wav.writeInt16LE(Math.round(track.right[i] * gain * 32767), 46 + i * 4);
  }
  writeFileSync(`${OUT}/${name}.wav`, wav);
  console.log(`  made ${OUT}/${name}.wav`);
}

const sparkle = (track, from, seconds, count, amp) => {
  for (let i = 0; i < count; i++) {
    const name = PENTATONIC[Math.floor(random() * 5)] + (7 + Math.floor(random() * 2));
    track.add(from + random() * seconds, bell(note(name), 0.5, amp * (0.5 + random() * 0.5)), random() * 1.6 - 0.8);
  }
};

mkdirSync(OUT, { recursive: true });

// Finding something new: a quick rising run of bells, then a shimmer of
// sparkles drifting down.
{
  const track = new Track(1.8);
  ["C6", "E6", "G6", "C7", "E7", "G7"].forEach((n, i) =>
    track.add(i * 0.045, bell(note(n), 0.7, 0.8 + i * 0.04), -0.5 + i * 0.2)
  );
  sparkle(track, 0.28, 0.6, 10, 0.35);
  save("discover", track, 0.3);
}

// An object works: a quick harp sweep up, crowned with a bell. Short,
// because you hear it a lot.
{
  const track = new Track(0.95);
  ["C5", "E5", "G5", "A5", "C6", "E6"].forEach((n, i) =>
    track.add(i * 0.03, pluck(note(n), 0.75, 0.8), -0.3 + i * 0.12)
  );
  track.add(0.18, bell(note("G6"), 0.7, 0.45), 0.3);
  sparkle(track, 0.2, 0.2, 3, 0.15);
  save("effect", track, 0.22);
}

// You can't go that way: a gentle wooden "uh-uh", two notes falling.
{
  const track = new Track(0.7);
  track.add(0, knock(note("E4"), 0.3, 0.9));
  track.add(0.16, knock(note("C4"), 0.4, 0.9, 0.03));
  save("no", track, 0.12);
}

// Nothing happens: one soft, low knock that sinks a little.
{
  const track = new Track(0.6);
  track.add(0, knock(note("A3"), 0.45, 1, 0.04));
  save("nothing", track, 0.15);
}

// Victory: a rising fanfare of bells, a big ringing chord over a harp
// sweep, and a long cascade of sparkles.
{
  const track = new Track(4.2);
  ["C5", "E5", "G5", "C6"].forEach((n, i) => track.add(i * 0.14, bell(note(n), 1, 0.9), -0.3 + i * 0.2));
  ["E5", "G5", "C6", "E6"].forEach((n, i) => track.add(0.7 + i * 0.1, bell(note(n), 1, 0.8), 0.3 - i * 0.2));
  for (const [n, pan] of [
    ["C6", -0.4],
    ["E6", 0.4],
    ["G6", -0.2],
    ["C7", 0.2],
  ]) {
    track.add(1.2, bell(note(n), 3, 0.9), pan);
  }
  ["C4", "E4", "G4", "C5", "E5", "G5", "C6", "E6", "G6", "C7"].forEach((n, i) =>
    track.add(1.1 + i * 0.03, pluck(note(n), 2.2, 0.55), -0.6 + i * 0.13)
  );
  sparkle(track, 1.3, 2, 28, 0.32);
  save("victory", track, 0.35);
}
