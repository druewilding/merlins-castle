---
name: death-scene
description: Build a short death scene for Merlin's Castle 3D, played from where you stand when you walk into a way that ends the adventure (Merlin catching you, the goblins, the stone statue, the frog, the giant's mouse and so on), up to the curtain and the score. Use when making or reworking any of them in src/three/.
---

# Making a death scene

How the death scenes were made, written down so the next one goes faster.
The six built so far each live in their own file:

| The words | The way | The scene |
| --- | --- | --- |
| The ladder slips and you fall. | mossy-steps east | `fall.ts` (`Fall`) |
| You are swept away by the current. | deep-river south | `swept.ts` (`Swept`) |
| The witches catch you and tie you up. | forest-witches west | `caught.ts` (`Caught`) |
| Oh dear! Merlin's trap is that way. | mountain east | `trap.ts` (`Trapped`) |
| You slip down a deep, deep hole. | maze north, treasure-room south | `hole.ts` (`Slipped`) |
| You fall over in the dark. | dark-tunnels south | `tripped.ts` (`Tripped`) |

`tripped.ts` is the newest and the simplest to copy. `trap.ts` shows a prop of
its own that goes on moving behind the curtain.

Keep the README and PLAN-V3 spoiler-free: never write there what kills you or
where. Commit messages may.

## 1. Look

- The way, in `data/world.json`: its words, and whether the way itself kills
  you (`"fatal": true` on the exit: the words are its `message`) or its
  obstacle does (`"fatal": true` on the obstacle: the words are its
  `blocked`). Note the object it `needs`: with that in use, the way is open
  and there's no scene.
- The place: walk there with `/3d?debug&at=x,z,yawDeg` and look at it the way
  you'd go. Its obstacle is in `src/three/models/land.json` (`obstacles["<place>
  <dir>"]`: a `box` [x, z, half x, half z] or a `circle`), its hall in `halls`
  if it's underground.
- What's there to use: a creature (`witches.ts`, `dragon.ts`), a prop
  (`trap.ts`'s net), your own glow (`lamp` in `main.ts`), the land.
- The ideas for it: `docs/notes.md` (gitignored), and the list below.

## 2. The tone

Gentle, storybook: "and that was the end of the adventure". Never violent
and never scary: a little comic, if anything (cartoon stars, a polite cough).
Clearly the end, and just enough to matter. The original's words come up on
the curtain, so the scene shows them, and doesn't need to explain itself.

Get to the moment quickly. The stumble in the dark first took four slow steps
before the trip, and was better as two quick ones. Most scenes are 6.5–8 s,
and the curtain starts to fall 1.5 s (`EARLY`) before `ends`.

The scenes still to make, and the ideas for them:

- **Merlin has caught you** (wizards-kitchen east): a polite cough behind you;
  you turn and Merlin's there, arms folded, shaking his head, tapping his
  foot, sparkles swirling round you.
- **The goblin's trap** (grand-hall west): the floor tips you onto a slide, a
  helter-skelter down into the dark, landing softly in a heap of straw.
- **Merlin's goblins capture you** (grand-hall east): goblins pop up all round
  you, giggling, lift you over their heads and carry you off, bouncing along.
- **A stone statue** (dungeon south): the colour drains in from the edges, you
  slow, and the picture settles grey and still, with a faint chime.
- **Turned into a frog** (merlins-lair north): a green puff, the camera drops to
  ankle height, the room looms huge, a hop or two, "ribbit".
- **Turned into a mouse by the giant** (giant west): a puff, the world shoots
  up, the giant's huge face peers down chuckling, a squeak.
- (**Falling into darkness**, treasure-room south, shares the deep hole's scene
  for now. Its own idea: drifting slowly down, Alice-style, past faint motes
  of light.)

## 3. The scene (`src/three/<name>.ts`)

A class with `readonly ends` (seconds) and `update(dt)`, which is all
`main.ts` needs (`Scene3d`). Begin the file with a comment quoting the words
and telling the scene beat by beat, as the others do.

- **Beats** as constants at the top, in seconds from walking into it (`TRIP`,
  `DOWN`, `ROLL`, `ROLLED`, `ENDS`), then the distances and angles, each
  commented with what it is.
- **The constructor** keeps where you were (`camera.position.clone()`) and how
  you were looking (`camera.quaternion.clone()`), and works out the rest:
  which way's on (from the obstacle's box, and which side of it you're on),
  your feet, its floor.
- **Each frame** it sets `camera.position` and `camera.quaternion` itself:
  `player.held` is true, so you can't walk. Turn from however you were
  looking with `slerpQuaternions(facing, look, ease(t / 0.4))`. Build a look
  with `Euler(pitch, yaw, roll, "YXZ")` (yaw 0 faces -z), or turn about a
  world axis with `setFromAxisAngle(...)` premultiplied (rolling over,
  `Tripped`). Use `ease()` (smoothstep) for anything that starts and stops.
  Something falling speeds up as `f * f`.
- **Sounds at beats:** take a callback (`play: (sound: "trip" | "bump") =>
  void`) and call it as a beat is crossed (`was < BEAT && t >= BEAT`), so each
  plays exactly once.
- **Behind the curtain:** the curtain and the score card are see-through, and
  `update` goes on being called until you start again. Something that should
  go on (the net swinging, the stars circling) needs the scene's clock to run
  on past `ends`: don't clamp `t` to `ENDS`.
- **Reduced motion** (`reducedMotion`): the scene still plays out, but without
  the extras: no bob, sway or wobble, and its effects hang still.
- **Ground and floors:** the land from `drawn` (as `Caught` uses it).
  Underground, `player.floorAt(x, z)` gives the floor of a hall or a way.

**Props** (sprites, a net, a creature): make them once, in `main.ts` or a
class of their own, and hand them to the scene. The scene shows and moves
them. Hide or reset them in `restart()`, beside `net.reset()` and
`stars.hide()`. Sprites for an effect drawn over everything: a canvas
texture, `depthTest: false`, `fog: false`, `toneMapped: false`, a high
`renderOrder` (the stars).

**Lights:** never add one for a scene (that makes every material rebuild).
Move the ones there: in the dark, your own glow (`lamp`) stays where you were
standing while the camera moves, so a scene underground carries it along
(`Slipped`, `Tripped` in the frame loop).

## 4. Wiring it in (`main.ts`)

- A constant for its way beside `BALCONY`, `RIVER`, `WITCHES` and `DARK_WAY`.
  Check the name isn't taken.
- An entry in `scenes`, keyed by the way, that makes it, or returns
  `undefined` when there's nothing to see (the object's in use:
  `effects(world, items.state).includes("<needs>")`).
- `dying()` does the rest: the engine's death, holding you still, the curtain
  with the words, Continue, the score.
- Add it to the list in the comment before `BALCONY`.

Sounds: the 3D version's own go in `src/three/sounds.json` (one line each:
writing it with a JSON library and Prettier spreads it out, so keep its
shape). Use a Kenney sound from `art/originals/fx` (footsteps, `impactSoft_*`
for a soft fall, cloth), or make one in `scripts/make-sounds.js`: add it at
the **end**, so the seeded random leaves the others as they were. Run `npm
run sounds` for a new synthesised one, then `npm run art:build`.

## 5. Check it

- Playwright, a temporary `*.t.mjs` in the repo root (webkit), deleted after:
  - English: `localStorage.setItem("merlins-castle:language", "en")` in
    `addInitScript` (the browser's own language otherwise: Danish here).
  - Start **outside the obstacle's reach** (a few metres back:
    `/3d?debug&at=x,z,yawDeg`). Placed within it, you count as already going
    through it, and walk straight on.
  - Hold the key on `window`: `dispatchEvent(new KeyboardEvent("keydown", {
    code: "KeyW" }))`, then wait for `document.body.classList.contains("scene")`
    and let go.
  - Screenshot at each beat, and well after the curtain; click `.curtain
    button` (Continue) and look behind the score card too. Combine them with
    `magick ... +append` and look side by side.
  - With `page.emulateMedia({ reducedMotion: "reduce" })` too.
  - `window.world.restart({ state: structuredClone(window.world.items.state) })`,
    then check its props are gone.
- With the object in use: no scene, and the way's open.
- The scene starts when you bump into the obstacle, which can be metres short
  of it (its reach). Check that where it happens still reads as going that
  way.
- Then `npx prettier --check src test`, `npx eslint src test`,
  `npx tsc --noEmit -p .` and `npx vitest run`.

## What the first looks caught (check these first)

- **Too long getting there:** a slow lead-in dulls it. Get to the moment.
- **Black in the dark:** underground, falling away from your glow, you saw
  nothing. Carry the glow with you.
- **Small, dull effects:** the stars first looked like dim buttons: a glow too
  strong for a star too small. Make the shape fill its sprite, the glow soft,
  and the size generous.
- **Frozen behind the curtain:** the stars stopped when the clock did. Let
  what should go on, go on.
