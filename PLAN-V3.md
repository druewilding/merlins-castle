# Merlin's Castle v3: walk through it

v1 and v2 show Merlin's land as paintings, one room at a time. v3 lets you
walk around in it: first person, mouse to look and WASD to move, as in
Counter-Strike. You climb the ladder yourself, swing the axe at the trees,
and throw the water at the dragon.

Three things make v3 what it is:

- **One connected world.** No loading between places. You walk from the
  grassy bank to the castle, down into the tunnels and up the mountain, and
  what you see in the distance is really there.
- **No words.** Everything the original says in text, v3 shows. The wall is
  too high because you can't climb it. The gate is locked because it rattles.
- **The same game.** The same map, obstacles, objects, clues, deaths and
  score, decided by the same engine.

Classic and Illustrated stay as they are. v3 is a third way to play.

Status: **an idea.** Nothing is built yet. Start with the first slice (below).

## Keep the engine

`act(world, state, command)` already knows everything: where you are, what you
carry, what is in use, what kills you. It has no screen code in it. v2 already
treats the pictures as a view of the game's state, and v3 does the same in 3D:

| You do this in 3D                          | The engine hears |
| ------------------------------------------ | ---------------- |
| Walk from one place's ground into the next | `go north`       |
| Look at an object and press E              | `take ladder`    |
| Hold an object (keys 1–5) and click        | `use ladder`     |
| Press G, or throw it                       | `drop ladder`    |

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
pass. A wall you may not climb yet is solid. When the engine says the way is
open, the 3D world opens it. Where the original kills you for trying (the
goblins, the giant, the witches), you can walk up, and the engine's answer
plays out.

## Tools

| Job                   | Choice                                                   | Why                                                                                      |
| --------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| Rendering             | **Three.js**                                             | Same TS/Vite project, same deploy to merlinscastle.net, runs on the iPad.                |
| Walking and bumping   | **Rapier** (`@dimforge/rapier3d-compat`)                 | Physics in WASM, with a ready-made character controller (slopes, steps).                 |
| Mouse look            | Pointer Lock API                                         | The browser's own Counter-Strike mouse.                                                  |
| Modelling             | **Blender** (free), mostly **driven by Python scripts**  | Scripts can be rerun, reviewed and changed by Claude; no Blender skills needed at first. |
| Objects and creatures | **Image-to-3D** (Tripo, Meshy or Hunyuan3D) from our art | The 20 item cut-outs and the creatures from the paintings become first-draft models.     |
| Animation             | **Mixamo** (free) for people-shaped characters           | Auto-rigging and ready walks, waves and dances for Merlin, the giant, goblins, guards.   |
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
grid as it is. The giant sits in the top row, where it's naturally found:
next to the treasure room and above the damp tunnels, which all fit. The
forest crossroads lies well south of the old wall, at the end of a long path,
right beside the witches. A long path between the old stone wall and
the grassy bank moves the whole north-east one step across, so the deep river
lies straight north of its south bank, and the castle straight south of the
grassy bank. The [picture map](https://claude.ai/artifact/9LzdktTaSaPtsdec2Qswq6) draws
this with every exit and the object it needs.

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

| Where                                                                | What the land does                                                                                                                                                                                                                |
| -------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| old-wall west → cave-entrance, cave-entrance south → old-wall (lamp) | **The long lamp tunnel**, right under the meadows (see below).                                                                                                                                                                    |
| deep-river east → evergreen-glade (one-way)                          | A path along the river bends north-east, ending in a drop down a mossy bank into the glade. You can slide down, not climb back.                                                                                                   |
| old-wall south → forest-crossroads                                   | A long path south from the old wall through the trees, **over the forest bridge** (see below), to the crossroads, which sits right beside the witches' clearing. The charcoal hut is south of the crossroads in its own clearing. |
| dragon-cave north → giant (one-way)                                  | **A long tunnel** under the mountain that comes into the giant's cave through its east entrance. It looks like the way back, but the giant's east exit is a lost one: try it and you get lost in the dark.                        |
| small-room west → merlins-lair (one-way)                             | A door that slams and locks behind you.                                                                                                                                                                                           |
| merlins-lair north → grand-hall (one-way)                            | A hidden door into the hall that closes into the wall behind you. From the hall it won't open (the original's "You cannot pass.", which technically leads back into the hall).                                                    |
| The six clue rooms                                                   | **The mist** (see below): the edges of the world where you get lost.                                                                                                                                                              |

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
  original's map, not an addition: the old wall's way south has no obstacle,
  so there was always a free way across. You can reach the castle without the plank by going round
  through the forest (old wall, crossroads, witches, forest edge, south bank).
- **It bends north** between the bridge and the deep river, round the misty
  wood north of the witches, so getting lost that way never reaches the
  water and needs no second bridge.
- **The deep river** is where it's narrowest and fastest, with rapids. The
  plank is the short cut, straight across from the grassy bank's side.
- **Without the plank**, from the north bank you're swept away downstream
  (deadly). From the south bank you fall in, and the current pushes you back
  out (not deadly), as in the original.
- **It goes underground** in the east, past the evergreen glade, plunging
  into a dark hole in the rocks. Somewhere in the tunnels below you can hear
  it roaring. That's also where you'd be swept, if you crossed without the
  plank.

### The old stone wall

One long wall, as in the paintings, with the rusty gate in it:

- It comes out of the forest south of the old stone wall, where thick trees
  stop you following it, so you never see where it starts.
- It runs north between the old stone wall and the old wall (the ladder
  crossing).
- It turns west along the rusty gate, and the gate is set in it.
- It turns north again, up the west side of the yellow flowers, and
  disappears into the trees.
- The lamp tunnel passes under its foundations.

### The long lamp tunnel

The old wall's small dark tunnel and the cave entrance's steps are the two
ends of **one long tunnel, deep underground**, running east under the old
stone wall, the grassy bank and the evergreen glade. It's a journey of its
own, about a minute's walk, with only your lamp to see by:

- **The lamp is the light.** Everywhere else the light is baked; here it's a
  real flickering flame in your hand, throwing moving shadows on the walls.
- **You pass under places you know.** The great foundation stones of the old
  stone wall. A crack in the roof with a thin blade of daylight and a
  glimpse of sky: you're under the grassy bank. Pine roots hanging through
  the roof under the evergreen glade. Water dripping somewhere. Then steps
  up, and daylight, and you come out under the cave entrance's mound.
- **Without the lamp**, the mouth is black. A few steps in, you can't see
  your hands, you stumble, and you find yourself back at the mouth. (The
  original's "You can't see." and "It's too dark down there.")
- **Both ends need the lamp**, as in the original: use it at the old wall to
  go in from the west, or at the bottom of the cave entrance's steps to go in
  from the east.
- **You can turn back.** Halfway along, you're still in the place you set
  off from, so walking back out the way you came is fine.

## No words

The original speaks in messages. v3 shows each one instead:

| The original says                              | v3 shows                                                                   |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| A room's description                           | The place itself                                                           |
| "You can see a ladder."                        | The ladder, lying there                                                    |
| "The wall is too high."                        | You can't climb it. You jump, you slide off.                               |
| "It is locked." / "The door is firmly locked." | The gate rattles, the door handle won't turn                               |
| "The trees are too dense."                     | You can't push through                                                     |
| "A pile of leaves fills the entrance."         | A wall of leaves that you sink into and are pushed back from               |
| "You fall in but get out safely."              | You wade into the river, the current pushes you back to the bank           |
| "Nothing happens."                             | The object in your hand glints and nothing changes, with a soft dull sound |
| "You're carrying too much."                    | Your slots flash and the object stays where it is                          |
| "The ladder leans against the wall."           | The ladder leans against the wall                                          |
| A death message                                | The death, from where you stand                                            |
| The score                                      | The treasure pile on the grassy bank (and a counter in the pause menu)     |

So there's nothing to translate: v3 is the same in English and Danish. The
only words are the title, the credit to Anita Straker and the menus (with
icons where they can be).

### Clues without words

The six clue rooms are where you get lost: the mist at the edges of the world
(the forest's west and south, the tunnels' far ends).
The mist thickens, the world fades, and the clue appears **as a vision**: a
ghostly little scene in the mist, then the game ends.

| Clue                                | The vision                                                           |
| ----------------------------------- | -------------------------------------------------------------------- |
| Use the spell when you meet Merlin  | Merlin raising his wand, the spell glowing, and he shrinks to a frog |
| Give Merlin silver for his buttons  | Merlin's robe with a missing button, a silver button floating to it  |
| A mask hides you from goblins       | A figure in the mask walking past goblins who don't look up          |
| A ring helps to move a stone        | The ring glows and a great stone rolls aside                         |
| A plank makes a bridge for you      | A plank settles across a river                                       |
| Tie goblins up with rope if you can | Goblins wrapped in rope, looking worried                             |

The v2 effect paintings already show most of these, so they're the concept
art for the visions.

## Things that undo themselves

In the original, **leaving a room clears everything in use**: the wall needs
the ladder again, the trees need the axe again, the dragon breathes fire
again. In a connected world you'd see that happen, so make it magic, on
purpose:

- **The trees grow back.** Chop through, look back, and the stumps creak and
  shoot up into forest again with a shimmer. It's Merlin's land: everything
  here is enchanted. And it tells you "you'll need the axe again" without a
  word.
- **The dragon's fire rekindles** as you leave.
- **The leaves blow back** into the cave mouth.
- **The ladder** comes back into your hands as you climb over (it's carried,
  as in the original).
- **Use, then drop** (the original's quirk: the way stays open): the dropped
  ladder simply stays against the wall until you leave. The quirk becomes
  common sense.
- **The plank** stays across the river while you're on it, then the river
  takes it back to your slot.

One rule covers all of it: **the way is open until you leave the place**,
exactly as `using` already works. Each place has an "open" and a "closed"
state per exit, the same list v2 painted (28 effects).

## Your hands

You never see yourself, as in the paintings: you're "you". Only your arm and
hand show, at the bottom right, holding whatever is in the chosen slot, like
the weapon in Counter-Strike.

- **One arm, a few poses**: a sleeve and a gloved hand (no skin to choose),
  holding out, raising, swinging (the axe), throwing (the water), playing (the
  harp), and both hands on the rungs when climbing.
- **It sways as you walk** and settles when you stop.
- **Drawn on its own layer**, so it never pokes into walls.
- **The lamp's flame is the light** in dark places, so the light moves with
  your hand.
- **The mirror** is the one place you might glimpse yourself. It shows the
  old woman, not you: you hold it up to her, not to your face.

- Five slots, keys **1–5**, like a weapon hotbar. The held object shows in your
  hand at the bottom right, Counter-Strike style.
- Carrying a ladder, a plank and a harp at once is fine: it's a game.
- Objects lie in the world where the engine puts them (the drop spots from
  `layout.ts` become 3D spots per place), and dropped ones fall with physics.
- The grassy bank's pile of treasure grows as you score, as now.

## Dying, getting lost, winning

- **Deaths** are short scenes from where you stand: the giant's hand, the
  goblins, the river's current. The 11 death paintings say what each one
  shows. Then the curtain falls, with no words, and the menu.
- **Lost**: the mist and a vision (above).
- **Winning**: the sleeping figure on the bank wakes. Then the tune.
- **The dragon** is the one place a little action fits: aim and throw the
  water before the fire reaches you. (Optional; the engine only needs `use`.)

## Controls everywhere

- **Laptop**: WASD or arrows, mouse look, E take, click use, G drop, 1–5 slots.
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
  effects.ts       what each `use` does to the world (ladder appears, trees fall)
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

What's genuinely hard, for anyone: **characters**. A good-looking, animated
Merlin, giant, dragon and trolls is the biggest piece of art work. Image-to-3D
plus Mixamo gets people-shaped characters a long way. The dragon (four legs
and wings) may need a bought or free model.

## Order of work

1. **Learn the pipeline on one place.** Install Blender. Claude writes a
   script that builds the grassy bank roughly, bakes its light and exports it.
   The game loads it and you can walk around. Proves Blender → glTF → Three.js.
2. **The whole map in grey boxes.** Every place as plain shapes at its spot,
   joined by paths and tunnels, with barriers, regions and the engine wired
   in. Playable from start to finish with stand-in objects. This settles the
   layout, the distances and the sight lines (the spire!) before any art.
3. **The first beautiful corner**: grassy bank, old stone wall, old wall and
   the ladder (where v2 began), fully modelled, textured and lit. **Then
   decide** whether the look works and how long a place takes.
4. **The meadows and forest**: the trees growing back, the witches, the mist.
5. **Underground**: the long lamp tunnel, the dragon, the long tunnel to the
   giant, the maze, the treasure room.
6. **The castle**: moat, courtyard, grand hall and its goblins,
   kitchen, dungeon, Merlin's lair.
7. **Deaths, visions, winning, sound**: music and fx carry over, plus
   footsteps, chopping and creaks.
8. **Phones and iPads**: performance pass, touch controls polished.

## Still to decide

- **How much action?** Puzzles only (the original), or a little danger: the
  dragon's fire, a goblin that chases you. Suggest: puzzles only at first.
- **Name**: a third button on the title screen, or its own page (`/3d`).
