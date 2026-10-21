const CACHE_NAME = 'kanaw-cache-v1';
const ASSETS = [
    '/',
    '/static/style.css',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// تثبيت الـ Service Worker وتخزين الملفات الأساسية
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS).catch(err => console.log('Cache add error', err));
        })
    );
});

// اعتراض الطلبات وتقديم النسخة المحفوظة إذا كان هناك انقطاع في الإنترنت
self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') return; // لا تخزن طلبات POST
    
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                // تحديث الكاش بأحدث نسخة (للملفات الثابتة فقط)
                if (event.request.url.includes('.css') || event.request.url.includes('.js')) {
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, networkResponse.clone());
                    });
                }
                return networkResponse;
            }).catch(() => {
                // إذا فشل الاتصال بالإنترنت، سيتم استخدام الكاش
                return cachedResponse;
            });
            return cachedResponse || fetchPromise;
        })
    );
});
