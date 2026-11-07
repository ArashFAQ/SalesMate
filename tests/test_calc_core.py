"""تست منطق «مشتریان و محاسبات» — باید با ابزار وب قبلی یکسان باشد."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))
import calc_core as cc  # noqa: E402


class Parse(unittest.TestCase):
    def test_n(self):
        self.assertEqual(cc.n("۱۲۳"), 123)
        self.assertEqual(cc.n("1,234,567"), 1234567)
        self.assertEqual(cc.n("2×3"), 6)
        self.assertEqual(cc.n("10÷4"), 2.5)
        self.assertEqual(cc.n("2*(3+4)"), 14)
        self.assertEqual(cc.n("3.66×1.83×0.008"), 3.66 * 1.83 * 0.008)
        self.assertEqual(cc.n("1٫5"), 1.5)
        self.assertEqual(cc.n("-2.5"), -2.5)
        for bad in ("abc", "", None, "1/0", "5--3", "2.5.3", "(1+2", "1e5"):
            self.assertEqual(cc.n(bad), 0, bad)

    def test_parse_amount(self):
        self.assertEqual(cc.parse_amount("۱,۲۳۴ ریال"), 1234)
        self.assertEqual(cc.parse_amount("x"), 0)

    def test_trunc_fmt(self):
        self.assertEqual(cc.trunc(10.289, 2), 10.28)
        self.assertEqual(cc.trunc(-1.99, 0), -1)
        self.assertEqual(cc.fmt(1234567), "1,234,567")
        self.assertEqual(cc.fmt(10.2, 2), "10.20")
        self.assertEqual(cc.fmt(None), "—")
        self.assertEqual(cc.fmt(float("nan")), "—")
        self.assertEqual(cc.fmt_free_cubic(20.56), "20.56")
        self.assertEqual(cc.fmt_free_cubic(20), "20")
        self.assertEqual(cc.fmt_free_cubic(100.5), "100.5")
        self.assertEqual(cc.fmt_free_cubic(0), "")


class Calc(unittest.TestCase):
    def test_tax_per(self):
        self.assertIsNone(cc.calc_tax(0))
        self.assertEqual(cc.calc_tax(11000), 1000)
        self.assertEqual(cc.calc_tax(14793600000), 1344872727)
        self.assertIsNone(cc.calc_per(0, 5))
        self.assertIsNone(cc.calc_per(100, 0))
        # مبلغ ÷ 1.1 ÷ متر مکعب + 1 سپس بُرش
        self.assertEqual(cc.calc_per(24960000000, 20.56), int(24960000000 / 1.1 / 20.56 + 1))

    def test_row_and_summary(self):
        sizes = cc.default_sizes()
        self.assertEqual(len(sizes), 9)
        s = sizes[0]
        r = cc.row_calc(s, {"count": 192, "amount": 14793600000})
        self.assertEqual(r["cubic"], 10.28)
        self.assertEqual(r["per"], int(14793600000 / 1.1 / 10.28 + 1))
        calc = {s["id"]: {"count": 192, "amount": 14793600000}, sizes[1]["id"]: {"count": 48, "amount": 5760000000}}
        sm = cc.summary(sizes, calc)
        self.assertEqual(sm["sheets"], 240)
        self.assertEqual(sm["amount"], 14793600000 + 5760000000)
        self.assertEqual(sm["tax"], cc.calc_tax(14793600000) + cc.calc_tax(5760000000))
        self.assertEqual(sm["cubic"], cc.trunc(10.28 + cc.trunc(0.1071648 * 48, 2), 2))

    def test_custom_size(self):
        s = cc.new_custom_size("تست", "2.44", "1.22", "8", 5)
        self.assertEqual(s["id"], "custom_5")
        self.assertTrue(s["custom"])
        self.assertAlmostEqual(s["volume"], 2.44 * 1.22 * 0.008)
        self.assertEqual(s["sourceFormula"], "2.44×1.22×0.008")
        self.assertEqual(cc.new_custom_size("a", "3", "1", "10", 1)["sourceFormula"], "3×1×0.01")
        self.assertIsNone(cc.new_custom_size("", "1", "1", "1", 1))
        self.assertIsNone(cc.new_custom_size("a", "0", "1", "1", 1))


class Customers(unittest.TestCase):
    CU = [{"customer": "علی رضایی", "national_id": "0012345678", "phone": "09121234567"},
          {"customer": "كريم", "national_id": "", "phone": ""}]

    def test_search(self):
        self.assertEqual(len(cc.customer_matches(self.CU, "")), 2)
        self.assertEqual(cc.customer_matches(self.CU, "۰۰۱۲")[0][1], 0)
        self.assertEqual(cc.customer_matches(self.CU, "کریم")[0][1], 1)  # ك/ي عربی
        self.assertEqual(cc.customer_matches(self.CU, "0912")[0][1], 0)
        self.assertEqual(cc.customer_matches(self.CU, "zzz"), [])
        self.assertEqual(len(cc.customer_matches(self.CU * 50, "", 12)), 12)

    def test_clean(self):
        c = cc.clean_customer(" علی ", "۰۰۱۲", "۰۹۱۲")
        self.assertEqual(c, {"customer": "علی", "national_id": "0012", "phone": "0912"})
        self.assertIsNone(cc.clean_customer("  ", "1", "2"))

    def test_same(self):
        self.assertTrue(cc.same_customer(cc.picked_from(self.CU[0]), self.CU[0]))
        self.assertFalse(cc.same_customer(None, self.CU[0]))


class StoreCloud(unittest.TestCase):
    def test_store_roundtrip(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "c.json")
        st = cc.load_store(p)
        self.assertEqual(st["customers"], [])
        self.assertEqual(st["freeCalc"], cc.FREE_DEFAULT)
        st["customers"].append({"customer": "x", "national_id": "", "phone": ""})
        cc.save_store(p, st)
        cc.save_store(p, st)
        self.assertEqual(len(cc.load_store(p)["customers"]), 1)
        open(p, "w").write("{bad")
        self.assertEqual(len(cc.load_store(p)["customers"]), 1)  # از .bak

    def test_payload(self):
        st = cc.empty_store()
        st["customers"] = [{"customer": "a", "national_id": "1", "phone": "2"}]
        calc = {s["id"]: {"count": 1, "amount": 2} for s in st["sizes"]}
        pl = cc.build_payload(st, calc)
        s2, c2 = cc.apply_payload(pl)
        self.assertEqual(s2["customers"], st["customers"])
        self.assertEqual(c2, calc)
        bk = cc.build_backup(st, calc)
        self.assertIn("exported_at", bk)
        self.assertTrue(cc.validate_payload(bk))
        self.assertFalse(cc.validate_payload({"customers": []}))
        with self.assertRaises(ValueError):
            cc.apply_payload({"customers": {}})

    def test_owner_rule(self):
        pl = {"customers": [1, 2], "sizes": [], "calc": {}}
        self.assertTrue(cc.is_owner("Arash.E.Maleki@gmail.com"))
        self.assertEqual(cc.payload_for_push(pl, "arash.e.maleki@gmail.com")["customers"], [1, 2])
        self.assertEqual(cc.payload_for_push(pl, "other@x.com")["customers"], [])
        self.assertEqual(cc.payload_for_pull(pl, "other@x.com", ["L"])["customers"], ["L"])
        self.assertEqual(cc.payload_for_pull(pl, cc.OWNER_EMAIL, ["L"])["customers"], [1, 2])


if __name__ == "__main__":
    unittest.main()


class TestFreeExact(unittest.TestCase):
    def test_free_case(self):
        import calc_core as cc
        r = cc.free_result(240240000000, 153.9811727516194)
        self.assertEqual(r["per"], 1418366022)
        self.assertEqual(r["tax"], 21840000000)
