# -*- coding: utf-8 -*-
"""صفحه‌ی «بالانس موجودی» — بخش بومی خود برنامه (بدون وب).

منطق در inventory_core.py است؛ اینجا فقط رابط کاربری، ذخیره‌ی محلی و همگام‌سازی نگاشت با ابر.
نگاشت‌ها و آخرین داده‌های خوانده‌شده در فایل inventory_balance.json کنار برنامه ذخیره می‌شوند.
"""
import json
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QObject, Signal, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, QTabWidget, QTabBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDoubleSpinBox, QCheckBox,
    QSplitter, QMessageBox, QFileDialog, QDialog, QMenu, QApplication, QSizePolicy, QScrollArea,
)

try:
    import inventory_core as ic
    from core_utils import fa_digits, en_digits
    from app_log import swallow as _swallow
except Exception:  # pragma: no cover
    from salesmate import inventory_core as ic
    from salesmate.core_utils import fa_digits, en_digits
    from salesmate.app_log import swallow as _swallow

STORE_NAME = "inventory_balance.json"

BTN = {
    "pri": "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:9px;padding:7px 14px;font-weight:700;}"
           "QPushButton:hover{background:#0D47A1;}QPushButton:disabled{background:#94A3B8;}",
    "ok": "QPushButton{background:#16A34A;color:#fff;border:none;border-radius:9px;padding:7px 14px;font-weight:700;}"
          "QPushButton:hover{background:#15803D;}QPushButton:disabled{background:#94A3B8;}",
    "bad": "QPushButton{background:#FEE2E2;color:#B91C1C;border:none;border-radius:9px;padding:7px 12px;font-weight:700;}"
           "QPushButton:hover{background:#FECACA;}",
    "sec": "QPushButton{background:#F1F5F9;color:#0F172A;border:1px solid #E2E8F0;border-radius:9px;padding:7px 12px;font-weight:700;}"
           "QPushButton:hover{background:#E2E8F0;}QPushButton:disabled{color:#94A3B8;}",
}


def _btn(text, kind="sec", tip=""):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(BTN[kind])
    if tip:
        b.setToolTip(tip)
    return b


class _SortItem(QTableWidgetItem):
    """سلول جدول با کلید مرتب‌سازی دلخواه (عدد واقعی، نه متن)."""

    def __init__(self, text, key=None, align=Qt.AlignCenter):
        super().__init__(text)
        self._k = text if key is None else key
        self.setTextAlignment(align)

    def __lt__(self, other):
        try:
            return self._k < other._k
        except Exception:
            return super().__lt__(other)


def _num_item(v, d=3):
    return _SortItem(fa_digits(("%." + str(d) + "f") % v), float(v))


class _Bridge(QObject):
    done = Signal(object)


class FileSlot(QFrame):
    """جعبه‌ی انتخاب فایل (کلیک یا کشیدن‌ورها کردن). سیگنال: picked(path)."""
    picked = Signal(str)
    cleared = Signal()
    warn_clicked = Signal()

    def __init__(self, title):
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("slot")
        self.setStyleSheet("QFrame#slot{border:2px dashed #CBD5E1;border-radius:10px;background:#fff;}"
                           "QFrame#slot[ok='true']{border:2px solid #86EFAC;background:#F0FDF4;}"
                           "QFrame#slot[err='true']{border:2px solid #FCA5A5;background:#FEF2F2;}"
                           "QFrame#slot[hover='true']{border:2px dashed #1565C0;background:#EFF6FF;}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("font-weight:800;color:#0F172A;border:none;background:transparent;")
        self.lbl_status = QLabel("فایلی انتخاب نشده — کلیک کنید یا فایل را اینجا رها کنید")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        row = QHBoxLayout()
        self.btn_pick = _btn("انتخاب فایل…", "sec")
        self.btn_warn = _btn("⚠", "bad", "هشدارهای خواندن فایل")
        self.btn_warn.hide()
        self.btn_clear = _btn("✕", "sec", "پاک‌کردن داده‌ی این فایل")
        self.btn_clear.setFixedWidth(34)
        row.addWidget(self.btn_pick)
        row.addWidget(self.btn_warn)
        row.addStretch(1)
        row.addWidget(self.btn_clear)
        lay.addWidget(self.lbl_title)
        lay.addWidget(self.lbl_status)
        lay.addLayout(row)
        self.btn_pick.clicked.connect(self._choose)
        self.btn_clear.clicked.connect(lambda: self.cleared.emit())
        self.btn_warn.clicked.connect(lambda: self.warn_clicked.emit())
        self.last_dir = ""

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.lbl_title.text(), self.last_dir, "Excel / CSV (*.xlsx *.xlsm *.xltx *.xls *.csv);;همه‌ی فایل‌ها (*.*)")
        if path:
            self.picked.emit(path)

    def _set_state(self, name):
        for k in ("ok", "err", "hover"):
            self.setProperty(k, "true" if k == name else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_status(self, text, ok=None, warnings=0, tip=""):
        self.lbl_status.setText(text)
        self.setToolTip(tip)
        self._set_state("ok" if ok is True else ("err" if ok is False else ""))
        self.btn_warn.setVisible(bool(warnings))
        if warnings:
            self.btn_warn.setText("⚠ " + fa_digits(warnings))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and not self.btn_pick.underMouse() and not self.btn_clear.underMouse() \
                and not self.btn_warn.underMouse():
            self._choose()
        super().mousePressEvent(ev)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()
            self._set_state("hover")

    def dragLeaveEvent(self, ev):
        self._set_state("")

    def dropEvent(self, ev):
        self._set_state("")
        for u in ev.mimeData().urls():
            p = u.toLocalFile()
            if p:
                self.picked.emit(p)
                break


class InventoryBalancePage(QWidget):
    def __init__(self, win, app_dir, cloud=None):
        super().__init__()
        self.win = win
        self.cloud = cloud or {}
        self.path = Path(app_dir) / STORE_NAME
        self.store = ic.load_store(self.path)
        self.system = self.store.get("system") or {}
        self.warehouse = self.store.get("warehouse") or {}
        self.mappings = self.store.get("mappings") or {}
        self.threshold = float(self.store.get("threshold") or 0.0)
        self.results = []
        self.selected = set()            # (انبار, کد سامانه) برای اظهار خروج
        self.warnings = {}               # کلید فایل → لیست هشدار
        self.active_wh = next((w for w in ic.WAREHOUSES if self.system.get(w)), ic.WAREHOUSES[0])
        self._free_rank = {}
        self._cloud_busy = False
        self._cloud_checked_session = False
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_bg_done)
        self._push_timer = QTimer(self)
        self._push_timer.setSingleShot(True)
        self._push_timer.timeout.connect(lambda: self.sync_maps(manual=False))
        self.setLayoutDirection(Qt.RightToLeft)
        self._build()
        for k, v in (self.store.get("files") or {}).items():
            self.warnings[k] = v.get("warnings") or []
        self._refresh_all()

    # ───────────────────────── ساخت UI ─────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel("⚖️ بالانس موجودی — سامانه ↔ انبار")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#0F172A;")
        head.addWidget(title)
        head.addStretch(1)
        self.lbl_cloud = QLabel("")
        self.lbl_cloud.setStyleSheet("color:#64748B;font-size:12px;")
        head.addWidget(self.lbl_cloud)
        self.btn_sync = _btn("☁ همگام‌سازی نگاشت", "sec", "ارسال/دریافت نگاشت‌ها با ابر (نگاشت اصلی روی همین سیستم ذخیره است)")
        self.btn_sync.clicked.connect(lambda: self.sync_maps(manual=True))
        head.addWidget(self.btn_sync)
        self.btn_io = _btn("⇅ نگاشت (فایل)", "sec")
        menu = QMenu(self)
        menu.addAction("خروجی نگاشت‌ها (JSON)").triggered.connect(self.export_maps_json)
        menu.addAction("ورودی نگاشت‌ها از فایل JSON").triggered.connect(self.import_maps_json)
        self.btn_io.setMenu(menu)
        head.addWidget(self.btn_io)
        btn_save = _btn("💾 ذخیره", "ok")
        btn_save.clicked.connect(lambda: self._save(toast="ذخیره شد"))
        head.addWidget(btn_save)
        root.addLayout(head)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrollable(self._build_files_tab(), 560), "۱) فایل‌ها")
        self.tabs.addTab(self._scrollable(self._build_map_tab(), 880), "۲) نگاشت کدها")
        self.tabs.addTab(self._scrollable(self._build_result_tab(), 860), "۳) مقایسه و خروجی")
        self.tabs.currentChanged.connect(self._on_tab)
        root.addWidget(self.tabs, 1)

    @staticmethod
    def _scrollable(content, min_h):
        """هر تب داخل یک اسکرول عمودی: جدول‌ها ارتفاع کافی (۱۰+ ردیف) دارند و اگر پنجره کوتاه بود کل صفحه اسکرول می‌شود."""
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        content.setMinimumHeight(min_h)
        sc.setWidget(content)
        return sc

    def _build_files_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel("برای هر انبار فایل «سامانه» و فایل «انبار» را انتخاب کنید (یا روی کادر رها کنید). فایل بلافاصله خوانده می‌شود؛ "
                      "نیازی به دکمه‌ی جداگانه نیست. داده‌ها و نگاشت‌ها روی همین سیستم می‌مانند و دفعه‌ی بعد دوباره باز می‌شوند.")
        info.setWordWrap(True)
        info.setStyleSheet("background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:8px;color:#1E40AF;")
        lay.addWidget(info)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        grid.addWidget(QLabel(""), 0, 0)
        h1, h2 = QLabel("📋 سامانه"), QLabel("🏭 انبار")
        for h in (h1, h2):
            h.setStyleSheet("font-weight:800;font-size:14px;")
            h.setAlignment(Qt.AlignCenter)
        grid.addWidget(h1, 0, 1)
        grid.addWidget(h2, 0, 2)
        self.slots = {}
        for r, wh in enumerate(ic.WAREHOUSES, 1):
            lbl = QLabel(wh)
            lbl.setStyleSheet("font-weight:800;font-size:15px;color:#0D47A1;")
            grid.addWidget(lbl, r, 0)
            for c, kind in ((1, "sys"), (2, "wh")):
                key = "%s-%s" % (kind, ic.WH_KEYS[wh])
                slot = FileSlot(("سامانه — " if kind == "sys" else "انبار — ") + wh)
                slot.picked.connect(lambda p, k=kind, n=wh: self._load_file(k, n, p))
                slot.cleared.connect(lambda k=kind, n=wh: self._clear_slot(k, n))
                slot.warn_clicked.connect(lambda k=key: self._show_warnings(k))
                grid.addWidget(slot, r, c)
                self.slots[key] = slot
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        lay.addLayout(grid)
        row = QHBoxLayout()
        self.btn_reread = _btn("↻ خواندن دوباره‌ی همه‌ی فایل‌ها", "pri", "فایل‌ها را از مسیر قبلی دوباره می‌خواند (بعد از بروزرسانی اکسل‌ها)")
        self.btn_reread.clicked.connect(self.reread_all)
        btn_clear = _btn("پاک‌کردن همه‌ی داده‌ها (نگاشت‌ها می‌مانند)", "bad")
        btn_clear.clicked.connect(self.clear_all_data)
        row.addWidget(self.btn_reread)
        row.addStretch(1)
        row.addWidget(btn_clear)
        lay.addLayout(row)
        self.lbl_files_info = QLabel("")
        self.lbl_files_info.setStyleSheet("color:#64748B;")
        lay.addWidget(self.lbl_files_info)
        lay.addStretch(1)
        return w

    def _build_map_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.wh_tabs = QTabBar()
        self.wh_tabs.setExpanding(False)
        for n in ic.WAREHOUSES:
            self.wh_tabs.addTab(n)
        self.wh_tabs.currentChanged.connect(self._on_wh_tab)
        top.addWidget(self.wh_tabs)
        top.addStretch(1)
        self.ed_sys_search = QLineEdit()
        self.ed_sys_search.setPlaceholderText("جستجوی کد یا شرح سامانه…")
        self.ed_sys_search.setClearButtonEnabled(True)
        self.ed_sys_search.setMinimumWidth(240)
        self.ed_sys_search.textChanged.connect(lambda *_: self._fill_sys())
        top.addWidget(self.ed_sys_search)
        self.cmb_sys_filter = QComboBox()
        self.cmb_sys_filter.addItems(["همه", "بدون نگاشت", "نگاشت‌شده"])
        self.cmb_sys_filter.currentIndexChanged.connect(lambda *_: self._fill_sys())
        top.addWidget(self.cmb_sys_filter)
        self.btn_suggest = _btn("✨ پیشنهاد خودکار", "pri", "برای کدهای بدون نگاشت، بهترین کد انبار آزاد را از روی ابعاد و شرح پیشنهاد می‌دهد")
        self.btn_suggest.clicked.connect(self.open_suggestions)
        top.addWidget(self.btn_suggest)
        lay.addLayout(top)

        # ── بالا: کالاهای سامانه (تمام‌عرض)
        top_w = QWidget()
        tl = QVBoxLayout(top_w)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(4)
        self.tbl_sys = QTableWidget(0, 6)
        self.tbl_sys.setHorizontalHeaderLabels(["", "کد سامانه", "شرح سامانه", "سامانه m³", "تعداد کد انبار", "جمع انبار m³"])
        self._style_table(self.tbl_sys)
        hh = self.tbl_sys.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for c in (0, 1, 3, 4, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tbl_sys.itemSelectionChanged.connect(self._on_sys_selected)
        self.tbl_sys.setMinimumHeight(180)          # حدود ۶ ردیف (نصف نسخه‌ی قبل)
        tl.addWidget(self.tbl_sys, 1)
        self.lbl_sys_info = QLabel("")
        self.lbl_sys_info.setStyleSheet("color:#64748B;")
        tl.addWidget(self.lbl_sys_info)
        lay.addWidget(top_w, 1)

        # ── پایین: شرح کالای انتخاب‌شده + دو جدول کنار هم (نگاشت‌شده | آزاد)
        bottom = QFrame()
        bottom.setObjectName("bp")
        bottom.setStyleSheet("QFrame#bp{background:#fff;border:1px solid #E2E8F0;border-radius:12px;}")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.setSpacing(6)
        self.lbl_cur = QLabel("یک کالای سامانه را از جدول بالا انتخاب کنید")
        self.lbl_cur.setWordWrap(True)
        self.lbl_cur.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_cur.setStyleSheet("font-weight:700;font-size:13px;color:#0F172A;background:#F0F9FF;"
                                   "border:1px solid #BAE6FD;border-radius:8px;padding:6px 10px;")
        bl.addWidget(self.lbl_cur)

        hs = QSplitter(Qt.Horizontal)
        hs.setChildrenCollapsible(False)
        hs.setHandleWidth(8)
        hs.setStyleSheet("QSplitter::handle{background:#E2E8F0;border-radius:3px;margin:30px 0;}"
                         "QSplitter::handle:hover{background:#1565C0;}")
        # نگاشت‌شده‌ها
        mw = QWidget()
        ml = QVBoxLayout(mw)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(4)
        ml.addWidget(self._small("✅ کدهای انبارِ نگاشت‌شده به این کالا (موجودی‌ها جمع می‌شوند)"))
        self.tbl_mapped = QTableWidget(0, 3)
        self.tbl_mapped.setHorizontalHeaderLabels(["کد انبار", "نام کالا در انبار", "m³"])
        self._style_table(self.tbl_mapped)
        mh = self.tbl_mapped.horizontalHeader()
        mh.setSectionResizeMode(1, QHeaderView.Stretch)
        mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl_mapped.itemSelectionChanged.connect(lambda: self._update_detail(self.tbl_mapped, 1))
        self.tbl_mapped.setMinimumHeight(300)
        ml.addWidget(self.tbl_mapped, 1)
        self.btn_unmap = _btn("حذف کد انتخاب‌شده از نگاشت", "bad")
        self.btn_unmap.clicked.connect(self.remove_selected_mapped)
        ml.addWidget(self.btn_unmap)
        hs.addWidget(mw)
        # آزادها
        fw = QWidget()
        fl = QVBoxLayout(fw)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(4)
        frow = QHBoxLayout()
        frow.addWidget(self._small("➕ کدهای انبارِ آزاد — شبیه‌ترین‌ها بالا؛ دابل‌کلیک = افزودن"))
        frow.addStretch(1)
        self.lbl_free_info = QLabel("")
        self.lbl_free_info.setStyleSheet("color:#64748B;font-size:12px;border:none;")
        frow.addWidget(self.lbl_free_info)
        self.ed_free_search = QLineEdit()
        self.ed_free_search.setPlaceholderText("جستجوی کد یا نام انبار…")
        self.ed_free_search.setClearButtonEnabled(True)
        self.ed_free_search.setMinimumWidth(220)
        self.ed_free_search.textChanged.connect(lambda *_: self._fill_free())
        frow.addWidget(self.ed_free_search)
        fl.addLayout(frow)
        self.tbl_free = QTableWidget(0, 4)
        self.tbl_free.setHorizontalHeaderLabels(["شباهت", "کد انبار", "نام کالا در انبار", "m³"])
        self._style_table(self.tbl_free, multi=True)
        fh = self.tbl_free.horizontalHeader()
        fh.setSectionResizeMode(2, QHeaderView.Stretch)
        for c in (0, 1, 3):
            fh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tbl_free.cellDoubleClicked.connect(lambda *_: self.add_selected_free())
        self.tbl_free.itemSelectionChanged.connect(lambda: self._update_detail(self.tbl_free, 2))
        self.tbl_free.setMinimumHeight(300)
        fl.addWidget(self.tbl_free, 1)
        arow = QHBoxLayout()
        self.btn_add = _btn("＋ افزودن انتخاب‌شده‌ها", "ok")
        self.btn_add.clicked.connect(self.add_selected_free)
        self.chk_next = QCheckBox("بعد از افزودن، برو به کالای بعدیِ بدون نگاشت")
        self.chk_next.setChecked(True)
        arow.addWidget(self.btn_add)
        arow.addWidget(self.chk_next)
        arow.addStretch(1)
        fl.addLayout(arow)
        hs.addWidget(fw)
        hs.setStretchFactor(0, 2)
        hs.setStretchFactor(1, 3)
        hs.setSizes([420, 700])
        bl.addWidget(hs, 1)

        self.lbl_detail = QLabel("روی یک ردیف کلیک کنید تا نام کامل کالای انبار اینجا نوشته شود.")
        self.lbl_detail.setWordWrap(True)
        self.lbl_detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_detail.setStyleSheet("color:#334155;background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;padding:5px 10px;")
        bl.addWidget(self.lbl_detail)
        lay.addWidget(bottom, 4)
        return w

    def _update_detail(self, table, name_col):
        """نام کامل ردیف انتخاب‌شده (جدول‌ها نام‌های بلند را کوتاه نشان می‌دهند)."""
        try:
            r = table.currentRow()
            it = table.item(r, name_col) if r is not None and r >= 0 else None
            if it is None:
                return
            code_it = table.item(r, 1 if name_col == 2 else 0)
            code = code_it.text() if code_it is not None else ""
            self.lbl_detail.setText("کد انبار %s — %s" % (code, it.text() or "—"))
        except Exception:
            _swallow()

    def _build_result_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        top.addWidget(QLabel("نادیده‌گرفتن اختلاف زیر:"))
        self.spn_th = QDoubleSpinBox()
        self.spn_th.setDecimals(2)
        self.spn_th.setRange(0.0, 100000.0)
        self.spn_th.setSingleStep(0.5)
        self.spn_th.setSuffix(" m³")
        self.spn_th.setValue(self.threshold)
        self.spn_th.valueChanged.connect(self._on_threshold)
        top.addWidget(self.spn_th)
        top.addSpacing(12)
        top.addWidget(QLabel("تاریخ سند:"))
        self.ed_date = QLineEdit(self.store.get("docDate") or self._today())
        self.ed_date.setFixedWidth(110)
        self.ed_date.editingFinished.connect(self._on_date)
        top.addWidget(self.ed_date)
        top.addStretch(1)
        self.btn_sel_dec = _btn("تیک کاهش سامانه", "sec")
        self.btn_sel_dec.clicked.connect(self.select_decreases)
        self.btn_sel_none = _btn("لغو تیک", "sec")
        self.btn_sel_none.clicked.connect(self.clear_selection)
        self.btn_khoroj = _btn("📤 اظهار خروج (xlsx)", "pri")
        self.btn_khoroj.clicked.connect(self.export_khoroj)
        self.btn_pdf = _btn("📄 PDF", "sec")
        self.btn_pdf.clicked.connect(self.export_pdf)
        self.btn_xlsx = _btn("⬇ اکسل کامل", "sec")
        self.btn_xlsx.clicked.connect(self.export_xlsx)
        for b in (self.btn_sel_dec, self.btn_sel_none, self.btn_khoroj, self.btn_pdf, self.btn_xlsx):
            top.addWidget(b)
        lay.addLayout(top)

        self.stats_row = QHBoxLayout()
        self.stat_lbls = {}
        for key, text, color in (("total", "کل", "#0F172A"), ("balanced", "بالانس", "#16A34A"), ("add", "افزایش سامانه", "#1565C0"),
                                 ("sub", "کاهش سامانه", "#DC2626"), ("unmapped", "بدون نگاشت", "#D97706")):
            card = QFrame()
            card.setStyleSheet("QFrame{background:#fff;border:1px solid #E2E8F0;border-radius:10px;}")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 6, 10, 6)
            cl.setSpacing(0)
            v = QLabel("۰")
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet("font-size:20px;font-weight:900;color:%s;border:none;" % color)
            t = QLabel(text)
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet("color:#64748B;font-size:12px;border:none;")
            cl.addWidget(v)
            cl.addWidget(t)
            self.stat_lbls[key] = v
            self.stats_row.addWidget(card)
        lay.addLayout(self.stats_row)

        flt = QHBoxLayout()
        self.ed_res_search = QLineEdit()
        self.ed_res_search.setPlaceholderText("جستجو: کد، شرح، انبار…")
        self.ed_res_search.setClearButtonEnabled(True)
        self.ed_res_search.textChanged.connect(lambda *_: self._fill_results())
        flt.addWidget(self.ed_res_search, 1)
        self.cmb_res_filter = QComboBox()
        self.cmb_res_filter.addItems(["همه", "بالانس", "افزایش سامانه", "کاهش سامانه", "بدون نگاشت"])
        self.cmb_res_filter.currentIndexChanged.connect(lambda *_: self._fill_results())
        flt.addWidget(self.cmb_res_filter)
        self.cmb_res_wh = QComboBox()
        self.cmb_res_wh.addItem("همه‌ی انبارها")
        self.cmb_res_wh.addItems(ic.WAREHOUSES)
        self.cmb_res_wh.currentIndexChanged.connect(lambda *_: self._fill_results())
        flt.addWidget(self.cmb_res_wh)
        self.lbl_sel = QLabel("۰ انتخاب")
        self.lbl_sel.setStyleSheet("color:#0D47A1;font-weight:800;")
        flt.addWidget(self.lbl_sel)
        lay.addLayout(flt)

        self.tbl_res = QTableWidget(0, 9)
        self.tbl_res.setHorizontalHeaderLabels(["", "انبار", "کد سامانه", "شرح", "کد انبار", "سامانه m³", "انبار m³", "اختلاف", "اقدام"])
        self._style_table(self.tbl_res)
        hh = self.tbl_res.horizontalHeader()
        hh.setSectionResizeMode(3, QHeaderView.Stretch)
        for c in (0, 1, 2, 4, 5, 6, 7, 8):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.tbl_res.itemChanged.connect(self._on_res_item_changed)
        self.tbl_res.setMinimumHeight(440)
        lay.addWidget(self.tbl_res, 1)
        self.lbl_res_info = QLabel("")
        self.lbl_res_info.setStyleSheet("color:#64748B;")
        lay.addWidget(self.lbl_res_info)
        return w

    @staticmethod
    def _small(text):
        l = QLabel(text)
        l.setStyleSheet("color:#64748B;font-size:12px;border:none;")
        l.setWordWrap(True)
        return l

    @staticmethod
    def _style_table(t, multi=False):
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setSelectionMode(QTableWidget.ExtendedSelection if multi else QTableWidget.SingleSelection)
        t.setAlternatingRowColors(True)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(26)      # ردیف‌های فشرده‌تر = ردیف بیشتر در دید
        t.setWordWrap(False)
        t.setLayoutDirection(Qt.RightToLeft)
        t.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        t.setSortingEnabled(True)

    # ───────────────────────── کمک‌ها ─────────────────────────
    @staticmethod
    def _today():
        n = datetime.now()
        try:
            from core_utils import gregorian_to_jalali
        except Exception:  # pragma: no cover
            from salesmate.core_utils import gregorian_to_jalali
        y, m, d = gregorian_to_jalali(n.year, n.month, n.day)
        return "%04d/%02d/%02d" % (y, m, d)

    def _toast(self, msg, kind="info"):
        try:
            if hasattr(self.win, "show_app_toast"):
                self.win.show_app_toast(msg, kind)
                return
        except Exception:
            _swallow()
        try:
            self.win.statusBar().showMessage(str(msg), 4000)
        except Exception:
            _swallow()

    def _save(self, toast=None, touch_maps=False):
        try:
            self.store["system"] = self.system
            self.store["warehouse"] = self.warehouse
            self.store["mappings"] = ic.normalize_mappings(self.mappings)
            self.mappings = self.store["mappings"]
            self.store["threshold"] = float(self.threshold)
            self.store["docDate"] = self.ed_date.text().strip()
            if touch_maps:
                ic.touch_maps(self.store)
            ic.save_store(self.path, self.store)
            try:  # نتیجه‌ی بالانس برای اپ موبایل هم به ابر برود
                try:
                    import app_core as _core
                except Exception:
                    from salesmate import app_core as _core
                _core.schedule_supabase_sync()
            except Exception:
                _swallow()
            if toast:
                self._toast(toast, "ok")
            return True
        except Exception as ex:
            _swallow()
            QMessageBox.critical(self, "ذخیره", "ذخیره‌ی محلی انجام نشد:\n" + str(ex))
            return False

    def _maps_changed(self):
        """بعد از هر تغییر نگاشت: ذخیره‌ی محلی (فوری) و ارسال به ابر با تأخیر."""
        self._save(touch_maps=True)
        if self._cloud_ok() and self.store.get("autoCloud", True):
            self._push_timer.start(2500)
        self._update_cloud_label()

    def _run_bg(self, fn, cb):
        def work():
            try:
                res = (fn(), None)
            except Exception as ex:
                res = (None, ex)
            self._bridge.done.emit((cb, res))
        threading.Thread(target=work, daemon=True).start()

    def _on_bg_done(self, payload):
        try:
            cb, res = payload
            cb(*res)
        except Exception:
            _swallow()

    # ───────────────────────── فایل‌ها ─────────────────────────
    def _slot_key(self, kind, wh):
        return "%s-%s" % (kind, ic.WH_KEYS[wh])

    def _load_file(self, kind, wh, path):
        key = self._slot_key(kind, wh)
        slot = self.slots[key]
        try:
            rows, info = ic.read_table(path)
            if kind == "sys":
                items, warns = ic.parse_system_rows(rows)
                self.system[wh] = items
            else:
                items, warns = ic.parse_warehouse_rows(rows)
                self.warehouse[wh] = items
        except ic.FileFormatError as ex:
            slot.set_status("✗ " + str(ex).split("\n")[0], False)
            QMessageBox.warning(self, "خواندن فایل", "%s\n\n%s" % (Path(path).name, ex))
            return False
        except Exception as ex:
            _swallow()
            slot.set_status("✗ خطا در خواندن فایل", False)
            QMessageBox.warning(self, "خواندن فایل", "%s\n\nخطا: %s" % (Path(path).name, ex))
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.store.setdefault("files", {})[key] = {
            "path": str(path), "name": Path(path).name, "rows": len(items), "readAt": now,
            "format": info.get("format", ""), "warnings": warns[:200]}
        self.warnings[key] = warns
        self.store["dataReadAt"] = now
        self.store["lastDir"] = str(Path(path).parent)
        self.mappings.setdefault(wh, {})
        self._save()
        self.active_wh = wh if (kind == "sys" or not self.system.get(self.active_wh)) else self.active_wh
        self._refresh_all()
        self._toast("%s خوانده شد: %s ردیف" % (Path(path).name, fa_digits(len(items))), "ok" if items else "warning")
        return True

    def _clear_slot(self, kind, wh):
        key = self._slot_key(kind, wh)
        if QMessageBox.question(self, "پاک‌کردن", "داده‌ی این فایل (%s — %s) پاک شود؟\nنگاشت‌ها دست نمی‌خورند." % (
                "سامانه" if kind == "sys" else "انبار", wh)) != QMessageBox.Yes:
            return
        (self.system if kind == "sys" else self.warehouse).pop(wh, None)
        self.store.get("files", {}).pop(key, None)
        self.warnings.pop(key, None)
        self._save()
        self._refresh_all()

    def clear_all_data(self):
        if QMessageBox.question(self, "پاک‌کردن", "همه‌ی داده‌های خوانده‌شده‌ی سامانه و انبار پاک شود؟\n(نگاشت‌ها می‌مانند)") != QMessageBox.Yes:
            return
        self.system.clear()
        self.warehouse.clear()
        self.store["files"] = {}
        self.warnings = {}
        self._save()
        self._refresh_all()

    def reread_all(self):
        files = self.store.get("files") or {}
        ok = fail = 0
        for wh in ic.WAREHOUSES:
            for kind in ("sys", "wh"):
                f = files.get(self._slot_key(kind, wh))
                if not f:
                    continue
                if not os.path.exists(f.get("path", "")):
                    self.slots[self._slot_key(kind, wh)].set_status("✗ فایل در مسیر قبلی نیست: " + f.get("name", ""), False)
                    fail += 1
                    continue
                if self._load_file(kind, wh, f["path"]):
                    ok += 1
                else:
                    fail += 1
        if not ok and not fail:
            self._toast("هنوز فایلی انتخاب نشده", "warning")
        else:
            self._toast("خوانده شد: %s فایل  |  ناموفق: %s" % (fa_digits(ok), fa_digits(fail)), "ok" if not fail else "warning")

    def _show_warnings(self, key):
        warns = self.warnings.get(key) or []
        if not warns:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("هشدارهای خواندن فایل")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(760, 420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(self._small("این ردیف‌ها خوانده شدند ولی ممکن است موجودی‌شان صفر یا ناقص حساب شده باشد:"))
        tb = QTableWidget(len(warns), 1)
        tb.setHorizontalHeaderLabels(["هشدار"])
        tb.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tb.setEditTriggers(QTableWidget.NoEditTriggers)
        for i, w in enumerate(warns):
            tb.setItem(i, 0, QTableWidgetItem(w))
        lay.addWidget(tb, 1)
        b = _btn("بستن", "sec")
        b.clicked.connect(dlg.accept)
        lay.addWidget(b)
        dlg.exec()

    def _refresh_slots(self):
        files = self.store.get("files") or {}
        last_dir = self.store.get("lastDir", "")
        for wh in ic.WAREHOUSES:
            for kind in ("sys", "wh"):
                key = self._slot_key(kind, wh)
                slot = self.slots[key]
                slot.last_dir = last_dir
                f = files.get(key)
                items = (self.system if kind == "sys" else self.warehouse).get(wh) or []
                if f and items:
                    warns = len(self.warnings.get(key) or [])
                    slot.set_status("✓ %s\n%s ردیف · خوانده شده: %s" % (f.get("name", ""), fa_digits(len(items)), fa_digits(f.get("readAt", ""))),
                                    True, warns, f.get("path", ""))
                elif items:
                    slot.set_status("✓ %s ردیف (از حافظه)" % fa_digits(len(items)), True)
                else:
                    slot.set_status("فایلی انتخاب نشده — کلیک کنید یا فایل را اینجا رها کنید", None)
        if self.store.get("dataReadAt"):
            self.lbl_files_info.setText("آخرین خواندن داده: " + fa_digits(self.store["dataReadAt"]) +
                                        " — برای اطلاعات به‌روز، اکسل‌های جدید را انتخاب کنید یا «خواندن دوباره» را بزنید.")
        else:
            self.lbl_files_info.setText("هنوز فایلی خوانده نشده.")

    # ───────────────────────── نگاشت ─────────────────────────
    def _on_tab(self, idx):
        if idx == 1:
            self._fill_sys()
        elif idx == 2:
            self._recompute()

    def _on_wh_tab(self, idx):
        if 0 <= idx < len(ic.WAREHOUSES):
            self.active_wh = ic.WAREHOUSES[idx]
            self._fill_sys()

    def _refresh_wh_tabs(self):
        self.wh_tabs.blockSignals(True)
        for i, n in enumerate(ic.WAREHOUSES):
            ns, nw = len(self.system.get(n) or []), len(self.warehouse.get(n) or [])
            mapped = sum(1 for s in (self.system.get(n) or []) if (self.mappings.get(n) or {}).get(ic.norm_code(s["code"])))
            self.wh_tabs.setTabText(i, "%s  (%s/%s · نگاشت %s)" % (n, fa_digits(ns), fa_digits(nw), fa_digits(mapped)))
        self.wh_tabs.setCurrentIndex(ic.WAREHOUSES.index(self.active_wh))
        self.wh_tabs.blockSignals(False)

    def _wh_by_code(self, wh):
        return {ic.norm_code(w["code"]): w for w in (self.warehouse.get(wh) or [])}

    def _fill_sys(self):
        wh = self.active_wh
        keep = self._cur_sys_code()
        q = en_digits(self.ed_sys_search.text() or "").strip().lower()
        flt = self.cmb_sys_filter.currentIndex()
        maps = self.mappings.get(wh) or {}
        by = self._wh_by_code(wh)
        self.tbl_sys.blockSignals(True)
        self.tbl_sys.setSortingEnabled(False)
        self.tbl_sys.setRowCount(0)
        shown = 0
        for s in (self.system.get(wh) or []):
            sc = ic.norm_code(s["code"])
            codes = maps.get(sc) or []
            if flt == 1 and codes:
                continue
            if flt == 2 and not codes:
                continue
            if q and q not in sc.lower() and q not in (s.get("desc") or "").lower():
                continue
            total = sum((by.get(ic.norm_code(c)) or {}).get("qty", 0.0) for c in codes)
            r = self.tbl_sys.rowCount()
            self.tbl_sys.insertRow(r)
            mark = _SortItem("✓" if codes else "○", 1 if codes else 0)
            mark.setForeground(QColor("#16A34A" if codes else "#D97706"))
            self.tbl_sys.setItem(r, 0, mark)
            code_item = _SortItem(sc, int(sc) if sc.isdigit() else 0)
            code_item.setData(Qt.UserRole, sc)
            self.tbl_sys.setItem(r, 1, code_item)
            d = QTableWidgetItem(s.get("desc") or "")
            d.setToolTip(s.get("desc") or "")
            self.tbl_sys.setItem(r, 2, d)
            self.tbl_sys.setItem(r, 3, _num_item(s["qty"]))
            self.tbl_sys.setItem(r, 4, _SortItem(fa_digits(len(codes)), len(codes)))
            ti = _num_item(total)
            if codes:
                diff = round(total - s["qty"], 3)
                ti.setToolTip("اختلاف با سامانه: %s" % fa_digits("%.3f" % diff))
            self.tbl_sys.setItem(r, 5, ti)
            shown += 1
        self.tbl_sys.setSortingEnabled(True)
        self.tbl_sys.blockSignals(False)
        total_n = len(self.system.get(wh) or [])
        unm = sum(1 for s in (self.system.get(wh) or []) if not maps.get(ic.norm_code(s["code"])))
        self.lbl_sys_info.setText("نمایش %s از %s کالا · بدون نگاشت: %s" % (fa_digits(shown), fa_digits(total_n), fa_digits(unm))
                                  if total_n else "برای این انبار فایل سامانه خوانده نشده است (تب «فایل‌ها»).")
        self._refresh_wh_tabs()
        if keep:
            self._select_sys_code(keep)
        else:
            self._on_sys_selected()

    def _cur_sys_code(self):
        r = self.tbl_sys.currentRow()
        if r is None or r < 0:
            return ""
        it = self.tbl_sys.item(r, 1)
        return it.data(Qt.UserRole) if it is not None else ""

    def _select_sys_code(self, code):
        for r in range(self.tbl_sys.rowCount()):
            it = self.tbl_sys.item(r, 1)
            if it is not None and it.data(Qt.UserRole) == code:
                self.tbl_sys.selectRow(r)
                self.tbl_sys.scrollToItem(it)
                return True
        self._on_sys_selected()
        return False

    def _sys_item(self, code):
        for s in (self.system.get(self.active_wh) or []):
            if ic.norm_code(s["code"]) == code:
                return s
        return None

    def _on_sys_selected(self):
        code = self._cur_sys_code()
        s = self._sys_item(code) if code else None
        self.tbl_mapped.setRowCount(0)
        self.tbl_free.setRowCount(0)
        if not s:
            self.lbl_cur.setText("یک کالای سامانه را از جدول بالا انتخاب کنید")
            self.lbl_free_info.setText("")
            self.lbl_detail.setText("روی یک ردیف کلیک کنید تا نام کامل کالای انبار اینجا نوشته شود.")
            return
        self.lbl_cur.setText("کالای سامانه %s — %s   |   موجودی: %s m³" % (
            fa_digits(code), s.get("desc") or "—", fa_digits("%.3f" % s["qty"])))
        by = self._wh_by_code(self.active_wh)
        codes = (self.mappings.get(self.active_wh) or {}).get(code) or []
        self.tbl_mapped.setSortingEnabled(False)
        for c in codes:
            w = by.get(ic.norm_code(c))
            r = self.tbl_mapped.rowCount()
            self.tbl_mapped.insertRow(r)
            ci = QTableWidgetItem(fa_digits(c))
            ci.setData(Qt.UserRole, c)
            self.tbl_mapped.setItem(r, 0, ci)
            nm = QTableWidgetItem((w or {}).get("name") or "⚠ در فایل انبار نیست")
            nm.setToolTip(nm.text())
            if not w:
                nm.setForeground(QColor("#DC2626"))
            self.tbl_mapped.setItem(r, 1, nm)
            self.tbl_mapped.setItem(r, 2, _num_item((w or {}).get("qty", 0.0)))
        self.tbl_mapped.setSortingEnabled(True)
        self._rank_free(s)
        self._fill_free()

    def _free_items(self):
        wh = self.active_wh
        used = ic.used_codes(self.mappings, wh)
        return [w for w in (self.warehouse.get(wh) or []) if ic.norm_code(w["code"]) not in used]

    def _rank_free(self, sys_item):
        self._free_rank = {ic.norm_code(w["code"]): (sc, why) for sc, why, w in ic.rank_free_codes(sys_item, self._free_items())}

    def _fill_free(self):
        code = self._cur_sys_code()
        q = en_digits(self.ed_free_search.text() or "").strip().lower()
        free = self._free_items()
        self.tbl_free.setSortingEnabled(False)
        self.tbl_free.setRowCount(0)
        shown = 0
        for w in free:
            wc = ic.norm_code(w["code"])
            if q and q not in wc.lower() and q not in (w.get("name") or "").lower():
                continue
            sc, why = self._free_rank.get(wc, (0.0, ""))
            r = self.tbl_free.rowCount()
            self.tbl_free.insertRow(r)
            star = _SortItem(("⭐ " if sc >= 0.8 else "") + fa_digits("%d%%" % round(sc * 100)) if code else "—", sc)
            star.setToolTip(why or "")
            if sc >= 0.8:
                star.setForeground(QColor("#16A34A"))
            self.tbl_free.setItem(r, 0, star)
            ci = _SortItem(fa_digits(wc), int(wc) if wc.isdigit() else 0)
            ci.setData(Qt.UserRole, wc)
            self.tbl_free.setItem(r, 1, ci)
            nm = QTableWidgetItem(w.get("name") or "")
            nm.setToolTip(w.get("name") or "")
            self.tbl_free.setItem(r, 2, nm)
            self.tbl_free.setItem(r, 3, _num_item(w.get("qty", 0.0)))
            shown += 1
        self.tbl_free.setSortingEnabled(True)
        if code:
            self.tbl_free.sortItems(0, Qt.DescendingOrder)
        self.lbl_free_info.setText("آزاد: %s از %s · در نگاشت: %s" % (
            fa_digits(shown), fa_digits(len(self.warehouse.get(self.active_wh) or [])),
            fa_digits(len(ic.used_codes(self.mappings, self.active_wh)))))

    def _selected_rows(self, table):
        return sorted({i.row() for i in table.selectedItems()})

    def add_selected_free(self):
        code = self._cur_sys_code()
        if not code:
            QMessageBox.information(self, "نگاشت", "ابتدا یک کالای سامانه را از جدول انتخاب کنید.")
            return
        rows = self._selected_rows(self.tbl_free)
        if not rows:
            QMessageBox.information(self, "نگاشت", "از «کدهای انبار آزاد» یک یا چند ردیف را انتخاب کنید.")
            return
        codes = [self.tbl_free.item(r, 1).data(Qt.UserRole) for r in rows]
        added, errors = ic.add_mapping(self.mappings, self.active_wh, code, codes)
        if errors:
            QMessageBox.warning(self, "نگاشت", "\n".join(errors[:6]))
        if added:
            self._maps_changed()
            self._after_mapping_change(code, go_next=self.chk_next.isChecked())

    def remove_selected_mapped(self):
        code = self._cur_sys_code()
        rows = self._selected_rows(self.tbl_mapped)
        if not code or not rows:
            QMessageBox.information(self, "نگاشت", "از «کدهای انبار نگاشت‌شده» یک ردیف را انتخاب کنید.")
            return
        for r in rows:
            ic.remove_mapping(self.mappings, self.active_wh, code, self.tbl_mapped.item(r, 0).data(Qt.UserRole))
        self._maps_changed()
        self._after_mapping_change(code, go_next=False)

    def _after_mapping_change(self, code, go_next=False):
        nxt = ""
        if go_next:
            nxt = self._next_unmapped_after(code)
        self._fill_sys()
        self._select_sys_code(nxt or code)
        self._refresh_wh_tabs()

    def _next_unmapped_after(self, code):
        maps = self.mappings.get(self.active_wh) or {}
        rows = self.tbl_sys.rowCount()
        start = self.tbl_sys.currentRow()
        for step in range(1, rows + 1):
            r = (start + step) % rows if rows else 0
            it = self.tbl_sys.item(r, 1)
            if it is None:
                continue
            c = it.data(Qt.UserRole)
            if c != code and not maps.get(c):
                return c
        return ""

    def open_suggestions(self):
        wh = self.active_wh
        sug = ic.suggest_mappings(self.system.get(wh) or [], self.warehouse.get(wh) or [], self.mappings, wh)
        if not sug:
            QMessageBox.information(self, "پیشنهاد خودکار", "پیشنهاد مطمئنی برای کدهای بدون نگاشتِ این انبار پیدا نشد.\n"
                                    "(برای پیشنهاد، شرح کالا باید ابعاد یا کلمات مشترک با نام انبار داشته باشد.)")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("پیشنهاد خودکار نگاشت — " + wh)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(1000, 560)
        lay = QVBoxLayout(dlg)
        lay.addWidget(self._small("پیشنهادها فقط بر اساس شباهت شرح/ابعاد/کد است؛ تیک‌های مورد تأیید را نگه دارید. ⭐ = شباهت بالا. "
                                  "هر کد انبار فقط به یک کالا پیشنهاد می‌شود."))
        tb = QTableWidget(len(sug), 6)
        tb.setHorizontalHeaderLabels(["", "کد سامانه", "شرح سامانه", "کد انبار", "نام انبار", "شباهت"])
        tb.setEditTriggers(QTableWidget.NoEditTriggers)
        tb.verticalHeader().setVisible(False)
        hh = tb.horizontalHeader()
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        for c in (0, 1, 3, 5):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        for i, s in enumerate(sug):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if s["score"] >= 0.8 else Qt.Unchecked)
            tb.setItem(i, 0, chk)
            tb.setItem(i, 1, QTableWidgetItem(fa_digits(s["sys_code"])))
            tb.setItem(i, 2, QTableWidgetItem(s["sys_desc"]))
            tb.setItem(i, 3, QTableWidgetItem(fa_digits(s["wh_code"])))
            tb.setItem(i, 4, QTableWidgetItem(s["wh_name"]))
            it = QTableWidgetItem(("⭐ " if s["score"] >= 0.8 else "") + fa_digits("%d%%" % round(s["score"] * 100)) + "  " + s["why"])
            tb.setItem(i, 5, it)
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        b_all = _btn("انتخاب همه", "sec")
        b_all.clicked.connect(lambda: [tb.item(i, 0).setCheckState(Qt.Checked) for i in range(tb.rowCount())])
        b_none = _btn("لغو همه", "sec")
        b_none.clicked.connect(lambda: [tb.item(i, 0).setCheckState(Qt.Unchecked) for i in range(tb.rowCount())])
        b_ok = _btn("افزودن تیک‌خورده‌ها به نگاشت", "ok")
        b_cancel = _btn("بستن", "sec")
        b_cancel.clicked.connect(dlg.reject)

        def apply():
            n = 0
            for i, s in enumerate(sug):
                if tb.item(i, 0).checkState() == Qt.Checked:
                    a, _e = ic.add_mapping(self.mappings, wh, s["sys_code"], [s["wh_code"]])
                    n += a
            dlg.accept()
            if n:
                self._maps_changed()
                self._fill_sys()
                self._toast("%s نگاشت اضافه شد" % fa_digits(n), "ok")
        b_ok.clicked.connect(apply)
        for b in (b_all, b_none):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        lay.addLayout(row)
        dlg.exec()

    # ───────────────────────── مقایسه ─────────────────────────
    def _on_threshold(self, v):
        self.threshold = float(v)
        self._recompute(save=True)

    def _on_date(self):
        self._save()

    def _recompute(self, save=False):
        self.results = ic.compare(self.system, self.warehouse, self.mappings, self.threshold)
        keys = {(r["warehouse"], r["sysCode"]) for r in self.results if r["diff"] < 0}
        self.selected &= keys
        if save:
            self._save()
        self._fill_results()

    def _filtered_results(self):
        q = en_digits(self.ed_res_search.text() or "").strip().lower()
        f = self.cmb_res_filter.currentIndex()
        wh = self.cmb_res_wh.currentText()
        out = []
        for r in self.results:
            st = ic.result_status(r)
            if f == 1 and st != "balanced":
                continue
            if f == 2 and st != "add":
                continue
            if f == 3 and st != "sub":
                continue
            if f == 4 and st != "unmapped":
                continue
            if wh in ic.WAREHOUSES and r["warehouse"] != wh:
                continue
            if q and q not in r["sysCode"].lower() and q not in (r["whCode"] or "").lower() and q not in (r["desc"] or "").lower() \
                    and q not in r["warehouse"]:
                continue
            out.append(r)
        return out

    def _fill_results(self):
        st = ic.result_stats(self.results)
        for k, lbl in self.stat_lbls.items():
            lbl.setText(fa_digits(st[k]))
        lst = self._filtered_results()
        t = self.tbl_res
        t.blockSignals(True)
        t.setSortingEnabled(False)
        t.setRowCount(0)
        for r in lst:
            row = t.rowCount()
            t.insertRow(row)
            key = (r["warehouse"], r["sysCode"])
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if key in self.selected else Qt.Unchecked)
            chk.setData(Qt.UserRole, key)
            t.setItem(row, 0, chk)
            t.setItem(row, 1, _SortItem(r["warehouse"]))
            t.setItem(row, 2, _SortItem(fa_digits(r["sysCode"]), int(r["sysCode"]) if r["sysCode"].isdigit() else 0))
            d = QTableWidgetItem(r["desc"] or "—")
            d.setToolTip(r["desc"] or "")
            t.setItem(row, 3, d)
            wc = QTableWidgetItem(fa_digits(r["whCode"]) if r["mapped"] else "—")
            tip = r["whName"] or ""
            if r["missing"]:
                tip += "\n⚠ کد(های) %s در فایل انبار پیدا نشد (موجودی صفر حساب شد)" % "، ".join(r["missing"])
                wc.setForeground(QColor("#DC2626"))
            wc.setToolTip(tip)
            t.setItem(row, 4, wc)
            t.setItem(row, 5, _num_item(r["sysQty"]))
            t.setItem(row, 6, _num_item(r["whQty"]))
            di = _SortItem("۰" if r["diff"] == 0 else fa_digits("%.3f" % r["diff"]), r["diff"])
            di.setForeground(QColor("#DC2626" if r["diff"] < 0 else ("#16A34A" if r["diff"] > 0 else "#64748B")))
            if r["diff"] == 0 and r["rawDiff"] != 0:
                di.setToolTip("اختلاف واقعی %s (کمتر از آستانه؛ صفر حساب شد)" % fa_digits("%.3f" % r["rawDiff"]))
            t.setItem(row, 7, di)
            act = QTableWidgetItem(r["action"])
            act.setForeground(QColor("#64748B" if not r["mapped"] else "#0F172A"))
            t.setItem(row, 8, act)
        t.setSortingEnabled(True)
        t.sortItems(7, Qt.AscendingOrder)
        t.blockSignals(False)
        self._update_sel_label()
        self.lbl_res_info.setText("نمایش %s از %s ردیف" % (fa_digits(len(lst)), fa_digits(len(self.results))) if self.results
                                  else "هنوز مقایسه‌ای نیست؛ فایل‌ها را بخوانید و کدها را نگاشت کنید.")

    def _on_res_item_changed(self, item):
        if item.column() != 0:
            return
        key = item.data(Qt.UserRole)
        if not key:
            return
        if item.checkState() == Qt.Checked:
            self.selected.add(tuple(key))
        else:
            self.selected.discard(tuple(key))
        self._update_sel_label()

    def _update_sel_label(self):
        n = len(self.selected)
        tot = 0.0
        by = {(r["warehouse"], r["sysCode"]): r for r in self.results}
        for k in self.selected:
            if k in by:
                tot += ic.decrease_qty(by[k]) if by[k]["diff"] < 0 else 0.0
        self.lbl_sel.setText("%s انتخاب%s" % (fa_digits(n), (" · جمع کاهش " + fa_digits("%.3f" % tot) + " m³") if n else ""))

    def select_decreases(self):
        self.selected = {(r["warehouse"], r["sysCode"]) for r in self.results if r["diff"] < 0 and r["sysCode"]}
        self._fill_results()

    def clear_selection(self):
        self.selected.clear()
        self._fill_results()

    def _selected_results(self):
        by = {(r["warehouse"], r["sysCode"]): r for r in self.results}
        return [by[k] for k in sorted(self.selected) if k in by]

    # ───────────────────────── خروجی‌ها ─────────────────────────
    def _ask_save(self, title, default_name, flt):
        d = self.store.get("lastExportDir") or str(Path.home())
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path(d) / default_name), flt)
        if path:
            self.store["lastExportDir"] = str(Path(path).parent)
            self._save()
        return path

    def _after_export(self, path, msg):
        box = QMessageBox(self)
        box.setWindowTitle("خروجی")
        box.setText(msg + "\n" + path)
        b_open = box.addButton("باز کردن پوشه", QMessageBox.ActionRole)
        box.addButton("بستن", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is b_open:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).parent)))

    def export_khoroj(self):
        sel = self._selected_results()
        dec = [r for r in sel if r["diff"] < 0]
        if not dec:
            QMessageBox.information(self, "اظهار خروج", "ردیفی برای کاهش سامانه تیک نخورده.\n(فقط اختلاف منفی در اظهار خروج می‌آید؛ «تیک کاهش سامانه» را بزنید.)")
            return
        path = self._ask_save("ذخیره‌ی اظهار خروج", "اظهار_خروج_انتخابی.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            n = ic.write_khoroj_xlsx(path, dec, self.ed_date.text().strip() or self._today())
            self._after_export(path, "اظهار خروج ذخیره شد (%s ردیف). برای سامانه‌ی رسمی محتوا را در قالب xlsm کپی کنید." % fa_digits(n))
        except Exception as ex:
            _swallow()
            QMessageBox.critical(self, "خطا", str(ex))

    def export_xlsx(self):
        if not self.results:
            QMessageBox.information(self, "خروجی", "نتیجه‌ای برای خروجی نیست.")
            return
        path = self._ask_save("ذخیره‌ی مقایسه", "inventory_mapped_balance.xlsx", "Excel (*.xlsx)")
        if not path:
            return
        try:
            ic.write_results_xlsx(path, self.results)
            self._after_export(path, "اکسل مقایسه ذخیره شد.")
        except Exception as ex:
            _swallow()
            QMessageBox.critical(self, "خطا", str(ex))

    def export_pdf(self):
        sel = self._selected_results()
        if not sel:
            QMessageBox.information(self, "PDF", "ردیفی انتخاب نشده (تیک بزنید یا «تیک کاهش سامانه»).")
            return
        path = self._ask_save("ذخیره‌ی PDF", "system_decrease_selected.pdf", "PDF (*.pdf)")
        if not path:
            return
        try:
            from PySide6.QtGui import QPdfWriter, QPageSize, QTextDocument, QFont
            from PySide6.QtCore import QSizeF, QMarginsF
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setResolution(110)
            try:
                writer.setPageMargins(QMarginsF(12, 12, 12, 12))
            except Exception:
                _swallow()
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Tahoma", 10))
            doc.setHtml(ic.results_html(sel, "فهرست کاهش سامانه (موارد انتخابی)", self.ed_date.text().strip()))
            doc.setPageSize(QSizeF(writer.width(), writer.height()))
            printer = getattr(doc, "print_", None) or getattr(doc, "print")
            printer(writer)
            self._after_export(path, "PDF ذخیره شد.")
        except Exception as ex:
            _swallow()
            QMessageBox.critical(self, "خطا", "ساخت PDF انجام نشد:\n" + str(ex))

    # ───────────────────────── نگاشت ↔ فایل JSON ─────────────────────────
    def export_maps_json(self):
        path = self._ask_save("خروجی نگاشت‌ها", "inventory_maps_%s.json" % datetime.now().strftime("%Y%m%d"), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "mappings": self.mappings}, f, ensure_ascii=False, indent=1)
            self._after_export(path, "نگاشت‌ها ذخیره شد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))

    def import_maps_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "ورود نگاشت‌ها", self.store.get("lastExportDir", ""), "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            maps = ic.normalize_mappings(data.get("mappings", data))
        except Exception as ex:
            QMessageBox.critical(self, "خطا", "فایل نگاشت معتبر نیست:\n" + str(ex))
            return
        box = QMessageBox(self)
        box.setWindowTitle("ورود نگاشت‌ها")
        box.setText("نگاشت‌های فایل چطور اعمال شوند؟")
        b_merge = box.addButton("ادغام با نگاشت فعلی", QMessageBox.AcceptRole)
        b_rep = box.addButton("جایگزین کامل", QMessageBox.DestructiveRole)
        box.addButton("لغو", QMessageBox.RejectRole)
        box.exec()
        c = box.clickedButton()
        if c is b_merge:
            self.mappings = ic.merge_mappings(self.mappings, maps)
        elif c is b_rep:
            self.mappings = maps
        else:
            return
        self._maps_changed()
        self._refresh_all()
        self._toast("نگاشت‌ها وارد شد", "ok")

    # ───────────────────────── همگام‌سازی نگاشت با ابر ─────────────────────────
    def _cloud_ok(self):
        try:
            return bool(self.cloud and self.cloud["enabled"]() and self.cloud["valid"]())
        except Exception:
            return False

    def _update_cloud_label(self, text=None, color="#64748B"):
        if text is None:
            if not self._cloud_ok():
                text = "نگاشت‌ها فقط روی همین سیستم ذخیره می‌شوند (ابر: وارد نشده)"
            else:
                synced = ic.parse_iso(self.store.get("cloudSyncedAt"))
                local = ic.parse_iso(self.store.get("mapsUpdatedAt"))
                if synced is None:
                    text, color = "☁ هنوز با ابر همگام نشده", "#D97706"
                elif local and local > synced:
                    text, color = "☁ تغییر محلی ارسال‌نشده", "#D97706"
                else:
                    text, color = "☁ همگام با ابر", "#16A34A"
        self.lbl_cloud.setText(text)
        self.lbl_cloud.setStyleSheet("color:%s;font-size:12px;" % color)

    def _fetch_cloud(self):
        status, rows = self.cloud["request"]("GET", "/rest/v1/inventory_code_maps?id=eq.1&select=mappings,updated_at")
        if not rows:
            return {}, ""
        maps = rows[0].get("mappings") or {}
        if isinstance(maps, str):
            try:
                maps = json.loads(maps)
            except Exception:
                maps = {}
        return ic.normalize_mappings(maps), rows[0].get("updated_at") or ""

    def _push_cloud(self):
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        body = {"id": 1, "mappings": self.mappings, "updated_at": now}
        try:
            self.cloud["request"]("POST", "/rest/v1/inventory_code_maps?on_conflict=id", [body],
                                  {"Prefer": "resolution=merge-duplicates,return=representation"})
        except Exception:
            self.cloud["request"]("PATCH", "/rest/v1/inventory_code_maps?id=eq.1", {"mappings": self.mappings, "updated_at": now})
        return now

    def sync_maps(self, manual=True):
        if not self._cloud_ok():
            if manual:
                QMessageBox.information(self, "ابر", "برای همگام‌سازی ابتدا در تنظیمات وارد حساب ابری شوید.\n"
                                        "نگاشت‌ها همین حالا هم روی همین سیستم ذخیره‌اند.")
            self._update_cloud_label()
            return
        if self._cloud_busy:
            return
        self._cloud_busy = True
        self._update_cloud_label("☁ در حال همگام‌سازی…", "#1565C0")
        self.btn_sync.setEnabled(False)
        self._run_bg(self._fetch_cloud, lambda res, err: self._after_fetch(res, err, manual))

    def _finish_sync(self):
        self._cloud_busy = False
        self.btn_sync.setEnabled(True)
        self._update_cloud_label()

    def _after_fetch(self, res, err, manual):
        if err is not None:
            self._finish_sync()
            self._update_cloud_label("☁ خطا در ارتباط با ابر", "#DC2626")
            if manual:
                QMessageBox.warning(self, "ابر", "دریافت نگاشت از ابر ممکن نشد:\n" + str(err) +
                                    "\n\nاگر جدول inventory_code_maps ساخته نشده، فایل SUPABASE_INVENTORY_MAPS.sql را در Supabase اجرا کنید.")
            return
        cloud_maps, cloud_at = res
        local_empty = not any(v for m in self.mappings.values() for v in m.values())
        cloud_empty = not any(v for m in cloud_maps.values() for v in m.values())
        t_cloud, t_local = ic.parse_iso(cloud_at), ic.parse_iso(self.store.get("mapsUpdatedAt"))
        t_sync = ic.parse_iso(self.store.get("cloudSyncedAt"))
        same = ic.normalize_mappings(cloud_maps) == ic.normalize_mappings(self.mappings)
        cloud_changed = bool(t_cloud and (t_sync is None or t_cloud > t_sync))
        local_changed = bool(t_local and (t_sync is None or t_local > t_sync))

        action = None            # "push" | "pull" | "ask" | "none"
        if same:
            action = "none"
        elif cloud_empty and not local_empty:
            action = "push"
        elif local_empty and not cloud_empty:
            action = "pull"
        elif cloud_changed and not local_changed:
            action = "pull"
        elif local_changed and not cloud_changed:
            action = "push"
        else:
            action = "ask"

        if action == "ask":
            if not manual:
                self._finish_sync()
                self._update_cloud_label("☁ تعارض با ابر — همگام‌سازی دستی را بزنید", "#D97706")
                return
            box = QMessageBox(self)
            box.setWindowTitle("تعارض نگاشت")
            box.setText("نگاشت‌های ابر و این سیستم هر دو تغییر کرده‌اند و یکسان نیستند. چه شود؟")
            b_merge = box.addButton("ادغام (اجتماع کدها)", QMessageBox.AcceptRole)
            b_pull = box.addButton("نگاشت ابر را بگیر", QMessageBox.DestructiveRole)
            b_push = box.addButton("نگاشت این سیستم را بفرست", QMessageBox.DestructiveRole)
            box.addButton("لغو", QMessageBox.RejectRole)
            box.exec()
            c = box.clickedButton()
            if c is b_merge:
                self.mappings = ic.merge_mappings(self.mappings, cloud_maps)
                action = "push"
            elif c is b_pull:
                action = "pull"
            elif c is b_push:
                action = "push"
            else:
                self._finish_sync()
                return

        if action == "pull":
            self.mappings = cloud_maps
            self._mark_synced(cloud_at)
            self._save()
            self._refresh_all()
            self._finish_sync()
            self._toast("نگاشت‌ها از ابر دریافت شد", "ok")
        elif action == "push":
            self._run_bg(self._push_cloud, lambda ts, e: self._after_push(ts, e, manual))
        else:
            self._mark_synced(cloud_at)
            self._save()
            self._finish_sync()
            if manual:
                self._toast("نگاشت‌ها با ابر یکسان است", "ok")

    def _mark_synced(self, ts):
        from datetime import timezone
        self.store["cloudSyncedAt"] = ts or datetime.now(timezone.utc).isoformat(timespec="seconds")
        if not self.store.get("mapsUpdatedAt"):
            self.store["mapsUpdatedAt"] = self.store["cloudSyncedAt"]

    def _after_push(self, ts, err, manual):
        if err is not None:
            self._finish_sync()
            self._update_cloud_label("☁ ارسال به ابر ناموفق", "#DC2626")
            if manual:
                QMessageBox.warning(self, "ابر", "ارسال نگاشت به ابر ممکن نشد:\n" + str(err))
            return
        self._mark_synced(ts)
        self.store["mapsUpdatedAt"] = ts
        self._save()
        self._finish_sync()
        if manual:
            self._toast("نگاشت‌ها روی ابر ذخیره شد", "ok")

    # ───────────────────────── به‌روزرسانی کلی ─────────────────────────
    def _refresh_all(self):
        self._refresh_slots()
        self._refresh_wh_tabs()
        self._fill_sys()
        self._recompute()
        self._update_cloud_label()

    def on_show(self):
        """هر بار که کاربر صفحه را باز می‌کند."""
        try:
            self._refresh_all()
            if self._cloud_ok() and not self._cloud_checked_session:
                self._cloud_checked_session = True
                QTimer.singleShot(600, lambda: self.sync_maps(manual=False))
        except Exception:
            _swallow()

    def ensure_loaded(self):          # سازگاری با HtmlToolPage
        return True
