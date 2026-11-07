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
    QGridLayout, QToolTip, QAbstractItemView
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
    CODE_TO_PRODUCT,
    INQUIRY_PATH,
    PRODUCT_FACTORS,
    resolve_product,
    _load_seed_contacts,
    _swallow,
    amount,
    clean_number,
    customer_balance,
    db,
    delete_inquiry_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    get_customer_color,
    gregorian_to_jalali,
    group_invoices_by_month,
    load_contacts,
    now_jalali,
    pull_contacts_from_supabase,
    push_contacts_to_supabase,
    save_contacts,
    schedule_supabase_sync,
)
except Exception:
    from salesmate.app_core import (
    APP_DIR,
    CODE_TO_PRODUCT,
    INQUIRY_PATH,
    PRODUCT_FACTORS,
    resolve_product,
    _load_seed_contacts,
    _swallow,
    amount,
    clean_number,
    customer_balance,
    db,
    delete_inquiry_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    get_customer_color,
    gregorian_to_jalali,
    group_invoices_by_month,
    load_contacts,
    now_jalali,
    pull_contacts_from_supabase,
    push_contacts_to_supabase,
    save_contacts,
    schedule_supabase_sync,
)


class MoneyLineEdit(QLineEdit):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignRight)
        self.textChanged.connect(self.format_money)

    def format_money(self,text):
        digits=clean_number(text)
        shown=fa_digits(f"{int(digits):,}") if digits else ""
        if shown != text:
            self.blockSignals(True)
            self.setText(shown)
            self.setCursorPosition(len(shown))
            self.blockSignals(False)

    def raw_value(self):
        return clean_number(self.text())


class _InvoiceItemsEnterDelegate(QStyledItemDelegate):
    """Enter در جدول اقلام → فیلد بعدی (مثل فرم استعلام)."""
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog

    def createEditor(self, parent, option, index):
        # ستون متراژ(4) و جمع(5) قابل ویرایش دستی نباشند
        if index.column() in (4, 5):
            return None
        editor = super().createEditor(parent, option, index)
        if editor is not None:
            editor.installEventFilter(self)
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            try:
                self.commitData.emit(editor)
                self.closeEditor.emit(editor, QAbstractItemDelegate.NoHint)
            except Exception:
                _swallow()
            try:
                self.dialog._advance_items_cell()
            except Exception:
                _swallow()
            return True
        return super().eventFilter(editor, event)


class InvoiceDialog(QDialog):

    def __init__(self, parent=None, row=None):
        super().__init__(parent)
        self.row = row
        self.setWindowTitle("ویرایش حواله" if row else "ثبت حواله جدید")
        self.resize(640, 580)
        self.setLayoutDirection(Qt.RightToLeft)
        l = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(10)

        self.customer = QComboBox()
        self.customer.setEditable(True)
        self.customer.setInsertPolicy(QComboBox.NoInsert)
        self.customer.setMaxVisibleItems(14)
        self.customer.lineEdit().setPlaceholderText("نام مشتری را تایپ کنید یا از لیست انتخاب کنید...")
        self.customer.setLayoutDirection(Qt.RightToLeft)
        self.load_customers()

        self.invoice = QLineEdit()
        self.invoice.textChanged.connect(self.format_invoice)
        self.invoice.setAlignment(Qt.AlignRight)
        self.date = QLineEdit()
        self.date.setPlaceholderText("تاریخ")
        self.date.setAlignment(Qt.AlignCenter)
        self.time = QLineEdit()
        self.time.setPlaceholderText("ساعت")
        self.time.setAlignment(Qt.AlignCenter)
        self.total = MoneyLineEdit()
        self.total.setPlaceholderText("مبلغ کل")
        self.paid = MoneyLineEdit()
        self.paid.setPlaceholderText("مبلغ پرداختی")
        self.image_path = ""
        self.image_label = QLabel("عکسی انتخاب نشده")
        self.image_label.setStyleSheet("color:#6B7280; padding:6px;")
        self.image_button = QPushButton("انتخاب عکس حواله")
        self.image_button.setProperty("class", "secondaryButton")
        self.image_button.clicked.connect(self.choose_image)

        self._inquiry_data = {}
        if row:
            cu, inv, da, ti, to = row[1], row[2], row[3], row[4], row[5]
            img = row[7] if len(row) > 7 else ""
            paid0 = row[8] if len(row) > 8 else ""
            inq_raw = row[9] if len(row) > 9 else ""
            self.customer.setCurrentText(cu)
            self.invoice.setText(inv)
            self.date.setText(fa_digits(da))
            self.time.setText(fa_digits(ti))
            self.total.setText(fmt(to))
            if paid0 is None or str(paid0).strip() == "":
                self.paid.setText(fmt(to))
            else:
                self.paid.setText(fmt(paid0))
            self.image_path = img or ""
            self.image_label.setText(Path(self.image_path).name if self.image_path else "عکسی انتخاب نشده")
            if inq_raw:
                try:
                    self._inquiry_data = json.loads(inq_raw) if isinstance(inq_raw, str) else (inq_raw or {})
                except Exception:
                    self._inquiry_data = {}
                if not isinstance(self._inquiry_data, dict):
                    self._inquiry_data = {}
        else:
            self.customer.setCurrentIndex(-1)
            self.customer.setCurrentText("")
            self.refresh_dt()
            self.paid.setText("")

        form.addRow("نام مشتری:", self.customer)
        form.addRow("شماره فاکتور:", self.invoice)
        form.addRow("تاریخ:", self.date)
        form.addRow("ساعت:", self.time)
        form.addRow("مبلغ کل:", self.total)
        form.addRow("مبلغ پرداختی:", self.paid)
        form.addRow("عکس حواله:", self.image_button)
        form.addRow("", self.image_label)
        l.addLayout(form)

        items_title = QLabel("اقلام کالا — کد / تعداد کارتن / مبلغ هر مترمربع")
        items_title.setStyleSheet("font-size:13px;font-weight:700;color:#0F172A;")
        l.addWidget(items_title)

        self.items_table = QTableWidget(0, 6)
        self.items_table.setHorizontalHeaderLabels(
            ["کد کالا", "نوع", "تعداد کارتن", "مبلغ هر مترمربع", "متراژ", "جمع ردیف"]
        )
        self.items_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setMinimumHeight(150)
        self.items_table.setStyleSheet(
            "QTableWidget{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;}"
            "QHeaderView::section{background:#F1F5F9;padding:6px;border:none;font-weight:700;}"
        )
        l.addWidget(self.items_table)

        row_btns = QHBoxLayout()
        add_row_btn = QPushButton("+ ردیف")
        add_row_btn.setCursor(Qt.PointingHandCursor)
        add_row_btn.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        add_row_btn.clicked.connect(lambda: self._add_item_row())

        del_row_btn = QPushButton("حذف ردیف")
        del_row_btn.setCursor(Qt.PointingHandCursor)
        del_row_btn.setStyleSheet(
            "QPushButton{background:#64748B;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        del_row_btn.clicked.connect(self._remove_item_row)
        sum_btn = QPushButton("محاسبه جمع کل از اقلام")
        sum_btn.setCursor(Qt.PointingHandCursor)
        sum_btn.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        sum_btn.clicked.connect(self._recalc_total_from_items)
        self._excel_locked = bool(isinstance(self._inquiry_data, dict)
                                  and self._inquiry_data.get("tab") == "analysis_import")
        if self._excel_locked:
            for _b in (add_row_btn, del_row_btn, sum_btn):
                _b.setEnabled(False)
            items_title.setText("اقلام کالا — واردشده از اکسل فروش (فقط‌خواندنی؛ برای تغییر، اکسل را اصلاح و دوباره بارگذاری کنید)")
            try:
                self.total.setReadOnly(True)
            except Exception:
                _swallow()
        row_btns.addWidget(add_row_btn)
        row_btns.addWidget(del_row_btn)
        row_btns.addWidget(sum_btn)
        row_btns.addStretch()
        l.addLayout(row_btns)

        # جمع اقلام برای چک کردن
        self.items_sum_lbl = QLabel("جمع اقلام: ۰ ردیف  |  متراژ: ۰  |  مبلغ: ۰ ریال")
        self.items_sum_lbl.setAlignment(Qt.AlignCenter)
        self.items_sum_lbl.setStyleSheet(
            "QLabel{background:#ECFDF5;color:#065F46;border:1px solid #A7F3D0;"
            "border-radius:12px;padding:10px 12px;font-size:13px;font-weight:800;}"
        )
        l.addWidget(self.items_sum_lbl)

        self._load_items_into_table()
        if self._excel_locked:
            self.items_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            self.items_table.cellChanged.connect(self._on_item_cell_changed)
        try:
            self.items_table.setItemDelegate(_InvoiceItemsEnterDelegate(self))
        except Exception:
            _swallow()

        buttons = QDialogButtonBox()
        save_btn = buttons.addButton("ذخیره", QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton("انصراف", QDialogButtonBox.RejectRole)
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        l.addWidget(buttons)

    def _add_item_row(self, code="", typ="", qty1="", price="", qty2="", cost=""):
        r = self.items_table.rowCount()
        self.items_table.blockSignals(True)
        self.items_table.insertRow(r)
        code_s = en_digits(str(code or "")).strip()
        typ_s = str(typ or "").strip()
        if not typ_s and code_s:
            typ_s = CODE_TO_PRODUCT.get(code_s, "") or ""
        vals = [
            fa_digits(code_s),
            typ_s,
            fa_digits(core.qty_int(qty1)),
            fmt(price) if price not in ("", None) else "",
            fa_digits(str(qty2 or "")),
            fmt(cost) if cost not in ("", None) and str(cost) not in ("0", "0.0") else "",
        ]
        for c, v in enumerate(vals):
            item = QTableWidgetItem(v)
            item.setTextAlignment(Qt.AlignCenter)
            if c in (4, 5):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.items_table.setItem(r, c, item)
        self.items_table.blockSignals(False)
        if str(qty1 or "").strip() and typ_s:
            self._recalc_row_meter_cost(r, force_meter=True)

    def _remove_item_row(self):
        r = self.items_table.currentRow()
        if r >= 0:
            self.items_table.removeRow(r)
            self._update_items_summary()

    def _load_items_into_table(self):
        self.items_table.setRowCount(0)
        rows = []
        if isinstance(self._inquiry_data, dict):
            rows = self._inquiry_data.get("rows") or []
        if not isinstance(rows, list):
            rows = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            self._add_item_row(
                r.get("code") or "",
                r.get("type") or r.get("typ") or "",
                core.qty_int(r.get("qty1")) or "",
                r.get("price") or "",
                r.get("qty2") or "",
                r.get("cost") or "",
            )
        if self.items_table.rowCount() == 0:
            self._add_item_row()
        self._update_items_summary()

    def _cell_text(self, row, col):
        it = self.items_table.item(row, col)
        return it.text().strip() if it else ""

    def _set_cell(self, row, col, text, editable=True):
        self.items_table.blockSignals(True)
        it = QTableWidgetItem(str(text or ""))
        it.setTextAlignment(Qt.AlignCenter)
        if not editable:
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
        self.items_table.setItem(row, col, it)
        self.items_table.blockSignals(False)

    def _type_for_row(self, row):
        typ = self._cell_text(row, 1).strip()
        code = en_digits(self._cell_text(row, 0)).strip()
        mapped = resolve_product(code, typ)
        if mapped:
            return mapped
        old_rows = (self._inquiry_data or {}).get("rows") or []
        if row < len(old_rows) and isinstance(old_rows[row], dict):
            t = old_rows[row].get("type") or old_rows[row].get("typ") or ""
            if t:
                return resolve_product("", t) or t
        return "Isofam Luxury"

    def _recalc_row_meter_cost(self, row, force_meter=False):
        if getattr(self, "_excel_locked", False):
            return
        if row < 0 or row >= self.items_table.rowCount():
            return
        typ = self._type_for_row(row)
        if typ not in PRODUCT_FACTORS:
            return  # ردیف واردشده از اکسل با نوع ناشناخته: مقدار ذخیره‌شده دست نمی‌خورد
        factor = PRODUCT_FACTORS[typ]
        try:
            cartons = float(en_digits(self._cell_text(row, 2)).replace(",", "") or 0)
        except Exception:
            cartons = 0.0
        meters = 0.0
        if force_meter or cartons > 0:
            meters = round(cartons * factor, 4) if cartons else 0.0
            mtxt = fa_digits(("%g" % meters) if meters else "")
            self._set_cell(row, 4, mtxt, editable=False)
        else:
            try:
                meters = float(en_digits(self._cell_text(row, 4)).replace(",", "") or 0)
            except Exception:
                meters = 0.0
        try:
            price = amount(en_digits(self._cell_text(row, 3)))
        except Exception:
            price = 0
        cost = int(round(price * meters)) if price and meters else 0
        self._set_cell(row, 5, fmt(cost) if cost else "", editable=False)
        self._update_items_summary()

    def _update_items_summary(self):
        """جمع تعداد ردیف، متراژ و مبلغ اقلام برای کنترل"""
        if not hasattr(self, "items_sum_lbl"):
            return
        rows = self._collect_item_rows()
        n = len(rows)
        meters = 0.0
        total = 0
        for r in rows:
            try:
                meters += float(en_digits(str(r.get("qty2") or "0")).replace(",", "") or 0)
            except Exception:
                _swallow()
            total += amount(r.get("cost") or 0)
        if meters:
            mtxt = ("%g" % round(meters, 4))
        else:
            mtxt = "0"
        self.items_sum_lbl.setText(
            "جمع اقلام: %s ردیف   |   متراژ: %s   |   مبلغ: %s ریال"
            % (fa_digits(n), fa_digits(mtxt), fmt(total))
        )

    def _on_item_cell_changed(self, row, col):
        if col == 0:
            code = en_digits(self._cell_text(row, 0)).strip()
            mapped = resolve_product(code, self._cell_text(row, 1))
            if mapped:
                self._set_cell(row, 1, mapped, editable=True)
            self._recalc_row_meter_cost(row, force_meter=True)
        elif col in (1, 2):
            self._recalc_row_meter_cost(row, force_meter=True)
        elif col == 3:
            raw = en_digits(self._cell_text(row, 3)).replace(",", "").strip()
            if raw:
                try:
                    self._set_cell(row, 3, fmt(amount(raw)), editable=True)
                except Exception:
                    _swallow()
            self._recalc_row_meter_cost(row, force_meter=False)

    def _advance_items_cell(self):
        row = self.items_table.currentRow()
        col = self.items_table.currentColumn()
        if row < 0:
            row = 0
        if col < 0:
            col = 0
        order = [0, 1, 2, 3]
        try:
            idx = order.index(col)
            next_idx = idx + 1
        except ValueError:
            next_idx = 0
        if next_idx < len(order):
            nc = order[next_idx]
            nr = row
        else:
            nr = row + 1
            nc = 0
            if nr >= self.items_table.rowCount():
                self._add_item_row()
        self.items_table.setCurrentCell(nr, nc)
        it = self.items_table.item(nr, nc)
        if it is None:
            self._set_cell(nr, nc, "", editable=True)
            it = self.items_table.item(nr, nc)
        if it is not None:
            self.items_table.editItem(it)

    def _collect_item_rows(self):
        out = []
        for r in range(self.items_table.rowCount()):
            code = en_digits(self._cell_text(r, 0)).strip()
            typ = self._cell_text(r, 1).strip()
            qty1 = en_digits(self._cell_text(r, 2)).strip()
            price_s = en_digits(self._cell_text(r, 3)).replace(",", "").strip()
            qty2 = en_digits(self._cell_text(r, 4)).strip()
            cost_s = en_digits(self._cell_text(r, 5)).replace(",", "").strip()
            if not code and not qty1 and not price_s and not qty2:
                continue
            if not typ:
                typ = CODE_TO_PRODUCT.get(code, "") or self._type_for_row(r)
            try:
                price = amount(price_s) if price_s else 0
            except Exception:
                price = 0
            try:
                meters = float(qty2.replace(",", "") or 0)
            except Exception:
                meters = 0.0
            try:
                cost = amount(cost_s) if cost_s else int(round(price * meters))
            except Exception:
                cost = int(round(price * meters)) if price and meters else 0
            _old = (self._inquiry_data or {}).get("rows") or []
            _nm = ""
            if r < len(_old) and isinstance(_old[r], dict):
                _nm = _old[r].get("name") or ""
            out.append({
                "code": code,
                "name": _nm,
                "type": typ,
                "qty1": core.qty_int(qty1),
                "qty2": qty2,
                "price": str(int(price)) if price else price_s,
                "cost": str(int(cost)) if cost else "0",
            })
        return out

    def _recalc_total_from_items(self):
        total = 0
        for r in range(self.items_table.rowCount()):
            self._recalc_row_meter_cost(r, force_meter=True)
        for r in self._collect_item_rows():
            total += amount(r.get("cost") or 0)
        if total > 0:
            self.total.setText(fmt(total))
        self._update_items_summary()

    def _build_inquiry_json(self):
        if getattr(self, "_excel_locked", False):
            return json.dumps(self._inquiry_data, ensure_ascii=False)  # ردیف‌ها و مبلغ کل همان اکسل می‌مانند
        rows = self._collect_item_rows()
        data = dict(self._inquiry_data) if isinstance(self._inquiry_data, dict) else {}
        data["rows"] = rows
        if not data.get("tab"):
            data["tab"] = "parquet"
        try:
            data["total"] = self.total.raw_value()
        except Exception:
            _swallow()
        if not rows and not self._inquiry_data:
            return ""
        return json.dumps(data, ensure_ascii=False)

    def load_customers(self):
        self.customer.clear()
        c = db()
        rows = c.execute(
            "SELECT DISTINCT customer FROM invoices WHERE TRIM(customer) != ''"
        ).fetchall()
        c.close()
        customers = sorted({r[0].strip() for r in rows if r[0] and r[0].strip()}, key=lambda x: x)
        self.customer.addItems(customers)
        completer = QCompleter(customers, self.customer)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setMaxVisibleItems(12)
        self.customer.setCompleter(completer)
        self.customer.lineEdit().setCompleter(completer)

    def refresh_dt(self):
        try:
            d, t = now_jalali()
            self.date.setText(fa_digits(d))
            self.time.setText(fa_digits(t))
        except Exception:
            _swallow()

    def format_invoice(self, text):
        digits = clean_number(text)
        shown = fa_digits(digits)
        if shown != text:
            self.invoice.blockSignals(True)
            self.invoice.setText(shown)
            self.invoice.setCursorPosition(len(shown))
            self.invoice.blockSignals(False)

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب عکس حواله", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if path:
            self.image_path = str(Path(path).resolve())
            self.image_label.setText("انتخاب شد: " + Path(path).name)

    def values(self):
        paid_raw = self.paid.raw_value()
        total_raw = self.total.raw_value()
        if not str(paid_raw).strip():
            paid_raw = total_raw
        inq_json = self._build_inquiry_json()
        return (
            self.customer.currentText().strip(),
            en_digits(self.invoice.text().strip()),
            en_digits(self.date.text()),
            en_digits(self.time.text()),
            total_raw,
            self.image_path,
            paid_raw,
            inq_json,
        )


def _to_float(v):
    try:
        t = en_digits(str(v if v is not None else "")).replace(",", "").replace("\u066c", "").replace("\u060c", "").strip()
        return float(t) if t else 0.0
    except Exception:
        return 0.0


def _fmt_qty(v):
    f = round(float(v or 0), 2)
    return fa_digits(("%d" % f) if f == int(f) else ("%.2f" % f).rstrip("0").rstrip("."))


def invoice_items_html(data, head=""):
    """جدول مرتب اقلام یک حواله (HTML سازگار با Qt): ردیف | نام کالا | تعداد | میزان | قیمت واحد | مبلغ.
    کد کالا نمایش داده نمی‌شود؛ سایز فقط برای «ام دی اف خام»؛ گرید کنار نام (ستون جدا نیست).
    واحدها: پارکت = بسته / متر مربع ، ام دی اف و خام = پالت / ورق."""
    if not isinstance(data, dict):
        return None
    rows = data.get("rows") or []
    if not rows:
        return None
    try:
        from statement_core import sample_last
    except Exception:
        from salesmate.statement_core import sample_last
    rows = sample_last(rows)          # سمپل همیشه آخر
    tab = data.get("tab") or "parquet"
    if tab == "analysis_import":
        tab = "mdf" if core.is_mdf_invoice(data) else "parquet"
    u1, u2 = ("بسته", "متر مربع") if tab in ("parquet", "") else ("پالت", "ورق")
    th = "style='color:#FFFFFF;font-weight:700;'"
    out = ["<div dir='rtl'>"]
    if head:
        out.append(f"<div align='right' style='font-weight:700;color:#0F172A;'>{head}</div>")
    out.append("<table dir='rtl' width='100%' cellspacing='0' cellpadding='5'>")
    def _tr(cells, bg):
        # Qt جدول را راست‌به‌چپ نمی‌چیند؛ ترتیب ستون‌ها را خودمان برعکس می‌کنیم تا «ردیف» سمت راست و «مبلغ» سمت چپ باشد
        return f"<tr bgcolor='{bg}'>" + "".join(reversed(cells)) + "</tr>"

    out.append(_tr([
        f"<td align='center' {th}>ردیف</td>", f"<td align='right' {th}>نام کالا</td>",
        f"<td align='center' {th}>{u1}</td>", f"<td align='center' {th}>{u2}</td>",
        f"<td align='center' {th}>قیمت واحد</td>", f"<td align='center' {th}>مبلغ</td>"], "#1E3A5F"))
    t1 = t2 = tc = 0.0
    for i, r in enumerate(rows, 1):
        r = r or {}
        name = str(r.get("name") or r.get("type") or "—")
        grade = str(r.get("grade") or "").strip()
        size = str(r.get("size") or "").strip()
        if tab == "raw" and size:
            name += " — " + size
        if grade:
            name += f" <span style='color:#64748B;font-size:11px;'>({grade})</span>"
        q1 = core.qty_int(r.get("qty1"))
        q2 = _to_float(r.get("qty2"))
        cost = _to_float(r.get("cost"))
        price = _to_float(r.get("price"))
        try:
            t1 += float(q1 or 0)
        except Exception:
            pass
        t2 += q2
        tc += cost
        bg = "#F1F5F9" if i % 2 == 0 else "#FFFFFF"
        out.append(_tr([
            f"<td align='center'>{fa_digits(i)}</td>",
            f"<td align='right'><b>{name}</b></td>",
            f"<td align='center'>{fa_digits(q1) if q1 not in (None, '') else '—'}</td>",
            f"<td align='center'>{_fmt_qty(q2) if q2 else '—'}</td>",
            f"<td align='center' style='color:#64748B;'>{fmt(price) if price else '—'}</td>",
            f"<td align='center'><b>{fmt(cost) if cost else '—'}</b></td>"], bg))
    out.append(_tr([
        "<td></td>", "<td align='right'><b>جمع</b></td>",
        f"<td align='center'><b>{_fmt_qty(t1)}</b></td>", f"<td align='center'><b>{_fmt_qty(t2)}</b></td>",
        "<td></td>", f"<td align='center'><b>{fmt(tc) if tc else '—'}</b></td>"], "#E0F2FE"))
    out.append("</table></div>")
    return "".join(out)


class SoftTip(QFrame):
    """Tooltip سفارشی سفید با متن مشکی — بدون استایل Native ویندوز"""
    _instance = None

    def __init__(self):
        super().__init__(None, Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(
            "QFrame{background:#FFFFFF;color:#0F172A;border:1px solid #CBD5E1;"
            "border-radius:18px;}"
            "QLabel{background:transparent;color:#0F172A;border:none;"
            "font-size:12px;font-weight:600;}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        self.lbl = QLabel("")
        self.lbl.setWordWrap(True)
        self.lbl.setStyleSheet("color:#0F172A;background:transparent;border:none;font-size:12px;font-weight:600;")
        lay.addWidget(self.lbl)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = SoftTip()
        return cls._instance

    @classmethod
    def show_text(cls, text, anchor_widget=None):
        tip = cls.instance()
        tip._hide_timer.stop()
        tip.lbl.setMinimumWidth(640 if str(text or "").lstrip().startswith("<") else 0)
        tip.lbl.setText(text or "")
        tip.lbl.adjustSize()
        tip.adjustSize()
        if anchor_widget is not None:
            br = anchor_widget.mapToGlobal(anchor_widget.rect().bottomRight())
            tr = anchor_widget.mapToGlobal(anchor_widget.rect().topRight())
            x, y = br.x() - tip.width() - 8, br.y() + 6
            alt_y = tr.y() - tip.height() - 6        # بالای کارت (وقتی پایین جا نیست)
        else:
            x, y = QCursor.pos().x() + 12, QCursor.pos().y() + 16
            alt_y = QCursor.pos().y() - tip.height() - 12
        try:
            scr = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
            g = scr.availableGeometry()
            if y + tip.height() > g.bottom() - 4:
                y = alt_y if alt_y >= g.top() + 4 else max(g.top() + 4, g.bottom() - tip.height() - 4)
            x = max(g.left() + 4, min(x, g.right() - tip.width() - 4))
        except Exception:
            _swallow()
        tip.move(x, y)
        tip.show()
        tip.raise_()

    @classmethod
    def hide_tip(cls):
        tip = cls.instance()
        tip._hide_timer.stop()
        tip.hide()


class DebtStatementDialog(QDialog):
    """پیش‌نمایش «اعلام بدهکاری/طلبکاری» مشتری هم‌شکل استعلام؛ خروجی عکس (PNG) و PDF."""
    W = 760

    def __init__(self, parent, customer):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("صورت‌حساب — " + customer)
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(820, 700)
        try:
            from statement_core import compute_statement, statement_html
        except Exception:
            from salesmate.statement_core import compute_statement, statement_html
        c = db()
        try:
            rows = c.execute(
                "SELECT invoice_no, date, total, paid_amount, inquiry_data FROM invoices WHERE customer=?", (customer,)
            ).fetchall()
            adj = c.execute("SELECT adjustment FROM customer_balance_adj WHERE customer=?", (customer,)).fetchone()
        finally:
            c.close()
        st = compute_statement(rows, adj[0] if adj else 0, getattr(core, "is_mdf_invoice", None))
        try:
            d, _t = now_jalali()
        except Exception:
            d = ""
        words = ""
        try:
            words = core.number_to_persian_words(abs(st["balance"]))
        except Exception:
            _swallow()
        self.html = statement_html(customer, d, st, words, qt=True)
        lay = QVBoxLayout(self)
        from PySide6.QtWidgets import QTextBrowser
        tb = QTextBrowser()
        tb.setHtml(self.html)
        tb.setStyleSheet("QTextBrowser{background:#fff;border:1px solid #E2E8F0;}")
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        b_img = QPushButton("ذخیره عکس (PNG)")
        b_pdf = QPushButton("ذخیره PDF")
        b_close = QPushButton("بستن")
        for b, col in ((b_img, "#1565C0"), (b_pdf, "#059669"), (b_close, "#64748B")):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton{background:%s;color:#fff;border:none;border-radius:10px;padding:9px 18px;font-weight:700;}" % col)
        b_img.clicked.connect(self.save_png)
        b_pdf.clicked.connect(self.save_pdf)
        b_close.clicked.connect(self.accept)
        row.addWidget(b_img)
        row.addWidget(b_pdf)
        row.addStretch(1)
        row.addWidget(b_close)
        lay.addLayout(row)

    def _doc(self, width):
        doc = QTextDocument()
        f = QFont("Tahoma", 10)
        doc.setDefaultFont(f)
        doc.setDocumentMargin(14)
        doc.setTextWidth(width)
        doc.setHtml(self.html)
        doc.setTextWidth(width)
        return doc

    def _fname(self, ext):
        safe = re.sub(r"[\\/:*?\"<>|]+", "_", self.customer).strip() or "customer"
        return "بدهکاری_%s.%s" % (safe, ext)

    def save_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره عکس", self._fname("png"), "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            doc = self._doc(self.W)
            sz = doc.size()
            k = 2
            img = QImage(int(self.W * k), int(sz.height() * k) + 4, QImage.Format_ARGB32)
            img.fill(QColor("#FFFFFF"))
            p = QPainter(img)
            p.scale(k, k)
            doc.drawContents(p)
            p.end()
            if img.save(path, "PNG"):
                QMessageBox.information(self, "ذخیره", "عکس ذخیره شد:\n" + path)
            else:
                QMessageBox.warning(self, "ذخیره", "ذخیره عکس انجام نشد.")
        except Exception as ex:
            QMessageBox.warning(self, "ذخیره", "ذخیره عکس انجام نشد:\n" + str(ex))

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره PDF", self._fname("pdf"), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        try:
            from PySide6.QtGui import QPdfWriter
            from PySide6.QtCore import QSizeF
            w = QPdfWriter(path)
            w.setPageSize(QPageSize(QPageSize.A4))
            w.setPageMargins(QMarginsF(10, 10, 10, 10), QPageLayout.Millimeter)
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Tahoma", 10))
            doc.setDocumentMargin(0)
            doc.setHtml(self.html)
            res = w.resolution()
            page_px = w.pageLayout().paintRectPixels(res)
            doc.setPageSize(QSizeF(page_px.width(), page_px.height()))
            doc.print_(w)
            QMessageBox.information(self, "ذخیره", "PDF ذخیره شد:\n" + path)
        except Exception as ex:
            QMessageBox.warning(self, "ذخیره", "ذخیره PDF انجام نشد:\n" + str(ex))


class HomePage(QWidget):
    def _home_is_owner(self):
        """فروشگاه فقط برای مالک؛ همکارها کارت‌های فروشگاه را در خانه نمی‌بینند."""
        try:
            return bool(self.win.is_owner_account())
        except Exception:
            return True

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        host = QWidget()
        l = QVBoxLayout(host)
        l.setContentsMargins(28, 22, 28, 28)
        l.setSpacing(16)

        h = QLabel("خانه")
        h.setObjectName("pageTitle")
        l.addWidget(h)
        s = QLabel("فروش هفته و ماه · فروشگاه · مقایسه با دوره قبل" if self._home_is_owner() else "فروش هفته و ماه · مقایسه با دوره قبل")
        s.setObjectName("hint")
        l.addWidget(s)

        self.kpi1 = QHBoxLayout()
        self.kpi1.setSpacing(12)
        l.addLayout(self.kpi1)

        self.kpi2 = QHBoxLayout()
        self.kpi2.setSpacing(12)
        l.addLayout(self.kpi2)

        two = QHBoxLayout()
        two.setSpacing(14)

        left = QFrame()
        left.setStyleSheet(
            "QFrame#dashCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        left.setObjectName("dashCard")
        left.setMinimumHeight(420)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(14, 12, 14, 12)
        ll.setSpacing(6)
        lt = QLabel("آخرین حواله‌ها")
        lt.setStyleSheet("font-size:14px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        ll.addWidget(lt)
        self.recent_host = QVBoxLayout()
        self.recent_host.setSpacing(6)
        ll.addLayout(self.recent_host)
        mt2 = QLabel("آخرین حواله‌های ام دی اف")
        mt2.setStyleSheet("font-size:14px;font-weight:700;color:#0F172A;border:none;background:transparent;margin-top:6px;")
        ll.addWidget(mt2)
        self.mdf_host = QVBoxLayout()
        self.mdf_host.setSpacing(6)
        ll.addLayout(self.mdf_host)
        ll.addStretch()
        two.addWidget(left, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        top_card = QFrame()
        top_card.setObjectName("dashCard")
        top_card.setStyleSheet(
            "QFrame#dashCard{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;}"
        )
        top_card.setFixedHeight(314)   # دقیقاً ۴ ردیف کامل
        tc = QVBoxLayout(top_card)
        tc.setContentsMargins(14, 12, 14, 12)
        tc.setSpacing(6)
        rt = QLabel("برترین مشتریان ماه")
        rt.setStyleSheet("font-size:14px;font-weight:700;color:#0F172A;border:none;background:transparent;")
        tc.addWidget(rt)
        self.top_scroll = QScrollArea()
        self.top_scroll.setWidgetResizable(True)
        self.top_scroll.setFrameShape(QFrame.NoFrame)
        self.top_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.top_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        top_inner = QWidget()
        self.top_host = QVBoxLayout(top_inner)
        self.top_host.setContentsMargins(0, 0, 0, 0)
        self.top_host.setSpacing(6)
        self.top_scroll.setWidget(top_inner)
        tc.addWidget(self.top_scroll, 1)
        right_col.addWidget(top_card)

        debt_card = QFrame()
        debt_card.setObjectName("dashCard")
        debt_card.setStyleSheet(
            "QFrame#dashCard{background:#FFFFFF;border:1px solid #FECACA;border-radius:16px;"
            "border-top:3px solid #DC2626;}"
        )
        debt_card.setFixedHeight(250)   # دقیقاً ۳ ردیف کامل
        dc = QVBoxLayout(debt_card)
        dc.setContentsMargins(14, 12, 14, 12)
        dc.setSpacing(6)
        dt = QLabel("بدهکارها")
        dt.setStyleSheet("font-size:14px;font-weight:700;color:#B91C1C;border:none;background:transparent;")
        dc.addWidget(dt)
        self.debt_scroll = QScrollArea()
        self.debt_scroll.setWidgetResizable(True)
        self.debt_scroll.setFrameShape(QFrame.NoFrame)
        self.debt_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.debt_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        debt_inner = QWidget()
        self.debt_host = QVBoxLayout(debt_inner)
        self.debt_host.setContentsMargins(0, 0, 0, 0)
        self.debt_host.setSpacing(6)
        self.debt_scroll.setWidget(debt_inner)
        dc.addWidget(self.debt_scroll, 1)
        right_col.addWidget(debt_card, 1)

        cred_card = QFrame()
        cred_card.setObjectName("dashCard")
        cred_card.setStyleSheet(
            "QFrame#dashCard{background:#FFFFFF;border:1px solid #A7F3D0;border-radius:16px;"
            "border-top:3px solid #059669;}"
        )
        cred_card.setFixedHeight(250)   # دقیقاً ۳ ردیف کامل
        cc = QVBoxLayout(cred_card)
        cc.setContentsMargins(14, 12, 14, 12)
        cc.setSpacing(6)
        ct = QLabel("طلبکارها")
        ct.setStyleSheet("font-size:14px;font-weight:700;color:#047857;border:none;background:transparent;")
        cc.addWidget(ct)
        self.cred_scroll = QScrollArea()
        self.cred_scroll.setWidgetResizable(True)
        self.cred_scroll.setFrameShape(QFrame.NoFrame)
        self.cred_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.cred_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        cred_inner = QWidget()
        self.cred_host = QVBoxLayout(cred_inner)
        self.cred_host.setContentsMargins(0, 0, 0, 0)
        self.cred_host.setSpacing(6)
        self.cred_scroll.setWidget(cred_inner)
        cc.addWidget(self.cred_scroll, 1)
        right_col.addWidget(cred_card, 1)

        two.addLayout(right_col, 1)

        l.addLayout(two)
        l.addStretch()
        scroll.setWidget(host)
        outer.addWidget(scroll)

    @staticmethod
    def _is_mdf_invoice(inquiry_data):
        return core.is_mdf_invoice(inquiry_data)

    def _recent_row(self, customer, inv_no, date, total, inquiry_data):
        color = get_customer_color(customer) or "#E2E8F0"
        row = QFrame()
        row.setFixedHeight(58)
        row.setStyleSheet(f"QFrame{{background:{color};border:1px solid #E2E8F0;border-radius:28px;}}")
        tip = self._invoice_items_tooltip(
            inquiry_data, f"{customer} · ش {fa_digits(inv_no)} · {fa_digits(date)} · مبلغ کل {fmt(total)}")
        row.setProperty("tipText", tip)
        row.setMouseTracking(True)
        row.enterEvent = (lambda e, w=row, t=tip: SoftTip.show_text(t, w))
        row.leaveEvent = (lambda e: SoftTip.hide_tip())
        hl = QHBoxLayout(row)
        hl.setContentsMargins(14, 6, 14, 6)
        name = QLabel(f"<b>{customer}</b>")
        name.setStyleSheet("border:none;background:transparent;color:#0F172A;")
        meta = QLabel(f"ش {fa_digits(inv_no)} · {fa_digits(date)}")
        meta.setStyleSheet("color:#1E293B;font-size:11px;border:none;background:transparent;")
        mid = QVBoxLayout()
        mid.setSpacing(2)
        mid.addWidget(name)
        mid.addWidget(meta)
        hl.addLayout(mid, 1)
        amt = QLabel(fmt(total))
        amt.setStyleSheet("font-weight:800;color:#0F172A;border:none;background:transparent;font-size:13px;")
        hl.addWidget(amt)
        return row

    def _open_statement(self, name):
        try:
            DebtStatementDialog(self, name).exec()
        except Exception as ex:
            QMessageBox.warning(self, "صورت‌حساب", "نمایش انجام نشد:\n" + str(ex))

    def _pill_row(self, name, meta, amount_text, bg, border="#E2E8F0", amt_color="#0F172A", tip=None, on_click=None):
        """ردیف کارتیِ هم‌شکل «آخرین حواله‌ها»: گوشه‌ی گرد، نام درشت، توضیح ریز و مبلغ."""
        row = QFrame()
        row.setFixedHeight(58)
        row.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {border};border-radius:28px;}}")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(14, 6, 14, 6)
        nm = QLabel(f"<b>{name}</b>")
        nm.setStyleSheet("border:none;background:transparent;color:#0F172A;")
        mid = QVBoxLayout()
        mid.setSpacing(2)
        mid.addWidget(nm)
        if meta:
            mt = QLabel(meta)
            mt.setStyleSheet("color:#1E293B;font-size:11px;border:none;background:transparent;")
            mid.addWidget(mt)
        hl.addLayout(mid, 1)
        am = QLabel(amount_text)
        am.setStyleSheet(f"font-weight:800;color:{amt_color};border:none;background:transparent;font-size:13px;")
        hl.addWidget(am)
        if on_click:
            row.setCursor(Qt.PointingHandCursor)
            row.mousePressEvent = lambda e, cb=on_click: cb() if e.button() == Qt.LeftButton else None
        if tip:
            row.setMouseTracking(True)
            row.enterEvent = (lambda e, w=row, t=tip: SoftTip.show_text(t, w))
            row.leaveEvent = (lambda e: SoftTip.hide_tip())
        return row

    def _kpi_card(self, title, value, accent="#1565C0", sub="", compare="", on_click=None, big=False):
        f = QFrame()
        f.setStyleSheet(
            f"QFrame{{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:16px;"
            f"border-top:4px solid {accent};}}"
        )
        if on_click:
            f.setCursor(Qt.PointingHandCursor)
            f.mousePressEvent = lambda e, cb=on_click: cb() if e.button() == Qt.LeftButton else None
        x = QVBoxLayout(f)
        x.setContentsMargins(14, 12, 14, 12)
        x.setSpacing(4)
        a = QLabel(title)
        a.setStyleSheet(
            "color:#64748B;font-size:%dpx;font-weight:600;border:none;background:transparent;"
            % (14 if big else 12)
        )
        b = QLabel(value)
        b.setWordWrap(True)
        b.setStyleSheet(
            "color:#0F172A;font-size:%dpx;font-weight:800;border:none;background:transparent;"
            % (22 if big else 16)
        )
        x.addWidget(a)
        x.addWidget(b)
        if sub:
            c = QLabel(sub)
            c.setWordWrap(True)
            c.setStyleSheet(
                "color:#64748B;font-size:%dpx;border:none;background:transparent;font-weight:600;"
                % (13 if big else 11)
            )
            x.addWidget(c)
        if compare:
            d = QLabel(compare)
            d.setWordWrap(True)
            col = "#94A3B8"
            if "▲" in compare or "جدید" in compare:
                col = "#059669"
            elif "▼" in compare:
                col = "#DC2626"
            d.setStyleSheet(
                "color:%s;font-size:11px;font-weight:700;border:none;background:transparent;" % col
            )
            x.addWidget(d)
        return f

    def _cmp_text(self, cur, prev, label="دوره قبل"):
        try:
            cur = float(cur or 0)
            prev = float(prev or 0)
        except Exception:
            return "نسبت به %s: —" % label
        if prev <= 0:
            if cur > 0:
                return "نسبت به %s: جدید ▲" % label
            return "نسبت به %s: —" % label
        pct = (cur - prev) / prev * 100.0
        arrow = "▲" if pct >= 0 else "▼"
        sign = "+" if pct >= 0 else "−"
        val = abs(pct)
        ptxt = fa_digits("%.0f" % val) if val >= 10 else fa_digits("%.1f" % val)
        return "نسبت به %s: %s%s٪ %s" % (label, sign, ptxt, arrow)

    def _open_saved_inquiries(self):
        try:
            lst = json.loads(INQUIRY_PATH.read_text(encoding="utf-8")) if INQUIRY_PATH.exists() else []
        except Exception:
            lst = []
        if not lst:
            QMessageBox.information(self, "ذخیره‌شده‌ها", "موردی ذخیره نشده است.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("استعلام‌های ذخیره‌شده")
        dlg.resize(520, 420)
        dlg.setLayoutDirection(Qt.RightToLeft)
        vl = QVBoxLayout(dlg)
        listw = QListWidget()
        for item in lst:
            tab_fa = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}.get(item.get("tab"), "")
            listw.addItem(
                f"{item.get('buyer', '—')} | {tab_fa} | {fa_digits(item.get('date', ''))} | {fmt(item.get('total', 0))}"
            )
        vl.addWidget(listw)
        btns = QHBoxLayout()
        load_b = QPushButton("بارگذاری")
        load_b.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;padding:10px 14px;font-weight:700;}"
        )
        del_b = QPushButton("حذف")
        del_b.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#991B1B;border:none;border-radius:10px;padding:10px 14px;font-weight:700;}"
        )
        close_b = QPushButton("بستن")
        close_b.setStyleSheet(
            "QPushButton{background:#E2E8F0;color:#0F172A;border:none;border-radius:10px;padding:10px 14px;font-weight:700;}"
        )
        btns.addWidget(load_b)
        btns.addWidget(del_b)
        btns.addWidget(close_b)
        vl.addLayout(btns)

        def do_load():
            i = listw.currentRow()
            if i < 0:
                QMessageBox.information(dlg, "بارگذاری", "یک مورد را انتخاب کنید.")
                return
            try:
                self.win.inquiry_page.load_inquiry(lst[i])
                self.win.inquiry()
            except Exception as ex:
                QMessageBox.warning(dlg, "بارگذاری", str(ex))
                return
            dlg.accept()

        def do_del():
            i = listw.currentRow()
            if i < 0:
                return
            if QMessageBox.question(dlg, "حذف", "حذف شود؟\nاز ابر و بقیه دستگاه‌ها هم حذف می‌شود.") != QMessageBox.Yes:
                return
            removed = lst.pop(i)
            try:
                try:
                    delete_inquiry_from_cloud(removed)
                except Exception:
                    _swallow()
                INQUIRY_PATH.write_text(json.dumps(lst, ensure_ascii=False, indent=2), encoding="utf-8")
                schedule_supabase_sync()
            except Exception as ex:
                QMessageBox.critical(dlg, "خطا", str(ex))
                return
            listw.takeItem(i)
            self.refresh()

        load_b.clicked.connect(do_load)
        del_b.clicked.connect(do_del)
        close_b.clicked.connect(dlg.accept)
        listw.itemDoubleClicked.connect(lambda *_: do_load())
        dlg.exec()

    def _invoice_items_tooltip(self, inquiry_data, head=""):
        if not inquiry_data or not str(inquiry_data).strip():
            return "جزئیات کالا ثبت نشده"
        try:
            data = json.loads(inquiry_data) if isinstance(inquiry_data, str) else inquiry_data
        except Exception:
            return "جزئیات کالا ثبت نشده"
        return invoice_items_html(data, head) or "جزئیات کالا ثبت نشده"

    def _clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def refresh(self):
        self._clear_layout(self.kpi1)
        self._clear_layout(self.kpi2)
        self._clear_layout(self.recent_host)
        self._clear_layout(self.mdf_host)
        self._clear_layout(self.top_host)
        if hasattr(self, "debt_host"):
            self._clear_layout(self.debt_host)
        if hasattr(self, "cred_host"):
            self._clear_layout(self.cred_host)

        c = db()
        today, _ = now_jalali()
        gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
        j_y, j_m, j_d = gregorian_to_jalali(gy, gm, gd)
        month_prefix = f"{j_y:04d}/{j_m:02d}/"

        year_prefix = f"{j_y:04d}/"
        month_prefix = f"{j_y:04d}/{j_m:02d}"
        # ماه قبل
        if j_m <= 1:
            prev_month_prefix = f"{j_y-1:04d}/12"
        else:
            prev_month_prefix = f"{j_y:04d}/{j_m-1:02d}"

        def _week_key(date_s):
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

        def _prev_week_key(wk):
            y, w = wk
            if y == 0:
                return (0, 0)
            if w > 0:
                return (y, w - 1)
            return (y - 1, 51)

        def _inv_meters(inquiry_data):
            m = 0.0
            try:
                data = inquiry_data
                if isinstance(data, str):
                    data = json.loads(data or "{}") if data else {}
                if not isinstance(data, dict):
                    return 0.0
                for r in (data.get("rows") or []):
                    try:
                        m += float(en_digits(str(r.get("qty2") or "0")).replace(",", "") or 0)
                    except Exception:
                        _swallow()
            except Exception:
                return 0.0
            return m

        def _fmt_m(m):
            if not m:
                return fa_digits("0")
            s = ("%g" % round(float(m), 4))
            return fa_digits(s)

        cur_week = _week_key(today)
        prev_week = _prev_week_key(cur_week)

        inv_rows = c.execute(
            "SELECT date, total, inquiry_data FROM invoices"
        ).fetchall()

        inv_week_sum = inv_week_m = 0
        inv_pweek_sum = inv_pweek_m = 0
        inv_month_sum = inv_month_m = 0
        inv_pmonth_sum = inv_pmonth_m = 0
        inv_year_sum = inv_year_m = 0

        for date_s, tot, inq in inv_rows:
            val = amount(tot)
            meters = _inv_meters(inq)
            ds = en_digits(str(date_s or ""))
            wk = _week_key(ds)
            if wk == cur_week and cur_week != (0, 0):
                inv_week_sum += val
                inv_week_m += meters
            if wk == prev_week and prev_week != (0, 0):
                inv_pweek_sum += val
                inv_pweek_m += meters
            if ds.startswith(month_prefix):
                inv_month_sum += val
                inv_month_m += meters
            if ds.startswith(prev_month_prefix):
                inv_pmonth_sum += val
                inv_pmonth_m += meters
            if ds.startswith(year_prefix):
                inv_year_sum += val
                inv_year_m += meters

        # فروشگاه
        store_rows = []
        try:
            store_rows = c.execute(
                "SELECT date, total, items_json FROM store_sales"
            ).fetchall()
        except Exception:
            store_rows = []

        def _store_meter(items_json):
            try:
                items = json.loads(items_json or "[]")
            except Exception:
                items = []
            m = 0.0
            for it in items or []:
                try:
                    m += float(en_digits(str(it.get("qty2") or "0")).replace(",", "") or 0)
                except Exception:
                    _swallow()
            return m

        store_week_sum = store_week_m = 0.0
        store_pweek_sum = store_pweek_m = 0.0
        store_month_sum = store_month_m = 0.0
        store_pmonth_sum = store_pmonth_m = 0.0
        store_year_sum = store_year_m = 0.0
        for date_s, tot, items_json in store_rows:
            val = amount(tot)
            meters = _store_meter(items_json)
            ds = en_digits(str(date_s or ""))
            wk = _week_key(ds)
            if wk == cur_week and cur_week != (0, 0):
                store_week_sum += val
                store_week_m += meters
            if wk == prev_week and prev_week != (0, 0):
                store_pweek_sum += val
                store_pweek_m += meters
            if ds.startswith(month_prefix):
                store_month_sum += val
                store_month_m += meters
            if ds.startswith(prev_month_prefix):
                store_pmonth_sum += val
                store_pmonth_m += meters
            if ds.startswith(year_prefix):
                store_year_sum += val
                store_year_m += meters

        saved_inq_count = 0
        try:
            if INQUIRY_PATH.exists():
                _inq = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
                if isinstance(_inq, list):
                    saved_inq_count = len(_inq)
        except Exception:
            saved_inq_count = 0

        recent_all = c.execute(
            "SELECT customer, invoice_no, date, time, total, inquiry_data FROM invoices"
        ).fetchall()
        def _home_inv_key(r):
            no = en_digits(str(r[1] or "")).strip()
            nums = re.findall(r"\d+", no)
            if nums:
                try:
                    return (0, int(nums[-1]), no)
                except Exception:
                    _swallow()
            return (1, 0, no)
        recent = sorted(recent_all, key=_home_inv_key, reverse=True)[:7]

        top = c.execute(
            "SELECT customer, COALESCE(SUM(CAST(total AS INTEGER)),0) AS s FROM invoices "
            "WHERE date LIKE ? GROUP BY customer ORDER BY s DESC LIMIT 5",
            (month_prefix + "%",),
        ).fetchall()
        c.close()

        self.kpi1.addWidget(
            self._kpi_card(
                "فروش هفته",
                fmt(int(inv_week_sum)) + " ریال",
                "#1565C0",
                "متراژ: " + _fmt_m(inv_week_m) + " متر",
                self._cmp_text(inv_week_sum, inv_pweek_sum, "هفته قبل"),
            )
        )
        self.kpi1.addWidget(
            self._kpi_card(
                "فروش ماه",
                fmt(int(inv_month_sum)) + " ریال",
                "#059669",
                "متراژ: " + _fmt_m(inv_month_m) + " متر",
                self._cmp_text(inv_month_sum, inv_pmonth_sum, "ماه قبل"),
            )
        )
        if self._home_is_owner():
          self.kpi1.addWidget(
            self._kpi_card(
                "فروشگاه — هفته",
                fmt(int(store_week_sum)) + " ریال",
                "#0EA5E9",
                "متراژ: " + _fmt_m(store_week_m) + " متر",
                self._cmp_text(store_week_sum, store_pweek_sum, "هفته قبل"),
            )
        )
          self.kpi1.addWidget(
            self._kpi_card(
                "فروشگاه — ماه",
                fmt(int(store_month_sum)) + " ریال",
                "#8B5CF6",
                "متراژ: " + _fmt_m(store_month_m) + " متر",
                self._cmp_text(store_month_sum, store_pmonth_sum, "ماه قبل"),
            )
        )

        self.kpi2.addWidget(
            self._kpi_card(
                "استعلام‌های ذخیره‌شده",
                fa_digits(saved_inq_count) + " مورد",
                "#F59E0B",
                "کلیک برای مشاهده",
                on_click=self._open_saved_inquiries,
            ),
            1,
        )
        self.kpi2.addWidget(
            self._kpi_card(
                "فروش سال " + fa_digits(j_y),
                fmt(int(inv_year_sum)) + " ریال",
                "#6366F1",
                "متراژ سال: " + _fmt_m(inv_year_m) + " متر",
                big=True,
            ),
            2,
        )
        if self._home_is_owner():
          self.kpi2.addWidget(
            self._kpi_card(
                "فروش کل فروشگاه " + fa_digits(j_y),
                fmt(int(store_year_sum)) + " ریال",
                "#0D9488",
                "متراژ: " + _fmt_m(store_year_m) + " متر",
                big=True,
            ),
            2,
        )

        if not recent:
            empty = QLabel("هنوز حواله‌ای ثبت نشده")
            empty.setStyleSheet("color:#94A3B8;padding:12px;")
            self.recent_host.addWidget(empty)
        else:
            for customer, inv_no, date, time_s, total, inquiry_data in recent:
                self.recent_host.addWidget(self._recent_row(customer, inv_no, date, total, inquiry_data))

        # آخرین حواله‌های ام دی اف (زیر «آخرین حواله‌ها» تا انتهای باکس)
        try:
            mdf_list = [r for r in sorted(recent_all, key=_home_inv_key, reverse=True)
                        if self._is_mdf_invoice(r[5])][:5]
        except Exception:
            mdf_list = []
        if mdf_list:
            for customer, inv_no, date, time_s, total, inquiry_data in mdf_list:
                self.mdf_host.addWidget(self._recent_row(customer, inv_no, date, total, inquiry_data))
        else:
            e = QLabel("حواله‌ی ام دی اف ثبت نشده")
            e.setStyleSheet("color:#94A3B8;padding:8px;border:none;background:transparent;")
            self.mdf_host.addWidget(e)

        max_top = amount(top[0][1]) if top else 1
        if not top:
            empty = QLabel("فروشی در این ماه نیست")
            empty.setStyleSheet("color:#94A3B8;padding:12px;")
            self.top_host.addWidget(empty)
        else:
            colors = ["#1565C0", "#0EA5E9", "#14B8A6", "#8B5CF6", "#F59E0B"]
            for i, (customer, s_) in enumerate(top):
                val = amount(s_)
                pct = int(100 * val / max_top) if max_top else 0
                bg = get_customer_color(customer) or "#E2E8F0"
                self.top_host.addWidget(self._pill_row(
                    customer, f"رتبه {fa_digits(i + 1)} · {fa_digits(pct)}٪ از برترین",
                    fmt(val), bg, amt_color="#0F172A"))

        # لیست بدهکار / طلبکار
        try:
            c2 = db()
            names = c2.execute(
                "SELECT DISTINCT customer FROM invoices WHERE TRIM(IFNULL(customer,'')) != ''"
            ).fetchall()
            c2.close()
        except Exception:
            names = []
        debtors = []
        creditors = []
        for (name,) in names:
            if not name or not str(name).strip():
                continue
            try:
                bal = customer_balance(str(name).strip())
            except Exception:
                bal = 0
            if bal > 0:
                debtors.append((str(name).strip(), bal))
            elif bal < 0:
                creditors.append((str(name).strip(), bal))
        debtors.sort(key=lambda x: x[1], reverse=True)
        creditors.sort(key=lambda x: x[1])

        if not debtors:
            e = QLabel("بدهکاری نیست")
            e.setStyleSheet("color:#94A3B8;padding:8px;border:none;background:transparent;")
            self.debt_host.addWidget(e)
        else:
            for name, bal in debtors:
                self.debt_host.addWidget(self._pill_row(
                    name, "بدهکار", fmt(bal), "#FEF2F2", "#FECACA", "#0F172A",
                    on_click=lambda n=name: self._open_statement(n)))

        if not creditors:
            e = QLabel("طلبکاری نیست")
            e.setStyleSheet("color:#94A3B8;padding:8px;border:none;background:transparent;")
            self.cred_host.addWidget(e)
        else:
            for name, bal in creditors:
                self.cred_host.addWidget(self._pill_row(
                    name, "طلبکار", fmt(abs(bal)), "#ECFDF5", "#A7F3D0", "#0F172A",
                    on_click=lambda n=name: self._open_statement(n)))

        # فاصله‌ی ردیف‌ها دقیقاً ۶ بماند (بدون پخش شدن فضای اضافه بین ردیف‌ها)
        for _h in (self.top_host, self.debt_host, self.cred_host):
            _h.addStretch(1)


_SRC_BADGES = {
    "excel": ("اکسل", "#0F766E", "#CCFBF1"),
    "inquiry": ("استعلام", "#1D4ED8", "#DBEAFE"),
    "manual": ("دستی", "#475569", "#E2E8F0"),
}


def _invoice_source(inquiry_data):
    s = str(inquiry_data or "")
    if not s.strip():
        return "manual"
    if '"tab": "analysis_import"' in s or '"tab":"analysis_import"' in s:
        return "excel"
    return "inquiry"


class InvoicesPage(QWidget):
    PAGE_SIZE = 60
    MONTH_FA = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)
        self._shown = self.PAGE_SIZE
        self._rows = []
        self._mode = "all"       # all | debt | paid

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()          # کل صفحه اسکرول می‌شود تا کارت‌های بیشتری دیده شود
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)
        l = QVBoxLayout(content)
        l.setContentsMargins(24, 14, 24, 18)
        l.setSpacing(8)

        title = QLabel("حواله‌ها  📄")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignRight)
        l.addWidget(title)

        # خلاصه (فشرده، یک ردیف)
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(8)
        l.addLayout(self.kpi_row)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        add = QPushButton("＋ حواله جدید")
        add.setObjectName("primaryButton")
        add.setFixedSize(140, 44)
        add.clicked.connect(win.new_invoice)

        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجوی مشتری یا شماره حواله...")
        self.search.setFixedHeight(44)
        self._inv_timer = QTimer(self)
        self._inv_timer.setSingleShot(True)
        self._inv_timer.setInterval(280)
        self._inv_timer.timeout.connect(self._reset_and_refresh)
        self.search.textChanged.connect(lambda: self._inv_timer.start())

        self.date_from = QLineEdit()
        self.date_from.setPlaceholderText("از تاریخ")
        self.date_from.setFixedHeight(44)
        self.date_from.setFixedWidth(120)
        self.date_from.textChanged.connect(lambda: self._inv_timer.start())

        self.date_to = QLineEdit()
        self.date_to.setPlaceholderText("تا تاریخ")
        self.date_to.setFixedHeight(44)
        self.date_to.setFixedWidth(120)
        self.date_to.textChanged.connect(lambda: self._inv_timer.start())

        excel_btn = QPushButton("⬇ اکسل")
        excel_btn.setProperty("class", "secondaryButton")
        excel_btn.setFixedSize(90, 44)
        excel_btn.clicked.connect(self.export_excel)

        add.hide()   # حواله‌ها از اکسل فروش می‌آیند؛ دکمه‌ی «حواله جدید» برداشته شد
        bar.addWidget(self.date_from)
        bar.addWidget(self.date_to)
        bar.addWidget(self.search, 2)
        bar.addWidget(excel_btn)
        l.addLayout(bar)

        # فیلتر سریع
        chips = QHBoxLayout()
        chips.setSpacing(6)
        self._chip_btns = {}
        for key, text in (("all", "همه"), ("debt", "بدهکار"), ("paid", "تسویه‌شده")):
            bt = QPushButton(text)
            bt.setCheckable(True)
            bt.setCursor(Qt.PointingHandCursor)
            bt.setFixedHeight(32)
            bt.setStyleSheet(
                "QPushButton{background:#fff;border:1px solid #CBD5E1;border-radius:16px;padding:0 16px;"
                "color:#334155;font-weight:700;}"
                "QPushButton:checked{background:#1565C0;color:#fff;border:1px solid #1565C0;}"
            )
            bt.clicked.connect(lambda _=False, k=key: self._set_mode(k))
            chips.addWidget(bt)
            self._chip_btns[key] = bt
        self._chip_btns["all"].setChecked(True)
        chips.addStretch(1)
        self.count_label = QLabel("")
        self.count_label.setStyleSheet("color:#667085;font-size:12px;padding:4px 8px;")
        chips.addWidget(self.count_label)
        l.addLayout(chips)

        # لیست کارت‌ها
        self.list_host = QWidget()
        self.list_host.setStyleSheet("background:transparent;")
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 2, 0, 2)
        self.list_layout.setSpacing(6)
        l.addWidget(self.list_host)
        l.addStretch(1)

        self.refresh()

    def _set_mode(self, mode):
        self._mode = mode
        for k, bt in self._chip_btns.items():
            bt.setChecked(k == mode)
        self._reset_and_refresh()

    def _reset_and_refresh(self):
        self._shown = self.PAGE_SIZE
        self.refresh(keep_scroll=False)

    def _filter_query(self):
        q=self.search.text().strip()
        d_from=en_digits(self.date_from.text().strip())
        d_to=en_digits(self.date_to.text().strip())
        sql="""SELECT id,customer,invoice_no,date,time,total,image_path,inquiry_data,paid_amount
               FROM invoices WHERE 1=1"""
        args=[]
        if q:
            q_en=en_digits(q)
            sql+=" AND (customer LIKE ? OR invoice_no LIKE ?)"
            args += [f"%{q}%",f"%{q_en}%"]
        if d_from:
            sql+=" AND date>=?"
            args.append(d_from)
        if d_to:
            sql+=" AND date<=?"
            args.append(d_to)
        sql+=" ORDER BY date DESC, time DESC, id DESC"
        return sql, args

    def export_excel(self):
        # دیالوگ فیلتر تاریخ مخصوص خروجی اکسل
        dlg = QDialog(self)
        dlg.setWindowTitle("خروجی اکسل")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(360)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        hint = QLabel("بازه تاریخ خروجی را مشخص کنید (خالی = همه)")
        hint.setObjectName("hint")
        lay.addWidget(hint)
        form = QFormLayout()
        df = QLineEdit(self.date_from.text())
        df.setPlaceholderText("از تاریخ  ")
        dt = QLineEdit(self.date_to.text())
        dt.setPlaceholderText("تا تاریخ  ")
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
        q = self.search.text().strip()

        sql = """SELECT id,customer,invoice_no,date,time,total,inquiry_data
                 FROM invoices WHERE 1=1"""
        args = []
        if q:
            q_en = en_digits(q)
            sql += " AND (customer LIKE ? OR invoice_no LIKE ?)"
            args += [f"%{q}%", f"%{q_en}%"]
        if d_from:
            sql += " AND date>=?"
            args.append(d_from)
        if d_to:
            sql += " AND date<=?"
            args.append(d_to)
        sql += " ORDER BY id DESC"

        c = db()
        rows = c.execute(sql, args).fetchall()
        c.close()
        def _inv_no_key_ex(r):
            no = en_digits(str(r[2] or "")).strip()
            nums = re.findall(r"\d+", no)
            if nums:
                try:
                    return (0, int(nums[-1]), no)
                except Exception:
                    _swallow()
            return (1, 0, no)
        rows = sorted(rows, key=_inv_no_key_ex, reverse=True)
        if not rows:
            QMessageBox.information(self, "اکسل", "با این فیلتر حواله‌ای پیدا نشد.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره اکسل", "SalesMate_Invoices.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill, numbers
            from openpyxl.utils import get_column_letter

            wb = Workbook()
            ws = wb.active
            ws.title = "حواله‌ها"
            ws.sheet_view.rightToLeft = True

            headers = ["شناسه", "مشتری", "شماره حواله", "تاریخ", "متراژ", "مبلغ کل (ریال)"]
            header_fill = PatternFill("solid", fgColor="1565C0")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            thin = Border(
                left=Side(style="thin", color="CBD5E1"),
                right=Side(style="thin", color="CBD5E1"),
                top=Side(style="thin", color="CBD5E1"),
                bottom=Side(style="thin", color="CBD5E1"),
            )
            center = Alignment(horizontal="center", vertical="center", wrap_text=True)
            MONTHS = ["", "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
                      "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند"]

            for col, h in enumerate(headers, 1):
                cell = ws.cell(1, col, h)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center
                cell.border = thin

            groups, grand = group_invoices_by_month(rows, amount)
            alt = PatternFill("solid", fgColor="F1F5F9")
            month_fill = PatternFill("solid", fgColor="DBEAFE")
            grand_fill = PatternFill("solid", fgColor="BBF7D0")
            r = 2
            for g in groups:
                if g["year"]:
                    title = "%s %s" % (MONTHS[g["month"]] if 1 <= g["month"] <= 12 else g["month"], g["year"])
                else:
                    title = "بدون تاریخ"
                for k, (inv_id, customer, inv_no, date, meters, amt) in enumerate(g["rows"]):
                    vals = [int(inv_id) if str(inv_id).isdigit() else inv_id, customer, inv_no, date,
                            round(meters, 4) if meters else 0, amt]
                    for col, val in enumerate(vals, 1):
                        cell = ws.cell(r, col, val)
                        cell.alignment = center
                        cell.border = thin
                        if k % 2 == 0:
                            cell.fill = alt
                        if col == 6:
                            cell.number_format = "#,##0"
                        if col == 5:
                            cell.number_format = "#,##0.##"
                    ws.row_dimensions[r].height = 20
                    r += 1
                # جمع همین ماه
                ws.cell(r, 1, "جمع " + title + "  (%d حواله)" % len(g["rows"]))
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
                ws.cell(r, 5, round(g["meters"], 4))
                ws.cell(r, 6, g["amount"])
                for col in range(1, 7):
                    cell = ws.cell(r, col)
                    cell.fill = month_fill
                    cell.font = Font(bold=True, color="1E3A8A")
                    cell.alignment = center
                    cell.border = thin
                ws.cell(r, 5).number_format = "#,##0.##"
                ws.cell(r, 6).number_format = "#,##0"
                ws.row_dimensions[r].height = 24
                r += 2  # یک ردیف فاصله بین ماه‌ها

            # جمع کل
            ws.cell(r, 1, "جمع کل  (%d حواله)" % grand["count"])
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
            ws.cell(r, 5, round(grand["meters"], 4))
            ws.cell(r, 6, grand["amount"])
            for col in range(1, 7):
                cell = ws.cell(r, col)
                cell.fill = grand_fill
                cell.font = Font(bold=True, color="14532D", size=12)
                cell.alignment = center
                cell.border = thin
            ws.cell(r, 5).number_format = "#,##0.##"
            ws.cell(r, 6).number_format = "#,##0"
            ws.row_dimensions[r].height = 26

            for i, w in enumerate([10, 28, 14, 14, 14, 20], 1):
                ws.column_dimensions[get_column_letter(i)].width = w
            ws.row_dimensions[1].height = 22
            ws.freeze_panes = "A2"

            wb.save(path)
            QMessageBox.information(
                self, "SalesMate",
                f"{fa_digits(len(rows))} حواله در فایل اکسل ذخیره شد.\nهر ماه جدا شده و جمع مبلغ و متراژ هر ماه و جمع کل در انتها نوشته شده است."
            )
        except ImportError:
            QMessageBox.critical(self, "خطا", "کتابخانه openpyxl نصب نیست. در CMD: pip install openpyxl")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"ذخیره اکسل انجام نشد:\n{ex}")

    # ───────── کارت‌ها ─────────
    @staticmethod
    def _clear(layout):
        while layout.count():
            it = layout.takeAt(0)
            w = it.widget()
            if w is not None:
                w.deleteLater()
            elif it.layout():
                InvoicesPage._clear(it.layout())

    def _kpi(self, title, value, color):
        card = QFrame()
        card.setStyleSheet(
            "QFrame{background:#fff;border:1px solid #E2E8F0;border-radius:10px;border-right:4px solid %s;}"
            "QLabel{background:transparent;border:none;}" % color)
        v = QHBoxLayout(card)
        v.setContentsMargins(12, 5, 12, 5)
        v.setSpacing(8)
        t = QLabel(title)
        t.setStyleSheet("color:#64748B;font-size:11px;font-weight:700;")
        val = QLabel(value)
        val.setStyleSheet("color:%s;font-size:15px;font-weight:900;" % color)
        v.addWidget(t)
        v.addStretch(1)
        v.addWidget(val)
        return card

    def _month_header(self, title, count, total):
        f = QFrame()
        f.setStyleSheet("QFrame{background:#E8EEF5;border:none;border-radius:10px;}QLabel{background:transparent;}")
        h = QHBoxLayout(f)
        h.setContentsMargins(14, 6, 14, 6)
        a = QLabel(title)
        a.setStyleSheet("font-weight:800;color:#0F172A;font-size:13px;")
        b = QLabel("%s حواله  ·  جمع: %s ریال" % (fa_digits(count), fmt(total)))
        b.setStyleSheet("color:#475569;font-size:12px;font-weight:600;")
        h.addWidget(a)
        h.addStretch(1)
        h.addWidget(b)
        return f

    def _icon_btn(self, text, tip, enabled, slot, danger=False):
        """دکمه‌ی متنی کوچک و رنگی (بدون tooltip)."""
        bt = QPushButton(text)
        bt.setFixedHeight(30)
        bt.setMinimumWidth(78)
        bt.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        fg, bg, hv = ("#B91C1C", "#FEF2F2", "#FEE2E2") if danger else ("#1D4ED8", "#EFF6FF", "#DBEAFE")
        bt.setStyleSheet(
            "QPushButton{background:%s;color:%s;border:1px solid transparent;border-radius:8px;font-size:12px;font-weight:700;padding:0 14px;}"
            "QPushButton:hover{background:%s;}"
            "QPushButton:disabled{background:#F8FAFC;color:#CBD5E1;}" % (bg, fg, hv))
        bt.setEnabled(enabled)
        if enabled:
            bt.clicked.connect(slot)
        return bt

    def _make_card(self, rowdata):
        invoice_id, customer, invoice_no, date, time_, total, image_path, inquiry_data = rowdata[:8]
        paid_raw = rowdata[8] if len(rowdata) > 8 else ""
        t_amt = amount(total)
        p_amt = t_amt if (paid_raw is None or str(paid_raw).strip() == "") else amount(paid_raw)
        remain = t_amt - p_amt
        color = get_customer_color(customer)

        card = QFrame()
        card.setObjectName("invCard")
        card.setStyleSheet(
            "QFrame#invCard{background:#FFFFFF;border:1px solid #E2E8F0;border-right:6px solid %s;border-radius:14px;}"
            "QFrame#invCard:hover{background:#F8FBFF;border-color:#BFDBFE;border-right:6px solid %s;}"
            "QLabel{background:transparent;border:none;}"
            "QToolTip{background:#FFFFFF;color:#0F172A;border:1px solid #CBD5E1;}" % (color, color))
        h = QHBoxLayout(card)
        h.setContentsMargins(14, 6, 10, 6)
        h.setSpacing(12)

        # نام + شماره/تاریخ + نشان منبع
        left = QVBoxLayout()
        left.setSpacing(2)
        name = QLabel(str(customer))
        name.setStyleSheet("font-size:14px;font-weight:800;color:#0F172A;")
        left.addWidget(name)
        sub = QHBoxLayout()
        sub.setSpacing(8)
        no = QLabel("شماره %s" % fa_digits(invoice_no))
        no.setStyleSheet("color:#475569;font-size:12px;font-weight:700;")
        dt = QLabel("📅 %s" % fa_digits(date))
        dt.setStyleSheet("color:#64748B;font-size:12px;")
        sid = QLabel("#%s" % fa_digits(invoice_id))
        sid.setStyleSheet("color:#94A3B8;font-size:11px;")
        txt, fg, bg = _SRC_BADGES[_invoice_source(inquiry_data)]
        badge = QLabel(txt)
        badge.setStyleSheet("background:%s;color:%s;border-radius:8px;padding:1px 8px;font-size:11px;font-weight:700;" % (bg, fg))
        for w in (no, dt, badge, sid):
            sub.addWidget(w)
        sub.addStretch(1)
        left.addLayout(sub)
        h.addLayout(left, 1)

        # مبلغ + مانده
        mid = QVBoxLayout()
        mid.setSpacing(2)
        try:
            from statement_core import invoice_chip
        except Exception:
            from salesmate.statement_core import invoice_chip
        net = getattr(self, "_cust_net", {}).get(str(customer or ""), 0)
        rt, kind, dtxt, dkind = invoice_chip(t_amt, p_amt, net)
        rf, rb = {"debt": ("#B91C1C", "#FEE2E2"), "cred": ("#1D4ED8", "#DBEAFE"),
                  "ok": ("#047857", "#D1FAE5")}[kind]
        _FS = "font-size:13px;font-weight:800;"
        # ستون‌های ثابت: مبلغ | اختلاف (سمت راست مبلغ)؛ زیرش نشان وضعیت، همه هم‌اندازه
        row_w = QWidget()
        row_w.setLayoutDirection(Qt.LeftToRight)       # ترتیب بصری صریح: چپ→راست = مبلغ، اختلاف
        arow = QHBoxLayout(row_w)
        arow.setContentsMargins(0, 0, 0, 0)
        arow.setSpacing(6)
        amt = QLabel(fa_digits("%s ریال" % fmt(total)))
        amt.setStyleSheet(_FS + "color:#0F172A;")
        amt.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        amt.setFixedWidth(190)
        amt.setLayoutDirection(Qt.RightToLeft)
        dl = QLabel(fa_digits(dtxt) if dtxt else "")
        dl.setStyleSheet(_FS + "color:%s;" % ("#DC2626" if dkind == "neg" else "#059669"))
        dl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        dl.setFixedWidth(120)
        arow.addWidget(amt)
        arow.addWidget(dl)
        mid.addWidget(row_w)
        rem = QLabel(fa_digits(rt))
        rem.setAlignment(Qt.AlignCenter)
        rem.setFixedSize(190, 22)
        rem.setStyleSheet("background:%s;color:%s;border-radius:10px;font-size:12px;font-weight:800;" % (rb, rf))
        mid.addWidget(rem, 0, Qt.AlignLeft)
        h.addLayout(mid, 0)

        # عملیات
        has_image = bool(image_path and Path(image_path).exists())
        has_inq = bool(inquiry_data and str(inquiry_data).strip())
        acts = QHBoxLayout()
        acts.setSpacing(6)
        acts.addWidget(self._icon_btn("شرح خرید", "", has_inq, lambda _=False, i=invoice_id: self.win.open_invoice_inquiry(i)))
        acts.addWidget(self._icon_btn("ویرایش", "", True, lambda _=False, i=invoice_id: self.win.edit_invoice(i)))
        acts.addWidget(self._icon_btn("حذف", "", True, lambda _=False, i=invoice_id: self.win.delete_invoice(i), danger=True))
        h.addLayout(acts, 0)
        return card

    def _remain_of(self, r):
        t = amount(r[5])
        p = t if (len(r) <= 8 or r[8] is None or str(r[8]).strip() == "") else amount(r[8])
        return t - p

    def refresh(self, keep_scroll=True):
        bar = self.scroll.verticalScrollBar()
        _pos = bar.value() if keep_scroll else 0
        c = db()
        sql, args = self._filter_query()
        rows = c.execute(sql, args).fetchall()
        # مانده‌ی کل هر مشتری (همه‌ی حواله‌ها + تعدیل دستی) برای نشان «تسویه»
        net = {}
        try:
            for cu, tt, pp in c.execute("SELECT customer, total, paid_amount FROM invoices").fetchall():
                t_ = amount(tt)
                p_ = t_ if (pp is None or str(pp).strip() == "") else amount(pp)
                net[str(cu or "")] = net.get(str(cu or ""), 0) + (t_ - p_)
            for cu, aj in c.execute("SELECT customer, adjustment FROM customer_balance_adj").fetchall():
                net[str(cu or "")] = net.get(str(cu or ""), 0) + amount(aj)
        except Exception:
            _swallow()
        self._cust_net = net
        c.close()

        def _inv_no_key(r):
            no = en_digits(str(r[2] or "")).strip()
            nums = re.findall(r"\d+", no)
            if nums:
                try:
                    return (0, int(nums[-1]), no)
                except Exception:
                    _swallow()
            return (1, 0, no)
        rows = sorted(rows, key=_inv_no_key, reverse=True)
        if self._mode == "debt":
            rows = [r for r in rows if self._remain_of(r) > 0]
        elif self._mode == "paid":
            rows = [r for r in rows if self._remain_of(r) <= 0]
        self._rows = rows

        # خلاصه
        self._clear(self.kpi_row)
        tot = sum(amount(r[5]) for r in rows)
        debt = sum(max(self._remain_of(r), 0) for r in rows)
        self.kpi_row.addWidget(self._kpi("تعداد حواله", fa_digits(len(rows)), "#1565C0"))
        self.kpi_row.addWidget(self._kpi("جمع مبلغ (ریال)", fmt(tot), "#059669"))
        self.kpi_row.addWidget(self._kpi("جمع مانده بدهکاری (ریال)", fmt(debt), "#DC2626"))

        # ماه‌ها (از کل نتیجه)
        month_tot = {}
        for r in rows:
            parts = str(r[3] or "").split("/")
            ym = (parts[0], parts[1]) if len(parts) >= 2 else ("", "")
            e = month_tot.setdefault(ym, [0, 0])
            e[0] += 1
            e[1] += amount(r[5])

        self.setUpdatesEnabled(False)
        try:
            self._clear(self.list_layout)
            shown = rows[: self._shown]
            prev_ym = None
            for r in shown:
                parts = str(r[3] or "").split("/")
                ym = (parts[0], parts[1]) if len(parts) >= 2 else ("", "")
                if ym != prev_ym and ym[0]:
                    try:
                        y, m = int(ym[0]), int(ym[1])
                        title = "📅  %s %s" % (self.MONTH_FA[m] if 1 <= m <= 12 else ym[1], fa_digits(y))
                    except Exception:
                        title = "📅  " + fa_digits(str(r[3])[:7])
                    cnt, sm = month_tot.get(ym, [0, 0])
                    self.list_layout.addWidget(self._month_header(title, cnt, sm))
                    prev_ym = ym
                self.list_layout.addWidget(self._make_card(r))
            if not rows:
                e = QLabel("هیچ حواله‌ای ثبت نشده است" if self._mode == "all" and not self.search.text().strip()
                           else "حواله‌ای با این فیلتر پیدا نشد")
                e.setAlignment(Qt.AlignCenter)
                e.setStyleSheet("color:#94A3B8;padding:40px;font-size:14px;")
                self.list_layout.addWidget(e)
            elif len(rows) > len(shown):
                more = QPushButton("نمایش %s حواله‌ی بعدی  (%s از %s)" % (
                    fa_digits(min(self.PAGE_SIZE, len(rows) - len(shown))), fa_digits(len(shown)), fa_digits(len(rows))))
                more.setCursor(Qt.PointingHandCursor)
                more.setFixedHeight(42)
                more.setStyleSheet("QPushButton{background:#fff;border:1px dashed #94A3B8;border-radius:12px;color:#1565C0;font-weight:800;}"
                                   "QPushButton:hover{background:#F0F7FF;}")
                more.clicked.connect(self._more)
                self.list_layout.addWidget(more)
            self.list_layout.addStretch(1)
        finally:
            self.setUpdatesEnabled(True)
        n = len(rows)
        self.count_label.setText("نمایش %s از %s حواله" % (fa_digits(min(self._shown, n)), fa_digits(n)) if n else "")
        # بعد از ساخته‌شدن کارت‌ها، جای اسکرول همان‌جا می‌ماند (ویرایش / حذف / نمایش بعدی)
        QTimer.singleShot(0, lambda: bar.setValue(_pos))
        QTimer.singleShot(60, lambda: bar.setValue(_pos))

    def _more(self):
        self._shown += self.PAGE_SIZE
        self.refresh(keep_scroll=True)


class CustomersPage(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)
        self.year_checks = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(12)

        # عنوان
        title = QLabel("مشتریان")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        # ردیف سرچ + سال‌ها (فشرده)
        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو در مشتریان...")
        self.search.setFixedHeight(36)
        self.search.setMinimumWidth(220)
        self.search.setMaximumWidth(300)
        self.search.setStyleSheet(
            "QLineEdit{border:1px solid #E2E8F0;border-radius:10px;padding:4px 12px;background:#fff;}"
        )
        self._search_timer = QTimer(self); self._search_timer.setSingleShot(True); self._search_timer.setInterval(280)
        self._search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda: self._search_timer.start())
        top.addWidget(self.search, 0)
        try:
            try:
                import name_completer as _nc
            except Exception:
                from salesmate import name_completer as _nc
            self._name_comp = _nc.attach_to_line_edit(self.search, [])
        except Exception:
            self._name_comp = None
            _swallow()

        yl = QLabel("سال‌های قبل:")
        yl.setStyleSheet("color:#64748B;font-size:12px;")
        top.addWidget(yl, 0)

        self.year_checks_host = QWidget()
        self.year_checks_layout = QHBoxLayout(self.year_checks_host)
        self.year_checks_layout.setContentsMargins(0, 0, 0, 0)
        self.year_checks_layout.setSpacing(6)
        top.addWidget(self.year_checks_host, 0)
        top.addStretch(1)
        rename_btn = QPushButton("ویرایش نام چند حواله")
        rename_btn.setCursor(Qt.PointingHandCursor)
        rename_btn.setFixedHeight(36)
        rename_btn.setStyleSheet(
            "QPushButton{background:#0F172A;color:#fff;border:none;border-radius:10px;"
            "padding:6px 14px;font-weight:700;font-size:12px;}"
            "QPushButton:hover{background:#1E293B;}"
        )
        rename_btn.clicked.connect(self.bulk_rename_customer)
        top.addWidget(rename_btn, 0)
        layout.addLayout(top)

        # لیست کارت‌ها
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 4, 0, 4)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_host)
        layout.addWidget(self.scroll, 1)

        self._build_year_checks()
        self.refresh()

    def years(self):
        c = db()
        rows = c.execute(
            "SELECT DISTINCT substr(date,1,4) FROM invoices WHERE date IS NOT NULL AND length(date)>=4"
        ).fetchall()
        c.close()
        ys = []
        for r in rows:
            try:
                y = int(str(r[0]))
                if y >= 1403:
                    ys.append(y)
            except Exception:
                _swallow()
        try:
            cur = int(now_jalali()[0].split("/")[0])
        except Exception:
            cur = 1405
        hi = max([cur, 1405] + ys)
        return sorted(set(list(range(1403, hi + 1))))

    def current_year(self):
        try:
            return int(now_jalali()[0].split("/")[0])
        except Exception:
            ys = self.years()
            return ys[-1] if ys else 1405

    def _build_year_checks(self):
        while self.year_checks_layout.count():
            item = self.year_checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.year_checks.clear()
        cur = self.current_year()
        for y in self.years():
            if y == cur:
                continue
            cb = QCheckBox(fa_digits(y))
            cb.setChecked(False)
            cb.setStyleSheet(
                "QCheckBox{padding:4px 10px;border:1px solid #E2E8F0;border-radius:8px;"
                "background:#F8FAFC;font-size:12px;font-weight:600;}"
                "QCheckBox::indicator{width:12px;height:12px;}"
            )
            cb.stateChanged.connect(self.refresh)
            self.year_checks[y] = cb
            self.year_checks_layout.addWidget(cb)

    def selected_extra_years(self):
        return sorted([y for y, cb in self.year_checks.items() if cb.isChecked()])

    def bulk_rename_customer(self):
        """تغییر نام مشتری روی همه حواله‌ها و بدهی/طلب مرتبط."""
        c = db()
        names = [
            r[0] for r in c.execute(
                "SELECT DISTINCT customer FROM invoices WHERE TRIM(customer)!='' ORDER BY customer COLLATE NOCASE"
            ).fetchall()
        ]
        c.close()
        if not names:
            QMessageBox.information(self, "ویرایش نام", "مشتری ثبت‌شده‌ای نیست.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("ویرایش گروهی نام مشتری")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)
        hint = QLabel("نام قدیم را انتخاب و نام جدید را بنویسید. همه حواله‌ها و بدهی/طلب همان مشتری عوض می‌شوند.")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        old_cb = QComboBox()
        old_cb.setEditable(True)
        old_cb.addItems(names)
        old_cb.setInsertPolicy(QComboBox.NoInsert)
        new_ed = QLineEdit()
        new_ed.setPlaceholderText("نام جدید مشتری")
        form.addRow("نام فعلی:", old_cb)
        form.addRow("نام جدید:", new_ed)
        lay.addLayout(form)
        count_lbl = QLabel("")
        count_lbl.setStyleSheet("color:#1565C0;font-weight:600;")
        lay.addWidget(count_lbl)

        def update_count():
            name = old_cb.currentText().strip()
            if not name:
                count_lbl.setText("")
                return
            cc = db()
            n = cc.execute("SELECT COUNT(*) FROM invoices WHERE customer=?", (name,)).fetchone()[0]
            cc.close()
            count_lbl.setText(fa_digits(n) + " حواله با این نام پیدا شد")

        old_cb.currentTextChanged.connect(lambda *_: update_count())
        update_count()
        buttons = QDialogButtonBox()
        ok_btn = buttons.addButton("اعمال تغییر نام", QDialogButtonBox.AcceptRole)
        cancel_btn = buttons.addButton("انصراف", QDialogButtonBox.RejectRole)
        ok_btn.clicked.connect(dlg.accept)
        cancel_btn.clicked.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        old_name = old_cb.currentText().strip()
        new_name = new_ed.text().strip()
        if not old_name or not new_name:
            QMessageBox.warning(self, "ویرایش نام", "نام قدیم و جدید را وارد کنید.")
            return
        if old_name == new_name:
            QMessageBox.information(self, "ویرایش نام", "نام جدید با قدیم یکی است.")
            return
        if QMessageBox.question(
            self, "تأیید",
            "همه حواله‌های «" + old_name + "» به «" + new_name + "» تغییر کند؟"
        ) != QMessageBox.Yes:
            return
        try:
            c = db()
            n_inv = c.execute(
                "UPDATE invoices SET customer=? WHERE customer=?",
                (new_name, old_name),
            ).rowcount
            try:
                row = c.execute(
                    "SELECT adjustment, note, updated_at FROM customer_balance_adj WHERE customer=?",
                    (old_name,),
                ).fetchone()
                if row:
                    c.execute("DELETE FROM customer_balance_adj WHERE customer=?", (old_name,))
                    exist = c.execute(
                        "SELECT adjustment FROM customer_balance_adj WHERE customer=?",
                        (new_name,),
                    ).fetchone()
                    if exist:
                        c.execute(
                            "UPDATE customer_balance_adj SET adjustment=adjustment+?, note=?, updated_at=? WHERE customer=?",
                            (row[0], row[1] or "", row[2] or "", new_name),
                        )
                    else:
                        c.execute(
                            "INSERT INTO customer_balance_adj(customer,adjustment,note,updated_at) VALUES(?,?,?,?)",
                            (new_name, row[0], row[1] or "", row[2] or ""),
                        )
            except Exception:
                _swallow()
            try:
                c.execute("UPDATE store_sales SET customer=? WHERE customer=?", (new_name, old_name))
            except Exception:
                _swallow()
            c.commit()
            c.close()
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))
            return
        try:
            self.win.refresh_all()
        except Exception:
            self.refresh()
        try:
            schedule_supabase_sync()
        except Exception:
            _swallow()
        QMessageBox.information(
            self, "ویرایش نام",
            "نام «" + old_name + "» به «" + new_name + "» تغییر کرد. تعداد حواله: " + fa_digits(n_inv)
        )

    def _append_customer_cards(self, cur_y, show_years, page=40):
        """افزودن کارت‌های مرتب‌شده — ترتیب ثابت از بیشترین فروش."""
        data = getattr(self, "_cust_data_full", []) or []
        start = getattr(self, "_cust_visible", 0)
        end = min(len(data), start + page)
        # stretch را موقتاً بردار
        stretch = None
        if self.list_layout.count():
            last = self.list_layout.itemAt(self.list_layout.count() - 1)
            if last and last.spacerItem():
                stretch = self.list_layout.takeAt(self.list_layout.count() - 1)
        if hasattr(self, "_more_btn") and self._more_btn is not None:
            try:
                self.list_layout.removeWidget(self._more_btn)
                self._more_btn.deleteLater()
            except Exception:
                _swallow()
            self._more_btn = None
        for item in data[start:end]:
            card = self._build_card(
                item["name"], item["count_year"], item["total"], item["balance"],
                item["last"], item["annual"], cur_y, show_years,
            )
            self.list_layout.addWidget(card)
        self._cust_visible = end
        if end < len(data):
            self._more_btn = QPushButton(f"نمایش بیشتر ({fa_digits(end)} از {fa_digits(len(data))})")
            self._more_btn.setCursor(Qt.PointingHandCursor)
            self._more_btn.setStyleSheet(
                "QPushButton{background:#EFF6FF;color:#1565C0;border:1px solid #BFDBFE;"
                "border-radius:12px;padding:12px;font-weight:700;}"
            )
            self._more_btn.clicked.connect(lambda: self._append_customer_cards(cur_y, show_years, page=40))
            self.list_layout.addWidget(self._more_btn)
        self.list_layout.addStretch(1)

    def _clear_list(self):
        self._more_btn = None
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _status_chip(self, balance):
        chip = QLabel()
        chip.setAlignment(Qt.AlignCenter)
        if balance > 0:
            chip.setText("بدهکار  " + fmt(balance))
            chip.setStyleSheet(
                "QLabel{background:#FEE2E2;color:#991B1B;border-radius:12px;"
                "padding:6px 12px;font-weight:700;font-size:12px;}"
            )
        elif balance < 0:
            chip.setText("طلبکار  " + fmt(abs(balance)))
            chip.setStyleSheet(
                "QLabel{background:#DCFCE7;color:#14532D;border-radius:12px;"
                "padding:6px 12px;font-weight:700;font-size:12px;}"
            )
        else:
            chip.setText("تسویه")
            chip.setStyleSheet(
                "QLabel{background:#F1F5F9;color:#475569;border-radius:12px;"
                "padding:6px 12px;font-weight:700;font-size:12px;}"
            )
        return chip

    def _build_card(self, name, count_year, total_all, balance, last, annual, cur_y, show_years):
        accent = get_customer_color(name) or "#94A3B8"
        card = QFrame()
        card.setStyleSheet(
            f"QFrame#custCard{{background:#fff;border:1px solid #E2E8F0;"
            f"border-radius:16px;border-right:10px solid {accent};}}"
        )
        card.setObjectName("custCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)

        info = QVBoxLayout()
        info.setSpacing(6)
        name_lbl = QLabel(name)
        name_lbl.setStyleSheet(
            "font-size:16px;font-weight:700;color:#0F172A;border:none;background:transparent;"
        )
        info.addWidget(name_lbl)

        # تعداد و آخرین خرید — متمایز و خوانا
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)
        cnt = QLabel(f"تعداد حواله {fa_digits(cur_y)}:  {fa_digits(count_year)}")
        cnt.setStyleSheet(
            "color:#0F172A;font-size:13px;font-weight:600;border:none;background:transparent;"
        )
        sep = QLabel("|")
        sep.setStyleSheet("color:#CBD5E1;font-size:14px;font-weight:700;border:none;background:transparent;")
        last_lbl = QLabel(f"آخرین خرید:  {fa_digits(last or '—')}")
        last_lbl.setStyleSheet(
            "color:#0F172A;font-size:13px;font-weight:600;border:none;background:transparent;"
        )
        meta_row.addWidget(cnt)
        meta_row.addWidget(sep)
        meta_row.addWidget(last_lbl)
        meta_row.addStretch()
        info.addLayout(meta_row)

        year_bits = []
        for y in show_years:
            year_bits.append(f"{fa_digits(y)}: {fmt(annual.get(y, 0))}")
        if year_bits:
            ylbl = QLabel("  |  ".join(year_bits))
            ylbl.setStyleSheet("color:#1565C0;font-size:11px;border:none;background:transparent;")
            info.addWidget(ylbl)
        row.addLayout(info, 1)

        sales_box = QVBoxLayout()
        sales_box.setAlignment(Qt.AlignCenter)
        s_lbl = QLabel(fmt(annual.get(cur_y, 0)))
        s_lbl.setStyleSheet(
            "color:#059669;font-size:18px;font-weight:800;border:none;background:transparent;"
        )
        s_lbl.setAlignment(Qt.AlignCenter)
        s_unit = QLabel(f"فروش {fa_digits(cur_y)} (ریال)")
        s_unit.setStyleSheet("color:#94A3B8;font-size:11px;border:none;background:transparent;")
        s_unit.setAlignment(Qt.AlignCenter)
        sales_box.addWidget(s_lbl)
        sales_box.addWidget(s_unit)
        row.addLayout(sales_box)

        row.addWidget(self._status_chip(balance), 0, Qt.AlignVCenter)

        btns = QVBoxLayout()
        btns.setSpacing(6)
        buy_btn = QPushButton("خریدها")
        buy_btn.setCursor(Qt.PointingHandCursor)
        buy_btn.setStyleSheet(
            "QPushButton{background:#1565C0;color:white;border:none;border-radius:10px;"
            "padding:8px 16px;font-weight:700;min-width:110px;}"
            "QPushButton:hover{background:#0D47A1;}"
        )
        buy_btn.clicked.connect(lambda _, n=name: self.show_purchases(n))
        bal_btn = QPushButton("تنظیم مانده")
        bal_btn.setCursor(Qt.PointingHandCursor)
        bal_btn.setStyleSheet(
            "QPushButton{background:#fff;color:#1565C0;border:1.5px solid #BAE6FD;"
            "border-radius:10px;padding:8px 16px;font-weight:600;min-width:110px;}"
            "QPushButton:hover{background:#F0F9FF;}"
        )
        bal_btn.clicked.connect(lambda _, n=name: self.edit_balance(n))
        btns.addWidget(buy_btn)
        btns.addWidget(bal_btn)
        row.addLayout(btns)
        return card

    def _format_inquiry_rows(self, data):
        """جدول مرتب اقلام حواله برای «جزئیات کالا» در تب مشتریان."""
        return invoice_items_html(data)

    def show_purchases(self, customer: str):
        c = db()
        rows = c.execute(
            "SELECT invoice_no, date, time, total, inquiry_data FROM invoices "
            "WHERE customer=? ORDER BY date DESC, time DESC, id DESC",
            (customer,),
        ).fetchall()
        c.close()
        dlg = QDialog(self)
        dlg.setWindowTitle("خریدهای — " + customer)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(560, 520)
        lay = QVBoxLayout(dlg)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        vl = QVBoxLayout(host)
        vl.setSpacing(8)
        if not rows:
            vl.addWidget(QLabel("خریدی ثبت نشده"))
        for inv_no, date, time_s, total, inq in rows:
            box = QFrame()
            box.setStyleSheet(
                "QFrame{background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;}"
            )
            bl = QVBoxLayout(box)
            bl.setSpacing(6)
            data = None
            try:
                data = json.loads(inq) if inq else None
            except Exception:
                data = None
            detail_html = self._format_inquiry_rows(data) if data else None

            head_row = QHBoxLayout()
            head_row.setSpacing(8)
            head = QLabel(
                f"<b>ش {fa_digits(inv_no or '—')}</b>"
                f"&nbsp;&nbsp;{fa_digits(date or '')}"
                f"&nbsp;&nbsp;<span style='color:#1565C0;font-weight:700'>{fmt(total)}</span>"
            )
            head.setTextFormat(Qt.RichText)
            head_row.addWidget(head, 1)

            if detail_html:
                toggle = QPushButton("▾ جزئیات کالا")
                toggle.setCursor(Qt.PointingHandCursor)
                toggle.setFixedHeight(28)
                toggle.setStyleSheet(
                    "QPushButton{background:#E0F2FE;border:none;border-radius:8px;"
                    "padding:4px 10px;color:#0D47A1;font-weight:600;font-size:12px;}"
                    "QPushButton:hover{background:#BAE6FD;}"
                )
                head_row.addWidget(toggle, 0, Qt.AlignVCenter)
            bl.addLayout(head_row)

            if detail_html:
                detail = QLabel(detail_html)
                detail.setTextFormat(Qt.RichText)
                detail.setWordWrap(True)
                detail.setStyleSheet(
                    "QLabel{background:#FFFFFF;border:none;border-radius:8px;"
                    "padding:8px 4px;color:#334155;font-size:12px;line-height:1.7;}"
                )
                detail.setVisible(False)
                state = {"open": False}

                def _toggle(_=None, btn=toggle, det=detail, st=state):
                    st["open"] = not st["open"]
                    det.setVisible(st["open"])
                    btn.setText("▴ بستن" if st["open"] else "▾ جزئیات کالا")

                toggle.clicked.connect(_toggle)
                bl.addWidget(detail)
            vl.addWidget(box)
        vl.addStretch()
        scroll.setWidget(host)
        lay.addWidget(scroll)
        close_b = QPushButton("بستن")
        close_b.clicked.connect(dlg.accept)
        lay.addWidget(close_b)
        dlg.exec()

    def refresh(self):
        q = self.search.text().strip()
        existing = set(self.year_checks.keys())
        all_prev = set(y for y in self.years() if y != self.current_year())
        if existing != all_prev:
            self._build_year_checks()

        cur_y = self.current_year()
        show_years = [cur_y] + self.selected_extra_years()
        c = db()
        rows = c.execute(
            "SELECT customer, COUNT(*), SUM(CAST(total AS INTEGER)), MAX(date) "
            "FROM invoices WHERE customer LIKE ? GROUP BY customer",
            (f"%{q}%",),
        ).fetchall()

        # یک‌بار همه فاکتورها و تعدیل‌ها را بخوان (به‌جای N+1 کوئری — خیلی سریع‌تر)
        all_inv = c.execute(
            "SELECT customer, date, total, paid_amount FROM invoices WHERE customer LIKE ?",
            (f"%{q}%",),
        ).fetchall()
        adj_map = {}
        try:
            for r in c.execute("SELECT customer, adjustment FROM customer_balance_adj").fetchall():
                adj_map[str(r[0] or "")] = amount(r[1])
        except Exception:
            _swallow()
        c.close()
        try:
            if getattr(self, "_name_comp", None) and not q:
                self._name_comp["model"].setStringList(sorted({str(r[0]).strip() for r in rows if r[0] and str(r[0]).strip()}))
        except Exception:
            _swallow()

        from collections import defaultdict
        by_cust = defaultdict(lambda: {"count": 0, "total": 0, "last": "", "annual": defaultdict(int), "balance": 0, "count_year": 0})
        for cust, date, total, paid in all_inv:
            name = str(cust or "")
            d = by_cust[name]
            tt = amount(total)
            d["count"] += 1
            d["total"] += int(tt)
            ds = en_digits(str(date or "")).strip()
            if ds > en_digits(str(d["last"] or "")):
                d["last"] = ds
            y = ds[:4] if len(ds) >= 4 else ""
            if y.isdigit():
                d["annual"][y] += int(tt)
            if y == str(cur_y):
                d["count_year"] += 1
            pp = tt if (paid is None or str(paid).strip() == "") else amount(paid)
            d["balance"] += tt - pp
        data = []
        name_set = set(str(r[0] or "") for r in rows)
        for name in name_set:
            d = by_cust.get(name)
            if not d:
                continue
            annual = {y: int(d["annual"].get(str(y), 0)) for y in show_years}
            bal = d["balance"] + adj_map.get(name, 0)
            cur_sales = int(annual.get(cur_y, 0) or annual.get(str(cur_y), 0) or 0)
            shown_sales = sum(int(annual.get(y, 0) or annual.get(str(y), 0) or 0) for y in show_years)
            data.append({
                "name": name,
                "count_year": int(d["count_year"]),
                "total": int(d["total"]),
                "balance": bal,
                "last": d["last"],
                "annual": annual,
                "cur_sales": cur_sales,
                "shown_sales": shown_sales,
            })
        # بیشترین خرید (فروش سال‌های انتخاب‌شده، بعد کل) اول لیست
        data.sort(key=lambda x: (int(x.get("shown_sales") or 0), int(x.get("total") or 0)), reverse=True)

        self._clear_list()
        self._cust_data_full = data
        self._cust_visible = 0
        if not data:
            empty = QLabel("مشتری‌ای یافت نشد")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#94A3B8;padding:40px;font-size:14px;")
            self.list_layout.addWidget(empty)
        else:
            # همه را یکجا و مرتب بساز (بدون جابه‌جایی عجیب دکمه بیشتر)
            self._append_customer_cards(cur_y, show_years, page=max(len(data), 50))

    def edit_balance(self, customer: str):
        c = db()
        rows = c.execute(
            "SELECT total, paid_amount FROM invoices WHERE customer=?",
            (customer,),
        ).fetchall()
        base = 0
        for t, p in rows:
            tt = amount(t)
            pp = tt if (p is None or str(p).strip() == "") else amount(p)
            base += tt - pp
        adj_row = c.execute(
            "SELECT adjustment, note FROM customer_balance_adj WHERE customer=?",
            (customer,),
        ).fetchone()
        c.close()
        current_adj = amount(adj_row[0]) if adj_row else 0
        note0 = (adj_row[1] if adj_row else "") or ""
        current_total = base + current_adj

        dlg = QDialog(self)
        dlg.setWindowTitle("تنظیم طلب / بدهی — " + customer)
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        info = QLabel(
            f"مانده از حواله‌ها: <b>{fmt(base)}</b> ریال<br/>"
            f"تعدیل فعلی: <b>{fmt(current_adj)}</b><br/>"
            f"مانده نهایی فعلی: <b>{'بدهکار ' + fmt(current_total) if current_total > 0 else ('طلبکار ' + fmt(abs(current_total)) if current_total < 0 else 'تسویه')}</b>"
        )
        info.setWordWrap(True)
        lay.addWidget(info)
        form = QFormLayout()
        new_bal = MoneyLineEdit()
        sign = QComboBox()
        sign.addItems(["بدهکار (مشتری بدهکار است)", "طلبکار (ما بدهکاریم)", "تسویه (صفر)"])
        if current_total > 0:
            sign.setCurrentIndex(0)
            new_bal.setText(f"{abs(current_total):,}")
        elif current_total < 0:
            sign.setCurrentIndex(1)
            new_bal.setText(f"{abs(current_total):,}")
        else:
            sign.setCurrentIndex(2)
            new_bal.setText("0")
        note = QLineEdit(note0)
        note.setPlaceholderText("توضیح (اختیاری)")
        form.addRow("نوع مانده:", sign)
        form.addRow("مبلغ مانده:", new_bal)
        form.addRow("یادداشت:", note)
        lay.addLayout(form)
        hint = QLabel(
            "با ذخیره، اختلاف نسبت به مانده حواله‌ها به‌عنوان تعدیل دستی ثبت می‌شود.\n"
            "پرداخت بیشتر از مبلغ حواله در فیلد مبلغ پرداختی، بدهی قبلی همان مشتری را هم کم می‌کند."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        btns = QDialogButtonBox()
        ok_b = btns.addButton("ذخیره", QDialogButtonBox.AcceptRole)
        cancel_b = btns.addButton("انصراف", QDialogButtonBox.RejectRole)
        ok_b.clicked.connect(dlg.accept)
        cancel_b.clicked.connect(dlg.reject)
        lay.addWidget(btns)
        if dlg.exec() != QDialog.Accepted:
            return
        idx = sign.currentIndex()
        val = amount(new_bal.text())
        if idx == 0:
            target = val
        elif idx == 1:
            target = -val
        else:
            target = 0
        new_adj = target - base
        try:
            c = db()
            c.execute("DELETE FROM customer_balance_adj WHERE customer=?", (customer,))
            c.execute(
                "INSERT INTO customer_balance_adj(customer, adjustment, note, updated_at) VALUES(?,?,?,?)",
                (customer, str(int(new_adj)), note.text().strip(), datetime.now().isoformat(timespec="seconds")),
            )
            c.commit()
            c.close()
        except Exception as ex:
            QMessageBox.critical(self, "خطا", str(ex))
            return
        QMessageBox.information(self, "تنظیم مانده", "مانده حساب ذخیره شد.")
        self.refresh()
        try:
            self.win.inquiry_page.reload_buyer_list()
        except Exception:
            _swallow()
        schedule_supabase_sync()


class MonthlyLineChart(QWidget):
    """نمودار خطی فروش ماهانه — مبالغ بر حسب میلیارد ریال + مقایسه سال قبل"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [0] * 12
        self.prev_values = [0] * 12
        self.year = None
        self.prev_year = None
        self.month_labels = [
            "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
            "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
        ]
        self.setMinimumHeight(280)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent; border: none;")

    def set_values(self, values, prev_values=None, year=None, prev_year=None):
        self.values = list(values) if values else [0] * 12
        if len(self.values) < 12:
            self.values += [0] * (12 - len(self.values))
        self.prev_values = list(prev_values) if prev_values else [0] * 12
        if len(self.prev_values) < 12:
            self.prev_values += [0] * (12 - len(self.prev_values))
        self.year = year
        self.prev_year = prev_year
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w, h = self.width(), self.height()
        left, right, top, bottom = 58, 14, 40, 56
        chart_w = max(1, w - left - right)
        chart_h = max(1, h - top - bottom)

        curr = [v / 1_000_000_000 for v in self.values]
        prev = [v / 1_000_000_000 for v in self.prev_values]
        max_v = max(max(curr) if any(curr) else 0, max(prev) if any(prev) else 0)
        if max_v <= 0:
            max_v = 1

        for i in range(5):
            y = top + chart_h * i / 4
            painter.setPen(QPen(QColor("#E2E8F0"), 1, Qt.DashLine))
            painter.drawLine(left, int(y), left + chart_w, int(y))
            val = max_v * (4 - i) / 4
            label = fa_digits(f"{val:.2f}".rstrip("0").rstrip("."))
            painter.setPen(QColor("#64748B"))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(0, int(y) - 9, left - 8, 18, Qt.AlignRight | Qt.AlignVCenter, label)

        painter.setPen(QPen(QColor("#94A3B8"), 1.2))
        painter.drawLine(left, top, left, top + chart_h)
        painter.drawLine(left, top + chart_h, left + chart_w, top + chart_h)

        def make_points(series):
            pts = []
            n = 12
            for i, v in enumerate(series[:12]):
                x = left + chart_w * i / (n - 1) if n > 1 else left
                y = top + chart_h - (chart_h * v / max_v)
                pts.append((x, y))
            return pts

        prev_pts = make_points(prev)
        curr_pts = make_points(curr)

        # سال قبل — خط خاکستری خط‌چین
        if any(self.prev_values):
            path = QPainterPath()
            path.moveTo(prev_pts[0][0], prev_pts[0][1])
            for x, y in prev_pts[1:]:
                path.lineTo(x, y)
            pen = QPen(QColor("#94A3B8"), 2.2, Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            for x, y in prev_pts:
                painter.setBrush(QColor("#FFFFFF"))
                painter.setPen(QPen(QColor("#94A3B8"), 1.5))
                painter.drawEllipse(int(x) - 3, int(y) - 3, 6, 6)

        # سال جاری — خط آبی + سایه
        if len(curr_pts) >= 2:
            area = QPainterPath()
            area.moveTo(curr_pts[0][0], top + chart_h)
            for x, y in curr_pts:
                area.lineTo(x, y)
            area.lineTo(curr_pts[-1][0], top + chart_h)
            area.closeSubpath()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(21, 101, 192, 30))
            painter.drawPath(area)

            path = QPainterPath()
            path.moveTo(curr_pts[0][0], curr_pts[0][1])
            for x, y in curr_pts[1:]:
                path.lineTo(x, y)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor("#1565C0"), 2.8))
            painter.drawPath(path)

        for x, y in curr_pts:
            painter.setBrush(QColor("#FFFFFF"))
            painter.setPen(QPen(QColor("#1565C0"), 2))
            painter.drawEllipse(int(x) - 5, int(y) - 5, 10, 10)
            painter.setBrush(QColor("#1565C0"))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(x) - 2, int(y) - 2, 4, 4)

        painter.setPen(QColor("#475569"))
        painter.setFont(QFont("Segoe UI", 8))
        for i, (x, y) in enumerate(curr_pts):
            painter.drawText(int(x) - 28, top + chart_h + 8, 56, 40, Qt.AlignHCenter | Qt.AlignTop, self.month_labels[i])

        painter.setPen(QColor("#1565C0"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Bold))
        painter.drawText(left, 6, chart_w, 20, Qt.AlignCenter, "نمودار فروش ماهانه")

        painter.setPen(QColor("#64748B"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(left, 6, chart_w, 20, Qt.AlignLeft | Qt.AlignVCenter, "واحد: میلیارد ریال")

        # راهنما
        y0 = 8
        x0 = left + chart_w - 160
        if self.year is not None:
            painter.setPen(QPen(QColor("#1565C0"), 3))
            painter.drawLine(x0, y0 + 6, x0 + 18, y0 + 6)
            painter.setPen(QColor("#334155"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(x0 + 22, y0 - 2, 80, 16, Qt.AlignLeft | Qt.AlignVCenter, fa_digits(str(self.year)))
        if self.prev_year is not None and any(self.prev_values):
            painter.setPen(QPen(QColor("#94A3B8"), 2, Qt.DashLine))
            painter.drawLine(x0 + 70, y0 + 6, x0 + 88, y0 + 6)
            painter.setPen(QColor("#334155"))
            painter.drawText(x0 + 92, y0 - 2, 80, 16, Qt.AlignLeft | Qt.AlignVCenter, fa_digits(str(self.prev_year)))


class ReportsPage(QWidget):
    MONTH_NAMES = [
        "فروردین", "اردیبهشت", "خرداد",
        "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر",
        "دی", "بهمن", "اسفند",
    ]
    MONTH_COLORS = [
        "#E3F2FD", "#E8F5E9", "#FFF3E0",
        "#F3E5F5", "#E0F7FA", "#FCE4EC",
        "#F1F8E9", "#EFEBE9", "#E8EAF6",
        "#FFF8E1", "#E0F2F1", "#FBE9E7",
    ]

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        l = QVBoxLayout(content)
        l.setContentsMargins(24, 18, 24, 24)
        l.setSpacing(14)

        title = QLabel("گزارش‌ها")
        title.setObjectName("pageTitle")
        l.addWidget(title)

        # انتخاب سال
        year_row = QHBoxLayout()
        year_row.setSpacing(10)
        year_lbl = QLabel("سال:")
        year_lbl.setStyleSheet("font-size: 14px; font-weight: 600;")
        self.year_combo = QComboBox()
        self.year_combo.setFixedWidth(120)
        self.year_combo.setLayoutDirection(Qt.RightToLeft)
        # سال‌ها از ۱۴۰۳ تا سال جاری جلالی + ۱
        gy, gm, gd = datetime.now().year, datetime.now().month, datetime.now().day
        jy, jm, jd = gregorian_to_jalali(gy, gm, gd)
        for y in range(1403, jy + 2):
            self.year_combo.addItem(fa_digits(str(y)), y)
        # انتخاب سال جاری به صورت پیش‌فرض
        idx = self.year_combo.findData(jy)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        self.year_combo.currentIndexChanged.connect(self.refresh)
        year_row.addWidget(year_lbl)
        year_row.addWidget(self.year_combo)
        year_row.addStretch()
        l.addLayout(year_row)

        # شبکه ۱۲ ماهه
        self.grid_wrap = QWidget()
        self.grid = QVBoxLayout(self.grid_wrap)  # will hold 3 rows of 4
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(14)
        l.addWidget(self.grid_wrap)

        # جمع کل سال
        self.year_total_lbl = QLabel()
        self.year_total_lbl.setObjectName("sectionTitle")
        self.year_total_lbl.setAlignment(Qt.AlignCenter)
        self.year_total_lbl.setStyleSheet("""
            font-size: 18px; font-weight: 700; color: #1565C0;
            background: transparent; border: none;
            padding: 14px;
        """)
        l.addWidget(self.year_total_lbl)

        # نمودار خطی فروش ماهانه
        self.chart = MonthlyLineChart()
        self.chart.setMinimumHeight(280)
        l.addWidget(self.chart)

        # فروش به تفکیک کد کالا
        self.code_section_title = QLabel("فروش به تفکیک کد کالا")
        self.code_section_title.setStyleSheet(
            "font-size:16px;font-weight:800;color:#0F172A;border:none;background:transparent;"
            "padding:8px 0 4px 0;"
        )
        l.addWidget(self.code_section_title)
        self.code_hint = QLabel("بر اساس اقلام حواله‌ها (استعلام) و فروشگاه — مرتب‌شده بر اساس متراژ")
        self.code_hint.setStyleSheet(
            "font-size:11px;color:#64748B;border:none;background:transparent;padding-bottom:6px;"
        )
        l.addWidget(self.code_hint)
        self.code_host = QVBoxLayout()
        self.code_host.setSpacing(8)
        self.code_host.setContentsMargins(0, 0, 0, 0)
        l.addLayout(self.code_host)

        l.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def _month_card(self, month_name, color, total, count):
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {color};
                border: none;
                border-radius: 12px;
            }}
        """)
        card.setMinimumHeight(100)
        card.setMinimumWidth(140)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(4)

        name_lbl = QLabel(month_name)
        name_lbl.setAlignment(Qt.AlignCenter)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #1E293B; background: transparent;")
        vl.addWidget(name_lbl)

        amount_lbl = QLabel(fmt(total) if total else "۰")
        amount_lbl.setAlignment(Qt.AlignCenter)
        amount_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #1565C0; background: transparent;")
        vl.addWidget(amount_lbl)

        count_lbl = QLabel(f"{fa_digits(count)} حواله")
        count_lbl.setAlignment(Qt.AlignCenter)
        count_lbl.setStyleSheet("font-size: 12px; color: #64748B; background: transparent;")
        vl.addWidget(count_lbl)

        return card

    def refresh(self):
        # پاک کردن شبکه قبلی
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                lay = item.layout()
                while lay.count():
                    it = lay.takeAt(0)
                    if it.widget():
                        it.widget().deleteLater()

        year = self.year_combo.currentData()
        if year is None:
            year = 1403
        prev_year = year - 1

        def load_year_months(conn, y):
            totals = [0] * 12
            counts = [0] * 12
            rows = conn.execute(
                "SELECT date, total FROM invoices WHERE date LIKE ?",
                (f"{y:04d}/%",)
            ).fetchall()
            for date_str, total in rows:
                try:
                    parts = date_str.split("/")
                    if len(parts) >= 2:
                        m = int(parts[1])
                        if 1 <= m <= 12:
                            totals[m - 1] += amount(total)
                            counts[m - 1] += 1
                except Exception:
                    _swallow()
            return totals, counts

        c = db()
        month_totals, month_counts = load_year_months(c, year)
        prev_totals, _ = load_year_months(c, prev_year)
        c.close()

        # ۳ ردیف × ۴ ستون
        for row_i in range(3):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(14)
            for col_i in range(4):
                mi = row_i * 4 + col_i
                card = self._month_card(
                    self.MONTH_NAMES[mi],
                    self.MONTH_COLORS[mi],
                    month_totals[mi],
                    month_counts[mi],
                )
                row_layout.addWidget(card)
            self.grid.addLayout(row_layout)

        year_sum = sum(month_totals)
        year_count = sum(month_counts)
        self.year_total_lbl.setText(
            f"جمع کل سال {fa_digits(year)}:  {fmt(year_sum)} ریال   |   {fa_digits(year_count)} حواله"
        )
        self.chart.set_values(month_totals, prev_totals, year=year, prev_year=prev_year)
        self._refresh_code_sales(year)


    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _refresh_code_sales(self, year):
        """جدول کارت‌مانند فروش هر کد در سال انتخاب‌شده"""
        if not hasattr(self, "code_host"):
            return
        self._clear_layout(self.code_host)

        # code -> {meters, cartons, amount, count, types}
        from collections import defaultdict
        agg = defaultdict(lambda: {"meters": 0.0, "cartons": 0.0, "amount": 0.0, "lines": 0, "types": set(), "names": {}})

        def add_row(code, typ, qty1, qty2, cost, tab="parquet", full_name=""):
            code = en_digits(str(code or "").strip())
            if not code or code in ("—", "-", "0"):
                return
            try:
                m = float(en_digits(str(qty2 or "0")).replace(",", "") or 0)
            except Exception:
                m = 0.0
            try:
                c = float(en_digits(str(qty1 or "0")).replace(",", "") or 0)
            except Exception:
                c = 0.0
            a = amount(cost)
            if a <= 0 and m > 0:
                # اگر cost نبود از price*qty2 حساب نشود اینجا — فقط cost
                pass
            bucket = agg[code]
            bucket["meters"] += m
            bucket["cartons"] += c
            bucket["amount"] += a
            bucket["lines"] += 1
            if typ:
                bucket["types"].add(str(typ))
            nm = str(full_name or typ or "").strip()
            if nm:
                bucket["names"][nm] = bucket["names"].get(nm, 0) + 1

        def _full_name(r):
            nm = r.get("name") or r.get("desc") or r.get("description")
            if nm:
                return str(nm)
            parts = [str(x).strip() for x in (r.get("type") or r.get("typ"), r.get("grade"), r.get("size")) if x and str(x).strip()]
            return " ".join(parts)

        c = db()
        # حواله‌ها با جزئیات استعلام
        try:
            inv_rows = c.execute(
                "SELECT date, inquiry_data, total FROM invoices WHERE date LIKE ?",
                (f"{year:04d}/%",),
            ).fetchall()
        except Exception:
            inv_rows = []
        for date_s, inq_raw, tot in inv_rows:
            data = None
            if inq_raw:
                try:
                    data = json.loads(inq_raw) if isinstance(inq_raw, str) else inq_raw
                except Exception:
                    data = None
            if not data or not isinstance(data, dict):
                continue
            rows = data.get("rows") or []
            try:
                from statement_core import sample_last
            except Exception:
                from salesmate.statement_core import sample_last
            rows = sample_last(rows)
            tab = data.get("tab") or "parquet"
            for r in rows:
                if not isinstance(r, dict):
                    continue
                add_row(
                    r.get("code"),
                    r.get("type") or r.get("typ"),
                    core.qty_int(r.get("qty1")),
                    r.get("qty2"),
                    r.get("cost") or 0,
                    tab,
                    _full_name(r),
                )

        # فروشگاه
        try:
            st_rows = c.execute(
                "SELECT date, tab, items_json, total FROM store_sales WHERE date LIKE ?",
                (f"{year:04d}/%",),
            ).fetchall()
        except Exception:
            st_rows = []
        c.close()
        for date_s, tab, items_json, tot in st_rows:
            try:
                items = json.loads(items_json or "[]")
            except Exception:
                items = []
            if not isinstance(items, list):
                continue
            for r in items:
                if not isinstance(r, dict):
                    continue
                add_row(
                    r.get("code"),
                    r.get("type") or r.get("typ"),
                    core.qty_int(r.get("qty1")),
                    r.get("qty2"),
                    r.get("cost") or 0,
                    tab or "parquet",
                    _full_name(r),
                )

        if not agg:
            empty = QLabel("برای این سال اقلام کددار ثبت نشده است.")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(
                "color:#94A3B8;padding:20px;font-size:13px;border:none;background:transparent;"
            )
            self.code_host.addWidget(empty)
            return

        # مرتب بر اساس متراژ نزولی
        items_sorted = sorted(
            agg.items(),
            key=lambda x: (x[1]["meters"], x[1]["amount"]),
            reverse=True,
        )

        # هدر
        header = QFrame()
        header.setStyleSheet(
            "QFrame{background:#1565C0;border:none;border-radius:14px;}"
            "QLabel{background:transparent;border:none;color:#FFFFFF;font-weight:700;font-size:12px;}"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 10, 14, 10)
        hl.setSpacing(8)
        for text_h, stretch in [
            ("کد کالا", 2),
            ("نام کالا", 6),
            ("متر مربع / ورق", 2),
            ("کارتن / پالت", 2),
            ("مبلغ", 3),
        ]:
            lb = QLabel(text_h)
            lb.setAlignment(Qt.AlignCenter)
            hl.addWidget(lb, stretch)
        self.code_host.addWidget(header)

        total_m = 0.0
        total_c = 0.0
        total_a = 0.0
        colors = ["#FFFFFF", "#F8FAFC"]
        for i, (code, d) in enumerate(items_sorted):
            total_m += d["meters"]
            total_c += d["cartons"]
            total_a += d["amount"]
            row = QFrame()
            row.setStyleSheet(
                f"QFrame{{background:{colors[i % 2]};border:1px solid #E2E8F0;border-radius:12px;"
                f"border-right:5px solid #1565C0;}}"
                "QLabel{background:transparent;border:none;}"
            )
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(8)

            code_lbl = QLabel(fa_digits(code))
            code_lbl.setAlignment(Qt.AlignCenter)
            code_lbl.setStyleSheet("font-size:14px;font-weight:800;color:#0F172A;")
            rl.addWidget(code_lbl, 2)

            # نام کامل: پرتکرارترین نام (در برابری، بلندترین)؛ بقیه‌ی نام‌ها در tooltip
            names_sorted = sorted(d["names"].items(), key=lambda kv: (-kv[1], -len(kv[0])))
            if names_sorted:
                main_name = names_sorted[0][0]
            else:
                main_name = "، ".join(sorted(d["types"])) if d["types"] else "—"
            low = " ".join(list(d["names"].keys()) + list(d["types"])).lower()
            is_mdf = any(k in low for k in ("ام دی اف", "mdf", "هایگلاس", "ملامینه", "خام"))
            typ_lbl = QLabel(fa_digits(main_name))
            typ_lbl.setAlignment(Qt.AlignCenter)
            typ_lbl.setStyleSheet("font-size:12px;font-weight:600;color:#0F172A;")
            typ_lbl.setWordWrap(True)
            if len(names_sorted) > 1:
                typ_lbl.setToolTip("\n".join(n for n, _ in names_sorted))
            rl.addWidget(typ_lbl, 6)

            def _fmt_m(v):
                if not v:
                    return fa_digits("0")
                s = f"{v:.4f}".rstrip("0").rstrip(".")
                return fa_digits(s)

            m_lbl = QLabel(_fmt_m(d["meters"]) + (" ورق" if is_mdf else " متر مربع"))
            m_lbl.setAlignment(Qt.AlignCenter)
            m_lbl.setStyleSheet("font-size:13px;font-weight:800;color:#1565C0;")
            rl.addWidget(m_lbl, 2)

            c_lbl = QLabel(fa_digits(str(int(d["cartons"] + 0.5))) + (" پالت" if is_mdf else " کارتن"))
            c_lbl.setAlignment(Qt.AlignCenter)
            c_lbl.setStyleSheet("font-size:13px;font-weight:700;color:#0F172A;")
            rl.addWidget(c_lbl, 2)

            a_lbl = QLabel(fmt(d["amount"]))
            a_lbl.setAlignment(Qt.AlignCenter)
            a_lbl.setStyleSheet("font-size:13px;font-weight:800;color:#059669;")
            rl.addWidget(a_lbl, 3)

            self.code_host.addWidget(row)

        # جمع
        foot = QFrame()
        foot.setStyleSheet(
            "QFrame{background:#ECFDF5;border:1px solid #A7F3D0;border-radius:14px;}"
            "QLabel{background:transparent;border:none;}"
        )
        fl = QHBoxLayout(foot)
        fl.setContentsMargins(14, 12, 14, 12)
        def _fmt_m2(v):
            if not v:
                return fa_digits("0")
            s = f"{v:.4f}".rstrip("0").rstrip(".")
            return fa_digits(s)
        sum_lbl = QLabel(
            f"جمع کدها: {fa_digits(len(items_sorted))}   |   "
            f"متراژ/ورق: {_fmt_m2(total_m)}   |   "
            f"کارتن/پالت: {fa_digits(str(int(total_c + 0.5)))}   |   "
            f"مبلغ: {fmt(total_a)} ریال"
        )
        sum_lbl.setAlignment(Qt.AlignCenter)
        sum_lbl.setStyleSheet("font-size:13px;font-weight:800;color:#065F46;")
        sum_lbl.setWordWrap(True)
        fl.addWidget(sum_lbl)
        self.code_host.addWidget(foot)


class ContactsPage(QWidget):
    """اطلاعات مشتری‌ها / نمایندگان — مشترک بین همه کاربران"""
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setLayoutDirection(Qt.RightToLeft)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        content = QWidget()
        self.lay = QVBoxLayout(content)
        self.lay.setContentsMargins(20, 16, 20, 20)
        self.lay.setSpacing(12)

        title = QLabel("اطلاعات مشتری‌ها")
        title.setObjectName("pageTitle")
        self.lay.addWidget(title)
        hint = QLabel("لیست مشترک نمایندگان و مشتریان — همه کاربران یکسان می‌بینند")
        hint.setStyleSheet("color:#64748B;font-size:12px;border:none;background:transparent;")
        self.lay.addWidget(hint)

        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("جستجو نام، موسسه، شهر، موبایل…")
        self.search.textChanged.connect(lambda: self._kick_refresh())
        tools.addWidget(self.search, 1)
        add_b = QPushButton("+ جدید")
        add_b.setCursor(Qt.PointingHandCursor)
        add_b.setStyleSheet(
            "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        add_b.clicked.connect(self.add_contact)
        pdf_b = QPushButton("خروجی PDF")
        pdf_b.setCursor(Qt.PointingHandCursor)
        pdf_b.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        pdf_b.clicked.connect(self.export_pdf)
        push_b = QPushButton("ارسال به ابر")
        push_b.setCursor(Qt.PointingHandCursor)
        push_b.setStyleSheet(
            "QPushButton{background:#7C3AED;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        push_b.clicked.connect(self.sync_push)
        pull_b = QPushButton("دریافت از ابر")
        pull_b.setCursor(Qt.PointingHandCursor)
        pull_b.setStyleSheet(
            "QPushButton{background:#0EA5E9;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        pull_b.clicked.connect(self.sync_pull)
        seed_b = QPushButton("بارگذاری لیست نمایندگان")
        seed_b.setCursor(Qt.PointingHandCursor)
        seed_b.setStyleSheet(
            "QPushButton{background:#F59E0B;color:#fff;border:none;border-radius:10px;padding:8px 14px;font-weight:700;}"
        )
        seed_b.clicked.connect(self.reload_seed)
        tools.addWidget(add_b)
        tools.addWidget(pdf_b)
        tools.addWidget(push_b)
        tools.addWidget(pull_b)
        tools.addWidget(seed_b)
        self.lay.addLayout(tools)

        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet("color:#64748B;font-size:12px;border:none;")
        self.lay.addWidget(self.count_lbl)

        self.list_host = QVBoxLayout()
        self.list_host.setSpacing(8)
        self.lay.addLayout(self.list_host)
        self.lay.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.refresh()

    def _clear_host(self):
        while self.list_host.count():
            it = self.list_host.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

    def _filtered(self):
        q = (self.search.text() or "").strip()
        items = load_contacts()
        if not q:
            return items
        q = q.lower()
        out = []
        for it in items:
            blob = " ".join([
                str(it.get("first_name") or ""),
                str(it.get("last_name") or ""),
                str(it.get("company") or ""),
                str(it.get("city") or ""),
                str(it.get("phone") or ""),
                str(it.get("mobile") or ""),
                str(it.get("address") or ""),
            ]).lower()
            if q in blob:
                out.append(it)
        return out

    def _kick_refresh(self):
        if not hasattr(self, "_ref_timer"):
            self._ref_timer = QTimer(self)
            self._ref_timer.setSingleShot(True)
            self._ref_timer.setInterval(250)
            self._ref_timer.timeout.connect(self.refresh)
        self._ref_timer.start()

    def auto_pull(self):
        """اگر این برنامه لیست اطلاعات مشتریان ندارد (نصب تازه / حساب جدید) و وارد ابر شده‌ایم، یک‌بار از ابر می‌گیرد."""
        try:
            if getattr(self, "_auto_pulled", False) or load_contacts():
                return
            if not core.supabase_session_valid():
                return
            self._auto_pulled = True

            def _run():
                try:
                    items = pull_contacts_from_supabase()
                except Exception:
                    return
                if items:
                    try:
                        from app_core import run_in_ui
                    except Exception:
                        from salesmate.app_core import run_in_ui
                    run_in_ui(self.refresh)
            threading.Thread(target=_run, daemon=True).start()
        except Exception:
            _swallow()

    def refresh(self):
        self.auto_pull()
        self._clear_host()
        items = self._filtered()
        all_n = len(load_contacts())
        self.count_lbl.setText(
            "نمایش %s از %s مورد" % (fa_digits(len(items)), fa_digits(all_n))
        )
        if not items:
            empty = QLabel("موردی یافت نشد")
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet("color:#94A3B8;padding:24px;")
            self.list_host.addWidget(empty)
            return
        for idx, it in enumerate(items):
            card = self._card(it, idx)
            self.list_host.addWidget(card)

    def _card(self, it, idx):
        """کارت تمام‌عرض: راست = نام/موسسه/شهر | وسط = تلفن‌ها | چپ‌تر = آدرس | انتهای چپ = دکمه‌ها."""
        f = QFrame()
        f.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;"
            "border-right:5px solid #1565C0;}"
            "QLabel{background:transparent;border:none;}"
        )
        hl = QHBoxLayout(f)
        hl.setContentsMargins(16, 12, 16, 12)
        hl.setSpacing(18)

        name = ((it.get("first_name") or "") + " " + (it.get("last_name") or "")).strip() or "—"
        company = it.get("company") or ""
        city = it.get("city") or ""

        c1 = QVBoxLayout()
        c1.setSpacing(4)
        nm = QLabel(name)
        nm.setStyleSheet("font-size:17px;font-weight:800;color:#0F172A;")
        c1.addWidget(nm)
        if company:
            cp = QLabel(company)
            cp.setStyleSheet("font-size:14px;font-weight:600;color:#1565C0;")
            cp.setWordWrap(True)
            c1.addWidget(cp)
        if city:
            ct = QLabel("📍 " + city)
            ct.setStyleSheet("font-size:14px;color:#475569;")
            c1.addWidget(ct)
        c1.addStretch()
        w1 = QWidget(); w1.setLayout(c1); w1.setMinimumWidth(210); w1.setMaximumWidth(300)
        w1.setStyleSheet("background:transparent;")
        hl.addWidget(w1, 3)

        c2 = QVBoxLayout()
        c2.setSpacing(4)
        for lab, key in (("موبایل", "mobile"), ("تلفن", "phone")):
            if it.get(key):
                p = QLabel("%s:  %s" % (lab, fa_digits(it.get(key))))
                p.setStyleSheet("font-size:15px;font-weight:700;color:#0F172A;")
                p.setTextInteractionFlags(Qt.TextSelectableByMouse)
                c2.addWidget(p)
        c2.addStretch()
        w2 = QWidget(); w2.setLayout(c2); w2.setMinimumWidth(190); w2.setMaximumWidth(260)
        w2.setStyleSheet("background:transparent;")
        hl.addWidget(w2, 2)

        addr = it.get("address") or ""
        a = QLabel(addr or "—")
        a.setWordWrap(True)
        a.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        a.setStyleSheet("font-size:14px;color:#334155;")
        a.setTextInteractionFlags(Qt.TextSelectableByMouse)
        hl.addWidget(a, 5)

        bl = QVBoxLayout()
        bl.setSpacing(6)
        edit_b = QPushButton("ویرایش")
        edit_b.setCursor(Qt.PointingHandCursor)
        edit_b.setStyleSheet(
            "QPushButton{background:#F1F5F9;color:#0F172A;border:none;border-radius:8px;padding:7px 16px;font-size:14px;font-weight:700;}"
        )
        edit_b.clicked.connect(lambda _=False, item=it: self.edit_contact(item))
        del_b = QPushButton("حذف")
        del_b.setCursor(Qt.PointingHandCursor)
        del_b.setStyleSheet(
            "QPushButton{background:#FEE2E2;color:#B91C1C;border:none;border-radius:8px;padding:7px 16px;font-size:14px;font-weight:700;}"
        )
        del_b.clicked.connect(lambda _=False, item=it: self.delete_contact(item))
        bl.addWidget(edit_b)
        bl.addWidget(del_b)
        bl.addStretch()
        wb = QWidget(); wb.setLayout(bl); wb.setStyleSheet("background:transparent;")
        hl.addWidget(wb, 0)
        return f

    def _dialog(self, item=None):
        dlg = QDialog(self)
        dlg.setWindowTitle("ویرایش تماس" if item else "مشتری / نماینده جدید")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(420, 420)
        form = QFormLayout(dlg)
        fields = {}
        for key, label in [
            ("first_name", "نام"),
            ("last_name", "نام خانوادگی"),
            ("company", "نام موسسه"),
            ("phone", "تلفن"),
            ("mobile", "همراه"),
            ("city", "شهر"),
            ("address", "آدرس"),
        ]:
            le = QLineEdit()
            if item:
                le.setText(str(item.get(key) or ""))
            if key == "address":
                le.setMinimumHeight(60)
            fields[key] = le
            form.addRow(label + ":", le)
        btns = QDialogButtonBox()
        ok = btns.addButton("ذخیره", QDialogButtonBox.AcceptRole)
        cancel = btns.addButton("انصراف", QDialogButtonBox.RejectRole)
        ok.clicked.connect(dlg.accept)
        cancel.clicked.connect(dlg.reject)
        form.addRow(btns)
        if dlg.exec() != QDialog.Accepted:
            return None
        return {k: fields[k].text().strip() for k in fields}

    def add_contact(self):
        data = self._dialog()
        if not data:
            return
        items = load_contacts()
        items.append(data)
        save_contacts(items)
        self.refresh()
        try:
            threading.Thread(target=lambda: push_contacts_to_supabase(items), daemon=True).start()
        except Exception:
            _swallow()

    def edit_contact(self, item):
        data = self._dialog(item)
        if not data:
            return
        items = load_contacts()
        # match by identity
        for i, it in enumerate(items):
            if it is item or (
                it.get("mobile") == item.get("mobile")
                and it.get("company") == item.get("company")
                and it.get("first_name") == item.get("first_name")
                and it.get("last_name") == item.get("last_name")
            ):
                items[i] = data
                break
        else:
            items.append(data)
        save_contacts(items)
        self.refresh()
        try:
            threading.Thread(target=lambda: push_contacts_to_supabase(items), daemon=True).start()
        except Exception:
            _swallow()

    def delete_contact(self, item):
        if QMessageBox.question(self, "حذف", "این مورد حذف شود؟") != QMessageBox.Yes:
            return
        items = load_contacts()
        new_items = []
        removed = False
        for it in items:
            if not removed and (
                it is item
                or (
                    it.get("mobile") == item.get("mobile")
                    and it.get("company") == item.get("company")
                    and it.get("first_name") == item.get("first_name")
                )
            ):
                removed = True
                continue
            new_items.append(it)
        save_contacts(new_items)
        self.refresh()
        try:
            threading.Thread(target=lambda: push_contacts_to_supabase(new_items), daemon=True).start()
        except Exception:
            _swallow()

    def sync_push(self):
        try:
            n = push_contacts_to_supabase()
            QMessageBox.information(self, "ابر", "ارسال شد: %s مورد" % fa_digits(n))
        except Exception as ex:
            QMessageBox.warning(self, "ابر", str(ex))

    def sync_pull(self):
        try:
            items = pull_contacts_from_supabase()
            QMessageBox.information(self, "ابر", "دریافت شد: %s مورد" % fa_digits(len(items)))
            self.refresh()
        except Exception as ex:
            QMessageBox.warning(self, "ابر", str(ex))

    def reload_seed(self):
        """اجباراً لیست اکسل نمایندگان را بارگذاری می‌کند"""
        items = _load_seed_contacts()
        if not items:
            QMessageBox.warning(self, "لیست", "فایل لیست نمایندگان پیدا نشد.")
            return
        # ادغام با موارد فعلی (موبایل+شرکت یکتا)
        current = load_contacts()
        seen = set()
        for it in current:
            key = (
                (it.get("mobile") or "").strip(),
                (it.get("company") or "").strip(),
                (it.get("first_name") or "").strip(),
                (it.get("last_name") or "").strip(),
            )
            seen.add(key)
        added = 0
        for it in items:
            key = (
                (it.get("mobile") or "").strip(),
                (it.get("company") or "").strip(),
                (it.get("first_name") or "").strip(),
                (it.get("last_name") or "").strip(),
            )
            if key in seen:
                continue
            current.append(it)
            seen.add(key)
            added += 1
        if added == 0 and len(current) < len(items):
            # احتمالاً لیست ناقص است — جایگزینی کامل از seed
            current = list(items)
            added = len(items)
        save_contacts(current)
        self.refresh()
        QMessageBox.information(
            self, "لیست",
            "بارگذاری شد.\nتعداد کل: %s\nجدید اضافه‌شده: %s"
            % (fa_digits(len(current)), fa_digits(added)),
        )
        try:
            threading.Thread(target=lambda: push_contacts_to_supabase(current), daemon=True).start()
        except Exception:
            _swallow()

    def export_pdf(self):
        items = self._filtered()
        if not items:
            QMessageBox.information(self, "PDF", "موردی برای خروجی نیست.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره PDF", str(APP_DIR / "اطلاعات_مشتریها.pdf"), "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            from PySide6.QtGui import QPdfWriter, QPainter, QPageSize, QPageLayout
            from PySide6.QtCore import QMarginsF
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.A4))
            writer.setPageMargins(QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter)
            painter = QPainter(writer)
            painter.setLayoutDirection(Qt.RightToLeft)
            page_w = writer.width()
            y = 40
            font_title = painter.font()
            font_title.setPointSize(16)
            font_title.setBold(True)
            painter.setFont(font_title)
            painter.drawText(0, y, page_w, 40, Qt.AlignCenter, "اطلاعات مشتری‌ها / نمایندگان")
            y += 50
            font_n = painter.font()
            font_n.setPointSize(9)
            font_n.setBold(False)
            painter.setFont(font_n)
            painter.drawText(0, y, page_w, 24, Qt.AlignCenter,
                             "تعداد: " + fa_digits(len(items)) + "  ·  " + fa_digits(datetime.now().strftime("%Y/%m/%d")))
            y += 36
            for i, it in enumerate(items, 1):
                name = ((it.get("first_name") or "") + " " + (it.get("last_name") or "")).strip() or "—"
                company = it.get("company") or "—"
                line1 = fa_digits(str(i)) + ") " + name + "  |  " + company
                line2 = (it.get("city") or "")
                line3 = ""
                if it.get("mobile"):
                    line3 += "موبایل: " + fa_digits(it["mobile"]) + "  "
                if it.get("phone"):
                    line3 += "تلفن: " + fa_digits(it["phone"])
                line4 = it.get("address") or ""
                need = 70
                if y + need > writer.height() - 40:
                    writer.newPage()
                    y = 40
                font_b = painter.font()
                font_b.setBold(True)
                font_b.setPointSize(10)
                painter.setFont(font_b)
                painter.drawText(20, y, page_w - 40, 22, Qt.AlignRight, line1)
                y += 20
                font_b.setBold(False)
                font_b.setPointSize(9)
                painter.setFont(font_b)
                if line2:
                    painter.drawText(20, y, page_w - 40, 18, Qt.AlignRight, line2)
                    y += 18
                if line3.strip():
                    painter.drawText(20, y, page_w - 40, 18, Qt.AlignRight, line3.strip())
                    y += 18
                if line4:
                    r = painter.boundingRect(20, y, page_w - 40, 60, Qt.AlignRight | Qt.TextWordWrap, line4)
                    painter.drawText(r, Qt.AlignRight | Qt.TextWordWrap, line4)
                    y += r.height() + 8
                y += 10
            painter.end()
            QMessageBox.information(self, "PDF", "ذخیره شد:\n" + path)
        except Exception as ex:
            QMessageBox.critical(self, "PDF", str(ex))
