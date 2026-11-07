
import sys, sqlite3, shutil, json, os, re, webbrowser, tempfile, threading, time
from pathlib import Path

# ── آپدیت سبک: اگر کد جدیدتری در پوشه‌ی code کنار exe باشد، آن اجرا می‌شود ──
if getattr(sys, "frozen", False) and __name__ == "__main__":
    try:
        import app_version as _av
        _bundle_ver = _av.APP_VERSION
        os.environ["SALESMATE_BUNDLE_VERSION"] = _bundle_ver
        sys.modules.pop("app_version", None)
        import code_overlay as _co
        _co.try_run_overlay(_bundle_ver)
    except SystemExit:
        raise
    except Exception:
        pass


# ───────────────────── صفحه‌ی بارگذاری (اسپلش) + زمان‌سنجی راه‌اندازی ─────────────────────
# همان لحظه‌ی اجرا، قبل از واردکردن کتابخانه‌های سنگین، یک پنجره‌ی کوچک با نوار ۰ تا ۱۰۰٪ باز می‌شود.
_BOOT_T0 = time.perf_counter()
_BOOT = {"win": None, "bar": None, "lbl": None, "marks": [], "app": None}


def _boot_dir():
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).resolve().parent
        return Path(__file__).resolve().parent.parent
    except Exception:
        return Path(".")


def _boot_start():
    if __name__ != "__main__":
        return
    try:
        from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QProgressBar
        from PySide6.QtCore import Qt
        app = QApplication.instance() or QApplication(sys.argv)
        app.setLayoutDirection(Qt.RightToLeft)
        w = QWidget(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        w.setFixedSize(460, 200)
        w.setStyleSheet("QWidget#boot{background:#FFFFFF;border:1px solid #CBD5E1;border-radius:16px;}")
        w.setObjectName("boot")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 28, 22)
        t = QLabel("SalesMate")
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-size:26px;font-weight:800;color:#1565C0;background:transparent;")
        sub = QLabel("مدیریت فروش")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("font-size:12px;color:#64748B;background:transparent;")
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(True)
        bar.setFormat("%p٪")
        bar.setFixedHeight(22)
        bar.setStyleSheet(
            "QProgressBar{background:#E2E8F0;border:none;border-radius:11px;color:#0F172A;"
            "font-weight:700;text-align:center;}"
            "QProgressBar::chunk{background:#1565C0;border-radius:11px;}")
        lbl = QLabel("در حال آماده‌سازی…")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size:12px;color:#475569;background:transparent;")
        lay.addWidget(t)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(bar)
        lay.addWidget(lbl)
        try:
            g = app.primaryScreen().availableGeometry()
            w.move(g.center().x() - w.width() // 2, g.center().y() - w.height() // 2)
        except Exception:
            pass
        w.show()
        app.processEvents()
        _BOOT.update(win=w, bar=bar, lbl=lbl, app=app)
    except Exception:
        _BOOT["win"] = None


def _boot(pct, text=""):
    """به‌روزرسانی نوار پیشرفت و ثبت زمان این مرحله."""
    try:
        _BOOT["marks"].append((text, time.perf_counter() - _BOOT_T0))
        if _BOOT["win"] is not None:
            _BOOT["bar"].setValue(int(pct))
            if text:
                _BOOT["lbl"].setText(text)
            _BOOT["app"].processEvents()
    except Exception:
        pass


def _boot_finish():
    """بستن اسپلش و نوشتن گزارش زمان‌بندی (startup_timing.txt کنار برنامه)."""
    try:
        _boot(100, "آماده")
        total = time.perf_counter() - _BOOT_T0
        lines = ["SalesMate startup timing (seconds from process start of main.py)"]
        prev = 0.0
        for name, t in _BOOT["marks"]:
            lines.append("%7.2fs  (+%5.2fs)  %s" % (t, t - prev, name))
            prev = t
        lines.append("TOTAL %.2fs" % total)
        (_boot_dir() / "startup_timing.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass
    try:
        if _BOOT["win"] is not None:
            _BOOT["win"].close()
            _BOOT["win"] = None
    except Exception:
        pass


_boot_start()
_boot(3, "بارگذاری هسته‌ی برنامه…")

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
_boot(8, "بارگذاری هسته…")
try:
    import app_core as core
except Exception:
    from salesmate import app_core as core
try:
    from app_core import (
    APP_DIR,
    APP_STYLE,
    APP_VERSION,
    ATTACHMENTS_DIR,
    _BACKGROUND_PULL_INTERVAL_MS,
    _CLOSE_PUSH_SKIP_SEC,
    _ago_fa,
    _sb_push_lock,
    _swallow,
    amount,
    db,
    delete_invoice_from_cloud,
    ensure_supabase_auth,
    fetch_remote_version_info,
    apply_code_patch,
    restart_app,
    CODE_DIR,
    init_ui_invoker,
    is_online,
    is_remote_newer,
    pull_all_from_supabase,
    push_all_to_supabase,
    rebuild_customer_colors,
    renumber_invoices_by_date,
    rotate_cloud_local_backup,
    run_in_ui,
    schedule_supabase_sync,
    settings,
    soft_pull_check_and_merge,
    supabase_enabled,
    supabase_refresh_session,
    supabase_request,
    supabase_session_valid,
    supabase_user_info,
    uit,
)
except Exception:
    from salesmate.app_core import (
    APP_DIR,
    APP_STYLE,
    APP_VERSION,
    ATTACHMENTS_DIR,
    _BACKGROUND_PULL_INTERVAL_MS,
    _CLOSE_PUSH_SKIP_SEC,
    _ago_fa,
    _sb_push_lock,
    _swallow,
    amount,
    db,
    delete_invoice_from_cloud,
    ensure_supabase_auth,
    fetch_remote_version_info,
    apply_code_patch,
    restart_app,
    CODE_DIR,
    init_ui_invoker,
    is_online,
    is_remote_newer,
    pull_all_from_supabase,
    push_all_to_supabase,
    rebuild_customer_colors,
    renumber_invoices_by_date,
    rotate_cloud_local_backup,
    run_in_ui,
    schedule_supabase_sync,
    settings,
    soft_pull_check_and_merge,
    supabase_enabled,
    supabase_refresh_session,
    supabase_request,
    supabase_session_valid,
    supabase_user_info,
    uit,
)
try:
    from store_pages import CheckRasPage, StorePage
except Exception:
    from salesmate.store_pages import CheckRasPage, StorePage
try:
    from invoice_pages import ContactsPage, CustomersPage, HomePage, InvoiceDialog, InvoicesPage, ReportsPage
except Exception:
    from salesmate.invoice_pages import ContactsPage, CustomersPage, HomePage, InvoiceDialog, InvoicesPage, ReportsPage
try:
    from stats_pages import FreeItemsPage, ParquetStatsPage
except Exception:
    from salesmate.stats_pages import FreeItemsPage, ParquetStatsPage
try:
    from inquiry_page import InquiryPage
except Exception:
    from salesmate.inquiry_page import InquiryPage
try:
    from settings_page import SettingsPage
except Exception:
    from salesmate.settings_page import SettingsPage
try:
    import coworker_core
    from coworker_page import CoworkerPage
    from coworker_free_page import CoworkerFreePage
except Exception:
    from salesmate import coworker_core
    from salesmate.coworker_page import CoworkerPage
    from salesmate.coworker_free_page import CoworkerFreePage


_boot(12, "بارگذاری ماژول‌ها…")


try:
    from inventory_balance_page import InventoryBalancePage
except Exception:
    from salesmate.inventory_balance_page import InventoryBalancePage


try:
    from calc_customers_page import CalcCustomersPage
except Exception:
    from salesmate.calc_customers_page import CalcCustomersPage


AnalysisPage = None          # تنبل: matplotlib و pandas فقط وقتی لازم شد (پس‌زمینه یا اولین باز شدن) وارد می‌شوند


_ANALYSIS_TRIED = False


def _load_analysis_class():
    global AnalysisPage, _ANALYSIS_TRIED
    if AnalysisPage is None and not _ANALYSIS_TRIED:
        _ANALYSIS_TRIED = True
        try:
            from analysis_page import AnalysisPage as _A
        except Exception:
            try:
                from salesmate.analysis_page import AnalysisPage as _A
            except Exception:
                _A = None
        AnalysisPage = _A
    return AnalysisPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle("SalesMate v" + APP_VERSION); self.resize(1100,720); self.setMinimumSize(720,520); self.setLayoutDirection(Qt.RightToLeft)
        root=QWidget(); rl=QVBoxLayout(root); rl.setContentsMargins(0,0,0,0)
        # هدر دو ردیفه: برند+ابر بالا، تب‌های اسکرول‌شونده پایین — در عرض کم هم کامل دیده می‌شوند
        header=QFrame(); header.setObjectName("header")
        header_l=QVBoxLayout(header)
        header_l.setContentsMargins(14, 8, 14, 8)
        header_l.setSpacing(6)

        top=QHBoxLayout(); top.setSpacing(8)
        b=QVBoxLayout(); b.setSpacing(0); b.setAlignment(Qt.AlignRight)
        brand=QLabel(settings()["company_name"]); brand.setObjectName("brand")
        sub=QLabel("SalesMate • مدیریت فروش"); sub.setObjectName("subtitle")
        b.addWidget(brand, alignment=Qt.AlignRight)
        b.addWidget(sub, alignment=Qt.AlignRight)
        top.addLayout(b)
        top.addStretch(1)
        btn_pull = QPushButton("⬇ ابر")
        btn_pull.setToolTip("دریافت از ابر (F5)")
        btn_pull.setCursor(Qt.PointingHandCursor)
        btn_pull.setFixedHeight(32)
        btn_pull.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;"
            "padding:4px 12px;font-weight:800;font-size:12px;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        btn_pull.clicked.connect(self.quick_cloud_pull)
        btn_push = QPushButton("⬆ ابر")
        btn_push.setToolTip("ارسال به ابر (Ctrl+S)")
        btn_push.setCursor(Qt.PointingHandCursor)
        btn_push.setFixedHeight(32)
        btn_push.setStyleSheet(
            "QPushButton{background:#16A34A;color:#fff;border:none;border-radius:10px;"
            "padding:4px 12px;font-weight:800;font-size:12px;}"
            "QPushButton:hover{background:#15803D;}"
        )
        btn_push.clicked.connect(self.quick_cloud_push)
        self.sync_badge = QPushButton("☁ …")
        self.sync_badge.setCursor(Qt.PointingHandCursor)
        self.sync_badge.setFixedHeight(32)
        self.sync_badge.setToolTip("وضعیت همگام‌سازی با ابر — کلیک = ارسال همین حالا")
        self.sync_badge.clicked.connect(self.quick_cloud_push)
        top.addWidget(self.sync_badge)
        top.addWidget(btn_pull)
        top.addWidget(btn_push)
        header_l.addLayout(top)
        self._sync_badge_timer = QTimer(self)
        self._sync_badge_timer.timeout.connect(self._update_sync_badge)
        self._sync_badge_timer.start(2000)
        QTimer.singleShot(300, self._update_sync_badge)

        # ردیف تب‌ها — عرض مساوی، فونت و متن با اندازه پنجره عوض می‌شود (بدون tooltip)
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(0, 0, 0, 0)
        nav_row.setSpacing(2)
        self._nav_specs = []  # (button, short, long)
        for short, long, fn in [
            ("خانه", "خانه", self.home),
            ("حواله‌ها", "حواله‌ها", self.invoices),
            ("استعلام", "استعلام", self.inquiry),
            ("مشتریان", "مشتریان", self.customers),
            ("اطلاعات", "اطلاعات مشتری‌ها", self.contacts),
            ("گزارش‌ها", "گزارش‌ها", self.reports),
            ("فروشگاه", "فروشگاه", self.store),
            ("راس چک", "راس چک", self.check_ras),
            ("بالانس", "بالانس موجودی", self.open_inventory_balancer),
            ("محاسبات", "مشتریان و محاسبات", self.open_calc_customers),
            ("تحلیل", "تحلیل فروش", self.open_analysis),
            ("پارکت", "آمار فروش پارکت", self.parquet_stats),
            ("سمپل", "سمپل و استند", self.free_items),
            ("همکاران", "همکاران", self.open_coworkers),
            ("تنظیمات", "تنظیمات", self.settings_page),
        ]:
            x = QPushButton(short)
            x.setProperty("class", "navButton")
            x.setCursor(Qt.PointingHandCursor)
            x.setFixedHeight(36)
            x.setMinimumWidth(0)
            x.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            x.clicked.connect(fn)
            nav_row.addWidget(x, 1)
            self._nav_specs.append((x, short, long))
        header_l.addLayout(nav_row)
        rl.addWidget(header)
        QTimer.singleShot(0, self._adapt_nav_buttons)
        self.stack=QStackedWidget(); rl.addWidget(self.stack, 1)
        _boot(66, "ساخت صفحه‌ی خانه و حواله‌ها…")
        self.home_page=HomePage(self); self.invoice_page=None
        self.inv_page=InvoicesPage(self)
        self.inquiry_page=InquiryPage(self)
        self.cust_page=CustomersPage(self); self.rep_page=ReportsPage(self)
        self.store_page=StorePage(self)
        self.contacts_page=ContactsPage(self)
        self.ras_page=CheckRasPage(self)
        _boot(76, "ساخت تنظیمات و بالانس…")
        self.set_page=SettingsPage(self)
        self.balance_page = InventoryBalancePage(
            self, APP_DIR,
            cloud={"request": supabase_request, "enabled": supabase_enabled, "valid": supabase_session_valid})
        self.calc_page = CalcCustomersPage(
            self, APP_DIR,
            cloud={"request": supabase_request, "enabled": supabase_enabled, "valid": supabase_session_valid,
                   "user": supabase_user_info})
        # تحلیل فروش: lazy — فقط با اولین باز کردن تب ساخته می‌شود (matplotlib سنگین است)
        self.analysis_page = None
        self._analysis_placeholder = QLabel("برای باز کردن تحلیل فروش روی تب «📈 تحلیل» بزنید…")
        self._analysis_placeholder.setAlignment(Qt.AlignCenter)
        self._analysis_placeholder.setStyleSheet("color:#64748b;font-size:14px;padding:40px;")
        _boot(86, "ساخت آمار پارکت و سمپل…")
        self.parquet_page = ParquetStatsPage(self)
        self.free_page = FreeItemsPage(self)
        self.cw_free_page = CoworkerFreePage(self)
        self.coworker_page = CoworkerPage(
            self, {"request": supabase_request, "valid": supabase_session_valid}, self._cw_df, self._cw_exclude, self._cw_mine)
        for p in [self.home_page,self.inv_page,self.inquiry_page,self.cust_page,self.contacts_page,self.rep_page,self.store_page,self.ras_page,self.balance_page,self.calc_page,self._analysis_placeholder,self.parquet_page,self.free_page,self.cw_free_page,self.coworker_page,self.set_page]:
            self.stack.addWidget(p)
        self.setCentralWidget(root)
        if uit is not None:
            try:
                uit.set_toast_host(self)
                uit.set_skeleton_host(self)
            except Exception:
                _swallow()
        QTimer.singleShot(2500, self.check_update_silent)
        try:
            coworker_core.CACHE_PATH = str(APP_DIR / "coworker_sent.json")
        except Exception:
            _swallow()
        self.apply_role_gating()
        QTimer.singleShot(6000, self.cw_apply_feed)
        QTimer.singleShot(1500, self._start_analysis_warmup)  # بعد از نمایش پنجره، تحلیل در پس‌زمینه گرم می‌شود
        self._soft_pull_timer = QTimer(self)
        self._soft_pull_timer.setInterval(300000)  # 5 دقیقه — کاهش مصرف اینترنت
        self._soft_pull_timer.timeout.connect(self.soft_cloud_poll)
        self._soft_pull_timer.start(); self.home()
        pass
        core._cloud_ui_window = self
        self._sync_flash = QLabel(self)
        self._sync_flash.setText("")
        self._sync_flash.setStyleSheet(
            "QLabel{color:#FFFFFF;font-size:16px;font-weight:900;"
            "background:#0EA5E9;border-radius:10px;padding:4px 8px;}"
        )
        self._sync_flash.setFixedSize(36, 28)
        self._sync_flash.move(12, 12)
        self._sync_flash.hide()
        self._sync_flash.raise_()
        _boot(93, "اتصال به ابر…")
        self._start_auth_refresh_timer()
        self._start_cloud_sync_timers()
        self._start_periodic_cloud_backup()


    def _start_cloud_sync_timers(self):
        """دریافت دوره‌ای از ابر + آماده‌سازی برای فعال شدن پنجره."""
        try:
            from PySide6.QtCore import QTimer
            self._cloud_pull_timer = QTimer(self)
            self._cloud_pull_timer.setInterval(_BACKGROUND_PULL_INTERVAL_MS)
            self._cloud_pull_timer.timeout.connect(self._background_cloud_pull)
            self._cloud_pull_timer.start()
            # چند ثانیه بعد از باز شدن یک‌بار بگیر
            QTimer.singleShot(10000, self._background_cloud_pull)
        except Exception:
            _swallow()

    def _background_cloud_pull(self):
        """دریافت خودکار از ابر غیرفعال است — فقط ارسال محلی و دریافت دستی.
        این کار جلوی پاک شدن داده با نسخه خالی ابر را می‌گیرد."""
        return


    def _set_sync_flash(self, mode):
        """up=ارسال ▲  down=دریافت ▼  خالی=مخفی"""
        try:
            if mode == "up":
                self._sync_flash.setText("▲ ارسال")
                self._sync_flash.setStyleSheet(
                    "QLabel{color:#FFFFFF;font-size:13px;font-weight:900;"
                    "background:#16A34A;border-radius:10px;padding:4px 10px;}"
                )
                self._sync_flash.setFixedWidth(70)
                self._sync_flash.setToolTip("در حال ارسال به ابر…")
                self._sync_flash.show()
                self._sync_flash.raise_()
            elif mode == "down":
                self._sync_flash.setText("▼ دریافت")
                self._sync_flash.setStyleSheet(
                    "QLabel{color:#FFFFFF;font-size:13px;font-weight:900;"
                    "background:#1565C0;border-radius:10px;padding:4px 10px;}"
                )
                self._sync_flash.setFixedWidth(80)
                self._sync_flash.setToolTip("در حال دریافت از ابر…")
                self._sync_flash.show()
                self._sync_flash.raise_()
            else:
                self._sync_flash.hide()
                self._sync_flash.setText("")
        except Exception:
            _swallow()

    def resizeEvent(self, event):
        try:
            self._sync_flash.move(10, 10)
            self._sync_flash.raise_()
        except Exception:
            _swallow()
        try:
            self._adapt_nav_buttons()
        except Exception:
            _swallow()
        return super().resizeEvent(event)

    def _adapt_nav_buttons(self):
        """اندازه فونت و متن تب‌ها را با عرض پنجره تنظیم می‌کند تا کل ردیف پر شود."""
        specs = getattr(self, "_nav_specs", None) or []
        if not specs:
            return
        w = int(self.width() or 0)
        if w >= 1280:
            fs, pad_h, pad_v = 13, 10, 6
            use_long = True
        elif w >= 1100:
            fs, pad_h, pad_v = 12, 8, 5
            use_long = True
        elif w >= 950:
            fs, pad_h, pad_v = 11, 6, 4
            use_long = False
        elif w >= 800:
            fs, pad_h, pad_v = 10, 4, 3
            use_long = False
        else:
            fs, pad_h, pad_v = 9, 2, 2
            use_long = False
        style = (
            "QPushButton{background:transparent;border:none;border-radius:10px;"
            "padding:%dpx %dpx;color:#475569;font-size:%dpx;font-weight:700;}"
            "QPushButton:hover{background:#E0F2FE;color:#0D47A1;}"
        ) % (pad_v, pad_h, fs)
        for btn, short, long in specs:
            try:
                btn.setText(long if use_long else short)
                btn.setStyleSheet(style)
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            except Exception:
                _swallow()


    def changeEvent(self, event):
        """فعال شدن پنجره دیگر از ابر نمی‌خواند (امنیت داده)."""
        try:
            pass
        except Exception:
            _swallow()
        try:
            super().changeEvent(event)
        except Exception:
            _swallow()

    def _start_auth_refresh_timer(self):
        """هر ۳۰ دقیقه توکن ابر را تمدید کن تا موقع بستن منقضی نباشد."""
        try:
            from PySide6.QtCore import QTimer
            self._auth_timer = QTimer(self)
            self._auth_timer.setInterval(30 * 60 * 1000)  # 30 min
            def _tick():
                try:
                    if supabase_enabled() and supabase_session_valid():
                        supabase_refresh_session(force=True)
                except Exception:
                    _swallow()
            self._auth_timer.timeout.connect(_tick)
            self._auth_timer.start()
            # یک‌بار هم چند ثانیه بعد از باز شدن
            QTimer.singleShot(5000, _tick)
        except Exception:
            _swallow()


    def _start_periodic_cloud_backup(self):
        """هر ۳ ساعت یک‌بار پشتیبان کامل روی ابر."""
        try:
            from PySide6.QtCore import QTimer
            self._periodic_cloud_timer = QTimer(self)
            self._periodic_cloud_timer.setInterval(3 * 60 * 60 * 1000)  # 3 hours
            def _tick():
                try:
                    if not supabase_enabled() or not supabase_session_valid():
                        return
                    if not is_online():
                        return
                    def _w():
                        try:
                            push_all_to_supabase()
                        except Exception:
                            _swallow()
                    threading.Thread(target=_w, daemon=True).start()
                except Exception:
                    _swallow()
            self._periodic_cloud_timer.timeout.connect(_tick)
            self._periodic_cloud_timer.start()
        except Exception:
            _swallow()

    def closeEvent(self, event):
        """هنگام بستن: همیشه بکاپ لوکال؛ اگر وارد ابر باشد پشتیبان ابری بفرست."""
        try:
            # بکاپ لوکال اجباری
            try:
                rotate_cloud_local_backup(max_keep=5, force=True)
            except Exception:
                _swallow()
            if not supabase_enabled() or not supabase_session_valid():
                event.accept()
                return
            if not is_online():
                ret = QMessageBox.warning(
                    self,
                    "آفلاین هستید",
                    "اتصال اینترنت برقرار نیست؛ پشتیبان ابری انجام نشد.\n\n"
                    "با «بستن» بدون پشتیبان خارج می‌شوید.\n"
                    "با «لغو» در برنامه می‌مانید تا آنلاین شوید.",
                    QMessageBox.Close | QMessageBox.Cancel,
                    QMessageBox.Cancel,
                )
                if ret == QMessageBox.Close:
                    event.accept()
                else:
                    event.ignore()
                return
            try:
                pass
                import time as _time
                # اگر همین ۹۰ ثانیه اخیر پشتیبان موفق بوده، دیگر صبر نکن
                if core._last_supabase_push_at and (_time.time() - core._last_supabase_push_at) < _CLOSE_PUSH_SKIP_SEC:
                    event.accept()
                    return
                self._close_push_with_progress()
            except Exception as e:
                try:
                    QApplication.restoreOverrideCursor()
                except Exception:
                    _swallow()
                ret = QMessageBox.critical(
                    self,
                    "خطا در پشتیبان ابری",
                    "ارسال به ابر انجام نشد:\n%s\n\nبدون پشتیبان بسته شود؟" % (e,),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if ret == QMessageBox.Yes:
                    event.accept()
                else:
                    event.ignore()
                return
            event.accept()
        except Exception:
            event.accept()


    def _close_push_with_progress(self):
        """ارسال به ابر هنگام بستن، با نوار پیشرفت ۰ تا ۱۰۰٪ (ارسال در رشته‌ی جدا)."""
        import time as _time
        dlg = QDialog(self)
        dlg.setWindowTitle("ارسال به ابر")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setModal(True)
        dlg.setMinimumWidth(380)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        title = QLabel("در حال ارسال اطلاعات به ابر؛ لطفاً صبر کنید…")
        title.setStyleSheet("font-weight:700;font-size:13px;")
        lay.addWidget(title)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(0)
        bar.setTextVisible(True)
        bar.setFormat("%p٪")
        bar.setMinimumHeight(22)
        bar.setStyleSheet(
            "QProgressBar{border:1px solid #CBD5E1;border-radius:8px;background:#F1F5F9;text-align:center;}"
            "QProgressBar::chunk{background:#1565C0;border-radius:7px;}"
        )
        lay.addWidget(bar)
        step = QLabel("شروع…")
        step.setStyleSheet("color:#64748B;font-size:12px;")
        lay.addWidget(step)
        dlg.show()

        state = {"pct": 0, "text": "شروع…", "err": None, "done": False}

        def _cb(pct, text):
            state["pct"] = pct
            state["text"] = text

        core._push_progress_cb = _cb

        def _work():
            try:
                try:
                    ensure_supabase_auth(force_refresh=True)
                except Exception:
                    _swallow()
                push_all_to_supabase()
            except Exception as ex:
                state["err"] = ex
            finally:
                state["done"] = True

        th = threading.Thread(target=_work, daemon=True)
        th.start()
        shown = 0.0
        try:
            while not state["done"]:
                # نرم به سمت مرحله‌ی فعلی؛ کمی جلوتر تا میان مرحله‌ها هم حرکت کند
                target = min(99.0, state["pct"] + 6.0)
                shown += (target - shown) * 0.06
                bar.setValue(int(shown))
                step.setText(state["text"])
                QApplication.processEvents()
                _time.sleep(0.03)
        finally:
            core._push_progress_cb = None
        if state["err"] is not None:
            dlg.close()
            raise state["err"]
        bar.setValue(100)
        step.setText("انجام شد")
        QApplication.processEvents()
        _time.sleep(0.25)
        dlg.close()

    def quick_cloud_pull(self):
        """دریافت از ابر — پس‌زمینه + اسکلتون + toast."""
        pass
        if not supabase_enabled() or not supabase_session_valid():
            QMessageBox.warning(self, "ابر", "ابتدا از تنظیمات وارد حساب ابر شوید.")
            return
        if core._local_dirty:
            ret = QMessageBox.question(
                self, "دریافت از ابر",
                "تغییرات این سیستم هنوز کامل به ابر نرسیده.\nاول ارسال می‌شود، بعد دریافت. ادامه؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                return
        else:
            ret = QMessageBox.question(
                self, "دریافت از ابر",
                "داده ابر برای این حساب روی این سیستم اعمال شود؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                return
        if uit is not None:
            try: uit.show_skeleton("در حال دریافت از ابر…")
            except Exception: _swallow()

        def _worker():
            err = None
            ts = ""
            try:
                if core._local_dirty:
                    push_all_to_supabase()
                ts = pull_all_from_supabase()
            except Exception as e:
                err = e

            def _done():
                if uit is not None:
                    try: uit.hide_skeleton()
                    except Exception: _swallow()
                if err:
                    if uit is not None:
                        try: uit.toast("خطا در دریافت: " + str(err)[:80], "error", 4500)
                        except Exception: _swallow()
                    QMessageBox.critical(self, "خطا", str(err))
                    return
                try:
                    self.refresh_all()
                except Exception:
                    _swallow()
                msg = "دریافت از ابر انجام شد"
                if ts == "kept-local-stronger-than-cloud":
                    msg = "ابر خالی‌تر بود — داده محلی حفظ شد"
                if uit is not None:
                    try: uit.toast(msg, "success")
                    except Exception: _swallow()
                else:
                    QMessageBox.information(self, "ابر", msg)

            run_in_ui(_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _ensure_push_bar(self):
        """نوار پیشرفت ارسال به ابر در پایین پنجره (پنهان تا موقع ارسال)."""
        if getattr(self, "_push_box", None) is not None:
            return
        box = QWidget()
        hl = QHBoxLayout(box)
        hl.setContentsMargins(8, 2, 8, 2)
        hl.setSpacing(10)
        self._push_lbl = QLabel("")
        self._push_lbl.setStyleSheet("color:#334155;font-size:12px;font-weight:600;")
        hl.addWidget(self._push_lbl)
        bar = QProgressBar()
        bar.setRange(0, 100)
        bar.setFixedHeight(18)
        bar.setMinimumWidth(320)
        bar.setFormat("%p٪")
        bar.setStyleSheet(
            "QProgressBar{border:1px solid #CBD5E1;border-radius:9px;background:#F1F5F9;text-align:center;font-size:11px;}"
            "QProgressBar::chunk{background:#1565C0;border-radius:8px;}"
        )
        hl.addWidget(bar, 1)
        self._push_bar = bar
        self._push_box = box
        box.hide()
        self.statusBar().addWidget(box, 1)
        self._push_state = {"pct": 0, "text": "", "done": False, "err": None, "ts": "", "shown": 0.0}
        self._push_timer = QTimer(self)
        self._push_timer.setInterval(40)
        self._push_timer.timeout.connect(self._push_tick)

    def _push_tick(self):
        st = self._push_state
        if not st["done"]:
            target = min(99.0, st["pct"] + 6.0)
            st["shown"] += (target - st["shown"]) * 0.06
            self._push_bar.setValue(int(st["shown"]))
            self._push_lbl.setText("ارسال به ابر: " + (st["text"] or ""))
            return
        self._push_timer.stop()
        core._push_progress_cb = None
        err = st["err"]
        if err:
            self._push_box.hide()
            self._push_busy = False
            if uit is not None:
                try: uit.toast("خطا در ارسال: " + str(err)[:80], "error", 4500)
                except Exception: _swallow()
            QMessageBox.critical(self, "خطا", str(err))
            return
        self._push_bar.setValue(100)
        self._push_lbl.setText("ارسال به ابر انجام شد ✓")
        if uit is not None:
            try: uit.toast("ارسال به ابر انجام شد", "success")
            except Exception: _swallow()

        def _hide():
            self._push_box.hide()
            self._push_busy = False
        QTimer.singleShot(1200, _hide)

    def quick_cloud_push(self):
        if not supabase_enabled() or not supabase_session_valid():
            QMessageBox.warning(self, "ابر", "ابتدا از تنظیمات وارد حساب ابر شوید.")
            return
        if getattr(self, "_push_busy", False):
            return
        self._ensure_push_bar()
        self._push_busy = True
        st = self._push_state
        st.update({"pct": 0, "text": "شروع…", "done": False, "err": None, "ts": "", "shown": 0.0})
        self._push_bar.setValue(0)
        self._push_box.show()

        def _cb(pct, text):
            st["pct"] = pct
            st["text"] = text

        core._push_progress_cb = _cb

        def _worker():
            try:
                st["ts"] = push_all_to_supabase()
            except Exception as e:
                st["err"] = e
            finally:
                st["done"] = True

        threading.Thread(target=_worker, daemon=True).start()
        self._push_timer.start()

    def keyPressEvent(self, event):
        try:
            from PySide6.QtCore import Qt as _Qt
            if event.key() == _Qt.Key_F5:
                self.quick_cloud_pull()
                return
            if event.key() == _Qt.Key_S and (event.modifiers() & _Qt.ControlModifier):
                self.quick_cloud_push()
                return
        except Exception:
            _swallow()
        super().keyPressEvent(event)

    def soft_cloud_poll(self):
        """هر چند دقیقه بررسی سبک ابر در پس‌زمینه — بدون قفل UI."""
        pass
        try:
            self.apply_role_gating()
            self.cw_apply_feed()
        except Exception:
            _swallow()
        try:
            if core._local_dirty:
                return
            if not supabase_session_valid():
                return
            if QApplication.activeModalWidget() is not None:
                return
            try:
                if __import__("time").time() - float(core._last_supabase_pull_at or 0) < 240:
                    return
            except Exception:
                _swallow()
            import threading
            def _run():
                try:
                    changed = soft_pull_check_and_merge()
                    if changed:
                        run_in_ui(self.refresh_all)
                except Exception:
                    _swallow()
            threading.Thread(target=_run, daemon=True).start()
        except Exception:
            _swallow()

    def check_update_silent(self):
        """آپدیت سبک (کد برنامه، چند صد کیلوبایت) خودکار و بی‌صدا نصب می‌شود؛
        آپدیت کامل (نصب مجدد) فقط اطلاع می‌دهد."""
        try:
            info = fetch_remote_version_info(timeout=8)
            remote = str(info.get("version") or "")
            if not is_remote_newer(APP_VERSION, remote):
                return
            patch_url = str(info.get("patch_url") or "").strip()
            # جلوگیری از حلقه: برای هر نسخه فقط یک‌بار تلاش خودکار (اگر نسخه بالا نیامد، دستی از تنظیمات)
            mark = Path(CODE_DIR) / "auto_attempt.txt"
            try:
                tried = mark.read_text(encoding="utf-8").strip() if mark.exists() else ""
            except Exception:
                tried = ""
            if patch_url and tried != remote and not getattr(self, "_auto_upd_busy", False):
                try:
                    Path(CODE_DIR).mkdir(parents=True, exist_ok=True)
                    mark.write_text(remote, encoding="utf-8")
                except Exception:
                    _swallow()
                self._auto_upd_busy = True
                self.setWindowTitle("SalesMate v" + APP_VERSION + "  •  در حال دریافت نسخه " + remote + "…")

                def _work():
                    err = None
                    try:
                        apply_code_patch(patch_url, remote)
                    except Exception as e:
                        err = e

                    def _done():
                        self._auto_upd_busy = False
                        if err:
                            _swallow()
                            self.setWindowTitle("SalesMate v" + APP_VERSION + "  •  نسخه جدید " + remote + " در تنظیمات")
                            return
                        self.setWindowTitle("SalesMate v" + APP_VERSION + "  •  نسخه " + remote + " نصب شد؛ برنامه دوباره باز می‌شود…")
                        QTimer.singleShot(1200, lambda: (restart_app(), QApplication.quit()))
                    run_in_ui(_done)

                threading.Thread(target=_work, daemon=True).start()
                return
            # نسخه‌ی کامل: فقط اطلاع
            self.setWindowTitle("SalesMate v" + APP_VERSION + "  •  نسخه جدید " + remote + " در تنظیمات")
            QTimer.singleShot(800, lambda: QMessageBox.information(
                self, "نسخه جدید",
                "نسخه جدید SalesMate آماده است: " + remote + "\n\n"
                "از منوی تنظیمات → بخش «آپدیت برنامه» آپدیت کنید."
            ))
        except Exception:
            _swallow()

    def home(self): self.home_page.refresh(); self.stack.setCurrentWidget(self.home_page)
    def invoices(self): self.inv_page.refresh(); self.stack.setCurrentWidget(self.inv_page)
    def inquiry(self):
        try:
            try: from inquiry_page import ask_prune_saved_inquiries
            except Exception: from salesmate.inquiry_page import ask_prune_saved_inquiries
            ask_prune_saved_inquiries(self)
        except Exception: _swallow()
        try: self.inquiry_page.reload_buyer_list()
        except Exception: _swallow()
        self.stack.setCurrentWidget(self.inquiry_page)
    def customers(self): self.cust_page.refresh(); self.stack.setCurrentWidget(self.cust_page)
    def reports(self): self.rep_page.refresh(); self.stack.setCurrentWidget(self.rep_page)
    def contacts(self):
        self.stack.setCurrentWidget(self.contacts_page)
        try:
            self.contacts_page.refresh()
        except Exception:
            _swallow()

    # ───────── همکاران / نقش‌ها ─────────
    OWNER_ONLY_TABS = {"فروشگاه", "بالانس", "محاسبات", "تحلیل", "پارکت", "همکاران"}   # «سمپل» برای همکار صفحه‌ی خودش را دارد

    def current_email(self):
        try:
            return str(supabase_user_info().get("email") or "")
        except Exception:
            return ""

    def is_owner_account(self):
        """مالک؟ حساب ناشناخته (هنوز وارد نشده) مثل مالک رفتار می‌کند تا نسخه‌ی خود مالک بدون ورود محدود نشود."""
        em = self.current_email()
        return (not em) or coworker_core.is_owner_email(em)

    def apply_role_gating(self):
        try:
            em = self.current_email()
            owner = (not em) or coworker_core.is_owner_email(em)
            real_owner = coworker_core.is_owner_email(em)
            for btn, short, long in getattr(self, "_nav_specs", []):
                if short == "همکاران":
                    btn.setVisible(real_owner)
                elif short in self.OWNER_ONLY_TABS:
                    btn.setVisible(owner)
            if not owner:
                hidden = [getattr(self, n, None) for n in ("store_page", "balance_page", "calc_page", "analysis_page",
                                                           "parquet_page", "free_page", "coworker_page", "_analysis_placeholder")]
                if self.stack.currentWidget() in [h for h in hidden if h is not None]:
                    self.home()
            elif not real_owner and self.stack.currentWidget() is getattr(self, "coworker_page", None):
                self.home()
        except Exception:
            _swallow()

    def _cw_df(self):
        if self.analysis_page is None:
            if _load_analysis_class() is None:
                return None
            self._build_analysis_page()
        return getattr(self.analysis_page, "df", None)

    def _cw_exclude(self):
        """مشتریان فروشگاه (انتخاب صریح در تحلیل فروش) قابل واگذاری به همکار نیستند."""
        try:
            if self.analysis_page is not None:
                return self.analysis_page._store_keys()
        except Exception:
            _swallow()
        return set()

    def _cw_mine(self):
        """ckey مشتریانی که خود مالک تیک زده (ورود به SalesMate)؛ اگر معلوم نبود None."""
        try:
            ap = self.analysis_page
            if ap is None:
                return None
            names = set(getattr(ap, "_selected_import_customers", set()) or set()) | set(ap._analysis_imported_customers())
            return {coworker_core.customer_key(n) for n in names} if names else None
        except Exception:
            _swallow()
            return None

    def open_coworkers(self):
        if not coworker_core.is_owner_email(self.current_email()):
            return
        self.stack.setCurrentWidget(self.coworker_page)
        QTimer.singleShot(30, self.coworker_page.on_show)

    def cw_apply_feed(self):
        """حساب همکار: حواله‌های در صف را (از اکسل مالک) در پس‌زمینه به این برنامه اضافه/حذف می‌کند."""
        try:
            em = self.current_email()
            if not em or coworker_core.is_owner_email(em) or not supabase_session_valid():
                return
            if getattr(self, "_cw_busy", False):
                return
            self._cw_busy = True
            uid = supabase_user_info().get("user_id") or ""
            if not uid:
                self._cw_busy = False
                return

            def _run():
                try:
                    c = sqlite3.connect(str(core.DB_PATH))
                    try:
                        res = coworker_core.apply_feed(supabase_request, uid, c)
                        # یک‌بار: ردیف‌های حواله‌های اکسلی با صف ابر (= اکسل مالک) یکی می‌شود
                        try:
                            if c.execute("PRAGMA user_version").fetchone()[0] < 3:
                                res["repaired"] = coworker_core.repair_from_feed(supabase_request, uid, c)
                                c.execute("PRAGMA user_version = 3")
                                c.commit()
                        except Exception:
                            _swallow()
                    finally:
                        c.close()
                    if res.get("added") or res.get("revoked") or res.get("repaired"):
                        def _ui():
                            try:
                                schedule_supabase_sync()
                                if hasattr(core, "renumber_invoices_by_date"):
                                    core.renumber_invoices_by_date()
                                if hasattr(core, "rebuild_customer_colors"):
                                    core.rebuild_customer_colors()
                            except Exception:
                                _swallow()
                            self.refresh_all()
                            try:
                                self.statusBar().showMessage("از اکسل مالک: %d حواله اضافه، %d حذف شد" % (res["added"], res["revoked"]), 8000)
                            except Exception:
                                _swallow()
                        run_in_ui(_ui)
                except Exception:
                    _swallow()
                finally:
                    self._cw_busy = False
            threading.Thread(target=_run, daemon=True).start()
        except Exception:
            self._cw_busy = False
            _swallow()

    def manual_invoice_ok(self):
        """حساب غیرمالک: هشدار نرم قبل از ثبت دستی حواله (حواله‌ها خودکار از اکسل می‌آیند)."""
        em = self.current_email()
        if not em or coworker_core.is_owner_email(em):
            return True
        r = QMessageBox.question(
            self, "ثبت دستی حواله",
            "حواله‌ها به‌صورت خودکار از اکسل فروش اضافه می‌شوند.\nمطمئنی می‌خواهی حواله‌ی دستی اضافه کنی؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return r == QMessageBox.Yes

    def store(self):
        try: self.store_page.refresh()
        except Exception: _swallow()
        self.stack.setCurrentWidget(self.store_page)
    def check_ras(self): self.stack.setCurrentWidget(self.ras_page)
    def settings_page(self): self.stack.setCurrentWidget(self.set_page)

    def open_inventory_balancer(self):
        self.stack.setCurrentWidget(self.balance_page)
        QTimer.singleShot(30, self.balance_page.on_show)

    def open_calc_customers(self):
        self.stack.setCurrentWidget(self.calc_page)
        QTimer.singleShot(30, self.calc_page.on_show)

    def _safe_ensure(self, page):
        try:
            if page is not None:
                page.ensure_loaded()
        except Exception:
            _swallow()

    def show_app_toast(self, message, kind="info"):
        if uit is not None:
            try:
                uit.toast(message, kind)
                return
            except Exception:
                _swallow()
        try:
            self.statusBar().showMessage(str(message), 3000)
        except Exception:
            _swallow()

    def apply_ui_theme(self, mode=None):
        if uit is None:
            return
        try:
            s = load_settings() if "load_settings" in dir() else {}
        except Exception:
            s = {}
        if mode is None:
            mode = "dark" if s.get("dark_mode") else "light"
        app = QApplication.instance()
        if app:
            uit.apply_theme(app, mode)
            # refresh style-dependent pages lightly
            try:
                self.setStyleSheet("")  # global app stylesheet handles it
            except Exception:
                _swallow()

    def _update_sync_badge(self):
        """نشانگر وضعیت همگام‌سازی ابر: همگام / ارسال‌نشده / در حال ارسال / خطا / وارد نشده."""
        try:
            tip_extra = f"\nآخرین ارسال: {_ago_fa(core._last_supabase_push_at)} · آخرین دریافت: {_ago_fa(core._last_supabase_pull_at)}"
            if not supabase_enabled() or not supabase_session_valid():
                txt, col, tip = "☁ ابر: وارد نشده", "#64748B", "برای همگام‌سازی از تنظیمات وارد حساب ابر شوید."
                if core._local_dirty:
                    tip += "\nتغییرات این سیستم هنوز جایی ارسال نشده."
            elif _sb_push_lock.locked() or core._sb_sync_busy:
                txt, col, tip = "⟳ در حال ارسال…", "#1565C0", "ارسال به ابر در جریان است." + tip_extra
            elif core._sb_last_error and core._sb_last_error_at >= core._last_supabase_push_at:
                txt, col = "⚠ خطا در ارسال", "#DC2626"
                tip = "آخرین ارسال ناموفق بود (کلیک = تلاش دوباره):\n" + core._sb_last_error + tip_extra
            elif core._local_dirty:
                txt, col, tip = "● ارسال‌نشده", "#D97706", "تغییرات هنوز به ابر نرسیده (کلیک = ارسال همین حالا)." + tip_extra
            else:
                txt, col, tip = "✓ همگام · " + _ago_fa(core._last_supabase_push_at), "#16A34A", "همه‌چیز با ابر هماهنگ است." + tip_extra
            self.sync_badge.setText(txt)
            self.sync_badge.setToolTip(tip)
            self.sync_badge.setStyleSheet(
                f"QPushButton{{background:#fff;color:{col};border:1px solid {col};border-radius:10px;"
                f"padding:4px 10px;font-weight:800;font-size:12px;}}"
                f"QPushButton:hover{{background:#F8FAFC;}}")
        except Exception:
            _swallow()

    def free_items(self):
        if not self.is_owner_account():                 # همکار: فقط سمپل/استند مشتریان خودش (از ابر)
            try:
                self.cw_free_page.refresh()
            except Exception:
                _swallow()
            self.stack.setCurrentWidget(self.cw_free_page)
            return
        try:
            self.free_page.refresh()
        except Exception:
            _swallow()
        self.stack.setCurrentWidget(self.free_page)

    def parquet_stats(self):
        try:
            self.parquet_page.refresh()
        except Exception:
            _swallow()
        self.stack.setCurrentWidget(self.parquet_page)

    def _build_analysis_page(self):
        """ساخت صفحه‌ی تحلیل (یک‌بار). True اگر آماده است."""
        if self.analysis_page is not None:
            return True
        if _load_analysis_class() is None:
            return False
        page = AnalysisPage(self)
        self.analysis_page = page
        idx = self.stack.indexOf(self._analysis_placeholder)
        if idx >= 0:
            cur_is_ph = self.stack.currentWidget() is self._analysis_placeholder
            self.stack.removeWidget(self._analysis_placeholder)
            self.stack.insertWidget(idx, page)
            if cur_is_ph:
                self.stack.setCurrentWidget(page)
        else:
            self.stack.addWidget(page)
        return True

    def _start_analysis_warmup(self):
        """کتابخانه‌های سنگین (pandas/matplotlib/تحلیل) در یک رشته‌ی پس‌زمینه وارد می‌شوند؛
        بعد صفحه‌ی تحلیل در نخ اصلی ساخته می‌شود. اگر شکست خورد، باز شدن اولین‌بار همان روش قبلی است."""
        def _work():
            try:
                import pandas, numpy  # noqa: F401
                _load_analysis_class()
            except Exception:
                _swallow()
            run_in_ui(self._preload_analysis)
        threading.Thread(target=_work, daemon=True).start()

    def _preload_analysis(self):
        """چند ثانیه بعد از بالا آمدن برنامه، صفحه‌ی تحلیل پیشاپیش ساخته می‌شود تا اولین کلیک فوری باشد."""
        try:
            if self.analysis_page is None and _load_analysis_class() is not None:
                self._build_analysis_page()
        except Exception:
            _swallow()

    def open_analysis(self):
        if self.analysis_page is None:
            if _load_analysis_class() is None:
                self.stack.setCurrentWidget(self._analysis_placeholder)
                self._analysis_placeholder.setText("ماژول تحلیل فروش در دسترس نیست.\n(pandas / matplotlib را نصب کنید)")
                return
            try:
                self._analysis_placeholder.setText("در حال آماده‌سازی تحلیل فروش…")
                QApplication.processEvents()
                self._build_analysis_page()
            except Exception as _ae:
                self._analysis_placeholder.setText("خطا در بارگذاری تحلیل فروش:\n" + str(_ae))
                self.stack.setCurrentWidget(self._analysis_placeholder)
                return
        self.stack.setCurrentWidget(self.analysis_page)

    def store_invoice_image(self, source, invoice_id):
        if not source or not Path(source).exists():
            return ""
        suffix=Path(source).suffix.lower() or ".jpg"
        target=ATTACHMENTS_DIR / f"invoice_{invoice_id}{suffix}"
        try:
            shutil.copy2(source,target)
            return str(target)
        except Exception:
            return ""

    def open_invoice_image(self, invoice_id):
        c=db()
        row=c.execute("SELECT image_path FROM invoices WHERE id=?",(invoice_id,)).fetchone()
        c.close()
        if not row or not row[0]:
            QMessageBox.information(self,"عکس حواله","برای این حواله عکسی ثبت نشده است.")
            return
        p=Path(row[0])
        if not p.is_absolute():
            p=(APP_DIR / p).resolve()
        if not p.exists():
            QMessageBox.warning(self,"عکس حواله","فایل عکس حواله پیدا نشد.")
            return
        try:
            os.startfile(str(p))
        except Exception as ex:
            QMessageBox.critical(self,"خطا","باز کردن عکس انجام نشد:\n"+str(ex))

    def open_invoice_inquiry(self, invoice_id):
        """نمایش اقلام خریداری‌شده برای حواله (استعلام / واردات تحلیل)."""
        c = db()
        row = c.execute(
            "SELECT inquiry_data, invoice_no, customer, date, total FROM invoices WHERE id=?",
            (invoice_id,),
        ).fetchone()
        c.close()
        if not row or not row[0] or not str(row[0]).strip():
            QMessageBox.information(self, "استعلام", "برای این حواله جزئیات کالا ذخیره نشده است.")
            return
        try:
            data = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
        except Exception as ex:
            QMessageBox.critical(self, "استعلام", "خواندن داده ممکن نیست:\n" + str(ex))
            return
        if not isinstance(data, dict):
            data = {}

        inv_no = str(row[1] or "")
        customer = str(row[2] or "")
        inv_date = str(row[3] or "")
        inv_total = str(row[4] or "")

        # نرمال‌سازی داده واردات تحلیل فروش
        tab = data.get("tab") or "parquet"
        try:
            from statement_core import sample_last
        except Exception:
            from salesmate.statement_core import sample_last
        rows = sample_last(data.get("rows") or [])
        if tab == "analysis_import" or (rows and "name" in (rows[0] or {}) and "type" not in (rows[0] or {})):
            norm_rows = []
            for i, r in enumerate(rows or []):
                r = r or {}
                cost = r.get("cost")
                try:
                    cost_n = int(round(float(str(cost).replace(",", "") or 0)))
                except Exception:
                    cost_n = 0
                price = r.get("price")
                try:
                    price_n = int(round(float(str(price).replace(",", "") or 0)))
                except Exception:
                    price_n = 0
                # مبالغ همان ریال ذخیره‌شده
                norm_rows.append({
                    "index": i + 1,
                    "code": r.get("code") or "",
                    "type": r.get("name") or r.get("type") or "",
                    "grade": "",
                    "qty1": core.qty_int(r.get("qty1")) or "",
                    "qty2": r.get("qty2") or "",
                    "price": price_n or r.get("price") or "",
                    "cost": cost_n or r.get("cost") or "",
                })
            data = {
                "tab": "mdf" if core.is_mdf_invoice(data) else "parquet",
                "buyer": data.get("buyer") or customer,
                "date": data.get("date") or inv_date,
                "total": amount(data.get("total") or inv_total),
                "rows": norm_rows,
                "warehouse": data.get("warehouse") or "",
                "transport": data.get("transport") or "",
                "validity": data.get("validity") or ("حواله " + inv_no),
            }

        if isinstance(data.get("rows"), list):
            data["rows"] = sample_last(data["rows"])
        # اطمینان از فیلدهای الزامی
        if not data.get("buyer"):
            data["buyer"] = customer
        if not data.get("date"):
            data["date"] = inv_date
        if data.get("total") in (None, "") and inv_total:
            data["total"] = amount(inv_total)

        try:
            html = InquiryPage.build_inquiry_html_static(data)
            out = APP_DIR / ("estelam_invoice_%s.html" % invoice_id)
            out.write_text(html, encoding="utf-8")
            webbrowser.open(out.as_uri())
        except Exception as ex:
            # fallback: دیالوگ ساده اقلام
            try:
                dlg = QDialog(self)
                dlg.setWindowTitle("اقلام حواله — " + customer)
                dlg.resize(700, 420)
                dlg.setLayoutDirection(Qt.RightToLeft)
                lay = QVBoxLayout(dlg)
                lay.addWidget(QLabel("مشتری: %s | حواله: %s | تاریخ: %s" % (customer, inv_no, inv_date)))
                table = QTableWidget(0, 5)
                table.setHorizontalHeaderLabels(["کد", "نام/نوع", "تعداد", "قیمت", "مبلغ"])
                table.horizontalHeader().setStretchLastSection(True)
                try:
                    from statement_core import sample_last as _sl
                except Exception:
                    from salesmate.statement_core import sample_last as _sl
                for r in _sl(data.get("rows") or []):
                    rr = table.rowCount()
                    table.insertRow(rr)
                    table.setItem(rr, 0, QTableWidgetItem(str(r.get("code") or "")))
                    table.setItem(rr, 1, QTableWidgetItem(str(r.get("type") or r.get("name") or "")))
                    table.setItem(rr, 2, QTableWidgetItem(str(core.qty_int(r.get("qty1")) or r.get("qty2") or "")))
                    table.setItem(rr, 3, QTableWidgetItem(str(r.get("price") or "")))
                    table.setItem(rr, 4, QTableWidgetItem(str(r.get("cost") or "")))
                lay.addWidget(table)
                close_b = QPushButton("بستن")
                close_b.clicked.connect(dlg.accept)
                lay.addWidget(close_b)
                dlg.exec()
            except Exception as ex2:
                QMessageBox.critical(self, "استعلام", "باز کردن انجام نشد:\n%s\n%s" % (ex, ex2))

    def new_invoice(self):
        if not self.manual_invoice_ok():
            return
        d=InvoiceDialog(self)
        if d.exec()!=QDialog.Accepted: return
        try:
            v=d.values()
        except Exception as ex:
            QMessageBox.critical(self,"خطا","خواندن اطلاعات حواله انجام نشد:\n"+str(ex))
            return
        if not v[0] or not v[1] or not v[4]:
            QMessageBox.warning(self,"اطلاعات ناقص","نام مشتری، شماره حواله و مبلغ کل الزامی هستند.")
            return
        if len(v) >= 8:
            customer, invoice_no, date, time, total, image, paid, inq_json = v
        else:
            customer, invoice_no, date, time, total, image, paid = v
            inq_json = ""
        c=db()
        try:
            cur=c.execute(
                "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) VALUES(?,?,?,?,?,?,?,?,?)",
                (customer,invoice_no,date,time,total,datetime.now().isoformat(timespec="seconds"),"", inq_json or "", str(paid)),
            )
            invoice_id=cur.lastrowid
            stored=self.store_invoice_image(image,invoice_id)
            c.execute("UPDATE invoices SET image_path=? WHERE id=?",(stored,invoice_id))
            c.commit()
        except Exception as ex:
            c.rollback()
            QMessageBox.critical(self,"خطا در ذخیره",f"حواله ذخیره نشد:\n{ex}")
            c.close(); return
        c.close()
        QMessageBox.information(self,"SalesMate","حواله با موفقیت ذخیره شد.")
        self.refresh_all(); self.invoices()


    def edit_invoice(self,i):
        c=db()
        row=c.execute(
            "SELECT id,customer,invoice_no,date,time,total,created_at,image_path,paid_amount,inquiry_data FROM invoices WHERE id=?",
            (i,),
        ).fetchone()
        c.close()
        if not row: return
        d=InvoiceDialog(self,row)
        if d.exec()!=QDialog.Accepted: return
        try:
            v=d.values()
        except Exception as ex:
            QMessageBox.critical(self,"خطا","خواندن اطلاعات حواله انجام نشد:\n"+str(ex))
            return
        if not v[0] or not v[1] or not v[4]:
            QMessageBox.warning(self,"اطلاعات ناقص","نام مشتری، شماره حواله و مبلغ کل الزامی هستند.")
            return
        if len(v) >= 8:
            customer, invoice_no, date, time, total, image, paid, inq_json = v
        else:
            customer, invoice_no, date, time, total, image, paid = v
            inq_json = ""
        c=db()
        try:
            old=c.execute("SELECT image_path FROM invoices WHERE id=?",(i,)).fetchone()
            stored=old[0] if old else ""
            if image and image != stored: stored=self.store_invoice_image(image,i)
            c.execute(
                "UPDATE invoices SET customer=?,invoice_no=?,date=?,time=?,total=?,image_path=?,paid_amount=?,inquiry_data=? WHERE id=?",
                (customer,invoice_no,date,time,total,stored,str(paid),inq_json or "",i),
            )
            c.commit()
        except Exception as ex:
            c.rollback()
            QMessageBox.critical(self,"خطا در ذخیره",f"تغییرات ذخیره نشد:\n{ex}")
            c.close(); return
        c.close()
        # ویرایش حواله هم مثل افزودن/حذف باید خودکار به ابر برود
        schedule_supabase_sync()
        QMessageBox.information(self,"SalesMate","تغییرات با موفقیت ذخیره شد.")
        self.refresh_all()


    def delete_invoice(self, i):
        if QMessageBox.question(
            self, "حذف حواله",
            "این حواله حذف شود؟\nاز ابر و بقیه دستگاه‌ها هم حذف می‌شود."
        ) != QMessageBox.Yes:
            return
        c = db()
        row = c.execute(
            "SELECT customer, invoice_no, date, time, total FROM invoices WHERE id=?",
            (i,),
        ).fetchone()
        c.execute("DELETE FROM invoices WHERE id=?", (i,))
        c.commit()
        c.close()
        # حذف فوری از ابر تا soft-pull دوباره برنگرداند
        if row:
            inv = {
                "customer": row[0] or "",
                "invoiceNo": row[1] or "",
                "date": row[2] or "",
                "time": row[3] or "",
                "total": str(row[4] or "0"),
            }
            def _del_cloud():
                try:
                    delete_invoice_from_cloud(inv)
                except Exception:
                    _swallow()
            try:
                threading.Thread(target=_del_cloud, daemon=True).start()
            except Exception:
                try:
                    delete_invoice_from_cloud(inv)
                except Exception:
                    _swallow()
        schedule_supabase_sync()
        self.refresh_all()
    def refresh_all(self):
        if uit is not None:
            try: uit.invalidate_customer_cache()
            except Exception: _swallow()
        rebuild_customer_colors()
        self.home_page.refresh(); self.inv_page.refresh(); self.cust_page.refresh(); self.rep_page.refresh()
        try:
            if hasattr(self, "inquiry_page") and self.inquiry_page:
                self.inquiry_page.reload_buyer_list()
        except Exception:
            _swallow()


def main():
    app = QApplication.instance() or QApplication(sys.argv); app.setLayoutDirection(Qt.RightToLeft)
    _boot(35, "آماده‌سازی ظاهر برنامه…")
    init_ui_invoker()
    try:
        mode = "dark" if settings().get("dark_mode") else "light"
    except Exception:
        mode = "light"
    if uit is not None:
        try:
            uit.apply_theme(app, mode)
        except Exception:
            app.setStyle("Fusion"); app.setStyleSheet(APP_STYLE)
    else:
        app.setStyle("Fusion"); app.setStyleSheet(APP_STYLE)
    try:
        pal = app.palette()
        pal.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
        pal.setColor(QPalette.ToolTipText, QColor("#0F172A"))
        app.setPalette(pal)
    except Exception:
        _swallow()
    _boot(45, "باز کردن پایگاه داده…")
    db()
    _boot(55, "مرتب‌سازی حواله‌ها…")
    renumber_invoices_by_date()
    _boot(62, "ساخت صفحه‌های برنامه…")
    w = MainWindow()
    _boot(97, "نمایش برنامه…")
    w.show()
    _boot_finish()
    sys.exit(app.exec())


if __name__=="__main__": main()
