"""توابع خالص SalesMate (بدون Qt): ارقام، مبلغ، تاریخ شمسی.
جدا از main.py تا بدون PySide6 قابل تست باشند (tests/test_core.py)."""
import re
from datetime import datetime

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
# ارقام فارسی (۰-۹) و عربی-هندی (٠-٩) → لاتین
LATIN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

def fa_digits(value):
    return str(value).translate(PERSIAN_DIGITS)


def en_digits(value):
    return str(value).translate(LATIN_DIGITS)


def clean_number(value):
    s=en_digits(str(value)).replace(",","").replace("٬","").replace("،","").replace(" ","")
    return re.sub(r"[^0-9]","",s)


def amount(v):
    """عدد صحیح؛ علامت منفی حفظ می‌شود.
    اعشار (مثل 1500000.0) نباید صفر اضافه کند.
    """
    try:
        if isinstance(v, bool):
            return 0
        if isinstance(v, (int, float)):
            return int(round(float(v)))
        s = en_digits(str(v)).strip()
        s = (
            s.replace(",", "")
            .replace("٬", "")
            .replace("،", "")
            .replace(" ", "")
            .replace("٫", ".")
        )
        if not s or s in ("-", "+", "."):
            return 0
        neg = s.startswith("-")
        if s[0] in "+-":
            s = s[1:]
        # فقط رقم و یک نقطه اعشار
        s = re.sub(r"[^0-9.]", "", s)
        if not s or s == ".":
            return 0
        # چند نقطه: فقط تا اولین بخش صحیح
        if s.count(".") > 1:
            parts = s.split(".")
            s = parts[0] + "." + "".join(parts[1:])
        n = int(round(float(s)))
        return -n if neg else n
    except Exception:
        return 0


def fmt(v):
    return fa_digits(f"{amount(v):,}")


def format_jalali_ymd(y, m, d):
    """نمایش تاریخ سال/ماه/روز با ارقام فارسی — روز سمت راست دیده می‌شود"""
    try:
        return fa_digits(f"{int(y):04d}/{int(m):02d}/{int(d):02d}")
    except Exception:
        return fa_digits(f"{y}/{m}/{d}")


def gregorian_to_jalali(gy, gm, gd):
    gdim=[31,29 if (gy%4==0 and (gy%100!=0 or gy%400==0)) else 28,31,30,31,30,31,31,30,31,30,31]
    gy2, gm2, gd2=gy-1600,gm-1,gd-1
    gdn=365*gy2+(gy2+3)//4-(gy2+99)//100+(gy2+399)//400+sum(gdim[:gm2])+gd2
    jdn=gdn-79
    jnp=jdn//12053; jdn%=12053
    jy=979+33*jnp+4*(jdn//1461); jdn%=1461
    if jdn>=366: jy+=(jdn-1)//365; jdn=(jdn-1)%365
    jm=1+jdn//31 if jdn<186 else 7+(jdn-186)//30
    jd=1+(jdn-(jm-1)*31 if jm<=6 else jdn-186-(jm-7)*30)
    return jy,jm,jd


def jalali_to_gregorian(jy, jm, jd):
    jy = int(jy); jm = int(jm); jd = int(jd)
    jy2 = jy - 979
    days = 365 * jy2 + (jy2 // 33) * 8 + ((jy2 % 33) + 3) // 4
    for i in range(1, jm):
        days += 31 if i <= 6 else 30
    days += jd - 1
    gdn = days + 79
    gy = 1600
    # approximate
    gy += 400 * (gdn // 146097)
    gdn %= 146097
    leap = True
    if gdn >= 36525:
        gdn -= 1
        gy += 100 * (gdn // 36524)
        gdn %= 36524
        if gdn >= 365:
            gdn += 1
        else:
            leap = False
    gy += 4 * (gdn // 1461)
    gdn %= 1461
    if gdn >= 366:
        leap = False
        gdn -= 1
        gy += gdn // 365
        gdn %= 365
    gd = gdn + 1
    gdim = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 1
    for dim in gdim:
        if gd <= dim:
            break
        gd -= dim
        gm += 1
    return gy, gm, gd


def parse_flexible_jalali(text_in, default_year=None):
    """۸/۷ یا ۸/۷/۰۶ یا ۱۴۰۶/۰۷/۰۸ → (y,m,d) یا None"""
    s = en_digits(str(text_in or "")).strip().replace("-", "/").replace(".", "/")
    s = s.replace(" ", "")
    if not s:
        return None
    parts = [p for p in s.split("/") if p != ""]
    if not parts:
        return None
    try:
        nums = [int(p) for p in parts]
    except Exception:
        return None
    if default_year is None:
        gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
        default_year = gregorian_to_jalali(gy, gm, gd)[0]
    if len(nums) == 1:
        # فقط روز → ماه جاری
        jy, jm, _ = gregorian_to_jalali(datetime.now().year, datetime.now().month, datetime.now().day)
        return default_year, jm, nums[0]
    if len(nums) == 2:
        d, m = nums[0], nums[1]
        if m > 12 and d <= 12:
            d, m = m, d
        y = default_year
        return y, m, d
    if len(nums) >= 3:
        # day/month/year or year/month/day
        a, b, c = nums[0], nums[1], nums[2]
        if a > 31:  # year first
            y, m, d = a, b, c
        else:
            d, m, y = a, b, c
        if y < 100:
            y = 1400 + y if y < 80 else 1300 + y
        return y, m, d
    return None


_MONEY_RE = re.compile(r"^[+-]?[\d,٬،\s]*\.?\d*$")


def canon_money(v):
    """مقدار مبلغ را به رشته‌ی عدد صحیح استاندارد تبدیل می‌کند ("۱,۲۰۰,۰۰۰" → "1200000").
    اگر مقدار اصلاً شبیه عدد نباشد None برمی‌گرداند تا دست نخورد."""
    if v is None:
        return None
    s = en_digits(str(v)).strip()
    if not s or s in ("-", "+", ".") or not _MONEY_RE.match(s):
        return None
    return str(amount(s))


def qty_int(v):
    """تعداد کارتن/پالت همیشه عدد صحیح است: «12.0» و «12.5» → «12» / «13»؛ مقدار غیرعددی دست نمی‌خورد."""
    if v is None:
        return ""
    t = en_digits(str(v)).replace(",", "").replace("\u066c", "").replace("\u060c", "").strip()
    if not t:
        return ""
    try:
        f = float(t)
    except Exception:
        return str(v)
    return str(int(f + 0.5)) if f >= 0 else str(-int(-f + 0.5))


def jalali_week_range(y, w):
    """بازه‌ی تاریخ هفته‌ی w (از ۰) سال شمسی y: بلوک‌های ۷ روزه از اول فروردین.
    خروجی: ((m1, d1), (m2, d2)) یا None اگر هفته بیرون از سال باشد."""
    y = int(y)
    w = int(w)
    try:
        is_leap = gregorian_to_jalali(*jalali_to_gregorian(y, 12, 30)) == (y, 12, 30)
    except Exception:
        is_leap = False
    last_doy = 366 if is_leap else 365

    def doy_to_md(doy):
        doy = max(1, min(int(doy), last_doy))
        if doy <= 186:
            return (doy - 1) // 31 + 1, (doy - 1) % 31 + 1
        r = doy - 186
        return 7 + (r - 1) // 30, (r - 1) % 30 + 1

    start = w * 7 + 1
    if w < 0 or start > last_doy:
        return None
    end = min(start + 6, last_doy)
    return doy_to_md(start), doy_to_md(end)


def customer_key(name):
    """کلید یکسان برای مقایسه‌ی نام مشتری بین اکسل‌های مختلف.
    تفاوت ي/ی، ك/ک، نیم‌فاصله، فاصله‌ی اضافه و ارقام فارسی/عربی نباید باعث «مشتری جدید» شود."""
    s = en_digits(str(name if name is not None else ""))
    s = s.replace("\u064a", "\u06cc").replace("\u0649", "\u06cc").replace("\u0643", "\u06a9")
    s = re.sub(r"[\u200c\u200d\u200e\u200f\u202a-\u202e\u0640\u064b-\u065f]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def names_matching(all_names, wanted):
    """از all_names آن‌هایی که با یکی از wanted (به‌کمک customer_key) برابرند."""
    keys = {customer_key(x) for x in (wanted or ()) if str(x).strip()}
    keys.discard("")
    out, seen = [], set()
    for nm in all_names:
        k = customer_key(nm)
        if k in keys and nm not in seen:
            seen.add(nm)
            out.append(nm)
    return out
