/* صفحه‌ها (۱): خانه، حواله‌ها، مشتریان، اطلاعات مشتریان، گزارش‌ها + اجزای مشترک استعلام */
'use strict';
const Pages = {};
const TAB_FA = { parquet: 'پارکت', mdf: 'ام‌دی‌اف', raw: 'ام‌دی‌اف خام' };

function searchBox(ph, val) { return '<input class="search" id="q" type="search" placeholder="' + esc(ph) + '" value="' + esc(val || '') + '" autocomplete="off">'; }
function noData(name) { return '<div class="card empty">' + esc(name) + ' هنوز دریافت نشده.<br>با دکمه‌ی ⟳ بالای صفحه به‌روزرسانی کنید.' + (Store.err[name] ? '<div class="err-t">' + esc(Store.err[name]) + '</div>' : '') + '</div>'; }
function snapMissing(k) {
  return '<div class="card empty">داده‌ی «' + esc(DS[k].label) + '» هنوز در ابر نیست.<br><span class="muted">در ویندوز یک‌بار «ارسال به ابر» را بزنید و فایل SUPABASE_MOBILE.sql را در Supabase اجرا کرده باشید.</span>' + (Store.err[k] ? '<div class="err-t">' + esc(Store.err[k]) + '</div>' : '') + '</div>';
}
function kpi(cls, label, value, sub) { return '<div class="kpi ' + cls + '"><div class="l">' + esc(label) + '</div><div class="v">' + value + '</div>' + (sub ? '<div class="s">' + sub + '</div>' : '') + '</div>'; }

/* ── ستون‌ها و جدول استعلام (مثل خروجی ویندوز) ── */
function inqCols(tab) {
  if (tab === 'mdf') return { h: ['ردیف', 'نوع کالا', 'کد', 'پالت', 'ورق', 'قیمت واحد', 'هزینه (ریال)'], c: r => [r.type || '', r.code || '', qtyInt(r.qty1), fm(num(r.qty2), 3), fmt(r.price), fmt(r.cost)] };
  if (tab === 'raw') return { h: ['ردیف', 'نوع کالا', 'سایز', 'پالت', 'ورق', 'قیمت واحد', 'هزینه (ریال)'], c: r => [r.type || '', r.size || '', qtyInt(r.qty1), fm(num(r.qty2), 3), fmt(r.price), fmt(r.cost)] };
  return { h: ['ردیف', 'کد کالا', 'نوع کالا', 'گرید', 'کارتن', 'متر مربع', 'قیمت واحد', 'هزینه (ریال)'], c: r => [en(r.code || ''), r.type || '', r.grade || '', qtyInt(r.qty1), fm(num(r.qty2), 4), fmt(r.price), fmt(r.cost)] };
}
function inqTotals(d) {
  const rows = d.rows || [], sub = rows.reduce((s, r) => s + amount(r.cost), 0), debt = amount(d.debt), disc = amount(d.discount);
  const total = d.total != null && d.total !== '' ? amount(d.total) : sub + debt - disc;
  return { sub, debt, disc, total };
}
function inqTable(d) {                    // روی موبایل: هر قلم یک کارت خوانا (به‌جای جدول عریض)
  const t = d.tab || 'parquet', rows = d.rows || [], u = t === 'parquet' ? ['کارتن', 'متر مربع'] : ['پالت', 'ورق'];
  return rows.map((r, i) => {
    const title = [r.code ? fa(en(r.code)) : '', r.type || '', r.grade || '', r.size || ''].filter(Boolean).join(' · ');
    return '<div style="border-bottom:1px solid var(--line);padding:8px 0"><div class="row between"><b style="flex:1">' + fa(i + 1) + ') ' + esc(title) + '</b><span class="amt">' + fmt(r.cost) + '</span></div>' +
      '<div class="muted" style="display:flex;gap:14px;flex-wrap:wrap;margin-top:2px">' +
      (r.qty1 !== '' && r.qty1 != null ? '<span>' + u[0] + ': <b>' + fa(qtyInt(r.qty1)) + '</b></span>' : '') +
      (r.qty2 !== '' && r.qty2 != null ? '<span>' + u[1] + ': <b>' + fm(num(r.qty2), 4) + '</b></span>' : '') +
      (r.price ? '<span>فی: <b>' + fmt(r.price) + '</b></span>' : '') + '</div></div>';
  }).join('');
}
function inqSummaryHtml(d) {
  const T = inqTotals(d);
  let h = '<div class="pill-row"><span>جمع اقلام</span><b>' + fmt(T.sub) + ' ریال</b></div>';
  if (T.debt) h += '<div class="pill-row"><span>مانده قبلی</span><b>' + fmt(T.debt) + '</b></div>';
  if (T.disc) h += '<div class="pill-row"><span>تخفیف</span><b>' + fmt(T.disc) + '</b></div>';
  h += '<div class="pill-row"><span><b>مبلغ کل</b></span><b class="amt">' + fmt(T.total) + ' ریال</b></div>';
  return h;
}
function inqMeters(d) { return (d.tab || 'parquet') !== 'parquet' ? 0 : (d.rows || []).reduce((s, r) => s + num(r.qty2), 0); }
function inqSheets(d) { return (d.tab || 'parquet') === 'parquet' ? 0 : (d.rows || []).reduce((s, r) => s + num(r.qty2), 0); }
function inqQty(d) { return (d.tab || 'parquet') === 'parquet' ? fm(inqMeters(d), 1) + ' متر مربع' : fm(inqSheets(d), 0) + ' ورق'; }
function inqText(d, buyerFallback) {                      // متن آماده‌ی پیام‌رسان
  const t = d.tab || 'parquet', rows = d.rows || [], T = inqTotals(d), u = t === 'parquet' ? ['کارتن', 'متر مربع'] : ['پالت', 'ورق'];
  const L = ['*استعلام قیمت' + (TAB_FA[t] ? ' ' + TAB_FA[t] : '') + '*'];
  L.push('خریدار: ' + (d.buyer || buyerFallback || '—'));
  if (d.date) L.push('تاریخ: ' + fa(en(d.date)));
  if (d.warehouse) L.push('انبار: ' + d.warehouse);
  L.push('');
  rows.forEach((r, i) => {
    const b = [fa(i + 1) + ')'];
    if (r.code) b.push('کد ' + fa(en(r.code)));
    if (r.type) b.push(r.type);
    if (r.grade) b.push(r.grade);
    if (r.size) b.push(r.size);
    if (r.qty1 !== '' && r.qty1 != null) b.push(fa(qtyInt(r.qty1)) + ' ' + u[0]);
    if (r.qty2 !== '' && r.qty2 != null) b.push(fm(num(r.qty2), 4) + ' ' + u[1]);
    if (r.price) b.push('فی ' + fmt(r.price));
    b.push('= ' + fmt(r.cost));
    L.push(b.join(' · '));
  });
  L.push('');
  L.push('جمع اقلام: ' + fmt(T.sub) + ' ریال');
  if (T.debt) L.push('مانده قبلی: ' + fmt(T.debt) + ' ریال');
  if (T.disc) L.push('تخفیف: ' + fmt(T.disc) + ' ریال');
  L.push('*مبلغ کل: ' + fmt(T.total) + ' ریال*');
  if (d.transport) L.push('حمل: ' + d.transport);
  if (d.validity) L.push('اعتبار: ' + d.validity);
  if (d.shaba) L.push('شبا: ' + d.shaba);
  return L.join('\n');
}

/* ── خانه ── */
Pages.home = {
  title: 'خانه',
  render(root) {
    const inv = Store.data.invoices;
    if (!inv) { root.innerHTML = noData('حواله‌ها'); return; }
    const t = todayJ(), wk = weekKey(t[0] + '/' + p2(t[1]) + '/' + p2(t[2]));
    let w = 0, wm = 0, m = 0, mm = 0, y = 0, ym = 0, wsh = 0, msh = 0, ysh = 0;
    const mp = t[0] + '/' + p2(t[1]);
    inv.forEach(i => {
      const ds = en(i.date || ''), a = amount(i.total), k = weekKey(ds);
      if (ds.slice(0, 4) === String(t[0])) { y += a; ym += invMeters(i); ysh += invSheets(i); }
      if (ds.slice(0, 7) === mp) { m += a; mm += invMeters(i); msh += invSheets(i); }
      if (k && wk && k[0] === wk[0] && k[1] === wk[1]) { w += a; wm += invMeters(i); wsh += invSheets(i); }
    });
    const cs = customerSummaries(), deb = cs.filter(c => c.bal > 0).sort((a, b) => b.bal - a.bal), cre = cs.filter(c => c.bal < 0).sort((a, b) => a.bal - b.bal);
    const recent = inv.slice().sort((a, b) => (en(b.date) + (b.time || '')).localeCompare(en(a.date) + (a.time || ''))).slice(0, 8);
    const top = cs.filter(c => c.year > 0).sort((a, b) => b.year - a.year).slice(0, 8);
    root.innerHTML =
      '<div class="grid2">' + kpi('b-blue', 'حواله — این هفته', fmt(w), qsub(wm, wsh)) + kpi('b-green', 'حواله — این ماه', fmt(m), qsub(mm, msh)) + '<div style="grid-column:1/-1">' + kpi('b-violet', 'حواله — امسال', fmt(y), qsub(ym, ysh)) + '</div></div>' +
      (isOwner() && Store.data.store ? (() => { const P = storePeriods(); return '<h2 style="margin:14px 4px 6px;font-size:15px">فروشگاه</h2><div class="grid2">' + kpi('b-blue', 'فروشگاه — این هفته', fmt(P.w.a), qsub(P.w.m, P.w.sh)) + kpi('b-green', 'فروشگاه — این ماه', fmt(P.m.a), qsub(P.m.m, P.m.sh)) + '<div style="grid-column:1/-1">' + kpi('b-violet', 'فروشگاه — امسال', fmt(P.y.a), qsub(P.y.m, P.y.sh)) + '</div></div>'; })() : '') +
      '<div class="card" style="margin-top:12px"><h2>حواله‌های اخیر</h2>' + recent.map(invItemHtml).join('') + '</div>' +
      '<div class="card"><h2>برترین مشتریان امسال</h2>' + (top.length ? top.map((c, i) => '<div class="pill-row"><span>' + fa(i + 1) + '. ' + esc(c.name) + '</span><b class="amt">' + fmt(c.year) + '</b></div>').join('') : '<div class="empty">—</div>') + '</div>' +
      '<div class="grid2"><div class="card"><h2 class="debt">بدهکارها</h2>' + (deb.slice(0, 6).map(c => '<div class="pill-row"><span>' + esc(c.name) + '</span><b class="debt">' + fmt(c.bal) + '</b></div>').join('') || '<div class="empty">—</div>') + '</div>' +
      '<div class="card"><h2 class="cred">طلبکارها</h2>' + (cre.slice(0, 6).map(c => '<div class="pill-row"><span>' + esc(c.name) + '</span><b class="cred">' + fmt(-c.bal) + '</b></div>').join('') || '<div class="empty">—</div>') + '</div></div>';
    root.querySelectorAll('[data-inv]').forEach(el => el.onclick = () => showInvoice(+el.dataset.inv));
  }
};

/* ── حواله‌ها ── */
function invItemHtml(i) {
  const b = invBalance(i);
  return '<div class="item cc" style="background:' + customerColor(i.customer) + '" data-inv="' + i.id + '"><div class="row between"><span class="t">' + esc(i.customer) + '</span><span class="amt">' + fmt(i.total) + '</span></div>' +
    '<div class="row between m"><span>شماره ' + fa(en(i.invoice_no || '')) + ' · ' + fa(en(i.date || '')) + '</span>' +
    (b > 0 ? '<span class="pb red">کمتر پرداخت · ' + fmt(b) + '</span>' : b < 0 ? '<span class="pb green">بیشتر پرداخت · ' + fmt(-b) + '</span>' : '<span class="pb ok">تسویه</span>') + '</div></div>';
}
function showInvoice(id) {
  const i = (Store.data.invoices || []).find(x => x.id === id); if (!i) return;
  const d = itemsOf(i), b = invBalance(i);
  let html = '<div class="card"><div class="pill-row"><span>مشتری</span><b>' + esc(i.customer) + '</b></div><div class="pill-row"><span>شماره / تاریخ</span><b>' + fa(en(i.invoice_no || '')) + ' · ' + fa(en(i.date || '')) + ' ' + fa(i.time || '') + '</b></div>' +
    '<div class="pill-row"><span>مبلغ</span><b class="amt">' + fmt(i.total) + ' ریال</b></div><div class="pill-row"><span>پرداختی</span><b>' + fmt((i.paid_amount == null || String(i.paid_amount).trim() === '') ? i.total : i.paid_amount) + '</b></div>' +
    '<div class="pill-row"><span>مانده</span><b class="' + (b > 0 ? 'debt' : 'cred') + '">' + (b > 0 ? 'بدهکار ' + fmt(b) : b < 0 ? 'طلبکار ' + fmt(-b) : 'تسویه') + '</b></div>' +
    (d ? '<div class="pill-row"><span>مقدار</span><b>' + inqQty(d) + '</b></div>' : '') + '</div>';
  if (d && (d.rows || []).length) html += '<div class="card"><h2>اقلام</h2>' + inqTable(d) + inqSummaryHtml(d) + '<button class="btn block" id="shInv" style="margin-top:10px">ارسال متن در پیام‌رسان</button></div>';
  openSheet('حواله ' + fa(en(i.invoice_no || '')), html, body => { const s = body.querySelector('#shInv'); if (s) s.onclick = () => shareText(inqText(d, i.customer)); });
}
Pages.invoices = {
  title: 'حواله‌ها', state: { q: '', ym: '' },
  render(root) {
    const inv = Store.data.invoices; if (!inv) { root.innerHTML = noData('حواله‌ها'); return; }
    const st = this.state, months = {};
    inv.forEach(i => { const k = en(i.date || '').slice(0, 7); if (k.length === 7) months[k] = 1; });
    const ml = Object.keys(months).sort().reverse().slice(0, 14);
    root.innerHTML = searchBox('جستجوی مشتری یا شماره حواله…', st.q) +
      '<div class="chips"><button class="chip' + (!st.ym ? ' on' : '') + '" data-ym="">همه</button>' + ml.map(k => '<button class="chip' + (st.ym === k ? ' on' : '') + '" data-ym="' + k + '">' + MONTHS[+k.slice(5) - 1] + ' ' + fa(k.slice(0, 4)) + '</button>').join('') + '</div><div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q);
      let rows = inv.filter(i => (!st.ym || en(i.date || '').slice(0, 7) === st.ym) && (!q || customerKey(i.customer).includes(q) || en(i.invoice_no || '').includes(q)));
      rows.sort((a, b) => (en(b.date) + (b.time || '')).localeCompare(en(a.date) + (a.time || '')) || b.id - a.id);
      const tot = rows.reduce((s, i) => s + amount(i.total), 0);
      root.querySelector('#list').innerHTML = '<div class="muted" style="margin-bottom:6px">' + fa(rows.length) + ' حواله · جمع ' + fmt(tot) + ' ریال</div>' + (rows.slice(0, 200).map(invItemHtml).join('') || '<div class="empty">موردی نیست</div>') + (rows.length > 200 ? '<div class="muted" style="text-align:center">۲۰۰ مورد اول — جستجو کنید</div>' : '');
      root.querySelectorAll('[data-inv]').forEach(el => el.onclick = () => showInvoice(+el.dataset.inv));
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    root.querySelectorAll('[data-ym]').forEach(b => b.onclick = () => { st.ym = b.dataset.ym; this.render(root); });
    draw();
  }
};

/* ── مشتریان ── */
Pages.customers = {
  title: 'مشتریان', state: { q: '', f: 'all' },
  render(root) {
    if (!Store.data.invoices) { root.innerHTML = noData('حواله‌ها'); return; }
    const st = this.state, cs = customerSummaries();
    root.innerHTML = searchBox('جستجوی نام مشتری…', st.q) + '<div class="chips">' + [['all', 'همه'], ['deb', 'بدهکار'], ['cre', 'طلبکار'], ['year', 'فعال امسال']].map(x => '<button class="chip' + (st.f === x[0] ? ' on' : '') + '" data-f="' + x[0] + '">' + x[1] + '</button>').join('') + '</div><div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q);
      let rows = cs.filter(c => (!q || customerKey(c.name).includes(q)) && (st.f === 'all' || (st.f === 'deb' && c.bal > 0) || (st.f === 'cre' && c.bal < 0) || (st.f === 'year' && c.year > 0)));
      rows.sort((a, b) => st.f === 'deb' ? b.bal - a.bal : st.f === 'cre' ? a.bal - b.bal : b.total - a.total);
      root.querySelector('#list').innerHTML = rows.slice(0, 250).map(c => '<div class="item cc" style="background:' + customerColor(c.name) + '" data-c="' + esc(c.name) + '"><div class="row between"><span class="t">' + esc(c.name) + '</span>' + (c.bal > 0 ? '<span class="pb red">کمتر پرداخت · ' + fmt(c.bal) + '</span>' : c.bal < 0 ? '<span class="pb green">بیشتر پرداخت · ' + fmt(-c.bal) + '</span>' : '<span class="pb ok">تسویه</span>') + '</div><div class="row between m"><span>' + fa(c.count) + ' حواله · آخرین ' + fa(c.last) + '</span><span>جمع ' + abbr(c.total) + '</span></div></div>').join('') || '<div class="empty">موردی نیست</div>';
      root.querySelectorAll('[data-c]').forEach(el => el.onclick = () => showCustomer(el.dataset.c));
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    root.querySelectorAll('[data-f]').forEach(b => b.onclick = () => { st.f = b.dataset.f; this.render(root); });
    draw();
  }
};
function showCustomer(name) {
  const c = customerSummaries().find(x => x.name === name); if (!c) return;
  const invs = (Store.data.invoices || []).filter(i => i.customer === name).sort((a, b) => en(b.date).localeCompare(en(a.date)));
  const years = {}; invs.forEach(i => { const y = en(i.date || '').slice(0, 4); years[y] = (years[y] || 0) + amount(i.total); });
  const ct = (Store.data.contacts || []).find(x => customerKey((x.company || '') + ' ' + (x.first_name || '') + ' ' + (x.last_name || '')).includes(customerKey(name)) || customerKey(name).includes(customerKey((x.first_name || '') + ' ' + (x.last_name || ''))) && (x.first_name || x.last_name));
  openSheet(name,
    '<div class="card"><div class="pill-row"><span>مانده</span><b class="' + (c.bal > 0 ? 'debt' : 'cred') + '">' + (c.bal > 0 ? 'بدهکار ' + fmt(c.bal) : c.bal < 0 ? 'طلبکار ' + fmt(-c.bal) : 'تسویه') + '</b></div><div class="pill-row"><span>تعداد حواله</span><b>' + fa(c.count) + '</b></div><div class="pill-row"><span>جمع خرید</span><b>' + fmt(c.total) + '</b></div>' +
    Object.keys(years).sort().reverse().map(y => '<div class="pill-row"><span>سال ' + fa(y) + '</span><b>' + fmt(years[y]) + '</b></div>').join('') + '</div>' +
    (ct && (ct.mobile || ct.phone) ? '<div class="card row between"><span>' + esc(ct.mobile || ct.phone) + '</span><a class="btn sm green" href="tel:' + esc(en(ct.mobile || ct.phone)) + '">تماس</a></div>' : '') +
    '<div class="card"><h2>حواله‌ها</h2>' + invs.slice(0, 60).map(invItemHtml).join('') + '</div>',
    body => body.querySelectorAll('[data-inv]').forEach(el => el.onclick = () => showInvoice(+el.dataset.inv)));
}

/* ── اطلاعات مشتریان ── */
Pages.contacts = {
  title: 'اطلاعات مشتریان', state: { q: '' },
  render(root) {
    const list = Store.data.contacts; if (!list) { root.innerHTML = noData('اطلاعات مشتریان'); return; }
    const st = this.state;
    root.innerHTML = searchBox('جستجوی نام، شرکت، شهر یا شماره…', st.q) + '<div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q);
      const rows = list.filter(c => !q || customerKey([c.first_name, c.last_name, c.company, c.city, c.phone, c.mobile].join(' ')).includes(q));
      root.querySelector('#list').innerHTML = rows.slice(0, 200).map(c => {
        const nm = ((c.first_name || '') + ' ' + (c.last_name || '')).trim() || c.company || '—', tel = c.mobile || c.phone || '';
        return '<div class="card"><div class="row between"><b>' + esc(nm) + '</b><span class="tag">' + esc(c.city || '') + '</span></div>' + (c.company && c.company !== nm ? '<div class="muted">' + esc(c.company) + '</div>' : '') +
          (c.address ? '<div class="muted">' + esc(c.address) + '</div>' : '') +
          '<div class="row wrap" style="margin-top:8px">' + (c.mobile ? '<a class="btn sm green" href="tel:' + esc(en(c.mobile)) + '">📞 ' + fa(esc(c.mobile)) + '</a><a class="btn sm sec" href="sms:' + esc(en(c.mobile)) + '">پیامک</a>' : '') + (c.phone ? '<a class="btn sm sec" href="tel:' + esc(en(c.phone)) + '">☎ ' + fa(esc(c.phone)) + '</a>' : '') + '</div></div>';
      }).join('') || '<div class="empty">موردی نیست</div>';
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    draw();
  }
};

/* ── گزارش‌ها ── */
Pages.reports = {
  title: 'گزارش‌ها', state: { year: 0 },
  render(root) {
    const inv = Store.data.invoices; if (!inv) { root.innerHTML = noData('حواله‌ها'); return; }
    const st = this.state, ys = Array.from(new Set(inv.map(i => en(i.date || '').slice(0, 4)).filter(y => /^\d{4}$/.test(y)))).sort().reverse();
    if (!st.year || !ys.includes(String(st.year))) st.year = +(ys[0] || todayJ()[0]);
    const mk = y => { const a = Array(12).fill(0), m = Array(12).fill(0); inv.forEach(i => { const ds = en(i.date || ''); if (ds.slice(0, 4) === String(y)) { const k = +ds.slice(5, 7) - 1; if (k >= 0 && k < 12) { a[k] += amount(i.total); m[k] += invMeters(i); } } }); return { a, m }; };
    const cur = mk(st.year), prev = mk(st.year - 1);
    const pts = MONTHS.map((n, k) => ({ label: n, cur: cur.a[k] / 1e9, prev: prev.a[k] / 1e9, met: cur.m[k] }));
    const tot = cur.a.reduce((s, x) => s + x, 0), totM = cur.m.reduce((s, x) => s + x, 0);
    const tc = {}; inv.forEach(i => { if (en(i.date || '').slice(0, 4) === String(st.year)) tc[i.customer] = (tc[i.customer] || 0) + amount(i.total); });
    const top = Object.entries(tc).sort((a, b) => b[1] - a[1]).slice(0, 15);
    const cols = ['#E3F2FD', '#E8F5E9', '#FFF8E1', '#FCE4EC', '#EDE7F6', '#E0F7FA', '#FFF3E0', '#F1F8E9', '#E8EAF6', '#FBE9E7', '#E0F2F1', '#F3E5F5'];
    root.innerHTML = '<div class="chips">' + ys.map(y => '<button class="chip' + (String(st.year) === y ? ' on' : '') + '" data-y="' + y + '">' + fa(y) + '</button>').join('') + '</div>' +
      '<div class="grid2">' + kpi('b-blue', 'فروش ' + fa(st.year), fmt(tot)) + kpi('b-green', 'متر مربع', fm(totM, 1) + ' متر مربع') + '</div>' +
      '<div class="card" style="margin-top:12px"><h2>فروش ماهانه (میلیارد ریال)</h2>' + lineChart(pts, [{ key: 'cur', name: fa(st.year), color: '#1565C0', fmt: v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '' }, { key: 'prev', name: fa(st.year - 1), color: '#F59E0B', fmt: v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '' }], { slot: 62 }) + '</div>' +
      '<div class="card"><h2>ماه‌ها</h2><div class="month-grid">' + MONTHS.map((n, k) => '<div class="mcell" style="background:' + cols[k] + ';color:#0F172A"><b>' + n + '</b><div class="v">' + abbr(cur.a[k]) + '</div><div class="s">' + fm(cur.m[k], 1) + ' متر مربع</div></div>').join('') + '</div></div>' +
      '<div class="card"><h2>برترین مشتریان ' + fa(st.year) + '</h2>' + top.map((x, i) => '<div class="pill-row"><span>' + fa(i + 1) + '. ' + esc(x[0]) + '</span><b class="amt">' + fmt(x[1]) + '</b></div>').join('') + '</div>';
    root.querySelectorAll('[data-y]').forEach(b => b.onclick = () => { st.year = +b.dataset.y; this.render(root); });
    scrollChartsToEnd(root);
  }
};
