/* /service-worker.js */
const CACHE_NAME = 'appstore-pwa-v1';
// 要缓存的静态资源列表
const urlsToCache = [
  '/pwa/index.html',
  '/pwa/app.js',
  '/pwa/styles.css',
  '/manifest.json',
  // 使用 CDN 的 Bootstrap CSS/JS
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
];

// 安装阶段：缓存静态资源
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: 缓存所有应用外壳文件');
        return cache.addAll(urlsToCache);
      })
  );
});

// 激活阶段：清理旧的缓存
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            console.log('Service Worker: 清理旧缓存', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// 抓取阶段：从缓存或网络提供资源
self.addEventListener('fetch', event => {
  // 对于 API 请求，直接走网络
  if (event.request.url.includes('/api/software')) {
    return fetch(event.request);
  }
  
  // 对于静态文件，优先从缓存获取
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});