// The words on the sign in the witches' clearing (its wood: art/blender/
// land.py), painted on in your language: a line on each of its planks, in
// pale paint, a little uneven, as if by hand, and worn.

import { CanvasTexture, Mesh, MeshStandardMaterial, PlaneGeometry, type Scene, SRGBColorSpace } from "three";

import { T } from "../shared/strings";

const PX = 512; // the painting's pixels across (its height in proportion)
const PAINT = "#ebe2c6";
const FONT = '"IM Fell English", Georgia, serif';
// Each plank's middle, down the painted face (as a share of its height), as
// land.py nails them; and how much of the face's height a line may fill.
const PLANKS = [0.22, 0.78];
const INK = 0.34;

export interface SignSpot {
  at: number[]; // its face's middle [x, y, z]
  facing: number[]; // which way it faces [x, z]
  tilt: number; // radians it's askew (rolled, its right end up)
  size: number[]; // its face, across and up, in metres
}

export async function paintSign(scene: Scene, spot: SignSpot, lines: string[] = T.witchesSign) {
  const [wide, tall] = spot.size;
  const canvas = document.createElement("canvas");
  canvas.width = PX;
  canvas.height = Math.round((PX * tall) / wide);
  const pen = canvas.getContext("2d")!;
  // (The page's own lettering, if it can be had; else Georgia.)
  await document.fonts.load(`64px ${FONT}`).catch(() => undefined);

  // A seeded wobble, so the sign's painted the same each time.
  let seed = 7;
  const wobble = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1;

  const h = canvas.height;
  pen.fillStyle = PAINT;
  pen.textBaseline = "alphabetic";
  lines.forEach((line, k) => {
    const middle = h * (PLANKS[k] ?? (k + 0.5) / lines.length);
    // As big as fits on its plank, along it, and up it from the bottom of
    // its lowest letter to the top of its tallest (not the font's own
    // height: "f" and "h" reach above that).
    let size = 100;
    pen.font = `${size}px ${FONT}`;
    let ink = pen.measureText(line);
    size *= Math.min((PX * 0.92) / ink.width, (h * INK) / (ink.actualBoundingBoxAscent + ink.actualBoundingBoxDescent));
    pen.font = `${size}px ${FONT}`;
    ink = pen.measureText(line);
    // (Its ink centred on the plank.)
    const baseline = middle + (ink.actualBoundingBoxAscent - ink.actualBoundingBoxDescent) / 2;
    let x = (PX - ink.width) / 2;
    for (const letter of line) {
      pen.save();
      pen.translate(x, baseline + wobble() * size * 0.02);
      pen.rotate(wobble() * 0.05);
      pen.fillText(letter, 0, 0);
      pen.restore();
      x += pen.measureText(letter).width;
    }
  });
  // Worn: flecks of the paint gone, here and there.
  pen.globalCompositeOperation = "destination-out";
  for (let i = 0; i < 260; i++) {
    pen.globalAlpha = 0.3 + 0.7 * Math.abs(wobble());
    pen.beginPath();
    pen.arc((wobble() * 0.5 + 0.5) * PX, (wobble() * 0.5 + 0.5) * h, 0.6 + 2.2 * Math.abs(wobble()), 0, Math.PI * 2);
    pen.fill();
  }

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.anisotropy = 4;
  const words = new Mesh(
    new PlaneGeometry(wide, tall),
    new MeshStandardMaterial({ map: texture, transparent: true, roughness: 0.9, depthWrite: false })
  );
  const [x, y, z] = spot.at;
  words.position.set(x, y, z);
  words.rotation.order = "YXZ";
  words.rotation.set(0, Math.atan2(spot.facing[0], spot.facing[1]), spot.tilt);
  words.receiveShadow = true;
  scene.add(words);
  return words;
}
