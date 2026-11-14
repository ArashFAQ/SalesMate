/* صفحه‌ها (۳): آمار فروش پارکت، سمپل و استند، بالانس موجودی، مشتریان و محاسبات، تنظیمات */
'use strict';

/* ── آمار فروش پارکت (از اسنپ‌شات ویندوز) ── */
function parquetRows(P) {
  return P.rows.map(r => ({ d: r[0], c: P.customers[r[1]] || '', code: r[2], n: P.names[r[3]] || '', a: r[4], m: r[5], wk: weekKey(r[0]) }));
}
function topBuyers(rows, n) {
  const m = {}; rows.forEach(r => { const o = m[r.c] || (m[r.c] = { c: r.c, a: 0, m: 0 }); o.a += r.a; o.m += r.m; });
  return Object.values(m).sort((x, y) => y.a - x.a).slice(0, n);
}
function buyersTable(list) {
  return '<table class="tbl"><tr><th>#</th><th>خریدار</th><th>مبلغ</th><th>متر مربع</th></tr>' + list.map((b, i) => '<tr><td>' + fa(i + 1) + '</td><td class="r">' + esc(b.c) + '</td><td class="n">' + fmt(b.a) + '</td><td class="n">' + fm(b.m, 1) + '</td></tr>').join('') + '</table>';
}
Pages.parquet = {
  title: 'آمار فروش پارکت', state: { tab: 'sum', year: 0, q: '', top: 'week', ty: {} },
  render(root) {
    const P = Store.data.parquet_sales; if (!P) { root.innerHTML = snapMissing('parquet_sales'); return; }
    const st = this.state, all = parquetRows(P), t = todayJ(), ts = t[0] + '/' + p2(t[1]) + '/' + p2(t[2]), cwk = weekKey(ts);
    const ys = Array.from(new Set(all.map(r => r.d.slice(0, 4)).filter(y => /^\d{4}$/.test(y)))).sort().reverse();
    if (!st.year || !ys.includes(String(st.year))) st.year = +(ys[0] || t[0]);
    const sum = rs => rs.reduce((o, r) => (o.a += r.a, o.m += r.m, o), { a: 0, m: 0 });
    const wRows = all.filter(r => r.wk && cwk && r.wk[0] === cwk[0] && r.wk[1] === cwk[1]), mRows = all.filter(r => r.d.slice(0, 7) === t[0] + '/' + p2(t[1])), yRows = all.filter(r => r.d.slice(0, 4) === String(t[0]));
    const tabs = [['sum', 'خلاصه'], ['months', 'ماه‌ها'], ['weeks', 'هفته‌ها'], ['cust', 'مشتریان'], ['codes', 'کدها']];
    let h = '<div class="muted" style="margin:0 4px 8px">آخرین بارگذاری از ویندوز: ' + snapAgo('parquet_sales') + '</div><div class="chips">' + tabs.map(x => '<button class="chip' + (st.tab === x[0] ? ' on' : '') + '" data-t="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>';
    const A = { key: 'amt', name: 'مبلغ (میلیارد ریال)', color: '#1565C0', fmt: v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '' }, M = { key: 'met', name: 'متر مربع', color: '#F59E0B', fmt: v => v ? fa(Math.round(v)) : '' };
    if (st.tab === 'sum') {
      const k = [['b-blue', 'فروش هفته', sum(wRows)], ['b-green', 'فروش ماه', sum(mRows)], ['b-violet', 'فروش سال', sum(yRows)], ['b-amber', 'کل داده', sum(all)]];
      h += '<div class="grid2">' + k.map(x => kpi(x[0], x[1], fmt(x[2].a), fm(x[2].m, 1) + ' متر مربع')).join('') + '</div>';
      const isSt = r => r.c === 'فروشگاه ایزوفام';
      const mon = {}; all.forEach(r => { const k2 = r.d.slice(0, 7); if (k2.length === 7) { const o = (mon[k2] = mon[k2] || [0, 0, 0, 0]); o[0] += r.a; o[1] += r.m; if (isSt(r)) { o[2] += r.a; o[3] += r.m; } } });
      const mk = Object.keys(mon).sort(), pts = []; if (mk.length) { let y = +mk[0].slice(0, 4), m = +mk[0].slice(5); const e = mk[mk.length - 1]; while (y + '/' + p2(m) <= e) { const v = mon[y + '/' + p2(m)] || [0, 0, 0, 0]; pts.push({ label: MONTHS[m - 1], sub: fa(y), t: [v[0] / 1e9, v[1]], s: [v[2] / 1e9, v[3]], c: [(v[0] - v[2]) / 1e9, v[1] - v[3]] }); if (++m > 12) { m = 1; y++; } } }
      const wk = {}; all.forEach(r => { if (r.wk) { const k2 = r.wk[0] * 100 + r.wk[1]; const o = (wk[k2] = wk[k2] || [0, 0, 0, 0]); o[0] += r.a; o[1] += r.m; if (isSt(r)) { o[2] += r.a; o[3] += r.m; } } });
      const wks = Object.keys(wk).map(Number).sort((a, b) => a - b), wp = []; if (wks.length) { let y = Math.floor(wks[0] / 100), w = wks[0] % 100; const e = wks[wks.length - 1]; while (y * 100 + w <= e) { const v = wk[y * 100 + w] || [0, 0, 0, 0]; wp.push({ label: 'هفته ' + fa(w + 1), sub: weekShort(y, w), t: [v[0] / 1e9, v[1]], s: [v[2] / 1e9, v[3]], c: [(v[0] - v[2]) / 1e9, v[1] - v[3]] }); if (++w > 52) { w = 0; y++; } } }
      h += '<div class="card" style="margin-top:12px"><h2>نمودار ماهانه — کل / فروشگاه / شرکت</h2>' + lineChart3(pts.slice(-24), { slot: 84 }) + '</div><div class="card"><h2>نمودار هفتگی — کل / فروشگاه / شرکت</h2>' + lineChart3(wp.slice(-60), { slot: 84 }) + '</div>' + typesBoxHtml('tyBox', st.ty, 'فروش بر اساس نوع پارکت');
    } else if (st.tab === 'months') {
      const cols = ['#E3F2FD', '#E8F5E9', '#FFF8E1', '#FCE4EC', '#EDE7F6', '#E0F7FA', '#FFF3E0', '#F1F8E9', '#E8EAF6', '#FBE9E7', '#E0F2F1', '#F3E5F5'];
      const yr = all.filter(r => r.d.slice(0, 4) === String(st.year));
      h += '<div class="chips">' + ys.map(y => '<button class="chip' + (String(st.year) === y ? ' on' : '') + '" data-y="' + y + '">' + fa(y) + '</button>').join('') + '</div><div class="muted" style="margin:0 4px 8px">روی هر ماه بزنید تا ۱۰ خریدار برتر را ببینید.</div><div class="month-grid">' +
        MONTHS.map((n, k) => { const s = sum(yr.filter(r => +r.d.slice(5, 7) === k + 1)); return '<div class="mcell" data-m="' + (k + 1) + '" style="background:' + cols[k] + ';color:#0F172A"><b>' + n + '</b><div class="v">' + abbr(s.a) + '</div><div class="s">' + fm(s.m, 1) + ' متر مربع</div></div>'; }).join('') + '</div>';
    } else if (st.tab === 'weeks') {
      const wk = {}; all.forEach(r => { if (r.wk) { const k2 = r.wk[0] * 100 + r.wk[1]; (wk[k2] = wk[k2] || { y: r.wk[0], w: r.wk[1], a: 0, m: 0 }); wk[k2].a += r.a; wk[k2].m += r.m; } });
      const list = Object.values(wk).sort((a, b) => (b.y - a.y) || (b.w - a.w)).slice(0, 40);
      h += '<div class="muted" style="margin:0 4px 8px">روی هر هفته بزنید تا ۱۰ خریدار برتر را ببینید.</div>' + list.map(x => '<div class="item" data-w="' + x.y + '|' + x.w + '"><div class="row between"><span class="t">هفته ' + fa(x.w + 1) + ' سال ' + fa(x.y) + '</span><span class="amt">' + fmt(x.a) + '</span></div><div class="row between m"><span>' + weekText(x.y, x.w) + '</span><span>' + fm(x.m, 1) + ' متر مربع</span></div></div>').join('');
    } else if (st.tab === 'cust') {
      const sets = { week: wRows, month: mRows, year: yRows.length >= 1 ? yRows : all };
      h += '<div class="chips">' + [['week', 'هفته جاری'], ['month', 'ماه جاری'], ['year', 'سال جاری'], ['all', 'کل']].map(x => '<button class="chip' + (st.top === x[0] ? ' on' : '') + '" data-top="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>' + buyersTable(topBuyers(st.top === 'all' ? all : sets[st.top], 25));
    } else {
      const m = {}; all.forEach(r => { if (!r.code) return; const ck = codeKey(r.code, r.n) || r.code, o = m[ck] || (m[ck] = { code: ck, a: 0, m: 0, names: {} }); o.a += r.a; o.m += r.m; const nm = codeName(r.code, r.n); o.names[nm] = (o.names[nm] || 0) + 1; });
      const q = customerKey(st.q), list = Object.values(m).sort((a, b) => b.a - a.a).filter(x => !q || x.code.includes(q) || customerKey(Object.keys(x.names).join(' ')).includes(q));
      h += searchBox('جستجوی کد یا نام کالا…', st.q) + '<div id="codes">' + list.slice(0, 150).map((x, i) => { const nm = Object.entries(x.names).sort((a, b) => b[1] - a[1])[0][0]; return '<div class="item"><div class="row between"><span class="t">' + fa(en(x.code)) + '</span><span class="amt">' + fmt(x.a) + '</span></div><div class="row between m"><span class="grow">' + esc(nm) + '</span><span>' + fm(x.m, 1) + ' متر مربع</span></div></div>'; }).join('') + '</div>';
    }
    root.innerHTML = h;
    if (st.tab === 'sum') typesFill(root, 'tyBox', st.ty, all.map(r => ({ d: r.d, code: r.code, n: r.n, a: r.a, m: r.m })), false);
    root.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { st.tab = b.dataset.t; this.render(root); });
    root.querySelectorAll('[data-y]').forEach(b => b.onclick = () => { st.year = +b.dataset.y; this.render(root); });
    root.querySelectorAll('[data-top]').forEach(b => b.onclick = () => { st.top = b.dataset.top; this.render(root); });
    root.querySelectorAll('[data-m]').forEach(el => el.onclick = () => { const mo = +el.dataset.m; openSheet(MONTHS[mo - 1] + ' ' + fa(st.year), buyersTable(topBuyers(all.filter(r => r.d.slice(0, 7) === st.year + '/' + p2(mo)), 10))); });
    root.querySelectorAll('[data-w]').forEach(el => el.onclick = () => { const [y, w] = el.dataset.w.split('|').map(Number); openSheet('هفته ' + fa(w + 1) + ' (' + weekText(y, w) + ')', buyersTable(topBuyers(all.filter(r => r.wk && r.wk[0] === y && r.wk[1] === w), 10))); });
    const qq = root.querySelector('#q'); if (qq) qq.oninput = debounce(e => { st.q = e.target.value; const pos = e.target.selectionStart; this.render(root); const n = root.querySelector('#q'); n.focus(); try { n.setSelectionRange(pos, pos); } catch (x) { } }, 250);
    scrollChartsToEnd(root);
  }
};

/* ── سمپل و استند ── */
const FREE_T = ['سمپل', 'استند', 'نمونه', 'سایر'];
Pages.free = {
  title: 'سمپل و استند', state: { q: '', month: '', cat: 'همه' },
  render(root) {
    const F = Store.data.free_items; if (!F) { root.innerHTML = snapMissing('free_items'); return; }
    const st = this.state, rows = F.rows.map(r => ({ d: r[0], c: F.customers[r[1]] || '', mo: r[2], cat: r[3], t: r[4], n: F.names[r[5]] || '', u: r[6], m: r[7] }));
    const months = Array.from(new Set(rows.map(r => r.mo).filter(Boolean))).sort();
    const pass = r => (!st.month || r.mo === st.month) && (st.cat === 'همه' || (st.cat === 'سایر' ? !['پارکت', 'ام دی اف'].includes(r.cat) : r.cat === st.cat));
    root.innerHTML = '<div class="muted" style="margin:0 4px 8px">آخرین بارگذاری از ویندوز: ' + snapAgo('free_items') + '</div>' + searchBox('جستجوی مشتری…', st.q) +
      '<div class="chips">' + ['همه', 'پارکت', 'ام دی اف', 'سایر'].map(c => '<button class="chip' + (st.cat === c ? ' on' : '') + '" data-cat="' + c + '">' + c + '</button>').join('') + '</div>' +
      '<div class="chips"><button class="chip' + (!st.month ? ' on' : '') + '" data-mo="">همه ماه‌ها</button>' + months.slice(-14).reverse().map(m => '<button class="chip' + (st.month === m ? ' on' : '') + '" data-mo="' + esc(m) + '">' + esc(m) + '</button>').join('') + '</div><div id="kp"></div><div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q), g = {};
      rows.filter(pass).forEach(r => { if (q && !customerKey(r.c).includes(q)) return; const o = g[r.c] || (g[r.c] = { c: r.c, t: {}, tot: 0, m: 0, last: '' }); o.t[r.t] = (o.t[r.t] || 0) + r.u; o.tot += r.u; o.m += r.m; if (r.d > o.last) o.last = r.d; });
      const list = Object.values(g).sort((a, b) => b.tot - a.tot);
      const tt = {}; list.forEach(o => FREE_T.forEach(k => { tt[k] = (tt[k] || 0) + (o.t[k] || 0); }));
      root.querySelector('#kp').innerHTML = '<div class="grid2">' + [['b-blue', 'سمپل'], ['b-violet', 'استند'], ['b-green', 'نمونه'], ['b-slate', 'سایر (قیمت صفر)']].map((x, i) => kpi(x[0], 'کل ' + x[1], fa(Math.round(tt[FREE_T[i]] || 0)))).join('') + '</div><div class="muted" style="margin:8px 4px">' + fa(list.length) + ' مشتری</div>';
      root.querySelector('#list').innerHTML = list.slice(0, 200).map(o => '<div class="item" data-c="' + esc(o.c) + '"><div class="row between"><span class="t">' + esc(o.c) + '</span><span class="amt">' + fa(Math.round(o.tot)) + '</span></div><div class="m">' + FREE_T.filter(k => o.t[k]).map(k => k + ' ' + fa(Math.round(o.t[k]))).join(' · ') + ' · ' + fm(o.m, 1) + ' متر · آخرین ' + fa(o.last) + '</div></div>').join('') || '<div class="empty">موردی نیست</div>';
      root.querySelectorAll('[data-c]').forEach(el => el.onclick = () => {
        const nm = el.dataset.c, rs = rows.filter(r => pass(r) && r.c === nm), tot = {}, prod = {};
        rs.forEach(r => { tot[r.t] = (tot[r.t] || 0) + r.u; const k = r.n + '|' + r.t, o = prod[k] || (prod[k] = { n: r.n || '—', t: r.t, u: 0, m: 0, c: 0 }); o.u += r.u; o.m += r.m; o.c++; });
        openSheet(nm, '<div class="grid2">' + FREE_T.filter(k => tot[k]).map(k => kpi(k === 'سمپل' ? 'b-blue' : k === 'استند' ? 'b-violet' : k === 'نمونه' ? 'b-green' : 'b-slate', k, fa(Math.round(tot[k])))).join('') + '</div><div class="card" style="margin-top:12px"><div class="scrollx"><table class="tbl"><tr><th>کالا</th><th>نوع</th><th>تعداد</th><th>متر مربع</th></tr>' +
          Object.values(prod).sort((a, b) => b.u - a.u).map(p => '<tr><td class="r">' + esc(p.n) + '</td><td>' + esc(p.t) + '</td><td class="n">' + fa(Math.round(p.u)) + '</td><td class="n">' + fm(p.m, 1) + '</td></tr>').join('') + '</table></div></div>');
      });
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    root.querySelectorAll('[data-cat]').forEach(b => b.onclick = () => { st.cat = b.dataset.cat; this.render(root); });
    root.querySelectorAll('[data-mo]').forEach(b => b.onclick = () => { st.month = b.dataset.mo; this.render(root); });
    draw();
  }
};

/* ── بالانس موجودی ── */
Pages.balance = {
  title: 'بالانس موجودی', state: { wh: '', st: 'all', q: '' },
  render(root) {
    const B = Store.data.balance; if (!B) { root.innerHTML = snapMissing('balance'); return; }
    const st = this.state, whs = Array.from(new Set(B.results.map(r => r.wh))), S = B.stats || {};
    const stl = [['all', 'همه'], ['add', 'افزایش'], ['sub', 'کاهش'], ['unmapped', 'بدون نگاشت'], ['balanced', 'بالانس']];
    root.innerHTML = '<div class="muted" style="margin:0 4px 8px">داده‌ی ویندوز: ' + (B.dataReadAt ? fa(String(B.dataReadAt).slice(0, 16).replace('T', ' ')) : snapAgo('balance')) + ' · آستانه ' + fa(B.threshold) + ' م³</div>' +
      '<div class="grid3">' + kpi('b-green', 'بالانس', fa(S.balanced || 0)) + kpi('b-amber', 'افزایش', fa(S.add || 0)) + kpi('b-red', 'کاهش', fa(S.sub || 0)) + '</div>' +
      '<div class="chips" style="margin-top:12px"><button class="chip' + (!st.wh ? ' on' : '') + '" data-wh="">همه انبارها</button>' + whs.map(w => '<button class="chip' + (st.wh === w ? ' on' : '') + '" data-wh="' + esc(w) + '">' + esc(w) + '</button>').join('') + '</div>' +
      '<div class="chips">' + stl.map(x => '<button class="chip' + (st.st === x[0] ? ' on' : '') + '" data-st="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>' + searchBox('جستجوی کد یا شرح…', st.q) + '<div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q), rs = B.results.filter(r => (!st.wh || r.wh === st.wh) && (st.st === 'all' || r.st === st.st) && (!q || customerKey(r.code + ' ' + r.desc + ' ' + r.whCode + ' ' + r.whName).includes(q)));
      root.querySelector('#list').innerHTML = '<div class="muted" style="margin-bottom:6px">' + fa(rs.length) + ' ردیف</div>' + rs.slice(0, 200).map(r => {
        const col = r.st === 'add' ? '#D97706' : r.st === 'sub' ? '#DC2626' : r.st === 'unmapped' ? '#94A3B8' : '#059669';
        return '<div class="item" style="border-inline-start-color:' + col + '"><div class="row between"><span class="t">' + fa(en(r.code)) + ' <span class="tag gray">' + esc(r.wh) + '</span></span><span style="color:' + col + ';font-weight:700">' + esc(fa(r.action).replace(/m³/g, 'م³')) + '</span></div><div class="m">' + esc(r.desc || '') + '</div>' +
          '<div class="row between m"><span>سامانه: <b>' + fm(r.sys, 3) + '</b></span><span>انبار: <b>' + fm(r.whQty, 3) + '</b>' + (r.whCode ? ' (' + esc(fa(r.whCode)) + ')' : '') + '</span></div></div>';
      }).join('') + (rs.length > 200 ? '<div class="muted" style="text-align:center">۲۰۰ مورد اول — فیلتر کنید</div>' : '');
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    root.querySelectorAll('[data-wh]').forEach(b => b.onclick = () => { st.wh = b.dataset.wh; this.render(root); });
    root.querySelectorAll('[data-st]').forEach(b => b.onclick = () => { st.st = b.dataset.st; this.render(root); });
    draw();
  }
};

/* ── مشتریان و محاسبات (فقط مشاهده‌ی دفترچه و آخرین محاسبه) ── */
function cTrunc(v, d) { const m = Math.pow(10, d || 0); return Math.trunc((+v + 2.220446049250313e-16) * m) / m; }
function cTax(a) { a = +a || 0; return a <= 0 ? null : Math.trunc(a / 11 + 1e-6); }
function cPer(a, c) { a = +a || 0; c = +c || 0; return (a <= 0 || c <= 0) ? null : Math.trunc(a * 10 / (11 * c) + 1 + 1e-6); }
Pages.calc = {
  title: 'مشتریان و محاسبات', state: { tab: 'cust', q: '' },
  render(root) {
    const C = Store.data.calc; if (!C) { root.innerHTML = noData('مشتریان و محاسبات') + '<div class="muted" style="text-align:center">فقط حساب مالک دفترچه (در ویندوز) آن را به ابر می‌فرستد.</div>'; return; }
    const st = this.state, sizes = C.sizes || [], calc = C.calc || {};
    root.innerHTML = '<div class="muted" style="margin:0 4px 8px">آخرین ذخیره در ابر: ' + (C.updatedAt ? fa(String(C.updatedAt).slice(0, 16).replace('T', ' ')) : '—') + '</div><div class="chips"><button class="chip' + (st.tab === 'cust' ? ' on' : '') + '" data-t="cust">دفترچه مشتریان</button><button class="chip' + (st.tab === 'calc' ? ' on' : '') + '" data-t="calc">آخرین محاسبه</button></div><div id="body"></div>';
    const body = root.querySelector('#body');
    if (st.tab === 'cust') {
      body.innerHTML = searchBox('جستجوی نام، کد ملی یا تلفن…', st.q) + '<div id="list"></div>';
      const draw = () => { const q = customerKey(st.q), rs = (C.customers || []).filter(c => !q || customerKey([c.customer, c.national_id, c.phone].join(' ')).includes(q)); body.querySelector('#list').innerHTML = rs.slice(0, 250).map(c => '<div class="item"><div class="t">' + esc(c.customer) + '</div><div class="row between m"><span>کد ملی: <span class="ltr">' + fa(esc(c.national_id || '—')) + '</span></span>' + (c.phone ? '<a class="tag green" href="tel:' + esc(en(c.phone)) + '">📞 ' + fa(esc(c.phone)) + '</a>' : '') + '</div></div>').join('') || '<div class="empty">موردی نیست</div>'; };
      body.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150); draw();
    } else {
      let sh = 0, am = 0, cu = 0, tx = 0;
      const rows = sizes.map(s => { const e = calc[s.id] || {}, cnt = +e.count || 0, a = +e.amount || 0, cub = cTrunc((+s.volume || 0) * cnt, 2), tax = cTax(a); sh += cnt; am += a; cu += cub; if (tax) tx += tax; return '<tr><td class="r">' + esc(fa(s.name)) + '</td><td class="n">' + fa(cnt) + '</td><td class="n">' + fm(cub, 2) + '</td><td class="n">' + fmt(a) + '</td><td class="n">' + (cPer(a, cub) ? fmt(cPer(a, cub)) : '—') + '</td><td class="n">' + (tax ? fmt(tax) : '—') + '</td></tr>'; });
      const fc = C.freeCalc || {};
      body.innerHTML = '<div class="grid2">' + kpi('b-blue', 'تعداد ورق', fa(sh)) + kpi('b-green', 'متر مکعب', fm(cTrunc(cu, 2), 2)) + kpi('b-violet', 'مبلغ', fmt(am)) + kpi('b-amber', 'مالیات', fmt(tx)) + '</div><div class="card" style="margin-top:12px"><div class="scrollx"><table class="tbl"><tr><th>سایز</th><th>تعداد</th><th>م³</th><th>مبلغ</th><th>هر م³</th><th>مالیات</th></tr>' + rows.join('') + '</table></div></div>' +
        (fc.amount ? '<div class="card"><h2>محاسبه‌ی آزاد</h2><div class="pill-row"><span>مبلغ</span><b>' + fmt(fc.amount) + '</b></div><div class="pill-row"><span>متر مکعب</span><b>' + fm(cTrunc(fc.cubic, 2), 2) + '</b></div><div class="pill-row"><span>هر متر مکعب</span><b>' + (cPer(fc.amount, cTrunc(fc.cubic, 2)) ? fmt(cPer(fc.amount, cTrunc(fc.cubic, 2))) : '—') + '</b></div><div class="pill-row"><span>مالیات</span><b>' + (cTax(fc.amount) ? fmt(cTax(fc.amount)) : '—') + '</b></div></div>' : '');
    }
    root.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { st.tab = b.dataset.t; this.render(root); });
  }
};

/* ── به‌روزرسانی برنامه ── */
const APK_URL = 'https://github.com/ArashFAQ/salesmate/releases/download/apk-latest/SalesMate.apk';
function verNum(v) { const m = String(v || '').match(/\d+(?:\.\d+)+/); return m ? m[0].split('.').map(Number) : null; }
function verGt(a, b) { a = verNum(a); b = verNum(b); if (!a || !b) return false; for (let i = 0; i < Math.max(a.length, b.length); i++) { const x = a[i] || 0, y = b[i] || 0; if (x !== y) return x > y; } return false; }
async function latestVersions() {
  let apk = null, web = null;
  try { const r = await fetch('https://api.github.com/repos/ArashFAQ/salesmate/releases/tags/apk-latest', { cache: 'no-store' }); if (r.ok) { const j = await r.json(); const m = String(j.body || '').match(/SM_VERSION=(\d+(?:\.\d+)+)/); apk = m ? m[1] : null; } } catch (e) {}
  try { const r = await fetch('https://raw.githubusercontent.com/ArashFAQ/salesmate/main/js/core.js?t=' + Date.now(), { cache: 'no-store' }); if (r.ok) { const t = await r.text(); const m = t.match(/APP_VERSION\s*=\s*'([\d.]+)'/); web = m ? m[1] : null; } } catch (e) {}
  return { apk, web };
}
function openExternal(url) { try { const w = window.open(url, '_system'); if (!w) location.href = url; } catch (e) { location.href = url; } }
function bindUpdateCard(root) {
  const btn = root.querySelector('#upChk'), out = root.querySelector('#upOut'); if (!btn) return;
  btn.onclick = async () => {
    btn.disabled = true; out.innerHTML = '<span class="muted">در حال بررسی…</span>';
    const v = await latestVersions(), isApp = !!window.Capacitor, newest = v.apk || v.web;
    btn.disabled = false;
    if (!newest) { out.innerHTML = '<span class="err-t">اتصال به اینترنت یا گیت‌هاب برقرار نشد.</span>'; return; }
    if (!verGt(newest, APP_VERSION)) { out.innerHTML = '<span class="tag green">نسخه‌ی شما به‌روز است (' + fa(APP_VERSION) + ')</span>'; return; }
    if (isApp) {
      if (v.apk && verGt(v.apk, APP_VERSION)) out.innerHTML = '<div style="margin-bottom:8px">نسخه‌ی جدید <b>' + fa(v.apk) + '</b> آماده است.</div><button class="btn block" id="upGo">⬇ دانلود و نصب نسخه‌ی ' + fa(v.apk) + '</button><div class="muted" style="margin-top:6px;font-size:12px">پس از دانلود، فایل را باز کنید و «نصب» را بزنید (اطلاعات شما پاک نمی‌شود).</div>';
      else out.innerHTML = '<div>نسخه‌ی ' + fa(v.web) + ' منتشر شده ولی فایل نصبی آن هنوز ساخته نشده. کمی بعد دوباره بررسی کنید.</div>';
      const go = out.querySelector('#upGo'); if (go) go.onclick = () => openExternal(APK_URL);
    } else {
      out.innerHTML = '<div style="margin-bottom:8px">نسخه‌ی جدید <b>' + fa(newest) + '</b> موجود است.</div><button class="btn block" id="upGo">⟳ به‌روزرسانی همین حالا</button>';
      out.querySelector('#upGo').onclick = async () => { try { const ks = await caches.keys(); await Promise.all(ks.map(k => caches.delete(k))); const rs = await navigator.serviceWorker.getRegistrations(); await Promise.all(rs.map(r => r.unregister())); } catch (e) {} location.reload(); };
    }
  };
}

/* ── تنظیمات ── */
Pages.settings = {
  title: 'تنظیمات',
  render(root) {
    const names = Object.keys(DS).filter(k => isOwner() || !OWNER_DS.includes(k));
    const th = getTheme();
    root.innerHTML = '<div class="card"><h2>ظاهر برنامه</h2><div class="grid3" style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">' +
      [['auto', '🌓 خودکار'], ['light', '☀️ روشن'], ['dark', '🌙 تاریک']].map(x => '<button class="btn' + (th === x[0] ? '' : ' sec') + '" data-theme-set="' + x[0] + '">' + x[1] + '</button>').join('') +
      '</div><div class="muted" style="margin-top:6px;font-size:12px">«خودکار» از تم گوشی پیروی می‌کند.</div></div>' +
      '<div class="card"><h2>حساب</h2><div class="pill-row"><span>ایمیل</span><b class="ltr">' + esc(Auth.email() || '—') + '</b></div><div class="pill-row"><span>نسخه برنامه</span><b>' + fa(APP_VERSION) + ' (فقط‌خواندنی)</b></div><div class="grid2" style="margin-top:10px"><button class="btn" id="rf">⟳ به‌روزرسانی همه</button><button class="btn sec" id="lo">خروج</button></div></div>' +
      '<div class="card"><h2>به‌روزرسانی برنامه</h2><div class="pill-row"><span>نسخه‌ی نصب‌شده</span><b>' + fa(APP_VERSION) + '</b></div><button class="btn block" id="upChk" style="margin-top:10px">🔍 بررسی نسخه‌ی جدید</button><div id="upOut" style="margin-top:10px"></div></div>' +
      '<div class="card"><h2>وضعیت داده‌ها</h2>' + names.map(k => { const n = Store.data[k] == null ? 0 : (Array.isArray(Store.data[k]) ? Store.data[k].length : (Store.data[k].rows ? Store.data[k].rows.length : (Store.data[k].results ? Store.data[k].results.length : 1))); return '<div class="pill-row"><span>' + esc(DS[k].label) + '</span><span>' + (Store.err[k] ? '<span class="tag red">خطا</span>' : Store.data[k] == null ? '<span class="tag amber">خالی</span>' : '<span class="tag green">' + fa(n) + '</span>') + ' <span class="muted">' + ago(Store.at[k]) + '</span></span></div>' + (Store.err[k] ? '<div class="err-t">' + esc(Store.err[k]) + '</div>' : ''); }).join('') + '</div>' +
      '<div class="card"><h2>راهنما</h2><div class="muted" style="line-height:1.9">• این برنامه فقط از ابر می‌خواند و هیچ چیزی در ابر نمی‌نویسد.<br>• داده‌ها آفلاین هم نمایش داده می‌شوند (آخرین نسخه‌ی دریافت‌شده).<br>• آمار پارکت، سمپل/استند و بالانس را برنامه‌ی ویندوز هنگام «ارسال به ابر» می‌فرستد.<br>• اگر آمار خالی بود: فایل <span class="ltr">SUPABASE_MOBILE.sql</span> را در Supabase اجرا و در ویندوز «ارسال به ابر» را بزنید.</div>' +
      '<button class="btn sec block" id="cc" style="margin-top:10px">پاک‌کردن کش گوشی</button></div>';
    bindUpdateCard(root);
    root.querySelectorAll('[data-theme-set]').forEach(b => b.onclick = () => { setTheme(b.dataset.themeSet); this.render(root); });
    root.querySelector('#rf').onclick = async () => { const f = await refreshAll(); toast(f ? 'بعضی داده‌ها دریافت نشد' : 'به‌روزرسانی شد', !!f); this.render(root); };
    root.querySelector('#lo').onclick = async () => { if (!confirm('از حساب خارج می‌شوید؟')) return; Auth.logout(); await Cache.clear(); location.reload(); };
    root.querySelector('#cc').onclick = async () => { await Cache.clear(); Store.data = {}; toast('کش پاک شد؛ دوباره به‌روزرسانی کنید'); this.render(root); };
  }
};
