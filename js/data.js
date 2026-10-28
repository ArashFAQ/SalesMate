/* لایه‌ی داده: همه چیز فقط از ابر خوانده می‌شود و در IndexedDB کش می‌شود (آفلاین هم می‌توان دید) */
'use strict';
const OWNER_DS = ['store', 'calc', 'parquet_sales', 'free_items', 'balance', 'sales_report'];
const DS = {
  invoices: { path: u => '/rest/v1/invoices?user_id=eq.' + u + '&select=id,customer,invoice_no,date,time,total,paid_amount,created_at,inquiry_data&order=id.asc', user: true, label: 'حواله‌ها' },
  balances: { path: u => '/rest/v1/customer_balances?user_id=eq.' + u + '&select=customer,adjustment', user: true, label: 'مانده‌ها' },
  inquiries: { path: u => '/rest/v1/inquiries?user_id=eq.' + u + '&select=id,payload,created_at&order=id.desc', user: true, label: 'استعلام‌ها' },
  store: { path: u => '/rest/v1/store_sales?user_id=eq.' + u + '&select=id,customer,invoice_no,date,time,total,tab,items_json,created_at&order=id.asc', user: true, label: 'فروشگاه' },
  inventory: { path: () => '/rest/v1/inventory_items?select=product_code,product_name,cartons,meters,design_codes,updated_at&order=product_code.asc', label: 'موجودی' },
  contacts: { path: () => '/rest/v1/customer_contacts?select=id,first_name,last_name,company,phone,mobile,city,address&order=id.asc', label: 'اطلاعات مشتریان' },
  calc: { path: u => '/rest/v1/calc_notebook?user_id=eq.' + u + '&select=payload,updated_at&order=updated_at.desc&limit=1', user: true, label: 'مشتریان و محاسبات', single: true },
  parquet_sales: { snap: true, label: 'آمار پارکت' },
  free_items: { snap: true, label: 'سمپل و استند' },
  balance: { snap: true, label: 'بالانس موجودی' },
  sales_report: { snap: true, label: 'تحلیل فروش' }
};
const Store = { data: {}, at: {}, err: {}, busy: false };

async function loadCached() {                                  // بلافاصله از کش بخوان
  await Promise.all(Object.keys(DS).filter(k => isOwner() || !OWNER_DS.includes(k)).map(async k => {
    const c = await Cache.get('ds_' + k);
    if (c) { Store.data[k] = c.data; Store.at[k] = c.at; }
  }));
}
async function fetchOne(k) {
  const d = DS[k], uid = Auth.sess().user_id;
  let data;
  if (d.snap) {
    const rows = await sbGet('/rest/v1/mobile_snapshots?key=eq.' + k + '&select=payload,updated_at');
    data = rows && rows[0] ? rows[0].payload : null;
  } else {
    try { data = await sbAll(d.path(uid)); }
    catch (e) {
      if (d.user && (e.status === 400 || e.status === 404)) data = await sbAll(d.path(uid).replace(/user_id=eq\.[^&]+&?/, ''));   // جدول بدون ستون user_id
      else throw e;
    }
    if (d.single) data = data && data[0] ? data[0].payload : null;
  }
  Store.data[k] = data; Store.at[k] = Date.now(); delete Store.err[k];
  await Cache.set('ds_' + k, { data: data, at: Store.at[k] });
  return data;
}
async function refreshAll(only) {
  if (Store.busy || !Auth.ok()) return;
  Store.busy = true;
  const bar = document.getElementById('progress'), btn = document.getElementById('refreshBtn');
  bar.classList.remove('hidden'); btn.classList.add('spin');
  let fails = 0;
  try {
    await Promise.all((only || Object.keys(DS)).filter(k => isOwner() || !OWNER_DS.includes(k)).map(k => fetchOne(k).catch(e => { Store.err[k] = e.message; fails++; })));
  } finally { Store.busy = false; bar.classList.add('hidden'); btn.classList.remove('spin'); }
  Store.lastAll = Date.now(); lsSet('sm_last', Store.lastAll);
  return fails;
}

/* ───────── مشتق‌ها ───────── */
function invBalance(inv) { const t = amount(inv.total), p = (inv.paid_amount == null || String(inv.paid_amount).trim() === '') ? t : amount(inv.paid_amount); return t - p; }
function invMeters(inv) {                 // فقط پارکت: متر مربع
  const d = itemsOf(inv); if (!d || (d.tab || 'parquet') !== 'parquet') return 0;
  return (d.rows || []).reduce((s, r) => s + num(r.qty2), 0);
}
function invSheets(inv) {                 // ام‌دی‌اف: ورق
  const d = itemsOf(inv); if (!d || (d.tab || 'parquet') === 'parquet') return 0;
  return (d.rows || []).reduce((s, r) => s + num(r.qty2), 0);
}
/* تشخیص کالای ام‌دی‌اف (پالت/ورق) از نام کالا؛ بقیه پارکت (کارتن/متر مربع) */
function isMdfName(n) {
  n = String(n || '').toLowerCase().replace(/[\u200c\u200f]/g, ' ');
  if (n.includes('پارکت')) return false;
  return /mdf|ام دی اف|امدیاف|هایگلاس|ملامینه|خام|ورق|پالت/.test(n);
}
function qsub(m, sh) { return fm(m, 1) + ' متر مربع' + (sh ? ' · ' + fm(sh, 0) + ' ورق' : ''); }
function customerSummaries() {
  const inv = Store.data.invoices || [], adj = {};
  (Store.data.balances || []).forEach(b => { adj[b.customer] = amount(b.adjustment); });
  const m = {}, ty = todayJ()[0];
  inv.forEach(i => {
    const n = i.customer || '—', c = m[n] || (m[n] = { name: n, count: 0, total: 0, last: '', bal: 0, year: 0 });
    const t = amount(i.total), ds = en(i.date || '');
    c.count++; c.total += t; c.bal += invBalance(i);
    if (ds > c.last) c.last = ds;
    if (ds.slice(0, 4) === String(ty)) c.year += t;
  });
  Object.keys(adj).forEach(n => { if (!m[n]) m[n] = { name: n, count: 0, total: 0, last: '', bal: 0, year: 0 }; m[n].bal += adj[n]; });
  return Object.values(m);
}
function storeItems(s) {
  let it = s.items_json; if (typeof it === 'string') { try { it = JSON.parse(it); } catch (e) { it = []; } }
  return Array.isArray(it) ? it.filter(x => x && typeof x === 'object') : [];
}
function storeMeters(s) { return (s.tab && s.tab !== 'parquet') ? 0 : storeItems(s).reduce((a, r) => a + num(r.qty2), 0); }
function storeSheets(s) { return (s.tab && s.tab !== 'parquet') ? storeItems(s).reduce((a, r) => a + num(r.qty2), 0) : 0; }
function ago(ts) {
  if (!ts) return '—';
  const m = Math.round((Date.now() - ts) / 60000);
  if (m < 1) return 'همین حالا';
  if (m < 60) return fa(m) + ' دقیقه پیش';
  if (m < 1440) return fa(Math.round(m / 60)) + ' ساعت پیش';
  return fa(Math.round(m / 1440)) + ' روز پیش';
}
function snapAgo(k) { const p = Store.data[k]; return p && p.at ? ago(Date.parse(p.at)) : '—'; }

/* جمع فروش فروشگاه: هفته/ماه/سال جاری {a: مبلغ، m: متر مربع پارکت، sh: ورق ام‌دی‌اف} */
function storePeriods() {
  const t = todayJ(), cw = weekKey(t[0] + '/' + p2(t[1]) + '/' + p2(t[2])), out = { w: { a: 0, m: 0, sh: 0 }, m: { a: 0, m: 0, sh: 0 }, y: { a: 0, m: 0, sh: 0 } };
  (Store.data.store || []).forEach(s => {
    const ds = en(s.date || ''), k = weekKey(ds), y = +ds.slice(0, 4), mo = +ds.slice(5, 7), a = amount(s.total), m = storeMeters(s), sh = storeSheets(s);
    const add = o => { o.a += a; o.m += m; o.sh += sh; };
    if (y === t[0]) add(out.y); if (y === t[0] && mo === t[1]) add(out.m); if (k && cw && k[0] === cw[0] && k[1] === cw[1]) add(out.w);
  });
  return out;
}

/* رنگ مشتری مثل ویندوز: رتبه‌ی فروش امسال روی طیف قرمز ← زرد ← سبز؛ بدون فروش = خاکستری */
let _ccKey = null, _ccMap = {};
function customerColor(name) {
  const inv = Store.data.invoices || [], ty = String(todayJ()[0]), key = inv.length + '|' + ty;
  if (_ccKey !== key) {
    _ccKey = key; const sales = {};
    inv.forEach(i => { const n = String(i.customer || '').trim(); if (!n) return; if (!(n in sales)) sales[n] = 0; if (en(i.date || '').slice(0, 4) === ty) sales[n] += amount(i.total); });
    const ranked = Object.entries(sales).sort((a, b) => a[1] - b[1] || (a[0] < b[0] ? -1 : 1)), npos = ranked.filter(x => x[1] > 0).length, used = new Set(); _ccMap = {}; let rank = 0;
    const lerp = (a, b, t) => Math.floor(a + (b - a) * t), h = v => ('0' + Math.min(255, v).toString(16)).slice(-2).toUpperCase();
    ranked.forEach(([n, s]) => {
      if (s <= 0) { _ccMap[n] = '#D1D5DB'; return; }
      const t = npos <= 1 ? 1 : rank / (npos - 1); rank++; let r, g, b;
      if (t >= 0.5) { const u = (t - 0.5) * 2; r = lerp(250, 5, u); g = lerp(204, 140, u); b = lerp(20, 50, u); } else { const u = t * 2; r = lerp(200, 250, u); g = lerp(30, 204, u); b = lerp(30, 20, u); }
      let col = '#' + h(r + 18) + h(g + 18) + h(b + 18), k = 0; while (used.has(col)) { k++; col = '#' + h(r + 18) + h(g + 18) + h(b + 18 + k); } used.add(col); _ccMap[n] = col;
    });
  }
  return _ccMap[String(name || '').trim()] || '#D1D5DB';
}
