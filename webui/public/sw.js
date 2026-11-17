const CACHE = "deluge-mobileui-v2";
const API_CACHE = "deluge-mobileui-api-v1";
const SHELL = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/icons/apple-touch-icon.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE && key !== API_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) {
    if (
      request.method === "GET" &&
      (url.pathname.startsWith("/api/torrents") ||
        url.pathname === "/api/session" ||
        url.pathname === "/api/labels")
    ) {
      event.respondWith(apiResponse(request));
    }
    return;
  }

  if (request.mode === "navigate") {
    if (url.pathname === "/share") {
      event.respondWith(
        caches
          .match("/index.html")
          .then((cached) => cached || fetch("/index.html")),
      );
      return;
    }
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put("/index.html", copy));
          return response;
        })
        .catch(() => caches.match("/index.html")),
    );
    return;
  }

  if (
    url.pathname.startsWith("/assets/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname === "/favicon.svg" ||
    url.pathname === "/manifest.webmanifest"
  ) {
    event.respondWith(
      caches.match(request).then(
        (cached) =>
          cached ||
          fetch(request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          }),
      ),
    );
  }
});

async function apiResponse(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (!cached) return Response.error();
    const headers = new Headers(cached.headers);
    headers.set("X-MobileUi-Stale", "1");
    return new Response(await cached.blob(), {
      status: cached.status,
      statusText: cached.statusText,
      headers,
    });
  }
}

self.addEventListener("message", (event) => {
  if (event.data?.type === "clear-api-cache") {
    event.waitUntil(caches.delete(API_CACHE));
  }
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = { body: event.data ? event.data.text() : "" };
  }
  const language = (
    (self.navigator && self.navigator.language) ||
    "en"
  ).toLowerCase();
  const hu = language.startsWith("hu");
  let title = payload.title || "Deluge Mobile";
  let body = payload.body || "";
  if (payload.kind === "finished") {
    title = hu ? "Torrent kész" : "Torrent finished";
    body = payload.name || body;
  } else if (payload.kind === "error") {
    title = hu ? "Torrent hiba" : "Torrent error";
    body = payload.name
      ? `${payload.name}: ${payload.message || (hu ? "Hiba" : "Error")}`
      : body;
  } else if (payload.kind === "test") {
    title = hu ? "Deluge Mobile teszt" : "Deluge Mobile test";
    body = hu
      ? "A push értesítések működnek."
      : "Push notifications are working.";
  }
  const url = payload.url || "/";
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      tag: payload.tag,
      icon: "/icons/icon-192.png",
      badge: "/icons/icon-192.png",
      data: { url },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(
    event.notification.data?.url || "/",
    self.location.origin,
  ).href;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clients) => {
        for (const client of clients) {
          if (client.url.startsWith(self.location.origin) && "focus" in client) {
            if ("navigate" in client) client.navigate(target);
            return client.focus();
          }
        }
        return self.clients.openWindow(target);
      }),
  );
});
