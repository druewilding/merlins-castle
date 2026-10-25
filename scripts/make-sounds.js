// Makes the game's magical sound effects (bell twinkles, harp glissandos and
// soft wooden knocks) from scratch, as WAV files in art/originals/fx/merlin.
// They're written in C major pentatonic and played a fourth lower, in G, the
// key of the background music, so everything sits happily together.
//
//   node scripts/make-sounds.js
//
// Then point src/shared/sounds.json at them, e.g.
//   "discover": { "file": "merlin/discover.wav", "volume": 0.7 }

import { mkdirSync, writeFileSync } from "node:fs";

const RATE = 44100;
const OUT = "art/originals/fx/merlin";

// Notes by name, e.g. note("C6").
const SEMITONES = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
const TRANSPOSE = -5; // C → G
const note = (name) => 440 * 2 ** ((SEMITONES[name[0]] + 12 * (Number(name.slice(1)) + 1) - 69 + TRANSPOSE) / 12);
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

// A harp string: exactly tuned harmonics, the higher ones fading first, which
// gives a soft, round pluck.
function harp(freq, seconds, amp = 1) {
  const out = new Float32Array(Math.ceil(seconds * RATE));
  for (let i = 0; i < out.length; i++) {
    const t = i / RATE;
    const attack = Math.min(1, t / 0.003);
    let v = 0;
    for (let k = 1; k <= 6; k++) {
      v += (Math.sin(2 * Math.PI * freq * k * t) / k ** 1.6) * Math.exp(-t / ((seconds * 0.35) / k ** 0.8));
    }
    out[i] = v * attack * amp * 0.5;
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
    track.add(i * 0.03, harp(note(n), 0.75, 0.8), -0.3 + i * 0.12)
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
    track.add(1.1 + i * 0.03, harp(note(n), 2.2, 0.55), -0.6 + i * 0.13)
  );
  sparkle(track, 1.3, 2, 28, 0.32);
  save("victory", track, 0.35);
}

// Falling down a deep, deep hole: a harp run down from high to low, slowing
// as it goes, and further and further away, in a big echoing space.
{
  const track = new Track(5);
  const run = [];
  for (let octave = 7; octave >= 3; octave--) for (const n of [...PENTATONIC].reverse()) run.push(n + octave);
  let at = 0;
  run.forEach((n, i) => {
    const k = i / (run.length - 1);
    track.add(at, harp(note(n), 1.4, 0.9 * (1 - 0.75 * k)), 0.5 * Math.sin(i * 0.7));
    at += 0.06 + 0.12 * k * k;
  });
  save("falling", track, 0.5);
}

// Noise, through a gentle low-pass filter (each sample `smooth` of the way
// to the next: the smaller, the deeper), as long as `seconds`, shaped by
// envelope(t).
function rush(seconds, smooth, envelope) {
  const out = new Float32Array(Math.round(seconds * RATE));
  let low = 0;
  let lower = 0;
  for (let i = 0; i < out.length; i++) {
    low += (random() * 2 - 1 - low) * smooth;
    lower += (low - lower) * smooth;
    out[i] = lower * envelope(i / RATE);
  }
  return release(out);
}

const rise = (t, from, to) => Math.min(1, Math.max(0, (t - from) / (to - from)));

// The dragon's fire: a great roaring whoosh, swelling quickly and dying
// away, with a crackle in it, deep in its cave.
{
  const track = new Track(2.8);
  const envelope = (t) => rise(t, 0, 0.15) * (1 - rise(t, 1.2, 2.4)) ** 2;
  track.add(0, rush(2.6, 0.035, envelope), -0.2);
  track.add(0.012, rush(2.6, 0.035, envelope), 0.2);
  track.add(
    0,
    rush(2.6, 0.25, (t) => envelope(t) * 0.25),
    0
  );
  const crackle = new Float32Array(Math.round(2.4 * RATE));
  for (let i = 0; i < crackle.length; i++) {
    if (random() < 0.0012) {
      const amp = (0.3 + random() * 0.5) * envelope(i / RATE);
      for (let j = 0; j < 220 && i + j < crackle.length; j++)
        crackle[i + j] += (random() * 2 - 1) * amp * Math.exp(-j / 40);
    }
  }
  track.add(0, release(crackle), 0.1);
  save("roar", track, 0.45);
}

// The fire doused: a long hiss of steam, loud at first, fading slowly.
{
  const track = new Track(3);
  const envelope = (t) => rise(t, 0, 0.05) * Math.exp(-t * 1.2) * (1 - rise(t, 2.4, 2.9));
  const hiss = (pan) => {
    const deep = rush(2.9, 0.5, envelope);
    // (High: the noise less what's deep in it.)
    const high = new Float32Array(deep.length);
    for (let i = 0; i < deep.length; i++) high[i] = (random() * 2 - 1) * envelope(i / RATE) * 0.5 - deep[i] * 0.3;
    track.add(0, release(high), pan);
  };
  hiss(-0.3);
  hiss(0.3);
  save("hiss", track, 0.3);
}

// Dazed, stars circling round your head: little twinkles going round and
// round you (from one ear to the other and back), a tinkling figure up and
// down again, slowing and fading.
{
  const track = new Track(4);
  const figure = ["E7", "G7", "A7", "G7", "E7", "D7"];
  let at = 0.05;
  for (let i = 0; i < 26; i++) {
    const k = i / 25;
    track.add(at, bell(note(figure[i % figure.length]), 0.6, 0.7 * (1 - 0.7 * k)), 0.8 * Math.sin(at * 4));
    at += 0.1 + 0.06 * k;
  }
  save("dizzy", track, 0.35);
}

// The harp played for the trolls: a merry jig in six-eight, each eighth a
// note (or "-", held), a bass note plucked under each beat, and a sweep up
// to finish.
{
  const EIGHTH = 0.15;
  const tune = [
    "E5 G5 A5 G5 E5 D5",
    "C5 D5 E5 D5 C5 A4",
    "C5 E5 G5 A5 G5 E5",
    "G5 - - D5 - -",
    "E5 G5 A5 C6 A5 G5",
    "A5 G5 E5 D5 E5 G5",
    "E5 D5 C5 D5 E5 D5",
    "C5 - - C5 - -",
  ].map((bar) => bar.split(" "));
  const bass = ["C3 G3", "A2 E3", "C3 G3", "G2 D3", "C3 G3", "A2 E3", "G2 D3", "C3 C3"].map((bar) => bar.split(" "));
  const track = new Track(tune.length * 6 * EIGHTH + 2.2);
  tune.forEach((bar, b) => {
    bar.forEach((n, k) => {
      if (n === "-") return;
      let held = 1;
      while (bar[k + held] === "-") held++;
      const at = (b * 6 + k) * EIGHTH;
      track.add(at, harp(note(n), 0.5 + held * EIGHTH, k % 3 === 0 ? 0.85 : 0.65), 0.15);
    });
    bass[b].forEach((n, k) => track.add((b * 6 + k * 3) * EIGHTH, harp(note(n), 0.9, 0.7), -0.25));
  });
  const end = tune.length * 6 * EIGHTH;
  ["C5", "E5", "G5", "A5", "C6", "E6", "G6", "C7"].forEach((n, i) =>
    track.add(end + i * 0.035, harp(note(n), 1.6, 0.6), -0.4 + i * 0.11)
  );
  save("jig", track, 0.28);
}

// The trolls' spell: a swirl of twinkles going round you, up and back down
// again, a little eerie (but kindly), with a shimmer of sparkles.
{
  const track = new Track(2.2);
  ["C6", "E6", "G6", "A6", "C7", "A6", "G6", "E6", "D6", "C6"].forEach((n, i) =>
    track.add(i * 0.09, bell(note(n), 0.8, 0.6), 0.8 * Math.sin(i * 0.9))
  );
  sparkle(track, 0.2, 1, 8, 0.25);
  save("spell", track, 0.4);
}

// The giant eating his cake: a big, soft, crumbly munch, a chomp and a
// chew or two, deep (he's huge).
{
  const track = new Track(0.75);
  [
    [0, 0.22, 1],
    [0.26, 0.16, 0.6],
    [0.46, 0.14, 0.45],
  ].forEach(([at, long, amp]) => {
    const envelope = (t) => amp * rise(t, 0, 0.012) * Math.exp(-t / (long * 0.35));
    track.add(at, rush(long, 0.08, envelope), -0.1);
    // (And the crumbs in it: little crackles.)
    const crumbs = new Float32Array(Math.round(long * RATE));
    for (let i = 0; i < crumbs.length; i++) {
      if (random() < 0.004) {
        const size = (0.15 + random() * 0.2) * envelope(i / RATE);
        for (let j = 0; j < 90 && i + j < crumbs.length; j++)
          crumbs[i + j] += (random() * 2 - 1) * size * Math.exp(-j / 18);
      }
    }
    track.add(at, release(crumbs), 0.1);
  });
  save("munch", track, 0.15);
}

// Turned into a mouse: poof! A soft burst of smoke, and twinkles tumbling
// down and down (you, shrinking).
{
  const track = new Track(1.6);
  track.add(
    0,
    rush(0.9, 0.15, (t) => rise(t, 0, 0.02) * Math.exp(-t / 0.18)),
    0
  );
  ["C8", "A7", "G7", "E7", "D7", "C7", "A6", "G6", "E6", "C6"].forEach((n, i) =>
    track.add(0.04 + i * 0.05, bell(note(n), 0.6, 0.55), 0.6 * Math.sin(i * 1.3))
  );
  sparkle(track, 0, 0.4, 6, 0.2);
  save("poof", track, 0.35);
}

// A mouse's squeak: two little chirps, up and down, the second smaller.
{
  const track = new Track(0.45);
  [
    [0, 0.13, 1],
    [0.17, 0.09, 0.6],
  ].forEach(([at, long, amp]) => {
    const out = new Float32Array(Math.round(long * RATE));
    let phase = 0;
    for (let i = 0; i < out.length; i++) {
      const u = i / out.length;
      const freq = 3200 + 1100 * Math.sin(Math.PI * Math.min(1, u * 1.4)) + 120 * Math.sin(i / 90);
      phase += (2 * Math.PI * freq) / RATE;
      out[i] = amp * Math.sin(Math.PI * u) ** 0.7 * (Math.sin(phase) + 0.2 * Math.sin(2 * phase));
    }
    track.add(at, release(out), 0.1);
  });
  save("squeak", track, 0.2);
}

// A voice: a buzz at pitch(t) (or, as voiced(t) falls, a breath of noise)
// through resonances [hertz, width, gain] that make its vowel, shaped by
// envelope(t).
function voice(seconds, pitch, voiced, formants, envelope) {
  const out = new Float32Array(Math.round(seconds * RATE));
  const filters = formants.map(([freq, width, gain]) => {
    const r = Math.exp((-Math.PI * width) / RATE);
    return { r, c: 2 * r * Math.cos((2 * Math.PI * freq) / RATE), gain, y1: 0, y2: 0 };
  });
  let phase = 0;
  for (let i = 0; i < out.length; i++) {
    const t = i / RATE;
    phase = (phase + pitch(t) / RATE) % 1;
    const source = voiced(t) * (1 - 2 * phase) + (1 - voiced(t)) * (random() * 2 - 1) * 0.5;
    let sum = 0;
    for (const f of filters) {
      const y = (1 - f.r) * source + f.c * f.y1 - f.r * f.r * f.y2;
      f.y2 = f.y1;
      f.y1 = y;
      sum += y * f.gain;
    }
    out[i] = sum * envelope(t);
  }
  return release(out);
}

// The giant chuckling: a deep, warm "ho, ho, ho", each lower and softer.
{
  const track = new Track(1.4);
  const O = [
    [420, 90, 1],
    [760, 110, 0.6],
    [2600, 200, 0.08],
  ];
  [0, 0.28, 0.56].forEach((at, k) => {
    const long = 0.24;
    const low = 88 - k * 8;
    track.add(
      at,
      voice(
        long,
        (t) => low * (1.08 - 0.15 * (t / long)),
        (t) => rise(t, 0.02, 0.06),
        O,
        (t) => (1 - 0.25 * k) * rise(t, 0, 0.015) * (1 - rise(t, long * 0.6, long))
      ),
      0
    );
  });
  save("chuckle", track, 0.45);
}
