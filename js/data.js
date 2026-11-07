/* لایه‌ی داده: همه چیز فقط از ابر خوانده می‌شود و در IndexedDB کش می‌شود (آفلاین هم می‌توان دید) */
'use strict';
const OWNER_DS = ['store', 'calc', 'parquet_sales', 'free_items', 'balance', 'sales_report', 'cheques_transit'];
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
  sales_report: { snap: true, label: 'تحلیل فروش' },
  cheques_transit: { snap: true, label: 'چک‌های در راه' },
  cw_cheques: { path: u => '/rest/v1/coworker_snapshots?assignee=eq.' + u + '&select=cheques', user: true, single: true, col: 'cheques', label: 'چک‌های در راه (همکار)' }
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
    if (d.single) data = data && data[0] ? data[0][d.col || 'payload'] : null;
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

/* چک‌های در راه (فقط مالک؛ فقط مشتری‌های خود مالک — از اسنپ‌شات ابری) */
let _trMap = null, _trSrc = null;
function transitFor(name) {
  // مالک: اسنپ‌شات مشتری‌های خودش؛ همکار: ردیف خودش در coworker_snapshots (فقط مشتری‌های واگذارشده)
  const d = isOwner() ? Store.data.cheques_transit : Store.data.cw_cheques;
  if (!d || !d.customers) return [];
  if (_trSrc !== d) {
    _trSrc = d; _trMap = {};
    const t = todayJ(), td = new Date(Date.UTC(...j2g(t[0], t[1], t[2]).slice(0, 3).map((v, i) => i === 1 ? v - 1 : v)));
    Object.keys(d.customers).forEach(n => {
      const rows = d.customers[n].filter(r => {                      // اسنپ‌شات ممکن است تا یک روز قدیمی باشد: قانون ۲ هفته دوباره اعمال شود
        const q = en(String(r[0])).split('/').map(Number); if (q.length < 3 || !q[0]) return false;
        const g = j2g(q[0], q[1], q[2]), dd = new Date(Date.UTC(g[0], g[1] - 1, g[2]));
        return (dd - td) / 864e5 >= -14;
      });
      if (rows.length) _trMap[customerKey(n)] = rows;
    });
  }
  return _trMap[customerKey(name)] || [];
}
function transitSum(rows) { return rows.reduce((s, r) => s + amount(r[1]), 0); }
function transitCanvas(name, rows) {
  const W = 800, S = 3, font = 'Vazirmatn, Tahoma, sans-serif', BLUE = '#1565C0', AMB = '#B45309', RH = 38, n = rows.length;
  const H = 70 + 12 + 70 + 12 + 34 + n * RH + 56 + 16;
  const cv = document.createElement('canvas'); cv.width = W * S; cv.height = H * S; const c = cv.getContext('2d'); c.scale(S, S); c.direction = 'rtl'; c.textBaseline = 'middle';
  const rr = (x, y, w, h, r, f) => { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); c.fillStyle = f; c.fill(); };
  const tx = (t, x, y, al, f, col) => { c.textAlign = al; c.font = f; c.fillStyle = col; c.fillText(t, x, y); };
  c.fillStyle = '#fff'; c.fillRect(0, 0, W, H);
  rr(0, 0, W, 70, [14, 14, 0, 0], BLUE); tx('چک‌های در راه', W - 18, 26, 'right', '800 18px ' + font, '#fff'); tx('SalesMate', W - 18, 52, 'right', '500 12px ' + font, 'rgba(255,255,255,.9)');
  let y = 82; const bw = (W - 10) / 1.7;
  rr(W - bw, y, bw, 70, 12, BLUE); tx('نام مشتری', W - 16, y + 18, 'right', '500 11px ' + font, 'rgba(255,255,255,.85)'); tx(name, W - 16, y + 44, 'right', '800 16px ' + font, '#fff');
  const dw = bw * 0.7; rr(0, y, dw, 70, 12, BLUE); tx('تاریخ گزارش', dw - 16, y + 18, 'right', '500 11px ' + font, 'rgba(255,255,255,.85)'); const t = todayJ(); tx(fa(jfmt(t[0], t[1], t[2])), dw - 16, y + 44, 'right', '800 16px ' + font, '#fff');
  y += 70 + 12;
  const fr = [0.10, 0.25, 0.30, 0.35], cx = []; let acc = W; fr.forEach(f => { const w = f * W; cx.push(acc - w / 2); acc -= w; });
  rr(0, y, W, 34, 0, BLUE); ['ردیف', 'تاریخ چک', 'شماره چک', 'مبلغ (ریال)'].forEach((h, j) => tx(h, cx[j], y + 17, 'center', '700 12px ' + font, '#fff')); y += 34;
  rows.forEach((r, i) => { c.fillStyle = i % 2 ? '#fff' : '#f0f9ff'; c.fillRect(0, y, W, RH); [fa(i + 1), fa(r[0]), fa(r[2] || '—')].forEach((v, j) => tx(v, cx[j], y + RH / 2, 'center', '500 13px ' + font, '#0F172A')); tx(fmt(r[1]), cx[3], y + RH / 2, 'center', '800 14px ' + font, '#0F172A'); c.fillStyle = '#e0f2fe'; c.fillRect(0, y + RH - 1, W, 1); y += RH; });
  y += 12; rr(0, y, W, 44, 12, '#FFF7ED'); tx('جمع کل چک‌های در راه', W - 18, y + 22, 'right', '700 14px ' + font, '#64748B'); tx(fmt(transitSum(rows)) + ' ریال', 18, y + 22, 'left', '900 18px ' + font, AMB);
  return cv;
}
function showTransit(name) {
  const rows = transitFor(name);
  const sorted = rows.slice().sort((a, b) => String(a[0]).localeCompare(String(b[0])));
  openSheet('چک‌های در راه — ' + name,
    '<div class="card"><div class="pill-row"><span>تعداد چک</span><b>' + fa(sorted.length) + '</b></div>' +
    '<table class="tbl"><tr><th>تاریخ چک</th><th>شماره چک</th><th>مبلغ (ریال)</th></tr>' +
    sorted.map(r => '<tr><td>' + fa(r[0]) + '</td><td>' + fa(r[2] || '—') + '</td><td>' + fmt(r[1]) + '</td></tr>').join('') +
    '<tr><td colspan="2"><b>جمع کل</b></td><td><b>' + fmt(transitSum(sorted)) + '</b></td></tr></table></div>' +
    '<div class="grid2"><button class="btn block" id="trImg">🖼 ارسال تصویر</button><button class="btn block" id="trPdf">📄 ارسال PDF</button></div>',
    body => {
      const build = async () => { try { await document.fonts.ready; } catch (e) { } return transitCanvas(name, sorted); };
      const txt = 'چک‌های در راه ' + name + ': ' + fmt(transitSum(sorted)) + ' ریال';
      body.querySelector('#trImg').onclick = async () => shareCanvas(await build(), 'chek_' + name, 'png', txt);
      body.querySelector('#trPdf').onclick = async () => shareCanvas(await build(), 'chek_' + name, 'pdf', txt);
    });
}

/* ───────── مشتق‌ها ─────────
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
  return Array.isArray(it) ? sampleLast(it.filter(x => x && typeof x === 'object')) : [];
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

/* ── نوع پارکت (جناغی / والنته / بقیه) و ادغام A/B جناغی ── */
const CH_CODES = ['6542', '6332', '6234', '6223', '6224', '6435', '6545', '6433', '6235'];
const VAL_CODES = ['7414', '7323', '7322', '7335', '7434', '7524', '7634', '7343', '7465'];
function parquetType(code, name) {
  const nm = String(name || ''), low = nm.toLowerCase(), c = en(String(code || '')).replace(/\D/g, '');
  if (nm.includes('جناغی') || nm.includes('جناقی')) return 'جناغی';
  if (low.includes('valente') || nm.includes('والنته') || nm.includes('ولنته')) return 'والنته';
  if (CH_CODES.includes(c)) return 'جناغی';
  if (VAL_CODES.includes(c)) return 'والنته';
  return 'بقیه';
}
function codeKey(code, name) {
  const c = en(String(code || '')).trim();
  if (parquetType(c, name) === 'جناغی') { const nm = en(String(name || '')); const m = nm.match(/(\d{4})\s*[ABab]?\s*$/) || nm.match(/(\d{4})(?!.*\d{4})/) || c.match(/^\s*(\d{1,5})(?!\d)/); if (m) return m[1]; }
  return c;
}
function codeName(code, name) {
  let nm = String(name || '').trim();
  if (parquetType(code, nm) === 'جناغی') nm = nm.replace(/[\s\-_]*\b[ABab]\s*$/, '').trim();
  return nm;
}
function normDate(s) {
  const p = en(String(s || '')).replace(/-/g, '/').split('/').map(x => parseInt(x, 10));
  return (p.length >= 3 && p.every(x => !isNaN(x))) ? p[0] + '/' + String(p[1]).padStart(2, '0') + '/' + String(p[2]).padStart(2, '0') : '';
}
/* rows: [{d, code, n, a, m, q}] — کارت‌های جناغی/والنته/بقیه + (اختیاری) جدول کدهای پرفروش */
function typesBoxHtml(id, st, title) {
  const t = todayJ();
  if (!st.f) st.f = t[0] + '/01/01';
  if (!st.t) st.t = t[0] + '/' + p2(t[1]) + '/' + p2(t[2]);
  return '<div class="card" id="' + id + '"><h2>' + title + '</h2><div class="row" style="gap:8px;margin-bottom:8px"><label class="grow muted">از<input class="search" data-df type="text" inputmode="numeric" dir="ltr" value="' + esc(fa(st.f)) + '"></label><label class="grow muted">تا<input class="search" data-dt type="text" inputmode="numeric" dir="ltr" value="' + esc(fa(st.t)) + '"></label></div><div data-out></div></div>';
}
function typesFill(root, id, st, rows, withCodes) {
  const box = root.querySelector('#' + id); if (!box) return;
  const out = box.querySelector('[data-out]');
  const draw = () => {
    const d1 = normDate(st.f), d2 = normDate(st.t);
    const sub = rows.filter(r => { const d = normDate(r.d); return (!d1 || (d && d >= d1)) && (!d2 || (d && d <= d2)); });
    const S = { 'جناغی': { a: 0, m: 0 }, 'والنته': { a: 0, m: 0 }, 'بقیه': { a: 0, m: 0 } }, codes = {};
    sub.forEach(r => {
      const k = parquetType(r.code, r.n); S[k].a += r.a; S[k].m += r.m;
      if (withCodes) { const ck = codeKey(r.code, r.n); if (ck) { const o = codes[ck] || (codes[ck] = { code: ck, a: 0, m: 0, q: 0, names: {} }); o.a += r.a; o.m += r.m; o.q += (r.q || 0); const nm = codeName(r.code, r.n); if (nm) o.names[nm] = (o.names[nm] || 0) + 1; } }
    });
    const tot = { a: S['جناغی'].a + S['والنته'].a + S['بقیه'].a, m: S['جناغی'].m + S['والنته'].m + S['بقیه'].m };
    const kp = (cls, l, v) => kpi(cls, l, fmt(v.a), fm(v.m, 1) + ' متر مربع');
    let h = '<div class="grid2">' + kp('b-amber', 'پارکت جناغی', S['جناغی']) + kp('b-violet', 'پارکت والنته', S['والنته']) + kp('b-blue', 'بقیه‌ی پارکت‌ها', S['بقیه']) + kp('b-green', 'جمع پارکت', tot) + '</div>';
    if (withCodes) {
      const list = Object.values(codes).sort((x, y) => y.a - x.a || y.m - x.m).slice(0, 40);
      h += '<h2 style="margin:12px 2px 6px;font-size:14px">پرفروش‌ترین کدها (بر اساس مبلغ)</h2>' + (list.length ? '<div style="max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:10px"><table class="tbl"><tr><th>#</th><th>کد / نام</th><th>کارتن</th><th>متر مربع</th><th>مبلغ</th></tr>' +
        list.map((x, i) => { const nm = Object.entries(x.names).sort((a, b) => b[1] - a[1])[0]; return '<tr><td>' + fa(i + 1) + '</td><td class="r"><b>' + fa(x.code) + '</b><div class="muted" style="font-size:11px">' + esc(nm ? nm[0] : '') + '</div></td><td class="n">' + fa(Math.round(x.q)) + '</td><td class="n">' + fm(x.m, 1) + '</td><td class="n">' + fmt(x.a) + '</td></tr>'; }).join('') + '</table></div>' : '<div class="empty">کدی در این بازه نیست</div>');
    }
    h += '<div class="muted" style="margin-top:6px">' + fa(sub.length) + ' ردیف · تشخیص از نام کالا: «جناغی» و «Valente/والنته»</div>';
    out.innerHTML = h;
  };
  box.querySelector('[data-df]').oninput = e => { st.f = en(e.target.value); draw(); };
  box.querySelector('[data-dt]').oninput = e => { st.t = en(e.target.value); draw(); };
  draw();
}
