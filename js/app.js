
function buildChartSvg(totals) {
  const max = Math.max(...totals, 1);
  const W = 360, H = 180, padL = 36, padR = 8, padT = 16, padB = 36;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const pts = totals.map((v, i) => {
    const x = padL + (i / 11) * plotW;
    const y = padT + plotH - (v / max) * plotH;
    return [x, y, v];
  });
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = line + ` L${pts[11][0].toFixed(1)},${padT + plotH} L${pts[0][0].toFixed(1)},${padT + plotH} Z`;
  let circles = pts.map(p => `<circle cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3.5" fill="#0284c7" stroke="#fff" stroke-width="1.5"/>`).join('');
  let labels = MONTHS.map((m, i) => {
    const x = padL + (i / 11) * plotW;
    return `<text x="${x.toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="8" fill="#64748b">${m.slice(0, 3)}</text>`;
  }).join('');
  // y ticks in billions
  let yticks = '';
  for (let t = 0; t <= 4; t++) {
    const val = max * t / 4;
    const y = padT + plotH - (t / 4) * plotH;
    const label = (val / 1e9).toFixed(1);
    yticks += `<line x1="${padL}" y1="${y}" x2="${W - padR}" y2="${y}" stroke="#e2e8f0" stroke-width="1"/>`;
    yticks += `<text x="${padL - 4}" y="${y + 3}" text-anchor="end" font-size="8" fill="#94a3b8">${label}</text>`;
  }
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" style="background:#fff;border-radius:12px">
    ${yticks}
    <path d="${area}" fill="rgba(2,132,199,0.12)"/>
    <path d="${line}" fill="none" stroke="#0284c7" stroke-width="2.5" stroke-linejoin="round"/>
    ${circles}
    ${labels}
    <text x="${W/2}" y="12" text-anchor="middle" font-size="10" fill="#0284c7" font-weight="700">نمودار فروش ماهانه (میلیارد ریال)</text>
  </svg>`;
}

/* SalesMate Mobile Web — localStorage */
const KEY = 'salesmate_mw_v1';
const SUPABASE_URL = 'https://sowftowkhvuvaijttpiv.supabase.co';
const SUPABASE_KEY = 'sb_publishable_5BrCyhkBlDQqbdjkGnEK1w_zpsHiAs8';

const PRODUCT_FACTORS = {
  'Isofam Luxury': 1.9608,
  Charlotte: 2.0066,
  Valente: 1.9608,
  Egmont: 1.8696,
  'N Egmont': 1.9608,
  'New Way': 1.9608
};
const PRODUCT_OPTIONS = Object.keys(PRODUCT_FACTORS);
const GRADE_OPTIONS = ['GA', 'GB', 'GC'];
const EGMONT_OPTIONS = ['Egmont', 'N Egmont'];
const CODE_TO_PRODUCT = {};
[
  '1122','1123','1124','1132','1133','1134','1144','1145','1154','1163',
  '1234','2113','2122','2123','2124','2132','2135','2137','2162','2164',
  '2254','2255','2133','2223','2120','2125','2126','2253','2117','2138',
  '2248','2252','2166','2273','2275','2276','2274','2142','2136','2144',
  '2486','2118','2453','2474','22530','2114','2468','2111','2465','246',
  '2463','2112','2104','2222','2134','2476'
].forEach(c => { CODE_TO_PRODUCT[c] = 'Isofam Luxury'; });
['6542','6332','6234','6223','6224','6435','6545','6433','6235'].forEach(c => { CODE_TO_PRODUCT[c] = 'Charlotte'; });
['7414','7323','7322','7335','7434','7524','7634','7343','7465'].forEach(c => { CODE_TO_PRODUCT[c] = 'Valente'; });
['443','126','444','452','442','456','114','453'].forEach(c => { CODE_TO_PRODUCT[c] = 'Egmont'; });
['9015','9010','9025','9020','9072','9052','9055','9059','9040','9050'].forEach(c => { CODE_TO_PRODUCT[c] = 'New Way'; });

function productFromCode(code) {
  const key = en(String(code || '').trim());
  return CODE_TO_PRODUCT[key] || null;
}

function typeOptionsHtml(selected, code) {
  const mapped = productFromCode(code);
  let opts = PRODUCT_OPTIONS.slice();
  let forceEmpty = false;
  if (mapped === 'Egmont') {
    opts = EGMONT_OPTIONS.slice();
    // بدون پیش‌فرض اگر هنوز یکی از دو تا انتخاب نشده
    if (selected !== 'Egmont' && selected !== 'N Egmont') {
      forceEmpty = true;
      selected = '';
    }
  } else if (mapped && mapped !== 'Egmont') {
    selected = mapped;
  }
  let html = forceEmpty ? '<option value="">— انتخاب کنید —</option>' : '';
  opts.forEach(t => {
    html += `<option value="${t}" ${selected === t ? 'selected' : ''}>${t}</option>`;
  });
  return { html, locked: !!(mapped && mapped !== 'Egmont'), mapped };
}
const MONTHS = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
const MONTH_COLORS = ['#0EA5E9','#10B981','#F59E0B','#EF4444','#8B5CF6','#EC4899','#14B8A6','#F97316','#6366F1','#84CC16','#06B6D4','#A855F7'];

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || defaultData();
  } catch {
    return defaultData();
  }
}
function defaultData() {
  return { invoices: [], balances: {}, inquiries: [], company: 'SalesMate', nextId: 1 };
}
function save(data, opts) {
  opts = opts || {};
  try {
    var prev = localStorage.getItem(KEY);
    if (prev && prev.length > 20) {
      localStorage.setItem('salesmate_db_backup', prev);
      localStorage.setItem('salesmate_db_backup_at', new Date().toISOString());
    }
  } catch (e) {}
  localStorage.setItem(KEY, JSON.stringify(data));
  if (opts.skipCloud) return;
  try { scheduleCloudPush(1500, true); } catch (e) {}
}
function restoreLocalBackup() {
  try {
    var raw = localStorage.getItem('salesmate_db_backup');
    if (!raw) return null;
    var data = JSON.parse(raw);
    if (!data || typeof data !== 'object') return null;
    localStorage.setItem(KEY, raw);
    DB = data;
    if (!Array.isArray(DB.invoices)) DB.invoices = [];
    if (!Array.isArray(DB.inquiries)) DB.inquiries = [];
    if (!Array.isArray(DB.storeSales)) DB.storeSales = [];
    return {
      inv: (DB.invoices || []).length,
      inq: (DB.inquiries || []).length,
      store: (DB.storeSales || []).length
    };
  } catch (e) { return null; }
}

let DB = load();

const SB_SESSION_KEY = 'salesmate_sb_session';

function loadSbSession() {
  try { return JSON.parse(localStorage.getItem(SB_SESSION_KEY)) || {}; } catch(e) { return {}; }
}
function saveSbSession(s) {
  localStorage.setItem(SB_SESSION_KEY, JSON.stringify(s || {}));
}
function clearSbSession() {
  localStorage.removeItem(SB_SESSION_KEY);
}

function backupOnCloseEnabled() {
  try {
    const v = localStorage.getItem('salesmate_backup_on_close');
    if (v === null) return true;
    return v === '1' || v === 'true';
  } catch(e) { return true; }
}
function setBackupOnClose(on) {
  try { localStorage.setItem('salesmate_backup_on_close', on ? '1' : '0'); } catch(e) {}
}

async function isOnlineQuick() {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return false;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 3000);
    const res = await fetch(SUPABASE_URL + '/auth/v1/health', {
      method: 'GET',
      headers: { apikey: SUPABASE_KEY },
      signal: ctrl.signal,
      cache: 'no-store'
    });
    clearTimeout(t);
    return true; // any response means network works
  } catch(e) {
    return navigator.onLine !== false && false;
  }
}

let _backupClosing = false;
async function tryBackupOnLeave() {
  if (_backupClosing) return;
  if (!backupOnCloseEnabled()) return;
  if (!sbLoggedIn()) return;
  _backupClosing = true;
  try {
    const online = await isOnlineQuick();
    if (!online) {
      // best-effort message (browsers limit dialogs on unload)
      try { alert('آفلاین هستید؛ پشتیبان ابری انجام نشد.'); } catch(e) {}
      return;
    }
    await pushToSupabase();
  } catch(e) {
    try { alert('پشتیبان ابری انجام نشد: ' + (e.message || e)); } catch(err) {}
  } finally {
    _backupClosing = false;
  }
}

function sbLoggedIn() {
  const s = loadSbSession();
  return !!(s.access_token && s.user_id);
}
function sbUser() {
  return loadSbSession();
}

async function sbAuth(path, body) {
  const res = await fetch(SUPABASE_URL + path, {
    method: 'POST',
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: 'Bearer ' + SUPABASE_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(body)
  });
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch(e) { data = { message: text }; }
  if (!res.ok) {
    const msg = (data && (data.error_description || data.msg || data.message || data.error)) || text || ('HTTP ' + res.status);
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return data;
}

function storeAuthResponse(data) {
  const prev = loadSbSession();
  let user = data.user || {};
  let uid = user.id || prev.user_id || '';
  let email = user.email || prev.email || '';
  if ((!uid || !email) && data.access_token) {
    try {
      const payload = data.access_token.split('.')[1];
      const pad = payload + '='.repeat((4 - payload.length % 4) % 4);
      const claims = JSON.parse(atob(pad.replace(/-/g, '+').replace(/_/g, '/')));
      uid = uid || claims.sub || '';
      email = email || claims.email || '';
    } catch(e) {}
  }
  saveSbSession({
    access_token: data.access_token || prev.access_token || '',
    refresh_token: data.refresh_token || prev.refresh_token || '',
    user_id: uid,
    email: email,
    expires_at: data.expires_in ? (Math.floor(Date.now()/1000) + Number(data.expires_in)) : (prev.expires_at || null)
  });
}

async function sbRefreshSession(force) {
  const sess = loadSbSession();
  if (!sess.refresh_token) return false;
  if (!force && sess.access_token) {
    try {
      const payload = sess.access_token.split('.')[1];
      const pad = payload + '='.repeat((4 - payload.length % 4) % 4);
      const claims = JSON.parse(atob(pad.replace(/-/g, '+').replace(/_/g, '/')));
      // هنوز بیش از ۳ دقیقه اعتبار دارد
      if (claims.exp && claims.exp * 1000 > Date.now() + 180000) return true;
    } catch(e) {}
  }
  const data = await sbAuth('/auth/v1/token?grant_type=refresh_token', {
    refresh_token: sess.refresh_token
  });
  if (!data.access_token) return false;
  storeAuthResponse(data);
  return true;
}

// تمدید دوره‌ای هر ۴۵ دقیقه وقتی صفحه باز است
if (typeof window !== 'undefined' && !window.__sbRefreshTimer) {
  window.__sbRefreshTimer = setInterval(function() {
    if (!sbLoggedIn()) return;
    sbRefreshSession(false).catch(function(){});
  }, 45 * 60 * 1000);
}

async function sbSignup(email, password) {
  const data = await sbAuth('/auth/v1/signup', { email: email.trim(), password });
  if (!data.access_token && data.user) {
    throw new Error('ثبت‌نام انجام شد. اگر تأیید ایمیل فعال است، ابتدا ایمیل را تأیید کنید سپس وارد شوید.');
  }
  if (!data.access_token) throw new Error('ثبت‌نام ناموفق بود.');
  storeAuthResponse(data);
  return data;
}

async function sbLogin(email, password) {
  const data = await sbAuth('/auth/v1/token?grant_type=password', { email: email.trim(), password });
  if (!data.access_token) throw new Error('ورود ناموفق بود.');
  storeAuthResponse(data);
  return data;
}

function sbLogout() {
  clearSbSession();
}

async function sbFetch(method, path, body, _retried) {
  if (!sbLoggedIn()) throw new Error('ابتدا وارد حساب ابری شوید.');
  try { await sbRefreshSession(false); } catch(e) {}
  const sess = sbUser();
  const headers = {
    apikey: SUPABASE_KEY,
    Authorization: 'Bearer ' + sess.access_token,
    'Content-Type': 'application/json',
    Prefer: 'return=representation'
  };
  const opts = { method, headers };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch(SUPABASE_URL + path, opts);
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch(e) { data = text; }
  if (!res.ok) {
    const msg = (data && (data.message || data.error_description || data.msg)) || text || ('HTTP ' + res.status);
    const s = typeof msg === 'string' ? msg : JSON.stringify(msg);
    if (!_retried && (res.status === 401 || res.status === 403) && /JWT|expired|PGRST30/i.test(s)) {
      try {
        const ok = await sbRefreshSession(true);
        if (ok) return sbFetch(method, path, body, true);
      } catch(e) {}
      throw new Error('نشست ابری منقضی شد. اگر ادامه داشت یک‌بار خروج و ورود کنید.');
    }
    throw new Error(s);
  }
  return data;
}


let _pushTimer = null;
let _cloudSynced = false;
let _cloudBusy = false;
let _lastPullAt = 0;
let _localDirty = false;
let _pushQueued = false;
function setSyncFlash(mode) {
  var el = document.getElementById('syncFlash');
  if (!el) return;
  el.classList.remove('up', 'down', 'on');
  if (mode === 'up') { el.classList.add('up', 'on'); el.textContent = '▲ ارسال'; el.title = 'ارسال به ابر'; }
  else if (mode === 'down') { el.classList.add('down', 'on'); el.textContent = '▼ دریافت'; el.title = 'دریافت از ابر'; }
  else { el.title = ''; }
}

function scheduleCloudPush(delayMs, force) {
  if (typeof sbLoggedIn === 'function' && !sbLoggedIn()) return;
  if (force) _localDirty = true;
  if (!_cloudSynced && !force) return;
  if (_cloudBusy) return;
  if (!force && Date.now() - _lastPullAt < 2000) return;
  // اگر dirty هستیم، push را عقب نیندازیم
  if (_pushTimer) clearTimeout(_pushTimer);
  _pushTimer = setTimeout(function () {
    _pushTimer = null;
    if (_cloudBusy || !sbLoggedIn()) return;
    if (!force && !_cloudSynced) return;
    if (!force && !_localDirty && Date.now() - _lastPullAt < 2000) return;
    _cloudSynced = true;
    pushToSupabase().then(function () {
      _localDirty = false;
    }).catch(function (e) { console.warn('cloud push', e); });
  }, delayMs == null ? 500 : delayMs);
}

function toIsoTimestamp(v) {
  if (v == null || v === '') return new Date().toISOString();
  var s = String(v).trim();
  // Persian digits -> English
  s = s.replace(/[۰-۹]/g, function(d) { return '۰۱۲۳۴۵۶۷۸۹'.indexOf(d); });
  // already ISO
  if (/^\d{4}-\d{2}-\d{2}T/.test(s)) {
    var d0 = new Date(s);
    if (!isNaN(d0.getTime())) return d0.toISOString();
  }
  // epoch
  if (/^\d{10,13}$/.test(s)) {
    var n = Number(s);
    return new Date(n < 1e12 ? n * 1000 : n).toISOString();
  }
  // Jalali-like or locale with slash/comma → discard
  if (/\d{4}\/\d{1,2}\/\d{1,2}/.test(s) || s.indexOf('،') >= 0 || /[^\x00-\x7F]/.test(s)) {
    return new Date().toISOString();
  }
  var d = new Date(s);
  if (!isNaN(d.getTime())) return d.toISOString();
  return new Date().toISOString();
}

function syncInvKey(inv) {
  if (!inv || typeof inv !== 'object') return '';
  var no = en(String(inv.invoiceNo || inv.invoice_no || '')).trim();
  var date = String(inv.date || '').trim();
  var cust = String(inv.customer || '').trim();
  var total = String(inv.total || '0').replace(/,/g, '').trim();
  return [no, date, cust, total].join('|');
}
function syncStoreKey(s) {
  if (!s || typeof s !== 'object') return '';
  var no = en(String(s.invoiceNo || s.invoice_no || '')).trim();
  var date = String(s.date || '').trim();
  var cust = String(s.customer || '').trim();
  var total = String(s.total || '0').replace(/,/g, '').trim();
  return [no, date, cust, total].join('|');
}
function syncInqKey(item) {
  if (!item || typeof item !== 'object') return '';
  if (item.fingerprint || item.fp) return String(item.fingerprint || item.fp);
  var buyer = String(item.buyer || item.customer || '').trim();
  var date = String(item.date || '').trim();
  var total = String(item.total || item.grandTotal || '0').trim();
  var saved = String(item.savedAt || item.createdAt || '').slice(0, 19);
  return [buyer, date, total, saved].join('|');
}

async function deleteInquiryFromCloud(item) {
  if (!item || typeof item !== 'object') return false;
  if (!sbLoggedIn()) return false;
  try {
    var uid = sbUser().user_id;
    var key = syncInqKey(item);
    if (!key) return false;
    var cloud = await sbFetch('GET', '/rest/v1/inquiries?user_id=eq.' + encodeURIComponent(uid) + '&select=id,payload') || [];
    var n = 0;
    for (var i = 0; i < cloud.length; i++) {
      var pl = cloud[i].payload;
      if (typeof pl === 'string') { try { pl = JSON.parse(pl); } catch (e) { continue; } }
      if (!pl || typeof pl !== 'object') continue;
      if (syncInqKey(pl) !== key) continue;
      if (cloud[i].id == null) continue;
      try {
        await sbFetch('DELETE', '/rest/v1/inquiries?id=eq.' + cloud[i].id + '&user_id=eq.' + encodeURIComponent(uid));
        n++;
      } catch (e) {}
    }
    return n > 0;
  } catch (e) {
    return false;
  }
}

async function pushToSupabase() {
  if (!sbLoggedIn()) throw new Error('ابتدا وارد شوید.');
  if (_cloudBusy) { _pushQueued = true; return; }
  _cloudBusy = true;
  setSyncFlash('up');
  try {
    try { DB = load(); } catch (e) {}
    const uid = sbUser().user_id;
    var nInv = (DB.invoices || []).length;
    if (nInv === 0) {
      try {
        var bak = localStorage.getItem('salesmate_db_backup');
        if (bak) {
          var bd = JSON.parse(bak);
          if ((bd.invoices || []).length > 0) {
            console.warn('push aborted: empty DB vs non-empty backup');
            return;
          }
        }
      } catch (e) {}
    }
    try {
      (DB.invoices || []).forEach(function (inv) {
        inv.createdAt = toIsoTimestamp(inv.createdAt || inv.created_at);
      });
      (DB.inquiries || []).forEach(function (item) {
        if (item && typeof item === 'object') {
          item.savedAt = toIsoTimestamp(item.savedAt || item.createdAt);
          item.createdAt = toIsoTimestamp(item.createdAt || item.savedAt);
        }
      });
      (DB.storeSales || []).forEach(function (s) {
        s.createdAt = toIsoTimestamp(s.createdAt || s.created_at);
      });
    } catch (e) {}

    // ---- invoices merge ----
    var cloudInvs = [];
    try {
      cloudInvs = await sbFetch('GET', '/rest/v1/invoices?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || [];
    } catch (e) { cloudInvs = []; }
    var cloudInvMap = {};
    cloudInvs.forEach(function (r) {
      var k = syncInvKey({ invoiceNo: r.invoice_no, date: r.date, customer: r.customer, total: r.total });
      if (k) cloudInvMap[k] = r;
    });
    var toPost = [], toPatch = [];
    (DB.invoices || []).forEach(function (inv) {
      var row = {
        customer: inv.customer || '',
        invoice_no: inv.invoiceNo || '',
        date: inv.date || '',
        time: inv.time || '',
        total: String(inv.total || '0'),
        paid_amount: String(inv.paidAmount || ''),
        created_at: toIsoTimestamp(inv.createdAt),
        inquiry_data: inv.inquiryData || '',
        image_path: inv.imagePath || '',
        user_id: uid
      };
      var k = syncInvKey(inv);
      var ex = cloudInvMap[k];
      if (ex && ex.id != null) toPatch.push({ id: ex.id, row: row });
      else toPost.push(row);
    });
    for (var i = 0; i < toPost.length; i += 80) {
      await sbFetch('POST', '/rest/v1/invoices', toPost.slice(i, i + 80));
    }
    for (var p = 0; p < toPatch.length; p++) {
      try {
        await sbFetch('PATCH', '/rest/v1/invoices?id=eq.' + toPatch[p].id + '&user_id=eq.' + encodeURIComponent(uid), toPatch[p].row);
      } catch (e) {}
    }

    // ---- balances ----
    var cloudBals = [];
    try {
      cloudBals = await sbFetch('GET', '/rest/v1/customer_balances?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || [];
    } catch (e) {}
    var balMap = {};
    cloudBals.forEach(function (b) { if (b.customer) balMap[b.customer] = b; });
    var bals = DB.balances || {};
    for (var cust in bals) {
      if (!Object.prototype.hasOwnProperty.call(bals, cust) || !cust) continue;
      var body = { customer: cust, adjustment: String(bals[cust]), note: '', updated_at: new Date().toISOString(), user_id: uid };
      var exb = balMap[cust];
      try {
        if (exb && exb.id != null) {
          await sbFetch('PATCH', '/rest/v1/customer_balances?id=eq.' + exb.id + '&user_id=eq.' + encodeURIComponent(uid), body);
        } else {
          await sbFetch('POST', '/rest/v1/customer_balances', body);
        }
      } catch (e) {
        try { await sbFetch('POST', '/rest/v1/customer_balances', body); } catch (e2) {}
      }
    }

    // ---- inquiries ----
    var cloudInqs = [];
    try {
      cloudInqs = await sbFetch('GET', '/rest/v1/inquiries?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || [];
    } catch (e) {}
    var inqMap = {};
    cloudInqs.forEach(function (r) {
      var pl = r.payload;
      if (typeof pl === 'string') { try { pl = JSON.parse(pl); } catch (e) { pl = {}; } }
      if (!pl || typeof pl !== 'object') pl = {};
      var k = syncInqKey(pl);
      if (k) inqMap[k] = r;
    });
    for (var qi = 0; qi < (DB.inquiries || []).length; qi++) {
      var item = DB.inquiries[qi];
      if (!item || typeof item !== 'object') continue;
      var ibody = { payload: item, user_id: uid, created_at: toIsoTimestamp(item.savedAt || item.createdAt) };
      var iex = inqMap[syncInqKey(item)];
      try {
        if (iex && iex.id != null) {
          await sbFetch('PATCH', '/rest/v1/inquiries?id=eq.' + iex.id + '&user_id=eq.' + encodeURIComponent(uid), ibody);
        } else {
          await sbFetch('POST', '/rest/v1/inquiries', ibody);
        }
      } catch (e) {}
    }

    // ---- store ----
    var cloudStore = [];
    try {
      cloudStore = await sbFetch('GET', '/rest/v1/store_sales?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || [];
    } catch (e) {}
    var stMap = {};
    cloudStore.forEach(function (r) {
      var k = syncStoreKey({ invoiceNo: r.invoice_no, date: r.date, customer: r.customer, total: r.total });
      if (k) stMap[k] = r;
    });
    var stPost = [];
    (DB.storeSales || []).forEach(function (s) {
      var row = {
        customer: s.customer || '', invoice_no: s.invoiceNo || '', date: s.date || '', time: s.time || '',
        total: String(s.total || '0'), tab: s.tab || 'parquet', items_json: s.itemsJson || '[]',
        created_at: toIsoTimestamp(s.createdAt), user_id: uid
      };
      var exs = stMap[syncStoreKey(s)];
      if (exs && exs.id != null) {
        sbFetch('PATCH', '/rest/v1/store_sales?id=eq.' + exs.id + '&user_id=eq.' + encodeURIComponent(uid), row).catch(function () {});
      } else stPost.push(row);
    });
    for (var si = 0; si < stPost.length; si += 80) {
      try { await sbFetch('POST', '/rest/v1/store_sales', stPost.slice(si, si + 80)); } catch (e) {}
    }

    _localDirty = false;
    _lastPullAt = Date.now();
  } finally {
    _cloudBusy = false;
    setSyncFlash('');
    if (typeof _pushQueued !== 'undefined' && _pushQueued) {
      _pushQueued = false;
      try { pushToSupabase(); } catch (e) {}
    }
  }
}


async function autoPullFromCloud(reason) {
  if (!sbLoggedIn()) return false;
  if (navigator.onLine === false) return false;
  if (_cloudBusy) return false;
  if (_localDirty) {
    try { scheduleCloudPush(300, true); } catch (e) {}
    // بعد از ارسال، ادغام از ابر
  }
  try {
    await pullFromSupabase({ force: true });
    _cloudSynced = true;
    return true;
  } catch (e) {
    console.warn('auto pull', reason, e);
    return false;
  }
}
async function pullFromSupabase(opts) {
  opts = opts || {};
  if (!sbLoggedIn()) throw new Error('ابتدا وارد شوید.');
  if (_cloudBusy) throw new Error('همگام‌سازی قبلی هنوز تمام نشده');
  if (_localDirty && !opts.force) {
    try { await pushToSupabase(); } catch (e) {
      throw new Error('ابتدا ارسال محلی: ' + (e.message || e));
    }
  }
  _cloudBusy = true;
  setSyncFlash('down');
  try {
    const uid = sbUser().user_id;
    try { DB = load(); } catch (e) {}
    if (!DB.invoices) DB.invoices = [];
    if (!DB.balances) DB.balances = {};
    if (!DB.inquiries) DB.inquiries = [];
    if (!DB.storeSales) DB.storeSales = [];

    var cloudInvs = await sbFetch('GET', '/rest/v1/invoices?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || [];
    var cloudBals = [];
    try { cloudBals = await sbFetch('GET', '/rest/v1/customer_balances?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || []; } catch (e) {}
    var cloudInqs = [];
    try { cloudInqs = await sbFetch('GET', '/rest/v1/inquiries?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || []; } catch (e) {}
    var cloudStore = [];
    try { cloudStore = await sbFetch('GET', '/rest/v1/store_sales?user_id=eq.' + encodeURIComponent(uid) + '&select=*') || []; } catch (e) {}

    var invMap = {};
    DB.invoices.forEach(function (inv) {
      var k = syncInvKey(inv);
      if (k) invMap[k] = inv;
    });
    cloudInvs.forEach(function (r) {
      var loc = {
        id: 0,
        customer: r.customer || '',
        invoiceNo: r.invoice_no || '',
        date: r.date || '',
        time: r.time || '',
        total: String(r.total || '0'),
        paidAmount: String(r.paid_amount || ''),
        createdAt: String(r.created_at || ''),
        inquiryData: r.inquiry_data || '',
        imagePath: r.image_path || ''
      };
      var k = syncInvKey(loc);
      if (!k) return;
      if (!invMap[k]) {
        DB.invoices.push(loc);
        invMap[k] = loc;
      } else {
        var cur = invMap[k];
        if (!cur.inquiryData && loc.inquiryData) cur.inquiryData = loc.inquiryData;
        if (!cur.paidAmount && loc.paidAmount) cur.paidAmount = loc.paidAmount;
      }
    });

    cloudBals.forEach(function (b) {
      if (b.customer && DB.balances[b.customer] == null) {
        DB.balances[b.customer] = String(b.adjustment || '0');
      }
    });

    // استعلام: ابر مرجع است — حذف‌شده‌ها از دستگاه هم می‌روند
    var newInqs = [];
    var seenInq = {};
    cloudInqs.forEach(function (r) {
      var pl = r.payload;
      if (typeof pl === 'string') { try { pl = JSON.parse(pl); } catch (e) { return; } }
      if (!pl || typeof pl !== 'object') return;
      var k = syncInqKey(pl);
      if (k && seenInq[k]) return;
      if (k) seenInq[k] = true;
      newInqs.push(pl);
    });
    DB.inquiries = newInqs;

    var stMap = {};
    DB.storeSales.forEach(function (s) {
      var k = syncStoreKey(s);
      if (k) stMap[k] = s;
    });
    cloudStore.forEach(function (r) {
      var loc = {
        customer: r.customer || '', invoiceNo: r.invoice_no || '', date: r.date || '', time: r.time || '',
        total: String(r.total || '0'), tab: r.tab || 'parquet', itemsJson: r.items_json || '[]',
        createdAt: String(r.created_at || '')
      };
      try { loc.items = JSON.parse(loc.itemsJson || '[]'); } catch (e) { loc.items = []; }
      if (!Array.isArray(loc.items)) loc.items = [];
      var k = syncStoreKey(loc);
      if (k && !stMap[k]) {
        DB.storeSales.push(loc);
        stMap[k] = loc;
      } else if (k && stMap[k]) {
        // اگر ابر اقلام دارد و محلی خالی است، پر کن
        var cur = stMap[k];
        if ((!cur.items || !cur.items.length) && loc.items.length) {
          cur.items = loc.items;
          cur.itemsJson = loc.itemsJson;
        }
      }
    });

    DB.nextId = DB.invoices.reduce(function (m, i) { return Math.max(m, i.id || 0); }, 0) + 1;
    DB.updatedAt = new Date().toISOString().slice(0, 19);
    _cloudSynced = true;
    _lastPullAt = Date.now();
    save(DB, { skipCloud: true });
        // نرمال‌سازی اقلام فروشگاه برای نمایش کد و متراژ
    (DB.storeSales || []).forEach(function (s) {
      if (!s.items || !s.items.length) {
        try { s.items = JSON.parse(s.itemsJson || s.items_json || '[]'); } catch (e) { s.items = []; }
      }
      if (!Array.isArray(s.items)) s.items = [];
      if (!s.itemsJson) s.itemsJson = JSON.stringify(s.items);
    });
return { merged: true, inv: DB.invoices.length, inq: DB.inquiries.length, store: DB.storeSales.length };
  } finally {
    _cloudBusy = false;
    setSyncFlash('');
  }
}



function fa(s) {
  return String(s).replace(/\d/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]);
}
function en(s) {
  return String(s).replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d));
}
function clean(s) {
  return en(String(s || '')).replace(/[,٬،\s]/g, '').replace(/[^\d.-]/g, '');
}
function amount(s) {
  const t = clean(s);
  if (!t || t === '-' || t === '+') return 0;
  const neg = t.startsWith('-');
  const n = parseInt(t.replace(/[+-]/g, '').replace(/\D/g, '') || '0', 10);
  return neg ? -n : n;
}
function fmt(n) {
  return fa(Math.round(Number(n) || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ','));
}
function words(num) {
  num = Math.floor(Math.abs(Number(num) || 0));
  if (num === 0) return 'صفر';
  const ones = ['','یک','دو','سه','چهار','پنج','شش','هفت','هشت','نه'];
  const teens = ['ده','یازده','دوازده','سیزده','چهارده','پانزده','شانزده','هفده','هجده','نوزده'];
  const tens = ['','','بیست','سی','چهل','پنجاه','شصت','هفتاد','هشتاد','نود'];
  const hundreds = ['','یکصد','دویست','سیصد','چهارصد','پانصد','ششصد','هفتصد','هشتصد','نهصد'];
  const scales = ['','هزار','میلیون','میلیارد','تریلیون'];
  function three(n) {
    let str = '';
    const h = Math.floor(n / 100), t = Math.floor((n % 100) / 10), o = n % 10;
    if (h) str += hundreds[h];
    if (t === 1) str += (str ? ' و ' : '') + teens[o];
    else {
      if (t) str += (str ? ' و ' : '') + tens[t];
      if (o) str += (str ? ' و ' : '') + ones[o];
    }
    return str;
  }
  const parts = [];
  let idx = 0, n = num;
  while (n > 0 && idx < scales.length) {
    const chunk = n % 1000;
    if (chunk) {
      let s = three(chunk);
      if (scales[idx]) s += ' ' + scales[idx];
      parts.unshift(s);
    }
    n = Math.floor(n / 1000);
    idx++;
  }
  return parts.join(' و ');
}

function customerBalance(name) {
  if (!name) return 0;
  let bal = 0;
  DB.invoices.filter(i => i.customer === name).forEach(i => {
    const t = amount(i.total);
    const p = (i.paidAmount === '' || i.paidAmount == null) ? t : amount(i.paidAmount);
    bal += t - p;
  });
  bal += amount(DB.balances[name] || 0);
  return bal;
}
function customerNames() {
  const set = new Set();
  (DB.invoices || []).forEach(i => {
    const n = (i.customer || '').trim();
    if (n) set.add(n);
  });
  (DB.inquiries || []).forEach(i => {
    const n = String(i.buyer || i.customer || '').trim();
    if (n) set.add(n);
  });
  (DB.storeSales || []).forEach(i => {
    const n = (i.customer || '').trim();
    if (n) set.add(n);
  });
  return [...set].sort((a, b) => a.localeCompare(b, 'fa'));
}

function refreshIqCustSuggestions(query) {
  const scroll = document.getElementById('iqCustScroll');
  const list = document.getElementById('custList');
  if (!scroll && !list) return;
  const q = String(query || '').trim();
  const names = customerNames().filter(n => !q || n.indexOf(q) >= 0 || n.replace(/\s/g, '').indexOf(q.replace(/\s/g, '')) >= 0);
  if (list) {
    list.innerHTML = names.map(n => '<option value="' + esc(n) + '">').join('');
  }
  if (scroll) {
    if (!names.length) {
      scroll.innerHTML = '<span class="muted">مشتری‌ای پیدا نشد — نام جدید تایپ کنید</span>';
    } else {
      scroll.innerHTML = names.slice(0, 40).map(n => {
        const b = customerBalance(n);
        const col = b > 0 ? '#dc2626' : b < 0 ? '#16a34a' : '#64748b';
        return '<button type="button" class="cust-chip" data-iqpick="' + esc(n) + '" style="border-color:' + col + ';color:' + col + '">' + esc(n) + '</button>';
      }).join('');
    }
    scroll.querySelectorAll('[data-iqpick]').forEach(b => {
      b.onclick = () => {
        const el = document.getElementById('iqBuyer');
        if (el) el.value = b.dataset.iqpick;
        inq.buyer = b.dataset.iqpick;
        refreshIqCustSuggestions(b.dataset.iqpick);
      };
    });
  }
}

function nowJalali() {
  // approximate Jalali from Gregorian (good enough for invoice date)
  const g = new Date();
  let gy = g.getFullYear(), gm = g.getMonth() + 1, gd = g.getDate();
  const g_d_m = [0,31,59,90,120,151,181,212,243,273,304,334];
  let jy = (gy <= 1600) ? 0 : 979;
  gy -= (gy <= 1600) ? 621 : 1600;
  let gy2 = (gm > 2) ? (gy + 1) : gy;
  let days = (365 * gy) + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400) - 80 + gd + g_d_m[gm - 1];
  jy += 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  const jm = (days < 186) ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + ((days < 186) ? (days % 31) : ((days - 186) % 30));
  const pad = n => String(n).padStart(2, '0');
  const time = g.toTimeString().slice(0, 8);
  return { date: jy + '/' + pad(jm) + '/' + pad(jd), time };
}

function currentYear() {
  const years = DB.invoices.map(i => (i.date || '').slice(0, 4)).filter(y => /^\d{4}$/.test(y));
  if (!years.length) return '1405';
  return String(Math.max(...years.map(Number)));
}


function salesColorMap(year) {
  const map = {};
  const names = customerNames();
  const sales = names.map(n => {
    const s = DB.invoices.filter(i => i.customer === n && (i.date || '').startsWith(year))
      .reduce((a, i) => a + amount(i.total), 0);
    return { n, s };
  }).sort((a, b) => b.s - a.s);
  const withSales = sales.filter(x => x.s > 0);
  const n = withSales.length || 1;
  withSales.forEach((x, i) => {
    // green -> yellow -> red
    const t = n === 1 ? 0 : i / (n - 1);
    let r, g, b;
    if (t < 0.5) {
      const u = t / 0.5;
      r = Math.round(34 + u * (234 - 34));
      g = Math.round(197 + u * (179 - 197));
      b = Math.round(94 + u * (8 - 94));
    } else {
      const u = (t - 0.5) / 0.5;
      r = Math.round(234 + u * (239 - 234));
      g = Math.round(179 + u * (68 - 179));
      b = Math.round(8 + u * (68 - 8));
    }
    map[x.n] = `rgb(${r},${g},${b})`;
  });
  sales.filter(x => x.s <= 0).forEach(x => { map[x.n] = '#D1D5DB'; });
  return map;
}
function monthKey(date) {
  const p = (date || '').split('/');
  if (p.length >= 2) return p[0] + '/' + p[1];
  return date || '';
}
function monthTitle(key) {
  const p = (key || '').split('/');
  if (p.length >= 2) {
    const mi = parseInt(p[1], 10) - 1;
    const name = MONTHS[mi] || p[1];
    return name + ' ' + fa(p[0]);
  }
  return fa(key);
}


/* ---------- راس‌گیری چک ---------- */
let rasRows = [{ date: '', amount: '' }];
let rasLastResult = null;
let rasBaseDate = null; // {y,m,d} تاریخ مبدأ

function jalaliToGregorian(jy, jm, jd) {
  jy = parseInt(jy, 10); jm = parseInt(jm, 10); jd = parseInt(jd, 10);
  var jy2 = jy - 979;
  var days = 365 * jy2 + Math.floor(jy2 / 33) * 8 + Math.floor(((jy2 % 33) + 3) / 4);
  for (var i = 1; i < jm; i++) days += (i <= 6) ? 31 : 30;
  days += jd - 1;
  var gdn = days + 79;
  var gy = 1600;
  gy += 400 * Math.floor(gdn / 146097);
  gdn %= 146097;
  var leap = true;
  if (gdn >= 36525) {
    gdn -= 1;
    gy += 100 * Math.floor(gdn / 36524);
    gdn %= 36524;
    if (gdn >= 365) gdn += 1;
    else leap = false;
  }
  gy += 4 * Math.floor(gdn / 1461);
  gdn %= 1461;
  if (gdn >= 366) {
    leap = false;
    gdn -= 1;
    gy += Math.floor(gdn / 365);
    gdn %= 365;
  }
  var gd = gdn + 1;
  var gdim = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  var gm = 1;
  for (var k = 0; k < gdim.length; k++) {
    if (gd <= gdim[k]) { gm = k + 1; break; }
    gd -= gdim[k];
  }
  return { y: gy, m: gm, d: gd };
}

function gregorianToJalaliNums(gy, gm, gd) {
  var gdim = [31, ((gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0) ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  var gy2 = gy - 1600, gm2 = gm - 1, gd2 = gd - 1;
  var gdn = 365 * gy2 + Math.floor((gy2 + 3) / 4) - Math.floor((gy2 + 99) / 100) + Math.floor((gy2 + 399) / 400);
  for (var i = 0; i < gm2; i++) gdn += gdim[i];
  gdn += gd2;
  var jdn = gdn - 79;
  var jnp = Math.floor(jdn / 12053);
  jdn %= 12053;
  var jy = 979 + 33 * jnp + 4 * Math.floor(jdn / 1461);
  jdn %= 1461;
  if (jdn >= 366) {
    jy += Math.floor((jdn - 1) / 365);
    jdn = (jdn - 1) % 365;
  }
  var jm = (jdn < 186) ? 1 + Math.floor(jdn / 31) : 7 + Math.floor((jdn - 186) / 30);
  var jd = 1 + ((jm <= 6) ? (jdn - (jm - 1) * 31) : (jdn - 186 - (jm - 7) * 30));
  return { y: jy, m: jm, d: jd };
}

function parseFlexibleJalali(textIn) {
  // 0809 → روز 8 ماه 9 سال جاری | 130706 → 13/07/1406
  var s = en(String(textIn || '')).trim().replace(/[-.]/g, '/').replace(/\s/g, '');
  if (!s) return null;
  var today = new Date();
  var cur = gregorianToJalaliNums(today.getFullYear(), today.getMonth() + 1, today.getDate());
  var y, m, d;

  if (/^\d+$/.test(s)) {
    var digits = s;
    var len = digits.length;
    if (len === 1 || len === 2) {
      d = parseInt(digits, 10); m = cur.m; y = cur.y;
    } else if (len === 3) {
      var d1 = parseInt(digits.slice(0, 1), 10);
      var m2 = parseInt(digits.slice(1), 10);
      var d2 = parseInt(digits.slice(0, 2), 10);
      var m1 = parseInt(digits.slice(2), 10);
      if (m2 >= 1 && m2 <= 12 && d1 >= 1 && d1 <= 31) { d = d1; m = m2; y = cur.y; }
      else if (m1 >= 1 && m1 <= 12 && d2 >= 1 && d2 <= 31) { d = d2; m = m1; y = cur.y; }
      else return null;
    } else if (len === 4) {
      d = parseInt(digits.slice(0, 2), 10);
      m = parseInt(digits.slice(2, 4), 10);
      y = cur.y;
    } else if (len === 5) {
      d = parseInt(digits.slice(0, 1), 10);
      m = parseInt(digits.slice(1, 3), 10);
      y = 1400 + parseInt(digits.slice(3), 10);
    } else if (len === 6) {
      d = parseInt(digits.slice(0, 2), 10);
      m = parseInt(digits.slice(2, 4), 10);
      y = 1400 + parseInt(digits.slice(4, 6), 10);
    } else if (len === 8) {
      d = parseInt(digits.slice(0, 2), 10);
      m = parseInt(digits.slice(2, 4), 10);
      y = parseInt(digits.slice(4, 8), 10);
    } else return null;
  } else {
    var parts = s.split('/').filter(Boolean);
    if (!parts.length) return null;
    var nums = parts.map(function (p) { return parseInt(p, 10); });
    if (nums.some(function (n) { return isNaN(n); })) return null;
    if (nums.length === 1) { y = cur.y; m = cur.m; d = nums[0]; }
    else if (nums.length === 2) {
      d = nums[0]; m = nums[1];
      if (m > 12 && d <= 12) { var tmp = d; d = m; m = tmp; }
      y = cur.y;
    } else {
      var a = nums[0], b = nums[1], c = nums[2];
      if (a > 31 || a >= 100) { y = a < 100 ? 1400 + a : a; m = b; d = c; }
      else { d = a; m = b; y = c < 100 ? 1400 + c : c; }
    }
  }
  if (!y || m < 1 || m > 12 || d < 1 || d > 31) return null;
  return { y: y, m: m, d: d };
}

function formatJalaliParts(y, m, d) {
  return String(y).padStart(4, '0') + '/' + String(m).padStart(2, '0') + '/' + String(d).padStart(2, '0');
}
function formatJalaliYmd(y, m, d) {
  // سال/ماه/روز با ارقام فارسی — روز سمت راست
  return fa(String(y).padStart(4, '0') + '/' + String(m).padStart(2, '0') + '/' + String(d).padStart(2, '0'));
}
function normalizeRasDateInput(val) {
  var p = parseFlexibleJalali(val);
  if (!p) return val;
  return formatJalaliYmd(p.y, p.m, p.d);
}



function getRasBaseParts() {
  if (rasBaseDate && rasBaseDate.y) return rasBaseDate;
  var t = new Date();
  return gregorianToJalaliNums(t.getFullYear(), t.getMonth() + 1, t.getDate());
}
function getRasBaseGDate() {
  var p = getRasBaseParts();
  var g = jalaliToGregorian(p.y, p.m, p.d);
  var d = new Date(g.y, g.m - 1, g.d);
  d.setHours(0, 0, 0, 0);
  return d;
}
function openRasBasePicker() {
  var cur = getRasBaseParts();
  var val = formatJalaliYmd(cur.y, cur.m, cur.d);
  showModal(
    '<h3>تاریخ مبدأ</h3>' +
    '<div class="muted" style="margin-bottom:8px">تاریخ مبدأ محاسبه راس را انتخاب کنید</div>' +
    '<label>تاریخ</label>' +
    '<input id="rasBaseIn" class="ltr" value="' + esc(val) + '" placeholder="" />' +
    '<div class="muted mt" style="font-size:12px">یا از تقویم زیر انتخاب کنید</div>' +
    '<div id="rasCal" style="margin-top:10px"></div>' +
    '<button class="btn btn-primary btn-block mt" id="rasBaseOk">تأیید</button>' +
    '<button class="btn btn-secondary btn-block" id="rasBaseToday">امروز</button>' +
    '<button class="btn btn-secondary btn-block" id="mClose">انصراف</button>'
  );
  // mini jalali calendar
  var calHost = document.getElementById('rasCal');
  var viewY = cur.y, viewM = cur.m;
  function renderCal() {
    var monthNames = ['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
    var daysInMonth = (viewM <= 6) ? 31 : (viewM <= 11 ? 30 : (((viewY % 33) % 4 === 1) ? 30 : 29));
    // weekday of 1st
    var g1 = jalaliToGregorian(viewY, viewM, 1);
    var wd = new Date(g1.y, g1.m - 1, g1.d).getDay(); // 0 Sun
    // convert to Sat=0
    var start = (wd + 1) % 7;
    var h = '<div class="row between" style="margin-bottom:8px">' +
      '<button type="button" class="btn btn-sm btn-secondary" id="calPrev">‹</button>' +
      '<strong>' + monthNames[viewM - 1] + ' ' + fa(viewY) + '</strong>' +
      '<button type="button" class="btn btn-sm btn-secondary" id="calNext">›</button></div>';
    h += '<div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;text-align:center;font-size:12px">';
    ['ش','ی','د','س','چ','پ','ج'].forEach(function (x) { h += '<div class="muted">' + x + '</div>'; });
    for (var i = 0; i < start; i++) h += '<div></div>';
    for (var day = 1; day <= daysInMonth; day++) {
      var sel = (viewY === cur.y && viewM === cur.m && day === cur.d);
      h += '<button type="button" data-cal-d="' + day + '" style="padding:8px 0;border-radius:8px;border:none;background:' +
        (sel ? '#0284c7' : '#f1f5f9') + ';color:' + (sel ? '#fff' : '#0f172a') + ';font-weight:600">' + fa(day) + '</button>';
    }
    h += '</div>';
    calHost.innerHTML = h;
    document.getElementById('calPrev').onclick = function () {
      viewM--; if (viewM < 1) { viewM = 12; viewY--; }
      renderCal();
    };
    document.getElementById('calNext').onclick = function () {
      viewM++; if (viewM > 12) { viewM = 1; viewY++; }
      renderCal();
    };
    calHost.querySelectorAll('[data-cal-d]').forEach(function (b) {
      b.onclick = function () {
        cur = { y: viewY, m: viewM, d: +b.dataset.calD };
        document.getElementById('rasBaseIn').value = formatJalaliYmd(cur.y, cur.m, cur.d);
        renderCal();
      };
    });
  }
  renderCal();
  document.getElementById('mClose').onclick = hideModal;
  document.getElementById('rasBaseToday').onclick = function () {
    var t = new Date();
    rasBaseDate = gregorianToJalaliNums(t.getFullYear(), t.getMonth() + 1, t.getDate());
    hideModal();
    go('ras');
  };
  document.getElementById('rasBaseOk').onclick = function () {
    var parsed = parseFlexibleJalali(document.getElementById('rasBaseIn').value);
    if (!parsed) { alert('تاریخ نامعتبر است'); return; }
    rasBaseDate = parsed;
    hideModal();
    go('ras');
  };
}



function loadInventory() {
  try {
    var raw = localStorage.getItem('salesmate_inventory');
    if (!raw) return [];
    var data = JSON.parse(raw);
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.items)) return data.items;
  } catch (e) {}
  return [];
}
function saveInventoryLocal(items) {
  localStorage.setItem('salesmate_inventory', JSON.stringify({
    items: items || [],
    updatedAt: new Date().toISOString()
  }));
}
async function pullInventoryFromCloud() {
  if (!sbLoggedIn()) return loadInventory();
  try {
    var rows = await sbFetch('GET', '/rest/v1/inventory_items?select=*&order=product_code.asc') || [];
    var items = rows.map(function (r) {
      return {
        product_code: r.product_code || '',
        product_name: r.product_name || '',
        cartons: Number(r.cartons || 0),
        meters: Number(r.meters || 0),
        design_codes: r.design_codes || ''
      };
    });
    saveInventoryLocal(items);
    return items;
  } catch (e) {
    console.warn('inventory pull', e);
    return loadInventory();
  }
}
function searchInventory(query) {
  var q = String(query || '').trim();
  if (!q) return [];
  var qNorm = en(q).toLowerCase().replace(/\s+/g, ' ');
  var items = loadInventory();
  return items.filter(function (it) {
    // فقط نام کالا
    var name = String(it.product_name || '');
    var nameNorm = en(name).toLowerCase().replace(/\s+/g, ' ');
    if (nameNorm.indexOf(qNorm) >= 0) return true;
    // بدون فاصله هم
    if (nameNorm.replace(/\s/g, '').indexOf(qNorm.replace(/\s/g, '')) >= 0) return true;
    return false;
  });
}
function inventoryUnitLabels(it) {
  var name = String((it && it.product_name) || '');
  var unit = String((it && (it.unit || it.unit_name || it.vahed)) || '');
  var blob = (name + ' ' + unit).toLowerCase();
  // MDF → ورق و پالت
  if (/mdf|ام\s*دی\s*اف|ورق|پالت/.test(blob) && !/پارکت|parquet|hdf|luxury|valente|egmont|charlotte|new\s*way|ایزوفام/.test(blob)) {
    return { u1: 'پالت', u2: 'ورق' };
  }
  if (/ورق|پالت/.test(blob)) return { u1: 'پالت', u2: 'ورق' };
  if (/mdf/.test(blob)) return { u1: 'پالت', u2: 'ورق' };
  // پیش‌فرض پارکت
  return { u1: 'کارتن', u2: 'متر مربع' };
}
function renderInventory() {
  var q = window._invQuery || '';
  var results = q ? searchInventory(q) : [];
  var html = '<div class="card">' +
    '<h2>موجودی کالا</h2>' +
    '<div class="muted">جستجو فقط روی <b>نام کالا</b></div>' +
    '<input id="invCode" placeholder="" value="' + esc(q) + '" style="text-align:right;font-size:16px;font-weight:600;margin-top:10px" />' +
    '<button type="button" class="btn btn-primary btn-block mt" id="invSearch">جستجو</button>' +
    '<button type="button" class="btn btn-primary btn-block" id="invRefresh" style="margin-top:8px;background:#0369a1">⬇ دریافت موجودی از ابر</button>' +
    '</div>';
  if (!q) {
    html += '<div class="muted" style="text-align:center;margin-top:16px">نام کالا را بنویسید</div>';
  } else if (!results.length) {
    html += '<div class="card" style="margin-top:12px;text-align:center">موردی با نام «' + esc(q) + '» پیدا نشد</div>';
  } else {
    html += '<div class="muted" style="margin:10px 0">' + fa(results.length) + ' مورد</div>';
    results.forEach(function (it) {
      var cart = Number(it.cartons || 0);
      var m2 = Number(it.meters || 0);
      var units = inventoryUnitLabels(it);
      var cartCls = cart <= 0 ? 'color:#b91c1c' : (cart < 20 ? 'color:#c2410c' : 'color:#047857');
      html += '<div class="list-item" style="margin-bottom:8px">' +
        '<div style="font-size:13px;font-weight:700;line-height:1.5">' + esc(it.product_name || '—') + '</div>' +
        '<div class="row between" style="margin-top:10px">' +
        '<div><div class="muted" style="font-size:11px">' + esc(units.u1) + '</div><strong style="' + cartCls + ';font-size:16px" class="ltr">' + fa(Math.round(cart * 1000) / 1000) + '</strong></div>' +
        '<div style="text-align:left"><div class="muted" style="font-size:11px">' + esc(units.u2) + '</div><strong class="ltr" style="font-size:16px;color:#0369a1">' + fa(Math.round(m2 * 100) / 100) + '</strong></div>' +
        '</div></div>';
    });
  }
  return html;
}
function bindInventoryPage() {
  var inp = document.getElementById('invCode');
  var doSearch = function () {
    var v = String((inp && inp.value) || '').trim();
    window._invQuery = v;
    go('inventory');
  };
  if (inp) {
    inp.removeAttribute('inputmode');
    inp.removeAttribute('pattern');
    inp.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doSearch(); }
    });
  }
  var btn = document.getElementById('invSearch');
  if (btn) btn.onclick = doSearch;
  var ref = document.getElementById('invRefresh');
  if (ref) ref.onclick = async function () {
    ref.disabled = true;
    ref.textContent = 'در حال دریافت...';
    try {
      await pullInventoryFromCloud();
      alert('موجودی بروزرسانی شد: ' + fa(loadInventory().length) + ' قلم');
      go('inventory');
    } catch (e) {
      alert('خطا: ' + (e.message || e));
      ref.disabled = false;
      ref.textContent = '⬇ دریافت موجودی از ابر';
    }
  };
}


function renderRas() {
  if (!rasRows.length) rasRows = [{ date: '', amount: '' }];
  var r = rasLastResult;
  var totalTxt = r ? fmt(r.total) + ' ریال' : '—';
  var daysTxt = r ? r.daysTxt : '—';
  var rasTxt = r ? fa(r.rasStr) : '—';
  var detail = r ? esc(r.detail) : 'پس از ورود چک‌ها «محاسبه راس» را بزنید.';
  var rowsHtml = '';
  rasRows.forEach(function (row, i) {
    rowsHtml += '<div class="ras-row">' +
      '<div><label>تاریخ</label><input data-ras-f="date" data-ras-i="' + i + '" value="' + esc(row.date) + '" placeholder="" class="ltr ras-date" inputmode="numeric" dir="ltr" style="direction:ltr;text-align:center;font-family:Vazirmatn,Tahoma,sans-serif" /></div>' +
      '<div><label>مبلغ</label><input data-ras-f="amount" data-ras-i="' + i + '" value="' + esc(row.amount) + '" placeholder="مبلغ" class="ltr" inputmode="numeric" /></div>' +
      '<button type="button" class="btn btn-danger btn-sm" data-ras-rm="' + i + '" style="margin-bottom:2px">✕</button>' +
      '</div>';
  });
  var baseP = getRasBaseParts();
  var baseStr = formatJalaliYmd(baseP.y, baseP.m, baseP.d);
  return '' +
    '<div class="card"><h2>راس‌گیری چک</h2>' +
    '<div class="muted">تاریخ به صورت سال/ماه/روز</div>' +
    '<div class="list-item" id="rasBasePick" style="cursor:pointer;background:#fff7ed;border:1px solid #fdba74;margin:10px 0">' +
    '<div class="row between"><span>📅 تاریخ مبدأ</span><strong class="ltr" style="color:#9a3412">' + baseStr + '</strong></div>' +
    '<div class="muted" style="font-size:11px;margin-top:4px">برای تغییر بزنید</div></div>' +
    '<div class="ras-cards">' +
    '<div class="ras-card" style="background:#0284c7"><div class="rl">جمع مبلغ</div><div class="rv">' + totalTxt + '</div></div>' +
    '<div class="ras-card" style="background:#f59e0b"><div class="rl">روز از مبدأ</div><div class="rv">' + daysTxt + '</div></div>' +
    '<div class="ras-card" style="background:#059669"><div class="rl">تاریخ راس</div><div class="rv">' + rasTxt + '</div></div>' +
    '</div>' +
    '<div class="row between"><strong>لیست چک‌ها</strong><button type="button" class="btn btn-primary btn-sm" id="rasAdd">+ افزودن چک</button></div>' +
    '<div id="rasRows">' + rowsHtml + '</div>' +
    '<button type="button" class="btn btn-green btn-block mt" id="rasCalc">محاسبه راس</button>' +
    (r ? ('<button type="button" class="btn btn-primary btn-block mt" id="rasPdf">📄 خروجی PDF</button>' + '<button type="button" class="btn btn-primary btn-block" id="rasImg">🖼 خروجی تصویر</button>') : '') +
    '<div class="muted mt" style="white-space:pre-line;line-height:1.7">' + detail + '</div>' +
    '</div>';
}

function bindRasPage() {
  var basePick = document.getElementById('rasBasePick');
  if (basePick) basePick.onclick = openRasBasePicker;
  function syncFromDom() {
    document.querySelectorAll('[data-ras-f]').forEach(function (inp) {
      var i = +inp.dataset.rasI;
      var f = inp.dataset.rasF;
      if (!rasRows[i]) return;
      if (f === 'amount') {
        // نمایش با جداکننده
        var raw = clean(inp.value);
        rasRows[i].amount = raw;
        var n = amount(raw);
        if (n && String(inp.value).replace(/[^\d]/g, '').length >= 4) {
          var pretty = fmt(n).replace(/[۰-۹]/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'.indexOf(d); });
          // keep English digits with commas for input
          pretty = String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
          if (inp.value !== pretty && document.activeElement !== inp) inp.value = pretty;
        }
      } else {
        rasRows[i][f] = inp.value;
      }
    });
  }

  document.querySelectorAll('[data-ras-f]').forEach(function (inp) {
    if (inp.dataset.rasF === 'date') {
      inp.onblur = function () {
        var i = +inp.dataset.rasI;
        var n = normalizeRasDateInput(inp.value);
        inp.value = n;
        if (rasRows[i]) rasRows[i].date = n;
      };
    }
    inp.oninput = function () {
      var i = +inp.dataset.rasI;
      var f = inp.dataset.rasF;
      if (!rasRows[i]) return;
      if (f === 'amount') {
        var digits = en(inp.value).replace(/[^\d]/g, '');
        rasRows[i].amount = digits;
        // format live
        if (digits) {
          var pretty = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
          var pos = inp.selectionStart;
          var oldLen = inp.value.length;
          inp.value = pretty;
          var newLen = pretty.length;
          try { inp.setSelectionRange(pos + (newLen - oldLen), pos + (newLen - oldLen)); } catch (e) {}
        }
      } else {
        rasRows[i][f] = inp.value;
      }
    };
    inp.onkeydown = function (e) {
      if (e.key !== 'Enter') return;
      e.preventDefault();
      var i = +inp.dataset.rasI;
      var f = inp.dataset.rasF;
      if (f === 'date') {
        var next = document.querySelector('[data-ras-i="' + i + '"][data-ras-f="amount"]');
        if (next) next.focus();
      } else if (f === 'amount') {
        if (i === rasRows.length - 1) {
          rasRows.push({ date: '', amount: '' });
          go('ras');
          setTimeout(function () {
            var el = document.querySelector('[data-ras-i="' + (rasRows.length - 1) + '"][data-ras-f="date"]');
            if (el) el.focus();
          }, 50);
        } else {
          var n = document.querySelector('[data-ras-i="' + (i + 1) + '"][data-ras-f="date"]');
          if (n) n.focus();
        }
      }
    };
  });

  document.querySelectorAll('[data-ras-rm]').forEach(function (b) {
    b.onclick = function () {
      var i = +b.dataset.rasRm;
      rasRows.splice(i, 1);
      if (!rasRows.length) rasRows = [{ date: '', amount: '' }];
      go('ras');
    };
  });

  var add = document.getElementById('rasAdd');
  if (add) add.onclick = function () {
    syncFromDom();
    rasRows.push({ date: '', amount: '' });
    go('ras');
    setTimeout(function () {
      var el = document.querySelector('[data-ras-i="' + (rasRows.length - 1) + '"][data-ras-f="date"]');
      if (el) { el.focus(); el.scrollIntoView({ block: 'center' }); }
    }, 50);
  };

  var calc = document.getElementById('rasCalc');
  if (calc) calc.onclick = function () {
    syncFromDom();
    var today = getRasBaseGDate();
    var items = [];
    for (var i = 0; i < rasRows.length; i++) {
      var row = rasRows[i];
      var am = amount(row.amount);
      if (!row.date && !am) continue;
      var jd = parseFlexibleJalali(row.date);
      if (!jd) {
        alert('تاریخ ردیف ' + fa(i + 1) + ' نامعتبر است');
        return;
      }
      if (!am) {
        alert('مبلغ ردیف ' + fa(i + 1) + ' را وارد کنید');
        return;
      }
      var g = jalaliToGregorian(jd.y, jd.m, jd.d);
      var gdate = new Date(g.y, g.m - 1, g.d);
      var delta = Math.round((gdate - today) / 86400000);
      items.push({ amount: am, delta: delta, y: jd.y, m: jd.m, d: jd.d, gdate: gdate });
    }
    if (!items.length) {
      alert('حداقل یک چک با تاریخ و مبلغ وارد کنید');
      return;
    }
    items.sort(function (a, b) { return a.gdate - b.gdate; });
    var total = items.reduce(function (s, x) { return s + x.amount; }, 0);
    var weighted = items.reduce(function (s, x) { return s + x.amount * x.delta; }, 0);
    var avgDays = weighted / total;
    var avgRound = Math.round(avgDays);
    var rasG = new Date(today.getTime());
    rasG.setDate(rasG.getDate() + avgRound);
    var rasJ = gregorianToJalaliNums(rasG.getFullYear(), rasG.getMonth() + 1, rasG.getDate());
    var rasStr = formatJalaliYmd(rasJ.y, rasJ.m, rasJ.d);
    var daysTxt;
    if (avgRound > 0) daysTxt = fa(avgRound) + ' روز بعد';
    else if (avgRound < 0) daysTxt = fa(Math.abs(avgRound)) + ' روز قبل';
    else daysTxt = 'روز مبدأ';
    var details = items.map(function (x, idx) {
      return 'چک ' + fa(idx + 1) + ': ' + formatJalaliYmd(x.y, x.m, x.d) +
        '  ·  ' + fmt(x.amount) + ' ریال  ·  ' + fa(x.delta) + ' روز';
    });
    rasLastResult = {
      total: total,
      avgDays: avgDays,
      avgRound: avgRound,
      daysTxt: daysTxt,
      rasStr: rasStr,
      items: items,
      baseStr: formatJalaliYmd(getRasBaseParts().y, getRasBaseParts().m, getRasBaseParts().d),
      detail: 'مبدأ: ' + formatJalaliYmd(getRasBaseParts().y, getRasBaseParts().m, getRasBaseParts().d) +
        '\nجزئیات (به ترتیب تاریخ):\n' + details.join('\n') +
        '\n\nمیانگین وزنی: ' + fa(avgDays.toFixed(2)) + ' روز  →  راس: ' + rasStr
    };
    go('ras');
  };
  function exportRas(asImage) {
    if (!rasLastResult) { alert('ابتدا محاسبه راس را انجام دهید'); return; }
    var r = rasLastResult;
    var itemsHtml = (r.items || []).map(function (x, idx) {
      return '<tr>' +
        '<td style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">' + fa(idx + 1) + '</td>' +
        '<td style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0;direction:ltr">' + formatJalaliYmd(x.y, x.m, x.d) + '</td>' +
        '<td style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0;direction:ltr">' + fmt(x.amount) + '</td>' +
        '<td style="padding:8px;text-align:center;border-bottom:1px solid #e2e8f0">' + fa(x.delta) + ' روز</td></tr>';
    }).join('');
    var inner = '<div id="estelamShareRoot" style="width:800px;max-width:100%;margin:0 auto;background:#fff;font-family:Tahoma,Vazirmatn,sans-serif;direction:rtl;color:#0f172a;padding:8px">' +
      '<div style="background:#0284c7;color:#fff;padding:16px 18px;border-radius:16px 16px 0 0">' +
      '<div style="font-size:20px;font-weight:800">گزارش راس‌گیری چک</div>' +
      '<div style="font-size:12px;opacity:.9;margin-top:4px">' + esc(DB.company || 'SalesMate') + '</div></div>' +
      '<div style="display:flex;gap:10px;padding:14px 0">' +
      '<div style="flex:1;background:#0284c7;border-radius:14px;padding:14px;color:#fff;text-align:center"><div style="font-size:12px;opacity:.9">جمع مبلغ</div><div style="font-size:16px;font-weight:800;margin-top:6px;direction:ltr">' + fmt(r.total) + ' ریال</div></div>' +
      '<div style="flex:1;background:#f59e0b;border-radius:14px;padding:14px;color:#fff;text-align:center"><div style="font-size:12px;opacity:.9">تعداد روز</div><div style="font-size:16px;font-weight:800;margin-top:6px">' + esc(r.daysTxt) + '</div></div>' +
      '<div style="flex:1;background:#059669;border-radius:14px;padding:14px;color:#fff;text-align:center"><div style="font-size:12px;opacity:.9">تاریخ راس</div><div style="font-size:18px;font-weight:900;margin-top:6px;direction:ltr">' + fa(r.rasStr) + '</div></div></div>' +
      '<table style="width:100%;border-collapse:collapse;margin-top:8px"><thead><tr style="background:#0284c7;color:#fff">' +
      '<th style="padding:10px">ردیف</th><th style="padding:10px">تاریخ چک</th><th style="padding:10px">مبلغ</th><th style="padding:10px">روز از امروز</th></tr></thead><tbody>' + itemsHtml + '</tbody></table>' +
      '<div style="margin-top:14px;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:14px;padding:14px;text-align:center">' +
      '<div style="color:#047857;font-size:13px">میانگین وزنی</div>' +
      '<div style="font-size:18px;font-weight:800;color:#047857;margin-top:4px">' + fa((r.avgDays || 0).toFixed(2)) + ' روز</div>' +
      '<div style="margin-top:8px;font-size:16px;font-weight:800">تاریخ راس: <span style="direction:ltr;display:inline-block">' + fa(r.rasStr) + '</span></div></div></div>';
    showInquiryPreview(inner, asImage, 'راس چک', r.total, {
      shareTitle: 'راس چک‌ها',
      shareText: 'راس چک‌ها — مبلغ کل: ' + fmt(r.total) + ' ریال'
    }).catch(function (err) {
      alert('خروجی انجام نشد: ' + (err && err.message ? err.message : err));
    });
  }
  var pdfBtn = document.getElementById('rasPdf');
  if (pdfBtn) pdfBtn.onclick = function () { exportRas(false); };
  var imgBtn = document.getElementById('rasImg');
  if (imgBtn) imgBtn.onclick = function () { exportRas(true); };
}



const titles = {
  home: 'خانه', invoices: 'حواله‌ها', inquiry: 'استعلام',
  customers: 'مشتریان', reports: 'گزارش‌ها', store: 'فروشگاه', inventory: 'موجودی', ras: 'راس چک', settings: 'تنظیمات'
};

function go(page, opts) {
  opts = opts || {};
  const keepScroll = !!opts.keepScroll;
  const _sy = keepScroll ? window.scrollY : 0;
  const _ae = document.activeElement;
  let _fs = null;
  if (keepScroll && _ae) {
    if (_ae.id) _fs = '#' + _ae.id;
    else if (_ae.dataset && _ae.dataset.r != null)
      _fs = '[data-r="' + _ae.dataset.r + '"][data-f="' + _ae.dataset.f + '"]';
  }
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.page === page));
  document.getElementById('pageTitle').textContent = titles[page] || page;
  const app = document.getElementById('app');
  if (page === 'home') app.innerHTML = renderHome();
  else if (page === 'invoices') app.innerHTML = renderInvoices();
  else if (page === 'inquiry') app.innerHTML = renderInquiry();
  else if (page === 'customers') app.innerHTML = renderCustomers();
  else if (page === 'reports') app.innerHTML = renderReports();
  else if (page === 'store') app.innerHTML = renderStore();
  else if (page === 'inventory') app.innerHTML = renderInventory();
  else if (page === 'ras') app.innerHTML = renderRas();
  else if (page === 'settings') app.innerHTML = renderSettings();
  bindPage(page);
  if (keepScroll) {
    window.scrollTo(0, _sy);
    if (_fs) {
      const el = document.querySelector(_fs);
      if (el) {
        try { el.focus({ preventScroll: true }); } catch (e) { try { el.focus(); } catch (e2) {} }
      }
    }
  } else {
    window.scrollTo(0, 0);
  }
}

/* ---------- HOME ---------- */
function storeWeekKey(dateStr) {
  const p = en(String(dateStr || '')).split('/');
  if (p.length < 3) return [0, 0];
  const y = parseInt(p[0], 10), m = parseInt(p[1], 10), d = parseInt(p[2], 10);
  if (!y || !m || !d) return [0, 0];
  let days = (m - 1) * 31;
  if (m > 6) days = 6 * 31 + (m - 7) * 30;
  days += d;
  return [y, Math.floor((days - 1) / 7)];
}
function storeParseItems(s) {
  if (!s) return [];
  if (Array.isArray(s.items) && s.items.length) return s.items;
  var raw = s.itemsJson || s.items_json || '[]';
  if (typeof raw === 'string') {
    try { raw = JSON.parse(raw || '[]'); } catch (e) { raw = []; }
  }
  return Array.isArray(raw) ? raw : [];
}
function storeItemsMeterage(items) {
  let t = 0;
  (items || []).forEach(it => {
    const v = parseFloat(en(String(it.qty2 || '')).replace(/,/g, '')) || 0;
    t += v;
  });
  return t;
}
function fmtMeter(m) {
  if (!m) return fa('0');
  const s = String(Number(m).toFixed(4)).replace(/\.?0+$/, '');
  return fa(s);
}
function invoiceItemsSummary(inquiryData) {
  if (!inquiryData) return 'جزئیات کالا ثبت نشده';
  let data = inquiryData;
  try {
    if (typeof data === 'string') data = JSON.parse(data);
  } catch (e) { return 'جزئیات کالا ثبت نشده'; }
  const rows = (data && data.rows) || [];
  const tab = (data && data.tab) || 'parquet';
  if (!rows.length) return 'جزئیات کالا ثبت نشده';
  return rows.map((r, i) => {
    const bits = [(i + 1) + ')'];
    let unit = amount(r.price);
    if (!unit) {
      const q2 = parseFloat(clean(r.qty2)) || 0;
      const cost = amount(r.cost);
      if (q2 > 0 && cost > 0) unit = Math.round(cost / q2);
    }
    if (tab === 'parquet') {
      bits.push('کد ' + (r.code || '—'));
      if (r.type) bits.push(r.type);
      if (r.qty1 !== undefined && r.qty1 !== '') bits.push(fa(r.qty1) + ' کارتن');
      if (r.qty2 !== undefined && r.qty2 !== '') bits.push(fa(r.qty2) + ' متر');
      if (unit > 0) bits.push('هر متر ' + fmt(unit));
    } else {
      if (r.code) bits.push('کد ' + r.code);
      if (r.type) bits.push(r.type);
      if (r.qty1 !== undefined && r.qty1 !== '') bits.push(fa(r.qty1));
      if (r.qty2 !== undefined && r.qty2 !== '') bits.push(fa(r.qty2));
      if (unit > 0) bits.push('فی ' + fmt(unit));
    }
    return bits.join(' · ');
  }).join('\n');
}

function renderHome() {
  const nj = nowJalali();
  const y = currentYear();
  const today = nj.date;
  const cm = parseInt(en(today).split('/')[1], 10) || 1;
  const monthPrefix = y + '/' + String(cm).padStart(2, '0') + '/';
  const yearInvs = DB.invoices.filter(i => (i.date || '').startsWith(y));
  const yearTotal = yearInvs.reduce((s, i) => s + amount(i.total), 0);
  const dayInvs = DB.invoices.filter(i => i.date === today);
  const dayTotal = dayInvs.reduce((s, i) => s + amount(i.total), 0);
  const dayCount = dayInvs.length;
  const monthInvs = DB.invoices.filter(i => (i.date || '').startsWith(monthPrefix.slice(0, 8)));
  const monthTotal = monthInvs.reduce((s, i) => s + amount(i.total), 0);
  const monthCount = monthInvs.length;
  const avgMonth = monthCount ? Math.round(monthTotal / monthCount) : 0;

  const curWeek = storeWeekKey(today);
  let storeWeekSum = 0, storeWeekM = 0, storeMonthSum = 0, storeMonthM = 0;
  (DB.storeSales || []).forEach(s => {
    const tot = amount(s.total);
    const meters = storeItemsMeterage(storeParseItems(s));
    const parts = en(String(s.date || '')).split('/');
    const sy = parseInt(parts[0], 10), sm = parseInt(parts[1], 10);
    if (sy === parseInt(y, 10) && sm === cm) {
      storeMonthSum += tot; storeMonthM += meters;
    }
    const wk = storeWeekKey(s.date);
    if (wk[0] === curWeek[0] && wk[1] === curWeek[1] && curWeek[0]) {
      storeWeekSum += tot; storeWeekM += meters;
    }
  });

  const savedInq = (DB.inquiries || []).length;
  const colors = salesColorMap(y);
  const recent = [...DB.invoices].sort((a, b) => {
    const ka = (a.date || '') + (a.time || '') + String(a.id || '').padStart(8, '0');
    const kb = (b.date || '') + (b.time || '') + String(b.id || '').padStart(8, '0');
    return kb.localeCompare(ka);
  }).slice(0, 7);

  const top = {};
  monthInvs.forEach(i => {
    if (!i.customer) return;
    top[i.customer] = (top[i.customer] || 0) + amount(i.total);
  });
  const topList = Object.entries(top).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxTop = topList.length ? topList[0][1] : 1;

  let html = `
    <div class="kpi-grid">
      <div class="kpi-card" style="border-top-color:#0284c7"><div class="k-label">فروش امروز</div><div class="k-value ltr">${fmt(dayTotal)}</div></div>
      <div class="kpi-card" style="border-top-color:#0ea5e9"><div class="k-label">حواله امروز</div><div class="k-value">${fa(dayCount)} فقره</div></div>
      <div class="kpi-card" style="border-top-color:#059669"><div class="k-label">فروش ماه</div><div class="k-value ltr">${fmt(monthTotal)}</div></div>
      <div class="kpi-card" style="border-top-color:#8b5cf6"><div class="k-label">میانگین حواله</div><div class="k-value ltr">${fmt(avgMonth)}</div></div>
      <div class="kpi-card" style="border-top-color:#0ea5e9"><div class="k-label">فروشگاه هفته</div><div class="k-value ltr">${fmt(storeWeekSum)}</div><div class="k-sub">متراژ ${fmtMeter(storeWeekM)}</div></div>
      <div class="kpi-card" style="border-top-color:#059669"><div class="k-label">فروشگاه ماه</div><div class="k-value ltr">${fmt(storeMonthSum)}</div><div class="k-sub">متراژ ${fmtMeter(storeMonthM)}</div></div>
      <div class="kpi-card kpi-click" id="homeSavedInq" style="border-top-color:#f59e0b"><div class="k-label">استعلام ذخیره‌شده</div><div class="k-value">${fa(savedInq)} مورد</div><div class="k-sub">برای مشاهده بزنید</div></div>
      <div class="kpi-card" style="border-top-color:#6366f1"><div class="k-label">فروش سال ${fa(y)}</div><div class="k-value ltr">${fmt(yearTotal)}</div><div class="k-sub">ماه ${fa(cm)}</div></div>
    </div>
    <div class="quick-actions">
      <button type="button" class="btn btn-primary" id="homeNewInv">حواله جدید</button>
      <button type="button" class="btn btn-dark" id="homeInq">استعلام</button>
      <button type="button" class="btn btn-green" id="homeStore">فروشگاه</button>
    </div>
    <div class="card" style="margin-top:12px"><h2>آخرین حواله‌ها</h2>`;

  if (!recent.length) html += `<div class="empty">حواله‌ای ثبت نشده</div>`;
  else {
    recent.forEach(i => {
      const bg = colors[i.customer] || '#e2e8f0';
      const tip = esc(invoiceItemsSummary(i.inquiryData)).replace(/\n/g, '&#10;');
      html += `<div class="home-inv-card" style="background:${bg}" title="${tip}">
        <div class="row between">
          <div>
            <strong>${esc(i.customer)}</strong>
            <div class="muted">ش ${fa(i.invoiceNo)} · ${fa(i.date)} ${fa(i.time || '')}</div>
          </div>
          <span class="ltr" style="font-weight:800">${fmt(i.total)}</span>
        </div>
        <div class="home-tip muted">${invoiceItemsSummary(i.inquiryData).split('\n').map(x => esc(x)).join('<br>')}</div>
      </div>`;
    });
  }
  html += `</div>
    <div class="card home-top-card" style="margin-top:12px">
      <h2>برترین مشتریان ماه</h2>
      <div class="home-top-scroll">`;
  if (!topList.length) html += `<div class="empty">فروشی در این ماه نیست</div>`;
  else {
    // همه مشتریان ماه (نه فقط ۵ تا) با اسکرول
    const allTop = Object.entries(top).sort((a, b) => b[1] - a[1]);
    const maxAll = allTop.length ? allTop[0][1] : 1;
    allTop.forEach(([name, val], idx) => {
      const pct = Math.max(4, Math.round(100 * val / maxAll));
      const col = colors[name] || '#0284c7';
      html += `<div class="top-row">
        <div class="row between"><span>${fa(idx + 1)}. ${esc(name)}</span><strong class="ltr">${fmt(val)}</strong></div>
        <div class="bar-bg"><div class="bar-fill" style="width:${pct}%;background:${col}"></div></div>
      </div>`;
    });
  }
  html += `</div></div>`;

  // بدهکار / طلبکار
  const debtors = [];
  const creditors = [];
  customerNames().forEach(name => {
    const bal = customerBalance(name);
    if (bal > 0) debtors.push([name, bal]);
    else if (bal < 0) creditors.push([name, bal]);
  });
  debtors.sort((a, b) => b[1] - a[1]);
  creditors.sort((a, b) => a[1] - b[1]);

  html += `<div class="card home-debt-card" style="margin-top:12px">
    <h2 style="color:#b91c1c">بدهکارها</h2>`;
  if (!debtors.length) html += `<div class="empty">بدهکاری نیست</div>`;
  else {
    debtors.forEach(([name, bal]) => {
      html += `<div class="bal-row debt">
        <span>${esc(name)}</span>
        <strong class="ltr" style="color:#b91c1c">${fmt(bal)}</strong>
      </div>`;
    });
  }
  html += `</div>
  <div class="card home-cred-card" style="margin-top:12px">
    <h2 style="color:#047857">طلبکارها</h2>`;
  if (!creditors.length) html += `<div class="empty">طلبکاری نیست</div>`;
  else {
    creditors.forEach(([name, bal]) => {
      html += `<div class="bal-row cred">
        <span>${esc(name)}</span>
        <strong class="ltr" style="color:#047857">${fmt(Math.abs(bal))}</strong>
      </div>`;
    });
  }
  html += `</div>`;
  return html;
}

/* ---------- INVOICES ---------- */
function renderInvoices(filter = '') {
  let list = [...DB.invoices].sort((a, b) => {
    const ka = (a.date || '') + (a.time || '') + String(a.id || '').padStart(8, '0');
    const kb = (b.date || '') + (b.time || '') + String(b.id || '').padStart(8, '0');
    return kb.localeCompare(ka); // تاریخ و ساعت جدیدتر بالا
  });
  if (filter) {
    const q = filter.trim();
    list = list.filter(i => (i.customer || '').includes(q) || String(i.invoiceNo).includes(en(q)));
  }
  const y = currentYear();
  const colors = salesColorMap(y);
  let html = `
    <input id="invSearch" placeholder="جستجوی مشتری یا شماره..." value="${filter.replace(/"/g, '&quot;')}" />
    <button class="btn btn-primary btn-block" id="btnNewInv">+ حواله جدید</button>
    <div class="card" style="padding:0;margin-top:12px">`;
  if (!list.length) html += `<div class="empty">موردی نیست</div>`;
  let lastMonth = null;
  list.forEach(i => {
    const mk = monthKey(i.date);
    if (mk !== lastMonth) {
      lastMonth = mk;
      html += `<div class="month-sep">📅 ${monthTitle(mk)}</div>`;
    }
    const bg = colors[i.customer] || '#e2e8f0';
    const tAmt = amount(i.total);
    const pAmt = (i.paidAmount === '' || i.paidAmount == null) ? tAmt : amount(i.paidAmount);
    const remain = tAmt - pAmt;
    let remHtml = '';
    if (remain > 0) remHtml = `<span class="remain debt">مانده: ${fmt(remain)}</span>`;
    else if (remain < 0) remHtml = `<span class="remain cred">بستانکار: ${fmt(Math.abs(remain))}</span>`;
    else remHtml = `<span class="remain zero">مانده: ۰</span>`;
    html += `<div class="list-item" style="background:${bg}22;border-right:4px solid ${bg}">
      <div class="row between"><strong>${i.customer}</strong><span class="ltr" style="font-weight:700">${fmt(i.total)}</span></div>
      <div class="muted">ش ${fa(i.invoiceNo)} | ${fa(i.date)} ${fa(i.time || '')}</div>
      <div class="row between" style="margin-top:4px"><span class="muted">پرداختی: <span class="ltr">${fmt(pAmt)}</span></span>${remHtml}</div>
      <div class="actions">
        <button class="btn btn-primary btn-sm" data-inq="${i.id}" ${i.inquiryData ? '' : 'disabled style="opacity:0.4"'}>استعلام</button>
        <button class="btn btn-secondary btn-sm" data-edit="${i.id}">ویرایش</button>
        <button class="btn btn-danger btn-sm" data-del="${i.id}">حذف</button>
      </div>
    </div>`;
  });
  html += `</div>`;
  return html;
}


function openInvoiceInquiry(inv) {
  if (!inv || !inv.inquiryData) {
    alert('برای این حواله استعلام ذخیره‌شده‌ای وجود ندارد.');
    return;
  }
  let data;
  try {
    data = typeof inv.inquiryData === 'string' ? JSON.parse(inv.inquiryData) : inv.inquiryData;
  } catch(e) {
    alert('خواندن استعلام ممکن نشد.');
    return;
  }
  // پر کردن فرم استعلام و خروجی PDF
  inq.tab = data.tab || 'parquet';
  inq.buyer = data.buyer || inv.customer || '';
  inq.date = data.date || inv.date || '';
  inq.rows = (data.rows && data.rows.length) ? JSON.parse(JSON.stringify(data.rows)) : [emptyRow()];
  inq.warehouse = data.warehouse || '';
  inq.transport = data.transport || 'به عهده مشتری می‌باشد';
  inq.debt = data.debt || '0';
  inq.discount = data.discount || '0';
  inq.validity = data.validity || inq.validity;
  inq.shaba = data.shaba || inq.shaba;
  // فقط نمایش PDF — بدون ذخیره در لیست و بدون اشتراک اجباری
  openInquiryExport(false, { skipSave: true });
}

function openInvoiceModal(inv) {
  const isNew = !inv;
  const nj = nowJalali();
  inv = inv || { customer: '', invoiceNo: '', date: nj.date, time: nj.time, total: '', paidAmount: '' };
  if (isNew) {
    inv.date = inv.date || nj.date;
    inv.time = inv.time || nj.time;
  }
  const names = customerNames();
  const opts = names.map(n => `<option value="${esc(n)}" ${n === inv.customer ? 'selected' : ''}>${esc(n)}</option>`).join('');
  showModal(`
    <h3>${isNew ? 'حواله جدید' : 'ویرایش حواله'}</h3>
    <label>مشتری</label>
    <input id="mCust" list="mCustList" value="${esc(inv.customer)}" placeholder="نام یا انتخاب از لیست" />
    <datalist id="mCustList">${names.map(n => `<option value="${esc(n)}">`).join('')}</datalist>
    <div class="cust-scroll">${names.map(n => `<button type="button" class="cust-chip" data-pick="${esc(n)}">${esc(n)}</button>`).join('') || '<span class="muted">هنوز مشتری‌ای نیست</span>'}</div>
    <label>شماره حواله</label><input id="mNo" value="${esc(inv.invoiceNo)}" />
    <label>تاریخ شمسی</label><input id="mDate" value="${esc(inv.date)}" placeholder="1405/01/01" />
    <label>ساعت</label><input id="mTime" value="${esc(inv.time || nj.time)}" placeholder="14:30:00" />
    <label>مبلغ کل</label><input id="mTotal" value="${esc(inv.total)}" inputmode="numeric" />
    <label>مبلغ پرداختی</label><input id="mPaid" value="${esc(inv.paidAmount !== '' && inv.paidAmount != null ? inv.paidAmount : inv.total)}" inputmode="numeric" />
    <button class="btn btn-primary btn-block" id="mSave">ذخیره</button>
    <button class="btn btn-secondary btn-block" id="mClose">انصراف</button>
  `);
  document.getElementById('mClose').onclick = hideModal;
  document.querySelectorAll('[data-pick]').forEach(b => {
    b.onclick = () => { document.getElementById('mCust').value = b.dataset.pick; };
  });
  document.getElementById('mSave').onclick = () => {
    const customer = document.getElementById('mCust').value.trim();
    const invoiceNo = en(document.getElementById('mNo').value.trim());
    const date = en(document.getElementById('mDate').value.trim());
    const time = en(document.getElementById('mTime').value.trim()) || nowJalali().time;
    const total = String(amount(document.getElementById('mTotal').value));
    const paidAmount = String(amount(document.getElementById('mPaid').value));
    if (!customer || !invoiceNo) return alert('مشتری و شماره حواله لازم است');
    const now = new Date();
    if (isNew) {
      DB.invoices.push({
        id: DB.nextId++, customer, invoiceNo, date, time, total, paidAmount,
        createdAt: now.toISOString(), inquiryData: ''
      });
    } else {
      const x = DB.invoices.find(x => x.id === inv.id);
      if (x) Object.assign(x, { customer, invoiceNo, date, time, total, paidAmount });
    }
    save(DB);
    hideModal();
    go('invoices');
  };
}

/* ---------- CUSTOMERS ---------- */
function renderCustomers() {
  const y = currentYear();
  const names = customerNames();
  const rows = names.map(name => {
    const invs = DB.invoices.filter(i => i.customer === name);
    const total = invs.reduce((s, i) => s + amount(i.total), 0);
    const yearSales = invs.filter(i => (i.date || '').startsWith(y)).reduce((s, i) => s + amount(i.total), 0);
    const bal = customerBalance(name);
    return { name, count: invs.length, total, yearSales, last: invs.map(i => i.date).sort().reverse()[0] || '', bal };
  }).sort((a, b) => b.yearSales - a.yearSales);

  let html = `<div class="card"><div class="muted">مرتب‌شده بر اساس فروش سال ${fa(y)}</div></div>`;
  if (!rows.length) html += `<div class="empty">مشتری‌ای نیست</div>`;
  const colors = salesColorMap(y);
  rows.forEach(c => {
    let chip = `<span class="chip chip-ok">تسویه</span>`;
    if (c.bal > 0) chip = `<span class="chip chip-debt">بدهکار ${fmt(c.bal)}</span>`;
    if (c.bal < 0) chip = `<span class="chip chip-cred">طلبکار ${fmt(Math.abs(c.bal))}</span>`;
    const bg = colors[c.name] || '#e2e8f0';
    html += `<div class="card" style="background:linear-gradient(90deg, ${bg}33 0%, #fff 55%);border-right:5px solid ${bg}">
      <div class="row between"><strong>${c.name}</strong>${chip}</div>
      <div class="muted mt">حواله: ${fa(c.count)} | خرید: ${fmt(c.total)} | فروش ${fa(y)}: ${fmt(c.yearSales)}</div>
      <div class="muted">آخرین: ${fa(c.last)}</div>
      <div class="actions mt">
        <button class="btn btn-primary btn-sm" data-cust-purchases="${esc(c.name)}">خریدها / استعلام</button>
        <button class="btn btn-secondary btn-sm" data-bal="${esc(c.name)}">تنظیم مانده</button>
      </div>
    </div>`;
  });
  return html;
}

function openBalanceModal(name) {
  const cur = customerBalance(name);
  const type = cur > 0 ? 0 : cur < 0 ? 1 : 2;
  showModal(`
    <h3>تنظیم طلب / بدهی — ${name}</h3>
    <label><input type="radio" name="btype" value="0" ${type === 0 ? 'checked' : ''}/> بدهکار</label>
    <label><input type="radio" name="btype" value="1" ${type === 1 ? 'checked' : ''}/> طلبکار</label>
    <label><input type="radio" name="btype" value="2" ${type === 2 ? 'checked' : ''}/> تسویه</label>
    <label>مبلغ</label><input id="bAmt" value="${Math.abs(cur)}" inputmode="numeric" />
    <button class="btn btn-primary btn-block" id="bSave">ذخیره</button>
    <button class="btn btn-secondary btn-block" id="mClose">انصراف</button>
  `);
  document.getElementById('mClose').onclick = hideModal;
  document.getElementById('bSave').onclick = () => {
    const t = Number(document.querySelector('input[name=btype]:checked').value);
    const v = amount(document.getElementById('bAmt').value);
    const target = t === 0 ? v : t === 1 ? -v : 0;
    // base without adj
    let base = 0;
    DB.invoices.filter(i => i.customer === name).forEach(i => {
      const tot = amount(i.total);
      const p = (i.paidAmount === '' || i.paidAmount == null) ? tot : amount(i.paidAmount);
      base += tot - p;
    });
    DB.balances[name] = String(target - base);
    save(DB);
    hideModal();
    go('customers');
  };
}

/* ---------- REPORTS ---------- */
function renderReports() {
  const y = currentYear();
  const yearInput = y;
  const totals = Array(12).fill(0);
  DB.invoices.filter(i => (i.date || '').startsWith(y)).forEach(i => {
    const parts = (i.date || '').split('/');
    const m = parseInt(parts[1], 10);
    if (m >= 1 && m <= 12) totals[m - 1] += amount(i.total);
  });
  const sum = totals.reduce((a, b) => a + b, 0);
  const years = [...new Set(DB.invoices.map(i => (i.date || '').slice(0, 4)).filter(x => /^\d{4}$/.test(x)))].sort().reverse();
  if (!years.includes(y)) years.unshift(y);
  let html = `
    <label>سال</label>
    <div class="year-scroll" id="yearScroll">`;
  years.forEach(yy => {
    html += `<button type="button" class="year-chip ${yy === y ? 'active' : ''}" data-year="${yy}">${fa(yy)}</button>`;
  });
  html += `</div>
    <input id="repYear" value="${fa(yearInput)}" style="display:none" />
    <div class="stat"><div class="label">جمع کل سال ${fa(y)}</div><div class="value">${fmt(sum)} ریال</div></div>
    <div class="month-grid mt">`;
  MONTHS.forEach((name, i) => {
    html += `<div class="month-box" style="background:${MONTH_COLORS[i]}"><div class="m">${name}</div><div class="v">${fmt(totals[i])}</div></div>`;
  });
  html += `</div>`;
  html += `<div class="card mt"><h2>نمودار فروش</h2>${buildChartSvg(totals)}</div>`;
  return html;
}

/* ---------- INQUIRY ---------- */
let inq = {
  tab: 'parquet', buyer: '', date: '', rows: [emptyRow()],
  warehouse: '', transport: 'به عهده مشتری می‌باشد', debt: '0', discount: '0',
  validity: 'اعتبار این استعلام کالا از تاریخ صدور تا پایان وقت اداری همان روز می‌باشد',
  shaba: 'IR650120020000005081809111'
};
function emptyRow() {
  return { code: '', type: 'Isofam Luxury', grade: 'GA', size: '', qty1: '', qty2: '', price: '' };
}
function rowCost(r) {
  const q2 = parseFloat(clean(r.qty2)) || 0;
  return Math.round(q2 * amount(r.price));
}
function inqTotal() {
  const sub = inq.rows.reduce((s, r) => s + rowCost(r), 0);
  return sub + amount(inq.debt) - amount(inq.discount);
}

function renderInquiry() {
  if (!inq.date || !String(inq.date).trim()) inq.date = nowJalali().date;
  const bal = customerBalance(inq.buyer.trim());
  const boxClass = bal > 0 ? 'buyer-debt' : bal < 0 ? 'buyer-cred' : '';
  const balTxt = !inq.buyer.trim() ? '' :
    bal > 0 ? `بدهکار: ${fmt(bal)}` : bal < 0 ? `طلبکار: ${fmt(Math.abs(bal))}` : 'تسویه';
  const sub = inq.rows.reduce((s, r) => s + rowCost(r), 0);
  const total = inqTotal();
  const names = customerNames();

  let html = `
    <div class="tabs">
      <button class="tab ${inq.tab === 'parquet' ? 'active' : ''}" data-tab="parquet">پارکت</button>
      <button class="tab ${inq.tab === 'mdf' ? 'active' : ''}" data-tab="mdf">ام‌دی‌اف</button>
      <button class="tab ${inq.tab === 'raw' ? 'active' : ''}" data-tab="raw">خام</button>
    </div>
    <div class="card ${boxClass}">
      <h2>خریدار</h2>
      <div class="row between" style="margin-bottom:8px">
        <h2 style="margin:0">اطلاعات</h2>
        <button type="button" class="btn btn-secondary btn-sm" id="btnSavedInq">استعلام‌های ذخیره‌شده</button>
      </div>
      <label>نام</label>
      <input id="iqBuyer" list="custList" value="${esc(inq.buyer)}" placeholder="تایپ یا انتخاب از لیست" />
      <datalist id="custList">${names.map(n => `<option value="${esc(n)}">`).join('')}</datalist>
      <div class="cust-scroll" id="iqCustScroll">${names.map(n => {
        const b = customerBalance(n);
        const col = b > 0 ? '#dc2626' : b < 0 ? '#16a34a' : '#64748b';
        return `<button type="button" class="cust-chip" data-iqpick="${esc(n)}" style="border-color:${col};color:${col}">${esc(n)}</button>`;
      }).join('') || '<span class="muted">مشتری ثبت‌شده نیست</span>'}</div>
      ${balTxt ? `<div class="muted" style="font-weight:700;margin-bottom:8px">${balTxt}</div>` : ''}
      <label>تاریخ</label>
      <input id="iqDate" value="${esc(inq.date || nowJalali().date)}" placeholder="1405/01/01" />
    </div>`;

  inq.rows.forEach((r, idx) => {
    html += `<div class="card"><div class="row between"><strong>ردیف ${fa(idx + 1)}</strong>
      ${inq.rows.length > 1 ? `<button class="btn btn-danger btn-sm" data-rmrow="${idx}">حذف</button>` : ''}</div>`;
    if (inq.tab === 'parquet') {
      const to = typeOptionsHtml(r.type, r.code);
      const typeLocked = to.locked ? 'disabled' : '';
      const egWarn = productFromCode(r.code) === 'Egmont' && r.type !== 'Egmont' && r.type !== 'N Egmont'
        ? '<div class="muted" style="color:#b45309;font-weight:700">نوع Egmont را انتخاب کنید (قدیم ۱٫۸۶۹۶ / جدید ۱٫۹۶۰۸)</div>' : '';
      html += `
        <label>کد کالا</label><input data-r="${idx}" data-f="code" value="${esc(r.code)}" />
        <label>نوع</label><select data-r="${idx}" data-f="type" ${typeLocked}>${to.html}</select>
        ${egWarn}
        <label>گرید</label><input data-r="${idx}" data-f="grade" value="${esc(r.grade)}" />
        <label>کارتن</label><input data-r="${idx}" data-f="qty1" value="${esc(r.qty1)}" inputmode="decimal" />
        <label>متراژ</label><input data-r="${idx}" data-f="qty2" value="${esc(r.qty2)}" readonly />
        <label>قیمت واحد</label><input data-r="${idx}" data-f="price" value="${esc(r.price)}" inputmode="numeric" />`;
    } else if (inq.tab === 'mdf') {
      html += `
        <label>نوع</label><input data-r="${idx}" data-f="type" value="${esc(r.type)}" />
        <label>کد</label><input data-r="${idx}" data-f="code" value="${esc(r.code)}" />
        <label>پالت</label><input data-r="${idx}" data-f="qty1" value="${esc(r.qty1)}" />
        <label>ورق</label><input data-r="${idx}" data-f="qty2" value="${esc(r.qty2)}" />
        <label>قیمت واحد</label><input data-r="${idx}" data-f="price" value="${esc(r.price)}" inputmode="numeric" />`;
    } else {
      html += `
        <label>نوع</label><input data-r="${idx}" data-f="type" value="${esc(r.type)}" />
        <label>سایز</label><input data-r="${idx}" data-f="size" value="${esc(r.size)}" />
        <label>پالت</label><input data-r="${idx}" data-f="qty1" value="${esc(r.qty1)}" />
        <label>ورق</label><input data-r="${idx}" data-f="qty2" value="${esc(r.qty2)}" />
        <label>قیمت واحد</label><input data-r="${idx}" data-f="price" value="${esc(r.price)}" inputmode="numeric" />`;
    }
    html += `<div class="muted">هزینه: <strong style="color:#0284c7">${fmt(rowCost(r))}</strong></div></div>`;
  });

  html += `
    <button class="btn btn-secondary btn-block" id="addRow">+ افزودن ردیف</button>
    <div class="card">
      <label>انبارداری</label><input id="iqWh" value="${esc(inq.warehouse)}" />
      <label>حمل</label><input id="iqTr" value="${esc(inq.transport)}" />
      <label>بدهی پیشین</label><input id="iqDebt" value="${esc(inq.debt)}" inputmode="numeric" />
      <label>تخفیف</label><input id="iqDisc" value="${esc(inq.discount)}" inputmode="numeric" />
      <label>اعتبار</label><input id="iqVal" value="${esc(inq.validity)}" />
      <label>شماره شبا</label><input id="iqShaba" value="${esc(inq.shaba || 'IR650120020000005081809111')}" class="ltr" />
    </div>
    <div class="stat">
      <div class="label">جمع اقلام ${fmt(sub)} — جمع کل</div>
      <div class="value">${fmt(total)} ریال</div>
      <div style="margin-top:6px;opacity:.9;font-size:13px">${words(total)} ریال</div>
    </div>
    <button class="btn btn-primary btn-block" id="iqPdf">📄 خروجی PDF</button>
    <button class="btn btn-primary btn-block" id="iqImg">🖼 خروجی تصویر</button>
    <button class="btn btn-secondary btn-block" id="iqSave">ذخیره استعلام</button>
    <button class="btn btn-green btn-block" id="iqFinal">✓ تایید نهایی و ثبت حواله</button>
  `;
  return html;
}

function syncInqFromDom() {
  const b = document.getElementById('iqBuyer');
  if (!b) return;
  inq.buyer = b.value;
  inq.date = document.getElementById('iqDate').value;
  inq.warehouse = document.getElementById('iqWh').value;
  inq.transport = document.getElementById('iqTr').value;
  inq.debt = document.getElementById('iqDebt').value;
  inq.discount = document.getElementById('iqDisc').value;
  inq.validity = document.getElementById('iqVal').value;
  const sh = document.getElementById('iqShaba');
  if (sh) inq.shaba = sh.value;
  document.querySelectorAll('[data-r]').forEach(el => {
    const i = +el.dataset.r, f = el.dataset.f;
    if (!inq.rows[i]) return;
    inq.rows[i][f] = el.value;
    if (inq.tab === 'parquet' && (f === 'qty1' || f === 'type')) {
      const factor = PRODUCT_FACTORS[inq.rows[i].type] || 1.96;
      const cartons = parseFloat(clean(inq.rows[i].qty1)) || 0;
      inq.rows[i].qty2 = cartons ? (cartons * factor).toFixed(4).replace(/\.?0+$/, '') : '';
    }
  });
}


function openInquiryExport(asImage, opts) {
  opts = opts || {};
  const total = inqTotal();
  const sub = inq.rows.reduce((s, r) => s + rowCost(r), 0);
  const buyer = inq.buyer || '—';
  const date = fa(inq.date || '—');
  const tab = inq.tab || 'parquet';
  const tabName = tab === 'parquet' ? 'پارکت' : tab === 'mdf' ? 'ام‌دی‌اف' : 'ام‌دی‌اف خام';
  const warehouse = inq.warehouse || '—';
  const transport = inq.transport || 'به عهده مشتری می‌باشد';
  const debt = amount(inq.debt);
  const disc = amount(inq.discount);
  const validity = inq.validity || '';
  const shaba = inq.shaba || '';
  const debtDisp = debt ? fmt(debt) : '۰';
  const discDisp = disc ? fmt(disc) : '۰';
  const shabaHtml = shaba
    ? '<div style="margin-top:10px;padding-top:10px;border-top:1px dashed #cbd5e1;font-size:12px;"><b>شبا:</b> <span style="direction:ltr;display:inline-block">' + esc(shaba) + '</span></div>'
    : '';
  let headers = [];
  if (tab === 'parquet') headers = ['ردیف','کد کالا','نوع کالا','گرید','مقدار (کارتن)','مقدار (متراژ)','قیمت واحد (ریال)','هزینه کالا (ریال)'];
  else if (tab === 'mdf') headers = ['ردیف','نوع کالا','کد','مقدار (پالت)','مقدار (ورق)','قیمت واحد (ریال)','هزینه کالا (ریال)'];
  else headers = ['ردیف','نوع کالا','سایز','مقدار (پالت)','مقدار (ورق)','قیمت واحد (ریال)','هزینه کالا (ریال)'];
  const headersHtml = headers.map(h => '<th style="padding:8px 5px;background:#0284c7;color:white;font-weight:600;font-size:11px;text-align:center;border:none;">' + h + '</th>').join('');
  let rowsHtml = '';
  inq.rows.forEach((r, idx) => {
    const cost = rowCost(r);
    let cells = [];
    if (tab === 'parquet') {
      cells = [fa(idx + 1), esc(r.code || '—'), esc(r.type || ''), esc(r.grade || ''), fa(r.qty1 || '—'), fa(r.qty2 || '—'), fmt(amount(r.price)), fmt(cost)];
    } else if (tab === 'mdf') {
      cells = [fa(idx + 1), esc(r.type || ''), esc(r.code || '—'), fa(r.qty1 || '—'), fa(r.qty2 || '—'), fmt(amount(r.price)), fmt(cost)];
    } else {
      cells = [fa(idx + 1), esc(r.type || ''), esc(r.size || ''), fa(r.qty1 || '—'), fa(r.qty2 || '—'), fmt(amount(r.price)), fmt(cost)];
    }
    const bg = idx % 2 ? '#f8fafc' : '#fff';
    rowsHtml += '<tr style="background:' + bg + '">' + cells.map(c => '<td style="padding:7px 5px;text-align:center;font-size:12px;border-bottom:1px solid #e2e8f0;">' + c + '</td>').join('') + '</tr>';
  });

  const inner = `
<div id="estelamShareRoot" style="width:800px;max-width:100%;margin:0 auto;background:#fff;font-family:Tahoma,Vazirmatn,sans-serif;direction:rtl;color:#0f172a;">
  <div style="background:#0284c7;color:white;padding:14px 18px;border-radius:14px 14px 0 0;">
    <div style="font-size:18px;font-weight:800;">استعلام کالا — ${tabName}</div>
    <div style="font-size:12px;opacity:.9;margin-top:4px;">${esc(DB.company || 'SalesMate')}</div>
  </div>
  <div style="display:flex;gap:10px;padding:12px 0;">
    <div style="flex:1;background:#0284c7;border-radius:12px;padding:14px 16px;color:white;">
      <div style="font-size:11px;opacity:.85;">خریدار</div>
      <div style="font-size:16px;font-weight:800;margin-top:4px;">${esc(buyer)}</div>
    </div>
    <div style="flex:0.7;background:#0284c7;border-radius:12px;padding:14px 16px;color:white;">
      <div style="font-size:11px;opacity:.85;">تاریخ</div>
      <div style="font-size:16px;font-weight:800;margin-top:4px;direction:ltr;text-align:right;">${date}</div>
    </div>
  </div>
  <table style="width:100%;border-collapse:collapse;margin-bottom:12px;">
    <thead><tr>${headersHtml}</tr></thead>
    <tbody>${rowsHtml}</tbody>
  </table>
  <div style="background:#f8fafc;border-radius:12px;padding:10px 14px;border:1px solid #e2e8f0;margin-bottom:12px;font-size:12px;">
    <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>مبلغ کل اقلام</span><span style="direction:ltr;font-weight:700;">${fmt(sub)}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>انبارداری</span><span>${esc(warehouse)}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>حمل</span><span>${esc(transport)}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>بدهی پیشین</span><span style="direction:ltr;">${debtDisp}</span></div>
    <div style="display:flex;justify-content:space-between;padding:4px 0;"><span>تخفیف</span><span style="direction:ltr;">${discDisp}</span></div>
  </div>
  <div style="background:#0284c7;border-radius:14px;padding:14px 18px;color:white;margin-bottom:12px;">
    <div style="font-size:13px;opacity:0.8;margin-bottom:6px;">جمع کل قابل پرداخت</div>
    <div style="font-size:24px;font-weight:900;direction:ltr;text-align:left;">${fmt(total)} <span style="font-size:15px;font-weight:500;">ریال</span></div>
    <div style="font-size:14px;margin-top:8px;opacity:0.9;">${words(total)} ریال</div>
  </div>
  <div style="background:#f8fafc;border-radius:12px;padding:16px 18px;border:1px solid #e2e8f0;font-size:11px;color:#475569;line-height:1.6;">
    <div style="font-weight:600;color:#0284c7;margin-bottom:8px;font-size:14px;">شرایط و نکات مهم</div>
    <p style="margin:4px 0;">• پس از واریز مبلغ به حساب شرکت و تأیید واحد حسابداری، حواله خروج بار صادر می‌گردد.</p>
    <p style="margin:4px 0;">• پس از خروج کالا از انبار شرکت هیچ مسئولیتی از لحاظ کمیت و کیفیت/سلامت کالا ندارد.</p>
    <p style="margin:4px 0;">• پس از فروش کالا به هیچ عنوان مرجوعی و ابطال حواله انجام نمی‌شود.</p>
    <p style="margin:10px 0 4px;font-weight:500;color:#1e293b;">${esc(validity)}</p>
    ${shabaHtml}
  </div>
</div>`;

  // فقط وقتی از فرم استعلام خروجی می‌گیریم ذخیره شود — نه از دکمه استعلام حواله
  if (!opts.skipSave) {
    try { saveInquirySmart(JSON.parse(JSON.stringify(inq)), total); } catch (e) {}
  }

  showInquiryPreview(inner, asImage, buyer, total).catch(function (err) {
    console.error(err);
    alert('نمایش خروجی انجام نشد: ' + (err && err.message ? err.message : err));
  });
}

function loadScriptOnce(src) {
  return new Promise(function (resolve, reject) {
    if (document.querySelector('script[data-src="' + src + '"]')) {
      resolve();
      return;
    }
    var s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.setAttribute('data-src', src);
    s.onload = function () { resolve(); };
    s.onerror = function () { reject(new Error('بارگذاری کتابخانه ناموفق: ' + src)); };
    document.head.appendChild(s);
  });
}

async function renderInquiryToFile(innerHtml, asImage, buyer) {
  var host = document.getElementById('estelamRenderHost');
  if (!host) {
    host = document.createElement('div');
    host.id = 'estelamRenderHost';
    document.body.appendChild(host);
  }
  host.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'width:800px', 'max-width:100vw',
    'background:#ffffff', 'z-index:2147483646', 'opacity:0.01',
    'pointer-events:none', 'overflow:visible', 'padding:0', 'margin:0'
  ].join(';');
  host.innerHTML = innerHtml;
  var root = host.querySelector('#estelamShareRoot') || host.firstElementChild;
  if (!root) throw new Error('محتوای استعلام ساخته نشد');

  await new Promise(function (r) { requestAnimationFrame(function () { requestAnimationFrame(r); }); });
  try { if (document.fonts && document.fonts.ready) await document.fonts.ready; } catch (e) {}

  await loadScriptOnce('https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js');
  if (!window.html2canvas) throw new Error('html2canvas لود نشد — اینترنت را چک کنید');
  if (!asImage) {
    await loadScriptOnce('https://cdn.jsdelivr.net/npm/jspdf@2.5.1/dist/jspdf.umd.min.js');
  }

  var canvas;
  try {
    canvas = await window.html2canvas(root, {
      scale: 2, useCORS: true, allowTaint: true, backgroundColor: '#ffffff',
      logging: false, foreignObjectRendering: false, removeContainer: true,
      windowWidth: Math.max(root.scrollWidth, 800),
      windowHeight: Math.max(root.scrollHeight, 600),
      scrollX: 0, scrollY: 0, x: 0, y: 0
    });
  } catch (e1) {
    canvas = await window.html2canvas(root, {
      scale: 1.5, backgroundColor: '#ffffff', logging: false,
      foreignObjectRendering: false, useCORS: true
    });
  }
  host.style.left = '-9999px';
  host.style.opacity = '0';
  host.innerHTML = '';
  if (!canvas || !canvas.width) throw new Error('رندر تصویر ناموفق بود');

  var safeName = String(buyer || 'estelam').replace(/[^\w\u0600-\u06FF\-]+/g, '_').slice(0, 40);
  var fileName, file, previewUrl, fileUrl;

  // همیشه پیش‌نمایش بصری از تصویر (روی موبایل iframe PDF اغلب سیاه می‌شود)
  var previewBlob = await new Promise(function (res) { canvas.toBlob(res, 'image/jpeg', 0.92); });
  if (!previewBlob) throw new Error('ساخت پیش‌نمایش ناموفق بود');
  previewUrl = URL.createObjectURL(previewBlob);

  if (asImage) {
    fileName = 'estelam_' + safeName + '.png';
    var blob = await new Promise(function (res) { canvas.toBlob(res, 'image/png'); });
    if (!blob) throw new Error('ساخت تصویر ناموفق بود');
    file = new File([blob], fileName, { type: 'image/png' });
    fileUrl = URL.createObjectURL(blob);
  } else {
    fileName = 'estelam_' + safeName + '.pdf';
    var jsPDF = (window.jspdf && window.jspdf.jsPDF) ? window.jspdf.jsPDF : window.jsPDF;
    if (!jsPDF) throw new Error('کتابخانه PDF لود نشد — اینترنت را چک کنید');
    var pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    var pageW = pdf.internal.pageSize.getWidth();
    var pageH = pdf.internal.pageSize.getHeight();
    var imgW = pageW - 10;
    var imgH = canvas.height * imgW / canvas.width;
    var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
    if (imgH <= pageH - 10) {
      pdf.addImage(dataUrl, 'JPEG', 5, 5, imgW, imgH);
    } else {
      var s = imgW / canvas.width;
      var pageCanvasH = (pageH - 10) / s;
      var offset = 0;
      var first = true;
      while (offset < canvas.height) {
        if (!first) pdf.addPage();
        first = false;
        var slice = document.createElement('canvas');
        slice.width = canvas.width;
        slice.height = Math.min(Math.ceil(pageCanvasH), canvas.height - offset);
        var ctx = slice.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, slice.width, slice.height);
        ctx.drawImage(canvas, 0, offset, slice.width, slice.height, 0, 0, slice.width, slice.height);
        pdf.addImage(slice.toDataURL('image/jpeg', 0.92), 'JPEG', 5, 5, imgW, slice.height * s);
        offset += pageCanvasH;
      }
    }
    var pdfBlob = pdf.output('blob');
    file = new File([pdfBlob], fileName, { type: 'application/pdf' });
    fileUrl = URL.createObjectURL(pdfBlob);
  }
  return { file: file, fileName: fileName, previewUrl: previewUrl, fileUrl: fileUrl, asImage: asImage };
}

async function showInquiryPreview(innerHtml, asImage, buyer, total, opts) {
  opts = opts || {};
  showModal('<h3>در حال آماده‌سازی خروجی...</h3><div class="muted">لطفاً صبر کنید</div>');
  var result;
  try {
    result = await renderInquiryToFile(innerHtml, asImage, buyer);
  } catch (e) {
    hideModal();
    throw e;
  }

  // همیشه تصویر نشان بده (موبایل iframe PDF را درست نشان نمی‌دهد)
  var kind = result.asImage ? 'تصویر' : 'PDF';
  var previewBlock = '<img src="' + result.previewUrl + '" alt="preview" style="width:100%;border-radius:12px;border:1px solid #e2e8f0;background:#fff;display:block;" />';

  showModal(
    '<h3>پیش‌نمایش ' + (buyer === 'راس چک' ? 'راس چک‌ها' : 'استعلام') + ' (' + kind + ')</h3>' +
    '<div class="muted" style="margin-bottom:8px;">' + esc(buyer || '') + ' — ' + fmt(total) + ' ریال</div>' +
    '<div style="max-height:55vh;overflow:auto;margin-bottom:12px;background:#f8fafc;border-radius:12px;padding:6px;">' + previewBlock + '</div>' +
    '<button class="btn btn-primary btn-block" id="prevDownload">⬇ ذخیره / دانلود ' + kind + '</button>' +
    '<button class="btn btn-green btn-block" id="prevShare">📤 ارسال به پیام‌رسان</button>' +
    '<button class="btn btn-secondary btn-block" id="prevClose">بستن</button>'
  );

  var cleaned = false;
  function cleanup() {
    if (cleaned) return;
    cleaned = true;
    try { URL.revokeObjectURL(result.previewUrl); } catch (e) {}
    try { if (result.fileUrl) URL.revokeObjectURL(result.fileUrl); } catch (e) {}
  }

  document.getElementById('prevClose').onclick = function () {
    cleanup();
    hideModal();
  };
  document.getElementById('prevDownload').onclick = function () {
    var a = document.createElement('a');
    a.href = result.fileUrl || result.previewUrl;
    a.download = result.fileName;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };
  document.getElementById('prevShare').onclick = async function () {
    try {
      var shareTitle = (opts && opts.shareTitle) || ('استعلام ' + (buyer || ''));
      var shareText = (opts && opts.shareText) || ('استعلام کالا — جمع کل: ' + fmt(total) + ' ریال');
      if (buyer === 'راس چک') {
        shareTitle = (opts && opts.shareTitle) || 'راس چک‌ها';
        shareText = (opts && opts.shareText) || ('راس چک‌ها — مبلغ کل: ' + fmt(total) + ' ریال');
      }
      var shareData = {
        files: [result.file],
        title: shareTitle,
        text: shareText
      };
      if (navigator.share && navigator.canShare && navigator.canShare({ files: [result.file] })) {
        await navigator.share(shareData);
        return;
      }
      if (navigator.share) {
        await navigator.share(shareData);
        return;
      }
      alert('اشتراک در این مرورگر پشتیبانی نمی‌شود؛ از دکمه ذخیره استفاده کنید.');
    } catch (e) {
      if (e && e.name === 'AbortError') return;
      alert('ارسال انجام نشد: ' + (e && e.message ? e.message : e));
    }
  };
}


function inquiryFingerprint(item) {
  const key = {
    tab: item.tab,
    buyer: (item.buyer || '').trim(),
    date: en(String(item.date || '')).trim(),
    warehouse: item.warehouse || '',
    transport: item.transport || '',
    debt: String(item.debt || '0'),
    discount: String(item.discount || '0'),
    validity: item.validity || '',
    shaba: item.shaba || '',
    total: item.total,
    rows: item.rows || []
  };
  return JSON.stringify(key);
}

function saveInquirySmart(snapshot, total) {
  DB.inquiries = DB.inquiries || [];
  const data = { ...snapshot, total: total, savedAt: new Date().toISOString() };
  const fp = inquiryFingerprint(data);
  const exist = DB.inquiries.find(x => inquiryFingerprint(x) === fp);
  if (exist) {
    // بدون تغییر → تکراری نساز
    return false;
  }
  data.id = Date.now();
  DB.inquiries.unshift(data);
  DB.inquiries = DB.inquiries.slice(0, 50);
  save(DB);
  try { if (typeof scheduleCloudPush === 'function') scheduleCloudPush(400, true); } catch (e) {}
  return true;
}

function openCustomerPurchases(name) {
  const invs = DB.invoices.filter(i => i.customer === name)
    .slice()
    .sort((a, b) => {
      const ka = (a.date || '') + (a.time || '') + String(a.id).padStart(8,'0');
      const kb = (b.date || '') + (b.time || '') + String(b.id).padStart(8,'0');
      return kb.localeCompare(ka);
    });
  let body = '';
  if (!invs.length) body = '<div class="empty">خریدی ثبت نشده</div>';
  else {
    invs.forEach(i => {
      let products = '';
      try {
        if (i.inquiryData) {
          const d = typeof i.inquiryData === 'string' ? JSON.parse(i.inquiryData) : i.inquiryData;
          const rows = (d && d.rows) || [];
          if (rows.length) {
            const tab = (d && d.tab) || 'parquet';
            products = '<div style="margin-top:6px;font-size:12px;line-height:1.75">' + rows.map((r, idx) => {
              const bits = [fa(idx + 1) + ')'];
              if (tab === 'parquet') {
                bits.push('کد ' + fa(r.code || '—'));
                if (r.type) bits.push(r.type);
                if (r.grade) bits.push(r.grade);
                if (r.qty1) bits.push(fa(r.qty1) + ' کارتن');
                if (r.qty2) bits.push(fa(r.qty2) + ' متر');
              } else if (tab === 'mdf') {
                if (r.code) bits.push('کد ' + fa(r.code));
                if (r.type) bits.push(r.type);
                if (r.qty1) bits.push(fa(r.qty1) + ' پالت');
                if (r.qty2) bits.push(fa(r.qty2) + ' ورق');
              } else {
                if (r.type) bits.push(r.type);
                if (r.size) bits.push(r.size);
                if (r.qty1) bits.push(fa(r.qty1) + ' پالت');
                if (r.qty2) bits.push(fa(r.qty2) + ' ورق');
              }
              if (r.price) bits.push('فی ' + fmt(r.price));
              if (r.cost) bits.push('<b style="color:#0284c7">' + fmt(r.cost) + '</b>');
              return bits.join(' · ');
            }).join('<br>') + '</div>';
          }
        }
      } catch(e) {}
      body += `<div class="list-item">
        <div class="row between"><strong>ش ${fa(i.invoiceNo || '—')}</strong><span class="ltr" style="font-weight:700;color:#0284c7">${fmt(i.total)}</span></div>
        <div class="muted">${fa(i.date || '')} ${fa(i.time || '')}</div>
        ${products || '<div class="muted" style="margin-top:4px">جزئیات کالا ثبت نشده</div>'}
      </div>`;
    });
  }
  showModal(`<h3>خریدهای ${esc(name)}</h3><div style="max-height:55vh;overflow:auto">${body}</div>
    <button class="btn btn-secondary btn-block" id="mClose">بستن</button>`);
  document.getElementById('mClose').onclick = hideModal;
}

function showSavedInquiries() {
  const list = DB.inquiries || [];
  let body = '';
  if (!list.length) body = '<div class="empty">استعلام ذخیره‌شده‌ای نیست</div>';
  else {
    list.forEach((item, idx) => {
      const tab = item.tab === 'parquet' ? 'پارکت' : item.tab === 'mdf' ? 'ام‌دی‌اف' : 'خام';
      body += `<div class="list-item">
        <div class="row between"><strong>${esc(item.buyer || '—')}</strong><span class="ltr" style="color:#0284c7;font-weight:700">${fmt(item.total || 0)}</span></div>
        <div class="muted">${tab} • ${fa(item.date || '—')} • ${esc(item.savedAt || '')}</div>
        <div class="actions">
          <button class="btn btn-primary btn-sm" data-loadinq="${idx}">بارگذاری</button>
          <button class="btn btn-danger btn-sm" data-delinq="${idx}">حذف</button>
        </div>
      </div>`;
    });
  }
  showModal(`<h3>استعلام‌های ذخیره‌شده</h3><div style="max-height:55vh;overflow:auto">${body}</div>
    <button class="btn btn-secondary btn-block" id="mClose">بستن</button>`);
  document.getElementById('mClose').onclick = hideModal;
  document.querySelectorAll('[data-loadinq]').forEach(b => {
    b.onclick = () => {
      const item = (DB.inquiries || [])[+b.dataset.loadinq];
      if (!item) return;
      inq.tab = item.tab || 'parquet';
      inq.buyer = item.buyer || '';
      inq.date = item.date || '';
      inq.rows = (item.rows && item.rows.length) ? JSON.parse(JSON.stringify(item.rows)) : [emptyRow()];
      inq.warehouse = item.warehouse || '';
      inq.transport = item.transport || 'به عهده مشتری می‌باشد';
      inq.debt = item.debt || '0';
      inq.discount = item.discount || '0';
      inq.validity = item.validity || inq.validity;
      inq.shaba = item.shaba || inq.shaba;
      hideModal();
      go('inquiry');
    };
  });
  document.querySelectorAll('[data-delinq]').forEach(b => {
    b.onclick = () => {
      if (!confirm('حذف شود؟\nاز ابر و بقیه دستگاه‌ها هم حذف می‌شود.')) return;
      var idx = +b.dataset.delinq;
      var removed = (DB.inquiries || [])[idx];
      DB.inquiries.splice(idx, 1);
      save(DB);
      if (removed) {
        deleteInquiryFromCloud(removed).then(function () {
          try { pushToSupabase(); } catch (e) {}
        }).catch(function () {});
      }
      showSavedInquiries();
    };
  });
}

function openFinalize() {
  syncInqFromDom();
  const total = inqTotal();
  if (!inq.buyer.trim() || total <= 0) return alert('نام خریدار و مبلغ را کامل کنید');
  showModal(`
    <h3>تایید نهایی</h3>
    <label>شماره حواله</label><input id="fNo" />
    <label>نام مشتری</label><input id="fCust" value="${esc(inq.buyer)}" />
    <label>تاریخ</label><input id="fDate" value="${esc(inq.date)}" />
    <div class="muted">مبلغ کل: <strong>${fmt(total)}</strong></div>
    <label>مبلغ پرداختی</label><input id="fPaid" value="${total}" inputmode="numeric" />
    <button class="btn btn-green btn-block" id="fSave">ثبت حواله</button>
    <button class="btn btn-secondary btn-block" id="mClose">انصراف</button>
  `);
  document.getElementById('mClose').onclick = hideModal;
  document.getElementById('fSave').onclick = () => {
    const invoiceNo = en(document.getElementById('fNo').value.trim());
    const customer = document.getElementById('fCust').value.trim();
    const date = en(document.getElementById('fDate').value.trim());
    const paid = amount(document.getElementById('fPaid').value);
    if (!invoiceNo || !customer) return alert('شماره حواله و مشتری لازم است');
    const time = new Date().toTimeString().slice(0, 8);
    DB.invoices.push({
      id: DB.nextId++,
      customer, invoiceNo, date, time,
      total: String(total), paidAmount: String(paid),
      createdAt: new Date().toISOString(),
      inquiryData: JSON.stringify(inq)
    });
    save(DB);
    hideModal();
    alert('حواله ثبت شد');
    go('invoices');
  };
}

/* ---------- SETTINGS ---------- */
function renderSettings() {
  return `
    <div class="card">
      <h2>نام برنامه</h2>
      <label>نام شرکت</label>
      <input id="setCompany" value="${esc(DB.company || 'SalesMate')}" />
      <button class="btn btn-primary btn-block" id="setSave">ذخیره</button>
    </div>
    <div class="card">
      <h2>پشتیبان ابری</h2>
      <p class="muted" style="font-size:12px;line-height:1.7">با همان ایمیل ویندوز وارد شوید. داده هر حساب جدا است.</p>
      <div id="sbStatus" class="muted" style="margin-bottom:8px;padding:8px;background:#f0f9ff;border-radius:10px;font-size:12px"></div>
      <label>ایمیل</label>
      <input id="sbEmail" type="email" placeholder="email@example.com" autocomplete="username" />
      <label>رمز عبور</label>
      <input id="sbPass" type="password" placeholder="حداقل ۶ کاراکتر" autocomplete="current-password" />
      <button class="btn btn-primary btn-block" id="btnSbLogin">ورود</button>
      <button class="btn btn-secondary btn-block" id="btnSbSignup">ثبت‌نام</button>
      <button class="btn btn-secondary btn-block" id="btnSbLogout">خروج از حساب</button>
      <label style="display:flex;align-items:center;gap:8px;margin:10px 0;font-size:13px">
        <input type="checkbox" id="chkBackupClose" style="width:auto;margin:0" />
        پشتیبان خودکار هنگام بستن صفحه
      </label>
      <button type="button" class="btn btn-secondary btn-block" id="btnRestoreLocal">بازیابی بک‌آپ محلی</button>
      <button type="button" id="btnSbPull">⬇ دریافت از ابر</button>
      <button class="btn btn-secondary btn-block" id="btnSbPush">⬆ ارسال به ابر</button>
    </div>
    <div class="card">
      <h2>پشتیبان فایل</h2>
      <button class="btn btn-primary btn-block" id="btnExport">⬆ ذخیره فایل همگام</button>
      <button class="btn btn-secondary btn-block" id="btnImport">⬇ دریافت فایل همگام</button>
      <input type="file" id="importFile" accept="application/json,.json" hidden />
    </div>
    <div class="card">
      <button class="btn btn-danger btn-block" id="btnClear">پاک کردن کل اطلاعات</button>
    </div>
    <p class="muted" style="text-align:center">SalesMate موبایل‌وب v1.20</p>
  `;
}

/* ---------- helpers ---------- */
function esc(s) {
  return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function showModal(html) {
  const m = document.getElementById('modal');
  m.innerHTML = `<div class="modal-sheet">${html}</div>`;
  m.classList.remove('hidden');
}
function hideModal() {
  document.getElementById('modal').classList.add('hidden');
  document.getElementById('modal').innerHTML = '';
}


/* ---------- STORE (فروشگاه) ---------- */
let storeForm = {
  tab: 'parquet', buyer: '', invoiceNo: '', date: '',
  rows: [{ code:'', type:'Isofam Luxury', grade:'GA', qty1:'', qty2:'', price:'', cost:0 }],
  editingId: null
};

function storeEmptyRow() {
  return { code:'', type:'Isofam Luxury', grade:'GA', qty1:'', qty2:'', size:'', price:'', cost:0 };
}

function storeItemsMeterage(items) {
  let t = 0;
  (items || []).forEach(it => {
    const v = parseFloat(en(String(it.qty2 || '')).replace(/,/g, '')) || 0;
    t += v;
  });
  return t;
}

function storeFmtMeter(m) {
  if (!m) return fa('0');
  const s = String(Number(m).toFixed(4)).replace(/\.?0+$/, '');
  return fa(s);
}

function storeWeekKey(dateStr) {
  const p = en(String(dateStr || '')).split('/');
  if (p.length < 3) return [0, 0];
  const y = parseInt(p[0], 10), m = parseInt(p[1], 10), d = parseInt(p[2], 10);
  if (!y || !m || !d) return [0, 0];
  let days = (m - 1) * 31;
  if (m > 6) days = 6 * 31 + (m - 7) * 30;
  days += d;
  return [y, Math.floor((days - 1) / 7)];
}

function storeRecalcRows() {
  (storeForm.rows || []).forEach(r => {
    if (storeForm.tab === 'parquet') {
      const c = parseFloat(en(String(r.qty1 || ''))) || 0;
      const factor = PRODUCT_FACTORS[r.type] || 1.9608;
      r.qty2 = c ? String(+(c * factor).toFixed(4)) : '';
    }
    const q2 = parseFloat(en(String(r.qty2 || '')).replace(/,/g, '')) || 0;
    const pr = amount(r.price);
    r.cost = Math.round(q2 * pr);
  });
}

function storeTotal() {
  storeRecalcRows();
  return (storeForm.rows || []).reduce((s, r) => s + (r.cost || 0), 0);
}

function renderStore() {
  if (!DB.storeSales) DB.storeSales = [];
  const nj = nowJalali();
  if (!storeForm.date) storeForm.date = nj.date;
  storeRecalcRows();
  const total = storeTotal();

  // week/month stats
  const cy = parseInt(en(nj.date).split('/')[0], 10);
  const cm = parseInt(en(nj.date).split('/')[1], 10);
  const cd = parseInt(en(nj.date).split('/')[2], 10);
  const curWeek = storeWeekKey(nj.date);
  let weekSum = 0, monthSum = 0, weekM = 0, monthM = 0;
  const monthTotals = Array(12).fill(0);
  (DB.storeSales || []).forEach(s => {
    const tot = amount(s.total);
    const meters = storeItemsMeterage(storeParseItems(s));
    const parts = en(String(s.date || '')).split('/');
    const y = parseInt(parts[0], 10), m = parseInt(parts[1], 10);
    if (y === cy && m === cm) { monthSum += tot; monthM += meters; }
    if (JSON.stringify(storeWeekKey(s.date)) === JSON.stringify(curWeek)) {
      weekSum += tot; weekM += meters;
    }
    if (y === cy && m >= 1 && m <= 12) monthTotals[m - 1] += tot;
  });

  let html = `
    <div class="stat"><div class="label">فروش هفته</div><div class="value">${fmt(weekSum)} ریال</div></div>
    <div class="stat stat-month" style="margin-top:8px;background:#0ea5e9"><div class="label">متراژ هفته</div><div class="value">${storeFmtMeter(weekM)} متر</div></div>
    <div class="stat" style="margin-top:8px"><div class="label">فروش ماه</div><div class="value">${fmt(monthSum)} ریال</div></div>
    <div class="stat stat-month" style="margin-top:8px;background:#10b981"><div class="label">متراژ ماه</div><div class="value">${storeFmtMeter(monthM)} متر</div></div>

    <div class="card" style="margin-top:12px">
      <h2>ثبت فروش فروشگاه</h2>
      <div class="tabs">
        <button type="button" class="tab ${storeForm.tab==='parquet'?'active':''}" data-store-tab="parquet">پارکت</button>
        <button type="button" class="tab ${storeForm.tab==='mdf'?'active':''}" data-store-tab="mdf">ام‌دی‌اف</button>
        <button type="button" class="tab ${storeForm.tab==='raw'?'active':''}" data-store-tab="raw">ام‌دی‌اف خام</button>
      </div>
      <label>نام خریدار</label>
      <input id="stBuyer" value="${esc(storeForm.buyer)}" placeholder="نام خریدار" />
      <label>شماره حواله</label>
      <input id="stInv" value="${esc(storeForm.invoiceNo)}" placeholder="شماره" class="ltr" />
      <label>تاریخ</label>
      <input id="stDate" value="${esc(storeForm.date)}" class="ltr" />
      <div id="stRows"></div>
      <button type="button" class="btn btn-secondary btn-block" id="stAddRow">+ افزودن ردیف</button>
      <div class="row between mt"><strong>جمع کل</strong><span class="ltr" style="font-weight:800;color:#0284c7">${fmt(total)} ریال</span></div>
      <button type="button" class="btn btn-primary btn-block mt" id="stConfirm">${storeForm.editingId ? 'ذخیره تغییرات' : 'تایید و ثبت در فروشگاه'}</button>
    </div>

    <div class="card" style="margin-top:12px"><h2>گزارش ماهانه فروشگاه</h2>
      <div class="month-grid">`;
  MONTHS.forEach((name, i) => {
    const col = MONTH_COLORS[i] || '#e2e8f0';
    html += `<div class="month-box" style="background:${col}22;border-top:3px solid ${col}"><div class="m-name">${name}</div><div class="m-val ltr" style="color:#0f172a;font-weight:800">${fmt(monthTotals[i])}</div></div>`;
  });
  html += `</div></div>
    <div class="card" style="margin-top:12px"><h2>فروش‌های ثبت‌شده</h2>`;

  const list = [...(DB.storeSales || [])].sort((a, b) => {
    const ka = (a.date || '') + (a.time || '') + String(a.id || '').padStart(8, '0');
    const kb = (b.date || '') + (b.time || '') + String(b.id || '').padStart(8, '0');
    return kb.localeCompare(ka);
  });
  if (!list.length) html += `<div class="empty">هنوز فروشی ثبت نشده</div>`;
  else {
    const groups = {};
    const order = [];
    list.forEach(s => {
      const k = storeWeekKey(s.date).join('-');
      if (!groups[k]) { groups[k] = []; order.push(k); }
      groups[k].push(s);
    });
    order.forEach(k => {
      const items = groups[k];
      const [yk, wn] = k.split('-').map(Number);
      const wTot = items.reduce((s, x) => s + amount(x.total), 0);
      const wM = items.reduce((s, x) => s + storeItemsMeterage(storeParseItems(x)), 0);
      html += `<div class="day-box" style="background:#fff;border-radius:16px;padding:10px;margin-bottom:10px;border:1px solid #e2e8f0">
        <div class="day-head" style="text-align:center;font-weight:700">هفته ${fa(wn + 1)} سال ${fa(yk)} · فروش: ${fmt(wTot)} · متراژ: ${storeFmtMeter(wM)} متر</div>`;
      items.forEach(s => {
        const tabFa = s.tab === 'parquet' ? 'پارکت' : s.tab === 'mdf' ? 'ام‌دی‌اف' : 'خام';
        let lines = '';
        storeParseItems(s).forEach((r, i) => {
          const bits = [`${fa(i + 1)})`];
          if (s.tab === 'parquet') {
            bits.push('کد ' + fa(r.code || '—'));
            bits.push(r.type || '');
            if (r.grade) bits.push(r.grade);
            if (r.qty1) bits.push(fa(r.qty1) + ' کارتن');
            if (r.qty2) bits.push(fa(r.qty2) + ' متر');
          } else {
            bits.push(r.type || '');
            if (r.code) bits.push('کد ' + fa(r.code));
            if (r.qty1) bits.push(fa(r.qty1));
          }
          if (r.price) bits.push('فی ' + fmt(r.price));
          bits.push('<b style="color:#0284c7">' + fmt(r.cost || 0) + '</b>');
          lines += `<div style="font-size:12px;line-height:1.7">${bits.join(' · ')}</div>`;
        });
        html += `<div class="list-item" style="border-right:4px solid #0284c7;background:#fff">
          <div class="row between"><strong>${esc(s.customer)}</strong><span class="ltr" style="font-weight:800;color:#059669">${fmt(s.total)}</span></div>
          <div class="muted">ش ${fa(s.invoiceNo)} | ${fa(s.date)} ${fa(s.time || '')} | ${tabFa}</div>
          ${lines}
          <div class="actions mt">
            <button class="btn btn-primary btn-sm" data-st-edit="${s.id}">ویرایش</button>
            <button class="btn btn-danger btn-sm" data-st-del="${s.id}">حذف</button>
          </div>
        </div>`;
      });
      html += `</div>`;
    });
  }
  html += `</div>`;
  return html;
}

function renderStoreRowsInto(container) {
  if (!container) return;
  try { storeRecalcRows(); } catch (e) {}
  let h = '';
  const gradesList = (typeof GRADE_OPTIONS !== 'undefined' && GRADE_OPTIONS) ? GRADE_OPTIONS : ['GA', 'GB', 'GC'];
  const productList = (typeof PRODUCT_OPTIONS !== 'undefined' && PRODUCT_OPTIONS) ? PRODUCT_OPTIONS : ['Isofam Luxury'];
  (storeForm.rows || []).forEach((r, idx) => {
    let locked = false;
    try {
      locked = storeForm.tab === 'parquet' && !!productFromCode(r.code);
      if (locked) r.type = productFromCode(r.code);
    } catch (e) {}
    if (storeForm.tab === 'parquet') {
      const opts = productList.map(o => '<option value="' + o + '" ' + (r.type === o ? 'selected' : '') + '>' + o + '</option>').join('');
      const grades = gradesList.map(g => '<option value="' + g + '" ' + (r.grade === g ? 'selected' : '') + '>' + g + '</option>').join('');
      h += '<div class="card" data-st-row="' + idx + '" style="padding:10px;margin-top:8px;background:#fff">' +
        '<div class="row between"><span class="muted">ردیف ' + fa(idx + 1) + '</span>' +
        '<button type="button" class="btn btn-danger btn-sm" data-st-rm="' + idx + '">✕</button></div>' +
        '<label>کد</label><input data-st-f="code" data-st-i="' + idx + '" value="' + esc(r.code) + '" class="ltr" autocomplete="off" />' +
        '<label>نوع</label><select data-st-f="type" data-st-i="' + idx + '" ' + (locked ? 'disabled' : '') + '>' + opts + '</select>' +
        '<label>گرید</label><select data-st-f="grade" data-st-i="' + idx + '">' + grades + '</select>' +
        '<label>کارتن</label><input data-st-f="qty1" data-st-i="' + idx + '" value="' + esc(r.qty1) + '" class="ltr" inputmode="decimal" autocomplete="off" />' +
        '<label>متراژ</label><input data-st-meter value="' + esc(r.qty2) + '" class="ltr" readonly tabindex="-1" />' +
        '<label>قیمت واحد</label><input data-st-f="price" data-st-i="' + idx + '" value="' + esc(r.price) + '" class="ltr" inputmode="numeric" autocomplete="off" />' +
        '<div class="muted mt">هزینه: <b class="ltr" data-st-cost>' + fmt(r.cost || 0) + '</b></div></div>';
    } else if (storeForm.tab === 'mdf') {
      h += '<div class="card" data-st-row="' + idx + '" style="padding:10px;margin-top:8px;background:#fff">' +
        '<div class="row between"><span class="muted">ردیف ' + fa(idx + 1) + '</span>' +
        '<button type="button" class="btn btn-danger btn-sm" data-st-rm="' + idx + '">✕</button></div>' +
        '<label>نوع</label><input data-st-f="type" data-st-i="' + idx + '" value="' + esc(r.type) + '" autocomplete="off" />' +
        '<label>کد</label><input data-st-f="code" data-st-i="' + idx + '" value="' + esc(r.code) + '" class="ltr" autocomplete="off" />' +
        '<label>پالت</label><input data-st-f="qty1" data-st-i="' + idx + '" value="' + esc(r.qty1) + '" class="ltr" autocomplete="off" />' +
        '<label>ورق</label><input data-st-f="qty2" data-st-i="' + idx + '" value="' + esc(r.qty2) + '" class="ltr" autocomplete="off" />' +
        '<label>قیمت</label><input data-st-f="price" data-st-i="' + idx + '" value="' + esc(r.price) + '" class="ltr" inputmode="numeric" autocomplete="off" />' +
        '<div class="muted mt">هزینه: <b class="ltr" data-st-cost>' + fmt(r.cost || 0) + '</b></div></div>';
    } else {
      h += '<div class="card" data-st-row="' + idx + '" style="padding:10px;margin-top:8px;background:#fff">' +
        '<div class="row between"><span class="muted">ردیف ' + fa(idx + 1) + '</span>' +
        '<button type="button" class="btn btn-danger btn-sm" data-st-rm="' + idx + '">✕</button></div>' +
        '<label>نوع</label><input data-st-f="type" data-st-i="' + idx + '" value="' + esc(r.type) + '" autocomplete="off" />' +
        '<label>سایز</label><input data-st-f="size" data-st-i="' + idx + '" value="' + esc(r.size || '') + '" autocomplete="off" />' +
        '<label>پالت</label><input data-st-f="qty1" data-st-i="' + idx + '" value="' + esc(r.qty1) + '" class="ltr" autocomplete="off" />' +
        '<label>ورق</label><input data-st-f="qty2" data-st-i="' + idx + '" value="' + esc(r.qty2) + '" class="ltr" autocomplete="off" />' +
        '<label>قیمت</label><input data-st-f="price" data-st-i="' + idx + '" value="' + esc(r.price) + '" class="ltr" inputmode="numeric" autocomplete="off" />' +
        '<div class="muted mt">هزینه: <b class="ltr" data-st-cost>' + fmt(r.cost || 0) + '</b></div></div>';
    }
  });
  container.innerHTML = h;
  // reset delegation flag so bind can re-attach if needed — actually keep flag on element; after innerHTML listeners on parent remain
}

function bindStorePage() {
  const rowsEl = document.getElementById('stRows');

  function updateStoreTotalsUI() {
    try {
      const total = storeTotal();
      document.querySelectorAll('.card .row.between.mt span.ltr').forEach(sp => {
        if (sp.parentElement && sp.parentElement.textContent.indexOf('جمع') >= 0) {
          sp.textContent = fmt(total) + ' ریال';
        }
      });
    } catch (e) {}
  }

  function updateStoreRowCostUI(i) {
    try {
      if (!storeForm.rows[i]) return;
      const rowCard = document.querySelector('[data-st-row="' + i + '"]');
      if (!rowCard) return;
      const costB = rowCard.querySelector('[data-st-cost]');
      if (costB) costB.textContent = fmt(storeForm.rows[i].cost || 0);
      const meter = rowCard.querySelector('[data-st-meter]');
      if (meter) meter.value = storeForm.rows[i].qty2 || '';
      const typeSel = rowCard.querySelector('[data-st-f="type"]');
      if (typeSel && storeForm.rows[i].type) {
        typeSel.value = storeForm.rows[i].type;
        const locked = !!productFromCode(storeForm.rows[i].code);
        typeSel.disabled = locked;
      }
    } catch (e) {}
  }

  function handleStoreField(el) {
    const i = +el.dataset.stI;
    const f = el.dataset.stF;
    if (isNaN(i) || !f || !storeForm.rows[i]) return;
    storeForm.rows[i][f] = el.value;
    if (f === 'code' && storeForm.tab === 'parquet') {
      const p = productFromCode(el.value);
      if (p) storeForm.rows[i].type = p;
    }
    storeRecalcRows();
    updateStoreRowCostUI(i);
    updateStoreTotalsUI();
  }

  // رندر ردیف‌ها
  try {
    renderStoreRowsInto(rowsEl);
  } catch (e) {
    console.error('renderStoreRowsInto', e);
    if (rowsEl) rowsEl.innerHTML = '<div class="empty">خطا در نمایش ردیف‌ها: ' + (e.message || e) + '</div>';
  }

  // تب‌ها
  document.querySelectorAll('[data-store-tab]').forEach(b => {
    b.onclick = function () {
      storeForm.tab = b.dataset.storeTab;
      storeForm.rows = [storeEmptyRow()];
      go('store');
    };
  });

  // افزودن ردیف — اول از همه
  const addBtn = document.getElementById('stAddRow');
  if (addBtn) {
    addBtn.onclick = function (e) {
      try { e.preventDefault(); e.stopPropagation(); } catch (err) {}
      if (!Array.isArray(storeForm.rows)) storeForm.rows = [];
      storeForm.rows.push(storeEmptyRow());
      try {
        renderStoreRowsInto(document.getElementById('stRows'));
      } catch (err) {
        alert('خطا افزودن ردیف: ' + (err.message || err));
        return;
      }
      updateStoreTotalsUI();
      try {
        const box = document.getElementById('stRows');
        const codes = box ? box.querySelectorAll('[data-st-f="code"], [data-st-f="type"]') : [];
        if (codes.length) {
          const el = codes[codes.length - 1];
          el.focus();
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      } catch (err) {}
    };
  }

  // event delegation — تایپ بدون از دست دادن فوکوس
  if (rowsEl && !rowsEl._storeBound) {
    rowsEl._storeBound = true;
    rowsEl.addEventListener('input', function (e) {
      const el = e.target;
      if (!el || !el.dataset || !el.dataset.stF) return;
      handleStoreField(el);
    }, true);
    rowsEl.addEventListener('change', function (e) {
      const el = e.target;
      if (!el || !el.dataset || !el.dataset.stF) return;
      handleStoreField(el);
    }, true);
    rowsEl.addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('[data-st-rm]') : null;
      if (!btn) return;
      try { e.preventDefault(); e.stopPropagation(); } catch (err) {}
      const i = +btn.dataset.stRm;
      storeForm.rows.splice(i, 1);
      if (!storeForm.rows.length) storeForm.rows.push(storeEmptyRow());
      renderStoreRowsInto(rowsEl);
      updateStoreTotalsUI();
    }, true);
  }

  updateStoreTotalsUI();

  function syncHeader() {
    storeForm.buyer = (document.getElementById('stBuyer') || {}).value || '';
    storeForm.invoiceNo = (document.getElementById('stInv') || {}).value || '';
    storeForm.date = (document.getElementById('stDate') || {}).value || '';
  }

  const conf = document.getElementById('stConfirm');
  if (conf) conf.onclick = function () {
    syncHeader();
    storeRecalcRows();
    const total = storeTotal();
    if (!storeForm.buyer.trim()) return alert('نام خریدار را وارد کنید');
    if (!en(storeForm.invoiceNo).trim()) return alert('شماره حواله را وارد کنید');
    if (total <= 0) return alert('حداقل یک ردیف با مقدار و قیمت وارد کنید');
    const nj = nowJalali();
    const time = new Date().toTimeString().slice(0, 8);
    const items = JSON.parse(JSON.stringify(storeForm.rows));
    if (!DB.storeNextId) DB.storeNextId = 1;
    const rec = {
      id: storeForm.editingId || (DB.storeNextId++),
      customer: storeForm.buyer.trim(),
      invoiceNo: en(storeForm.invoiceNo).trim(),
      date: en(storeForm.date || nj.date),
      time: time,
      total: String(total),
      tab: storeForm.tab,
      items: items,
      itemsJson: JSON.stringify(items),
      createdAt: new Date().toISOString()
    };
    if (!DB.storeSales) DB.storeSales = [];
    if (storeForm.editingId) {
      const ix = DB.storeSales.findIndex(x => x.id === storeForm.editingId);
      if (ix >= 0) DB.storeSales[ix] = rec;
      else DB.storeSales.unshift(rec);
    } else {
      DB.storeSales.unshift(rec);
    }
    save(DB);
    storeForm = { tab: storeForm.tab, buyer: '', invoiceNo: '', date: nj.date, rows: [storeEmptyRow()], editingId: null };
    try { if (sbLoggedIn()) pushToSupabase(); } catch (e) {}
    go('store');
    alert('ثبت شد');
  };

  document.querySelectorAll('[data-st-edit]').forEach(b => {
    b.onclick = function () {
      const id = +b.dataset.stEdit;
      const s = (DB.storeSales || []).find(x => x.id === id);
      if (!s) return;
      storeForm.editingId = id;
      storeForm.tab = s.tab || 'parquet';
      storeForm.buyer = s.customer || '';
      storeForm.invoiceNo = s.invoiceNo || '';
      storeForm.date = s.date || nowJalali().date;
      var _si = storeParseItems(s); storeForm.rows = _si.length ? JSON.parse(JSON.stringify(_si)) : [storeEmptyRow()];
      go('store');
      window.scrollTo(0, 0);
    };
  });
  document.querySelectorAll('[data-st-del]').forEach(b => {
    b.onclick = function () {
      if (!confirm('حذف شود؟')) return;
      const id = +b.dataset.stDel;
      DB.storeSales = (DB.storeSales || []).filter(x => x.id !== id);
      save(DB);
      try { if (sbLoggedIn()) pushToSupabase(); } catch (e) {}
      go('store');
    };
  });
}



function bindPage(page) {
  if (page === 'home') {
    const newInv = document.getElementById('homeNewInv');
    if (newInv) newInv.onclick = function () {
      go('invoices');
      setTimeout(function () {
        try { openInvoiceModal(null); } catch (e) { console.warn(e); }
      }, 50);
    };
    const homeInq = document.getElementById('homeInq');
    if (homeInq) homeInq.onclick = function () { go('inquiry'); };
    const homeStore = document.getElementById('homeStore');
    if (homeStore) homeStore.onclick = function () { go('store'); };
    const savedInq = document.getElementById('homeSavedInq');
    if (savedInq) {
      savedInq.style.cursor = 'pointer';
      savedInq.onclick = function () {
        try { showSavedInquiries(); } catch (e) {
          go('inquiry');
          setTimeout(function () {
            try { showSavedInquiries(); } catch (e2) { console.warn(e2); }
          }, 80);
        }
      };
    }
  }
  if (page === 'invoices') {
    const s = document.getElementById('invSearch');
    if (s) s.oninput = () => {
      document.getElementById('app').innerHTML = renderInvoices(s.value);
      bindPage('invoices');
    };
    document.getElementById('btnNewInv').onclick = () => openInvoiceModal(null);
    document.querySelectorAll('[data-inq]').forEach(b => {
      b.onclick = () => {
        const inv = DB.invoices.find(i => i.id === +b.dataset.inq);
        if (!inv) return;
        openInvoiceInquiry(inv);
      };
    });
    document.querySelectorAll('[data-edit]').forEach(b => {
      b.onclick = () => {
        const inv = DB.invoices.find(i => i.id === +b.dataset.edit);
        if (inv) openInvoiceModal(inv);
      };
    });
    document.querySelectorAll('[data-del]').forEach(b => {
      b.onclick = () => {
        if (!confirm('حذف شود؟')) return;
        DB.invoices = DB.invoices.filter(i => i.id !== +b.dataset.del);
        save(DB);
        go('invoices');
      };
    });
  }
  if (page === 'customers') {
    document.querySelectorAll('[data-bal]').forEach(b => {
      b.onclick = () => openBalanceModal(b.dataset.bal);
    });
    document.querySelectorAll('[data-cust-purchases]').forEach(b => {
      b.onclick = () => openCustomerPurchases(b.dataset.custPurchases);
    });
  }
  if (page === 'reports') {
    document.querySelectorAll('[data-year]').forEach(btn => {
      btn.onclick = () => {
        window._forceReportYear = btn.dataset.year;
        const totals = Array(12).fill(0);
        const yy = btn.dataset.year;
        DB.invoices.filter(i => (i.date || '').startsWith(yy)).forEach(i => {
          const m = parseInt((i.date || '').split('/')[1], 10);
          if (m >= 1 && m <= 12) totals[m - 1] += amount(i.total);
        });
        const sum = totals.reduce((a, b) => a + b, 0);
        const years = [...new Set(DB.invoices.map(i => (i.date || '').slice(0, 4)).filter(x => /^\d{4}$/.test(x)))].sort().reverse();
        if (!years.includes(yy)) years.unshift(yy);
        let html = `<label>سال</label><div class="year-scroll" id="yearScroll">`;
        years.forEach(y2 => {
          html += `<button type="button" class="year-chip ${y2 === yy ? 'active' : ''}" data-year="${y2}">${fa(y2)}</button>`;
        });
        html += `</div>
          <div class="stat"><div class="label">جمع کل سال ${fa(yy)}</div><div class="value">${fmt(sum)} ریال</div></div>
          <div class="month-grid mt">`;
        MONTHS.forEach((name, i) => {
          html += `<div class="month-box" style="background:${MONTH_COLORS[i]}"><div class="m">${name}</div><div class="v">${fmt(totals[i])}</div></div>`;
        });
        html += `</div><div class="card mt"><h2>نمودار فروش</h2>${buildChartSvg(totals)}</div>`;
        document.getElementById('app').innerHTML = html;
        bindPage('reports');
      };
    });
  }
  if (page === 'inquiry') {
    document.querySelectorAll('[data-tab]').forEach(t => {
      t.onclick = () => {
        syncInqFromDom();
        inq.tab = t.dataset.tab;
        inq.rows = [emptyRow()];
        go('inquiry');
      };
    });
    const reRender = () => {
      syncInqFromDom();
      go('inquiry', { keepScroll: true });
    };
    document.querySelectorAll('[data-r]').forEach(el => {
      const live = () => {
        // update row fields + auto meterage for parquet
        const i = +el.dataset.r, f = el.dataset.f;
        if (inq.rows[i]) inq.rows[i][f] = el.value;
        if (inq.tab === 'parquet' && (f === 'qty1' || f === 'type')) {
          const typeEl = document.querySelector(`[data-r="${i}"][data-f="type"]`);
          const qty1El = document.querySelector(`[data-r="${i}"][data-f="qty1"]`);
          const qty2El = document.querySelector(`[data-r="${i}"][data-f="qty2"]`);
          const typeVal = typeEl ? typeEl.value : (inq.rows[i].type || 'Isofam Luxury');
          const factor = PRODUCT_FACTORS[typeVal] || 1.9608;
          const cartons = parseFloat(clean(qty1El ? qty1El.value : '')) || 0;
          const meter = cartons ? (cartons * factor).toFixed(4).replace(/\.0+$/, '').replace(/(\.[0-9]*?)0+$/, '$1') : '';
          if (inq.rows[i]) {
            inq.rows[i].type = typeVal;
            inq.rows[i].qty1 = qty1El ? qty1El.value : '';
            inq.rows[i].qty2 = meter;
          }
          if (qty2El) qty2El.value = meter;
        }
        if (f === 'price' || f === 'qty2' || f === 'qty1' || f === 'type') {
          // live cost on row + totals without full re-render
          const costEls = document.querySelectorAll('.card .muted strong');
          // safer: soft re-render totals only
          syncInqFromDom();
          const sub = inq.rows.reduce((s, r) => s + rowCost(r), 0);
          const total = inqTotal();
          const stat = document.querySelector('.stat .value');
          const label = document.querySelector('.stat .label');
          const wordsEl = document.querySelector('.stat div[style]');
          if (stat) stat.textContent = fmt(total) + ' ریال';
          if (label) label.textContent = 'جمع اقلام ' + fmt(sub) + ' — جمع کل';
          if (wordsEl) wordsEl.textContent = words(total) + ' ریال';
          // update row cost labels
          document.querySelectorAll('[data-r][data-f="price"]').forEach(pe => {
            const ri = +pe.dataset.r;
            const card = pe.closest('.card');
            if (!card) return;
            const strong = card.querySelector('.muted strong');
            if (strong && inq.rows[ri]) strong.textContent = fmt(rowCost(inq.rows[ri]));
          });
        }
      };
      el.oninput = () => {
        live();
        if (el.dataset.f === 'code' && inq.tab === 'parquet') {
          const ri = +el.dataset.r;
          const mapped = productFromCode(el.value);
          const typeEl = document.querySelector('[data-r="' + ri + '"][data-f="type"]');
          if (mapped === 'Egmont') {
            if (inq.rows[ri].type !== 'Egmont' && inq.rows[ri].type !== 'N Egmont') {
              inq.rows[ri].type = '';
            }
            // فقط برای Egmont رندر لازم است (دو گزینه)
            reRender();
          } else if (mapped) {
            inq.rows[ri].type = mapped;
            if (typeEl) {
              const to = typeOptionsHtml(mapped, el.value);
              typeEl.innerHTML = to.html;
              typeEl.value = mapped;
              typeEl.disabled = !!to.locked;
            }
            live();
          } else if (typeEl) {
            // کد ناشناخته → نوع قابل انتخاب
            const to = typeOptionsHtml(inq.rows[ri].type || 'Isofam Luxury', el.value);
            typeEl.innerHTML = to.html;
            typeEl.disabled = false;
          }
        }
      };
      el.onchange = () => {
        live();
        if (el.dataset.f === 'type' || el.dataset.f === 'code') reRender();
      };
    });
    document.getElementById('addRow').onclick = () => {
      syncInqFromDom();
      inq.rows.push(emptyRow());
      go('inquiry');
    };
    document.querySelectorAll('[data-rmrow]').forEach(b => {
      b.onclick = () => {
        syncInqFromDom();
        inq.rows.splice(+b.dataset.rmrow, 1);
        go('inquiry');
      };
    });
    document.getElementById('iqSave').onclick = () => {
      syncInqFromDom();
      saveInquirySmart(JSON.parse(JSON.stringify(inq)), inqTotal());
      save(DB);
      alert('استعلام ذخیره شد');
    };
    document.getElementById('iqFinal').onclick = openFinalize;
    const pdfBtn = document.getElementById('iqPdf');
    const imgBtn = document.getElementById('iqImg');
    function ensureEgmontChosen() {
      if (inq.tab !== 'parquet') return true;
      for (let i = 0; i < inq.rows.length; i++) {
        const r = inq.rows[i];
        if (productFromCode(r.code) === 'Egmont' && r.type !== 'Egmont' && r.type !== 'N Egmont') {
          alert('برای کد Egmont در ردیف ' + fa(i + 1) + ' نوع را انتخاب کنید:\nEgmont = ۱٫۸۶۹۶\nN Egmont = ۱٫۹۶۰۸');
          return false;
        }
      }
      return true;
    }
    if (pdfBtn) pdfBtn.onclick = () => {
      syncInqFromDom();
      if (!ensureEgmontChosen()) return;
      openInquiryExport(false);
    };
    if (imgBtn) imgBtn.onclick = () => {
      syncInqFromDom();
      if (!ensureEgmontChosen()) return;
      openInquiryExport(true);
    };
    const savedBtn = document.getElementById('btnSavedInq');
    if (savedBtn) savedBtn.onclick = showSavedInquiries;
    document.querySelectorAll('[data-iqpick]').forEach(b => {
      b.onclick = () => {
        const el = document.getElementById('iqBuyer');
        if (el) el.value = b.dataset.iqpick;
        inq.buyer = b.dataset.iqpick;
        refreshIqCustSuggestions(b.dataset.iqpick);
      };
    });
    // پیشنهاد نام مشتری هنگام تایپ
    try {
      const be = document.getElementById('iqBuyer');
      if (be) {
        be.oninput = function () {
          inq.buyer = be.value;
          refreshIqCustSuggestions(be.value);
        };
        refreshIqCustSuggestions(be.value);
      }
    } catch (e) {}
    // default date if empty
    const dEl = document.getElementById('iqDate');
    if (dEl && !dEl.value.trim()) dEl.value = nowJalali().date;
  }
  if (page === 'store') {
    bindStorePage();
  }
  if (page === 'inventory') {
    bindInventoryPage();
  }
  if (page === 'ras') {
    bindRasPage();
  }
  if (page === 'settings') {
    document.getElementById('setSave').onclick = () => {
      DB.company = document.getElementById('setCompany').value.trim() || 'SalesMate';
      save(DB);
      alert('ذخیره شد');
    };
    const chkBC = document.getElementById('chkBackupClose');
    if (chkBC) {
      chkBC.checked = backupOnCloseEnabled();
      chkBC.onchange = () => setBackupOnClose(chkBC.checked);
    }
    function refreshSbStatus() {
      const el = document.getElementById('sbStatus');
      if (!el) return;
      if (sbLoggedIn()) {
        const u = sbUser();
        el.textContent = 'وضعیت: وارد شده — ' + (u.email || '') + ' (داده جدا)';
        const em = document.getElementById('sbEmail');
        if (em && u.email) em.value = u.email;
      } else {
        el.textContent = 'وضعیت: وارد نشده — ثبت‌نام یا ورود کنید';
      }
    }
    refreshSbStatus();
    const btnLogin = document.getElementById('btnSbLogin');
    const btnSignup = document.getElementById('btnSbSignup');
    const btnLogout = document.getElementById('btnSbLogout');
    if (btnLogin) btnLogin.onclick = async () => {
      const email = (document.getElementById('sbEmail').value || '').trim();
      const pass = document.getElementById('sbPass').value || '';
      if (!email || !pass) return alert('ایمیل و رمز لازم است');
      try {
        btnLogin.textContent = 'در حال ورود...';
        await sbLogin(email, pass);
        document.getElementById('sbPass').value = '';
        _cloudSynced = true;
        try {
          await pullFromSupabase();
          _cloudSynced = true;
        } catch (pe) {
          console.warn(pe);
        }
        refreshSbStatus();
        alert('با موفقیت وارد شدید — داده ابر دریافت شد');
        go('home');
      } catch (e) {
        alert('خطا ورود: ' + e.message);
      } finally {
        btnLogin.textContent = 'ورود';
      }
    };
    if (btnSignup) btnSignup.onclick = async () => {
      const email = (document.getElementById('sbEmail').value || '').trim();
      const pass = document.getElementById('sbPass').value || '';
      if (!email || pass.length < 6) return alert('ایمیل و رمز حداقل ۶ کاراکتر لازم است');
      try {
        btnSignup.textContent = 'در حال ثبت‌نام...';
        await sbSignup(email, pass);
        document.getElementById('sbPass').value = '';
        refreshSbStatus();
        alert('حساب ساخته شد');
      } catch (e) {
        alert('خطا ثبت‌نام: ' + e.message);
      } finally {
        btnSignup.textContent = 'ثبت‌نام';
      }
    };
    if (btnLogout) btnLogout.onclick = () => {
      sbLogout();
      refreshSbStatus();
      alert('از حساب خارج شدید');
    };
    const btnRestore = document.getElementById('btnRestoreLocal');
    if (btnRestore) btnRestore.onclick = function () {
      if (!confirm('بک‌آپ محلی بازیابی شود؟')) return;
      var c = restoreLocalBackup();
      if (!c) { alert('بک‌آپ پیدا نشد'); return; }
      alert('بازیابی شد — حواله: ' + fa(c.inv) + ' / استعلام: ' + fa(c.inq));
      try { scheduleCloudPush(500, true); } catch (e) {}
      go('home');
    };
    const sbPull = document.getElementById('btnSbPull');
    const sbPush = document.getElementById('btnSbPush');
    if (sbPull) sbPull.onclick = async () => {
      if (!sbLoggedIn()) return alert('ابتدا وارد شوید');
      if (!confirm('داده ابر با داده گوشی ادغام شود؟ (اطلاعات محلی پاک نمی‌شود)')) return;
      try {
        sbPull.textContent = 'در حال دریافت...';
        if (_localDirty) {
          try { await pushToSupabase(); _localDirty = false; } catch (pe) { alert('اول باید تغییرات محلی ارسال شود: ' + pe.message); return; }
        }
        await pullFromSupabase();
        try { await pullInventoryFromCloud(); } catch (ie) {}
        _cloudSynced = true;
        const nStore = (DB.storeSales || []).length;
        alert('داده حساب شما از ابر دریافت شد\nتعداد فروشگاه: ' + nStore);
        go('home');
      } catch (e) {
        alert('خطا: ' + e.message);
      } finally {
        sbPull.textContent = '⬇ دریافت داده من از ابر';
      }
    };
    if (sbPush) sbPush.onclick = async () => {
      if (!sbLoggedIn()) return alert('ابتدا وارد شوید');
      try {
        sbPush.textContent = 'در حال ارسال...';
        await pushToSupabase();
        alert('داده حساب شما به ابر ارسال شد');
      } catch (e) {
        alert('خطا: ' + e.message);
      } finally {
        sbPush.textContent = '⬆ ارسال داده من به ابر';
      }
    };
    document.getElementById('btnExport').onclick = () => {
      DB.updatedAt = new Date().toISOString().slice(0, 19);
      DB.version = 1;
      save(DB);
      const blob = new Blob([JSON.stringify(DB, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'salesmate_sync.json';
      a.click();
      alert('فایل salesmate_sync.json ذخیره شد. آن را در پوشه SalesMate_Backup در Google Drive بگذارید.');
    };
    document.getElementById('btnImport').onclick = () => document.getElementById('importFile').click();
    document.getElementById('importFile').onchange = e => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try {
          const data = JSON.parse(reader.result);
          if (!data || !Array.isArray(data.invoices)) throw new Error('فرمت نامعتبر');
          if (!confirm('داده فعلی گوشی با فایل همگام جایگزین شود؟')) return;
          DB = data;
          if (!DB.balances) DB.balances = {};
          if (!DB.inquiries) DB.inquiries = [];
          if (!DB.nextId) DB.nextId = (DB.invoices.reduce((m, i) => Math.max(m, i.id || 0), 0) + 1);
          DB.updatedAt = data.updatedAt || new Date().toISOString().slice(0, 19);
          save(DB);
          alert('همگام‌سازی انجام شد' + (data.updatedAt ? ('\nزمان فایل: ' + data.updatedAt) : ''));
          go('home');
        } catch (err) {
          alert('خطا در خواندن فایل همگام');
        }
      };
      reader.readAsText(file);
    };
    document.getElementById('btnClear').onclick = () => {
      if (!confirm('همه اطلاعات پاک شود؟')) return;
      DB = defaultData();
      save(DB);
      go('home');
    };
  }
}

document.querySelectorAll('.nav-btn').forEach(b => {
  b.addEventListener('click', () => go(b.dataset.page));
});
document.getElementById('modal').addEventListener('click', e => {
  if (e.target.id === 'modal') hideModal();
});

try {
  go('home');
} catch (err) {
  var app = document.getElementById('app');
  if (app) app.innerHTML = '<div class="card" style="color:#b91c1c"><b>خطای اجرا:</b><br>' + (err && err.message ? err.message : err) + '</div>';
  console.error(err);
}

// با باز شدن اپ: اگر لاگین است از ابر بگیر (داده ویندوز بیاید)
(function bootCloudSync() {
  if (!sbLoggedIn()) return;
  _cloudSynced = true;
  var app = document.getElementById('app');
  var banner = document.createElement('div');
  banner.id = 'syncBanner';
  banner.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#0284c7;color:#fff;text-align:center;padding:8px;font-size:13px;font-family:Vazirmatn,Tahoma,sans-serif;';
  banner.textContent = 'در حال دریافت داده از ابر...';
  document.body.appendChild(banner);
  autoPullFromCloud('boot').then(function (ok) {
    banner.textContent = ok ? 'داده ابر به‌روز شد' : 'ابر در دسترس نیست یا آفلاین — داده محلی';
    banner.style.background = ok ? '#059669' : '#b45309';
    if (ok) {
      try { go(document.querySelector('.nav-btn.active') ? document.querySelector('.nav-btn.active').dataset.page : 'home', { keepScroll: true }); } catch (e) { go('home'); }
    }
    setTimeout(function () { if (banner.parentNode) banner.parentNode.removeChild(banner); }, 1800);
  });
})();
if ('serviceWorker' in navigator && location.protocol.indexOf('http') === 0) {
  navigator.serviceWorker.register('./sw.js').catch(function () {});
}

// پشتیبان هنگام بستن / ترک صفحه (مثل ویندوز)
window.addEventListener('pagehide', function () {
  if (!backupOnCloseEnabled() || !sbLoggedIn()) return;
  // sendBeacon-style: try sync push (async may be killed; still best effort)
  try { tryBackupOnLeave(); } catch(e) {}
});
document.addEventListener('visibilitychange', function () {
  if (document.visibilityState === 'hidden') {
    try { tryBackupOnLeave(); } catch(e) {}
  } else if (document.visibilityState === 'visible') {
    // برگشت به اپ → فقط اگر حداقل ۴۵ ثانیه از آخرین pull گذشته
    if (sbLoggedIn() && navigator.onLine !== false && !_cloudBusy && (Date.now() - _lastPullAt > 45000)) {
      autoPullFromCloud('visible').then(function (ok) {
        if (ok) {
          try {
            var active = document.querySelector('.nav-btn.active');
            go(active ? active.dataset.page : 'home', { keepScroll: true });
          } catch (e) {}
        }
      });
    }
  }
});
window.addEventListener('beforeunload', function (e) {
  // اگر آفلاین و لاگین و تیک فعال: هشدار (مرورگر متن سفارشی را اغلب نشان نمی‌دهد)
  if (!backupOnCloseEnabled() || !sbLoggedIn()) return;
  if (navigator.onLine === false) {
    e.preventDefault();
    e.returnValue = '';
  }
});


(function softCloudPollInit() {
  setInterval(function () {
    try {
      if (typeof sbLoggedIn !== 'function' || !sbLoggedIn()) return;
      if (typeof _localDirty !== 'undefined' && _localDirty) return;
      if (typeof _cloudBusy !== 'undefined' && _cloudBusy) return;
      if (document.hidden) return;
      var before = JSON.stringify({
        inv: (DB.invoices || []).length,
        inq: (DB.inquiries || []).length,
        st: (DB.storeSales || []).length
      });
      pullFromSupabase().then(function () {
        try {
          var after = JSON.stringify({
            inv: (DB.invoices || []).length,
            inq: (DB.inquiries || []).length,
            st: (DB.storeSales || []).length
          });
          // فقط اگر داده عوض شد و بدون پرش به بالا
          if (before !== after) {
            var active = document.querySelector('.nav-btn.active');
            go(active ? active.dataset.page : 'home', { keepScroll: true });
          }
        } catch (e) {}
      }).catch(function () {});
    } catch (e) {}
  }, 20000);
})();
