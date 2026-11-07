# -*- coding: utf-8 -*-
"""تب «مقایسه فروش»: سه نمودار (کل تجمعی، ماه، هفته) با یک خط رنگی برای هر همکار و یک خط برای مالک.
روی هر نقطه نگه دارید: مبلغ، متر مربع پارکت و ورق ام دی اف نمایش داده می‌شود."""
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QFont, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QScrollArea, QToolTip, QFrame,
)

try:
    import coworker_core as cw
except Exception:
    from salesmate import coworker_core as cw
try:
    from app_core import _abbr_amount, fa_digits
except Exception:
    from salesmate.app_core import _abbr_amount, fa_digits

COLORS = ["#1565C0", "#16A34A", "#F59E0B", "#DC2626", "#7C3AED", "#0891B2", "#DB2777", "#65A30D"]


def _fmt_q(v):
    return fa_digits(("%g" % round(float(v or 0), 1)))


class MultiLineChart(QWidget):
    """نمودار چندخطی؛ هر نقطه [مبلغ، متر مربع پارکت، ورق ام دی اف]."""
    SLOT = 56
    PAD_L, PAD_R, PAD_T, PAD_B = 74.0, 16.0, 40.0, 42.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.series = []        # [{name,color,pts:[[a,p,m],...]}]
        self._hover = None      # (series_index, point_index)
        self.setMouseTracking(True)
        self.setMinimumHeight(330)

    def set_data(self, labels, series):
        self.labels = list(labels or [])
        self.series = list(series or [])
        self._hover = None
        self.setMinimumWidth(max(560, len(self.labels) * self.SLOT + 100))
        self.update()

    def _plot(self):
        W, H = float(self.width()), float(self.height())
        return QRectF(self.PAD_L, self.PAD_T, max(W - self.PAD_L - self.PAD_R, 10.0), max(H - self.PAD_T - self.PAD_B, 10.0))

    def _xy(self, si, pi, plot, mx):
        n = max(len(self.labels), 1)
        x = plot.left() + (pi + 0.5) * plot.width() / n
        a = max(float(self.series[si]["pts"][pi][0]), 0.0)
        y = plot.bottom() - (a / mx) * plot.height()
        return x, y

    def _max(self):
        return max([float(p[0]) for s in self.series for p in s["pts"]] + [1.0])

    def paintEvent(self, ev):
        pa = QPainter(self)
        pa.setRenderHint(QPainter.Antialiasing, True)
        pa.setRenderHint(QPainter.TextAntialiasing, True)
        W, H = self.width(), self.height()
        pa.setPen(QPen(QColor("#E2E8F0"), 1))
        pa.setBrush(QColor("#FFFFFF"))
        pa.drawRoundedRect(QRectF(0.5, 0.5, W - 1.0, H - 1.0), 14, 14)
        if not self.labels or not self.series:
            pa.setPen(QColor("#94A3B8"))
            pa.drawText(QRectF(0, 0, W, H), Qt.AlignCenter, "داده‌ای نیست")
            pa.end()
            return
        plot = self._plot()
        mx = self._max()
        base = QFont(self.font())
        small = QFont(base); small.setPointSize(8)
        pa.setFont(small)
        for k in range(5):
            gy = plot.top() + plot.height() * k / 4.0
            pa.setPen(QPen(QColor("#F1F5F9"), 1))
            pa.drawLine(int(plot.left()), int(gy), int(plot.right()), int(gy))
            pa.setPen(QColor("#64748B"))
            pa.drawText(QRectF(2, gy - 8, self.PAD_L - 8, 16), Qt.AlignRight | Qt.AlignVCenter, _abbr_amount(mx * (4 - k) / 4.0))
        n = len(self.labels)
        step = 1 if n <= 14 else (2 if n <= 28 else 3)
        slot = plot.width() / max(n, 1)
        for i, lb in enumerate(self.labels):
            if i % step:
                continue
            x = plot.left() + (i + 0.5) * slot
            pa.setPen(QColor("#334155"))
            pa.drawText(QRectF(x - slot * step / 2.0, plot.bottom() + 8, slot * step, 16), Qt.AlignCenter, fa_digits(str(lb)))
        # خط‌ها
        for si, s in enumerate(self.series):
            col = QColor(s["color"])
            path = QPainterPath()
            for pi in range(len(s["pts"])):
                x, y = self._xy(si, pi, plot, mx)
                if pi == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)
            pa.setBrush(Qt.NoBrush)
            pa.setPen(QPen(col, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            pa.drawPath(path)
            for pi in range(len(s["pts"])):
                x, y = self._xy(si, pi, plot, mx)
                hov = self._hover == (si, pi)
                r = 6.0 if hov else (3.2 if n > 30 else 4.2)
                pa.setPen(QPen(col, 2.0))
                pa.setBrush(col if hov else QColor("#FFFFFF"))
                pa.drawEllipse(QRectF(x - r, y - r, 2 * r, 2 * r))
        # راهنما
        x0 = plot.right()
        pa.setFont(small)
        for si, s in enumerate(self.series):
            tw = 14 + 8 * max(len(s["name"]), 3)
            x0 -= tw + 10
            pa.setPen(Qt.NoPen)
            pa.setBrush(QColor(s["color"]))
            pa.drawRoundedRect(QRectF(x0 + tw - 10, 14, 10, 10), 3, 3)
            pa.setPen(QColor("#0F172A"))
            pa.drawText(QRectF(x0, 8, tw - 14, 22), Qt.AlignRight | Qt.AlignVCenter, str(s["name"]))
        pa.end()

    def _hit(self, pos):
        if not self.labels or not self.series:
            return None
        plot = self._plot()
        mx = self._max()
        best, bd = None, 16.0
        for si, s in enumerate(self.series):
            for pi in range(len(s["pts"])):
                x, y = self._xy(si, pi, plot, mx)
                d = ((pos.x() - x) ** 2 + (pos.y() - y) ** 2) ** 0.5
                if d < bd:
                    best, bd = (si, pi), d
        return best

    def mouseMoveEvent(self, ev):
        h = self._hit(ev.position())
        if h != self._hover:
            self._hover = h
            self.update()
        if h:
            si, pi = h
            s = self.series[si]
            a, p, m = s["pts"][pi]
            tip = "%s — %s\nمبلغ: %s ریال\nپارکت: %s متر مربع\nام دی اف: %s ورق" % (
                s["name"], fa_digits(str(self.labels[pi])), fa_digits("{:,}".format(int(a))), _fmt_q(p), _fmt_q(m))
            QToolTip.showText(ev.globalPosition().toPoint(), tip, self)
        else:
            QToolTip.hideText()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        self._hover = None
        QToolTip.hideText()
        self.update()


class CompareTab(QWidget):
    """سه نمودار زیر هم + انتخاب سال."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self.request_year = None
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("سال:"))
        self.year = QComboBox()
        self.year.setFixedWidth(110)
        self.year.currentIndexChanged.connect(self._year_changed)
        top.addWidget(self.year)
        self.note = QLabel("")
        self.note.setStyleSheet("color:#64748b;")
        top.addWidget(self.note, 1)
        lay.addLayout(top)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        hl = QVBoxLayout(host)
        self.charts = {}
        for key, title in (("total", "کل — فروش تجمعی از ابتدای سال"), ("month", "فروش ماهانه"), ("week", "فروش هفتگی")):
            t = QLabel(title)
            t.setStyleSheet("font-weight:800;font-size:14px;color:#0F172A;padding-top:6px;")
            hl.addWidget(t)
            sa = QScrollArea()
            sa.setWidgetResizable(True)
            sa.setMinimumHeight(360)
            ch = MultiLineChart()
            sa.setWidget(ch)
            hl.addWidget(sa)
            self.charts[key] = ch
        sc.setWidget(host)
        lay.addWidget(sc, 1)

    def set_loading(self):
        self.note.setText("در حال محاسبه…")

    def _year_changed(self, _i):
        if getattr(self, "_busy", False):
            return
        cb = getattr(self, "request_year", None)
        if cb:
            cb(self.year.currentData())

    def show_result(self, d):
        self._busy = True
        try:
            self.year.clear()
            for y in d["years"]:
                self.year.addItem(fa_digits(str(y)), y)
            if d["year"] in d["years"]:
                self.year.setCurrentIndex(d["years"].index(d["year"]))
        finally:
            self._busy = False
        names = d["names"]
        self.note.setText("مبلغ به ریال؛ فروشگاه حساب نمی‌شود. «%s» = مشتریانی که خودتان تیک زده‌اید (ورود به SalesMate) و به همکار نداده‌اید." % cw.ME_LABEL)
        for key, ch in self.charts.items():
            c = d["charts"].get(key)
            if not c:
                ch.set_data([], [])
                continue
            ser = [{"name": n, "color": COLORS[i % len(COLORS)], "pts": c["series"][n]} for i, n in enumerate(names)]
            ch.set_data(c["labels"], ser)
