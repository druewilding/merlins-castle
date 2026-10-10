// One Web Audio context for the music and the sound effects. Browsers only
// let it start after a click or key press, so it's made (or woken) then.

let context: AudioContext | null = null;

export function audioContext(): AudioContext {
  context ??= create();
  if (context.state !== "running") void context.resume();
  return context;
}

// iPhones and iPads mute Web Audio in silent mode (or a Sleep focus), but not
// the music's <audio> element, so the sound effects went quiet on their own.
// Saying the page plays media makes both follow the Sound settings instead.
// Classic, which has no Sound settings, still follows silent mode.
// (Safari 16.4 and later; not yet in TypeScript's DOM types.)
function create(): AudioContext {
  const session = (navigator as Navigator & { audioSession?: { type: string } }).audioSession;
  if (session) session.type = "playback";
  return new AudioContext();
}
