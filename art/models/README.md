# Model packs

The 3D models are built from these packs by Quaternius (`npm run models`, the
scripts in `art/blender/`). They're big, so they aren't kept in git: download
each one and unzip it into a folder of that name here. The game itself only
needs the `.glb` files already built into `src/three/models/`, so you only need
the packs to rebuild those.

| Folder                          | Pack                                                                                                    | Used for                                                 |
| ------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| `ultimate-nature`               | [Ultimate Nature](https://quaternius.com/packs/ultimatenature.html) (the Blender files)                 | Trees, in `land.py` (from `Blends/`)                     |
| `universal-base-characters`     | [Universal Base Characters](https://quaternius.com/packs/universalbasecharacters.html)                  | Heads and hair, in `merlin.py`, `witches.py`             |
| `modular-character-outfits`     | [Modular Character Outfits – Fantasy](https://quaternius.com/packs/modularcharacteroutfitsfantasy.html) | Outfits, in `merlin.py`, `witches.py`                    |
| `universal-animation-library-1` | [Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html)              | Animations, in `merlin.py`, `witches.py`                 |
| `universal-animation-library-2` | [Universal Animation Library 2](https://quaternius.com/packs/universalanimationlibrary2.html)           | Animations, in `merlin.py`, `witches.py`                 |
| `fantasy-props-megakit`         | [Fantasy Props MegaKit](https://quaternius.com/packs/fantasypropsmegakit.html)                          | Furniture, in `land.py`                                  |
| `medieval-village-megakit`      | [Medieval Village MegaKit](https://quaternius.com/packs/medievalvillagemegakit.html)                    | (None used yet)                                          |
| `ultimate-monsters`             | [Ultimate Monsters](https://quaternius.com/packs/ultimatemonsters.html) (the Blender files)             | The rabbits, in `rabbits.py` (from `Blends/Bunny.blend`) |
| `ultimate-crops`                | [Ultimate Crops](https://quaternius.com/packs/ultimatecrops.html) (the Blender files)                   | Toadstools, in `land.py` (from `Blends/`)                |
| `easy-enemy`                    | [Easy Enemy](https://quaternius.com/packs/easyenemy.html) (the Blender files)                           | (None used yet: `snake.py` takes its snake's colours)    |

The free (Standard) version of each is enough. Keep the folders inside each
pack as they come: the scripts read files such as
`modular-character-outfits/Exports/glTF (Godot-Unreal)/Outfits/Male_Ranger.gltf`.

Licence: CC0 1.0 (public domain), as Quaternius releases these packs: free to
use anywhere, credit not needed (but kindly given here).
