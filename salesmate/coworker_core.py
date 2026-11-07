# -*- coding: utf-8 -*-
"""مدیریت همکاران: منطق خالص + ارتباط با Supabase از طریق یک تابع request.

request(method, path, body=None, extra_headers=None) -> (status, data)  (همان supabase_request)
هیچ ایمپورتی از Qt ندارد تا بدون نمایشگر قابل تست باشد.
"""
import json
import zlib
from datetime import datetime, timezone

try:
    from .core_utils import customer_key, en_digits
except Exception:  # اجرای مستقل / تست
    from core_utils import customer_key, en_digits

OWNER_EMAIL = "arash.e.maleki@gmail.com"
LOGIN_DOMAIN = "@sales.local"
STORE_KEY = customer_key("فروشگاه ایزوفام")
ORIGIN_TAB = "analysis_import"      # نشانه‌ی حواله‌ی آمده از اکسل (در inquiry_data)


# ───────────── نقش و ورود ─────────────
def login_email(username):
    """ali → ali@sales.local ؛ اگر @ دارد همان را برمی‌گرداند."""
    s = str(username or "").strip()
    if not s:
        return ""
    if "@" in s:
        return s
    return s.lower() + LOGIN_DOMAIN


def is_owner_email(email):
    return str(email or "").strip().lower() == OWNER_EMAIL


def short_name(email):
    e = str(email or "")
    return e[:-len(LOGIN_DOMAIN)] if e.lower().endswith(LOGIN_DOMAIN) else e


# ───────────── ساخت حواله از اکسل ─────────────
def is_store_name(name):
    return customer_key(name).startswith(STORE_KEY)


def _s(v):
    s = "" if v is None else str(v)
    return "" if s in ("nan", "None") else s


KINDS = ("parquet", "mdf")
KIND_FA = {"parquet": "پارکت", "mdf": "ام دی اف"}


def row_kind(cat):
    """دسته‌ی اکسل → گروه واگذاری: «ام دی اف» و «خام» = mdf ؛ هر چیز دیگر (پارکت، سایر، گمرک، ضایعات) = parquet."""
    c = str(cat or "").strip()
    return "mdf" if c in ("ام دی اف", "خام") else "parquet"


def _kinds_col(d):
    if "دسته" in d.columns:
        return d["دسته"].map(row_kind)
    return d["نام مشتری"].map(lambda _: "parquet")


def label_of(kinds):
    kinds = set(kinds)
    return "all" if kinds >= set(KINDS) else (sorted(kinds)[0] if kinds else "")


def excel_invoices(df, ckey_kinds=None, exclude=None):
    """حواله‌های اکسل (گروه: مشتری+تاریخ+شماره فرم) → لیست دیکشنری.
    ckey_kinds: {ckey: {گروه‌ها}}؛ اگر داده شود فقط همین مشتری‌ها و فقط ردیف‌های همین گروه‌ها. فروشگاه ایزوفام همیشه حذف می‌شود."""
    out = []
    if df is None or len(df) == 0 or "نام مشتری" not in df.columns:
        return out
    d = df.copy()
    if "شماره فرم" not in d.columns:
        d["شماره فرم"] = ""
    d["شماره فرم"] = d["شماره فرم"].astype(str).replace({"nan": "", "None": ""})
    d["تاریخ"] = d["تاریخ"].astype(str)
    d["_ck"] = d["نام مشتری"].astype(str).map(customer_key)
    d["_kd"] = _kinds_col(d)
    d = d[~d["_ck"].str.startswith(STORE_KEY)]
    if exclude:
        d = d[~d["_ck"].isin(set(exclude))]
    if ckey_kinds is not None:
        d = d[[(ck in ckey_kinds and kd in ckey_kinds[ck]) for ck, kd in zip(d["_ck"], d["_kd"])]]
    if len(d) == 0:
        return out
    for (name, date, form), grp in d.groupby(["نام مشتری", "تاریخ", "شماره فرم"], dropna=False, sort=False):
        name = _s(name).strip()
        date = _s(date).strip()
        form = _s(form).strip()
        if not name or not date:
            continue
        total = int(round(float(grp["مبلغ"].sum()))) if "مبلغ" in grp.columns else 0
        if total <= 0:
            continue
        inv_no = form or "AN-%s-%s" % (date.replace("/", ""), zlib.crc32((name + date).encode("utf-8")) % 100000)
        rows = []
        for _, r in grp.iterrows():
            rows.append({
                "code": _s(r.get("کد کالا", "")),
                "name": _s(r.get("نام کالا", "")),
                "type": _s(r.get("نام کالا", "")) or _s(r.get("دسته", "")),
                "qty1": _s(r.get("تعداد 1", "")) or _s(r.get("تعداد_ورق", "")),
                "qty2": _s(r.get("تعداد 2", "")),
                "price": _s(r.get("قیمت", "")),
                "cost": _s(r.get("مبلغ", "")),
            })
        ck = customer_key(name)
        label = label_of(ckey_kinds[ck]) if ckey_kinds is not None and ck in ckey_kinds else "all"
        out.append({"customer": name, "ckey": ck, "invoice_no": inv_no, "date": date,
                    "total": total, "rows": rows, "label": label})
    return out


def feed_key(inv):
    return "%s|%s|%s|%s" % (inv["ckey"], en_digits(str(inv["date"])), en_digits(str(inv["invoice_no"])), inv.get("label", "all"))


def excel_customer_names(df, exclude=None):
    """{ckey: نمایشی} مرتب (بدون فروشگاه)."""
    return {ck: v[0] for ck, v in excel_customer_info(df, exclude).items()}


def excel_customer_info(df, exclude=None):
    """{ckey: (نام نمایشی, {گروه‌هایی که خرید کرده})} مرتب، بدون فروشگاه ایزوفام."""
    res = {}
    if df is None or len(df) == 0 or "نام مشتری" not in df.columns:
        return res
    names = df["نام مشتری"].astype(str).str.strip()
    kinds = _kinds_col(df)
    for nm, kd in zip(names, kinds):
        if not nm or nm in ("nan", "None") or is_store_name(nm):
            continue
        ck = customer_key(nm)
        if exclude and ck in exclude:
            continue
        if ck not in res:
            res[ck] = (nm, set())
        res[ck][1].add(kd)
    return dict(sorted(res.items(), key=lambda kv: kv[1][0]))


# ───────────── صفحه‌بندی ─────────────
def get_all(request, path, page=1000, max_pages=200):
    sep = "&" if "?" in path else "?"
    rows, off = [], 0
    for _ in range(max_pages):
        _, data = request("GET", "%s%slimit=%d&offset=%d" % (path, sep, page, off))
        data = data or []
        rows.extend(data)
        if len(data) < page:
            break
        off += page
    return rows


# ───────────── حافظه‌ی محلیِ «قبلاً ارسال شده» (مالک) ─────────────
CACHE_PATH = None          # مسیر فایل JSON؛ برنامه آن را تنظیم می‌کند. None = بدون حافظه (مثل تست‌ها)


def _cache_load():
    if not CACHE_PATH:
        return {"feed": {}, "free": {}}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            c = json.load(f)
        c.setdefault("feed", {})
        c.setdefault("free", {})
        return c
    except Exception:
        return {"feed": {}, "free": {}}


def _cache_save(c):
    if not CACHE_PATH:
        return
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False)
    except Exception:
        pass


# ───────────── سمت مالک ─────────────
def load_accounts(request):
    """[{user_id, email, label, old_user_id, active}] برای همکاران مجاز."""
    _, lst = request("POST", "/rest/v1/rpc/coworker_list", {})
    lst = lst or []
    meta = {r["user_id"]: r for r in get_all(request, "/rest/v1/coworker_accounts?select=*")}
    out = []
    for u in lst:
        m = meta.get(u["user_id"], {})
        out.append({"user_id": u["user_id"], "email": u["email"],
                    "label": m.get("label") or short_name(u["email"]),
                    "old_user_id": m.get("old_user_id") or "",
                    "active": m.get("active", True)})
    return out


def save_account(request, user_id, label, old_user_id=""):
    row = {"user_id": user_id, "label": label or "", "old_user_id": old_user_id or None, "active": True}
    request("POST", "/rest/v1/coworker_accounts?on_conflict=user_id", [row],
            {"Prefer": "resolution=merge-duplicates,return=minimal"})


def load_assignments(request):
    """{(ckey, kind): {'assignee':uid,'name':excel_name}}"""
    rows = get_all(request, "/rest/v1/coworker_customers?select=customer_key,kind,excel_name,assignee")
    return {(r["customer_key"], r["kind"]): {"assignee": r["assignee"], "name": r["excel_name"]} for r in rows}


def suggest_from_old(request, old_user_id, ckeys):
    """مشتری‌هایی (ckey) که در حساب قدیمی همکار حواله داشته‌اند و در اکسل هستند."""
    if not old_user_id:
        return set()
    rows = get_all(request, "/rest/v1/invoices?user_id=eq.%s&select=customer" % old_user_id)
    have = {customer_key(r.get("customer", "")) for r in rows}
    return have & set(ckeys)


def _enc(s):
    from urllib.parse import quote
    return quote(str(s), safe="")


def effective(assignments, ckey):
    """برای یک مشتری: {uid: برچسب} (parquet / mdf / all اگر هر دو گروه به یک نفر رسیده)."""
    per = {}
    for (ck, kd), a in assignments.items():
        if ck == ckey:
            per.setdefault(a["assignee"], set()).add(kd)
    return {u: label_of(k) for u, k in per.items()}


def apply_changes(request, saved, changes, names):
    """changes: {(ckey, kind): uid|None}. هر همکاری که وضعیت مشتری برایش عوض شود
    (حذف یا تغییر برچسب) صف add‌اش پاک و یک revoke برایش ثبت می‌شود؛ حواله‌ی دستی همکار دست نمی‌خورد."""
    new = {k: v for k, v in saved.items()}
    for k, uid in changes.items():
        if uid:
            new[k] = {"assignee": uid, "name": names.get(k[0]) or (saved.get(k) or {}).get("name", "")}
        else:
            new.pop(k, None)
    for ck in {k[0] for k in changes}:
        old_e, new_e = effective(saved, ck), effective(new, ck)
        for uid, lab in old_e.items():
            if new_e.get(uid) != lab:
                _c = _cache_load()
                _c["feed"][uid] = [k for k in _c["feed"].get(uid, []) if not k.startswith(ck + "|")]
                _cache_save(_c)
                request("DELETE", "/rest/v1/sales_feed?assignee=eq.%s&ckey=eq.%s&op=eq.add" % (uid, _enc(ck)),
                        None, {"Prefer": "return=minimal"})
                request("POST", "/rest/v1/sales_feed", [{
                    "assignee": uid, "ckey": ck,
                    "feed_key": "revoke|%s|%s" % (ck, datetime.now().strftime("%Y%m%d%H%M%S%f")),
                    "op": "revoke", "payload": {"name": names.get(ck, "")}}], {"Prefer": "return=minimal"})
    for (ck, kd), uid in changes.items():
        if uid:
            request("POST", "/rest/v1/coworker_customers?on_conflict=customer_key,kind",
                    [{"customer_key": ck, "kind": kd, "excel_name": new[(ck, kd)]["name"], "assignee": uid}],
                    {"Prefer": "resolution=merge-duplicates,return=minimal"})
        else:
            request("DELETE", "/rest/v1/coworker_customers?customer_key=eq.%s&kind=eq.%s" % (_enc(ck), kd),
                    None, {"Prefer": "return=minimal"})
    return new


def sync_feed(request, df, assignments=None, exclude=None, use_cache=True, stats=None):
    """حواله‌های اکسل مشتری‌های واگذارشده را (بدون تکرار) به صف همکارشان اضافه می‌کند. تعداد اضافه‌شده را برمی‌گرداند.
    با use_cache=True آنچه قبلاً ارسال شده از حافظه‌ی محلی می‌آید (فقط موارد جدید به ابر می‌رود)؛
    use_cache=False همه چیز را با ابر تطبیق می‌دهد («ارسال مجدد»)."""
    if assignments is None:
        assignments = load_assignments(request)
    by_assignee = {}
    for (ck, kd), a in assignments.items():
        by_assignee.setdefault(a["assignee"], {}).setdefault(ck, set()).add(kd)
    cache = _cache_load()
    added = 0
    for uid, ck_kinds in by_assignee.items():
        invs = excel_invoices(df, ck_kinds, exclude)
        if stats is not None:
            stats.setdefault(uid, 0)
        if not invs:
            continue
        if use_cache and uid in cache["feed"]:
            existing = set(cache["feed"][uid])
        else:
            existing = {r["feed_key"] for r in get_all(
                request, "/rest/v1/sales_feed?assignee=eq.%s&op=eq.add&select=feed_key" % uid)}
        new = []
        for inv in invs:
            fk = feed_key(inv)
            if fk in existing:
                continue
            existing.add(fk)
            new.append({"assignee": uid, "ckey": inv["ckey"], "feed_key": fk, "op": "add",
                        "payload": {"customer": inv["customer"], "invoice_no": inv["invoice_no"],
                                    "date": inv["date"], "total": inv["total"], "rows": inv["rows"],
                                    "kind": inv["label"]}})
        for i in range(0, len(new), 100):
            request("POST", "/rest/v1/sales_feed?on_conflict=assignee,feed_key", new[i:i + 100],
                    {"Prefer": "resolution=ignore-duplicates,return=minimal"})
        cache["feed"][uid] = sorted(existing)
        added += len(new)
        if stats is not None:
            stats[uid] = len(new)
    _cache_save(cache)
    return added


def pending_counts(request):
    rows = get_all(request, "/rest/v1/sales_feed?status=eq.pending&select=assignee")
    res = {}
    for r in rows:
        res[r["assignee"]] = res.get(r["assignee"], 0) + 1
    return res


# ───────────── سمت همکار ─────────────
def _is_excel_origin(inquiry_data):
    return ('"tab": "%s"' % ORIGIN_TAB) in (inquiry_data or "") or ('"tab":"%s"' % ORIGIN_TAB) in (inquiry_data or "")


def apply_feed(request, uid, conn, now=None):
    """صف در انتظار همکار را روی sqlite محلی اعمال می‌کند. conn = اتصال sqlite (commit با این تابع).
    خروجی: {'added','revoked','skipped'}. کاملاً idempotent."""
    rows = get_all(request, "/rest/v1/sales_feed?assignee=eq.%s&status=eq.pending&select=*&order=id.asc" % uid)
    res = {"added": 0, "revoked": 0, "skipped": 0}
    if not rows:
        return res
    now = now or datetime.now().isoformat(timespec="seconds")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(invoices)").fetchall()]
    for col in ("inquiry_data", "paid_amount"):
        if col not in cols:
            conn.execute("ALTER TABLE invoices ADD COLUMN %s TEXT DEFAULT ''" % col)
    local = conn.execute("SELECT id, customer, invoice_no, date, inquiry_data FROM invoices").fetchall()
    done_ids = []
    for r in rows:
        p = r.get("payload") or {}
        if r["op"] == "add":
            ck = r.get("ckey") or customer_key(p.get("customer", ""))
            no = en_digits(str(p.get("invoice_no", ""))).strip()
            date = str(p.get("date", "")).strip()
            dup = any(customer_key(x[1]) == ck and (en_digits(str(x[2])).strip() == no) for x in local) or \
                any(en_digits(str(x[2])).strip() == no and str(x[3]) == date for x in local)
            if dup:
                res["skipped"] += 1
            else:
                name = p.get("customer", "")
                for x in local:                      # نام استاندارد مشتری = نامی که قبلاً در این برنامه هست
                    if customer_key(x[1]) == ck:
                        name = x[1]
                        break
                total = int(p.get("total") or 0)
                inquiry = json.dumps({"tab": ORIGIN_TAB, "buyer": name, "date": date,
                                      "total": total, "rows": p.get("rows") or [], "kind": p.get("kind", "all")}, ensure_ascii=False)
                cur = conn.execute(
                    "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, no, date, "12:00:00", str(total), now, "", inquiry, str(total)))
                local.append((cur.lastrowid, name, no, date, inquiry))
                res["added"] += 1
        elif r["op"] == "revoke":
            ck = r.get("ckey")
            for x in list(local):
                if customer_key(x[1]) == ck and _is_excel_origin(x[4]):
                    conn.execute("DELETE FROM invoices WHERE id=?", (x[0],))
                    local.remove(x)
                    res["revoked"] += 1
        done_ids.append(r["id"])
    conn.commit()
    # علامت‌گذاری انجام‌شده (پس از commit محلی؛ اگر این مرحله شکست بخورد دفعه‌ی بعد idempotent است)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for i in range(0, len(done_ids), 100):
        ids = ",".join(str(x) for x in done_ids[i:i + 100])
        request("PATCH", "/rest/v1/sales_feed?id=in.(%s)&assignee=eq.%s" % (ids, uid),
                {"status": "applied", "applied_at": stamp}, {"Prefer": "return=minimal"})
    return res


def _fnum(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def _rows_differ(old_rows, new_rows):
    if not isinstance(old_rows, list) or len(old_rows) != len(new_rows):
        return True
    for o, n in zip(old_rows, new_rows):
        if not isinstance(o, dict) or not isinstance(n, dict):
            return True
        if str(o.get("code") or "").strip() != str(n.get("code") or "").strip():
            return True
        for k in ("qty1", "qty2", "price", "cost"):
            if abs(_fnum(o.get(k)) - _fnum(n.get(k))) > 0.00051:
                return True
    return False


def repair_from_feed(request, uid, conn):
    """حواله‌های اکسلیِ موجود در این برنامه را با نسخه‌ی صف ابر (= اکسل مالک) مقایسه می‌کند و اگر فرق داشت یکی می‌کند.
    (برای ردیف‌هایی که بعد از رسیدن، به‌خاطر اصلاح‌های قدیمی کد تغییر کرده‌اند.) خروجی: تعداد حواله‌ی اصلاح‌شده."""
    rows = get_all(request, "/rest/v1/sales_feed?assignee=eq.%s&op=eq.add&select=id,ckey,payload&order=id.asc" % uid)
    truth = {}
    for r in rows:
        p = r.get("payload") or {}
        ck = r.get("ckey") or customer_key(p.get("customer", ""))
        no = en_digits(str(p.get("invoice_no", ""))).strip()
        truth.setdefault((ck, no), p)
    if not truth:
        return 0
    fixed = 0
    for iid, cust, no, total, paid, blob in conn.execute(
            "SELECT id, customer, invoice_no, total, paid_amount, inquiry_data FROM invoices").fetchall():
        if not _is_excel_origin(blob):
            continue
        p = truth.get((customer_key(cust), en_digits(str(no)).strip()))
        if not p:
            continue
        try:
            data = json.loads(blob)
        except Exception:
            continue
        new_rows = p.get("rows") or []
        new_total = int(p.get("total") or 0)
        if new_total <= 0 or not new_rows:
            continue
        if not _rows_differ(data.get("rows"), new_rows) and abs(_fnum(total) - new_total) <= 0.5:
            continue
        data["rows"] = new_rows
        data["total"] = new_total
        pd = str(paid or "")
        if pd.strip() and abs(_fnum(pd) - _fnum(total)) <= 0.5:
            pd = str(new_total)
        conn.execute("UPDATE invoices SET inquiry_data=?, total=?, paid_amount=? WHERE id=?",
                     (json.dumps(data, ensure_ascii=False), str(new_total), pd, iid))
        fixed += 1
    conn.commit()
    return fixed


# ───────────── مقایسه‌ی فروش همکاران و مالک ─────────────
MONTHS_FA = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
             "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
ME_LABEL = "من"


def _num(v):
    try:
        t = en_digits(str(v if v is not None else "")).replace(",", "").replace("٬", "").strip()
        return float(t) if t and t not in ("nan", "None") else 0.0
    except Exception:
        return 0.0


def _doy(m, d):
    return (m - 1) * 31 + d if m <= 6 else 186 + (m - 7) * 30 + d


def _parse_date(s):
    p = en_digits(str(s or "")).strip().split("/")
    if len(p) != 3:
        return None
    try:
        y, m, d = int(p[0]), int(p[1]), int(p[2])
    except Exception:
        return None
    return (y, m, d) if 1 <= m <= 12 and 1 <= d <= 31 else None


def compare_data(df, assignments, labels, exclude=None, year=None, mine=None):
    """فروش هر همکار + مالک (مشتری/گروه‌های واگذارنشده)، بر اساس مبلغ؛ همراه متراژ پارکت (متر مربع) و ورق ام دی اف.
    assignments: {(ckey,kind): {'assignee':uid,...}} ؛ labels: {uid: نام نمایشی}.
    mine: مجموعه‌ی ckey مشتریانِ تیک‌خوردهٔ خود مالک؛ اگر داده شود فقط همین‌ها «من» حساب می‌شوند و بقیه‌ی واگذارنشده‌ها کنار می‌روند.
    خروجی: {'years','year','names','charts':{'total','month','week'}} که هر نمودار
    {'labels':[...], 'series':{name:[[amt, pq, mdf], ...]}} است. «total» تجمعی روزانه است."""
    out = {"years": [], "year": None, "names": [ME_LABEL] + [labels[u] for u in labels],
           "charts": {}}
    if df is None or len(df) == 0 or "مبلغ" not in df.columns or "تاریخ" not in df.columns:
        return out
    qcol = "تعداد_ورق" if "تعداد_ورق" in df.columns else ("تعداد 2" if "تعداد 2" in df.columns else None)
    rows = []
    years = set()
    for rec in df.to_dict("records"):
        dt = _parse_date(rec.get("تاریخ"))
        if not dt:
            continue
        nm = str(rec.get("نام مشتری") or "").strip()
        ck = customer_key(nm)
        if not ck or ck.startswith(STORE_KEY) or (exclude and ck in exclude):
            continue
        kd = row_kind(rec.get("دسته"))
        a = assignments.get((ck, kd))
        if a:
            who = labels.get(a["assignee"])
        else:
            who = ME_LABEL if (mine is None or ck in mine) else None
        if who is None:                        # همکاری که دیگر در فهرست نیست
            continue
        years.add(dt[0])
        pq = _num(rec.get("تعداد 2")) if kd == "parquet" else 0.0
        md = _num(rec.get(qcol)) if (kd == "mdf" and qcol) else 0.0
        rows.append((dt, who, int(round(_num(rec.get("مبلغ")))), pq, md))
    out["years"] = sorted(years)
    if not years:
        return out
    y = year if year in years else max(years)
    out["year"] = y
    names = out["names"]
    rows = [r for r in rows if r[0][0] == y]

    def build(keyfn, label_of_key, cumulative=False, fill=None):
        keys = sorted({keyfn(r[0]) for r in rows})
        if fill is not None:
            keys = fill(keys)
        idx = {k: i for i, k in enumerate(keys)}
        ser = {n: [[0, 0.0, 0.0] for _ in keys] for n in names}
        for dt, who, amt, pq, md in rows:
            c = ser[who][idx[keyfn(dt)]]
            c[0] += amt
            c[1] += pq
            c[2] += md
        if cumulative:
            for n in names:
                run = [0, 0.0, 0.0]
                for c in ser[n]:
                    for j in range(3):
                        run[j] += c[j]
                        c[j] = run[j]
        for n in names:
            for c in ser[n]:
                c[1] = round(c[1], 2)
                c[2] = round(c[2], 2)
        return {"labels": [label_of_key(k) for k in keys], "series": ser}

    # کل = تجمعی روزانه
    out["charts"]["total"] = build(lambda d: (d[1], d[2]), lambda k: "%d/%d" % (k[0], k[1]), cumulative=True)
    out["charts"]["month"] = build(lambda d: d[1], lambda k: MONTHS_FA[k - 1],
                                   fill=lambda ks: list(range(1, (max(ks) if ks else 0) + 1)))
    out["charts"]["week"] = build(lambda d: (_doy(d[1], d[2]) - 1) // 7 + 1, lambda k: _week_label(y, k),
                                  fill=lambda ks: list(range(1, (max(ks) if ks else 0) + 1)))
    return out


def _week_label(y, w):
    try:
        try:
            from .core_utils import jalali_week_range
        except Exception:
            from core_utils import jalali_week_range
        r = jalali_week_range(y, w - 1)
        if r:
            (m1, d1), (m2, d2) = r
            return "%d/%d" % (m1, d1)
    except Exception:
        pass
    return "هفته %d" % w


# ───────────── سمپل و استند همکاران ─────────────
FREE_COLS = ["تاریخ", "نام مشتری", "ماه", "دسته", "نام کالا", "نام برگه", "کد کالا", "تعداد 1", "تعداد 2", "مبلغ"]


def free_rows_for(df, ck_kinds, exclude=None):
    """ردیف‌های با مبلغ صفر مشتری/گروه‌های واگذارشده (ck_kinds={ckey:{kinds}}) → {'cols','rows'} کم‌حجم."""
    out = {"cols": FREE_COLS, "rows": []}
    if df is None or len(df) == 0 or "مبلغ" not in df.columns or "نام مشتری" not in df.columns:
        return out
    d = df
    try:
        amt = d["مبلغ"].map(_num)
        d = d[amt == 0]
    except Exception:
        return out
    if len(d) == 0:
        return out
    cks = d["نام مشتری"].astype(str).map(customer_key)
    kds = _kinds_col(d)
    keep = [(ck in ck_kinds and kd in ck_kinds[ck] and not (exclude and ck in exclude))
            for ck, kd in zip(cks, kds)]
    d = d[keep]
    cols = [c for c in FREE_COLS if c in d.columns]
    rows = []
    for rec in d.to_dict("records"):
        rows.append([("" if rec.get(c) is None else str(rec.get(c))) for c in FREE_COLS if c in cols])
    out["cols"] = cols
    out["rows"] = rows
    return out


def push_free_snapshots(request, df, assignments=None, exclude=None, use_cache=True):
    """برای هر همکار، سمپل/استند مشتریان واگذارشده‌اش را در coworker_snapshots می‌نویسد (مالک)."""
    if assignments is None:
        assignments = load_assignments(request)
    by_assignee = {}
    for (ck, kd), a in assignments.items():
        by_assignee.setdefault(a["assignee"], {}).setdefault(ck, set()).add(kd)
    # همکارانی که قبلاً ردیف داشته‌اند و حالا مشتری ندارند هم خالی می‌شوند
    for r in get_all(request, "/rest/v1/coworker_snapshots?select=assignee"):
        by_assignee.setdefault(r["assignee"], {})
    at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n = 0
    cache = _cache_load()
    import hashlib
    for uid, ck_kinds in by_assignee.items():
        free = free_rows_for(df, ck_kinds, exclude)
        h = hashlib.md5(json.dumps(free, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        if use_cache and cache["free"].get(uid) == h:
            continue                       # تغییری نکرده؛ ارسال نمی‌شود
        cache["free"][uid] = h
        free["at"] = at
        request("POST", "/rest/v1/coworker_snapshots?on_conflict=assignee",
                [{"assignee": uid, "free": free, "updated_at": at}],
                {"Prefer": "resolution=merge-duplicates,return=minimal"})
        n += 1
    _cache_save(cache)
    return n


def fetch_free_df(request, uid):
    """همکار: DataFrame سمپل/استند خودش از ابر (یا None)."""
    import pandas as pd
    _, rows = request("GET", "/rest/v1/coworker_snapshots?assignee=eq.%s&select=free" % uid)
    if not rows:
        return None
    free = rows[0].get("free") or {}
    cols, data = free.get("cols") or FREE_COLS, free.get("rows") or []
    if not data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(data, columns=cols)
    for c in ("تعداد 1", "تعداد 2", "مبلغ"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df
