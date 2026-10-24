---
name: magical-creature
description: Build a creature for Merlin's Castle 3D (a beast, a goblin, a troll, a giant) as a Blender script and a game class, from its painting to standing in its place, moving, and passing review. Use when making or reworking any creature model in art/blender/ and its src/three/ behaviour.
---

# Making a magical creature

How the dragon was made (`art/blender/dragon.py`, `src/three/dragon.ts`), written
down so the next creature goes faster. Follow the steps in order; each ends with
something to look at before going on.

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
  Library's clips, as `merlin.py`, `guards.py` and `witches.py` do. Add our own
  pieces with `c.skinned(...)`, weighted to its bones. Scale the whole of it for
  a giant (and its clips play at any size). Turn bones on top of clips in code,
  as `guards.ts` turns their heads.
- **Not human-shaped** (a beast): build it all in Blender from code, with its
  own skeleton and no clips, as `dragon.py` does. The game turns its bones.

## 2. The model, in code

Conventions (`art/blender/common.py`):

- Metres; z up; it stands on z = 0, facing -y. Exported, three.js sees it
  facing +z, y up, its left +x.
- Vertex colours, one material. Names use hyphens (three.js drops dots).
- Make it at whatever size is easy, then scale every point and bone to its
  height (`TALL`) **before** making the objects. (Applying a transform to an
  armature with children afterwards scales them twice.)
- Print its point count and scale; keep the `.glb` well under 1 MB.

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

Skeleton (a beast's own):

- Chains along the body tube by distance along it: tail bones, a body bone, neck
  bones, head, jaw. Weights blend between neighbouring bones near the ends of
  each piece. Legs ride on the body bone (still).
- Add an empty bone where things come out: a `mouth` at the nose, pointing
  forward, for fire, breath and aim.

Previews: render several views with `--preview` (front, side, back, plus
close-ups of the head, horns and legs), and combine them with `magick` to look
at side by side.

## 3. In its place (`art/blender/land.py`)

- Choose its spot, which way it faces, and where its action goes. Export them
  to `land.json` (as `"dragon"` is).
- Make it solid: circles of its outline (`under_circle` underground,
  `solid_circle` on the land), scaled as the model is.
- Clear the place round it. Keep stalactites away from its head and stalagmites
  away from every circle of its outline, its tail included.
- Check the roof: its height against the roof's curve where its head and horns
  are, and leave it a little room.
- The exit it blocks stays an `obstacle(...)`; the creature only shows why.

## 4. In the game (`src/three/<creature>.ts`)

- A class: a constructor taking the scene, its model, its spot, `reducedMotion`
  and callbacks for sounds. Then `update(dt, eye, here)` and the verbs the
  story needs (the dragon's are `douse`, `relight` and `blaze`).
- Skinned meshes: set `frustumCulled = false` (bones move it out of its
  bounds). Hide it when far off.
- Turning bones about the **model's** axes: keep each bone's rest quaternion
  and its rest rotation in the model, Q. Each frame, set
  `bone.quaternion = rest * Q⁻¹ * turn * Q`. The turn then composes down the
  chain, and a child's turn rides on its parents'. Order matters: premultiply
  in the order you want them applied. To keep a child's aim while its parent
  tips, as the mouth bone does while the head throws back, give the child the
  opposite turn.
- Axes in model space: +x across (a positive turn about it pitches forward and
  down; a jaw opens with a positive angle), +y up, +z ahead.
- Wiring in `main.ts`: load its `.glb` with the others, then make it.
  - Find its exit's shape with `shapeOf.get("<place> <dir>")`, and add it to the
    shapes `inUse()` may open.
  - Call its verbs from `inUse()`. When loading (`instantly`), it's straight to
    the end state, with no animation.
  - Call `update` from the frame loop. React to `player.onBump(exit)` for "you
    tried to go past".
  - Add it to `window.world` (the `?debug` object) for testing.
- **Make it obvious.** The way's shut the moment you arrive, and again the
  moment you try it: no waiting for a timer.
- **Keep it gentle** (storybook): fire across the way, never at you.
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
hiss for steam), list them in `src/three/sounds.json`, and run
`npm run art:build`.

## 5. Check it

- `test/<creature>.test.ts`: it blocks the right exit; it stands in its place,
  clear of the walls; its effect lands in front of the obstacle; the ways across
  its place stay clear of its outline (more than the player's body plus a
  margin).
- Screenshots: a temporary `*.t.mjs` in the repo root (webkit, English,
  `/3d?debug&at=x,z,yaw`, wait for `window.world?.player`, then delete it).
  For close-ups, render from your own camera inside `page.evaluate`, with
  `renderer.render(scene, cam)` then `canvas.toDataURL()`, placed with
  `model.localToWorld`.
- Flicker: cast rays through the suspect pixels against the named meshes, and
  report pairs of hits under a centimetre apart with parallel normals. Opposite
  normals mean a folded or doubled face; equal ones mean coplanar overlap. Fix
  the geometry so it doesn't overlap; moving faces apart alone isn't enough.
- Drive the story for real: give yourself the object (`items.restart` with
  `itemLocations.<id> = "carried"`), press keys with `KeyboardEvent`, and log
  its state over time.
- Then `npx prettier --check src test`, `npx eslint src test`,
  `npx tsc --noEmit -p .` and `npx vitest run`.

## What the review caught on the dragon (check these first)

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
