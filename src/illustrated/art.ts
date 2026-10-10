// URLs for the web images that exist (see scripts/build-art.js). Anything not
// painted yet returns null, and the game shows the night sky and its fireflies.

import manifest from "./art-manifest.json";

export type ArtKind = "scenes" | "rooms" | "items" | "moments" | "effects";

const available = manifest as Record<ArtKind, string[]>;

export function artUrl(kind: ArtKind, id: string | undefined): string | null {
  if (!id || !available[kind]?.includes(id)) return null;
  return `${import.meta.env.BASE_URL}art/${kind}/${id}.webp`;
}

// Start loading images the player is likely to need next.
export function preload(urls: (string | null)[]): void {
  for (const url of urls) if (url) new Image().src = url;
}
