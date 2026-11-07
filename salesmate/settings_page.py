# -*- coding: utf-8 -*-
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
    import app_core as core
except Exception:
    from salesmate import app_core as core
try:
    from app_core import (
    APP_DIR,
    APP_VERSION,
    ATTACHMENTS_DIR,
    DB_PATH,
    DEFAULT_GITHUB_REPO,
    SETTINGS_PATH,
    _swallow,
    _write_updater_script,
    amount,
    db,
    download_update_zip,
    en_digits,
    fa_digits,
    fetch_remote_version_info,
    github_repo_slug,
    is_remote_newer,
    launch_updater_and_exit,
    load_inventory,
    parse_inventory_excel,
    pull_all_from_supabase,
    pull_inventory_from_supabase,
    push_all_to_supabase,
    push_inventory_to_supabase,
    rebuild_customer_colors,
    renumber_invoices_by_date,
    rotate_cloud_local_backup,
    run_in_ui,
    save_inventory,
    save_settings,
    schedule_supabase_sync,
    settings,
    supabase_config,
    supabase_login,
    supabase_logout,
    supabase_session_valid,
    supabase_signup,
    supabase_user_info,
    uit,
)
except Exception:
    from salesmate.app_core import (
    APP_DIR,
    APP_VERSION,
    ATTACHMENTS_DIR,
    DB_PATH,
    DEFAULT_GITHUB_REPO,
    SETTINGS_PATH,
    _swallow,
    _write_updater_script,
    amount,
    db,
    download_update_zip,
    en_digits,
    fa_digits,
    fetch_remote_version_info,
    github_repo_slug,
    is_remote_newer,
    launch_updater_and_exit,
    load_inventory,
    parse_inventory_excel,
    pull_all_from_supabase,
    pull_inventory_from_supabase,
    push_all_to_supabase,
    push_inventory_to_supabase,
    rebuild_customer_colors,
    renumber_invoices_by_date,
    rotate_cloud_local_backup,
    run_in_ui,
    save_inventory,
    save_settings,
    schedule_supabase_sync,
    settings,
    supabase_config,
    supabase_login,
    supabase_logout,
    supabase_session_valid,
    supabase_signup,
    supabase_user_info,
    uit,
)


class SettingsPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        outer.addWidget(scroll)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        scroll.setWidget(content)
        l = QVBoxLayout(content)
        l.setContentsMargins(28, 22, 28, 28)
        l.setSpacing(16)

        t = QLabel("تنظیمات")
        t.setObjectName("pageTitle")
        l.addWidget(t)
        sub = QLabel("پشتیبان‌گیری دستی و ابری")
        sub.setObjectName("hint")
        l.addWidget(sub)

        # ---- نام شرکت ----
        card0 = QFrame()
        card0.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        card0.setObjectName("setCard")
        c0 = QVBoxLayout(card0)
        c0.setContentsMargins(18, 16, 18, 16)
        c0.setSpacing(10)
        h0 = QLabel("نام برنامه")
        h0.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        c0.addWidget(h0)
        self.company = QLineEdit()
        self.company.setText(settings().get("company_name", "SalesMate"))
        self.company.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:10px 12px;}"
        )
        c0.addWidget(self.company)
        save = QPushButton("ذخیره نام")
        save.setCursor(Qt.PointingHandCursor)
        save.setStyleSheet(
            "QPushButton{background:#1565C0;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:12px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        save.clicked.connect(self.save)
        c0.addWidget(save)
        l.addWidget(card0)

        # ---- ظاهر ----
        cardTheme = QFrame()
        cardTheme.setObjectName("setCard")
        cardTheme.setStyleSheet(
            "QFrame#setCard{background:palette(base);border:1px solid #E2E8F0;border-radius:16px;}"
        )
        ct = QVBoxLayout(cardTheme)
        ct.setContentsMargins(18, 16, 18, 16)
        ct.setSpacing(10)
        ht = QLabel("ظاهر برنامه")
        ht.setStyleSheet("font-size:15px;font-weight:700;border:none;background:transparent;")
        ct.addWidget(ht)
        self.dark_mode_chk = QCheckBox("حالت تیره (Dark Mode)")
        self.dark_mode_chk.setChecked(bool(settings().get("dark_mode")))
        self.dark_mode_chk.setStyleSheet("font-weight:600;spacing:8px;")
        def _toggle_dark(on):
            s = settings()
            s["dark_mode"] = bool(on)
            try:
                save_settings(s)
            except Exception:
                try:
                    SETTINGS_PATH.write_text(__import__("json").dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception:
                    _swallow()
            if uit is not None:
                try:
                    uit.apply_theme(QApplication.instance(), "dark" if on else "light")
                    uit.toast("تم تیره فعال شد" if on else "تم روشن فعال شد", "success")
                except Exception:
                    _swallow()
        self.dark_mode_chk.toggled.connect(_toggle_dark)
        ct.addWidget(self.dark_mode_chk)
        tip_t = QLabel("فونت یکپارچه Vazirmatn · رنگ‌ها و فاصله‌ها از سیستم طراحی واحد")
        tip_t.setWordWrap(True)
        tip_t.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        ct.addWidget(tip_t)
        l.addWidget(cardTheme)

        # ---- آپدیت برنامه ----
        cardUpd = QFrame()
        cardUpd.setObjectName("setCard")
        cardUpd.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        cu = QVBoxLayout(cardUpd)
        cu.setContentsMargins(18, 16, 18, 16)
        cu.setSpacing(10)
        hu = QLabel("آپدیت برنامه")
        hu.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        cu.addWidget(hu)
        self.upd_status = QLabel("نسخه فعلی: " + APP_VERSION)
        self.upd_status.setWordWrap(True)
        self.upd_status.setStyleSheet("color:#64748B;font-size:13px;font-weight:700;border:none;background:transparent;")
        cu.addWidget(self.upd_status)
        self.upd_progress = QProgressBar()
        self.upd_progress.setRange(0, 100)
        self.upd_progress.setValue(0)
        self.upd_progress.setTextVisible(True)
        self.upd_progress.setFormat("%p%")
        self.upd_progress.setMinimumHeight(22)
        self.upd_progress.setVisible(False)
        self.upd_progress.setStyleSheet(
            "QProgressBar{border:1px solid #CBD5E1;border-radius:8px;background:#F1F5F9;text-align:center;}"
            "QProgressBar::chunk{background:#1565C0;border-radius:7px;}"
        )
        cu.addWidget(self.upd_progress)
        tip_u = QLabel(
            "آپدیت خودکار نیست. لینک دانلود از آخرین Release گیت‌هاب گرفته می‌شود. قبل از آپدیت پشتیبان محلی گرفته می‌شود."
        )
        tip_u.setWordWrap(True)
        tip_u.setStyleSheet("color:#94A3B8;font-size:11px;border:none;background:transparent;")
        cu.addWidget(tip_u)
        lab_repo = QLabel("ریپوی GitHub (برای پیدا کردن خودکار آخرین Release)")
        lab_repo.setStyleSheet("color:#64748B;font-size:11px;border:none;background:transparent;")
        cu.addWidget(lab_repo)
        self.upd_repo_edit = QLineEdit()
        self.upd_repo_edit.setPlaceholderText("ArashFAQ/SalesMate")
        self.upd_repo_edit.setText(settings().get("github_repo") or DEFAULT_GITHUB_REPO)
        self.upd_repo_edit.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:8px 10px;font-size:12px;}"
        )
        cu.addWidget(self.upd_repo_edit)
        row_u = QHBoxLayout()
        self.btn_check_update = QPushButton("بررسی نسخه")
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.setStyleSheet(
            "QPushButton{background:#0F172A;color:#fff;border:none;border-radius:12px;padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#1E293B;}"
        )
        self.btn_check_update.clicked.connect(self.check_update_now)
        self.btn_do_update = QPushButton("آپدیت (با پشتیبان محلی)")
        self.btn_do_update.setCursor(Qt.PointingHandCursor)
        self.btn_do_update.setEnabled(False)
        self.btn_do_update.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:12px;padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}"
            "QPushButton:disabled{background:#94A3B8;color:#F1F5F9;}"
        )
        self.btn_do_update.clicked.connect(self.do_update_now)
        row_u.addWidget(self.btn_check_update)
        row_u.addWidget(self.btn_do_update)
        cu.addLayout(row_u)
        l.addWidget(cardUpd)
        self._remote_update_info = None

        # ---- موجودی کالا (اکسل مشترک) ----
        cardInv = QFrame()
        cardInv.setObjectName("setCard")
        cardInv.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        ci = QVBoxLayout(cardInv)
        ci.setContentsMargins(18, 16, 18, 16)
        ci.setSpacing(10)
        hi = QLabel("موجودی کالا (اکسل)")
        hi.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        ci.addWidget(hi)
        tip_i = QLabel(
            "فایل اکسل خروجی آمیسا (کد کالا، نام، مانده کارتن و متر) را انتخاب کنید.\n"
            "بعد از ارسال به ابر، همه کاربران در اپ موبایل موجودی را می‌بینند."
        )
        tip_i.setWordWrap(True)
        tip_i.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        ci.addWidget(tip_i)
        self.inv_status = QLabel("")
        self.inv_status.setStyleSheet("color:#0D47A1;font-size:12px;border:none;background:transparent;")
        n_local = len(load_inventory())
        self.inv_status.setText("موجودی محلی: " + fa_digits(n_local) + " قلم")
        ci.addWidget(self.inv_status)
        row_i = QHBoxLayout()
        btn_imp = QPushButton("ورود از اکسل")
        btn_imp.setCursor(Qt.PointingHandCursor)
        btn_imp.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:12px;"
            "padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#047857;}"
        )
        btn_imp.clicked.connect(self.import_inventory_excel)
        btn_push = QPushButton("ارسال موجودی به ابر")
        btn_push.setCursor(Qt.PointingHandCursor)
        btn_push.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:12px;"
            "padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        btn_push.clicked.connect(self.push_inventory_cloud)
        btn_pull = QPushButton("دریافت از ابر")
        btn_pull.setCursor(Qt.PointingHandCursor)
        btn_pull.setStyleSheet(
            "QPushButton{background:#0F172A;color:#fff;border:none;border-radius:12px;"
            "padding:12px;font-weight:700;}"
        )
        btn_pull.clicked.connect(self.pull_inventory_cloud)
        row_i.addWidget(btn_imp)
        row_i.addWidget(btn_push)
        row_i.addWidget(btn_pull)
        ci.addLayout(row_i)
        l.addWidget(cardInv)

        # ---- پشتیبان دستی ----
        card1 = QFrame()
        card1.setObjectName("setCard")
        card1.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        c1 = QVBoxLayout(card1)
        c1.setContentsMargins(18, 16, 18, 16)
        c1.setSpacing(10)
        h1 = QLabel("پشتیبان‌گیری دستی (فایل)")
        h1.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        c1.addWidget(h1)
        d1 = QLabel("فایل ZIP روی کامپیوتر ذخیره یا بازیابی می‌شود.")
        d1.setWordWrap(True)
        d1.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        c1.addWidget(d1)
        row1 = QHBoxLayout()
        row1.setSpacing(10)
        b1 = QPushButton("⬇  پشتیبان ZIP")
        b1.setCursor(Qt.PointingHandCursor)
        b1.setStyleSheet(
            "QPushButton{background:#0F172A;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:14px 12px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#1E293B;}"
        )
        b1.clicked.connect(self.backup)
        b2 = QPushButton("⬆  بازیابی ZIP")
        b2.setCursor(Qt.PointingHandCursor)
        b2.setStyleSheet(
            "QPushButton{background:#E0F2FE;color:#0C4A6E;border:none;border-radius:12px;"
            "padding:14px 12px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#BAE6FD;}"
        )
        b2.clicked.connect(self.restore)
        row1.addWidget(b1)
        row1.addWidget(b2)
        c1.addLayout(row1)
        b1405 = QPushButton("📥 ورود فروش ۱۴۰۵ از فایل")
        b1405.setCursor(Qt.PointingHandCursor)
        b1405.setStyleSheet(
            "QPushButton{background:#059669;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:12px;font-weight:700;font-size:13px;}"
            "QPushButton:hover{background:#047857;}"
        )
        b1405.clicked.connect(self.import_1405_sales)
        c1.addWidget(b1405)
        l.addWidget(card1)

        # ---- ابر ----
        card2 = QFrame()
        card2.setObjectName("setCard")
        card2.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        c2 = QVBoxLayout(card2)
        c2.setContentsMargins(18, 16, 18, 16)
        c2.setSpacing(10)
        h2 = QLabel("پشتیبان‌گیری ابری")
        h2.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        c2.addWidget(h2)
        d2 = QLabel("با ایمیل وارد شوید. داده هر حساب جدا است و با موبایل همگام می‌شود.")
        d2.setWordWrap(True)
        d2.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        c2.addWidget(d2)

        self.sb_email = QLineEdit()
        self.sb_email.setPlaceholderText("ایمیل یا نام کاربری")
        self.sb_email.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:10px 12px;}"
        )
        self.sb_pass = QLineEdit()
        self.sb_pass.setEchoMode(QLineEdit.Password)
        self.sb_pass.setPlaceholderText("رمز عبور")
        self.sb_pass.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:10px 12px;}"
        )
        c2.addWidget(self.sb_email)
        c2.addWidget(self.sb_pass)

        auth_row = QHBoxLayout()
        auth_row.setSpacing(8)
        btn_login = QPushButton("ورود")
        btn_login.setCursor(Qt.PointingHandCursor)
        btn_login.setStyleSheet(
            "QPushButton{background:#1565C0;color:#FFFFFF;border:none;border-radius:10px;"
            "padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        btn_login.clicked.connect(self.supabase_do_login)
        btn_signup = QPushButton("ثبت‌نام")
        btn_signup.setCursor(Qt.PointingHandCursor)
        btn_signup.setStyleSheet(
            "QPushButton{background:#E2E8F0;color:#0F172A;border:none;border-radius:10px;"
            "padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#CBD5E1;}"
        )
        btn_signup.clicked.connect(self.supabase_do_signup)
        btn_logout = QPushButton("خروج")
        btn_logout.setCursor(Qt.PointingHandCursor)
        btn_logout.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#991B1B;border:none;border-radius:10px;"
            "padding:12px;font-weight:700;}"
            "QPushButton:hover{background:#FECACA;}"
        )
        btn_logout.clicked.connect(self.supabase_do_logout)
        auth_row.addWidget(btn_login)
        auth_row.addWidget(btn_signup)
        auth_row.addWidget(btn_logout)
        c2.addLayout(auth_row)

        self.chk_supabase = QCheckBox("فعال بودن همگام آنلاین")
        self.chk_supabase.setChecked(bool(settings().get("supabase_enabled", True)))
        self.chk_supabase.toggled.connect(self.toggle_supabase)
        self.chk_supabase.setStyleSheet("color:#334155;font-weight:600;")
        c2.addWidget(self.chk_supabase)

        self.chk_backup_close = QCheckBox("پشتیبان خودکار هنگام بستن برنامه")
        self.chk_backup_close.setChecked(bool(settings().get("backup_on_close", True)))
        self.chk_backup_close.toggled.connect(self.toggle_backup_on_close)
        self.chk_backup_close.setStyleSheet("color:#334155;font-weight:600;")
        c2.addWidget(self.chk_backup_close)

        self.sb_status = QLabel("")
        self.sb_status.setWordWrap(True)
        self.sb_status.setStyleSheet(
            "font-size:13px;padding:12px;background:#F0F9FF;border-radius:12px;"
            "color:#0C4A6E;border:1px solid #BAE6FD;"
        )
        c2.addWidget(self.sb_status)

        sbrow = QHBoxLayout()
        sbrow.setSpacing(10)
        btn_sb_push = QPushButton("⬆  ارسال به ابر")
        btn_sb_push.setCursor(Qt.PointingHandCursor)
        btn_sb_push.setStyleSheet(
            "QPushButton{background:#1565C0;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:14px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        btn_sb_push.clicked.connect(self.supabase_push)
        btn_sb_pull = QPushButton("⬇  دریافت از ابر")
        btn_sb_pull.setCursor(Qt.PointingHandCursor)
        btn_sb_pull.setStyleSheet(
            "QPushButton{background:#0F172A;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:14px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#1E293B;}"
        )
        btn_sb_pull.clicked.connect(self.supabase_pull)
        sbrow.addWidget(btn_sb_push)
        sbrow.addWidget(btn_sb_pull)
        c2.addLayout(sbrow)
        l.addWidget(card2)

        # ---- پاک‌سازی ----
        # ---- سلامت داده (فقط مالک) ----
        self.card_health = QFrame()
        self.card_health.setObjectName("setCard")
        self.card_health.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        ch = QVBoxLayout(self.card_health)
        ch.setContentsMargins(18, 16, 18, 16)
        ch.setSpacing(8)
        hh_ = QLabel("سلامت داده")
        hh_.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        ch.addWidget(hh_)
        self.health_lbl = QLabel("حواله‌ی تکراری، نام‌های چندگانه، مغایرت فروشگاه و استعلام‌های شبیه حواله را بررسی می‌کند.")
        self.health_lbl.setWordWrap(True)
        self.health_lbl.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        ch.addWidget(self.health_lbl)
        hb = QPushButton("🩺  بررسی سلامت داده")
        hb.setCursor(Qt.PointingHandCursor)
        hb.setStyleSheet(
            "QPushButton{background:#059669;color:#FFFFFF;border:none;border-radius:12px;"
            "padding:14px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#047857;}"
        )
        hb.clicked.connect(self.open_health)
        ch.addWidget(hb)
        l.addWidget(self.card_health)
        try:
            owner = bool(self.win.is_owner_account())
        except Exception:
            owner = True
        self.card_health.setVisible(owner)
        if owner:
            QTimer.singleShot(1500, self._health_quick)

        card3 = QFrame()
        card3.setObjectName("setCard")
        card3.setStyleSheet(
            "QFrame#setCard{background:#FFFFFF;border:1px solid #FECACA;border-radius:16px;}"
        )
        c3 = QVBoxLayout(card3)
        c3.setContentsMargins(18, 16, 18, 16)
        clear_btn = QPushButton("پاک کردن کل اطلاعات محلی")
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#991B1B;border:none;border-radius:12px;"
            "padding:14px;font-weight:700;font-size:14px;}"
            "QPushButton:hover{background:#FECACA;}"
        )
        clear_btn.clicked.connect(self.clear_all_data)
        c3.addWidget(clear_btn)
        l.addWidget(card3)

        l.addStretch()
        self._refresh_sb_status()





    
    def _health_quick(self):
        """شمارش سریع مشکل‌ها هنگام باز شدن تنظیمات (فقط عدد؛ اصلاحی انجام نمی‌شود)."""
        try:
            try:
                import health_core as hc
            except Exception:
                from salesmate import health_core as hc
            c = core.db()
            try:
                sm = hc.summarize(c)
            finally:
                c.close()
            n = sum(len(g) - 1 for g in sm["dup_invoices"]) + len(sm["name_variants"]) + len(sm["bad_invoices"])
            if n:
                self.health_lbl.setText("⚠ %s مورد نیاز به بررسی (حواله‌ی تکراری / نام چندگانه / حواله‌ی ناقص)." % fa_digits(n))
                self.health_lbl.setStyleSheet("color:#B91C1C;font-size:12px;font-weight:700;border:none;background:transparent;")
            else:
                self.health_lbl.setText("✓ در بررسی سریع مشکلی دیده نشد.")
                self.health_lbl.setStyleSheet("color:#047857;font-size:12px;border:none;background:transparent;")
        except Exception:
            pass

    def open_health(self):
        try:
            try:
                from health_page import HealthDialog
            except Exception:
                from salesmate.health_page import HealthDialog
            HealthDialog(self.win).exec()
            self._health_quick()
        except Exception as ex:
            QMessageBox.warning(self, "سلامت داده", "باز نشد:\n" + str(ex))

    def toggle_supabase(self, checked):
        s = settings()
        s["supabase_enabled"] = bool(checked)
        save_settings(s)
        self._refresh_sb_status()

    def toggle_backup_on_close(self, checked):
        s = settings()
        s["backup_on_close"] = bool(checked)
        save_settings(s)

    def _refresh_sb_status(self):
        url, key, en = supabase_config()
        info = supabase_user_info()
        if not en:
            self.sb_status.setText("وضعیت همگام: غیرفعال")
            return
        if supabase_session_valid():
            self.sb_status.setText(
                "وضعیت: وارد شده\nایمیل: {email}\nشناسه کاربر: …{uid}\nداده شما از داده بقیه کاربران جدا است.".format(
                    email=info.get("email") or "—",
                    uid=(info.get("user_id") or "")[-8:],
                )
            )
            if hasattr(self, "sb_email") and info.get("email"):
                self.sb_email.setText(info["email"])
        else:
            self.sb_status.setText(
                "وضعیت: وارد نشده\nثبت‌نام یا ورود کنید تا همگام فقط برای حساب خودتان فعال شود."
            )

    def supabase_do_login(self):
        email = self.sb_email.text().strip()
        password = self.sb_pass.text()
        if not email or not password:
            QMessageBox.warning(self, "ورود", "ایمیل و رمز را وارد کنید.")
            return
        try:
            supabase_login(email, password)
            self.sb_pass.clear()
            self._refresh_sb_status()
            try:
                self.win.apply_role_gating()
                self.win.cw_apply_feed()
                self.win.contacts_page.auto_pull()
            except Exception:
                _swallow()
            QMessageBox.information(self, "ورود", "با موفقیت وارد شدید.")
        except Exception as e:
            QMessageBox.critical(self, "خطا ورود", str(e))

    def supabase_do_signup(self):
        email = self.sb_email.text().strip()
        password = self.sb_pass.text()
        if not email or len(password) < 6:
            QMessageBox.warning(self, "ثبت‌نام", "ایمیل معتبر و رمز حداقل ۶ کاراکتر لازم است.")
            return
        try:
            supabase_signup(email, password)
            self.sb_pass.clear()
            self._refresh_sb_status()
            QMessageBox.information(
                self, "ثبت‌نام",
                "حساب ساخته شد. اگر وارد نشدید و تأیید ایمیل فعال است، ابتدا ایمیل را تأیید کنید."
            )
        except Exception as e:
            QMessageBox.critical(self, "خطا ثبت‌نام", str(e))

    def supabase_do_logout(self):
        supabase_logout()
        self._refresh_sb_status()
        QMessageBox.information(self, "خروج", "از حساب ابری خارج شدید.")

    def import_inventory_excel(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل موجودی اکسل", "",
            "Excel (*.xlsx *.xls);;All (*.*)"
        )
        if not path:
            return
        try:
            items = parse_inventory_excel(path)
            if not items:
                QMessageBox.warning(self, "موجودی", "ردیفی از اکسل خوانده نشد.")
                return
            save_inventory(items, meta={"file": path})
            self.inv_status.setText(
                "موجودی محلی: " + fa_digits(len(items)) + " قلم — آماده ارسال به ابر"
            )
            # خودکار به ابر بفرست اگر لاگین است
            if supabase_session_valid():
                try:
                    n = push_inventory_to_supabase(items)
                    self.inv_status.setText(
                        "ارسال شد: " + fa_digits(n) + " قلم — همه کاربران می‌بینند"
                    )
                    QMessageBox.information(
                        self, "موجودی",
                        fa_digits(n) + " قلم از اکسل خوانده و به ابر ارسال شد.\n"
                        "همه کاربران موبایل می‌توانند موجودی را ببینند."
                    )
                    return
                except Exception as e:
                    QMessageBox.warning(
                        self, "ابر",
                        "اکسل ذخیره شد ولی ارسال به ابر نشد:\n%s\n"
                        "جدول inventory_items را در Supabase بسازید و دوباره «ارسال موجودی به ابر» را بزنید."
                        % e
                    )
                    return
            QMessageBox.information(
                self, "موجودی",
                fa_digits(len(items)) + " قلم ذخیره شد.\n"
                "برای دیدن همه کاربران، وارد ابر شوید و «ارسال موجودی به ابر» را بزنید."
            )
        except Exception as e:
            QMessageBox.critical(self, "خطا", "خواندن اکسل:\n" + str(e))

    def push_inventory_cloud(self):
        items = load_inventory()
        if not items:
            QMessageBox.information(self, "موجودی", "اول از اکسل موجودی را وارد کنید.")
            return
        try:
            n = push_inventory_to_supabase(items)
            self.inv_status.setText("ارسال شد: " + fa_digits(n) + " قلم")
            QMessageBox.information(self, "موجودی", fa_digits(n) + " قلم به ابر ارسال شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

    def pull_inventory_cloud(self):
        try:
            items = pull_inventory_from_supabase()
            self.inv_status.setText("از ابر: " + fa_digits(len(items)) + " قلم")
            QMessageBox.information(self, "موجودی", fa_digits(len(items)) + " قلم از ابر دریافت شد.")
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))

    def _save_update_url(self):
        s = settings()
        s["github_repo"] = (self.upd_repo_edit.text() or "").strip() or DEFAULT_GITHUB_REPO
        save_settings(s)



    def check_update_now(self):
        self._save_update_url()
        if getattr(self, "_check_busy", False):
            return
        self._check_busy = True
        self.upd_status.setText("در حال بررسی نسخه از GitHub…")
        self.upd_status.setStyleSheet(
            "color:#0D47A1;font-size:13px;font-weight:700;border:none;background:transparent;"
        )
        self.btn_do_update.setEnabled(False)
        self._remote_update_info = None
        try:
            self.btn_check_update.setEnabled(False)
        except Exception:
            _swallow()
        try:
            self.upd_progress.setVisible(True)
            self.upd_progress.setRange(0, 0)
        except Exception:
            _swallow()

        # پل امن به UI (حتماً روی main thread ساخته می‌شود)
        bridge = getattr(self, "_check_bridge", None)
        if bridge is None:
            from PySide6.QtCore import QObject, Signal

            class _CheckBridge(QObject):
                finished = Signal(object, object)  # err, info

            bridge = _CheckBridge(self)
            self._check_bridge = bridge

            def _on_finished(err, info):
                self._check_busy = False
                try:
                    self.btn_check_update.setEnabled(True)
                except Exception:
                    _swallow()
                try:
                    self.upd_progress.setVisible(False)
                    self.upd_progress.setRange(0, 100)
                    self.upd_progress.setValue(0)
                except Exception:
                    _swallow()
                if err:
                    self.upd_status.setText("بررسی ناموفق: " + str(err))
                    self.upd_status.setStyleSheet(
                        "color:#DC2626;font-size:13px;border:none;background:transparent;"
                    )
                    QMessageBox.warning(
                        self, "آپدیت",
                        "نتوانست نسخه را از GitHub بخواند.\n\n"
                        "ریپو و Release (Latest) را چک کنید.\n"
                        "اگر اینترنت قطع است یا SSL خطا می‌دهد، VPN/DNS را امتحان کنید.\n\n"
                        + str(err)
                    )
                    return
                remote = str((info or {}).get("version") or "").strip()
                asset = str((info or {}).get("asset_name") or "")
                self._remote_update_info = info
                self.btn_do_update.setEnabled(True)
                if is_remote_newer(APP_VERSION, remote):
                    msg = "نسخه جدید: %s  |  فعلی: %s" % (remote, APP_VERSION)
                    if asset:
                        msg += "\nفایل: " + asset
                    self.upd_status.setText(msg)
                    self.upd_status.setStyleSheet(
                        "color:#059669;font-size:13px;font-weight:700;border:none;background:transparent;"
                    )
                    QMessageBox.information(self, "آپدیت", msg + "\n\nدکمه «آپدیت» را بزنید.")
                else:
                    msg = "برنامه به‌روز است (فعلی: %s ، ابر: %s)." % (APP_VERSION, remote or "—")
                    if asset:
                        msg += "\nفایل: " + asset
                    msg += "\nمی‌توانید دوباره نصب کنید."
                    self.upd_status.setText(msg)
                    self.upd_status.setStyleSheet(
                        "color:#64748B;font-size:13px;border:none;background:transparent;"
                    )
                    QMessageBox.information(self, "آپدیت", msg)

            bridge.finished.connect(_on_finished)

        def _worker():
            err = None
            info = None
            try:
                info = fetch_remote_version_info(timeout=15)
            except Exception as e:
                err = e
            try:
                bridge.finished.emit(err, info)
            except Exception:
                # fallback
                try:
                    run_in_ui(lambda: bridge.finished.emit(err, info))
                except Exception:
                    _swallow()

        threading.Thread(target=_worker, daemon=True).start()

        def _watchdog():
            if not getattr(self, "_check_busy", False):
                return
            self._check_busy = False
            try:
                self.btn_check_update.setEnabled(True)
            except Exception:
                _swallow()
            try:
                self.upd_progress.setVisible(False)
                self.upd_progress.setRange(0, 100)
            except Exception:
                _swallow()
            self.upd_status.setText("بررسی قطع شد. دوباره تلاش کنید.")
            self.upd_status.setStyleSheet(
                "color:#DC2626;font-size:13px;border:none;background:transparent;"
            )
            try:
                repo = str(github_repo_slug())
            except Exception:
                repo = ""
            QMessageBox.warning(
                self,
                "آپدیت",
                "پاسخی از GitHub نیامد (بیش از 90 ثانیه).\n"
                "اینترنت، فیلتر یا SSL را بررسی کنید.\n"
                "آدرس ریپو: " + repo,
            )

        QTimer.singleShot(90000, _watchdog)

    def _patch_update(self, info):
        """آپدیت سبک: فقط zip کوچک کد دانلود می‌شود (چند صد کیلوبایت)."""
        self._update_busy = True
        self.btn_do_update.setEnabled(False)
        self.upd_status.setText("دانلود آپدیت سبک…")
        try:
            self.upd_progress.setVisible(True)
            self.upd_progress.setRange(0, 0)
        except Exception:
            _swallow()
        ver = str(info.get("version") or "")
        url = str(info.get("patch_url") or "")

        def _work():
            err = None
            try:
                try:
                    core.rotate_cloud_local_backup(max_keep=5, force=True)
                except Exception:
                    _swallow()
                core.apply_code_patch(url, ver)
            except Exception as e:
                err = e

            def _done():
                self._update_busy = False
                self.btn_do_update.setEnabled(True)
                try:
                    self.upd_progress.setVisible(False)
                    self.upd_progress.setRange(0, 100)
                except Exception:
                    _swallow()
                if err:
                    self.upd_status.setText("آپدیت سبک انجام نشد")
                    QMessageBox.warning(self, "آپدیت", "آپدیت سبک انجام نشد:\n" + str(err))
                    return
                self.upd_status.setText("نسخه " + ver + " نصب شد")
                r = QMessageBox.question(
                    self, "آپدیت",
                    "نسخه " + ver + " نصب شد.\nبرنامه الان دوباره باز شود؟",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if r == QMessageBox.Yes:
                    core.restart_app()
                    QApplication.quit()

            run_in_ui(_done)

        threading.Thread(target=_work, daemon=True).start()

    def do_update_now(self):
        if getattr(self, "_update_busy", False):
            QMessageBox.information(self, "آپدیت", "دانلود در حال انجام است؛ صبر کنید.")
            return

        def _start_with_info(info):
            if str((info or {}).get("patch_url") or "").strip():
                try:
                    pj_ok = True
                    if pj_ok:
                        self._patch_update(info)
                        return
                except Exception:
                    _swallow()
            url = str((info or {}).get("download_url") or (info or {}).get("url") or "").strip()
            if not url:
                QMessageBox.warning(self, "آپدیت", "لینک دانلود پیدا نشد. اول «بررسی نسخه» را بزنید.")
                return
            ret = QMessageBox.question(
                self, "آپدیت",
                "۱) پشتیبان کامل محلی\n"
                "۲) دانلود نسخه جدید (نوار پیشرفت را ببینید)\n"
                "۳) بستن و نصب خودکار\n\n"
                "ادامه؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes,
            )
            if ret != QMessageBox.Yes:
                return

            self._update_busy = True
            self.btn_do_update.setEnabled(False)
            try:
                self.btn_check_update.setEnabled(False)
            except Exception:
                _swallow()
            self.upd_status.setText("شروع آپدیت…")
            self.upd_status.setStyleSheet(
                "color:#0D47A1;font-size:13px;font-weight:700;border:none;background:transparent;"
            )
            try:
                self.upd_progress.setVisible(True)
                self.upd_progress.setRange(0, 100)
                self.upd_progress.setValue(0)
            except Exception:
                _swallow()

            ver = str(info.get("version") or "new")
            lower = url.lower().split("?")[0]
            work = APP_DIR / "_update_work"
            work.mkdir(parents=True, exist_ok=True)
            if lower.endswith(".exe"):
                dest = work / ("SalesMate_" + ver + ".exe")
            else:
                dest = work / ("SalesMate_" + ver + ".zip")

            # سیگنال امن برای UI از thread
            bridge = getattr(self, "_upd_bridge", None)
            if bridge is None:
                from PySide6.QtCore import QObject, Signal

                class _UpdBridge(QObject):
                    status = Signal(str)
                    progress = Signal(int)
                    finished = Signal(object, object, object, object)  # err, bak, dest, bat

                bridge = _UpdBridge()
                self._upd_bridge = bridge

                def _on_status(msg):
                    try:
                        self.upd_status.setText(msg)
                        self.upd_status.setStyleSheet(
                            "color:#0D47A1;font-size:13px;font-weight:700;border:none;background:transparent;"
                        )
                    except Exception:
                        _swallow()

                def _on_progress(pct):
                    try:
                        self.upd_progress.setVisible(True)
                        if pct < 0:
                            self.upd_progress.setRange(0, 0)
                        else:
                            if self.upd_progress.maximum() == 0:
                                self.upd_progress.setRange(0, 100)
                            self.upd_progress.setValue(max(0, min(100, int(pct))))
                    except Exception:
                        _swallow()

                def _on_finished(err, bak, dest_path, bat_path=None):
                    self._update_busy = False
                    try:
                        self.btn_check_update.setEnabled(True)
                    except Exception:
                        _swallow()
                    try:
                        self.upd_progress.setRange(0, 100)
                        self.upd_progress.setValue(100)
                    except Exception:
                        _swallow()
                    if err:
                        self.btn_do_update.setEnabled(True)
                        try:
                            self.upd_progress.setVisible(False)
                        except Exception:
                            _swallow()
                        self.upd_status.setText("آپدیت ناموفق")
                        self.upd_status.setStyleSheet(
                            "color:#DC2626;font-size:13px;border:none;background:transparent;"
                        )
                        QMessageBox.critical(self, "خطا", "آپدیت انجام نشد:\n" + str(err))
                        return
                    self.upd_status.setText("در حال نصب — برنامه بسته می‌شود…")
                    self.upd_status.setStyleSheet(
                        "color:#059669;font-size:13px;font-weight:700;border:none;background:transparent;"
                    )
                    try:
                        if bat_path:
                            bat = Path(bat_path)
                        else:
                            bat = _write_updater_script(Path(dest_path))
                    except Exception as e:
                        self.btn_do_update.setEnabled(True)
                        QMessageBox.critical(self, "خطا", "ساخت نصب‌کننده:\n" + str(e))
                        return
                    try:
                        launch_updater_and_exit(bat)
                    except Exception as e:
                        self.btn_do_update.setEnabled(True)
                        QMessageBox.critical(self, "خطا", "اجرای نصب:\n" + str(e))

                bridge.status.connect(_on_status)
                bridge.progress.connect(_on_progress)
                bridge.finished.connect(_on_finished)

            def _worker():
                err = None
                bak = None
                try:
                    bridge.status.emit("پشتیبان محلی…")
                    bridge.progress.emit(-1)
                    try:
                        bak = rotate_cloud_local_backup(max_keep=5, force=True)
                    except Exception:
                        bak = None
                    bridge.status.emit("دانلود از GitHub…")
                    bridge.progress.emit(0)

                    last_pct = [-1]

                    def progress(done, total):
                        if total and total > 0:
                            pct = int(100 * done / total)
                            if pct != last_pct[0]:
                                last_pct[0] = pct
                                mb = done / (1024 * 1024)
                                tmb = total / (1024 * 1024)
                                bridge.status.emit("دانلود… %s٪  (%.1f از %.1f مگ)" % (fa_digits(pct), mb, tmb))
                                bridge.progress.emit(pct)
                        else:
                            mb = done / (1024 * 1024)
                            bridge.status.emit("دانلود… %.1f مگ" % mb)
                            bridge.progress.emit(-1)

                    download_update_zip(url, dest, progress_cb=progress)
                    try:
                        sz = dest.stat().st_size
                    except Exception:
                        sz = 0
                    if sz < 1_000_000:
                        raise RuntimeError(
                            "فایل دانلود شده خیلی کوچک است (%s بایت).\nدانلود ناقص یا لینک اشتباه." % sz
                        )
                    bridge.status.emit("آماده نصب…")
                    bridge.progress.emit(100)
                    bat_path = _write_updater_script(dest)
                except Exception as e:
                    err = e
                    bat_path = None
                bridge.finished.emit(err, bak, dest, bat_path)

            threading.Thread(target=_worker, daemon=True).start()

        info = self._remote_update_info
        if not info or not (info.get("download_url") or info.get("patch_url")):
            # خودش بررسی کند
            self.upd_status.setText("در حال گرفتن لینک دانلود…")
            try:
                self.upd_progress.setVisible(True)
                self.upd_progress.setRange(0, 0)
            except Exception:
                _swallow()

            def _fetch():
                err = None
                info2 = None
                try:
                    info2 = fetch_remote_version_info(timeout=20)
                except Exception as e:
                    err = e

                def _done():
                    try:
                        self.upd_progress.setRange(0, 100)
                    except Exception:
                        _swallow()
                    if err:
                        try:
                            self.upd_progress.setVisible(False)
                        except Exception:
                            _swallow()
                        QMessageBox.warning(self, "آپدیت", "لینک دانلود گرفته نشد:\n" + str(err))
                        return
                    self._remote_update_info = info2
                    _start_with_info(info2)

                run_in_ui(_done)

            threading.Thread(target=_fetch, daemon=True).start()
            return

        _start_with_info(info)

    def supabase_push(self):
        if not supabase_session_valid():
            QMessageBox.warning(self, "ابر", "ابتدا وارد حساب ابر شوید.")
            return
        self.upd_status_msg = getattr(self, "upd_status", None)
        QMessageBox.information(
            self, "ارسال به ابر",
            "ارسال در پس‌زمینه شروع شد.\n"
            "می‌توانید با برنامه کار کنید؛ پایان با پیام اعلام می‌شود."
        )

        def _worker():
            err = None
            ts = ""
            try:
                ts = push_all_to_supabase()
            except Exception as e:
                err = e

            def _done():
                if err:
                    QMessageBox.critical(
                        self, "خطا",
                        str(err) + "\n\nاگر طول کشید یا قطع شد، دوباره «ارسال به ابر» را بزنید."
                    )
                else:
                    QMessageBox.information(
                        self, "Supabase",
                        "داده حساب شما به ابر ارسال شد.\n" + str(ts)
                    )
                try:
                    self._refresh_sb_status()
                except Exception:
                    _swallow()

            run_in_ui(_done)

        threading.Thread(target=_worker, daemon=True).start()


    def supabase_pull(self):
        pass
        if core._local_dirty:
            ret = QMessageBox.question(
                self, "دریافت از ابر",
                "تغییرات محلی هنوز کامل به ابر نرسیده.\nاول ارسال می‌شود، بعد دریافت.\nادامه؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
            )
            if ret != QMessageBox.Yes:
                return
            try:
                push_all_to_supabase()
            except Exception as e:
                QMessageBox.warning(self, "ارسال", "اول ارسال نشد:\n%s" % e)
                return
        elif QMessageBox.question(
            self, "دریافت از ابر",
            "داده این کامپیوتر با داده ابر (فقط حساب خودتان) جایگزین می‌شود. ادامه؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            return
        try:
            ts = pull_all_from_supabase()
            if hasattr(self.win, "refresh_all"):
                self.win.refresh_all()
            else:
                try:
                    self.win.home()
                except Exception:
                    _swallow()
            QMessageBox.information(self, "Supabase", "داده حساب شما از ابر دریافت شد.\n" + str(ts))
        except Exception as e:
            QMessageBox.critical(self, "خطا", str(e))





    def _write_backup_zip(self, path: Path):
        import zipfile
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            if DB_PATH.exists():
                z.write(DB_PATH, "salesmate.db")
            if SETTINGS_PATH.exists():
                z.write(SETTINGS_PATH, "settings.json")
            inq = APP_DIR / "inquiries.json"
            if inq.exists():
                z.write(inq, "inquiries.json")
            if ATTACHMENTS_DIR.exists():
                for p in ATTACHMENTS_DIR.rglob("*"):
                    if p.is_file():
                        try:
                            z.write(p, Path("attachments") / p.relative_to(ATTACHMENTS_DIR).as_posix())
                        except Exception:
                            z.write(p, Path("attachments") / p.name)
            meta = {
                "app": "SalesMate",
                "backed_up_at": datetime.now().isoformat(timespec="seconds"),
            }
            z.writestr("backup_meta.json", json.dumps(meta, ensure_ascii=False, indent=2))

    def _restore_backup_zip(self, path: Path):
        import zipfile
        with zipfile.ZipFile(path) as z:
            if "salesmate.db" in z.namelist():
                z.extract("salesmate.db", APP_DIR)
            if "settings.json" in z.namelist():
                z.extract("settings.json", APP_DIR)
            if "inquiries.json" in z.namelist():
                z.extract("inquiries.json", APP_DIR)
            for n in z.namelist():
                if n.startswith("attachments/") and not n.endswith("/"):
                    z.extract(n, APP_DIR)
        renumber_invoices_by_date()



    def save(self):
        s=settings()
        s["company_name"]=self.company.text().strip() or "SalesMate"
        save_settings(s)
        QMessageBox.information(self,"SalesMate","تنظیمات ذخیره شد.")
    def backup(self):
        path,_=QFileDialog.getSaveFileName(self,"ذخیره پشتیبان","SalesMate_Backup.zip","ZIP (*.zip)")
        if not path: return
        try:
            self._write_backup_zip(Path(path))
            QMessageBox.information(self,"SalesMate","پشتیبان شامل دیتابیس، استعلام‌ها و عکس حواله‌ها ذخیره شد.")
        except Exception as ex:
            QMessageBox.critical(self,"خطا",str(ex))
    def restore(self):
        path,_=QFileDialog.getOpenFileName(self,"انتخاب پشتیبان","","ZIP (*.zip)")
        if not path: return
        if QMessageBox.question(self,"تأیید","اطلاعات فعلی با پشتیبان جایگزین شود؟")==QMessageBox.Yes:
            try:
                self._restore_backup_zip(Path(path))
                self.win.refresh_all()
                QMessageBox.information(self,"SalesMate","اطلاعات و عکس‌های حواله‌ها بازیابی شدند.")
            except Exception as ex:
                QMessageBox.critical(self,"خطا",str(ex))


    def import_1405_sales(self):
        """افزودن حواله‌های فروش ۱۴۰۵ از فایل JSON کنار برنامه (بدون پاک کردن بقیه)."""
        candidates = [
            APP_DIR / "import_1405_invoices.json",
            Path(__file__).resolve().parent.parent / "import_1405_invoices.json",
            Path(__file__).resolve().parent / "import_1405_invoices.json",
        ]
        src = next((p for p in candidates if p.exists()), None)
        if not src:
            path, _ = QFileDialog.getOpenFileName(
                self, "انتخاب فایل فروش ۱۴۰۵", str(APP_DIR), "JSON (*.json)"
            )
            if not path:
                return
            src = Path(path)
        try:
            rows = json.loads(src.read_text(encoding="utf-8"))
        except Exception as ex:
            QMessageBox.critical(self, "ورود داده", f"خواندن فایل ممکن نشد:\n{ex}")
            return
        if not isinstance(rows, list) or not rows:
            QMessageBox.warning(self, "ورود داده", "فایل خالی یا نامعتبر است.")
            return
        if QMessageBox.question(
            self, "ورود داده",
            f"{fa_digits(len(rows))} حواله از فایل افزوده شود؟\n"
            "حواله‌هایی که همان شماره را دارند دوباره اضافه نمی‌شوند."
        ) != QMessageBox.Yes:
            return
        c = db()
        added = 0
        skipped = 0
        try:
            for r in rows:
                inv_no = str(r.get("invoiceNo") or r.get("invoice_no") or "").strip()
                customer = str(r.get("customer") or "").strip()
                date = en_digits(str(r.get("date") or "").strip())
                total = str(amount(r.get("total") or 0))
                if not inv_no or not customer or not date:
                    skipped += 1
                    continue
                exists = c.execute(
                    "SELECT 1 FROM invoices WHERE invoice_no=? LIMIT 1", (inv_no,)
                ).fetchone()
                if exists:
                    skipped += 1
                    continue
                note = str(r.get("note") or "")
                cartons = r.get("cartons")
                inquiry = ""
                if cartons not in (None, "") or note:
                    # ذخیره توضیح در inquiry_data ساده
                    meta = {"tab": "parquet", "rows": [], "note": note}
                    if cartons not in (None, ""):
                        meta["rows"] = [{"qty1": core.qty_int(cartons), "type": note or "پارکت", "code": "", "price": "", "cost": total}]
                    inquiry = json.dumps(meta, ensure_ascii=False)
                c.execute(
                    "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                    "VALUES(?,?,?,?,?,?,?,?,?)",
                    (
                        customer, inv_no, date, "12:00:00", total,
                        datetime.now().isoformat(timespec="seconds"),
                        "", inquiry, "",
                    ),
                )
                added += 1
            c.commit()
        except Exception as ex:
            QMessageBox.critical(self, "ورود داده", str(ex))
            return
        finally:
            c.close()
        try:
            renumber_invoices_by_date()
        except Exception:
            _swallow()
        try:
            self.win.refresh_all()
        except Exception:
            _swallow()
        try:
            schedule_supabase_sync()
        except Exception:
            _swallow()
        QMessageBox.information(
            self, "ورود داده",
            f"افزوده شد: {fa_digits(added)}\nرد شد (تکراری/نامعتبر): {fa_digits(skipped)}"
        )


    def clear_all_data(self):
        r1 = QMessageBox.question(
            self, "هشدار",
            "همه حواله‌ها و عکس‌ها برای همیشه حذف می‌شوند.\nآیا مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if r1 != QMessageBox.Yes:
            return
        r2 = QMessageBox.question(
            self, "تأیید نهایی",
            "این عمل قابل بازگشت نیست (مگر از پشتیبان).\nحذف کامل انجام شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if r2 != QMessageBox.Yes:
            return
        try:
            c = db()
            c.execute("DELETE FROM invoices")
            c.commit()
            c.close()
            if ATTACHMENTS_DIR.exists():
                for p in ATTACHMENTS_DIR.rglob("*"):
                    if p.is_file():
                        try:
                            p.unlink()
                        except Exception:
                            _swallow()
            rebuild_customer_colors()
            self.win.refresh_all()
            QMessageBox.information(self, "SalesMate", "همه اطلاعات پاک شد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"پاک‌سازی انجام نشد:\n{ex}")
