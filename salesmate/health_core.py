"""سلامت داده — بررسی‌های خالص (بدون Qt) روی دیتابیس محلی SalesMate. فقط گزارش؛ اصلاح در رابط با پشتیبان و تأیید."""
import re

try:
    from core_utils import customer_key, en_digits, amount
except Exception:  # pragma: no cover
    from salesmate.core_utils import customer_key, en_digits, amount


def name_sig(name):
    """امضای نام: بدون فاصله و خط تیره (همان قاعده‌ی تحلیل فروش)."""
    return re.sub(r"[\s\-_]+", "", customer_key(name))


def _inv_rows(c):
    return [{"id": r[0], "customer": str(r[1] or ""), "no": en_digits(str(r[2] or "")).strip(),
             "date": en_digits(str(r[3] or "")).strip(), "total": int(round(amount(r[4])))}
            for r in c.execute("SELECT id, customer, invoice_no, date, total FROM invoices ORDER BY id").fetchall()]


def invoice_duplicates(c):
    """گروه‌های حواله‌ی تکراری: همان تاریخ + همان شماره‌ی حواله، یا (بدون شماره) همان تاریخ + مبلغ + نام.
    هر گروه: لیست dict؛ اولی (کمترین id) نگه داشته می‌شود."""
    groups = {}
    for r in _inv_rows(c):
        if r["no"] and not r["no"].upper().startswith("AN-"):
            k = ("n", r["date"], r["no"])
        else:
            k = ("c", r["date"], r["total"], name_sig(r["customer"]))
        groups.setdefault(k, []).append(r)
    return [g for g in groups.values() if len(g) > 1]


def name_variants(c):
    """نام‌هایی که یک مشتری‌اند ولی چند جور نوشته شده‌اند (فاصله/خط تیره/ی و ی…).
    خروجی: [[(نام, تعداد)...], ...] فقط گروه‌های با بیش از یک املا."""
    cnt = {}
    for tbl in ("invoices", "store_sales"):
        try:
            for (nm,) in c.execute("SELECT customer FROM %s" % tbl).fetchall():
                nm = str(nm or "").strip()
                if nm:
                    cnt[nm] = cnt.get(nm, 0) + 1
        except Exception:
            pass
    by = {}
    for nm, n in cnt.items():
        by.setdefault(name_sig(nm), []).append((nm, n))
    return [sorted(v, key=lambda x: -x[1]) for v in by.values() if len(v) > 1]


def bad_invoices(c):
    """حواله‌ی بدون نام مشتری یا با مبلغ صفر/خالی."""
    return [r for r in _inv_rows(c) if not r["customer"].strip() or r["total"] <= 0]


def summarize(c):
    d, n, b = invoice_duplicates(c), name_variants(c), bad_invoices(c)
    return {"dup_invoices": d, "name_variants": n, "bad_invoices": b}
