/* راه‌اندازی، مسیریابی و ورود */
'use strict';
const NAV = [['home', '🏠', 'خانه'], ['invoices', '📄', 'حواله'], ['inquiry', '📝', 'استعلام'], ['inventory', '📦', 'موجودی'], ['ras', '📅', 'راس چک']];
const MORE = [['customers', '👥', 'مشتریان'], ['contacts', '📇', 'اطلاعات مشتریان'], ['reports', '📊', 'گزارش‌ها'], ['store', '🛒', 'فروشگاه'], ['balance', '⚖️', 'بالانس موجودی'], ['calc', '🧮', 'مشتریان و محاسبات'], ['salesrep', '📊', 'تحلیل فروش'], ['parquet', '📈', 'آمار فروش پارکت'], ['free', '🎁', 'سمپل و استند'], ['settings', '⚙️', 'تنظیمات']];
let curPage = 'home';

function drawNav() {
  const nav = document.getElementById('nav'), inMore = moreList().some(x => x[0] === curPage);
  nav.innerHTML = NAV.map(x => '<button class="nav-btn' + (curPage === x[0] ? ' active' : '') + '" data-p="' + x[0] + '"><span>' + x[1] + '</span>' + x[2] + '</button>').join('') +
    '<button class="nav-btn' + (inMore ? ' active' : '') + '" data-p="_more"><span>☰</span>بیشتر</button>';
  nav.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { if (b.dataset.p === '_more') openMore(); else go(b.dataset.p); });
}
function moreList() { return MORE.filter(x => isOwner() || !OWNER_PAGES.includes(x[0])); }
function openMore() {
  openSheet('بخش‌ها', '<div class="menu-grid">' + moreList().map(x => '<button class="menu-btn" data-p="' + x[0] + '"><span>' + x[1] + '</span>' + x[2] + '</button>').join('') + '</div>',
    body => body.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { closeSheet(); go(b.dataset.p); }));
}
function go(p) { if (location.hash !== '#/' + p) location.hash = '#/' + p; else showPage(p); }
function showPage(p) {
  if (!Pages[p] || (OWNER_PAGES.includes(p) && !isOwner())) p = 'home';
  curPage = p; closeSheet();
  const pg = Pages[p], root = document.getElementById('app');
  document.getElementById('pageTitle').textContent = pg.title || 'SalesMate';
  document.getElementById('pageSub').textContent = Store.lastAll ? 'آخرین به‌روزرسانی: ' + ago(Store.lastAll) : '';
  drawNav();
  try { pg.render(root); } catch (e) { root.innerHTML = '<div class="card err-t">خطا در نمایش: ' + esc(e.message) + '</div>'; console.error(e); }
  window.scrollTo(0, 0);
}
function rerender() { if (Auth.ok()) showPage(curPage); }

function showLogin(msg) {
  document.querySelector('.topbar').classList.add('hidden'); document.getElementById('nav').classList.add('hidden');
  document.body.style.paddingTop = '0'; document.body.style.paddingBottom = '0';
  document.getElementById('app').innerHTML = '<div class="login card"><div class="logo">S</div><h2 style="text-align:center">ورود به SalesMate</h2><div class="muted" style="text-align:center;margin-bottom:8px">با همان ایمیل و رمز برنامه‌ی ویندوز وارد شوید</div>' +
    '<label>ایمیل</label><input id="em" type="email" class="ltr" autocomplete="username" inputmode="email"><label>رمز عبور</label><input id="pw" type="password" class="ltr" autocomplete="current-password">' +
    '<button class="btn block" id="lg" style="margin-top:14px">ورود</button><div class="err-t" id="le">' + esc(msg || '') + '</div></div>';
  const lg = document.getElementById('lg'), pw = document.getElementById('pw');
  const doLogin = async () => {
    lg.disabled = true; document.getElementById('le').textContent = '';
    try { await Auth.login(document.getElementById('em').value, pw.value); location.reload(); }
    catch (e) { document.getElementById('le').textContent = e.message || 'ورود ناموفق'; lg.disabled = false; }
  };
  lg.onclick = doLogin; pw.onkeydown = e => { if (e.key === 'Enter') doLogin(); };
}
async function boot() {
  if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) navigator.serviceWorker.register('./sw.js').catch(() => { });
  if (!Auth.ok()) { showLogin(); return; }
  Store.lastAll = lsGet('sm_last', 0);
  await loadCached();
  document.getElementById('refreshBtn').onclick = async () => { const f = await refreshAll(); toast(f ? 'بعضی داده‌ها دریافت نشد' : 'به‌روزرسانی شد', !!f); rerender(); };
  window.addEventListener('hashchange', () => showPage((location.hash.replace('#/', '') || 'home')));
  showPage(location.hash.replace('#/', '') || 'home');
  const stale = !Store.lastAll || Date.now() - Store.lastAll > 5 * 60 * 1000;
  if (navigator.onLine !== false && (stale || !Store.data.invoices)) { await refreshAll(); rerender(); }
  document.addEventListener('visibilitychange', async () => { if (!document.hidden && navigator.onLine !== false && Date.now() - (Store.lastAll || 0) > 10 * 60 * 1000) { await refreshAll(); rerender(); } });
}
document.addEventListener('keydown', e => { if (e.key === 'Enter' && e.target && e.target.id === 'q') { e.preventDefault(); e.target.blur(); } });
boot();
