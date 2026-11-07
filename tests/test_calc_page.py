"""تست دودی صفحه‌ی مشتریان و محاسبات با Qt ساختگی."""
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

import calc_core as cc  # noqa: E402


@unittest.skipUnless(not HAVE_QT, "فقط با Qt ساختگی اجرا می‌شود")
class PageSmoke(unittest.TestCase):
    def setUp(self):
        import fake_qt
        import calc_customers_page as ccp
        self.fq, self.ccp = fake_qt, ccp
        self.dir = tempfile.mkdtemp()
        self.calls = []
        self.remote = {}

        def request(method, path, body=None, extra=None):
            self.calls.append((method, path))
            if method == "POST":
                self.remote = body[0]
                return 201, body
            if method == "GET":
                return 200, [self.remote] if self.remote else []
            return 200, None
        self.email = cc.OWNER_EMAIL
        self.cloud = {"request": request, "enabled": lambda: True, "valid": lambda: True,
                      "user": lambda: {"user_id": "u1", "email": self.email}}
        fake_qt.QMessageBox.log.clear()
        fake_qt.QMessageBox.answer = 1
        self.page = ccp.CalcCustomersPage(None, self.dir, self.cloud)

    def test_row_typing(self):
        p = self.page
        sid = p.store["sizes"][0]["id"]
        rw = p._row_widgets[sid]
        rw["count"].setText("۱۹۲")
        p._row_edit(sid, "count", rw["count"])
        rw["amount"].setText("14793600000")
        p._row_edit(sid, "amount", rw["amount"])
        self.assertEqual(p.calc[sid], {"count": 192, "amount": 14793600000})
        self.assertEqual(rw["count"].text(), "192")
        self.assertEqual(rw["amount"].text(), "14,793,600,000")
        self.assertIn("10", rw["cubic"].text().replace("۱", "1").replace("۰", "0"))
        self.assertTrue(p.k_tax_copy._enabled)

    def test_reset_and_persist(self):
        p = self.page
        sid = p.store["sizes"][0]["id"]
        p.calc[sid]["count"] = 5
        p.reset_calculations()
        self.assertEqual(p.calc[sid]["count"], 0)
        self.assertEqual(p.store["freeCalc"], {"amount": 0, "cubic": 0})
        p2 = self.ccp.CalcCustomersPage(None, self.dir, self.cloud)
        self.assertEqual(p2.store["freeCalc"], {"amount": 0, "cubic": 0})

    def test_free(self):
        p = self.page
        p.free_cubic.setText("2*10")
        p._free_live("cubic")
        p._free_commit("cubic")
        p.free_amount.setText("2200")
        p._free_live("amount")
        self.assertEqual(p._free_vals["tax"], cc.calc_tax(2200))
        self.assertEqual(p._free_vals["per"], cc.calc_per(2200, 20))
        p._free_commit("cubic")
        self.assertEqual(p.store["freeCalc"]["cubic"], 20)

    def test_customers_flow(self):
        p = self.page
        p.f_name.setText("علی")
        p.f_nat.setText("۰۰۱۲")
        p.f_phone.setText("0912")
        p.open_form(-1)
        p.f_name.setText("علی")
        p.f_nat.setText("۰۰۱۲")
        p.save_form()
        self.assertEqual(p.store["customers"][0]["national_id"], "0012")
        import time
        for _ in range(50):
            if any(c[0] == "POST" for c in self.calls):
                break
            time.sleep(0.02)
        self.assertTrue(any(c[0] == "POST" for c in self.calls))  # مالک: ارسال خودکار
        p._use_for_calc(0)
        self.assertEqual(p.store["pickedCustomer"]["customer"], "علی")
        p.delete_customer(0)
        self.assertEqual(p.store["customers"], [])
        self.assertIsNone(p.store["pickedCustomer"])

    def test_non_owner_no_autopush(self):
        self.email = "x@y.com"
        p = self.page
        p.open_form(-1)
        p.f_name.setText("زهرا")
        p.save_form()
        self.assertFalse(any(c[0] == "POST" for c in self.calls))

    def test_custom_size(self):
        p = self.page
        n0 = len(p.store["sizes"])
        s = cc.new_custom_size("سفارشی", "2", "1", "10", 99)
        p.add_size(s)
        self.assertEqual(len(p.store["sizes"]), n0 + 1)
        p.delete_size("custom_99")
        self.assertEqual(len(p.store["sizes"]), n0)
        self.assertNotIn("custom_99", p.calc)

    def test_backup_roundtrip(self):
        p = self.page
        p.store["customers"].append({"customer": "q", "national_id": "", "phone": ""})
        f = os.path.join(self.dir, "b.json")
        self.fq.QFileDialog.save_path = f
        p.export_backup()
        p.store["customers"].clear()
        self.fq.QFileDialog.open_path = f
        p.import_backup()
        self.assertEqual(p.store["customers"][0]["customer"], "q")

    def test_cloud_pull_nonowner_keeps_local(self):
        p = self.page
        self.email = "x@y.com"
        p.store["customers"] = [{"customer": "محلی", "national_id": "", "phone": ""}]
        pl = cc.build_payload(cc.empty_store(), {})
        pl["customers"] = [{"customer": "ابری", "national_id": "", "phone": ""}]
        p._after_pull([{"payload": pl}], None)
        self.assertEqual(p.store["customers"][0]["customer"], "محلی")


if __name__ == "__main__":
    unittest.main()
