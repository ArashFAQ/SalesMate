"""مغایرت «تب فروشگاه» با اکسل فروش (بدون Qt — قابل تست). فقط گزارش می‌دهد و چیزی را تغییر نمی‌دهد."""
import zlib

try:
    from core_utils import en_digits, customer_key
except Exception:  # pragma: no cover
    from salesmate.core_utils import en_digits, customer_key


def _inv_no(form, customer, date):
    f = str(form or "").strip()
    if f and f not in ("nan", "None"):
        return en_digits(f)
    return "AN-%s-%s" % (date.replace("/", ""), zlib.crc32((customer + date).encode("utf-8")) % 100000)


def excel_groups(df, store_keys):
    """گروه‌های (مشتری، تاریخ، شماره فرم) اکسل برای مشتریان فروشگاه → [{customer,date,no,total}]."""
    out = []
    if df is None or len(df) == 0 or "نام مشتری" not in df.columns or "مبلغ" not in df.columns:
        return out
    d = df.copy()
    if "شماره فرم" not in d.columns:
        d["شماره فرم"] = ""
    d["_c"] = d["نام مشتری"].astype(str).str.strip()
    d = d[d["_c"].map(customer_key).isin(store_keys)]
    d["تاریخ"] = d["تاریخ"].astype(str).map(lambda x: en_digits(x).strip())
    d["شماره فرم"] = d["شماره فرم"].astype(str)
    for (c, dt, fm), g in d.groupby(["_c", "تاریخ", "شماره فرم"], dropna=False):
        tot = int(round(float(g["مبلغ"].sum())))
        if tot <= 0 or not dt or dt in ("nan", "None"):
            continue
        out.append({"customer": c, "date": dt, "no": _inv_no(fm, c, dt), "total": tot})
    return out


def reconcile(excel, store_rows):
    """store_rows: [{id, customer, date, no, total}]. خروجی: only_store، dup_store (نسخه‌های اضافه)، only_excel."""
    ex_by_key = {}
    for e in excel:
        ex_by_key[(e["date"], e["no"])] = e
    ex_by_ct = {}
    for e in excel:
        ex_by_ct.setdefault((customer_key(e["customer"]), e["date"], e["total"]), e)
    seen = {}
    only_store, dup_store = [], []
    matched = set()
    for r in store_rows:
        key = (r["date"], r["no"])
        k2 = (customer_key(r["customer"]), r["date"], r["total"])
        e = ex_by_key.get(key) or ex_by_ct.get(k2)
        sk = key
        if sk in seen:
            dup_store.append(r)
            continue
        seen[sk] = r
        if e is None:
            only_store.append(r)
        else:
            matched.add((e["date"], e["no"]))
    only_excel = [e for e in excel if (e["date"], e["no"]) not in matched]
    return {"only_store": only_store, "dup_store": dup_store, "only_excel": only_excel}


def total_of(rows, year_prefix=""):
    return sum(r["total"] for r in rows if str(r.get("date", "")).startswith(year_prefix))
