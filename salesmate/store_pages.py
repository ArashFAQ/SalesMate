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
    CODE_TO_PRODUCT,
    GRADE_OPTIONS,
    PRODUCT_FACTORS,
    PRODUCT_OPTIONS,
    _swallow,
    amount,
    db,
    delete_store_sale_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    format_jalali_ymd,
    gregorian_to_jalali,
    jalali_to_gregorian,
    now_jalali,
    parse_flexible_jalali,
    schedule_supabase_sync,
    settings,
)
except Exception:
    from salesmate.app_core import (
    CODE_TO_PRODUCT,
    GRADE_OPTIONS,
    PRODUCT_FACTORS,
    PRODUCT_OPTIONS,
    _swallow,
    amount,
    db,
    delete_store_sale_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    format_jalali_ymd,
    gregorian_to_jalali,
    jalali_to_gregorian,
    now_jalali,
    parse_flexible_jalali,
    schedule_supabase_sync,
    settings,
)
try:
    from invoice_pages import MoneyLineEdit, ReportsPage
    from stats_pages import SalesLineChart, ParquetStatsPage
except Exception:
    from salesmate.invoice_pages import MoneyLineEdit, ReportsPage
    from salesmate.stats_pages import SalesLineChart, ParquetStatsPage


class StorePage(QWidget):
    """صفحه فروشگاه — مستقل از حواله‌ها، مشتریان و گزارش‌ها"""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.current_tab = "parquet"
        self.row_widgets = []
        self.editing_id = None
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        title = QLabel("فروشگاه")
        title.setObjectName("pageTitle")
        sub = QLabel("ثبت فروش فروشگاهی — مستقل از حواله‌ها و آمار اصلی")
        sub.setObjectName("hint")
        layout.addWidget(title)
        layout.addWidget(sub)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.week_card = self._stat_card("فروش هفته", "۰")
        self.week_m_card = self._stat_card("متراژ هفته", "۰")
        self.month_card = self._stat_card("فروش ماه (PDF)", "۰")
        self.month_m_card = self._stat_card("متراژ ماه", "۰")
        self.month_card.setCursor(Qt.PointingHandCursor)
        self.month_card.setToolTip("کلیک برای خروجی PDF عملکرد ماه جاری")
        self.month_card.mousePressEvent = lambda ev: self.export_month_pdf(None, None)
        stats.addWidget(self.week_card)
        stats.addWidget(self.week_m_card)
        stats.addWidget(self.month_card)
        stats.addWidget(self.month_m_card)
        layout.addLayout(stats)

        form_card = QFrame()
        form_card.setObjectName("storeForm")
        form_card.setStyleSheet(
            "QFrame#storeForm{background:#fff;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        fl = QVBoxLayout(form_card)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(10)

        tabs = QHBoxLayout()
        self.tab_btns = {}
        for key, label in [("parquet", "پارکت"), ("mdf", "ام‌دی‌اف"), ("raw", "ام‌دی‌اف خام")]:
            b = QPushButton(label)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _, k=key: self.switch_tab(k))
            self.tab_btns[key] = b
            tabs.addWidget(b)
        tabs.addStretch()
        fl.addLayout(tabs)

        info = QFormLayout()
        self.buyer = QLineEdit()
        self.buyer.setPlaceholderText("نام خریدار")
        self.invoice_no = QLineEdit()
        self.invoice_no.setPlaceholderText("شماره حواله")
        self.invoice_no.setAlignment(Qt.AlignCenter)
        self.date_edit = QLineEdit(fa_digits(now_jalali()[0]))
        self.date_edit.setAlignment(Qt.AlignCenter)
        info.addRow("نام خریدار:", self.buyer)
        info.addRow("شماره حواله:", self.invoice_no)
        info.addRow("تاریخ:", self.date_edit)
        fl.addLayout(info)
        for w in (self.buyer, self.invoice_no, self.date_edit):
            self._wire_enter(w)

        items_head = QHBoxLayout()
        items_head.addWidget(QLabel("<b>اقلام کالا</b>"))
        add_btn = QPushButton("+ افزودن ردیف")
        add_btn.setProperty("class", "secondaryButton")
        add_btn.clicked.connect(self.add_row)
        items_head.addStretch()
        items_head.addWidget(add_btn)
        fl.addLayout(items_head)

        self.items_host = QVBoxLayout()
        self.items_host.setSpacing(6)
        fl.addLayout(self.items_host)

        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("<b>جمع کل:</b>"))
        self.total_lbl = QLabel("۰")
        self.total_lbl.setStyleSheet("font-size:18px;font-weight:800;color:#1565C0;")
        total_row.addWidget(self.total_lbl)
        total_row.addStretch()
        fl.addLayout(total_row)

        self.conf_btn = QPushButton("✓ تایید و ثبت در فروشگاه")
        self.conf_btn.setObjectName("primaryButton")
        self.conf_btn.setMinimumHeight(44)
        self.conf_btn.clicked.connect(self.confirm_sale)
        fl.addWidget(self.conf_btn)
        form_card.hide()   # فروش فروشگاه از اکسل فروش می‌آید؛ فرم ورود دستی برداشته شد
        layout.addWidget(form_card)

        self.report_host = QGridLayout()
        self.report_host.setSpacing(8)
        layout.addLayout(self.report_host)

        # فروش فروشگاه بر اساس نوع پارکت (جناغی / والنته / بقیه) در بازه‌ی تاریخ
        tbox = QFrame()
        tbox.setObjectName("typeBox")
        tbox.setStyleSheet("QFrame#typeBox{background:#fff;border:1px solid #E2E8F0;border-radius:16px;}")
        tl = QVBoxLayout(tbox)
        tl.setContentsMargins(12, 10, 12, 12)
        tl.setSpacing(8)
        trow = QHBoxLayout()
        tt = QLabel("فروش فروشگاه بر اساس نوع پارکت")
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
        tb.clicked.connect(self._fill_store_types)
        self.type_from.returnPressed.connect(self._fill_store_types)
        self.type_to.returnPressed.connect(self._fill_store_types)
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
        ct = QLabel("پرفروش‌ترین کدهای پارکت فروشگاه (از زیاد به کم، بر اساس مبلغ)")
        ct.setStyleSheet("font-size:14px;font-weight:800;color:#0F172A;border:none;margin-top:6px;")
        tl.addWidget(ct)
        self.code_tbl = QLabel("")
        self.code_tbl.setTextFormat(Qt.RichText)
        self.code_tbl.setLayoutDirection(Qt.LeftToRight)
        self.code_tbl.setStyleSheet("border:none;background:transparent;")
        self.code_scroll = QScrollArea()
        self.code_scroll.setWidgetResizable(False)
        self.code_scroll.setFrameShape(QFrame.NoFrame)
        self.code_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.code_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self.code_scroll.setWidget(self.code_tbl)
        self.code_scroll.setFixedHeight(318)       # سرتیتر + ۱۰ ردیف؛ بقیه با اسکرول
        tl.addWidget(self.code_scroll, 0, Qt.AlignRight | Qt.AlignAbsolute)
        self._types_rows = []
        layout.addWidget(tbox)

        def _chart_box(title, chart):
            t = QLabel(title)
            t.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;margin-top:6px;")
            layout.addWidget(t)
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.NoFrame)
            sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            sc.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            sc.setFixedHeight(316)
            sc.setStyleSheet("QScrollArea{background:transparent;border:none;}")
            sc.setWidget(chart)
            layout.addWidget(sc)

        self.month_chart = SalesLineChart("#1565C0")
        self.week_chart = SalesLineChart("#F59E0B")
        _chart_box("نمودار فروش ماهانه فروشگاه (مبلغ و متراژ)", self.month_chart)
        _chart_box("نمودار فروش هفتگی فروشگاه (مبلغ و متراژ)", self.week_chart)

        list_head = QHBoxLayout()
        list_title = QLabel("فروش‌های ثبت‌شده")
        list_title.setStyleSheet("font-size:15px;font-weight:700;margin-top:8px;")
        list_head.addWidget(list_title)
        list_head.addStretch()
        excel_btn = QPushButton("📊 خروجی اکسل")
        excel_btn.setCursor(Qt.PointingHandCursor)
        excel_btn.setStyleSheet(
            "QPushButton{background:#0F172A;color:#fff;border:none;border-radius:10px;"
            "padding:8px 14px;font-weight:700;}"
            "QPushButton:hover{background:#1E293B;}"
        )
        excel_btn.clicked.connect(self.export_excel)
        list_head.addWidget(excel_btn)
        layout.addLayout(list_head)
        self.list_host = QVBoxLayout()
        self.list_host.setSpacing(10)
        layout.addLayout(self.list_host)
        layout.addStretch()

        scroll.setWidget(host)
        outer.addWidget(scroll)
        self.switch_tab("parquet")
        self.refresh_list()

    def _stat_card(self, label, value):
        card = QFrame()
        card.setStyleSheet("QFrame{background:#fff;border:1px solid #E2E8F0;border-radius:16px;}")
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 14, 16, 14)
        lb = QLabel(label)
        lb.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        val = QLabel(value)
        val.setStyleSheet("color:#0F172A;font-size:20px;font-weight:800;border:none;background:transparent;")
        vl.addWidget(lb)
        vl.addWidget(val)
        card._value = val
        return card

    def _wire_enter(self, widget):
        try:
            widget.installEventFilter(self)
        except Exception:
            _swallow()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            focusables = []
            for w in self.findChildren(QWidget):
                if not w.isVisible() or not w.isEnabled():
                    continue
                if isinstance(w, QLineEdit) and not w.isReadOnly():
                    focusables.append(w)
                elif isinstance(w, QComboBox) and w.isEnabled():
                    focusables.append(w)
            focusables = sorted(
                focusables,
                key=lambda w: (w.mapTo(self, w.rect().topLeft()).y(),
                               -w.mapTo(self, w.rect().topLeft()).x()),
            )
            if obj in focusables:
                i = focusables.index(obj)
                if i + 1 < len(focusables):
                    focusables[i + 1].setFocus()
                    if isinstance(focusables[i + 1], QLineEdit):
                        focusables[i + 1].selectAll()
                    return True
        return super().eventFilter(obj, event)

    def _style_tabs(self):
        for k, b in self.tab_btns.items():
            if k == self.current_tab:
                b.setStyleSheet(
                    "QPushButton{background:#1565C0;color:white;border:none;border-radius:10px;"
                    "padding:8px 16px;font-weight:700;}"
                )
            else:
                b.setStyleSheet(
                    "QPushButton{background:#E2E8F0;color:#334155;border:none;border-radius:10px;"
                    "padding:8px 16px;font-weight:600;}"
                )

    def switch_tab(self, tab):
        self.current_tab = tab
        self._style_tabs()
        while self.items_host.count():
            it = self.items_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.row_widgets.clear()
        self.add_row()
        self.recalc()

    def add_row(self):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;}"
            "QLineEdit,QComboBox{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:4px 6px;}"
            "QLabel{background:transparent;border:none;}"
        )
        hl = QHBoxLayout(row)
        hl.setSpacing(6)
        fields = {}
        tab = self.current_tab

        def field(name, widget):
            fields[name] = widget
            self._wire_enter(widget)
            return widget

        if tab == "parquet":
            code = QLineEdit(); code.setPlaceholderText("کد کالا")
            typ = QComboBox(); typ.addItems(PRODUCT_OPTIONS)
            grade = QComboBox(); grade.addItems(GRADE_OPTIONS)
            qty1 = QLineEdit(); qty1.setPlaceholderText("کارتن"); qty1.setAlignment(Qt.AlignCenter)
            qty2 = QLineEdit(); qty2.setPlaceholderText("متراژ"); qty2.setReadOnly(True); qty2.setAlignment(Qt.AlignCenter)
            price = MoneyLineEdit(); price.setPlaceholderText("قیمت واحد"); price.setAlignment(Qt.AlignCenter)
            for w in (code, typ, grade, qty1, qty2, price):
                hl.addWidget(w)
            field("code", code); field("type", typ); field("grade", grade)
            field("qty1", qty1); field("qty2", qty2); field("price", price)

            def update_m():
                try:
                    c = float(en_digits(qty1.text()) or 0)
                except Exception:
                    c = 0
                factor = PRODUCT_FACTORS.get(typ.currentText(), 1.9608)
                qty2.setText(f"{c * factor:.4f}".rstrip("0").rstrip(".") if c else "")
                self.recalc()

            def apply_code_product():
                raw = en_digits(code.text() or "").strip()
                key = "".join(ch for ch in raw if ch.isdigit())
                product = CODE_TO_PRODUCT.get(key)
                typ.blockSignals(True)
                if product:
                    idx = typ.findText(product)
                    if idx >= 0:
                        typ.setCurrentIndex(idx)
                    typ.setEnabled(False)
                else:
                    typ.setEnabled(True)
                typ.blockSignals(False)
                update_m()

            code.textChanged.connect(apply_code_product)
            qty1.textChanged.connect(update_m)
            typ.currentIndexChanged.connect(update_m)
            price.textChanged.connect(self.recalc)
        elif tab == "mdf":
            typ = QLineEdit(); typ.setPlaceholderText("نوع کالا")
            code = QLineEdit(); code.setPlaceholderText("کد")
            qty1 = QLineEdit(); qty1.setPlaceholderText("پالت"); qty1.setAlignment(Qt.AlignCenter)
            qty2 = QLineEdit(); qty2.setPlaceholderText("ورق"); qty2.setAlignment(Qt.AlignCenter)
            price = MoneyLineEdit(); price.setPlaceholderText("قیمت واحد"); price.setAlignment(Qt.AlignCenter)
            for w in (typ, code, qty1, qty2, price):
                hl.addWidget(w)
            field("type", typ); field("code", code)
            field("qty1", qty1); field("qty2", qty2); field("price", price)
            for w in (qty1, qty2, price):
                w.textChanged.connect(self.recalc)
        else:
            typ = QLineEdit(); typ.setPlaceholderText("نوع کالا")
            size = QLineEdit(); size.setPlaceholderText("سایز")
            qty1 = QLineEdit(); qty1.setPlaceholderText("پالت"); qty1.setAlignment(Qt.AlignCenter)
            qty2 = QLineEdit(); qty2.setPlaceholderText("ورق"); qty2.setAlignment(Qt.AlignCenter)
            price = MoneyLineEdit(); price.setPlaceholderText("قیمت واحد"); price.setAlignment(Qt.AlignCenter)
            for w in (typ, size, qty1, qty2, price):
                hl.addWidget(w)
            field("type", typ); field("size", size)
            field("qty1", qty1); field("qty2", qty2); field("price", price)
            for w in (qty1, qty2, price):
                w.textChanged.connect(self.recalc)

        cost_lbl = QLabel("۰")
        cost_lbl.setMinimumWidth(90)
        cost_lbl.setAlignment(Qt.AlignCenter)
        fields["cost_lbl"] = cost_lbl
        hl.addWidget(cost_lbl)
        rm = QPushButton("✕")
        rm.setFixedWidth(36)
        rm.clicked.connect(lambda: self.remove_row(row))
        hl.addWidget(rm)
        self.items_host.addWidget(row)
        self.row_widgets.append((row, fields))
        self.recalc()

    def remove_row(self, row):
        for i, (r, _) in enumerate(self.row_widgets):
            if r is row:
                self.row_widgets.pop(i)
                break
        row.deleteLater()
        self.recalc()

    def get_rows_data(self):
        rows = []
        for i, (_, fields) in enumerate(self.row_widgets):
            data = {"index": i + 1}
            for k, w in fields.items():
                if k == "cost_lbl":
                    continue
                if isinstance(w, QComboBox):
                    data[k] = w.currentText()
                else:
                    data[k] = w.text()
            try:
                qty2 = float(en_digits(str(data.get("qty2") or "0")) or 0)
            except Exception:
                qty2 = 0
            price = amount(data.get("price") or 0)
            data["cost"] = int(round(qty2 * price))
            rows.append(data)
        return rows

    def recalc(self):
        total = 0
        for _, fields in self.row_widgets:
            data = {}
            for k, w in fields.items():
                if k == "cost_lbl":
                    continue
                if isinstance(w, QComboBox):
                    data[k] = w.currentText()
                else:
                    data[k] = w.text()
            try:
                qty2 = float(en_digits(str(data.get("qty2") or "0")) or 0)
            except Exception:
                qty2 = 0
            price = amount(data.get("price") or 0)
            cost = int(round(qty2 * price))
            total += cost
            if "cost_lbl" in fields:
                fields["cost_lbl"].setText(fmt(cost))
        self.total_lbl.setText(fmt(total) + " ریال")
        self._last_total = total

    def confirm_sale(self):
        buyer = self.buyer.text().strip()
        inv_no = en_digits(self.invoice_no.text().strip())
        date = en_digits(self.date_edit.text().strip()) or now_jalali()[0]
        rows = self.get_rows_data()
        if not buyer:
            QMessageBox.warning(self, "فروشگاه", "نام خریدار را وارد کنید.")
            return
        if not inv_no:
            QMessageBox.warning(self, "فروشگاه", "شماره حواله را وارد کنید.")
            return
        if not rows or all(not r.get("cost") for r in rows):
            QMessageBox.warning(self, "فروشگاه", "حداقل یک ردیف با مقدار و قیمت وارد کنید.")
            return
        total = int(getattr(self, "_last_total", 0) or 0)
        if total <= 0:
            QMessageBox.warning(self, "فروشگاه", "جمع کل باید بیشتر از صفر باشد.")
            return
        from datetime import datetime as _dt
        time_str = _dt.now().strftime("%H:%M:%S")
        try:
            c = db()
            if self.editing_id:
                c.execute(
                    "UPDATE store_sales SET customer=?, invoice_no=?, date=?, time=?, total=?, tab=?, items_json=? WHERE id=?",
                    (
                        buyer, inv_no, date, time_str, str(total),
                        self.current_tab,
                        json.dumps(rows, ensure_ascii=False),
                        self.editing_id,
                    ),
                )
                msg = "فروش ویرایش شد."
            else:
                c.execute(
                    "INSERT INTO store_sales(customer,invoice_no,date,time,total,tab,items_json,created_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (
                        buyer, inv_no, date, time_str, str(total),
                        self.current_tab,
                        json.dumps(rows, ensure_ascii=False),
                        _dt.now().isoformat(timespec="seconds"),
                    ),
                )
                msg = "فروش در فروشگاه ثبت شد."
            c.commit()
            c.close()
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))
            return
        self.editing_id = None
        self.conf_btn.setText("✓ تایید و ثبت در فروشگاه")
        self.buyer.clear()
        self.invoice_no.clear()
        self.date_edit.setText(fa_digits(now_jalali()[0]))
        self.switch_tab(self.current_tab)
        self.refresh_list()
        try:
            schedule_supabase_sync()
        except Exception:
            _swallow()
        QMessageBox.information(self, "فروشگاه", msg)

    _MN = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
           "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

    def _week_range_txt(self, y, wn, short=False):
        """بازه‌ی تاریخ هفته: «۱ تا ۷ فروردین» یا «۲۹ فروردین تا ۴ اردیبهشت»."""
        try:
            r = core.jalali_week_range(y, wn)
        except Exception:
            r = None
        if not r:
            return ""
        (m1, d1), (m2, d2) = r
        if short:
            return f"{fa_digits('%02d' % m1)}/{fa_digits('%02d' % d1)} تا {fa_digits('%02d' % m2)}/{fa_digits('%02d' % d2)}"
        if m1 == m2:
            return f"{fa_digits(d1)} تا {fa_digits(d2)} {self._MN[m1 - 1]}"
        return f"{fa_digits(d1)} {self._MN[m1 - 1]} تا {fa_digits(d2)} {self._MN[m2 - 1]}"

    def _jalali_parts(self, date_s):
        parts = en_digits(str(date_s or "")).split("/")
        if len(parts) >= 3:
            try:
                return int(parts[0]), int(parts[1]), int(parts[2])
            except Exception:
                _swallow()
        return None, None, None

    def _week_of_year_approx(self, y, m, d):
        days = (m - 1) * 31
        if m > 6:
            days = 6 * 31 + (m - 7) * 30
        days += d
        return y, (days - 1) // 7

    def _items_meterage(self, items_json, tab=None):
        """جمع متراژ اقلام (qty2 برای پارکت؛ برای بقیه هم qty2 در صورت عدد بودن)."""
        try:
            items = json.loads(items_json or "[]")
        except Exception:
            items = []
        total = 0.0
        for it in items or []:
            raw = it.get("qty2")
            if raw in (None, ""):
                continue
            try:
                total += float(en_digits(str(raw)).replace(",", "").replace("٬", "").replace("،", "") or 0)
            except Exception:
                _swallow()
        return total

    def _fmt_meter(self, m):
        if not m:
            return "۰"
        s = f"{m:.4f}".rstrip("0").rstrip(".")
        return fa_digits(s)

    def _fill_store_types(self, *_):
        while self.type_row.count():
            it = self.type_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        norm = ParquetStatsPage._norm_date_in
        t1, t2 = self.type_from.text().strip(), self.type_to.text().strip()
        d1, d2 = norm(t1), norm(t2)
        if (t1 and not d1) or (t2 and not d2):
            self.type_note.setText("تاریخ را به شکل 1405/08/08 بنویسید.")
            return
        sums = {"جناغی": [0.0, 0.0], "والنته": [0.0, 0.0], "بقیه": [0.0, 0.0]}
        codes = {}
        n_sales = 0
        for rid, customer, inv_no, date, time_s, total, tab, items_json in self._types_rows:
            if str(tab or "parquet").lower() not in ("parquet", "پارکت", ""):
                continue
            dn = norm(date)
            if (d1 and (not dn or dn < d1)) or (d2 and (not dn or dn > d2)):
                continue
            try:
                items = json.loads(items_json or "[]")
            except Exception:
                items = []
            n_sales += 1
            for it in items or []:
                it = it or {}
                nm = it.get("name") or it.get("type") or ""
                k = ParquetStatsPage.parquet_type_of(en_digits(str(it.get("code") or "")), nm)
                try:
                    m = float(en_digits(str(it.get("qty2") or 0)).replace(",", "").replace("٬", "").replace("،", "") or 0)
                except Exception:
                    m = 0.0
                sums[k][0] += amount(it.get("cost"))
                sums[k][1] += m
                cd = ParquetStatsPage.code_key(it.get("code"), nm)
                if cd:
                    e = codes.setdefault(cd, {"a": 0.0, "m": 0.0, "q": 0.0, "names": {}})
                    e["a"] += amount(it.get("cost"))
                    e["m"] += m
                    try:
                        e["q"] += float(en_digits(str(it.get("qty1") or 0)).replace(",", "") or 0)
                    except Exception:
                        pass
                    nmk = ParquetStatsPage.code_name(it.get("code"), nm)
                    if nmk:
                        e["names"][nmk] = e["names"].get(nmk, 0) + 1
        ta = sum(v[0] for v in sums.values())
        tm = sum(v[1] for v in sums.values())
        for title, k in (("پارکت جناغی", "جناغی"), ("پارکت والنته", "والنته"), ("بقیه‌ی پارکت‌ها", "بقیه")):
            c = self._stat_card(title, fmt(sums[k][0]) + " ریال")
            c.layout().addWidget(QLabel(self._fmt_meter(sums[k][1]) + " متر"))
            c.layout().itemAt(2).widget().setStyleSheet("color:#475569;font-size:13px;border:none;background:transparent;")
            self.type_row.addWidget(c)
        c = self._stat_card("جمع پارکت", fmt(ta) + " ریال")
        c.layout().addWidget(QLabel(self._fmt_meter(tm) + " متر"))
        c.layout().itemAt(2).widget().setStyleSheet("color:#475569;font-size:13px;border:none;background:transparent;")
        self.type_row.addWidget(c)
        # جدول کدها
        th = "padding:5px 10px;background:#EFF6FF;color:#1E3A8A;font-weight:800;border:1px solid #DBEAFE;"
        td = "padding:5px 10px;border:1px solid #E2E8F0;"
        order = sorted(codes.items(), key=lambda kv: (kv[1]["a"], kv[1]["m"]), reverse=True)[:40]
        if not order:
            self.code_tbl.setText("<span style='color:#94A3B8'>کدی در این بازه نیست</span>")
        else:
            h = ("<table cellspacing='0' cellpadding='0' style='font-size:12px;border-collapse:collapse;'>"
                 "<tr><td style='%s' align='center'>مبلغ (ریال)</td><td style='%s' align='center'>متر مربع</td>"
                 "<td style='%s' align='center'>کارتن</td><td style='%s' align='center'>نام کالا</td>"
                 "<td style='%s' align='center'>کد</td><td style='%s' align='center'>رتبه</td></tr>"
                 % ((th,) * 6))
            for i, (cd, e) in enumerate(order, 1):
                nm_top = max(e["names"], key=e["names"].get) if e["names"] else "—"
                bg = "#FFFFFF" if i % 2 else "#F8FAFC"
                h += ("<tr style='background:%s'><td style='%s' align='right'><b>%s</b></td><td style='%s' align='right'>%s</td>"
                      "<td style='%s' align='right'>%s</td><td style='%s' align='right'>%s</td>"
                      "<td style='%s' align='center'>%s</td><td style='%s' align='center'>%s</td></tr>"
                      % (bg, td, fa_digits(fmt(e["a"])), td, self._fmt_meter(e["m"]),
                         td, fa_digits(f"{e['q']:,.0f}"), td, nm_top,
                         td, fa_digits(cd), td, fa_digits(i)))
            h += "</table>"
            self.code_tbl.setText(h)
        self.code_tbl.adjustSize()
        self.code_scroll.setFixedWidth(max(self.code_tbl.sizeHint().width(), 300) + 22)
        rng = (d1 or "ابتدا") + " تا " + (d2 or "انتها")
        self.type_note.setText(
            f"بازه: {fa_digits(rng)} · {fa_digits(n_sales)} فروش پارکت · "
            "تشخیص از نام کالا: «جناغی» و «Valente/والنته»؛ بقیه در «بقیه‌ی پارکت‌ها»."
        )

    def refresh_list(self):
        while self.list_host.count():
            it = self.list_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        while self.report_host.count():
            it = self.report_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        c = db()
        rows = c.execute(
            "SELECT id, customer, invoice_no, date, time, total, tab, items_json "
            "FROM store_sales ORDER BY date DESC, time DESC, id DESC"
        ).fetchall()
        c.close()

        try:
            cy, cm, cd = self._jalali_parts(now_jalali()[0])
        except Exception:
            cy = cm = cd = None
        week_sum = 0
        month_sum = 0
        week_m = 0.0
        month_m = 0.0
        month_totals = [0] * 12
        cur_week = self._week_of_year_approx(cy, cm, cd) if cy else None

        for rid, customer, inv_no, date, time_s, total, tab, items_json in rows:
            tot = amount(total)
            meters = self._items_meterage(items_json, tab)
            y, m, d = self._jalali_parts(date)
            if y == cy and m == cm:
                month_sum += tot
                month_m += meters
            if y and m and d and cur_week:
                if self._week_of_year_approx(y, m, d) == cur_week:
                    week_sum += tot
                    week_m += meters
            if y == cy and m and 1 <= m <= 12:
                month_totals[m - 1] += tot

        self.week_card._value.setText(fmt(week_sum) + " ریال")
        self.week_m_card._value.setText(self._fmt_meter(week_m) + " متر")
        self.month_card._value.setText(fmt(month_sum) + " ریال")
        self.month_m_card._value.setText(self._fmt_meter(month_m) + " متر")

        month_names = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ]
        colors = list(ReportsPage.MONTH_COLORS)
        for i, name in enumerate(month_names):
            box = QFrame()
            box.setCursor(Qt.PointingHandCursor)
            box.setStyleSheet(
                f"QFrame{{background:{colors[i]};border:none;border-radius:12px;}}"
                f"QFrame:hover{{border:2px solid #1565C0;}}"
            )
            bl = QVBoxLayout(box)
            bl.setContentsMargins(8, 10, 8, 10)
            bl.setSpacing(2)
            n = QLabel(name)
            n.setAlignment(Qt.AlignCenter)
            n.setStyleSheet("font-size:11px;font-weight:700;color:#334155;border:none;background:transparent;")
            v = QLabel(fmt(month_totals[i]))
            v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet("font-size:12px;font-weight:800;color:#0F172A;border:none;background:transparent;")
            pdf_hint = QLabel("PDF ⬇")
            pdf_hint.setAlignment(Qt.AlignCenter)
            pdf_hint.setStyleSheet("font-size:10px;color:#0D47A1;font-weight:700;border:none;background:transparent;")
            bl.addWidget(n)
            bl.addWidget(v)
            bl.addWidget(pdf_hint)
            box.setToolTip("کلیک برای خروجی PDF این ماه")
            box.mousePressEvent = lambda ev, mi=i + 1, yr=cy: self.export_month_pdf(yr, mi)
            self.report_host.addWidget(box, i // 6, i % 6)

        self._update_store_charts(rows)
        self._types_rows = rows
        if not self.type_to.text().strip():
            self.type_to.setText(now_jalali()[0])
        if not self.type_from.text().strip() and cy:
            self.type_from.setText(f"{cy:04d}/01/01")
        self._fill_store_types()

        if not rows:
            empty = QLabel("هنوز فروشی در فروشگاه ثبت نشده")
            empty.setStyleSheet("color:#94A3B8;padding:20px;")
            empty.setAlignment(Qt.AlignCenter)
            self.list_host.addWidget(empty)
            return

        from collections import OrderedDict
        groups = OrderedDict()
        for row in rows:
            rid, customer, inv_no, date, time_s, total, tab, items_json = row
            y, m, d = self._jalali_parts(date)
            if y and m and d:
                wk = self._week_of_year_approx(y, m, d)
            else:
                wk = (0, 0)
            groups.setdefault(wk, []).append(row)

        for wk, items_rows in groups.items():
            week_total = sum(amount(r[5]) for r in items_rows)
            week_meters = sum(self._items_meterage(r[7], r[6]) for r in items_rows)
            yk, wn = wk
            head = QFrame()
            head.setStyleSheet(
                "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;"
                "border-radius:24px;}"
            )
            hl = QHBoxLayout(head)
            hl.setContentsMargins(16, 10, 16, 10)
            mtxt = self._fmt_meter(week_meters)
            if yk:
                t = QLabel(
                    f"هفته {fa_digits(wn + 1)} سال {fa_digits(yk)} ({self._week_range_txt(yk, wn)})   ·   "
                    f"فروش هفته: {fmt(week_total)} ریال   ·   متراژ: {mtxt} متر"
                )
            else:
                t = QLabel(
                    f"بدون تاریخ   ·   فروش هفته: {fmt(week_total)} ریال   ·   متراژ: {mtxt} متر"
                )
            t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet(
                "font-size:13px;font-weight:700;color:#0F172A;"
                "background:transparent;border:none;"
            )
            hl.addWidget(t)
            self.list_host.addWidget(head)

            for rid, customer, inv_no, date, time_s, total, tab, items_json in items_rows:
                card = QFrame()
                card.setObjectName("storeCard")
                card.setStyleSheet(
                    "QFrame#storeCard{background:#FFFFFF;border:1px solid #E2E8F0;"
                    "border-radius:16px;border-right:8px solid #1565C0;}"
                    "QFrame#storeCard QLabel{background:transparent;border:none;}"
                )
                vl = QVBoxLayout(card)
                vl.setContentsMargins(16, 12, 16, 12)
                vl.setSpacing(6)

                head_row = QHBoxLayout()
                name_lbl = QLabel(customer)
                name_lbl.setStyleSheet(
                    "font-size:15px;font-weight:700;color:#0F172A;background:transparent;border:none;"
                )
                head_row.addWidget(name_lbl, 1)
                amt = QLabel(fmt(total) + " ریال")
                amt.setStyleSheet(
                    "font-size:16px;font-weight:800;color:#059669;background:transparent;border:none;"
                )
                head_row.addWidget(amt)
                edit_btn = QPushButton("ویرایش")
                edit_btn.setCursor(Qt.PointingHandCursor)
                edit_btn.setStyleSheet(
                    "QPushButton{background:#E0F2FE;color:#0D47A1;border:none;"
                    "border-radius:8px;padding:6px 12px;font-weight:600;}"
                )
                edit_btn.clicked.connect(lambda _, i=rid: self.edit_sale(i))
                del_btn = QPushButton("حذف")
                del_btn.setCursor(Qt.PointingHandCursor)
                del_btn.setStyleSheet(
                    "QPushButton{background:#FEE2E2;color:#991B1B;border:none;"
                    "border-radius:8px;padding:6px 12px;font-weight:600;}"
                )
                del_btn.clicked.connect(lambda _, i=rid: self.delete_sale(i))
                head_row.addWidget(edit_btn)
                head_row.addWidget(del_btn)
                vl.addLayout(head_row)

                tab_fa = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}.get(tab or "", "")
                meta = QLabel(
                    f"شماره: {fa_digits(inv_no)}   |   تاریخ: {fa_digits(date)} {fa_digits(time_s or '')}   |   {tab_fa}"
                )
                meta.setStyleSheet(
                    "color:#64748B;font-size:12px;background:transparent;border:none;"
                )
                vl.addWidget(meta)

                try:
                    items = json.loads(items_json or "[]")
                except Exception:
                    items = []
                if items:
                    table = QLabel(self._format_items_html(items, tab or "parquet"))
                    table.setTextFormat(Qt.RichText)
                    table.setWordWrap(True)
                    table.setStyleSheet(
                        "QLabel{background:transparent;border:none;padding:2px 0;"
                        "font-size:12px;color:#334155;}"
                    )
                    vl.addWidget(table)
                self.list_host.addWidget(card)

    def _format_items_html(self, items, tab):
        try:
            from statement_core import sample_last
        except Exception:
            from salesmate.statement_core import sample_last
        items = sample_last(items)          # سمپل همیشه آخر
        lines = []
        for i, r in enumerate(items, 1):
            code = r.get("code") or "—"
            typ = r.get("type") or "—"
            grade = r.get("grade") or ""
            qty1 = core.qty_int(r.get("qty1")) or ""
            qty2 = r.get("qty2") or ""
            price = r.get("price") or ""
            cost = r.get("cost") or 0
            bits = [f"{fa_digits(i)})"]
            if tab == "parquet":
                bits.append(f"کد {fa_digits(code)}")
                bits.append(str(typ))
                if grade:
                    bits.append(str(grade))
                if qty1 not in ("", None):
                    bits.append(f"{fa_digits(qty1)} کارتن")
                if qty2 not in ("", None):
                    bits.append(f"{fa_digits(qty2)} متر")
            elif tab == "mdf":
                bits.append(f"کد {fa_digits(code)}")
                bits.append(str(typ))
                if qty1 not in ("", None):
                    bits.append(f"{fa_digits(qty1)} پالت")
                if qty2 not in ("", None):
                    bits.append(f"{fa_digits(qty2)} ورق")
            else:
                bits.append(str(typ))
                size = r.get("size") or ""
                if size:
                    bits.append(str(size))
                if qty1 not in ("", None):
                    bits.append(f"{fa_digits(qty1)} پالت")
            if price not in ("", None):
                bits.append(f"فی {fmt(price)}")
            bits.append(f"<b style='color:#1565C0'>{fmt(cost)}</b>")
            lines.append(" · ".join(bits))
        return "<div style='line-height:1.75'>" + "<br>".join(lines) + "</div>"

    def edit_sale(self, rid):
        c = db()
        row = c.execute(
            "SELECT customer, invoice_no, date, total, tab, items_json FROM store_sales WHERE id=?",
            (rid,),
        ).fetchone()
        c.close()
        if not row:
            return
        customer, inv_no, date, total, tab, items_json = row
        self.editing_id = rid
        self.conf_btn.setText("✓ ذخیره تغییرات")
        self.buyer.setText(customer or "")
        self.invoice_no.setText(fa_digits(inv_no or ""))
        self.date_edit.setText(fa_digits(date or ""))
        self.switch_tab(tab or "parquet")
        try:
            items = json.loads(items_json or "[]")
        except Exception:
            items = []
        while self.items_host.count():
            it = self.items_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.row_widgets.clear()
        if not items:
            self.add_row()
        else:
            for it in items:
                self.add_row()
                _, fields = self.row_widgets[-1]
                for k, widget in fields.items():
                    if k == "cost_lbl" or k not in it:
                        continue
                    val = it[k]
                    if isinstance(widget, QComboBox):
                        idx = widget.findText(str(val))
                        if idx >= 0:
                            widget.setCurrentIndex(idx)
                        widget.setEnabled(True)
                    else:
                        widget.setText(str(val) if val is not None else "")
                if "code" in fields and "type" in fields:
                    key = "".join(ch for ch in en_digits(str(it.get("code") or "")) if ch.isdigit())
                    product = CODE_TO_PRODUCT.get(key)
                    if product and isinstance(fields["type"], QComboBox):
                        fields["type"].setEnabled(False)
        self.recalc()

    def delete_sale(self, rid):
        if QMessageBox.question(self, "حذف", "این فروش حذف شود؟\nاز ابر هم حذف می‌شود.") != QMessageBox.Yes:
            return
        try:
            c = db()
            row = c.execute(
                "SELECT customer, invoice_no, date, time, total FROM store_sales WHERE id=?",
                (rid,),
            ).fetchone()
            c.execute("DELETE FROM store_sales WHERE id=?", (rid,))
            c.commit()
            c.close()
            if row:
                sale = {
                    "customer": row[0] or "",
                    "invoiceNo": row[1] or "",
                    "date": row[2] or "",
                    "time": row[3] or "",
                    "total": str(row[4] or "0"),
                }
                def _d():
                    try:
                        delete_store_sale_from_cloud(sale)
                    except Exception:
                        _swallow()
                try:
                    threading.Thread(target=_d, daemon=True).start()
                except Exception:
                    _swallow()
            schedule_supabase_sync()
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))
            return
        self.refresh_list()

    def export_excel(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("خروجی اکسل فروشگاه")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(360)
        lay = QVBoxLayout(dlg)
        hint = QLabel("بازه تاریخ را مشخص کنید (خالی = همه)")
        hint.setObjectName("hint")
        lay.addWidget(hint)
        form = QFormLayout()
        df = QLineEdit()
        df.setPlaceholderText("از تاریخ  ")
        dt = QLineEdit()
        dt.setPlaceholderText("تا تاریخ")
        form.addRow("از تاریخ:", df)
        form.addRow("تا تاریخ:", dt)
        lay.addLayout(form)
        buttons = QDialogButtonBox()
        ok_btn = buttons.addButton("دریافت اکسل", QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton("انصراف", QDialogButtonBox.RejectRole)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        d_from = en_digits(df.text().strip())
        d_to = en_digits(dt.text().strip())
        sql = "SELECT id,customer,invoice_no,date,time,total,tab,items_json FROM store_sales WHERE 1=1"
        args = []
        if d_from:
            sql += " AND date>=?"
            args.append(d_from)
        if d_to:
            sql += " AND date<=?"
            args.append(d_to)
        sql += " ORDER BY date DESC, time DESC, id DESC"
        c = db()
        rows = c.execute(sql, args).fetchall()
        c.close()
        if not rows:
            QMessageBox.information(self, "اکسل", "با این فیلتر فروشی پیدا نشد.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره اکسل", "SalesMate_Store.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
            from openpyxl.utils import get_column_letter
            wb = Workbook()
            ws = wb.active
            ws.title = "فروشگاه"
            ws.sheet_view.rightToLeft = True
            headers = ["شناسه", "مشتری", "شماره", "تاریخ", "ساعت", "مبلغ", "نوع", "اقلام", "هفته", "بازه هفته"]
            header_fill = PatternFill("solid", fgColor="0284C7")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            thin = Border(
                left=Side(style="thin", color="CBD5E1"),
                right=Side(style="thin", color="CBD5E1"),
                top=Side(style="thin", color="CBD5E1"),
                bottom=Side(style="thin", color="CBD5E1"),
            )
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            for col, h in enumerate(headers, 1):
                cell = ws.cell(1, col, h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center
                cell.border = thin
            alt = PatternFill("solid", fgColor="F8FAFC")
            tab_map = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}
            for r, row in enumerate(rows, 2):
                rid, customer, inv_no, date, time_s, total, tab, items_json = row
                try:
                    items = json.loads(items_json or "[]")
                except Exception:
                    items = []
                parts = []
                for it in items:
                    code = it.get("code") or ""
                    typ = it.get("type") or ""
                    q1 = core.qty_int(it.get("qty1")) or ""
                    q2 = it.get("qty2") or ""
                    cost = it.get("cost") or ""
                    bits = []
                    if code:
                        bits.append(f"کد {code}")
                    if typ:
                        bits.append(str(typ))
                    if q1:
                        bits.append(f"{q1} کارتن")
                    if q2:
                        bits.append(f"{q2}")
                    if cost:
                        bits.append(str(cost))
                    if bits:
                        parts.append(" · ".join(bits))
                values = [
                    rid, customer or "", str(inv_no or ""), str(date or ""),
                    str(time_s or ""), amount(total), tab_map.get(tab or "", tab or ""),
                    " | ".join(parts),
                ]
                _y, _m, _d = self._jalali_parts(date)
                if _y and _m and _d:
                    _wy, _wn = self._week_of_year_approx(_y, _m, _d)
                    values += ["هفته " + fa_digits(_wn + 1), self._week_range_txt(_wy, _wn)]
                else:
                    values += ["", ""]
                for col, val in enumerate(values, 1):
                    cell = ws.cell(r, col, val)
                    cell.alignment = center
                    cell.border = thin
                    if r % 2 == 0:
                        cell.fill = alt
                    if col == 6:
                        cell.number_format = "#,##0"
            widths = [8, 22, 12, 12, 10, 16, 12, 50, 10, 24]
            for i, w in enumerate(widths, 1):
                ws.column_dimensions[get_column_letter(i)].width = w
            total_row = len(rows) + 2
            ws.cell(total_row, 5, "جمع کل").font = Font(bold=True)
            sum_cell = ws.cell(total_row, 6, f"=SUM(F2:F{total_row-1})")
            sum_cell.font = Font(bold=True, color="0284C7")
            sum_cell.number_format = "#,##0"
            wb.save(path)
            QMessageBox.information(
                self, "SalesMate",
                f"{fa_digits(len(rows))} فروش در فایل اکسل ذخیره شد.",
            )
        except ImportError:
            QMessageBox.critical(self, "خطا", "کتابخانه openpyxl نصب نیست. در CMD: pip install openpyxl")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"ذخیره اکسل انجام نشد: {ex}")

    def _update_store_charts(self, rows):
        mnames = ["فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]
        mon, wk = {}, {}
        for r in rows:
            y, m, d = self._jalali_parts(r[3])
            if not (y and m and d and 1 <= m <= 12):
                continue
            tot = amount(r[5])
            met = self._items_meterage(r[7], r[6])
            a = mon.setdefault((y, m), [0, 0.0]); a[0] += tot; a[1] += met
            w = wk.setdefault(self._week_of_year_approx(y, m, d), [0, 0.0]); w[0] += tot; w[1] += met
        mpts, wpts = [], []
        if mon:
            y, m = min(mon)
            ey, em = max(mon)
            while (y, m) <= (ey, em):
                amt, met = mon.get((y, m), [0, 0.0])
                mpts.append(dict(label=mnames[m - 1], sub=fa_digits(y), amt=amt, met=met,
                                 tip=f"{mnames[m - 1]} {fa_digits(y)}\nمبلغ: {fmt(amt)} ریال\nمتراژ: {self._fmt_meter(met)} متر"))
                m += 1
                if m > 12:
                    y, m = y + 1, 1
        if wk:
            y, w = min(wk)
            ey, ew = max(wk)
            while (y, w) <= (ey, ew):
                amt, met = wk.get((y, w), [0, 0.0])
                wpts.append(dict(label="هفته " + fa_digits(w + 1), sub=self._week_range_txt(y, w, True), amt=amt, met=met,
                                 tip=f"هفته {fa_digits(w + 1)} سال {fa_digits(y)}\n{self._week_range_txt(y, w)}\nمبلغ: {fmt(amt)} ریال\nمتراژ: {self._fmt_meter(met)} متر"))
                w += 1
                if w > 52:
                    y, w = y + 1, 0
        self.month_chart.set_points(mpts[-24:])
        self.week_chart.set_points(wpts[-60:])

    def refresh(self):
        self.refresh_list()



    def _format_store_item_line(self, it, tab):
        """یک خط خوانا از قلم فروش"""
        if not isinstance(it, dict):
            return ""
        bits = []
        code = it.get("code") or ""
        typ = it.get("type") or it.get("typ") or ""
        grade = it.get("grade") or ""
        qty1 = core.qty_int(it.get("qty1"))
        qty2 = it.get("qty2")
        price = it.get("price")
        cost = it.get("cost")
        size = it.get("size") or ""
        if code:
            bits.append("کد " + fa_digits(str(code)))
        if typ:
            bits.append(str(typ))
        if grade:
            bits.append(str(grade))
        if size:
            bits.append(str(size))
        if tab == "parquet":
            if qty1 not in (None, ""):
                bits.append(fa_digits(str(qty1)) + " کارتن")
            if qty2 not in (None, ""):
                bits.append(fa_digits(str(qty2)) + " متر")
        else:
            if qty1 not in (None, ""):
                bits.append(fa_digits(str(qty1)) + " پالت")
            if qty2 not in (None, ""):
                bits.append(fa_digits(str(qty2)) + " ورق")
        if price not in (None, ""):
            bits.append("فی " + fmt(price))
        if cost not in (None, ""):
            bits.append("مبلغ " + fmt(cost))
        return " · ".join(bits)





    def export_month_pdf(self, year, month):
        """گزارش ماه فروشگاه — خلاصه هفته تراز + کارت‌های فروش مثل اپ (بدون ویرایش/حذف)."""
        if not year or not month:
            try:
                year, month, _ = self._jalali_parts(now_jalali()[0])
            except Exception:
                QMessageBox.warning(self, "گزارش", "سال/ماه معتبر نیست.")
                return
        month_names = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ]
        mname = month_names[month - 1] if 1 <= month <= 12 else str(month)
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره گزارش ماه فروشگاه",
            f"فروشگاه_{fa_digits(year)}_{mname}.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"

        c = db()
        rows = c.execute(
            "SELECT id, customer, invoice_no, date, time, total, tab, items_json "
            "FROM store_sales ORDER BY date ASC, time ASC, id ASC"
        ).fetchall()
        c.close()
        month_rows = [r for r in rows if self._jalali_parts(r[3])[:2] == (year, month)]
        if not month_rows:
            QMessageBox.information(self, "گزارش", f"در {mname} {fa_digits(year)} فروشی ثبت نشده.")
            return

        from collections import OrderedDict
        week_groups = OrderedDict()
        month_sum = 0
        month_m = 0.0
        for row in month_rows:
            month_sum += amount(row[5])
            month_m += self._items_meterage(row[7], row[6])
            y, m, d = self._jalali_parts(row[3])
            wk = self._week_of_year_approx(y, m, d) if y else (0, 0)
            week_groups.setdefault(wk, []).append(row)

        company = settings().get("company_name", "SalesMate")

        try:
            from PySide6.QtGui import QPdfWriter, QPageSize
            from PySide6.QtCore import QMarginsF, QRect

            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            try:
                from PySide6.QtGui import QPageLayout as _PL
                writer.setPageOrientation(_PL.Landscape)
            except Exception:
                _swallow()
            writer.setResolution(120)
            try:
                writer.setPageMargins(QMarginsF(12, 12, 12, 12))
            except Exception:
                _swallow()

            p = QPainter(writer)
            p.setRenderHint(QPainter.TextAntialiasing, True)
            p.setRenderHint(QPainter.Antialiasing, True)

            page_w = writer.width()
            page_h = writer.height()
            margin = 48
            content_w = page_w - 2 * margin
            y = margin
            page_no = 1

            font = QFont("Tahoma", 10)
            font_b = QFont("Tahoma", 10, QFont.Bold)
            font_title = QFont("Tahoma", 16, QFont.Bold)
            font_sub = QFont("Tahoma", 11)
            font_sm = QFont("Tahoma", 9)
            font_kpi = QFont("Tahoma", 12, QFont.Bold)
            font_card = QFont("Tahoma", 11, QFont.Bold)
            font_amt = QFont("Tahoma", 12, QFont.Bold)

            blue = QColor("#1565C0")
            text_dark = QColor("#0F172A")
            text_muted = QColor("#64748B")
            line_c = QColor("#E2E8F0")
            bg_soft = QColor("#F8FAFC")
            green = QColor("#059669")
            white = QColor("#FFFFFF")

            def footer():
                p.setPen(text_muted)
                p.setFont(font_sm)
                p.drawText(
                    QRect(margin, page_h - 40, content_w, 24),
                    Qt.AlignCenter,
                    f"{company}  |  صفحه {fa_digits(page_no)}  |  SalesMate",
                )

            def ensure(h):
                nonlocal y, page_no
                if y + h > page_h - 55:
                    footer()
                    writer.newPage()
                    page_no += 1
                    y = margin

            def hline(yy, x0=None, x1=None):
                p.setPen(QPen(line_c, 1))
                p.drawLine(x0 if x0 is not None else margin, yy,
                           x1 if x1 is not None else margin + content_w, yy)

            def round_rect(x, yy, w, h, color, radius=12, border=None):
                path = QPainterPath()
                path.addRoundedRect(QRectF(x, yy, w, h), radius, radius)
                p.fillPath(path, color)
                if border is not None:
                    p.setPen(QPen(border, 1.5))
                    p.drawPath(path)

            # ---- عنوان ----
            p.setPen(blue)
            p.setFont(font_title)
            p.drawText(QRect(margin, y, content_w, 34), Qt.AlignCenter, f"{mname} {fa_digits(year)}")
            y += 36
            p.setPen(text_muted)
            p.setFont(font_sub)
            p.drawText(QRect(margin, y, content_w, 22), Qt.AlignCenter, "گزارش عملکرد فروشگاه")
            y += 28
            hline(y)
            y += 14

            # ---- دو باکس جمع ----
            ensure(72)
            box_w = (content_w - 14) // 2
            for i, (lab, val, col) in enumerate([
                ("مبلغ کل ماه", fmt(month_sum) + " ریال", green),
                ("متراژ کل ماه", self._fmt_meter(month_m) + " متر", blue),
            ]):
                x = margin + i * (box_w + 14)
                round_rect(x, y, box_w, 62, bg_soft, 12, line_c)
                p.setPen(text_muted)
                p.setFont(font_sm)
                p.drawText(QRect(x + 8, y + 8, box_w - 16, 18), Qt.AlignCenter, lab)
                p.setPen(col)
                p.setFont(font_kpi)
                p.drawText(QRect(x + 8, y + 28, box_w - 16, 28), Qt.AlignCenter, val)
            y += 76

            # ---- خلاصه هفته‌ها (ستون‌های تراز راست‌چین ثابت) ----
            ensure(30)
            p.setPen(text_dark)
            p.setFont(font_b)
            p.drawText(QRect(margin, y, content_w, 22), Qt.AlignRight, "خلاصه هفته‌ها")
            y += 26

            # عرض ستون‌ها از راست: هفته | مبلغ | متراژ | تعداد
            # RTL visual: right side = week label
            col_w = [
                int(content_w * 0.40),  # هفته
                int(content_w * 0.25),  # مبلغ
                int(content_w * 0.20),  # متراژ
                int(content_w * 0.15),  # تعداد
            ]
            # positions from left
            def col_x(i):
                return margin + sum(col_w[:i])

            row_h = 26
            ensure(row_h)
            p.fillRect(margin, y, content_w, row_h, QColor("#E0F2FE"))
            p.setPen(text_dark)
            p.setFont(font_b)
            headers = ["هفته", "مبلغ فروش", "متراژ", "تعداد"]
            for i, h in enumerate(headers):
                # مبلغ و متراژ چپ‌چین تا مرتب از یک لبه شروع شوند
                align = Qt.AlignLeft | Qt.AlignVCenter if i in (1, 2) else Qt.AlignCenter
                pad = 8 if i in (1, 2) else 0
                p.drawText(QRect(col_x(i) + pad, y, col_w[i] - pad * 2, row_h), align, h)
            y += row_h

            for wk, items_rows in week_groups.items():
                ensure(row_h)
                yk, wn = wk
                w_sum = sum(amount(r[5]) for r in items_rows)
                w_m = sum(self._items_meterage(r[7], r[6]) for r in items_rows)
                wlabel = f"هفته {fa_digits((wn or 0) + 1)}"
                if yk:
                    wlabel += f" ({self._week_range_txt(yk, wn)})"
                vals = [
                    wlabel,
                    fmt(w_sum),
                    self._fmt_meter(w_m),
                    fa_digits(len(items_rows)),
                ]
                bg = white if (wn or 0) % 2 == 0 else bg_soft
                p.fillRect(margin, y, content_w, row_h, bg)
                p.setPen(text_dark)
                p.setFont(font)
                for i, v in enumerate(vals):
                    align = Qt.AlignLeft | Qt.AlignVCenter if i in (1, 2) else Qt.AlignCenter
                    pad = 8 if i in (1, 2) else 0
                    p.setFont(font_b if i == 1 else font)
                    p.drawText(QRect(col_x(i) + pad, y, col_w[i] - pad * 2, row_h), align, v)
                hline(y + row_h)
                y += row_h

            y += 18

            # ---- جزئیات فروش‌ها — جدول ----
            ensure(28)
            p.setPen(text_dark)
            p.setFont(font_b)
            p.drawText(QRect(margin, y, content_w, 22), Qt.AlignRight, "جزئیات فروش‌ها")
            y += 28

            tab_map = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}
            units = {"mdf": ("پالت", "ورق"), "raw": ("پالت", "ورق")}
            # ستون‌ها از راست به چپ
            cw_frac = [0.04, 0.09, 0.37, 0.10, 0.12, 0.13, 0.15]
            cw = [int(content_w * f) for f in cw_frac]
            cw[2] += content_w - sum(cw)
            titles = ["ردیف", "کد کالا", "شرح کالا", "تعداد", "متراژ / ورق", "فی (ریال)", "مبلغ (ریال)"]

            def cx(i):  # لبه‌ی چپ ستون i وقتی ستون ۰ در راست است
                return margin + content_w - sum(cw[:i + 1])

            def table_header():
                nonlocal y
                ensure(28)
                p.fillRect(margin, y, content_w, 26, QColor("#1565C0"))
                p.setPen(white)
                p.setFont(font_b)
                for i, t in enumerate(titles):
                    p.drawText(QRect(cx(i) + 4, y, cw[i] - 8, 26), Qt.AlignCenter, t)
                y += 26

            week_idx = 0
            for wk, items_rows in week_groups.items():
                yk, wn = wk
                w_sum = sum(amount(r[5]) for r in items_rows)
                w_m = sum(self._items_meterage(r[7], r[6]) for r in items_rows)
                mtxt = self._fmt_meter(w_m)
                if week_idx > 0:
                    y += 14
                week_idx += 1

                ensure(110)
                head_h = 34
                round_rect(margin, y, content_w, head_h, QColor("#E0F2FE"), 10, line_c)
                p.setPen(text_dark)
                p.setFont(font_b)
                if yk:
                    head_txt = (
                        f"هفته {fa_digits((wn or 0) + 1)} سال {fa_digits(yk)}  ({self._week_range_txt(yk, wn)})   ·   "
                        f"فروش هفته: {fmt(w_sum)} ریال   ·   متراژ: {mtxt} متر"
                    )
                else:
                    head_txt = f"بدون تاریخ   ·   فروش هفته: {fmt(w_sum)} ریال   ·   متراژ: {mtxt} متر"
                p.drawText(QRect(margin + 10, y, content_w - 20, head_h), Qt.AlignCenter, head_txt)
                y += head_h + 8

                for row in items_rows:
                    rid, customer, inv_no, date, time_s, total, tab, items_json = row
                    tab_fa = tab_map.get(tab or "", tab or "—")
                    u1, u2 = units.get(tab or "", ("کارتن", "متر"))
                    try:
                        items = json.loads(items_json or "[]")
                    except Exception:
                        items = []
                    if not isinstance(items, list):
                        items = []
                    items = [it for it in items if isinstance(it, dict)]

                    ensure(26 + 26 + 40)
                    # نوار فاکتور
                    bar_h = 28
                    p.fillRect(margin, y, content_w, bar_h, QColor("#F1F5F9"))
                    p.fillRect(margin + content_w - 5, y, 5, bar_h, blue)
                    p.setPen(text_dark)
                    p.setFont(font_card)
                    fmb = p.fontMetrics()
                    half = int(content_w * 0.5)
                    p.drawText(
                        QRect(margin + content_w - half - 12, y, half, bar_h),
                        Qt.AlignRight | Qt.AlignVCenter,
                        fmb.elidedText(customer or "—", Qt.ElideLeft, half - 10),
                    )
                    p.setPen(text_muted)
                    p.setFont(font_sm)
                    p.drawText(
                        QRect(margin + 190, y, content_w - half - 210, bar_h),
                        Qt.AlignRight | Qt.AlignVCenter,
                        f"شماره {fa_digits(inv_no or '—')}  |  {fa_digits(date or '')}  |  {tab_fa}",
                    )
                    p.setPen(green)
                    p.setFont(font_amt)
                    p.drawText(
                        QRect(margin + 8, y, 180, bar_h),
                        Qt.AlignLeft | Qt.AlignVCenter,
                        fmt(total) + " ریال",
                    )
                    y += bar_h
                    table_header()

                    p.setFont(font)
                    fmr = p.fontMetrics()
                    for i, it in enumerate(items, 1):
                        typ = str(it.get("type") or it.get("name") or "")
                        extra = [str(it.get(k)) for k in ("grade", "size") if it.get(k) and str(it.get(k)) not in typ]
                        desc = " ".join([x for x in [typ] + extra if x]) or "—"
                        q1, q2, pr, cst = core.qty_int(it.get("qty1")), it.get("qty2"), it.get("price"), it.get("cost")
                        cells = [
                            fa_digits(i),
                            fa_digits(it.get("code") or "—"),
                            desc,
                            (fa_digits(q1) + " " + u1) if q1 not in ("", None) else "—",
                            (fa_digits(q2) + " " + u2) if q2 not in ("", None) else "—",
                            fmt(pr) if pr not in ("", None) else "—",
                            fmt(cst) if cst not in ("", None) else "—",
                        ]
                        dr = fmr.boundingRect(QRect(0, 0, cw[2] - 12, 2000), int(Qt.TextWordWrap | Qt.AlignRight), desc)
                        rh = max(26, dr.height() + 12)
                        ensure(rh + 2)
                        if y == margin:
                            table_header()
                            p.setFont(font)
                        p.fillRect(margin, y, content_w, rh, white if i % 2 else bg_soft)
                        p.setPen(text_dark)
                        p.setFont(font)
                        for ci, val in enumerate(cells):
                            r_ = QRect(cx(ci) + 6, y, cw[ci] - 12, rh)
                            if ci == 2:
                                p.drawText(r_, int(Qt.TextWordWrap | Qt.AlignRight | Qt.AlignVCenter), val)
                            elif ci in (5, 6):
                                if ci == 6:
                                    p.setFont(font_b)
                                p.drawText(r_, Qt.AlignLeft | Qt.AlignVCenter, val)
                                p.setFont(font)
                            else:
                                p.drawText(r_, Qt.AlignCenter, val)
                        hline(y + rh)
                        y += rh
                    y += 12

            y += 12
            ensure(28)
            p.setPen(text_muted)
            p.setFont(font_sm)
            p.drawText(
                QRect(margin, y, content_w, 22),
                Qt.AlignCenter,
                f"جمع: {fmt(month_sum)} ریال  |  {self._fmt_meter(month_m)} متر  |  {fa_digits(len(month_rows))} فروش",
            )
            footer()
            p.end()
            QMessageBox.information(self, "گزارش", f"PDF گزارش {mname} ذخیره شد:\n{path}")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", "خروجی PDF انجام نشد:\n" + str(ex))


class CheckRasPage(QWidget):
    """راس‌گیری چک — ورود ساده تاریخ و مبلغ"""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)
        self.rows = []
        self._last_result = None
        self._base_date = datetime.now().date()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # یک اسکرول برای کل صفحه: همه چک‌ها یکجا دیده می‌شوند؛ برای دکمه‌ها اسکرول کنید
        self.page_scroll = QScrollArea()
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.NoFrame)
        self.page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.page_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.page_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:12px;background:#F1F5F9;border-radius:6px;margin:2px;}"
            "QScrollBar::handle:vertical{background:#94A3B8;border-radius:6px;min-height:48px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(16, 12, 16, 16)
        lay.setSpacing(10)

        title = QLabel("راس‌گیری چک")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        sub = QLabel("تاریخ و مبلغ هر چک را وارد کنید — همه چک‌ها در صفحه دیده می‌شوند")
        sub.setObjectName("hint")
        lay.addWidget(sub)

        tip = QLabel("تاریخ به صورت سال/ماه/روز  ·  مبلغ با جداکننده هزارگان  ·  برای دیدن دکمه‌های پایین صفحه را اسکرول کنید")
        tip.setWordWrap(True)
        tip.setStyleSheet(
            "background:#EFF6FF;color:#1E40AF;border:1px solid #BFDBFE;"
            "border-radius:12px;padding:8px 12px;font-size:12px;"
        )
        lay.addWidget(tip)

        base_row = QHBoxLayout()
        base_lbl = QLabel("تاریخ مبدأ:")
        base_lbl.setStyleSheet("font-size:13px;font-weight:600;color:#334155;")
        self.base_date_btn = QPushButton()
        self.base_date_btn.setCursor(Qt.PointingHandCursor)
        self.base_date_btn.setMinimumHeight(40)
        self.base_date_btn.setStyleSheet(
            "QPushButton{background:#FFF7ED;color:#9A3412;border:1px solid #FDBA74;"
            "border-radius:12px;padding:8px 14px;font-size:14px;font-weight:700;text-align:center;}"
            "QPushButton:hover{background:#FFEDD5;}"
        )
        self.base_date_btn.clicked.connect(self.pick_base_date)
        self._refresh_base_date_btn()
        base_row.addWidget(base_lbl)
        base_row.addWidget(self.base_date_btn, 1)
        lay.addLayout(base_row)

        res = QHBoxLayout()
        res.setSpacing(8)
        self.card_total = self._result_card("جمع مبلغ چک‌ها", "۰ ریال", "#1565C0")
        self.card_days = self._result_card("تعداد روز از مبدأ", "—", "#F59E0B")
        self.card_ras = self._result_card("تاریخ راس", "—", "#059669")
        res.addWidget(self.card_total)
        res.addWidget(self.card_days)
        res.addWidget(self.card_ras)
        lay.addLayout(res)

        head = QHBoxLayout()
        hl = QLabel("لیست چک‌ها")
        hl.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;")
        head.addWidget(hl)
        head.addStretch()
        add_btn = QPushButton("+ افزودن چک")
        add_btn.setCursor(Qt.PointingHandCursor)
        add_btn.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;"
            "padding:8px 14px;font-weight:700;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        add_btn.clicked.connect(lambda: self.add_check_row())
        head.addWidget(add_btn)
        lay.addLayout(head)

        # همه چک‌ها بدون اسکرول جدا — ارتفاع طبیعی
        self.rows_host = QVBoxLayout()
        self.rows_host.setContentsMargins(0, 0, 0, 0)
        self.rows_host.setSpacing(6)
        lay.addLayout(self.rows_host)

        self.detail_lbl = QLabel("")
        self.detail_lbl.setWordWrap(True)
        self.detail_lbl.setStyleSheet(
            "background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;"
            "padding:8px 12px;color:#334155;font-size:12px;"
        )
        lay.addWidget(self.detail_lbl)

        # دکمه‌ها داخل همان صفحه اسکرول‌شونده
        bottom = QFrame()
        bottom.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;}"
        )
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(10, 10, 10, 10)
        bl.setSpacing(8)
        actions = QHBoxLayout()
        calc_btn = QPushButton("محاسبه راس")
        calc_btn.setMinimumHeight(44)
        calc_btn.setCursor(Qt.PointingHandCursor)
        calc_btn.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:12px;"
            "font-size:14px;font-weight:800;padding:10px;}"
            "QPushButton:hover{background:#047857;}"
        )
        calc_btn.clicked.connect(self.calculate)
        clear_btn = QPushButton("پاک کردن")
        clear_btn.setMinimumHeight(44)
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#991B1B;border:none;border-radius:12px;"
            "padding:10px 14px;font-weight:700;}"
        )
        clear_btn.clicked.connect(self.clear_all)
        actions.addWidget(calc_btn, 2)
        actions.addWidget(clear_btn, 1)
        bl.addLayout(actions)
        exp_row = QHBoxLayout()
        pdf_btn = QPushButton("خروجی PDF")
        img_btn = QPushButton("خروجی تصویر")
        for b, col in ((pdf_btn, "#1565C0"), (img_btn, "#0F172A")):
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(42)
            b.setStyleSheet(
                f"QPushButton{{background:{col};color:#fff;border:none;border-radius:12px;"
                f"font-weight:700;font-size:13px;padding:8px 12px;}}"
            )
        pdf_btn.clicked.connect(self.export_pdf)
        img_btn.clicked.connect(self.export_image)
        exp_row.addWidget(pdf_btn)
        exp_row.addWidget(img_btn)
        bl.addLayout(exp_row)
        lay.addWidget(bottom)
        lay.addSpacing(20)

        self.page_scroll.setWidget(page)
        outer.addWidget(self.page_scroll, 1)

        # سازگاری با کد قبلی که rows_scroll داشت
        self.rows_scroll = self.page_scroll

        self.add_check_row()
        self.add_check_row()



    def _result_card(self, title, value, color):
        f = QFrame()
        f.setStyleSheet(
            f"QFrame{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;"
            f"border-top:3px solid {color};}}"
        )
        v = QVBoxLayout(f)
        v.setContentsMargins(10, 8, 10, 8)
        t = QLabel(title)
        t.setStyleSheet("color:#64748B;font-size:12px;font-weight:600;border:none;background:transparent;")
        val = QLabel(value)
        val.setObjectName("rasValue")
        val.setStyleSheet(
            "color:#0F172A;font-size:18px;font-weight:800;border:none;background:transparent;"
        )
        val.setAlignment(Qt.AlignCenter)
        v.addWidget(t)
        v.addWidget(val)
        f._val = val
        return f

    def add_check_row(self):
        row = QFrame()
        row.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;}"
        )
        hl = QHBoxLayout(row)
        hl.setContentsMargins(10, 6, 10, 6)
        hl.setSpacing(8)
        n = len(self.rows) + 1
        num = QLabel(fa_digits(n))
        num.setFixedWidth(28)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet(
            "background:#EFF6FF;color:#1D4ED8;border-radius:8px;font-weight:800;padding:6px;"
        )
        date_ed = QLineEdit()
        date_ed.setPlaceholderText("")
        date_ed.setLayoutDirection(Qt.LeftToRight)
        date_ed.setAlignment(Qt.AlignCenter)
        date_ed.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;"
            "padding:10px;font-family:Vazirmatn,Tahoma,'Segoe UI';font-size:14px;"
            "direction:ltr;}"
        )
        date_ed.editingFinished.connect(lambda d=date_ed: self._normalize_ras_date(d))
        amt_ed = MoneyLineEdit()
        amt_ed.setPlaceholderText("مبلغ (ریال)")
        amt_ed.setAlignment(Qt.AlignCenter)
        amt_ed.setStyleSheet(
            "QLineEdit{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:10px;}"
        )
        rm = QPushButton("✕")
        rm.setFixedWidth(36)
        rm.setCursor(Qt.PointingHandCursor)
        rm.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#991B1B;border:none;border-radius:8px;font-weight:700;}"
        )
        rm.clicked.connect(lambda: self.remove_row(row))
        date_ed.returnPressed.connect(lambda d=date_ed, a=amt_ed: self._on_date_enter(d, a))
        amt_ed.returnPressed.connect(lambda a=amt_ed: self._on_amount_enter(a))
        hl.addWidget(num)
        hl.addWidget(date_ed, 2)
        hl.addWidget(amt_ed, 2)
        hl.addWidget(rm)
        self.rows_host.addWidget(row)
        self.rows.append((date_ed, amt_ed, row, num))
        # با فوکوس هر کادر، همان ردیف در دید بیاید (وقتی چک‌ها زیادند صفحه پایین نماند)
        if not hasattr(self, "_ed_row"):
            self._ed_row = {}
        for ed in (date_ed, amt_ed):
            self._ed_row[id(ed)] = row
            ed.installEventFilter(self)
        date_ed.setFocus()
        self._show_row(row)

    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.FocusIn:
                row = getattr(self, "_ed_row", {}).get(id(obj))
                if row is not None:
                    self._show_row(row)
        except Exception:
            _swallow()
        return super().eventFilter(obj, ev)

    def _show_row(self, row):
        """ردیف در حال پر شدن را در دید نگه می‌دارد؛ چند بار (بعد از چیدمان) تا جای نادرست نماند."""
        def _go():
            try:
                self.page_scroll.widget().layout().activate()
                self.page_scroll.ensureWidgetVisible(row, 0, 90)
            except Exception:
                _swallow()
        for ms in (0, 60, 160):
            QTimer.singleShot(ms, _go)

    def _normalize_ras_date(self, date_ed):
        """بعد از ورود، تاریخ را به صورت سال/ماه/روز فارسی نشان بده (روز سمت راست)."""
        try:
            parsed = parse_flexible_jalali(date_ed.text())
            if not parsed:
                return
            y, m, d = parsed
            date_ed.setLayoutDirection(Qt.LeftToRight)
            date_ed.setText(format_jalali_ymd(y, m, d))
        except Exception:
            _swallow()

    def _on_date_enter(self, date_ed, amt_ed):
        self._normalize_ras_date(date_ed)
        amt_ed.setFocus()
        amt_ed.selectAll()

    def _on_amount_enter(self, amt_ed):
        idx = None
        for i, (d, a, w, n) in enumerate(self.rows):
            if a is amt_ed:
                idx = i
                break
        if idx is None:
            return
        if idx >= len(self.rows) - 1:
            self.add_check_row()
            if self.rows:
                self.rows[-1][0].setFocus()
                self._show_row(self.rows[-1][2])
        else:
            self.rows[idx + 1][0].setFocus()
            self.rows[idx + 1][0].selectAll()
            self._show_row(self.rows[idx + 1][2])

    def remove_row(self, row_w):
        self.rows = [r for r in self.rows if r[2] is not row_w]
        row_w.deleteLater()
        for i, r in enumerate(self.rows, 1):
            r[3].setText(fa_digits(i))
        if not self.rows:
            self.add_check_row()

    def clear_all(self):
        for _, _, w, _ in self.rows:
            w.deleteLater()
        self.rows.clear()
        self.add_check_row()
        self.add_check_row()
        self.card_total._val.setText("۰ ریال")
        self.card_days._val.setText("—")
        self.card_ras._val.setText("—")
        self.detail_lbl.setText("")

    def _refresh_base_date_btn(self):
        d = getattr(self, "_base_date", datetime.now().date())
        jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
        self.base_date_btn.setText(
            "📅  " + format_jalali_ymd(jy, jm, jd) + "  (برای تغییر بزنید)"
        )

    def pick_base_date(self):
        """تقویم شمسی برای انتخاب تاریخ مبدأ"""
        from PySide6.QtWidgets import (
            QDialog, QDialogButtonBox, QGridLayout, QHBoxLayout as _QH,
            QVBoxLayout as _QV, QSizePolicy,
        )
        PERSIAN_MONTHS = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ]
        WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"]  # شنبه تا جمعه

        bd = getattr(self, "_base_date", datetime.now().date())
        jy, jm, jd = gregorian_to_jalali(bd.year, bd.month, bd.day)
        state = {"y": jy, "m": jm, "d": jd}

        dlg = QDialog(self)
        dlg.setWindowTitle("انتخاب تاریخ مبدأ (شمسی)")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(380, 420)
        lay = _QV(dlg)
        lay.setSpacing(10)

        info = QLabel("تاریخ مبدأ را از تقویم شمسی انتخاب کنید")
        info.setStyleSheet("color:#64748B;font-size:12px;")
        lay.addWidget(info)

        # نوار ماه
        nav = _QH()
        btn_prev = QPushButton("‹")
        btn_next = QPushButton("›")
        for b in (btn_prev, btn_next):
            b.setFixedSize(36, 36)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{background:#F1F5F9;border:none;border-radius:10px;font-size:18px;font-weight:800;}"
                "QPushButton:hover{background:#E2E8F0;}"
            )
        title = QLabel()
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size:15px;font-weight:800;color:#0F172A;")
        nav.addWidget(btn_prev)
        nav.addWidget(title, 1)
        nav.addWidget(btn_next)
        lay.addLayout(nav)

        # هدر روزهای هفته
        grid = QGridLayout()
        grid.setSpacing(4)
        for col, w in enumerate(WEEKDAYS):
            lab = QLabel(w)
            lab.setAlignment(Qt.AlignCenter)
            lab.setStyleSheet("color:#94A3B8;font-size:12px;font-weight:700;")
            grid.addWidget(lab, 0, col)
        day_btns = []
        for r in range(6):
            for c in range(7):
                b = QPushButton("")
                b.setFixedSize(42, 42)
                b.setCursor(Qt.PointingHandCursor)
                b.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                grid.addWidget(b, r + 1, c)
                day_btns.append(b)
        lay.addLayout(grid)

        preview = QLabel()
        preview.setAlignment(Qt.AlignCenter)
        preview.setStyleSheet("font-size:15px;font-weight:800;color:#1565C0;padding:8px;")
        lay.addWidget(preview)

        def days_in_jmonth(y, m):
            if m <= 6:
                return 31
            if m <= 11:
                return 30
            # اسفند: اگر ۳۰ معتبر باشد کبیسه است
            gy, gm, gd = jalali_to_gregorian(y, 12, 30)
            jy2, jm2, jd2 = gregorian_to_jalali(gy, gm, gd)
            return 30 if (jy2, jm2, jd2) == (y, 12, 30) else 29

        def jmonth_start_weekday(y, m):
            """0=شنبه ... 6=جمعه"""
            gy, gm, gd = jalali_to_gregorian(y, m, 1)
            # Python: Mon=0 ... Sun=6 → شنبه=5
            wd = datetime(gy, gm, gd).weekday()  # Mon=0
            # map to Sat=0: Sat=5,Sun=6,Mon=0,...Fri=4
            return (wd + 2) % 7

        def paint():
            y, m, d = state["y"], state["m"], state["d"]
            title.setText(PERSIAN_MONTHS[m - 1] + " " + fa_digits(y))
            preview.setText(format_jalali_ymd(y, m, d))
            dim = days_in_jmonth(y, m)
            start = jmonth_start_weekday(y, m)
            for i, b in enumerate(day_btns):
                day = i - start + 1
                b.blockSignals(True)
                if day < 1 or day > dim:
                    b.setText("")
                    b.setEnabled(False)
                    b.setStyleSheet("QPushButton{background:transparent;border:none;}")
                    b.setProperty("jday", 0)
                else:
                    b.setEnabled(True)
                    b.setText(fa_digits(day))
                    b.setProperty("jday", day)
                    if day == d:
                        b.setStyleSheet(
                            "QPushButton{background:#1565C0;color:#fff;border:none;"
                            "border-radius:10px;font-weight:800;}"
                        )
                    else:
                        b.setStyleSheet(
                            "QPushButton{background:#F8FAFC;color:#0F172A;border:1px solid #E2E8F0;"
                            "border-radius:10px;font-weight:600;}"
                            "QPushButton:hover{background:#E0F2FE;}"
                        )
                b.blockSignals(False)

        def on_day():
            b = dlg.sender()
            day = b.property("jday")
            if not day:
                return
            state["d"] = int(day)
            paint()

        for b in day_btns:
            b.clicked.connect(on_day)

        def prev_m():
            state["m"] -= 1
            if state["m"] < 1:
                state["m"] = 12
                state["y"] -= 1
            dim = days_in_jmonth(state["y"], state["m"])
            if state["d"] > dim:
                state["d"] = dim
            paint()

        def next_m():
            state["m"] += 1
            if state["m"] > 12:
                state["m"] = 1
                state["y"] += 1
            dim = days_in_jmonth(state["y"], state["m"])
            if state["d"] > dim:
                state["d"] = dim
            paint()

        btn_prev.clicked.connect(prev_m)
        btn_next.clicked.connect(next_m)
        paint()

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("تأیید")
        btns.button(QDialogButtonBox.Cancel).setText("انصراف")
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() != QDialog.Accepted:
            return
        gy, gm, gd = jalali_to_gregorian(state["y"], state["m"], state["d"])
        self._base_date = datetime(gy, gm, gd).date()
        self._refresh_base_date_btn()
        try:
            if self._last_result:
                self.calculate()
        except Exception:
            _swallow()

    def calculate(self):
        today = getattr(self, "_base_date", None) or datetime.now().date()
        jy0, jm0, jd0 = gregorian_to_jalali(today.year, today.month, today.day)
        items = []
        details = []
        for i, (date_ed, amt_ed, _, _) in enumerate(self.rows, 1):
            parsed = parse_flexible_jalali(date_ed.text(), default_year=jy0)
            am = amount(amt_ed.text())
            if not parsed and not amt_ed.text().strip():
                continue
            if not parsed:
                QMessageBox.warning(self, "راس چک", f"تاریخ ردیف {fa_digits(i)} نامعتبر است.")
                return
            if am <= 0:
                QMessageBox.warning(self, "راس چک", f"مبلغ ردیف {fa_digits(i)} را وارد کنید.")
                return
            y, m, d = parsed
            try:
                gy, gm, gd = jalali_to_gregorian(y, m, d)
                gdate = datetime(gy, gm, gd).date()
            except Exception:
                QMessageBox.warning(self, "راس چک", f"تاریخ ردیف {fa_digits(i)} قابل تبدیل نیست.")
                return
            delta = (gdate - today).days
            items.append((am, delta, gdate, y, m, d))
            details.append(
                f"چک {fa_digits(i)}: {fa_digits(f'{y:04d}/{m:02d}/{d:02d}')}  ·  "
                f"{fmt(am)} ریال  ·  {fa_digits(delta)} روز از امروز"
            )
        if not items:
            QMessageBox.information(self, "راس چک", "حداقل یک چک با تاریخ و مبلغ وارد کنید.")
            return
        total = sum(a for a, *_ in items)
        weighted = sum(a * days for a, days, *_ in items)
        avg_days = weighted / total if total else 0
        # round to nearest day
        avg_round = int(round(avg_days))
        ras_g = today + __import__('datetime').timedelta(days=avg_round)
        ry, rm, rd = gregorian_to_jalali(ras_g.year, ras_g.month, ras_g.day)
        ras_str = format_jalali_ymd(ry, rm, rd)

        items_sorted = sorted(items, key=lambda x: x[2])
        details = []
        for i, (am, delta, gdate, y, m, d) in enumerate(items_sorted, 1):
            details.append(
                "چک " + fa_digits(i) + ": " + format_jalali_ymd(y, m, d)
                + "  ·  " + fmt(am) + " ریال  ·  " + fa_digits(delta) + " روز"
            )
        self.card_total._val.setText(fmt(total) + " ریال")
        if avg_round > 0:
            days_txt = fa_digits(avg_round) + " روز بعد"
        elif avg_round < 0:
            days_txt = fa_digits(abs(avg_round)) + " روز قبل"
        else:
            days_txt = "همان روز مبدأ"
        self.card_days._val.setText(days_txt)
        self.card_ras._val.setText(ras_str)
        self.detail_lbl.setText(
            "جزئیات (به ترتیب تاریخ):\n" + "\n".join(details)
            + "\n\nمیانگین وزنی: " + fa_digits(f"{avg_days:.2f}")
            + " روز  →  راس: " + ras_str
        )
        self._last_result = {
            "items": items_sorted,
            "total": total,
            "avg_days": avg_days,
            "avg_round": avg_round,
            "days_txt": days_txt,
            "ras_str": ras_str,
            "today_j": f"{jy0:04d}/{jm0:02d}/{jd0:02d}",
        }





    def _ras_font(self, size=12, bold=False):
        from PySide6.QtGui import QFont
        # روی رزولوشن بالا، نقطه را بزرگ‌تر کن تا خوانا بماند
        scale = getattr(self, "_ras_font_scale", 1.0)
        px = max(10, int(round(size * scale)))
        f = QFont("Tahoma")
        for name in ("Vazirmatn", "Vazir", "IRANSans", "B Nazanin", "Tahoma"):
            f = QFont(name)
            f.setPixelSize(px)
            f.setBold(bold)
            if QFont(name).exactMatch() or name == "Tahoma":
                break
        f.setPixelSize(px)
        f.setBold(bold)
        return f

    def _paint_ras_report(self, painter, page_w, page_h, margin=36):
        """رسم گزارش راس — خوانا و متعادل (کمی درشت‌تر از نسخه پایه)."""
        from PySide6.QtGui import QColor, QPen, QPainterPath
        from PySide6.QtCore import QRectF
        r = self._last_result
        if not r:
            return

        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        # کمی بزرگ‌تر از پایه (نه ۲ برابر)
        self._ras_font_scale = max(1.2, float(page_w) / 1050.0)

        painter.fillRect(0, 0, page_w, page_h, QColor("#F1F5F9"))
        content = QRectF(margin, margin, page_w - 2 * margin, page_h - 2 * margin)

        card = QRectF(content.left(), content.top(), content.width(), content.height() - 8)
        path = QPainterPath()
        path.addRoundedRect(card, 18, 18)
        painter.fillPath(path, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#E2E8F0"), 1.5))
        painter.drawPath(path)

        x = card.left() + 28
        w = card.width() - 56

        # هدر
        header = QRectF(card.left() + 12, card.top() + 12, card.width() - 24, 88)
        hpath = QPainterPath()
        hpath.addRoundedRect(header, 14, 14)
        painter.fillPath(hpath, QColor("#0F172A"))

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self._ras_font(22, True))
        painter.drawText(header.adjusted(12, 10, -12, -32), Qt.AlignCenter, "گزارش راس‌گیری چک")
        painter.setFont(self._ras_font(12, False))
        painter.setPen(QColor("#94A3B8"))
        painter.drawText(
            header.adjusted(12, 48, -12, -8),
            Qt.AlignCenter,
            "تاریخ محاسبه: " + fa_digits(r["today_j"]),
        )

        y = header.bottom() + 22

        # سه کارت
        gap = 12
        box_w = (w - 2 * gap) / 3
        boxes = [
            ("جمع مبلغ", fmt(r["total"]) + " ریال", QColor("#1565C0"), QColor("#EFF6FF")),
            ("تعداد روز", r["days_txt"], QColor("#D97706"), QColor("#FFFBEB")),
            ("تاریخ راس", fa_digits(r["ras_str"]), QColor("#059669"), QColor("#ECFDF5")),
        ]
        for i, (lbl, val, accent, bg) in enumerate(boxes):
            bx = x + i * (box_w + gap)
            br = QRectF(bx, y, box_w, 90)
            bp = QPainterPath()
            bp.addRoundedRect(br, 12, 12)
            painter.fillPath(bp, bg)
            painter.setPen(QPen(accent, 2 if i == 2 else 1.2))
            painter.drawPath(bp)
            painter.fillRect(QRectF(bx, y, box_w, 5), accent)
            painter.setPen(QColor("#64748B"))
            painter.setFont(self._ras_font(11, True))
            painter.drawText(br.adjusted(6, 14, -6, -48), Qt.AlignCenter, lbl)
            painter.setPen(accent if i == 2 else QColor("#0F172A"))
            painter.setFont(self._ras_font(15 if i != 2 else 17, True))
            painter.drawText(br.adjusted(6, 40, -6, -8), Qt.AlignCenter, val)

        y += 110

        painter.setPen(QColor("#0F172A"))
        painter.setFont(self._ras_font(13, True))
        painter.drawText(QRectF(x, y, w, 26), Qt.AlignRight | Qt.AlignVCenter, "لیست چک‌ها (به ترتیب تاریخ)")
        y += 32

        cols = [0.10, 0.28, 0.37, 0.25]
        headers = ["ردیف", "تاریخ چک", "مبلغ (ریال)", "روز از امروز"]
        row_h = 42
        th = QRectF(x, y, w, row_h)
        painter.fillRect(th, QColor("#0F172A"))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self._ras_font(11, True))
        cx = x
        for frac, htxt in zip(cols, headers):
            cw = w * frac
            align = (Qt.AlignRight | Qt.AlignVCenter) if htxt == "تاریخ چک" else Qt.AlignCenter
            painter.drawText(QRectF(cx, y, cw, row_h).adjusted(8, 0, -8, 0), align, htxt)
            cx += cw
        y += row_h

        for i, (am, delta, gdate, yy, mm, dd) in enumerate(r["items"]):
            if y + row_h > card.bottom() - 72:
                break
            bg = QColor("#F8FAFC") if i % 2 == 0 else QColor("#FFFFFF")
            painter.fillRect(QRectF(x, y, w, row_h), bg)
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
            painter.drawLine(int(x), int(y + row_h), int(x + w), int(y + row_h))

            dstr = fa_digits(f"{yy:04d}/{mm:02d}/{dd:02d}")
            vals = [
                (fa_digits(i + 1), Qt.AlignCenter, QColor("#334155"), 12, False),
                (dstr, Qt.AlignRight | Qt.AlignVCenter, QColor("#0D47A1"), 13, True),
                (fmt(am), Qt.AlignCenter, QColor("#0F172A"), 12, True),
                (fa_digits(delta), Qt.AlignCenter, QColor("#334155"), 12, False),
            ]
            cx = x
            for frac, (v, align, color, fsize, bold) in zip(cols, vals):
                cw = w * frac
                painter.setPen(color)
                painter.setFont(self._ras_font(fsize, bold))
                painter.drawText(QRectF(cx, y, cw, row_h).adjusted(8, 0, -8, 0), align, v)
                cx += cw
            y += row_h

        y = max(y + 20, card.bottom() - 64)
        foot = QRectF(x, y, w, 52)
        fp = QPainterPath()
        fp.addRoundedRect(foot, 12, 12)
        painter.fillPath(fp, QColor("#059669"))
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(self._ras_font(13, True))
        foot_txt = (
            "تاریخ راس: " + fa_digits(r["ras_str"])
            + "    |    " + r["days_txt"]
            + "    |    جمع: " + fmt(r["total"]) + " ریال"
        )
        painter.drawText(foot, Qt.AlignCenter, foot_txt)

    def export_pdf(self):
        if not self._last_result:
            QMessageBox.information(self, "خروجی", "ابتدا محاسبه راس را انجام دهید.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره PDF راس چک", "ras_check.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            from PySide6.QtGui import QPainter, QPageSize, QPdfWriter, QImage
            from PySide6.QtCore import QSizeF, QMarginsF
            # روش پایدار: اول روی تصویر با کیفیت بکش، بعد به PDF منتقل کن
            img_w, img_h = 2480, 3508  # A4 در حدود 300dpi
            img = QImage(img_w, img_h, QImage.Format_ARGB32)
            img.fill(0xFFF8FAFC)
            p_img = QPainter(img)
            self._paint_ras_report(p_img, img_w, img_h, margin=80)
            p_img.end()

            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setResolution(300)
            try:
                writer.setPageMargins(QMarginsF(8, 8, 8, 8))
            except Exception:
                _swallow()
            painter = QPainter(writer)
            # مقیاس به صفحه PDF
            pw = writer.width()
            ph = writer.height()
            # حفظ نسبت
            scale = min(pw / img_w, ph / img_h)
            tw = int(img_w * scale)
            th = int(img_h * scale)
            ox = (pw - tw) // 2
            oy = (ph - th) // 2
            from PySide6.QtCore import QRect
            painter.drawImage(QRect(ox, oy, tw, th), img)
            painter.end()
            QMessageBox.information(self, "خروجی", "فایل PDF با موفقیت ذخیره شد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", "خروجی PDF انجام نشد:\n" + str(ex))

    def export_image(self):
        if not self._last_result:
            QMessageBox.information(self, "خروجی", "ابتدا محاسبه راس را انجام دهید.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره تصویر راس چک", "ras_check.png", "PNG (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            from PySide6.QtGui import QImage, QPainter
            # رزولوشن بالا برای وضوح
            w, h = 2480, 3508
            img = QImage(w, h, QImage.Format_ARGB32)
            img.fill(0xFFF8FAFC)
            painter = QPainter(img)
            self._paint_ras_report(painter, w, h, margin=80)
            painter.end()
            img.save(path, "PNG", 100)
            QMessageBox.information(self, "خروجی", "تصویر با موفقیت ذخیره شد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", "خروجی تصویر انجام نشد:\n" + str(ex))
