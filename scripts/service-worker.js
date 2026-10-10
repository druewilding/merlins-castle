// The service worker that lets Merlin's Castle work offline. `npm run build`
// fills in the file lists and version (see offline() in vite.config.ts) and
// writes it to dist/sw.js.
//
// - The game itself (code, styles, sounds, icons) is stored when you first
//   visit, so it always starts, even offline.
// - Pictures and music are stored as you meet them.
// - The installed app asks for everything, so the whole world is there for a
//   journey without signal.

const VERSION = "__VERSION__";
const CORE = __CORE__;
const MEDIA = __MEDIA__; // { path: fingerprint }

const CORE_CACHE = `core-${VERSION}`;
const MEDIA_CACHE = "media"; // kept across versions; only changed files are replaced
const FINGERPRINTS = "./__fingerprints__"; // what's in the media cache, by path
const FONT_CACHE = "fonts";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CORE_CACHE)
      .then((cache) => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      for (const name of await caches.keys()) {
        if (name.startsWith("core-") && name !== CORE_CACHE) await caches.delete(name);
      }
      // Forget pictures and music that have changed or are no longer used.
      const media = await caches.open(MEDIA_CACHE);
      const stored = await media.match(FINGERPRINTS).then((r) => (r ? r.json() : {}));
      for (const request of await media.keys()) {
        const path = "./" + new URL(request.url).href.slice(self.registration.scope.length);
        if (path === FINGERPRINTS) continue;
        if (MEDIA[path] !== stored[path]) await media.delete(request);
      }
      await media.put(FINGERPRINTS, new Response(JSON.stringify(MEDIA)));
      await self.clients.claim();
    })()
  );
});

// The installed app asks for every picture and the music up front.
self.addEventListener("message", (event) => {
  if (event.data === "cache-everything") event.waitUntil(cacheEverything());
});

async function cacheEverything() {
  const cache = await caches.open(MEDIA_CACHE);
  for (const path of Object.keys(MEDIA)) {
    if (await cache.match(path, { ignoreVary: true })) continue;
    try {
      await cache.add(path);
    } catch {
      return; // offline or interrupted: carry on another time
    }
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Pages: try the network for the latest version, fall back to the stored one.
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match("./index.html", { ignoreSearch: true, ignoreVary: true }).then((r) => r ?? Response.error())
      )
    );
    return;
  }

  // Google Fonts: use the stored copy, and refresh it when online.
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(staleWhileRevalidate(FONT_CACHE, request));
    return;
  }

  if (url.origin !== self.location.origin) return;

  // Pictures and music: use the stored copy (an update replaces any that
  // changed). Music is fetched in ranges by the browser, so it's stored whole
  // the first time and served from the store after that.
  if (/\/(art|music)\//.test(url.pathname)) {
    event.respondWith(media(request));
    return;
  }

  // Everything else (code, styles, sounds, icons): stored copy first.
  // (Servers may mark files as varying by Origin; any stored copy will do.)
  event.respondWith(caches.match(request, { ignoreVary: true }).then((cached) => cached ?? fetch(request)));
});

async function media(request) {
  const cache = await caches.open(MEDIA_CACHE);
  const key = request.url;
  const cached = await cache.match(key, { ignoreVary: true });
  if (cached) return request.headers.has("range") ? rangeOf(cached, request.headers.get("range")) : cached;
  if (request.headers.has("range")) {
    // Store the whole file for next time, but answer this request directly.
    cache.add(key).catch(() => {});
    return fetch(request);
  }
  const response = await fetch(request);
  if (response.ok) cache.put(key, response.clone());
  return response;
}

// Answer a range request (as browsers make for audio) from a stored file.
async function rangeOf(response, range) {
  const body = await response.arrayBuffer();
  const [, from, to] = /bytes=(\d*)-(\d*)/.exec(range) ?? [];
  const start = Number(from || 0);
  const end = to ? Number(to) : body.byteLength - 1;
  return new Response(body.slice(start, end + 1), {
    status: 206,
    headers: {
      "Content-Type": response.headers.get("Content-Type") ?? "audio/mpeg",
      "Content-Range": `bytes ${start}-${end}/${body.byteLength}`,
      "Content-Length": String(end - start + 1),
    },
  });
}

async function staleWhileRevalidate(name, request) {
  const cache = await caches.open(name);
  const cached = await cache.match(request, { ignoreVary: true });
  const fresh = fetch(request)
    .then((response) => {
      cache.put(request, response.clone());
      return response;
    })
    .catch(() => cached);
  return cached ?? fresh;
}
