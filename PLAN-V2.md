# Merlin's Castle v2: pictures that change

In v1, using an object changes the words ("The ladder leans against the
wall.") and makes the exit glow, but the picture stays the same. Players miss
that something has opened up. In v2, a working object changes the picture
too: the ladder appears against the wall, the snake leaves the steps, Merlin
becomes a frog.

Only the Illustrated version changes. Classic stays as the original was.
Pictures have no words, so Danish needs nothing new.

## How it behaves

- **What counts as an effect**: an object that is in use (`state.using`) and
  opens an exit in the current room. Using something that does nothing here
  ("Nothing happens.") leaves the picture alone.
- **When it shows**: the moment the object is used, the scene **crossfades**
  (about 0.8 s, not the fade through black we use for moving) to the changed
  picture. The exit glows gold as it does now. With reduced motion, the
  picture swaps instantly.
- **How long it lasts**: as long as the rules say the way is open, which is
  until you leave the room (`using` is cleared). Come back and the wall is
  bare again, just as the original makes you use the ladder again.
- **Saving and loading**: `using` is already saved, so a loaded game shows the
  right picture.
- **Fatal exits too**: using the right object at a deadly exit is where the
  pictures are most fun: Merlin as a frog, the old woman turned to stone, the
  witches flying off to the moon.

### Two effects in one room

Five rooms have two: the grand hall, the mossy steps, the cave entrance, the
old wall and the giant.

Each of those five rooms gets one extra picture with **both effects**, so 5
more images, each made by editing a single-effect picture so they match.
(Showing only the most recent effect would be wrong at times: at the mossy
steps, the "ladder" picture would still have the snake on the steps after
the apple had sent it away.) The picture is chosen from the set of objects in
use, so the order doesn't matter. Until a both-effects picture is painted,
the game falls back to the most recent effect.

### Effects that happen behind you

The camera always looks north, so a south exit is behind the viewer. The
bottom quarter of every picture also sits under the text panel on wider
screens, so whatever we paint needs to rise above that. **Light tells the
story wherever it can**, and we repaint a base only where it can't.

| Room           | South exit         | Approach                                                                                                                                                             |
| -------------- | ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| yellow-flowers | rusty gate (key)   | **Repaint the base**, as you suggested: the tops of the rusty gate's iron spikes and arch rise up from the bottom edge, seen from behind. Then the variant opens it. |
| giant          | padlock (key)      | **Light tells it**: cool daylight spills up from the newly opened way south, across the tunnel floor.                                                                |
| tower          | stone (ring)       | **Light tells it**: the thin cracks of daylight become a flood of daylight from the bottom edge, lighting the whole room.                                            |
| oak-door       | door (key)         | **Light tells it**: the warm glow from behind becomes a broad shaft of golden light across the floor, with the shadow of an open door.                               |
| treasure-room  | hole (rope)        | **The rope tells it**: a rope tied round a pillar runs down and out of the bottom edge, towards the hole.                                                            |
| moat           | drawbridge (penny) | **The guards tell it**: they step aside, and one bites the penny and waves you through. Chains glint as the drawbridge lowers.                                       |

The other south exits (dungeon, dragon cave, dark tunnels, cave entrance,
deep river) are already in the picture.

## The pictures

There are 28 single effects and 5 combinations, so 33 new images, plus a
repainted yellow-flowers. They are named `<room>--<object>` and, for combinations,
`<room>--<object>+<object>` with the objects in alphabetical order.

| Image                     | What changes                                                                                         |
| ------------------------- | ---------------------------------------------------------------------------------------------------- |
| old-stone-wall--ladder    | The ladder (matching `items/ladder`) leans against the stone wall on the left, reaching the top.     |
| old-wall--ladder          | The same ladder, from this side, against the wall on the right.                                      |
| old-wall--lamp            | Warm lamplight shows the way into the small dark tunnel on the left.                                 |
| old-wall--ladder+lamp     | Both.                                                                                                |
| cave-entrance--broom      | The leaves are swept aside into heaps, and the cave mouth is open.                                   |
| cave-entrance--lamp       | Lamplight glows down the steps and into the tunnel.                                                  |
| cave-entrance--broom+lamp | Both.                                                                                                |
| dragon-cave--water        | The dragon's fire is now a harmless puff of grey smoke and steam. The dragon looks rather surprised. |
| dark-tunnels--lamp        | Warm lamplight fills the crossroads, with a faint musical shimmer in the air.                        |
| mountain-path--axe        | Stumps where the dense trees stood. The path runs on up the mountain.                                |
| rusty-gate--key           | The gate stands open, the mist parts, and you glimpse yellow flowers beyond.                         |
| yellow-flowers--key       | The gate at the bottom edge stands open (needs the repainted base).                                  |
| mossy-steps--apple        | The snake is gone from the steps, with just the tip of its tail slipping into the grass.             |
| mossy-steps--ladder       | The ladder is propped against the tower, up to the balcony.                                          |
| mossy-steps--apple+ladder | Both.                                                                                                |
| tower--ring               | Daylight floods in from behind and lights the room.                                                  |
| forest-witches--broom     | The witches rise above the trees on broomsticks towards a pale moon. The rabbits relax.              |
| maze--rope                | A rope is tied to the beam over the north passage and hangs ready to swing on.                       |
| treasure-room--rope       | A rope is tied round a pillar and leads off the bottom edge.                                         |
| trolls--harp              | The trolls dance, the north passage is clear, and golden notes float in the air.                     |
| oak-door--key             | A broad shaft of golden light and the shadow of an open door.                                        |
| giant--cake               | The giant sits munching cake, smiling, and the west tunnel is clear.                                 |
| giant--key                | Cool daylight spills up from the open way south, behind you.                                         |
| giant--cake+key           | Both.                                                                                                |
| deep-river--plank         | A plank reaches from the bank across the river. It must start above the bottom quarter.              |
| river-south-bank--plank   | A plank bridges the river in the upper middle.                                                       |
| moat--penny               | The guards step aside, and one bites the penny and waves you through.                                |
| merlins-lair--spell       | A large frog wearing Merlin's starry hat sits where he stood.                                        |
| wizards-kitchen--silver   | Merlin has gone to replace his button: the kitchen is empty and his pot bubbles on.                  |
| grand-hall--rope          | The west goblins are tied up together in a bundle by the west door, looking worried.                 |
| grand-hall--mask          | The mask floats in the air near the east goblins, who stare at it, baffled.                          |
| grand-hall--mask+rope     | Both.                                                                                                |
| dungeon--mirror           | The old woman is a grey stone statue in the same pose, among her own statues.                        |

The grand hall's pair does what you hoped: one picture says "the rope is for
the west goblins", the other says "the mask is for the east ones".

## Making the art

The key difference from v1 is that each variant is an **edit** of an existing
picture, not a new painting. The crossfade only looks magical if everything
else stays put.

- A new art kind, `effects`: prompts in `art/prompts/effects/`, originals in
  `art/originals/effects/`, web images in `public/art/effects/`.
  `npm run art` and `art:status` list them after the rooms, in exploring order.
- A new prompt header, `reference: edit`. `npm run art` attaches the room's
  original first and pastes something like: _"Edit the attached picture. Keep
  everything exactly as it is (composition, camera, light, colours, every
  stone and leaf) and change only this: …"_. There's no style block, since it
  tempts ChatGPT to repaint everything.
- Objects that appear (ladder, rope, plank) also attach their item cut-out
  with `match:`, so it's the same ladder you're carrying.
- Combinations attach the first single-effect picture to edit and the second
  to match.
- **Drift**: ChatGPT's edits sometimes shift colours or move things slightly.
  If one does, use ChatGPT's select tool to paint over just the area that
  should change. A crossfade hides small shifts, but not a moved wall.
- The repainted yellow-flowers replaces the v1 original, so it comes first.

## Code changes

Smaller than it sounds, because the engine already tracks everything needed.

1. **Engine** (`src/engine/engine.ts`): `effects(world, state): ItemId[]`, the
   objects in use that open an exit in this room, in order of use. It is
   pure and tested. When an object that is already in use is used again, it
   moves to the end of `using`, which only matters for the fallback.
2. **Tests**: no object opens two exits in one room (so `room--object` is
   unique), and `effects` works for none, one, two, an object used then
   dropped (the original's quirk: still in use, so still shown), and after
   moving.
3. **Art pipeline**: add `effects` to `KINDS` in `scripts/art.js`,
   `scripts/build-art.js` and `src/illustrated/art.ts`, plus the
   `reference: edit` wording.
4. **Picking the picture** (`sceneFor` in `src/illustrated/app.ts`): try the
   combination, then the most recent single effect, then the room. A missing
   image falls through, as with `grassy-bank-sleeping` today, so the game
   works however much is painted.
5. **Crossfade**: a second `<img>` layer over the scene that fades in, then
   becomes the scene. A use goes through it, and moving still uses the fade
   through black.
6. **Preload**: on arriving in a room, preload the effect pictures for objects
   you're carrying that work here, so the crossfade never waits.
7. **Drop spots** stay as they are, since the edits keep each room's floor.

Because missing pictures fall back gracefully, v2 can ship code first and
gain pictures batch by batch, like v1 did.

## Order of work

1. ~~Engine, tests and the art pipeline (no visible change yet).~~ ✅ `effects()`,
   the `effects` art kind with `reference: edit`, and all 33 prompts.
2. ~~Picture choice, crossfade and preload, tested with one effect:
   `old-stone-wall--ladder`, the one that started all this.~~ ✅
3. Repaint yellow-flowers.
4. Paint the rest in exploring order, releasing as we go.
5. Add a Decisions row to PLAN.md. v1 said "no objects painted into rooms",
   and v2 makes a deliberate exception for objects in use.

## Decided

- **Both effects** get their own picture in the five rooms that have two.
- **The mask** floats near the east goblins in the picture, and they look
  confused. There's no eye-hole overlay.
- **A used object you're still carrying** shows both in the picture and in
  your slot, as the original's rules allow. The slot's yellow "in use" glow
  is enough.
- **Behind you**: light tells the story wherever it can (tower, oak door,
  giant). Only yellow-flowers gets a repainted base.
