// The page's own bits over the 3D picture (the place's name and the score,
// the dot you aim with and what E would do, the slots, what's said), painted
// onto a copy of the picture as they look on the screen: where they are, their
// boxes, borders and glows, their words in their fonts, the objects' pictures,
// and the tick on one in use. For the debug panel's picture (P), so it shows
// all you see. (A browser can't photograph its own page, so it's drawn again.)

/** Paints these elements (and all in them) onto `pen`, at `scale` canvas pixels to a CSS pixel. */
export function paintPage(pen: CanvasRenderingContext2D, scale: number, parts: Element[]) {
  pen.save();
  pen.scale(scale, scale);
  for (const part of parts) paint(pen, part, opacityAbove(part));
  pen.restore();
}

// How see-through everything round it makes it.
function opacityAbove(el: Element) {
  let alpha = 1;
  for (let up = el.parentElement; up; up = up.parentElement) alpha *= Number(getComputedStyle(up).opacity);
  return alpha;
}

function paint(pen: CanvasRenderingContext2D, el: Element, above: number) {
  const style = getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden") return;
  const alpha = above * Number(style.opacity);
  if (alpha < 0.01) return;
  const at = el.getBoundingClientRect();
  pen.save();
  pen.globalAlpha = alpha;
  box(pen, at, style);
  if (el instanceof HTMLImageElement && el.complete && el.naturalWidth) picture(pen, el, at);
  pen.restore();
  for (const node of el.childNodes) {
    if (node instanceof Element) paint(pen, node, alpha);
    else if (node.nodeType === Node.TEXT_NODE) words(pen, node as Text, style, alpha);
  }
  // A ::after's words (the tick on an object in use), in its own corner.
  const after = getComputedStyle(el, "::after");
  if (after.content && after.content !== "none" && after.content !== "normal") {
    const text = after.content.replace(/^["']|["']$/g, "");
    pen.save();
    pen.globalAlpha = alpha;
    pen.font = font(after);
    pen.fillStyle = after.color;
    shadow(pen, after.textShadow);
    pen.textAlign = "right";
    pen.textBaseline = "bottom";
    pen.fillText(text, at.right - (parseFloat(after.right) || 0), at.bottom - (parseFloat(after.bottom) || 0));
    pen.restore();
  }
}

// Its background and border, rounded, with its glow (box-shadow).
function box(pen: CanvasRenderingContext2D, at: DOMRect, style: CSSStyleDeclaration) {
  const fill = style.backgroundColor;
  const border = parseFloat(style.borderTopWidth) || 0;
  const hasFill = !/rgba\(.*,\s*0\)$|transparent/.test(fill);
  if (!hasFill && !border) return;
  const r = radius(style.borderTopLeftRadius, at);
  pen.save();
  shadow(pen, style.boxShadow);
  pen.beginPath();
  pen.roundRect(at.left, at.top, at.width, at.height, r);
  if (hasFill) {
    pen.fillStyle = fill;
    pen.fill();
  }
  if (border && style.borderTopStyle !== "none") {
    if (hasFill) shadow(pen, "none");
    pen.beginPath();
    pen.roundRect(
      at.left + border / 2,
      at.top + border / 2,
      at.width - border,
      at.height - border,
      Math.max(0, r - border / 2)
    );
    pen.lineWidth = border;
    pen.strokeStyle = style.borderTopColor;
    pen.stroke();
  }
  pen.restore();
}

// An object's picture, fitted in its box (object-fit: contain), with a soft shadow under it.
function picture(pen: CanvasRenderingContext2D, image: HTMLImageElement, at: DOMRect) {
  const fit = Math.min(at.width / image.naturalWidth, at.height / image.naturalHeight);
  const w = image.naturalWidth * fit;
  const h = image.naturalHeight * fit;
  shadow(pen, "rgba(0, 0, 0, 0.6) 0px 2px 3px");
  pen.drawImage(image, at.left + (at.width - w) / 2, at.top + (at.height - h) / 2, w, h);
}

// Its words, one at a time where the page put each (so they wrap as they do there).
function words(pen: CanvasRenderingContext2D, node: Text, style: CSSStyleDeclaration, alpha: number) {
  const text = node.textContent ?? "";
  if (!text.trim()) return;
  const range = document.createRange();
  pen.save();
  pen.globalAlpha = alpha;
  pen.font = font(style);
  pen.fillStyle = style.color;
  pen.textBaseline = "middle";
  shadow(pen, style.textShadow);
  for (const word of text.matchAll(/\S+/g)) {
    range.setStart(node, word.index);
    range.setEnd(node, word.index + word[0].length);
    const at = range.getBoundingClientRect();
    if (at.width) pen.fillText(word[0], at.left, at.top + at.height / 2);
  }
  pen.restore();
}

function font(style: CSSStyleDeclaration) {
  return `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
}

function radius(value: string, at: DOMRect) {
  const r = parseFloat(value) || 0;
  return value.endsWith("%") ? (Math.min(at.width, at.height) * r) / 100 : r;
}

// The first of a CSS shadow ("rgba(0, 0, 0, 0.6) 0px 2px 8px"), as the pen's shadow.
function shadow(pen: CanvasRenderingContext2D, css: string) {
  const match = /(rgba?\([^)]*\)|#[0-9a-f]+)\s+(-?[\d.]+)px\s+(-?[\d.]+)px(?:\s+([\d.]+)px)?/i.exec(css);
  const scale = pen.getTransform().a; // (shadows aren't scaled with the rest)
  pen.shadowColor = match ? match[1] : "transparent";
  pen.shadowOffsetX = match ? Number(match[2]) * scale : 0;
  pen.shadowOffsetY = match ? Number(match[3]) * scale : 0;
  pen.shadowBlur = match ? Number(match[4] ?? 0) * scale : 0;
}
