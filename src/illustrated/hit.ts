// Object pictures are squares with see-through padding, so when objects pile
// up, one picture's padding can cover another object. Clicks only count where
// a picture is actually painted.

const SIZE = 64;
const masks = new Map<string, Uint8ClampedArray | null>(); // null while loading

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
    masks.set(url, context.getImageData(0, 0, SIZE, SIZE).data);
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
  return mask[(v * SIZE + u) * 4 + 3] > 40;
}

// The frontmost object painted at this point, if any.
export function thingAt(things: HTMLElement[], x: number, y: number): HTMLElement | undefined {
  return [...things]
    .reverse()
    .sort((a, b) => Number(b.style.zIndex) - Number(a.style.zIndex))
    .find((el) => paintedAt(el, x, y));
}
