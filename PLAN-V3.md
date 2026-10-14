# Merlin's Castle v3: walk through it

v1 and v2 show Merlin's land as paintings, one room at a time. v3 lets you
walk around in it: first person, mouse to look and WASD to move, as in
Counter-Strike. What the original tells you in words, you do with your own
hands.

Three things make v3 what it is:

- **One connected world.** No loading between places. You walk from the
  grassy bank to the castle, down into the tunnels and up the mountain, and
  what you see in the distance is really there.
- **No words.** Everything the original says in text, v3 shows. A way you
  can't take yet looks and feels closed.
- **The same game.** The same map, obstacles, objects, clues, deaths and
  score, decided by the same engine.

Classic and Illustrated stay as they are. v3 is a third way to play.

Status: **step 2 under way.** The whole land, above ground, underground and
indoors, is built in grey boxes (`art/blender/land.py`) and you can walk it
at `/3d`. It's built and deployed with the site, but not linked from
anywhere yet. Next: all the obstacles, their animations, the lost scenes and
the death scenes.

## Keep the engine

`act(world, state, command)` already knows everything: where you are, what you
carry, what is in use, what kills you. It has no screen code in it. v2 already
treats the pictures as a view of the game's state, and v3 does the same in 3D:

| You do this in 3D                          | The engine hears |
| ------------------------------------------ | ---------------- |
| Walk from one place's ground into the next | `go north`       |
| Look at an object and press E              | `take <object>`  |
| Hold an object (keys 1–5) and press E      | `use <object>`   |
| Press G, or throw it                       | `drop <object>`  |

The world is divided into invisible **regions**, one per room. Crossing from
one region into another sends the exit of the first that leads to the second.
The paths and tunnels between places belong to no region: while you walk
along one, you're still in the place you set off from, and the exit happens
when you step out at the other end. Turn back halfway and nothing has
happened.
Each event that comes back plays something: an animation, a sound, a change in
the world. So the 72 tests, the walkthrough to 100 points, saving and the
score all carry over.

**The engine stays the judge.** The 3D world never decides whether you may
pass. A way you may not take yet is solid. When the engine says the way is
open, the 3D world opens it. Where the original kills you for trying, you can
walk up, and the engine's answer plays out.

## Tools

| Job                   | Choice                                                   | Why                                                                                      |
| --------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Rendering             | **Three.js**                                             | Same TS/Vite project, same deploy to merlinscastle.net, runs on the iPad.                |
| Walking and bumping   | **Rapier** (`@dimforge/rapier3d-compat`)                 | Physics in WASM, with a ready-made character controller (slopes, steps).                 |
| Mouse look            | Pointer Lock API                                         | The browser's own Counter-Strike mouse.                                                  |
| Modelling             | **Blender** (free), mostly **driven by Python scripts**  | Scripts can be rerun, reviewed and changed by Claude; no Blender skills needed at first. |
| Objects and creatures | **Image-to-3D** (Tripo, Meshy or Hunyuan3D) from our art | The 20 item cut-outs and the creatures from the paintings become first-draft models.     |
| Animation             | **Mixamo** (free) for people-shaped characters           | Auto-rigging and ready walks, waves and dances for the people of the land.               |
| File format           | **glTF / .glb**, compressed with Draco and KTX2          | What Three.js loads best.                                                                |
| Light                 | **Baked in Blender** into lightmaps                      | Soft painterly light for free at run time, so phones and iPads keep up.                  |

Unity was considered: a better editor, but big web builds, C#, and the
engine would have to be rewritten. Not worth it for a game this size.

## The look

The 70 paintings are the concept art. Each place should feel like stepping
into its picture: the same layout, colours and time of day.

- **Stylised, not realistic**: chunky shapes, hand-painted-looking textures,
  soft baked light, fog for depth. Think storybook diorama.
- **North is still up.** Each place is built so that standing at its south
  edge and looking north shows roughly its painting.
- Textures can be painted by ChatGPT the same way as now (tileable stone, bark,
  grass, flagstones), with a prompt per material in `art/prompts/materials/`.

## One connected world

Laid out from the grassy bank, with north at the top, the map nearly fits a
grid as it is. The giant's cave sits in the top row, next to the treasure
room and above the damp tunnels, which all fit. The forest crossroads lies
well south of the old wall, at the end of a long path, right beside the
witches. A long path between the old stone wall and the grassy bank moves
the whole north-east one step across, so the deep river lies straight north
of its south bank, and the castle straight south of the grassy bank.
`docs/v3-world.png` is the whole land painted in ChatGPT: concept art for
the feel, while the grey-box world settles the exact distances.

```
tower        .            oak-door     treasure     giant        .            .
mossy-steps  .            trolls       maze         damp-tun     .            .
yellow-fl    .            .            mountain     .            .            .
rusty-gate   .            .            mtn-path     .            .            .
old-wall     old-stone    .            GRASSY BANK  evergreen    cave-entr    dragon-cave
.            .            .            deep-river   .            .            dark-tunnels
forest-x     witches      forest-edge  river-south  .            .            beautiful
charcoal     .            .            moat         .            .            .
.            .            .            courtyard    coach-house  .            .
.            .            wizards-kit  grand-hall   dungeon      .            .
.            .            .            merlins-lair small-room   .            .
```

The places needn't be the same size or evenly spaced, and it's fine to walk
further between them: paths, banks, slopes and tunnel stretches fill the gaps.
That makes almost every clash go away. Where the grid doesn't fit, the land
does this:

| Where                                                         | What the land does                                                                                                                                                                                                                |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| old-wall west → cave-entrance, cave-entrance south → old-wall | **The long tunnel**, right under the meadows (see below).                                                                                                                                                                         |
| deep-river east → evergreen-glade (one-way)                   | A path along the river bends north-east, ending in a drop down a mossy bank into the glade. You can slide down, not climb back.                                                                                                   |
| old-wall south → forest-crossroads                            | A long path south from the old wall through the trees, **over the forest bridge** (see below), to the crossroads, which sits right beside the witches' clearing. The charcoal hut is south of the crossroads in its own clearing. |
| dragon-cave north → giant (one-way)                           | **A long tunnel** under the mountain that comes into the giant's cave through its east entrance.                                                                                                                                  |
| small-room west → merlins-lair (one-way)                      | A door that only opens one way.                                                                                                                                                                                                   |
| merlins-lair north → grand-hall (one-way)                     | A hidden door into the hall, that only opens one way.                                                                                                                                                                             |
| The six clue rooms                                            | **The mist** (see below): the edges of the world where you get lost.                                                                                                                                                              |

`scripts/map-check.js` (to write) checks this grid against `world.json` and
lists the clashes, so the table stays true.

**Every missing exit needs a barrier** you believe: a cliff, thick hedge,
bramble, river, castle wall or rock face. The original just says nothing
happens; v3 has to show why you can't go that way. This is the real design
work of a connected world.

**Seeing far**: because the world is real, places show in the distance before
you can reach them. The castle's golden spire rises to the south of the
river, the tower to the north-west, the mountain to the north. You see where
you're trying to get to long before you know how. Far-off places are drawn as
simple low-detail versions until you're close.

**Loading**: the world is cut into areas (meadows, forest, mountain, tunnels,
castle) that load in the background as you approach. 34 small places isn't a
lot for a browser. There's one loading screen, at the start.

### The river

The river runs right across the land, west to east, as the paintings
already show it: between the meadows to the north and the forest and castle
to the south.

- **It comes out of the mist** in the far west of the forest. Nobody knows
  where it starts.
- **The forest bridge**: the long path south from the old wall crosses it
  halfway along, on an old wooden bridge among the trees. This is the
  original's map, not an addition.
- **It bends north** between the bridge and the deep river, round the misty
  wood north of the witches, so getting lost that way never reaches the
  water and needs no second bridge.
- **The deep river** is where it's narrowest and fastest, with rapids.
- **It goes underground** in the east, past the evergreen glade, plunging
  into a dark hole in the rocks. Somewhere in the tunnels below you can hear
  it roaring.

### The old stone wall

One long wall, as in the paintings, with the rusty gate in it:

- It comes out of the forest south of the old stone wall, where thick trees
  stop you following it, so you never see where it starts.
- It runs north between the old stone wall and the old wall.
- It turns west along the rusty gate, and the gate is set in it.
- It turns north again, up the west side of the yellow flowers, and
  disappears into the trees.
- The long tunnel passes under its foundations.

### The long tunnel

The old wall's small dark tunnel and the cave entrance's steps are the two
ends of **one long tunnel, deep underground**, running east under the old
stone wall, the grassy bank and the evergreen glade. It's a journey of its
own, about a minute's walk, in the dark:

- **You pass under places you know.** The great foundation stones of the old
  stone wall. A crack in the roof with a thin blade of daylight and a
  glimpse of sky: you're under the grassy bank. Pine roots hanging through
  the roof under the evergreen glade. Water dripping somewhere. Then steps
  up, and daylight, and you come out under the cave entrance's mound.
- **You can turn back.** Halfway along, you're still in the place you set
  off from, so walking back out the way you came is fine.

## Few words

The original speaks in messages. v3 shows the places and what happens
instead, but **obstacles keep their words**: when something's in your way,
the original's message for it comes up at the bottom of the screen, as well
as what you see. Everything else is shown:

| The original says           | v3 shows                                                                   |
| --------------------------- | -------------------------------------------------------------------------- |
| A room's description        | The place itself                                                           |
| "You can see …"             | The object, lying there                                                    |
| A way you can't take yet    | Why, in the world: it's solid, it's locked, it pushes you back             |
| "Nothing happens."          | The object in your hand glints and nothing changes, with a soft dull sound |
| "You're carrying too much." | Your slots flash and the object stays where it is                          |
| What using an object does   | It happening, in front of you                                              |
| A death message             | The death, from where you stand                                            |
| The score                   | The treasure pile on the grassy bank (and a counter in the pause menu)     |

So there's little to translate: the obstacles' messages (already in
data/da.json), the title, the credit to Anita Straker and the menus (with
icons where they can be).

### Clues without words

The six clue rooms are where you get lost: the mist at the edges of the world
(the forest's west and south, the tunnels' far ends).
The mist thickens, the world fades, and the clue appears **as a vision**: a
ghostly little scene in the mist, then the game ends. The v2 effect
paintings already show most of them, so they're the concept art for the
visions.

## Things that undo themselves

In the original, **leaving a room clears everything in use**: a way you
opened is closed again when you come back. In a connected world you'd see
that happen, so make it magic, on purpose: it's Merlin's land, and
everything here is enchanted. What you opened mends itself as you leave,
with a shimmer, and tells you you'll need the object again without a word.

- **Use, then drop** (the original's quirk: the way stays open): the dropped
  object simply stays where you used it until you leave. The quirk becomes
  common sense.

One rule covers all of it: **the way is open until you leave the place**,
exactly as `using` already works. Each place has an "open" and a "closed"
state per exit, the same list v2 painted (28 effects).

## One way, as in the original

Many of the original's obstacles only stand in one direction: an object gets
you past one going one way, while the other way is always free. **v3 keeps
those rules exactly**, rather than making obstacles things with a state of
their own (open or not):

- **The puzzle was built on them.** You can get somewhere one way with an
  object and come back another way without it. With obstacles that remember,
  that player would be stuck, in a game that could always be finished.
- **People who know the original** expect what worked then to work now.
- **State brings its own puzzles**: saving and loading, dying, coming at a
  place another way. The one-way rules have none.

So the rules stay the original's, and **state is only in what you see**:
each one-way obstacle looks the way it works from where you stand, and has a
reason you can see for letting you through one way and not the other. It
explains the rule instead of just enforcing it.

In the code: an obstacle's names are the exits it blocks, and it only stops
you going their way (`wayThrough` in `src/three/player.ts`). Going through
it the free way, you go all the way through, even past its middle. So a
one-way obstacle's far side must only be reachable from that side.

## Your hands

You never see yourself, as in the paintings: you're "you". Only your arm and
hand show, at the bottom right, holding whatever is in the chosen slot, like
the weapon in Counter-Strike.

- **One arm, a few poses**: a sleeve and a gloved hand (no skin to choose),
  holding out, raising, swinging, throwing, and both hands when climbing.
- **It sways as you walk** and settles when you stop.
- **Drawn on its own layer**, so it never pokes into walls.

- Five slots, keys **1–5**, like a weapon hotbar. The held object shows in your
  hand at the bottom right, Counter-Strike style.
- Carrying big things and small at once is fine: it's a game.
- Objects start in the place the engine puts them, at a random spot in it
  you can walk to (a new one every game, so you go hunting for them), and
  lie where you drop them, resting on the bumps of the ground.
- The grassy bank's pile of treasure grows as you score, as now.

## Dying, getting lost, winning

- **Deaths** are short scenes from where you stand. The 11 death paintings
  say what each one shows. Then the curtain falls, with no words, and the
  menu.
- **Lost**: the mist and a vision (above).
- **Winning**: a scene of its own, then the tune.

## Controls everywhere

- **Laptop**: WASD or arrows, mouse look, E take (or use, looking at nothing to take), click use too, G drop, 1–5 slots.
- **iPad and phone**: a left thumb stick to walk, drag on the right to look,
  buttons for take, use and drop.
- **Gamepad**: free with the Gamepad API.
- **Reduced motion**: no head bob, gentler effects.

## Code layout

```
src/engine/        unchanged: the judge
src/three/         the 3D version
  main.ts          boot, loading screen
  world.ts         streams areas (.glb) in and out
  regions.ts       which place you're standing in; crossing one sends `go`
  player.ts        Rapier character controller, mouse look, touch sticks
  places.ts        per place: open/closed states, object spots, barriers
  effects.ts       what each `use` does to the world
  moments.ts       deaths, mist and visions, winning
art/blender/       Python scripts that build each area in Blender
art/models/        the .blend sources and image-to-3D downloads
public/models/     the compressed .glb files the game loads
```

The title screen gets a third choice next to Classic and Illustrated.

## Who does what

**Claude** can do most of the building:

- All the TypeScript: the 3D app, player, regions, streaming,
  touch controls, and wiring the engine in. Tested with Playwright and
  screenshots, as with v2.
- **Blender through Python**: Claude writes scripts that build terrain,
  walls, paths, steps, tunnels, rooms and simple props, set up the light, bake
  it, and export the `.glb`. You run one command (`npm run models`), which runs
  Blender with no window. Claude renders preview images to check its own work.
- Prompts for textures and for image-to-3D, as with the paintings.

**Drue** does the eye and the hands:

- Judging the look: "the wall is too clean", "the oak door is wrong".
- Generating textures and models in ChatGPT and the image-to-3D site, as now.
- Small fixes in Blender by hand, once comfortable (moving a tree, scaling a
  rock). Claude can talk you through the few clicks needed.
- Mixamo: upload a character, pick an animation, download. A few clicks.
- Playing it, a lot.

What's genuinely hard, for anyone: **characters**. Good-looking, animated
people and creatures are the biggest piece of art work. Image-to-3D plus
Mixamo gets people-shaped characters a long way. The rest may need a bought
or free model.

## Order of work

1. ~~**Learn the pipeline on one place.**~~ ✅ The grassy bank on its own,
   now kept as a study of the look to aim for
   (`art/blender/studies/grassy-bank.py`).
2. **The whole map in grey boxes.** Every place as plain shapes at its spot,
   joined by paths and tunnels, with barriers, regions and the engine wired
   in. Playable from start to finish with stand-in objects. This settles the
   layout, the distances and the sight lines (the spire!) before any art.
   - ~~**Above ground**~~ ✅ `npm run models` runs `art/blender/land.py` in
     Blender with no window (add `-- land --preview` for a picture in
     `art/blender/previews/`). Open `http://localhost:5173/3d`.
   - **Underground** ✅: the long tunnel (dark at both mouths); the caves in
     the mountain, dug into crags round the maze (trolls, oak door, treasure
     room over a deep hole, giant, damp tunnels); the dragon's cave inside a
     rocky hill, its long tunnel up under a ridge into the giant's east
     side, and its way down to the dark tunnels (which run out west and east
     into the mist) and the beautiful chamber.
   - **The castle** ✅: the courtyard (well, flowers) with the coach house
     as a barn; the keep across its south, entered from the courtyard into
     the grand hall. The kitchen opens straight off the hall's west side; a
     corridor runs east and down steps to the dungeon, then south and up to
     the small room. Merlin's lair is big enough to share a wall with both
     the small room and the hall. Each room furnished after its painting,
     with its own light.
   - **Indoors** ✅: the charcoal burner's hut (its door north to the
     crossroads; a hearth, a straw bed, sacks of charcoal) and the round room
     in the tower (its door south at the top of the mossy steps, and steps
     curling up the wall to the floor above, which you can climb), each cut
     out of the land like the coach house.
   - **Obstacles speak** ✅: walk into one and you're nudged gently back,
     with the original's words for it at the bottom of the screen, in
     English or Danish, for the exit you're trying. One-way, as in the
     original.
   - **The game**: taking, using and dropping objects ✅ (the first objects'
     models are made by `art/blender/items.py`); the first obstacles opening
     ✅; saving and loading ✅ (the same saves as the other versions, and
     switching between all three with the game carried over); the trees ✅
     (Quaternius's, a mix for each part of the land, `src/three/trees.ts`).
     Still to come: all the rest of the obstacles, their animations, the
     lost scenes and the death scenes.
3. **The first beautiful corner**: grassy bank, old stone wall and old wall
   (where v2 began), fully modelled, textured and lit. **Then decide**
   whether the look works and how long a place takes.
4. **The meadows and forest**: the witches' clearing, the mist.
5. **Underground**: the long tunnel, the dragon's cave, the long tunnel to
   the giant, the maze, the treasure room.
6. **The castle**: moat, courtyard, grand hall, kitchen, dungeon, Merlin's
   lair.
7. **Deaths, visions, winning, sound**: music and fx carry over, plus
   footsteps and creaks.
8. **Phones and iPads**: performance pass, touch controls polished.

## Decided along the way

- **Vertex colours, not textures**, for now: every place is a handful of
  meshes sharing one material, coloured per vertex with a little noise for a
  painted look. Paths are strips laid on the ground, so their edges stay crisp.
- **Real-time light for now**, not baked: a low warm sun from the west-north-
  west, a sky-and-grass hemisphere light, and shadows that follow you. Baking
  comes later if phones need it.
- **Places are 40 m apart**: close, as the original felt. The whole map is
  about 450 m from end to end; the grassy bank to the castle is half a
  minute's walk.
- **`art/blender/layout.json` says where everything is**, for both Blender
  and the game: each place's square on the grid, which are buildings and
  caves, and where the mists and deadly ways are.
- **Forest is the barrier.** Trees grow wherever the ground isn't a place, a
  path, the meadow, the mountain top or the castle grounds. A walkability map
  (a square metre at a time) keeps you out of the forest, the river and the
  moat, so there are no gaps between trees to slip through.
- **Obstacles are named by the exit they block** (`land.json`). Only
  obstacles that stop you need one: where the original kills you for trying,
  you walk up and the game decides.
- **`test/land.test.ts` walks the land** with every obstacle closed and checks
  you only reach the places the original lets you: it found a gap that no
  screenshot would have shown.
- **Simple bumping for now**, not Rapier: the ground's heights come from a
  grid, and walls, buildings and rocks are circles and boxes. Rapier comes in
  when there are steps and slopes to climb.
- **Names use hyphens**: three.js drops dots from names when it loads a file.
- **Meshopt compression**: the land is 5 MB, decoded by three.js with no
  extra files.
- **You can walk round the outside of the moat**, all the way behind the
  castle: a little extra for people who like to explore. It changes nothing
  in the game: it leads nowhere else, and the castle rooms are all more than
  30 m from it, so you never count as being in one.
- **Ways underground** are lines with a floor height at each point
  (`ways` in `land.json`). The ground has a hole only over their ramps, lined
  with stone walls, with a lintel where the roof begins. You step into a way
  at the top of its ramp; from then on its floor holds you up and its walls
  hold you in until you walk out of an end. While you're in one, you're
  still in the place you set off from.
- **Halls** are the caverns the ways join (`halls` in `land.json`): round,
  with a flat floor and a domed roof. Walking into one is walking into its
  place. Some have their own light: torches, fire, gold.
- **Rooms** are halls with square corners (`w` and `d`), and corridors are
  ways marked `indoor`: walls and a roof all the way, and the light of
  indoors as you go in at the door. The keep and the coach house are cut out
  of the land, so you're only ever in them along a way.
- **An obstacle is one shape with the names of every exit it blocks** (an
  exit and the one coming back the other way). It only stops you going the
  way its exits go; the other way, you walk straight through it (as the
  original's one-way exits). In your way, it nudges you back and says its
  blocked message, or the exit's own message, or "You can't go that way."
  So a one-way obstacle's far side must only be reachable from that side.
  Obstacles at the tunnels' mouths are on the land, a little way down the
  ramp and reaching out over the top, so you're stopped before you go down;
  coming up out of a tunnel, you're going through them the free way.
- **`npm run gaps` finds holes in the world** (`scripts/gaps.js`): with the
  sky magenta, it looks round from every few metres along the ways, in the
  halls and round the buildings, and follows every magenta pixel's ray back.
  Sky seen through the earth, or (from inside) through a wall or a roof, is
  a gap; out of a door, a mouth or an open ramp, it isn't. Run it after
  changing the land.
- **Obstacles underground** block only the ways (`"under": true`), so an
  obstacle on the land over a tunnel doesn't stop you down below. The test
  walks the ways and halls too, with every obstacle closed and every one open.
- **Underground light**: as you go down, the sun and sky fade and a warm
  glow round you takes over. The land casts shadows, so the sun can't shine
  into a tunnel from above. Indoors in a building the sun stays out (the
  roof's shadow keeps it off you, and it's still day outside the door); only
  the sky's light softens. Every lit cave and room keeps its own light on
  (the four nearest you, a fixed number of lights, so materials never
  rebuild), so a room seen through a doorway is lit too.
- **A debug panel** at `/3d?debug`, built or not (the 0 key): fly (F), walk
  through anything (N), open every obstacle (O), show the obstacles and
  their reach (R, red where they kill you), show gaps with a magenta sky
  (M), float the places' names (L), go up to 10× faster (, and .), copy a
  picture (P), and a map to jump anywhere. The letter keys work with the panel closed
  too. `src/three/debug.ts` and `debug.css` are only loaded with `?debug`,
  so nobody else downloads them.
- **Names over the places** (L, in the debug panel only; off to start with)
  while the world is grey, and the place you're in at the top left. For now
  they're made from the code's names (so "Merlins lair",
  without its apostrophe); they should become the original's own names, in
  English and Danish, when the game is wired in.

## Still to decide

- **How much action?** Puzzles only (the original), or a little danger in a
  few places. Suggest: puzzles only at first.
- **Name**: a third button on the title screen, or its own page (`/3d`).
