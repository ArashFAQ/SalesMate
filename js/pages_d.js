/* تحلیل فروش (فقط مالک): فروش کل شرکت، ام‌دی‌اف خام، ام‌دی‌اف (کل/هایگلاس/ملامینه) — فقط جمع‌ها، بدون ریز حواله */
'use strict';
Pages.salesrep = {
  title: 'تحلیل فروش', state: { tab: 'all', sub: 'mdf', year: 0 },
  groups(st) { return st.tab === 'all' ? ['all'] : st.tab === 'raw' ? ['raw'] : st.sub === 'hg' ? ['hg'] : st.sub === 'mel' ? ['mel'] : ['hg', 'mel']; },
  render(root) {
    const R = Store.data.sales_report; if (!R) { root.innerHTML = snapMissing('sales_report'); return; }
    const st = this.state, gs = this.groups(st), withQty = true, t = todayJ(), cw = weekKey(t[0] + '/' + p2(t[1]) + '/' + p2(t[2]));
    const rows = (R.rows || []).filter(r => gs.includes(r[1]));
    const ys = Array.from(new Set(rows.map(r => r[0].slice(0, 4)).filter(y => /^\d{4}$/.test(y)))).sort().reverse();
    if (!st.year || !ys.includes(String(st.year))) st.year = +(ys[0] || t[0]);
    const mon = {}, wk = {}, mA = Array(12).fill(0), mQ = Array(12).fill(0), P = { w: [0, 0], m: [0, 0], y: [0, 0] };
    rows.forEach(r => {
      const ds = r[0], y = +ds.slice(0, 4), mo = +ds.slice(5, 7), k = weekKey(ds), a = r[2], q = r[3];
      if (y === st.year && mo >= 1 && mo <= 12) { mA[mo - 1] += a; mQ[mo - 1] += q; }
      if (y && mo >= 1 && mo <= 12) { const mk = y * 100 + mo; (mon[mk] = mon[mk] || [0, 0]); mon[mk][0] += a; mon[mk][1] += q; }
      if (k) { const kk = k[0] * 100 + k[1]; (wk[kk] = wk[kk] || [0, 0]); wk[kk][0] += a; wk[kk][1] += q; }
      if (y === t[0]) { P.y[0] += a; P.y[1] += q; if (mo === t[1]) { P.m[0] += a; P.m[1] += q; } }
      if (k && cw && k[0] === cw[0] && k[1] === cw[1]) { P.w[0] += a; P.w[1] += q; }
    });
    const mpts = [], wpts = [], mks = Object.keys(mon).map(Number).sort((a, b) => a - b), wks = Object.keys(wk).map(Number).sort((a, b) => a - b);
    if (mks.length) { let y = Math.floor(mks[0] / 100), m = mks[0] % 100; const e = mks[mks.length - 1]; while (y * 100 + m <= e) { const v = mon[y * 100 + m] || [0, 0]; mpts.push({ label: MONTHS[m - 1], sub: fa(y), amt: v[0] / 1e9, q: v[1] }); if (++m > 12) { m = 1; y++; } } }
    if (wks.length) { let y = Math.floor(wks[0] / 100), w = wks[0] % 100; const e = wks[wks.length - 1]; while (y * 100 + w <= e) { const v = wk[y * 100 + w] || [0, 0]; wpts.push({ label: 'هفته ' + fa(w + 1), sub: weekShort(y, w), amt: v[0] / 1e9, q: v[1], y, w }); if (++w > 52) { w = 0; y++; } } }
    const A = { key: 'amt', name: 'مبلغ (میلیارد ریال)', color: '#1565C0', fmt: v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '' }, Q = { key: 'q', name: 'ورق', color: '#F59E0B', fmt: v => v ? fa(Math.round(v)) : '' }, ser = withQty ? [A, Q] : [A];
    const cols = ['#E3F2FD', '#E8F5E9', '#FFF8E1', '#FCE4EC', '#EDE7F6', '#E0F7FA', '#FFF3E0', '#F1F8E9', '#E8EAF6', '#FBE9E7', '#E0F2F1', '#F3E5F5'];
    const sub = q => withQty ? fm(q, 0) + ' ورق' : '', tabs = [['all', 'فروش کل شرکت (بدون پارکت)'], ['raw', 'ام‌دی‌اف خام'], ['mdf', 'ام‌دی‌اف']];
    let h = '<div class="muted" style="margin:0 4px 8px">آخرین بارگذاری از ویندوز: ' + snapAgo('sales_report') + '</div><div class="chips">' + tabs.map(x => '<button class="chip' + (st.tab === x[0] ? ' on' : '') + '" data-t="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>';
    if (st.tab === 'mdf') h += '<div class="chips">' + [['mdf', 'کل ام‌دی‌اف'], ['hg', 'هایگلاس'], ['mel', 'ملامینه']].map(x => '<button class="chip' + (st.sub === x[0] ? ' on' : '') + '" data-s="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>';
    h += '<div class="chips">' + ys.map(y => '<button class="chip' + (String(st.year) === y ? ' on' : '') + '" data-y="' + y + '">' + fa(y) + '</button>').join('') + '</div>' +
      '<div class="grid2">' + kpi('b-blue', 'این هفته', fmt(P.w[0]), sub(P.w[1])) + kpi('b-green', 'این ماه', fmt(P.m[0]), sub(P.m[1])) + '<div style="grid-column:1/-1">' + kpi('b-violet', 'امسال', fmt(P.y[0]), sub(P.y[1])) + '</div></div>' +
      '<div class="card" style="margin-top:12px"><h2>ماه‌ها — ' + fa(st.year) + '</h2><div class="month-grid">' + MONTHS.map((n, k) => '<div class="mcell" style="background:' + cols[k] + ';color:#0F172A"><b>' + n + '</b><div class="v">' + abbr(mA[k]) + '</div>' + (withQty ? '<div class="s">' + fm(mQ[k], 0) + ' ورق</div>' : '') + '</div>').join('') + '</div></div>' +
      '<div class="card"><h2>نمودار ماهانه' + (withQty ? ' (مبلغ و ورق)' : ' (مبلغ)') + '</h2>' + lineChart(mpts.slice(-24), ser, { slot: 74 }) + '</div>' +
      '<div class="card"><h2>نمودار هفتگی' + (withQty ? ' (مبلغ و ورق)' : ' (مبلغ)') + '</h2>' + lineChart(wpts.slice(-60), ser, { slot: 82 }) + '</div>' +
      '<div class="card"><h2>هفته‌های اخیر</h2>' + wpts.slice(-12).reverse().map(x => '<div class="pill-row"><span>هفته ' + fa(x.w + 1) + ' · ' + weekText(x.y, x.w) + '</span><span dir="rtl"><b>' + fmt(x.amt * 1e9) + '</b>' + (withQty ? ' · ' + fm(x.q, 0) + ' ورق' : '') + '</span></div>').join('') + '</div>';
    root.innerHTML = h;
    root.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { st.tab = b.dataset.t; this.render(root); });
    root.querySelectorAll('[data-s]').forEach(b => b.onclick = () => { st.sub = b.dataset.s; this.render(root); });
    root.querySelectorAll('[data-y]').forEach(b => b.onclick = () => { st.year = +b.dataset.y; this.render(root); });
    scrollChartsToEnd(root);
  }
};
