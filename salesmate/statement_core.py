"""صورت‌حساب بدهکاری مشتری (بدون Qt — قابل تست).
حواله‌های تسویه‌نشده + اعتبار (پرداخت اضافه / تعدیل طلبکاری) که فقط به‌صورت مبلغ می‌آید و از جمع کم می‌شود."""
import re
try:
    from core_utils import fa_digits, amount
except Exception:  # pragma: no cover
    from salesmate.core_utils import fa_digits, amount


def _fl(v):
    try:
        return float(str(v).replace(",", "").replace("٬", "").strip() or 0)
    except Exception:
        return 0.0


def _items_of(blob, mdf_fn=None):
    """اقلام حواله برای زیرردیف: [{name, q1, q2, u1, u2, price, cost}] — پارکت: کارتن/متر مربع ، ام دی اف: پالت/ورق."""
    import json
    try:
        d = json.loads(blob) if isinstance(blob, str) else (blob or {})
    except Exception:
        return []
    if not isinstance(d, dict):
        return []
    tab = d.get("tab") or "parquet"
    mdf = tab in ("mdf", "raw")
    if tab == "analysis_import" and mdf_fn:
        try:
            mdf = bool(mdf_fn(d))
        except Exception:
            mdf = False
    u1, u2 = ("پالت", "ورق") if mdf else ("کارتن", "متر مربع")
    out = []
    for r in d.get("rows") or []:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or r.get("type") or "").strip()
        grade = str(r.get("grade") or "").strip()
        if grade:
            name += " (%s)" % grade
        out.append({"name": name, "q1": _fl(r.get("qty1")), "q2": _fl(r.get("qty2")),
                    "u1": u1, "u2": u2, "price": _fl(r.get("price")), "cost": _fl(r.get("cost")),
                    "free": is_free_row(r)})
    return [x for x in out if not x["free"]] + [x for x in out if x["free"]]


def compute_statement(rows, adj=0, mdf_fn=None):
    """rows: [(invoice_no, date, total, paid)] ؛ paid خالی = تسویه. adj: تعدیل دستی (مثبت = بدهکار، منفی = طلبکار).
    خروجی: debts (حواله‌های دارای مانده مثبت)، credit (جمع اعتبار)، extra (تعدیل بدهکاری)، balance."""
    debts = []
    credit = 0
    for rw in rows:
        no, date, total, paid = rw[0], rw[1], rw[2], rw[3]
        blob = rw[4] if len(rw) > 4 else ""
        t = amount(total)
        p = t if paid is None or str(paid).strip() == "" else amount(paid)
        rem = t - p
        if rem > 0:
            debts.append({"no": str(no or ""), "date": str(date or ""), "total": t, "paid": p, "rem": rem,
                          "items": _items_of(blob, mdf_fn) if blob else []})
        elif rem < 0:
            credit += -rem
    adj = amount(adj)
    extra = adj if adj > 0 else 0
    if adj < 0:
        credit += -adj
    debts.sort(key=lambda d: (d["date"], d["no"]))
    balance = sum(d["rem"] for d in debts) + extra - credit
    return {"debts": debts, "credit": credit, "extra": extra, "balance": balance}


def _q(v):
    v = round(float(v or 0), 4)
    t = ("%d" % v) if v == int(v) else ("%.4f" % v).rstrip("0").rstrip(".")
    return fa_digits(t).replace(".", "٫")


def _item_lines(items):
    lines = []
    for it in items:
        parts = [it["name"] or "—"]
        if it["q1"]:
            parts.append("%s %s" % (_q(it["q1"]), it["u1"]))
        if it["q2"]:
            parts.append("%s %s" % (_q(it["q2"]), it["u2"]))
        if it["price"]:
            parts.append("قیمت واحد %s" % _n(it["price"]))
        if it["cost"]:
            parts.append("مبلغ %s" % _n(it["cost"]))
        lines.append("  ·  ".join(parts))
    return lines


def _items_table(items, qt=True):
    """جدول ریز اقلام یک حواله (کوچک، غیر بولد). ستون‌ها: نام کالا | بسته/پالت | متر مربع/ورق | قیمت واحد | مبلغ."""
    u1, u2 = items[0]["u1"], items[0]["u2"]
    heads = ["نام کالا", u1, u2, "قیمت واحد", "مبلغ"]
    widths = ["40%", "10%", "14%", "18%", "18%"]
    aligns = ["right", "center", "center", "center", "center"]
    css = "font-size:10px;font-weight:normal;color:#64748b;padding:2px 4px;"

    def row(vals, extra=""):
        idx = list(range(5))
        if qt:
            idx.reverse()
        return "<tr>%s</tr>" % "".join(
            '<td width="%s" align="%s" style="%s%s">%s</td>' % (widths[i], aligns[i], css, extra, vals[i]) for i in idx)

    out = ['<table width="100%" cellspacing="0" cellpadding="0">']
    out.append(row(heads, "border-bottom:1px solid #cbd5e1;color:#475569;"))
    for it in items:
        out.append(row([it["name"] or "—", _q(it["q1"]) if it["q1"] else "", _q(it["q2"]) if it["q2"] else "",
                        _n(it["price"]) if it["price"] else "", _n(it["cost"]) if it["cost"] else ""],
                       "border-bottom:1px solid #e2e8f0;"))
    out.append("</table>")
    return "".join(out)


def _n(v):
    return fa_digits("{:,}".format(int(v))).replace(",", "٬")


def statement_html(customer, date_str, st, words="", qt=True):
    """HTML هم‌شکل فرم استعلام (نوار آبی، کارت خریدار/تاریخ، جدول، جمع کل).
    بدهکار: جمع کل قرمز. طلبکار (مانده منفی): فقط مبلغ طلب، بدون جزئیات حواله.
    qt=True: ترتیب ستون‌ها برعکس (QTextDocument جهت ستون‌ها را راست‌به‌چپ نمی‌کند)."""
    bal = int(st["balance"])
    is_cred = bal < 0
    blue = "#1565C0"
    red = "#DC2626"
    head = ["ردیف", "شماره حواله", "تاریخ", "مبلغ حواله (ریال)", "پرداخت‌شده (ریال)", "مانده (ریال)"]

    def cells(vals, style, tag="td"):
        vv = list(reversed(vals)) if qt else list(vals)
        return "".join('<%s align="center" style="%s">%s</%s>' % (tag, style, v, tag) for v in vv)

    body = ""
    if not is_cred:
        th = "padding:8px 5px;background:%s;color:white;font-weight:600;font-size:11px;" % blue
        body += "<tr>%s</tr>" % cells(head, th, "th")
        for i, d in enumerate(st["debts"]):
            bg = "#f0f9ff" if i % 2 == 0 else "#ffffff"
            td = "padding:7px 5px;font-size:12px;background:%s;" % bg
            body += "<tr>%s</tr>" % cells([
                fa_digits(i + 1), fa_digits(d["no"]), fa_digits(d["date"]),
                _n(d["total"]), _n(d["paid"]),
                '<b style="color:%s;">%s</b>' % (red, _n(d["rem"])),
            ], td)
            if d.get("items"):
                body += ('<tr><td colspan="6" dir="rtl" style="padding:2px 10px 8px 10px;background:#f8fafc;">%s</td></tr>'
                         % _items_table(d["items"], qt))
    rows_tbl = ('<table width="100%%" cellspacing="0" cellpadding="0" style="border:1px solid #bae6fd;">%s</table>' % body) if body else ""

    sums = []
    if is_cred:
        pass
    elif st["debts"]:
        sums.append(("جمع حواله‌های تسویه‌نشده", _n(sum(d["rem"] for d in st["debts"])), "#0F172A"))
    if st["extra"] and not is_cred:
        sums.append(("تعدیل / بدهی پیشین", _n(st["extra"]), "#0F172A"))
    if st["credit"] and not is_cred:
        sums.append(("طلبکاری (کسر از جمع)", "−" + _n(st["credit"]), "#059669"))
    sum_rows = ""
    for i, (lab, val, col) in enumerate(sums):
        bg = "#f0f9ff" if i % 2 == 0 else "#ffffff"
        a = '<td style="padding:6px 10px;background:%s;color:#64748b;font-size:12px;">%s</td>' % (bg, lab)
        b = '<td align="left" style="padding:6px 10px;background:%s;color:%s;font-weight:bold;font-size:14px;">%s</td>' % (bg, col, val)
        sum_rows += "<tr>%s</tr>" % ((b + a) if qt else (a + b))
    sums_tbl = ('<table width="100%%" cellspacing="0" cellpadding="0">%s</table>' % sum_rows) if sum_rows else ""

    title = "اعلام طلبکاری" if is_cred else "اعلام بدهکاری"
    lab_total = "مبلغ طلب شما" if is_cred else "جمع کل بدهکاری"
    tot_col = "#059669" if is_cred else red
    tot_bg = "#ECFDF5" if is_cred else "#FEF2F2"
    tot_bd = "#A7F3D0" if is_cred else "#FECACA"
    words_html = ('<div style="font-size:13px;color:#475569;margin-top:6px;">%s ریال</div>' % words) if words else ""
    card1 = ('<td width="68%%" style="background:%s;color:white;padding:12px 16px;">'
             '<span style="font-size:11px;">نام مشتری</span><br><b style="font-size:17px;">%s</b></td>' % (blue, customer))
    card2 = ('<td width="32%%" style="background:%s;color:white;padding:12px 16px;" align="center">'
             '<span style="font-size:11px;">تاریخ</span><br><b style="font-size:17px;">%s</b></td>' % (blue, fa_digits(date_str)))
    cards = "<tr>%s</tr>" % ((card2 + card1) if qt else (card1 + card2))
    return (
        '<html><body dir="rtl" style="font-family:Tahoma,Vazirmatn,sans-serif;color:#1e293b;background:#ffffff;">'
        '<table width="100%%" cellspacing="0" cellpadding="0"><tr><td style="background:%s;color:white;padding:12px 18px;">'
        '<b style="font-size:18px;">%s</b></td></tr></table><br>'
        '<table width="100%%" cellspacing="6" cellpadding="0">%s</table><br>'
        '%s<br>%s<br>'
        '<table width="100%%" cellspacing="0" cellpadding="0"><tr><td style="background:%s;border:2px solid %s;padding:14px 18px;">'
        '<span style="font-size:13px;color:#64748b;">%s</span><br>'
        '<b style="font-size:26px;color:%s;">%s ریال</b>%s</td></tr></table>'
        '</body></html>'
    ) % (blue, title, cards, rows_tbl, sums_tbl, tot_bg, tot_bd, lab_total, tot_col, _n(abs(bal)), words_html)


def invoice_chip(total, paid, net):
    """نشان هر حواله در لیست حواله‌ها.
    net = مانده‌ی کل مشتری (مثبت بدهکار، منفی طلبکار).
    برمی‌گرداند: (chip_text, kind, diff_text, diff_kind)
      kind: debt / cred / ok ؛ diff_kind: neg (کمتر پرداخت) / pos (بیشتر پرداخت) / ""
    اگر مانده‌ی کل مشتری صفر است: همه «تسویه»، و اگر پرداخت این حواله با مبلغش فرق دارد
    اختلاف در پرانتز می‌آید ( −کمتر / +بیشتر ).
    اگر مشتری در کل بدهکار/طلبکار است: مثل قبل مانده/بستانکار همین حواله."""
    remain = total - paid
    if net == 0:
        if remain > 0:
            return "تسویه ✓", "ok", "(−%s)" % _grp(remain), "neg"
        if remain < 0:
            return "تسویه ✓", "ok", "(+%s)" % _grp(-remain), "pos"
        return "تسویه ✓", "ok", "", ""
    if remain > 0:
        return "مانده %s" % _grp(remain), "debt", "", ""
    if remain < 0:
        return "بستانکار %s" % _grp(-remain), "cred", "", ""
    return "تسویه ✓", "ok", "", ""


def _grp(n):
    return "{:,}".format(int(round(n)))


def is_sample_name(name):
    """ردیف سمپل؟ (نام کالا «سمپل/سامپل/sample» دارد)"""
    t = str(name or "").lower()
    return ("سمپل" in t) or ("سامپل" in t) or bool(re.search(r"(?<![a-z])sample(?![a-z])", t))


def is_free_row(r):
    """ردیف رایگان (سمپل/استند/نمونه): قیمت و مبلغ صفر، یا نام سمپل."""
    r = r or {}
    if is_sample_name(r.get("name") or r.get("type") or ""):
        return True
    keys = [k for k in ("price", "cost") if k in r]
    if not keys:
        return False
    return all(_fl(r.get(k)) == 0 for k in keys)


def sample_last(rows):
    """ردیف‌های قیمت‌صفر (سمپل/استند/نمونه) همیشه آخر بیایند؛ ترتیب بقیه دست‌نخورده می‌ماند."""
    rows = [r for r in (rows or []) if r is not None]
    return [r for r in rows if not is_free_row(r)] + [r for r in rows if is_free_row(r)]
