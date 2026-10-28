/* محاسبات تعاملی روی گوشی — همان فرمول ویندوز. ورودی‌ها فقط روی گوشی می‌مانند (چیزی به ابر نوشته نمی‌شود). */
'use strict';
const CalcTool = {
  KEY: 'sm_calc_local',
  get() {
    let L = lsGet(this.KEY, null); const C = Store.data.calc || {};
    if (!L) L = { calc: JSON.parse(JSON.stringify(C.calc || {})), free: Object.assign({ amount: 24960000000, cubic: 20.56 }, C.freeCalc || {}), custom: [], myCust: [] };
    L.custom = L.custom || []; L.myCust = L.myCust || []; return L;
  },
  put(L) { lsSet(this.KEY, L); },
  sizes() { return ((Store.data.calc || {}).sizes || []).concat(this.get().custom); },
  render(body, st) {
    const L = this.get(), sizes = this.sizes();
    const rowsHtml = sizes.map(s => { const e = L.calc[s.id] || {}; return '<div class="crow" data-id="' + esc(s.id) + '"><div class="row between"><b>' + esc(fa(s.name)) + '</b><span class="muted">' + fm(s.volume, 4) + ' م³/ورق</span></div><div class="f"><input class="inqf ltr" data-k="count" inputmode="numeric" enterkeyhint="next" placeholder="تعداد" value="' + esc(e.count ? fa(e.count) : '') + '"><input class="inqf ltr" data-k="amount" inputmode="numeric" enterkeyhint="next" placeholder="مبلغ (ریال)" value="' + esc(e.amount ? commas(e.amount) : '') + '"></div><div class="muted cres"></div></div>'; }).join('');
    body.innerHTML = '<div class="grid2"><div id="k1"></div><div id="k2"></div><div id="k3"></div><div id="k4"></div></div>' +
      (L.picked ? '<div class="card" style="margin-top:10px"><div class="row between"><span>مشتری انتخاب‌شده: <b>' + esc(L.picked) + '</b></span><button class="btn sm sec" id="unp">✕</button></div></div>' : '') +
      '<div style="margin-top:10px">' + rowsHtml + '</div>' +
      '<div class="card"><h2>سایز دلخواه</h2><div class="f"><input class="inqf ltr" id="cl" inputmode="decimal" placeholder="طول (متر)"><input class="inqf ltr" id="cw" inputmode="decimal" placeholder="عرض (متر)"><input class="inqf ltr" id="ct" inputmode="decimal" placeholder="ضخامت (میلی‌متر)"></div><button class="btn sec block" id="cadd" style="margin-top:8px">＋ افزودن سایز</button></div>' +
      '<div class="card"><h2>محاسبه‌ی آزاد</h2><div class="f"><input class="inqf ltr" id="fa" inputmode="numeric" enterkeyhint="next" placeholder="مبلغ" value="' + esc(commas(L.free.amount)) + '"><input class="inqf ltr" id="fc" inputmode="decimal" enterkeyhint="done" placeholder="متر مکعب" value="' + esc(L.free.cubic) + '"></div><div class="pill-row"><span>هر متر مکعب</span><b id="fp">—</b></div><div class="pill-row"><span>مالیات</span><b id="ft">—</b></div></div>' +
      '<div class="grid2"><button class="btn sec block" id="cshare">💬 ارسال خلاصه</button><button class="btn sec block" id="creset">⟲ پاک‌کردن ورودی‌ها</button></div>';
    const q = s => body.querySelector(s);
    const recalc = () => {
      let sh = 0, am = 0, cu = 0, tx = 0;
      body.querySelectorAll('.crow').forEach(el => {
        const s = sizes.find(x => String(x.id) === el.dataset.id), e = L.calc[s.id] || {}, cnt = num(e.count), a = amount(e.amount), cub = cTrunc((+s.volume || 0) * cnt, 2), tax = cTax(a), per = cPer(a, cub);
        sh += cnt; am += a; cu += cub; if (tax) tx += tax;
        el.querySelector('.cres').innerHTML = (cnt || a) ? 'حجم: <b>' + fm(cub, 2) + '</b> م³' + (per ? ' · هر م³: <b>' + fmt(per) + '</b>' : '') + (tax ? ' · مالیات: <b>' + fmt(tax) + '</b>' : '') : '';
      });
      this.sum = { sh, am, cu: cTrunc(cu, 2), tx };
      q('#k1').innerHTML = kpi('b-blue', 'تعداد ورق', fa(sh)); q('#k2').innerHTML = kpi('b-green', 'متر مکعب', fm(this.sum.cu, 2)); q('#k3').innerHTML = kpi('b-violet', 'مبلغ', fmt(am)); q('#k4').innerHTML = kpi('b-amber', 'مالیات', fmt(tx));
      const fa_ = amount(L.free.amount), fc_ = num(L.free.cubic), p = cPer(fa_, fc_), t = cTax(fa_);
      q('#fp').textContent = p ? fmt(p) : '—'; q('#ft').textContent = t ? fmt(t) : '—';
    };
    body.querySelectorAll('.crow').forEach(el => el.querySelectorAll('input').forEach(inp => inp.oninput = () => {
      const id = el.dataset.id, e = L.calc[id] || (L.calc[id] = {}), k = inp.dataset.k;
      if (k === 'amount') { inp.value = commas(inp.value); e.amount = amount(inp.value); } else { const v = en(inp.value).replace(/\D/g, ''); inp.value = v; e.count = +v || 0; }
      this.put(L); recalc();
    }));
    q('#fa').oninput = e => { e.target.value = commas(e.target.value); L.free.amount = amount(e.target.value); this.put(L); recalc(); };
    q('#fc').oninput = e => { L.free.cubic = num(e.target.value); this.put(L); recalc(); };
    q('#cadd').onclick = () => { const l = num(q('#cl').value), w = num(q('#cw').value), t = num(q('#ct').value); if (!(l > 0 && w > 0 && t > 0)) { toast('طول، عرض و ضخامت را وارد کنید', true); return; } L.custom.push({ id: 'custom_' + Date.now(), name: fm(l, 2) + '×' + fm(w, 2) + '×' + fm(t, 1), volume: l * w * (t / 1000), count: 0, amount: 0 }); this.put(L); this.render(body, st); };
    const unp = q('#unp'); if (unp) unp.onclick = () => { delete L.picked; this.put(L); this.render(body, st); };
    q('#creset').onclick = () => { if (!confirm('همه‌ی ورودی‌ها پاک شود؟')) return; L.calc = {}; L.custom = []; delete L.picked; this.put(L); this.render(body, st); };
    q('#cshare').onclick = () => { const s = this.sum; shareText((L.picked ? 'مشتری: ' + L.picked + '\n' : '') + 'تعداد ورق: ' + fa(s.sh) + '\nمتر مکعب: ' + fm(s.cu, 2) + '\nمبلغ: ' + fmt(s.am) + ' ریال\nمالیات: ' + fmt(s.tx) + ' ریال'); };
    // Enter → فیلد بعدی
    const all = () => Array.from(body.querySelectorAll('.inqf')).filter(x => x.offsetParent !== null);
    body.querySelectorAll('.inqf').forEach(el => { el.onkeydown = e => { if (e.key !== 'Enter') return; e.preventDefault(); const a = all(), i = a.indexOf(el); if (i < a.length - 1) a[i + 1].focus(); else el.blur(); }; el.onfocus = () => document.body.classList.add('kb'); el.onblur = () => setTimeout(() => { if (!/INPUT/.test((document.activeElement || {}).tagName || '')) document.body.classList.remove('kb'); }, 150); });
    recalc();
  }
};

(function () {
  const P = Pages.calc, base = P.render;
  P.render = function (root) {
    const st = this.state;
    if (st.tab === 'calc') {
      if (!Store.data.calc && !lsGet(CalcTool.KEY, null)) { /* بدون داده‌ی ابر هم قابل استفاده است */ }
      root.innerHTML = '<div class="chips"><button class="chip" data-t="cust">دفترچه مشتریان</button><button class="chip on" data-t="calc">محاسبه</button></div><div id="body"></div>';
      root.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { st.tab = b.dataset.t; this.render(root); });
      CalcTool.render(root.querySelector('#body'), st); return;
    }
    // دفترچه: افزودن مشتری محلی + انتخاب برای محاسبه
    const L = CalcTool.get(), holder = document.createElement('div');
    base.call(this, holder);
    root.innerHTML = ''; root.appendChild(holder);
    const body = holder.querySelector('#body');
    if (!body) { /* ابر خالی */ holder.innerHTML = '<div class="chips"><button class="chip on" data-t="cust">دفترچه مشتریان</button><button class="chip" data-t="calc">محاسبه</button></div><div id="body"></div>'; holder.querySelectorAll('[data-t]').forEach(b => b.onclick = () => { st.tab = b.dataset.t; this.render(root); }); }
    holder.querySelectorAll('[data-t]').forEach(b => { if (b.dataset.t === 'calc') b.textContent = 'محاسبه'; });
    const b2 = holder.querySelector('#body'), add = document.createElement('div');
    add.className = 'card'; add.innerHTML = '<h2>مشتری جدید (روی گوشی)</h2><div class="f"><input class="inqf" id="mcn" placeholder="نام مشتری" enterkeyhint="next"><input class="inqf ltr" id="mci" inputmode="numeric" placeholder="کد ملی" enterkeyhint="next"><input class="inqf ltr" id="mcp" inputmode="tel" placeholder="تلفن" enterkeyhint="done"></div><button class="btn block green" id="mca" style="margin-top:8px">ذخیره و استفاده در محاسبه</button>' +
      (L.myCust.length ? '<div style="margin-top:10px">' + L.myCust.map((c, i) => '<div class="pill-row"><span>' + esc(c.customer) + ' <span class="muted ltr">' + fa(esc(c.national_id || '')) + '</span></span><span><button class="btn sm sec" data-use="' + i + '">محاسبه</button> <button class="btn sm sec" data-rm="' + i + '">✕</button></span></div>').join('') + '</div>' : '');
    (b2 || holder).prepend(add);
    add.querySelector('#mca').onclick = () => { const n = add.querySelector('#mcn').value.trim(); if (!n) { toast('نام را وارد کنید', true); return; } L.myCust.unshift({ customer: n, national_id: en(add.querySelector('#mci').value), phone: en(add.querySelector('#mcp').value) }); L.picked = n; CalcTool.put(L); st.tab = 'calc'; this.render(root); };
    add.querySelectorAll('[data-use]').forEach(b => b.onclick = () => { L.picked = L.myCust[+b.dataset.use].customer; CalcTool.put(L); st.tab = 'calc'; this.render(root); });
    add.querySelectorAll('[data-rm]').forEach(b => b.onclick = () => { L.myCust.splice(+b.dataset.rm, 1); CalcTool.put(L); this.render(root); });
    add.querySelectorAll('.inqf').forEach(el => { el.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); const a = Array.from(add.querySelectorAll('.inqf')), i = a.indexOf(el); if (i < a.length - 1) a[i + 1].focus(); else add.querySelector('#mca').click(); } }; });
    // انتخاب مشتری ابری با کلیک برای محاسبه
    holder.addEventListener('click', e => { const it = e.target.closest('#list .item'); if (!it || e.target.closest('a')) return; const n = it.querySelector('.t'); if (n && confirm('«' + n.textContent + '» برای محاسبه انتخاب شود؟')) { L.picked = n.textContent; CalcTool.put(L); st.tab = 'calc'; this.render(root); } });
  };
})();
