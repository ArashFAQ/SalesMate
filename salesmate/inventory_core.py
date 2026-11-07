# -*- coding: utf-8 -*-
"""بالانس موجودی (سامانه ↔ انبار) — منطق خالص و بدون Qt.

جریان کار (همان منطق ابزار قدیمی، بازنویسی‌شده):
  ۱) برای هر انبار دو فایل اکسل: «سامانه» (کد، شرح، موجودی m³) و «انبار» (کد، نام، واحد، تعداد → m³).
  ۲) هر کد سامانه به یک یا چند کد انبار «نگاشت» می‌شود؛ موجودی کدهای انبار جمع می‌شود.
  ۳) مقایسه: اختلاف = جمع انبار − سامانه؛ اختلاف کمتر از آستانه صفر حساب می‌شود.
  ۴) خروجی: اظهار خروج (xlsx)، PDF، اکسل کامل.
"""
import csv
import io
import json
import os
import re
import tempfile
from datetime import datetime
from html.parser import HTMLParser

try:
    from core_utils import en_digits
except Exception:  # pragma: no cover
    from salesmate.core_utils import en_digits

WAREHOUSES = ["بهارستان", "گلسرخ", "خلیج", "گلشن"]
WH_KEYS = {"بهارستان": "bahar", "گلسرخ": "gol", "خلیج": "khalij", "گلشن": "golshan"}
POSTAL = {"بهارستان": "1834179435", "گلسرخ": "1834185391", "خلیج": "1378946463", "گلشن": "1834167115"}
PALLET_SHEETS = 48            # هر پالت = ۴۸ ورق (وقتی تعداد ورق در فایل نیست)
STORE_VERSION = 1


class FileFormatError(Exception):
    pass


# ───────────────────────── کمک‌ها ─────────────────────────

def cell_str(v):
    """مقدار سلول → متن (عدد صحیح اعشاری مثل 123.0 → «123»)."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        if v != v:                      # NaN
            return ""
        if v == int(v):
            return str(int(v))
        return repr(v)
    return str(v).strip()


def to_num(v):
    """مقدار سلول → عدد (فارسی/عربی، جداکننده‌ی هزارگان، خالی → ۰)."""
    if v is None or isinstance(v, bool):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v) if v == v else 0.0
    s = en_digits(str(v)).replace(",", "").replace("٬", "").replace("،", "").replace("٫", ".").strip()
    m = re.match(r"^[-+]?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else 0.0


def norm_code(c):
    """کد یکسان: بدون فاصله و «.0» انتهایی؛ کد کاملاً عددی بدون صفرِ اول."""
    s = en_digits(cell_str(c)).strip()
    s = re.sub(r"\.0$", "", s)
    if re.fullmatch(r"\d+", s):
        s = str(int(s))
    return s


def _strip_grade(text):
    return re.sub(r"درجه\s*[12۱۲]", "", text or "", flags=re.I).strip()


# ───────────────────────── خواندن فایل ─────────────────────────

class _HtmlTable(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell, self._in = [], None, None, False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell, self._in = [], True

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append("".join(self._cell).strip())
            self._cell, self._in = None, False
        elif tag == "tr" and self._row is not None:
            if any(c for c in self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._in and self._cell is not None:
            self._cell.append(data)


def _decode_text(raw):
    for enc in ("utf-8-sig", "utf-16", "cp1256", "cp1252"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("latin-1", errors="replace")


def _trim_rows(rows):
    out = []
    for r in rows:
        r = list(r)
        while r and (r[-1] is None or (isinstance(r[-1], str) and not r[-1].strip())):
            r.pop()
        out.append(r)
    while out and not out[-1]:
        out.pop()
    return out


def read_table(path):
    """هر فایل جدولی (xlsx / xls / csv / html با پسوند اشتباه) → (rows, info).
    نوع فایل از روی محتوا تشخیص داده می‌شود نه پسوند (خروجی بعضی نرم‌افزارها .xls ولی در واقع xlsx/html/csv است)."""
    path = str(path)
    if not os.path.exists(path):
        raise FileFormatError("فایل پیدا نشد: " + path)
    with open(path, "rb") as f:
        raw = f.read()
    if not raw:
        raise FileFormatError("فایل خالی است.")
    head = raw[:8]
    info = {"format": "", "sheet": ""}

    if head[:2] == b"PK":                                   # xlsx / xlsm / xltx
        from openpyxl import load_workbook
        try:
            wb = load_workbook(io.BytesIO(raw), data_only=True)
        except Exception as ex:
            raise FileFormatError("خواندن فایل Excel ممکن نشد: %s" % ex)
        info["format"] = "xlsx"
        for ws in wb.worksheets:
            rows = _trim_rows([list(r) for r in ws.iter_rows(values_only=True)])
            if any(any(c not in (None, "") for c in r) for r in rows):
                info["sheet"] = ws.title
                return rows, info
        raise FileFormatError("هیچ برگه‌ی دارای داده‌ای در فایل نیست.")

    if head[:4] == b"\xd0\xcf\x11\xe0":                      # xls قدیمی (OLE2)
        try:
            import xlrd
        except Exception:
            raise FileFormatError(
                "این فایل Excel قدیمی (.xls) است و کتابخانه‌ی xlrd نصب نیست.\n"
                "راه‌حل: فایل را در Excel باز کنید و با «Save As → xlsx» ذخیره کنید، "
                "یا در برنامه  pip install xlrd  اجرا شود.")
        try:
            wb = xlrd.open_workbook(file_contents=raw)
        except Exception as ex:
            raise FileFormatError("خواندن فایل xls ممکن نشد: %s" % ex)
        info["format"] = "xls"
        for sh in wb.sheets():
            rows = _trim_rows([sh.row_values(i) for i in range(sh.nrows)])
            if any(any(c not in (None, "") for c in r) for r in rows):
                info["sheet"] = sh.name
                return rows, info
        raise FileFormatError("هیچ برگه‌ی دارای داده‌ای در فایل نیست.")

    text = _decode_text(raw)
    low = text[:4000].lower()
    if "<table" in low or "<html" in low:                    # HTML با پسوند xls
        p = _HtmlTable()
        p.feed(text)
        if not p.rows:
            raise FileFormatError("جدولی در فایل HTML پیدا نشد.")
        info["format"] = "html"
        return _trim_rows(p.rows), info

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect)]
    rows = _trim_rows(rows)
    if not rows:
        raise FileFormatError("فایل CSV خالی است.")
    info["format"] = "csv"
    return rows, info


# ───────────────────────── ابعاد و حجم ─────────────────────────

def parse_dims(text):
    """(T, L, W) برحسب mm از روی شرح کالا؛ مقدار ناموجود None."""
    text = en_digits(text or "")
    T = L = W = None

    def fnum(m):
        try:
            return float(m.group(1).rstrip("."))
        except Exception:
            return None

    m = re.search(r"ضخامت\s*([\d.]+)\s*mm", text, re.I)
    if m:
        T = fnum(m)
    m = re.search(r"طول\s*([\d.]+)\s*mm", text, re.I)
    if m:
        L = fnum(m)
    m = re.search(r"عرض\s*([\d.]+)\s*mm", text, re.I)
    if m:
        W = fnum(m)
    if T and L and W:
        return T, L, W
    n = re.sub(r"[،\s]", "", text)
    n = re.sub(r"[×xX]", "*", n)
    m = re.search(r"(\d{3,4})\*(\d{3,4})\*([\d.]+)", n)
    if m:
        try:
            return float(m.group(3).rstrip(".")), float(m.group(1)), float(m.group(2))
        except Exception:
            pass
    m = re.search(r"([\d.]+)\s*mm", text, re.I)
    if m:
        return fnum(m), None, None
    return None, None, None


def moshtarak_defaults(dims, name):
    """کالای «مشترک / غیر قابل تولید»: ابعاد استاندارد بر اساس ضخامت."""
    T, L, W = dims
    if not re.search(r"مشترک|غیر قابل تولید", name or ""):
        return dims
    if T is None:
        return dims
    if re.search(r"2\.4\s*mm\s*[=:]\s*2\.44|2\.4\s*میل", en_digits(name or ""), re.I):
        return 2.4, 2440.0, 1830.0
    if L is None or W is None:
        t = round(T * 10) / 10
        if t in (25, 18, 16, 12, 4):
            return T, 3660.0, 1830.0
        if t == 8:
            return T, 2800.0, 1220.0
        if t in (2.4, 2.5):
            return T, 2440.0, 1830.0
        return T, 3660.0, 1830.0
    return dims


def vol_per_sheet(T, L, W):
    """حجم یک ورق به m³ (ابعاد به mm)."""
    if not T or not L or not W:
        return 0.0
    return (T / 1000.0) * (L / 1000.0) * (W / 1000.0)


# ───────────────────────── تجزیه‌ی فایل‌ها ─────────────────────────

SYSTEM_HEADERS = ("شناسه کالا", "شناسهکالا", "کد کالا")


def parse_system_rows(rows):
    """فایل «سامانه» → (items, warnings). item = {code, desc, qty}"""
    items, index, warnings = [], {}, []
    for n, row in enumerate(rows, 1):
        row = list(row) + [None] * 8
        c0, c1, c2 = cell_str(row[0]), cell_str(row[1]), cell_str(row[2])
        if c0 in SYSTEM_HEADERS:
            continue
        c0e, c1e = en_digits(c0), en_digits(c1)
        if c0e and re.match(r"^\d+", re.sub(r"\.0$", "", c0e)):
            code = norm_code(c0e)
            desc = c1
            qty = to_num(row[4]) or to_num(row[3])
        elif c1e and re.match(r"^\d", c1e):
            code = norm_code(c1e)
            desc = c2
            qty = to_num(row[5]) or to_num(row[4])
        else:
            continue
        if code in index:
            index[code]["qty"] += qty
        else:
            it = {"code": code, "desc": _strip_grade(desc), "qty": qty}
            index[code] = it
            items.append(it)
    for it in items:
        it["qty"] = round(it["qty"], 3)
    if not items:
        warnings.append("هیچ ردیفی با کد عددی در فایل سامانه پیدا نشد؛ ساختار ستون‌ها را بررسی کنید.")
    return items, warnings


def parse_warehouse_rows(rows):
    """فایل «انبار» → (items, warnings). item = {code, name, qty(m³), sheets, unit, dims}"""
    start = 0
    for i in range(min(5, len(rows))):
        if any(("کد کالا" in cell_str(c)) or ("نام کالا" in cell_str(c)) for c in rows[i]):
            start = i + 1
            break
    items, index, warnings = [], {}, []
    for n in range(start, len(rows)):
        row = list(rows[n]) + [None] * 8
        code = norm_code(row[1])
        name = cell_str(row[2])
        if not code or code.lower() == "nan" or "جمع" in name or not re.match(r"^\d", code):
            continue
        unit = cell_str(row[3])
        q1, q2 = to_num(row[4]), to_num(row[5])
        dims = moshtarak_defaults(parse_dims(name), name)
        vps = vol_per_sheet(*dims)
        sheets = m3 = 0.0
        if "پالت" in unit:
            if q2 > 0:
                sheets, m3 = q2, q2 * vps
            elif q1 > 0:
                sheets = q1 * PALLET_SHEETS
                m3 = sheets * vps
        elif "ورق" in unit:
            sheets, m3 = q1, q1 * vps
        else:
            if q1 > 0 or q2 > 0:
                warnings.append("ردیف %d کد %s: واحد «%s» نامشخص است (فقط پالت/ورق)؛ موجودی صفر حساب شد." % (n + 1, code, unit))
        if vps == 0 and (q1 > 0 or q2 > 0):
            warnings.append("ردیف %d کد %s: ابعاد در شرح پیدا نشد؛ m³ صفر حساب شد  («%s»)" % (n + 1, code, name[:50]))
        if code in index:
            index[code]["qty"] += m3
            index[code]["sheets"] += sheets
        else:
            it = {"code": code, "name": _strip_grade(name), "qty": m3, "sheets": sheets, "unit": unit}
            index[code] = it
            items.append(it)
    for it in items:
        it["qty"] = round(it["qty"], 3)
        it["sheets"] = int(round(it["sheets"]))
    if not items:
        warnings.append("هیچ ردیفی با کد کالا در فایل انبار پیدا نشد؛ ستون دوم باید «کد کالا» باشد.")
    return items, warnings


# ───────────────────────── نگاشت ─────────────────────────

def normalize_mappings(maps):
    out = {}
    for wh, m in (maps or {}).items():
        out[wh] = {}
        for sc, arr in (m or {}).items():
            seen, lst = set(), []
            for c in (arr or []):
                nc = norm_code(c)
                if nc and nc not in seen:
                    seen.add(nc)
                    lst.append(nc)
            out[wh][norm_code(sc)] = lst
    return out


def used_codes(maps, wh):
    used = set()
    for arr in (maps.get(wh) or {}).values():
        used.update(norm_code(c) for c in arr)
    return used


def add_mapping(maps, wh, sys_code, wh_codes):
    """کد(های) انبار را به کد سامانه وصل می‌کند. برمی‌گرداند (تعداد افزوده‌شده, پیام خطاها)."""
    sc = norm_code(sys_code)
    maps.setdefault(wh, {}).setdefault(sc, [])
    used = used_codes(maps, wh)
    added, errors = 0, []
    for c in wh_codes:
        nc = norm_code(c)
        if not nc:
            continue
        if nc in maps[wh][sc]:
            errors.append("کد %s قبلاً برای همین کالا اضافه شده." % nc)
        elif nc in used:
            errors.append("کد %s قبلاً به کالای دیگری وصل است." % nc)
        else:
            maps[wh][sc].append(nc)
            used.add(nc)
            added += 1
    return added, errors


def remove_mapping(maps, wh, sys_code, wh_code):
    sc, wc = norm_code(sys_code), norm_code(wh_code)
    lst = maps.get(wh, {}).get(sc, [])
    maps[wh][sc] = [c for c in lst if norm_code(c) != wc]


def merge_mappings(a, b):
    """ادغام دو نگاشت (اجتماع کدها)؛ کد انبارِ تکراری در یک انبار فقط یک‌بار (اولویت با a)."""
    out = normalize_mappings(a)
    for wh, m in normalize_mappings(b).items():
        for sc, arr in m.items():
            add_mapping(out, wh, sc, arr)
    return out


# ───────────────────────── پیشنهاد خودکار نگاشت ─────────────────────────

_STOP = {"درجه", "mm", "میل", "ورق", "پالت", "mdf", "ام", "دی", "اف", "و", "با", "از", "به", "برای", "مدل", "کد", "طول", "عرض", "ضخامت"}


def _tokens(s):
    s = en_digits(s or "").lower()
    s = re.sub(r"[^\w.]+", " ", s)
    return {t for t in s.split() if t and t not in _STOP and len(t) > 1}


def similarity(sys_code, sys_desc, wh_code, wh_name):
    """امتیاز شباهت ۰..۱ بین یک کالای سامانه و یک کالای انبار (کد یکسان / ابعاد / کلمات مشترک)."""
    if norm_code(sys_code) and norm_code(sys_code) == norm_code(wh_code):
        return 1.0, "کد یکسان"
    d1 = moshtarak_defaults(parse_dims(sys_desc), sys_desc)
    d2 = moshtarak_defaults(parse_dims(wh_name), wh_name)
    score, why = 0.0, []
    if d1[0] and d2[0] and abs(d1[0] - d2[0]) < 0.05:
        score += 0.4
        why.append("ضخامت")
        if d1[1] and d1[2] and d2[1] and d2[2]:
            if abs(d1[1] - d2[1]) <= 1 and abs(d1[2] - d2[2]) <= 1:
                score += 0.3
                why.append("طول×عرض")
        else:
            score += 0.1
    t1, t2 = _tokens(sys_desc), _tokens(wh_name)
    if t1 and t2:
        jac = len(t1 & t2) / float(len(t1 | t2))
        if jac:
            score += 0.3 * jac
            why.append("کلمات مشترک")
    return min(score, 1.0), "، ".join(why)


def suggest_mappings(sys_items, wh_items, maps, wh, min_score=0.6):
    """برای کدهای سامانه‌ی بدون نگاشت بهترین کد انبار آزاد را پیشنهاد می‌دهد.
    خروجی: [{sys_code, sys_desc, wh_code, wh_name, score, why}] (هر کد انبار حداکثر یک‌بار)."""
    used = used_codes(maps, wh)
    mapped_sys = {norm_code(k) for k, v in (maps.get(wh) or {}).items() if v}
    free = [w for w in wh_items if norm_code(w["code"]) not in used]
    cands = []
    for s in sys_items:
        if norm_code(s["code"]) in mapped_sys:
            continue
        scored = []
        for w in free:
            sc, why = similarity(s["code"], s.get("desc", ""), w["code"], w.get("name", ""))
            if sc >= min_score:
                scored.append((sc, why, w))
        scored.sort(key=lambda x: -x[0])
        if scored:
            # اگر دو کاندید تقریباً هم‌امتیازند، مطمئن نیستیم → پیشنهاد نده
            if len(scored) > 1 and scored[0][0] - scored[1][0] < 0.05 and scored[0][0] < 1.0:
                continue
            sc, why, w = scored[0]
            cands.append({"sys_code": s["code"], "sys_desc": s.get("desc", ""), "wh_code": w["code"],
                          "wh_name": w.get("name", ""), "score": round(sc, 2), "why": why})
    cands.sort(key=lambda c: -c["score"])
    taken, out = set(), []
    for c in cands:
        if c["wh_code"] in taken:
            continue
        taken.add(c["wh_code"])
        out.append(c)
    return out


def rank_free_codes(sys_item, free_items):
    """کدهای انبار آزاد را برای یک کالای سامانه بر اساس شباهت مرتب می‌کند → [(score, why, item)]."""
    res = []
    for w in free_items:
        sc, why = similarity(sys_item["code"], sys_item.get("desc", ""), w["code"], w.get("name", ""))
        res.append((sc, why, w))
    res.sort(key=lambda x: (-x[0], norm_code(x[2]["code"]).zfill(12)))
    return res


# ───────────────────────── مقایسه ─────────────────────────

def pick_warehouse_qty(wh_items, mapped_codes):
    codes = [norm_code(c) for c in mapped_codes]
    if not codes:
        return {"qty": 0.0, "code": "", "name": "", "sheets": 0, "mapped": False, "parts": []}
    by_code = {norm_code(w["code"]): w for w in wh_items}
    qty, sheets, names, parts = 0.0, 0, [], []
    for c in codes:
        w = by_code.get(c)
        q = w["qty"] if w else 0.0
        qty += q
        sheets += (w or {}).get("sheets", 0) or 0
        nm = (w or {}).get("name", "")
        if nm:
            names.append(nm)
        parts.append({"code": c, "name": nm, "qty": q, "found": bool(w)})
    return {"qty": round(qty, 3), "code": " + ".join(codes), "name": " | ".join(names),
            "sheets": sheets, "mapped": True, "parts": parts}


def compare(system, warehouse, mappings, threshold, warehouses=None):
    """نتیجه‌ی مقایسه برای همه‌ی انبارها (ترتیب: انبار، سپس ترتیب فایل سامانه)."""
    results = []
    for wh in (warehouses or WAREHOUSES):
        wh_items = warehouse.get(wh, [])
        maps = (mappings.get(wh) or {})
        for s in system.get(wh, []):
            picked = pick_warehouse_qty(wh_items, maps.get(norm_code(s["code"]), []))
            raw = round(picked["qty"] - s["qty"], 3)
            diff = 0.0 if abs(raw) < threshold else raw
            if not picked["mapped"]:
                action = "بدون نگاشت"
            elif diff > 0:
                action = "افزایش سامانه %.3f m³" % diff
            elif diff < 0:
                action = "کاهش سامانه %.3f m³" % abs(diff)
            else:
                action = "بالانس ✓"
            missing = [p["code"] for p in picked["parts"] if not p["found"]]
            results.append({
                "warehouse": wh, "sysCode": s["code"], "desc": s.get("desc", ""), "sysQty": s["qty"],
                "whCode": picked["code"], "whName": picked["name"], "whQty": picked["qty"], "sheets": picked["sheets"],
                "rawDiff": raw, "diff": diff, "action": action, "mapped": picked["mapped"], "missing": missing,
            })
    return results


def result_status(r):
    if not r["mapped"]:
        return "unmapped"
    if r["diff"] > 0:
        return "add"
    if r["diff"] < 0:
        return "sub"
    return "balanced"


def result_stats(results):
    st = {"total": len(results), "balanced": 0, "add": 0, "sub": 0, "unmapped": 0}
    for r in results:
        st[result_status(r)] += 1
    return st


def decrease_qty(r):
    """مقدار کاهش سامانه برای اظهار خروج (همیشه مثبت)."""
    q = round(r["sysQty"] - r["whQty"], 3)
    if q <= 0:
        q = abs(r["rawDiff"])
    return q


# ───────────────────────── خروجی‌ها ─────────────────────────

KHOROJ_HEADERS = ["* کدپستی  انبار مبدا", "* تاریخ سند ", "* نوع سند", "شماره سند مرتبط",
                  "شرح ", "* شناسه کالا", "* تعداد/مقدار", "مبلغ واحد (ریال)"]


def khoroj_rows(selected, doc_date):
    """سطرهای فایل «ثبت اظهار خروج» برای ردیف‌های انتخاب‌شده‌ی دارای کاهش."""
    rows = [list(KHOROJ_HEADERS)]
    for r in selected:
        if not r.get("sysCode") or r["diff"] >= 0:
            continue
        postal = POSTAL.get(r["warehouse"], "")
        code = r["sysCode"]
        rows.append([int(postal) if postal else "", doc_date, "استفاده در تولید", "", "",
                     int(code) if re.fullmatch(r"\d+", code) else code, decrease_qty(r), ""])
        rows.append(["", "", "", "", "", "", "", ""])
    return rows


def write_khoroj_xlsx(path, selected, doc_date):
    from openpyxl import Workbook
    rows = khoroj_rows(selected, doc_date)
    if len(rows) <= 1:
        raise ValueError("ردیفی برای کاهش سامانه انتخاب نشده (فقط اختلاف منفی صادر می‌شود).")
    wb = Workbook()
    ws = wb.active
    ws.title = "ثبت اظهار خروج"
    for r in rows:
        ws.append(r)
    ws.sheet_view.rightToLeft = True
    for col, w in zip("ABCDEFGH", (22, 14, 18, 16, 14, 16, 16, 16)):
        ws.column_dimensions[col].width = w
    wb.save(path)
    return (len(rows) - 1) // 2


RESULT_COLUMNS = [("انبار", "warehouse"), ("کد سامانه", "sysCode"), ("شرح", "desc"), ("کد انبار", "whCode"),
                  ("نام انبار", "whName"), ("سامانه m3", "sysQty"), ("انبار m3", "whQty"), ("اختلاف", "diff"),
                  ("اختلاف واقعی", "rawDiff"), ("اقدام", "action")]


def write_results_xlsx(path, results):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "مقایسه"
    ws.append([c[0] for c in RESULT_COLUMNS] + ["نگاشت"])
    for r in results:
        ws.append([r[k] for _, k in RESULT_COLUMNS] + ["بله" if r["mapped"] else "خیر"])
    ws.sheet_view.rightToLeft = True
    for col, w in zip("ABCDEFGHIJK", (12, 12, 40, 18, 40, 12, 12, 12, 14, 26, 8)):
        ws.column_dimensions[col].width = w
    wb.save(path)


def results_html(results, title, doc_date=""):
    """HTML راست‌چین برای چاپ PDF (Qt QTextDocument)."""
    import html as _h
    rows = []
    for i, r in enumerate(results, 1):
        rows.append("<tr><td>%d</td><td>%s</td><td>%s</td><td>%s</td><td>%.3f</td><td>%.3f</td><td><b>%.3f</b></td></tr>" % (
            i, _h.escape(r["warehouse"]), _h.escape(r["sysCode"]), _h.escape((r["desc"] or "")[:70]),
            r["sysQty"], r["whQty"], decrease_qty(r) if r["diff"] < 0 else abs(r["diff"])))
    return ("<html><body dir='rtl' style='font-family:Tahoma;font-size:10pt'><h3>%s</h3><p>تاریخ: %s — تعداد: %d</p>"
            "<table border='1' cellspacing='0' cellpadding='4' width='100%%'>"
            "<tr style='background:#e0f2fe'><th>#</th><th>انبار</th><th>کد سامانه</th><th>شرح</th><th>سامانه m³</th><th>انبار m³</th><th>مقدار کاهش</th></tr>%s</table></body></html>"
            % (_h.escape(title), _h.escape(doc_date), len(results), "".join(rows)))


# ───────────────────────── ذخیره‌ی محلی ─────────────────────────

def _now_iso():
    """زمان UTC با اختلاف‌زمان (برای مقایسه‌ی درست با updated_at ابر)."""
    from datetime import timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_store():
    return {"version": STORE_VERSION, "mappings": {}, "threshold": 5.0, "docDate": "",
            "system": {}, "warehouse": {}, "files": {}, "mapsUpdatedAt": "", "cloudSyncedAt": "", "dataReadAt": ""}


def load_store(path):
    """بارگذاری ذخیره‌ی محلی؛ اگر خراب بود از .bak می‌خواند؛ در نهایت ذخیره‌ی خالی."""
    for p in (str(path), str(path) + ".bak"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                st = empty_store()
                st.update(data)
                st["mappings"] = normalize_mappings(st.get("mappings"))
                return st
        except FileNotFoundError:
            continue
        except Exception:
            continue
    return empty_store()


def save_store(path, store):
    """ذخیره‌ی اتمیک (فایل موقت + replace) با نسخه‌ی .bak از حالت قبل."""
    path = str(path)
    store = dict(store)
    store["version"] = STORE_VERSION
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".inv_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False)
        if os.path.exists(path):
            try:
                with open(path, "rb") as a, open(path + ".bak", "wb") as b:
                    b.write(a.read())
            except Exception:
                pass
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def touch_maps(store):
    store["mapsUpdatedAt"] = _now_iso()


def parse_iso(s):
    """رشته‌ی ISO (با Z یا بدون) → datetime ساده (UTC فرض می‌شود برای مقایسه)؛ خطا → None."""
    if not s:
        return None
    try:
        t = str(s).replace("Z", "+00:00")
        dt = datetime.fromisoformat(t)
        if dt.tzinfo is not None:
            from datetime import timezone
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None
