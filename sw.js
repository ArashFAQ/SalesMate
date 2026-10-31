// SalesMate موبایل — سرویس‌ورکر: شبکه اول (تا به‌روزرسانی‌ها همیشه برسد)، اگر آفلاین بود از کش
const VERSION = 'sm-mobile-2.4.3';
const ASSETS = ['./', './index.html', './manifest.json', './icon.svg', './css/app.css?v=2.4.3',
  './js/core.js?v=2.4.3', './js/data.js?v=2.4.3', './js/charts.js?v=2.4.3', './js/pages_a.js?v=2.4.3',
  './js/pages_b.js?v=2.4.3', './js/pages_c.js?v=2.4.3', './js/pages_d.js?v=2.4.3', './js/inquiry_new.js?v=2.4.3', './js/calc_tool.js?v=2.4.3', './js/app.js?v=2.4.3',
  './fonts/Vazirmatn-Regular.ttf', './fonts/Vazirmatn-Medium.ttf', './fonts/Vazirmatn-Bold.ttf'];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(ASSETS).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== VERSION).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(fetch(req).then(res => {
    const copy = res.clone();
    caches.open(VERSION).then(c => c.put(req, copy)).catch(() => {});
    return res;
  }).catch(() => caches.match(req).then(r => r || caches.match('./index.html'))));
});
