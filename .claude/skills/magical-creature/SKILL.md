---
name: magical-creature
description: Build a creature for Merlin's Castle 3D (a beast, a goblin, a troll, a giant) as a Blender script and a game class, from its painting to standing in its place, moving, and passing review. Use when making or reworking any creature model in art/blender/ and its src/three/ behaviour.
---

# Making a magical creature

How the dragon (`art/blender/dragon.py`, `src/three/dragon.ts`) and the trolls
(`art/blender/trolls.py`, `src/three/trolls.ts`) were made, written down so the
next creature goes faster. The dragon is the beast route, built from scratch;
the trolls are the human-shaped route, built on the kit and its clips. Follow
the steps in order; each ends with something to look at before going on.

Keep the README and PLAN-V3 spoiler-free: never write there which object gets you
past a creature. Commit messages may.

## 1. Look, and decide the route

- Read its painting (`art/originals/rooms/<place>.png`) and its row in
  `docs/models.md` (what it must do). Note its colours, shape, posture and what
  moves.
- Read its place in `data/world.json`: the exit it blocks, the object that gets
  you past, the messages.
- Check the packs (`art/models/README.md`). Free models elsewhere rarely match
  the painting or the style; the user prefers ours.
- **Human-shaped** (goblins, trolls, a giant): start from Quaternius's base
  characters and outfits on their one skeleton, with the Universal Animation
  Library's clips, as `merlin.py`, `guards.py`, `witches.py` and `trolls.py`
  do. Follow 2b.
- **Not human-shaped** (a beast): build it all in Blender from code, with its
  own skeleton and no clips, as `dragon.py` does. The game turns its bones.
  Follow 2a.
- More than one of them (a band of goblins, a family of trolls): plan from the
  start for each to look different and for them to fill their place (see
  "Many of them" in 2b).

## 2. The model, in code

Conventions, for both routes (`art/blender/common.py`):

- Metres; z up; it stands on z = 0, facing -y. Exported, three.js sees it
  facing +z, y up, its left +x.
- Vertex colours, one material. Names use hyphens (three.js drops dots).
- Print its point count and scale; keep the `.glb` well under 1 MB.
- Previews: render several views with `--preview` (front, side, back, plus
  close-ups of the head and anything fiddly; for the kit route, also each of
  its looks, sitting or posed as its clips have it, and blinking), and combine
  them with `magick` to look at side by side.

### 2a. A beast, from scratch

- Make it at whatever size is easy, then scale every point and bone to its
  height (`TALL`) **before** making the objects. (Applying a transform to an
  armature with children afterwards scales them twice.)

Shapes (all in `dragon.py`, reuse them):

- `spline(points)`: a smooth curve through points, each with its radii,
  evenly sampled. `frames(samples, up)`: rotation-minimising frames, so a tube
  never twists. `tube(...)`: rings along it, with colour, bone weights and
  scale coordinates for each point.
- Body, neck and tail are **one** tube (no joins to show). Legs, toes, horns,
  spars: their own tubes.
- **Every part grows out of what it's on.** Start a limb's tube well inside the
  body, straight above where it comes out (so it also runs the right way for its
  scales). Toes start inside the foot, claws inside the toe, horns sunk into the
  skull (`on_skull`). An open tube end that shows is a bug.
- **Close every opening.** Cap the nose and the chin. Give the upper jaw lips
  that wrap down past the mouth line over the lower jaw. Close the back of the
  skull. From any angle, there should be no hole to see into.
- Beasts' legs: a big thigh, the knee forward, a long shin back to a hock high
  off the ground, a long foot down to the toes. Front legs: a heavy shoulder,
  the elbow back, a forearm thick at the elbow slimming to the wrist. Straight
  even cylinders look like human legs.
- Membranes (wings): their own mesh, triangle panels subdivided, scalloped
  between the fingertips, with a little billow. Materials are double-sided, so
  one layer is enough: never two coplanar layers.
- Anything the game bends along a path each frame (the snake's body): clamp
  every lookup by position along it to the ends of its arrays. A point a hair
  past the end rounds to index -1 and turns the whole mesh NaN.

Skin:

- Colours by where a point is round its tube (`a`: 0 its back, pi its belly):
  darker down its back, its own colour on its sides, pale plates under its
  belly with darker seams, and a little noise.
- Scales are drawn by the game, from two UV sets the model carries (`Skinned`):
  UV0 = (cos a, sin a), which blends smoothly all the way round; UV1 = (along,
  round), both counted in scales. Round 0 means no scales (teeth, claws, horns,
  the inside of the mouth). Round > 0 means scales but not on its belly; < 0
  means scales all round. Make the along sign run so each scale lies over the
  one behind: from the tail to the head on the body, and **down** the legs.
  glTF flips V on export, so the shader uses 1 - v.

Skeleton:

- Chains along the body tube by distance along it: tail bones, a body bone, neck
  bones, head, jaw. Weights blend between neighbouring bones near the ends of
  each piece. Legs ride on the body bone (still).
- Add an empty bone where things come out: a `mouth` at the nose, pointing
  forward, for fire, breath and aim.

### 2b. Human-shaped, from the kit

The body:

- One Universal Base Character's whole body, reshaped in code (`trolls.py`'s
  `grown`, `faced`, `trolled`). Scale the whole of it for a giant; its clips
  play at any size.
- **The kit's mesh is split along its UV seams**: each point on a seam is two
  or three. Move them as one (`welded`), or the seams open into holes (the
  trolls' waist had a dark band that was really a gap).
- Bulk it out by moving points along their normals, by how much each is
  weighted to the limb or trunk bones. Keep bulges to the part that moves as
  one: a belly on the tummy, not over the hips, which bend their own way and
  stretch it when it dances.
- **Go gently with exaggeration.** The trolls' bellies took four rounds of
  shrinking. Start smaller than you think, and offer more.
- Smooth away the kit hero's muscles (a six-pack reads wrong on a troll), and
  replace its normal and roughness maps: the kit's are muscles and shiny
  briefs. Clear its colour masks too, or the game darkens the skin by them.
- Variations as **shape keys** on the body (bigger belly, fatter all over, a
  long nose, big ears, `blink`), mixed per creature in the game. A shape key
  that fattens must leave alone where the clips rest a hand (the fronts of the
  thighs, sitting).
- A friendly face: lift the corners of the mouth and push the cheeks up and
  out; arch the brows over each eye (tilted ones look worried); keep the nose
  clear of the mouth.
- Its eyes: a `blink` shape key, with the lids meeting a little below the
  middle. Eye colour by tinting the iris on the kit's eye picture (find its
  middle and size in its UVs).

Its own pieces (hair, moss, a beard, clothes):

- Skin them to the kit's skeleton with `c.skinned(...)`, each blade or piece
  weighted as the skin it grows from. Give them the body's shape keys too
  (`grow_moss(..., keys=...)`), or they float or sink when it's fatter.
- **What hangs must hang from the right bone.** Grass growing from the thighs
  swings forward with them when it sits, and lies along its lap. To hang
  straight down whatever it does, weight it to the hips (`troll-fringe`).
- Look for gaps from low down and while it sits: between the legs, under the
  arms, the back of the neck. Cover them with something that belongs (a
  fringe of moss, a beard), not by moving the body.

**The clips are made for the kit's slim hero.** Anything bigger (hands,
thighs, a belly) ends up inside the skin where the clip puts a hand. Fix it in
the game (section 4), never by squashing the body round the hand.

Many of them:

- One table of looks in the game (`LOOKS` in `trolls.ts`): hair, beard, shape
  keys, head size, skin and moss tints, eye colour. The model carries every
  piece once; each creature shows its own.
- Different sizes, to fill the place: the user wanted them to take up space.
  Size their seats, solid circles and the clearing round them to match (3).

## 3. In its place (`art/blender/land.py`)

- Choose its spot, which way it faces, and where its action goes. Export them
  to `land.json` (as `"dragon"` and `"trolls"` are).
- Make it solid: circles of its outline (`under_circle` underground,
  `solid_circle` on the land), scaled as the model is.
- Clear the place round it. Keep stalactites away from its head and stalagmites
  away from every circle of its outline, its tail included. Do it so every
  other cave stays exactly as it was.
- Check the roof: its height against the roof's curve where its head and horns
  are, and leave it a little room.
- The exit it blocks stays an `obstacle(...)`; the creature only shows why.

## 4. In the game (`src/three/<creature>.ts`)

- A class: a constructor taking the scene, its model, its spot, `reducedMotion`
  and callbacks for sounds. Then `update(dt, eye, here)` and the verbs the
  story needs (the dragon's are `douse`, `relight` and `blaze`; the trolls',
  `dance`).
- Skinned meshes: set `frustumCulled = false` (bones move it out of its
  bounds). Hide it when far off. Several from one model: `clone` from
  `SkeletonUtils`, each with its own mixer.
- Turning bones about the **model's** axes: keep each bone's rest quaternion
  and its rest rotation in the model, Q. Each frame, set
  `bone.quaternion = rest * Q⁻¹ * turn * Q`. The turn then composes down the
  chain, and a child's turn rides on its parents'. Order matters: premultiply
  in the order you want them applied. To keep a child's aim while its parent
  tips, as the mouth bone does while the head throws back, give the child the
  opposite turn.
- Axes in model space: +x across (a positive turn about it pitches forward and
  down; a jaw opens with a positive angle), +y up, +z ahead.

On top of clips (the kit route):

- **Put back the clip's pose before adding to it.** The mixer only sets a
  bone when its clip moves it, so a turn added each frame piles on the last
  (the trolls' hands drifted up to their faces in a second). After
  `mixer.update`, keep each bone you change (`armsPosed`), change it, and copy
  it back before the next update (`shape` / `unshape` in `trolls.ts`).
- Clips set every bone's size and position each frame, so anything you change
  there goes back every frame, after the mixer:
  - **Bigger hands, head:** scale their bones, not the mesh. Then the fingers
    bend where their joints are. A bigger hand mesh on the hero's joints bends
    mid-finger and folds through the palm.
  - **Shorter fingers:** pull their middle and end joints in towards the
    knuckles (`FINGERS`).
- **Keep hands out of the body**, adjusting the clip's arms in world space:
  sitting, lift each forearm at the elbow and turn the hand back as much, so it
  lies flat on the lap (`LAP`); dancing, swing the upper arms out (`SPREAD`).
  More for the fatter ones. **Blend the adjustments through every change of
  clip**: standing up, they push off their knees, and if the lap lift drops
  before the spread comes in, the wrist goes through the thigh.
- **Aim the head from where its face points now**, not from the body's angle
  to you: the clip already turns the head (the trolls all looked a little to
  your right). Measure its face's direction each frame and turn the rest of the
  way, up to how far its neck goes.
- **Make it alive:** glances to either side and back every few seconds, a blink
  now and then (sometimes two together).
- **Don't all do the same thing at once.** One asks at a time, for a few
  seconds each; the rest idle. Stagger shared moments (one after another getting
  up), and start each one's clip at a different time.

Wiring in `main.ts`:

- Load its `.glb` with the others, then make it.
- Find its exit's shape with `shapeOf.get("<place> <dir>")`, and add it to the
  shapes `inUse()` may open.
- Call its verbs from `inUse()`. When loading (`instantly`), it's straight to
  the end state, with no animation.
- Call `update` from the frame loop. React to `player.onBump(exit)` for "you
  tried to go past".
- Add it to `window.world` (the `?debug` object) for testing.

Behaviour:

- **Make it obvious.** The way's shut the moment you arrive, and again the
  moment you try it: no waiting for a timer.
- **Keep it gentle** (storybook): fire across the way, never at you; a spell is
  a swirl of twinkles round your head.
- Reduced motion: posed once, still, with its effect hanging in the air.

Effects (sprites):

- A pool of sprites, each with its own `SpriteMaterial`, using `puff()` from
  `smoke.ts`. Fire uses additive blending, growing and cooling yellow → orange
  → red. Steam and smoke use normal blending and rise slowly.
- **Keep sprites out of the rock.** A big sprite cut by a wall shows hard
  stripes. Lift it off the floor by its size, and fade it as it nears the walls
  and roof (the cave's shape comes from `land.halls`).
- Lights: add any light at start-up and keep it in the scene. Change its
  intensity, never the number of lights (that makes every material rebuild).

Sounds: synthesise them in `scripts/make-sounds.js` (filtered noise for fire, a
hiss for steam, a jig, a twinkling spell), list them in `src/three/sounds.json`,
and run `npm run art:build`.

## 5. Check it

- `test/<creature>.test.ts`: it blocks the right exit; it stands in its place,
  clear of the walls; its effect lands in front of the obstacle; the ways across
  its place stay clear of its outline (more than the player's body plus a
  margin).
- Screenshots: a temporary `*.t.mjs` in the repo root, run against
  `npx vite --port 5179`. Launch with `chromium.launch({ channel: "chrome" })`
  (Playwright's own browsers aren't installed), English,
  `/3d?debug&at=x,z,yaw`, wait for `window.world?.player`, then delete the
  script and stop vite.
  For close-ups, render from your own camera inside `page.evaluate`, with
  `renderer.render(scene, cam)` then `canvas.toDataURL()`, placed with
  `model.localToWorld`. Look from where the user would stand, and from low
  down.
- Flicker: cast rays through the suspect pixels against the named meshes, and
  report pairs of hits under a centimetre apart with parallel normals. Opposite
  normals mean a folded or doubled face; equal ones mean coplanar overlap. Fix
  the geometry so it doesn't overlap; moving faces apart alone isn't enough.
- **Parts through the body:** measure, don't eyeball. Over a few seconds of
  every clip, for every creature, test each fingertip (and anything else that
  swings close) for being inside the skin, and count. Then **film the changes
  between clips** (getting up, sitting down) frame by frame, from the user's
  view: the measuring was unreliable there, and that's where the wrist went
  through the leg.
- Run it for a good while: anything added each frame shows only after a
  second or more (the drifting hands), and timers only after they fire twice.
- Drive the story for real: give yourself the object (`items.restart` with
  `itemLocations.<id> = "carried"`), press keys with `KeyboardEvent`, and log
  its state over time.
- Watch the console for warnings (a NaN mesh names no one: find it by its
  point count).
- Then `npx prettier --check src test`, `npx eslint src test`,
  `npx tsc --noEmit -p .` and `npx vitest run`.

## What the review caught on the dragon (a beast)

- The jaw opened upwards (wrong sign); the head should tip back as it opens.
- Its tail passed through a stalagmite: clear the place by its outline.
- It breathed on a timer: make it immediate, on arriving and on bumping the way.
- Horns, front legs, toes and claws weren't attached: grow every part from
  inside.
- Sprites striped the walls: fade them near the rock.
- Legs looked human: shape them like a beast's.
- Plain skin looked like a toy: give it scales, small and tight, running the
  right way on every part.
- The mouth looked hollow: close the nose and chin, add lips, rest the jaw just
  open enough to show the teeth.
- Doused, it hissed and steamed again every couple of seconds: a one-off
  moment (a hiss, a burst of steam) must reset its own timer when it fires,
  not rely on the state it moves to. Drive it and log each sound for a good
  while after, not just the first few seconds.

## What the review caught on the trolls (human-shaped)

- All alike, all doing the same thing: give each its own look, and take turns.
- Fingers folded through their hands, and were too long: scale hands by their
  bones, shorten the finger joints in the game.
- Not friendly enough: lift the smile, arch the brows, smooth the muscles.
- A hole at the waist: the kit's seams opened; weld them.
- They all looked a little to your right: aim from where the face points now.
- They never blinked: add a blink shape key, and glances.
- Pot bellies too big, and stretching when dancing: smaller, higher, off the
  hips. It took four rounds.
- Hands and thumbs inside bellies and thighs: lift the forearms sitting, swing
  the arms out dancing; and keep the fronts of the thighs slim.
- The wrist through the leg, standing up: blend the arm adjustments through
  every change of clip.
- A gap to see into between the legs: a fringe of moss, hung from the hips.
- Too small for their big cave: size them up, and their boulders with them.
