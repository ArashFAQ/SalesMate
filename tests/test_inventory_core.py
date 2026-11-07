"""تست منطق بالانس موجودی (inventory_core) — بدون PySide6."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))

import inventory_core as ic  # noqa: E402


def make_xlsx(path, rows):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    wb.save(path)


class Basics(unittest.TestCase):
    def test_cell_and_num(self):
        self.assertEqual(ic.cell_str(123.0), "123")
        self.assertEqual(ic.cell_str(None), "")
        self.assertEqual(ic.to_num("۱٬۲۳۴٫۵"), 1234.5)
        self.assertEqual(ic.to_num("abc"), 0.0)
        self.assertEqual(ic.norm_code("00123.0"), "123")
        self.assertEqual(ic.norm_code("۰۱۲"), "12")
        self.assertEqual(ic.norm_code("AB-1"), "AB-1")

    def test_dims(self):
        self.assertEqual(ic.parse_dims("ورق mdf ضخامت 16 mm طول 3660 mm عرض 1830 mm"), (16.0, 3660.0, 1830.0))
        self.assertEqual(ic.parse_dims("ورق 3660×1830×16"), (16.0, 3660.0, 1830.0))
        self.assertEqual(ic.parse_dims("ورق ۱۸ mm"), (18.0, None, None))
        self.assertEqual(ic.parse_dims("بدون ابعاد"), (None, None, None))

    def test_moshtarak(self):
        d = ic.moshtarak_defaults((18.0, None, None), "ورق مشترک 18 mm")
        self.assertEqual(d, (18.0, 3660.0, 1830.0))
        self.assertEqual(ic.moshtarak_defaults((8.0, None, None), "غیر قابل تولید 8 mm"), (8.0, 2800.0, 1220.0))
        self.assertEqual(ic.moshtarak_defaults((18.0, None, None), "ورق عادی 18 mm"), (18.0, None, None))
        self.assertAlmostEqual(ic.vol_per_sheet(16, 3660, 1830), 0.016 * 3.66 * 1.83)


class Parsing(unittest.TestCase):
    def test_system_two_layouts(self):
        rows = [
            ["شناسه کالا", "شرح", "", "", "موجودی"],
            ["101.0", "ورق درجه 1 ضخامت 16 mm", "", 2.0, 12.5],          # چیدمان A: qty=col4
            [None, "102", "ورق دیگر", "", "", 7.25],                      # چیدمان B: code=col1, qty=col5
            ["101", "ورق تکراری", "", 0, 1.5],                            # ادغام کد تکراری
            ["جمع", "", "", "", 99],                                      # نادیده
        ]
        items, warn = ic.parse_system_rows(rows)
        d = {i["code"]: i for i in items}
        self.assertEqual(sorted(d), ["101", "102"])
        self.assertEqual(d["101"]["qty"], 14.0)
        self.assertNotIn("درجه", d["101"]["desc"])
        self.assertEqual(d["102"]["qty"], 7.25)
        self.assertEqual(warn, [])

    def test_system_empty_warns(self):
        items, warn = ic.parse_system_rows([["x", "y"]])
        self.assertEqual(items, [])
        self.assertTrue(warn)

    def test_warehouse(self):
        rows = [
            ["ردیف", "کد کالا", "نام کالا", "واحد", "مقدار۱", "مقدار۲"],
            [1, "5001", "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "ورق", 100, ""],
            [2, "5002", "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "پالت", 2, 70],     # qty2>0 → ورق=70
            [3, "5003", "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "پالت", 2, 0],      # 2*48 ورق
            [4, "5004", "ورق مشترک 18 mm", "ورق", 10, ""],                              # پیش‌فرض مشترک
            [5, "5005", "کالای بدون ابعاد", "ورق", 10, ""],                             # هشدار ابعاد
            [6, "5006", "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "متر", 10, ""],     # هشدار واحد
            [7, "جمع", "جمع کل", "", 1, 1],
            [8, "5001", "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "ورق", 50, ""],     # ادغام
        ]
        items, warn = ic.parse_warehouse_rows(rows)
        d = {i["code"]: i for i in items}
        vps = ic.vol_per_sheet(16, 3660, 1830)
        self.assertAlmostEqual(d["5001"]["qty"], round(150 * vps, 3))
        self.assertEqual(d["5001"]["sheets"], 150)
        self.assertEqual(d["5002"]["sheets"], 70)
        self.assertEqual(d["5003"]["sheets"], 96)
        self.assertAlmostEqual(d["5004"]["qty"], round(10 * ic.vol_per_sheet(18, 3660, 1830), 3))
        self.assertEqual(d["5005"]["qty"], 0)
        self.assertEqual(d["5006"]["qty"], 0)
        self.assertEqual(len(warn), 2)
        self.assertNotIn("جمع", d)


class ReadTable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def p(self, name):
        return os.path.join(self.tmp, name)

    def test_xlsx_and_disguised_xls(self):
        make_xlsx(self.p("a.xlsx"), [["کد", "نام"], [1, "الف"]])
        rows, info = ic.read_table(self.p("a.xlsx"))
        self.assertEqual(info["format"], "xlsx")
        self.assertEqual(rows[1][1], "الف")
        os.rename(self.p("a.xlsx"), self.p("b.xls"))               # xlsx با پسوند xls
        rows, info = ic.read_table(self.p("b.xls"))
        self.assertEqual(info["format"], "xlsx")

    def test_first_nonempty_sheet(self):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.title = "خالی"
        ws = wb.create_sheet("داده")
        ws.append(["x", 1])
        wb.save(self.p("c.xlsx"))
        rows, info = ic.read_table(self.p("c.xlsx"))
        self.assertEqual(info["sheet"], "داده")

    def test_csv_cp1256_and_semicolon(self):
        text = "کد;نام\n1;الف\n"
        with open(self.p("d.csv"), "wb") as f:
            f.write(text.encode("cp1256"))
        rows, info = ic.read_table(self.p("d.csv"))
        self.assertEqual(info["format"], "csv")
        self.assertEqual(rows[1], ["1", "الف"])

    def test_html_table(self):
        html = "<html><body><table><tr><th>کد</th><th>نام</th></tr><tr><td>1</td><td>الف</td></tr></table></body></html>"
        with open(self.p("e.xls"), "w", encoding="utf-8") as f:
            f.write(html)
        rows, info = ic.read_table(self.p("e.xls"))
        self.assertEqual(info["format"], "html")
        self.assertEqual(rows[1], ["1", "الف"])

    def test_errors(self):
        with self.assertRaises(ic.FileFormatError):
            ic.read_table(self.p("nope.xlsx"))
        open(self.p("empty.xlsx"), "wb").close()
        with self.assertRaises(ic.FileFormatError):
            ic.read_table(self.p("empty.xlsx"))
        with open(self.p("old.xls"), "wb") as f:
            f.write(b"\xd0\xcf\x11\xe0" + b"\x00" * 50)
        with self.assertRaises(ic.FileFormatError):
            ic.read_table(self.p("old.xls"))


class Mapping(unittest.TestCase):
    def test_add_remove_validation(self):
        m = {}
        self.assertEqual(ic.add_mapping(m, "گلسرخ", "101", ["5001", "5002"]), (2, []))
        n, err = ic.add_mapping(m, "گلسرخ", "101", ["5001"])
        self.assertEqual(n, 0)
        self.assertIn("قبلاً برای همین", err[0])
        n, err = ic.add_mapping(m, "گلسرخ", "102", ["5002"])
        self.assertEqual(n, 0)
        self.assertIn("دیگری", err[0])
        # همان کد در انبار دیگر آزاد است
        self.assertEqual(ic.add_mapping(m, "خلیج", "102", ["5002"])[0], 1)
        ic.remove_mapping(m, "گلسرخ", "101", "5001")
        self.assertEqual(m["گلسرخ"]["101"], ["5002"])

    def test_merge(self):
        a = {"گلسرخ": {"101": ["1"]}}
        b = {"گلسرخ": {"101": ["2"], "102": ["1"]}}      # 1 در a به 101 وصل است
        out = ic.merge_mappings(a, b)
        self.assertEqual(out["گلسرخ"]["101"], ["1", "2"])
        self.assertEqual(out["گلسرخ"]["102"], [])

    def test_suggest(self):
        sysi = [{"code": "101", "desc": "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "qty": 1},
                {"code": "777", "desc": "کالای عجیب", "qty": 1}]
        whi = [{"code": "9001", "name": "ورق ضخامت 16 mm طول 3660 mm عرض 1830 mm", "qty": 0, "sheets": 0},
               {"code": "9002", "name": "ورق ضخامت 18 mm طول 3660 mm عرض 1830 mm", "qty": 0, "sheets": 0},
               {"code": "777", "name": "هر چیزی", "qty": 0, "sheets": 0}]
        out = ic.suggest_mappings(sysi, whi, {}, "گلسرخ")
        pairs = {(o["sys_code"], o["wh_code"]) for o in out}
        self.assertIn(("101", "9001"), pairs)
        self.assertIn(("777", "777"), pairs)             # کد یکسان
        # کد انبار استفاده‌شده پیشنهاد نمی‌شود
        out2 = ic.suggest_mappings(sysi, whi, {"گلسرخ": {"500": ["9001"]}}, "گلسرخ")
        self.assertNotIn("9001", {o["wh_code"] for o in out2})


class CompareExport(unittest.TestCase):
    def setUp(self):
        self.system = {"گلسرخ": [{"code": "101", "desc": "الف", "qty": 10.0},
                                 {"code": "102", "desc": "ب", "qty": 5.0},
                                 {"code": "103", "desc": "ج", "qty": 3.0},
                                 {"code": "104", "desc": "د", "qty": 1.0}]}
        self.wh = {"گلسرخ": [{"code": "1", "name": "n1", "qty": 4.0, "sheets": 10},
                             {"code": "2", "name": "n2", "qty": 3.0, "sheets": 5},
                             {"code": "3", "name": "n3", "qty": 8.0, "sheets": 20},
                             {"code": "4", "name": "n4", "qty": 1.002, "sheets": 1}]}
        self.maps = {"گلسرخ": {"101": ["1", "2"], "102": ["3"], "103": ["99"], "104": ["4"]}}

    def test_compare(self):
        res = ic.compare(self.system, self.wh, self.maps, 0.5, ["گلسرخ"])
        d = {r["sysCode"]: r for r in res}
        self.assertEqual(d["101"]["whQty"], 7.0)
        self.assertEqual(d["101"]["diff"], -3.0)                 # کاهش سامانه
        self.assertEqual(d["102"]["diff"], 3.0)                  # افزایش سامانه
        self.assertEqual(d["103"]["missing"], ["99"])            # کد نگاشت‌شده که در فایل انبار نیست
        self.assertEqual(d["103"]["diff"], -3.0)
        self.assertEqual(d["104"]["diff"], 0.0)                  # زیر آستانه
        st = ic.result_stats(res)
        self.assertEqual((st["sub"], st["add"], st["balanced"], st["unmapped"]), (2, 1, 1, 0))
        res2 = ic.compare(self.system, self.wh, {}, 0.5, ["گلسرخ"])
        self.assertEqual(ic.result_stats(res2)["unmapped"], 4)

    def test_khoroj_and_xlsx(self):
        res = ic.compare(self.system, self.wh, self.maps, 0.5, ["گلسرخ"])
        sel = [r for r in res if r["sysCode"] in ("101", "102")]     # 102 افزایش است → در اظهار خروج نمی‌آید
        rows = ic.khoroj_rows(sel, "1405/08/05")
        self.assertEqual(len(rows), 3)                               # هدر + ۱ ردیف + ردیف خالی
        self.assertEqual(rows[1][0], 1834185391)
        self.assertEqual(rows[1][5], 101)
        self.assertEqual(rows[1][6], 3.0)
        tmp = tempfile.mkdtemp()
        n = ic.write_khoroj_xlsx(os.path.join(tmp, "k.xlsx"), sel, "1405/08/05")
        self.assertEqual(n, 1)
        with self.assertRaises(ValueError):
            ic.write_khoroj_xlsx(os.path.join(tmp, "k2.xlsx"), [res[1]], "1405/08/05")
        ic.write_results_xlsx(os.path.join(tmp, "r.xlsx"), res)
        from openpyxl import load_workbook
        ws = load_workbook(os.path.join(tmp, "r.xlsx")).active
        self.assertEqual(ws.max_row, 5)
        self.assertIn("<table", ic.results_html(sel, "t", "1405/08/05"))


class Store(unittest.TestCase):
    def test_roundtrip_bak_and_corrupt(self):
        tmp = tempfile.mkdtemp()
        p = os.path.join(tmp, "inv.json")
        st = ic.empty_store()
        st["mappings"] = {"گلسرخ": {"101": ["1"]}}
        ic.touch_maps(st)
        ic.save_store(p, st)
        st["threshold"] = 7.0
        ic.save_store(p, st)                       # نسخه‌ی قبلی → .bak
        self.assertTrue(os.path.exists(p + ".bak"))
        self.assertEqual(ic.load_store(p)["threshold"], 7.0)
        with open(p, "w") as f:
            f.write("{خراب")
        self.assertEqual(ic.load_store(p)["mappings"], {"گلسرخ": {"101": ["1"]}})   # از .bak
        self.assertEqual(ic.load_store(os.path.join(tmp, "none.json"))["mappings"], {})

    def test_parse_iso(self):
        a = ic.parse_iso("2026-10-27T10:00:00Z")
        b = ic.parse_iso("2026-10-27T13:30:00+03:30")
        self.assertEqual(a, b)
        self.assertIsNone(ic.parse_iso("x"))


if __name__ == "__main__":
    unittest.main()
