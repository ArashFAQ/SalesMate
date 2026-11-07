# -*- coding: utf-8 -*-
"""منطق خالص (بدون Qt) برای:
  • گزارش بعد از بارگذاری اکسل تحلیل فروش
  • شناسایی سمپل / استند / نمونه (ردیف‌های با قیمت صفر) و خلاصه‌ی هر مشتری
"""
import html as _html
import re



class _LazyPandas:
    """pandas فقط هنگام اولین استفاده وارد می‌شود (راه‌اندازی سریع‌تر برنامه)."""
    def __getattr__(self, name):
        import pandas
        globals()["pd"] = pandas
        return getattr(pandas, name)


pd = _LazyPandas()

try:
    from core_utils import customer_key, en_digits
except Exception:  # pragma: no cover
    from salesmate.core_utils import customer_key, en_digits

FREE_TYPES = ("سمپل", "استند", "نمونه")
OTHER_FREE = "سایر"          # ردیف با قیمت صفر که جزو سه نوع بالا نیست


# ───────────────────────── شناسایی نوع ─────────────────────────

def _norm_text(s):
    return customer_key(s)


def classify_free_item(name="", sheet="", code=""):
    """نوع ردیف صفرتومانی: «سمپل» | «استند» | «نمونه» | «» (نامشخص).
    اول نام کالا، بعد نام برگه، بعد کد بررسی می‌شود."""
    for raw in (name, sheet, code):
        t = _norm_text(raw)
        if not t:
            continue
        if "سمپل" in t or "سامپل" in t or re.search(r"(?<![a-z])sample(?![a-z])", t):
            return "سمپل"
        if "استند" in t or "استاند" in t or re.search(r"(?<![a-z])stand(?![a-z])", t):
            return "استند"
        if "نمونه" in t:
            return "نمونه"
    return ""


def _num_col(df, col):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return pd.Series(0.0, index=df.index)


def _date_str(x):
    return en_digits(str(x if x is not None else "")).strip()


# ───────────────────────── خلاصه‌ی سمپل/استند ─────────────────────────

def free_item_rows(df):
    """فقط ردیف‌های با مبلغ صفر، با ستون‌های کمکی: _type (سمپل/استند/نمونه/سایر), _units, _ds, _key."""
    if df is None or getattr(df, "empty", True) or "مبلغ" not in df.columns:
        return pd.DataFrame()
    z = df[_num_col(df, "مبلغ") == 0].copy()
    if z.empty:
        return z
    name = z["نام کالا"].astype(str) if "نام کالا" in z.columns else pd.Series("", index=z.index)
    sheet = z["نام برگه"].astype(str) if "نام برگه" in z.columns else pd.Series("", index=z.index)
    code = z["کد کالا"].astype(str) if "کد کالا" in z.columns else pd.Series("", index=z.index)
    cache = {}
    types = []
    for n, s, c in zip(name, sheet, code):
        k = (n, s, c)
        if k not in cache:
            cache[k] = classify_free_item(n, s, c) or OTHER_FREE
        types.append(cache[k])
    z["_type"] = types
    q = _num_col(z, "تعداد 1")
    z["_units"] = q.where(q > 0, 1.0)
    z["_ds"] = z["تاریخ"].map(_date_str) if "تاریخ" in z.columns else ""
    cust = z["نام مشتری"].astype(str).str.strip() if "نام مشتری" in z.columns else pd.Series("", index=z.index)
    z["_cust"] = cust
    z["_key"] = cust.map(customer_key)
    z["_m"] = _num_col(z, "تعداد 2")
    return z


CATEGORY_CHOICES = ("همه", "پارکت", "ام دی اف", "سایر")


def filter_category(z, category):
    """فیلتر دسته روی ردیف‌های free_item_rows. «سایر» = هر دسته‌ای جز پارکت و ام دی اف."""
    if z is None or getattr(z, "empty", True) or not category or category == "همه" or "دسته" not in z.columns:
        return z
    cat = z["دسته"].astype(str)
    if category == "سایر":
        return z[~cat.isin(["پارکت", "ام دی اف"])]
    return z[cat == category]


def free_items_by_customer(df, month=None, search="", category=None):
    """جدول هر مشتری: تعداد سمپل/استند/نمونه/سایر + جمع، متراژ، تعداد ردیف، آخرین تاریخ.
    month: مقدار ستون «ماه» برای فیلتر (None = همه). search: بخشی از نام مشتری.
    category: «پارکت» | «ام دی اف» | «سایر» | None/«همه»."""
    z = free_item_rows(df)
    cols = ["مشتری", "سمپل", "استند", "نمونه", OTHER_FREE, "جمع", "ردیف", "متراژ", "آخرین تاریخ", "_key"]
    if z.empty:
        return pd.DataFrame(columns=cols)
    if month and month != "همه" and "ماه" in z.columns:
        z = z[z["ماه"].astype(str) == str(month)]
    z = filter_category(z, category)
    s = customer_key(search) if search else ""
    if s:
        z = z[z["_key"].str.contains(re.escape(s), na=False)]
    if z.empty:
        return pd.DataFrame(columns=cols)
    out = []
    for key, g in z.groupby("_key", dropna=False):
        shown = g["_cust"].value_counts().index[0] if not g["_cust"].empty else str(key)
        row = {"مشتری": shown, "_key": key}
        for t in FREE_TYPES + (OTHER_FREE,):
            row[t] = float(g.loc[g["_type"] == t, "_units"].sum())
        row["جمع"] = float(g["_units"].sum())
        row["ردیف"] = int(len(g))
        row["متراژ"] = float(g["_m"].sum())
        ds = [d for d in g["_ds"] if d]
        row["آخرین تاریخ"] = max(ds) if ds else ""
        out.append(row)
    res = pd.DataFrame(out, columns=cols)
    return res.sort_values(["جمع", "مشتری"], ascending=[False, True]).reset_index(drop=True)


def free_items_of_customer(df, key):
    """ردیف‌های ریز یک مشتری (برای پنجره‌ی جزئیات)."""
    z = free_item_rows(df)
    if z.empty:
        return z
    z = z[z["_key"] == key]
    return z.sort_values("_ds", ascending=False)


# ───────────────────────── گزارش بارگذاری ─────────────────────────

def build_upload_report(old_df, new_df, merged_df, replace=False, files=None, errors=None, dup_removed=0):
    """old_df: داده‌ی قبل از بارگذاری؛ new_df: ردیف‌های فایل‌های جدید (بعد از حذف تکراری داخل خودشان)؛
    merged_df: داده‌ی نهایی. files = [(نام فایل, تعداد ردیف خوانده‌شده)]."""
    rep = {
        "files": list(files or []),
        "errors": list(errors or []),
        "replace": bool(replace),
        "dup_removed": int(dup_removed or 0),
        "total_rows": int(len(merged_df)) if merged_df is not None else 0,
    }
    old_empty = old_df is None or getattr(old_df, "empty", True)
    if replace or old_empty or "unique_key" not in new_df.columns:
        fresh = new_df
    else:
        fresh = new_df[~new_df["unique_key"].isin(set(old_df["unique_key"]))]
    rep["read_rows"] = int(sum(n for _, n in rep["files"])) if rep["files"] else int(len(new_df))
    rep["new_rows"] = int(len(fresh))
    rep["existing_rows"] = int(len(new_df) - len(fresh))

    rep["amount"] = float(_num_col(fresh, "مبلغ").sum()) if len(fresh) else 0.0
    ds = [d for d in (fresh["تاریخ"].map(_date_str) if "تاریخ" in fresh.columns else []) if d]
    rep["date_from"] = min(ds) if ds else ""
    rep["date_to"] = max(ds) if ds else ""
    rep["customers"] = int(fresh["نام مشتری"].map(customer_key).nunique()) if (len(fresh) and "نام مشتری" in fresh.columns) else 0

    cats = []
    if len(fresh) and "دسته" in fresh.columns:
        tmp = fresh.assign(_a=_num_col(fresh, "مبلغ"), _m=_num_col(fresh, "تعداد_ورق"))
        for cat, g in tmp.groupby("دسته", dropna=False):
            cats.append((str(cat), int(len(g)), float(g["_a"].sum()), float(g["_m"].sum())))
        cats.sort(key=lambda x: -x[2])
    rep["categories"] = cats

    # مشتریان جدید (که قبلاً در داده نبودند)
    new_cust = []
    if (not replace) and (not old_empty) and len(fresh) and "نام مشتری" in fresh.columns and "نام مشتری" in old_df.columns:
        old_keys = set(old_df["نام مشتری"].map(customer_key))
        seen = {}
        for nm in fresh["نام مشتری"].astype(str).str.strip():
            k = customer_key(nm)
            if k and k not in old_keys and k not in seen:
                seen[k] = nm
        new_cust = list(seen.values())
    rep["new_customers"] = new_cust

    # ردیف‌های با مبلغ صفر (سمپل/استند/نمونه/...)
    z = free_item_rows(fresh)
    free_counts = {t: 0 for t in FREE_TYPES + (OTHER_FREE,)}
    other_names = []
    if not z.empty:
        for t, g in z.groupby("_type"):
            free_counts[t] = int(len(g))
        og = z[z["_type"] == OTHER_FREE]
        if "نام کالا" in og.columns:
            other_names = [str(x) for x in og["نام کالا"].astype(str).value_counts().head(5).index]
    rep["zero_rows"] = int(len(z))
    rep["free_counts"] = free_counts
    rep["other_zero_names"] = other_names
    rep["auto"] = {}
    rep["cloud"] = ""
    return rep


def _fa(n):
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _fmt(n):
    try:
        return _fa(f"{int(round(float(n))):,}")
    except Exception:
        return _fa(n)


def report_to_html(rep):
    e = _html.escape
    h = ["<div dir='rtl' style='font-size:13px;line-height:1.9;'>"]
    h.append("<h3 style='margin:0 0 6px 0;'>گزارش بارگذاری اکسل</h3>")
    mode = "جایگزین داده‌ی قبلی شد" if rep.get("replace") else "به داده‌ی قبلی اضافه شد"
    h.append(f"<div style='color:#64748B;'>{e(mode)} · جمع کل داده: <b>{_fmt(rep.get('total_rows', 0))}</b> ردیف</div>")
    h.append("<hr>")

    if rep.get("files"):
        h.append("<b>فایل‌ها</b><ul style='margin:2px 0;'>")
        for name, n in rep["files"]:
            h.append(f"<li>{e(str(name))} — {_fmt(n)} ردیف</li>")
        h.append("</ul>")
    for er in rep.get("errors", []):
        h.append(f"<div style='color:#B91C1C;'>⚠ {e(str(er))}</div>")

    h.append("<b>نتیجه</b><ul style='margin:2px 0;'>")
    h.append(f"<li>ردیف جدید اضافه‌شده: <b>{_fmt(rep.get('new_rows', 0))}</b></li>")
    ex = rep.get("existing_rows", 0)
    dup = rep.get("dup_removed", 0)
    if ex or dup:
        h.append(f"<li>ردیف تکراری ردشده: <b>{_fmt(dup)}</b> (از جمله {_fmt(ex)} ردیف که از قبل در داده بود)</li>")
    if rep.get("new_rows"):
        h.append(f"<li>مبلغ ردیف‌های جدید: <b>{_fmt(rep.get('amount', 0))}</b> ریال</li>")
        if rep.get("date_from"):
            h.append(f"<li>بازه‌ی تاریخ ردیف‌های جدید: {_fa(e(rep['date_from']))} تا {_fa(e(rep['date_to']))}</li>")
        h.append(f"<li>تعداد مشتریان در ردیف‌های جدید: {_fmt(rep.get('customers', 0))}</li>")
    h.append("</ul>")

    if rep.get("categories"):
        h.append("<b>به تفکیک دسته</b><table cellspacing='4' dir='rtl'>")
        h.append("<tr><td><b>دسته</b></td><td><b>ردیف</b></td><td><b>مبلغ (ریال)</b></td><td><b>متراژ/ورق</b></td></tr>")
        for cat, n, a, m in rep["categories"]:
            h.append(f"<tr><td>{e(cat)}</td><td>{_fmt(n)}</td><td>{_fmt(a)}</td><td>{_fa(('%g' % round(m, 2)) if m else '0')}</td></tr>")
        h.append("</table>")

    nc = rep.get("new_customers") or []
    if nc:
        shown = "، ".join(e(x) for x in nc[:15])
        more = f" و {_fmt(len(nc) - 15)} مورد دیگر" if len(nc) > 15 else ""
        h.append(f"<div style='margin-top:6px;'><b>مشتریان جدید ({_fmt(len(nc))}):</b> {shown}{more}</div>")

    if rep.get("zero_rows"):
        fc = rep.get("free_counts", {})
        parts = [f"{t}: <b>{_fmt(fc.get(t, 0))}</b>" for t in FREE_TYPES + (OTHER_FREE,) if fc.get(t, 0)]
        h.append(f"<div style='margin-top:6px;'><b>ردیف‌های با مبلغ صفر ({_fmt(rep['zero_rows'])}):</b> " + " · ".join(parts)
                 + " <span style='color:#64748B;'>— در آمار فروش حساب نمی‌شوند؛ در بخش «سمپل و استند» دیده می‌شوند.</span></div>")
        if rep.get("other_zero_names"):
            h.append("<div style='color:#64748B;'>نمونه کالاهای صفرِ نامشخص: " + "، ".join(e(x) for x in rep["other_zero_names"]) + "</div>")

    a = rep.get("auto") or {}
    if a and a.get("customers"):
        h.append("<hr><b>ورود خودکار به SalesMate</b><ul style='margin:2px 0;'>")
        h.append(f"<li>مشتریان تیک‌خورده: {_fmt(a.get('customers', 0))}</li>")
        h.append(f"<li>حواله/فروش جدید اضافه‌شده: <b>{_fmt(a.get('added', 0))}</b>"
                 + (f" (از جمله {_fmt(a.get('store', 0))} در فروشگاه)" if a.get("store") else "") + "</li>")
        h.append(f"<li>تکراری ردشده: {_fmt(a.get('skipped', 0))}</li>")
        if a.get("fixed"):
            h.append(f"<li style='color:#B45309;'>حواله‌ی موجودِ اصلاح‌شده با اکسل: {_fmt(a.get('fixed', 0))}</li>")
        h.append("</ul>")
    if a and (a.get("cw_by") or a.get("cw_skipped") or a.get("cw_error")):
        h.append("<hr><b>ارسال حواله به همکاران</b><ul style='margin:2px 0;'>")
        by = a.get("cw_by") or []
        if by:
            for nm, n in by:
                h.append(f"<li>{e(str(nm))}: <b>{_fmt(n)}</b> حواله‌ی جدید</li>")
            h.append(f"<li>جمع: <b>{_fmt(sum(int(n) for _, n in by))}</b> حواله</li>")
        else:
            h.append("<li>حواله‌ی جدیدی برای همکاران نبود.</li>")
        if a.get("cw_skipped"):
            h.append(f"<li style='color:#64748B;'>{_fmt(a.get('cw_skipped'))} مشتری دارای ردیف واگذارشده به همکار (آن ردیف‌ها وارد حواله‌های خودتان نشد)</li>")
        if a.get("cw_error"):
            h.append(f"<li style='color:#DC2626;'>خطا در ارسال به همکاران: {e(str(a.get('cw_error')))}</li>")
        h.append("</ul>")
    if rep.get("cloud"):
        h.append(f"<div style='margin-top:4px;'>☁ {e(rep['cloud'])}</div>")
    h.append("</div>")
    return "".join(h)


# ───────────────────────── تفکیک سمپل/استند یک مشتری ─────────────────────────

def free_items_breakdown(z):
    """z: ریزردیف‌های یک مشتری (خروجی free_items_of_customer، احتمالاً فیلترشده).
    خروجی: (جمع هر نوع {نوع: تعداد}, جدول کالاها: لیست dict با کلیدهای کالا/نوع/تعداد/متراژ/ردیف — از زیاد به کم)."""
    totals = {t: 0.0 for t in FREE_TYPES + (OTHER_FREE,)}
    if z is None or getattr(z, "empty", True):
        return totals, []
    for t, g in z.groupby("_type"):
        totals[str(t)] = totals.get(str(t), 0.0) + float(g["_units"].sum())
    name_col = "نام کالا" if "نام کالا" in z.columns else None
    rows = {}
    for rec in z.to_dict("records"):
        nm = str(rec.get("نام کالا", "") or "").strip() if name_col else ""
        k = (nm, str(rec.get("_type", "")))
        r = rows.setdefault(k, {"کالا": nm or "—", "نوع": k[1], "تعداد": 0.0, "متراژ": 0.0, "ردیف": 0})
        r["تعداد"] += float(rec.get("_units", 0) or 0)
        r["متراژ"] += float(rec.get("_m", 0) or 0)
        r["ردیف"] += 1
    out = sorted(rows.values(), key=lambda r: (-r["تعداد"], r["کالا"]))
    return totals, out


# ───────────────────────── خروجی اکسل حواله‌ها به تفکیک ماه ─────────────────────────

def invoice_meters(inquiry_data):
    """جمع متراژ (qty2) ردیف‌های استعلام یک حواله."""
    import json
    try:
        data = inquiry_data
        if isinstance(data, str):
            data = json.loads(data) if data.strip() else {}
        if not isinstance(data, dict):
            return 0.0
        m = 0.0
        for r in (data.get("rows") or []):
            try:
                m += float(re.sub(r"[^0-9.\-]", "", _en(str(r.get("qty2") or "0"))) or 0)
            except Exception:
                pass
        return m
    except Exception:
        return 0.0


def _en(s):
    return str(s).translate({ord(c): str(i) for i, c in enumerate("۰۱۲۳۴۵۶۷۸۹")}).translate(
        {ord(c): str(i) for i, c in enumerate("٠١٢٣٤٥٦٧٨٩")}).replace("٬", "").replace(",", "")


def group_invoices_by_month(rows, amount_fn):
    """rows: (id, customer, invoice_no, date, time, total, inquiry_data). ماه‌ها از جدید به قدیم (بدون تاریخ آخر)؛
    داخل هر ماه به ترتیب شماره حواله (بزرگ به کوچک).
    خروجی: لیست dict(year, month, rows=[(id, customer, no, date, meters, amount)], amount, meters) + جمع کل."""
    groups = {}
    for (iid, cust, no, date, _tm, total, inq) in rows:
        d = _en(date or "").strip()
        parts = d.split("/")
        try:
            key = (int(parts[0]), int(parts[1]))
        except Exception:
            key = (0, 0)
        groups.setdefault(key, []).append((iid, cust or "", str(no or ""), str(date or ""),
                                           invoice_meters(inq), float(amount_fn(total) or 0)))

    def nokey(r):
        nums = re.findall(r"\d+", _en(r[2]))
        return (0, int(nums[-1])) if nums else (1, 0)

    out = []
    for key in sorted((k for k in groups if k != (0, 0)), reverse=True) + ([(0, 0)] if (0, 0) in groups else []):
        rs = sorted(groups[key], key=nokey, reverse=True)
        out.append({"year": key[0], "month": key[1], "rows": rs,
                    "amount": sum(r[5] for r in rs), "meters": sum(r[4] for r in rs)})
    total = {"amount": sum(g["amount"] for g in out), "meters": sum(g["meters"] for g in out),
             "count": sum(len(g["rows"]) for g in out)}
    return out, total
