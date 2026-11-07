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
    CATEGORY_CHOICES,
    FREE_TYPES,
    OTHER_FREE,
    _abbr_amount,
    _swallow,
    _top10_tooltip_html,
    amount,
    db,
    en_digits,
    fa_digits,
    filter_category,
    fmt,
    free_items_breakdown,
    free_items_by_customer,
    free_items_of_customer,
    get_customer_color,
    gregorian_to_jalali,
    jalali_week_range,
    now_jalali,
)
except Exception:
    from salesmate.app_core import (
    APP_DIR,
    CATEGORY_CHOICES,
    FREE_TYPES,
    OTHER_FREE,
    _abbr_amount,
    _swallow,
    _top10_tooltip_html,
    amount,
    db,
    en_digits,
    fa_digits,
    filter_category,
    fmt,
    free_items_breakdown,
    free_items_by_customer,
    free_items_of_customer,
    get_customer_color,
    gregorian_to_jalali,
    jalali_week_range,
    now_jalali,
)


class SalesLineChart(QWidget):
    """نمودار خطی فروش؛ روی هر نقطه مبلغ و متراژ نوشته می‌شود. قدیمی‌ترین ماه/هفته سمت چپ، جدیدترین سمت راست."""

    SLOT = 86

    def __init__(self, color="#1565C0", parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.points = []   # هر مورد: dict(label, sub, amt, met, tip)
        self._hover = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(290)
        self.setMinimumWidth(320)

    def set_points(self, pts):
        self.points = list(pts or [])
        self._hover = -1
        self.setMinimumWidth(max(320, len(self.points) * self.SLOT + 40))
        self.update()

    def _layout(self):
        W, H = float(self.width()), float(self.height())
        plot = QRectF(20.0, 58.0, max(W - 40.0, 10.0), max(H - 58.0 - 50.0, 10.0))
        n = max(len(self.points), 1)
        slot = plot.width() / n
        mx = max([max(float(p["amt"]), 0.0) for p in self.points] + [1.0])
        pts = []
        for i, p in enumerate(self.points):
            x = plot.left() + (i + 0.5) * slot
            y = plot.bottom() - (max(float(p["amt"]), 0.0) / mx) * plot.height()
            pts.append((x, y))
        return plot, slot, pts

    def paintEvent(self, ev):
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing, True)
        pa.setRenderHint(QPainter.TextAntialiasing, True)
        W, H = self.width(), self.height()
        pa.setPen(QPen(QColor("#E2E8F0"), 1))
        pa.setBrush(QColor("#FFFFFF"))
        pa.drawRoundedRect(QRectF(0.5, 0.5, W - 1.0, H - 1.0), 14, 14)
        if not self.points:
            pa.setPen(QColor("#94A3B8"))
            pa.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "داده‌ای نیست")
            pa.end()
            return
        plot, slot, xy = self._layout()
        # خطوط راهنما
        pa.setPen(QPen(QColor("#F1F5F9"), 1))
        for k in range(5):
            gy = plot.top() + plot.height() * k / 4.0
            pa.drawLine(int(plot.left()), int(gy), int(plot.right()), int(gy))
        # سطح زیر خط
        if len(xy) >= 2:
            area = QPainterPath()
            area.moveTo(xy[0][0], plot.bottom())
            for (x, y) in xy:
                area.lineTo(x, y)
            area.lineTo(xy[-1][0], plot.bottom())
            area.closeSubpath()
            fill = QColor(self.color)
            fill.setAlpha(28)
            pa.setPen(Qt.NoPen)
            pa.setBrush(fill)
            pa.drawPath(area)
            line = QPainterPath()
            line.moveTo(*xy[0])
            for (x, y) in xy[1:]:
                line.lineTo(x, y)
            pa.setBrush(Qt.NoBrush)
            pa.setPen(QPen(self.color, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            pa.drawPath(line)
        base_font = QFont(self.font())
        for i, (p, (x, y)) in enumerate(zip(self.points, xy)):
            hov = (i == self._hover)
            r = 6.5 if hov else 4.5
            pa.setPen(QPen(self.color, 2.4))
            pa.setBrush(QColor("#FFFFFF") if not hov else self.color)
            pa.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
            # برچسب مبلغ + متراژ
            pw = min(slot - 6.0, 96.0)
            pill = QRectF(x - pw / 2.0, y - 44.0, pw, 33.0)
            pa.setPen(QPen(QColor("#CBD5E1" if not hov else self.color), 1))
            pa.setBrush(QColor(255, 255, 255, 235))
            pa.drawRoundedRect(pill, 8, 8)
            f1 = QFont(base_font); f1.setPointSize(8); f1.setBold(True)
            pa.setFont(f1)
            pa.setPen(QColor("#0F172A"))
            pa.drawText(QRectF(pill.left(), pill.top() + 2, pill.width(), 15), Qt.AlignCenter, _abbr_amount(p["amt"]))
            f2 = QFont(base_font); f2.setPointSize(7)
            pa.setFont(f2)
            pa.setPen(QColor("#0D47A1"))
            met = p["met"]
            mt = fa_digits(("%g" % round(float(met), 1)) if met else "0") + " متر"
            pa.drawText(QRectF(pill.left(), pill.top() + 17, pill.width(), 14), Qt.AlignCenter, mt)
            # برچسب محور
            f3 = QFont(base_font); f3.setPointSize(8); f3.setBold(True)
            pa.setFont(f3)
            pa.setPen(QColor("#334155"))
            pa.drawText(QRectF(x - slot / 2.0, plot.bottom() + 8, slot, 16), Qt.AlignCenter, str(p["label"]))
            if p.get("sub"):
                f4 = QFont(base_font); f4.setPointSize(7)
                pa.setFont(f4)
                pa.setPen(QColor("#94A3B8"))
                pa.drawText(QRectF(x - slot / 2.0, plot.bottom() + 24, slot, 14), Qt.AlignCenter, str(p["sub"]))
        pa.end()

    def _index_at(self, pos):
        if not self.points:
            return -1
        plot, slot, xy = self._layout()
        best, bd = -1, 1e9
        for i, (x, y) in enumerate(xy):
            d = abs(pos.x() - x)
            if d < bd:
                best, bd = i, d
        return best if bd <= slot / 2.0 else -1

    def mouseMoveEvent(self, ev):
        i = self._index_at(ev.position())
        if i != self._hover:
            self._hover = i
            self.update()
        if i >= 0:
            QToolTip.showText(ev.globalPosition().toPoint(), self.points[i].get("tip", ""), self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        self._hover = -1
        QToolTip.hideText()
        self.update()
        super().leaveEvent(ev)


def _sig(name):
    import re as _re
    try:
        from core_utils import customer_key
    except Exception:
        from salesmate.core_utils import customer_key
    return _re.sub(r"[\s\-\u2010-\u2015\u2212_]+", "", customer_key(name))


def store_diff(ex_rows, st_rows):
    """مغایرت فروشگاه: ex_rows = [(تاریخ, شماره فرم, مبلغ, متراژ, مشتری)] ردیف‌های پارکتِ اکسل برای فروشگاه؛
    st_rows = [(id, مشتری, شماره، تاریخ، مبلغ، متراژ)] فروش‌های ثبت‌شده در تب فروشگاه.
    تطبیق: ۱) تاریخ+شماره ۲) تاریخ+مبلغ ۳) همان مشتری و تاریخ (اگر یکتا بود).
    خروجی: (فقط در فروشگاه، فقط در اکسل)؛ موارد هم‌تطبیق با مبلغ متفاوت در store_diff.last_diffs."""
    ex = {}
    ex_cust = {}
    for row in ex_rows:
        d, f, a, m = row[:4]
        cu = row[4] if len(row) > 4 else ""
        k = (en_digits(str(d or "")).strip(), en_digits(str(f or "")).strip())
        g = ex.setdefault(k, [0, 0.0])
        g[0] += a
        g[1] += m
        ex_cust[k] = cu
    by_total = {}
    by_cd = {}
    for (d, f), (a, m) in ex.items():
        by_total.setdefault((d, int(round(a))), []).append((d, f))
        by_cd.setdefault((_sig(ex_cust.get((d, f), "")), d), []).append((d, f))
    used = set()
    only_store = []
    diffs = []
    for iid, cust, no, d, tot, m in st_rows:
        d = en_digits(str(d or "")).strip()
        no = en_digits(str(no or "")).strip()
        t = int(round(float(tot)))
        k = (d, no)
        pick = None
        if k in ex and k not in used:
            pick = k
        else:
            cand = [x for x in by_total.get((d, t), []) if x not in used]
            if cand:
                pick = cand[0]
            else:
                cand = [x for x in by_cd.get((_sig(cust), d), []) if x not in used]
                if len(cand) == 1:
                    pick = cand[0]
        if pick is None:
            only_store.append((d, no, cust, t, m))
            continue
        used.add(pick)
        if abs(ex[pick][0] - t) > 1:
            diffs.append((d, no, cust, t, int(round(ex[pick][0]))))
    only_excel = [(d, f, int(round(a)), m) for (d, f), (a, m) in sorted(ex.items()) if (d, f) not in used]
    store_diff.last_diffs = diffs
    return only_store, only_excel


def find_store_duplicates(rows):
    """rows = [(id, مشتری, شماره، تاریخ، مبلغ)] → [(id_حذفی, id_نگه‌داشته)] .
    تکراری = همان تاریخ + همان شماره‌ی حواله (مبلغ فرق کند هم یکی است)؛ برای شماره‌ی AN- (بدون شماره‌ی فرم): همان تاریخ + مبلغ + نام.
    کمترین id نگه داشته می‌شود؛ مبلغ نگه‌داشته‌شده بعداً با بارگذاری اکسل اصلاح می‌شود."""
    try:
        from core_utils import customer_key
    except Exception:
        from salesmate.core_utils import customer_key
    keep = {}
    out = []
    for iid, cust, no, d, tot in sorted(rows, key=lambda r: r[0]):
        no = en_digits(str(no or "")).strip()
        dt = en_digits(str(d or "")).strip()
        if no and not no.startswith("AN-"):
            k = ("n", dt, no)
        else:
            k = ("c", dt, int(round(float(tot or 0))), customer_key(cust))
        if k in keep:
            out.append((iid, keep[k]))
        else:
            keep[k] = iid
    return out


class ParquetStatsPage(QWidget):
    """آمار فروش کلی پارکت از داده تحلیل فروش (اکسل کل شرکت)."""

    MONTH_FA = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

    MONTHS_PER_ROW = 6
    WEEKS_IN_CHART = 16

    def _chart_scroll(self, chart):
        """نمودار داخل اسکرول افقی؛ فقط وقتی پنجره از عرض لازم کوچک‌تر باشد اسکرول فعال می‌شود."""
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setFixedHeight(316)
        sc.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        sc.setWidget(chart)
        return sc

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("آمار فروش کلی پارکت")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#0F172A;")
        head.addWidget(title)
        head.addStretch()
        self.hint = QLabel("")
        self.hint.setStyleSheet("color:#64748B;font-size:12px;")
        head.addWidget(self.hint)
        ref = QPushButton("↻ بروزرسانی")
        ref.setCursor(Qt.PointingHandCursor)
        ref.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;"
            "padding:8px 16px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        ref.clicked.connect(self.refresh)
        head.addWidget(ref)
        diff_b = QPushButton("بررسی مغایرت فروشگاه")
        diff_b.setCursor(Qt.PointingHandCursor)
        diff_b.setStyleSheet(
            "QPushButton{background:#F59E0B;color:#fff;border:none;border-radius:10px;"
            "padding:8px 16px;font-weight:700;}"
        )
        diff_b.clicked.connect(self.show_store_diff)
        head.addWidget(diff_b)
        root.addLayout(head)

        tip = QLabel(
            "بر اساس اکسل «تحلیل فروش» · نام‌های شروع‌شده با «فروشگاه ایزوفام» یک‌جا حساب می‌شوند"
        )
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#64748B;font-size:12px;margin-bottom:4px;")
        root.addWidget(tip)

        # اسکرول کل صفحه
        outer = QScrollArea()
        outer.setWidgetResizable(True)
        outer.setFrameShape(QFrame.NoFrame)
        outer.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        try:
            outer.setFocusPolicy(Qt.StrongFocus)
        except Exception:
            pass
        host = QWidget()
        self.body = QVBoxLayout(host)
        self.body.setContentsMargins(0, 0, 4, 8)
        self.body.setSpacing(14)
        outer.setWidget(host)
        root.addWidget(outer, 1)

        # سطل‌های محتوا
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(12)
        self.body.addLayout(self.kpi_row)

        # فروش بر اساس نوع پارکت (جناغی / والنته / بقیه) در بازه‌ی تاریخ
        tbox = QFrame()
        tbox.setStyleSheet("QFrame#typeBox{background:#fff;border:1px solid #E2E8F0;border-radius:16px;}")
        tbox.setObjectName("typeBox")
        tl = QVBoxLayout(tbox)
        tl.setContentsMargins(12, 10, 12, 12)
        tl.setSpacing(8)
        trow = QHBoxLayout()
        tt = QLabel("فروش بر اساس نوع پارکت")
        tt.setStyleSheet("font-size:15px;font-weight:800;color:#0F172A;border:none;")
        trow.addWidget(tt)
        trow.addStretch(1)
        _lbl_s = "color:#475569;font-size:12px;border:none;"
        _edit_s = "QLineEdit{border:1px solid #CBD5E1;border-radius:8px;padding:5px 8px;background:#fff;}"
        l1 = QLabel("از تاریخ"); l1.setStyleSheet(_lbl_s)
        self.type_from = QLineEdit(); self.type_from.setFixedWidth(110)
        self.type_from.setPlaceholderText("1405/01/01"); self.type_from.setStyleSheet(_edit_s)
        l2 = QLabel("تا تاریخ"); l2.setStyleSheet(_lbl_s)
        self.type_to = QLineEdit(); self.type_to.setFixedWidth(110)
        self.type_to.setPlaceholderText("1405/08/08"); self.type_to.setStyleSheet(_edit_s)
        tb = QPushButton("محاسبه")
        tb.setCursor(Qt.PointingHandCursor)
        tb.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:8px;"
            "padding:6px 16px;font-weight:700;}"
        )
        tb.clicked.connect(self._fill_types)
        self.type_to.returnPressed.connect(self._fill_types)
        self.type_from.returnPressed.connect(self._fill_types)
        for w in (l1, self.type_from, l2, self.type_to, tb):
            trow.addWidget(w)
        tl.addLayout(trow)
        self.type_row = QHBoxLayout()
        self.type_row.setSpacing(12)
        tl.addLayout(self.type_row)
        self.type_note = QLabel("")
        self.type_note.setStyleSheet("color:#64748B;font-size:11px;border:none;")
        self.type_note.setWordWrap(True)
        tl.addWidget(self.type_note)
        self._pdf_types = None
        self.body.addWidget(tbox)

        self.months_title = QLabel("فروش هر ماه (پارکت)")
        self.months_title.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;")
        self.body.addWidget(self.months_title)
        # ماه‌ها: شبکه‌ی ۶ تایی در هر ردیف (بدون اسکرول افقی)
        self.months_row = QGridLayout()
        self.months_row.setHorizontalSpacing(8)
        self.months_row.setVerticalSpacing(8)
        for _c in range(self.MONTHS_PER_ROW):
            self.months_row.setColumnStretch(_c, 1)
        self.body.addLayout(self.months_row)

        self.month_chart_title = QLabel("نمودار فروش ماهانه (مبلغ و متراژ)")
        self.month_chart_title.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;")
        self.body.addWidget(self.month_chart_title)
        self.month_chart = SalesLineChart("#1565C0")
        self.body.addWidget(self._chart_scroll(self.month_chart))

        self.week_chart_title = QLabel("نمودار فروش هفتگی (مبلغ و متراژ) — از اولین هفته‌ی ثبت‌شده")
        self.week_chart_title.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;")
        self.body.addWidget(self.week_chart_title)
        self.week_chart = SalesLineChart("#059669")
        self.body.addWidget(self._chart_scroll(self.week_chart))

        ranks = QHBoxLayout()
        ranks.setSpacing(12)
        self.week_list = QVBoxLayout()
        self.month_list = QVBoxLayout()
        self.year_list = QVBoxLayout()
        ranks.addWidget(self._rank_panel("۲۵ خریدار برتر — این هفته", self.week_list), 1)
        ranks.addWidget(self._rank_panel("۲۵ خریدار برتر — این ماه", self.month_list), 1)
        ranks.addWidget(self._rank_panel("۲۵ خریدار برتر — کل / سال", self.year_list), 1)
        self.body.addLayout(ranks)

        # فروش کدها — زیر مشتریان
        self.codes_title = QLabel("فروش کدهای پارکت (از زیاد به کم)")
        self.codes_title.setStyleSheet("font-size:15px;font-weight:800;color:#0F172A;margin-top:8px;")
        self.body.addWidget(self.codes_title)
        # بدون اسکرول داخلی — اسکرول صفحه اصلی؛ حداقل ۶–۷ کارت دیده می‌شود
        codes_box = QFrame()
        codes_box.setStyleSheet(
            "QFrame{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        codes_box_lay = QVBoxLayout(codes_box)
        codes_box_lay.setContentsMargins(10, 10, 10, 10)
        codes_box_lay.setSpacing(0)
        self.codes_list = QVBoxLayout()
        self.codes_list.setSpacing(8)
        self.codes_list.setContentsMargins(0, 0, 0, 0)
        codes_box_lay.addLayout(self.codes_list)
        codes_box.setMinimumHeight(520)
        self.body.addWidget(codes_box)
        self.body.addStretch(1)

    def _rank_panel(self, title, list_layout):
        box = QFrame()
        box.setStyleSheet(
            "QFrame#rankBox{background:#fff;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        box.setObjectName("rankBox")
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet("font-size:13px;font-weight:700;color:#0F172A;")
        v.addWidget(t)
        host = QWidget()
        host.setLayout(list_layout)
        list_layout.setSpacing(6)
        list_layout.setContentsMargins(0, 0, 0, 0)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setMinimumHeight(420)
        sc.setWidget(host)
        sc.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        # چرخ موس روی لبه به اسکرول والد پاس داده شود
        try:
            sc.setFocusPolicy(Qt.NoFocus)
            host.setFocusPolicy(Qt.NoFocus)
        except Exception:
            pass
        v.addWidget(sc, 1)
        return box

    def _clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                self._clear_layout(it.layout())

    def _load_store_names(self):
        """همه نام‌های ثبت‌شده در تب فروشگاه → باید در آمار پارکت به فروشگاه ایزوفام بروند."""
        names = set()
        try:
            c = db()
            rows = c.execute(
                "SELECT DISTINCT customer FROM store_sales "
                "WHERE customer IS NOT NULL AND TRIM(customer) != ''"
            ).fetchall()
            c.close()
            for r in rows:
                n = str(r[0] or "").strip()
                if n:
                    names.add(n)
        except Exception:
            _swallow()
        return names

    def _norm_customer(self, name):
        s = str(name or "").strip()
        if not s:
            return s
        if s.startswith("فروشگاه ایزوفام") or s.startswith("فروشگاه ايزوفام"):
            return "فروشگاه ایزوفام"
        try:
            try:
                from core_utils import customer_key as _ck
            except Exception:
                from salesmate.core_utils import customer_key as _ck
            if _ck(s).startswith(_ck("فروشگاه ایزوفام")):     # ي/ی، نیم‌فاصله، فاصله‌ی غیرمعمول
                return "فروشگاه ایزوفام"
        except Exception:
            _swallow()
        store_names = getattr(self, "_store_names", None)
        if store_names is None:
            self._store_names = self._load_store_names()
            store_names = self._store_names
        if s in store_names:
            return "فروشگاه ایزوفام"
        # تطبیق بدون فاصله اضافه
        s2 = " ".join(s.split())
        for sn in store_names:
            if s2 == " ".join(str(sn).split()):
                return "فروشگاه ایزوفام"
        return s

    def _store_parquet_extra_rows(self):
        """ردیف‌های پارکت تب فروشگاه را هم به آمار اضافه می‌کند."""
        rows = []
        try:
            c = db()
            data = c.execute(
                "SELECT date, total, tab, items_json, customer FROM store_sales"
            ).fetchall()
            c.close()
        except Exception:
            return rows
        for date_s, total, tab, items_json, customer in data:
            tab_s = str(tab or "").lower()
            is_parquet = tab_s in ("parquet", "پارکت", "")
            meters = 0.0
            try:
                items = json.loads(items_json or "[]")
            except Exception:
                items = []
            if isinstance(items, list):
                for it in items:
                    try:
                        meters += float(en_digits(str(it.get("qty2") or "0")).replace(",", "") or 0)
                    except Exception:
                        _swallow()
            # اگر تب mdf است و متراژ پارکت‌مانند ندارد رد کن
            if tab_s == "mdf" and meters <= 0:
                continue
            if tab_s not in ("parquet", "پارکت", "") and meters <= 0:
                # اگر تب مشخص نیست ولی آیتم دارد، بپذیر
                if not items:
                    continue
            rows.append({
                "تاریخ": en_digits(str(date_s or "")),
                "نام مشتری": "فروشگاه ایزوفام",
                "مبلغ": amount(total),
                "تعداد_ورق": meters,
                "دسته": "پارکت",
            })
        return rows

    def _kpi_card(self, title, amount, meters, color):
        card = QFrame()
        card.setMinimumHeight(108)
        card.setStyleSheet(
            f"QFrame{{background:#FFFFFF;border:1px solid #E2E8F0;"
            f"border-radius:20px;border-top:5px solid {color};}}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet(
            "color:#64748B;font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        a = QLabel(fmt(int(amount)) + " ریال")
        a.setStyleSheet(
            f"color:{color};font-size:18px;font-weight:900;background:transparent;border:none;"
        )
        a.setWordWrap(True)
        m = QLabel(
            "متراژ: "
            + fa_digits(("%g" % round(float(meters), 2)) if meters else "0")
            + " متر"
        )
        m.setStyleSheet(
            "color:#0F172A;font-size:14px;font-weight:700;background:transparent;border:none;"
        )
        lay.addWidget(t)
        lay.addWidget(a)
        lay.addWidget(m)
        lay.addStretch(1)
        return card

    def _mini_month(self, label, amount, meters):
        card = QFrame()
        card.setMinimumWidth(100)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card.setStyleSheet(
            "QFrame{background:#F0F9FF;border:1px solid #BAE6FD;border-radius:12px;}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        t = QLabel(label)
        t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("font-weight:700;color:#0D47A1;font-size:12px;border:none;background:transparent;")
        a = QLabel(fmt(int(amount)))
        a.setAlignment(Qt.AlignCenter)
        a.setStyleSheet("font-weight:800;color:#0F172A;font-size:12px;border:none;background:transparent;")
        a.setWordWrap(True)
        m = QLabel(fa_digits(("%g" % round(float(meters), 2)) if meters else "0") + " م")
        m.setAlignment(Qt.AlignCenter)
        m.setStyleSheet("color:#64748B;font-size:11px;border:none;background:transparent;")
        lay.addWidget(t)
        lay.addWidget(a)
        lay.addWidget(m)
        return card

    def _week_range_text(self, y, w):
        """«از ۱۴۰۵/۰۱/۰۱ تا ۱۴۰۵/۰۱/۰۷» برای هفته‌ی w (از ۰) سال y؛ هفته‌ها بلوک ۷ روزه از اول فروردین‌اند."""
        try:
            r = jalali_week_range(y, w)
            if not r:
                return ""
            (m1, d1), (m2, d2) = r
            y = int(y)
            return ("از " + fa_digits(f"{y:04d}/{m1:02d}/{d1:02d}")
                    + " تا " + fa_digits(f"{y:04d}/{m2:02d}/{d2:02d}"))
        except Exception:
            return ""

    def _week_row(self, label, amount, meters, range_text=""):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{background:#fff;border:1px solid #E2E8F0;border-radius:10px;}"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(12, 8, 12, 8)
        lab = QLabel(label)
        lab.setStyleSheet("font-weight:700;color:#0F172A;font-size:12px;")
        h.addWidget(lab)
        if range_text:
            rng = QLabel(range_text)
            rng.setStyleSheet("color:#64748B;font-size:12px;border:none;")
            h.addWidget(rng, 1)
        else:
            h.addStretch(1)
        amt = QLabel(fmt(int(amount)) + " ریال")
        amt.setStyleSheet("font-weight:700;color:#1565C0;font-size:12px;")
        h.addWidget(amt)
        met = QLabel(fa_digits(("%g" % round(float(meters), 2)) if meters else "0") + " متر")
        met.setStyleSheet("color:#64748B;font-size:12px;")
        h.addWidget(met)
        return row

    def _rank_row(self, rank, name, amount, meters, accent):
        # کارت شبیه «آخرین حواله‌ها» در خانه — بیضی، مبلغ و متراژ واضح
        try:
            bg = get_customer_color(name) or "#EEF2FF"
        except Exception:
            bg = "#EEF2FF"
        row = QFrame()
        row.setStyleSheet(
            f"QFrame{{background:{bg};border:1px solid #E2E8F0;border-radius:28px;}}"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(10)

        badge = QLabel(fa_digits(rank))
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{accent};color:#FFFFFF;border-radius:17px;"
            "font-weight:900;font-size:13px;border:none;"
        )
        h.addWidget(badge)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        n = QLabel(f"<b>{name}</b>")
        n.setStyleSheet(
            "border:none;background:transparent;color:#0F172A;font-size:13px;"
        )
        n.setWordWrap(True)
        mid.addWidget(n)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        amt = QLabel(fmt(int(amount)) + " ریال")
        amt.setStyleSheet(
            "font-weight:800;color:#0F172A;font-size:14px;"
            "border:none;background:transparent;"
        )
        met = QLabel(
            "متراژ: "
            + fa_digits(("%g" % round(float(meters), 2)) if meters else "0")
            + " متر"
        )
        met.setStyleSheet(
            "font-weight:700;color:#0D47A1;font-size:13px;"
            "border:none;background:transparent;"
        )
        stats.addWidget(amt)
        stats.addWidget(met)
        stats.addStretch(1)
        mid.addLayout(stats)
        h.addLayout(mid, 1)
        return row

    
    def _code_row(self, rank, code, product, amount, meters, accent):
        """کارت فروش هر کد — شبیه کارت مشتری صفحه خانه."""
        row = QFrame()
        row.setStyleSheet(
            f"QFrame{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:28px;"
            f"border-right:6px solid {accent};}}"
        )
        h = QHBoxLayout(row)
        h.setContentsMargins(14, 12, 14, 12)
        h.setSpacing(12)

        badge = QLabel(fa_digits(rank))
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{accent};color:#FFFFFF;border-radius:17px;"
            "font-weight:900;font-size:13px;border:none;"
        )
        h.addWidget(badge)

        mid = QVBoxLayout()
        mid.setSpacing(4)
        code_lbl = QLabel(f"<b>کد {fa_digits(code)}</b>")
        code_lbl.setStyleSheet(
            "border:none;background:transparent;color:#0F172A;font-size:14px;"
        )
        mid.addWidget(code_lbl)
        if product:
            pr = QLabel(str(product))
            pr.setStyleSheet(
                "border:none;background:transparent;color:#475569;font-size:12px;"
            )
            pr.setWordWrap(True)
            mid.addWidget(pr)

        stats = QHBoxLayout()
        stats.setSpacing(16)
        amt = QLabel(fmt(int(amount)) + " ریال")
        amt.setStyleSheet(
            "font-weight:900;color:#0F172A;font-size:14px;"
            "border:none;background:transparent;"
        )
        met = QLabel(
            "متراژ: "
            + fa_digits(("%g" % round(float(meters), 2)) if meters else "0")
            + " متر"
        )
        met.setStyleSheet(
            "font-weight:700;color:#0D47A1;font-size:13px;"
            "border:none;background:transparent;"
        )
        stats.addWidget(amt)
        stats.addWidget(met)
        stats.addStretch(1)
        mid.addLayout(stats)
        h.addLayout(mid, 1)
        return row

    def remove_store_duplicates(self):
        """فروش‌های تکراریِ تب فروشگاه (همان تاریخ/شماره/مبلغ با نام مشتریِ متفاوت‌نوشته) را حذف می‌کند؛ یکی نگه داشته می‌شود."""
        try:
            c = db()
            rows = c.execute("SELECT id, customer, invoice_no, date, total FROM store_sales").fetchall()
            dups = find_store_duplicates([(r[0], r[1], r[2], r[3], amount(r[4])) for r in rows])
            if not dups:
                c.close()
                QMessageBox.information(self, "تکراری", "فروش تکراری پیدا نشد.")
                return
            by_id = {r[0]: r for r in rows}
            tot = sum(amount(by_id[d][4]) for d, _k in dups)
            if QMessageBox.question(
                    self, "حذف تکراری‌ها",
                    "%s فروش تکراری (جمع %s ریال) حذف می‌شود و از هر مورد یکی می‌ماند.\nاز ابر هم حذف می‌شود. قبلش پشتیبان گرفته می‌شود.\nادامه؟" % (fa_digits(len(dups)), fmt(tot)),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                c.close()
                return
            try:
                from app_core import rotate_cloud_local_backup
            except Exception:
                from salesmate.app_core import rotate_cloud_local_backup
            try:
                rotate_cloud_local_backup(max_keep=5, force=True)
            except Exception:
                _swallow()
            sales = []
            for d, _k in dups:
                r = by_id[d]
                sales.append({"customer": r[1] or "", "invoiceNo": r[2] or "", "date": r[3] or "", "total": str(r[4] or "0")})
                c.execute("DELETE FROM store_sales WHERE id=?", (d,))
            c.commit()
            c.close()
            try:
                from app_core import delete_store_sale_from_cloud, schedule_supabase_sync
            except Exception:
                from salesmate.app_core import delete_store_sale_from_cloud, schedule_supabase_sync

            def _run():
                for sale in sales:
                    try:
                        delete_store_sale_from_cloud(sale)
                    except Exception:
                        _swallow()
            threading.Thread(target=_run, daemon=True).start()
            try:
                schedule_supabase_sync()
            except Exception:
                _swallow()
            QMessageBox.information(self, "تکراری", "%s فروش تکراری حذف شد." % fa_digits(len(dups)))
            self.refresh()
            try:
                self.win.refresh_all()
            except Exception:
                _swallow()
        except Exception as ex:
            QMessageBox.warning(self, "تکراری", "انجام نشد:\n" + str(ex))

    def show_store_diff(self):
        """فروش‌های تب فروشگاه (امسال) را با اکسل تحلیل فروش مقایسه می‌کند و موارد بدون تطبیق را نشان می‌دهد."""
        from PySide6.QtWidgets import QTextBrowser
        df = self._load_df()
        if df is None:
            QMessageBox.information(self, "مغایرت", "داده‌ی تحلیل فروش نیست.")
            return
        try:
            gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
            j_y = gregorian_to_jalali(gy, gm, gd)[0]
            yp = "%04d/" % j_y
            self._store_names = self._load_store_names()
            d = df[df["دسته"].astype(str).str.contains("پارکت", na=False)].copy() if "دسته" in df.columns else df.copy()
            d["_n"] = d["نام مشتری"].map(self._norm_customer)
            d = d[d["_n"] == "فروشگاه ایزوفام"]
            d["_amt"] = d["مبلغ"].apply(lambda x: amount(x))
            d = d[d["_amt"] != 0]
            d["_ds"] = d["تاریخ"].map(lambda x: en_digits(str(x or "")))
            d = d[d["_ds"].str.startswith(yp)]
            mcol = "تعداد_ورق" if "تعداد_ورق" in d.columns else "تعداد 2"
            ex_rows = []
            for _, r in d.iterrows():
                try:
                    m = float(en_digits(str(r.get(mcol) or 0)).replace(",", "") or 0)
                except Exception:
                    m = 0.0
                ex_rows.append((r["_ds"], r.get("شماره فرم", ""), r["_amt"], m, r.get("نام مشتری", "")))
            c = db()
            rows = [r for r in c.execute("SELECT id, customer, invoice_no, date, total, items_json FROM store_sales").fetchall()
                    if en_digits(str(r[3] or "")).strip().startswith(yp)]
            c.close()
            st_rows = []
            for iid, cust, no, dt, tot, js in rows:
                m = 0.0
                try:
                    for it in json.loads(js or "[]") or []:
                        m += float(en_digits(str(it.get("qty2") or 0)).replace(",", "") or 0)
                except Exception:
                    _swallow()
                st_rows.append((iid, cust, no, dt, amount(tot), m))
            only_store, only_excel = store_diff(ex_rows, st_rows)
        except Exception as ex:
            QMessageBox.warning(self, "مغایرت", "بررسی انجام نشد:\n" + str(ex))
            return
        tot_st = sum(x[3] for x in only_store)
        tot_ex = sum(x[2] for x in only_excel)
        h = ["<div dir='rtl' style='font-size:13px'>"]
        h.append("<b>مجموع تب فروشگاه (امسال):</b> %s ریال — <b>مجموع اکسل (پارکت فروشگاه):</b> %s ریال<br>" % (
            fmt(sum(x[4] for x in st_rows)), fmt(sum(x[2] for x in ex_rows))))
        h.append("<br><b>فقط در تب فروشگاه (در اکسل نیست): %s مورد — %s ریال</b><br>" % (fa_digits(len(only_store)), fmt(tot_st)))
        for d_, no, cu, t, m in only_store:
            h.append("%s · شماره %s · %s · %s ریال · %s متر<br>" % (fa_digits(d_), fa_digits(no), cu, fmt(t), fa_digits("%g" % round(m, 3))))
        try:
            c2 = db()
            all_st = c2.execute("SELECT id, customer, invoice_no, date, total FROM store_sales").fetchall()
            c2.close()
            _byid = {r[0]: r for r in all_st}
            _dups = find_store_duplicates([(r[0], r[1], r[2], r[3], amount(r[4])) for r in all_st])
            if _dups:
                h.append("<br><b>فروش تکراری در تب فروشگاه (همان شماره و تاریخ): %s مورد</b><br>" % fa_digits(len(_dups)))
                for did, kid in _dups[:60]:
                    r1, r2 = _byid[kid], _byid[did]
                    h.append("%s · شماره %s · نگه‌داشته: %s %s ریال · تکراری: %s %s ریال<br>" % (
                        fa_digits(r1[3]), fa_digits(r1[2]), r1[1], fmt(amount(r1[4])), r2[1], fmt(amount(r2[4]))))
        except Exception:
            _swallow()
        dbg = []
        try:
            for (d_, no, cu, t, m) in only_store[:4]:
                sub = df[df["نام مشتری"].map(lambda x: _sig(x) == _sig(cu))]
                dbg.append("<br><b>ردیف‌های اکسل برای «%s» (%s ردیف):</b><br>" % (cu, fa_digits(len(sub))))
                for _, r in sub.head(8).iterrows():
                    nm = str(r.get("نام مشتری", ""))
                    ds = en_digits(str(r.get("تاریخ", "")))
                    why = []
                    if "پارکت" not in str(r.get("دسته", "")):
                        why.append("دسته=" + str(r.get("دسته", "")))
                    if self._norm_customer(nm) != "فروشگاه ایزوفام":
                        why.append("نام ادغام نشد")
                    if amount(r.get("مبلغ", 0)) == 0:
                        why.append("مبلغ صفر")
                    if not ds.startswith(yp):
                        why.append("تاریخ خارج از سال")
                    dbg.append("تاریخ %s · فرم %s · دسته %s · مبلغ %s · %s<br>" % (
                        fa_digits(ds), fa_digits(str(r.get("شماره فرم", ""))), r.get("دسته", ""), fmt(amount(r.get("مبلغ", 0))),
                        ("خارج‌شده: " + "، ".join(why)) if why else "شمرده می‌شود"))
        except Exception as _ex:
            dbg.append("خطا در بررسی: %s<br>" % _ex)
        h.extend(dbg)
        odd = []
        try:
            for nm in sorted({str(x) for x in df["نام مشتری"].dropna().unique()}):
                if "ایزو" in nm.replace("ي", "ی") and self._norm_customer(nm) != "فروشگاه ایزوفام":
                    odd.append(nm)
        except Exception:
            _swallow()
        if odd:
            h.append("<br><b>نام‌هایی در اکسل شبیه فروشگاه ایزوفام که در آمار به فروشگاه نرفته‌اند: %s</b><br>" % fa_digits(len(odd)))
            for nm in odd[:50]:
                h.append("%s<br>" % nm)
        diffs = getattr(store_diff, "last_diffs", [])
        h.append("<br><b>هم‌شماره و هم‌تاریخ ولی مبلغ متفاوت: %s مورد — اختلاف جمع %s ریال</b><br>" % (
            fa_digits(len(diffs)), fmt(sum(x[3] - x[4] for x in diffs))))
        for d_, no, cu, st_t, ex_t in diffs[:200]:
            h.append("%s · شماره %s · %s · فروشگاه %s · اکسل %s · اختلاف %s<br>" % (fa_digits(d_), fa_digits(no), cu, fmt(st_t), fmt(ex_t), fmt(st_t - ex_t)))
        h.append("<br>تعداد: فروش فروشگاه %s · گروه اکسل %s<br>" % (fa_digits(len(st_rows)), fa_digits(len(set((x[0], str(x[1])) for x in ex_rows)))))
        h.append("<br><b>فقط در اکسل (در تب فروشگاه نیست): %s مورد — %s ریال</b><br>" % (fa_digits(len(only_excel)), fmt(tot_ex)))
        for d_, f, t, m in only_excel:
            h.append("%s · شماره %s · %s ریال · %s متر<br>" % (fa_digits(d_), fa_digits(f), fmt(t), fa_digits("%g" % round(m, 3))))
        h.append("</div>")
        dlg = QDialog(self)
        dlg.setWindowTitle("مغایرت فروشگاه با اکسل")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(760, 620)
        lay = QVBoxLayout(dlg)
        tb = QTextBrowser()
        tb.setHtml("".join(h))
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        b0 = QPushButton("حذف تکراری‌های فروشگاه")
        b0.setStyleSheet("QPushButton{background:#DC2626;color:#fff;border:none;border-radius:8px;padding:8px 14px;font-weight:700;}")
        b0.clicked.connect(lambda: (self.remove_store_duplicates(), dlg.accept()))
        row.addWidget(b0)
        b1 = QPushButton("کپی متن")
        b1.clicked.connect(lambda: QApplication.clipboard().setText(tb.toPlainText()))
        b2 = QPushButton("بستن")
        b2.clicked.connect(dlg.accept)
        row.addWidget(b1)
        row.addStretch(1)
        row.addWidget(b2)
        lay.addLayout(row)
        dlg.exec()

    @staticmethod
    def parquet_type_of(code, name):
        """نوع پارکت: جناغی / والنته / بقیه (جناغی بر اساس نام، قاعده‌ی ثابت برنامه)."""
        nm = str(name or "")
        low = nm.lower()
        if "جناغی" in nm or "جناقی" in nm:
            return "جناغی"
        if "valente" in low or "والنته" in nm or "ولنته" in nm:
            return "والنته"
        try:
            prod = core.resolve_product(code, nm)
        except Exception:
            prod = ""
        if prod == "Valente":
            return "والنته"
        if prod == "Charlotte":
            return "جناغی"
        return "بقیه"

    @staticmethod
    def code_key(code, name):
        """کلید ردیف کد: برای جناغی، A و B یک ردیف می‌شوند (کد = عدد اصلی، مثلاً 6235)."""
        c = en_digits(str(code or "")).strip()
        if ParquetStatsPage.parquet_type_of(c, name) == "جناغی":
            nm = en_digits(str(name or ""))
            # شماره‌ی مدل جناغی (مثل 6433) در آخر نام است؛ کد کالا برای A و B فرق دارد
            m = (re.search(r"(\d{4})\s*[ABab]?\s*$", nm)
                 or re.search(r"(\d{4})(?!.*\d{4})", nm)
                 or re.match(r"\s*(\d{1,5})(?!\d)", c))
            if m:
                return m.group(1)
        return c

    @staticmethod
    def code_name(code, name):
        """نام نمایشی: برای جناغی پسوند A/B حذف می‌شود."""
        nm = str(name or "").strip()
        if ParquetStatsPage.parquet_type_of(str(code or ""), nm) == "جناغی":
            nm = re.sub(r"[\s\-_]*\b[ABab]\s*$", "", nm).strip()
        return nm

    @staticmethod
    def _norm_date_in(txt):
        parts = en_digits(str(txt or "")).replace("-", "/").split("/")
        try:
            return "%04d/%02d/%02d" % (int(parts[0]), int(parts[1]), int(parts[2]))
        except Exception:
            return ""

    def _fill_types(self, *_):
        self._clear_layout(self.type_row)
        pdf = getattr(self, "_pdf_types", None)
        if pdf is None or getattr(pdf, "empty", True):
            self.type_note.setText("ابتدا داده‌ی تحلیل فروش لازم است.")
            return
        d1 = self._norm_date_in(self.type_from.text())
        d2 = self._norm_date_in(self.type_to.text())
        if (self.type_from.text().strip() and not d1) or (self.type_to.text().strip() and not d2):
            self.type_note.setText("تاریخ را به شکل 1405/08/08 بنویسید.")
            return
        sub = pdf
        ds = sub["_dsn"]
        if d1:
            sub = sub[ds >= d1]
            ds = sub["_dsn"]
        if d2:
            sub = sub[ds <= d2]
        code_col = None
        for cand in ("کد کالا", "کد", "code"):
            if cand in sub.columns:
                code_col = cand
                break
        name_col = None
        for cand in ("نام کالا", "نام محصول", "نوع"):
            if cand in sub.columns:
                name_col = cand
                break
        cats = []
        for _, r in sub.iterrows():
            cats.append(self.parquet_type_of(
                en_digits(str(r[code_col] or "")) if code_col else "",
                r[name_col] if name_col else "",
            ))
        sub = sub.copy()
        sub["_t"] = cats
        colors = {"جناغی": "#D97706", "والنته": "#7C3AED", "بقیه": "#1565C0"}
        tot_a = tot_m = 0.0
        for k in ("جناغی", "والنته", "بقیه"):
            g = sub[sub["_t"] == k]
            a, m = float(g["_amt"].sum()), float(g["_m"].sum())
            tot_a += a
            tot_m += m
            self.type_row.addWidget(self._kpi_card("پارکت " + k if k != "بقیه" else "بقیه‌ی پارکت‌ها", a, m, colors[k]))
        self.type_row.addWidget(self._kpi_card("جمع پارکت", tot_a, tot_m, "#059669"))
        rng = (d1 or "ابتدا") + " تا " + (d2 or "انتها")
        self.type_note.setText(
            f"بازه: {fa_digits(rng)} · {fa_digits(len(sub))} ردیف · "
            "تشخیص نوع از نام کالا: «جناغی» و «Valente/والنته»؛ بقیه در «بقیه‌ی پارکت‌ها»."
        )

    def _load_df(self):
        try:
            if self.win and getattr(self.win, "analysis_page", None) is not None:
                df = getattr(self.win.analysis_page, "df", None)
                if df is not None and not getattr(df, "empty", True):
                    return df
        except Exception:
            _swallow()
        try:
            cache = APP_DIR / "analysis_sales_cache.pkl"
            if cache.exists():
                import pandas as pd
                df = pd.read_pickle(str(cache))
                if df is not None and not getattr(df, "empty", True):
                    return df
        except Exception:
            _swallow()
        return None

    def _month_key(self, date_s):
        parts = en_digits(str(date_s or "")).split("/")
        try:
            return (int(parts[0]), int(parts[1]))
        except Exception:
            return (0, 0)

    def _week_key(self, date_s):
        parts = en_digits(str(date_s or "")).split("/")
        if len(parts) < 3:
            return (0, 0)
        try:
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        except Exception:
            return (0, 0)
        days = (m - 1) * 31
        if m > 6:
            days = 6 * 31 + (m - 7) * 30
        days += d
        return (y, (days - 1) // 7)

    def refresh(self):
        lays = [self.kpi_row, self.months_row,
                self.week_list, self.month_list, self.year_list]
        if hasattr(self, "codes_list"):
            lays.append(self.codes_list)
        for lay in lays:
            self._clear_layout(lay)
        self._store_names = self._load_store_names()
        self._pdf_types = None
        self._clear_layout(self.type_row)

        df = self._load_df()
        if df is None or getattr(df, "empty", True):
            self.hint.setText("داده تحلیل فروش نیست")
            empty = QLabel("ابتدا در «تحلیل فروش» اکسل را بارگذاری کنید، بعد بروزرسانی بزنید.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#94A3B8;padding:30px;font-size:14px;")
            self.kpi_row.addWidget(empty)
            return

        if "دسته" in df.columns:
            pdf = df[df["دسته"].astype(str).str.contains("پارکت", na=False)].copy()
        else:
            pdf = df.copy()

        # ردیف‌های تب فروشگاه جدا اضافه نمی‌شوند (در اکسل تحلیل هستن و باعث دوبار شماری می‌شد)
        # فقط نام‌های ثبت‌شده در فروشگاه → ادغام به «فروشگاه ایزوفام»

        if pdf.empty:
            self.hint.setText("ردیف پارکت نیست")
            empty = QLabel("در داده بارگذاری‌شده فروش پارکت پیدا نشد.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#94A3B8;padding:30px;")
            self.kpi_row.addWidget(empty)
            return

        # نام‌های موجود در تب فروشگاه + فروشگاه ایزوفام* → «فروشگاه ایزوفام»
        pdf["نام_نرمال"] = (
            pdf["نام مشتری"].map(self._norm_customer)
            if "نام مشتری" in pdf.columns
            else "فروشگاه ایزوفام"
        )
        pdf["_amt"] = pdf["مبلغ"].apply(lambda x: amount(x)) if "مبلغ" in pdf.columns else 0
        if "تعداد_ورق" in pdf.columns:
            pdf["_m"] = pdf["تعداد_ورق"].apply(
                lambda x: float(en_digits(str(x or 0)).replace(",", "") or 0)
            )
        elif "تعداد 2" in pdf.columns:
            pdf["_m"] = pdf["تعداد 2"].apply(
                lambda x: float(en_digits(str(x or 0)).replace(",", "") or 0)
            )
        else:
            pdf["_m"] = 0.0

        # ردیف‌های با مبلغ ۰ در آمار نیایند
        if "مبلغ" in pdf.columns:
            pdf = pdf[pdf["_amt"] != 0].copy()
            if pdf.empty:
                self.hint.setText("ردیف با مبلغ غیرصفر نیست")
                empty = QLabel("در داده بارگذاری‌شده فروش پارکتِ دارای مبلغ پیدا نشد.")
                empty.setAlignment(Qt.AlignCenter)
                empty.setStyleSheet("color:#94A3B8;padding:30px;")
                self.kpi_row.addWidget(empty)
                self.month_chart.set_points([])
                self.week_chart.set_points([])
                return

        today, _ = now_jalali()
        gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
        j_y, j_m, j_d = gregorian_to_jalali(gy, gm, gd)
        year_prefix = f"{j_y:04d}/"
        month_prefix = f"{j_y:04d}/{j_m:02d}"
        cur_week = self._week_key(today)

        pdf["_ds"] = pdf["تاریخ"].map(lambda x: en_digits(str(x or ""))) if "تاریخ" in pdf.columns else ""
        pdf["_dsn"] = pdf["_ds"].map(self._norm_date_in)
        self._pdf_types = pdf
        if not self.type_to.text().strip():
            self.type_to.setText(today)
        if not self.type_from.text().strip():
            self.type_from.setText(f"{j_y:04d}/01/01")
        self._fill_types()
        pdf["_wk"] = pdf["_ds"].map(self._week_key)

        week_df = pdf[pdf["_wk"].apply(lambda k: k == cur_week)] if cur_week != (0, 0) else pdf.iloc[0:0]
        month_df = pdf[pdf["_ds"].astype(str).str.startswith(month_prefix)]
        year_df = pdf[pdf["_ds"].astype(str).str.startswith(year_prefix)]
        # اگر سال خالی بود کل داده
        all_df = pdf

        self.kpi_row.addWidget(
            self._kpi_card("فروش کل هفته", week_df["_amt"].sum(), week_df["_m"].sum(), "#1565C0")
        )
        self.kpi_row.addWidget(
            self._kpi_card("فروش کل ماه", month_df["_amt"].sum(), month_df["_m"].sum(), "#059669")
        )
        self.kpi_row.addWidget(
            self._kpi_card("فروش کل سال", year_df["_amt"].sum(), year_df["_m"].sum(), "#7C3AED")
        )
        self.kpi_row.addWidget(
            self._kpi_card("فروش کل (همه داده)", all_df["_amt"].sum(), all_df["_m"].sum(), "#D97706")
        )

        # ۱۰ خریدار برتر هر ماه / هر هفته (برای tooltip)
        pdf["_mkS"] = pdf["_ds"].map(lambda d: "%d-%d" % self._month_key(d))
        pdf["_wkS"] = pdf["_wk"].map(lambda k: "%d-%d" % (k[0], k[1]))

        def top10_map(col):
            out = {}
            g = pdf.groupby([col, "نام_نرمال"], dropna=False).agg(a=("_amt", "sum"), m=("_m", "sum")).reset_index()
            for key, sub in g.groupby(col):
                sub = sub.sort_values(["a", "m"], ascending=False).head(10)
                out[key] = [(str(n), float(a), float(m)) for n, a, m in zip(sub["نام_نرمال"], sub["a"], sub["m"])]
            return out

        month_top = top10_map("_mkS")
        week_top = top10_map("_wkS")

        # ماه‌ها — شبکه‌ی ۶ تایی
        month_groups = {}
        for _, r in pdf.iterrows():
            y, m = self._month_key(r.get("_ds"))
            if (y, m) == (0, 0):
                continue
            key = (y, m)
            if key not in month_groups:
                month_groups[key] = [0, 0.0]
            month_groups[key][0] += float(r.get("_amt") or 0)
            month_groups[key][1] += float(r.get("_m") or 0)
        month_points = []
        for idx, (y, m) in enumerate(sorted(month_groups.keys())):
            lab = f"{self.MONTH_FA[m] if 1 <= m <= 12 else m} {fa_digits(y)}"
            amt, met = month_groups[(y, m)]
            tip = _top10_tooltip_html("۱۰ خریدار برتر — " + lab, month_top.get("%d-%d" % (y, m), []))
            card = self._mini_month(lab, amt, met)
            card.setToolTip(tip)
            self.months_row.addWidget(card, idx // self.MONTHS_PER_ROW, idx % self.MONTHS_PER_ROW)
            month_points.append({
                "label": self.MONTH_FA[m] if 1 <= m <= 12 else str(m),
                "sub": fa_digits(y), "amt": amt, "met": met, "tip": tip,
            })
        if not month_groups:
            self.months_row.addWidget(QLabel("—"), 0, 0)
        self.month_chart.set_points(month_points)

        # هفته‌ها (همه)
        week_groups = {}
        for _, r in pdf.iterrows():
            wk = r.get("_wk")
            if not wk or wk == (0, 0):
                continue
            if wk not in week_groups:
                week_groups[wk] = [0, 0.0]
            week_groups[wk][0] += float(r.get("_amt") or 0)
            week_groups[wk][1] += float(r.get("_m") or 0)

        # نمودار هفتگی: هفته‌های پیوسته‌ی ۷ روزه از اول سال (بدون توجه به شروع ماه)؛ هفته‌ی بدون فروش = ۰
        week_points = []
        if week_groups:
            ks = sorted(week_groups.keys())
            seq, (cy, cw) = [], ks[0]
            guard = 0
            while (cy, cw) <= ks[-1] and guard < 2000:
                seq.append((cy, cw))
                cw += 1
                if cw > 52:
                    cy, cw = cy + 1, 0
                guard += 1
            for (y, w) in seq:
                amt, met = week_groups.get((y, w), [0, 0.0])
                rng = self._week_range_text(y, w)
                sub = ""
                try:
                    r = jalali_week_range(y, w)
                    if r:
                        (m1, d1), _e = r
                        sub = fa_digits(f"{m1:02d}/{d1:02d}")
                except Exception:
                    _swallow()
                week_points.append({
                    "label": f"هفته {fa_digits(w + 1)}", "sub": sub, "amt": amt, "met": met,
                    "tip": _top10_tooltip_html(f"۱۰ خریدار برتر — هفته {fa_digits(w + 1)} سال {fa_digits(y)} {rng}",
                                               week_top.get("%d-%d" % (y, w), [])),
                })
        self.week_chart.set_points(week_points)

        def top25(sub):
            if sub is None or getattr(sub, "empty", True):
                return []
            g = (
                sub.groupby("نام_نرمال", dropna=False)
                .agg(amount=("_amt", "sum"), meters=("_m", "sum"))
                .reset_index()
                .sort_values(["amount", "meters"], ascending=False)
                .head(25)
            )
            out = []
            for _, row in g.iterrows():
                out.append((str(row["نام_نرمال"]), float(row["amount"]), float(row["meters"])))
            return out

        colors = ["#1565C0", "#059669", "#D97706", "#DC2626", "#7C3AED", "#0EA5E9", "#84CC16"]

        def fill_rank(layout, rows):
            if not rows:
                e = QLabel("موردی نیست")
                e.setStyleSheet("color:#94A3B8;padding:8px;")
                layout.addWidget(e)
            else:
                for i, (name, amt, met) in enumerate(rows, 1):
                    layout.addWidget(
                        self._rank_row(i, name, amt, met, colors[(i - 1) % len(colors)])
                    )
            layout.addStretch(1)

        fill_rank(self.week_list, top25(week_df))
        fill_rank(self.month_list, top25(month_df))
        # کل / سال: اول سال جاری، اگر کمتر از ۲۵ بود از کل داده
        year_top = top25(year_df)
        if len(year_top) < 25:
            year_top = top25(all_df)
        fill_rank(self.year_list, year_top)

        # —— فروش کدها (کل داده پارکت، از زیاد به کم)
        if hasattr(self, "codes_list"):
            code_col = None
            for cand in ("کد کالا", "کد", "code"):
                if cand in pdf.columns:
                    code_col = cand
                    break
            name_col = None
            for cand in ("نام کالا", "نام محصول", "نوع"):
                if cand in pdf.columns:
                    name_col = cand
                    break
            if code_col:
                try:
                    tmp = pdf.copy()
                    _nc = name_col
                    tmp["_code"] = [
                        self.code_key(c_, (n_ if _nc else ""))
                        for c_, n_ in zip(tmp[code_col], tmp[_nc] if _nc else [""] * len(tmp))
                    ]
                    if _nc:
                        tmp["_nm"] = [self.code_name(c_, n_) for c_, n_ in zip(tmp[code_col], tmp[_nc])]
                    tmp = tmp[tmp["_code"].astype(str).str.len() > 0]
                    if name_col:
                        # نام پرتکرار هر کد
                        def _mode_name(s):
                            try:
                                v = s.dropna().astype(str)
                                v = v[v.str.strip() != ""]
                                if v.empty:
                                    return ""
                                return v.value_counts().index[0]
                            except Exception:
                                return ""
                        g = (
                            tmp.groupby("_code", dropna=False)
                            .agg(
                                amount=("_amt", "sum"),
                                meters=("_m", "sum"),
                                product=("_nm", _mode_name),
                            )
                            .reset_index()
                            .sort_values(["amount", "meters"], ascending=False)
                        )
                    else:
                        g = (
                            tmp.groupby("_code", dropna=False)
                            .agg(amount=("_amt", "sum"), meters=("_m", "sum"))
                            .reset_index()
                            .sort_values(["amount", "meters"], ascending=False)
                        )
                        g["product"] = ""
                    colors_c = [
                        "#1565C0", "#059669", "#D97706", "#DC2626",
                        "#7C3AED", "#0EA5E9", "#84CC16", "#DB2777",
                    ]
                    if g.empty:
                        e = QLabel("کدی در داده پارکت نیست")
                        e.setStyleSheet("color:#94A3B8;padding:12px;")
                        self.codes_list.addWidget(e)
                    else:
                        for i, row in enumerate(g.itertuples(index=False), 1):
                            code = getattr(row, "_code", "") or ""
                            amt = float(getattr(row, "amount", 0) or 0)
                            met = float(getattr(row, "meters", 0) or 0)
                            prod = str(getattr(row, "product", "") or "")
                            self.codes_list.addWidget(
                                self._code_row(
                                    i, code, prod, amt, met,
                                    colors_c[(i - 1) % len(colors_c)],
                                )
                            )
                    self.codes_list.addStretch(1)
                except Exception as ex:
                    e = QLabel("خطا در آمار کدها: " + str(ex)[:80])
                    e.setStyleSheet("color:#B91C1C;padding:8px;")
                    self.codes_list.addWidget(e)
            else:
                e = QLabel("ستون «کد کالا» در اکسل تحلیل پیدا نشد.")
                e.setStyleSheet("color:#94A3B8;padding:12px;")
                self.codes_list.addWidget(e)

        self.hint.setText(
            f"{fa_digits(len(pdf))} ردیف پارکت · "
            f"هفته: {fa_digits(week_df['نام_نرمال'].nunique() if not week_df.empty else 0)} خریدار · "
            f"ماه: {fa_digits(month_df['نام_نرمال'].nunique() if not month_df.empty else 0)} · "
            f"کل: {fa_digits(pdf['نام_نرمال'].nunique())}"
        )


class _NumItem(QTableWidgetItem):
    """سلول عددی که درست مرتب می‌شود (نه به‌صورت متن)."""
    def __init__(self, value, text=None):
        super().__init__(text if text is not None else fa_digits(("%g" % value) if value else "0"))
        self._v = float(value or 0)
        self.setTextAlignment(Qt.AlignCenter)

    def __lt__(self, other):
        try:
            return self._v < other._v
        except Exception:
            return super().__lt__(other)


class FreeItemsPage(QWidget):
    """سمپل / استند / نمونه: هر مشتری چندتا گرفته (ردیف‌های با مبلغ صفر اکسل تحلیل فروش)."""

    HEAD = ["مشتری", "سمپل", "استند", "نمونه", "سایر (قیمت صفر)", "جمع", "آخرین تاریخ"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self._df = None
        self._table_df = None
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("سمپل، استند و نمونه")
        title.setStyleSheet("font-size:20px;font-weight:800;color:#0F172A;")
        head.addWidget(title)
        head.addStretch()
        self.hint = QLabel("")
        self.hint.setStyleSheet("color:#64748B;font-size:12px;")
        head.addWidget(self.hint)
        btn_csv = QPushButton("⬇ خروجی CSV")
        btn_csv.setCursor(Qt.PointingHandCursor)
        btn_csv.setStyleSheet(
            "QPushButton{background:#16A34A;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
            "QPushButton:hover{background:#15803D;}")
        btn_csv.clicked.connect(self.export_csv)
        head.addWidget(btn_csv)
        ref = QPushButton("↻ بروزرسانی")
        ref.setCursor(Qt.PointingHandCursor)
        ref.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;padding:8px 16px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}")
        ref.clicked.connect(self.refresh)
        head.addWidget(ref)
        root.addLayout(head)

        tip = QLabel("ردیف‌هایی از اکسل «تحلیل فروش» که مبلغشان صفر است؛ نوع از روی نام کالا/برگه تشخیص داده می‌شود. "
                     "روی هر مشتری دو بار کلیک کنید تا ریز ردیف‌ها را ببینید.")
        tip.setWordWrap(True)
        tip.setStyleSheet("color:#64748B;font-size:12px;")
        root.addWidget(tip)

        flt = QHBoxLayout()
        flt.addWidget(QLabel("ماه:"))
        self.cmb_month = QComboBox()
        self.cmb_month.setMinimumWidth(140)
        self.cmb_month.currentIndexChanged.connect(lambda *_: self._fill_table())
        flt.addWidget(self.cmb_month)
        flt.addSpacing(8)
        flt.addWidget(QLabel("دسته:"))
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(list(CATEGORY_CHOICES))
        self.cmb_cat.setMinimumWidth(110)
        self.cmb_cat.currentIndexChanged.connect(lambda *_: self._fill_table())
        flt.addWidget(self.cmb_cat)
        flt.addSpacing(12)
        self.ed_search = QLineEdit()
        self.ed_search.setPlaceholderText("جستجوی نام مشتری…")
        self.ed_search.setClearButtonEnabled(True)
        self.ed_search.textChanged.connect(lambda *_: self._fill_table())
        flt.addWidget(self.ed_search, 1)
        root.addLayout(flt)

        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(10)
        root.addLayout(self.kpi_row)

        self.table = QTableWidget(0, len(self.HEAD))
        self.table.setHorizontalHeaderLabels(self.HEAD)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.cellDoubleClicked.connect(self._open_detail)
        root.addWidget(self.table, 1)

    _load_df = ParquetStatsPage._load_df

    def _clear_kpis(self):
        while self.kpi_row.count():
            it = self.kpi_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _kpi(self, title, value, color):
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:#fff;border:1px solid #E2E8F0;border-radius:14px;border-top:4px solid {color};}}")
        l = QVBoxLayout(card)
        l.setContentsMargins(12, 8, 12, 8)
        l.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet("color:#64748B;font-size:12px;font-weight:700;border:none;background:transparent;")
        v = QLabel(fa_digits(("%g" % value) if value else "0"))
        v.setStyleSheet(f"color:{color};font-size:20px;font-weight:900;border:none;background:transparent;")
        l.addWidget(t)
        l.addWidget(v)
        return card

    def refresh(self):
        df = self._load_df()
        self._df = df
        cur = self.cmb_month.currentText()
        self.cmb_month.blockSignals(True)
        self.cmb_month.clear()
        self.cmb_month.addItem("همه")
        try:
            if df is not None and "ماه" in df.columns:
                for m in sorted(x for x in df["ماه"].dropna().astype(str).unique().tolist() if x):
                    self.cmb_month.addItem(m)
        except Exception:
            _swallow()
        i = self.cmb_month.findText(cur)
        self.cmb_month.setCurrentIndex(i if i >= 0 else 0)
        self.cmb_month.blockSignals(False)
        self._fill_table()

    def _fill_table(self):
        self._clear_kpis()
        df = self._df
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        if df is None or getattr(df, "empty", True):
            self.hint.setText("داده تحلیل فروش نیست")
            self.kpi_row.addWidget(QLabel("ابتدا در «تحلیل فروش» اکسل را بارگذاری کنید، بعد بروزرسانی بزنید."))
            self.table.setSortingEnabled(True)
            return
        month = self.cmb_month.currentText() or "همه"
        t = free_items_by_customer(df, month=month, search=self.ed_search.text(), category=self.cmb_cat.currentText())
        self._table_df = t
        for r, row in enumerate(t.to_dict("records")):
            self.table.insertRow(r)
            name = QTableWidgetItem(str(row["مشتری"]))
            name.setData(Qt.UserRole, row["_key"])
            name.setToolTip(f"{row['مشتری']}\n{fa_digits(row['ردیف'])} ردیف · متراژ: "
                            f"{fa_digits(('%g' % round(row['متراژ'], 2)) if row['متراژ'] else '0')} متر")
            self.table.setItem(r, 0, name)
            for c, key in enumerate(list(FREE_TYPES) + [OTHER_FREE, "جمع"], 1):
                it = _NumItem(row[key])
                if key == OTHER_FREE:
                    it.setForeground(QColor("#94A3B8"))
                if key == "جمع":
                    f = it.font(); f.setBold(True); it.setFont(f)
                self.table.setItem(r, c, it)
            d = QTableWidgetItem(fa_digits(row["آخرین تاریخ"]))
            d.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 6, d)
        self.table.setSortingEnabled(True)
        self.table.sortItems(5, Qt.DescendingOrder)

        tot = {k: float(t[k].sum()) if len(t) else 0.0 for k in list(FREE_TYPES) + [OTHER_FREE]}
        colors = {"سمپل": "#1565C0", "استند": "#7C3AED", "نمونه": "#059669", OTHER_FREE: "#94A3B8"}
        for k in list(FREE_TYPES) + [OTHER_FREE]:
            self.kpi_row.addWidget(self._kpi("کل " + k if k != OTHER_FREE else "سایر (قیمت صفر)", tot[k], colors[k]))
        self.kpi_row.addWidget(self._kpi("تعداد مشتری", len(t), "#D97706"))
        self.hint.setText(f"{fa_digits(len(t))} مشتری")

    def _open_detail(self, row, col):
        try:
            it = self.table.item(row, 0)
            key = it.data(Qt.UserRole)
            z = free_items_of_customer(self._df, key)
            month = self.cmb_month.currentText() or "همه"
            if month != "همه" and "ماه" in z.columns:
                z = z[z["ماه"].astype(str) == month]
            z = filter_category(z, self.cmb_cat.currentText())
            dlg = QDialog(self)
            dlg.setWindowTitle("ریز ردیف‌ها — " + it.text())
            dlg.setLayoutDirection(Qt.RightToLeft)
            dlg.resize(1100, 760)
            lay = QVBoxLayout(dlg)
            # —— بالا: تفکیک نوع‌ها + جدول آمار کالاها
            totals, prod_rows = free_items_breakdown(z)
            chips = QHBoxLayout()
            chip_colors = {"سمپل": "#1565C0", "استند": "#7C3AED", "نمونه": "#059669", OTHER_FREE: "#94A3B8"}
            for tname in list(FREE_TYPES) + [OTHER_FREE]:
                cnt = totals.get(tname, 0.0)
                chip = QLabel("%s: %s" % (tname if tname != OTHER_FREE else "سایر", fa_digits("%g" % cnt)))
                chip.setAlignment(Qt.AlignCenter)
                chip.setStyleSheet(
                    "background:%s;color:#fff;border-radius:10px;padding:8px 16px;font-weight:800;font-size:14px;"
                    % (chip_colors[tname] if cnt else "#CBD5E1"))
                chips.addWidget(chip)
            chip_all = QLabel("جمع: " + fa_digits("%g" % sum(totals.values())))
            chip_all.setAlignment(Qt.AlignCenter)
            chip_all.setStyleSheet("background:#D97706;color:#fff;border-radius:10px;padding:8px 16px;font-weight:800;font-size:14px;")
            chips.addWidget(chip_all)
            lay.addLayout(chips)
            sh = ["کالا", "نوع", "تعداد", "متراژ", "ردیف"]
            st = QTableWidget(len(prod_rows), len(sh))
            st.setHorizontalHeaderLabels(sh)
            st.setEditTriggers(QTableWidget.NoEditTriggers)
            st.verticalHeader().setVisible(False)
            st.setAlternatingRowColors(True)
            st.setTextElideMode(Qt.ElideNone)
            sh_h = st.horizontalHeader()
            for c in range(len(sh)):
                sh_h.setSectionResizeMode(c, QHeaderView.Stretch if c == 0 else QHeaderView.ResizeToContents)
            for r_i, pr in enumerate(prod_rows):
                vals = [pr["کالا"], pr["نوع"], fa_digits("%g" % pr["تعداد"]),
                        fa_digits("%g" % round(pr["متراژ"], 2)), fa_digits(str(pr["ردیف"]))]
                for c, v in enumerate(vals):
                    cell = QTableWidgetItem(v)
                    cell.setTextAlignment(Qt.AlignCenter if c else (Qt.AlignRight | Qt.AlignVCenter))
                    cell.setToolTip(pr["کالا"])
                    st.setItem(r_i, c, cell)
            st.setMinimumHeight(150)
            st.setMaximumHeight(230)
            lay.addWidget(QLabel("آمار کالاها (تفکیک نوع):"))
            lay.addWidget(st)
            lay.addWidget(QLabel("ریز ردیف‌ها:"))
            head = ["تاریخ", "شماره فرم", "کد کالا", "شرح کالا", "نوع", "تعداد", "متراژ"]
            tb = QTableWidget(len(z), len(head))
            tb.setHorizontalHeaderLabels(head)
            tb.setEditTriggers(QTableWidget.NoEditTriggers)
            tb.setSelectionBehavior(QTableWidget.SelectRows)
            tb.setSelectionMode(QTableWidget.SingleSelection)
            tb.setWordWrap(True)
            tb.setTextElideMode(Qt.ElideNone)
            tb.verticalHeader().setVisible(False)
            hh = tb.horizontalHeader()
            for c in range(len(head)):
                hh.setSectionResizeMode(c, QHeaderView.Stretch if c == 3 else QHeaderView.ResizeToContents)
            full_names = []
            for r, rec in enumerate(z.to_dict("records")):
                full = str(rec.get("نام کالا", ""))
                full_names.append(full)
                vals = [
                    fa_digits(rec.get("_ds", "")), fa_digits(str(rec.get("شماره فرم", ""))),
                    fa_digits(str(rec.get("کد کالا", ""))), full, str(rec.get("_type", "")),
                    fa_digits(("%g" % rec.get("_units", 0))), fa_digits(("%g" % round(float(rec.get("_m", 0) or 0), 2))),
                ]
                for c, v in enumerate(vals):
                    cell = QTableWidgetItem(v)
                    cell.setTextAlignment(Qt.AlignCenter if c != 3 else (Qt.AlignRight | Qt.AlignVCenter))
                    cell.setToolTip(full if full else v)      # موس روی هر خانه = شرح کامل کالا
                    tb.setItem(r, c, cell)
            tb.resizeRowsToContents()
            lay.addWidget(tb, 1)
            full_lbl = QLabel("روی یک ردیف کلیک کنید یا موس را روی آن نگه دارید تا شرح کامل کالا اینجا نوشته شود.")
            full_lbl.setWordWrap(True)
            full_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            full_lbl.setStyleSheet("background:#F0F9FF;border:1px solid #BAE6FD;border-radius:10px;padding:10px;font-size:14px;")
            lay.addWidget(full_lbl)

            def _show_full(r, c, _pr, _pc):
                if 0 <= r < len(full_names):
                    full_lbl.setText("شرح کامل کالا: " + (full_names[r] or "—"))
            tb.currentCellChanged.connect(_show_full)
            dlg.exec()
        except Exception:
            _swallow()

    def export_csv(self):
        t = self._table_df
        if t is None or getattr(t, "empty", True):
            QMessageBox.information(self, "خروجی", "داده‌ای برای خروجی نیست.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره CSV", str(APP_DIR / "samples_stands.csv"), "CSV (*.csv)")
        if not path:
            return
        try:
            t.drop(columns=["_key"]).to_csv(path, index=False, encoding="utf-8-sig")
            QMessageBox.information(self, "خروجی", "ذخیره شد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))
