// Object pictures are squares with see-through padding, so when objects pile
// up, one picture's padding can cover another object. Clicks only count where
// a picture is actually painted, or very near it, so thin or gappy objects
// (the ladder's rungs, the key) are still easy to hit.

const SIZE = 64;
const REACH = 4; // how far beyond the painted pixels still counts, out of SIZE
const masks = new Map<string, Uint8Array | null>(); // null while loading

// Painted pixels, grown by REACH in every direction.
export function grow(painted: Uint8Array, size = SIZE, reach = REACH): Uint8Array {
  const out = new Uint8Array(size * size);
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (!painted[y * size + x]) continue;
      for (let dy = -reach; dy <= reach; dy++) {
        for (let dx = -reach; dx <= reach; dx++) {
          const nx = x + dx;
          const ny = y + dy;
          if (dx * dx + dy * dy <= reach * reach && nx >= 0 && ny >= 0 && nx < size && ny < size)
            out[ny * size + nx] = 1;
        }
      }
    }
  }
  return out;
}

export function loadMask(url: string) {
  if (masks.has(url)) return;
  masks.set(url, null);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = SIZE;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) return;
    context.drawImage(img, 0, 0, SIZE, SIZE);
    const pixels = context.getImageData(0, 0, SIZE, SIZE).data;
    masks.set(url, grow(Uint8Array.from({ length: SIZE * SIZE }, (_, i) => (pixels[i * 4 + 3] > 40 ? 1 : 0))));
  };
  img.src = url;
}

// Is the picture painted at this point on the screen? Objects without a
// picture, or whose mask hasn't loaded yet, count everywhere inside their box.
export function paintedAt(el: HTMLElement, x: number, y: number): boolean {
  const rect = el.getBoundingClientRect();
  if (x < rect.left || x >= rect.right || y < rect.top || y >= rect.bottom) return false;
  const src = el.querySelector("img")?.getAttribute("src");
  const mask = src ? masks.get(src) : null;
  if (!mask) return true;
  const u = Math.floor(((x - rect.left) / rect.width) * SIZE);
  const v = Math.floor(((y - rect.top) / rect.height) * SIZE);
  return mask[v * SIZE + u] === 1;
}

// The frontmost object painted at this point, if any.
export function thingAt(things: HTMLElement[], x: number, y: number): HTMLElement | undefined {
  return [...things]
    .reverse()
    .sort((a, b) => Number(b.style.zIndex) - Number(a.style.zIndex))
    .find((el) => paintedAt(el, x, y));
}
