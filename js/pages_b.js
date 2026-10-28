/* صفحه‌ها (۲): استعلام (+تصویر برای پیام‌رسان)، موجودی، راس چک، فروشگاه */
'use strict';

/* ── رندر تصویر استعلام روی Canvas (RTL) ── */
function wrapLines(ctx, text, maxW) {
  const words = String(text || '').split(/\s+/), out = []; let cur = '';
  words.forEach(w => { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width <= maxW || !cur) cur = t; else { out.push(cur); cur = w; } });
  if (cur) out.push(cur); return out.length ? out : [''];
}
function renderInquiryCanvas(d, buyerFallback) {      // دقیقاً هم‌قالب خروجی ویندوز
  const t = d.tab || 'parquet', rows = d.rows || [], T = inqTotals(d), W = 800, S = 3.5, font = 'Vazirmatn, Tahoma, sans-serif', BLUE = '#0284c7';
  const heads = t === 'parquet' ? ['ردیف', 'کد کالا', 'نوع کالا', 'گرید', 'مقدار (کارتن)', 'مقدار (متر مربع)', 'قیمت واحد (ریال)', 'هزینه کالا (ریال)'] : t === 'mdf' ? ['ردیف', 'نوع کالا', 'کد', 'مقدار (پالت)', 'مقدار (ورق)', 'قیمت واحد (ریال)', 'هزینه کالا (ریال)'] : ['ردیف', 'نوع کالا', 'سایز', 'مقدار (پالت)', 'مقدار (ورق)', 'قیمت واحد (ریال)', 'هزینه کالا (ریال)'];
  const fr = t === 'parquet' ? [0.06, 0.10, 0.17, 0.08, 0.13, 0.14, 0.15, 0.17] : [0.07, 0.27, 0.14, 0.11, 0.13, 0.13, 0.15], cw = fr.map(f => f * W);
  const cells = rows.map((r, i) => (t === 'parquet' ? [fa(i + 1), fa(en(r.code || '—')), r.type || '', r.grade || '', fa(qtyInt(r.qty1) || '—'), fa(r.qty2 || '—'), fmt(r.price), fmt(r.cost)] : t === 'mdf' ? [fa(i + 1), r.type || '', fa(en(r.code || '—')), fa(qtyInt(r.qty1) || '—'), fa(r.qty2 || '—'), fmt(r.price), fmt(r.cost)] : [fa(i + 1), r.type || '', fa(en(r.size || '')), fa(qtyInt(r.qty1) || '—'), fa(r.qty2 || '—'), fmt(r.price), fmt(r.cost)]));
  const mc = document.createElement('canvas').getContext('2d'); mc.font = '500 12px ' + font;
  const rh = cells.map(cs => { let n = 1; cs.forEach((c, j) => { n = Math.max(n, wrapLines(mc, c, cw[j] - 10).length); }); return 14 + n * 18; });
  const terms = ['پس از واریز مبلغ به حساب شرکت و تأیید واحد حسابداری، حواله خروج بار صادر می‌گردد.', 'پس از خروج کالا از انبار شرکت هیچ مسئولیتی از لحاظ کمیت و کیفیت/سلامت کالا ندارد.', 'پس از فروش کالا به هیچ عنوان مرجوعی و ابطال حواله انجام نمی‌شود.'];
  mc.font = '500 11px ' + font; const valL = d.validity ? (mc.font = '600 12px ' + font, wrapLines(mc, d.validity, W - 70)) : [];
  const wordsTxt = (T.total ? numberToWords(T.total) : 'صفر') + ' ریال'; mc.font = '500 14px ' + font; const wL = wrapLines(mc, wordsTxt, W - 50);
  const termsH = 16 + 26 + terms.length * 24 + (valL.length ? 12 + valL.length * 20 : 0) + (d.shaba ? 38 : 0) + 16;
  const H = 70 + 12 + 78 + 12 + 34 + rh.reduce((a, b) => a + b, 0) + 14 + 5 * 30 + 24 + 14 + (90 + wL.length * 22) + 14 + termsH + 12;
  const cv = document.createElement('canvas'); cv.width = W * S; cv.height = H * S; const c = cv.getContext('2d'); c.scale(S, S); c.direction = 'rtl'; c.textBaseline = 'middle';
  const rr = (x, y, w, h, r, f, st) => { c.beginPath(); c.roundRect ? c.roundRect(x, y, w, h, r) : c.rect(x, y, w, h); if (f) { c.fillStyle = f; c.fill(); } if (st) { c.strokeStyle = st; c.lineWidth = 1; c.stroke(); } };
  const tx = (s, x, y, al, f, col) => { c.textAlign = al; c.font = f; c.fillStyle = col; c.fillText(s, x, y); };
  c.fillStyle = '#fff'; c.fillRect(0, 0, W, H);
  rr(0, 0, W, 70, [14, 14, 0, 0], BLUE); tx('استعلام کالا — ' + (TAB_FA[t] || ''), W - 18, 26, 'right', '800 18px ' + font, '#fff'); tx('SalesMate', W - 18, 52, 'right', '500 12px ' + font, 'rgba(255,255,255,.9)');
  let y = 82; const bw = (W - 10) / 1.7;
  rr(W - bw, y, bw, 78, 12, BLUE); tx('خریدار', W - 16, y + 18, 'right', '500 11px ' + font, 'rgba(255,255,255,.85)'); tx(d.buyer || buyerFallback || '—', W - 16, y + 46, 'right', '800 16px ' + font, '#fff');
  const dw = bw * 0.7; rr(0, y, dw, 78, 12, BLUE); tx('تاریخ', dw - 16, y + 18, 'right', '500 11px ' + font, 'rgba(255,255,255,.85)'); tx(fa(en(d.date || '—')), dw - 16, y + 46, 'right', '800 16px ' + font, '#fff');
  y += 78 + 12;
  c.fillStyle = BLUE; c.fillRect(0, y, W, 34); let x = W; heads.forEach((h, j) => { tx(h, x - cw[j] / 2, y + 17, 'center', '600 11px ' + font, '#fff'); x -= cw[j]; }); y += 34;
  cells.forEach((cs, i) => {
    c.fillStyle = i % 2 ? '#f8fafc' : '#fff'; c.fillRect(0, y, W, rh[i]); let xx = W;
    cs.forEach((cell, j) => { const ls = wrapLines(c, cell, cw[j] - 10); c.font = '500 12px ' + font; ls.forEach((l, k) => tx(l, xx - cw[j] / 2, y + 7 + 9 + k * 18 + (rh[i] - 14 - ls.length * 18) / 2, 'center', '500 12px ' + font, '#0f172a')); xx -= cw[j]; });
    c.strokeStyle = '#e2e8f0'; c.lineWidth = 1; c.beginPath(); c.moveTo(0, y + rh[i]); c.lineTo(W, y + rh[i]); c.stroke(); y += rh[i];
  });
  y += 14; rr(0.5, y, W - 1, 5 * 30 + 20, 12, '#f8fafc', '#e2e8f0'); y += 10;
  [['مبلغ کل اقلام', fmt(T.sub), 1], ['انبارداری', d.warehouse || '—'], ['حمل', d.transport || 'به عهده مشتری می‌باشد'], ['بدهی پیشین', T.debt ? fmt(T.debt) : '۰'], ['تخفیف', T.disc ? fmt(T.disc) : '۰']].forEach(r => { tx(r[0], W - 14, y + 15, 'right', '500 12px ' + font, '#0f172a'); tx(r[1], 14, y + 15, 'left', (r[2] ? '700' : '500') + ' 12px ' + font, '#0f172a'); y += 30; });
  y += 10 + 14; const th = 90 + wL.length * 22; rr(0, y, W, th, 14, BLUE);
  tx('جمع کل قابل پرداخت', W - 18, y + 24, 'right', '500 13px ' + font, 'rgba(255,255,255,.8)');
  const tt = fmt(T.total); c.font = '900 24px ' + font; const tw = c.measureText(tt).width; tx(tt, 18, y + 58, 'left', '900 24px ' + font, '#fff'); tx('ریال', 18 + tw + 8, y + 60, 'left', '500 15px ' + font, '#fff');
  wL.forEach((l, k) => tx(l, W - 18, y + 88 + k * 22, 'right', '500 14px ' + font, 'rgba(255,255,255,.92)')); y += th + 14;
  rr(0.5, y, W - 1, termsH, 12, '#f8fafc', '#e2e8f0'); let ty = y + 26; tx('شرایط و نکات مهم', W - 18, ty, 'right', '600 14px ' + font, BLUE); ty += 28;
  terms.forEach(s => { tx('• ' + s, W - 18, ty, 'right', '500 11px ' + font, '#475569'); ty += 24; });
  if (valL.length) { ty += 2; valL.forEach(l => { tx(l, W - 18, ty, 'right', '600 12px ' + font, '#1e293b'); ty += 20; }); }
  if (d.shaba) { c.strokeStyle = '#cbd5e1'; c.setLineDash([3, 3]); c.beginPath(); c.moveTo(18, ty); c.lineTo(W - 18, ty); c.stroke(); c.setLineDash([]); ty += 16; tx('شبا: ' + d.shaba, W - 18, ty, 'right', '500 12px ' + font, '#475569'); }
  return cv;
}
async function shareInquiryImage(d, buyer, kind) {
  try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) { }
  await shareCanvas(renderInquiryCanvas(d, buyer), 'estelam_' + (d.buyer || buyer || 'x'), kind, 'استعلام کالا — جمع کل: ' + fmt(inqTotals(d).total) + ' ریال');
}
async function delCloudInq(d, done) {
  if (!d || !confirm('استعلام «' + (d.buyer || '') + '» حذف شود؟')) return;
  const rid = d._rid; let cloud = false;
  try { if (rid != null) cloud = (await sbDelete('/rest/v1/inquiries?id=eq.' + encodeURIComponent(rid))) > 0; } catch (e) { }
  const hid = lsGet('sm_inq_hidden', []); hid.push(String(rid)); lsSet('sm_inq_hidden', hid.slice(-500));
  toast(cloud ? 'از ابر و گوشی حذف شد' : 'از لیست گوشی حذف شد (حذف از ابر ممکن نبود)'); done && done();
}
function showInquiry(d, buyer) {
  const T = inqTotals(d);
  openSheet('استعلام ' + (d.buyer || buyer || ''), '<div class="card insq"><div class="h">استعلام قیمت ' + (TAB_FA[d.tab || 'parquet'] || '') + '</div>' +
    '<div class="pill-row"><span>خریدار</span><b>' + esc(d.buyer || buyer || '—') + '</b></div><div class="pill-row"><span>تاریخ</span><b>' + fa(en(d.date || '—')) + '</b></div>' + (d.warehouse ? '<div class="pill-row"><span>انبار</span><b>' + esc(d.warehouse) + '</b></div>' : '') +
    '<div style="margin:8px 0">' + inqTable(d) + '</div>' + inqSummaryHtml(d) +
    (d.transport ? '<div class="muted" style="margin-top:6px">حمل: ' + esc(d.transport) + '</div>' : '') + (d.validity ? '<div class="muted">اعتبار: ' + esc(d.validity) + '</div>' : '') + (d.shaba ? '<div class="muted">شبا: ' + esc(d.shaba) + '</div>' : '') + '</div>' +
    '<div class="grid2"><button class="btn block" id="shImg">🖼 ارسال تصویر</button><button class="btn block" id="shPdf">📄 ارسال PDF</button></div><div style="margin-top:8px"><button class="btn sec block" id="shTxt">💬 ارسال متن</button></div>' +
    (d._rid != null ? '<div style="margin-top:8px"><button class="btn sec block" id="shDel" style="color:#B91C1C">🗑 حذف این استعلام</button></div>' : '') + '<div class="grid2" style="margin-top:8px"><a class="btn sec block" id="shWa" target="_blank" rel="noopener">واتس‌اپ</a><a class="btn sec block" id="shTg" target="_blank" rel="noopener">تلگرام</a></div>',
    body => {
      const txt = inqText(d, buyer);
      body.querySelector('#shImg').onclick = () => shareInquiryImage(d, buyer);
      body.querySelector('#shPdf').onclick = () => shareInquiryImage(d, buyer, 'pdf');
      body.querySelector('#shTxt').onclick = () => shareText(txt);
      const sd = body.querySelector('#shDel'); if (sd) sd.onclick = () => delCloudInq(d, () => { closeSheet(); rerender(); });
      body.querySelector('#shWa').href = 'https://wa.me/?text=' + encodeURIComponent(txt);
      body.querySelector('#shTg').href = 'https://t.me/share/url?url=%20&text=' + encodeURIComponent(txt);
    });
}
Pages.inquiry = {
  title: 'استعلام', state: { q: '' },
  render(root) {
    const list = Store.data.inquiries; if (!list) { root.innerHTML = noData('استعلام‌ها'); return; }
    const st = this.state;
    const hid = lsGet('sm_inq_hidden', []), items = list.filter(r => !hid.includes(String(r.id))).map(r => { let p = r.payload; if (typeof p === 'string') { try { p = JSON.parse(p); } catch (e) { p = null; } } if (p && typeof p === 'object') { p = Object.assign({}, p); p._rid = r.id; return p; } return null; }).filter(Boolean)
      .sort((a, b) => String(b.savedAt || b.id || '').localeCompare(String(a.savedAt || a.id || '')));
    root.innerHTML = searchBox('جستجوی نام خریدار…', st.q) + '<div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q), rows = items.filter(d => !q || customerKey(d.buyer).includes(q));
      root.querySelector('#list').innerHTML = rows.slice(0, 150).map((d, i) => { const T = inqTotals(d); return '<div class="item" data-i="' + i + '"><div class="row between"><span class="t">' + esc(d.buyer || '—') + '</span><span class="amt">' + fmt(T.total) + '</span></div><div class="row between m"><span>' + fa(en(d.date || '')) + ' · ' + fa((d.rows || []).length) + ' قلم · ' + inqQty(d) + '</span><span class="row"><span class="tag">' + (TAB_FA[d.tab || 'parquet'] || '') + '</span><button class="btn sm sec" data-del="' + i + '" style="padding:2px 9px">🗑</button></span></div></div>'; }).join('') || '<div class="empty">استعلامی نیست</div>';
      root.querySelectorAll('[data-i]').forEach(el => el.onclick = () => showInquiry(rows[+el.dataset.i]));
      root.querySelectorAll('[data-del]').forEach(el => el.onclick = e => { e.stopPropagation(); delCloudInq(rows[+el.dataset.del], () => Pages.inquiry.render(root.closest('#app') || root)); });
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    draw();
  }
};

/* ── موجودی ── */
Pages.inventory = {
  title: 'موجودی', state: { q: '', f: 'all', c: 'all' },
  render(root) {
    const list = Store.data.inventory; if (!list) { root.innerHTML = noData('موجودی'); return; }
    const st = this.state;
    const upd = list.reduce((m, x) => (x.updated_at && x.updated_at > m ? x.updated_at : m), '');
    const P = list.filter(x => !isMdfName(x.product_name)), M = list.filter(x => isMdfName(x.product_name));
    const sum = (a, k) => a.reduce((s, x) => s + (+x[k] || 0), 0), n0 = v => fa(Math.round(v).toLocaleString('en-US'));
    root.innerHTML = '<div class="grid2">' + kpi('b-blue', 'پارکت — جمع کارتن', n0(sum(P, 'cartons'))) + kpi('b-green', 'پارکت — جمع متر مربع', fm(sum(P, 'meters'), 1)) + kpi('b-violet', 'ام‌دی‌اف — جمع پالت', n0(sum(M, 'cartons'))) + kpi('b-amber', 'ام‌دی‌اف — جمع ورق', n0(sum(M, 'meters'))) + '</div>' +
      '<div class="muted" style="margin:6px 4px 10px">آخرین به‌روزرسانی موجودی: ' + (upd ? fa(upd.slice(0, 16).replace('T', ' ')) : '—') + '</div>' +
      searchBox('جستجوی نام کالا…', st.q) + '<div class="chips">' + [['all', 'همه کالاها'], ['p', 'پارکت'], ['m', 'ام‌دی‌اف']].map(x => '<button class="chip' + (st.c === x[0] ? ' on' : '') + '" data-c="' + x[0] + '">' + x[1] + '</button>').join('') + '</div>' +
      '<div class="chips">' + [['all', 'همه'], ['pos', 'موجود'], ['zero', 'تمام‌شده']].map(x => '<button class="chip' + (st.f === x[0] ? ' on' : '') + '" data-f="' + x[0] + '">' + x[1] + '</button>').join('') + '</div><div id="list"></div>';
    const draw = () => {
      const q = customerKey(st.q);
      const rows = list.filter(x => (st.c === 'all' || (st.c === 'm') === isMdfName(x.product_name)) && (!q || customerKey(x.product_name || '').includes(q)) && (st.f === 'all' || (st.f === 'pos' ? (+x.cartons > 0 || +x.meters > 0) : !(+x.cartons > 0 || +x.meters > 0))));
      root.querySelector('#list').innerHTML = '<div class="muted" style="margin-bottom:6px">' + fa(rows.length) + ' کالا</div>' + rows.slice(0, 300).map(x => {
        const z = !(+x.cartons > 0 || +x.meters > 0), mdf = isMdfName(x.product_name);
        return '<div class="item" style="border-inline-start-color:' + (z ? '#DC2626' : '#059669') + '"><div class="row between"><span class="t">' + fa(en(x.product_code || '')) + '</span><span class="' + (z ? 'debt' : 'amt') + '">' + fa(qtyInt(x.cartons)) + (mdf ? ' پالت' : ' کارتن') + '</span></div>' +
          '<div class="row between m"><span class="grow">' + esc(x.product_name || '') + '</span><b>' + (mdf ? fm(x.meters, 0) + ' ورق' : fm(x.meters, 2) + ' متر مربع') + '</b></div>' + (x.design_codes ? '<div class="muted">طرح: ' + esc(x.design_codes) + '</div>' : '') + '</div>';
      }).join('') + (rows.length > 300 ? '<div class="muted" style="text-align:center">۳۰۰ مورد اول — جستجو کنید</div>' : '');
    };
    root.querySelector('#q').oninput = debounce(e => { st.q = e.target.value; draw(); }, 150);
    root.querySelectorAll('[data-f]').forEach(b => b.onclick = () => { st.f = b.dataset.f; this.render(root); });
    root.querySelectorAll('[data-c]').forEach(b => b.onclick = () => { st.c = b.dataset.c; this.render(root); });
    draw();
  }
};

/* ── راس چک (محاسبه‌ی محلی؛ همان منطق ویندوز) ── */
function pyRound(x) { const f = Math.floor(x), d = x - f; if (Math.abs(d - 0.5) < 1e-12) return f % 2 === 0 ? f : f + 1; return Math.round(x); }
function commas(v) { const s = en(v).replace(/[^\d]/g, ''); return s ? s.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : ''; }
const Ras = {
  st: lsGet('sm_ras', null) || { base: '', rows: [{ d: '', a: '' }, { d: '', a: '' }] },
  today() { const t = todayJ(); return t[0] + '/' + p2(t[1]) + '/' + p2(t[2]); },
  norm(v) { v = en(v || '').trim(); if (!v) return ''; const p = parseFlexJ(v); return p ? p[0] + '/' + p2(p[1]) + '/' + p2(p[2]) : v; },
  save() { lsSet('sm_ras', this.st); },
  calc() {
    const t = todayJ(), baseTxt = this.st.base.trim(), bp = baseTxt ? parseFlexJ(baseTxt, t[0]) : t;
    if (!bp) return { err: 'تاریخ مبدأ نامعتبر است.' };
    const bg = j2g(bp[0], bp[1], bp[2]), base = Date.UTC(bg[0], bg[1] - 1, bg[2]);
    const items = [];
    for (let i = 0; i < this.st.rows.length; i++) {
      const r = this.st.rows[i], a = amount(r.a), p = parseFlexJ(r.d, bp[0]);
      if (!p && !String(r.a).trim()) continue;
      if (!p) return { err: 'تاریخ ردیف ' + fa(i + 1) + ' نامعتبر است.' };
      if (a <= 0) return { err: 'مبلغ ردیف ' + fa(i + 1) + ' را وارد کنید.' };
      const g = j2g(p[0], p[1], p[2]), ts = Date.UTC(g[0], g[1] - 1, g[2]);
      items.push({ a, delta: Math.round((ts - base) / 864e5), ts, p });
    }
    if (!items.length) return { err: 'حداقل یک چک با تاریخ و مبلغ وارد کنید.' };
    const total = items.reduce((s, x) => s + x.a, 0), avg = items.reduce((s, x) => s + x.a * x.delta, 0) / total, ar = pyRound(avg);
    const rd = new Date(base + ar * 864e5), rj = g2j(rd.getUTCFullYear(), rd.getUTCMonth() + 1, rd.getUTCDate());
    items.sort((x, y) => x.ts - y.ts);
    return { items, total, avg, ar, ras: jfmt(rj[0], rj[1], rj[2]), base: jfmt(bp[0], bp[1], bp[2]), days: ar > 0 ? fa(ar) + ' روز بعد' : ar < 0 ? fa(-ar) + ' روز قبل' : 'همان روز مبدأ' };
  },
  canvas(r) {
    const W = 1000, S = 2, pad = 30, font = 'Vazirmatn, Tahoma, sans-serif', n = r.items.length, H = 70 + 150 + 52 + n * 50 + 150;
    const cv = document.createElement('canvas'); cv.width = W * S; cv.height = H * S; const c = cv.getContext('2d'); c.scale(S, S); c.direction = 'rtl'; c.textBaseline = 'middle';
    c.fillStyle = '#fff'; c.fillRect(0, 0, W, H); c.fillStyle = '#1565C0'; c.fillRect(0, 0, W, 70); c.fillStyle = '#fff'; c.font = '700 32px ' + font; c.textAlign = 'center'; c.fillText('راس‌گیری چک', W / 2, 36);
    let y = 90; const kv = (k, v, col) => { c.textAlign = 'right'; c.fillStyle = '#64748B'; c.font = '500 22px ' + font; c.fillText(k, W - pad, y + 16); c.textAlign = 'left'; c.fillStyle = col || '#0F172A'; c.font = '700 24px ' + font; c.fillText(v, pad + 0, y + 16); y += 40; };
    kv('تاریخ مبدأ', fa(r.base)); kv('جمع مبلغ', fmt(r.total) + ' ریال'); kv('میانگین وزنی', fa(r.avg.toFixed(2)) + ' روز');
    y += 6; c.fillStyle = '#1565C0'; c.fillRect(pad, y, W - pad * 2, 44); c.fillStyle = '#fff'; c.font = '700 21px ' + font; c.textAlign = 'center';
    const cx = [W - pad - 40, W - pad - 250, W - pad - 560, pad + 70]; ['#', 'تاریخ', 'مبلغ (ریال)', 'روز'].forEach((h, j) => c.fillText(h, cx[j], y + 23)); y += 44;
    r.items.forEach((x, i) => { c.fillStyle = i % 2 ? '#F1F5F9' : '#fff'; c.fillRect(pad, y, W - pad * 2, 50); c.fillStyle = '#0F172A'; c.font = '500 22px ' + font; c.textAlign = 'center';
      [fa(i + 1), fa(jfmt(x.p[0], x.p[1], x.p[2])), fmt(x.a), fa(x.delta)].forEach((t, j) => c.fillText(t, cx[j], y + 26)); y += 50; });
    y += 20; c.fillStyle = '#ECFDF5'; c.fillRect(pad, y, W - pad * 2, 96); c.textAlign = 'center'; c.fillStyle = '#047857'; c.font = '700 34px ' + font; c.fillText('تاریخ راس: ' + fa(r.ras), W / 2, y + 36); c.font = '500 22px ' + font; c.fillStyle = '#334155'; c.fillText(r.days, W / 2, y + 72);
    return cv;
  },
  text(r) {
    return ['*راس چک*', 'تاریخ مبدأ: ' + r.base].concat(r.items.map((x, i) => 'چک ' + fa(i + 1) + ': ' + jfmt(x.p[0], x.p[1], x.p[2]) + ' · ' + fmt(x.a) + ' ریال · ' + fa(x.delta) + ' روز'))
      .concat(['', 'جمع: ' + fmt(r.total) + ' ریال', 'میانگین وزنی: ' + fa(r.avg.toFixed(2)) + ' روز', '*تاریخ راس: ' + r.ras + '* (' + r.days + ')']).join('\n');
  }
};
Pages.ras = {
  title: 'راس چک',
  render(root) {
    const S = Ras.st, t = todayJ(); if (S.baseDay !== Ras.today()) { S.baseDay = Ras.today(); S.base = Ras.today(); Ras.save(); }
    const rowsH = () => S.rows.map((r, i) => '<div class="row" style="margin-bottom:8px"><div class="grow"><input data-f="d" data-i="' + i + '" class="ltr" inputmode="decimal" placeholder="تاریخ" value="' + esc(r.d) + '"></div><div class="grow"><input data-f="a" data-i="' + i + '" class="ltr" inputmode="numeric" placeholder="مبلغ (ریال)" value="' + esc(r.a) + '"></div><button class="btn sm sec" data-rm="' + i + '" style="padding:10px">✕</button></div>').join('');
    root.innerHTML = '<div class="card"><h2>راس‌گیری چک</h2><label>تاریخ مبدأ (خالی = امروز ' + jfmt(t[0], t[1], t[2]) + ')</label><input id="base" class="ltr" inputmode="decimal" value="' + esc(S.base) + '" placeholder="امروز">' +
      '<h2 style="margin-top:14px">چک‌ها</h2><div id="rows">' + rowsH() + '</div><div class="grid2"><button class="btn sec" id="add">+ افزودن چک</button><button class="btn sec" id="clr">پاک‌کردن همه</button></div>' +
      '<button class="btn green block" id="go" style="margin-top:10px">محاسبه راس</button></div><div id="res"></div>';
    const bind = () => {
      root.querySelectorAll('[data-f]').forEach(inp => {
        inp.oninput = () => { const r = S.rows[+inp.dataset.i]; if (inp.dataset.f === 'a') { const c = commas(inp.value); inp.value = c; r.a = c; } else r.d = inp.value; Ras.save(); };
        const fixD = () => { if (inp.dataset.f === 'd' || inp.id === 'base') { const v = Ras.norm(inp.value); if (v !== inp.value) { inp.value = v; if (inp.id === 'base') S.base = v; else S.rows[+inp.dataset.i].d = v; Ras.save(); } } };
        inp.onblur = fixD;
        inp.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); fixD(); const all = Array.from(root.querySelectorAll('[data-f],#base')), k = all.indexOf(inp);
          if (all[k + 1]) all[k + 1].focus();
          else { S.rows.push({ d: '', a: '' }); Ras.save(); root.querySelector('#rows').innerHTML = rowsH(); bind(); const nd = root.querySelector('[data-f="d"][data-i="' + (S.rows.length - 1) + '"]'); if (nd) nd.focus(); } } };
      });
      root.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { S.rows.splice(+b.dataset.rm, 1); if (!S.rows.length) S.rows.push({ d: '', a: '' }); Ras.save(); root.querySelector('#rows').innerHTML = rowsH(); bind(); });
    };
    const show = () => {
      const r = Ras.calc(), el = root.querySelector('#res');
      if (r.err) { el.innerHTML = '<div class="card err-t">' + esc(r.err) + '</div>'; return; }
      el.innerHTML = '<div class="grid3">' + kpi('b-blue', 'جمع مبلغ', fmt(r.total)) + kpi('b-amber', 'روز از مبدأ', r.days) + kpi('b-green', 'تاریخ راس', r.ras) + '</div>' +
        '<div class="card" style="margin-top:12px"><h2>جزئیات (به ترتیب تاریخ)</h2>' + r.items.map((x, i) => '<div class="pill-row"><span>چک ' + fa(i + 1) + ': ' + jfmt(x.p[0], x.p[1], x.p[2]) + '</span><span dir="rtl">' + fmt(x.a) + ' ریال ‏· ' + fa(x.delta) + ' روز</span></div>').join('') +
        '<div class="pill-row"><span>میانگین وزنی</span><b>' + fa(r.avg.toFixed(2)) + ' روز</b></div><div class="grid2" style="margin-top:10px"><button class="btn block" id="shi">🖼 ارسال تصویر</button><button class="btn block" id="shp">📄 ارسال PDF</button></div><button class="btn sec block" id="shr" style="margin-top:8px">💬 ارسال متن</button></div>';
      el.querySelector('#shr').onclick = () => shareText(Ras.text(r));
      el.querySelector('#shi').onclick = async () => { try { await document.fonts.ready; } catch (e) { } shareCanvas(Ras.canvas(r), 'ras_' + r.ras.replace(/\//g, '-'), 'png'); };
      el.querySelector('#shp').onclick = async () => { try { await document.fonts.ready; } catch (e) { } shareCanvas(Ras.canvas(r), 'ras_' + r.ras.replace(/\//g, '-'), 'pdf'); };
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    };
    root.querySelector('#base').oninput = e => { S.base = e.target.value; Ras.save(); };
    root.querySelector('#base').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); e.target.value = S.base = Ras.norm(e.target.value); Ras.save(); const f = root.querySelector('[data-f="d"]'); if (f) f.focus(); } };
    root.querySelector('#add').onclick = () => { S.rows.push({ d: '', a: '' }); Ras.save(); root.querySelector('#rows').innerHTML = rowsH(); bind(); };
    root.querySelector('#clr').onclick = () => { S.rows = [{ d: '', a: '' }, { d: '', a: '' }]; Ras.save(); this.render(root); };
    root.querySelector('#go').onclick = () => { root.querySelectorAll('[data-f="d"]').forEach(x => { x.value = Ras.norm(x.value); S.rows[+x.dataset.i].d = x.value; }); Ras.save(); show(); };
    bind();
  }
};

/* ── فروشگاه ── */
function storeLine(it, tab) {
  const b = []; if (it.code) b.push('کد ' + fa(en(it.code))); if (it.type || it.typ) b.push(it.type || it.typ); if (it.grade) b.push(it.grade); if (it.size) b.push(it.size);
  const u = tab === 'parquet' ? ['کارتن', 'متر مربع'] : ['پالت', 'ورق'];
  if (it.qty1 !== '' && it.qty1 != null) b.push(fa(qtyInt(it.qty1)) + ' ' + u[0]);
  if (it.qty2 !== '' && it.qty2 != null) b.push(fa(String(it.qty2)) + ' ' + u[1]);
  if (it.price) b.push('فی ' + fmt(it.price)); if (it.cost) b.push('مبلغ ' + fmt(it.cost));
  return b.join(' · ');
}
Pages.store = {
  title: 'فروشگاه', state: { year: 0 },
  render(root) {
    const list = Store.data.store; if (!list) { root.innerHTML = noData('فروشگاه'); return; }
    const st = this.state, t = todayJ(), cw = weekKey(t[0] + '/' + p2(t[1]) + '/' + p2(t[2]));
    const rows = list.map(s => ({ s, ds: en(s.date || ''), a: amount(s.total), m: storeMeters(s), sh: storeSheets(s) })).sort((x, y) => (y.ds + (y.s.time || '')).localeCompare(x.ds + (x.s.time || '')) || y.s.id - x.s.id);
    const ys = Array.from(new Set(rows.map(r => r.ds.slice(0, 4)).filter(y => /^\d{4}$/.test(y)))).sort().reverse();
    if (!st.year || !ys.includes(String(st.year))) st.year = +(ys[0] || t[0]);
    let wa = 0, wm = 0, ma = 0, mm = 0, ws = 0, ms = 0; const mon = {}, wk = {}, mTot = Array(12).fill(0), mMet = Array(12).fill(0);
    rows.forEach(r => {
      const k = weekKey(r.ds), y = +r.ds.slice(0, 4), mo = +r.ds.slice(5, 7);
      if (y === t[0] && mo === t[1]) { ma += r.a; mm += r.m; ms += r.sh; }
      if (k && cw && k[0] === cw[0] && k[1] === cw[1]) { wa += r.a; wm += r.m; ws += r.sh; }
      if (y === st.year && mo >= 1 && mo <= 12) { mTot[mo - 1] += r.a; mMet[mo - 1] += r.m; }
      if (y && mo >= 1 && mo <= 12) { const mk = y * 100 + mo; (mon[mk] = mon[mk] || [0, 0]); mon[mk][0] += r.a; mon[mk][1] += r.m; }
      if (k) { const kk = k[0] * 100 + k[1]; (wk[kk] = wk[kk] || [0, 0]); wk[kk][0] += r.a; wk[kk][1] += r.m; }
    });
    const mpts = [], wpts = [];
    const mks = Object.keys(mon).map(Number).sort((a, b) => a - b);
    if (mks.length) { let y = Math.floor(mks[0] / 100), m = mks[0] % 100; const e = mks[mks.length - 1]; while (y * 100 + m <= e) { const v = mon[y * 100 + m] || [0, 0]; mpts.push({ label: MONTHS[m - 1], sub: fa(y), amt: v[0] / 1e9, met: v[1] }); if (++m > 12) { m = 1; y++; } } }
    const wks = Object.keys(wk).map(Number).sort((a, b) => a - b);
    if (wks.length) { let y = Math.floor(wks[0] / 100), w = wks[0] % 100; const e = wks[wks.length - 1]; while (y * 100 + w <= e) { const v = wk[y * 100 + w] || [0, 0]; wpts.push({ label: 'هفته ' + fa(w + 1), sub: weekShort(y, w), amt: v[0] / 1e9, met: v[1] }); if (++w > 52) { w = 0; y++; } } }
    const A = { key: 'amt', name: 'مبلغ (میلیارد ریال)', color: '#1565C0', fmt: v => v ? fa(v.toFixed(2).replace(/\.?0+$/, '')) : '' }, M = { key: 'met', name: 'متر مربع', color: '#F59E0B', fmt: v => v ? fa(Math.round(v)) : '' };
    const cols = ['#E3F2FD', '#E8F5E9', '#FFF8E1', '#FCE4EC', '#EDE7F6', '#E0F7FA', '#FFF3E0', '#F1F8E9', '#E8EAF6', '#FBE9E7', '#E0F2F1', '#F3E5F5'];
    let list_h = '', lastW = '';
    rows.slice(0, 120).forEach(r => {
      const k = weekKey(r.ds), wid = k ? k.join('|') : '0';
      if (wid !== lastW) { lastW = wid; const g = rows.filter(x => { const kk = weekKey(x.ds); return (kk ? kk.join('|') : '0') === wid; }); list_h += '<div class="card" style="padding:8px 12px;margin:10px 0 8px;text-align:center;font-weight:700">' + (k ? 'هفته ' + fa(k[1] + 1) + ' سال ' + fa(k[0]) + ' (' + weekText(k[0], k[1]) + ')' : 'بدون تاریخ') + '<div class="muted">فروش ' + fmt(g.reduce((s, x) => s + x.a, 0)) + ' ریال · ' + fm(g.reduce((s, x) => s + x.m, 0), 1) + ' متر مربع</div></div>'; }
      list_h += '<div class="item"><div class="row between"><span class="t">' + esc(r.s.customer) + '</span><span class="amt">' + fmt(r.a) + '</span></div><div class="m">شماره ' + fa(en(r.s.invoice_no || '')) + ' · ' + fa(r.ds) + ' · ' + (TAB_FA[r.s.tab] || '') + ' · ' + ((r.s.tab && r.s.tab !== 'parquet') ? fm(r.sh, 0) + ' ورق' : fm(r.m, 1) + ' متر مربع') + '</div>' +
        storeItems(r.s).map((it, i) => '<div class="m">' + fa(i + 1) + ') ' + esc(storeLine(it, r.s.tab)) + '</div>').join('') + '</div>';
    });
    root.innerHTML = '<div class="grid2">' + kpi('b-blue', 'فروش هفته', fmt(wa), qsub(wm, ws)) + kpi('b-green', 'فروش ماه', fmt(ma), qsub(mm, ms)) + '</div>' +
      '<div class="chips" style="margin-top:12px">' + ys.map(y => '<button class="chip' + (String(st.year) === y ? ' on' : '') + '" data-y="' + y + '">' + fa(y) + '</button>').join('') + '</div>' +
      '<div class="card"><h2>فروش ماهانه فروشگاه ' + fa(st.year) + '</h2><div class="month-grid">' + MONTHS.map((n, k) => '<div class="mcell" style="background:' + cols[k] + ';color:#0F172A"><b>' + n + '</b><div class="v">' + abbr(mTot[k]) + '</div><div class="s">' + fm(mMet[k], 1) + ' متر مربع</div></div>').join('') + '</div></div>' +
      '<div class="card"><h2>نمودار ماهانه (مبلغ و متر مربع)</h2>' + lineChart(mpts.slice(-24), [A, M], { slot: 74 }) + '</div>' +
      '<div class="card"><h2>نمودار هفتگی (مبلغ و متر مربع)</h2>' + lineChart(wpts.slice(-60), [A, M], { slot: 82 }) + '</div>' +
      '<h2 style="margin:14px 4px 0;font-size:15px">فروش‌های ثبت‌شده</h2>' + list_h;
    root.querySelectorAll('[data-y]').forEach(b => b.onclick = () => { st.year = +b.dataset.y; this.render(root); });
    scrollChartsToEnd(root);
  }
};
