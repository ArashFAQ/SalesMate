"""حواله‌های دو هفته‌ی اخیر یک بخش (پارکت / ام دی اف خام) از دیتافریم تحلیل فروش — بدون Qt، قابل تست."""
import re

_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _num(v):
    try:
        return float(str(v).translate(_FA).replace(",", "").replace("٬", "").strip() or 0)
    except Exception:
        return 0.0


def _ymd(s):
    p = re.split(r"[/\-]", str(s or "").translate(_FA).strip())
    try:
        return int(p[0]), int(p[1]), int(p[2])
    except Exception:
        return None


def _ordinal(y, m, d):
    days = (m - 1) * 31 if m <= 7 else 6 * 31 + (m - 7) * 30
    return y * 366 + days + d


def recent_invoices(records, days=14, date_from=None, date_to=None):
    """records: لیست dict با کلیدهای تاریخ، شماره فرم، نام مشتری، تعداد 1، تعداد 2، مبلغ.
    پنجره = «days» روز منتهی به آخرین تاریخ همان بخش. هر حواله (تاریخ + شماره + مشتری) یک ردیف.
    خروجی: {"rows": [...جدیدترین اول], "from": str, "to": str, "tot": {q1, q2, amount, n}}"""
    items = []
    for r in records or []:
        ymd = _ymd(r.get("تاریخ"))
        if ymd:
            items.append((ymd, r))
    if not items:
        return {"rows": [], "from": "", "to": "", "tot": {"q1": 0, "q2": 0, "amount": 0, "n": 0}}
    last = max(i[0] for i in items)
    d1, d2 = _ymd(date_from), _ymd(date_to)
    if d1 or d2:                      # بازه‌ی دلخواه
        lo = _ordinal(*d1) if d1 else -10 ** 9
        hi = _ordinal(*d2) if d2 else 10 ** 9
        last = d2 or last
    else:
        lo = _ordinal(*last) - (days - 1)
        hi = 10 ** 9
    groups = {}
    for ymd, r in items:
        if _ordinal(*ymd) < lo or _ordinal(*ymd) > hi:
            continue
        date = "%04d/%02d/%02d" % ymd
        no = str(r.get("شماره فرم") or "").translate(_FA).strip()
        no = re.sub(r"\.0$", "", no) or "—"
        cust = str(r.get("نام مشتری") or "").strip()
        g = groups.setdefault((date, no, cust), {"date": date, "no": no, "customer": cust,
                                                  "q1": 0.0, "q2": 0.0, "amount": 0.0, "n": 0})
        g["q1"] += _num(r.get("تعداد 1"))
        g["q2"] += _num(r.get("تعداد 2"))
        g["amount"] += _num(r.get("مبلغ"))
        g["n"] += 1

    def _nokey(g):
        m = re.findall(r"\d+", g["no"])
        return int(m[-1]) if m else 0
    rows = sorted(groups.values(), key=lambda g: (g["date"], _nokey(g)), reverse=True)
    tot = {"q1": sum(g["q1"] for g in rows), "q2": sum(g["q2"] for g in rows),
           "amount": sum(g["amount"] for g in rows), "n": len(rows)}
    return {"rows": rows, "from": rows[-1]["date"] if rows else "", "to": "%04d/%02d/%02d" % last, "tot": tot}
