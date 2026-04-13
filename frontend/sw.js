/*
  sw.js — Service Worker
  ──────────────────────
  A Service Worker is a script that runs in the background,
  separate from your web page. It acts as a middleman between
  your app and the network — intercepting requests and deciding
  whether to serve from cache or fetch from server.

  Think of it like a smart offline assistant:
    - First visit  → downloads and caches all your app files
    - Later visits → serves from cache instantly (fast!)
    - Offline      → still works using cached files
    - New version  → detects changes and updates cache automatically
*/

const CACHE_NAME = "momentum-v1";

// These are the files we cache on install
// The app will work offline with just these files
const STATIC_ASSETS = [
  "/",
  "/static/style.css",
  "/static/app.js",
  "https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap",
  "https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"
];

// ── Install event ──────────────────────────────────────────────────────────────
// Fires once when the service worker is first installed
// We use this to pre-cache all static assets
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log("[SW] Caching static assets");
      // addAll fetches and caches every URL in the list
      return cache.addAll(STATIC_ASSETS);
    })
  );
  // Force this SW to become active immediately (don't wait for old tabs to close)
  self.skipWaiting();
});

// ── Activate event ─────────────────────────────────────────────────────────────
// Fires when this SW takes control — clean up old caches here
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)  // find old cache versions
          .map(key => {
            console.log("[SW] Deleting old cache:", key);
            return caches.delete(key);         // delete them
          })
      )
    )
  );
  // Take control of all open tabs immediately
  self.clients.claim();
});

// ── Fetch event ────────────────────────────────────────────────────────────────
// Fires on EVERY network request the app makes
// This is where we decide: serve from cache or go to network?
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);

  // API requests: ALWAYS go to network (never serve stale data from cache)
  // We want live habit/task data, not cached responses
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(event.request).catch(() => {
        // If network fails (offline), return a helpful JSON error
        return new Response(
          JSON.stringify({ error: "You are offline. Please check your connection." }),
          { headers: { "Content-Type": "application/json" } }
        );
      })
    );
    return;
  }

  // Static assets: Cache First strategy
  // Check cache first → if not there, fetch from network and cache it
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) {
        return cached;  // Serve from cache instantly
      }
      // Not in cache → fetch from network
      return fetch(event.request).then(response => {
        // Don't cache bad responses or non-GET requests
        if (!response || response.status !== 200 || event.request.method !== "GET") {
          return response;
        }
        // Save a copy to cache for next time
        const toCache = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(event.request, toCache));
        return response;
      });
    })
  );
});
