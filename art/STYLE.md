# Merlin's Castle — art style guide

Every image is made in ChatGPT from two parts pasted together:

1. The **style block** below (scenes or objects), unchanged every time.
2. The image's own prompt from `prompts/`.

Attach the **anchor image(s)** to every request once we have them. Don't
rely on ChatGPT remembering an earlier conversation: the pasted style block
and the attached anchors are what keep 75 images looking like one world.

## Workflow

1. Start with `prompts/rooms/grassy-bank.md` (no anchor yet). Iterate in that
   chat until you love it. That image becomes **the anchor**: save it as
   `art/anchors/grassy-bank.png`.
2. For every later image, start a new chat (ideally inside a "Merlin's Castle
   art" ChatGPT Project). Attach the anchor, plus the closest existing scene
   if there is one (e.g. another cave for a cave). Then paste, in order:
   - the reference line below, so ChatGPT doesn't edit the anchor instead;
   - the style block (scene or object);
   - the image's prompt.

   > The attached image is a **style reference only**: match its painting
   > style, brushwork, level of detail and camera angle, but create a
   > completely new scene with the lighting described below. Don't copy its
   > content, layout or colours.

   For objects, say "create a single new object" instead of "a completely new
   scene".

3. Save the full-size original into `art/originals/<kind>/<id>.png`, named
   after the room or object id in `data/world.json`. A script will turn these
   into web-sized files in `public/art/`.
4. If something drifts (colours too saturated, angle too steep), say so in the
   same chat, e.g. "match the anchor's light and camera angle more closely".

## Scene style block

> Painterly semi-realistic fantasy illustration, like a storybook matte
> painting. Soft, natural, slightly dreamlike light; rich but gentle colours;
> fine brushwork detail; a faint haze in the distance. Calm and enchanted,
> never grim or gory. The world of a 1980s children's adventure game, retold
> with love.
>
> Camera: an elevated three-quarter view, about 30 degrees above the ground,
> looking **north**, as if hovering just above the southern edge of the place.
> The whole location is visible, like a stage set. North is at the top/back of
> the picture, south at the bottom/front edge, west on the left and east on
> the right. Paths, doors or tunnels that lead away must leave the picture on
> the matching side.
>
> Composition: landscape 3:2. The **bottom quarter** is simple, uncluttered
> foreground (grass, earth, flagstones or water) because text will cover it.
> The **middle** has open, fairly flat ground where small objects could rest.
> The main features sit in the **upper middle**. The top and bottom edges may
> be cropped, so nothing important there.
>
> Do not include: any text, letters, signs, frames or user interface; the
> player or any person unless described; loose portable objects (no ladders,
> ropes, keys, lamps, coins, tools or treasure lying around).

## Object style block

> A single object painted in the same painterly semi-realistic storybook style
> as the attached image. Square image. Three-quarter view from slightly above,
> lit softly from the upper left. The object is centred and fills most of the
> frame, with a small even margin, and the whole object is visible.
>
> It will be shown very small in the game, so give it a **clear, bold
> silhouette** and strong, readable shapes and colours, with less fine detail
> than a scene.
>
> **Transparent background.** No ground, cast shadow, glow, sparkles, text or
> other objects, unless the prompt asks for them. The game adds its own shadow
> and glow.

Objects use their own anchor: once the ladder is approved it becomes
`art/anchors/ladder.png`. Attach it (and the grassy bank anchor) for every
later object, so all 20 look like one set.

The game decides how big each object appears, so don't worry about scale
between objects. A ring and a ladder both fill their square.

## Palette and light

- Outdoors: warm summer afternoon, sun from the upper left (north-west), long
  soft shadows, honey-gold light, fresh greens, blue sky.
- Forest: dappled light, mist, deeper greens.
- Underground: dark blues and browns lit by fire, lamp or glowing magic.
- Castle: warm candlelight on grey stone, rich red/purple/gold fabrics.
- Merlin's magic: a recurring soft violet-and-gold glow with tiny light motes.
  It's a subtle signature in every scene.
- The original's highlighted words (grassy bank in green, golden spire in
  yellow, the dragon in red) should be the eye-catching colours in their scenes.

## Moment style block

For deaths, the lost scenes and victory (`prompts/moments/`). These are not
map views, so the camera rule doesn't apply.

> Painterly semi-realistic fantasy illustration, like a full-page picture in
> a storybook, in the same style, brushwork and level of detail as the
> attached image. Landscape 3:2. A single dramatic moment, composed freely for
> effect, with soft cinematic light. It is for children, so it's never gory or
> truly frightening: the mood is whimsical, eerie or bittersweet, like the
> "and that was the end of the adventure" page of a fairy tale. Keep the
> bottom quarter calm and simple, because text will cover it. No text or
> letters.

Where a moment shows the player (as a frog, a statue or a mouse), they are
small, seen from a distance or from behind, with no recognisable face.

## The "behind you" rule

The camera always faces north, so the south is behind the viewer:

- Things **far away to the south** (the golden spire seen across the river)
  are not shown. The text describes them.
- Things **at the south exit** (a creature guarding the south tunnel, a gate
  to the south) stand in the lower part of the picture **seen from behind**,
  facing into the scene. Their heads can turn in profile.
- South paths, tunnels and doors simply leave the bottom edge of the picture.
- A door or wall **directly behind** the viewer (the tower's stone, the oak
  door) is suggested by light or sound coming from the bottom edge, not
  painted.

## Things to keep consistent

- Merlin: a tall old wizard, long silver beard, deep blue robe and hat with
  faint silver stars (as in Drue's 2010 map sketch).
- The dragon: splendid, crimson-pink scales, violet wings, more magnificent
  than scary (as in the sketch).
- The golden spire: a slender gold spire on Merlin's castle. The camera always
  looks north, so only show it where the castle lies to the north or the
  sides. For anything behind the viewer (to the south), leave it out of the
  picture and let the text mention it.
