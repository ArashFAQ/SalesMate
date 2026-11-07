# -*- coding: utf-8 -*-
"""سیستم طراحی یکپارچه SalesMate — تم روشن/تیره، فونت، Toast، Skeleton."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QObject, Signal
from PySide6.QtGui import QFont, QFontDatabase, QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame,
    QGraphicsOpacityEffect, QSizePolicy,
)

# ─── فاصله / شعاع / سایه (توکن‌های طراحی) ───────────────────────────
SPACE = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}
RADIUS = {"sm": 8, "md": 12, "lg": 16, "xl": 20, "pill": 999}
FONT_FAMILY = "Vazirmatn"
FONT_FALLBACK = '"Vazirmatn", "Segoe UI", "Tahoma", sans-serif'

LIGHT = {
    "bg": "#F1F5F9",
    "surface": "#FFFFFF",
    "surface2": "#F8FAFC",
    "border": "#E2E8F0",
    "border_strong": "#CBD5E1",
    "text": "#0F172A",
    "text_muted": "#64748B",
    "text_faint": "#94A3B8",
    "primary": "#1565C0",
    "primary_hover": "#0D47A1",
    "primary_soft": "#E3F2FD",
    "success": "#059669",
    "success_soft": "#ECFDF5",
    "danger": "#DC2626",
    "danger_soft": "#FEF2F2",
    "warning": "#D97706",
    "nav_bg": "#FFFFFF",
    "header_bg": "#FFFFFF",
    "table_row": "#FFFFFF",
    "table_alt": "#F8FAFC",
    "table_hover": "#EFF6FF",
    "shadow": "rgba(15,23,42,0.08)",
    "skeleton": "#E2E8F0",
    "skeleton2": "#F1F5F9",
}

DARK = {
    "bg": "#0B1220",
    "surface": "#111827",
    "surface2": "#1E293B",
    "border": "#334155",
    "border_strong": "#475569",
    "text": "#F1F5F9",
    "text_muted": "#94A3B8",
    "text_faint": "#64748B",
    "primary": "#3B82F6",
    "primary_hover": "#2563EB",
    "primary_soft": "#1E3A5F",
    "success": "#34D399",
    "success_soft": "#064E3B",
    "danger": "#F87171",
    "danger_soft": "#7F1D1D",
    "warning": "#FBBF24",
    "nav_bg": "#111827",
    "header_bg": "#0F172A",
    "table_row": "#111827",
    "table_alt": "#0F172A",
    "table_hover": "#1E3A5F",
    "shadow": "rgba(0,0,0,0.35)",
    "skeleton": "#1E293B",
    "skeleton2": "#334155",
}

_current_mode = "light"
_font_loaded = False
_toast_host: Optional[QWidget] = None
_skeleton_host: Optional[QWidget] = None


def _fonts_dir() -> Path:
    here = Path(__file__).resolve().parent
    candidates = [
        here / "fonts",
        here.parent / "fonts",
    ]
    if getattr(__import__("sys"), "frozen", False):
        import sys
        base = Path(sys.executable).resolve().parent
        candidates += [
            base / "fonts",
            base / "_internal" / "fonts",
            base / "salesmate" / "fonts",
            Path(getattr(sys, "_MEIPASS", here)) / "fonts",
        ]
    for c in candidates:
        if c.exists():
            return c
    return here / "fonts"


def load_app_fonts() -> str:
    """بارگذاری Vazirmatn؛ نام خانواده را برمی‌گرداند."""
    global _font_loaded
    fam = FONT_FAMILY
    try:
        fd = _fonts_dir()
        for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Medium.ttf", "Vazirmatn-Bold.ttf"):
            p = fd / name
            if p.exists():
                QFontDatabase.addApplicationFont(str(p))
        _font_loaded = True
    except Exception:
        fam = "Segoe UI"
    return fam


def current_palette():
    return DARK if _current_mode == "dark" else LIGHT


def is_dark() -> bool:
    return _current_mode == "dark"


def build_stylesheet(mode: str = "light") -> str:
    t = DARK if mode == "dark" else LIGHT
    r = RADIUS
    return f"""
* {{ font-family: {FONT_FALLBACK}; }}
QWidget {{
    background: {t['bg']};
    color: {t['text']};
    font-family: {FONT_FALLBACK};
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: {t['bg']};
}}
/* برچسب‌ها و گزینه‌ها روی کارت سفید نباید مستطیل طوسی پس‌زمینه داشته باشند */
QLabel, QCheckBox, QRadioButton {{
    background: transparent;
}}
#header {{
    background: {t['header_bg']};
    border-bottom: 1px solid {t['border']};
}}
#brand {{
    color: {t['primary']};
    font-size: 22px;
    font-weight: 800;
}}
#subtitle {{
    color: {t['text_muted']};
    font-size: 12px;
}}
#hello, #pageTitle {{
    font-size: 22px;
    font-weight: 800;
    color: {t['text']};
}}
#sectionTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {t['text']};
}}
#hint {{
    color: {t['text_muted']};
    font-size: 13px;
}}
QFrame.card, .card {{
    background: {t['surface']};
    border: 1px solid {t['border']};
    border-radius: {r['lg']}px;
}}
QLabel.statTitle, .statTitle {{
    color: {t['text_muted']};
    font-size: 12px;
}}
QLabel.statValue, .statValue {{
    color: {t['primary']};
    font-size: 20px;
    font-weight: 800;
}}
QPushButton {{
    background: {t['surface2']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: {t['border']};
}}
QPushButton:disabled {{
    color: {t['text_faint']};
    background: {t['surface2']};
}}
QPushButton#primaryButton, QPushButton#newInvoice, QPushButton[class="primaryButton"] {{
    background: {t['primary']};
    color: white;
    border: none;
    border-radius: {r['md']}px;
    font-weight: 700;
    padding: 10px 16px;
}}
QPushButton#primaryButton:hover, QPushButton#newInvoice:hover {{
    background: {t['primary_hover']};
}}
QPushButton[class="secondaryButton"], QPushButton.secondaryButton {{
    background: {t['surface']};
    color: {t['primary']};
    border: 1px solid {t['primary']};
    border-radius: {r['md']}px;
    font-weight: 700;
}}
QPushButton[class="navButton"], QPushButton.navButton {{
    background: transparent;
    color: {t['text_muted']};
    border: none;
    border-radius: {r['sm']}px;
    padding: 6px 8px;
    font-weight: 700;
    font-size: 12px;
}}
QPushButton[class="navButton"]:hover {{
    background: {t['primary_soft']};
    color: {t['primary']};
}}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox, QDateEdit {{
    background: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    padding: 8px 12px;
    selection-background-color: {t['primary']};
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {t['primary']};
}}
QTableWidget, QTableView, QTreeView, QListView {{
    background: {t['surface']};
    alternate-background-color: {t['table_alt']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    gridline-color: {t['border']};
}}
QHeaderView::section {{
    background: {t['surface2']};
    color: {t['text_muted']};
    border: none;
    border-bottom: 1px solid {t['border']};
    padding: 8px;
    font-weight: 700;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {t['border_strong']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QTabWidget::pane {{
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    background: {t['surface']};
}}
QTabBar::tab {{
    background: {t['surface2']};
    color: {t['text_muted']};
    padding: 8px 16px;
    border-top-left-radius: {r['sm']}px;
    border-top-right-radius: {r['sm']}px;
    margin-left: 2px;
    font-weight: 700;
}}
QTabBar::tab:selected {{
    background: {t['primary']};
    color: white;
}}
QToolTip {{
    background: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
    padding: 6px 10px;
    border-radius: 8px;
}}
QMessageBox {{
    background: {t['surface']};
}}
QProgressBar {{
    background: {t['surface2']};
    border: 1px solid {t['border']};
    border-radius: 8px;
    text-align: center;
    color: {t['text']};
}}
QProgressBar::chunk {{
    background: {t['primary']};
    border-radius: 7px;
}}
QCheckBox {{
    color: {t['text']};
    spacing: 8px;
}}
QGroupBox {{
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: {r['md']}px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 700;
}}
"""


def apply_theme(app: QApplication, mode: str = "light"):
    global _current_mode
    _current_mode = "dark" if mode == "dark" else "light"
    load_app_fonts()
    app.setStyle("Fusion")
    app.setFont(QFont(FONT_FAMILY, 10))
    app.setStyleSheet(build_stylesheet(_current_mode))
    # palette for native dialogs
    t = current_palette()
    from PySide6.QtGui import QPalette
    pal = app.palette()
    pal.setColor(QPalette.Window, QColor(t["bg"]))
    pal.setColor(QPalette.WindowText, QColor(t["text"]))
    pal.setColor(QPalette.Base, QColor(t["surface"]))
    pal.setColor(QPalette.AlternateBase, QColor(t["surface2"]))
    pal.setColor(QPalette.Text, QColor(t["text"]))
    pal.setColor(QPalette.Button, QColor(t["surface2"]))
    pal.setColor(QPalette.ButtonText, QColor(t["text"]))
    pal.setColor(QPalette.Highlight, QColor(t["primary"]))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)


def set_toast_host(widget: QWidget):
    global _toast_host
    _toast_host = widget


def set_skeleton_host(widget: QWidget):
    global _skeleton_host
    _skeleton_host = widget


class Toast(QFrame):
    def __init__(self, parent, message: str, kind: str = "info", ms: int = 2800):
        super().__init__(parent)
        t = current_palette()
        colors = {
            "success": (t["success_soft"], t["success"]),
            "error": (t["danger_soft"], t["danger"]),
            "info": (t["primary_soft"], t["primary"]),
            "warn": (t["surface2"], t["warning"]),
        }
        bg, fg = colors.get(kind, colors["info"])
        self.setObjectName("smToast")
        self.setStyleSheet(
            f"#smToast{{background:{bg};border:1px solid {fg};border-radius:12px;}}"
            f"QLabel{{color:{fg};font-weight:700;font-size:13px;background:transparent;border:none;}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        icons = {"success": "✓", "error": "!", "info": "i", "warn": "!"}
        ic = QLabel(icons.get(kind, "i"))
        ic.setStyleSheet(f"color:{fg};font-size:16px;font-weight:900;background:transparent;")
        msg = QLabel(message)
        msg.setWordWrap(True)
        lay.addWidget(ic)
        lay.addWidget(msg, 1)
        self.adjustSize()
        self.setMinimumWidth(min(360, parent.width() - 40) if parent else 280)
        self._fade = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._fade)
        self._fade.setOpacity(0.0)
        QTimer.singleShot(10, self._show_anim)
        QTimer.singleShot(ms, self._hide_anim)

    def _show_anim(self):
        anim = QPropertyAnimation(self._fade, b"opacity", self)
        anim.setDuration(180)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start()
        self._anim_show = anim

    def _hide_anim(self):
        anim = QPropertyAnimation(self._fade, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.finished.connect(self.deleteLater)
        anim.start()
        self._anim_hide = anim

    def place(self):
        p = self.parent()
        if not p:
            return
        self.adjustSize()
        x = (p.width() - self.width()) // 2
        y = p.height() - self.height() - 28
        self.move(max(12, x), max(12, y))
        self.show()
        self.raise_()


def toast(message: str, kind: str = "info", ms: int = 2800):
    """نمایش پیام یکدست در پایین پنجره اصلی."""
    host = _toast_host
    if host is None:
        app = QApplication.instance()
        if app:
            for w in app.topLevelWidgets():
                if w.isVisible() and w.metaObject().className() == "MainWindow":
                    host = w
                    break
    if host is None:
        return
    t = Toast(host, message, kind, ms)
    t.place()


class SkeletonOverlay(QFrame):
    """پوشش نیمه‌شفاف هنگام همگام‌سازی ابر."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("smSkeleton")
        t = current_palette()
        self.setStyleSheet(
            f"#smSkeleton{{background:rgba(15,23,42,0.35);}}"
            f"QFrame#card{{background:{t['surface']};border-radius:16px;border:1px solid {t['border']};}}"
            f"QLabel{{color:{t['text']};background:transparent;border:none;}}"
        )
        self.hide()
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(280)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(24, 20, 24, 20)
        self.lbl = QLabel("در حال همگام‌سازی با ابر…")
        self.lbl.setAlignment(Qt.AlignCenter)
        self.lbl.setStyleSheet("font-weight:800;font-size:14px;")
        self.sub = QLabel("لطفاً چند لحظه صبر کنید")
        self.sub.setAlignment(Qt.AlignCenter)
        self.sub.setStyleSheet(f"color:{t['text_muted']};font-size:12px;")
        # نوار اسکلتون ساده
        bar = QFrame()
        bar.setFixedHeight(6)
        bar.setStyleSheet(
            f"background:{t['skeleton']};border-radius:3px;"
        )
        cl.addWidget(self.lbl)
        cl.addWidget(self.sub)
        cl.addSpacing(8)
        cl.addWidget(bar)
        outer.addWidget(card)
        self._dots = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._dots = (self._dots + 1) % 4
        self.lbl.setText("در حال همگام‌سازی با ابر" + ("." * self._dots))

    def show_overlay(self, text: str = "در حال همگام‌سازی با ابر…"):
        if self.parent():
            self.setGeometry(self.parent().rect())
        self.lbl.setText(text)
        self.show()
        self.raise_()
        self._timer.start(400)

    def hide_overlay(self):
        self._timer.stop()
        self.hide()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.parent() and self.isVisible():
            self.setGeometry(self.parent().rect())


_skeleton: Optional[SkeletonOverlay] = None


def ensure_skeleton(parent: QWidget) -> SkeletonOverlay:
    global _skeleton
    if _skeleton is None or _skeleton.parent() is not parent:
        _skeleton = SkeletonOverlay(parent)
    return _skeleton


def show_skeleton(text: str = "در حال همگام‌سازی با ابر…"):
    host = _skeleton_host or _toast_host
    if not host:
        return
    sk = ensure_skeleton(host)
    sk.show_overlay(text)


def hide_skeleton():
    if _skeleton is not None:
        _skeleton.hide_overlay()


# ─── کش آمار مشتری ───────────────────────────────────────────────
_customer_cache = {
    "colors": {},
    "balances": {},
    "year_sales": {},
    "dirty": True,
    "built_at": 0.0,
}


def invalidate_customer_cache():
    _customer_cache["dirty"] = True
    _customer_cache["colors"] = {}
    _customer_cache["balances"] = {}
    _customer_cache["year_sales"] = {}


def cache_get_color(name: str, builder):
    if name in _customer_cache["colors"] and not _customer_cache["dirty"]:
        return _customer_cache["colors"][name]
    c = builder(name)
    _customer_cache["colors"][name] = c
    return c


def cache_set_balances(mapping: dict):
    _customer_cache["balances"] = dict(mapping)
    _customer_cache["dirty"] = False


def cache_get_balance(name: str, default=0):
    return _customer_cache["balances"].get(name, default)


def cache_set_year_sales(mapping: dict):
    _customer_cache["year_sales"] = dict(mapping)


def cache_get_year_sales(name: str, year, default=0):
    return _customer_cache["year_sales"].get((name, str(year)), default)
