var cacheVersion = "##1##";
var offlinePage = "##2##";

const offlineUrl = '/pwa/offline_page';
var currentCache = {
    offline: 'offline-cache' + cacheVersion
};

self.addEventListener('install', event => {
    // At this point everything has been cached
    self.skipWaiting();
    event.waitUntil(
        caches.open(currentCache.offline).then(function(cache) {
            return cache.addAll([
                offlineUrl,
                '/theme_prime/static/src/img/pwa_offline.png',
                '/pwa/logo.png'
            ]);
    }));
});

self.addEventListener('activate', function (event) {
    var cacheWhitelist = []; // add cache names which you do not want to delete
    cacheWhitelist.push(currentCache.offline);
    event.waitUntil(
        caches.keys().then(function (cacheNames) {
            return Promise.all(
                cacheNames.map(function (cacheName) {
                    if (!cacheWhitelist.includes(cacheName)) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

if (offlinePage) {

    self.addEventListener('fetch', event => {
        const url = new URL(event.request.url);
        if (event.request.method !== 'GET') {
            return;
        }

        if (url.origin === location.origin) {
            if (event.clientId === "" && // Not fetched via AJAX after page load.
                event.request.method == "GET" && // Don't fetch on POST, DELETE, etc.
                !url.href.includes('.css') && // Don't run on CSS.
                !url.href.includes('.js') && // Don't run on JS.
                !url.href.includes('/web') && // Don't run for backend.
                !url.href.includes('/manifest.json') && // Don't run manifest.
                (!url.href.includes('/static/src') || url.href.includes('pwa_offline.png'))// Don't run for static.
                ) {
                // request.mode = navigate isn't supported in all browsers
                // so include a check for Accept: text/html header.
                if ((event && event.request && event.request.mode === 'navigate') || (event.request.method === 'GET' && event.request.headers.get('accept').includes('text/html'))) {
                    event.respondWith(
                        fetch(event.request)
                        .then(function (response) {
                            return response;
                        })
                        .catch(error => {
                            // Return the offline page
                            return caches.match(offlineUrl);
                    }));
                }
            }
            if (event.request.method === 'GET' &&
                (
                    url.href.includes('/pwa/offline_page') ||
                    url.href.includes('/pwa_offline.png') ||
                    url.href.includes('/pwa/logo.png')
                )
            ) {
                event.respondWith(caches.match(event.request)
                    .then(function (response) {
                        return response || fetch(event.request);
                    })
                );
            }
        }

    });

} else {
    // Without this PWA option will not be displayed
    // When offline page is disabled
    self.addEventListener('fetch', event => { });
}
