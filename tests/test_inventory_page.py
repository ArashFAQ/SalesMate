"""تست دودی صفحه‌ی بالانس با Qt ساختگی (اگر PySide6 واقعی نصب نباشد)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import PySide6.QtWidgets  # noqa: F401
    HAVE_QT = True
except Exception:
    HAVE_QT = False

if not HAVE_QT:
    import fake_qt
    fake_qt.install()
    HAVE_FAKE = True
else:
    HAVE_FAKE = False

import inventory_core as ic  # noqa: E402


def make_xlsx(path, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


@unittest.skipUnless(HAVE_FAKE, "فقط با Qt ساختگی اجرا می‌شود")
class PageSmoke(unittest.TestCase):
    def setUp(self):
        import fake_qt
        import inventory_balance_page as ibp
        self.fq, self.ibp = fake_qt, ibp
        self.dir = tempfile.mkdtemp()
        self.calls = []
        self.cloud_state = {"maps": {}, "updated_at": ""}

        def request(method, path, body=None, extra=None):
            self.calls.append((method, path))
            if method == "GET":
                if self.cloud_state["maps"] or self.cloud_state["updated_at"]:
                    return 200, [{"mappings": self.cloud_state["maps"], "updated_at": self.cloud_state["updated_at"]}]
                return 200, []
            if method == "POST":
                self.cloud_state["maps"] = body[0]["mappings"]
                self.cloud_state["updated_at"] = body[0]["updated_at"]
                return 201, body
            return 200, None
        self.cloud = {"request": request, "enabled": lambda: True, "valid": lambda: True}
        fake_qt.QMessageBox.log.clear()
        # فایل‌های اکسل نمونه برای گلسرخ
        self.sysf = os.path.join(self.dir, "sys.xlsx")
        self.whf = os.path.join(self.dir, "wh.xlsx")
        make_xlsx(self.sysf, [["شناسه کالا", "شرح", "", "", "موجودی"],
                              [101, "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "", "", 10.0],
                              [102, "ورق ضخامت 18 mm طول 3660 mm عرض 1830 mm", "", "", 5.0]])
        make_xlsx(self.whf, [["ردیف", "کد کالا", "نام کالا", "واحد", "مقدار۱", "مقدار۲"],
                             [1, 9001, "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "ورق", 500, ""],
                             [2, 9002, "ورق ضخامت 18 mm طول 3660 mm عرض 1830 mm", "ورق", 100, ""]])

    def page(self):
        return self.ibp.InventoryBalancePage(object(), self.dir, cloud=self.cloud)

    def test_full_flow(self):
        pg = self.page()
        self.assertTrue(pg._load_file("sys", "گلسرخ", self.sysf))
        self.assertTrue(pg._load_file("wh", "گلسرخ", self.whf))
        self.assertEqual(len(pg.system["گلسرخ"]), 2)
        self.assertEqual(len(pg.warehouse["گلسرخ"]), 2)
        # جدول سامانه پر شده و انتخاب → پنل نگاشت
        pg.active_wh = "گلسرخ"
        pg._fill_sys()
        self.assertEqual(pg.tbl_sys.rowCount(), 2)
        pg.tbl_sys.selectRow(0)
        self.assertEqual(pg._cur_sys_code(), "101")
        self.assertEqual(pg.tbl_free.rowCount(), 2)
        # کد 9001 باید بالاتر (شباهت بیشتر) بیاید
        self.assertEqual(pg.tbl_free.item(0, 1).data(self.fq.Qt.UserRole), "9001")
        pg.tbl_free.selectRow(0)
        pg.add_selected_free()
        self.assertEqual(pg.mappings["گلسرخ"]["101"], ["9001"])
        # به کالای بعدیِ بدون نگاشت رفت
        self.assertEqual(pg._cur_sys_code(), "102")
        self.assertEqual(pg.tbl_free.rowCount(), 1)             # 9001 دیگر آزاد نیست
        # مقایسه
        pg._recompute()
        d = {r["sysCode"]: r for r in pg.results if r["warehouse"] == "گلسرخ"}
        self.assertTrue(d["101"]["mapped"] and not d["102"]["mapped"])
        # ذخیره‌ی محلی و بازگشت بعد از «ری‌استارت»
        pg2 = self.page()
        self.assertEqual(pg2.mappings["گلسرخ"]["101"], ["9001"])
        self.assertEqual(len(pg2.system["گلسرخ"]), 2)
        pg2._refresh_all()
        self.assertEqual(pg2.tbl_sys.rowCount(), 2)

    def test_threshold_selection_and_exports(self):
        pg = self.page()
        pg._load_file("sys", "گلسرخ", self.sysf)
        pg._load_file("wh", "گلسرخ", self.whf)
        ic.add_mapping(pg.mappings, "گلسرخ", "101", ["9001"])
        ic.add_mapping(pg.mappings, "گلسرخ", "102", ["9002"])
        pg._maps_changed()
        pg.threshold = 0.0
        pg._recompute()
        pg.select_decreases()
        sel = pg._selected_results()
        self.assertTrue(all(r["diff"] < 0 for r in sel))
        self.fq.QFileDialog.save_path = os.path.join(self.dir, "k.xlsx")
        self.fq.QMessageBox.log.clear()
        if sel:
            pg.export_khoroj()
            self.assertTrue(os.path.exists(self.fq.QFileDialog.save_path))
        self.fq.QFileDialog.save_path = os.path.join(self.dir, "all.xlsx")
        pg.export_xlsx()
        self.assertTrue(os.path.exists(self.fq.QFileDialog.save_path))

    def test_bad_file_is_reported(self):
        pg = self.page()
        bad = os.path.join(self.dir, "bad.xlsx")
        open(bad, "wb").close()
        self.assertFalse(pg._load_file("sys", "بهارستان", bad))
        self.assertTrue(any(k == "warn" for k, _ in self.fq.QMessageBox.log))
        self.assertEqual(pg.system.get("بهارستان"), None)

    def test_cloud_sync_paths(self):
        pg = self.page()
        ic.add_mapping(pg.mappings, "گلسرخ", "101", ["9001"])
        pg._maps_changed()
        # ابر خالی + محلی پر → ارسال (thread واقعی؛ منتظر می‌مانیم)
        pg._run_bg = lambda fn, cb: cb(*self._call(fn))
        pg.sync_maps(manual=True)
        self.assertEqual(self.cloud_state["maps"], {"گلسرخ": {"101": ["9001"]}})
        self.assertIn(("POST", "/rest/v1/inventory_code_maps?on_conflict=id"), self.calls)
        # ابر جدیدتر و محلی بدون تغییر جدید → دریافت
        self.cloud_state["maps"] = {"گلسرخ": {"101": ["9001"], "102": ["9002"]}}
        self.cloud_state["updated_at"] = "2099-01-01T00:00:00Z"
        pg.sync_maps(manual=True)
        self.assertEqual(pg.mappings["گلسرخ"]["102"], ["9002"])

    def _call(self, fn):
        try:
            return fn(), None
        except Exception as ex:
            return None, ex


if __name__ == "__main__":
    unittest.main()
