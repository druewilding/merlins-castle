# Merlin's Castle — remake plan

A faithful remake of Anita Straker's BBC Micro adventure (BBC Model B, April
1983; published by ESM in 1984), rebuilt as a static TypeScript web game with
illustrated scenes. Successor to `../merlin-web` (Rails 3 + MongoDB, 2010).

Status: **complete and deployed: both versions, all 70 pictures and music. Sound effects and polish next.**

## Decisions

| Topic            | Decision                                                                                                                                                                                                                                     |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fidelity         | Map, text and quirks **exactly** as the original.                                                                                                                                                                                            |
| Input            | **Clicking** plus keyboard (arrows / N S E W, 1–5 for slots). Classic has no typed command line (yet).                                                                                                                                       |
| Look             | **Full-screen painted scene**, a text panel along the bottom, 5 inventory slots. Teletext **Classic mode** kept as a toggle.                                                                                                                 |
| Art              | **Painterly semi-realism**, made with ChatGPT. See `art/STYLE.md`. No player shown.                                                                                                                                                          |
| Dead ends        | The "You are lost…" clue rooms **end the game**.                                                                                                                                                                                             |
| Object placement | Random each game (as the original: many objects have two possible rooms).                                                                                                                                                                    |
| Saving           | **localStorage only**, with named save slots (the original had named position files).                                                                                                                                                        |
| Sound            | Illustrated: looping music (Kevin MacLeod, CC BY 4.0) and sound effects, each switched on or off in the Sound dialog. Classic is silent like the original, except for the original's own victory tune, played from its DATA.                 |
| Language         | English and Danish (Merlins borg). The world's words are in `data/da.json`, laid over `world.json` by `src/engine/localise.ts`; everything else is in `src/shared/strings.ts`. Follows the browser at first, then the Language/Sprog choice. |
| Credit           | Credit Anita Straker clearly on the title and about screens.                                                                                                                                                                                 |
| Hosting          | GitHub Pages → www.druewilding.com/merlins-castle, later merlinscastle.net.                                                                                                                                                                  |
| Multiplayer      | Decided against: it stays a single-player game, as the original was.                                                                                                                                                                         |

## Source material

`original/` holds the real thing:

- `MerlinsCastle.ssd`: disk image from https://bbcmicro.co.uk/game.php?id=2164
  (playable online there, handy for side-by-side checking).
- `MERLIN1.bas`: the title screen. `MERLIN2.bas`: the whole game, with all
  rooms, objects and messages as DATA.
- `notes.txt`: the original teacher's notes (story, commands, classroom ideas).
- `extract.py` (DFS disk → files), `detok.py` (BBC BASIC detokeniser) and
  `convert.py` (MERLIN2 DATA → `data/world.json`).

`docs/`: the original BBC start screen, and Drue's 2010 crayon map sketch.

## How the original works (from MERLIN2.bas)

- **40 rooms, 20 objects.** Start and home is the grassy bank (room 20).
- **Exits** are stored in the order south, west, north, east. Each exit is either:
  - a plain exit (or none), or
  - a **guarded exit**, which has:
    - the object needed,
    - a _use message_ ("The ladder leans against the wall."),
    - a _blocked message_ ("The wall is too high."), plus whether being blocked kills you,
    - a _pass message_ ("You have climbed over."), plus whether passing kills you.
  - Guarded exits that need no object are just messages or traps. For example,
    the mountain's east exit says "Oh dear! Merlin's trap is that way." and kills you.
- **Use** marks an object as in use in the current room. Several objects can be
  in use at once. Moving to any room clears all of them. Quirk: dropping an object
  doesn't clear it, so you can use it, drop it and still pass. If nothing here
  needs the object: "Nothing happens."
- **Take / Drop** work on one object or "all". The carry limit is 5. Messages:
  "You have a rope.", "You're carrying too much.", "You've already got it.",
  "It's not here.", "You haven't taken that.", "All taken.", "All dropped.",
  "There's nothing here.", "You haven't got that.".
- **Score**: 3 per object on the grassy bank, +8 for the five treasures (pearl,
  gold, emerald, ring, silver), for a maximum of 100. The teacher's notes say
  +10 for four treasures (no ring), which also totals 100. **We follow the code.**
- **Winning**: all 20 objects on the bank, while you're standing there. Then
  "You have solved the mystery of Merlin!" and the tune plays.
- **Grassy bank text**: "You wake up on…" on the first visit, then "…a figure
  lies sleeping.", then "You are by a grassy bank." once more than 12 objects
  are there.
- **Clue rooms**: every exit loops back to the same room. One quirk:
  `clue-silver` leads on to `clue-mask`, so you get two clues.
- **Game over** (death, dead end or quit): shows "Your score this time",
  "Best possible score: 100" and "Best score so far" (this session).
- **Colours**: teletext control codes. Each code takes up one space and the colour
  runs to the next code or the end of the row. All text is double height. Message
  colours: errors red (with a beep), obstacle messages cyan, passing messages
  green, objects red.

## Target architecture

```
merlins-castle/
  data/world.json        # generated by original/convert.py — the game content
  src/engine/            # pure TS, no DOM: types, newGame, act, score, describe
  src/ui/                # scene, teletext panel, arrows, inventory, save slots
  src/main.ts
  public/art/            # finished images (rooms/, items/, deaths/), web-optimised
  art/prompts/           # the prompt for each image, so art can be regenerated consistently
  test/                  # vitest
```

- **Vite + TypeScript, no framework.** `base: './'` so one build works at
  `/merlins-castle/` and at the root of `merlinscastle.net`.
- **Engine**: `act(world, state, command) → { state, events }`. Randomness is
  injected, so tests are deterministic. The world is validated at load and in
  a test: every `to` and `needs` must exist.
- **Tests**: port the old cucumber scenarios. Add a scripted **full
  walkthrough to 100 points** as a golden test.
- **Teletext renderer**: port `PROCprint`'s 38-column word wrap so colours
  break across rows exactly as they did on the BBC. Use a Mode 7 font
  (e.g. Bedstead or a teletext webfont).
- **Persistence**: `localStorage` save slots `{ name, savedAt, state }`. Wrap
  every read and write in try/catch.
- **Deploy**: GitHub Actions → Pages on `druewilding/merlins-castle`.

## Art direction and illustrated UI

The style guide and prompts are in `art/` (`STYLE.md`, `prompts/`).

- **Scenes**: painterly semi-realism, storybook matte-painting light, dreamlike.
  Camera about 30° above the ground looking north, so north is at the top of
  the frame, south at the bottom edge, and east/west at the sides. Mood by area:
  summer outdoors, misty forest, dark underground, candlelit castle.
- **North is always up, in every room.** You can arrive from any direction,
  so the view never turns. Anything behind the viewer to the south (the river
  rooms' golden spire, for example) is left to the text.
- **Format**: 1536×1024 (ChatGPT's 3:2 landscape), cropped to fill the screen.
  The top and bottom ~8% may be cropped. The bottom quarter sits under the text
  panel, so it should be plain foreground.
- **No objects painted into rooms**: objects are separate transparent cut-outs,
  placed at per-room "drop spots" (to add to `world.json`). The grassy bank needs
  20 spots, so its pile of treasures grows into a visible score.
- **Consistency**: paste the same style guide every time and attach the anchor
  image(s). Don't rely on ChatGPT remembering a long conversation.
- **Picking up**: the object grows into the centre with its message, then
  whooshes into one of 5 slots at the bottom.
- **Using**: several objects can be in use at once, as in the original code.
  Objects in use glow yellow, and the glow fades on leaving the room.
- **Dropping**: a small button under the slot, or drag it back into the scene.
- **Text panel**: a magical serif (IM Fell English, with Cinzel for titles).
  Highlighted words keep the original's colours, softened. Text appears letter
  by letter, and a click shows it all. A message line shows "Nothing happens." etc.
- **Moving**: fade through black between scenes.
- **Mockups**: `docs/mockups/` (title, grassy bank, dragon cave; laptop and phone
  screenshots) show the gradient text panel, softened highlight colours,
  5 slots, a compass with missing exits dimmed, and drifting motes.
- **Phones held upright**: show the whole picture across the top, with the text
  below and the compass as a thumb pad above the slots, so side exits aren't
  cropped away. Landscape screens get the full-screen layout with a corner
  compass.
- **Extra images**: full-screen death scenes, lost-in-the-mist scenes (shared
  by the clue rooms), the title and victory.
- **Classic mode**: the existing teletext UI, plus (one day) a typed command
  line ported from `PROCin`. It matches on the first 3 letters: `use lad`, `n`.

## Milestones

1. ~~Recover the content~~ ✅ `data/world.json`: all 40 rooms and 20 objects.
2. ~~Engine + tests~~ ✅ Rules and quirks, plus a golden walkthrough to 100 points
   (`test/walkthrough.test.ts`).
3. ~~Teletext UI~~ ✅ Black-screen Mode 7 version, playable by clicking or
   keyboard, with save slots, notes, about and game over.
4. **Art**: style exploration on 3–4 rooms first, then the rest.
5. ~~Illustrated UI~~ ✅ Painted scenes with a fade through black, objects to
   click (rising into a spotlight, then whooshing into one of 5 slots),
   typed text, a compass, use glow, drag to drop, death/lost/victory moments,
   and Classic mode (switchable mid-game). Rooms without art yet show a
   placeholder. `npm run art` builds new images into `public/art/`.
   - **To tune**: per-room floor zones for objects (`src/illustrated/layout.ts`)
     as each room is painted.
6. **Polish**: README, release-please, maybe the victory tune, maybe a port of the
   MERLIN1 title picture (random castle towers on blue) for Classic mode.

Deployed: https://www.druewilding.com/merlins-castle/ (a release, when deploy-please is run).

## Decided along the way

- **Arrows** show only the real exits. Lost rooms have none, which also
  removes the original's "two clues" quirk at `clue-silver`. The arrow keys
  and N/S/E/W keys work as well.
- **Death or dead end**: show the scene and message first, then "Press
  RETURN" leads to the score screen.
- **Best score** is kept in localStorage indefinitely.
- **"You can see"** lists objects alphabetically in both modes. This is a
  deliberate change: the original listed them in the order of its DATA.
- **Starting score**: objects that start on the bank (sometimes the ladder)
  count at once, so a game can start at 3. This is faithful to the original.
