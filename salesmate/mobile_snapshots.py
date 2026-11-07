# -*- coding: utf-8 -*-
"""ساخت و ارسال «اسنپ‌شات»های فقط‌خواندنی برای اپ موبایل.

اپ موبایل فقط از ابر می‌خواند. داده‌هایی که در ابر جدول مستقیم ندارند (آمار فروش پارکت، سمپل/استند،
بالانس موجودی) اینجا فشرده می‌شوند و در جدول mobile_snapshots (کلید → JSON) ذخیره می‌شوند.
منطق خالص است (بدون Qt) و تست‌پذیر."""
import json
from datetime import datetime, timezone

try:
    from core_utils import amount, en_digits, customer_key
    import sales_extras as se
    import inventory_core as ic
except Exception:  # pragma: no cover
    from salesmate.core_utils import amount, en_digits, customer_key
    from salesmate import sales_extras as se
    from salesmate import inventory_core as ic

SNAPSHOT_TABLE = "mobile_snapshots"
KEYS = ("parquet_sales", "free_items", "balance", "sales_report")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _num(x):
    try:
        return float(en_digits(str(x if x is not None else 0)).replace(",", "").replace("٬", "") or 0)
    except Exception:
        return 0.0


class _Dict:
    """جدول مقدارها → شاخص (برای کم‌کردن حجم JSON)."""

    def __init__(self):
        self.items, self.idx = [], {}

    def add(self, v):
        v = str(v or "")
        i = self.idx.get(v)
        if i is None:
            i = len(self.items)
            self.idx[v] = i
            self.items.append(v)
        return i


def build_parquet_snapshot(df, norm_customer=None):
    """فروش پارکت (مبلغ ≠ ۰) تجمیع‌شده بر اساس (تاریخ، مشتری، کد، کالا).
    ردیف: [تاریخ, ش.مشتری, کد, ش.کالا, مبلغ, متراژ]. None اگر داده نبود."""
    if df is None or getattr(df, "empty", True):
        return None
    pdf = df
    if "دسته" in pdf.columns:
        pdf = pdf[pdf["دسته"].astype(str).str.contains("پارکت", na=False)]
    if pdf.empty or "مبلغ" not in pdf.columns:
        return None
    norm = norm_customer or (lambda s: str(s or "").strip())
    cust_col = "نام مشتری" if "نام مشتری" in pdf.columns else None
    mcol = "تعداد_ورق" if "تعداد_ورق" in pdf.columns else ("تعداد 2" if "تعداد 2" in pdf.columns else None)
    agg = {}
    custs, names = _Dict(), _Dict()
    for rec in pdf.to_dict("records"):
        amt = amount(rec.get("مبلغ"))
        if not amt:
            continue
        d = en_digits(str(rec.get("تاریخ") or "")).strip()
        c = norm(rec.get(cust_col)) if cust_col else "فروشگاه ایزوفام"
        code = en_digits(str(rec.get("کد کالا") or "")).strip()
        nm = str(rec.get("نام کالا") or "").strip()
        k = (d, custs.add(c), code, names.add(nm))
        a = agg.setdefault(k, [0, 0.0])
        a[0] += amt
        a[1] += _num(rec.get(mcol)) if mcol else 0.0
    if not agg:
        return None
    rows = [[k[0], k[1], k[2], k[3], int(v[0]), round(v[1], 3)] for k, v in agg.items()]
    rows.sort(key=lambda r: (r[0], r[1]))
    return {"v": 1, "at": _now(), "customers": custs.items, "names": names.items, "rows": rows}


def build_free_snapshot(df):
    """سمپل/استند/نمونه: ردیف [تاریخ, ش.مشتری, ماه, دسته, نوع, ش.کالا, تعداد, متراژ]."""
    z = se.free_item_rows(df)
    if z is None or getattr(z, "empty", True):
        return None
    custs, names = _Dict(), _Dict()
    agg = {}
    for rec in z.to_dict("records"):
        k = (
            str(rec.get("_ds") or ""),
            custs.add(str(rec.get("_cust") or "").strip()),
            str(rec.get("ماه") or ""),
            str(rec.get("دسته") or ""),
            str(rec.get("_type") or ""),
            names.add(str(rec.get("نام کالا") or "").strip()),
        )
        a = agg.setdefault(k, [0.0, 0.0])
        a[0] += float(rec.get("_units") or 0)
        a[1] += float(rec.get("_m") or 0)
    rows = [list(k) + [round(v[0], 3), round(v[1], 3)] for k, v in agg.items()]
    rows.sort(key=lambda r: (r[0], r[1]))
    return {"v": 1, "at": _now(), "customers": custs.items, "names": names.items, "rows": rows}


def build_sales_report_snapshot(df):
    """گزارش فروش کل شرکت / ام‌دی‌اف خام / ام‌دی‌اف (هایگلاس و ملامینه) — بدون ریز حواله.
    ردیف: [تاریخ, گروه, مبلغ, ورق]؛ گروه‌ها: all (همه‌ی دسته‌ها به‌جز پارکت)، raw (خام)، hg (ام‌دی‌اف هایگلاس)،
    mel (بقیه‌ی ام‌دی‌اف = ملامینه). تجمیع روزانه است؛ هفته/ماه را موبایل از تاریخ می‌سازد."""
    if df is None or getattr(df, "empty", True) or "مبلغ" not in df.columns or "تاریخ" not in df.columns:
        return None
    qcol = "تعداد_ورق" if "تعداد_ورق" in df.columns else ("تعداد 2" if "تعداد 2" in df.columns else None)
    agg = {}
    for rec in df.to_dict("records"):
        d = en_digits(str(rec.get("تاریخ") or "")).strip()
        if len(d.split("/")) != 3:
            continue
        amt = amount(rec.get("مبلغ"))
        q = _num(rec.get(qcol)) if qcol else 0.0
        cat = str(rec.get("دسته") or "")
        name = str(rec.get("نام کالا") or "")
        groups = [] if "پارکت" in cat else ["all"]      # فروش کل شرکت بدون پارکت (مبلغ + ورق)
        if cat == "خام":
            groups.append("raw")
        elif cat == "ام دی اف":
            groups.append("hg" if "هایگلاس" in name else "mel")
        for g in groups:
            a = agg.setdefault((d, g), [0, 0.0])
            a[0] += amt
            a[1] += q
    if not agg:
        return None
    rows = [[k[0], k[1], int(v[0]), round(v[1], 3)] for k, v in agg.items()]
    rows.sort(key=lambda r: (r[0], r[1]))
    return {"v": 1, "at": _now(), "rows": rows}


def build_balance_snapshot(store):
    """آخرین نتیجه‌ی بالانس موجودی (همان مقایسه‌ی صفحه‌ی بالانس)."""
    if not isinstance(store, dict):
        return None
    system, warehouse = store.get("system") or {}, store.get("warehouse") or {}
    if not system:
        return None
    th = float(store.get("threshold") or 0.0)
    res = ic.compare(system, warehouse, ic.normalize_mappings(store.get("mappings")), th)
    out = []
    for r in res:
        out.append({
            "wh": r["warehouse"], "code": r["sysCode"], "desc": r.get("desc", ""),
            "sys": r["sysQty"], "whCode": r.get("whCode", ""), "whName": r.get("whName", ""),
            "whQty": r["whQty"], "diff": r["diff"], "action": r["action"], "mapped": bool(r["mapped"]),
            "st": ic.result_status(r),
        })
    return {"v": 1, "at": _now(), "dataReadAt": store.get("dataReadAt", ""), "docDate": store.get("docDate", ""),
            "threshold": th, "stats": ic.result_stats(res), "results": out}


def build_all(df, store, norm_customer=None):
    """{کلید: payload} برای همه‌ی اسنپ‌شات‌هایی که داده دارند."""
    out = {}
    for key, fn in (
        ("parquet_sales", lambda: build_parquet_snapshot(df, norm_customer)),
        ("free_items", lambda: build_free_snapshot(df)),
        ("sales_report", lambda: build_sales_report_snapshot(df)),
        ("balance", lambda: build_balance_snapshot(store)),
    ):
        try:
            v = fn()
        except Exception:
            v = None
        if v:
            out[key] = v
    return out


def push_snapshots(request, snaps, last_hash=None):
    """upsert هر اسنپ‌شات. request(method, path, body, extra_headers). اگر محتوا (بدون زمان) تغییر نکرده باشد ارسال نمی‌شود.
    خروجی: (لیست کلیدهای ارسال‌شده, هش‌های جدید)."""
    sent, hashes = [], dict(last_hash or {})
    for key, payload in snaps.items():
        core = {k: v for k, v in payload.items() if k != "at"}
        h = json.dumps(core, ensure_ascii=False, sort_keys=True)
        if hashes.get(key) == h:
            continue
        body = [{"key": key, "payload": payload, "updated_at": _now()}]
        request("POST", "/rest/v1/%s?on_conflict=key" % SNAPSHOT_TABLE, body,
                {"Prefer": "resolution=merge-duplicates,return=minimal"})
        hashes[key] = h
        sent.append(key)
    return sent, hashes
