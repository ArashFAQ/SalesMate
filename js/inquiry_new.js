/* ساخت استعلام جدید روی موبایل — همان منطق ویندوز (کد → نوع کالا، متر مربع = کارتن × ضریب، هزینه = متر مربع × قیمت).
   ذخیره فقط روی گوشی است؛ چیزی به ابر نوشته نمی‌شود. با Enter به فیلد بعدی می‌رود و صفحه با کیبورد نمی‌پرد. */
'use strict';
const PRODUCT_FACTORS = { 'Isofam Luxury': 1.9608, Charlotte: 2.0066, Valente: 1.9608, Egmont: 1.8696, 'N Egmont': 1.9608, 'New Way': 1.9608 };
const PRODUCT_OPTIONS = Object.keys(PRODUCT_FACTORS), EGMONT_OPTIONS = ['Egmont', 'N Egmont'], GRADE_OPTIONS = ['GA', 'GB', 'GC'];
const CODE_TO_PRODUCT = {};
[['Isofam Luxury', '1122 1123 1124 1132 1133 1134 1144 1145 1154 1163 1234 2113 2122 2123 2124 2132 2135 2137 2162 2164 2254 2255 2133 2223 2120 2125 2126 2253 2117 2138 2248 2252 2166 2273 2275 2276 2274 2142 2136 2144 2486 2118 2453 2474 22530 2114 2468 2111 2465 246 2463 2112 2104 2222 2134 2476'],
['Charlotte', '6542 6332 6234 6223 6224 6435 6545 6433 6235'], ['Valente', '7414 7323 7322 7335 7434 7524 7634 7343 7465'],
['Egmont', '443 126 444 452 442 456 114 453'], ['New Way', '9015 9010 9025 9020 9072 9052 9055 9059 9040 9050']].forEach(p => p[1].split(' ').forEach(c => { CODE_TO_PRODUCT[c] = p[0]; }));

function numberToWords(n) {
  n = Math.abs(Math.round(+n || 0)); if (!n) return 'صفر';
  const ones = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه'], teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده'],
    tens = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود'], hund = ['', 'یکصد', 'دویست', 'سیصد', 'چهارصد', 'پانصد', 'ششصد', 'هفتصد', 'هشتصد', 'نهصد'], sc = ['', 'هزار', 'میلیون', 'میلیارد', 'تریلیون'];
  const three = x => { const h = Math.floor(x / 100), t = Math.floor((x % 100) / 10), o = x % 10, p = []; if (h) p.push(hund[h]); if (t === 1) p.push(teens[o]); else { if (t) p.push(tens[t]); if (o) p.push(ones[o]); } return p.join(' و '); };
  const parts = []; let i = 0;
  while (n > 0 && i < sc.length) { const c = n % 1000; if (c) { let s = three(c); if (sc[i]) s += ' ' + sc[i]; parts.unshift(s); } n = Math.floor(n / 1000); i++; }
  return parts.join(' و ');
}

const InqBuilder = {
  S: null, custs: [],
  fresh(tab) {
    const t = todayJ();
    return { tab: tab || 'parquet', buyer: '', date: t[0] + '/' + p2(t[1]) + '/' + p2(t[2]), rows: [], warehouse: '', transport: 'به عهده مشتری می‌باشد', debt: '0', discount: '0', validity: '', shaba: 'IR650120020000005081809111' };
  },
  validityFor(tab) { return tab === 'mdf' ? 'اعتبار این استعلام کالا از تاریخ صدور تا ساعت ۱۱ همان روز می‌باشد' : 'اعتبار این استعلام کالا از تاریخ صدور تا پایان وقت اداری همان روز می‌باشد'; },
  newRow(tab) { return tab === 'parquet' ? { code: '', type: PRODUCT_OPTIONS[0], grade: 'GA', qty1: '', qty2: '', price: '' } : tab === 'mdf' ? { type: '', code: '', qty1: '', qty2: '', price: '' } : { type: '', size: '', qty1: '', qty2: '', price: '' }; },
  save() { lsSet('sm_inq_draft', this.S); },
  rowCost(r) { return Math.round(num(r.qty2) * amount(r.price)); },
  snapshot() {
    const S = this.S, rows = S.rows.map((r, i) => Object.assign({ index: i + 1 }, r, { cost: this.rowCost(r) }));
    const sub = rows.reduce((a, r) => a + r.cost, 0);
    return { tab: S.tab, buyer: S.buyer.trim(), date: en(S.date), rows, warehouse: S.warehouse, transport: S.transport, debt: en(S.debt), discount: en(S.discount), validity: S.validity, shaba: S.tab === 'parquet' ? S.shaba : '', total: sub + amount(S.debt) - amount(S.discount) };
  },
  /* ───── رندر ───── */
  mount(root, preset, onClose) {
    const draft = lsGet('sm_inq_draft', null);
    this.S = preset || draft || this.fresh('parquet');
    if (!this.S.validity) this.S.validity = this.validityFor(this.S.tab);
    if (!this.S.rows.length) this.S.rows.push(this.newRow(this.S.tab));
    this.custs = customerSummaries(); this.onClose = onClose; this.root = root;
    this.draw();
  },
  draw() {
    const S = this.S, root = this.root;
    root.innerHTML =
      '<div class="row between" style="margin-bottom:10px"><button class="btn sm sec" id="ibBack">‹ لیست استعلام‌ها</button><button class="btn sm sec" id="ibClear">پاک‌کردن فرم</button></div>' +
      '<div class="seg" id="ibTabs">' + [['parquet', 'پارکت'], ['mdf', 'ام‌دی‌اف'], ['raw', 'ام‌دی‌اف خام']].map(x => '<button data-t="' + x[0] + '" class="' + (S.tab === x[0] ? 'on' : '') + '">' + x[1] + '</button>').join('') + '</div>' +
      '<div class="card" id="ibBuyerCard"><div style="position:relative"><label>نام خریدار — چند حرف اول را بنویسید</label><input id="ibBuyer" class="inqf" autocomplete="off" enterkeyhint="next" placeholder="نام مشتری…" value="' + esc(S.buyer) + '"><div class="sugg hidden" id="ibSug"></div></div><div class="muted" id="ibBal" style="margin-top:4px"></div>' +
      '<label>تاریخ</label><input id="ibDate" class="inqf ltr" inputmode="decimal" enterkeyhint="next" value="' + esc(fa(S.date)) + '"></div>' +
      '<div class="row between" style="margin:4px 2px 8px"><b>اقلام کالا</b><button class="btn sm sec" id="ibAdd">+ افزودن ردیف</button></div><div id="ibRows"></div>' +
      '<div class="card"><div class="pill-row"><span>جمع اقلام</span><b id="ibSub">۰</b></div><label>هزینه انبارداری</label><input id="ibWh" class="inqf" enterkeyhint="next" value="' + esc(S.warehouse) + '"><label>هزینه حمل</label><input id="ibTr" class="inqf" enterkeyhint="next" value="' + esc(S.transport) + '">' +
      '<label>بدهی پیشین (ریال)</label><input id="ibDebt" class="inqf ltr" inputmode="numeric" enterkeyhint="next" value="' + esc(commas(S.debt) || '0') + '"><label>تخفیف (ریال)</label><input id="ibDisc" class="inqf ltr" inputmode="numeric" enterkeyhint="next" value="' + esc(commas(S.discount) || '0') + '">' +
      '<div class="pill-row" style="margin-top:8px"><span><b>جمع کل</b></span><b class="amt" id="ibTot" style="font-size:17px">۰</b></div><div class="muted" id="ibWords"></div></div>' +
      '<div class="card"><label>اعتبار استعلام</label><input id="ibVal" class="inqf" enterkeyhint="next" value="' + esc(S.validity) + '">' + (S.tab === 'parquet' ? '<label>شماره شبا</label><input id="ibSh" class="inqf ltr" enterkeyhint="done" value="' + esc(S.shaba) + '">' : '') + '</div>' +
      '<div class="grid2"><button class="btn block" id="ibImg">🖼 ارسال تصویر</button><button class="btn block" id="ibPdf">📄 ارسال PDF</button></div><div style="margin-top:8px"><button class="btn sec block" id="ibTxt">💬 ارسال متن</button></div>' +
      '<div class="grid2" style="margin-top:8px"><button class="btn green block" id="ibSave">💾 ذخیره روی گوشی</button><button class="btn sec block" id="ibPrev">👁 پیش‌نمایش</button></div>';
    const q = id => root.querySelector('#' + id);
    this.rowsEl = q('ibRows'); S.rows.forEach((r, i) => this.rowsEl.appendChild(this.rowEl(r, i)));
    q('ibBack').onclick = () => { this.save(); this.onClose && this.onClose(); };
    q('ibClear').onclick = () => { if (!confirm('فرم پاک شود؟')) return; this.S = this.fresh(S.tab); this.S.validity = this.validityFor(this.S.tab); this.S.rows.push(this.newRow(this.S.tab)); this.save(); this.draw(); };
    q('ibAdd').onclick = () => { this.addRow(true); };
    q('ibTabs').querySelectorAll('button').forEach(b => b.onclick = () => { if (b.dataset.t === S.tab) return; S.tab = b.dataset.t; S.rows = [this.newRow(S.tab)]; S.validity = this.validityFor(S.tab); this.save(); this.draw(); });
    const bind = (id, key, fmtFn) => { const el = q(id); if (!el) return; el.oninput = () => { let v = el.value; if (fmtFn) { v = fmtFn(v); el.value = v; } S[key] = v; this.save(); this.recalc(); }; };
    bind('ibWh', 'warehouse'); bind('ibTr', 'transport'); bind('ibVal', 'validity'); bind('ibSh', 'shaba');
    bind('ibDebt', 'debt', v => commas(v) || '0'); bind('ibDisc', 'discount', v => commas(v) || '0');
    q('ibDate').oninput = () => { S.date = en(q('ibDate').value); this.save(); };
    this.bindBuyer();
    root.querySelectorAll('.inqf').forEach(el => this.wireEnter(el));
    root.querySelectorAll('input').forEach(el => { el.onfocus = () => document.body.classList.add('kb'); el.onblur = () => setTimeout(() => { if (!document.activeElement || !/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) document.body.classList.remove('kb'); }, 150); });
    q('ibTxt').onclick = () => { if (!this.check()) return; shareText(inqText(this.snapshot(), '')); };
    q('ibImg').onclick = () => { if (!this.check()) return; shareInquiryImage(this.snapshot(), ''); };
    q('ibPdf').onclick = () => { if (!this.check()) return; shareInquiryImage(this.snapshot(), '', 'pdf'); };
    q('ibPrev').onclick = () => showInquiry(this.snapshot(), '');
    q('ibSave').onclick = () => { if (!this.check()) return; this.saveLocal(); };
    this.recalc(); this.buyerState();
  },
  check() {
    const d = this.snapshot();
    if (!d.buyer) { toast('نام خریدار را وارد کنید', true); const b = this.root.querySelector('#ibBuyer'); b.focus(); return false; }
    if (!d.rows.some(r => r.cost > 0 || num(r.qty2) > 0)) { toast('حداقل یک قلم با تعداد و قیمت وارد کنید', true); return false; }
    const bad = []; if (d.tab === 'parquet') d.rows.forEach((r, i) => { if (CODE_TO_PRODUCT[en(r.code).replace(/\D/g, '')] === 'Egmont' && !EGMONT_OPTIONS.includes(r.type)) bad.push(fa(i + 1)); });
    if (bad.length) { toast('نوع Egmont را برای ردیف ' + bad.join('، ') + ' انتخاب کنید', true); return false; }
    return true;
  },
  /* ───── ردیف ───── */
  rowEl(r, i) {
    const S = this.S, tab = S.tab, el = document.createElement('div'); el.className = 'inq-row';
    const inp = (k, ph, cls, extra) => '<input class="inqf ' + (cls || '') + '" data-k="' + k + '" placeholder="' + ph + '" value="' + esc(r[k] || '') + '" ' + (extra || '') + ' enterkeyhint="next">';
    let f;
    if (tab === 'parquet') f = inp('code', 'کد کالا', 'ltr', 'inputmode="numeric"') + '<select class="inqf" data-k="type"></select><select class="inqf" data-k="grade">' + GRADE_OPTIONS.map(g => '<option' + (r.grade === g ? ' selected' : '') + '>' + g + '</option>').join('') + '</select>' + inp('qty1', 'تعداد کارتن', 'ltr', 'inputmode="numeric"') + inp('qty2', 'متر مربع (خودکار)', 'ltr', 'readonly tabindex="-1"') + inp('price', 'قیمت واحد', 'ltr', 'inputmode="numeric"');
    else if (tab === 'mdf') f = inp('type', 'نوع کالا', 'full') + inp('code', 'کد', 'ltr') + inp('qty1', 'پالت', 'ltr', 'inputmode="numeric"') + inp('qty2', 'ورق', 'ltr', 'inputmode="decimal"') + inp('price', 'قیمت واحد', 'ltr', 'inputmode="numeric"');
    else f = inp('type', 'نوع کالا', 'full') + inp('size', 'سایز') + inp('qty1', 'پالت', 'ltr', 'inputmode="numeric"') + inp('qty2', 'ورق', 'ltr', 'inputmode="decimal"') + inp('price', 'قیمت واحد', 'ltr', 'inputmode="numeric"');
    el.innerHTML = '<div class="row between" style="margin-bottom:6px"><b class="muted">ردیف <span class="rn"></span></b><button class="btn sm sec" data-rm style="padding:4px 10px">✕</button></div><div class="f">' + f + '</div><div class="inq-cost">هزینه: <span class="cv">۰</span> ریال</div>';
    const q = k => el.querySelector('[data-k="' + k + '"]');
    // انتخاب نوع بر اساس کد (مثل ویندوز)
    const applyCode = () => {
      if (tab !== 'parquet') return; const sel = q('type'), key = en(r.code || '').replace(/\D/g, ''), prod = CODE_TO_PRODUCT[key];
      let opts, dis = false;
      if (prod === 'Egmont') { opts = ['⚠ انتخاب کنید…'].concat(EGMONT_OPTIONS); if (!EGMONT_OPTIONS.includes(r.type)) r.type = opts[0]; }
      else if (prod) { opts = PRODUCT_OPTIONS; r.type = prod; dis = true; }
      else { opts = PRODUCT_OPTIONS; if (!PRODUCT_OPTIONS.includes(r.type)) r.type = PRODUCT_OPTIONS[0]; }
      sel.innerHTML = opts.map(o => '<option' + (o === r.type ? ' selected' : '') + '>' + o + '</option>').join(''); sel.disabled = dis;
      sel.style.borderColor = (prod === 'Egmont' && !EGMONT_OPTIONS.includes(r.type)) ? '#F97316' : '';
      el.style.borderInlineStartColor = (prod === 'Egmont' && !EGMONT_OPTIONS.includes(r.type)) ? '#F59E0B' : '';
    };
    const upd = () => {
      if (tab === 'parquet') { const c = num(r.qty1), fac = PRODUCT_FACTORS[r.type]; r.qty2 = (fac && c) ? (c * fac).toFixed(4).replace(/\.?0+$/, '') : ''; q('qty2').value = r.qty2; }
      el.querySelector('.cv').textContent = fmt(this.rowCost(r)); this.save(); this.recalc();
    };
    el.querySelectorAll('[data-k]').forEach(x => {
      const k = x.dataset.k;
      if (x.tagName === 'SELECT') { x.onchange = () => { r[k] = x.value; if (k === 'type') { applyCode(); } upd(); }; return; }
      if (x.hasAttribute('readonly')) return;
      x.oninput = () => { let v = x.value; if (k === 'price') { v = commas(v); x.value = v; } else if (k === 'qty1' || (k === 'code' && tab === 'parquet')) { v = en(v).replace(/[^\d.]/g, ''); if (k === 'code') v = v.replace(/\./g, ''); if (x.value !== v) x.value = v; } r[k] = v; if (k === 'code') applyCode(); upd(); };
    });
    el.querySelector('[data-rm]').onclick = () => { const idx = S.rows.indexOf(r); if (S.rows.length > 1) S.rows.splice(idx, 1); else S.rows[0] = this.newRow(tab); this.save(); this.draw(); };
    applyCode(); if (tab === 'parquet') { const c = num(r.qty1), fac = PRODUCT_FACTORS[r.type]; r.qty2 = (fac && c) ? (c * fac).toFixed(4).replace(/\.?0+$/, '') : ''; q('qty2').value = r.qty2; }
    el.querySelector('.cv').textContent = fmt(this.rowCost(r));
    return el;
  },
  addRow(focus) {
    const r = this.newRow(this.S.tab); this.S.rows.push(r); const el = this.rowEl(r, this.S.rows.length - 1); this.rowsEl.appendChild(el);
    el.querySelectorAll('.inqf').forEach(x => this.wireEnter(x)); el.querySelectorAll('input').forEach(x => { x.onfocus = () => document.body.classList.add('kb'); });
    this.numberRows(); this.save();
    if (focus) { const f = el.querySelector('input:not([readonly])'); if (f) f.focus(); }
  },
  numberRows() { this.rowsEl.querySelectorAll('.rn').forEach((s, i) => { s.textContent = fa(i + 1); }); },
  recalc() {
    const S = this.S, sub = S.rows.reduce((a, r) => a + this.rowCost(r), 0), tot = sub + amount(S.debt) - amount(S.discount), q = id => this.root.querySelector('#' + id);
    q('ibSub').textContent = fmt(sub); q('ibTot').textContent = fmt(tot); q('ibWords').textContent = tot ? numberToWords(tot) + ' ریال' : '';
    this.numberRows(); this.rowsEl.querySelectorAll('.inq-row').forEach((el, i) => { if (S.rows[i]) el.querySelector('.cv').textContent = fmt(this.rowCost(S.rows[i])); });
  },
  /* ───── Enter = فیلد بعدی ───── */
  wireEnter(el) {
    el.onkeydown = e => {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      if (el.tagName !== 'SELECT' && el.id === 'ibBuyer') { const sg = this.root.querySelector('#ibSug'); if (!sg.classList.contains('hidden') && sg.firstElementChild) { this.pickBuyer(sg.firstElementChild.dataset.n); return; } }
      const rowE = el.closest('.inq-row');
      if (rowE && el.dataset.k === 'code') { const sel = rowE.querySelector('select[data-k="type"]'); if (sel && !sel.disabled && sel.value.indexOf('⚠') === 0) { sel.focus(); return; } }
      const all = Array.from(this.root.querySelectorAll('input.inqf')).filter(x => !x.disabled && !x.readOnly && x.offsetParent !== null), i = all.indexOf(el);
      const rowEl = el.closest('.inq-row');
      if (rowEl && el.dataset.k === 'price' && rowEl === this.rowsEl.lastElementChild) { this.addRow(true); return; }
      if (el.tagName === 'SELECT') { const nx = all.find(x => el.compareDocumentPosition(x) & 4); if (nx) nx.focus(); return; }
      if (i >= 0 && i < all.length - 1) { all[i + 1].focus(); try { all[i + 1].select(); } catch (x) { } } else el.blur();
    };
  },
  /* ───── مشتری ───── */
  bindBuyer() {
    const S = this.S, q = id => this.root.querySelector('#' + id), inp = q('ibBuyer'), sg = q('ibSug');
    const show = () => {
      const k = customerKey(inp.value); if (!k) { sg.classList.add('hidden'); return; }
      const starts = [], inc = []; this.custs.forEach(c => { const n = customerKey(c.name); if (n.startsWith(k)) starts.push(c); else if (n.includes(k)) inc.push(c); });
      const list = starts.concat(inc).slice(0, 8);
      if (!list.length || (list.length === 1 && customerKey(list[0].name) === k)) { sg.classList.add('hidden'); return; }
      sg.innerHTML = list.map(c => '<div data-n="' + esc(c.name) + '"><b>' + esc(c.name) + '</b>' + (c.bal > 0 ? ' <span class="debt" style="font-size:12px">بدهکار ' + abbr(c.bal) + '</span>' : c.bal < 0 ? ' <span class="cred" style="font-size:12px">طلبکار ' + abbr(-c.bal) + '</span>' : '') + '</div>').join('');
      sg.classList.remove('hidden');
      sg.querySelectorAll('div').forEach(d => d.onpointerdown = e => { e.preventDefault(); this.pickBuyer(d.dataset.n); });
    };
    inp.oninput = () => { S.buyer = inp.value; this.save(); this.buyerState(); show(); };
    inp.onblur = () => setTimeout(() => sg.classList.add('hidden'), 150);
    inp.onfocus = () => show();
  },
  pickBuyer(name) {
    const inp = this.root.querySelector('#ibBuyer'); inp.value = name; this.S.buyer = name; this.save(); this.root.querySelector('#ibSug').classList.add('hidden'); this.buyerState();
    const next = this.root.querySelector('#ibDate'); if (next) { next.focus(); try { next.select(); } catch (e) { } }
  },
  buyerState() {
    const c = this.custs.find(x => customerKey(x.name) === customerKey(this.S.buyer)), card = this.root.querySelector('#ibBuyerCard'), bal = this.root.querySelector('#ibBal');
    card.classList.remove('buyer-red', 'buyer-green');
    if (c && c.bal > 0) { card.classList.add('buyer-red'); bal.innerHTML = '<span class="debt">بدهکار: ' + fmt(c.bal) + ' ریال</span>'; if (amount(this.S.debt) === 0) { /* مانده‌ی قبلی به‌صورت پیشنهاد */ bal.innerHTML += ' <button class="btn sm sec" id="ibUse" style="padding:2px 10px">درج در «بدهی پیشین»</button>'; const b = bal.querySelector('#ibUse'); b.onclick = () => { this.S.debt = String(c.bal); const d = this.root.querySelector('#ibDebt'); d.value = commas(String(c.bal)); this.save(); this.recalc(); }; } }
    else if (c && c.bal < 0) { card.classList.add('buyer-green'); bal.innerHTML = '<span class="cred">طلبکار: ' + fmt(-c.bal) + ' ریال</span>'; }
    else bal.textContent = c ? 'تسویه' : '';
  },
  /* ───── ذخیره‌ی محلی ───── */
  saveLocal() {
    const d = this.snapshot(), list = lsGet('sm_inq_local', []), fp = JSON.stringify([d.tab, d.buyer, d.date, d.rows, d.debt, d.discount, d.total]);
    if (list.some(x => x._fp === fp)) { toast('این استعلام قبلاً ذخیره شده'); return; }
    d.id = Date.now(); d.savedAt = new Date().toISOString(); d._fp = fp; list.unshift(d); lsSet('sm_inq_local', list.slice(0, 50)); toast('روی گوشی ذخیره شد');
  }
};

/* ───── اتصال به صفحه‌ی استعلام: دکمه‌ی جدید + ذخیره‌شده‌های گوشی ───── */
(function () {
  const P = Pages.inquiry, base = P.render;
  P.render = function (root) {
    const st = this.state;
    if (st.mode === 'new') { InqBuilder.mount(root, st.preset || null, () => { st.mode = 'list'; st.preset = null; this.render(root); }); return; }
    const local = lsGet('sm_inq_local', []);
    root.innerHTML = '<button class="btn block green" id="inNew" style="margin-bottom:10px">＋ استعلام جدید</button>' + (lsGet('sm_inq_draft', null) ? '<div class="muted" style="margin:-4px 4px 10px">یک پیش‌نویس ناتمام دارید؛ با «استعلام جدید» ادامه می‌دهید.</div>' : '') +
      (local.length ? '<div class="card"><h2>ذخیره‌شده روی گوشی</h2><div id="loc"></div></div>' : '') + '<div id="cloud"></div>';
    root.querySelector('#inNew').onclick = () => { st.mode = 'new'; this.render(root); };
    const loc = root.querySelector('#loc');
    if (loc) {
      loc.innerHTML = local.map((d, i) => '<div class="item" data-i="' + i + '"><div class="row between"><span class="t">' + esc(d.buyer || '—') + '</span><span class="amt">' + fmt(d.total) + '</span></div><div class="row between m"><span>' + fa(en(d.date || '')) + ' · ' + fa((d.rows || []).length) + ' قلم</span><span class="row"><button class="btn sm sec" data-ed="' + i + '">ویرایش</button><button class="btn sm sec" data-del="' + i + '">حذف</button></span></div></div>').join('');
      loc.querySelectorAll('[data-i]').forEach(el => el.onclick = () => showInquiry(local[+el.dataset.i], ''));
      loc.querySelectorAll('[data-ed]').forEach(b => b.onclick = e => { e.stopPropagation(); const d = JSON.parse(JSON.stringify(local[+b.dataset.ed])); delete d._fp; d.rows = d.rows.map(r => { const o = Object.assign({}, r); delete o.cost; delete o.index; return o; }); st.preset = Object.assign(InqBuilder.fresh(d.tab), d); st.mode = 'new'; this.render(root); });
      loc.querySelectorAll('[data-del]').forEach(b => b.onclick = e => { e.stopPropagation(); if (!confirm('این استعلام از گوشی حذف شود؟')) return; local.splice(+b.dataset.del, 1); lsSet('sm_inq_local', local); this.render(root); });
    }
    const holder = document.createElement('div'); root.querySelector('#cloud').appendChild(holder);
    base.call(this, holder);
  };
})();
