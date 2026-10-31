/* SalesMate موبایل ۲.۰ — فقط‌خواندنی. هسته: ابزارها، تاریخ شمسی، کش، ورود، API */
'use strict';
function loginEmail(v) { v = String(v || '').trim(); return v && v.indexOf('@') < 0 ? v.toLowerCase() + '@sales.local' : v; }
const APP_VERSION = '2.4.3';
const SUPABASE_URL = 'https://sowftowkhvuvaijttpiv.supabase.co';
const SUPABASE_KEY = 'sb_publishable_5BrCyhkBlDQqbdjkGnEK1w_zpsHiAs8';

/* ───────── ارقام و قالب ───────── */
const FA = '۰۱۲۳۴۵۶۷۸۹';
function fa(v) { return String(v == null ? '' : v).replace(/[0-9]/g, d => FA[d]); }
function en(v) {
  return String(v == null ? '' : v).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
}
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
function amount(v) {
  if (v == null || v === '') return 0;
  if (typeof v === 'number') return Math.round(v);
  let s = en(v).trim().replace(/[,٬،\s]/g, '').replace(/٫/g, '.');
  if (!s || s === '-' || s === '+' || s === '.') return 0;
  const neg = s[0] === '-';
  s = s.replace(/[^0-9.]/g, '');
  if (!s) return 0;
  const n = Math.round(parseFloat(s));
  return isNaN(n) ? 0 : (neg ? -n : n);
}
function commas(v) { const d = en(v == null ? '' : v).replace(/[^\d]/g, ''); return d ? d.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''; }
function num(v) { const n = parseFloat(en(v).replace(/[,٬،\s]/g, '')); return isNaN(n) ? 0 : n; }
function fmt(v) { return fa(amount(v).toLocaleString('en-US')); }
function qtyInt(v) {                      // کارتن/پالت همیشه صحیح
  if (v == null || v === '') return '';
  const t = en(v).replace(/[,٬،\s]/g, '');
  const f = parseFloat(t);
  if (isNaN(f)) return String(v);
  return String(f >= 0 ? Math.floor(f + 0.5) : -Math.floor(-f + 0.5));
}
function fm(v, d) {                      // اعشار کوتاه
  const n = +v || 0;
  const s = n.toFixed(d == null ? 2 : d).replace(/\.?0+$/, '');
  return fa(s === '' ? '0' : s);
}
function abbr(v) {
  const n = Math.abs(+v || 0), s = (+v || 0) < 0 ? '-' : '';
  if (n >= 1e9) return fa(s + (n / 1e9).toFixed(2).replace(/\.?0+$/, '') + ' میلیارد');
  if (n >= 1e6) return fa(s + (n / 1e6).toFixed(1).replace(/\.?0+$/, '') + ' میلیون');
  if (n >= 1e3) return fa(s + (n / 1e3).toFixed(0) + ' هزار');
  return fa(s + n);
}
function customerKey(s) {
  return en(s).replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[‌‍‎‏‪-‮ـً-ٟ]/g, ' ').replace(/\s+/g, ' ').trim().toLowerCase();
}

/* ───────── تاریخ شمسی (همان الگوریتم ویندوز) ───────── */
const MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
const fl = Math.floor;
function g2j(gy, gm, gd) {
  const leap = (gy % 4 === 0 && (gy % 100 !== 0 || gy % 400 === 0));
  const gdim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  const y2 = gy - 1600, m2 = gm - 1, d2 = gd - 1;
  let gdn = 365 * y2 + fl((y2 + 3) / 4) - fl((y2 + 99) / 100) + fl((y2 + 399) / 400) + d2;
  for (let i = 0; i < m2; i++) gdn += gdim[i];
  let jdn = gdn - 79;
  const jnp = fl(jdn / 12053); jdn %= 12053;
  let jy = 979 + 33 * jnp + 4 * fl(jdn / 1461); jdn %= 1461;
  if (jdn >= 366) { jy += fl((jdn - 1) / 365); jdn = (jdn - 1) % 365; }
  const jm = jdn < 186 ? 1 + fl(jdn / 31) : 7 + fl((jdn - 186) / 30);
  const jd = 1 + (jm <= 6 ? jdn - (jm - 1) * 31 : jdn - 186 - (jm - 7) * 30);
  return [jy, jm, jd];
}
function j2g(jy, jm, jd) {
  const jy2 = jy - 979;
  let days = 365 * jy2 + fl(jy2 / 33) * 8 + fl(((jy2 % 33) + 3) / 4);
  for (let i = 1; i < jm; i++) days += i <= 6 ? 31 : 30;
  days += jd - 1;
  let gdn = days + 79, gy = 1600, leap = true;
  gy += 400 * fl(gdn / 146097); gdn %= 146097;
  if (gdn >= 36525) {
    gdn -= 1; gy += 100 * fl(gdn / 36524); gdn %= 36524;
    if (gdn >= 365) gdn += 1; else leap = false;
  }
  gy += 4 * fl(gdn / 1461); gdn %= 1461;
  if (gdn >= 366) { leap = false; gdn -= 1; gy += fl(gdn / 365); gdn %= 365; }
  let gd = gdn + 1, gm = 1;
  const gdim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  for (const dim of gdim) { if (gd <= dim) break; gd -= dim; gm++; }
  return [gy, gm, gd];
}
function todayJ() { const d = new Date(); return g2j(d.getFullYear(), d.getMonth() + 1, d.getDate()); }
function p2(n) { return String(n).padStart(2, '0'); }
function jfmt(y, m, d) { return fa(String(y).padStart(4, '0') + '/' + p2(m) + '/' + p2(d)); }
function parseJ(s) {                       // «۱۴۰۵/۰۷/۰۸» → [y,m,d] | null
  const p = en(s).trim().replace(/[-.]/g, '/').split('/').filter(x => x !== '');
  if (p.length < 3) return null;
  const a = p.map(x => parseInt(x, 10));
  if (a.some(isNaN)) return null;
  return a[0] > 31 ? [a[0], a[1], a[2]] : [a[2], a[1], a[0]];
}
function parseFlexJ(text, defY) {          // ۸/۷ یا ۸/۷/۰۶ یا ۱۴۰۶/۰۷/۰۸
  const s = en(text).trim().replace(/[-.]/g, '/').replace(/\s/g, '');
  if (!s) return null;
  const nums = s.split('/').filter(x => x !== '').map(x => parseInt(x, 10));
  if (!nums.length || nums.some(isNaN)) return null;
  const t = todayJ();
  if (defY == null) defY = t[0];
  if (/^\d+$/.test(s) && [4, 6, 8].includes(s.length)) {          // بدون اسلش: ddmm / ddmmyy / ddmmyyyy
    const d = +s.slice(0, 2), m = +s.slice(2, 4); let y = defY;
    if (s.length === 6) { const yy = +s.slice(4); y = yy < 80 ? 1400 + yy : 1300 + yy; }
    if (s.length === 8) { if (+s.slice(0, 4) >= 1300) return [+s.slice(0, 4), +s.slice(4, 6), +s.slice(6)]; y = +s.slice(4); }
    return [y, m, d];
  }
  if (nums.length === 1) return [defY, t[1], nums[0]];
  if (nums.length === 2) { let d = nums[0], m = nums[1]; if (m > 12 && d <= 12) { const x = d; d = m; m = x; } return [defY, m, d]; }
  let [a, b, c] = nums, y, m, d;
  if (a > 31) { y = a; m = b; d = c; } else { d = a; m = b; y = c; }
  if (y < 100) y = y < 80 ? 1400 + y : 1300 + y;
  return [y, m, d];
}
function isLeapJ(y) { const g = j2g(y, 12, 30); const r = g2j(g[0], g[1], g[2]); return r[0] === y && r[1] === 12 && r[2] === 30; }
function weekKey(dateStr) {                // هفته‌های ۷روزه از اول فروردین (مثل ویندوز)
  const p = en(dateStr).split('/');
  if (p.length < 3) return null;
  const y = +p[0], m = +p[1], d = +p[2];
  if (!y || !m || !d) return null;
  const days = m <= 6 ? (m - 1) * 31 + d : 186 + (m - 7) * 30 + d;
  return [y, fl((days - 1) / 7)];
}
function weekRange(y, w) {                 // [[m1,d1],[m2,d2]] | null
  const last = isLeapJ(y) ? 366 : 365;
  const md = doy => { doy = Math.max(1, Math.min(doy, last)); if (doy <= 186) return [fl((doy - 1) / 31) + 1, (doy - 1) % 31 + 1]; const r = doy - 186; return [7 + fl((r - 1) / 30), (r - 1) % 30 + 1]; };
  const st = w * 7 + 1; if (w < 0 || st > last) return null;
  return [md(st), md(Math.min(st + 6, last))];
}
function weekText(y, w) {
  const r = weekRange(y, w); if (!r) return '';
  const [[m1, d1], [m2, d2]] = r;
  return m1 === m2 ? fa(d1) + ' تا ' + fa(d2) + ' ' + MONTHS[m1 - 1] : fa(d1) + ' ' + MONTHS[m1 - 1] + ' تا ' + fa(d2) + ' ' + MONTHS[m2 - 1];
}
function weekShort(y, w) {
  const r = weekRange(y, w); if (!r) return '';
  return fa(p2(r[0][0]) + '/' + p2(r[0][1])) + '–' + fa(p2(r[1][0]) + '/' + p2(r[1][1]));
}

/* ───────── کش محلی (IndexedDB) ───────── */
const Cache = (function () {
  let dbp = null;
  function open() {
    if (dbp) return dbp;
    dbp = new Promise((res, rej) => {
      try {
        const rq = indexedDB.open('salesmate_mobile', 1);
        rq.onupgradeneeded = () => rq.result.createObjectStore('kv');
        rq.onsuccess = () => res(rq.result);
        rq.onerror = () => rej(rq.error);
      } catch (e) { rej(e); }
    });
    return dbp;
  }
  async function get(k) {
    try {
      const db = await open();
      return await new Promise((res) => { const r = db.transaction('kv').objectStore('kv').get(k); r.onsuccess = () => res(r.result); r.onerror = () => res(undefined); });
    } catch (e) { return undefined; }
  }
  async function set(k, v) {
    try {
      const db = await open();
      await new Promise((res) => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').put(v, k); t.oncomplete = res; t.onerror = res; });
    } catch (e) { /* بدون کش هم کار می‌کند */ }
  }
  async function clear() {
    try { const db = await open(); await new Promise(res => { const t = db.transaction('kv', 'readwrite'); t.objectStore('kv').clear(); t.oncomplete = res; t.onerror = res; }); } catch (e) { }
  }
  return { get, set, clear };
})();
function lsGet(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
function lsSet(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }

/* ───────── ورود و API (فقط خواندن؛ به‌جز ورود/تمدید توکن هیچ نوشتنی ندارد) ───────── */
const Auth = {
  sess() { return lsGet('sm_sess', null); },
  ok() { const s = this.sess(); return !!(s && s.access_token && s.user_id); },
  email() { const s = this.sess(); return s ? s.email : ''; },
  _save(d, prev) {
    prev = prev || {};
    let uid = (d.user && d.user.id) || prev.user_id || '', email = (d.user && d.user.email) || prev.email || '';
    try { if (!uid && d.access_token) uid = JSON.parse(atob(d.access_token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))).sub; } catch (e) { }
    lsSet('sm_sess', { access_token: d.access_token, refresh_token: d.refresh_token || prev.refresh_token || '', user_id: uid, email: email, exp: Date.now() + ((d.expires_in || 3600) - 60) * 1000 });
  },
  async login(email, pass) {
    const r = await fetch(SUPABASE_URL + '/auth/v1/token?grant_type=password', { method: 'POST', headers: { apikey: SUPABASE_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ email: loginEmail(email), password: pass }) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || !d.access_token) throw new Error(d.error_description || d.msg || d.message || 'ایمیل یا رمز اشتباه است');
    this._save(d);
  },
  async refresh() {
    const s = this.sess(); if (!s || !s.refresh_token) return false;
    try {
      const r = await fetch(SUPABASE_URL + '/auth/v1/token?grant_type=refresh_token', { method: 'POST', headers: { apikey: SUPABASE_KEY, 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh_token: s.refresh_token }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || !d.access_token) return false;
      this._save(d, s); return true;
    } catch (e) { return false; }
  },
  logout() { try { localStorage.removeItem('sm_sess'); } catch (e) { } }
};

async function sbGet(path) {                // فقط GET
  let s = Auth.sess();
  if (!s) throw new Error('وارد نشده‌اید');
  if (Date.now() > (s.exp || 0)) { await Auth.refresh(); s = Auth.sess(); }
  const go = async () => fetch(SUPABASE_URL + path, { headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + Auth.sess().access_token } });
  let r = await go();
  if (r.status === 401 && await Auth.refresh()) r = await go();
  if (r.status === 401) throw new Error('نشست منقضی شد؛ دوباره وارد شوید');
  if (!r.ok) { const t = await r.text().catch(() => ''); const e = new Error('خطا ' + r.status + ': ' + t.slice(0, 160)); e.status = r.status; throw e; }
  return r.json();
}
async function sbDelete(path) {            // فقط برای حذف استعلام
  let s = Auth.sess(); if (!s) throw new Error('وارد نشده‌اید');
  if (Date.now() > (s.exp || 0)) { await Auth.refresh(); s = Auth.sess(); }
  const go = async () => fetch(SUPABASE_URL + path, { method: 'DELETE', headers: { apikey: SUPABASE_KEY, Authorization: 'Bearer ' + Auth.sess().access_token, Prefer: 'return=representation' } });
  let r = await go(); if (r.status === 401 && await Auth.refresh()) r = await go();
  if (!r.ok) throw new Error('خطا ' + r.status);
  const j = await r.json().catch(() => []); return Array.isArray(j) ? j.length : 0;
}
const OWNER_EMAIL = 'arash.e.maleki@gmail.com';
function isOwner() { return String(Auth.email() || '').trim().toLowerCase() === OWNER_EMAIL; }
const OWNER_PAGES = ['store', 'balance', 'calc', 'parquet', 'free', 'salesrep'];
/* PDF ساده از تصویر بوم (JPEG داخل PDF) — بدون کتابخانه */
async function pdfFromCanvas(cv) {
  const jb = await new Promise(r => cv.toBlob(r, 'image/jpeg', 0.97)), jpg = new Uint8Array(await jb.arrayBuffer());
  const W = cv.width, H = cv.height, pw = 595, ph = Math.round(595 * H / W), enc = new TextEncoder(), parts = [], offs = []; let len = 0;
  const add = x => { const u = typeof x === 'string' ? enc.encode(x) : x; parts.push(u); len += u.length; };
  add('%PDF-1.4\n');
  const obj = (n, body) => { offs[n] = len; add(n + ' 0 obj\n'); add(body); add('\nendobj\n'); };
  obj(1, '<< /Type /Catalog /Pages 2 0 R >>'); obj(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>');
  obj(3, '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ' + pw + ' ' + ph + '] /Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>');
  offs[4] = len; add('4 0 obj\n<< /Type /XObject /Subtype /Image /Width ' + W + ' /Height ' + H + ' /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ' + jpg.length + ' >>\nstream\n'); add(jpg); add('\nendstream\nendobj\n');
  const cs = 'q ' + pw + ' 0 0 ' + ph + ' 0 0 cm /Im0 Do Q'; obj(5, '<< /Length ' + cs.length + ' >>\nstream\n' + cs + '\nendstream');
  const xr = len; add('xref\n0 6\n0000000000 65535 f \n'); for (let i = 1; i <= 5; i++) add(String(offs[i]).padStart(10, '0') + ' 00000 n \n');
  add('trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + xr + '\n%%EOF');
  return new Blob(parts, { type: 'application/pdf' });
}
async function shareCanvas(cv, base, kind, text) {
  base = String(base || 'x').replace(/[^\w؀-ۿ-]+/g, '_').slice(0, 30);
  if (kind === 'pdf') { const b = await pdfFromCanvas(cv); await shareBlob(b, base + '.pdf', text || ''); return; }
  const b = await new Promise(r => cv.toBlob(r, 'image/png')); if (!b) { toast('ساخت تصویر ناموفق بود', true); return; } await shareBlob(b, base + '.png', text || '');
}
async function sbAll(path) {                // صفحه‌بندی ۱۰۰۰تایی
  let out = [], off = 0;
  for (; ;) {
    const part = await sbGet(path + (path.includes('?') ? '&' : '?') + 'limit=1000&offset=' + off);
    out = out.concat(part);
    if (part.length < 1000) break;
    off += 1000;
    if (off > 200000) break;
  }
  return out;
}

/* ───────── رابط: ورق پایین، پیام، اشتراک ───────── */
function toast(msg, err) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.className = 'toast' + (err ? ' err' : '');
  clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.add('hidden'), 2600);
}
function openSheet(title, html, onMount) {
  const sh = document.getElementById('sheet');
  sh.innerHTML = '<div class="sheet-in"><div class="sheet-head"><b>' + esc(title) + '</b><button class="x" aria-label="بستن">✕</button></div><div id="sheetBody">' + html + '</div></div>';
  sh.classList.remove('hidden');
  sh.onclick = e => { if (e.target === sh) closeSheet(); };
  sh.querySelector('.x').onclick = closeSheet;
  if (onMount) onMount(document.getElementById('sheetBody'));
}
function closeSheet() { const sh = document.getElementById('sheet'); sh.classList.add('hidden'); sh.innerHTML = ''; }
async function shareText(text, title) {
  try {
    if (navigator.share) { await navigator.share({ title: title || 'SalesMate', text }); return true; }
  } catch (e) { if (e && e.name === 'AbortError') return false; }
  try { await navigator.clipboard.writeText(text); toast('متن کپی شد'); return true; } catch (e) { toast('اشتراک‌گذاری ممکن نشد', true); return false; }
}
async function shareBlob(blob, name, text) {
  const file = new File([blob], name, { type: blob.type });
  try {
    if (navigator.canShare && navigator.canShare({ files: [file] })) { await navigator.share({ files: [file], text: text || '' }); return true; }
  } catch (e) { if (e && e.name === 'AbortError') return false; }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
  toast('فایل ذخیره شد'); return true;
}
function debounce(fn, ms) { let t; return function () { const a = arguments; clearTimeout(t); t = setTimeout(() => fn.apply(null, a), ms); }; }
function itemsOf(inv) {                      // اقلام یک حواله از inquiry_data
  let d = inv.inquiry_data || inv.inquiryData; if (!d) return null;
  if (typeof d === 'string') { try { d = JSON.parse(d); } catch (e) { return null; } }
  return d && typeof d === 'object' ? d : null;
}
