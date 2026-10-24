---
name: magical-item
description: Build an object you find and carry in Merlin's Castle 3D (the cake, the mask, the harp, the mirror, the ring, the pearl and so on) as a model in art/blender/items.py, dressed in the game, from its painting to lying on the ground where it's easy to spot. Use when making or reworking any item model.
---

# Making an object to find and carry

How the objects were made (`art/blender/items.py`, dressed in
`src/three/main.ts`), written down so the next one goes faster. The water's
flask is the newest example; the lamp shows the same see-through parts.

Keep the README and PLAN-V3 spoiler-free: never write there where an object is
used. Commit messages may.

## 1. Look

- Its painting: `art/originals/items/<id>.png`. Note its shape, its colours,
  what it's made of (wood, brass, glass, cork, cloth), and what makes it read
  as itself at a glance.
- Its entry in `data/world.json` (`items.<id>`): its id, which is also its
  model's name, and where it starts.
- Anything it needs to do in the game beyond lying there and being carried
  (lit, thrown, hung up, propped against a wall): find where the game does it
  (`main.ts`, and its own file, e.g. `lantern.ts`, `ladder.ts`, `rope.ts`).
- Most objects are built from code. A pack model (`art/models/README.md`)
  only if it matches the painting and the style.

## 2. The model, in `items.py`

Add it after the last object, before `if out:`, and add its name to the list
in the file's header comment.

Conventions:

- Metres; z up. It lies as it would on the ground, its middle at the origin,
  its underside at z = 0, its length along y (the game turns it as it lands).
  Something that stands (the lamp, the water) stands up.
- **Big, so you can spot it:** a key or a coin about 30–35 cm, a lamp or a
  flask 50–80 cm. Build it at its natural proportions, then scale every part
  with one `<NAME>_SIZE` (`part.data.transform(Matrix.Scale(SIZE, 4))`), so it's
  easy to change.
- Vertex colours, from `c.linear("#hex")` constants named for what they are
  (`CORK`, `CORK_DARK`, `BRASS_LIGHT`). Mottle them with `noise.noise` and
  `c.vary`, in a small function per material (`brass(p)`, `corky(p, t)`,
  `rusty(p)`): rubbed, worn, speckled, lighter where it catches the light.
- `outward(obj)` on every opaque part: the glow round what you point at grows
  out along its normals.
- A block comment before it, as the others have: "as in its picture", what it
  looks like from bottom to top, and its size and why.

Shapes to reuse (all in `items.py`):

- `lathe(builder, profile, colour, sides)`: anything turned round its middle
  (flasks, lamps, cups, knobs, a cork). The profile is (radius, z) from the
  bottom up; a radius of 0 closes it there. Build the profile from small
  pieces (`base + round_ + neck + lip`), each a list comprehension.
- `round_tube(...)` and `tube(...)`: handles, wires, rims, bars along a path.
  `roped(...)` for rope and twine.
- `box(...)` and `lamp_box(...)`: flat-shaded blocks. `builder.blob(...)`:
  rivets, knobs, beads.
- Faces built by hand, ring by ring (the penny, the emerald, the apple), when
  nothing above fits.
- Colour from its painting (`face_at` on the penny) when it has a picture on
  it.

**See-through parts** (glass, water, a flame): build each with its own
`c.Builder()` and name it `<id>-<part>` (`water-glass`, `water-inside`,
`lamp-glass`, `lamp-flame`). Parent them to the opaque part named `<id>`, so
the game finds the object by its id and its parts travel with it. Don't
`outward()` a single-surface glass shell. Keep a liquid a few millimetres
inside its glass (`WALL`), so they never touch.

Build it with `npm run models -- items` (about 2 s; `--preview` renders all of
them at once, which is little use for one object, so look at it in the game).

## 3. Dressing it in the game (`main.ts`)

Opaque parts need nothing: they get the shared vertex-colour material. Dress
the others after the models load, beside the emerald, the lamp and the water:

- **Glass:** `MeshPhysicalMaterial`, `transparent`, low `opacity` (0.1–0.2),
  `roughness` near 0, `envMap: shine` (the room reflections, made once and
  shared), `side: DoubleSide`, `depthWrite: false`, and `renderOrder = 1`, so
  what's inside is drawn first. Flat opacity looks like a haze: brighten and
  thicken it towards its edges, where you look through more of it, with an
  `onBeforeCompile` before `#include <opaque_fragment>` (as the water's glass
  does). Assign the material to a `const` first, so TypeScript knows its type.
- **Liquid or a gem:** a strong, saturated colour, mostly opaque, with a
  little `emissive` of its own colour, so it still reads in the shade.
- **A flame or a glow:** `MeshBasicMaterial`, `toneMapped: false`.
- Metal: `metalness` and `roughness` a little, as `dressLamp` gives brass.

The game lays it down (`items.ts`'s `lay`), turns it, rests it on the ground,
glows round it when you point at it, and shows its painting in your slots: no
code needed for any of that.

## 4. Check it

- Render it in the game from your own camera: a temporary `*.t.mjs` in the
  repo root (webkit, English, `/3d?debug`, wait for `window.world?.player`).
  Find it with `window.world.items.lyingAt("<id>")`, then render
  `renderer.render(scene, cam)` and `toDataURL()` from about 1 m (close up),
  about 5 m at standing height (can you spot it?) and further off. Combine
  them with `magick ... +append` and look side by side. Delete the script.
- Compare it with its painting: the colour first, then its shape.
- Where it starts is random, so look at it on grass, on a path, and somewhere
  dark (underground) if it can be there.
- Then `npx prettier --check src test`, `npx eslint src test`,
  `npx tsc --noEmit -p .` and `npx vitest run`.

## What the first look at the water caught (check these first)

- **Too small:** it has to be easy to spot from a few metres off. Bigger than
  life, with one size constant to change.
- **Washed-out colour:** light blue water with reflections on top looked
  white. Saturate it, and give it a little glow of its own.
- **Glass like a flat haze:** clearer face on, whiter and more solid at its
  edges.
