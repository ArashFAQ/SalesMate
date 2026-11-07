# -*- coding: utf-8 -*-
"""صفحه‌ی «مشتریان و محاسبات» — بخش بومی خود برنامه (جایگزین ابزار وب قبلی).

منطق دقیقاً همان ابزار قبلی است و در calc_core.py قرار دارد؛ اینجا فقط رابط کاربری.
داده‌ی ماندگار (مشتریان، سایزها، محاسبه‌ی آزاد، مشتری انتخاب‌شده) در calc_customers.json
کنار برنامه ذخیره می‌شود. تعداد/مبلغ ردیف‌ها مثل قبل با هر بار باز شدن برنامه از صفر شروع می‌شود.
نشست ابری همان نشست خود برنامه است (ورود جداگانه لازم نیست).
"""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, QTabWidget,
    QLineEdit, QMessageBox, QFileDialog, QDialog, QApplication, QScrollArea, QFormLayout,
)

try:
    import calc_core as cc
    from core_utils import fa_digits
    from app_log import swallow as _swallow
except Exception:  # pragma: no cover
    from salesmate import calc_core as cc
    from salesmate.core_utils import fa_digits
    from salesmate.app_log import swallow as _swallow

STORE_NAME = "calc_customers.json"

BTN = {
    "pri": "QPushButton{background:#1565C0;color:#fff;border:none;border-radius:9px;padding:7px 14px;font-weight:700;}"
           "QPushButton:hover{background:#0D47A1;}QPushButton:disabled{background:#94A3B8;}",
    "ok": "QPushButton{background:#16A34A;color:#fff;border:none;border-radius:9px;padding:7px 14px;font-weight:700;}"
          "QPushButton:hover{background:#15803D;}QPushButton:disabled{background:#94A3B8;}",
    "bad": "QPushButton{background:#FEE2E2;color:#B91C1C;border:none;border-radius:9px;padding:7px 12px;font-weight:700;}"
           "QPushButton:hover{background:#FECACA;}",
    "sec": "QPushButton{background:#F1F5F9;color:#0F172A;border:1px solid #E2E8F0;border-radius:9px;padding:7px 12px;font-weight:700;}"
           "QPushButton:hover{background:#E2E8F0;}QPushButton:disabled{color:#94A3B8;}",
    "copy": "QPushButton{background:#E0F2FE;color:#0D47A1;border:none;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:#BAE6FD;}QPushButton:disabled{background:#F1F5F9;color:#CBD5E1;}",
}
INPUT_CSS = ("QLineEdit{background:#fff;border:1px solid #CBD5E1;border-radius:8px;padding:7px 10px;font-size:13px;min-height:20px;}"
             "QLineEdit:focus{border:1px solid #1565C0;}")
CARD_CSS = "QFrame#card{background:#fff;border:1px solid #E2E8F0;border-radius:14px;}"
PAGE_CSS = ("QLabel{background:transparent;border:none;padding:0;}"
            "QScrollArea{background:transparent;border:none;}"
            "QScrollArea > QWidget > QWidget{background:transparent;}")
ITEM_CSS = ("QPushButton{background:#F8FAFC;color:#0F172A;border:1px solid #E2E8F0;border-radius:9px;"
            "padding:7px 10px;text-align:right;}QPushButton:hover{background:#EFF6FF;border-color:#BFDBFE;}")
ITEM_SEL_CSS = ("QPushButton{background:#E0F2FE;color:#0C4A6E;border:1px solid #38BDF8;border-radius:9px;"
                "padding:7px 10px;text-align:right;font-weight:700;}")
TILE_CSS = ["QFrame#tile{background:%s;border:none;border-radius:10px;}" % c
            for c in ("#EFF6FF", "#F0FDF4", "#FFFBEB", "#FDF2F8")]
HEAD_CSS = "color:#64748B;font-weight:700;font-size:12px;"
SEP_CSS = "background:#F1F5F9;border:none;"


def _btn(text, kind="sec"):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(BTN[kind])
    return b


def _card():
    f = QFrame()
    f.setObjectName("card")
    f.setStyleSheet(CARD_CSS)
    return f


def _item_btn(text, selected=False):
    b = QPushButton(text)
    b.setCursor(Qt.PointingHandCursor)
    b.setStyleSheet(ITEM_SEL_CSS if selected else ITEM_CSS)
    return b


def _list_area(max_h=None, min_h=None):
    """ناحیه‌ی اسکرول‌دار برای لیست دکمه‌ها؛ (area, vbox) برمی‌گرداند."""
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setFrameShape(QFrame.NoFrame)
    sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    inner = QWidget()
    box = QVBoxLayout(inner)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(5)
    box.setAlignment(Qt.AlignTop)
    sc.setWidget(inner)
    if max_h:
        sc.setMaximumHeight(max_h)
    if min_h:
        sc.setMinimumHeight(min_h)
    return sc, box


def _clear(layout):
    while layout.count():
        it = layout.takeAt(0)
        w = it.widget()
        if w is not None:
            w.setParent(None)
            w.deleteLater()
        elif it.layout() is not None:
            _clear(it.layout())


def _en(n):
    """عدد به متن با ارقام فارسی برای نمایش."""
    return fa_digits(n)


class _Bridge(QObject):
    done = Signal(object)


class CalcCustomersPage(QWidget):
    def __init__(self, win, app_dir, cloud=None):
        super().__init__()
        self.win = win
        self.path = Path(app_dir) / STORE_NAME
        self.cloud = cloud
        self.store = cc.load_store(self.path)
        # محاسبات هر بار با باز شدن برنامه از صفر شروع می‌شوند
        self.calc = {s["id"]: {"count": 0, "amount": 0} for s in self.store["sizes"]}
        self.sel = -1          # اندیس مشتریِ نمایش‌داده‌شده در دفترچه
        self.editing = -1      # اندیس مشتریِ در حال ویرایش (-1 = جدید)
        self._inputs = []
        self._row_widgets = {}
        self._bridge = _Bridge()
        self._bridge.done.connect(self._on_bg_done)
        self._build()
        self.render_all()

    # ───────────────────────── ساخت رابط ─────────────────────────
    def _build(self):
        self.setStyleSheet(PAGE_CSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        head = QHBoxLayout()
        title = QLabel("مشتریان و محاسبات")
        title.setStyleSheet("font-weight:800;font-size:15px;color:#0f172a;")
        head.addWidget(title, 1)
        root.addLayout(head)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._scrollable(self._build_calc_tab(), 760), "محاسبات")
        self.tab_cust_index = 1
        self.tabs.addTab(self._scrollable(self._build_customers_tab(), 560), "دفترچه مشتریان (۰)")
        self.tabs.addTab(self._scrollable(self._build_backup_tab(), 420), "پشتیبان‌گیری")
        root.addWidget(self.tabs, 1)

    @staticmethod
    def _scrollable(content, min_h):
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setWidget(content)
        return sc

    # --- تب محاسبات ---
    def _build_calc_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)

        # مشتریِ این محاسبه
        pc = _card()
        pl = QVBoxLayout(pc)
        row = QHBoxLayout()
        row.addWidget(QLabel("مشتریِ این محاسبه (اختیاری):"))
        self.calc_cust_search = QLineEdit()
        self.calc_cust_search.setPlaceholderText("جستجو: نام، کد ملی یا تلفن…")
        self.calc_cust_search.setStyleSheet(INPUT_CSS)
        self.calc_cust_search.textChanged.connect(self._calc_suggest)
        row.addWidget(self.calc_cust_search, 1)
        pl.addLayout(row)
        self.sugg_area, self.sugg_box = _list_area(max_h=200)
        self.sugg_area.setVisible(False)
        pl.addWidget(self.sugg_area)
        self.picked_box = QHBoxLayout()
        pl.addLayout(self.picked_box)
        lay.addWidget(pc)

        # خلاصه
        kc = QWidget()
        kl = QHBoxLayout(kc)
        kl.setContentsMargins(0, 0, 0, 0)
        kl.setSpacing(10)
        self.k_sheets, self.k_amount, self.k_cubic, self.k_tax = QLabel("۰"), QLabel("۰"), QLabel("۰"), QLabel("۰")
        for k, (cap, lab) in enumerate((("جمع تعداد ورق", self.k_sheets), ("جمع مبلغ", self.k_amount),
                                        ("جمع متر مکعب", self.k_cubic), ("جمع مالیات", self.k_tax))):
            tile = QFrame()
            tile.setObjectName("tile")
            tile.setStyleSheet(TILE_CSS[k])
            box = QVBoxLayout(tile)
            box.setContentsMargins(14, 10, 14, 10)
            c = QLabel(cap)
            c.setStyleSheet("color:#64748B;font-size:11px;font-weight:700;")
            lab.setStyleSheet("font-size:18px;font-weight:800;color:#0F172A;")
            box.addWidget(c)
            box.addWidget(lab)
            kl.addWidget(tile, 1)
        self.k_tax_copy = _btn("کپی مالیات", "copy")
        self.k_tax_copy.clicked.connect(lambda: self._copy(self._sum_tax_val))
        kl.addWidget(self.k_tax_copy)
        self._sum_tax_val = None
        lay.addWidget(kc)

        # جدول سایزها
        tc = _card()
        tl = QVBoxLayout(tc)
        bar = QHBoxLayout()
        t = QLabel("سایزها")
        t.setStyleSheet("font-weight:800;")
        bar.addWidget(t, 1)
        b_add = _btn("+ سایز جدید", "pri")
        b_add.clicked.connect(self.add_size_dialog)
        b_clear = _btn("پاک کردن محاسبات", "bad")
        b_clear.clicked.connect(self.reset_calculations)
        bar.addWidget(b_add)
        bar.addWidget(b_clear)
        tl.addLayout(bar)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(6)
        for ci, wt in enumerate((3, 2, 3, 2, 3, 3)):
            self.grid.setColumnStretch(ci, wt)
        tl.addWidget(self.grid_host)
        lay.addWidget(tc)

        # محاسبه‌ی آزاد
        fc = _card()
        fl = QGridLayout(fc)
        ft = QLabel("محاسبه آزاد")
        ft.setStyleSheet("font-weight:800;")
        fl.addWidget(ft, 0, 0, 1, 4)
        self.free_cubic = QLineEdit()
        self.free_cubic.setPlaceholderText("متر مکعب (می‌تواند عبارت باشد؛ مثل 2.66*…)")
        self.free_amount = QLineEdit()
        self.free_amount.setPlaceholderText("مبلغ کل")
        for e in (self.free_cubic, self.free_amount):
            e.setStyleSheet(INPUT_CSS)
        fl.addWidget(QLabel("متر مکعب"), 1, 0)
        fl.addWidget(self.free_cubic, 1, 1)
        fl.addWidget(QLabel("مبلغ کل"), 1, 2)
        fl.addWidget(self.free_amount, 1, 3)
        self.free_per, self.free_tax = QLabel("—"), QLabel("—")
        self.free_per_copy, self.free_tax_copy = _btn("کپی", "copy"), _btn("کپی", "copy")
        self._free_vals = {"per": None, "tax": None}
        self.free_per_copy.clicked.connect(lambda: self._copy(self._free_vals["per"]))
        self.free_tax_copy.clicked.connect(lambda: self._copy(self._free_vals["tax"]))
        fl.addWidget(QLabel("هر متر مکعب"), 2, 0)
        pr = QHBoxLayout()
        pr.addWidget(self.free_per)
        pr.addWidget(self.free_per_copy)
        fl.addLayout(pr, 2, 1)
        fl.addWidget(QLabel("مالیات"), 2, 2)
        tr = QHBoxLayout()
        tr.addWidget(self.free_tax)
        tr.addWidget(self.free_tax_copy)
        fl.addLayout(tr, 2, 3)
        self.free_cubic.textEdited.connect(lambda _t: self._free_live("cubic"))
        self.free_amount.textEdited.connect(lambda _t: self._free_live("amount"))
        self.free_cubic.editingFinished.connect(lambda: self._free_commit("cubic"))
        self.free_amount.editingFinished.connect(lambda: self._free_commit("amount"))
        self.free_cubic.returnPressed.connect(lambda: self._focus_next(self.free_cubic))
        self.free_amount.returnPressed.connect(lambda: self._focus_next(self.free_amount))
        lay.addWidget(fc)
        lay.addStretch(1)
        return w

    # --- تب دفترچه ---
    def _build_customers_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        top = QHBoxLayout()
        self.cust_search = QLineEdit()
        self.cust_search.setPlaceholderText("جستجو: نام، کد ملی یا تلفن…")
        self.cust_search.setStyleSheet(INPUT_CSS)
        self.cust_search.textChanged.connect(lambda _t: self.render_customers())
        b_new = _btn("+ مشتری جدید", "pri")
        b_new.clicked.connect(lambda: self.open_form(-1))
        top.addWidget(self.cust_search, 1)
        top.addWidget(b_new)
        lay.addLayout(top)
        body = QHBoxLayout()
        left = _card()
        ll = QVBoxLayout(left)
        sc, self.cust_results = _list_area(min_h=380)
        ll.addWidget(sc)
        right = _card()
        rl = QVBoxLayout(right)
        self.cust_detail = QVBoxLayout()
        rl.addLayout(self.cust_detail)
        # فرم
        self.form_box = QWidget()
        fl = QFormLayout(self.form_box)
        self.form_title = QLabel("افزودن مشتری")
        self.form_title.setStyleSheet("font-weight:800;")
        self.f_name, self.f_nat, self.f_phone = QLineEdit(), QLineEdit(), QLineEdit()
        for e in (self.f_name, self.f_nat, self.f_phone):
            e.setStyleSheet(INPUT_CSS)
        fl.addRow(self.form_title)
        fl.addRow("نام مشتری", self.f_name)
        fl.addRow("کد ملی", self.f_nat)
        fl.addRow("شماره تماس", self.f_phone)
        fb = QHBoxLayout()
        b_save = _btn("ذخیره", "ok")
        b_save.clicked.connect(self.save_form)
        b_cancel = _btn("انصراف", "sec")
        b_cancel.clicked.connect(self.close_form)
        fb.addWidget(b_save)
        fb.addWidget(b_cancel)
        fl.addRow(fb)
        self.form_box.setVisible(False)
        rl.addWidget(self.form_box)
        rl.addStretch(1)
        body.addWidget(left, 1)
        body.addWidget(right, 1)
        lay.addLayout(body, 1)
        return w

    # --- تب پشتیبان ---
    def _build_backup_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        c1 = _card()
        l1 = QVBoxLayout(c1)
        t1 = QLabel("پشتیبان محلی")
        t1.setStyleSheet("font-weight:800;")
        l1.addWidget(t1)
        d1 = QLabel("مشتریان، سایزها و محاسبات را در یک فایل ذخیره یا از فایل بازیابی کنید.")
        d1.setWordWrap(True)
        l1.addWidget(d1)
        r1 = QHBoxLayout()
        b_exp = _btn("ساخت فایل پشتیبان", "pri")
        b_exp.clicked.connect(self.export_backup)
        b_imp = _btn("بازیابی از فایل", "sec")
        b_imp.clicked.connect(self.import_backup)
        r1.addWidget(b_exp)
        r1.addWidget(b_imp)
        r1.addStretch(1)
        l1.addLayout(r1)
        lay.addWidget(c1)
        c2 = _card()
        l2 = QVBoxLayout(c2)
        t2 = QLabel("ذخیره‌ی ابری (دستی)")
        t2.setStyleSheet("font-weight:800;")
        l2.addWidget(t2)
        self.cloud_status = QLabel("")
        self.cloud_status.setWordWrap(True)
        l2.addWidget(self.cloud_status)
        d2 = QLabel("از همان حساب ابری خود برنامه استفاده می‌شود. جدول calc_notebook باید یک‌بار در Supabase ساخته شده باشد.")
        d2.setWordWrap(True)
        d2.setStyleSheet("color:#64748B;font-size:11px;")
        l2.addWidget(d2)
        r2 = QHBoxLayout()
        self.b_push = _btn("ارسال به ابر", "ok")
        self.b_push.clicked.connect(self.push_cloud)
        self.b_pull = _btn("دریافت از ابر", "sec")
        self.b_pull.clicked.connect(self.pull_cloud)
        r2.addWidget(self.b_push)
        r2.addWidget(self.b_pull)
        r2.addStretch(1)
        l2.addLayout(r2)
        lay.addWidget(c2)
        lay.addStretch(1)
        return w

    # ───────────────────────── رندر ─────────────────────────
    def render_all(self):
        self.render_calc()
        self.render_customers()
        self.render_picked()
        self.render_free()
        self.update_badge()
        self.update_cloud_status()

    def on_show(self):
        self.update_cloud_status()

    def update_badge(self):
        try:
            self.tabs.setTabText(self.tab_cust_index, "دفترچه مشتریان (%s)" % _en(len(self.store["customers"])))
        except Exception:
            _swallow()

    def render_calc(self):
        _clear(self.grid)
        self._inputs = []
        self._row_widgets = {}
        heads = ("سایز", "تعداد ورق", "مبلغ کل", "متر مکعب", "هر متر مکعب", "مالیات")
        for ci, h in enumerate(heads):
            lb = QLabel(h)
            lb.setStyleSheet(HEAD_CSS)
            lb.setAlignment((Qt.AlignRight if ci == 0 else Qt.AlignCenter) | Qt.AlignVCenter)
            self.grid.addWidget(lb, 0, ci)
        for ri, s in enumerate(self.store["sizes"], start=1):
            ri = ri * 2 - 1 + 1  # هر ردیف یک خط جداکننده‌ی باریک بالای خود دارد
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(SEP_CSS)
            self.grid.addWidget(sep, ri - 1, 0, 1, 6)
            sid = s["id"]
            entry = self.calc.setdefault(sid, {"count": 0, "amount": 0})
            # نام + فرمول (+ حذف برای سایز دلخواه)
            nm = QWidget()
            nl = QHBoxLayout(nm)
            nl.setContentsMargins(0, 0, 0, 0)
            col = QVBoxLayout()
            n1 = QLabel(s.get("name", ""))
            n1.setStyleSheet("font-weight:700;font-size:13px;")
            n1.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            n2 = QLabel(s.get("sourceFormula", "") or "")
            n2.setStyleSheet("color:#94A3B8;font-size:11px;")
            n2.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            col.addWidget(n1)
            col.addWidget(n2)
            if s.get("custom"):
                bd = _btn("حذف", "bad")
                bd.clicked.connect(lambda _=False, i=sid: self.delete_size(i))
                nl.addWidget(bd)
            nl.addLayout(col, 1)
            self.grid.addWidget(nm, ri, 0)
            e_cnt, e_amt = QLineEdit(), QLineEdit()
            for e in (e_cnt, e_amt):
                e.setStyleSheet(INPUT_CSS)
                e.setAlignment(Qt.AlignCenter)
            e_cnt.setText(cc.fmt(entry["count"]) if entry["count"] else "")
            e_amt.setText(cc.fmt(entry["amount"]) if entry["amount"] else "")
            self.grid.addWidget(e_cnt, ri, 1)
            self.grid.addWidget(e_amt, ri, 2)
            lab_cubic = QLabel("—")
            lab_cubic.setAlignment(Qt.AlignCenter)
            self.grid.addWidget(lab_cubic, ri, 3)
            per_lab, per_btn, per_w = self._copy_cell()
            tax_lab, tax_btn, tax_w = self._copy_cell()
            self.grid.addWidget(per_w, ri, 4)
            self.grid.addWidget(tax_w, ri, 5)
            self._row_widgets[sid] = {"cubic": lab_cubic, "per": (per_lab, per_btn), "tax": (tax_lab, tax_btn),
                                      "count": e_cnt, "amount": e_amt}
            for field, ed in (("count", e_cnt), ("amount", e_amt)):
                ed.textEdited.connect(lambda _t, i=sid, f=field, x=ed: self._row_edit(i, f, x))
                ed.editingFinished.connect(lambda i=sid, f=field, x=ed: self._row_commit(i, f, x))
                ed.returnPressed.connect(lambda x=ed: self._focus_next(x))
                self._inputs.append(ed)
            self._update_row(sid)
        self._inputs += [self.free_cubic, self.free_amount]
        self.update_summary()

    def _copy_cell(self):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        lab = QLabel("—")
        lab.setAlignment(Qt.AlignCenter)
        b = _btn("کپی", "copy")
        b.setEnabled(False)
        h.addWidget(lab, 1)
        h.addWidget(b)
        return lab, b, w

    def _set_copy_cell(self, pair, value):
        lab, b = pair
        has = value is not None and value != ""
        lab.setText(_en(cc.fmt(value)) if has else "—")
        b.setEnabled(has)
        try:
            b.clicked.disconnect()
        except Exception:
            pass
        if has:
            b.clicked.connect(lambda _=False, v=value: self._copy(v))

    def _update_row(self, sid):
        s = next((x for x in self.store["sizes"] if x["id"] == sid), None)
        rw = self._row_widgets.get(sid)
        if not s or not rw:
            return
        r = cc.row_calc(s, self.calc.get(sid))
        rw["cubic"].setText(_en(cc.fmt(r["cubic"], 2)) if r["cubic"] else "—")
        self._set_copy_cell(rw["per"], r["per"])
        self._set_copy_cell(rw["tax"], r["tax"])

    def update_summary(self):
        sm = cc.summary(self.store["sizes"], self.calc)
        self.k_sheets.setText(_en(cc.fmt(sm["sheets"])))
        self.k_amount.setText(_en(cc.fmt(sm["amount"])))
        self.k_cubic.setText(_en(cc.fmt(sm["cubic"], 2)))
        self.k_tax.setText(_en(cc.fmt(sm["tax"])))
        self._sum_tax_val = sm["tax"] or None
        self.k_tax_copy.setEnabled(bool(sm["tax"]))
        return sm

    # ورودی‌های ردیف
    def _row_edit(self, sid, field, ed):
        val = cc.parse_amount(ed.text())
        self.calc[sid][field] = val
        ed.setText(cc.fmt(val) if val else "")
        try:
            ed.setCursorPosition(len(ed.text()))
        except Exception:
            _swallow()
        self._update_row(sid)
        self.update_summary()

    def _row_commit(self, sid, field, ed):
        val = cc.parse_amount(ed.text())
        self.calc[sid][field] = val
        ed.setText(cc.fmt(val) if val else "")
        self._update_row(sid)
        self.update_summary()

    def _focus_next(self, cur):
        try:
            i = self._inputs.index(cur)
        except ValueError:
            return
        if i < len(self._inputs) - 1:
            nxt = self._inputs[i + 1]
            nxt.setFocus()
            try:
                nxt.selectAll()
            except Exception:
                _swallow()
        else:
            cur.clearFocus()

    # محاسبه‌ی آزاد
    def render_free(self):
        fc = self.store["freeCalc"]
        self.free_amount.setText(cc.fmt(fc.get("amount")) if fc.get("amount") else "")
        self.free_cubic.setText(cc.fmt_free_cubic(cc.n(fc.get("cubic"))))
        self._free_fill(cc.n(fc.get("amount")), cc.n(fc.get("cubic")))

    def _free_fill(self, amount, cubic):
        r = cc.free_result(amount, cubic)
        self._free_vals = r
        self.free_per.setText(_en(cc.fmt(r["per"])) if r["per"] is not None else "—")
        self.free_tax.setText(_en(cc.fmt(r["tax"])) if r["tax"] is not None else "—")
        self.free_per_copy.setEnabled(r["per"] is not None)
        self.free_tax_copy.setEnabled(r["tax"] is not None)

    def _free_live(self, which):
        fc = self.store["freeCalc"]
        if which == "amount":
            val = cc.parse_amount(self.free_amount.text())
            fc["amount"] = val
            self.free_amount.setText(cc.fmt(val) if val else "")
            try:
                self.free_amount.setCursorPosition(len(self.free_amount.text()))
            except Exception:
                _swallow()
        amount = cc.n(fc.get("amount"))
        cubic = cc.n(self.free_cubic.text()) if which == "cubic" else cc.n(fc.get("cubic"))
        self._free_fill(amount, cubic)

    def _free_commit(self, which):
        fc = self.store["freeCalc"]
        if which == "amount":
            val = cc.parse_amount(self.free_amount.text())
            fc["amount"] = val
            self.free_amount.setText(cc.fmt(val) if val else "")
        else:
            val = cc.n(self.free_cubic.text())
            fc["cubic"] = val
            self.free_cubic.setText(cc.fmt_free_cubic(val))
        self._save()
        self._free_fill(cc.n(fc.get("amount")), cc.n(fc.get("cubic")))

    def reset_calculations(self):
        if QMessageBox.question(self, "پاک کردن", "همه تعدادها و مبلغ‌های واردشده پاک شوند؟") != QMessageBox.Yes:
            return
        self.calc = {s["id"]: {"count": 0, "amount": 0} for s in self.store["sizes"]}
        self.store["freeCalc"] = {"amount": 0, "cubic": 0}
        self._save()
        self.render_calc()
        self.render_free()
        self._toast("محاسبات پاک شد")

    # سایز دلخواه
    def add_size_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("سایز جدید")
        fl = QFormLayout(dlg)
        e_name, e_l, e_w, e_t = QLineEdit(), QLineEdit(), QLineEdit(), QLineEdit()
        for e in (e_name, e_l, e_w, e_t):
            e.setStyleSheet(INPUT_CSS)
        fl.addRow("نام سایز", e_name)
        fl.addRow("طول (متر)", e_l)
        fl.addRow("عرض (متر)", e_w)
        fl.addRow("ضخامت (میلی‌متر)", e_t)
        row = QHBoxLayout()
        ok, cancel = _btn("افزودن", "ok"), _btn("انصراف", "sec")
        row.addWidget(ok)
        row.addWidget(cancel)
        fl.addRow(row)

        def go():
            s = cc.new_custom_size(e_name.text(), e_l.text(), e_w.text(), e_t.text(), int(time.time() * 1000))
            if not s:
                QMessageBox.warning(dlg, "سایز جدید", "نام، طول، عرض و ضخامت را کامل وارد کنید.")
                return
            self.add_size(s)
            dlg.accept()
        ok.clicked.connect(go)
        cancel.clicked.connect(dlg.reject)
        dlg.exec()

    def add_size(self, s):
        self.store["sizes"].append(s)
        self.calc[s["id"]] = {"count": 0, "amount": 0}
        self._save()
        self.render_calc()
        self._toast("سایز جدید اضافه شد")

    def delete_size(self, sid):
        if QMessageBox.question(self, "حذف سایز", "این سایز حذف شود؟") != QMessageBox.Yes:
            return
        self.store["sizes"] = [s for s in self.store["sizes"] if s["id"] != sid]
        self.calc.pop(sid, None)
        self._save()
        self.render_calc()

    # مشتریِ این محاسبه
    def _calc_suggest(self, _t=None):
        _clear(self.sugg_box)
        q = self.calc_cust_search.text().strip()
        self.sugg_area.setVisible(bool(q))
        if not q:
            return
        res = cc.customer_matches(self.store["customers"], q, 12)
        if not res:
            lb = QLabel("مشتری پیدا نشد.")
            lb.setStyleSheet("color:#94A3B8;padding:6px;")
            self.sugg_box.addWidget(lb)
            return
        for c, _i in res:
            txt = "%s   %s%s" % (c.get("customer", ""), c.get("national_id", ""),
                                 (" | " + c["phone"]) if c.get("phone") else "")
            b = _item_btn(txt)
            b.clicked.connect(lambda _=False, cu=c: self._pick(cu))
            self.sugg_box.addWidget(b)

    def _pick(self, c):
        self.store["pickedCustomer"] = cc.picked_from(c)
        self.calc_cust_search.setText("")
        _clear(self.sugg_box)
        self.sugg_area.setVisible(False)
        self._save()
        self.render_picked()

    def render_picked(self):
        _clear(self.picked_box)
        p = self.store.get("pickedCustomer")
        if not p:
            lb = QLabel("مشتری انتخاب نشده")
            lb.setStyleSheet("color:#94A3B8;font-size:12px;")
            self.picked_box.addWidget(lb)
            return
        nm = QLabel(p.get("customer", ""))
        nm.setStyleSheet("font-weight:800;")
        self.picked_box.addWidget(nm)
        self.picked_box.addWidget(QLabel("کد ملی: " + (p.get("national_id") or "—")))
        b1 = _btn("کپی", "copy")
        b1.setEnabled(bool(p.get("national_id")))
        b1.clicked.connect(lambda: self._copy(p.get("national_id")))
        self.picked_box.addWidget(b1)
        self.picked_box.addWidget(QLabel("تماس: " + (p.get("phone") or "—")))
        b2 = _btn("کپی", "copy")
        b2.setEnabled(bool(p.get("phone")))
        b2.clicked.connect(lambda: self._copy(p.get("phone")))
        self.picked_box.addWidget(b2)
        bx = _btn("حذف انتخاب", "sec")
        bx.clicked.connect(self._unpick)
        self.picked_box.addWidget(bx)
        self.picked_box.addStretch(1)

    def _unpick(self):
        self.store["pickedCustomer"] = None
        self._save()
        self.render_picked()

    # ───────────────────────── دفترچه ─────────────────────────
    def render_customers(self):
        _clear(self.cust_results)
        res = cc.customer_matches(self.store["customers"], self.cust_search.text(), 80)
        if not res:
            lb = QLabel("مشتری پیدا نشد.")
            lb.setStyleSheet("color:#94A3B8;padding:8px;")
            self.cust_results.addWidget(lb)
            return
        for c, i in res:
            sub = (("کد ملی: " + c["national_id"]) if c.get("national_id") else "کد ملی ثبت نشده") + \
                  ((" | " + c["phone"]) if c.get("phone") else "")
            b = _item_btn("%s\n%s" % (c.get("customer", ""), sub), i == self.sel)
            b.clicked.connect(lambda _=False, k=i: self.select_customer(k))
            self.cust_results.addWidget(b)

    def _detail_field(self, label, display, copy_value):
        row = QHBoxLayout()
        cap = QLabel(label)
        cap.setStyleSheet("color:#64748B;")
        val = QLabel(display)
        val.setStyleSheet("font-weight:700;")
        b = _btn("کپی", "copy")
        b.setEnabled(bool(copy_value))
        b.clicked.connect(lambda: self._copy(copy_value))
        row.addWidget(cap)
        row.addWidget(val, 1)
        row.addWidget(b)
        return row

    def select_customer(self, i):
        if not (0 <= i < len(self.store["customers"])):
            return
        self.sel = i
        self.close_form()
        self.render_customers()
        c = self.store["customers"][i]
        _clear(self.cust_detail)
        h = QLabel(c.get("customer", ""))
        h.setStyleSheet("font-weight:800;font-size:15px;")
        self.cust_detail.addWidget(h)
        self.cust_detail.addLayout(self._detail_field("کد ملی", c.get("national_id") or "ثبت نشده", c.get("national_id")))
        self.cust_detail.addLayout(self._detail_field("شماره تماس", c.get("phone") or "ثبت نشده", c.get("phone")))
        ac = QHBoxLayout()
        use = _btn("انتخاب برای محاسبه", "pri")
        use.clicked.connect(lambda: self._use_for_calc(i))
        ed = _btn("ویرایش", "sec")
        ed.clicked.connect(lambda: self.open_form(i))
        de = _btn("حذف مشتری", "bad")
        de.clicked.connect(lambda: self.delete_customer(i))
        for b in (use, ed, de):
            ac.addWidget(b)
        self.cust_detail.addLayout(ac)

    def _use_for_calc(self, i):
        self.store["pickedCustomer"] = cc.picked_from(self.store["customers"][i])
        self._save()
        self.render_picked()
        self.tabs.setCurrentIndex(0)
        self._toast("مشتری انتخاب شد")

    def open_form(self, i=-1):
        self.editing = i
        self.form_box.setVisible(True)
        self.form_title.setText("ویرایش مشتری" if i >= 0 else "افزودن مشتری")
        c = self.store["customers"][i] if i >= 0 else {"customer": "", "national_id": "", "phone": ""}
        self.f_name.setText(c.get("customer", ""))
        self.f_nat.setText(c.get("national_id", ""))
        self.f_phone.setText(c.get("phone", ""))
        self.f_name.setFocus()

    def close_form(self):
        self.editing = -1
        self.form_box.setVisible(False)

    def save_form(self):
        c = cc.clean_customer(self.f_name.text(), self.f_nat.text(), self.f_phone.text())
        if not c:
            QMessageBox.warning(self, "مشتری", "نام مشتری را وارد کنید.")
            return
        lst = self.store["customers"]
        if self.editing >= 0:
            lst[self.editing] = c
            self.sel = self.editing
        else:
            lst.append(c)
            self.sel = len(lst) - 1
        self._save()
        self.close_form()
        self.cust_search.setText(c["customer"])
        self.render_customers()
        self.select_customer(self.sel)
        self.update_badge()
        self._toast("مشتری ذخیره شد")
        # ارسال خودکار به ابر فقط برای مالک دفترچه
        try:
            if self._cloud_ok() and cc.is_owner(self._email()):
                self._run_bg(self._push_work, lambda r, e: None)
        except Exception:
            _swallow()

    def delete_customer(self, i):
        if QMessageBox.question(self, "حذف", "این مشتری حذف شود؟") != QMessageBox.Yes:
            return
        c = self.store["customers"].pop(i)
        if cc.same_customer(self.store.get("pickedCustomer"), c):
            self.store["pickedCustomer"] = None
        self.sel = -1
        self._save()
        _clear(self.cust_detail)
        self.cust_detail.addWidget(QLabel("یک مشتری را از لیست انتخاب کنید."))
        self.render_customers()
        self.render_picked()
        self.update_badge()
        self._toast("مشتری حذف شد")

    # ───────────────────────── پشتیبان محلی ─────────────────────────
    def export_backup(self):
        name = "backup_customers_calculations_%s.json" % datetime.now().strftime("%Y-%m-%d")
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره‌ی پشتیبان", name, "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cc.build_backup(self.store, self.calc), f, ensure_ascii=False, indent=2)
            self._toast("فایل پشتیبان ساخته شد")
        except Exception as ex:
            QMessageBox.critical(self, "پشتیبان", "ذخیره نشد:\n%s" % ex)

    def import_backup(self):
        path, _ = QFileDialog.getOpenFileName(self, "بازیابی پشتیبان", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
            store, calc = cc.apply_payload(d)
        except Exception:
            QMessageBox.warning(self, "پشتیبان", "فایل پشتیبان معتبر نیست.")
            return
        if QMessageBox.question(self, "بازیابی", "اطلاعات فعلی با فایل پشتیبان جایگزین شود؟") != QMessageBox.Yes:
            return
        self._replace(store, calc)
        self._toast("پشتیبان بازیابی شد")

    def _replace(self, store, calc):
        self.store, self.calc = store, calc
        self.sel = -1
        self._save()
        self.render_all()

    # ───────────────────────── ابر ─────────────────────────
    def _cloud_ok(self):
        try:
            return bool(self.cloud and self.cloud["enabled"]() and self.cloud["valid"]())
        except Exception:
            return False

    def _user(self):
        try:
            return self.cloud["user"]() or {}
        except Exception:
            return {}

    def _email(self):
        return self._user().get("email", "")

    def update_cloud_status(self):
        ok = self._cloud_ok()
        em = self._email()
        if ok:
            self.cloud_status.setText("وارد شده: " + (em or self._user().get("user_id", "")))
            self.cloud_status.setStyleSheet("color:#15803D;font-weight:700;")
        else:
            self.cloud_status.setText("وارد حساب ابری نشده‌اید — از بخش تنظیمات/ورود برنامه وارد شوید.")
            self.cloud_status.setStyleSheet("color:#64748B;")
        self.b_push.setEnabled(ok)
        self.b_pull.setEnabled(ok)

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

    def _push_work(self):
        uid = self._user().get("user_id", "")
        req = self.cloud["request"]
        try:
            req("DELETE", "/rest/v1/calc_notebook?user_id=eq." + uid)
        except Exception:
            _swallow()
        payload = cc.payload_for_push(cc.build_payload(self.store, self.calc), self._email())
        req("POST", "/rest/v1/calc_notebook",
            [{"user_id": uid, "payload": payload, "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}])
        return True

    def push_cloud(self):
        if not self._cloud_ok():
            QMessageBox.warning(self, "ابر", "ابتدا وارد حساب ابری شوید.")
            return
        if QMessageBox.question(self, "ارسال به ابر",
                                "اطلاعات فعلی به ابر ارسال شود؟ (داده قبلی شما در ابر جایگزین می‌شود)") != QMessageBox.Yes:
            return

        def done(_r, err):
            if err:
                QMessageBox.critical(self, "ابر", "خطا در ارسال به ابر:\n%s\n\nاگر جدول پیدا نشد: SQL مربوط به "
                                     "calc_notebook را در Supabase دوباره Run کنید." % err)
            else:
                self._toast("در ابر ذخیره شد")
                QMessageBox.information(self, "ابر", "ذخیره در فضای ابری انجام شد.")
        self._run_bg(self._push_work, done)

    def _pull_work(self):
        uid = self._user().get("user_id", "")
        _st, rows = self.cloud["request"](
            "GET", "/rest/v1/calc_notebook?user_id=eq.%s&select=*&order=updated_at.desc&limit=1" % uid)
        return rows

    def pull_cloud(self):
        if not self._cloud_ok():
            QMessageBox.warning(self, "ابر", "ابتدا وارد حساب ابری شوید.")
            return
        if QMessageBox.question(self, "دریافت از ابر", "اطلاعات فعلی با داده ابر جایگزین شود؟") != QMessageBox.Yes:
            return
        self._run_bg(self._pull_work, self._after_pull)

    def _after_pull(self, rows, err):
        if err:
            QMessageBox.critical(self, "ابر", "خطا در دریافت از ابر:\n%s" % err)
            return
        if not rows:
            QMessageBox.information(self, "ابر", "در ابر داده‌ای برای این حساب نیست.")
            return
        try:
            pl = rows[0].get("payload")
            if isinstance(pl, str):
                pl = json.loads(pl)
            owner = cc.is_owner(self._email())
            pl = cc.payload_for_pull(pl, self._email(), self.store["customers"])
            store, calc = cc.apply_payload(pl)
        except Exception:
            QMessageBox.warning(self, "ابر", "داده ابری نامعتبر است.")
            return
        self._replace(store, calc)
        self._toast("از ابر دریافت شد")
        if owner:
            QMessageBox.information(self, "ابر", "بازیابی از ابر انجام شد (شامل مشتریان).")
        else:
            QMessageBox.information(
                self, "ابر",
                "حساب شما مالک دفترچه مشتریان ابری نیست.\nفقط محاسبات اعمال شد؛ لیست مشتریان ابری فقط برای %s "
                "بارگذاری می‌شود." % cc.OWNER_EMAIL)

    # ───────────────────────── کمکی ─────────────────────────
    def _copy(self, value):
        if value is None or value == "" or value == "—":
            return
        s = str(value).replace(",", "").strip()
        if not s:
            return
        try:
            QApplication.clipboard().setText(s)
            self._toast("کپی شد")
        except Exception:
            _swallow()

    def _toast(self, msg, kind="info"):
        try:
            if hasattr(self.win, "show_app_toast"):
                self.win.show_app_toast(msg, kind)
                return
        except Exception:
            _swallow()
        try:
            self.win.statusBar().showMessage(str(msg), 3000)
        except Exception:
            _swallow()

    def _save(self):
        try:
            cc.save_store(self.path, self.store)
        except Exception as ex:
            QMessageBox.critical(self, "ذخیره", "ذخیره‌ی محلی انجام نشد:\n%s" % ex)
