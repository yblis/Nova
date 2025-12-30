const CACHE_VERSION = 'v6.6.0';
const CACHE_NAME = `app-shell-${CACHE_VERSION}`;
const STATIC_ASSETS = [
  '/static/img/icon.svg',
];

self.addEventListener('install', (e) => {
  self.skipWaiting(); // Force new SW to take control immediately
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(STATIC_ASSETS))
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    Promise.all([
      self.clients.claim(), // Take control of all open clients immediately
      caches.keys().then((keys) => {
        return Promise.all(
          keys.map((key) => {
            if (key !== CACHE_NAME) return caches.delete(key);
          })
        );
      }),
    ])
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Ignore non-http requests (like extensions)
  if (!url.protocol.startsWith('http')) return;

  // Always network for API calls
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Network-first for HTML pages to ensure fresh content
  // This is critical for HTMX navigation and login to work correctly
  if (event.request.mode === 'navigate' ||
    event.request.headers.get('accept')?.includes('text/html') ||
    url.pathname === '/' ||
    url.pathname.startsWith('/partials/') ||
    url.pathname.startsWith('/chat') ||
    url.pathname.startsWith('/texts') ||
    url.pathname.startsWith('/specialists') ||
    url.pathname.startsWith('/models') ||
    url.pathname.startsWith('/settings') ||
    url.pathname.startsWith('/discover') ||
    url.pathname.startsWith('/downloads') ||
    url.pathname.startsWith('/auth') ||
    url.pathname.startsWith('/admin')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          return response;
        })
        .catch(() => {
          // Only use cache as fallback when offline
          return caches.match(event.request);
        })
    );
    return;
  }

  // Stale-while-revalidate only for static assets (CSS, JS, images)
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.match(event.request).then((cached) => {
        const fetchPromise = fetch(event.request)
          .then((response) => {
            if (response && response.status === 200) {
              cache.put(event.request, response.clone());
            }
            return response;
          })
          .catch(() => cached || new Response('Hors ligne', { status: 503 }));

        return cached || fetchPromise;
      });
    })
  );
});
