// Minimal Service Worker for Calimara
// This prevents the "SW registration failed" error

self.addEventListener('install', function(event) {
    console.log('Service Worker installed');
    self.skipWaiting();
});

self.addEventListener('activate', function(event) {
    console.log('Service Worker activated');
    event.waitUntil(clients.claim());
});

// For now, just pass through all fetch requests
// In the future, this could be used for offline support or caching
self.addEventListener('fetch', function(event) {
    event.respondWith(fetch(event.request));
});