# Merlin's Castle

A remake of **Merlin's Castle**, the adventure game Anita Straker wrote for
the BBC Micro in 1983. Every room, object, message and quirk comes from her
original program; this version adds a painted picture for every place and
plays in the browser.

**Play it at [www.druewilding.com/merlins-castle](https://www.druewilding.com/merlins-castle/)**

You wake up on a grassy bank at a crossroads. Somewhere in this magic land
are objects and treasures; bring as many as you can back to the bank. Click
the compass (or use the arrow keys or N, S, E and W) to move, click objects to
pick them up, and click an object you're carrying (or press 1 to 5) to use
it. You can carry five things at a time.

There are two ways to play:

- **Illustrated**: painted scenes, objects you can see and drag, and music.
- **Classic**: the original 1983 teletext screen, with its colours, its
  beep and its victory tune. Switch between them at any time, even mid-game.

Games can be saved in your browser, and your best score is remembered.
You can also install it on your phone or computer (Add to Home Screen, or
Install in the browser's menu): it then opens like an app and downloads the
whole world, so it works without a connection.

## Credits

- **Original game**: Anita Straker, 1983, published by ESM. You can still
  play the original at
  [bbcmicro.co.uk](https://bbcmicro.co.uk/game.php?id=2164).
- **Remake**: Drue Wilding, who played it at school and never forgot it,
  built together with Claude (Anthropic).
- **Music**: "The Path of the Goblin King" by Kevin MacLeod
  ([incompetech.com](https://incompetech.com)), licensed under
  [Creative Commons: By Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Sound effects**: the magical ones (twinkles, harp and bells) were
  composed in code by Claude, in `scripts/make-sounds.js`; the rest are from
  [Kenney](https://kenney.nl) (CC0).
- **Pictures**: painted with ChatGPT from the prompts in `art/prompts`.
- **Fonts**: IM Fell English and Cinzel, from Google Fonts.

## Running it locally

You need Node 24.

```sh
npm install
npm run dev        # play at http://localhost:5173
npm test           # run the tests
npm run build      # build the static site into dist/
```

Changes reach `main` through pull requests, checked by
`.github/workflows/code-quality.yml`. Releases are made on purpose: running
**Release please** from the Actions tab opens a release pull request with the
changelog, and merging it publishes the release. Running **Deploy please**
(`.github/workflows/deploy-please.yml`) then builds the latest release and
deploys it to GitHub Pages; give it an older version to roll back.
Dependencies are updated monthly by `.github/workflows/update-please.yml`.

## How it's made

- `original/`: the tools that recovered the game from the original disk
  image: a disk extractor, a BBC BASIC detokeniser, and `convert.py`, which
  turns the program's DATA statements into `data/world.json`
  (`npm run world`). The disk image itself isn't committed; the
  `.gitignore` says how to fetch it.
- `data/world.json`: the whole game world: 40 rooms, 20 objects and every
  message.
- `src/engine/`: the game rules as a pure function,
  `act(world, state, command) → { state, events }`, faithful to the
  original down to its quirks.
- `src/classic/`: the teletext version.
- `src/illustrated/`: the painted version.
- `art/`: the art style guide and a prompt for every picture. `npm run art`
  picks the next picture to paint, copies its prompt to the clipboard and
  shows which reference images to attach. Full-size originals go in
  `art/originals/` (not committed) and are converted into `public/` for the
  game automatically, while `npm run dev` is running or with
  `npm run art:build`. See `art/prompts/README.md`.
- `scripts/service-worker.js`: what makes it work offline. The build fills
  in the list of files and writes `dist/sw.js`.
- `PLAN.md`: the decisions behind the remake.

The game's map, text and puzzles are Anita Straker's. The code in this
repository is ISC licensed.
