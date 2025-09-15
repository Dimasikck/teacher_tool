const CACHE_NAME = 'teacher-tools-v1.0.0';
const STATIC_CACHE = 'static-cache-v1';
const DYNAMIC_CACHE = 'dynamic-cache-v1';

// Файлы для кэширования при установке
const STATIC_FILES = [
  '/',
  '/static/css/bootstrap.min.css',
  '/static/css/style.css',
  '/static/js/bootstrap.bundle.min.js',
  '/static/js/app.js',
  '/manifest.json',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png'
];

// API эндпоинты, которые нужно кэшировать
const API_CACHE_PATTERNS = [
  /^\/api\/schedule\/events/,
  /^\/api\/groups/,
  /^\/api\/assignments/
];

// Установка Service Worker
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('Service Worker: Caching static files');
        return cache.addAll(STATIC_FILES);
      })
      .then(() => {
        console.log('Service Worker: Installation complete');
        return self.skipWaiting();
      })
      .catch((error) => {
        console.error('Service Worker: Installation failed', error);
      })
  );
});

// Активация Service Worker
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cacheName) => {
            if (cacheName !== STATIC_CACHE && cacheName !== DYNAMIC_CACHE) {
              console.log('Service Worker: Deleting old cache', cacheName);
              return caches.delete(cacheName);
            }
          })
        );
      })
      .then(() => {
        console.log('Service Worker: Activation complete');
        return self.clients.claim();
      })
  );
});

// Перехват запросов
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Пропускаем не-GET запросы
  if (request.method !== 'GET') {
    return;
  }

  // Стратегия кэширования для разных типов ресурсов
  if (isStaticFile(url.pathname)) {
    // Статические файлы: Cache First
    event.respondWith(cacheFirst(request, STATIC_CACHE));
  } else if (isAPIRequest(url.pathname)) {
    // API запросы: Network First с fallback на кэш
    event.respondWith(networkFirst(request, DYNAMIC_CACHE));
  } else if (isPageRequest(url.pathname)) {
    // HTML страницы: Network First с fallback на кэш
    event.respondWith(networkFirst(request, DYNAMIC_CACHE));
  } else {
    // Остальные запросы: Network First
    event.respondWith(networkFirst(request, DYNAMIC_CACHE));
  }
});

// Стратегия Cache First
async function cacheFirst(request, cacheName) {
  try {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.error('Cache First strategy failed:', error);
    return new Response('Offline content not available', { status: 503 });
  }
}

// Стратегия Network First
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    
    return networkResponse;
  } catch (error) {
    console.log('Network failed, trying cache:', error);
    
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Для страниц возвращаем офлайн страницу
    if (isPageRequest(new URL(request.url).pathname)) {
      return new Response(`
        <!DOCTYPE html>
        <html lang="ru">
        <head>
          <meta charset="UTF-8">
          <meta name="viewport" content="width=device-width, initial-scale=1.0">
          <title>Офлайн - Teacher Tools</title>
          <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
            .offline-message { max-width: 400px; margin: 0 auto; }
            .icon { font-size: 64px; color: #667eea; margin-bottom: 20px; }
          </style>
        </head>
        <body>
          <div class="offline-message">
            <div class="icon">📱</div>
            <h2>Нет подключения к интернету</h2>
            <p>Приложение работает в офлайн режиме. Некоторые функции могут быть недоступны.</p>
            <button onclick="window.location.reload()">Попробовать снова</button>
          </div>
        </body>
        </html>
      `, {
        headers: { 'Content-Type': 'text/html' }
      });
    }

    return new Response('Content not available offline', { status: 503 });
  }
}

// Проверка типа файла
function isStaticFile(pathname) {
  return pathname.match(/\.(css|js|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/);
}

function isAPIRequest(pathname) {
  return pathname.startsWith('/api/') || API_CACHE_PATTERNS.some(pattern => pattern.test(pathname));
}

function isPageRequest(pathname) {
  return pathname.endsWith('/') || pathname.match(/\.(html|htm)$/) || !pathname.includes('.');
}

// Обработка push уведомлений (если понадобится в будущем)
self.addEventListener('push', (event) => {
  if (event.data) {
    const data = event.data.json();
    const options = {
      body: data.body,
      icon: '/static/icons/icon-192x192.png',
      badge: '/static/icons/icon-72x72.png',
      vibrate: [100, 50, 100],
      data: data.data || {},
      actions: [
        {
          action: 'open',
          title: 'Открыть',
          icon: '/static/icons/icon-72x72.png'
        },
        {
          action: 'close',
          title: 'Закрыть',
          icon: '/static/icons/icon-72x72.png'
        }
      ]
    };

    event.waitUntil(
      self.registration.showNotification(data.title || 'Teacher Tools', options)
    );
  }
});

// Обработка кликов по уведомлениям
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  if (event.action === 'open' || !event.action) {
    event.waitUntil(
      clients.openWindow('/')
    );
  }
});

// Синхронизация в фоне (если понадобится)
self.addEventListener('sync', (event) => {
  if (event.tag === 'background-sync') {
    event.waitUntil(doBackgroundSync());
  }
});

async function doBackgroundSync() {
  // Здесь можно добавить логику синхронизации данных
  console.log('Background sync triggered');
}
