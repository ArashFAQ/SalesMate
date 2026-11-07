import sys, sqlite3, shutil, json, os, re, webbrowser, tempfile, threading, time
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QUrl, QStringListModel, QMarginsF, QEvent, QRect, QRectF, QObject, Slot, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMessageBox,
    QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QStyledItemDelegate, QAbstractItemDelegate,
    QDateEdit, QSpinBox, QCompleter, QScrollArea, QSizePolicy, QListWidget, QCheckBox, QProgressBar,
    QGridLayout, QToolTip
)
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath, QTextDocument, QPageSize, QPageLayout, QPixmap, QImage, QPalette, QCursor
from PySide6.QtPrintSupport import QPrinter, QPrintDialog


try:
    from core_utils import (
        PERSIAN_DIGITS, LATIN_DIGITS, fa_digits, en_digits, clean_number, amount, fmt,
        format_jalali_ymd, gregorian_to_jalali, jalali_to_gregorian, parse_flexible_jalali,
        canon_money, jalali_week_range, qty_int,
    )
except Exception:
    from salesmate.core_utils import (
        PERSIAN_DIGITS, LATIN_DIGITS, fa_digits, en_digits, clean_number, amount, fmt,
        format_jalali_ymd, gregorian_to_jalali, jalali_to_gregorian, parse_flexible_jalali,
        canon_money, jalali_week_range, qty_int,
    )

try:
    from db_migrations import migrate_money_v1, migrate_jenagi_v2
except Exception:
    from salesmate.db_migrations import migrate_money_v1, migrate_jenagi_v2

try:
    from app_log import swallow as _swallow, log, setup_logging
except Exception:
    from salesmate.app_log import swallow as _swallow, log, setup_logging

try:
    import ui_theme as uit
except Exception:
    try:
        from salesmate import ui_theme as uit
    except Exception:
        uit = None

try:
    from sales_extras import free_items_by_customer, free_items_of_customer, filter_category, FREE_TYPES, OTHER_FREE, CATEGORY_CHOICES, free_items_breakdown, group_invoices_by_month
except Exception:
    from salesmate.sales_extras import free_items_by_customer, free_items_of_customer, filter_category, FREE_TYPES, OTHER_FREE, CATEGORY_CHOICES, free_items_breakdown, group_invoices_by_month

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, QUrl, QStringListModel, QMarginsF, QEvent, QRect, QRectF, QObject, Slot, Signal

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QBoxLayout,
    QLabel, QPushButton, QFrame, QStackedWidget, QMessageBox,
    QLineEdit, QFormLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QStyledItemDelegate, QAbstractItemDelegate,
    QDateEdit, QSpinBox, QCompleter, QScrollArea, QSizePolicy, QListWidget, QCheckBox, QProgressBar,
    QGridLayout, QToolTip
)

from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath, QTextDocument, QPageSize, QPageLayout, QPixmap, QImage, QPalette, QCursor

from PySide6.QtPrintSupport import QPrinter, QPrintDialog

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent.parent

DB_PATH = APP_DIR / "salesmate.db"

CONTACTS_PATH = APP_DIR / "customer_contacts.json"

try:
    from app_version import APP_VERSION
except Exception:
    try:
        from salesmate.app_version import APP_VERSION
    except Exception:
        APP_VERSION = "0.0.0"

DEFAULT_GITHUB_REPO = "ArashFAQ/SalesMate"  # owner/repo برای Releases

DEFAULT_UPDATE_URL = ""  # خالی = فقط از GitHub Releases (خودکار)

BACKUP_DIR = APP_DIR / "backups"

SETTINGS_PATH = APP_DIR / "settings.json"

ATTACHMENTS_DIR = APP_DIR / "attachments"

ATTACHMENTS_DIR.mkdir(exist_ok=True)

setup_logging(APP_DIR)

_sb_push_lock = threading.Lock()

_sb_push_again = False

_sb_timer = None

_sb_sync_busy = False

_local_dirty = False

_BACKGROUND_PULL_INTERVAL_MS = 600000  # 10 دقیقه — دریافت پس‌زمینه غیرفعال است ولی مقدار دارد

_last_supabase_pull_at = 0.0

_last_supabase_push_at = 0.0

_sb_last_error = ""

_sb_last_error_at = 0.0

_CLOSE_PUSH_SKIP_SEC = 90

class _UiInvoker(QObject):
    """اجرای تابع در thread اصلی Qt. emit از هر thread امن است (صف می‌شود)."""
    _call = Signal(object)

    def __init__(self):
        super().__init__()
        self._call.connect(self._run)

    @Slot(object)
    def _run(self, fn):
        try:
            fn()
        except Exception:
            _swallow()

_ui_invoker = None

def init_ui_invoker():
    """بعد از ساخت QApplication و در thread اصلی صدا زده شود."""
    global _ui_invoker
    if _ui_invoker is None:
        _ui_invoker = _UiInvoker()

def run_in_ui(fn):
    """از thread پس‌زمینه برای به‌روزرسانی UI استفاده کن (QTimer.singleShot از thread ساده کار نمی‌کند)."""
    inv = _ui_invoker
    if inv is None:
        QTimer.singleShot(0, fn)
    else:
        inv._call.emit(fn)

def mark_local_dirty():
    global _local_dirty
    _local_dirty = True
    try:
        schedule_change_local_backup()
    except Exception:
        _swallow()

_change_local_backup_timer = None

def schedule_change_local_backup():
    """بعد از هر تغییر داده، با تأخیر کوتاه بکاپ محلی چرخشی (حداکثر ۵ فایل)."""
    global _change_local_backup_timer
    try:
        from PySide6.QtCore import QTimer
        app = QApplication.instance()
        if app is None:
            schedule_cloud_local_backup(force=True)
            return
        if _change_local_backup_timer is None:
            _change_local_backup_timer = QTimer()
            _change_local_backup_timer.setSingleShot(True)
            def _do():
                try:
                    schedule_cloud_local_backup(force=True)
                except Exception:
                    _swallow()
            _change_local_backup_timer.timeout.connect(_do)
        _change_local_backup_timer.stop()
        _change_local_backup_timer.start(2500)  # debounce 2.5s
    except Exception:
        try:
            schedule_cloud_local_backup(force=True)
        except Exception:
            _swallow()

def build_sync_payload():
    """خروجی JSON مشترک PC ↔ موبایل"""
    c = db()
    try:
        rows = c.execute(
            "SELECT id,customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount "
            "FROM invoices ORDER BY id"
        ).fetchall()
        invoices = []
        max_id = 0
        for r in rows:
            iid = int(r[0] or 0)
            max_id = max(max_id, iid)
            paid = r[9]
            if paid is None or str(paid).strip() == "":
                paid = r[5]
            invoices.append({
                "id": iid,
                "customer": r[1] or "",
                "invoiceNo": r[2] or "",
                "date": r[3] or "",
                "time": r[4] or "",
                "total": str(r[5] or "0"),
                "createdAt": r[6] or "",
                "imagePath": r[7] or "",
                "inquiryData": r[8] or "",
                "paidAmount": str(paid),
            })
        balances = {}
        for cust, adj, note, updated in c.execute(
            "SELECT customer, adjustment, note, updated_at FROM customer_balance_adj"
        ).fetchall():
            balances[cust] = str(adj or "0")
        inquiries = []
        if INQUIRY_PATH.exists():
            try:
                inquiries = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
            except Exception:
                inquiries = []
        store_sales = []
        try:
            for r in c.execute(
                "SELECT id,customer,invoice_no,date,time,total,tab,items_json,created_at "
                "FROM store_sales ORDER BY id"
            ).fetchall():
                store_sales.append({
                    "id": int(r[0] or 0),
                    "customer": r[1] or "",
                    "invoiceNo": r[2] or "",
                    "date": r[3] or "",
                    "time": r[4] or "",
                    "total": str(r[5] or "0"),
                    "tab": r[6] or "parquet",
                    "itemsJson": r[7] or "[]",
                    "createdAt": r[8] or "",
                })
        except Exception:
            store_sales = []
        s = settings()
        return {
            "version": 1,
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
            "company": s.get("company_name", "SalesMate"),
            "nextId": max_id + 1,
            "invoices": invoices,
            "balances": balances,
            "inquiries": inquiries if isinstance(inquiries, list) else [],
            "storeSales": store_sales,
        }
    finally:
        c.close()

def apply_sync_payload(data: dict):
    """جایگزینی داده محلی با payload همگام (با تأیید کاربر فراخوانی شود)"""
    if not isinstance(data, dict) or "invoices" not in data:
        raise RuntimeError("فرمت فایل همگام نامعتبر است.")
    c = db()
    try:
        c.execute("DELETE FROM invoices")
        c.execute("DELETE FROM customer_balance_adj")
        for inv in data.get("invoices") or []:
            iid = int(inv.get("id") or 0)
            vals = (
                inv.get("customer") or "",
                inv.get("invoiceNo") or inv.get("invoice_no") or "",
                inv.get("date") or "",
                inv.get("time") or "",
                str(inv.get("total") or "0"),
                inv.get("createdAt") or inv.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                inv.get("imagePath") or inv.get("image_path") or "",
                inv.get("inquiryData") or inv.get("inquiry_data") or "",
                str(inv.get("paidAmount") if inv.get("paidAmount") is not None else inv.get("paid_amount") or ""),
            )
            if iid > 0:
                c.execute(
                    "INSERT INTO invoices(id,customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (iid,) + vals,
                )
            else:
                c.execute(
                    "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    vals,
                )
        balances = data.get("balances") or {}
        if isinstance(balances, dict):
            for cust, adj in balances.items():
                c.execute(
                    "INSERT OR REPLACE INTO customer_balance_adj(customer,adjustment,note,updated_at) VALUES(?,?,?,?)",
                    (cust, str(adj), "", datetime.now().isoformat(timespec="seconds")),
                )
        c.commit()
        # fix sqlite sequence
        max_id = c.execute("SELECT COALESCE(MAX(id),0) FROM invoices").fetchone()[0]
        c.execute("DELETE FROM sqlite_sequence WHERE name='invoices'")
        try:
            c.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('invoices',?)", (max_id,))
        except Exception:
            _swallow()
        c.commit()
    finally:
        c.close()
    inquiries = data.get("inquiries")
    if isinstance(inquiries, list):
        INQUIRY_PATH.write_text(json.dumps(inquiries, ensure_ascii=False, indent=2), encoding="utf-8")
    if data.get("company"):
        s = settings()
        s["company_name"] = data["company"]
        save_settings(s)

SUPABASE_URL_DEFAULT = "https://sowftowkhvuvaijttpiv.supabase.co"

SUPABASE_KEY_DEFAULT = "sb_publishable_5BrCyhkBlDQqbdjkGnEK1w_zpsHiAs8"

SUPABASE_SESSION_FILE = APP_DIR / "supabase_session.json"

def supabase_config():
    s = settings()
    return (
        (s.get("supabase_url") or SUPABASE_URL_DEFAULT).rstrip("/"),
        s.get("supabase_key") or SUPABASE_KEY_DEFAULT,
        bool(s.get("supabase_enabled", True)),
    )

def load_supabase_session():
    try:
        if SUPABASE_SESSION_FILE.exists():
            return json.loads(SUPABASE_SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        _swallow()
    return {}

def save_supabase_session(data: dict):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SUPABASE_SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        _swallow()

def clear_supabase_session():
    try:
        if SUPABASE_SESSION_FILE.exists():
            SUPABASE_SESSION_FILE.unlink()
    except Exception:
        _swallow()

def supabase_session_valid():
    sess = load_supabase_session()
    return bool(sess.get("access_token") and sess.get("user_id"))

def supabase_user_info():
    sess = load_supabase_session()
    return {
        "user_id": sess.get("user_id") or "",
        "email": sess.get("email") or "",
        "access_token": sess.get("access_token") or "",
    }

def supabase_auth_request(path: str, body: dict):
    """Auth API: signup / token"""
    import urllib.request
    import urllib.error
    url, key, _ = supabase_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url + path, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(err)
            msg = j.get("error_description") or j.get("msg") or j.get("message") or err
        except Exception:
            msg = err
        raise RuntimeError(msg) from e

def supabase_signup(email: str, password: str):
    data = supabase_auth_request(
        "/auth/v1/signup",
        {"email": email.strip(), "password": password},
    )
    # sometimes email confirmation required → no session
    if not data.get("access_token") and data.get("user"):
        raise RuntimeError(
            "ثبت‌نام انجام شد. اگر تأیید ایمیل فعال است، ابتدا ایمیل را تأیید کنید سپس وارد شوید."
        )
    _store_auth_response(data)
    return data

def supabase_login(email: str, password: str):
    try:
        try:
            from coworker_core import login_email as _le
        except Exception:
            from salesmate.coworker_core import login_email as _le
        email = _le(email) or email
    except Exception:
        _swallow()
    data = supabase_auth_request(
        "/auth/v1/token?grant_type=password",
        {"email": email.strip(), "password": password},
    )
    if not data.get("access_token"):
        raise RuntimeError("ورود ناموفق بود.")
    _store_auth_response(data)
    return data

def _jwt_claims(access_token: str) -> dict:
    try:
        import base64
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode()).decode())
    except Exception:
        return {}

def _store_auth_response(data: dict):
    prev = load_supabase_session()
    user = data.get("user") or {}
    access = data.get("access_token") or prev.get("access_token") or ""
    claims = _jwt_claims(access) if access else {}
    uid = user.get("id") or claims.get("sub") or prev.get("user_id") or ""
    email = user.get("email") or claims.get("email") or prev.get("email") or ""
    # expires_at: unix seconds
    expires_at = None
    if data.get("expires_in") is not None:
        try:
            expires_at = int(time.time()) + int(data.get("expires_in"))
        except Exception:
            expires_at = None
    if expires_at is None and claims.get("exp"):
        try:
            expires_at = int(claims.get("exp"))
        except Exception:
            expires_at = None
    if expires_at is None and data.get("expires_at"):
        # ممکن است عدد یا رشته ISO باشد
        try:
            expires_at = int(data.get("expires_at"))
        except Exception:
            expires_at = None
    save_supabase_session({
        "access_token": access,
        "refresh_token": data.get("refresh_token") or prev.get("refresh_token") or "",
        "user_id": uid,
        "email": email,
        "expires_at": expires_at,
    })

def supabase_logout():
    clear_supabase_session()

def supabase_token_needs_refresh(leeway_sec=180):
    """آیا access_token نزدیک انقضا یا منقضی است؟"""
    sess = load_supabase_session()
    access = sess.get("access_token") or ""
    if not access:
        return True
    exp = sess.get("expires_at")
    if not exp:
        claims = _jwt_claims(access)
        exp = claims.get("exp")
    try:
        return int(exp) <= int(time.time()) + int(leeway_sec)
    except Exception:
        return True

def supabase_refresh_session(force=False):
    """تمدید access_token با refresh_token."""
    sess = load_supabase_session()
    rt = (sess.get("refresh_token") or "").strip()
    if not rt:
        return False
    if not force and not supabase_token_needs_refresh(180):
        return True
    try:
        data = supabase_auth_request(
            "/auth/v1/token?grant_type=refresh_token",
            {"refresh_token": rt},
        )
    except Exception as e:
        # فقط اگر refresh واقعاً باطل باشد نشست را پاک کن
        msg = str(e).lower()
        if "invalid" in msg or "expired" in msg and "refresh" in msg:
            # refresh token باطل → نیاز به ورود مجدد
            return False
        raise
    if not data.get("access_token"):
        return False
    _store_auth_response(data)
    return True

def ensure_supabase_auth():
    """قبل از هر ارسال ابری: توکن را در صورت نیاز تمدید کن."""
    if not supabase_session_valid():
        raise RuntimeError("ابتدا وارد حساب ابری شوید.")
    sess = load_supabase_session()
    if not (sess.get("refresh_token") or "").strip():
        # نشست قدیمی بدون refresh_token
        raise RuntimeError(
            "نشست ابری ناقص است (بدون refresh). یک‌بار خروج و ورود مجدد کنید."
        )
    try:
        ok = supabase_refresh_session(force=supabase_token_needs_refresh(300))
    except Exception as e:
        raise RuntimeError("تمدید نشست ابری ناموفق: " + str(e)) from e
    if not ok and supabase_token_needs_refresh(0):
        raise RuntimeError(
            "نشست ابری منقضی شد. لطفاً یک‌بار دوباره وارد شوید تا تمدید خودکار فعال شود."
        )
    return True

def supabase_request(method: str, path: str, body=None, extra_headers=None, use_user_token=True, _retried=False):
    import urllib.request
    import urllib.error
    url, key, _ = supabase_config()
    if not url or not key:
        raise RuntimeError("تنظیمات Supabase ناقص است.")
    token = key
    if use_user_token:
        try:
            ensure_supabase_auth()
        except RuntimeError:
            # اگر ensure خطا داد ولی هنوز access داریم، یک‌بار امتحان کن
            if not supabase_user_info().get("access_token"):
                raise
        info = supabase_user_info()
        if not info.get("access_token"):
            raise RuntimeError("ابتدا وارد حساب ابری شوید.")
        token = info["access_token"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        # هر 401/403 → force refresh و یک‌بار تکرار
        if use_user_token and not _retried and e.code in (401, 403):
            try:
                if supabase_refresh_session(force=True):
                    return supabase_request(
                        method, path, body=body, extra_headers=extra_headers,
                        use_user_token=use_user_token, _retried=True,
                    )
            except Exception:
                _swallow()
            raise RuntimeError(
                "نشست ابری منقضی یا نامعتبر است. یک‌بار دوباره وارد شوید.\n" + err
            ) from e
        raise RuntimeError(f"Supabase HTTP {e.code}: {err}") from e

def supabase_enabled():
    _, _, en = supabase_config()
    return en

def is_online(timeout=3.0):
    """بررسی دسترسی اینترنت (برای پشتیبان هنگام بستن)."""
    import socket
    import urllib.request
    try:
        url, _, _ = supabase_config()
        host = url.replace("https://", "").replace("http://", "").split("/")[0]
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, 443), timeout=timeout).close()
        return True
    except Exception:
        try:
            urllib.request.urlopen("https://www.google.com", timeout=timeout)
            return True
        except Exception:
            return False

def backup_on_close_enabled():
    return bool(settings().get("backup_on_close", True))

def _sync_inv_key(inv):
    """کلید پایدار حواله: شماره + تاریخ + مشتری (بدون مبلغ تا ویرایش مبلغ ردیف را عوض نکند)."""
    if not isinstance(inv, dict):
        return ""
    no = en_digits(str(inv.get("invoiceNo") or inv.get("invoice_no") or "")).strip()
    date = str(inv.get("date") or "").strip()
    cust = str(inv.get("customer") or "").strip()
    return "|".join([no, date, cust])

def _sync_store_key(s):
    if not isinstance(s, dict):
        return ""
    no = en_digits(str(s.get("invoiceNo") or s.get("invoice_no") or "")).strip()
    date = str(s.get("date") or "").strip()
    cust = str(s.get("customer") or "").strip()
    total = str(s.get("total") or "0").strip().replace(",", "")
    return "|".join([no, date, cust, total])

def _sync_inq_key(item):
    if not isinstance(item, dict):
        return ""
    # ترجیح fingerprint ذخیره‌شده
    fp = item.get("fingerprint") or item.get("fp")
    if fp:
        return str(fp)
    buyer = str(item.get("buyer") or item.get("customer") or "").strip()
    date = str(item.get("date") or "").strip()
    total = str(item.get("total") or item.get("grandTotal") or "0").strip()
    saved = str(item.get("savedAt") or item.get("createdAt") or "")[:19]
    return "|".join([buyer, date, total, saved])

def _cloud_inv_to_local(r):
    return {
        "id": 0,
        "customer": r.get("customer") or "",
        "invoiceNo": r.get("invoice_no") or "",
        "date": r.get("date") or "",
        "time": r.get("time") or "",
        "total": str(r.get("total") or "0"),
        "paidAmount": str(r.get("paid_amount") or ""),
        "createdAt": str(r.get("created_at") or ""),
        "inquiryData": r.get("inquiry_data") or "",
        "imagePath": r.get("image_path") or "",
    }

def _cloud_store_to_local(r):
    return {
        "customer": r.get("customer") or "",
        "invoiceNo": r.get("invoice_no") or "",
        "date": r.get("date") or "",
        "time": r.get("time") or "",
        "total": str(r.get("total") or "0"),
        "tab": r.get("tab") or "parquet",
        "itemsJson": r.get("items_json") or "[]",
        "createdAt": str(r.get("created_at") or ""),
    }

def delete_inquiry_from_cloud(item):
    """حذف یک استعلام از ابر بر اساس کلید پایدار (برای همگام حذف بین دستگاه‌ها)."""
    if not item or not isinstance(item, dict):
        return False
    if not supabase_session_valid():
        return False
    try:
        ensure_supabase_auth()
        uid = supabase_user_info()["user_id"]
        key = _sync_inq_key(item)
        if not key:
            return False
        _, cloud_inqs = supabase_request(
            "GET",
            f"/rest/v1/inquiries?user_id=eq.{uid}&select=id,payload",
        )
        deleted = 0
        for r in (cloud_inqs or []):
            pl = r.get("payload")
            if isinstance(pl, str):
                try:
                    pl = json.loads(pl)
                except Exception:
                    continue
            if not isinstance(pl, dict):
                continue
            if _sync_inq_key(pl) != key:
                continue
            rid = r.get("id")
            if rid is None:
                continue
            try:
                supabase_request(
                    "DELETE",
                    f"/rest/v1/inquiries?id=eq.{rid}&user_id=eq.{uid}",
                    extra_headers={"Prefer": "return=minimal"},
                )
                deleted += 1
            except Exception:
                _swallow()
        return deleted > 0
    except Exception:
        return False

def delete_invoice_from_cloud(inv):
    """حذف یک حواله از ابر — تا با pull دوباره برنگردد."""
    if not inv or not isinstance(inv, dict):
        return False
    if not supabase_session_valid():
        return False
    try:
        ensure_supabase_auth()
        uid = supabase_user_info()["user_id"]
        key = _sync_inv_key(inv)
        if not key:
            return False
        _, cloud_invs = supabase_request(
            "GET",
            f"/rest/v1/invoices?user_id=eq.{uid}&select=id,customer,invoice_no,date,total",
        )
        deleted = 0
        for r in (cloud_invs or []):
            loc = {
                "customer": r.get("customer") or "",
                "invoiceNo": r.get("invoice_no") or "",
                "date": r.get("date") or "",
                "total": str(r.get("total") or "0"),
            }
            if _sync_inv_key(loc) != key:
                continue
            rid = r.get("id")
            if rid is None:
                continue
            try:
                supabase_request(
                    "DELETE",
                    f"/rest/v1/invoices?id=eq.{rid}&user_id=eq.{uid}",
                    extra_headers={"Prefer": "return=minimal"},
                )
                deleted += 1
            except Exception:
                _swallow()
        return deleted > 0
    except Exception:
        return False

def delete_store_sale_from_cloud(sale):
    """حذف یک فروش فروشگاه از ابر."""
    if not sale or not isinstance(sale, dict):
        return False
    if not supabase_session_valid():
        return False
    try:
        ensure_supabase_auth()
        uid = supabase_user_info()["user_id"]
        key = _sync_store_key(sale)
        if not key:
            return False
        _, rows = supabase_request(
            "GET",
            f"/rest/v1/store_sales?user_id=eq.{uid}&select=id,customer,invoice_no,date,total",
        )
        deleted = 0
        for r in (rows or []):
            loc = {
                "customer": r.get("customer") or "",
                "invoiceNo": r.get("invoice_no") or "",
                "date": r.get("date") or "",
                "total": str(r.get("total") or "0"),
            }
            if _sync_store_key(loc) != key:
                continue
            rid = r.get("id")
            if rid is None:
                continue
            try:
                supabase_request(
                    "DELETE",
                    f"/rest/v1/store_sales?id=eq.{rid}&user_id=eq.{uid}",
                    extra_headers={"Prefer": "return=minimal"},
                )
                deleted += 1
            except Exception:
                _swallow()
        return deleted > 0
    except Exception:
        return False

_push_progress_cb = None


def _push_progress(pct, text=""):
    """گزارش پیشرفت ارسال به ابر (۰ تا ۱۰۰) برای نوار هنگام بستن برنامه."""
    cb = _push_progress_cb
    if cb:
        try:
            cb(pct, text)
        except Exception:
            pass


def push_all_to_supabase():
    """آپلود داده محلی به ابر — فقط برای کاربر لاگین‌شده.
    با قفل سراسری: چند ارسال همزمان دیگر داده را له نمی‌کند."""
    global _sb_push_again, _sb_last_error, _sb_last_error_at
    set_cloud_sync_ui("up")
    last = ""
    try:
        with _sb_push_lock:
            while True:
                _sb_push_again = False
                last = _push_all_to_supabase_body()
                # اگر وسط ارسال، تغییر جدیدی آمده دوباره با داده تازه بفرست
                if not _sb_push_again:
                    break
        _sb_last_error = ""
        return last
    except Exception as _ex:
        _sb_last_error = str(_ex)[:300] or _ex.__class__.__name__
        _sb_last_error_at = time.time()
        raise
    finally:
        set_cloud_sync_ui("")

_MOBILE_STATE_PATH = APP_DIR / "mobile_snap_state.json"


def _mobile_norm_customer_fn():
    """همان قاعده‌ی آمار پارکت: نام‌های فروشگاه → «فروشگاه ایزوفام»."""
    names = set()
    try:
        c = db()
        for r in c.execute("SELECT DISTINCT customer FROM store_sales WHERE customer IS NOT NULL AND TRIM(customer) != ''").fetchall():
            n = " ".join(str(r[0] or "").split())
            if n:
                names.add(n)
        c.close()
    except Exception:
        _swallow()

    def norm(name):
        s = str(name or "").strip()
        if not s:
            return s
        if s.startswith("فروشگاه ایزوفام") or s.startswith("فروشگاه ايزوفام"):
            return "فروشگاه ایزوفام"
        if " ".join(s.split()) in names:
            return "فروشگاه ایزوفام"
        return s
    return norm


def push_mobile_snapshots(force=False):
    """آمار پارکت، سمپل/استند و بالانس موجودی را برای اپ موبایل در جدول mobile_snapshots می‌نویسد.
    فقط وقتی فایل‌های منبع (کش تحلیل فروش، inventory_balance.json) نسبت به آخرین ارسال تغییر کرده باشند
    ساخته می‌شود تا بستن/ارسال سریع بماند. اگر جدول در Supabase ساخته نشده باشد بی‌صدا رد می‌شود."""
    cache = APP_DIR / "analysis_sales_cache.pkl"
    store_p = APP_DIR / "inventory_balance.json"

    def _mt(p):
        try:
            return p.stat().st_mtime if p.exists() else 0
        except Exception:
            return 0

    cur = {"cache": _mt(cache), "store": _mt(store_p)}
    try:
        old = json.loads(_MOBILE_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    if not force and old.get("cache") == cur["cache"] and old.get("store") == cur["store"] and old.get("ok"):
        return []
    try:
        from mobile_snapshots import build_all, push_snapshots
    except Exception:
        from salesmate.mobile_snapshots import build_all, push_snapshots
    df = None
    if cur["cache"]:
        try:
            import pandas as pd
            df = pd.read_pickle(str(cache))
        except Exception:
            df = None
    store = None
    if cur["store"]:
        try:
            try:
                import inventory_core as _ic
            except Exception:
                from salesmate import inventory_core as _ic
            store = _ic.load_store(store_p)
        except Exception:
            store = None
    snaps = build_all(df, store, _mobile_norm_customer_fn())
    if not snaps:
        return []
    sent, _ = push_snapshots(lambda m, pth, body=None, hdr=None: supabase_request(m, pth, body, hdr), snaps)
    try:
        _MOBILE_STATE_PATH.write_text(json.dumps({**cur, "ok": True}), encoding="utf-8")
    except Exception:
        _swallow()
    return sent


def _push_all_to_supabase_body():
    """ارسال ادغامی سریع‌تر:
    - فقط ردیف‌های جدید/تغییریافته
    - PATCH موازی (بدون قفل UI طولانی)
    - بدون DELETE دسته‌جمعی
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if not supabase_session_valid():
        raise RuntimeError("برای ارسال به ابر باید وارد شوید.")
    _push_progress(4, "بررسی ورود به ابر…")
    ensure_supabase_auth()
    uid = supabase_user_info()["user_id"]
    _push_progress(8, "آماده‌سازی داده‌ها…")
    payload = build_sync_payload()
    _push_progress(14, "ارسال حواله‌ها…")
    local_invs = payload.get("invoices") or []
    local_stores = payload.get("storeSales") or []
    local_inqs = payload.get("inquiries") or []
    local_bals = payload.get("balances") or {}

    # حافظه‌ی «آخرین وضعیت ارسال‌شده» تا حواله‌های بدون تغییر دوباره PATCH نشوند
    # (ستون inquiry_data از ابر دانلود نمی‌شود، پس مقایسه‌ی مستقیم همیشه «متفاوت» درمی‌آمد)
    import hashlib as _hl
    _state_path = APP_DIR / "cloud_push_state.json"
    try:
        _state = json.loads(_state_path.read_text(encoding="utf-8"))
        if not isinstance(_state, dict):
            _state = {}
    except Exception:
        _state = {}
    _inv_state = dict((_state.get("inv") or {}).get(uid) or {})
    _inq_known = set((_state.get("inq") or {}).get(uid) or [])

    def _row_hash(r):
        raw = "\x1f".join(str(r.get(c) or "") for c in (
            "customer", "invoice_no", "date", "time", "total", "paid_amount", "inquiry_data", "image_path"))
        return _hl.md5(raw.encode("utf-8")).hexdigest()

    def _same_light(local_row, cloud_r):
        return (
            str(cloud_r.get("customer") or "") == local_row["customer"]
            and str(cloud_r.get("invoice_no") or "") == local_row["invoice_no"]
            and str(cloud_r.get("date") or "") == local_row["date"]
            and str(cloud_r.get("time") or "") == local_row["time"]
            and str(cloud_r.get("total") or "0") == local_row["total"]
            and str(cloud_r.get("paid_amount") or "") == local_row["paid_amount"]
        )

    def _same_inv(local_row, cloud_r):
        return (
            str(cloud_r.get("customer") or "") == local_row["customer"]
            and str(cloud_r.get("invoice_no") or "") == local_row["invoice_no"]
            and str(cloud_r.get("date") or "") == local_row["date"]
            and str(cloud_r.get("time") or "") == local_row["time"]
            and str(cloud_r.get("total") or "0") == local_row["total"]
            and str(cloud_r.get("paid_amount") or "") == local_row["paid_amount"]
            and str(cloud_r.get("inquiry_data") or "") == local_row["inquiry_data"]
        )

    # ---- invoices ----
    try:
        _, cloud_invs = supabase_request(
            "GET",
            f"/rest/v1/invoices?user_id=eq.{uid}&select=id,customer,invoice_no,date,time,total,paid_amount,created_at",
        )
        cloud_invs = cloud_invs or []
    except Exception:
        cloud_invs = []
    cloud_inv_map = {}
    for r in cloud_invs:
        k = _sync_inv_key({
            "invoiceNo": r.get("invoice_no"),
            "date": r.get("date"),
            "customer": r.get("customer"),
            "total": r.get("total"),
        })
        if k:
            cloud_inv_map[k] = r

    to_post, to_patch = [], []
    for inv in local_invs:
        row = {
            "customer": inv.get("customer") or "",
            "invoice_no": inv.get("invoiceNo") or "",
            "date": inv.get("date") or "",
            "time": inv.get("time") or "",
            "total": str(inv.get("total") or "0"),
            "paid_amount": str(inv.get("paidAmount") or ""),
            "created_at": inv.get("createdAt") or datetime.now().isoformat(timespec="seconds"),
            "inquiry_data": inv.get("inquiryData") or "",
            "image_path": inv.get("imagePath") or "",
            "user_id": uid,
        }
        k = _sync_inv_key(inv)
        existing = cloud_inv_map.get(k)
        h = _row_hash(row)
        if existing and existing.get("id") is not None:
            if _inv_state.get(k) == h:
                if not _same_light(row, existing):
                    to_patch.append((existing["id"], row, k, h))
            elif k not in _inv_state and _same_light(row, existing):
                _inv_state[k] = h            # اولین بار بعد از به‌روزرسانی: ابر همان ارسال قبلی است
            else:
                to_patch.append((existing["id"], row, k, h))
        else:
            to_post.append(row)
            _inv_state[k] = h

    for i in range(0, len(to_post), 100):
        supabase_request(
            "POST", "/rest/v1/invoices", to_post[i:i + 100],
            extra_headers={"Prefer": "return=minimal"},
        )

    def _patch_inv(item):
        cid, row, k_, h_ = item
        try:
            supabase_request(
                "PATCH",
                f"/rest/v1/invoices?id=eq.{cid}&user_id=eq.{uid}",
                row,
                extra_headers={"Prefer": "return=minimal"},
            )
            _inv_state[k_] = h_             # فقط بعد از PATCH موفق در حافظه ثبت می‌شود
        except Exception:
            _swallow()

    if to_patch:
        with ThreadPoolExecutor(max_workers=8) as ex:
            list(ex.map(_patch_inv, to_patch))

    # حذف حواله‌های ابری که محلی دیگر نیستند (همگام حذف)
    local_keys = set()
    for inv in local_invs:
        k = _sync_inv_key(inv)
        if k:
            local_keys.add(k)
    for k in list(_inv_state):
        if k not in local_keys:
            _inv_state.pop(k, None)
    for k, r in list(cloud_inv_map.items()):
        if k and k not in local_keys and r.get("id") is not None:
            try:
                supabase_request(
                    "DELETE",
                    f"/rest/v1/invoices?id=eq.{r['id']}&user_id=eq.{uid}",
                    extra_headers={"Prefer": "return=minimal"},
                )
            except Exception:
                _swallow()

    _push_progress(60, "ارسال موجودی‌ها…")
    # ---- balances ----
    try:
        _, cloud_bals = supabase_request(
            "GET",
            f"/rest/v1/customer_balances?user_id=eq.{uid}&select=id,customer,adjustment",
        )
        cloud_bals = cloud_bals or []
    except Exception:
        cloud_bals = []
    cloud_bal_map = {(r.get("customer") or ""): r for r in cloud_bals}
    bal_post, bal_patch = [], []
    for cust, adj in (local_bals or {}).items():
        if not cust:
            continue
        body = {
            "customer": cust,
            "adjustment": str(adj),
            "note": "",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "user_id": uid,
        }
        ex = cloud_bal_map.get(cust)
        if ex and str(ex.get("adjustment") or "0") == str(adj):
            continue
        if ex and ex.get("id") is not None:
            bal_patch.append((ex["id"], body))
        else:
            bal_post.append(body)
    if bal_post:
        try:
            supabase_request(
                "POST", "/rest/v1/customer_balances", bal_post,
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            for body in bal_post:
                try:
                    supabase_request(
                        "POST", "/rest/v1/customer_balances", body,
                        extra_headers={"Prefer": "return=minimal"},
                    )
                except Exception:
                    _swallow()

    def _patch_bal(item):
        cid, body = item
        try:
            supabase_request(
                "PATCH",
                f"/rest/v1/customer_balances?id=eq.{cid}&user_id=eq.{uid}",
                body,
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            _swallow()

    if bal_patch:
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_patch_bal, bal_patch))

    _push_progress(75, "ارسال استعلام‌ها…")
    # ---- inquiries ----
    cloud_inqs = []
    if not _inq_known:                    # فقط بار اول (بدون حافظه) کل استعلام‌های ابر دانلود می‌شود
        try:
            _, cloud_inqs = supabase_request(
                "GET",
                f"/rest/v1/inquiries?user_id=eq.{uid}&select=id,payload,created_at",
            )
            cloud_inqs = cloud_inqs or []
        except Exception:
            cloud_inqs = []
    cloud_inq_map = {}
    for r in cloud_inqs:
        pl = r.get("payload")
        if isinstance(pl, str):
            try:
                pl = json.loads(pl)
            except Exception:
                pl = {}
        if not isinstance(pl, dict):
            pl = {}
        k = _sync_inq_key(pl)
        if k:
            cloud_inq_map[k] = r
    inq_post = []
    for item in local_inqs:
        if not isinstance(item, dict):
            continue
        k = _sync_inq_key(item)
        if k and (k in cloud_inq_map or k in _inq_known):
            _inq_known.add(k)
            continue  # بدون تغییر؛ استعلام معمولاً ثابت است
        if k:
            _inq_known.add(k)
        inq_post.append({
            "payload": item,
            "user_id": uid,
            "created_at": item.get("savedAt") or item.get("createdAt") or datetime.now().isoformat(timespec="seconds"),
        })
    for i in range(0, len(inq_post), 40):
        try:
            supabase_request(
                "POST", "/rest/v1/inquiries", inq_post[i:i + 40],
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            _swallow()

    _push_progress(88, "ارسال فروش فروشگاه…")
    # ---- store_sales ----
    try:
        _, cloud_store = supabase_request(
            "GET",
            f"/rest/v1/store_sales?user_id=eq.{uid}&select=id,customer,invoice_no,date,time,total,tab,items_json,created_at",
        )
        cloud_store = cloud_store or []
    except Exception:
        cloud_store = []
    cloud_st_map = {}
    for r in cloud_store:
        k = _sync_store_key({
            "invoiceNo": r.get("invoice_no"),
            "date": r.get("date"),
            "customer": r.get("customer"),
            "total": r.get("total"),
        })
        if k:
            cloud_st_map[k] = r
    st_post, st_patch = [], []
    for s in local_stores:
        row = {
            "customer": s.get("customer") or "",
            "invoice_no": s.get("invoiceNo") or "",
            "date": s.get("date") or "",
            "time": s.get("time") or "",
            "total": str(s.get("total") or "0"),
            "tab": s.get("tab") or "parquet",
            "items_json": s.get("itemsJson") or "[]",
            "created_at": s.get("createdAt") or datetime.now().isoformat(timespec="seconds"),
            "user_id": uid,
        }
        k = _sync_store_key(s)
        ex = cloud_st_map.get(k)
        if ex and ex.get("id") is not None:
            same = (
                str(ex.get("total") or "0") == row["total"]
                and str(ex.get("items_json") or "[]") == row["items_json"]
                and str(ex.get("customer") or "") == row["customer"]
            )
            if not same:
                st_patch.append((ex["id"], row))
        else:
            st_post.append(row)
    for i in range(0, len(st_post), 80):
        try:
            supabase_request(
                "POST", "/rest/v1/store_sales", st_post[i:i + 80],
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            _swallow()

    def _patch_st(item):
        cid, row = item
        try:
            supabase_request(
                "PATCH",
                f"/rest/v1/store_sales?id=eq.{cid}&user_id=eq.{uid}",
                row,
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            _swallow()

    if st_patch:
        with ThreadPoolExecutor(max_workers=6) as ex:
            list(ex.map(_patch_st, st_patch))

    try:
        _state.setdefault("inv", {})[uid] = _inv_state
        _state.setdefault("inq", {})[uid] = sorted(_inq_known)
        _state_path.write_text(json.dumps(_state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        _swallow()

    global _local_dirty, _last_supabase_push_at
    _local_dirty = False
    try:
        _last_supabase_push_at = time.time()
    except Exception:
        _last_supabase_push_at = __import__("time").time()
    # بکاپ محلی چرخشی (حداکثر ۵ فایل) در پس‌زمینه
    try:
        schedule_cloud_local_backup(force=False)
    except Exception:
        _swallow()
    _push_progress(94, "ارسال آمار برای موبایل…")
    try:
        push_mobile_snapshots()
    except Exception as _ex:  # جدول mobile_snapshots ممکن است هنوز ساخته نشده باشد
        try:
            log.warning("mobile snapshots: %s", _ex)
        except Exception:
            _swallow()
    _push_progress(100, "انجام شد")
    return datetime.now().isoformat(timespec="seconds")

def soft_pull_check_and_merge():
    """بررسی سبک ابر: بدون دانلود inquiry_data همه ردیف‌ها.
    فقط اگر ردیف جدید/حذف‌شده یا تغییر فیلدهای سبک بود، همان‌ها را کامل می‌گیرد.
    Returns True اگر داده محلی عوض شد.
    """
    global _last_supabase_pull_at, _local_dirty
    if not supabase_session_valid():
        return False
    if _local_dirty:
        return False
    ensure_supabase_auth()
    set_cloud_sync_ui("down")
    changed = False
    try:
        uid = supabase_user_info()["user_id"]
        # سبک: بدون inquiry_data / image_path
        light_sel = "id,customer,invoice_no,date,time,total,paid_amount,created_at"
        _, cloud_invs = supabase_request(
            "GET",
            f"/rest/v1/invoices?user_id=eq.{uid}&select={light_sel}",
        )
        cloud_invs = cloud_invs or []
        try:
            _, cloud_bals = supabase_request(
                "GET",
                f"/rest/v1/customer_balances?user_id=eq.{uid}&select=id,customer,adjustment",
            )
            cloud_bals = cloud_bals or []
        except Exception:
            cloud_bals = []
        try:
            _, cloud_inqs = supabase_request(
                "GET",
                f"/rest/v1/inquiries?user_id=eq.{uid}&select=id,buyer,date,total,saved_at,created_at",
            )
            cloud_inqs = cloud_inqs or []
        except Exception:
            cloud_inqs = []
        try:
            _, cloud_stores = supabase_request(
                "GET",
                f"/rest/v1/store_sales?user_id=eq.{uid}&select=id,customer,invoice_no,date,time,total,tab,created_at",
            )
            cloud_stores = cloud_stores or []
        except Exception:
            cloud_stores = []

        payload = build_sync_payload()
        local_invs = payload.get("invoices") or []
        local_map = {}
        for inv in local_invs:
            k = _sync_inv_key(inv)
            if k:
                local_map[k] = inv

        cloud_map = {}
        for r in cloud_invs:
            k = _sync_inv_key({
                "invoiceNo": r.get("invoice_no"),
                "date": r.get("date"),
                "customer": r.get("customer"),
                "total": r.get("total"),
            })
            if k:
                cloud_map[k] = r

        # فقط ردیف‌هایی که لوکال اصلاً ندارد — هرگز حواله موجود لوکال را با ابر بازنویسی نکن
        # (بازنویسی باعث برگشت ویرایش بعد از ۱–۵ دقیقه می‌شد)
        need_full_ids = []
        for k, r in cloud_map.items():
            if k not in local_map and r.get("id") is not None:
                need_full_ids.append(str(r["id"]))

        full_rows = []
        # batch in chunks of 30
        for i in range(0, len(need_full_ids), 30):
            chunk = need_full_ids[i:i+30]
            if not chunk:
                continue
            ids_or = ",".join(chunk)
            try:
                _, rows = supabase_request(
                    "GET",
                    f"/rest/v1/invoices?user_id=eq.{uid}&id=in.({ids_or})&select=*",
                )
                full_rows.extend(rows or [])
            except Exception:
                # fallback: one full pull if batch fails
                return False

        if full_rows:
            # merge only these into local via apply-like logic
            for r in full_rows:
                k = _sync_inv_key({
                    "invoiceNo": r.get("invoice_no"),
                    "date": r.get("date"),
                    "customer": r.get("customer"),
                    "total": r.get("total"),
                })
                loc = {
                    "id": None,
                    "customer": r.get("customer") or "",
                    "invoiceNo": r.get("invoice_no") or "",
                    "date": r.get("date") or "",
                    "time": r.get("time") or "",
                    "total": str(r.get("total") or "0"),
                    "paidAmount": str(r.get("paid_amount") or ""),
                    "createdAt": r.get("created_at") or "",
                    "inquiryData": r.get("inquiry_data") or "",
                    "imagePath": r.get("image_path") or "",
                }
                if k in local_map:
                    # حواله از قبل لوکال هست — soft-pull آن را دست نمی‌زند (جلوگیری از برگشت ویرایش)
                    pass
                else:
                    try:
                        c = db()
                        try:
                            c.execute(
                                "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                                "VALUES(?,?,?,?,?,?,?,?,?)",
                                (
                                    loc["customer"], loc["invoiceNo"], loc["date"], loc["time"],
                                    loc["total"], loc["createdAt"], loc["imagePath"],
                                    loc["inquiryData"], loc["paidAmount"],
                                ),
                            )
                            c.commit()
                        finally:
                            c.close()
                        changed = True
                    except Exception:
                        _swallow()

        # balances: اگر تعدیل ابر با لوکال فرق داشت اعمال کن
        try:
            local_bals = payload.get("balances") or {}
            bal_changed = False
            c = db()
            try:
                for r in cloud_bals:
                    cust = (r.get("customer") or "").strip()
                    if not cust:
                        continue
                    cadj = str(r.get("adjustment") or "0")
                    ladj = str(local_bals.get(cust) or "0")
                    if cadj != ladj:
                        c.execute(
                            "INSERT OR REPLACE INTO customer_balance_adj(customer,adjustment,note,updated_at) VALUES(?,?,?,?)",
                            (cust, cadj, "", __import__("datetime").datetime.now().isoformat(timespec="seconds")),
                        )
                        bal_changed = True
                if bal_changed:
                    c.commit()
                    changed = True
            finally:
                c.close()
        except Exception:
            _swallow()

        # inquiries: if cloud has more, full pull inquiries only once
        local_inqs = payload.get("inquiries") or []
        if len(cloud_inqs) > len(local_inqs) + 0:
            # fetch full inquiries list once
            try:
                _, full_inqs = supabase_request(
                    "GET",
                    f"/rest/v1/inquiries?user_id=eq.{uid}&select=*",
                )
                if full_inqs:
                    # reuse part of pull_all — apply inquiries into settings/json path via apply_sync
                    # minimal: call full pull only for inquiries path through existing merge
                    # to keep simple and safe: if inquiry count differs significantly, full pull
                    if abs(len(full_inqs) - len(local_inqs)) >= 1:
                        pull_all_from_supabase()
                        return True
            except Exception:
                _swallow()

        # store sales count mismatch → full pull
        try:
            c = db()
            try:
                n_store = c.execute("SELECT COUNT(*) FROM store_sales").fetchone()[0]
            finally:
                c.close()
        except Exception:
            n_store = 0
        if len(cloud_stores) > int(n_store or 0):
            pull_all_from_supabase()
            return True

        _last_supabase_pull_at = __import__("time").time()
        return changed
    finally:
        set_cloud_sync_ui("")

def pull_all_from_supabase():
    """دریافت ادغامی از ابر — ردیف‌های فقط-محلی پاک نمی‌شوند."""
    global _last_supabase_pull_at, _local_dirty
    if not supabase_session_valid():
        raise RuntimeError("برای دریافت از ابر باید وارد شوید.")
    if _local_dirty:
        # اول ارسال محلی
        try:
            push_all_to_supabase()
        except Exception as e:
            raise RuntimeError("تغییرات محلی هنوز ارسال نشده: " + str(e))
    ensure_supabase_auth()
    set_cloud_sync_ui("down")
    try:
        uid = supabase_user_info()["user_id"]
        _, cloud_invs = supabase_request("GET", f"/rest/v1/invoices?user_id=eq.{uid}&select=*")
        cloud_invs = cloud_invs or []
        try:
            _, cloud_bals = supabase_request("GET", f"/rest/v1/customer_balances?user_id=eq.{uid}&select=*")
            cloud_bals = cloud_bals or []
        except Exception:
            cloud_bals = []
        try:
            _, cloud_inqs = supabase_request("GET", f"/rest/v1/inquiries?user_id=eq.{uid}&select=*")
            cloud_inqs = cloud_inqs or []
        except Exception:
            cloud_inqs = []
        try:
            _, cloud_store = supabase_request("GET", f"/rest/v1/store_sales?user_id=eq.{uid}&select=*")
            cloud_store = cloud_store or []
        except Exception:
            cloud_store = []

        # --- merge invoices ---
        payload = build_sync_payload()
        local_invs = list(payload.get("invoices") or [])
        local_map = {}
        for inv in local_invs:
            k = _sync_inv_key(inv)
            if k:
                local_map[k] = inv
        for r in cloud_invs:
            loc = _cloud_inv_to_local(r)
            k = _sync_inv_key(loc)
            if not k:
                continue
            if k not in local_map:
                local_invs.append(loc)
                local_map[k] = loc
            else:
                # دریافت از ابر: مبلغ پرداختی و فیلدهای اصلی از ابر بیاید (بدهکار/طلبکار یکسان)
                cur = local_map[k]
                if loc.get("total") is not None and str(loc.get("total")) != "":
                    cur["total"] = str(loc.get("total"))
                cur["paidAmount"] = str(loc.get("paidAmount") if loc.get("paidAmount") is not None else "")
                if loc.get("inquiryData"):
                    cur["inquiryData"] = loc["inquiryData"]
                if loc.get("imagePath"):
                    cur["imagePath"] = loc["imagePath"]
                if loc.get("time"):
                    cur["time"] = loc["time"]
                if loc.get("customer"):
                    cur["customer"] = loc["customer"]

        # --- merge balances: ابر مرجع تعدیل‌هاست ---
        balances = {}
        for r in cloud_bals:
            cust = r.get("customer") or ""
            if cust:
                balances[cust] = str(r.get("adjustment") or "0")

        # --- inquiries: ابر مرجع لیست است (حذف‌ها هم منتقل شوند) ---
        local_inqs = []
        seen_inq = set()
        for r in cloud_inqs:
            pl = r.get("payload")
            if isinstance(pl, str):
                try:
                    pl = json.loads(pl)
                except Exception:
                    continue
            if not isinstance(pl, dict):
                continue
            k = _sync_inq_key(pl)
            if k and k in seen_inq:
                continue
            if k:
                seen_inq.add(k)
            local_inqs.append(pl)

        # --- merge store ---
        local_stores = list(payload.get("storeSales") or [])
        st_map = {}
        for s in local_stores:
            k = _sync_store_key(s)
            if k:
                st_map[k] = s
        for r in cloud_store:
            loc = _cloud_store_to_local(r)
            k = _sync_store_key(loc)
            if k and k not in st_map:
                local_stores.append(loc)
                st_map[k] = loc

        data = {
            "version": 1,
            "updatedAt": datetime.now().isoformat(timespec="seconds"),
            "company": settings().get("company_name", "SalesMate"),
            "nextId": max([int(i.get("id") or 0) for i in local_invs] + [0]) + 1,
            "invoices": local_invs,
            "balances": balances,
            "inquiries": local_inqs,
            "storeSales": local_stores,
        }
        # بک‌آپ قبل از اعمال
        try:
            if DB_PATH.exists():
                bak = APP_DIR / ("salesmate_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db")
                shutil.copy2(DB_PATH, bak)
                baks = sorted(APP_DIR.glob("salesmate_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
                for oldb in baks[5:]:
                    try:
                        oldb.unlink()
                    except Exception:
                        _swallow()
        except Exception:
            _swallow()
        apply_sync_payload(data)
        # store sales in sqlite if table exists
        try:
            c = db()
            try:
                c.execute("DELETE FROM store_sales")
                for s in local_stores:
                    c.execute(
                        "INSERT INTO store_sales(customer,invoice_no,date,time,total,tab,items_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                        (
                            s.get("customer") or "",
                            s.get("invoiceNo") or "",
                            s.get("date") or "",
                            s.get("time") or "",
                            str(s.get("total") or "0"),
                            s.get("tab") or "parquet",
                            s.get("itemsJson") or "[]",
                            s.get("createdAt") or "",
                        ),
                    )
                c.commit()
            finally:
                c.close()
        except Exception:
            _swallow()
        _last_supabase_pull_at = __import__("time").time()
        _local_dirty = False
        return data["updatedAt"]
    finally:
        set_cloud_sync_ui("")

def set_cloud_sync_ui(mode):
    """mode: 'up' | 'down' | ''  — فلش کوچک گوشه بالا چپ"""
    w = _cloud_ui_window
    if w is None:
        return
    try:
        from PySide6.QtCore import QTimer
        def _apply():
            try:
                w._set_sync_flash(mode)
            except Exception:
                _swallow()
        QTimer.singleShot(0, _apply)
    except Exception:
        _swallow()

def schedule_supabase_sync():
    """تغییر محلی → بکاپ لوکال + ارسال به ابر (debounce)."""
    global _sb_timer, _sb_sync_busy
    mark_local_dirty()
    # بک‌آپ چرخشی محلی از دیتابیس (بدون وابستگی به ابر)
    try:
        if DB_PATH.exists():
            bak = APP_DIR / "salesmate_autosave.db"
            shutil.copy2(DB_PATH, bak)
    except Exception:
        _swallow()
    if not supabase_enabled() or not supabase_session_valid():
        return
    app = QApplication.instance()
    if app is None:
        return
    if _sb_timer is None:
        from PySide6.QtCore import QTimer
        _sb_timer = QTimer()
        _sb_timer.setSingleShot(True)

        def _do():
            global _sb_sync_busy, _sb_push_again
            if _sb_sync_busy:
                # ارسال در جریان است — بعد از اتمام یک‌بار دیگر با داده تازه
                _sb_push_again = True
                return
            _sb_sync_busy = True

            def _worker():
                global _sb_sync_busy
                try:
                    push_all_to_supabase()
                except Exception:
                    _swallow()
                finally:
                    _sb_sync_busy = False

            import threading
            threading.Thread(target=_worker, daemon=True).start()

        _sb_timer.timeout.connect(_do)
    _sb_timer.stop()
    _sb_timer.start(4000)  # debounce بیشتر برای کاهش ترافیک

def extract_design_codes(name: str):
    """استخراج کدهای طرح از نام کالا برای جستجو"""
    import re as _re
    s = str(name or "")
    codes = set()
    for m in _re.finditer(r"NEW\s*WAY\s+(\d{3,5})", s, _re.I):
        codes.add(m.group(1))
    for m in _re.finditer(r"\bV\s*-?\s*(\d{3,5})\b", s, _re.I):
        codes.add(m.group(1))
    for m in _re.finditer(r"\bE\s*-\s*(\d{2,5})\b", s, _re.I):
        codes.add(m.group(1))
    for m in _re.finditer(r"[-–]\s*(\d{3,5})\b", s):
        codes.add(m.group(1))
    for m in _re.finditer(r"\b(\d{4,5})\b", s):
        codes.add(m.group(1))
    return sorted(codes, key=lambda x: int(x) if x.isdigit() else 0)

def inventory_path():
    return APP_DIR / "inventory.json"

def load_inventory():
    p = inventory_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data.get("items") or []
        if isinstance(data, list):
            return data
    except Exception:
        _swallow()
    return []

def save_inventory(items, meta=None):
    payload = {
        "items": items or [],
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
        "meta": meta or {},
    }
    inventory_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload

def parse_inventory_excel(path):
    """خواندن فایل اکسل موجودی آمیسا — ستون‌های کد کالا، نام، تعداد کارتن، متراژ"""
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    # پیدا کردن هدر
    header_idx = 0
    headers = [str(c or "").strip() for c in rows[0]]
    for i, r in enumerate(rows[:5]):
        hs = [str(c or "").strip() for c in r]
        joined = " ".join(hs)
        if "کد" in joined or "کالا" in joined:
            header_idx = i
            headers = hs
            break

    def col(*keys):
        for i, h in enumerate(headers):
            for k in keys:
                if k in h:
                    return i
        return None

    i_code = col("کد کالا", "کدکالا", "کد")
    i_name = col("نام کالا", "نامکالا", "شرح", "نام")
    i_cart = col("تعداد 1", "تعداد۱", "مانده", "کارتن")
    i_m2 = col("تعداد 2", "تعداد۲", "متر")
    # اگر پیدا نشد با ترتیب ثابت Book1
    if i_code is None:
        i_code = 1 if len(headers) > 1 else 0
    if i_name is None:
        i_name = 2 if len(headers) > 2 else 1
    if i_cart is None:
        i_cart = 4 if len(headers) > 4 else 3
    if i_m2 is None:
        i_m2 = 5 if len(headers) > 5 else 4

    items = []
    for r in rows[header_idx + 1:]:
        if not r:
            continue
        code = str(r[i_code] if i_code < len(r) else "" or "").strip()
        name = str(r[i_name] if i_name < len(r) else "" or "").strip()
        if not code and not name:
            continue
        if "جمع" in name or "جمع" in code:
            continue
        def num(v):
            try:
                if v is None or v == "":
                    return 0.0
                if isinstance(v, (int, float)):
                    return float(v)
                s = en_digits(str(v)).replace(",", "").strip()
                return float(s) if s else 0.0
            except Exception:
                return 0.0
        cartons = num(r[i_cart] if i_cart is not None and i_cart < len(r) else 0)
        meters = num(r[i_m2] if i_m2 is not None and i_m2 < len(r) else 0)
        # اعداد بسیار کوچک شناور ≈ صفر
        if abs(cartons) < 1e-6:
            cartons = 0.0
        if abs(meters) < 1e-6:
            meters = 0.0
        dcodes = extract_design_codes(name)
        items.append({
            "product_code": code,
            "product_name": name,
            "cartons": cartons,
            "meters": meters,
            "design_codes": ",".join(dcodes),
        })
    return items

def push_inventory_to_supabase(items):
    """موجودی مشترک برای همه کاربران — حذف قبلی و درج جدید"""
    if not supabase_session_valid():
        raise RuntimeError("برای ارسال موجودی به ابر باید وارد شوید.")
    ensure_supabase_auth()
    set_cloud_sync_ui("up")
    try:
        # حذف همه ردیف‌های قبلی (جدول مشترک)
        supabase_request(
            "DELETE",
            "/rest/v1/inventory_items?updated_at=not.is.null",
            extra_headers={"Prefer": "return=minimal"},
        )
        rows = []
        for it in items:
            rows.append({
                "product_code": it.get("product_code") or "",
                "product_name": it.get("product_name") or "",
                "cartons": float(it.get("cartons") or 0),
                "meters": float(it.get("meters") or 0),
                "design_codes": it.get("design_codes") or "",
                "updated_at": datetime.now().isoformat(),
            })
        for i in range(0, len(rows), 80):
            chunk = rows[i:i + 80]
            if chunk:
                supabase_request(
                    "POST",
                    "/rest/v1/inventory_items",
                    body=chunk,
                    extra_headers={"Prefer": "return=minimal"},
                )
        # ثبت زمان بارگذاری اکسل برای نمایش در موبایل
        try:
            uploaded = None
            if rows:
                uploaded = rows[0].get("updated_at")
            save_inventory(
                items,
                meta={
                    "source": "excel_upload",
                    "uploadedAt": uploaded or datetime.now().isoformat(timespec="seconds"),
                    "count": len(rows),
                },
            )
        except Exception:
            _swallow()
        try:
            schedule_cloud_local_backup(force=False)
        except Exception:
            _swallow()
        return len(rows)
    finally:
        set_cloud_sync_ui("")

def pull_inventory_from_supabase():
    if not supabase_session_valid():
        raise RuntimeError("برای دریافت موجودی از ابر باید وارد شوید.")
    set_cloud_sync_ui("down")
    try:
        _, data = supabase_request(
            "GET",
            "/rest/v1/inventory_items?select=*&order=product_code.asc",
        )
        items = []
        for r in (data or []):
            items.append({
                "product_code": r.get("product_code") or "",
                "product_name": r.get("product_name") or "",
                "cartons": float(r.get("cartons") or 0),
                "meters": float(r.get("meters") or 0),
                "design_codes": r.get("design_codes") or "",
            })
        save_inventory(items, meta={"source": "cloud"})
        return items
    finally:
        set_cloud_sync_ui("")

CONTACTS_SEED_DATA = []

def _contacts_seed_path():
    candidates = []
    try:
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent / "contacts_seed.json")
            meipass = getattr(sys, "_MEIPASS", None)
            if meipass:
                candidates.append(Path(meipass) / "contacts_seed.json")
                candidates.append(Path(meipass) / "salesmate" / "contacts_seed.json")
    except Exception:
        _swallow()
    try:
        candidates.append(Path(__file__).resolve().parent / "contacts_seed.json")
    except Exception:
        _swallow()
    try:
        candidates.append(APP_DIR / "contacts_seed.json")
    except Exception:
        _swallow()
    for p in candidates:
        try:
            if p.exists():
                return p
        except Exception:
            _swallow()
    return candidates[0] if candidates else Path("contacts_seed.json")

def _is_placeholder_contact(c):
    """ردیف‌های عنوان/نمونه‌ی اکسل (مثل «نام / نام خانوادگی / نام موسسه») مشتری واقعی نیستند."""
    if not isinstance(c, dict):
        return True
    return (str(c.get("first_name") or "").strip() == "نام"
            and str(c.get("last_name") or "").strip() == "نام خانوادگی")

def _load_seed_contacts():
    """داده اولیه‌ی نمایندگان — از ثابت داخلی (خالی) یا فایل contacts_seed.json کنار برنامه"""
    items = list(CONTACTS_SEED_DATA) if CONTACTS_SEED_DATA else []
    if not items:
        sp = _contacts_seed_path()
        try:
            if sp.exists():
                data = json.loads(sp.read_text(encoding="utf-8"))
                if isinstance(data, list) and data:
                    items = data
                elif isinstance(data, dict) and data.get("items"):
                    items = data["items"]
        except Exception:
            items = []
    return [c for c in items if not _is_placeholder_contact(c)]

def load_contacts(force_seed=False):
    """لیست اطلاعات مشتری/نماینده — مشترک. اگر خالی بود از اکسل seed پر می‌شود."""
    items = []
    if not force_seed and CONTACTS_PATH.exists():
        try:
            data = json.loads(CONTACTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "items" in data:
                items = data.get("items") or []
            elif isinstance(data, list):
                items = data
        except Exception:
            items = []
    if not items:
        items = _load_seed_contacts()
        if items:
            try:
                save_contacts(items)
            except Exception:
                _swallow()
    return items

def save_contacts(items):
    CONTACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "items": items or [],
        "updatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    CONTACTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def push_contacts_to_supabase(items=None):
    """اطلاعات مشتری مشترک برای همه کاربران"""
    if not supabase_session_valid():
        raise RuntimeError("برای ارسال به ابر باید وارد شوید.")
    ensure_supabase_auth()
    set_cloud_sync_ui("up")
    try:
        if items is None:
            items = load_contacts()
        # پاکسازی جدول مشترک
        try:
            supabase_request(
                "DELETE",
                "/rest/v1/customer_contacts?id=gt.0",
                extra_headers={"Prefer": "return=minimal"},
            )
        except Exception:
            try:
                supabase_request(
                    "DELETE",
                    "/rest/v1/customer_contacts?updated_at=not.is.null",
                    extra_headers={"Prefer": "return=minimal"},
                )
            except Exception:
                _swallow()
        rows = []
        now = datetime.now().isoformat(timespec="seconds")
        for it in (items or []):
            rows.append({
                "first_name": it.get("first_name") or "",
                "last_name": it.get("last_name") or "",
                "company": it.get("company") or "",
                "phone": it.get("phone") or "",
                "mobile": it.get("mobile") or "",
                "city": it.get("city") or "",
                "address": it.get("address") or "",
                "updated_at": now,
            })
        for i in range(0, len(rows), 50):
            chunk = rows[i:i + 50]
            if chunk:
                supabase_request(
                    "POST",
                    "/rest/v1/customer_contacts",
                    body=chunk,
                    extra_headers={"Prefer": "return=minimal"},
                )
        save_contacts(items or [])
        return len(rows)
    finally:
        set_cloud_sync_ui("")

def pull_contacts_from_supabase():
    if not supabase_session_valid():
        raise RuntimeError("برای دریافت از ابر باید وارد شوید.")
    set_cloud_sync_ui("down")
    try:
        _, data = supabase_request(
            "GET",
            "/rest/v1/customer_contacts?select=*&order=id.asc",
        )
        items = []
        for r in (data or []):
            items.append({
                "first_name": r.get("first_name") or "",
                "last_name": r.get("last_name") or "",
                "company": r.get("company") or "",
                "phone": r.get("phone") or "",
                "mobile": r.get("mobile") or "",
                "city": r.get("city") or "",
                "address": r.get("address") or "",
            })
        if items:
            save_contacts(items)
        return items
    finally:
        set_cloud_sync_ui("")

APP_STYLE = """
QWidget { background:#F5F7FA; color:#17202A; font-family:"Segoe UI"; }
QLabel, QCheckBox, QRadioButton { background:transparent; }
#header { background:white; border-bottom:1px solid #E5E7EB; }
#brand { color:#1565C0; font-size:24px; font-weight:700; }
#subtitle { color:#7B8794; font-size:12px; }
#hello { font-size:27px; font-weight:700; }
#pageTitle { font-size:25px; font-weight:700; }
#sectionTitle { font-size:19px; font-weight:700; }
#hint { color:#6B7280; font-size:14px; }
.card { background:white; border:1px solid #E7EBF0; border-radius:16px; }
.statTitle { color:#6B7280; font-size:13px; }
.statValue { color:#1565C0; font-size:23px; font-weight:700; }
#newInvoice,#primaryButton {
    background:#1565C0; color:white; border:none; border-radius:14px;
    font-size:16px; font-weight:700; padding:14px;
}
#newInvoice:hover,#primaryButton:hover { background:#0D47A1; }
.secondaryButton {
    background:white; color:#1565C0; border:1px solid #B8CCE2;
    border-radius:12px; font-size:14px; font-weight:600; padding:10px;
}
.navButton {
    background:transparent; border:none; border-radius:10px; padding:6px 10px;
    color:#52606D; font-size:12px; font-weight:600;
}
.navButton:hover { background:#EAF2FB; color:#1565C0; }
QLineEdit,QComboBox,QTableWidget,QSpinBox {
    background:white; border:1px solid #D8DEE6; border-radius:8px; padding:8px;
    font-size:14px;
}
QHeaderView::section {
    background:#EEF3F8; border:none; padding:8px; font-weight:600;
}
QPushButton { cursor:pointer; min-height:32px; }
QPushButton[class="secondaryButton"] {
    min-height:30px;
    padding:4px 8px;
    border-radius:8px;
}
QPushButton[class="primaryButton"] {
    min-height:32px;
    padding:8px 14px;
    border-radius:10px;
}
QToolTip {
    background-color: #FFFFFF;
    color: #0F172A;
    border: 1px solid #CBD5E1;
    border-radius: 10px;
    padding: 8px 10px;
    font-size: 12px;
}
"""

def now_jalali():
    n=datetime.now(); y,m,d=gregorian_to_jalali(n.year,n.month,n.day)
    return f"{y:04d}/{m:02d}/{d:02d}", n.strftime("%H:%M:%S")

PERSIAN_WEEKDAYS = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]

def jalali_day_name(gy, gm, gd):
    """نام روز هفته به فارسی از تاریخ میلادی"""
    wd = datetime(gy, gm, gd).weekday()  # 0=Mon ... 6=Sun
    return PERSIAN_WEEKDAYS[wd]

_CUSTOMER_COLOR_CACHE = {}

_CUSTOMER_COLOR_YEAR = None

def _lerp(a, b, t):
    return int(a + (b - a) * t)

def spectrum_color_from_t(t: float) -> str:
    """t از 0 (قرمز) تا 1 (سبز پررنگ) — فاصله رنگی زیاد روی طیف"""
    t = max(0.0, min(1.0, float(t)))
    # سه نقطه قوی: قرمز → زرد طلایی → سبز
    if t >= 0.5:
        u = (t - 0.5) * 2
        r = _lerp(250, 5, u)      # زرد → سبز تیره
        g = _lerp(204, 140, u)
        b = _lerp(20, 50, u)
    else:
        u = t * 2
        r = _lerp(200, 250, u)    # قرمز → زرد
        g = _lerp(30, 204, u)
        b = _lerp(30, 20, u)
    # کمی روشن فقط برای خوانایی، بدون نزدیک کردن رنگ‌ها به هم
    r = min(255, r + 18)
    g = min(255, g + 18)
    b = min(255, b + 18)
    return f"#{r:02X}{g:02X}{b:02X}"

def rebuild_customer_colors():
    if uit is not None:
        try: uit.invalidate_customer_cache()
        except Exception: _swallow()
    """رنگ‌ها بر اساس فروش سال جاری؛ رتبه‌بندی یکنواخت روی طیف برای فاصله بیشتر بین رنگ‌ها"""
    global _CUSTOMER_COLOR_CACHE, _CUSTOMER_COLOR_YEAR
    gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    _CUSTOMER_COLOR_YEAR = jy
    c = db()
    rows = c.execute(
        "SELECT customer, COALESCE(SUM(CAST(total AS INTEGER)),0) "
        "FROM invoices WHERE substr(date,1,4)=? GROUP BY customer",
        (f"{jy:04d}",)
    ).fetchall()
    c.close()
    sales_map = {}
    for name, total in rows:
        if not name or not str(name).strip():
            continue
        sales_map[str(name).strip()] = int(total or 0)

    # کم‌فروش → rank پایین (قرمز)، پرفروش → rank بالا (سبز)
    ranked = sorted(sales_map.items(), key=lambda x: (x[1], x[0]))
    n_pos = sum(1 for _, v in ranked if v > 0)
    used = set()
    cache = {}
    rank = 0
    for name, sales in ranked:
        if sales <= 0:
            col = "#D1D5DB"
        else:
            if n_pos <= 1:
                t = 1.0
            else:
                # توزیع یکنواخت روی کل طیف = بیشترین فاصله بین رنگ‌ها
                t = rank / (n_pos - 1)
            col = spectrum_color_from_t(t)
            rank += 1
            base = col
            n = 0
            while col in used:
                n += 1
                r = int(base[1:3], 16)
                g = int(base[3:5], 16)
                b = min(255, int(base[5:7], 16) + n)
                col = f"#{r:02X}{g:02X}{b:02X}"
            used.add(col)
        cache[name] = col
    _CUSTOMER_COLOR_CACHE = cache
    return cache

def get_customer_color(name: str) -> str:
    if uit is not None:
        try:
            return uit.cache_get_color(name, _get_customer_color_uncached)
        except Exception:
            _swallow()
    return _get_customer_color_uncached(name)

def _get_customer_color_uncached(name: str) -> str:
    """رنگ مشتری بر اساس فروش سال جاری (کش‌شده)"""
    if not name or not str(name).strip():
        return "#FFFFFF"
    name = str(name).strip()
    gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
    jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
    if not _CUSTOMER_COLOR_CACHE or _CUSTOMER_COLOR_YEAR != jy:
        rebuild_customer_colors()
    return _CUSTOMER_COLOR_CACHE.get(name, "#D1D5DB")

def settings():
    default={"company_name":"SalesMate","currency":"ریال","supabase_enabled":True,"backup_on_close":True,"supabase_url":"https://sowftowkhvuvaijttpiv.supabase.co","supabase_key":"sb_publishable_5BrCyhkBlDQqbdjkGnEK1w_zpsHiAs8"}
    if SETTINGS_PATH.exists():
        try:
            default.update(json.loads(SETTINGS_PATH.read_text(encoding="utf-8")))
        except Exception: _swallow()
    return default

def save_settings(s):
    SETTINGS_PATH.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding="utf-8")

def db():
    c=sqlite3.connect(DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS invoices(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL, invoice_no TEXT NOT NULL,
        date TEXT NOT NULL, time TEXT NOT NULL,
        total TEXT NOT NULL, created_at TEXT NOT NULL,
        image_path TEXT DEFAULT ""
    )""")
    # Upgrade databases created by older SalesMate versions.
    cols = [r[1] for r in c.execute("PRAGMA table_info(invoices)").fetchall()]
    if "image_path" not in cols:
        c.execute('ALTER TABLE invoices ADD COLUMN image_path TEXT DEFAULT ""')
    if "inquiry_data" not in cols:
        c.execute('ALTER TABLE invoices ADD COLUMN inquiry_data TEXT DEFAULT ""')
    if "paid_amount" not in cols:
        c.execute('ALTER TABLE invoices ADD COLUMN paid_amount TEXT DEFAULT ""')
    c.execute("""CREATE TABLE IF NOT EXISTS customer_balance_adj(
        customer TEXT PRIMARY KEY,
        adjustment TEXT NOT NULL DEFAULT '0',
        note TEXT DEFAULT '',
        updated_at TEXT DEFAULT ''
    )""")
    # فروشگاه — جدا از حواله‌ها و آمار اصلی
    c.execute("""CREATE TABLE IF NOT EXISTS store_sales(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer TEXT NOT NULL,
        invoice_no TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        total TEXT NOT NULL,
        tab TEXT DEFAULT 'parquet',
        items_json TEXT DEFAULT '[]',
        created_at TEXT NOT NULL
    )""")
    c.commit()
    try:
        if c.execute("PRAGMA user_version").fetchone()[0] < 1:
            migrate_money_v1(c, DB_PATH, BACKUP_DIR)
    except Exception:
        _swallow()
    try:
        if c.execute("PRAGMA user_version").fetchone()[0] < 2:
            if migrate_jenagi_v2(c, DB_PATH, BACKUP_DIR):
                try:
                    mark_local_dirty()
                except Exception:
                    _swallow()
    except Exception:
        _swallow()
    return c

def customer_balance(customer: str) -> int:
    """مانده = (جمع کل - جمع پرداختی حواله‌ها) + تعدیل دستی.
    مثبت = بدهکار، منفی = طلبکار
    """
    if not customer:
        return 0
    c = db()
    try:
        rows = c.execute(
            "SELECT total, paid_amount FROM invoices WHERE customer=?",
            (customer,),
        ).fetchall()
        bal = 0
        for total, paid in rows:
            t = amount(total)
            if paid is None or str(paid).strip() == "":
                p = t
            else:
                p = amount(paid)
            bal += t - p
        adj = c.execute(
            "SELECT adjustment FROM customer_balance_adj WHERE customer=?",
            (customer,),
        ).fetchone()
        if adj:
            bal += amount(adj[0])
        return bal
    finally:
        c.close()

def renumber_invoices_by_date():
    """شناسه‌ها را بر اساس تاریخ از قدیم به جدید از ۱ شماره می‌زند؛ جدیدترین = بزرگ‌ترین شناسه"""
    c = sqlite3.connect(DB_PATH)
    try:
        rows = c.execute(
            "SELECT id FROM invoices ORDER BY date ASC, time ASC, id ASC"
        ).fetchall()
        if not rows:
            c.close()
            return
        old_ids = [r[0] for r in rows]
        n = len(old_ids)
        # اگر از قبل مرتب و پشت‌سرهم ۱..n است، کاری نکن
        if old_ids == list(range(1, n + 1)):
            c.close()
            return
        # انتقال موقت برای جلوگیری از تداخل PRIMARY KEY
        offset = 10_000_000
        c.execute("UPDATE invoices SET id = id + ?", (offset,))
        for new_id, old_id in enumerate(old_ids, 1):
            c.execute(
                "UPDATE invoices SET id = ? WHERE id = ?",
                (new_id, old_id + offset),
            )
        # ریست کردن شمارنده AUTOINCREMENT
        c.execute("DELETE FROM sqlite_sequence WHERE name='invoices'")
        try:
            c.execute(
                "INSERT INTO sqlite_sequence(name, seq) VALUES('invoices', ?)",
                (n,),
            )
        except Exception:
            _swallow()
        c.commit()
    finally:
        c.close()

def parse_version_tuple(v):
    """1.90.0 یا 1.90 یا v1.90.0 → (1,90,0)"""
    s = str(v or "").strip().lstrip("vV")
    parts = []
    for p in s.replace("-", ".").split("."):
        try:
            parts.append(int("".join(ch for ch in p if ch.isdigit()) or "0"))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:4])

def is_remote_newer(local_ver, remote_ver):
    return parse_version_tuple(remote_ver) > parse_version_tuple(local_ver)

def github_repo_slug():
    s = settings()
    repo = (s.get("github_repo") or DEFAULT_GITHUB_REPO).strip()
    repo = repo.replace("https://github.com/", "").replace("http://github.com/", "").strip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo or DEFAULT_GITHUB_REPO

def update_check_url():
    s = settings()
    return (s.get("update_url") or DEFAULT_UPDATE_URL).strip()

def _ssl_contexts():
    """اول SSL عادی، اگر در شبکه ایران/آنتی‌ویروس خطا داد بدون verify."""
    import ssl
    contexts = []
    try:
        contexts.append(ssl.create_default_context())
    except Exception:
        _swallow()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
        contexts.append(ctx)
    except Exception:
        _swallow()
    try:
        contexts.append(ssl._create_unverified_context())
    except Exception:
        _swallow()
    # یکتا نگه دار
    out = []
    for c in contexts:
        if c not in out:
            out.append(c)
    return out or [None]

def _urlopen_resilient(req, timeout=30):
    """urlopen با تحمل خطای SSL (رایج در ایران)."""
    import urllib.request
    import ssl
    last_err = None
    for ctx in _ssl_contexts():
        try:
            if ctx is None:
                return urllib.request.urlopen(req, timeout=timeout)
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            # فقط برای SSL دوباره تلاش کن؛ بقیه را همان‌جا بالا بده
            if "ssl" in msg or "certificate" in msg or "cert" in msg:
                continue
            raise
    raise last_err if last_err else RuntimeError("اتصال برقرار نشد")

def _http_json(url, timeout=12):
    import urllib.request
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SalesMate-Windows/" + APP_VERSION,
            "Accept": "application/vnd.github+json",
            "Cache-Control": "no-cache",
        },
    )
    with _urlopen_resilient(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)

def fetch_from_github_releases(timeout=12):
    """آخرین Release را از GitHub می‌گیرد — لینک دانلود خودکار.
    ترجیح: zip کامل (dist/سورس) بعد exe تنها.
    فقط فایل SalesMate.exe کافی نیست اگر Build از نوع onedir باشد.
    """
    repo = github_repo_slug()
    data = _http_json("https://api.github.com/repos/%s/releases/latest" % repo, timeout=timeout)
    tag = str(data.get("tag_name") or data.get("name") or "").strip()
    ver = tag.lstrip("vV")
    if not ver:
        raise RuntimeError("در آخرین Release تگ نسخه نیست.")
    assets = data.get("assets") or []
    # امتیازدهی به دارایی‌ها
    scored = []
    patch_url = ""
    for a in assets:
        name = str(a.get("name") or "")
        url = a.get("browser_download_url") or ""
        if not url:
            continue
        nl = name.lower()
        size = int(a.get("size") or 0)
        if nl.startswith("salesmate_code_") and nl.endswith(".zip"):
            patch_url = url      # آپدیت سبک (فقط کد برنامه)
            continue
        score = 0
        frozen = bool(getattr(sys, "frozen", False))
        try:
            onedir = frozen and (Path(sys.executable).resolve().parent / "_internal").is_dir()
        except Exception:
            onedir = False
        if nl.endswith(".exe"):
            # ساخت پوشه‌ای (onedir): فقط exe کافی نیست؛ zip کامل اولویت دارد
            score += (-60 if onedir else (120 if frozen else 50))
            if "salesmate" in nl:
                score += 40
            if ver and ver in nl:
                score += 30
            if size > 20_000_000:
                score += 25
        elif nl.endswith(".zip"):
            score += 160 if onedir else (80 if not frozen else 40)
            if "salesmate" in nl:
                score += 40
            if "dist" in nl or "pc" in nl:
                score += 30
            if ver and ver in nl:
                score += 30
            if size > 5_000_000:
                score += 20
            # سورس خیلی کوچک را پایین بیاور
            if size < 500_000:
                score -= 50
        else:
            score += 5
        scored.append((score, size, name, url))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    download_url = ""
    asset_name = ""
    if scored:
        _, _, asset_name, download_url = scored[0]
    if not download_url and not patch_url:
        raise RuntimeError(
            "در آخرین Release فایل exe یا zip پیدا نشد.\n"
            "یک Release بسازید و zip کامل dist یا SalesMate.exe را Attach کنید."
        )
    return {
        "version": ver,
        "download_url": download_url,
        "asset_name": asset_name,
        "patch_url": patch_url,
        "notes": (data.get("body") or data.get("name") or "").strip()[:300],
        "source": "github-releases",
        "repo": repo,
        "tag": tag,
    }

def is_mdf_invoice(inquiry_data):
    """حواله‌ی ام دی اف/خام؟ از تب استعلام، یا (برای حواله‌ی اکسل) از نام کالاها."""
    try:
        d = json.loads(inquiry_data) if isinstance(inquiry_data, str) else (inquiry_data or {})
    except Exception:
        return False
    if not isinstance(d, dict):
        return False
    tab = d.get("tab")
    if tab in ("mdf", "raw"):
        return True
    if tab == "parquet":
        return False
    names = " ".join(str((r or {}).get("name") or (r or {}).get("type") or "") for r in (d.get("rows") or [])).lower()
    if not names or "پارکت" in names:
        return False
    return any(k in names for k in ("ام دی اف", "ام‌دی‌اف", "mdf", "هایگلاس", "ملامینه", "خام"))

def bundle_version():
    """نسخه‌ی کتابخانه‌ها/exe نصب‌شده (نه لزوماً نسخه‌ی کدی که الان اجرا می‌شود)."""
    return os.environ.get("SALESMATE_BUNDLE_VERSION") or APP_VERSION

CODE_DIR = APP_DIR / "code"

def apply_code_patch(url, ver, progress_cb=None):
    """دانلود و نصب آپدیت سبک (zip چند صد کیلوبایتی از فایل‌های .py).
    بعد از آن باید برنامه بسته و دوباره باز شود. خطا → Exception با پیام فارسی."""
    import zipfile, shutil as _sh
    CODE_DIR.mkdir(parents=True, exist_ok=True)
    dl = CODE_DIR / "_download.zip"
    download_update_zip(url, dl, progress_cb=progress_cb)
    try:
        with zipfile.ZipFile(dl) as z:
            names = z.namelist()
            if "main.py" not in names or "patch.json" not in names:
                raise RuntimeError("بستهٔ آپدیت نامعتبر است.")
            pj = json.loads(z.read("patch.json").decode("utf-8"))
            pver = str(pj.get("version") or ver)
            if parse_version_tuple(pj.get("min_bundle", "0")) > parse_version_tuple(bundle_version()):
                raise RuntimeError(
                    "این نسخه به نصب کامل نیاز دارد (کتابخانه‌ها تغییر کرده‌اند).\n"
                    "نسخه‌ی کامل را از صاحب برنامه بگیرید.")
            tmp = CODE_DIR / ("v" + pver + ".tmp")
            final = CODE_DIR / ("v" + pver)
            if tmp.exists():
                _sh.rmtree(tmp, ignore_errors=True)
            tmp.mkdir(parents=True)
            for n in names:
                base = os.path.basename(n)
                if n != base or not (base.endswith(".py") or base == "patch.json"):
                    continue          # فقط فایل‌های ساده‌ی .py و patch.json
                (tmp / base).write_bytes(z.read(n))
        if final.exists():
            _sh.rmtree(final, ignore_errors=True)
        tmp.rename(final)
        (CODE_DIR / "current.json").write_text(
            json.dumps({"version": pver, "dir": "v" + pver}), encoding="utf-8")
        # فقط دو نسخه‌ی آخر را نگه دار
        olds = sorted([p for p in CODE_DIR.glob("v*") if p.is_dir() and p.name != final.name],
                      key=lambda p: parse_version_tuple(p.name.lstrip("v")), reverse=True)
        for p in olds[1:]:
            _sh.rmtree(p, ignore_errors=True)
        return pver
    finally:
        try:
            dl.unlink()
        except Exception:
            pass

def restart_app():
    """برنامه را دوباره اجرا می‌کند (بعد از آپدیت سبک)."""
    import subprocess
    try:
        env = dict(os.environ)
        env.pop("SALESMATE_OVERLAY_ACTIVE", None)   # وگرنه برنامه‌ی جدید کد آپدیت را نادیده می‌گیرد
        if getattr(sys, "frozen", False):
            subprocess.Popen([sys.executable], cwd=str(APP_DIR), env=env)
        else:
            subprocess.Popen([sys.executable] + sys.argv, cwd=str(APP_DIR), env=env)
    except Exception:
        _swallow()

def fetch_code_patch_branch(timeout=12):
    """آپدیت سبک از شاخه‌ی windows-update ریپو (version.json + SalesMate_code.zip کوچک)."""
    repo = github_repo_slug()
    base = "https://raw.githubusercontent.com/%s/windows-update/" % repo
    data = _http_json(base + "version.json", timeout=timeout)
    ver = str(data.get("version") or "").strip()
    if not ver:
        raise RuntimeError("version.json شاخه‌ی windows-update نامعتبر است.")
    return {
        "version": ver,
        "download_url": "",
        "patch_url": base + str(data.get("file") or "SalesMate_code.zip"),
        "asset_name": str(data.get("file") or "SalesMate_code.zip"),
        "notes": str(data.get("notes") or "")[:300],
        "source": "windows-update-branch",
        "repo": repo,
    }

def fetch_remote_version_info(timeout=12):
    """اول شاخه‌ی windows-update (آپدیت سبک)، بعد GitHub Releases، بعد version.json اختیاری."""
    errors = []
    try:
        return fetch_code_patch_branch(timeout=timeout)
    except Exception as e:
        errors.append("windows-update: " + str(e))
    try:
        return fetch_from_github_releases(timeout=timeout)
    except Exception as e:
        errors.append("Releases: " + str(e))
    # fallback: version.json دستی (اختیاری)
    url = update_check_url()
    if url:
        try:
            data = _http_json(url, timeout=timeout)
            if not isinstance(data, dict) or not data.get("version"):
                raise RuntimeError("version.json نامعتبر")
            data.setdefault("source", "version.json")
            return data
        except Exception as e:
            errors.append("version.json: " + str(e))
    raise RuntimeError("بررسی نسخه ناموفق:\n- " + "\n- ".join(errors))

_last_cloud_local_backup_at = 0.0

_CLOUD_LOCAL_BACKUP_MIN_SEC = 8  # حداقل فاصله بین بکاپ‌های چرخشی (ثانیه) — بعد از هر تغییر

def rotate_cloud_local_backup(max_keep=5, force=False):
    """بکاپ محلی سبک بعد از ارسال ابر — حداکثر ۵ فایل (قدیمی‌ها حذف).
    در پس‌زمینه صدا زده شود تا UI نلرزد.
    """
    global _last_cloud_local_backup_at
    import zipfile
    now = time.time()
    if not force and _last_cloud_local_backup_at and (now - _last_cloud_local_backup_at) < _CLOUD_LOCAL_BACKUP_MIN_SEC:
        return None
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = BACKUP_DIR / ("cloud_sync_" + stamp + ".zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for name in (
                "salesmate.db",
                "settings.json",
                "inventory.json",
                "inventory_balance.json",
                "calc_customers.json",
                "inquiries.json",
                "supabase_session.json",
            ):
                p = APP_DIR / name
                if p.exists() and p.is_file():
                    try:
                        z.write(p, name)
                    except Exception:
                        _swallow()
            # چند عکس اخیر را نه — برای سرعت؛ فقط متا
            meta = {
                "type": "cloud_sync_backup",
                "app_version": APP_VERSION,
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            z.writestr("backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        # چرخش: فقط cloud_sync_*.zip
        files = sorted(
            BACKUP_DIR.glob("cloud_sync_*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in files[max_keep:]:
            try:
                old.unlink()
            except Exception:
                _swallow()
        _last_cloud_local_backup_at = now
        return path
    except Exception:
        return None

def schedule_cloud_local_backup(force=False):
    """اجرای بکاپ چرخشی در thread جدا"""
    def _w():
        try:
            rotate_cloud_local_backup(max_keep=5, force=force)
        except Exception:
            _swallow()
    try:
        threading.Thread(target=_w, daemon=True).start()
    except Exception:
        try:
            rotate_cloud_local_backup(max_keep=5, force=force)
        except Exception:
            _swallow()

def create_full_local_backup():
    """پشتیبان کامل محلی از همه چیز قبل از آپدیت"""
    import zipfile
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = BACKUP_DIR / ("SalesMate_FullBackup_" + stamp + ".zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        # دیتابیس و تنظیمات
        for name in (
            "salesmate.db",
            "salesmate_autosave.db",
            "settings.json",
            "inventory.json",
            "inventory_balance.json",
            "calc_customers.json",
            "inquiries.json",
            "supabase_session.json",
        ):
            p = APP_DIR / name
            if p.exists() and p.is_file():
                z.write(p, name)
        # بک‌آپ‌های db قبلی
        for p in APP_DIR.glob("salesmate_backup_*.db"):
            try:
                z.write(p, p.name)
            except Exception:
                _swallow()
        # پیوست‌ها
        if ATTACHMENTS_DIR.exists():
            for p in ATTACHMENTS_DIR.rglob("*"):
                if p.is_file():
                    try:
                        z.write(p, "attachments/" + str(p.relative_to(ATTACHMENTS_DIR)).replace("\\\\", "/"))
                    except Exception:
                        _swallow()
        # متا
        meta = {
            "app_version": APP_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "app_dir": str(APP_DIR),
        }
        z.writestr("backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
    return path

def download_update_zip(url, dest: Path, progress_cb=None):
    import urllib.request
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "SalesMate-Windows/" + APP_VERSION})
    with _urlopen_resilient(req, timeout=180) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress_cb and total:
                    progress_cb(done, total)
    return dest

_UPDATE_PRESERVE = {
    "salesmate.db", "salesmate_autosave.db", "settings.json", "inventory.json", "inventory_balance.json", "calc_customers.json",
    "inquiries.json", "supabase_session.json", "mobile_snap_state.json",
}

def _write_updater_script(download_path: Path):
    """اسکریپت نصب آپدیت — برای exe قفل‌شده چندبار تلاش می‌کند تا جایگزین شود."""
    upd_dir = APP_DIR / "_update_work"
    upd_dir.mkdir(parents=True, exist_ok=True)
    bat_path = upd_dir / "apply_update.bat"
    log_path = upd_dir / "update_log.txt"
    extract_dir = upd_dir / "extracted"
    is_exe = download_path.suffix.lower() == ".exe"
    pid = os.getpid()

    def W(p):
        return str(Path(p).resolve())

    if getattr(sys, "frozen", False):
        app_exe = W(sys.executable)
        exe_target = app_exe
        app_dir = str(Path(sys.executable).resolve().parent)
    else:
        app_dir = W(APP_DIR)
        if (APP_DIR / "SalesMate.exe").exists():
            app_exe = W(APP_DIR / "SalesMate.exe")
            exe_target = app_exe
        elif (APP_DIR / "run.bat").exists():
            app_exe = W(APP_DIR / "run.bat")
            exe_target = W(APP_DIR / "SalesMate.exe")
        else:
            app_exe = W(APP_DIR / "salesmate" / "main.py")
            exe_target = W(APP_DIR / "SalesMate.exe")

    new_file = W(download_path)
    nl = "\r\n"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        "setlocal EnableExtensions",
        'set LOG="' + W(log_path) + '"',
        "echo === SalesMate update start ===> %LOG%",
        "echo PID was " + str(pid) + ">> %LOG%",
        "echo target=" + exe_target + ">> %LOG%",
        "echo newfile=" + new_file + ">> %LOG%",
        # صبر تا پروسه اصلی بمیرد
        "timeout /t 3 /nobreak >nul",
        ":waitpid",
        'tasklist /FI "PID eq ' + str(pid) + '" 2>nul | find "' + str(pid) + '" >nul',
        "if not errorlevel 1 (",
        "  echo still running>> %LOG%",
        "  timeout /t 2 /nobreak >nul",
        "  goto waitpid",
        ")",
        "echo process gone>> %LOG%",
        "timeout /t 2 /nobreak >nul",
    ]

    if is_exe:
        # جایگزین exe با تلاش مکرر (فایل قفل‌شده)
        lines += [
            "echo replacing exe>> %LOG%",
            "set TRY=0",
            ":retry_exe",
            "set /a TRY+=1",
            "echo try %TRY%>> %LOG%",
            'if exist "' + exe_target + '.old" del /f /q "' + exe_target + '.old" >nul 2>&1',
            'if exist "' + exe_target + '" (',
            '  ren "' + exe_target + '" "SalesMate.exe.old" >> %LOG% 2>&1',
            "  if errorlevel 1 (",
            "    echo rename failed>> %LOG%",
            "    if %TRY% LSS 15 (",
            "      timeout /t 2 /nobreak >nul",
            "      goto retry_exe",
            "    )",
            "  )",
            ")",
            'copy /Y "' + new_file + '" "' + exe_target + '" >> %LOG% 2>&1',
            "if errorlevel 1 (",
            "  echo copy failed>> %LOG%",
            "  if %TRY% LSS 15 (",
            "    timeout /t 2 /nobreak >nul",
            "    goto retry_exe",
            "  )",
            "  echo GIVING UP>> %LOG%",
            "  goto open_folder",
            ")",
            "echo copy ok>> %LOG%",
            'if exist "' + exe_target + '.old" del /f /q "' + exe_target + '.old" >nul 2>&1',
            'if exist "' + str(Path(exe_target).parent / "SalesMate.exe.old") + '" del /f /q "' + str(Path(exe_target).parent / "SalesMate.exe.old") + '" >nul 2>&1',
            # تأیید حجم فایل
            'for %%A in ("' + exe_target + '") do echo size=%%~zA>> %LOG%',
            "goto launch",
        ]
    else:
        ps1 = upd_dir / "apply_update.ps1"
        preserve_ps = ", ".join("'" + x + "'" for x in sorted(_UPDATE_PRESERVE))
        ps_lines = [
            "$ErrorActionPreference='Continue'",
            "$log='" + W(log_path).replace("'", "''") + "'",
            "$srcZip='" + W(download_path).replace("'", "''") + "'",
            "$extract='" + W(extract_dir).replace("'", "''") + "'",
            "$dst='" + app_dir.replace("'", "''") + "'",
            "$preserve=@(" + preserve_ps + ")",
            "Add-Content -Path $log -Value 'extract zip'",
            "if (Test-Path $extract) { Remove-Item -LiteralPath $extract -Recurse -Force }",
            "New-Item -ItemType Directory -Path $extract | Out-Null",
            "Expand-Archive -LiteralPath $srcZip -DestinationPath $extract -Force",
            "$root=$extract",
            "$kids=@(Get-ChildItem -LiteralPath $extract -Force)",
            "if ($kids.Count -eq 1 -and $kids[0].PSIsContainer) { $root=$kids[0].FullName }",
            # اگر داخل zip فقط SalesMate.exe بود
            "if (Test-Path (Join-Path $root 'SalesMate.exe')) {",
            "  $exeDst = Join-Path $dst 'SalesMate.exe'",
            "  Copy-Item -LiteralPath (Join-Path $root 'SalesMate.exe') -Destination $exeDst -Force",
            "  Add-Content $log 'copied SalesMate.exe from zip'",
            "}",
            "function Copy-Tree([string]$from,[string]$to) {",
            "  Get-ChildItem -LiteralPath $from -Force | ForEach-Object {",
            "    $name=$_.Name",
            "    if ($preserve -contains $name) { Add-Content $log ('skip '+$name); return }",
            "    if ($name -in @('backups','attachments','_update_work')) { return }",
            "    $target=Join-Path $to $name",
            "    if ($_.PSIsContainer) {",
            "      if (-not (Test-Path -LiteralPath $target)) { New-Item -ItemType Directory -Path $target | Out-Null }",
            "      Copy-Tree $_.FullName $target",
            "    } else {",
            "      Copy-Item -LiteralPath $_.FullName -Destination $target -Force",
            "      Add-Content $log ('copied '+$name)",
            "    }",
            "  }",
            "}",
            "Copy-Tree $root $dst",
            "Add-Content $log 'copy done'",
        ]
        ps1.write_text("\n".join(ps_lines) + "\n", encoding="utf-8")
        lines += [
            "echo unzip>> %LOG%",
            'powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + W(ps1) + '" >> %LOG% 2>&1',
            "goto launch",
        ]

    lines += [
        ":launch",
        "echo launching>> %LOG%",
        "timeout /t 1 /nobreak >nul",
        # explorer = دابل‌کلیک واقعی؛ خطای parent process نمی‌دهد
        'explorer.exe "' + app_exe + '"',
        "timeout /t 2 /nobreak >nul",
        # اگر باز نشد یک‌بار دیگر با start
        'start "" /D "' + app_dir + '" "' + app_exe + '"',
        "echo done>> %LOG%",
        "goto end",
        ":open_folder",
        'explorer.exe "' + app_dir + '"',
        "echo opened folder after failure>> %LOG%",
        ":end",
        "endlocal",
    ]
    bat_path.write_text(nl.join(lines) + nl, encoding="utf-8")

    # VBS مخفی بدون پنجره سیاه
    vbs_path = upd_dir / "apply_update.vbs"
    bat_s = W(bat_path).replace("\\", "\\\\")
    vbs = (
        'On Error Resume Next\r\n'
        'Set sh = CreateObject("WScript.Shell")\r\n'
        'sh.CurrentDirectory = "' + app_dir.replace("\\", "\\\\") + '"\r\n'
        'sh.Run "cmd.exe /c """"' + W(bat_path).replace('"', '""') + '""""", 0, False\r\n'
    )
    vbs_path.write_text(vbs, encoding="ascii", errors="replace")
    return vbs_path

def launch_updater_and_exit(script_path: Path):
    """نصب‌کننده را اجرا کن و فوراً process را بکش (بدون QTimer تا هنگ نشود)."""
    import subprocess
    script = str(Path(script_path).resolve())
    flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED | NEW_GROUP | NO_WINDOW
    try:
        if script.lower().endswith(".vbs"):
            subprocess.Popen(
                ["wscript.exe", "//B", "//Nologo", script],
                cwd=str(APP_DIR),
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                ["cmd.exe", "/c", script],
                cwd=str(APP_DIR),
                creationflags=flags,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
    except Exception as e:
        try:
            os.startfile(script)  # type: ignore
        except Exception:
            raise RuntimeError("اجرای آپدیت ممکن نشد: " + str(e))
    # خروج فوری — UI دیگر اجرا نمی‌شود
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        _swallow()
    os._exit(0)

PRODUCT_FACTORS = {
    "Isofam Luxury": 1.9608,
    "Charlotte": 2.0066,
    "Valente": 1.9608,
    "Egmont": 1.8696,       # متراژ قدیمی
    "N Egmont": 1.9608,     # متراژ جدید
    "New Way": 1.9608,
}

PRODUCT_OPTIONS = list(PRODUCT_FACTORS.keys())

def resolve_product(code="", name=""):
    """نوع محصول پارکت از کد، و اگر نشد از روی نام کالا (جناغی ← Charlotte = ۲٫۰۰۶۶).
    اگر تشخیص داده نشد رشته‌ی خالی برمی‌گرداند."""
    try:
        key = "".join(ch for ch in str(code or "") if ch.isdigit())
        if key in CODE_TO_PRODUCT:
            return CODE_TO_PRODUCT[key]
        nm = str(name or "")
        if nm.strip() in PRODUCT_FACTORS:
            return nm.strip()
        if "جناغی" in nm or "جناقی" in nm:
            return "Charlotte"
    except Exception:
        pass
    return ""

EGMONT_OPTIONS = ["Egmont", "N Egmont"]

GRADE_OPTIONS = ["GA", "GB", "GC"]

CODE_TO_PRODUCT = {}

for _code in [
    "1122", "1123", "1124", "1132", "1133", "1134", "1144", "1145", "1154", "1163",
    "1234", "2113", "2122", "2123", "2124", "2132", "2135", "2137", "2162", "2164",
    "2254", "2255", "2133", "2223", "2120", "2125", "2126", "2253", "2117", "2138",
    "2248", "2252", "2166", "2273", "2275", "2276", "2274", "2142", "2136", "2144",
    "2486", "2118", "2453", "2474", "22530", "2114", "2468", "2111", "2465", "246",
    "2463", "2112", "2104", "2222", "2134", "2476",
]:
    CODE_TO_PRODUCT[_code] = "Isofam Luxury"

for _code in ["6542", "6332", "6234", "6223", "6224", "6435", "6545", "6433", "6235"]:
    CODE_TO_PRODUCT[_code] = "Charlotte"

for _code in ["7414", "7323", "7322", "7335", "7434", "7524", "7634", "7343", "7465"]:
    CODE_TO_PRODUCT[_code] = "Valente"

for _code in ["443", "126", "444", "452", "442", "456", "114", "453"]:
    CODE_TO_PRODUCT[_code] = "Egmont"

for _code in ["9015", "9010", "9025", "9020", "9072", "9052", "9055", "9059", "9040", "9050"]:
    CODE_TO_PRODUCT[_code] = "New Way"

INQUIRY_PATH = APP_DIR / "inquiries.json"

CONTACTS_PATH = APP_DIR / "customer_contacts.json"

def number_to_persian_words(num):
    try:
        num = int(abs(round(float(num))))
    except Exception:
        return ""
    if num == 0:
        return "صفر"
    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    teens = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
    tens = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    hundreds = ["", "یکصد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]
    scales = ["", "هزار", "میلیون", "میلیارد", "تریلیون"]

    def three(n):
        h, t, o = n // 100, (n % 100) // 10, n % 10
        parts = []
        if h:
            parts.append(hundreds[h])
        if t == 1:
            parts.append(teens[o])
        else:
            if t:
                parts.append(tens[t])
            if o:
                parts.append(ones[o])
        return " و ".join(parts)

    parts, idx = [], 0
    while num > 0 and idx < len(scales):
        chunk = num % 1000
        if chunk:
            s = three(chunk)
            if scales[idx]:
                s += " " + scales[idx]
            parts.insert(0, s)
        num //= 1000
        idx += 1
    return " و ".join(parts)

def _abbr_amount(v):
    """مبلغ کوتاه‌شده برای روی نمودار: ۱٫۲ میلیارد / ۴۵۰ میلیون / ۱۲٬۰۰۰"""
    try:
        v = float(v)
    except Exception:
        v = 0.0
    neg = "-" if v < 0 else ""
    a = abs(v)
    if a >= 1e9:
        t = ("%.2f" % (a / 1e9)).rstrip("0").rstrip(".") + " میلیارد"
    elif a >= 1e6:
        t = ("%.1f" % (a / 1e6)).rstrip("0").rstrip(".") + " میلیون"
    else:
        t = fmt(int(a))
    return neg + fa_digits(t.replace(".", "٫"))

def _top10_tooltip_html(title, rows):
    """tooltip ۱۰ خریدار برتر: rows = [(name, amount, meters)]"""
    import html as _html
    out = ["<div dir='rtl' style='text-align:right;'><b>", _html.escape(str(title)), "</b>"]
    if not rows:
        out.append("<br>خریداری ثبت نشده")
    else:
        out.append("<table cellspacing='3' dir='rtl'>")
        for i, (name, amt, met) in enumerate(rows, 1):
            out.append(
                "<tr><td>%s.</td><td><b>%s</b></td><td>%s ریال</td><td>%s متر</td></tr>" % (
                    fa_digits(i), _html.escape(str(name)), fa_digits(fmt(int(amt))),
                    fa_digits(("%g" % round(float(met), 2)) if met else "0"))
            )
        out.append("</table>")
    out.append("</div>")
    return "".join(out)

def _ago_fa(ts):
    try:
        if not ts:
            return "—"
        d = int(time.time() - float(ts))
        if d < 60:
            return "چند ثانیه پیش"
        if d < 3600:
            return fa_digits(d // 60) + " دقیقه پیش"
        if d < 86400:
            return fa_digits(d // 3600) + " ساعت پیش"
        return fa_digits(d // 86400) + " روز پیش"
    except Exception:
        return "—"

_cloud_ui_window = None   # پنجره‌ی اصلی (توسط MainWindow مقدار می‌گیرد)
