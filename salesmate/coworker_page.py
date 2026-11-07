# -*- coding: utf-8 -*-
"""تب «همکاران» (فقط برای حساب مالک): برای هر همکار جدول مشتریان اکسل با دو تیک جدا برای پارکت و ام دی اف."""
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QTabWidget,
    QListWidget, QMessageBox, QComboBox, QApplication, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView,
)

try:
    import coworker_core as cw
    from coworker_compare import CompareTab
except Exception:
    from salesmate import coworker_core as cw
    from salesmate.coworker_compare import CompareTab

COL_NAME, COL_PQ, COL_MDF = 0, 1, 2
KIND_COL = {COL_PQ: "parquet", COL_MDF: "mdf"}


class CoworkerPage(QWidget):
    """cloud = {'request': fn, 'valid': fn}؛ get_df = تابعی که DataFrame اکسل فروش را می‌دهد."""

    def __init__(self, win, cloud, get_df, get_exclude=None, get_mine=None):
        super().__init__()
        self.win = win
        self.cloud = cloud
        self.get_df = get_df
        self.get_exclude = get_exclude or (lambda: set())
        self.get_mine = get_mine or (lambda: None)
        self.accounts = []        # همکاران جدید (@sales.local)
        self.olds = []            # حساب‌های قدیمی برای پیشنهاد
        self.info = {}            # ckey → (نام, {kinds})
        self.saved = {}           # (ckey, kind) → {'assignee','name'}
        self.stage = {}           # (ckey, kind) → uid یا None (تغییرات ذخیره‌نشده)
        self.tables = {}          # uid → QTableWidget
        self.queries = {}
        self._busy = False
        self._loading = False
        self._dirty = set()
        self._compare_dirty = True
        self.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.status = QLabel("")
        self.status.setStyleSheet("color:#475569;font-weight:700;")
        b_reload = QPushButton("بازخوانی")
        b_reload.clicked.connect(self.reload)
        b_resend = QPushButton("ارسال مجدد به همکاران")
        b_resend.setToolTip("حواله‌ها و سمپل/استند همه‌ی همکاران را با اکسل فعلی دوباره به‌روز می‌کند (بدون نیاز به تغییر تیک)")
        b_resend.clicked.connect(self.resend)
        self.b_save = QPushButton("ذخیره و ارسال به همکاران")
        self.b_save.setStyleSheet("QPushButton{background:#16A34A;color:white;font-weight:800;border-radius:8px;padding:6px 14px;}")
        self.b_save.clicked.connect(self.save)
        top.addWidget(self.status, 1)
        top.addWidget(b_reload)
        top.addWidget(b_resend)
        top.addWidget(self.b_save)
        lay.addLayout(top)
        info = QLabel("برای هر همکار، مشتریانش را تیک بزنید و «ذخیره» را بزنید. هر مشتری دو تیک دارد: پارکت و ام دی اف (خام هم جزو ام دی اف است؛ بقیه‌ی دسته‌ها با پارکت). "
                      "هر کدام را می‌توان به همکار جدا داد. بعد از هر بارگذاری اکسل فروش، حواله‌های جدید خودکار به برنامه‌ی همکار می‌رسد. "
                      "جابه‌جایی = برداشتن تیک از همکار قبلی و تیک برای همکار جدید (حواله‌های اکسلیِ قبلی از برنامه‌ی همکار قبلی حذف می‌شود).")
        info.setWordWrap(True)
        info.setStyleSheet("color:#64748b;")
        lay.addWidget(info)
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs, 1)

    # ───────── داده ─────────
    def on_show(self):
        self.reload()

    def _req(self):
        return self.cloud["request"]

    def _bg(self, work, done):
        """work در رشته‌ی پس‌زمینه؛ done(result, error) در رشته‌ی رابط."""
        try:
            from app_core import run_in_ui
        except Exception:
            from salesmate.app_core import run_in_ui

        def _run():
            res, err = None, None
            try:
                res = work()
            except Exception as ex:
                err = ex
            run_in_ui(lambda: done(res, err))
        threading.Thread(target=_run, daemon=True).start()

    def reload(self):
        if self._loading:
            return
        if self.stage and QMessageBox.question(self, "همکاران", "تغییرات ذخیره‌نشده از بین می‌رود. ادامه؟") != QMessageBox.Yes:
            return
        if not self.cloud["valid"]():
            self.status.setText("ابتدا وارد حساب ابری شوید.")
            return
        try:
            df = self.get_df()                 # ساخت صفحه‌ی تحلیل (در صورت نیاز) فقط در رشته‌ی رابط
            excl = self.get_exclude()
        except Exception as ex:
            self.status.setText("خطا: " + str(ex)[:150])
            return
        req = self._req()
        self._loading = True
        self.b_save.setEnabled(False)
        self.status.setText("در حال دریافت از ابر…")

        def work():
            info = cw.excel_customer_info(df, excl)
            allacc = cw.load_accounts(req)
            saved = cw.load_assignments(req)
            pend = cw.pending_counts(req)
            return info, allacc, saved, pend

        def done(res, err):
            self._loading = False
            self.b_save.setEnabled(True)
            if err is not None:
                self.status.setText("خطا: " + str(err)[:150])
                return
            self.info, allacc, self.saved, pend = res
            self.accounts = [a for a in allacc if a["email"].lower().endswith(cw.LOGIN_DOMAIN)]
            self.olds = [a for a in allacc if not a["email"].lower().endswith(cw.LOGIN_DOMAIN)]
            self.stage = {}
            if not self.info:
                self.status.setText("اکسل فروش در «تحلیل فروش» بارگذاری نشده است.")
            else:
                self.status.setText("%d مشتری در اکسل | %d همکار" % (len(self.info), len(self.accounts)))
            self._build(pend)
        self._bg(work, done)

    def _owner_of(self, ck, kd):
        if (ck, kd) in self.stage:
            return self.stage[(ck, kd)]
        a = self.saved.get((ck, kd))
        return a["assignee"] if a else None

    def _label(self, uid):
        for a in self.accounts:
            if a["user_id"] == uid:
                return a["label"]
        return "همکار دیگر"

    # ───────── رابط ─────────
    def _build(self, pend):
        try:
            self.tabs.currentChanged.disconnect(self._on_tab)
        except Exception:
            pass
        self.setUpdatesEnabled(False)
        try:
            self.tabs.clear()
            self.tables = {}
            self.queries = {}
            self._w2uid = {}
            self.tabs.addTab(self._make_free_tab(), "تخصیص‌نیافته")
            for a in self.accounts:
                n = pend.get(a["user_id"], 0)
                w = self._make_tab(a)
                self._w2uid[id(w)] = a["user_id"]
                self.tabs.addTab(w, "%s (%d)" % (a["label"], n) if n else a["label"])
            self.compare = CompareTab()
            self.compare.request_year = self._run_compare
            self.tabs.addTab(self.compare, "مقایسه فروش")
            self._compare_dirty = True
            self._dirty = set(self.tables)
            self._fill_free()
        finally:
            self.setUpdatesEnabled(True)
        self.tabs.currentChanged.connect(self._on_tab)
        self._on_tab(self.tabs.currentIndex())

    def _on_tab(self, _i):
        w = self.tabs.currentWidget()
        uid = self._w2uid.get(id(w)) if hasattr(self, "_w2uid") else None
        if uid and uid in self._dirty:
            self._fill_table(uid)
        elif w is getattr(self, "compare", None) and self._compare_dirty:
            self._run_compare(None)

    def _run_compare(self, year=None):
        """نمودارهای مقایسه در پس‌زمینه حساب می‌شوند و فقط وقتی زیرتبش باز شد."""
        try:
            df = self.get_df()
            exclude, mine = self.get_exclude(), self.get_mine()
        except Exception as ex:
            self.status.setText("مقایسه‌ی فروش: " + str(ex)[:120])
            return
        saved = dict(self.saved)
        labels = {a["user_id"]: a["label"] for a in self.accounts}
        self._compare_dirty = False
        self.compare.set_loading()

        def work():
            return cw.compare_data(df, saved, labels, exclude, year, mine)

        def done(d, err):
            if err is not None:
                self.status.setText("مقایسه‌ی فروش: " + str(err)[:120])
                return
            self.compare.show_result(d)
        self._bg(work, done)

    def _make_free_tab(self):
        w = QWidget()
        l = QVBoxLayout(w)
        self.free_list = QListWidget()
        fq = QLineEdit()
        fq.setPlaceholderText("جستجوی مشتری…")
        fq.textChanged.connect(lambda t: self._filter_list(self.free_list, t))
        self.queries["free"] = fq
        l.addWidget(QLabel("مشتری/گروه‌هایی که به هیچ همکاری داده نشده‌اند (مشتری جدید اکسل هم اینجا می‌آید):"))
        l.addWidget(fq)
        if not self.accounts:
            warn = QLabel("هیچ حساب همکاری پیدا نشد. حساب‌ها فقط وقتی اینجا می‌آیند که: (۱) SUPABASE_COWORKERS.sql اجرا شده باشد، "
                          "(۲) کاربر با ایمیلی مثل ali@sales.local در Supabase ساخته شده باشد، (۳) به جدول allowed_users اضافه شده باشد. "
                          "بعد از انجام، «بازخوانی» را بزنید. (حساب‌های مجاز بدون @sales.local: %d)" % len(self.olds))
            warn.setWordWrap(True)
            warn.setStyleSheet("background:#FEF3C7;color:#92400E;padding:8px;border-radius:6px;")
            l.addWidget(warn)
        l.addWidget(self.free_list)
        return w

    def _make_tab(self, acc):
        w = QWidget()
        l = QVBoxLayout(w)
        row = QHBoxLayout()
        q = QLineEdit()
        q.setPlaceholderText("جستجوی مشتری…")
        tb = QTableWidget(0, 3)
        tb.setHorizontalHeaderLabels(["مشتری", "پارکت", "ام دی اف"])
        tb.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tb.verticalHeader().setVisible(False)
        hh = tb.horizontalHeader()
        hh.setSectionResizeMode(COL_NAME, QHeaderView.Stretch)
        hh.setSectionResizeMode(COL_PQ, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(COL_MDF, QHeaderView.ResizeToContents)
        q.textChanged.connect(lambda t, T=tb: self._filter_table(T, t))
        row.addWidget(q, 1)
        if self.olds:
            cb = QComboBox()
            cb.addItem("حساب قدیمی همکار (برای پیشنهاد)…", "")
            for o in self.olds:
                cb.addItem(o["email"], o["user_id"])
            idx = cb.findData(acc.get("old_user_id") or "")
            cb.setCurrentIndex(max(idx, 0))
            b = QPushButton("پیشنهاد از سابقه")
            b.clicked.connect(lambda _=False, A=acc, C=cb: self._suggest(A, C))
            row.addWidget(cb)
            row.addWidget(b)
        l.addLayout(row)
        l.addWidget(tb, 1)
        tb.itemChanged.connect(lambda it, A=acc: self._changed(A, it))
        self.tables[acc["user_id"]] = tb
        self.queries[acc["user_id"]] = q
        return w

    def _filter_list(self, lst, text):
        t = cw.customer_key(text)
        for i in range(lst.count()):
            it = lst.item(i)
            it.setHidden(bool(t) and t not in cw.customer_key(it.text()))

    def _filter_table(self, tb, text):
        t = cw.customer_key(text)
        for r in range(tb.rowCount()):
            it = tb.item(r, COL_NAME)
            tb.setRowHidden(r, bool(t) and t not in cw.customer_key(it.text()))

    def _cell(self, ck, kd, uid, bought):
        """سلول تیک: فقط برای گروهی که مشتری در اکسل خریده؛ اگر مال همکار دیگری است نامش دیده می‌شود."""
        it = QTableWidgetItem("")
        if not bought:
            it.setText("—")
            it.setFlags(Qt.ItemIsEnabled)
            return it
        owner = self._owner_of(ck, kd)
        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        it.setCheckState(Qt.Checked if owner == uid else Qt.Unchecked)
        if owner not in (None, uid):
            it.setText("← " + self._label(owner))
        return it

    def _fill_free(self):
        self.free_list.clear()
        for ck, (nm, kinds) in self.info.items():
            free = [cw.KIND_FA[k] for k in cw.KINDS if k in kinds and self._owner_of(ck, k) is None]
            if free:
                self.free_list.addItem("%s   —   %s" % (nm, " + ".join(free)))
        self._filter_list(self.free_list, self.queries["free"].text())
        self._mark()

    def _fill_table(self, uid):
        tb = self.tables.get(uid)
        if tb is None:
            return
        self._busy = True
        tb.setUpdatesEnabled(False)
        try:
            tb.setRowCount(0)
            tb.setRowCount(len(self.info))
            for r, (ck, (nm, kinds)) in enumerate(self.info.items()):
                ni = QTableWidgetItem(nm)
                ni.setFlags(Qt.ItemIsEnabled)
                ni.setData(Qt.UserRole, ck)
                tb.setItem(r, COL_NAME, ni)
                for col, kd in KIND_COL.items():
                    c = self._cell(ck, kd, uid, kd in kinds)
                    c.setData(Qt.UserRole, ck)
                    tb.setItem(r, col, c)
            self._filter_table(tb, self.queries[uid].text())
        finally:
            tb.setUpdatesEnabled(True)
            self._busy = False
        self._dirty.discard(uid)

    def _fill_all(self):
        """بعد از هر تغییر تیک: فقط جدول همکارِ جاری و فهرست تخصیص‌نیافته تازه می‌شود؛ بقیه هنگام باز شدن."""
        self._dirty = set(self.tables)
        self._fill_free()
        w = self.tabs.currentWidget()
        uid = self._w2uid.get(id(w)) if hasattr(self, "_w2uid") else None
        if uid:
            self._fill_table(uid)

    def _changed(self, acc, it):
        if self._busy or it.column() not in KIND_COL:
            return
        ck = it.data(Qt.UserRole)
        kd = KIND_COL[it.column()]
        uid = acc["user_id"]
        if it.checkState() == Qt.Checked:
            self.stage[(ck, kd)] = uid
        elif self._owner_of(ck, kd) == uid:
            self.stage[(ck, kd)] = None
        self._normalize()
        self._fill_all()

    def _normalize(self):
        for k in list(self.stage):
            cur = self.saved.get(k)
            if self.stage[k] == (cur["assignee"] if cur else None):
                del self.stage[k]

    def _suggest(self, acc, cb):
        old = cb.currentData()
        if not old:
            QMessageBox.information(self, "پیشنهاد", "ابتدا حساب قدیمی همکار را انتخاب کنید.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            cw.save_account(self._req(), acc["user_id"], acc["label"], old)
            acc["old_user_id"] = old
            sug = cw.suggest_from_old(self._req(), old, set(self.info))
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "پیشنهاد", str(ex)[:200])
            return
        QApplication.restoreOverrideCursor()
        n = 0
        for ck in sug:
            for kd in self.info[ck][1]:
                if self._owner_of(ck, kd) is None:      # گروهِ دارای همکار دیگر دست نمی‌خورد
                    self.stage[(ck, kd)] = acc["user_id"]
                    n += 1
        self._normalize()
        self._fill_all()
        QMessageBox.information(self, "پیشنهاد", "%d تیک گذاشته شد (هنوز ذخیره نشده؛ بررسی کنید و «ذخیره» را بزنید)." % n)

    def _mark(self):
        self.b_save.setText("ذخیره و ارسال به همکاران" + (" (%d تغییر)" % len(self.stage) if self.stage else ""))

    # ───────── ذخیره ─────────
    def resend(self):
        """همان کاری که بعد از بارگذاری اکسل انجام می‌شود: صف حواله و سمپل/استند همه‌ی همکاران با اکسل فعلی."""
        if self._loading:
            return
        if not self.cloud["valid"]():
            self.status.setText("ابتدا وارد حساب ابری شوید.")
            return
        try:
            df = self.get_df()
            excl = self.get_exclude()
        except Exception as ex:
            self.status.setText("خطا: " + str(ex)[:150])
            return
        if df is None or len(df) == 0:
            QMessageBox.warning(self, "همکاران", "اکسل فروش در «تحلیل فروش» بارگذاری نشده است.")
            return
        req = self._req()
        self._loading = True
        self.b_save.setEnabled(False)
        self.status.setText("در حال ارسال…")

        def work():
            saved = cw.load_assignments(req)
            n = cw.sync_feed(req, df, saved, excl, use_cache=False)
            m = cw.push_free_snapshots(req, df, saved, excl, use_cache=False)
            return n, m

        def done(res, err):
            self._loading = False
            self.b_save.setEnabled(True)
            if err is not None:
                self.status.setText("ارسال ناموفق")
                QMessageBox.critical(self, "همکاران", "ارسال کامل نشد:\n" + str(err)[:300])
                return
            self.status.setText("%d مشتری در اکسل | %d همکار" % (len(self.info), len(self.accounts)))
            QMessageBox.information(self, "همکاران", "%d حواله‌ی جدید در صف قرار گرفت و سمپل/استند %d همکار به‌روز شد." % res)
        self._bg(work, done)

    def save(self):
        if self._loading:
            return
        if not self.stage:
            QMessageBox.information(self, "همکاران", "تغییری برای ذخیره نیست.")
            return
        try:
            df = self.get_df()
            excl = self.get_exclude()
        except Exception as ex:
            QMessageBox.critical(self, "همکاران", str(ex)[:300])
            return
        req = self._req()
        saved, changes = dict(self.saved), dict(self.stage)
        names = {ck: v[0] for ck, v in self.info.items()}
        self._loading = True
        self.b_save.setEnabled(False)
        self.status.setText("در حال ذخیره و ارسال…")

        def work():
            cw.apply_changes(req, saved, changes, names)
            new_saved = cw.load_assignments(req)
            n = cw.sync_feed(req, df, new_saved, excl)
            try:
                cw.push_free_snapshots(req, df, new_saved, excl)
            except Exception:
                pass
            return new_saved, n, cw.pending_counts(req)

        def done(res, err):
            self._loading = False
            self.b_save.setEnabled(True)
            if err is not None:
                self.status.setText("ذخیره کامل نشد")
                QMessageBox.critical(self, "همکاران", "ذخیره کامل نشد:\n" + str(err)[:300])
                return
            self.saved, n, pend = res
            self.stage = {}
            self.status.setText("%d مشتری در اکسل | %d همکار" % (len(self.info), len(self.accounts)))
            self._build(pend)
            QMessageBox.information(self, "همکاران", "ذخیره شد. %d حواله‌ی جدید برای ارسال به همکاران ثبت شد.\n"
                                    "همکار با اولین اتصال برنامه، حواله‌ها را دریافت می‌کند." % n)
        self._bg(work, done)
