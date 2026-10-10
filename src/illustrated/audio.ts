// One Web Audio context for the music and the sound effects. Browsers only
// let it start after a click or key press, so it's made (or woken) then.

let context: AudioContext | null = null;

export function audioContext(): AudioContext {
  context ??= new AudioContext();
  if (context.state !== "running") void context.resume();
  return context;
}
