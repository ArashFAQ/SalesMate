# -*- coding: utf-8 -*-
"""
SalesMate Analysis — تحلیل فروش MDF / پارکت / خام / ضایعات
اپلیکیشن دسکتاپ PySide6 (قابل اجرا با run.bat و build با build_exe.bat)
"""

import sys
import json
import os
import hashlib
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

from PySide6.QtCore import Qt, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, QTimer
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QFileDialog, QMessageBox, QTabWidget, QTableView,
    QLineEdit, QComboBox, QFrame, QSplitter, QHeaderView, QGroupBox,
    QStatusBar, QProgressBar, QCheckBox, QTextEdit, QSizePolicy, QScrollArea,
    QDialog, QDialogButtonBox, QRadioButton, QButtonGroup, QFormLayout, QListWidget, QListWidgetItem, QAbstractItemView,
    QTableWidget, QTableWidgetItem
)
from PySide6.QtGui import QFont, QColor, QPalette, QAction

# Charts
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
matplotlib.use("QtAgg")
matplotlib.rcParams["font.family"] = ["Tahoma", "Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

# Optional Jalali
try:
    import jdatetime
    HAS_JALALI = True
except ImportError:
    HAS_JALALI = False

try:
    from app_version import APP_VERSION
except Exception:
    try:
        from salesmate.app_version import APP_VERSION
    except Exception:
        APP_VERSION = "0.0.0"
try:
    from app_log import swallow as _swallow
except Exception:
    try:
        from salesmate.app_log import swallow as _swallow
    except Exception:
        def _swallow(note=""):
            pass

try:
    from core_utils import customer_key, names_matching
except Exception:
    from salesmate.core_utils import customer_key, names_matching
try:
    from sales_extras import build_upload_report, report_to_html
except Exception:
    from salesmate.sales_extras import build_upload_report, report_to_html

# مسیرها داخل پکیج SalesMate
_HERE = Path(__file__).resolve().parent
if getattr(sys, "frozen", False):
    _BASE = Path(sys.executable).resolve().parent
    _CANDIDATES = [
        _HERE,
        Path(getattr(sys, "_MEIPASS", _HERE)),
        _BASE,
        _BASE / "_internal",
    ]
else:
    _CANDIDATES = [_HERE, _HERE.parent]

def _find_subdir(name: str) -> Path:
    for b in _CANDIDATES:
        p = Path(b) / name
        if p.exists():
            return p
    return _HERE / name

DATA_DIR = _find_subdir("analysis_data")
FONTS_DIR = _find_subdir("analysis_fonts")
# مسیر نوشتنی پایدار (کنار exe / ریشه پروژه) — نه داخل _internal
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent
def _find_sample_path() -> Path:
    """فایل نمونه‌ی فروش (داده‌ی واقعی شرکت) داخل پکیج نیست؛ کنار برنامه در analysis_data/ بگذار."""
    for b in [APP_DIR] + list(_CANDIDATES):
        p = Path(b) / "analysis_data" / "sample_sales.xlsx"
        if p.exists():
            return p
    return APP_DIR / "analysis_data" / "sample_sales.xlsx"


SAMPLE_PATH = _find_sample_path()
STORE_PREFIX_KEY = customer_key("فروشگاه ایزوفام")
ANALYSIS_CACHE = APP_DIR / "analysis_sales_cache.pkl"
ANALYSIS_SELECTED = APP_DIR / "analysis_selected_customers.json"
ANALYSIS_CACHE_CSV = APP_DIR / "analysis_sales_cache.csv"
ANALYSIS_REPORTS = APP_DIR / "analysis_upload_reports.json"


# ─────────────────────────── توابع کمکی ───────────────────────────

def format_num(n):
    """فرمت مبلغ به ریال (اعداد از قبل به ریال تبدیل شده‌اند)."""
    try:
        n = float(n)
        if abs(n) >= 1e12:
            return f"{n/1e12:,.2f} هزارمیلیارد"
        if abs(n) >= 1e9:
            return f"{n/1e9:,.2f} میلیارد"
        if abs(n) >= 1e6:
            return f"{n/1e6:,.1f} میلیون"
        return f"{n:,.0f}"
    except Exception:
        return "۰"


def format_rial(n):
    """مبلغ + واحد ریال"""
    return f"{format_num(n)} ریال"


def _qty_int(v):
    try:
        from core_utils import qty_int
    except Exception:
        from salesmate.core_utils import qty_int
    return qty_int(v)


def jalali_week(date_str):
    try:
        parts = str(date_str).strip().split("/")
        if len(parts) != 3:
            return None
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        if HAS_JALALI:
            jd = jdatetime.date(y, m, d)
            start = jdatetime.date(y, 1, 1)
            return (jd - start).days // 7 + 1
        return None
    except Exception:
        return None


def jalali_month(date_str):
    try:
        parts = str(date_str).strip().split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1].zfill(2)}"
        return None
    except Exception:
        return None


_MONTH_FA = {
    1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر",
    5: "مرداد", 6: "شهریور", 7: "مهر", 8: "آبان",
    9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند",
}


def _parse_jalali(date_str):
    try:
        parts = str(date_str).strip().split("/")
        if len(parts) != 3:
            return None
        return int(parts[0]), int(parts[1]), int(parts[2])
    except Exception:
        return None


def week_range_label(dates):
    """برچسب بازه هفته: از روز ماه تا روز ماه"""
    parsed = [p for p in (_parse_jalali(d) for d in dates) if p]
    if not parsed:
        return "?"
    parsed.sort()
    y1, m1, d1 = parsed[0]
    y2, m2, d2 = parsed[-1]
    name1 = _MONTH_FA.get(m1, str(m1))
    name2 = _MONTH_FA.get(m2, str(m2))
    if m1 == m2 and y1 == y2:
        return f"{d1} تا {d2} {name1}"
    if y1 == y2:
        return f"{d1} {name1} تا {d2} {name2}"
    return f"{d1} {name1} {y1} تا {d2} {name2} {y2}"


def _year_of(date_str):
    try:
        return int(str(date_str).strip().split("/")[0])
    except Exception:
        return None


def week_block_label(y, w):
    """برچسب هفته‌ی پیوسته‌ی ۷ روزه (از اول سال) مثل «۳ تا ۹ تیر» — مستقل از اول ماه."""
    try:
        from core_utils import jalali_week_range
    except Exception:  # pragma: no cover
        from salesmate.core_utils import jalali_week_range
    r = jalali_week_range(y, w - 1)
    if not r:
        return "هفته %d" % w
    (m1, d1), (m2, d2) = r
    if m1 == m2:
        return f"{d1} تا {d2} {_MONTH_FA.get(m1, m1)}"
    return f"{d1} {_MONTH_FA.get(m1, m1)} تا {d2} {_MONTH_FA.get(m2, m2)}"


def _continuous_week_series(df, sub, value_col):
    """هفته‌های پیوسته (بلوک ۷ روزه از اول فروردین، بدون توجه به اول ماه)؛ هفته‌ی بدون فروش = ۰.
    بازه از اولین تا آخرین هفته‌ی کل df تا نمودار دسته‌ها هم‌تراز باشند."""
    def keys(frame):
        w = frame.dropna(subset=["هفته"])
        if w.empty:
            return None
        y = w["تاریخ"].map(_year_of)
        ok = y.notna()
        if not ok.any():
            return None
        return pd.DataFrame({"y": y[ok].astype(int), "w": w.loc[ok, "هفته"].astype(int), "v": w.loc[ok, value_col]})
    allk = keys(df)
    if allk is None:
        return pd.Series(dtype=float)
    first = (int(allk["y"].min()), int(allk.loc[allk["y"] == allk["y"].min(), "w"].min()))
    last = (int(allk["y"].max()), int(allk.loc[allk["y"] == allk["y"].max(), "w"].max()))
    sk = keys(sub)
    sums = {}
    if sk is not None:
        for (y, w), v in sk.groupby(["y", "w"])["v"].sum().items():
            sums[(int(y), int(w))] = float(v)
    labels, vals = [], []
    cur, guard = first, 0
    while cur <= last and guard < 3000:
        labels.append(week_block_label(*cur))
        vals.append(sums.get(cur, 0.0))
        y, w = cur
        w += 1
        try:
            from core_utils import jalali_week_range as _jr
        except Exception:  # pragma: no cover
            from salesmate.core_utils import jalali_week_range as _jr
        if w > 53 or _jr(y, w - 1) is None:
            y, w = y + 1, 1
        cur = (y, w)
        guard += 1
    return pd.Series(vals, index=labels, dtype=float)



def week_key_series(frame):
    """کلید پیوسته‌ی هفته «سال|هفته» (بلوک ۷ روزه از اول سال؛ مستقل از اول ماه)."""
    y = frame["تاریخ"].map(_year_of)
    w = frame["هفته"]
    return y.astype("Int64").astype(str) + "|" + w.astype("Int64").astype(str).str.zfill(2)


def _split_week_key(k):
    y, w = str(k).split("|")
    return int(y), int(w)


def prev_week_key(k):
    y, w = _split_week_key(k)
    if w > 1:
        return "%d|%02d" % (y, w - 1)
    # اولین هفته‌ی سال → آخرین هفته‌ی سال قبل
    last = 52
    try:
        from core_utils import jalali_week_range as _jr
    except Exception:  # pragma: no cover
        from salesmate.core_utils import jalali_week_range as _jr
    for cand in (53, 52):
        if _jr(y - 1, cand - 1):
            last = cand
            break
    return "%d|%02d" % (y - 1, last)


def build_week_labels(df):
    """دیکشنری برچسب هفته (کلید «سال|هفته») با بازه‌ی ۷ روزه‌ی پیوسته."""
    if df.empty or "هفته" not in df.columns:
        return {}
    w = df.dropna(subset=["هفته"])
    w = w[w["تاریخ"].map(_year_of).notna()]
    if w.empty:
        return {}
    labels = {}
    for k in sorted(set(week_key_series(w).tolist())):
        y, wk = _split_week_key(k)
        labels[k] = week_block_label(y, wk)
    return labels


def categorize(row):
    name = str(row.get("نام کالا", "")).lower()
    sheet = str(row.get("نام برگه", "")).lower()
    if "ضایعات" in name or "ضایعات" in sheet:
        return "ضایعات"
    if "پارکت" in name or "پارکت" in sheet:
        return "پارکت"
    if "خام" in name:
        return "خام"
    if "ام دی اف" in sheet or "mdf" in name or "هایگلاس" in name or "ملامینه" in name:
        return "ام دی اف"
    if "گمرک" in sheet:
        return "گمرک"
    return "سایر"



def normalize_customer_name(s):
    """یکسان‌سازی نام برای تطبیق با مشتریان SalesMate."""
    import re as _re
    s = str(s or "").strip()
    s = _re.sub(r"\s+", " ", s)
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    s = s.translate(trans)
    low = s
    prefixes = (
        "جناب آقای", "جناب خانم", "جناب", "آقای", "خانم", "شرکت", "فروشگاه",
        "آقاي", "سید", "دکتر", "مهندس",
    )
    changed = True
    while changed:
        changed = False
        for p in prefixes:
            if low.startswith(p + " ") or low == p:
                low = low[len(p):].strip()
                changed = True
    return low.strip()


def load_salesmate_customer_names():
    """نام مشتریان ثبت‌شده در حواله‌های SalesMate از دیتابیس محلی."""
    import sqlite3
    candidates = []
    try:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).resolve().parent
            candidates += [base / "salesmate.db", base / "_internal" / "salesmate.db"]
        here = Path(__file__).resolve().parent
        candidates += [
            here.parent / "salesmate.db",
            here / "salesmate.db",
            APP_DIR / "salesmate.db",
        ]
        # کنار exe کاربر
        try:
            candidates.append(Path.cwd() / "salesmate.db")
        except Exception:
            _swallow()
    except Exception:
        _swallow()
    db_path = None
    for c in candidates:
        try:
            if c and Path(c).exists():
                db_path = Path(c)
                break
        except Exception:
            _swallow()
    if not db_path:
        return set(), {}
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT DISTINCT customer FROM invoices WHERE customer IS NOT NULL AND TRIM(customer) != ''"
        ).fetchall()
        conn.close()
    except Exception:
        return set(), {}
    raw_to_norm = {}
    norm_set = set()
    for (cust,) in rows:
        raw = str(cust or "").strip()
        if not raw:
            continue
        n = normalize_customer_name(raw)
        if not n:
            continue
        norm_set.add(n)
        raw_to_norm[raw] = n
    return norm_set, raw_to_norm


def match_salesmate_customer(excel_name, sm_norm_set):
    n = normalize_customer_name(excel_name)
    if not n:
        return False
    if n in sm_norm_set:
        return True
    if len(n) >= 3:
        for sm in sm_norm_set:
            if len(sm) < 3:
                continue
            if n in sm or sm in n:
                return True
    return False


def _name_sig(name):
    """نام مشتری برای کلید یکتا: فاصله، خط تیره و نیم‌فاصله نادیده گرفته می‌شود
    («فروشگاه ایزوفام - علی» و «فروشگاه ایزوفام-علی» یکی هستند)."""
    import re as _re
    return _re.sub(r"[\s\-\u2010-\u2015\u2212_]+", "", customer_key(name))


def unique_key(row):
    return f"{row.get('تاریخ','')}|{row.get('شماره فرم','')}|{row.get('کد کالا','')}|{_name_sig(row.get('نام مشتری',''))}|{row.get('مبلغ',0)}"


def renorm_dedupe(df):
    """کلید یکتا را با نام نرمال دوباره می‌سازد و ردیف‌های تکراریِ ناشی از نوشتن متفاوت نام را حذف می‌کند."""
    if df is None or getattr(df, "empty", True) or "نام مشتری" not in df.columns:
        return df
    df = df.copy()
    df["unique_key"] = df.apply(unique_key, axis=1)
    return df.drop_duplicates(subset=["unique_key"], keep="first").reset_index(drop=True)


def load_excel(path_or_buf, header=1):
    df = pd.read_excel(path_or_buf, header=header)
    # اگر هدر اشتباه بود
    if "تاریخ" not in df.columns and len(df.columns) >= 2:
        df = pd.read_excel(path_or_buf, header=None)
        # پیدا کردن ردیف هدر
        for i in range(min(5, len(df))):
            row_vals = [str(x) for x in df.iloc[i].tolist()]
            if "تاریخ" in row_vals or "نام مشتری" in row_vals:
                df.columns = df.iloc[i]
                df = df.iloc[i + 1:].reset_index(drop=True)
                break
    return df


def _fnum(v):
    try:
        return float(str(v).replace(",", "").strip() or 0)
    except Exception:
        return 0.0


def excel_rows_differ(old_rows, new_rows):
    """آیا ردیف‌های ذخیره‌شده‌ی یک حواله‌ی اکسلی با ردیف‌های اکسل فرق دارد؟ (کد/تعداد/متراژ/قیمت/مبلغ)"""
    if not isinstance(old_rows, list) or len(old_rows) != len(new_rows):
        return True
    for o, n in zip(old_rows, new_rows):
        if not isinstance(o, dict):
            return True
        if str(o.get("code") or "").strip() != str(n.get("code") or "").strip():
            return True
        for k in ("qty1", "qty2", "price", "cost"):
            if abs(_fnum(o.get(k)) - _fnum(n.get(k))) > 0.00051:
                return True
    return False


def refresh_existing_from_excel(c, table, rid, blob, old_total, old_paid, rows_meta, total):
    """حواله/فروش اکسلیِ موجود را با عددهای اکسل یکی می‌کند. True اگر چیزی عوض شد."""
    import json as _json
    try:
        data = _json.loads(blob or "")
    except Exception:
        return False
    if table == "invoices":
        if not isinstance(data, dict) or data.get("tab") != "analysis_import":
            return False
        old_rows = data.get("rows")
    else:
        if not isinstance(data, list) or not data or not all(isinstance(x, dict) and "name" in x for x in data):
            return False
        old_rows = data
    total_changed = abs(_fnum(old_total) - float(total)) > 0.5
    if not excel_rows_differ(old_rows, rows_meta) and not total_changed:
        return False
    if table == "invoices":
        data["rows"] = rows_meta
        data["total"] = int(total)
        paid = str(old_paid or "")
        if paid.strip() and abs(_fnum(paid) - _fnum(old_total)) <= 0.5:
            paid = str(int(total))
        c.execute("UPDATE invoices SET inquiry_data=?, total=?, paid_amount=? WHERE id=?",
                  (_json.dumps(data, ensure_ascii=False), str(int(total)), paid, rid))
    else:
        c.execute("UPDATE store_sales SET items_json=?, total=? WHERE id=?",
                  (_json.dumps(rows_meta, ensure_ascii=False), str(int(total)), rid))
    return True


def fix_unit_order(df):
    """بعضی ردیف‌های اکسل جای «تعداد 1» و «تعداد 2» برعکس است.
    ام دی اف/خام: تعداد 1 = پالت (کمتر)، تعداد 2 = ورق (بیشتر)
    پارکت: تعداد 1 = بسته/کارتن (کمتر)، تعداد 2 = متراژ (بیشتر)
    پس اگر |تعداد 1| از |تعداد 2| بزرگ‌تر بود (و هر دو غیرصفر)، جابه‌جا می‌شوند."""
    if "تعداد 1" not in df.columns or "تعداد 2" not in df.columns or "دسته" not in df.columns:
        return df
    a = pd.to_numeric(df["تعداد 1"], errors="coerce").fillna(0)
    b = pd.to_numeric(df["تعداد 2"], errors="coerce").fillna(0)
    sw = df["دسته"].isin(["پارکت", "ام دی اف", "خام"]) & (a != 0) & (b != 0) & (a.abs() > b.abs())
    if sw.any():
        df = df.copy()
        df.loc[sw, "تعداد 1"] = b[sw]
        df.loc[sw, "تعداد 2"] = a[sw]
        if "تعداد_ورق" in df.columns:
            df["تعداد_ورق"] = pd.to_numeric(df["تعداد 2"], errors="coerce").fillna(0)
    return df


def clean_df(df):
    df = df.copy()
    df = df.dropna(subset=["تاریخ"], how="all") if "تاریخ" in df.columns else df
    for col in ["تعداد 1", "تعداد 2", "قیمت", "مبلغ", "تعداد 2 برگشتی", "تعداد 2 مانده"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    # مبالغ همان واحد فایل اکسل (ریال) — بدون تقسیم
    for col in ["کد کالا", "نام کالا", "نام مشتری", "نام برگه", "تاریخ"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    df["دسته"] = df.apply(categorize, axis=1)
    df = fix_unit_order(df)
    df["هفته"] = df["تاریخ"].apply(jalali_week) if "تاریخ" in df.columns else None
    df["ماه"] = df["تاریخ"].apply(jalali_month) if "تاریخ" in df.columns else None
    df["تعداد_ورق"] = df["تعداد 2"] if "تعداد 2" in df.columns else 0
    df["unique_key"] = df.apply(unique_key, axis=1)
    return df


# ─────────────────────────── مدل جدول ───────────────────────────

class PandasModel(QAbstractTableModel):
    def __init__(self, df=None, parent=None):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
        self._sort_col = -1
        self._sort_asc = True

    def setDataFrame(self, df):
        self.beginResetModel()
        self._df = df.copy() if df is not None else pd.DataFrame()
        self._sort_col = -1
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.TextAlignmentRole:
            col_name = str(self._df.columns[index.column()])
            # نام کالا راست‌چین و کامل
            if "نام" in col_name:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignCenter)
        if role == Qt.ToolTipRole:
            val = self._df.iat[index.row(), index.column()]
            if pd.isna(val):
                return ""
            if isinstance(val, (int, float, np.integer, np.floating)):
                return f"{val:,.4f}".rstrip("0").rstrip(".") if isinstance(val, float) else f"{val:,.0f}"
            return str(val)
        if role != Qt.DisplayRole:
            return None
        val = self._df.iat[index.row(), index.column()]
        if pd.isna(val):
            return ""
        if isinstance(val, (int, float, np.integer, np.floating)):
            if isinstance(val, float) and not float(val).is_integer():
                return f"{val:,.4f}".rstrip("0").rstrip(".")
            if abs(val) >= 1000:
                return f"{val:,.0f}"
            return f"{val:,.0f}" if isinstance(val, (int, np.integer)) or float(val).is_integer() else str(val)
        return str(val)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            name = str(self._df.columns[section])
            if section == self._sort_col:
                name += " ▲" if self._sort_asc else " ▼"
            return name
        return str(section + 1)

    def sort_by_column(self, col: int):
        if self._df.empty or col < 0 or col >= len(self._df.columns):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = False  # اولین کلیک: نزولی
        col_name = self._df.columns[col]
        self.beginResetModel()
        self._df = self._df.sort_values(col_name, ascending=self._sort_asc, kind="mergesort").reset_index(drop=True)
        self.endResetModel()


class FilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self._col_idx = None  # cache column indices to search

    def setFilterText(self, text):
        self._text = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if not self._text:
            return True
        model = self.sourceModel()
        if not isinstance(model, PandasModel):
            return True
        df = model._df
        if self._col_idx is None or len(self._col_idx) != len(df.columns):
            preferred = {"نام مشتری", "نام کالا", "کد کالا", "دسته", "تاریخ", "شماره فرم"}
            self._col_idx = [i for i, c in enumerate(df.columns) if c in preferred]
            if not self._col_idx:
                self._col_idx = list(range(min(6, df.shape[1])))
        for col in self._col_idx:
            val = str(df.iat[source_row, col]).lower()
            if self._text in val:
                return True
        return False


# ─────────────────────────── ویجت نمودار ───────────────────────────

class MplCanvas(FigureCanvas):
    """نمودار زیبا با hover و اسکرول موس به parent."""

    def __init__(self, parent=None, width=8, height=3.0, dpi=80):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="#f7fafc")
        self._last_hover_draw = 0.0
        self.ax = self.fig.add_subplot(111)
        self._style_axes()
        super().__init__(self.fig)
        self.setParent(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.NoFocus)
        self._annot = None
        self._bar_containers = []
        self._point_sets = []
        self.mpl_connect("motion_notify_event", self._on_hover)
        self.mpl_connect("axes_leave_event", self._on_leave)
        self.mpl_connect("scroll_event", self._on_scroll)

    def _style_axes(self):
        self.ax.set_facecolor("#F1F5F9")
        for spine in ("top", "right"):
            self.ax.spines[spine].set_visible(False)
        self.ax.spines["left"].set_color("#b0bec5")
        self.ax.spines["bottom"].set_color("#b0bec5")
        self.ax.tick_params(colors="#455a64", labelsize=10)
        self.fig.subplots_adjust(left=0.10, right=0.97, top=0.90, bottom=0.18)

    def wheelEvent(self, event):
        # اسکرول را به ScrollArea بده — هرگز زوم matplotlib (کند و مزاحم)
        parent = self.parent()
        while parent is not None:
            if isinstance(parent, QScrollArea):
                bar = parent.verticalScrollBar()
                delta = event.angleDelta().y()
                # اسکرول نرم‌تر با گام بزرگ‌تر
                step = max(40, abs(delta))
                if delta > 0:
                    bar.setValue(bar.value() - step)
                else:
                    bar.setValue(bar.value() + step)
                event.accept()
                return
            parent = parent.parent()
        event.ignore()

    def _on_scroll(self, event):
        # جلوگیری از زوم matplotlib؛ اسکرول به Qt می‌رود
        pass

    def _hover_draw(self):
        """حداکثر ~20 فریم در ثانیه برای tooltip — اسکرول روان می‌ماند."""
        import time
        now = time.monotonic()
        if now - getattr(self, "_last_hover_draw", 0) < 0.05:
            return
        self._last_hover_draw = now
        try:
            self.draw_idle()
        except Exception:
            _swallow()

    def clear_hover(self):
        self._bar_containers = []
        self._point_sets = []
        if self._annot is not None:
            self._annot.set_visible(False)
            self._annot = None

    def register_points(self, xs, ys, labels, unit=""):
        self._point_sets = getattr(self, "_point_sets", [])
        self._point_sets.append((list(xs), [float(v) for v in ys], list(labels), unit))

    def register_bars(self, container, labels, values, unit=""):
        self._bar_containers.append((container, list(labels), list(values), unit))

    def _ensure_annot(self):
        if self._annot is None:
            self._annot = self.ax.annotate(
                "", xy=(0, 0), xytext=(0, 20),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.5", fc="#1a365d", ec="#90cdf4", lw=1.2, alpha=0.95),
                color="white", fontsize=10, fontfamily="Tahoma", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#2b6cb0", lw=1.5),
                zorder=20,
                ha="center",
            )
            self._annot.set_visible(False)

    def _on_leave(self, event):
        if self._annot is not None and self._annot.get_visible():
            self._annot.set_visible(False)
            self.draw_idle()

    def _on_hover_points(self, event):
        """نزدیک‌ترین نقطه‌ی خط (تا ۲۸ پیکسل) → مقدار دقیق."""
        best = None
        for xs, ys, labels, unit in self._point_sets:
            for i, (x, y) in enumerate(zip(xs, ys)):
                px, py = self.ax.transData.transform((x, y))
                d = ((px - event.x) ** 2 + (py - event.y) ** 2) ** 0.5
                if d < 28 and (best is None or d < best[0]):
                    best = (d, i, x, y, labels, unit, len(xs))
        self._ensure_annot()
        if best is None:
            if self._annot.get_visible():
                self._annot.set_visible(False)
                self.draw_idle()
            return
        _, i, x, y, labels, unit, n = best
        val_s = f"{y:,.2f}" if abs(y - round(y)) > 0.001 else f"{y:,.0f}"
        self._annot.xy = (x, y)
        self._annot.set_text(f"{labels[i]}\n{val_s} {unit}".strip())
        self._annot.set_ha("right" if i >= n - 2 and n > 3 else ("left" if i <= 1 and n > 3 else "center"))
        ylim = self.ax.get_ylim()
        high = y > ylim[0] + 0.72 * ((ylim[1] - ylim[0]) or 1)
        self._annot.set_position((-40 if (i >= n - 2 and n > 3) else (40 if (i <= 1 and n > 3) else 0), -45 if high else 28))
        self._annot.set_visible(True)
        self.draw_idle()

    def _on_hover(self, event):
        if getattr(self, "_point_sets", None):
            if event.inaxes != self.ax:
                self._on_leave(event)
                return
            self._on_hover_points(event)
            return
        if event.inaxes != self.ax or not self._bar_containers:
            if self._annot is not None and self._annot.get_visible():
                self._annot.set_visible(False)
                self.draw_idle()
            return
        self._ensure_annot()
        found = False
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        n_bars = 0
        for container, _, _, _ in self._bar_containers:
            n_bars = max(n_bars, len(container))

        for container, labels, values, unit in self._bar_containers:
            for i, bar in enumerate(container):
                contains, _ = bar.contains(event)
                if contains:
                    x = bar.get_x() + bar.get_width() / 2
                    y = bar.get_height()
                    label = labels[i] if i < len(labels) else ""
                    val = values[i] if i < len(values) else y
                    if isinstance(val, float) and abs(val - round(val)) > 0.001:
                        val_s = f"{val:,.2f}"
                    else:
                        val_s = f"{val:,.0f}"
                    txt = f"{label}\n{val_s} {unit}".strip()
                    self._annot.xy = (x, y)
                    self._annot.set_text(txt)

                    # نگه داشتن tooltip داخل نمودار
                    x_off, y_off = 0, 28
                    # اگر نزدیک لبه راست → به چپ
                    if n_bars and i >= n_bars - 2:
                        x_off = -50
                        self._annot.set_ha("right")
                    elif n_bars and i <= 1:
                        x_off = 50
                        self._annot.set_ha("left")
                    else:
                        self._annot.set_ha("center")
                    # اگر میله بلند است → tooltip پایین‌تر از نوک
                    y_range = ylim[1] - ylim[0] if ylim[1] != ylim[0] else 1
                    if y > ylim[0] + 0.72 * y_range:
                        y_off = -45
                    self._annot.set_position((x_off, y_off))
                    self._annot.set_visible(True)
                    found = True
                    break
            if found:
                break
        if not found and self._annot.get_visible():
            self._annot.set_visible(False)
        self.draw_idle()


# ─────────────────────────── پنجره اصلی ───────────────────────────

class AnalysisPage(QWidget):
    def __init__(self, win=None):
        super().__init__()
        self.win = win
        self.df = pd.DataFrame()
        self.df_f = pd.DataFrame()
        self._sm_customers_norm = set()
        self._sm_customers_raw = {}
        self._selected_import_customers = set()  # مشتریان تیک‌خورده → حواله
        self._selected_store_customers = set()    # مشتریان تیک‌خورده → فروشگاه
        self._status = QLabel(f"نسخه {APP_VERSION} | مبالغ به ریال")
        self._status.setStyleSheet("background:#0F172A;color:white;padding:6px 10px;font-size:12px;")
        self._build_ui()
        self._apply_style()
        try:
            self._load_selected_customers()
        except Exception:
            _swallow()
        try:
            self._load_cache()
        except Exception:
            _swallow()
        # نمونه را خودکار بارگذاری نکن

    def _apply_style(self):
        self.setStyleSheet("""
            AnalysisPage, QWidget { background: #F1F5F9; }
            QTabWidget::pane { border: 1px solid #c5d0de; background: white; border-radius: 6px; }
            QTabBar::tab {
                background: #e2eaf2; color: #0F172A; padding: 8px 18px;
                margin-right: 2px; border-top-left-radius: 6px; border-top-right-radius: 6px;
                font-weight: 600;
            }
            QTabBar::tab:selected { background: #1565C0; color: white; }
            QPushButton {
                background: #1565C0; color: white; border: none; border-radius: 6px;
                padding: 8px 16px; font-weight: 600;
            }
            QPushButton:hover { background: #1976D2; }
            QPushButton#danger { background: #c0392b; }
            QPushButton#success { background: #27ae60; }
            QLineEdit, QComboBox {
                border: 1px solid #b0bec5; border-radius: 5px; padding: 6px 10px;
                background: white;
            }
            QGroupBox {
                font-weight: 700; color: #0F172A; border: 1px solid #c5d0de;
                border-radius: 8px; margin-top: 10px; padding-top: 12px;
            }
            QGroupBox::title { subcontrol-origin: margin; right: 12px; padding: 0 6px; }
            QHeaderView::section {
                background: #1565C0; color: white; padding: 6px; font-weight: 600;
                border: none;
            }
            QTableView {
                gridline-color: #e0e6ed; selection-background-color: #d6e6f5;
                font-size: 12px;
            }
            QStatusBar { background: #0F172A; color: white; }
            QLabel { background: transparent; }
            QLabel#kpiValue { font-size: 18px; font-weight: 700; color: #0F172A; background: transparent; }
            QLabel#kpiLabel { font-size: 11px; color: #607d8b; background: transparent; }
            QFrame#kpiCard {
                background: white; border-radius: 12px; border: 1px solid #e2e8f0;
                border-right: 4px solid #1565C0;
            }
        """)

    def _kpi_card(self, title, value_label, color="#1565C0"):
        frame = QFrame()
        frame.setObjectName("kpiCard")
        frame.setStyleSheet(
            f"QFrame#kpiCard {{ background: white; border: 1px solid #e2e8f0; border-right: 4px solid {color}; "
            f"border-radius: 12px; }} QLabel {{ background: transparent; border: none; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 10)
        lbl = QLabel(title)
        lbl.setObjectName("kpiLabel")
        lbl.setAlignment(Qt.AlignCenter)
        val = QLabel("—")
        val.setObjectName("kpiValue")
        val.setAlignment(Qt.AlignCenter)
        value_label[0] = val
        lay.addWidget(lbl)
        lay.addWidget(val)
        return frame

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 8)
        root.setSpacing(10)

        # ── نوار بالا ──
        top = QHBoxLayout()
        title = QLabel("📊 SalesMate — تحلیل فروش")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #0F172A;")
        top.addWidget(title)
        top.addStretch()

        self.btn_load = QPushButton("📂 افزودن اکسل")
        self.btn_load.clicked.connect(self.on_add_excel)
        top.addWidget(self.btn_load)

        self.btn_report = QPushButton("📋 گزارش بارگذاری")
        self.btn_report.setToolTip("گزارش آخرین بارگذاری اکسل")
        self.btn_report.clicked.connect(self.on_show_last_report)
        top.addWidget(self.btn_report)

        self.btn_sample = QPushButton("فایل نمونه")
        self.btn_sample.setObjectName("success")
        self.btn_sample.clicked.connect(self.on_load_sample)
        top.addWidget(self.btn_sample)

        self.btn_clear = QPushButton("پاک کردن داده")
        self.btn_clear.setObjectName("danger")
        self.btn_clear.clicked.connect(self.on_clear)
        top.addWidget(self.btn_clear)

        self.btn_pdf = QPushButton("📄 خروجی PDF هیئت‌مدیره")
        self.btn_pdf.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:8px;"
            "padding:8px 14px;font-weight:700;}"
            "QPushButton:hover{background:#047857;}"
        )
        self.btn_pdf.clicked.connect(self.on_export_pdf)
        top.addWidget(self.btn_pdf)

        root.addLayout(top)

        # ── KPI ──
        kpi_row = QHBoxLayout()
        self.kpi_sales = [None]
        self.kpi_sheets = [None]
        self.kpi_cust = [None]
        self.kpi_prod = [None]
        self.kpi_inv = [None]
        self.kpi_rows = [None]
        kpi_row.addWidget(self._kpi_card("کل فروش (ریال)", self.kpi_sales, "#1565C0"))
        kpi_row.addWidget(self._kpi_card("تعداد ورق", self.kpi_sheets, "#e67e22"))
        kpi_row.addWidget(self._kpi_card("مشتریان", self.kpi_cust, "#27ae60"))
        kpi_row.addWidget(self._kpi_card("محصولات", self.kpi_prod, "#8e44ad"))
        kpi_row.addWidget(self._kpi_card("فاکتورها", self.kpi_inv, "#2980b9"))
        kpi_row.addWidget(self._kpi_card("ردیف‌ها", self.kpi_rows, "#7f8c8d"))
        root.addLayout(kpi_row)

        # ── فیلترها ──
        filt = QHBoxLayout()
        filt.addWidget(QLabel("دسته:"))
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItem("همه")
        self.cmb_cat.currentTextChanged.connect(self.apply_filters)
        filt.addWidget(self.cmb_cat)

        filt.addWidget(QLabel("ماه:"))
        self.cmb_month = QComboBox()
        self.cmb_month.addItem("همه")
        self.cmb_month.currentTextChanged.connect(self.apply_filters)
        filt.addWidget(self.cmb_month)

        filt.addWidget(QLabel("جستجو:"))
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("نام مشتری / محصول / کد…")
        # debounce: بعد از توقف تایپ (۳۰۰ms) فیلتر اعمال می‌شود — نه روی هر حرف
        self._timer_search = QTimer(self)
        self._timer_search.setSingleShot(True)
        self._timer_search.setInterval(300)
        self._timer_search.timeout.connect(self.apply_filters)
        self.txt_search.textChanged.connect(lambda: self._timer_search.start())
        filt.addWidget(self.txt_search, 1)

        self.chk_my_customers = QCheckBox("فقط انتخاب‌شده‌ها در نمودار")
        self.chk_my_customers.setChecked(False)
        self.chk_my_customers.setToolTip("اگر مشتری انتخاب کرده باشید، فقط همان‌ها در نمودارها بیاید")
        self.chk_my_customers.toggled.connect(self.apply_filters)
        filt.addWidget(self.chk_my_customers)

        self.btn_pick_import = QPushButton("📥 ورود به SalesMate (حواله)")
        self.btn_pick_import.setStyleSheet(
            "QPushButton{background:#059669;color:white;border:none;border-radius:10px;"
            "padding:8px 14px;font-weight:800;}"
            "QPushButton:hover{background:#047857;}"
        )
        self.btn_pick_import.setToolTip(
            "مشتریان انتخابی → حواله‌ها / خانه / گزارش"
        )
        self.btn_pick_import.clicked.connect(lambda: self.open_import_customers_dialog(target="invoices"))
        filt.addWidget(self.btn_pick_import)

        self.btn_pick_store = QPushButton("🛒 ورود به فروشگاه")
        self.btn_pick_store.setStyleSheet(
            "QPushButton{background:#1565C0;color:white;border:none;border-radius:10px;"
            "padding:8px 14px;font-weight:800;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        self.btn_pick_store.setToolTip("مشتریان انتخابی فقط در تب فروشگاه ثبت شوند")
        self.btn_pick_store.clicked.connect(lambda: self.open_import_customers_dialog(target="store"))
        filt.addWidget(self.btn_pick_store)

        root.addLayout(filt)

        # ── تب‌ها ──
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.tab_total = QWidget()
        self.tab_mdf = QWidget()
        self.tab_raw = QWidget()
        self.tab_parq = QWidget()
        self._build_category_tabs()
        self.tabs.addTab(self.tab_total, "📈 فروش کل")
        self.tabs.addTab(self.tab_mdf, "🟦 ام‌دی‌اف")
        self.tabs.addTab(self.tab_raw, "🟩 خام")
        self.tabs.addTab(self.tab_parq, "🟧 پارکت")

        self.tab_cust = QWidget()
        self._build_cust_tab()
        self.tabs.addTab(self._scrollable_tab(self.tab_cust), "👥 مشتریان")

        self.tab_prod = QWidget()
        self._build_prod_tab()
        self.tabs.addTab(self._scrollable_tab(self.tab_prod), "📦 محصولات")

        self.tab_cat = QWidget()
        self._build_cat_tab()
        self.tabs.addTab(self.tab_cat, "📊 دسته‌ها")

        self.tab_detail = QWidget()
        self._build_detail_tab()
        self.tabs.addTab(self.tab_detail, "🔍 جزئیات")

        root.addWidget(self._status)

        # ساخت تنبل: فقط تب فعال رسم می‌شود؛ بقیه هنگام باز شدن
        self._tab_keys = {
            id(self.tab_total): "tot", id(self.tab_mdf): "mdf", id(self.tab_raw): "raw", id(self.tab_parq): "parq",
            id(self._tab_wrappers.get(id(self.tab_cust))): "cust", id(self._tab_wrappers.get(id(self.tab_prod))): "prod",
            id(self.tab_cat): "cat", id(self.tab_detail): "detail",
        }
        self._dirty = set(self._tab_keys.values())
        self.tabs.currentChanged.connect(lambda _i: self._ensure_current_tab())

    def _scrollable_tab(self, inner):
        """تب داخل اسکرول عمودی (جدول‌ها ارتفاع زیاد دارند و کل صفحه اسکرول می‌شود)."""
        if not hasattr(self, "_tab_wrappers"):
            self._tab_wrappers = {}
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(inner)
        self._tab_wrappers[id(inner)] = sc
        return sc

    def _ensure_current_tab(self):
        """تب فعلی اگر کثیف است همین حالا بازسازی شود."""
        try:
            key = self._tab_keys.get(id(self.tabs.currentWidget()))
        except Exception:
            key = None
        if not key or key not in self._dirty:
            return
        self._dirty.discard(key)
        if key in ("tot", "mdf", "raw", "parq"):
            self._draw_charts(key)
        elif key == "cust":
            self.refresh_customers()
        elif key == "prod":
            self.refresh_products()
        elif key == "cat":
            self.refresh_categories()
        elif key == "detail":
            self.refresh_details()

    def _make_scroll_charts(self, parent, chart_specs):
        """ساخت صفحه اسکرول‌پذیر با نمودارهای بزرگ."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll.setStyleSheet("QScrollArea { background: #f7fafc; border: none; }")
        holder = QWidget()
        holder.setStyleSheet("background: #f7fafc;")
        lay = QVBoxLayout(holder)
        lay.setSpacing(16)
        lay.setContentsMargins(12, 12, 12, 28)

        canvases = []
        for title, color in chart_specs:
            card = QFrame()
            card.setStyleSheet(
                "QFrame { background: white; border-radius: 14px; "
                "border: 1px solid #e2e8f0; }"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            lbl = QLabel(title)
            lbl.setStyleSheet(
                f"font-weight: 700; font-size: 13px; color: {color}; "
                "background: transparent; border: none; padding: 2px 4px;"
            )
            card_lay.addWidget(lbl)
            canvas = MplCanvas(width=9, height=3.0)
            canvas.setMinimumHeight(280)
            card_lay.addWidget(canvas)
            lay.addWidget(card)
            canvases.append(canvas)

        scroll.setWidget(holder)
        outer = QVBoxLayout(parent)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return canvases

    def _build_category_tabs(self):
        # فروش کل
        c = self._make_scroll_charts(self.tab_total, [
            ("مبلغ فروش کل — ماهانه (ریال)  ·  موس روی نقطه = مقدار دقیق", "#1a365d"),
            ("مبلغ فروش کل — هفتگی (ریال)", "#2c5282"),
        ])
        self.canvas_tot_m_amt, self.canvas_tot_w_amt = c

        # ام‌دی‌اف ملامینه/هایگلاس
        c = self._make_scroll_charts(self.tab_mdf, [
            ("مبلغ فروش ماهانه — ام‌دی‌اف (ریال)  ·  موس روی نقطه = مقدار دقیق", "#2b6cb0"),
            ("تعداد ورق ماهانه — ام‌دی‌اف ملامینه / هایگلاس", "#3182ce"),
            ("مبلغ فروش هفتگی — ام‌دی‌اف (ریال)", "#2b6cb0"),
            ("تعداد ورق هفتگی — ام‌دی‌اف ملامینه / هایگلاس", "#3182ce"),
        ])
        self.canvas_mdf_m_amt, self.canvas_mdf_m_qty, self.canvas_mdf_w_amt, self.canvas_mdf_w_qty = c

        # خام
        c = self._make_scroll_charts(self.tab_raw, [
            ("مبلغ فروش ماهانه — خام (ریال)", "#276749"),
            ("تعداد ورق ماهانه — ام‌دی‌اف خام", "#38a169"),
            ("مبلغ فروش هفتگی — خام (ریال)", "#276749"),
            ("تعداد ورق هفتگی — ام‌دی‌اف خام", "#38a169"),
        ])
        self.canvas_raw_m_amt, self.canvas_raw_m_qty, self.canvas_raw_w_amt, self.canvas_raw_w_qty = c

        # پارکت
        c = self._make_scroll_charts(self.tab_parq, [
            ("مبلغ فروش ماهانه — پارکت (ریال)", "#c05621"),
            ("متراژ ماهانه — پارکت (مترمربع)", "#dd6b20"),
            ("مبلغ فروش هفتگی — پارکت (ریال)", "#c05621"),
            ("متراژ هفتگی — پارکت (مترمربع)", "#dd6b20"),
        ])
        self.canvas_parq_m_amt, self.canvas_parq_m_qty, self.canvas_parq_w_amt, self.canvas_parq_w_qty = c

        # جدول حواله‌های ۲ هفته‌ی اخیر (بعد از نمودارها) برای خام و پارکت
        self._recent_ui = {}
        for key, tab, color, u1, u2 in (("mdf", self.tab_mdf, "#2b6cb0", "پالت", "ورق"),
                                        ("raw", self.tab_raw, "#276749", "پالت", "ورق"),
                                        ("parq", self.tab_parq, "#c05621", "کارتن", "متر مربع")):
            try:
                holder_lay = tab.findChild(QScrollArea).widget().layout()
                card = QFrame()
                card.setStyleSheet("QFrame { background: white; border-radius: 14px; border: 1px solid #e2e8f0; }")
                cl = QVBoxLayout(card)
                cl.setContentsMargins(14, 12, 14, 12)
                lbl = QLabel("")
                lbl.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {color}; background: transparent; border: none; padding: 2px 4px;")
                cl.addWidget(lbl)
                drow = QHBoxLayout()
                _es = "QLineEdit{border:1px solid #CBD5E1;border-radius:8px;padding:5px 8px;background:#fff;}"
                e1, e2 = QLineEdit(), QLineEdit()
                for e, ph in ((e1, "از تاریخ 1405/08/01"), (e2, "تا تاریخ 1405/08/12")):
                    e.setPlaceholderText(ph); e.setFixedWidth(170); e.setStyleSheet(_es)
                    e.setLayoutDirection(Qt.LeftToRight)
                b_go = QPushButton("نمایش بازه")
                b_rc = QPushButton("۲ هفته‌ی اخیر")
                for b in (b_go, b_rc):
                    b.setCursor(Qt.PointingHandCursor)
                    b.setStyleSheet("QPushButton{background:#1565C0;color:#fff;border:none;border-radius:8px;padding:6px 14px;font-weight:700;}")
                b_rc.setStyleSheet("QPushButton{background:#E2E8F0;color:#0F172A;border:none;border-radius:8px;padding:6px 14px;font-weight:700;}")
                b_go.clicked.connect(lambda _=False, k=key: self._fill_recent(k, self.df))
                e1.returnPressed.connect(lambda k=key: self._fill_recent(k, self.df))
                e2.returnPressed.connect(lambda k=key: self._fill_recent(k, self.df))
                def _reset(_=False, k=key, a=e1, b=e2):
                    a.clear(); b.clear(); self._fill_recent(k, self.df)
                b_rc.clicked.connect(_reset)
                for w in (e1, e2, b_go, b_rc):
                    drow.addWidget(w)
                drow.addStretch(1)
                cl.addLayout(drow)
                tbl = QTableWidget(0, 6)
                tbl.setLayoutDirection(Qt.RightToLeft)
                tbl.setHorizontalHeaderLabels(["تاریخ", "شماره حواله", "مشتری", u1, u2, "مبلغ (ریال)"])
                tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
                tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
                tbl.verticalHeader().setVisible(False)
                tbl.setAlternatingRowColors(True)
                tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                hh = tbl.horizontalHeader()
                hh.setSectionResizeMode(QHeaderView.Interactive)
                hh.setSectionResizeMode(2, QHeaderView.Stretch)
                for ci, w in ((0, 100), (1, 100), (3, 90), (4, 110), (5, 150)):
                    tbl.setColumnWidth(ci, w)
                cl.addWidget(tbl)
                holder_lay.addWidget(card)
                self._recent_ui[key] = (lbl, tbl, e1, e2)
            except Exception:
                _swallow()

    # ── تب مشتریان ──
    def _build_cust_tab(self):
        lay = QVBoxLayout(self.tab_cust)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("مرتب‌سازی:"))
        self.cmb_cust_sort = QComboBox()
        self.cmb_cust_sort.addItems([
            "مبلغ فروش ↓", "مبلغ فروش ↑", "تعداد ورق ↓", "تعداد خرید ↓", "نام"
        ])
        self.cmb_cust_sort.currentIndexChanged.connect(self.refresh_customers)
        bar.addWidget(self.cmb_cust_sort)
        bar.addWidget(QLabel("جستجو:"))
        self.txt_cust_search = QLineEdit()
        self.txt_cust_search.setPlaceholderText("نام مشتری یا نام/کد محصول…")
        self._timer_cust = QTimer(self)
        self._timer_cust.setSingleShot(True)
        self._timer_cust.setInterval(250)
        self._timer_cust.timeout.connect(self.refresh_customers)
        self.txt_cust_search.textChanged.connect(lambda: self._timer_cust.start())
        bar.addWidget(self.txt_cust_search, 1)
        lay.addLayout(bar)

        split = QVBoxLayout()
        self.tbl_cust = QTableView()
        self.tbl_cust.setMinimumHeight(560)
        self.tbl_cust.setAlternatingRowColors(True)
        self.tbl_cust.setSelectionBehavior(QTableView.SelectRows)
        self.tbl_cust.setTextElideMode(Qt.ElideNone)
        self.tbl_cust.setWordWrap(False)
        self.tbl_cust.clicked.connect(self.on_cust_clicked)
        self.model_cust = PandasModel()
        self.tbl_cust.setModel(self.model_cust)
        self.tbl_cust.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_cust.horizontalHeader().setStretchLastSection(True)
        self.tbl_cust.horizontalHeader().sectionClicked.connect(
            lambda col: self.model_cust.sort_by_column(col)
        )
        split.addWidget(self.tbl_cust, 3)

        self.tbl_cust_detail = QTableView()
        self.tbl_cust_detail.setMinimumHeight(340)
        self.tbl_cust_detail.setAlternatingRowColors(True)
        self.tbl_cust_detail.setTextElideMode(Qt.ElideNone)
        self.model_cust_detail = PandasModel()
        self.tbl_cust_detail.setModel(self.model_cust_detail)
        self.tbl_cust_detail.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_cust_detail.horizontalHeader().setStretchLastSection(True)
        self.tbl_cust_detail.horizontalHeader().sectionClicked.connect(
            lambda col: self.model_cust_detail.sort_by_column(col)
        )
        split.addWidget(self.tbl_cust_detail, 2)
        lay.addLayout(split)

    # ── تب محصولات ──
    def _build_prod_tab(self):
        lay = QVBoxLayout(self.tab_prod)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("مرتب‌سازی:"))
        self.cmb_prod_sort = QComboBox()
        self.cmb_prod_sort.addItems([
            "مبلغ فروش ↓", "تعداد ورق ↓", "تعداد خرید ↓", "نام"
        ])
        self.cmb_prod_sort.currentIndexChanged.connect(self.refresh_products)
        bar.addWidget(self.cmb_prod_sort)
        bar.addWidget(QLabel("جستجو:"))
        self.txt_prod_search = QLineEdit()
        self.txt_prod_search.setPlaceholderText("نام یا کد محصول…")
        self._timer_prod = QTimer(self)
        self._timer_prod.setSingleShot(True)
        self._timer_prod.setInterval(250)
        self._timer_prod.timeout.connect(self.refresh_products)
        self.txt_prod_search.textChanged.connect(lambda: self._timer_prod.start())
        bar.addWidget(self.txt_prod_search, 1)
        lay.addLayout(bar)

        split = QVBoxLayout()
        self.tbl_prod = QTableView()
        self.tbl_prod.setMinimumHeight(560)
        self.tbl_prod.setAlternatingRowColors(True)
        self.tbl_prod.setSelectionBehavior(QTableView.SelectRows)
        self.tbl_prod.setTextElideMode(Qt.ElideNone)
        self.tbl_prod.setWordWrap(False)
        self.tbl_prod.clicked.connect(self.on_prod_clicked)
        self.model_prod = PandasModel()
        self.tbl_prod.setModel(self.model_prod)
        self.tbl_prod.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_prod.horizontalHeader().setStretchLastSection(True)
        self.tbl_prod.horizontalHeader().setMinimumSectionSize(80)
        self.tbl_prod.horizontalHeader().sectionClicked.connect(
            lambda col: self.model_prod.sort_by_column(col)
        )
        # ستون نام کالا عریض‌تر
        self.tbl_prod.setColumnWidth(1, 420)
        split.addWidget(self.tbl_prod, 3)

        self.tbl_prod_detail = QTableView()
        self.tbl_prod_detail.setMinimumHeight(340)
        self.tbl_prod_detail.setAlternatingRowColors(True)
        self.tbl_prod_detail.setTextElideMode(Qt.ElideNone)
        self.model_prod_detail = PandasModel()
        self.tbl_prod_detail.setModel(self.model_prod_detail)
        self.tbl_prod_detail.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_prod_detail.horizontalHeader().setStretchLastSection(True)
        self.tbl_prod_detail.horizontalHeader().sectionClicked.connect(
            lambda col: self.model_prod_detail.sort_by_column(col)
        )
        split.addWidget(self.tbl_prod_detail, 2)
        lay.addLayout(split)

    # ── تب دسته ──
    def _build_cat_tab(self):
        lay = QVBoxLayout(self.tab_cat)
        self.tbl_cat = QTableView()
        self.tbl_cat.setAlternatingRowColors(True)
        self.tbl_cat.setTextElideMode(Qt.ElideNone)
        self.model_cat = PandasModel()
        self.tbl_cat.setModel(self.model_cat)
        self.tbl_cat.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_cat.horizontalHeader().sectionClicked.connect(
            lambda col: self.model_cat.sort_by_column(col)
        )
        lay.addWidget(self.tbl_cat)
        self.canvas_cat = MplCanvas(width=7, height=2.8)
        lay.addWidget(self.canvas_cat)

    # ── تب جزئیات ──
    def _build_detail_tab(self):
        lay = QVBoxLayout(self.tab_detail)
        bar = QHBoxLayout()
        bar.addWidget(QLabel("جستجو در ردیف‌ها:"))
        self.txt_detail_search = QLineEdit()
        self._timer_detail = QTimer(self)
        self._timer_detail.setSingleShot(True)
        self._timer_detail.setInterval(250)
        self._timer_detail.timeout.connect(self.refresh_details)
        self.txt_detail_search.textChanged.connect(lambda: self._timer_detail.start())
        bar.addWidget(self.txt_detail_search, 1)
        lay.addLayout(bar)
        self.tbl_detail = QTableView()
        self.tbl_detail.setAlternatingRowColors(True)
        self.tbl_detail.setTextElideMode(Qt.ElideNone)
        self.model_detail = PandasModel()
        self.proxy_detail = FilterProxy()
        self.proxy_detail.setSourceModel(self.model_detail)
        self.tbl_detail.setModel(self.proxy_detail)
        self.tbl_detail.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.tbl_detail.horizontalHeader().setStretchLastSection(True)
        self.tbl_detail.horizontalHeader().setMinimumSectionSize(60)
        self.tbl_detail.horizontalHeader().sectionClicked.connect(self._on_detail_header_click)
        lay.addWidget(self.tbl_detail)

    # ───────────── بارگذاری داده ─────────────



    def _save_selected_customers(self):
        try:
            data = {
                "invoices": sorted(getattr(self, "_selected_import_customers", set()) or set()),
                "store": sorted(getattr(self, "_selected_store_customers", set()) or set()),
                "store_seeded": bool(getattr(self, "_store_seeded", False)),
                "store_prefix_seen": sorted(getattr(self, "_store_prefix_seen", None) or []),
            }
            ANALYSIS_SELECTED.parent.mkdir(parents=True, exist_ok=True)
            ANALYSIS_SELECTED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            _swallow()

    def _load_selected_customers(self):
        try:
            if not ANALYSIS_SELECTED.exists():
                return
            data = json.loads(ANALYSIS_SELECTED.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._selected_import_customers = set(str(x) for x in (data.get("invoices") or []) if str(x).strip())
                self._selected_store_customers = set(str(x) for x in (data.get("store") or []) if str(x).strip())
                self._store_seeded = bool(data.get("store_seeded", False))
                if "store_prefix_seen" in data:
                    self._store_prefix_seen = set(str(x) for x in (data.get("store_prefix_seen") or []))
            elif isinstance(data, list):
                self._selected_import_customers = set(str(x) for x in data if str(x).strip())
        except Exception:
            _swallow()

    def _store_keys(self):
        """customer_key مشتریان فروشگاه — فقط انتخاب صریح کاربر (نه پیشوند نام)."""
        return {customer_key(x) for x in (getattr(self, "_selected_store_customers", set()) or set())}

    def _seed_store_prefix(self):
        """مشتریانی که نامشان «فروشگاه ایزوفام…» است و برای اولین بار در اکسل دیده می‌شوند، خودکار به فروشگاه اضافه می‌شوند.
        اگر کاربر خودش تیک یکی را برداشته باشد (در پنجره‌ی انتخاب) دیگر برنگردانده نمی‌شود."""
        try:
            if self.df is None or self.df.empty or "نام مشتری" not in self.df.columns:
                return
            cur = set(getattr(self, "_selected_store_customers", set()) or set())
            seen = getattr(self, "_store_prefix_seen", None)
            if seen is None:
                # نسخه‌ی قدیمی: آنچه الان تیک خورده را «دیده‌شده» حساب کن
                seen = {customer_key(x) for x in cur if customer_key(x).startswith(STORE_PREFIX_KEY)}
            seen = set(seen)
            names = [n for n in self.df["نام مشتری"].astype(str).str.strip().unique().tolist()
                     if customer_key(n).startswith(STORE_PREFIX_KEY)]
            cur_keys = {customer_key(x) for x in cur}
            add = [n for n in names if customer_key(n) not in seen and customer_key(n) not in cur_keys]
            for n in names:
                seen.add(customer_key(n))
            self._store_prefix_seen = seen
            self._store_seeded = True
            if add:
                self._selected_store_customers = cur | set(add)
            self._save_selected_customers()
        except Exception:
            _swallow()

    def _analysis_imported_customers(self):
        """مشتریانی که قبلاً از تحلیل وارد SalesMate شده‌اند (از خود دیتابیس).
        این منبع با خود salesmate.db جابه‌جا می‌شود، پس حتی اگر فایل انتخاب‌ها گم شود،
        مشتریِ «قبلاً تیک‌خورده» شناخته می‌شود. با برداشتن تیک، حواله‌هایشان پاک و از این لیست خارج می‌شوند."""
        import sqlite3
        out = set()
        try:
            c = sqlite3.connect(str(self._salesmate_db_path()))
            try:
                rows = c.execute(
                    "SELECT DISTINCT customer FROM invoices "
                    "WHERE customer IS NOT NULL AND (inquiry_data LIKE '%analysis_import%' OR invoice_no LIKE 'AN-%')"
                ).fetchall()
            finally:
                c.close()
            out = {str(r[0]).strip() for r in rows if r and str(r[0]).strip()}
        except Exception:
            _swallow()
        return out

    def _auto_import_selected(self, silent=True):
        """بعد از اکسل جدید: مشتریان تیک‌خورده را خودکار وارد SalesMate کن (بدون تکراری).
        تطبیق نام با customer_key انجام می‌شود (نه برابری دقیق رشته)."""
        self._auto_stats = {}
        if self.df is None or self.df.empty or "نام مشتری" not in self.df.columns:
            return 0
        df_names = self.df["نام مشتری"].astype(str).str.strip().unique().tolist()
        saved_inv = set(getattr(self, "_selected_import_customers", set()) or set())
        saved_store = set(getattr(self, "_selected_store_customers", set()) or set())
        db_inv = self._analysis_imported_customers()

        # مشتریان واگذارشده به همکاران از ورود خودکار خود مالک کنار می‌روند
        cw_excl, cw_synced = set(), 0     # cw_excl = {(ckey, kind)} واگذارشده
        cwm = self._cw_module()
        self._cw_excl_pairs = set()
        if cwm is not None:
            try:
                cw_excl = set(cwm["core"].load_assignments(cwm["request"]).keys())
                self._cw_excl_pairs = set(cw_excl)
            except Exception:
                _swallow()
        cw_cks = {k[0] for k in cw_excl}
        self._seed_store_prefix()
        saved_store = set(getattr(self, "_selected_store_customers", set()) or set())
        skeys = {customer_key(x) for x in saved_store}
        store_names = list(dict.fromkeys(names_matching(df_names, saved_store)))
        inv_names = [n for n in names_matching(df_names, saved_inv | db_inv)
                     if customer_key(n) not in skeys]
        cw_skipped = [n for n in inv_names if customer_key(n) in cw_cks]   # ردیف‌های واگذارشده‌شان در ورود حذف می‌شود

        # انتخاب‌ها را پایدار کن تا دفعه‌ی بعد هم از فایل خوانده شوند
        try:
            changed = False
            if inv_names and not {customer_key(x) for x in inv_names} <= {customer_key(x) for x in saved_inv}:
                self._selected_import_customers = saved_inv | set(inv_names)
                changed = True
            if changed:
                self._save_selected_customers()
        except Exception:
            _swallow()

        total_added = 0
        agg = {"customers": len(set(inv_names) | set(store_names)), "added": 0, "store": 0, "skipped": 0, "fixed": 0}
        for names, force in ((inv_names, False), (store_names, True)):
            if not names:
                continue
            try:
                self._last_import_stats = {}
                n = self._do_import_selected(names, skip_dup=True, paid_full=True, force_store=force, silent=silent)
                total_added += int(n or 0)
                st = getattr(self, "_last_import_stats", {}) or {}
                agg["added"] += int(st.get("added", 0))
                agg["store"] += int(st.get("store", 0))
                agg["skipped"] += int(st.get("skipped", 0))
                agg["fixed"] += int(st.get("fixed", 0))
            except Exception:
                _swallow()
        # ارسال حواله‌های اکسل مشتریان همکاران به صف آن‌ها
        if cwm is not None and cw_excl:
            try:
                _cw_stats = {}
                cw_synced = cwm["core"].sync_feed(cwm["request"], self.df, None, self._store_keys(), stats=_cw_stats)
                try:
                    _labels = {a["user_id"]: a["label"] for a in cwm["core"].load_accounts(cwm["request"])}
                    agg["cw_by"] = sorted(
                        [(_labels.get(u, u[:8]), int(n)) for u, n in _cw_stats.items() if int(n) > 0],
                        key=lambda x: -x[1])
                except Exception:
                    _swallow()
                try:
                    cwm["core"].push_free_snapshots(cwm["request"], self.df, None, self._store_keys())
                except Exception:
                    _swallow()
            except Exception as ex:
                _swallow()
                agg["cw_error"] = str(ex)[:80]
        agg["cw_synced"] = int(cw_synced)
        agg["cw_skipped"] = len(cw_skipped)
        self._auto_stats = agg
        try:
            if cw_synced or cw_skipped:
                self._status.setText("همکاران: %d حواله‌ی جدید در صف ارسال | %d مشتری دارای ردیف واگذارشده به همکار (آن ردیف‌ها وارد حواله‌های شما نشد)"
                                     % (cw_synced, len(cw_skipped)))
        except Exception:
            _swallow()
        return total_added

    def _cw_module(self):
        """فقط حساب مالک با ابر فعال: {'core','request'} وگرنه None."""
        try:
            mod = None
            for mn in ("__main__", "main", "salesmate.main"):
                m = sys.modules.get(mn)
                if m is not None and hasattr(m, "supabase_request"):
                    mod = m
                    break
            if mod is None or not mod.supabase_session_valid():
                return None
            try:
                import coworker_core as cwc
            except Exception:
                from salesmate import coworker_core as cwc
            if not cwc.is_owner_email(mod.supabase_user_info().get("email")):
                return None
            return {"core": cwc, "request": mod.supabase_request}
        except Exception:
            return None

    def _save_cache(self):
        try:
            if self.df is None or self.df.empty:
                for p in (ANALYSIS_CACHE, ANALYSIS_CACHE_CSV):
                    if p.exists():
                        try:
                            p.unlink()
                        except Exception:
                            _swallow()
                return
            ANALYSIS_CACHE.parent.mkdir(parents=True, exist_ok=True)
            # pickle اصلی
            self.df.to_pickle(str(ANALYSIS_CACHE))
            # پشتیبان CSV برای بازیابی مطمئن‌تر
            try:
                self.df.to_csv(str(ANALYSIS_CACHE_CSV), index=False, encoding="utf-8-sig")
            except Exception:
                _swallow()
            # داده‌ی تازه → آمار پارکت/سمپل برای اپ موبایل هم به ابر برود
            try:
                try:
                    import app_core as _core
                except Exception:
                    from salesmate import app_core as _core
                _core.schedule_supabase_sync()
            except Exception:
                _swallow()
        except Exception as ex:
            try:
                self._status.setText("خطا در ذخیره کش تحلیل: " + str(ex)[:80])
            except Exception:
                _swallow()

    def _load_cache(self):
        df = None
        try:
            if ANALYSIS_CACHE.exists():
                df = pd.read_pickle(str(ANALYSIS_CACHE))
        except Exception:
            df = None
        if df is None or getattr(df, "empty", True):
            try:
                if ANALYSIS_CACHE_CSV.exists():
                    df = pd.read_csv(str(ANALYSIS_CACHE_CSV), encoding="utf-8-sig")
            except Exception:
                df = None
        try:
            if df is None or getattr(df, "empty", True):
                return False
            try:
                df = fix_unit_order(df)
            except Exception:
                _swallow()
            try:
                df = renorm_dedupe(df)
            except Exception:
                _swallow()
            self.df = df
            try:
                self._fill_filter_combos()
            except Exception:
                _swallow()
            try:
                self.apply_filters()
            except Exception:
                self.df_f = self.df
            try:
                self._status.setText(f"بازیابی از حافظه: {len(self.df):,} ردیف")
            except Exception:
                _swallow()
            return True
        except Exception:
            return False

    def on_load_sample(self):
        if not SAMPLE_PATH.exists():
            QMessageBox.warning(self, "فایل نمونه", "فایل نمونه پیدا نشد.\nفایل sample_sales.xlsx را در پوشه‌ی analysis_data کنار برنامه بگذار.")
            return
        self._load_paths([SAMPLE_PATH], replace=True, show_report=False)

    def on_add_excel(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "انتخاب فایل اکسل",
            str(APP_DIR),
            "Excel (*.xlsx *.xls);;All (*.*)"
        )
        if paths:
            self._load_paths(paths, replace=False)

    def on_clear(self):
        self.df = pd.DataFrame()
        self.df_f = pd.DataFrame()
        try:
            self._save_cache()
        except Exception:
            _swallow()
        self._refresh_all()
        self._status.setText("داده‌ها پاک شد")

    def _load_paths(self, paths, replace=False, show_report=True):
        frames = []
        errors = []
        files_info = []
        for p in paths:
            try:
                raw = load_excel(p)
                frames.append(clean_df(raw))
                files_info.append((Path(p).name, int(len(raw))))
            except Exception as e:
                errors.append(f"{Path(p).name}: {e}")
        if not frames:
            QMessageBox.critical(self, "خطا", "هیچ فایلی خوانده نشد.\n" + "\n".join(errors))
            return
        try:
            if self.df is not None and not self.df.empty:
                self.df = renorm_dedupe(self.df)
        except Exception:
            _swallow()
        old_df = self.df.copy() if (self.df is not None and not self.df.empty) else pd.DataFrame()
        new_df = pd.concat(frames, ignore_index=True)
        before = len(new_df)
        new_df = new_df.drop_duplicates(subset=["unique_key"], keep="first")
        dup = before - len(new_df)

        if replace or self.df.empty:
            self.df = new_df
        else:
            combined = pd.concat([self.df, new_df], ignore_index=True)
            before2 = len(combined)
            self.df = combined.drop_duplicates(subset=["unique_key"], keep="first")
            dup += before2 - len(self.df)

        try:
            self.df = fix_unit_order(self.df)
        except Exception:
            _swallow()
        self._fill_filter_combos()
        self.apply_filters()
        try:
            self._save_cache()
        except Exception:
            _swallow()
        auto_n = 0
        try:
            auto_n = self._auto_import_selected(silent=True) or 0
        except Exception:
            auto_n = 0
        msg = f"بارگذاری شد: {len(self.df):,} ردیف"
        if dup:
            msg += f" | {dup:,} تکراری حذف شد"
        if auto_n:
            msg += f" | خودکار وارد شد: {auto_n:,} حواله/فروش جدید برای مشتریان تیک‌خورده"
        _st = getattr(self, "_auto_stats", None) or {}
        if _st.get("fixed"):
            msg += f" | {int(_st['fixed']):,} حواله‌ی موجود با اکسل اصلاح شد"
        if _st.get("cw_synced") or _st.get("cw_skipped"):
            msg += f" | همکاران: {int(_st.get('cw_synced', 0)):,} حواله در صف ارسال، {int(_st.get('cw_skipped', 0)):,} مشتری دارای ردیف واگذارشده به همکار (آن ردیف‌ها وارد حواله‌های شما نشد)"
        self._status.setText(msg)

        # گزارش بعد از بارگذاری
        try:
            rep = build_upload_report(old_df, new_df, self.df, replace=replace, files=files_info,
                                      errors=errors, dup_removed=dup)
            st = dict(getattr(self, "_auto_stats", None) or {})
            if st.get("customers") or st.get("cw_by") or st.get("cw_skipped") or st.get("fixed"):
                rep["auto"] = st
            rep["cloud"] = self._cloud_state_text(bool(auto_n))
            self._last_report = rep
            self._save_report_history(rep)
            if show_report:
                self._show_upload_report(rep)
        except Exception:
            _swallow()
            if errors:
                QMessageBox.warning(self, "هشدار", "\n".join(errors))

    # ───────────── گزارش بارگذاری ─────────────
    def _cloud_state_text(self, did_import):
        """وضعیت ارسال به ابر برای خط آخر گزارش."""
        try:
            mod = None
            for mn in ("__main__", "main", "salesmate.main"):
                m = sys.modules.get(mn)
                if m is not None and hasattr(m, "supabase_enabled"):
                    mod = m
                    break
            if mod is None:
                return ""
            if not (mod.supabase_enabled() and mod.supabase_session_valid()):
                return "ابر: وارد حساب نشده‌اید؛ تغییرات فقط روی همین سیستم ذخیره شد." if did_import else ""
            return "ارسال به ابر چند ثانیه‌ی دیگر خودکار انجام می‌شود." if did_import else "تغییری برای ارسال به ابر نبود."
        except Exception:
            _swallow()
            return ""

    def _save_report_history(self, rep):
        try:
            import time as _t
            hist = []
            if ANALYSIS_REPORTS.exists():
                hist = json.loads(ANALYSIS_REPORTS.read_text(encoding="utf-8"))
                if not isinstance(hist, list):
                    hist = []
            item = {"ts": _t.strftime("%Y-%m-%d %H:%M"), "rep": rep}
            hist.append(item)
            ANALYSIS_REPORTS.write_text(
                json.dumps(hist[-20:], ensure_ascii=False, default=lambda o: sorted(o) if isinstance(o, set) else str(o)),
                encoding="utf-8")
        except Exception:
            _swallow()

    def _show_upload_report(self, rep):
        from PySide6.QtWidgets import QTextBrowser
        dlg = QDialog(self)
        dlg.setWindowTitle("گزارش بارگذاری اکسل")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(640, 640)
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setHtml(report_to_html(rep))
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        btn_copy = QPushButton("کپی متن")
        btn_copy.clicked.connect(lambda: QApplication.clipboard().setText(tb.toPlainText()))
        btn_close = QPushButton("بستن")
        btn_close.clicked.connect(dlg.accept)
        row.addWidget(btn_copy)
        row.addStretch(1)
        row.addWidget(btn_close)
        lay.addLayout(row)
        dlg.exec()

    def on_show_last_report(self):
        rep = getattr(self, "_last_report", None)
        if rep is None:
            try:
                if ANALYSIS_REPORTS.exists():
                    hist = json.loads(ANALYSIS_REPORTS.read_text(encoding="utf-8"))
                    if hist:
                        rep = hist[-1].get("rep")
            except Exception:
                _swallow()
        if not rep:
            QMessageBox.information(self, "گزارش", "هنوز اکسلی بارگذاری نشده است.")
            return
        self._show_upload_report(rep)

    def _fill_filter_combos(self):
        cats = sorted(self.df["دسته"].dropna().unique().tolist()) if not self.df.empty else []
        months = sorted(self.df["ماه"].dropna().unique().tolist()) if not self.df.empty else []
        cur_c = self.cmb_cat.currentText()
        cur_m = self.cmb_month.currentText()
        self.cmb_cat.blockSignals(True)
        self.cmb_month.blockSignals(True)
        self.cmb_cat.clear()
        self.cmb_cat.addItem("همه")
        self.cmb_cat.addItems(cats)
        self.cmb_month.clear()
        self.cmb_month.addItem("همه")
        self.cmb_month.addItems(months)
        if cur_c in [self.cmb_cat.itemText(i) for i in range(self.cmb_cat.count())]:
            self.cmb_cat.setCurrentText(cur_c)
        if cur_m in [self.cmb_month.itemText(i) for i in range(self.cmb_month.count())]:
            self.cmb_month.setCurrentText(cur_m)
        self.cmb_cat.blockSignals(False)
        self.cmb_month.blockSignals(False)



    def _salesmate_db_path(self):
        candidates = []
        try:
            if getattr(sys, "frozen", False):
                base = Path(sys.executable).resolve().parent
                candidates += [base / "salesmate.db", base / "_internal" / "salesmate.db"]
            here = Path(__file__).resolve().parent
            candidates += [here.parent / "salesmate.db", here / "salesmate.db", APP_DIR / "salesmate.db"]
            candidates.append(Path.cwd() / "salesmate.db")
            if self.win is not None:
                try:
                    candidates.insert(0, Path(self.win.__class__.__module__ and APP_DIR) / "salesmate.db")
                except Exception:
                    _swallow()
        except Exception:
            _swallow()
        for c in candidates:
            try:
                if c and Path(c).exists():
                    return Path(c)
            except Exception:
                _swallow()
        # ساخت کنار APP_DIR
        try:
            p = APP_DIR / "salesmate.db"
            return p
        except Exception:
            return Path("salesmate.db")

    def open_import_customers_dialog(self, target="invoices"):
        """انتخاب مشتریان از فروش کل شرکت و ورود به دیتابیس SalesMate."""
        if self.df is None or self.df.empty or "نام مشتری" not in self.df.columns:
            QMessageBox.warning(self, "ورود به SalesMate", "اول فایل فروش را بارگذاری کنید.")
            return

        # خلاصه فروش هر مشتری
        g = (
            self.df.groupby("نام مشتری", dropna=False)
            .agg(rows=("نام مشتری", "count"), amount=("مبلغ", "sum"))
            .reset_index()
            .sort_values("amount", ascending=False)
        )

        self._seed_store_prefix()
        store_keys = self._store_keys()
        sm_norm = getattr(self, "_sm_customers_norm", set()) or set()
        try:
            self.reload_salesmate_customers(silent=True)
            sm_norm = getattr(self, "_sm_customers_norm", set()) or set()
        except Exception:
            _swallow()

        dlg = QDialog(self)
        dlg.setWindowTitle("ورود به فروشگاه" if target == "store" else "ورود به SalesMate (حواله)")
        dlg.resize(720, 560)
        dlg.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(dlg)

        tip = QLabel(
            "تیک = ورود حواله‌های آن مشتری | برداشتن تیک = حذف حواله‌های واردشده از تحلیل برای همان مشتری.\n"
            "مبالغ به ریال (همان اکسل). "
            + ("مقصد: فروشگاه." if target == "store" else "مقصد: حواله / خانه / گزارش.")
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#334155;font-size:13px;")
        lay.addWidget(tip)

        search_box = QLineEdit()
        search_box.setPlaceholderText("جستجوی نام مشتری…")
        search_box.setClearButtonEnabled(True)
        lay.addWidget(search_box)

        bar = QHBoxLayout()
        btn_all = QPushButton("انتخاب همه")
        btn_none = QPushButton("هیچ‌کدام")
        btn_sm = QPushButton("انتخاب مشتریان قبلی SalesMate")
        bar.addWidget(btn_all)
        bar.addWidget(btn_none)
        bar.addWidget(btn_sm)
        bar.addStretch()
        lay.addLayout(bar)

        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.NoSelection)
        if target == "store":
            prev = getattr(self, "_selected_store_customers", set()) or set()
        else:
            prev = getattr(self, "_selected_import_customers", set()) or set()

        for _, row in g.iterrows():
            name = str(row["نام مشتری"])
            amt = float(row["amount"] or 0)
            rows_n = int(row["rows"] or 0)
            is_sm = match_salesmate_customer(name, sm_norm) if sm_norm else False
            label = f"{name}   |   {amt:,.0f} ریال   |   {rows_n} ردیف"
            if is_sm:
                label += "   ✓ قبلاً در SalesMate"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            # پیش‌فرض فروشگاه: فقط انتخاب‌های قبلیِ فروشگاه. پیش‌فرض حواله: قبلی‌ها یا مشتریان SalesMate، به‌جز مشتریان فروشگاه
            in_store = customer_key(name) in store_keys
            if target == "store":
                checked = in_store or (name in prev)
            else:
                checked = ((name in prev) or is_sm) and not in_store
                if in_store:
                    label += "   🛒 فروشگاه"
                    item.setText(label)
            item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            item.setData(Qt.UserRole, name)
            lst.addItem(item)

        lay.addWidget(lst, 1)

        def sel_all(state):
            for i in range(lst.count()):
                lst.item(i).setCheckState(Qt.Checked if state else Qt.Unchecked)

        def filter_list(text):
            q = (text or "").strip().lower()
            for i in range(lst.count()):
                it = lst.item(i)
                name = str(it.data(Qt.UserRole) or "").lower()
                label = it.text().lower()
                it.setHidden(bool(q) and q not in name and q not in label)

        search_box.textChanged.connect(filter_list)

        btn_all.clicked.connect(lambda: sel_all(True))
        btn_none.clicked.connect(lambda: sel_all(False))

        def sel_sm():
            for i in range(lst.count()):
                it = lst.item(i)
                name = it.data(Qt.UserRole)
                it.setCheckState(Qt.Checked if match_salesmate_customer(name, sm_norm)
                                 and (target == "store" or customer_key(name) not in store_keys) else Qt.Unchecked)

        btn_sm.clicked.connect(sel_sm)

        opt = QCheckBox("اگر حواله تکراری بود رد شو (پیشنهادی)")
        opt.setChecked(True)
        lay.addWidget(opt)

        opt_paid = QCheckBox("مبلغ پرداختی = مبلغ کل (بدون بدهکاری)")
        opt_paid.setChecked(True)
        lay.addWidget(opt_paid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("ثبت در SalesMate")
        buttons.button(QDialogButtonBox.Cancel).setText("انصراف")
        lay.addWidget(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)

        if dlg.exec() != QDialog.Accepted:
            return

        selected = []
        unchecked = []
        all_names = []
        for i in range(lst.count()):
            it = lst.item(i)
            name = it.data(Qt.UserRole)
            all_names.append(name)
            if it.checkState() == Qt.Checked:
                selected.append(name)
            else:
                unchecked.append(name)

        if target == "store":
            self._selected_store_customers = set(selected)
            try:
                seen = set(getattr(self, "_store_prefix_seen", None) or set())
                seen |= {customer_key(n) for n in all_names if customer_key(n).startswith(STORE_PREFIX_KEY)}
                self._store_prefix_seen = seen
            except Exception:
                _swallow()
        else:
            self._selected_import_customers = set(selected)
        try:
            self._save_selected_customers()
        except Exception:
            _swallow()
        skip_dup = opt.isChecked()
        paid_full = opt_paid.isChecked()

        # حذف حواله‌های تحلیل برای تیک‌برداشته‌ها
        removed = 0
        try:
            removed = self._remove_analysis_imports_for_customers(
                unchecked, target=("store" if target == "store" else "invoices")
            )
        except Exception:
            removed = 0

        if selected:
            self._do_import_selected(
                selected, skip_dup=skip_dup, paid_full=paid_full, force_store=(target == "store")
            )
        else:
            try:
                if self.win is not None:
                    self.win.refresh_all()
            except Exception:
                _swallow()
            msg = "هیچ مشتری تیک نخورده بود."
            if removed:
                msg += f"\n{removed:,} حواله/فروش قبلیِ تحلیل حذف شد."
            QMessageBox.information(self, "همگام‌سازی", msg)
            return

        if removed:
            try:
                QMessageBox.information(
                    self, "همگام‌سازی",
                    f"علاوه بر ورود، {removed:,} مورد مربوط به مشتریان بدون تیک حذف شد."
                )
            except Exception:
                _swallow()

    
    def _remove_analysis_imports_for_customers(self, names, target="invoices"):
        """حذف حواله/فروشگاه واردشده از تحلیل برای مشتریان تیک‌برداشته."""
        import sqlite3
        names = [str(n).strip() for n in names if str(n).strip()]
        if not names:
            return 0
        db_path = self._salesmate_db_path()
        removed = 0
        try:
            c = sqlite3.connect(str(db_path))
            for name in names:
                if target == "store":
                    cur = c.execute(
                        "DELETE FROM store_sales WHERE customer=? AND (invoice_no LIKE 'AN-%' OR items_json LIKE '%analysis_import%' OR items_json LIKE '%\"code\":%')",
                        (name,),
                    )
                    # safer: only AN- prefix for store
                    cur = c.execute(
                        "DELETE FROM store_sales WHERE customer=? AND invoice_no LIKE 'AN-%'",
                        (name,),
                    )
                    removed += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                else:
                    cur = c.execute(
                        "DELETE FROM invoices WHERE customer=? AND (invoice_no LIKE 'AN-%' OR inquiry_data LIKE '%analysis_import%')",
                        (name,),
                    )
                    removed += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
            c.commit()
            c.close()
        except Exception:
            return removed
        return removed

    def _do_import_selected(self, selected_names, skip_dup=True, paid_full=True, force_store=False, silent=False):
        import sqlite3
        import zlib
        from datetime import datetime as _dt

        names = set(str(x) for x in selected_names)
        df = self.df[self.df["نام مشتری"].astype(str).isin(names)].copy()
        # ردیف‌های (مشتری، پارکت/ام دی اف) که به همکار واگذار شده در حواله‌های خود مالک نمی‌آید
        _pairs = getattr(self, "_cw_excl_pairs", None)
        if _pairs and not force_store and "دسته" in df.columns:
            try:
                try:
                    import coworker_core as _cwc
                except Exception:
                    from salesmate import coworker_core as _cwc
                _ck = df["نام مشتری"].astype(str).map(customer_key)
                _kd = df["دسته"].map(_cwc.row_kind)
                df = df[[(c, k) not in _pairs for c, k in zip(_ck, _kd)]].copy()
            except Exception:
                _swallow()
        if df.empty:
            if not silent:
                QMessageBox.warning(self, "ورود", "ردیفی برای این مشتریان پیدا نشد.")
            return 0

        # گروه: مشتری + تاریخ + شماره فرم
        if "شماره فرم" not in df.columns:
            df["شماره فرم"] = ""
        df["شماره فرم"] = df["شماره فرم"].astype(str).replace({"nan": "", "None": ""})
        df["تاریخ"] = df["تاریخ"].astype(str)

        keys = ["نام مشتری", "تاریخ", "شماره فرم"]
        groups = df.groupby(keys, dropna=False)
        _gcount = {}
        for (_n, _d, _f) in groups.groups.keys():
            _k = (_name_sig(_n), str(_d or "").strip())
            _gcount[_k] = _gcount.get(_k, 0) + 1

        db_path = self._salesmate_db_path()
        added = 0
        skipped = 0
        fixed = 0
        errors = []

        try:
            c = sqlite3.connect(str(db_path))
            # اطمینان از ستون‌ها
            cols = [r[1] for r in c.execute("PRAGMA table_info(invoices)").fetchall()]
            if not cols:
                if not silent:
                    QMessageBox.critical(self, "ورود", "جدول invoices پیدا نشد. یک‌بار اپ اصلی را باز کنید.")
                c.close()
                return 0
            for col, typ in (("inquiry_data", "TEXT DEFAULT ''"), ("paid_amount", "TEXT DEFAULT ''"), ("image_path", "TEXT DEFAULT ''")):
                if col not in cols:
                    try:
                        c.execute(f"ALTER TABLE invoices ADD COLUMN {col} {typ}")
                    except Exception:
                        _swallow()

            store_added = 0
            # نام استاندارد مشتری = همان نامی که قبلاً در دیتابیس ثبت شده (ي/ی و ... یک مشتری جدا نسازد)
            canon_names = {}
            names_by_key = {}
            try:
                for tbl in ("invoices", "store_sales"):
                    for (nm,) in c.execute(f"SELECT DISTINCT customer FROM {tbl} WHERE customer IS NOT NULL"):
                        nm = str(nm).strip()
                        canon_names.setdefault(customer_key(nm), nm)
                        names_by_key.setdefault(customer_key(nm), set()).add(nm)
            except Exception:
                _swallow()
            for (customer, date, form_no), grp in groups:
                customer = str(customer or "").strip()
                customer = canon_names.get(customer_key(customer), customer)
                canon_names.setdefault(customer_key(customer), customer)
                names_by_key.setdefault(customer_key(customer), set()).add(customer)
                _variants = sorted(names_by_key[customer_key(customer)])
                _ph = ",".join("?" * len(_variants))
                date = str(date or "").strip()
                form_no = str(form_no or "").strip()
                if not customer or not date or date in ("nan", "None"):
                    skipped += 1
                    continue
                total = int(round(float(grp["مبلغ"].sum()))) if "مبلغ" in grp.columns else 0
                if total <= 0:
                    skipped += 1
                    continue

                inv_no = form_no if form_no and form_no not in ("nan", "None", "") else ""
                if not inv_no:
                    inv_no = "AN-%s-%s" % (date.replace("/", ""), zlib.crc32((customer + date).encode("utf-8")) % 100000)

                # جزئیات کالا
                rows_meta = []
                for _, r in grp.iterrows():
                    rows_meta.append({
                        "code": str(r.get("کد کالا", "") or ""),
                        "name": str(r.get("نام کالا", "") or ""),
                        "type": str(r.get("نام کالا", "") or r.get("دسته", "") or ""),
                        "qty1": _qty_int(r.get("تعداد 1", "") or r.get("تعداد_ورق", "") or ""),
                        "qty2": str(r.get("تعداد 2", "") or ""),
                        "price": str(r.get("قیمت", "") or ""),
                        "cost": str(r.get("مبلغ", "") or ""),
                    })
                time_str = "12:00:00"
                created = _dt.now().isoformat(timespec="seconds")

                # فروشگاه ایزوفام یا دکمه «ورود به فروشگاه»
                is_store = force_store or (customer_key(customer) in self._store_keys())
                if is_store:
                    if skip_dup:
                        exists = c.execute(
                            f"SELECT id, items_json, total, '' FROM store_sales WHERE customer IN ({_ph}) AND date=? AND "
                            "(invoice_no=? OR (total=? AND invoice_no LIKE 'AN-%')) LIMIT 1",
                            (*_variants, date, inv_no, str(total)),
                        ).fetchone()
                        if not exists and _gcount.get((_name_sig(customer), date)) == 1:
                            # شماره‌ی حواله فرق دارد ولی آن روز فقط همین یک حواله‌ی اکسل برای این مشتری هست
                            _rs = c.execute(
                                f"SELECT id, items_json, total, '' FROM store_sales WHERE customer IN ({_ph}) AND date=?",
                                (*_variants, date)).fetchall()
                            if len(_rs) == 1:
                                exists = _rs[0]
                        if not exists and not inv_no.startswith("AN-"):
                            # همان شماره‌ی حواله در همان تاریخ با نوشتنِ متفاوتِ نام مشتری (مثلاً خط تیره با/بدون فاصله) = تکراری
                            exists = c.execute(
                                "SELECT id, items_json, total, '' FROM store_sales WHERE date=? AND invoice_no=? LIMIT 1",
                                (date, inv_no),
                            ).fetchone()
                        if exists:
                            try:
                                if refresh_existing_from_excel(c, "store_sales", exists[0], exists[1], exists[2], exists[3], rows_meta, total):
                                    fixed += 1
                            except Exception:
                                _swallow()
                            skipped += 1
                            continue
                    # تب بر اساس دسته غالب
                    cats = grp["دسته"].astype(str).tolist() if "دسته" in grp.columns else []
                    tab = "parquet"
                    if any("ام دی اف" in x and "خام" not in x for x in cats):
                        tab = "mdf"
                    elif any("خام" in x for x in cats):
                        tab = "raw"
                    try:
                        c.execute(
                            "INSERT INTO store_sales(customer,invoice_no,date,time,total,tab,items_json,created_at) "
                            "VALUES(?,?,?,?,?,?,?,?)",
                            (
                                customer, inv_no, date, time_str, str(total), tab,
                                json.dumps(rows_meta, ensure_ascii=False), created,
                            ),
                        )
                        store_added += 1
                        added += 1
                    except Exception as ex:
                        errors.append(str(ex))
                    continue

                if skip_dup:
                    exists = c.execute(
                        f"SELECT id, inquiry_data, total, paid_amount FROM invoices WHERE customer IN ({_ph}) AND date=? AND (invoice_no=? OR (total=? AND invoice_no LIKE 'AN-%')) LIMIT 1",
                        (*_variants, date, inv_no, str(total)),
                    ).fetchone()
                    if not exists:
                        exists = c.execute(
                            "SELECT id, inquiry_data, total, paid_amount FROM invoices WHERE invoice_no=? LIMIT 1", (inv_no,)
                        ).fetchone()
                    if not exists and _gcount.get((_name_sig(customer), date)) == 1:
                        _rs = c.execute(
                            f"SELECT id, inquiry_data, total, paid_amount FROM invoices WHERE customer IN ({_ph}) AND date=?",
                            (*_variants, date)).fetchall()
                        if len(_rs) == 1:
                            exists = _rs[0]
                    if exists:
                        try:
                            if refresh_existing_from_excel(c, "invoices", exists[0], exists[1], exists[2], exists[3], rows_meta, total):
                                fixed += 1
                        except Exception:
                            _swallow()
                        skipped += 1
                        continue

                inquiry = json.dumps({
                    "tab": "analysis_import",
                    "buyer": customer,
                    "date": date,
                    "total": total,
                    "rows": rows_meta,
                }, ensure_ascii=False)
                paid = str(total) if paid_full else ""
                try:
                    c.execute(
                        "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                        "VALUES(?,?,?,?,?,?,?,?,?)",
                        (customer, inv_no, date, time_str, str(total), created, "", inquiry, paid),
                    )
                    added += 1
                except Exception as ex:
                    errors.append(str(ex))
            c.commit()
            c.close()
        except Exception as ex:
            if not silent:
                QMessageBox.critical(self, "ورود", str(ex))
            try:
                self._status.setText("خطا در ورود خودکار به SalesMate: " + str(ex)[:80])
            except Exception:
                _swallow()
            return 0

        # dirty + ارسال به ابر (Supabase) + refresh
        try:
            mod = None
            for mn in ("__main__", "main", "salesmate.main"):
                m = sys.modules.get(mn)
                if m is not None and hasattr(m, "mark_local_dirty"):
                    mod = m
                    break
            if mod and (added or fixed):
                if hasattr(mod, "schedule_supabase_sync"):
                    try:
                        mod.schedule_supabase_sync()   # dirty + بکاپ + push با debounce
                    except Exception:
                        _swallow()
                else:
                    mod.mark_local_dirty()
            elif mod:
                mod.mark_local_dirty()
            if mod and added and hasattr(mod, "renumber_invoices_by_date"):
                try:
                    mod.renumber_invoices_by_date()
                except Exception:
                    _swallow()
            if mod and added and hasattr(mod, "rebuild_customer_colors"):
                try:
                    mod.rebuild_customer_colors()
                except Exception:
                    _swallow()
        except Exception:
            _swallow()

        try:
            try:
                from inquiry_page import ask_prune_saved_inquiries
            except Exception:
                from salesmate.inquiry_page import ask_prune_saved_inquiries
            ask_prune_saved_inquiries(self.win)          # اگر استعلام ذخیره‌شده با حواله‌ی تازه شباهت دارد بپرس
        except Exception:
            _swallow()
        try:
            if self.win is not None:
                self.win.refresh_all()
        except Exception:
            _swallow()

        self._last_import_stats = {"added": int(added), "store": int(store_added), "skipped": int(skipped), "fixed": int(fixed)}
        msg = f"{added:,} مورد به SalesMate اضافه شد."
        try:
            if store_added:
                msg += f" (از جمله {store_added:,} در فروشگاه)"
        except Exception:
            _swallow()
        if fixed:
            msg += f"\n{fixed:,} حواله‌ی موجود با عددهای اکسل اصلاح شد."
        if skipped:
            msg += f"\n{skipped:,} مورد تکراری/خالی رد شد."
        if errors:
            msg += "\nبرخی خطاها: " + " | ".join(errors[:3])
        if not silent:
            QMessageBox.information(self, "ورود به SalesMate", msg)
        try:
            self._status.setText(msg.replace("\n", " | "))
        except Exception:
            _swallow()
        return added
        # فیلتر نمودار روی انتخاب‌شده‌ها اختیاری
        try:
            if self.chk_my_customers.isChecked():
                self.apply_filters()
        except Exception:
            _swallow()

    def reload_salesmate_customers(self, silent=False):
        """بارگذاری نام مشتریان از دیتابیس اصلی SalesMate."""
        try:
            norm, raw = load_salesmate_customer_names()
        except Exception:
            norm, raw = set(), {}
        self._sm_customers_norm = norm or set()
        self._sm_customers_raw = raw or {}
        n = len(self._sm_customers_norm)
        if not silent:
            try:
                QMessageBox.information(
                    self, "مشتریان SalesMate",
                    "%s مشتری یکتا از حواله‌ها خوانده شد.\n"
                    "برای دیدن فقط آن‌ها، تیک «فقط مشتریان من» را بزنید." % f"{n:,}"
                )
            except Exception:
                _swallow()
        try:
            self._status.setText("مشتریان SalesMate: %s نفر" % f"{n:,}")
        except Exception:
            _swallow()
        try:
            if not self.df.empty:
                self.apply_filters()
        except Exception:
            _swallow()

    def _tag_my_customers(self, df):
        if df is None or df.empty or "نام مشتری" not in getattr(df, "columns", []):
            return df
        sm = getattr(self, "_sm_customers_norm", set()) or set()
        out = df.copy()
        if not sm:
            out["مشتری_من"] = False
            return out
        out["مشتری_من"] = out["نام مشتری"].astype(str).map(
            lambda x: match_salesmate_customer(x, sm)
        )
        return out

    def apply_filters(self):
        if self.df.empty:
            self.df_f = self.df
            self._refresh_all()
            return
        df = self.df
        try:
            df = self._tag_my_customers(df)
        except Exception:
            df = self.df
        cat = self.cmb_cat.currentText()
        month = self.cmb_month.currentText()
        q = self.txt_search.text().strip()
        only_mine = False
        try:
            only_mine = bool(self.chk_my_customers.isChecked())
        except Exception:
            only_mine = False
        # اگر تیک زده ولی لیست مشتریان خالی یا هیچ تطبیقی نبود → همه را نشان بده + هشدار
        if only_mine:
            sel = getattr(self, "_selected_import_customers", set()) or set()
            if sel and "نام مشتری" in df.columns:
                df = df[df["نام مشتری"].astype(str).isin(sel)]
            elif "مشتری_من" in getattr(df, "columns", []):
                matched = int(df["مشتری_من"].sum()) if "مشتری_من" in df.columns else 0
                if matched > 0:
                    df = df[df["مشتری_من"] == True]
        if cat and cat != "همه":
            df = df[df["دسته"] == cat]
        if month and month != "همه":
            df = df[df["ماه"] == month]
        if q:
            ql = q.lower()
            cols = set(df.columns)
            mask = False
            if "نام مشتری" in cols:
                mask = df["نام مشتری"].astype(str).str.lower().str.contains(ql, regex=False, na=False)
            if "نام کالا" in cols:
                m2 = df["نام کالا"].astype(str).str.lower().str.contains(ql, regex=False, na=False)
                mask = m2 if mask is False else (mask | m2)
            if "کد کالا" in cols:
                m3 = df["کد کالا"].astype(str).str.lower().str.contains(ql, regex=False, na=False)
                mask = m3 if mask is False else (mask | m3)
            if mask is not False:
                df = df[mask]
        self.df_f = df
        try:
            total_rows = len(self.df)
            shown = len(df)
            sm_n = len(getattr(self, "_sm_customers_norm", set()) or set())
            self._status.setText(
                "ردیف کل: %s | نمایش: %s | مشتریان SalesMate: %s"
                % (f"{total_rows:,}", f"{shown:,}", f"{sm_n:,}")
            )
        except Exception:
            _swallow()
        self._refresh_all()

    def _refresh_all(self):
        self._update_kpis()
        # فقط تب فعال همین حالا؛ بقیه علامت «کثیف» می‌خورند و با باز شدن ساخته می‌شوند
        self._dirty = set(self._tab_keys.values())
        self._ensure_current_tab()

    def _update_kpis(self):
        df = self.df_f
        if df.empty:
            for ref in (self.kpi_sales, self.kpi_sheets, self.kpi_cust, self.kpi_prod, self.kpi_inv, self.kpi_rows):
                if ref[0]:
                    ref[0].setText("—")
            return
        self.kpi_sales[0].setText(format_num(df["مبلغ"].sum()))
        # اگر فقط پارکت فیلتر شده → مترمربع
        only_parq = (not df.empty) and set(df["دسته"].unique().tolist()) == {"پارکت"}
        qsum = df["تعداد_ورق"].sum()
        if only_parq:
            self.kpi_sheets[0].setText(f"{qsum:,.1f} م²")
        else:
            self.kpi_sheets[0].setText(f"{qsum:,.0f}")
        self.kpi_cust[0].setText(f"{df['نام مشتری'].nunique():,}")
        self.kpi_prod[0].setText(f"{df['کد کالا'].nunique():,}")
        self.kpi_inv[0].setText(f"{df['شماره فرم'].nunique():,}")
        self.kpi_rows[0].setText(f"{len(df):,}")

    # ───────────── نمودارها ─────────────

    def _plot_bar(self, canvas, series, color, ylabel, unit="", rotate=30, max_bars=None, title=""):
        canvas.ax.clear()
        canvas.clear_hover()
        canvas._style_axes()
        if series is None or len(series) == 0:
            canvas.ax.text(0.5, 0.5, "داده‌ای نیست", ha="center", va="center",
                           fontsize=14, color="#90a4ae", transform=canvas.ax.transAxes)
            canvas.draw_idle()
            return
        s = series.copy()
        if max_bars and len(s) > max_bars:
            s = s.tail(max_bars)
        labels = [str(x) for x in s.index]
        values = [float(v) for v in s.values]
        xs = list(range(len(values)))
        canvas.ax.plot(xs, values, color=color, linewidth=2.4, marker="o", markersize=6,
                       markerfacecolor="#ffffff", markeredgewidth=2, markeredgecolor=color, zorder=4)
        canvas.ax.fill_between(xs, values, color=color, alpha=0.10, zorder=2)
        canvas.ax.set_xticks(xs)
        canvas.ax.set_xticklabels(labels)
        canvas.ax.set_xlim(-0.5, max(len(xs) - 0.5, 0.5))
        canvas.ax.set_ylim(bottom=0)
        canvas.register_points(xs, values, labels, unit)
        if title:
            canvas.ax.set_title(title, fontsize=13, fontweight="bold", color="#1a365d", pad=10)
        canvas.ax.set_ylabel(ylabel, fontsize=11, color="#37474f")
        canvas.ax.tick_params(axis="x", rotation=rotate, labelsize=9)
        canvas.ax.tick_params(axis="y", labelsize=10)
        canvas.ax.grid(axis="y", linestyle="--", alpha=0.4, zorder=0)
        canvas.ax.set_axisbelow(True)
        is_money = unit in ("ریال", "ریال") or "مبلغ" in ylabel or "ریال" in unit
        if is_money:
            canvas.ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, _: format_num(x))
            )
        else:
            canvas.ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}")
            )
        # فضای بیشتر پایین برای برچسب‌های بازه تاریخ
        canvas.fig.tight_layout()
        canvas.fig.subplots_adjust(bottom=0.22 if rotate >= 30 else 0.14)
        canvas.draw_idle()

    def _series_for(self, df, cat, value_col, period="ماه", week_labels=None):
        """سری ماهانه یا هفتگی برای یک دسته. برچسب هفتگی = بازه تاریخ."""
        sub = df[df["دسته"] == cat] if cat else df
        if sub.empty:
            return pd.Series(dtype=float)
        if period == "ماه":
            return sub.groupby("ماه", sort=True)[value_col].sum()
        return _continuous_week_series(df, sub, value_col)

    def refresh_charts(self):
        """نمودارها فقط برای تب فعال رسم می‌شوند؛ بقیه هنگام باز شدن."""
        for k in ("tot", "mdf", "raw", "parq"):
            self._dirty.add(k)
        self._ensure_current_tab()

    def _draw_charts(self, key):
        df = self.df_f
        empty = df.empty or "ماه" not in df.columns
        week_labels = build_week_labels(df) if not empty else {}
        if key == "tot":
            self._draw_tot(df, empty, week_labels)
        elif key == "mdf":
            self._draw_cat_group(df, empty, week_labels, "ام دی اف", "mdf", ("#3182ce", "#63b3ed"), "ورق", "تعداد ورق", "ورق")
            self._fill_recent("mdf", df)
        elif key == "raw":
            self._draw_cat_group(df, empty, week_labels, "خام", "raw", ("#38a169", "#68d391"), "ورق", "تعداد ورق", "ورق")
            self._fill_recent("raw", df)
        elif key == "parq":
            self._draw_cat_group(df, empty, week_labels, "پارکت", "parq", ("#dd6b20", "#f6ad55"), "متراژ", "مترمربع", "مترمربع")
            self._fill_recent("parq", df)

    def _fill_recent(self, key, df):
        """جدول حواله‌های ۲ هفته‌ی آخر همین بخش (هر حواله یک ردیف) + ردیف جمع."""
        ui = getattr(self, "_recent_ui", {}).get(key)
        if not ui:
            return
        lbl, tbl, e1, e2 = ui
        df = self.df if getattr(self, "df", None) is not None else df     # همه‌ی تاریخ‌ها (نه فقط فیلتر ماه)
        try:
            try:
                from recent_core import recent_invoices
            except Exception:
                from salesmate.recent_core import recent_invoices
            cat = {"raw": "خام", "parq": "پارکت", "mdf": "ام دی اف"}[key]
            sub = df[df["دسته"] == cat] if ("دسته" in df.columns and not df.empty) else df.iloc[0:0]
            cols = [c for c in ("تاریخ", "شماره فرم", "نام مشتری", "تعداد 1", "تعداد 2", "مبلغ") if c in sub.columns]
            res = recent_invoices(sub[cols].to_dict("records") if len(sub) else [], 14,
                                  e1.text().strip() or None, e2.text().strip() or None)
            ranged = bool(e1.text().strip() or e2.text().strip())
            rows, tot = res["rows"], res["tot"]
            title = ("حواله‌ها در بازه — " if ranged else "حواله‌های ۲ هفته‌ی اخیر — ") + {"raw": "ام‌دی‌اف خام", "parq": "پارکت", "mdf": "ام‌دی‌اف"}[key]
            if rows:
                title += f"   ({res['from']} تا {res['to']}  ·  {len(rows)} حواله  ·  جمع {tot['amount']:,.0f} ریال)"
            else:
                title += "   (حواله‌ای نیست)"
            lbl.setText(title)
            tbl.setRowCount(0)
            fmtq = lambda v: ("%.4f" % v).rstrip("0").rstrip(".") if v else "0"
            from PySide6.QtGui import QFont as _QF
            for g in rows + ([{"date": "جمع", "no": "", "customer": "", "q1": tot["q1"], "q2": tot["q2"], "amount": tot["amount"], "_t": 1}] if rows else []):
                r = tbl.rowCount()
                tbl.insertRow(r)
                vals = [g["date"], g["no"], g["customer"], fmtq(g["q1"]), fmtq(g["q2"]), f"{g['amount']:,.0f}"]
                for ci, v in enumerate(vals):
                    it = QTableWidgetItem(str(v))
                    it.setTextAlignment(Qt.AlignCenter if ci != 2 else (Qt.AlignRight | Qt.AlignVCenter))
                    if g.get("_t"):
                        f = it.font(); f.setBold(True); it.setFont(f)
                        it.setBackground(QColor("#EFF6FF"))
                    tbl.setItem(r, ci, it)
            tbl.setFixedHeight(min(tbl.rowCount(), 18) * 30 + 40 if rows else 70)
        except Exception:
            _swallow()

    def _draw_tot(self, df, empty, week_labels):
        # فروش کل
        tot_m = self._series_for(df, None, "مبلغ", "ماه") if not empty else pd.Series(dtype=float)
        tot_w = self._series_for(df, None, "مبلغ", "هفته", week_labels) if not empty else pd.Series(dtype=float)
        self._plot_bar(self.canvas_tot_m_amt, tot_m, "#2c5282", "مبلغ", "ریال", 25, title="فروش کل — ماهانه")
        self._plot_bar(self.canvas_tot_w_amt, tot_w, "#2b6cb0", "مبلغ", "ریال", 35, max_bars=60, title="فروش کل — هفتگی")


    def _draw_cat_group(self, df, empty, week_labels, cat, pfx, colors, qty_title, qty_ylabel, qty_unit):
        E = pd.Series(dtype=float)
        m_amt = self._series_for(df, cat, "مبلغ", "ماه") if not empty else E
        m_qty = self._series_for(df, cat, "تعداد_ورق", "ماه") if not empty else E
        w_amt = self._series_for(df, cat, "مبلغ", "هفته", week_labels) if not empty else E
        w_qty = self._series_for(df, cat, "تعداد_ورق", "هفته", week_labels) if not empty else E
        c = lambda n: getattr(self, "canvas_%s_%s" % (pfx, n))
        self._plot_bar(c("m_amt"), m_amt, colors[0], "مبلغ", "ریال", 25, title="ماهانه — مبلغ")
        self._plot_bar(c("m_qty"), m_qty, colors[1], qty_ylabel, qty_unit, 25, title="ماهانه — " + qty_title)
        self._plot_bar(c("w_amt"), w_amt, colors[0], "مبلغ", "ریال", 35, max_bars=60, title="هفتگی — مبلغ")
        self._plot_bar(c("w_qty"), w_qty, colors[1], qty_ylabel, qty_unit, 35, max_bars=60, title="هفتگی — " + qty_title)

    # ───────────── مشتریان ─────────────

    def refresh_customers(self):
        df = self.df_f
        if df.empty:
            self.model_cust.setDataFrame(pd.DataFrame())
            self.model_cust_detail.setDataFrame(pd.DataFrame())
            return
        q = self.txt_cust_search.text().strip()
        # اگر محصول سرچ شده: فقط مشتریان خریدار آن محصول
        if q:
            ql = q.lower()
            by_name = df["نام مشتری"].astype(str).str.contains(q, case=False, na=False, regex=False)
            by_prod = (
                df["نام کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
                | df["کد کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
            )
            # مشتریانی که نامشان match است یا آن محصول را خریده‌اند
            matched_customers = set(df.loc[by_name, "نام مشتری"].unique()) | set(
                df.loc[by_prod, "نام مشتری"].unique()
            )
            df_view = df[df["نام مشتری"].isin(matched_customers)]
            # اگر فقط محصول match شده (نه نام مشتری)، آمار را فقط روی همان محصول حساب کن
            only_prod = by_prod.any() and not by_name.any()
            if only_prod:
                df_view = df[by_prod]
        else:
            df_view = df

        agg = df_view.groupby("نام مشتری").agg(
            مبلغ_کل=("مبلغ", "sum"),
            تعداد_ورق=("تعداد_ورق", "sum"),
            تعداد_خرید=("شماره فرم", "nunique"),
            تنوع_محصول=("کد کالا", "nunique"),
            اولین=("تاریخ", "min"),
            آخرین=("تاریخ", "max"),
        ).reset_index()
        sort_mode = self.cmb_cust_sort.currentText()
        if sort_mode == "مبلغ فروش ↓":
            agg = agg.sort_values("مبلغ_کل", ascending=False)
        elif sort_mode == "مبلغ فروش ↑":
            agg = agg.sort_values("مبلغ_کل", ascending=True)
        elif sort_mode == "تعداد ورق ↓":
            agg = agg.sort_values("تعداد_ورق", ascending=False)
        elif sort_mode == "تعداد خرید ↓":
            agg = agg.sort_values("تعداد_خرید", ascending=False)
        else:
            agg = agg.sort_values("نام مشتری")
        self.model_cust.setDataFrame(agg)
        self.model_cust_detail.setDataFrame(pd.DataFrame())
        # اگر سرچ محصول بود، جزئیات اولین مشتری را خالی نگه دار تا کاربر کلیک کند

    def on_cust_clicked(self, index):
        row = index.row()
        name = self.model_cust._df.iloc[row]["نام مشتری"]
        q = self.txt_cust_search.text().strip()
        detail = self.df_f[self.df_f["نام مشتری"] == name]
        # اگر سرچ محصول فعال است، فقط ردیف‌های همان محصول
        if q:
            by_prod = (
                detail["نام کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
                | detail["کد کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
            )
            by_name = str(name).lower().find(q.lower()) >= 0
            if by_prod.any() and not by_name:
                detail = detail[by_prod]
        detail = detail[
            ["تاریخ", "شماره فرم", "کد کالا", "نام کالا", "دسته", "تعداد_ورق", "قیمت", "مبلغ"]
        ].sort_values("تاریخ")
        self.model_cust_detail.setDataFrame(detail)

    # ───────────── محصولات ─────────────

    def refresh_products(self):
        df = self.df_f
        if df.empty:
            self.model_prod.setDataFrame(pd.DataFrame())
            self.model_prod_detail.setDataFrame(pd.DataFrame())
            return
        agg = df.groupby(["کد کالا", "نام کالا", "دسته"]).agg(
            مبلغ_کل=("مبلغ", "sum"),
            تعداد_ورق=("تعداد_ورق", "sum"),
            تعداد_خرید=("شماره فرم", "nunique"),
            تعداد_مشتری=("نام مشتری", "nunique"),
            میانگین_قیمت=("قیمت", "mean"),
        ).reset_index()
        q = self.txt_prod_search.text().strip()
        if q:
            agg = agg[
                agg["نام کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
                | agg["کد کالا"].astype(str).str.contains(q, case=False, na=False, regex=False)
            ]
        sort_mode = self.cmb_prod_sort.currentText()
        if sort_mode == "مبلغ فروش ↓":
            agg = agg.sort_values("مبلغ_کل", ascending=False)
        elif sort_mode == "تعداد ورق ↓":
            agg = agg.sort_values("تعداد_ورق", ascending=False)
        elif sort_mode == "تعداد خرید ↓":
            agg = agg.sort_values("تعداد_خرید", ascending=False)
        else:
            agg = agg.sort_values("نام کالا")
        self.model_prod.setDataFrame(agg)
        self.model_prod_detail.setDataFrame(pd.DataFrame())
        # عرض ستون نام کالا برای نمایش کامل
        if self.model_prod.columnCount() >= 2:
            self.tbl_prod.setColumnWidth(1, 450)  # نام کالا
            self.tbl_prod.setColumnWidth(0, 110)  # کد کالا
            self.tbl_prod.setColumnWidth(2, 90)   # دسته

    def on_prod_clicked(self, index):
        row = index.row()
        code = self.model_prod._df.iloc[row]["کد کالا"]
        # هر خرید با تاریخ — نه فقط جمع مشتری
        detail = self.df_f[self.df_f["کد کالا"] == code][
            ["تاریخ", "نام مشتری", "شماره فرم", "تعداد_ورق", "قیمت", "مبلغ"]
        ].sort_values(["تاریخ", "نام مشتری"], ascending=[False, True]).reset_index(drop=True)
        self.model_prod_detail.setDataFrame(detail)
        if self.model_prod_detail.columnCount() >= 2:
            self.tbl_prod_detail.setColumnWidth(0, 100)   # تاریخ
            self.tbl_prod_detail.setColumnWidth(1, 220)   # نام مشتری
            self.tbl_prod_detail.setColumnWidth(2, 100)   # شماره فرم

    # ───────────── دسته‌ها ─────────────

    def refresh_categories(self):
        df = self.df_f
        self.canvas_cat.ax.clear()
        if df.empty:
            self.model_cat.setDataFrame(pd.DataFrame())
            self.canvas_cat.draw_idle()
            return
        agg = df.groupby("دسته").agg(
            مبلغ=("مبلغ", "sum"),
            تعداد_ورق=("تعداد_ورق", "sum"),
            تعداد_ردیف=("مبلغ", "count"),
            تعداد_مشتری=("نام مشتری", "nunique"),
        ).reset_index().sort_values("مبلغ", ascending=False)
        self.model_cat.setDataFrame(agg)
        if len(agg):
            colors = ["#3498db", "#e67e22", "#27ae60", "#95a5a6", "#9b59b6", "#1abc9c"]
            self.canvas_cat.ax.pie(
                agg["مبلغ"], labels=agg["دسته"], autopct="%1.1f%%",
                colors=colors[: len(agg)], startangle=90
            )
            self.canvas_cat.ax.set_title("سهم فروش هر دسته")
        self.canvas_cat.fig.tight_layout()
        self.canvas_cat.draw_idle()

    # ───────────── جزئیات ─────────────

    def _on_detail_header_click(self, col):
        # مرتب‌سازی مدل اصلی؛ پروکسی فیلتر را حفظ می‌کند
        self.model_detail.sort_by_column(col)

    def refresh_details(self):
        df = self.df_f
        if df.empty:
            self.model_detail.setDataFrame(pd.DataFrame())
            return
        cols = [c for c in [
            "تاریخ", "شماره فرم", "کد کالا", "نام کالا", "نام مشتری", "دسته",
            "تعداد 1", "تعداد_ورق", "قیمت", "مبلغ"
        ] if c in df.columns]
        self.model_detail.setDataFrame(df[cols].copy())
        self.proxy_detail.setFilterText(self.txt_detail_search.text())
        # عرض ستون نام کالا
        try:
            idx = cols.index("نام کالا")
            self.tbl_detail.setColumnWidth(idx, 420)
        except Exception:
            _swallow()

    # ───────────── خروجی PDF هیئت‌مدیره ─────────────

    def on_export_pdf(self):
        if self.df.empty:
            QMessageBox.information(self, "PDF", "ابتدا داده بارگذاری کنید.")
            return
        dlg = BoardReportDialog(self.df, self)
        if dlg.exec() != QDialog.Accepted:
            return
        opts = dlg.get_options()
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="salesmate_report_")
        os.close(fd)
        try:
            generate_board_pdf(self.df, opts, tmp)
        except Exception as ex:
            try:
                os.remove(tmp)
            except Exception:
                pass
            QMessageBox.critical(self, "PDF", f"خطا در ساخت PDF:\n{ex}")
            return
        safe = str(opts["period_label"]).replace("/", "-").replace("\\", "-").replace(":", "-")
        pv = PdfPreviewDialog(tmp, str(APP_DIR / f"گزارش_فروش_{safe}.pdf"), self)
        pv.exec()
        if not pv.external_used:
            try:
                os.remove(tmp)
            except Exception:
                pass


# ─────────────────────────── دیالوگ گزارش ───────────────────────────


class PdfPreviewDialog(QDialog):
    """پیش‌نمایش گزارش PDF (همه صفحه‌ها) با دکمه‌ی ذخیره."""

    def __init__(self, pdf_path, default_save, parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QScrollArea
        self.pdf_path = pdf_path
        self.default_save = default_save
        self.external_used = False
        self._doc = None
        self.setWindowTitle("پیش‌نمایش گزارش")
        self.setLayoutDirection(Qt.RightToLeft)
        try:
            _g = QApplication.primaryScreen().availableGeometry()
            self.resize(820, max(500, int(_g.height() * 0.85)))
        except Exception:
            self.resize(820, 700)
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        lay.addLayout(row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        host = QWidget()
        self.vbox = QVBoxLayout(host)
        self.vbox.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.scroll.setWidget(host)
        lay.addWidget(self.scroll, 1)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color:#64748b;")
        row.addWidget(self.lbl_info, 1)
        b_save = QPushButton("💾 ذخیره PDF…")
        b_save.clicked.connect(self._save)
        b_open = QPushButton("باز کردن در برنامه‌ی PDF")
        b_open.clicked.connect(self._open_external)
        b_close = QPushButton("بستن")
        b_close.clicked.connect(self.reject)
        row.addWidget(b_save)
        row.addWidget(b_open)
        row.addWidget(b_close)
        b_save.setStyleSheet("background:#2563eb;color:white;font-weight:700;padding:6px 14px;")
        self._render()

    def _render(self):
        try:
            from PySide6.QtPdf import QPdfDocument
            from PySide6.QtCore import QSize
            from PySide6.QtGui import QPixmap
            doc = QPdfDocument(self)
            doc.load(self.pdf_path)
            n = doc.pageCount()
            if n <= 0:
                raise RuntimeError("no pages")
            self._doc = doc
            w = 740
            for i in range(n):
                ps = doc.pagePointSize(i)
                h = int(w * ps.height() / max(1.0, ps.width()))
                img = doc.render(i, QSize(w, h))
                lb = QLabel()
                lb.setPixmap(QPixmap.fromImage(img))
                lb.setStyleSheet("border:1px solid #cbd5e1;background:white;")
                self.vbox.addWidget(lb, 0, Qt.AlignHCenter)
            self.lbl_info.setText(f"{n} صفحه")
        except Exception:
            lb = QLabel("پیش‌نمایش داخل برنامه در دسترس نیست.\nبا «باز کردن در برنامه‌ی PDF» گزارش را ببینید یا مستقیم ذخیره کنید.")
            lb.setAlignment(Qt.AlignCenter)
            self.vbox.addWidget(lb)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره گزارش PDF", self.default_save, "PDF (*.pdf)")
        if not path:
            return
        try:
            import shutil
            shutil.copyfile(self.pdf_path, path)
            QMessageBox.information(self, "PDF", f"گزارش ذخیره شد:\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "PDF", f"خطا در ذخیره:\n{ex}")

    def _open_external(self):
        try:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            self.external_used = True
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.pdf_path))
        except Exception:
            _swallow()


class BoardReportDialog(QDialog):
    """انتخاب نوع گزارش و دوره برای خروجی PDF هیئت‌مدیره."""

    def __init__(self, df, parent=None):
        super().__init__(parent)
        self.df = df
        self.setWindowTitle("خروجی PDF — گزارش هیئت‌مدیره")
        self.setMinimumWidth(460)
        self.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(self)

        title = QLabel("تنظیمات گزارش فروش")
        title.setStyleSheet("font-size:16px;font-weight:700;color:#0F172A;")
        lay.addWidget(title)

        form = QFormLayout()
        self.cmb_type = QComboBox()
        self.cmb_type.addItems([
            "گزارش کامل (همه دسته‌ها)",
            "فروش کل",
            "ام دی اف",
            "خام",
            "پارکت",
        ])
        form.addRow("نوع گزارش:", self.cmb_type)

        self.cmb_period_type = QComboBox()
        self.cmb_period_type.addItems(["ماهانه", "هفتگی", "روزانه"])
        self.cmb_period_type.currentIndexChanged.connect(self._reload_periods)
        form.addRow("نوع دوره:", self.cmb_period_type)

        self.cmb_period = QComboBox()
        form.addRow("انتخاب دوره:", self.cmb_period)
        lay.addLayout(form)

        hint = QLabel(
            "گزارش کامل: کارت فروش خام / ام‌دی‌اف / پارکت / مبلغ کل + ۵ محصول برتر هر بخش.\n"
            "درصد رشد سبز و افت قرمز نمایش داده می‌شود. نام کالا کامل است."
        )
        hint.setStyleSheet("color:#64748b;font-size:11px;")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("پیش‌نمایش گزارش")
        btns.button(QDialogButtonBox.Cancel).setText("انصراف")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._reload_periods()

    def _reload_periods(self):
        self.cmb_period.clear()
        if self.cmb_period_type.currentText() == "روزانه":
            self.cmb_period.addItems(_sorted_days(self.df)[::-1])
        elif self.cmb_period_type.currentText() == "ماهانه":
            months = sorted(self.df["ماه"].dropna().unique().tolist())
            self.cmb_period.addItems([str(m) for m in months])
        else:
            labels = build_week_labels(self.df)
            keys = sorted(labels.keys())
            for k in keys:
                self.cmb_period.addItem(labels[k], k)

    def get_options(self):
        t = self.cmb_type.currentText()
        full = t.startswith("گزارش کامل")
        cat_map = {
            "فروش کل": None,
            "ام دی اف": "ام دی اف",
            "خام": "خام",
            "پارکت": "پارکت",
        }
        is_day = self.cmb_period_type.currentText() == "روزانه"
        is_month = self.cmb_period_type.currentText() == "ماهانه"
        if is_day:
            period_key = self.cmb_period.currentText()
            period_label = period_key
        elif is_month:
            period_key = self.cmb_period.currentText()
            period_label = period_key
        else:
            period_key = self.cmb_period.currentData()
            period_label = self.cmb_period.currentText()
        return {
            "full_report": full,
            "category": None if full else cat_map.get(t),
            "category_title": "گزارش کامل" if full else t,
            "is_month": is_month,
            "is_day": is_day,
            "period_key": period_key,
            "period_label": period_label,
        }


def _sorted_days(df):
    """تاریخ‌های (روزهای) موجود در داده، مرتب از قدیم به جدید."""
    if "تاریخ" not in df.columns:
        return []
    days = [d for d in df["تاریخ"].dropna().astype(str).str.strip().unique().tolist() if _parse_jalali(d)]
    days.sort(key=lambda d: _parse_jalali(d))
    return days


def _filter_period(df, opts, category=None):
    """فیلتر داده برای دوره انتخاب‌شده و دوره قبل. category اختیاری برای گزارش کامل."""
    cat = category if category is not None else opts.get("category")
    sub = df if cat is None else df[df["دسته"] == cat]
    if opts.get("is_day"):
        days = _sorted_days(df)
        cur = opts["period_key"]
        key = df["تاریخ"].astype(str).str.strip() if "تاریخ" in df.columns else None
        cur_df = sub[sub["تاریخ"].astype(str).str.strip() == cur]
        prev = None
        try:
            i = days.index(cur)
            prev = days[i - 1] if i > 0 else None
        except ValueError:
            prev = None
        prev_df = sub[sub["تاریخ"].astype(str).str.strip() == prev] if prev else sub.iloc[0:0]
        return cur_df, prev_df, (prev or "—")
    if opts["is_month"]:
        # ماه‌ها را از کل داده بگیر تا مقایسه درست باشد
        months = sorted(df["ماه"].dropna().unique().tolist())
        cur = opts["period_key"]
        cur_df = sub[sub["ماه"] == cur]
        try:
            idx = months.index(cur)
            prev = months[idx - 1] if idx > 0 else None
        except ValueError:
            prev = None
        prev_df = sub[sub["ماه"] == prev] if prev else sub.iloc[0:0]
        prev_label = str(prev) if prev else "—"
        return cur_df, prev_df, prev_label
    sub_all = df.dropna(subset=["هفته"]).copy()
    sub_all = sub_all[sub_all["تاریخ"].map(_year_of).notna()].copy()
    sub_all["_wk"] = week_key_series(sub_all)
    cur = opts["period_key"]
    if cat is None:
        cur_df = sub_all[sub_all["_wk"] == cur]
        prev_pool = sub_all
    else:
        s = sub.dropna(subset=["هفته"]).copy()
        s = s[s["تاریخ"].map(_year_of).notna()].copy()
        s["_wk"] = week_key_series(s)
        cur_df = s[s["_wk"] == cur]
        prev_pool = s
    try:
        prev = prev_week_key(cur)   # هفته‌ی تقویمی قبل (ممکن است بدون فروش باشد)
    except Exception:
        prev = None
    prev_df = prev_pool[prev_pool["_wk"] == prev] if prev else prev_pool.iloc[0:0]
    labels = build_week_labels(df)
    prev_label = "—"
    if prev:
        prev_label = labels.get(prev) or week_block_label(*_split_week_key(prev))
    return cur_df, prev_df, prev_label


def _qty_unit(category):
    if category == "پارکت":
        return "مترمربع", "متراژ فروش"
    if category == "خام":
        return "ورق", "تعداد ورق خام"
    if category == "ام دی اف":
        return "ورق", "تعداد ورق ام‌دی‌اف"
    return "واحد", "میزان فروش"


def _pct_change(cur, prev):
    if prev is None or prev == 0:
        return None
    return (cur - prev) / abs(prev) * 100.0


def _fmt_pct(p):
    if p is None:
        return "—"
    sign = "▲" if p > 0 else ("▼" if p < 0 else "●")
    return f"{sign} {abs(p):.1f}٪"


def _fmt_money(n):
    """مبلغ در گزارش‌های PDF به تومان (هر تومان = ۱۰ ریال)."""
    try:
        n = float(n) / 10.0
    except Exception:
        n = 0.0
    return f"{format_num(n)} تومان"



def _fa(s):
    """شکل‌دهی فارسی: فقط reshape (بدون bidi مضاعف)."""
    if s is None:
        return ""
    s = str(s)
    try:
        import arabic_reshaper
        return arabic_reshaper.reshape(s)
    except Exception:
        return s


def _font_paths():
    candidates_reg = [
        FONTS_DIR / "NotoSansArabic-Regular.ttf",
        Path(__file__).resolve().parent.parent / "fonts" / "NotoSansArabic-Regular.ttf",
        Path("/usr/share/fonts/SlidesCarnival/google/Noto Sans Arabic/static/NotoSansArabic-Regular.ttf"),
    ]
    candidates_bold = [
        FONTS_DIR / "NotoSansArabic-Bold.ttf",
        Path(__file__).resolve().parent.parent / "fonts" / "NotoSansArabic-Bold.ttf",
        Path("/usr/share/fonts/SlidesCarnival/google/Noto Sans Arabic/static/NotoSansArabic-Bold.ttf"),
    ]
    reg = next((p for p in candidates_reg if p.exists()), None)
    bold = next((p for p in candidates_bold if p.exists()), None)
    return reg, bold


def _period_stats(cur_df, prev_df):
    cur_amt = float(cur_df["مبلغ"].sum()) if not cur_df.empty else 0.0
    prev_amt = float(prev_df["مبلغ"].sum()) if not prev_df.empty else 0.0
    cur_qty = float(cur_df["تعداد_ورق"].sum()) if not cur_df.empty else 0.0
    prev_qty = float(prev_df["تعداد_ورق"].sum()) if not prev_df.empty else 0.0
    return {
        "cur_amt": cur_amt, "prev_amt": prev_amt,
        "cur_qty": cur_qty, "prev_qty": prev_qty,
        "amt_pct": _pct_change(cur_amt, prev_amt),
        "qty_pct": _pct_change(cur_qty, prev_qty),
    }


def _top_products(cur_df, n=5):
    if cur_df.empty:
        return pd.DataFrame()
    return (
        cur_df.groupby("نام کالا")
        .agg(مبلغ=("مبلغ", "sum"), میزان=("تعداد_ورق", "sum"))
        .reset_index()
        .sort_values("مبلغ", ascending=False)
        .head(n)
    )


def _top_customers(cur_df, n=5):
    if cur_df.empty:
        return pd.DataFrame()
    return (
        cur_df.groupby("نام مشتری")
        .agg(مبلغ=("مبلغ", "sum"), میزان=("تعداد_ورق", "sum"))
        .reset_index()
        .sort_values("مبلغ", ascending=False)
        .head(n)
    )


def _daily_report(pdf, df, opts, T, header_bar, kpi_card, section_title, qty_str, pct_rgb, C):
    """گزارش روزانه‌ی فشرده — در یک صفحه‌ی A4."""
    day = opts["period_key"]
    header_bar(f"گزارش روزانه — {day}")

    def compact_table(cur_df, unit, title, color, kind):
        section_title(title, color)
        if kind == "customer":
            tops = _top_customers(cur_df, 3)
            name_col, name_header = "نام مشتری", "نام مشتری"
        else:
            tops = _top_products(cur_df, 3)
            name_col, name_header = "نام کالا", "نام محصول"
        col_w = [32, 32, 110, 12]
        headers = ["مبلغ", "میزان", name_header, "ردیف"]
        y = pdf.get_y()
        x = 12
        pdf.set_font("Fa", "B", 7)
        for i, h in enumerate(headers):
            pdf.set_xy(x, y)
            pdf.set_fill_color(*color)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(col_w[i], 5.5, T(h), align="C", fill=True)
            x += col_w[i]
        y += 5.5
        if tops.empty:
            pdf.set_xy(12, y)
            pdf.set_text_color(*C["SLATE"])
            pdf.set_font("Fa", size=8)
            pdf.cell(186, 6, T("فروشی ثبت نشده"), align="C")
            pdf.set_y(y + 8)
            return
        for ni, (_, r) in enumerate(tops.iterrows()):
            name = str(r[name_col])
            row_h = 9 if len(name) > 60 else 6
            bg = (240, 253, 250) if ni % 2 == 0 else C["WHITE"]
            vals = [_fmt_money(r["مبلغ"]), ("—" if unit is None else qty_str(r["میزان"], unit)), name, str(ni + 1)]
            aligns = ["C", "C", "R", "C"]
            x = 12
            for i, val in enumerate(vals):
                pdf.set_xy(x, y)
                pdf.set_fill_color(*bg)
                pdf.set_draw_color(*C["LINE"])
                pdf.set_text_color(*C["DARK"])
                pdf.set_font("Fa", size=(6.5 if (i == 2 and len(name) > 40) else 7))
                pdf.cell(col_w[i], row_h, T(val), align=aligns[i], fill=True, border=1)
                x += col_w[i]
            y += row_h
        pdf.set_y(y + 2)
        pdf.set_text_color(*C["DARK"])

    # کارت مبلغ کل روز
    tot_cur, tot_prev, prev_label = _filter_period(df, opts, category=None)
    tot = _period_stats(tot_cur, tot_prev)
    y = pdf.get_y()
    pdf.set_fill_color(*C["WHITE"])
    pdf.set_draw_color(*C["LINE"])
    pdf.rect(12, y, 186, 17, "FD")
    pdf.set_fill_color(*C["NAVY"])
    pdf.rect(196.2, y + 2, 1.5, 13, "F")
    pdf.set_xy(14, y + 1.5)
    pdf.set_font("Fa", size=8)
    pdf.set_text_color(*C["SLATE"])
    pdf.cell(180, 4, T(f"مبلغ کل فروش روز {day}"), align="R")
    pdf.set_xy(14, y + 6)
    pdf.set_font("Fa", "B", 12)
    pdf.set_text_color(*C["DARK"])
    pdf.cell(180, 5, T(_fmt_money(tot["cur_amt"])), align="R")
    pdf.set_xy(14, y + 12)
    pdf.set_font("Fa", size=7)
    pdf.set_text_color(*C["SLATE"])
    pdf.cell(120, 4, T(f"روز فروش قبل ({prev_label}): {_fmt_money(tot['prev_amt'])}"), align="R")
    pdf.set_xy(14, y + 10.5)
    pdf.set_font("Fa", "B", 10)
    pdf.set_text_color(*pct_rgb(tot["amt_pct"]))
    pdf.cell(50, 5, T(_fmt_pct(tot["amt_pct"])), align="L")
    pdf.set_y(y + 20)
    pdf.set_text_color(*C["DARK"])

    cat = None if opts.get("full_report") else opts.get("category")
    blocks = [
        ("خام", C["RAW"], "ورق", "تعداد ورق خام", "ام‌دی‌اف خام"),
        ("ام دی اف", C["BLUE"], "ورق", "تعداد ورق ام‌دی‌اف", "ام‌دی‌اف (ملامینه / هایگلاس)"),
        ("پارکت", C["ORANGE"], "مترمربع", "متراژ فروش", "پارکت"),
    ]
    if cat:
        blocks = [b for b in blocks if b[0] == cat]
    for bcat, accent, unit, qty_title, title in blocks:
        cd, pdf_, _ = _filter_period(df, opts, category=bcat)
        if cd.empty:
            if pdf.get_y() > 270:
                pdf.add_page()
                header_bar(f"گزارش روزانه — {day} (ادامه)")
            section_title(f"{title} — فروشی در این روز ثبت نشده", C["SLATE"])
            continue
        if pdf.get_y() + 92 > 282:
            pdf.add_page()
            header_bar(f"گزارش روزانه — {day} (ادامه)")
        section_title(title, accent)
        st = _period_stats(cd, pdf_)
        y = pdf.get_y()
        w, h, gap = 90, 18, 4
        kpi_card(12 + w + gap, y, w, h, "مبلغ فروش روز", _fmt_money(st["cur_amt"]),
                 f"قبل: {_fmt_money(st['prev_amt'])}", st["amt_pct"], accent)
        kpi_card(12, y, w, h, qty_title, qty_str(st["cur_qty"], unit),
                 f"قبل: {qty_str(st['prev_qty'], unit)}", st["qty_pct"], accent)
        pdf.set_y(y + h + 2)
        compact_table(cd, unit, f"۳ محصول پرفروش — {title}", accent, "product")
        compact_table(cd, unit, f"۳ مشتری برتر — {title} (میزان خرید)", accent, "customer")


def generate_board_pdf(df, opts, path):
    """گزارش PDF با fpdf2 و فونت فارسی (بدون برعکس‌شدن متن)."""
    from fpdf import FPDF

    reg_path, bold_path = _font_paths()
    if not reg_path:
        raise RuntimeError("فونت فارسی یافت نشد. پوشه fonts را کنار برنامه قرار دهید.")

    C_NAVY = (30, 58, 95)
    C_BLUE = (37, 99, 235)
    C_GREEN = (5, 150, 105)
    C_RED = (220, 38, 38)
    C_SLATE = (100, 116, 139)
    C_DARK = (15, 23, 42)
    C_LINE = (226, 232, 240)
    C_BG = (248, 250, 252)
    C_TEAL = (15, 118, 110)
    C_ORANGE = (192, 86, 33)
    C_RAW = (39, 103, 73)
    C_WHITE = (255, 255, 255)

    class BoardPDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font("Fa", size=7)
            self.set_text_color(*C_SLATE)
            self.cell(
                0, 6,
                _fa(f"تولیدشده توسط SalesMate Analysis  |  {datetime.now().strftime('%Y/%m/%d %H:%M')}  |  مبالغ به تومان"),
                align="C",
            )

    pdf = BoardPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_font("Fa", "", str(reg_path))
    if bold_path:
        pdf.add_font("Fa", "B", str(bold_path))
    else:
        pdf.add_font("Fa", "B", str(reg_path))

    # تلاش برای text shaping واقعی
    try:
        pdf.set_text_shaping(True)
        use_raw = True  # با shaping نیازی به reshape نیست
    except Exception:
        use_raw = False

    def T(s):
        if s is None:
            return ""
        s = str(s)
        if use_raw:
            return s
        return _fa(s)

    def pct_rgb(p):
        if p is None:
            return C_SLATE
        if p > 0:
            return C_GREEN
        if p < 0:
            return C_RED
        return C_SLATE

    def qty_str(v, unit):
        if unit == "مترمربع":
            return f"{v:,.1f} مترمربع"
        return f"{v:,.0f} ورق"

    def header_bar(subtitle=""):
        pdf.set_fill_color(*C_NAVY)
        pdf.rect(0, 0, 210, 22, "F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Fa", "B", 15)
        pdf.set_xy(10, 5)
        pdf.cell(190, 8, T("گزارش فروش — هیئت مدیره"), align="C")
        pdf.set_font("Fa", size=8)
        pdf.set_text_color(191, 219, 254)
        sub = f"SalesMate Analysis  |  نسخه {APP_VERSION}"
        if subtitle:
            sub = f"{subtitle}  |  {sub}"
        pdf.set_xy(10, 13)
        pdf.cell(190, 6, T(sub), align="C")
        pdf.set_fill_color(*C_BLUE)
        pdf.rect(0, 22, 210, 1.2, "F")
        pdf.set_y(26)
        pdf.set_text_color(*C_DARK)

    def meta_box(prev_label):
        y = pdf.get_y()
        pdf.set_fill_color(*C_BG)
        pdf.set_draw_color(*C_LINE)
        pdf.rect(12, y, 186, 16, "FD")
        pdf.set_font("Fa", "B", 10)
        pdf.set_text_color(*C_NAVY)
        pdf.set_xy(14, y + 2)
        pdf.cell(182, 5, T(f"دسته: {opts['category_title']}"), align="R")
        pdf.set_font("Fa", size=9)
        pdf.set_text_color(*C_DARK)
        period_type = "روزانه" if opts.get("is_day") else ("ماهانه" if opts["is_month"] else "هفتگی")
        pdf.set_xy(14, y + 7)
        pdf.cell(182, 4, T(f"دوره: {opts['period_label']}  ({period_type})"), align="R")
        pdf.set_text_color(*C_SLATE)
        pdf.set_xy(14, y + 11)
        pdf.cell(182, 4, T(f"مقایسه با دوره قبل: {prev_label}"), align="R")
        pdf.set_y(y + 19)
        pdf.set_text_color(*C_DARK)

    def kpi_card(x, y, w, h, title, value, sub, pct, accent):
        pdf.set_fill_color(*C_WHITE)
        pdf.set_draw_color(*C_LINE)
        pdf.rect(x, y, w, h, "FD")
        pdf.set_fill_color(*accent)
        pdf.rect(x + w - 1.8, y + 2, 1.2, h - 4, "F")
        pdf.set_xy(x + 2, y + 2)
        pdf.set_font("Fa", size=7)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(w - 6, 4, T(title), align="R")
        pdf.set_xy(x + 2, y + 7)
        pdf.set_font("Fa", "B", 10)
        pdf.set_text_color(*C_DARK)
        pdf.cell(w - 6, 5, T(value), align="R")
        pdf.set_xy(x + 2, y + 13)
        pdf.set_font("Fa", size=7)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(w - 6, 4, T(sub), align="R")
        if pct is not None:
            pdf.set_xy(x + 3, y + 13)
            pdf.set_font("Fa", "B", 8)
            pdf.set_text_color(*pct_rgb(pct))
            pdf.cell(30, 4, T(_fmt_pct(pct)), align="L")

    def two_kpis(title1, val1, sub1, pct1, acc1, title2, val2, sub2, pct2, acc2):
        y = pdf.get_y()
        if y > 250:
            pdf.add_page()
            header_bar("ادامه")
            y = pdf.get_y()
        w = 90
        h = 20
        gap = 4
        # راست = اول
        kpi_card(12 + w + gap, y, w, h, title1, val1, sub1, pct1, acc1)
        kpi_card(12, y, w, h, title2, val2, sub2, pct2, acc2)
        pdf.set_y(y + h + 4)
        pdf.set_text_color(*C_DARK)

    def section_title(text, color=C_NAVY):
        if pdf.get_y() > 255:
            pdf.add_page()
            header_bar("ادامه")
        pdf.set_font("Fa", "B", 11)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, T(text), align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*C_DARK)

    def top5_table(cur_df, unit, title, header_color, kind="product"):
        """جدول ۵تایی محصول یا مشتری — نام کامل بدون حذف."""
        if pdf.get_y() > 230:
            pdf.add_page()
            header_bar("ادامه")
        section_title(title, header_color)
        if kind == "customer":
            tops = _top_customers(cur_df, 5)
            name_col = "نام مشتری"
            name_header = "نام مشتری"
        else:
            tops = _top_products(cur_df, 5)
            name_col = "نام کالا"
            name_header = "نام محصول"
        # RTL visual: مبلغ | میزان | نام | ردیف
        col_w = [32, 32, 110, 12]
        headers = ["مبلغ", "میزان", name_header, "ردیف"]
        y = pdf.get_y()
        x0 = 12
        x = x0
        pdf.set_font("Fa", "B", 7)
        for i, h in enumerate(headers):
            pdf.set_xy(x, y)
            pdf.set_fill_color(*header_color)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(col_w[i], 6, T(h), align="C", fill=True)
            x += col_w[i]
        y += 6
        if tops.empty:
            pdf.set_xy(x0, y)
            pdf.set_text_color(*C_SLATE)
            pdf.set_font("Fa", size=8)
            pdf.cell(186, 6, T("داده‌ای ثبت نشده"), align="C")
            pdf.set_y(y + 8)
            return
        for ni, (_, r) in enumerate(tops.iterrows()):
            if y > 275:
                pdf.add_page()
                header_bar("ادامه")
                y = pdf.get_y()
            name = str(r[name_col])
            bg = (240, 253, 250) if ni % 2 == 0 else C_WHITE
            if kind == "customer":
                bg = (239, 246, 255) if ni % 2 == 0 else C_WHITE
            name_font = 6.5 if len(name) > 60 else (7 if len(name) > 40 else 7.5)
            row_h = 10 if len(name) > 55 else 7
            vals = [
                _fmt_money(r["مبلغ"]),
                qty_str(r["میزان"], unit),
                name,
                str(ni + 1),
            ]
            aligns = ["C", "C", "R", "C"]
            x = x0
            for i, val in enumerate(vals):
                pdf.set_xy(x, y)
                pdf.set_fill_color(*bg)
                pdf.set_draw_color(*C_LINE)
                pdf.set_text_color(*C_DARK)
                pdf.set_font("Fa", size=name_font if i == 2 else 7)
                pdf.cell(col_w[i], row_h, T(val), align=aligns[i], fill=True, border=1)
                x += col_w[i]
            y += row_h
        pdf.set_y(y + 3)
        pdf.set_text_color(*C_DARK)

    def cat_block(cat, accent, unit, qty_title, title):
        section_title(title, accent)
        cur_df, prev_df, _ = _filter_period(df, opts, category=cat)
        st = _period_stats(cur_df, prev_df)
        two_kpis(
            "مبلغ فروش", _fmt_money(st["cur_amt"]),
            f"قبل: {_fmt_money(st['prev_amt'])}", st["amt_pct"], accent,
            qty_title, qty_str(st["cur_qty"], unit),
            f"قبل: {qty_str(st['prev_qty'], unit)}", st["qty_pct"], accent,
        )
        top5_table(cur_df, unit, f"۵ محصول پرفروش — {title}", accent, kind="product")
        top5_table(cur_df, unit, f"۵ مشتری برتر — {title}", accent, kind="customer")

    # ─── شروع ساخت ───
    pdf.add_page()
    header_bar("گزارش کامل" if opts.get("full_report") else opts.get("category_title", ""))

    if opts.get("is_day"):
        _daily_report(pdf, df, opts, T, header_bar, kpi_card, section_title, qty_str, pct_rgb,
                      dict(NAVY=C_NAVY, BLUE=C_BLUE, RAW=C_RAW, ORANGE=C_ORANGE, SLATE=C_SLATE,
                           DARK=C_DARK, LINE=C_LINE, WHITE=C_WHITE, TEAL=C_TEAL))
        pdf.output(path)
        return

    if opts.get("full_report"):
        _, _, prev_label = _filter_period(df, opts, category=None)
        meta_box(prev_label)

        tot_cur, tot_prev, _ = _filter_period(df, opts, category=None)
        tot = _period_stats(tot_cur, tot_prev)
        # مبلغ کل تمام‌عرض
        y = pdf.get_y()
        pdf.set_fill_color(*C_WHITE)
        pdf.set_draw_color(*C_LINE)
        pdf.rect(12, y, 186, 18, "FD")
        pdf.set_fill_color(*C_NAVY)
        pdf.rect(196.2, y + 2, 1.5, 14, "F")
        pdf.set_xy(14, y + 2)
        pdf.set_font("Fa", size=8)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(180, 4, T("مبلغ کل فروش (همه دسته‌ها)"), align="R")
        pdf.set_xy(14, y + 7)
        pdf.set_font("Fa", "B", 12)
        pdf.set_text_color(*C_DARK)
        pdf.cell(180, 5, T(_fmt_money(tot["cur_amt"])), align="R")
        pdf.set_xy(14, y + 13)
        pdf.set_font("Fa", size=7)
        pdf.set_text_color(*C_SLATE)
        pdf.cell(120, 4, T(f"دوره قبل: {_fmt_money(tot['prev_amt'])}"), align="R")
        pdf.set_xy(14, y + 12)
        pdf.set_font("Fa", "B", 11)
        pdf.set_text_color(*pct_rgb(tot["amt_pct"]))
        pdf.cell(50, 5, T(_fmt_pct(tot["amt_pct"])), align="L")
        pdf.set_y(y + 21)
        pdf.set_text_color(*C_DARK)

        cat_block("خام", C_RAW, "ورق", "تعداد ورق خام", "ام‌دی‌اف خام")
        cat_block("ام دی اف", C_BLUE, "ورق", "تعداد ورق ام‌دی‌اف", "ام‌دی‌اف (ملامینه / هایگلاس)")
        cat_block("پارکت", C_ORANGE, "مترمربع", "متراژ فروش", "پارکت")
        pdf.output(path)
        return

    # تک‌دسته
    cat = opts["category"]
    unit, qty_title = _qty_unit(cat)
    if cat == "پارکت":
        accent = C_ORANGE
    elif cat == "خام":
        accent = C_RAW
    elif cat == "ام دی اف":
        accent = C_BLUE
    else:
        accent = C_NAVY
        unit, qty_title = "ورق", "میزان فروش"

    cur_df, prev_df, prev_label = _filter_period(df, opts)
    st = _period_stats(cur_df, prev_df)
    meta_box(prev_label)
    two_kpis(
        "مبلغ فروش دوره", _fmt_money(st["cur_amt"]),
        f"قبل: {_fmt_money(st['prev_amt'])}", st["amt_pct"], accent,
        qty_title, qty_str(st["cur_qty"], unit),
        f"قبل: {qty_str(st['prev_qty'], unit)}", st["qty_pct"], accent,
    )
    top5_table(cur_df, unit, "۵ محصول پرفروش دوره", accent if cat else C_TEAL, kind="product")
    top5_table(cur_df, unit, "۵ مشتری برتر دوره", accent if cat else C_TEAL, kind="customer")

    if cat is None:
        section_title("خلاصه دسته‌ها در همین دوره")
        for cname, u, qtitle, col in [
            ("خام", "ورق", "ورق خام", C_RAW),
            ("ام دی اف", "ورق", "ورق ام‌دی‌اف", C_BLUE),
            ("پارکت", "مترمربع", "متراژ پارکت", C_ORANGE),
        ]:
            cd, pd_, _ = _filter_period(df, opts, category=cname)
            s = _period_stats(cd, pd_)
            two_kpis(
                f"مبلغ {cname}", _fmt_money(s["cur_amt"]),
                f"قبل: {_fmt_money(s['prev_amt'])}", s["amt_pct"], col,
                qtitle, qty_str(s["cur_qty"], u),
                f"قبل: {qty_str(s['prev_qty'], u)}", s["qty_pct"], col,
            )

    pdf.output(path)



def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    font = QFont("Tahoma", 10)
    app.setFont(font)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


