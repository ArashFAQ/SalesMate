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
    CODE_TO_PRODUCT,
    EGMONT_OPTIONS,
    GRADE_OPTIONS,
    INQUIRY_PATH,
    PRODUCT_FACTORS,
    PRODUCT_OPTIONS,
    _swallow,
    amount,
    clean_number,
    customer_balance,
    db,
    delete_inquiry_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    now_jalali,
    number_to_persian_words,
    schedule_supabase_sync,
)
except Exception:
    from salesmate.app_core import (
    APP_DIR,
    CODE_TO_PRODUCT,
    EGMONT_OPTIONS,
    GRADE_OPTIONS,
    INQUIRY_PATH,
    PRODUCT_FACTORS,
    PRODUCT_OPTIONS,
    _swallow,
    amount,
    clean_number,
    customer_balance,
    db,
    delete_inquiry_from_cloud,
    en_digits,
    fa_digits,
    fmt,
    now_jalali,
    number_to_persian_words,
    schedule_supabase_sync,
)
try:
    from invoice_pages import MoneyLineEdit
except Exception:
    from salesmate.invoice_pages import MoneyLineEdit



def _names_close(a, b):
    """نام تقریباً یکسان: برابر، یکی داخل دیگری، یا شباهت بالا."""
    try:
        from core_utils import customer_key
    except Exception:
        from salesmate.core_utils import customer_key
    import difflib
    ka, kb = customer_key(a), customer_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    ka2, kb2 = ka.replace(" ", "").replace("-", ""), kb.replace(" ", "").replace("-", "")
    if ka2 == kb2:
        return True
    if min(len(ka2), len(kb2)) >= 4 and (ka2 in kb2 or kb2 in ka2):
        return True
    return difflib.SequenceMatcher(None, ka2, kb2).ratio() >= 0.82


_DECLINED_PATH = APP_DIR / "inquiry_prune_declined.json"


def _declined_pairs():
    try:
        return set(json.loads(_DECLINED_PATH.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_declined(pairs):
    try:
        _DECLINED_PATH.write_text(json.dumps(sorted(pairs), ensure_ascii=False), encoding="utf-8")
    except Exception:
        _swallow()


def _inq_key(item):
    return str(item.get("id") or "%s|%s|%s" % (item.get("buyer"), item.get("date"), item.get("total")))


def _row_codes(rows):
    out = set()
    for r in rows or []:
        c = en_digits(str((r or {}).get("code") or "")).strip()
        if c:
            out.add(c)
    return out


def find_inquiry_invoice_matches():
    """برای هر استعلام ذخیره‌شده، شبیه‌ترین حواله‌ی بعدش را پیدا می‌کند.
    شباهت = نام مشتری یکسان/نزدیک، یا مبلغ یکسان، یا همه‌ی کدهای استعلام در حواله باشد.
    حواله باید هم‌تاریخ یا بعد از استعلام باشد. جفت‌های «خیر»شده دوباره پرسیده نمی‌شوند.
    خروجی: [(item, invoice_dict, [دلیل‌ها])]"""
    out = []
    try:
        if not INQUIRY_PATH.exists():
            return out
        lst = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
        if not isinstance(lst, list) or not lst:
            return out
        c = db()
        try:
            inv = c.execute(
                "SELECT id, customer, invoice_no, date, total, inquiry_data FROM invoices"
            ).fetchall()
        finally:
            c.close()
        declined = _declined_pairs()

        def nd(x):
            parts = en_digits(str(x or "")).replace("-", "/").split("/")
            try:
                return "%04d/%02d/%02d" % (int(parts[0]), int(parts[1]), int(parts[2]))
            except Exception:
                return ""
        invs = []
        for iid, cu, no, dt, tt, blob in inv:
            try:
                d = json.loads(blob) if isinstance(blob, str) and blob.strip() else {}
            except Exception:
                d = {}
            invs.append({"id": iid, "customer": str(cu or ""), "no": str(no or ""), "date": str(dt or ""),
                         "dn": nd(dt), "total": int(amount(tt)), "data": d if isinstance(d, dict) else {},
                         "codes": _row_codes((d or {}).get("rows") if isinstance(d, dict) else [])})
        for item in lst:
            ik = _inq_key(item)
            idate = nd(item.get("date"))
            ttl = int(amount(item.get("total")))
            icodes = _row_codes(item.get("rows"))
            best = None
            for v in invs:
                if "%s|%s" % (ik, v["id"]) in declined:
                    continue
                if idate and v["dn"] and v["dn"] < idate:
                    continue
                why = []
                if _names_close(item.get("buyer"), v["customer"]):
                    why.append("نام مشتری یکسان")
                if ttl > 0 and v["total"] == ttl:
                    why.append("مبلغ یکسان")
                if icodes and icodes <= v["codes"]:
                    why.append("کد کالا یکسان")
                if not why:
                    continue
                score = (len(why), v["dn"])
                if best is None or score > best[0]:
                    best = (score, v, why)
            if best:
                out.append((item, best[1], best[2]))
    except Exception:
        _swallow()
    return out


def _tbl_html(data, tab_default="parquet"):
    try:
        try:
            from invoice_pages import invoice_items_html
        except Exception:
            from salesmate.invoice_pages import invoice_items_html
        d = dict(data or {})
        d.setdefault("tab", tab_default)
        return invoice_items_html(d) or "<span style='color:#94A3B8'>جزئیات کالا ثبت نشده</span>"
    except Exception:
        return "<span style='color:#94A3B8'>جزئیات کالا ثبت نشده</span>"


def ask_prune_saved_inquiries(parent=None):
    """برای هر استعلام ذخیره‌شده‌ای که حواله‌ی شبیه دارد می‌پرسد: حذف شود؟ (بله / خیر).
    بالا جدول استعلام، پایین جدول حواله. «خیر» ماندگار است و دوباره نمی‌پرسد."""
    matches = find_inquiry_invoice_matches()
    if not matches:
        return 0
    removed = 0
    declined = _declined_pairs()
    for item, v, why in matches:
        dlg = QDialog(parent)
        dlg.setWindowTitle("استعلام ذخیره‌شده با حواله شباهت دارد")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.resize(820, 700)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(8)
        q = QLabel("این استعلام ذخیره‌شده با یک حواله شباهت دارد (%s). استعلام حذف شود؟" % "، ".join(why))
        q.setWordWrap(True)
        q.setStyleSheet("font-size:14px;font-weight:800;color:#0F172A;")
        lay.addWidget(q)

        def box(title, meta, data):
            f = QFrame()
            f.setStyleSheet("QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;}"
                            "QLabel{border:none;background:transparent;}")
            fl = QVBoxLayout(f)
            fl.setContentsMargins(10, 8, 10, 8)
            t = QLabel("<b>%s</b>  ·  %s" % (title, meta))
            t.setStyleSheet("font-size:13px;color:#1E3A8A;")
            fl.addWidget(t)
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.NoFrame)
            body = QLabel(_tbl_html(data))
            body.setTextFormat(Qt.RichText)
            body.setWordWrap(True)
            body.setAlignment(Qt.AlignTop | Qt.AlignRight)
            sc.setWidget(body)
            fl.addWidget(sc, 1)
            return f
        imeta = "%s  ·  تاریخ %s  ·  مبلغ %s ریال" % (
            item.get("buyer") or "—", fa_digits(item.get("date") or ""), fa_digits(fmt(item.get("total") or 0)))
        vmeta = "%s  ·  حواله %s  ·  تاریخ %s  ·  مبلغ %s ریال" % (
            v["customer"] or "—", fa_digits(v["no"]), fa_digits(v["date"]), fa_digits(fmt(v["total"])))
        idata = {"tab": item.get("tab") or "parquet", "rows": item.get("rows") or []}
        lay.addWidget(box("استعلام", imeta, idata), 1)
        lay.addWidget(box("حواله", vmeta, v["data"]), 1)
        btns = QHBoxLayout()
        yes = QPushButton("بله، استعلام حذف شود")
        no = QPushButton("خیر")
        yes.setStyleSheet("QPushButton{background:#DC2626;color:#fff;border:none;border-radius:10px;padding:10px 18px;font-weight:700;}")
        no.setStyleSheet("QPushButton{background:#E2E8F0;color:#0F172A;border:none;border-radius:10px;padding:10px 18px;font-weight:700;}")
        yes.clicked.connect(dlg.accept)
        no.clicked.connect(dlg.reject)
        btns.addWidget(yes)
        btns.addWidget(no)
        lay.addLayout(btns)
        if dlg.exec() == QDialog.Accepted:
            try:
                cur = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
                keep = [x for x in cur if _inq_key(x) != _inq_key(item)]
                try:
                    delete_inquiry_from_cloud(item)
                except Exception:
                    _swallow()
                INQUIRY_PATH.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")
                removed += 1
            except Exception:
                _swallow()
        else:
            declined.add("%s|%s" % (_inq_key(item), v["id"]))
            _save_declined(declined)
    if removed:
        try:
            schedule_supabase_sync()
        except Exception:
            _swallow()
    return removed


class InquiryPage(QWidget):
    """صفحه استعلام قیمت کالا — پارکت / ام‌دی‌اف / ام‌دی‌اف خام"""

    def __init__(self, win):
        super().__init__()
        self.current_saved_id = None  # id استعلام بارگذاری‌شده برای جلوگیری از ذخیره تکراری
        self.win = win
        self.current_tab = "parquet"
        self.row_widgets = []
        self.editing_id = None
        self.setLayoutDirection(Qt.RightToLeft)
        self.installEventFilter(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setStyleSheet(
            "QWidget{background:transparent;}"
            "QLineEdit{background:#FFFFFF;}"
            "QComboBox{background:#FFFFFF;}"
        )
        self.l = QVBoxLayout(content)
        self.l.setContentsMargins(24, 18, 24, 24)
        self.l.setSpacing(12)

        title = QLabel("استعلام قیمت کالا")
        title.setObjectName("pageTitle")
        self.l.addWidget(title)
        sub = QLabel("پارکت • ام‌دی‌اف • ام‌دی‌اف خام")
        sub.setObjectName("hint")
        self.l.addWidget(sub)

        # تب‌ها
        tabs = QHBoxLayout()
        self.tab_btns = {}
        for key, label in [("parquet", "پارکت"), ("mdf", "ام‌دی‌اف"), ("raw", "ام‌دی‌اف خام")]:
            b = QPushButton(label)
            b.setMinimumHeight(40)
            b.clicked.connect(lambda _, k=key: self.switch_tab(k))
            tabs.addWidget(b)
            self.tab_btns[key] = b
        self.l.addLayout(tabs)

        # خریدار
        buyer_box = QFrame()
        buyer_box.setProperty("class", "card")
        buyer_box.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;}"
            "QLabel{background:transparent;border:none;}"
            "QLineEdit,QComboBox{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:6px 8px;}"
            "QComboBox QAbstractItemView{background:#FFFFFF;}"
        )
        bf = QFormLayout(buyer_box)
        self.buyer_name = QComboBox()
        self.buyer_name.setEditable(True)
        self.buyer_name.setInsertPolicy(QComboBox.NoInsert)
        self.buyer_name.setMaxVisibleItems(12)
        self.buyer_name.currentTextChanged.connect(self.update_buyer_box_color)
        self.buyer_name.editTextChanged.connect(self.update_buyer_box_color)
        self.inquiry_date = QLineEdit()
        d, _ = now_jalali()
        self.inquiry_date.setText(fa_digits(d))
        self.inquiry_date.setAlignment(Qt.AlignCenter)
        self._wire_enter(self.buyer_name)
        self._wire_enter(self.inquiry_date)
        bf.addRow("نام خریدار:", self.buyer_name)
        bf.addRow("تاریخ:", self.inquiry_date)
        self.buyer_box = buyer_box
        self.reload_buyer_list()
        self.update_buyer_box_color()
        self.l.addWidget(buyer_box)

        # اقلام
        items_header = QHBoxLayout()
        items_header.addWidget(QLabel("اقلام کالا"))
        add_btn = QPushButton("+ افزودن ردیف")
        add_btn.setProperty("class", "secondaryButton")
        add_btn.clicked.connect(self.add_row)
        items_header.addStretch()
        items_header.addWidget(add_btn)
        self.l.addLayout(items_header)
        self.items_host = QVBoxLayout()
        self.items_host.setSpacing(8)
        self.l.addLayout(self.items_host)

        # جمع‌بندی
        sum_box = QFrame()
        sum_box.setProperty("class", "card")
        sum_box.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;}"
            "QLabel{background:transparent;border:none;}"
            "QLineEdit{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:6px 8px;}"
        )
        sf = QFormLayout(sum_box)
        self.warehouse = QLineEdit()
        self.transport = QLineEdit("به عهده مشتری می‌باشد")
        self.debt = MoneyLineEdit()
        self.debt.setText("0")
        self.discount = MoneyLineEdit()
        self.discount.setText("0")
        for w in (self.debt, self.discount):
            w.setAlignment(Qt.AlignCenter)
            w.textChanged.connect(self.recalc)
        for w in (self.warehouse, self.transport, self.debt, self.discount):
            self._wire_enter(w)
        sf.addRow("هزینه انبارداری:", self.warehouse)
        sf.addRow("هزینه حمل:", self.transport)
        sf.addRow("بدهی پیشین (ریال):", self.debt)
        sf.addRow("تخفیف (ریال):", self.discount)
        self.subtotal_lbl = QLabel("۰")
        self.total_lbl = QLabel("۰")
        self.total_words = QLabel("")
        self.total_lbl.setStyleSheet("font-size:18px;font-weight:700;color:#1565C0;")
        sf.addRow("جمع اقلام:", self.subtotal_lbl)
        sf.addRow("جمع کل:", self.total_lbl)
        sf.addRow("", self.total_words)
        self.l.addWidget(sum_box)

        note_box = QFrame()
        note_box.setProperty("class", "card")
        note_box.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;}"
            "QLabel{background:transparent;border:none;}"
            "QLineEdit{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:6px 8px;}"
        )
        nf = QFormLayout(note_box)
        self.validity = QLineEdit("اعتبار این استعلام کالا از تاریخ صدور تا پایان وقت اداری همان روز می‌باشد")
        self.shaba = QLineEdit("IR650120020000005081809111")
        self._wire_enter(self.validity)
        self._wire_enter(self.shaba)
        nf.addRow("اعتبار استعلام:", self.validity)
        nf.addRow("شماره شبا:", self.shaba)
        self.l.addWidget(note_box)

        actions = QHBoxLayout()
        primary_btn_css = (
            "QPushButton{background:#1565C0;color:#FFFFFF;border:none;border-radius:12px;"
            "font-size:14px;font-weight:700;padding:12px 16px;min-height:40px;}"
            "QPushButton:hover{background:#0D47A1;}"
            "QPushButton:disabled{background:#94A3B8;color:#E2E8F0;}"
        )
        pdf_btn = QPushButton("تولید PDF / چاپ")
        pdf_btn.setObjectName("primaryButton")
        pdf_btn.setCursor(Qt.PointingHandCursor)
        pdf_btn.setStyleSheet(primary_btn_css)
        pdf_btn.clicked.connect(self.print_inquiry)
        img_btn = QPushButton("خروجی تصویر")
        img_btn.setObjectName("primaryButton")
        img_btn.setCursor(Qt.PointingHandCursor)
        img_btn.setStyleSheet(primary_btn_css)
        img_btn.clicked.connect(self.export_inquiry_image)
        save_btn = QPushButton("ذخیره استعلام")
        save_btn.setProperty("class", "secondaryButton")
        save_btn.clicked.connect(self.save_inquiry)
        saved_btn = QPushButton("ذخیره‌شده‌ها")
        saved_btn.setProperty("class", "secondaryButton")
        saved_btn.clicked.connect(self.show_saved)
        final_btn = QPushButton("✓ تایید نهایی و ثبت حواله")
        final_btn.setStyleSheet(
            "QPushButton { background:#059669; color:white; border:none; border-radius:12px; "
            "font-size:14px; font-weight:700; padding:12px; }"
            "QPushButton:hover { background:#047857; }"
        )
        final_btn.clicked.connect(self.finalize_to_invoice)
        actions.addWidget(pdf_btn)
        actions.addWidget(img_btn)
        actions.addWidget(save_btn)
        actions.addWidget(saved_btn)
        final_btn.hide()   # ثبت حواله دستی حذف شد (حواله‌ها از اکسل فروش می‌آیند)
        self.l.addLayout(actions)
        self.l.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.switch_tab("parquet")

    def _install_buyer_completer(self, model):
        """پیشنهاد نام: هر بخشی از نام (در هر ترتیب) کافی است، نه فقط حرف‌های اول."""
        try:
            try:
                import name_completer as nc
            except Exception:
                from salesmate import name_completer as nc
            if getattr(self, "_buyer_proxy", None) is None:
                comp, proxy = nc.make_completer(self.buyer_name, model)
                comp.activated[str].connect(lambda t: self.buyer_name.setEditText(t))
                self._buyer_comp, self._buyer_proxy = comp, proxy
                le = self.buyer_name.lineEdit()
                if le is not None:
                    le.textEdited.connect(proxy.set_query)
            else:
                self._buyer_proxy.setSourceModel(model)
            # QComboBox.setModel مدل کامپلیتر را به مدل خام برمی‌گرداند؛ دوباره به proxy وصل کن
            self._buyer_comp.setModel(self._buyer_proxy)
            self.buyer_name.setCompleter(self._buyer_comp)
            le = self.buyer_name.lineEdit()
            if le is not None:
                le.setCompleter(self._buyer_comp)
        except Exception:
            _swallow()

    def reload_buyer_list(self):
        """لیست مشتریان با رنگ: بدهکار قرمز، طلبکار سبز"""
        from PySide6.QtGui import QStandardItemModel, QStandardItem
        current = self.buyer_name.currentText().strip()
        names = []
        try:
            c = db()
            rows = c.execute(
                "SELECT DISTINCT customer FROM invoices WHERE customer IS NOT NULL AND customer!='' ORDER BY customer"
            ).fetchall()
            c.close()
            names = [r[0] for r in rows if r[0]]
        except Exception:
            names = []
        model = QStandardItemModel()
        for name in names:
            item = QStandardItem(name)
            bal = customer_balance(name)
            if bal > 0:
                item.setForeground(QColor("#DC2626"))  # بدهکار قرمز
            elif bal < 0:
                item.setForeground(QColor("#16A34A"))  # طلبکار سبز
            model.appendRow(item)
        self.buyer_name.blockSignals(True)
        self.buyer_name.setModel(model)
        self._install_buyer_completer(model)
        if current:
            idx = self.buyer_name.findText(current)
            if idx >= 0:
                self.buyer_name.setCurrentIndex(idx)
            else:
                self.buyer_name.setEditText(current)
        else:
            self.buyer_name.setCurrentIndex(-1)
            self.buyer_name.setEditText("")
        self.buyer_name.blockSignals(False)
        self.update_buyer_box_color()

    def update_buyer_box_color(self, _t=None):
        """باکس اطلاعات خریدار: بدهکار قرمز / طلبکار سبز (فقط UI استعلام)"""
        if not hasattr(self, "buyer_box"):
            return
        name = self.buyer_name.currentText().strip()
        if not name:
            self.buyer_box.setStyleSheet("")
            return
        bal = customer_balance(name)
        if bal > 0:
            # بدهکار قرمز
            self.buyer_box.setStyleSheet(
                "QFrame { background:#FEF2F2; border:2px solid #DC2626; border-radius:12px; }"
            )
        elif bal < 0:
            # طلبکار سبز
            self.buyer_box.setStyleSheet(
                "QFrame { background:#F0FDF4; border:2px solid #16A34A; border-radius:12px; }"
            )
        else:
            self.buyer_box.setStyleSheet(
                "QFrame { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:12px; }"
            )

    def switch_tab(self, tab):

        self.current_tab = tab
        for k, b in self.tab_btns.items():
            if k == tab:
                b.setStyleSheet("background:#1565C0;color:white;border:none;border-radius:10px;padding:10px;font-weight:600;")
            else:
                b.setStyleSheet("background:#E2E8F0;color:#334155;border:none;border-radius:10px;padding:10px;")
        while self.items_host.count():
            item = self.items_host.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.row_widgets.clear()
        if tab == "mdf":
            self.validity.setText("اعتبار این استعلام کالا از تاریخ صدور تا ساعت ۱۱ همان روز می‌باشد")
            self.shaba.setVisible(True)
        else:
            self.validity.setText("اعتبار این استعلام کالا از تاریخ صدور تا پایان وقت اداری همان روز می‌باشد")
            self.shaba.setVisible(True)
        self.add_row()
        self.recalc()

    def _wire_enter(self, widget):
        """با Enter به فیلد بعدی برود"""
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if isinstance(obj, (QLineEdit, QComboBox)):
                if isinstance(obj, QComboBox) and obj.view().isVisible():
                    return super().eventFilter(obj, event)
                # روی قیمت واحد (متر مربع): ردیف جدید
                if isinstance(obj, QLineEdit) and obj.property("inqPriceField"):
                    self.add_row()
                    # فوکوس روی کد/اولین فیلد ردیف جدید
                    if self.row_widgets:
                        _, fields = self.row_widgets[-1]
                        for key in ("code", "type", "qty1"):
                            w = fields.get(key)
                            if w is not None and hasattr(w, "setFocus"):
                                w.setFocus()
                                break
                    return True
                self.focusNextChild()
                return True
        return super().eventFilter(obj, event)

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
            return widget

        if tab == "parquet":
            code = QLineEdit(); code.setPlaceholderText("کد کالا")
            typ = QComboBox(); typ.addItems(PRODUCT_OPTIONS)
            grade = QComboBox(); grade.addItems(GRADE_OPTIONS)
            qty1 = QLineEdit(); qty1.setPlaceholderText("کارتن"); qty1.setAlignment(Qt.AlignCenter)
            qty2 = QLineEdit(); qty2.setPlaceholderText("متراژ"); qty2.setReadOnly(True); qty2.setAlignment(Qt.AlignCenter)
            price = MoneyLineEdit(); price.setPlaceholderText("قیمت واحد"); price.setAlignment(Qt.AlignCenter)
            price.setProperty("inqPriceField", True)
            for w in (code, typ, grade, qty1, qty2, price):
                hl.addWidget(w)
            field("code", code); field("type", typ); field("grade", grade)
            field("qty1", qty1); field("qty2", qty2); field("price", price)

            def update_m():
                try:
                    c = float(en_digits(qty1.text()) or 0)
                except Exception:
                    c = 0
                tname = typ.currentText().strip()
                if tname not in PRODUCT_FACTORS:
                    qty2.setText("")
                    self.recalc()
                    return
                factor = PRODUCT_FACTORS.get(tname, 1.9608)
                qty2.setText(f"{c * factor:.4f}".rstrip("0").rstrip(".") if c else "")
                self.recalc()

            def style_egmont_choice():
                t = typ.currentText().strip()
                if typ.property("egmontNeedChoice"):
                    if t in EGMONT_OPTIONS:
                        typ.setStyleSheet("")
                        row.setStyleSheet(
                            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:10px;}"
                            "QLineEdit,QComboBox{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:4px 6px;}"
                            "QLabel{background:transparent;border:none;}"
                        )
                    else:
                        typ.setStyleSheet(
                            "QComboBox{background:#FFF7ED;border:2px solid #F97316;border-radius:8px;padding:4px 6px;}"
                        )
                        row.setStyleSheet(
                            "QFrame{background:#FFFBEB;border:2px solid #F59E0B;border-radius:10px;}"
                            "QLineEdit,QComboBox{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:4px 6px;}"
                            "QLabel{background:transparent;border:none;}"
                        )
                else:
                    typ.setStyleSheet("")

            def apply_code_product():
                """Egmont: دو گزینه بدون پیش‌فرض تا کاربر عمداً انتخاب کند."""
                raw = en_digits(code.text() or "").strip()
                key = "".join(ch for ch in raw if ch.isdigit())
                product = CODE_TO_PRODUCT.get(key)
                typ.blockSignals(True)
                if product == "Egmont":
                    cur = typ.currentText()
                    typ.clear()
                    typ.addItem("⚠ انتخاب کنید…")
                    typ.addItems(EGMONT_OPTIONS)
                    if cur in EGMONT_OPTIONS:
                        typ.setCurrentText(cur)
                    else:
                        typ.setCurrentIndex(0)
                    typ.setEnabled(True)
                    typ.setProperty("egmontNeedChoice", True)
                    typ.setToolTip("حتماً یکی را انتخاب کنید: Egmont=۱٫۸۶۹۶ | N Egmont=۱٫۹۶۰۸")
                elif product:
                    typ.clear()
                    typ.addItems(PRODUCT_OPTIONS)
                    idx = typ.findText(product)
                    if idx >= 0:
                        typ.setCurrentIndex(idx)
                    typ.setEnabled(False)
                    typ.setProperty("egmontNeedChoice", False)
                    typ.setToolTip("این کد به " + product + " مربوط است و قابل تغییر نیست")
                else:
                    typ.clear()
                    typ.addItems(PRODUCT_OPTIONS)
                    typ.setEnabled(True)
                    typ.setProperty("egmontNeedChoice", False)
                    typ.setToolTip("کد در لیست تعریف‌شده نیست؛ نوع را دستی انتخاب کنید")
                typ.blockSignals(False)
                style_egmont_choice()
                update_m()

            def on_type_changed():
                style_egmont_choice()
                update_m()

            code.textChanged.connect(apply_code_product)
            qty1.textChanged.connect(update_m)
            typ.currentIndexChanged.connect(on_type_changed)
            price.textChanged.connect(self.recalc)
        elif tab == "mdf":
            typ = QLineEdit(); typ.setPlaceholderText("نوع کالا")
            code = QLineEdit(); code.setPlaceholderText("کد")
            qty1 = QLineEdit(); qty1.setPlaceholderText("پالت"); qty1.setAlignment(Qt.AlignCenter)
            qty2 = QLineEdit(); qty2.setPlaceholderText("ورق"); qty2.setAlignment(Qt.AlignCenter)
            price = MoneyLineEdit(); price.setPlaceholderText("قیمت واحد"); price.setAlignment(Qt.AlignCenter)
            price.setProperty("inqPriceField", True)
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
            price.setProperty("inqPriceField", True)
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
        for k, w in fields.items():
            if k != "cost_lbl":
                self._wire_enter(w)
        self.recalc()

    def remove_row(self, row):
        self.row_widgets = [(w, f) for w, f in self.row_widgets if w is not row]
        row.deleteLater()
        self.recalc()

    def _egmont_unselected_rows(self):
        bad = []
        for i, (w, f) in enumerate(self.row_widgets, 1):
            typ_w = f.get("type")
            code_w = f.get("code")
            if not isinstance(typ_w, QComboBox):
                continue
            t = typ_w.currentText().strip()
            need = bool(typ_w.property("egmontNeedChoice"))
            if need and t not in EGMONT_OPTIONS:
                code = code_w.text().strip() if code_w is not None else ""
                bad.append(f"ردیف {fa_digits(i)}" + (f" (کد {fa_digits(code)})" if code else ""))
        return bad

    def _ensure_egmont_chosen(self, title="استعلام"):
        bad = self._egmont_unselected_rows()
        if not bad:
            return True
        msg = (
            "برای کدهای Egmont باید نوع را انتخاب کنید:\n"
            "• Egmont → متراژ ۱٫۸۶۹۶\n"
            "• N Egmont → متراژ ۱٫۹۶۰۸\n\n"
            + "\n".join(bad)
        )
        QMessageBox.warning(self, title, msg)
        return False

    def get_rows_data(self):
        rows = []
        for i, (w, f) in enumerate(self.row_widgets):
            data = {"index": i + 1}
            for k, widget in f.items():
                if k == "cost_lbl":
                    continue
                if isinstance(widget, QComboBox):
                    data[k] = widget.currentText()
                else:
                    data[k] = widget.text().strip()
            try:
                q2s = en_digits(str(data.get("qty2") or "0")).replace(",", "").replace("٬", "").replace("،", "").strip()
                qty2 = float(q2s or 0)
            except Exception:
                qty2 = 0
            # قیمت با جداکننده هزارگان / ارقام فارسی
            try:
                price = float(clean_number(data.get("price") or "0") or 0)
            except Exception:
                price = 0
            data["cost"] = int(round(qty2 * price))
            rows.append(data)
        return rows

    def recalc(self):
        rows = self.get_rows_data()
        subtotal = 0
        for (w, f), r in zip(self.row_widgets, rows):
            subtotal += r["cost"]
            f["cost_lbl"].setText(fmt(r["cost"]))
        try:
            debt = amount(self.debt.text())
        except Exception:
            debt = 0
        try:
            disc = amount(self.discount.text())
        except Exception:
            disc = 0
        total = subtotal + debt - disc
        self.subtotal_lbl.setText(fmt(subtotal))
        self.total_lbl.setText(fmt(total))
        self.total_words.setText(number_to_persian_words(total) + " ریال")

    def _inquiry_snapshot(self):
        """وضعیت فعلی فرم استعلام برای ذخیره / ثبت حواله"""
        rows = self.get_rows_data()
        sub = sum(r["cost"] for r in rows)
        return {
            "tab": self.current_tab,
            "buyer": self.buyer_name.currentText().strip(),
            "date": en_digits(self.inquiry_date.text().strip()),
            "rows": rows,
            "warehouse": self.warehouse.text(),
            "transport": self.transport.text(),
            "debt": en_digits(self.debt.text()),
            "discount": en_digits(self.discount.text()),
            "validity": self.validity.text(),
            "shaba": self.shaba.text(),
            "total": sub + amount(self.debt.text()) - amount(self.discount.text()),
        }

    def _inquiry_fingerprint(self, data):
        """امضای محتوا برای تشخیص استعلام تکراری (بدون id/savedAt)."""
        key = {
            "tab": data.get("tab"),
            "buyer": (data.get("buyer") or "").strip(),
            "date": en_digits(str(data.get("date") or "")).strip(),
            "warehouse": data.get("warehouse") or "",
            "transport": data.get("transport") or "",
            "debt": str(data.get("debt") or "0"),
            "discount": str(data.get("discount") or "0"),
            "validity": data.get("validity") or "",
            "shaba": data.get("shaba") or "",
            "total": data.get("total"),
            "rows": data.get("rows") or [],
        }
        return json.dumps(key, ensure_ascii=False, sort_keys=True, default=str)

    def save_inquiry(self, silent=False):
        """اگر محتوا تغییر نکرده باشد تکراری ذخیره نمی‌شود؛ اگر تغییر کرده باشد رکورد جدید."""
        if not self.buyer_name.currentText().strip():
            if not silent:
                QMessageBox.warning(self, "استعلام", "نام خریدار را وارد کنید.")
            return False
        data = self._inquiry_snapshot()
        data["savedAt"] = datetime.now().isoformat(timespec="seconds")
        fp = self._inquiry_fingerprint(data)
        try:
            lst = []
            if INQUIRY_PATH.exists():
                lst = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
            if not isinstance(lst, list):
                lst = []

            # اگر دقیقاً همین محتوا قبلاً ذخیره شده → هیچ ردیف جدیدی نساز
            for item in lst:
                if self._inquiry_fingerprint(item) == fp:
                    self.current_saved_id = item.get("id")
                    if not silent:
                        QMessageBox.information(
                            self, "استعلام",
                            "این استعلام قبلاً ذخیره شده و تغییری نداشته؛ تکراری ثبت نشد."
                        )
                    return True

            # محتوا جدید یا تغییر کرده → ذخیره به‌عنوان استعلام جدید
            data["id"] = int(datetime.now().timestamp() * 1000)
            self.current_saved_id = data["id"]
            lst.insert(0, data)
            lst = lst[:50]
            INQUIRY_PATH.write_text(json.dumps(lst, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                schedule_supabase_sync()
            except Exception:
                _swallow()
            if not silent:
                QMessageBox.information(self, "استعلام", "استعلام جدید ذخیره شد.")
            return True
        except Exception as ex:
            if not silent:
                QMessageBox.critical(self, "خطا", str(ex))
            return False


    def _remove_saved_inquiry_after_finalize(self, snap=None):
        """بعد از تایید نهایی، استعلام متناظر را از لیست ذخیره‌شده‌ها حذف کن."""
        try:
            if not INQUIRY_PATH.exists():
                self.current_saved_id = None
                return
            lst = json.loads(INQUIRY_PATH.read_text(encoding="utf-8"))
            if not isinstance(lst, list) or not lst:
                self.current_saved_id = None
                return

            target_id = getattr(self, "current_saved_id", None)
            form_snap = self._inquiry_snapshot()
            form_fp = self._inquiry_fingerprint(form_snap)

            # fingerprint بدون تاریخ (چون تاریخ حواله ممکن است امروز باشد)
            def fp_no_date(d):
                key = {
                    "tab": d.get("tab"),
                    "buyer": (d.get("buyer") or "").strip(),
                    "warehouse": d.get("warehouse") or "",
                    "transport": d.get("transport") or "",
                    "debt": str(d.get("debt") or "0"),
                    "discount": str(d.get("discount") or "0"),
                    "validity": d.get("validity") or "",
                    "shaba": d.get("shaba") or "",
                    "total": d.get("total"),
                    "rows": d.get("rows") or [],
                }
                return json.dumps(key, ensure_ascii=False, sort_keys=True, default=str)

            form_fp2 = fp_no_date(form_snap)
            new_lst = []
            removed = 0
            for item in lst:
                if target_id is not None and item.get("id") == target_id:
                    removed += 1
                    continue
                if self._inquiry_fingerprint(item) == form_fp:
                    removed += 1
                    continue
                if fp_no_date(item) == form_fp2:
                    removed += 1
                    continue
                new_lst.append(item)

            if removed:
                # حذف از ابر برای مواردی که از لیست خارج شدند
                try:
                    for item in lst:
                        if item not in new_lst:
                            try:
                                delete_inquiry_from_cloud(item)
                            except Exception:
                                _swallow()
                except Exception:
                    _swallow()
                INQUIRY_PATH.write_text(
                    json.dumps(new_lst, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                try:
                    schedule_supabase_sync()
                except Exception:
                    _swallow()
            self.current_saved_id = None
        except Exception:
            try:
                self.current_saved_id = None
            except Exception:
                _swallow()

    def show_saved(self):
        ask_prune_saved_inquiries(self)
        try:
            lst = json.loads(INQUIRY_PATH.read_text(encoding="utf-8")) if INQUIRY_PATH.exists() else []
        except Exception:
            lst = []
        if not lst:
            QMessageBox.information(self, "ذخیره‌شده‌ها", "موردی ذخیره نشده است.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("استعلام‌های ذخیره‌شده")
        dlg.resize(480, 400)
        dlg.setLayoutDirection(Qt.RightToLeft)
        vl = QVBoxLayout(dlg)
        listw = QListWidget()
        for item in lst:
            tab_fa = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}.get(item.get("tab"), "")
            listw.addItem(f"{item.get('buyer','—')} | {tab_fa} | {fa_digits(item.get('date',''))} | {fmt(item.get('total',0))}")
        vl.addWidget(listw)
        btns = QHBoxLayout()
        load_b = QPushButton("بارگذاری")
        del_b = QPushButton("حذف")
        close_b = QPushButton("بستن")
        btns.addWidget(load_b); btns.addWidget(del_b); btns.addWidget(close_b)
        vl.addLayout(btns)

        def do_load():
            i = listw.currentRow()
            if i < 0:
                return
            self.load_inquiry(lst[i])
            dlg.accept()

        def do_del():
            i = listw.currentRow()
            if i < 0:
                return
            if QMessageBox.question(dlg, "حذف", "حذف شود؟\nاز ابر و بقیه دستگاه‌ها هم حذف می‌شود.") != QMessageBox.Yes:
                return
            removed = lst.pop(i)
            try:
                delete_inquiry_from_cloud(removed)
            except Exception:
                _swallow()
            INQUIRY_PATH.write_text(json.dumps(lst, ensure_ascii=False, indent=2), encoding="utf-8")
            try:
                schedule_supabase_sync()
            except Exception:
                _swallow()
            listw.takeItem(i)

        load_b.clicked.connect(do_load)
        del_b.clicked.connect(do_del)
        close_b.clicked.connect(dlg.reject)
        dlg.exec()

    def load_inquiry(self, item):
        self.current_saved_id = item.get("id")
        self.switch_tab(item.get("tab") or "parquet")
        self.buyer_name.setEditText(item.get("buyer") or "")
        self.inquiry_date.setText(fa_digits(item.get("date") or ""))
        self.warehouse.setText(item.get("warehouse") or "")
        self.transport.setText(item.get("transport") or "به عهده مشتری می‌باشد")
        self.debt.setText(str(item.get("debt") or "0"))
        self.discount.setText(str(item.get("discount") or "0"))
        self.validity.setText(item.get("validity") or "")
        self.shaba.setText(item.get("shaba") or "")
        while self.items_host.count():
            it = self.items_host.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.row_widgets.clear()
        for r in item.get("rows") or []:
            self.add_row()
            _, fields = self.row_widgets[-1]
            for k, widget in fields.items():
                if k == "cost_lbl" or k not in r:
                    continue
                val = r[k]
                if isinstance(widget, QComboBox):
                    idx = widget.findText(str(val))
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                else:
                    widget.setText(str(val) if val is not None else "")
        if not item.get("rows"):
            self.add_row()
        self.recalc()

    def _normalize_customer_name(self, name: str) -> str:
        """حذف القاب رایج برای تطبیق بهتر نام مشتری"""
        n = (name or "").strip()
        for prefix in (
            "جناب آقای", "جناب خانم", "سرکار خانم", "جناب آقا",
            "آقای", "خانم", "جناب", "آقا", "شرکت", "فروشگاه",
        ):
            if n.startswith(prefix):
                n = n[len(prefix):].strip()
                break
        # فاصله‌های اضافه
        n = " ".join(n.split())
        return n

    def _existing_customers(self):
        c = db()
        rows = c.execute(
            "SELECT customer, COUNT(*) FROM invoices GROUP BY customer ORDER BY customer"
        ).fetchall()
        c.close()
        return [r[0] for r in rows if r[0]]

    def _suggest_customer(self, buyer: str):
        """پیشنهاد نزدیک‌ترین نام از مشتریان قبلی"""
        existing = self._existing_customers()
        if not existing:
            return buyer, existing
        # اگر دقیقاً از لیست انتخاب شده، همان بماند
        for name in existing:
            if name == buyer:
                return name, existing
        norm = self._normalize_customer_name(buyer).casefold()
        for name in existing:
            if self._normalize_customer_name(name).casefold() == norm:
                return name, existing
        for name in existing:
            nn = self._normalize_customer_name(name).casefold()
            if norm and (norm in nn or nn in norm):
                return name, existing
        return buyer, existing

    def finalize_to_invoice(self):
        """تایید نهایی استعلام → ثبت حواله با شماره دستی و انتخاب نام مشتری"""
        try:
            if self.win is not None and not self.win.manual_invoice_ok():
                return
        except Exception:
            pass
        if not self._ensure_egmont_chosen("تایید نهایی"):
            return
        rows = self.get_rows_data()
        if not rows or all(not r.get("cost") for r in rows):
            QMessageBox.warning(self, "تایید نهایی", "حداقل یک ردیف با مقدار و قیمت وارد کنید.")
            return
        buyer = self.buyer_name.currentText().strip()
        if not buyer:
            QMessageBox.warning(self, "تایید نهایی", "نام خریدار را وارد کنید.")
            return

        subtotal = sum(r["cost"] for r in rows)
        debt = amount(self.debt.text())
        disc = amount(self.discount.text())
        total = subtotal + debt - disc
        if total <= 0:
            QMessageBox.warning(self, "تایید نهایی", "مبلغ کل باید بیشتر از صفر باشد.")
            return

        suggested, customers = self._suggest_customer(buyer)

        dlg = QDialog(self)
        dlg.setWindowTitle("تایید نهایی — ثبت حواله")
        dlg.setLayoutDirection(Qt.RightToLeft)
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        info = QLabel(
            f"مبلغ قابل ثبت: <b>{fmt(total)}</b> ریال<br/>"
            f"نام واردشده در استعلام: <b>{buyer}</b>"
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        form = QFormLayout()
        inv_no = QLineEdit()
        inv_no.setPlaceholderText("شماره حواله را وارد کنید")
        inv_no.setAlignment(Qt.AlignCenter)

        cust = QComboBox()
        cust.setEditable(True)
        cust.setInsertPolicy(QComboBox.NoInsert)
        # اول پیشنهاد، بعد بقیه
        seen = set()
        ordered = []
        for n in [suggested, buyer] + customers:
            if n and n not in seen:
                seen.add(n)
                ordered.append(n)
        cust.addItems(ordered)
        if suggested:
            idx = cust.findText(suggested)
            if idx >= 0:
                cust.setCurrentIndex(idx)
            else:
                cust.setEditText(suggested)

        date_edit = QLineEdit(fa_digits(now_jalali()[0]))  # تاریخ امروز، نه تاریخ استعلام
        date_edit.setAlignment(Qt.AlignCenter)
        total_lbl = QLabel(fmt(total))
        total_lbl.setStyleSheet("font-size:16px;font-weight:700;color:#059669;")

        paid_edit = MoneyLineEdit()
        paid_edit.setText(fmt(total).replace("٬", ","))  # will reformat
        # نمایش با جداکننده هزارگان
        paid_edit.blockSignals(True)
        paid_edit.setText(f"{int(total):,}")
        paid_edit.blockSignals(False)
        paid_edit.setAlignment(Qt.AlignCenter)
        paid_edit.setStyleSheet("font-size:16px;font-weight:700;color:#059669;padding:6px;")
        paid_edit.setPlaceholderText("مبلغ پرداختی")

        form.addRow("شماره حواله:", inv_no)
        form.addRow("نام مشتری (نهایی):", cust)
        form.addRow("تاریخ:", date_edit)
        form.addRow("مبلغ کل:", total_lbl)
        form.addRow("مبلغ پرداختی:", paid_edit)
        lay.addLayout(form)

        hint = QLabel(
            "اگر نام استعلام با مشتری قبلی فرق دارد، از لیست همان مشتری قبلی را انتخاب کنید "
            "تا رنگ و گزارش‌ها درست بماند."
        )
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        lay.addWidget(hint)

        buttons = QDialogButtonBox()
        ok_b = buttons.addButton("ثبت حواله", QDialogButtonBox.AcceptRole)
        cancel_b = buttons.addButton("انصراف", QDialogButtonBox.RejectRole)
        ok_b.clicked.connect(dlg.accept)
        cancel_b.clicked.connect(dlg.reject)
        lay.addWidget(buttons)

        inv_no.setFocus()
        if dlg.exec() != QDialog.Accepted:
            return

        invoice_no = en_digits(inv_no.text().strip())
        customer = cust.currentText().strip()
        date = en_digits(date_edit.text().strip())
        paid_val = amount(paid_edit.text())
        if not invoice_no:
            QMessageBox.warning(self, "تایید نهایی", "شماره حواله الزامی است.")
            return
        if not customer:
            QMessageBox.warning(self, "تایید نهایی", "نام مشتری الزامی است.")
            return
        if not date:
            date = now_jalali()[0]

        # ساعت فعلی
        from datetime import datetime as _dt
        time_str = _dt.now().strftime("%H:%M:%S")

        # ذخیره جزئیات استعلام روی حواله برای باز کردن PDF بعداً
        snap = self._inquiry_snapshot()
        snap["buyer"] = customer  # نام نهایی انتخاب‌شده
        snap["date"] = date
        snap["total"] = int(total)
        snap["paid_amount"] = int(paid_val)
        try:
            c = db()
            c.execute(
                "INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,image_path,inquiry_data,paid_amount) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    customer,
                    invoice_no,
                    date,
                    time_str,
                    str(int(total)),
                    _dt.now().isoformat(timespec="seconds"),
                    "",
                    json.dumps(snap, ensure_ascii=False),
                    str(int(paid_val)),
                ),
            )
            c.commit()
            c.close()
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"ثبت حواله انجام نشد:\n{ex}")
            return

        # حذف از استعلام‌های ذخیره‌شده (با fingerprint یا id بارگذاری‌شده)
        try:
            self._remove_saved_inquiry_after_finalize(snap)
            try:
                schedule_supabase_sync()
            except Exception:
                _swallow()
        except Exception:
            _swallow()

        QMessageBox.information(
            self, "تایید نهایی",
            f"حواله شماره {fa_digits(invoice_no)} برای «{customer}» ثبت شد."
        )
        try:
            self.win.refresh_all()
            self.win.invoices()
        except Exception:
            _swallow()

    def export_inquiry_image(self):
        """ذخیره فایل PNG واقعی با ظاهر نزدیک به PDF ایزوفام"""
        if not self._ensure_egmont_chosen("خروجی تصویر"):
            return
        rows = self.get_rows_data()
        if not rows or all(not r.get("cost") for r in rows):
            QMessageBox.warning(self, "استعلام", "حداقل یک ردیف با مقدار و قیمت وارد کنید.")
            return
        self.save_inquiry(silent=True)
        data = self._inquiry_snapshot()

        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیره تصویر استعلام", "estelam.png", "PNG (*.png)"
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"

        try:
            ok = InquiryPage.render_inquiry_png(data, path)
            if ok:
                QMessageBox.information(self, "خروجی تصویر", f"فایل تصویر ذخیره شد:\n{path}")
            else:
                QMessageBox.critical(self, "خطا", "ذخیره تصویر انجام نشد.")
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"خروجی تصویر انجام نشد:\n{ex}")

    @staticmethod
    def render_inquiry_png(data: dict, path: str) -> bool:
        """رندر استعلام PNG با ظاهر نزدیک PDF؛ کد کالا بدون جداکننده هزارگان"""
        def pnum(val, decimals=None, no_sep=False):
            if val is None or val == "":
                return ""
            s = en_digits(str(val)).replace(",", "").replace("٬", "").replace(" ", "").strip()
            try:
                num = float(s)
            except Exception:
                return fa_digits(str(val))
            if no_sep:
                # کد کالا و مقادیر خام بدون جداکننده
                if decimals is not None:
                    t = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
                elif abs(num - round(num)) < 1e-9:
                    t = str(int(round(num)))
                else:
                    t = f"{num:.4f}".rstrip("0").rstrip(".")
                return fa_digits(t)
            if decimals is not None:
                t = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
            elif abs(num - round(num)) < 1e-9:
                t = f"{int(round(num)):,}"
            else:
                t = f"{num:.4f}".rstrip("0").rstrip(".")
            return fa_digits(t)

        tab = data.get("tab") or "parquet"
        rows = data.get("rows") or []
        buyer = data.get("buyer") or "—"
        date_fa = fa_digits(en_digits(data.get("date") or "—"))
        tab_fa = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}.get(tab, "")
        subtotal = sum(int(r.get("cost") or 0) for r in rows)
        debt = amount(data.get("debt") or 0)
        disc = amount(data.get("discount") or 0)
        total = amount(data.get("total")) if data.get("total") not in (None, "") else (subtotal + debt - disc)
        warehouse = data.get("warehouse") or "—"
        transport = data.get("transport") or "به عهده مشتری می‌باشد"
        validity = data.get("validity") or ""
        shaba = data.get("shaba") or ""

        if tab == "parquet":
            headers = ["ردیف", "کد کالا", "نوع کالا", "گرید", "مقدار (کارتن)", "مقدار (متراژ)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]
            def row_cells(r, i):
                return [
                    pnum(r.get("index", i + 1), no_sep=True),
                    pnum(r.get("code"), no_sep=True),  # کد بدون جداکننده
                    r.get("type") or "",
                    r.get("grade") or "",
                    pnum(core.qty_int(r.get("qty1")), no_sep=True),
                    pnum(r.get("qty2"), 4, no_sep=True),
                    pnum(r.get("price")),
                    pnum(r.get("cost")),
                ]
            col_w = [0.06, 0.10, 0.15, 0.08, 0.12, 0.13, 0.17, 0.19]
        elif tab == "mdf":
            headers = ["ردیف", "نوع کالا", "کد", "مقدار (پالت)", "مقدار (ورق)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]
            def row_cells(r, i):
                return [
                    pnum(r.get("index", i + 1), no_sep=True),
                    r.get("type") or "",
                    pnum(r.get("code"), no_sep=True),
                    pnum(core.qty_int(r.get("qty1")), no_sep=True),
                    pnum(r.get("qty2"), no_sep=True),
                    pnum(r.get("price")),
                    pnum(r.get("cost")),
                ]
            col_w = [0.07, 0.16, 0.12, 0.13, 0.13, 0.18, 0.21]
        else:
            headers = ["ردیف", "نوع کالا", "سایز", "مقدار (پالت)", "مقدار (ورق)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]
            def row_cells(r, i):
                return [
                    pnum(r.get("index", i + 1), no_sep=True),
                    r.get("type") or "",
                    r.get("size") or "",
                    pnum(core.qty_int(r.get("qty1")), no_sep=True),
                    pnum(r.get("qty2"), no_sep=True),
                    pnum(r.get("price")),
                    pnum(r.get("cost")),
                ]
            col_w = [0.07, 0.16, 0.12, 0.13, 0.13, 0.18, 0.21]

        # رندر با وضوح بالاتر (2x) تا اعداد مثل PDF واضح باشند
        scale = 2
        W = 1100
        margin = 24
        blue = QColor("#1565C0")
        blue_soft = QColor("#e0f2fe")
        blue_light = QColor("#f0f9ff")
        text_dark = QColor("#1e293b")
        text_muted = QColor("#64748b")
        white = QColor("#ffffff")

        row_h = 42
        h = 50 + 110 + 80 + 20 + 40 + len(rows) * row_h + 30 + 5 * 36 + 120 + 180 + 40
        img = QImage(W * scale, h * scale, QImage.Format_ARGB32)
        img.fill(white)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        try:
            p.setRenderHint(QPainter.LosslessImageRendering, True)
        except Exception:
            _swallow()
        p.scale(scale, scale)

        def make_font(size, bold=False):
            # فونت‌هایی که ارقام فارسی/لاتین را واضح‌تر نشان می‌دهند (شبیه مرورگر PDF)
            families = [
                "Vazirmatn", "Segoe UI", "Tahoma", "Arial", "DejaVu Sans", "Sans Serif"
            ]
            f = QFont()
            f.setFamilies(families)
            f.setPointSize(size)
            if bold:
                f.setWeight(QFont.Bold)
            f.setStyleStrategy(QFont.PreferAntialias)
            f.setHintingPreference(QFont.PreferFullHinting)
            f.setStyleHint(QFont.SansSerif)
            return f

        font = make_font(12)
        font_b = make_font(12, True)
        font_sm = make_font(10)
        font_md = make_font(13, True)
        font_lg = make_font(16, True)
        font_xl = make_font(22, True)
        font_code = make_font(13, True)

        # ---- هدر ساده بدون برند ----
        header_h = 56
        p.fillRect(0, 0, W, header_h, blue)
        p.setPen(white)
        p.setFont(font_lg)
        p.drawText(QRect(margin, 12, W // 2, 32), Qt.AlignRight | Qt.AlignVCenter, "استعلام قیمت کالا")
        p.setFont(font_sm)
        p.setPen(QColor("#e0f2fe"))
        p.drawText(QRect(margin, 12, W - margin * 2, 32), Qt.AlignLeft | Qt.AlignVCenter, tab_fa)
        y = header_h + 16

        # ---- کارت‌های خریدار و تاریخ (مثل PDF) ----
        card_h = 70
        gap = 14
        content_w = W - margin * 2
        buyer_w = int(content_w * 0.58)
        date_w = content_w - buyer_w - gap
        p.setBrush(blue)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(W - margin - buyer_w, y, buyer_w, card_h, 14, 14)
        p.drawRoundedRect(margin, y, date_w, card_h, 14, 14)
        p.setPen(QColor("#bae6fd"))
        p.setFont(font_sm)
        p.drawText(QRect(W - margin - buyer_w + 16, y + 10, buyer_w - 32, 18), Qt.AlignRight, "نام خریدار")
        p.drawText(QRect(margin + 16, y + 10, date_w - 32, 18), Qt.AlignRight, "تاریخ")
        p.setPen(white)
        p.setFont(font_lg)
        p.drawText(QRect(W - margin - buyer_w + 16, y + 32, buyer_w - 32, 30), Qt.AlignRight | Qt.AlignVCenter, buyer)
        p.drawText(QRect(margin + 16, y + 32, date_w - 32, 30), Qt.AlignLeft | Qt.AlignVCenter, date_fa)
        y += card_h + 16

        # ---- جدول داخل قاب ----
        table_x = margin
        table_w = content_w
        header_row_h = 36
        # قاب جدول
        table_top = y
        table_body_h = header_row_h + len(rows) * row_h
        p.setBrush(white)
        p.setPen(QPen(QColor("#bae6fd"), 1))
        p.drawRoundedRect(table_x, table_top, table_w, table_body_h + 2, 12, 12)

        # هدر جدول
        p.setBrush(blue)
        p.setPen(Qt.NoPen)
        # clip-ish: fill header area
        p.drawRect(table_x + 1, y + 1, table_w - 2, header_row_h)
        p.setPen(white)
        p.setFont(font_sm)
        x = table_x + table_w
        for hdr, frac in zip(headers, col_w):
            cw = int(table_w * frac)
            x -= cw
            p.drawText(QRect(x, y, cw, header_row_h), Qt.AlignCenter, hdr)
        y += header_row_h

        for idx, r in enumerate(rows):
            bg = blue_light if idx % 2 == 0 else white
            p.fillRect(table_x + 1, y, table_w - 2, row_h, bg)
            cells = row_cells(r, idx)
            x = table_x + table_w
            for ci, (cell, frac) in enumerate(zip(cells, col_w)):
                cw = int(table_w * frac)
                x -= cw
                # کد کالا بولد و کمی بزرگ‌تر
                if tab == "parquet" and ci == 1:
                    p.setFont(font_code)
                    p.setPen(text_dark)
                elif tab == "mdf" and ci == 2:
                    p.setFont(font_code)
                    p.setPen(text_dark)
                else:
                    p.setFont(QFont("Tahoma", 10))
                    p.setPen(text_dark)
                p.drawText(QRect(x + 2, y, cw - 4, row_h), Qt.AlignCenter, str(cell))
            # خط زیر ردیف
            p.setPen(QPen(QColor("#e0f2fe"), 1))
            p.drawLine(table_x + 1, y + row_h - 1, table_x + table_w - 1, y + row_h - 1)
            y += row_h

        y += 16

        # ---- خلاصه مبالغ در باکس‌های یک‌درمیان ----
        summary = [
            ("مبلغ کل اقلام", pnum(subtotal), True),
            ("هزینه انبارداری", warehouse if warehouse else "—", False),
            ("هزینه حمل", transport, True),
            ("بدهی پیشین", pnum(debt) if debt else "", False),
            ("تخفیف", pnum(disc) if disc else "", True),
        ]
        sum_h = 32
        for label, val, alt in summary:
            if alt:
                p.fillRect(margin, y, content_w, sum_h, blue_light)
            p.setPen(text_muted)
            p.setFont(font_sm)
            p.drawText(QRect(margin + content_w // 2, y, content_w // 2 - 10, sum_h), Qt.AlignRight | Qt.AlignVCenter, label)
            p.setPen(text_dark)
            p.setFont(font_b if label == "مبلغ کل اقلام" else font)
            p.drawText(QRect(margin + 10, y, content_w // 2 - 10, sum_h), Qt.AlignLeft | Qt.AlignVCenter, str(val))
            y += sum_h

        y += 14

        # ---- باکس جمع کل ----
        total_h = 96
        p.setBrush(blue)
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(margin, y, content_w, total_h, 16, 16)
        p.setPen(QColor("#bae6fd"))
        p.setFont(font_sm)
        p.drawText(QRect(margin + 18, y + 12, content_w - 36, 20), Qt.AlignRight, "جمع کل قابل پرداخت")
        p.setPen(white)
        p.setFont(font_xl)
        p.drawText(QRect(margin + 18, y + 34, content_w - 36, 32), Qt.AlignLeft | Qt.AlignVCenter, pnum(total) + "  ریال")
        p.setFont(font)
        p.setPen(QColor("#e0f2fe"))
        p.drawText(QRect(margin + 18, y + 68, content_w - 36, 22), Qt.AlignRight, number_to_persian_words(total) + " ریال")
        y += total_h + 14

        # ---- شرایط در باکس ----
        terms_lines = [
            "• پس از واریز مبلغ به حساب شرکت و تأیید واحد حسابداری، حواله خروج بار صادر می‌گردد.",
            "• پس از خروج کالا از انبار شرکت هیچ مسئولیتی از لحاظ کمیت و کیفیت/سلامت کالا ندارد.",
            "• پس از فروش کالا به هیچ عنوان مرجوعی و ابطال حواله انجام نمی‌شود.",
        ]
        if validity:
            terms_lines.append(validity)
        if shaba:
            terms_lines.append("شماره شبا بانک ملت: " + shaba)
        terms_h = 28 + len(terms_lines) * 22 + 16
        p.setBrush(QColor("#f8fafc"))
        p.setPen(QPen(QColor("#e2e8f0"), 1))
        p.drawRoundedRect(margin, y, content_w, terms_h, 14, 14)
        p.setPen(blue)
        p.setFont(font_b)
        p.drawText(QRect(margin + 16, y + 10, content_w - 32, 22), Qt.AlignRight, "شرایط و نکات مهم")
        p.setPen(text_muted)
        p.setFont(font_sm)
        ty = y + 36
        for line in terms_lines:
            color = blue if "شبا" in line else text_muted
            if validity and line == validity:
                color = text_dark
            p.setPen(color)
            p.drawText(QRect(margin + 16, ty, content_w - 32, 20), Qt.AlignRight | Qt.AlignVCenter, line)
            ty += 22

        p.end()
        final_h = min(y + terms_h + 24, h)
        # تصویر با scale=2 رندر شده؛ برش در مختصات پیکسل واقعی
        cropped = img.copy(0, 0, W * scale, final_h * scale)
        # برای حجم کمتر می‌توان نصف کرد، اما وضوح بالا می‌ماند
        return cropped.save(path, "PNG")

    def print_inquiry(self):

        """خروجی استعلام مثل نسخه وب — HTML در مرورگر (چاپ/PDF با کیفیت)"""
        if not self._ensure_egmont_chosen("تولید PDF"):
            return
        rows = self.get_rows_data()
        if not rows or all(not r.get("cost") for r in rows):
            QMessageBox.warning(self, "استعلام", "حداقل یک ردیف با مقدار و قیمت وارد کنید.")
            return
        self.save_inquiry(silent=True)
        data = self._inquiry_snapshot()
        try:
            html = InquiryPage.build_inquiry_html_static(data)
            out = APP_DIR / "estelam_print.html"
            out.write_text(html, encoding="utf-8")
            webbrowser.open(out.as_uri())
            QMessageBox.information(
                self, "استعلام",
                "صفحه استعلام در مرورگر باز شد و استعلام ذخیره شد.\n"
                "برای PDF: چاپ → Save as PDF و Background graphics را فعال کنید."
            )
        except Exception as ex:
            QMessageBox.critical(self, "خطا", f"باز کردن خروجی انجام نشد:\n{ex}")

    @staticmethod
    def build_inquiry_html_static(data: dict) -> str:
        """ساخت HTML استعلام از دیکشنری داده (فرم یا حواله)"""
        def only_fa_digits(s):
            return fa_digits(str(s)) if s is not None else ""

        def to_fa_num(val, decimals=None):
            if val is None or val == "":
                return ""
            s = en_digits(str(val)).replace(",", "").replace("٬", "").replace(" ", "").strip()
            try:
                num = float(s)
            except Exception:
                return only_fa_digits(val)
            if decimals is not None:
                formatted = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
            elif abs(num - round(num)) < 1e-9:
                formatted = f"{int(round(num)):,}"
            else:
                formatted = f"{num:.4f}".rstrip("0").rstrip(".")
            parts = formatted.split(".")
            if parts[0].replace(",", "").isdigit():
                parts[0] = f"{int(parts[0].replace(',','')):,}".replace(",", "٬")
            return fa_digits(".".join(parts)).replace(".", "٫")

        tab = data.get("tab") or "parquet"
        rows = data.get("rows") or []
        buyer = data.get("buyer") or "—"
        date_fa = only_fa_digits(en_digits(data.get("date") or "—"))
        tab_fa = {"parquet": "پارکت", "mdf": "ام‌دی‌اف", "raw": "ام‌دی‌اف خام"}.get(tab, "")
        subtotal = sum(int(r.get("cost") or 0) for r in rows)
        debt = amount(data.get("debt") or 0)
        disc = amount(data.get("discount") or 0)
        total = amount(data.get("total")) if data.get("total") not in (None, "") else (subtotal + debt - disc)
        warehouse = data.get("warehouse") or ""
        transport = data.get("transport") or "به عهده مشتری می‌باشد"
        validity = data.get("validity") or ""
        shaba = data.get("shaba") or ""

        if tab == "parquet":
            headers = ["ردیف", "کد کالا", "نوع کالا", "گرید", "مقدار (کارتن)", "مقدار (متراژ)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]
        elif tab == "mdf":
            headers = ["ردیف", "نوع کالا", "کد", "مقدار (پالت)", "مقدار (ورق)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]
        else:
            headers = ["ردیف", "نوع کالا", "سایز", "مقدار (پالت)", "مقدار (ورق)", "قیمت واحد (ریال)", "هزینه کالا (ریال)"]

        headers_html = "".join(
            f'<th style="padding:8px 5px;background:#1565C0;color:white;font-weight:600;font-size:11px;text-align:center;border:none;">{h}</th>'
            for h in headers
        )
        rows_html = []
        for idx, r in enumerate(rows):
            if tab == "parquet":
                cells = [
                    to_fa_num(r.get("index", idx + 1)),
                    f'<span style="font-size:15px;font-weight:700;">{only_fa_digits(r.get("code") or "")}</span>',
                    r.get("type") or "",
                    r.get("grade") or "",
                    to_fa_num(core.qty_int(r.get("qty1"))),
                    to_fa_num(r.get("qty2"), 4),
                    to_fa_num(r.get("price")),
                    to_fa_num(r.get("cost")),
                ]
            elif tab == "mdf":
                cells = [
                    to_fa_num(r.get("index", idx + 1)),
                    r.get("type") or "",
                    f'<span style="font-size:15px;font-weight:700;">{only_fa_digits(r.get("code") or "")}</span>',
                    to_fa_num(core.qty_int(r.get("qty1"))),
                    to_fa_num(r.get("qty2")),
                    to_fa_num(r.get("price")),
                    to_fa_num(r.get("cost")),
                ]
            else:
                cells = [
                    to_fa_num(r.get("index", idx + 1)),
                    r.get("type") or "",
                    r.get("size") or "",
                    to_fa_num(core.qty_int(r.get("qty1"))),
                    to_fa_num(r.get("qty2")),
                    to_fa_num(r.get("price")),
                    to_fa_num(r.get("cost")),
                ]
            bg = "#f0f9ff" if idx % 2 == 0 else "#ffffff"
            tds = "".join(
                f'<td style="padding:7px 5px;text-align:center;font-size:12px;border-bottom:1px solid #e0f2fe;">{c}</td>'
                for c in cells
            )
            rows_html.append(f'<tr style="background:{bg};">{tds}</tr>')

        debt_display = to_fa_num(debt) if debt else ""
        disc_display = to_fa_num(disc) if disc else ""
        shaba_html = ""
        if shaba:
            shaba_html = f'<p style="margin:8px 0 0;font-weight:500;color:#1565C0;">شماره شبا بانک ملت: {shaba}</p>'

        return f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<title>استعلام قیمت کالا</title>
<link href="https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@v33.003/Vazirmatn-font-face.css" rel="stylesheet">
<style>
  *{{font-family:Vazirmatn,Tahoma,sans-serif!important;box-sizing:border-box;
    -webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}
  body{{margin:0;padding:0;color:#1e293b;font-size:14px;line-height:1.55;background:#fff}}
  table{{width:100%;border-collapse:collapse}}
  @media print{{
    @page{{size:A4;margin:0}}
    body{{padding:0}}
    .no-print{{display:none!important}}
  }}
</style>
</head>
<body>
<div class="no-print" style="position:sticky;top:0;z-index:10;background:#0f172a;color:white;padding:10px 16px;
     display:flex;gap:10px;align-items:center;justify-content:center;">
  <span style="font-size:13px;">چاپ → Save as PDF و Background graphics را فعال کنید</span>
  <button onclick="window.print()" style="background:#1565C0;color:white;border:none;padding:8px 18px;border-radius:8px;font-weight:bold;cursor:pointer;">چاپ / ذخیره PDF</button>
</div>
<div style="background:#1565C0;color:white;padding:14px 18px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div style="font-size:18px;font-weight:bold;">استعلام قیمت کالا</div>
    <div style="font-size:13px;opacity:0.95;">{tab_fa}</div>
  </div>
</div>
<div style="padding:14px 16px;">
  <div style="display:flex;gap:14px;margin-bottom:12px;">
    <div style="flex:1;background:#1565C0;border-radius:12px;padding:14px 16px;color:white;">
      <div style="font-size:12px;opacity:0.75;margin-bottom:4px;">نام خریدار</div>
      <div style="font-size:17px;font-weight:bold;">{buyer}</div>
    </div>
    <div style="flex:0.7;background:#1565C0;border-radius:12px;padding:14px 16px;color:white;">
      <div style="font-size:12px;opacity:0.75;margin-bottom:4px;">تاریخ</div>
      <div style="font-size:17px;font-weight:bold;direction:ltr;text-align:left;">{date_fa}</div>
    </div>
  </div>
  <div style="border-radius:12px;overflow:hidden;border:1px solid #bae6fd;margin-bottom:12px;">
    <table>
      <thead><tr>{headers_html}</tr></thead>
      <tbody>{''.join(rows_html)}</tbody>
    </table>
  </div>
  <div style="margin-bottom:12px;">
    <table style="font-size:11px;">
      <tr>
        <td style="padding:6px 10px;background:#f0f9ff;color:#64748b;width:35%;">مبلغ کل اقلام</td>
        <td style="padding:6px 10px;background:#f0f9ff;text-align:left;direction:ltr;font-weight:600;font-size:15px;">{to_fa_num(subtotal)}</td>
      </tr>
      <tr>
        <td style="padding:6px 10px;color:#64748b;">هزینه انبارداری</td>
        <td style="padding:6px 10px;">{warehouse or "—"}</td>
      </tr>
      <tr>
        <td style="padding:6px 10px;background:#f0f9ff;color:#64748b;">هزینه حمل</td>
        <td style="padding:6px 10px;background:#f0f9ff;">{transport}</td>
      </tr>
      <tr>
        <td style="padding:6px 10px;color:#64748b;">بدهی پیشین</td>
        <td style="padding:6px 10px;text-align:left;direction:ltr;">{debt_display}</td>
      </tr>
      <tr>
        <td style="padding:6px 10px;background:#f0f9ff;color:#64748b;">تخفیف</td>
        <td style="padding:6px 10px;background:#f0f9ff;text-align:left;direction:ltr;">{disc_display}</td>
      </tr>
    </table>
  </div>
  <div style="background:#1565C0;border-radius:14px;padding:14px 18px;color:white;margin-bottom:12px;">
    <div style="font-size:13px;opacity:0.8;margin-bottom:6px;">جمع کل قابل پرداخت</div>
    <div style="font-size:24px;font-weight:900;direction:ltr;text-align:left;">{to_fa_num(total)} <span style="font-size:15px;font-weight:500;">ریال</span></div>
    <div style="font-size:15px;margin-top:8px;opacity:0.9;font-weight:500;">{number_to_persian_words(total)} ریال</div>
  </div>
  <div style="background:#f8fafc;border-radius:12px;padding:16px 18px;border:1px solid #e2e8f0;font-size:11px;color:#475569;line-height:1.6;">
    <div style="font-weight:600;color:#1565C0;margin-bottom:8px;font-size:14px;">شرایط و نکات مهم</div>
    <p style="margin:4px 0;">• پس از واریز مبلغ به حساب شرکت و تأیید واحد حسابداری، حواله خروج بار صادر می‌گردد.</p>
    <p style="margin:4px 0;">• پس از خروج کالا از انبار شرکت هیچ مسئولیتی از لحاظ کمیت و کیفیت/سلامت کالا ندارد.</p>
    <p style="margin:4px 0;">• پس از فروش کالا به هیچ عنوان مرجوعی و ابطال حواله انجام نمی‌شود.</p>
    <p style="margin:10px 0 4px;font-weight:500;color:#1e293b;">{validity}</p>
    {shaba_html}
  </div>
</div>
</body>
</html>
"""
