# -*- coding: utf-8 -*-
"""منطق «مشتریان و محاسبات» — بدون وابستگی به Qt (قابل تست).

بازنویسی دقیق منطق ابزار قبلی (calc_customers.html):
  * n()            : تبدیل متن/عبارت ریاضی ساده به عدد (ارقام فارسی/عربی، ×، ÷، جداکننده‌ها)
  * trunc / fmt    : برش به سمت صفر و قالب‌بندی هزارگان انگلیسی
  * calc_tax       : مالیات = مبلغ ÷ ۱.۱ ÷ ۱۰ (بُرش به عدد صحیح)
  * calc_per       : هر متر مکعب = بُرش(مبلغ ÷ ۱.۱ ÷ متر مکعب + ۱)
"""
import json
import math
import os
import re
import sys
import tempfile
from datetime import datetime, timezone

STORE_VERSION = 1
OWNER_EMAIL = "arash.e.maleki@gmail.com"
FREE_DEFAULT = {"amount": 24960000000, "cubic": 20.56}

INITIAL_SIZES = [
 {
  "name": "8 بزرگ",
  "volume": 0.0535824,
  "count": 192,
  "amount": 14793600000,
  "sourceFormula": "3.66×1.83×0.008"
 },
 {
  "name": "16 بزرگ",
  "volume": 0.1071648,
  "count": 48,
  "amount": 5760000000,
  "sourceFormula": "3.66×1.83×0.016"
 },
 {
  "name": "18 بزرگ",
  "volume": 0.1205604,
  "count": 90,
  "amount": 11700000000,
  "sourceFormula": "3.66×1.83×0.018"
 },
 {
  "name": "25 بزرگ",
  "volume": 0.167445,
  "count": 62,
  "amount": 13826000000,
  "sourceFormula": "3.66×1.83×0.025"
 },
 {
  "name": "280 8",
  "volume": 0.027328,
  "count": 100,
  "amount": 2100000000,
  "sourceFormula": "2.8×1.22×0.008"
 },
 {
  "name": "280 16",
  "volume": 0.054656,
  "count": 100,
  "amount": 5800000000,
  "sourceFormula": "2.8×1.22×0.016"
 },
 {
  "name": "280 18",
  "volume": 0.061488,
  "count": 135,
  "amount": 8775000000,
  "sourceFormula": "2.8×1.22×0.018"
 },
 {
  "name": "3 میل",
  "volume": 0.01071648,
  "count": 340,
  "amount": 3400000000,
  "sourceFormula": "2.44×1.83×0.0024"
 },
 {
  "name": "آفکات",
  "volume": 0.0357216,
  "count": 288,
  "amount": 10080000000,
  "sourceFormula": "3.66×0.61×0.016"
 }
]

_FA = "۰۱۲۳۴۵۶۷۸۹"
_AR = "٠١٢٣٤٥٦٧٨٩"
_DIGIT_MAP = {ord(c): str(i) for i, c in enumerate(_FA)}
_DIGIT_MAP.update({ord(c): str(i) for i, c in enumerate(_AR)})


def fa_to_en(s):
    return ("" if s is None else str(s)).translate(_DIGIT_MAP)


def default_sizes():
    return [dict(x, id="base_%d" % i, custom=False) for i, x in enumerate(INITIAL_SIZES)]


def js_num(x):
    """نمایش عدد مثل رشته‌سازی جاوااسکریپت (۳ نه ۳.۰)."""
    x = float(x)
    if x == int(x) and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


# ───────────────────────── تجزیه‌ی عدد ─────────────────────────
class _Bad(Exception):
    pass


def _tokenize(s):
    toks, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isdigit() or c == ".":
            j = i
            while j < len(s) and (s[j].isdigit() or s[j] == "."):
                j += 1
            t = s[i:j]
            if t.count(".") > 1 or t == ".":
                raise _Bad()
            toks.append(("n", float(t)))
            i = j
        elif s.startswith("**", i):
            toks.append(("op", "**"))
            i += 2
        elif c in "+-*/()":
            toks.append(("op", c))
            i += 1
        else:
            raise _Bad()
    return toks


def _eval(toks):
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def expr():
        v = term()
        while peek() in (("op", "+"), ("op", "-")):
            op = take()[1]
            nxt = peek()
            if nxt == ("op", op):  # «++» و «--» در جاوااسکریپت خطاست
                raise _Bad()
            r = term()
            v = v + r if op == "+" else v - r
        return v

    def term():
        v = unary()
        while peek() in (("op", "*"), ("op", "/")):
            op = take()[1]
            r = unary()
            if op == "*":
                v = v * r
            else:
                v = v / r if r != 0 else (math.inf if v > 0 else (-math.inf if v < 0 else math.nan))
        return v

    def unary():
        t = peek()
        if t == ("op", "-") or t == ("op", "+"):
            take()
            if peek() == t:
                raise _Bad()
            v = unary()
            return -v if t[1] == "-" else v
        return power()

    def power():
        b = atom()
        if peek() == ("op", "**"):
            take()
            e = unary()
            try:
                return b ** e
            except Exception:
                return math.nan
        return b

    def atom():
        t = take()
        if t is None:
            raise _Bad()
        if t[0] == "n":
            return t[1]
        if t == ("op", "("):
            v = expr()
            if take() != ("op", ")"):
                raise _Bad()
            return v
        raise _Bad()

    v = expr()
    if pos[0] != len(toks):
        raise _Bad()
    return v


_PLAIN = re.compile(r"^-?\d+(\.\d+)?$")
_SAFE = re.compile(r"^[\d+\-*/().]+$")


def n(s):
    """هم‌ارز n() ابزار قبلی: عدد ساده یا عبارت ریاضی امن؛ در غیر این صورت ۰."""
    st = fa_to_en(s).strip()
    st = re.sub(r"[,_،\s]", "", st).replace("×", "*").replace("÷", "/").replace("٫", ".")
    if not st:
        return 0
    if _PLAIN.match(st):
        v = float(st)
        return v if math.isfinite(v) else 0
    if not _SAFE.match(st):
        return 0
    try:
        v = _eval(_tokenize(st))
        return v if (isinstance(v, (int, float)) and math.isfinite(v)) else 0
    except Exception:
        return 0


def parse_amount(s):
    """فقط رقم‌ها (ارقام فارسی/عربی هم) — برای تعداد و مبلغ."""
    d = re.sub(r"[^0-9]", "", fa_to_en(s))
    return int(d) if d else 0


def trunc(v, d=0):
    m = 10 ** d
    return math.trunc((float(v) + sys.float_info.epsilon) * m) / m


def fmt(v, d=0):
    if v is None:
        return "—"
    try:
        f = float(v)
    except Exception:
        return "—"
    if not math.isfinite(f):
        return "—"
    from decimal import Decimal, ROUND_HALF_UP
    q = Decimal(1).scaleb(-d)
    dv = Decimal(repr(f)).quantize(q, rounding=ROUND_HALF_UP)
    return format(dv, ",.%df" % d)


def fmt_free_cubic(v):
    """متراژ آزاد: بُرش به ۲ رقم اعشار (مثل سایزها) و بدون صفر اضافه — همان عددی که در محاسبه استفاده می‌شود."""
    if not v:
        return ""
    s = "%.2f" % trunc(float(v), 2)
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def normalize(s):
    return fa_to_en(s or "").strip().replace("ي", "ی").replace("ى", "ی").replace("ك", "ک").lower()


# ───────────────────────── محاسبات ─────────────────────────
def _dec(v):
    from decimal import Decimal
    return Decimal(repr(float(v or 0)))


def calc_tax(amount):
    """مالیات = مبلغ ÷ ۱.۱ ÷ ۱۰ (بُرش) — با محاسبه‌ی دقیق اعشاری تا خطای ممیز شناور بُرش را یکی کم نکند."""
    from decimal import Decimal
    amount = float(amount or 0)
    if amount <= 0:
        return None
    return int(_dec(amount) / Decimal("1.1") / 10)


def calc_per(amount, cubic):
    """هر متر مکعب = بُرش(مبلغ ÷ ۱.۱ ÷ متر مکعب + ۱) — محاسبه‌ی دقیق اعشاری."""
    from decimal import Decimal
    amount = float(amount or 0)
    cubic = float(cubic or 0)
    if amount <= 0 or cubic <= 0:
        return None
    return int(_dec(amount) / Decimal("1.1") / _dec(cubic) + 1)


def row_calc(size, entry):
    """برای یک سایز: متر مکعب، هر متر مکعب، مالیات."""
    entry = entry or {}
    count = float(entry.get("count") or 0)
    amount = float(entry.get("amount") or 0)
    cubic = trunc(float(size.get("volume") or 0) * count, 2)
    return {"cubic": cubic, "per": calc_per(amount, cubic), "tax": calc_tax(amount)}


def summary(sizes, calc):
    sheets = amount = cubic = tax = 0
    for s in sizes:
        c = calc.get(s.get("id")) or {}
        cnt = float(c.get("count") or 0)
        amt = float(c.get("amount") or 0)
        sheets += cnt
        amount += amt
        cubic += trunc(float(s.get("volume") or 0) * cnt, 2)
        t = calc_tax(amt)
        if t:
            tax += t
    return {"sheets": sheets, "amount": amount, "cubic": trunc(cubic, 2), "tax": tax}


def free_result(amount, cubic):
    cubic = trunc(cubic, 2) if cubic else 0     # همان عددی که در کادر نمایش داده می‌شود
    return {"per": calc_per(amount, cubic), "tax": calc_tax(amount)}


def new_custom_size(name, length, width, thickness_mm, stamp_ms):
    """سایز دلخواه؛ None اگر ورودی ناقص باشد."""
    name = (name or "").strip()
    L, W, T = n(length), n(width), n(thickness_mm)
    if not name or L <= 0 or W <= 0 or T <= 0:
        return None
    return {
        "id": "custom_%d" % stamp_ms,
        "name": name,
        "volume": L * W * (T / 1000),
        "sourceFormula": "%s×%s×%s" % (js_num(L), js_num(W), js_num(T / 1000)),
        "custom": True,
    }


# ───────────────────────── مشتریان ─────────────────────────
def customer_matches(customers, q, limit=80):
    nq = normalize(q)
    out = []
    for i, c in enumerate(customers):
        if (not nq or nq in normalize(c.get("customer")) or nq in normalize(c.get("national_id"))
                or nq in normalize(c.get("phone"))):
            out.append((c, i))
            if len(out) >= limit:
                break
    return out


def clean_customer(name, national_id, phone):
    name = (name or "").strip()
    if not name:
        return None
    return {"customer": name, "national_id": fa_to_en((national_id or "").strip()),
            "phone": fa_to_en((phone or "").strip())}


def picked_from(c):
    return {"customer": c.get("customer", ""), "national_id": c.get("national_id", ""), "phone": c.get("phone", "")}


def same_customer(picked, c):
    return bool(picked) and normalize(picked.get("customer")) == normalize(c.get("customer")) \
        and picked.get("national_id") == c.get("national_id")


# ───────────────────────── ذخیره‌ی محلی و پشتیبان ─────────────────────────
def empty_store():
    return {"version": STORE_VERSION, "customers": [], "sizes": default_sizes(),
            "freeCalc": dict(FREE_DEFAULT), "pickedCustomer": None}


def _sane(st):
    base = empty_store()
    if isinstance(st.get("customers"), list):
        base["customers"] = [c for c in st["customers"] if isinstance(c, dict)]
    if isinstance(st.get("sizes"), list) and st["sizes"]:
        base["sizes"] = [s for s in st["sizes"] if isinstance(s, dict) and s.get("id")]
    if isinstance(st.get("freeCalc"), dict):
        base["freeCalc"] = st["freeCalc"]
    if isinstance(st.get("pickedCustomer"), dict):
        base["pickedCustomer"] = st["pickedCustomer"]
    return base


def load_store(path):
    for p in (str(path), str(path) + ".bak"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return _sane(data)
        except Exception:
            continue
    return empty_store()


def save_store(path, store):
    path = str(path)
    data = {k: store.get(k) for k in ("customers", "sizes", "freeCalc", "pickedCustomer")}
    data["version"] = STORE_VERSION
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".calc_", suffix=".tmp", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
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


def build_payload(store, calc, now_iso=None):
    return {
        "version": 1,
        "updatedAt": now_iso or datetime.now(timezone.utc).isoformat(),
        "customers": store.get("customers", []),
        "sizes": store.get("sizes", []),
        "calc": calc,
        "freeCalc": store.get("freeCalc"),
        "pickedCustomer": store.get("pickedCustomer"),
    }


def build_backup(store, calc, now_iso=None):
    d = build_payload(store, calc, now_iso)
    d.pop("updatedAt", None)
    d["exported_at"] = now_iso or datetime.now(timezone.utc).isoformat()
    return d


def validate_payload(d):
    return isinstance(d, dict) and isinstance(d.get("customers"), list) \
        and isinstance(d.get("sizes"), list) and isinstance(d.get("calc"), dict)


def apply_payload(d):
    """(store, calc) از پشتیبان/ابر؛ ValueError اگر نامعتبر."""
    if not validate_payload(d):
        raise ValueError("invalid")
    store = _sane({"customers": d["customers"], "sizes": d["sizes"],
                   "freeCalc": d.get("freeCalc") or {"amount": 0, "cubic": 0},
                   "pickedCustomer": d.get("pickedCustomer")})
    if not isinstance(d.get("freeCalc"), dict):
        store["freeCalc"] = {"amount": 0, "cubic": 0}
    calc = {}
    for s in store["sizes"]:
        c = d["calc"].get(s["id"])
        calc[s["id"]] = {"count": (c or {}).get("count") or 0, "amount": (c or {}).get("amount") or 0}
    return store, calc


def is_owner(email):
    return str(email or "").strip().lower() == OWNER_EMAIL.lower()


def payload_for_push(payload, email):
    """غیرمالک مشتریان را به ابر نمی‌فرستد."""
    p = dict(payload)
    if not is_owner(email):
        p["customers"] = []
    return p


def payload_for_pull(payload, email, local_customers):
    """غیرمالک: لیست مشتریان ابری اعمال نمی‌شود (لیست محلی می‌ماند)."""
    if is_owner(email):
        return payload
    p = dict(payload)
    p["customers"] = list(local_customers)
    return p
