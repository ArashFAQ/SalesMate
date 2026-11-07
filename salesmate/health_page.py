# -*- coding: utf-8 -*-
"""پنجره‌ی «سلامت داده» — گزارش مشکل‌های داده با دکمه‌ی اصلاح (همیشه پشتیبان + تأیید)."""
import html
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextBrowser, QMessageBox,
)

try:
    import app_core as core
    import health_core as hc
    from core_utils import fa_digits, amount, fmt
except Exception:  # pragma: no cover
    from salesmate import app_core as core
    from salesmate import health_core as hc
    from salesmate.core_utils import fa_digits, amount, fmt


def _swallow():
    try:
        core._swallow()
    except Exception:
        pass


def _esc(x):
    return html.escape(str(x if x is not None else ""))


class HealthDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("سلامت داده")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(900, 720)
        lay = QVBoxLayout(self)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setStyleSheet("QTextBrowser{background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:8px;font-size:13px;}")
        lay.addWidget(self.view, 1)
        self.btn_row = QVBoxLayout()
        lay.addLayout(self.btn_row)
        top = QHBoxLayout()
        again = QPushButton("⟳ بررسی دوباره")
        again.clicked.connect(self.run)
        close = QPushButton("بستن")
        close.clicked.connect(self.accept)
        for b in (again, close):
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet("QPushButton{background:#E2E8F0;color:#0F172A;border:none;border-radius:10px;padding:9px 18px;font-weight:700;}")
        top.addWidget(again)
        top.addStretch(1)
        top.addWidget(close)
        lay.addLayout(top)
        self.run()

    # ───────────── بررسی ─────────────
    def _clear_buttons(self):
        while self.btn_row.count():
            it = self.btn_row.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
            elif it.layout():
                while it.layout().count():
                    x = it.layout().takeAt(0)
                    if x.widget():
                        x.widget().deleteLater()

    def _add_btn(self, text, fn, color="#1565C0"):
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet("QPushButton{background:%s;color:#fff;border:none;border-radius:10px;padding:10px 16px;font-weight:700;}" % color)
        b.clicked.connect(fn)
        self.btn_row.addWidget(b)

    def run(self):
        self._clear_buttons()
        parts, issues = [], 0
        c = core.db()
        try:
            s = hc.summarize(c)
            store_rows = c.execute("SELECT id, customer, invoice_no, date, total FROM store_sales").fetchall()
        finally:
            c.close()

        def sec(title, n, body, ok_text):
            if n:
                return "<h3 style='color:#B91C1C'>⚠ %s — %s</h3>%s" % (title, fa_digits(n), body)
            return "<h3 style='color:#047857'>✓ %s</h3><div style='color:#64748B'>%s</div>" % (title, ok_text)

        # ۱) حواله‌ی تکراری
        dups = s["dup_invoices"]
        extra = sum(len(g) - 1 for g in dups)
        body = ""
        if dups:
            issues += extra
            body = "<table cellspacing=0 cellpadding=4 border=1 style='border-collapse:collapse;border-color:#E2E8F0'><tr style='background:#F1F5F9'><td>مشتری</td><td>شماره</td><td>تاریخ</td><td>مبالغ (id)</td></tr>"
            for g in dups[:40]:
                body += "<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
                    _esc(g[0]["customer"]), _esc(fa_digits(g[0]["no"])), _esc(fa_digits(g[0]["date"])),
                    "، ".join("%s (#%s)" % (fa_digits(f"{x['total']:,}"), x["id"]) for x in g))
            body += "</table><div style='color:#64748B'>از هر گروه، کمترین id می‌ماند.</div>"
        parts.append(sec("حواله‌های تکراری", extra, body, "حواله‌ی تکراری نیست."))
        if dups:
            self._add_btn("حذف حواله‌های تکراری (%s)" % fa_digits(extra), lambda: self.fix_invoice_dups(dups), "#DC2626")

        # ۲) فروش فروشگاهِ تکراری
        try:
            try:
                from stats_pages import find_store_duplicates
            except Exception:
                from salesmate.stats_pages import find_store_duplicates
            sd = find_store_duplicates([(r[0], r[1], r[2], r[3], amount(r[4])) for r in store_rows])
        except Exception:
            _swallow()
            sd = []
        tot = 0
        by = {r[0]: r for r in store_rows}
        for d, _k in sd:
            tot += amount(by[d][4])
        parts.append(sec("فروش‌های تکراری فروشگاه", len(sd),
                         "<div>جمع مبلغ تکراری: %s ریال</div>" % fa_digits(f"{int(tot):,}"), "فروش تکراری در فروشگاه نیست."))
        issues += len(sd)
        if sd:
            self._add_btn("حذف تکراری‌های فروشگاه (%s)" % fa_digits(len(sd)), self.fix_store_dups, "#DC2626")
        self._add_btn("مقایسه‌ی فروشگاه با اکسل فروش…", self.open_store_diff, "#0F172A")

        # ۳) املاهای مختلف نام
        nv = s["name_variants"]
        body = ""
        if nv:
            issues += len(nv)
            body = "<ul>" + "".join("<li>" + "  |  ".join("%s (%s)" % (_esc(n), fa_digits(k)) for n, k in g) + "</li>" for g in nv[:40]) + "</ul>"
            body += "<div style='color:#64748B'>این‌ها از نظر برنامه یک مشتری حساب می‌شوند (در تحلیل فروش یکی می‌شوند)؛ فقط در حواله‌ها/فروشگاه جدا نوشته شده‌اند.</div>"
        parts.append(sec("نام مشتری با چند املا", len(nv), body, "هر مشتری یک جور نوشته شده."))

        # ۴) حواله‌ی ناقص
        bd = s["bad_invoices"]
        body = ""
        if bd:
            issues += len(bd)
            body = "<ul>" + "".join("<li>#%s — %s — %s — %s ریال</li>" % (x["id"], _esc(x["customer"] or "(بدون نام)"), _esc(fa_digits(x["date"])), fa_digits(f"{x['total']:,}")) for x in bd[:40]) + "</ul>"
        parts.append(sec("حواله‌ی بدون نام یا با مبلغ صفر", len(bd), body, "همه‌ی حواله‌ها نام و مبلغ دارند."))

        # ۵) استعلام ذخیره‌شده‌ی شبیه حواله
        try:
            try:
                from inquiry_page import find_inquiry_invoice_matches
            except Exception:
                from salesmate.inquiry_page import find_inquiry_invoice_matches
            qm = find_inquiry_invoice_matches()
        except Exception:
            _swallow()
            qm = []
        body = ""
        if qm:
            issues += len(qm)
            body = "<ul>" + "".join("<li>%s — %s ریال ↔ حواله %s (%s)</li>" % (
                _esc(it.get("buyer")), fa_digits(fmt(it.get("total") or 0)), _esc(fa_digits(v["no"])), "، ".join(why)) for it, v, why in qm[:40]) + "</ul>"
        parts.append(sec("استعلام ذخیره‌شده‌ی شبیه حواله", len(qm), body, "استعلام ذخیره‌شده‌ی شبیه حواله نیست."))
        if qm:
            self._add_btn("بررسی استعلام‌های شبیه حواله…", self.open_inq, "#0F172A")

        head = ("<h2 style='color:%s'>%s</h2>" % (("#B91C1C", "%s مورد نیاز به بررسی" % fa_digits(issues)) if issues else ("#047857", "همه چیز سالم است ✓")))
        self.view.setHtml("<div dir='rtl'>" + head + "".join(parts) + "</div>")
        self.issue_count = issues

    # ───────────── اصلاح‌ها ─────────────
    def _backup(self):
        try:
            core.rotate_cloud_local_backup(max_keep=5, force=True)
        except Exception:
            _swallow()

    def fix_invoice_dups(self, dups):
        ids = [x["id"] for g in dups for x in g[1:]]
        if QMessageBox.question(
                self, "حذف حواله‌های تکراری",
                "%s حواله‌ی تکراری حذف می‌شود و از هر گروه یکی می‌ماند.\nاز ابر هم حذف می‌شود. قبلش پشتیبان گرفته می‌شود.\nادامه؟" % fa_digits(len(ids)),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self._backup()
        c = core.db()
        invs = []
        try:
            for i in ids:
                r = c.execute("SELECT customer, invoice_no, date, time, total FROM invoices WHERE id=?", (i,)).fetchone()
                if r:
                    invs.append({"customer": r[0] or "", "invoiceNo": r[1] or "", "date": r[2] or "", "time": r[3] or "", "total": str(r[4] or "0")})
                c.execute("DELETE FROM invoices WHERE id=?", (i,))
            c.commit()
        finally:
            c.close()

        def _run():
            for inv in invs:
                try:
                    core.delete_invoice_from_cloud(inv)
                except Exception:
                    _swallow()
        threading.Thread(target=_run, daemon=True).start()
        try:
            core.schedule_supabase_sync()
        except Exception:
            _swallow()
        try:
            self.win.refresh_all()
        except Exception:
            _swallow()
        QMessageBox.information(self, "سلامت داده", "%s حواله‌ی تکراری حذف شد." % fa_digits(len(ids)))
        self.run()

    def fix_store_dups(self):
        try:
            self.win.parquet_page.remove_store_duplicates()
        except Exception as ex:
            QMessageBox.warning(self, "سلامت داده", "انجام نشد:\n" + str(ex))
        self.run()

    def open_store_diff(self):
        try:
            self.win.parquet_page.show_store_diff()
        except Exception as ex:
            QMessageBox.warning(self, "سلامت داده", "انجام نشد:\n" + str(ex))

    def open_inq(self):
        try:
            try:
                from inquiry_page import ask_prune_saved_inquiries
            except Exception:
                from salesmate.inquiry_page import ask_prune_saved_inquiries
            ask_prune_saved_inquiries(self)
        except Exception as ex:
            QMessageBox.warning(self, "سلامت داده", "انجام نشد:\n" + str(ex))
        self.run()
