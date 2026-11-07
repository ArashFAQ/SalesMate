import json, sqlite3, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))
from db_migrations import migrate_jenagi_v2


class JenagiTest(unittest.TestCase):
    def test_migration(self):
        d = Path(tempfile.mkdtemp())
        db = d / "t.db"
        c = sqlite3.connect(str(db))
        c.execute("create table invoices(id integer primary key, inquiry_data text, total text)")
        rows = [
            {"code": "1", "name": "پارکت AC4 جناغی 6235 A", "type": "x", "qty1": "3", "qty2": "5.8824", "price": "34500000", "cost": "202942800"},
            {"code": "2", "name": "پارکت AC4 جناغی 6235 B", "type": "x", "qty1": "3", "qty2": "5.8824", "price": "34500000", "cost": "202942800"},
            {"code": "3", "name": "luxury", "type": "y", "qty1": "30", "qty2": "58.824", "price": "26800000", "cost": "1576483200"},
        ]
        c.execute("insert into invoices values(1,?,?)", (json.dumps({"rows": rows, "total": 1991849400}, ensure_ascii=False), "1991849400"))
        c.commit()
        self.assertEqual(migrate_jenagi_v2(c, db, d / "b"), 1)
        data = json.loads(c.execute("select inquiry_data from invoices").fetchone()[0])
        self.assertEqual(data["rows"][0]["qty2"], "6.0198")
        self.assertEqual(data["rows"][0]["cost"], "207683100")
        self.assertEqual(data["rows"][2]["cost"], "1576483200")
        self.assertEqual(c.execute("select total from invoices").fetchone()[0], "1991849400")


class RefreshTest(unittest.TestCase):
    def test_refresh(self):
        import types
        sys.modules.setdefault("PySide6", types.ModuleType("PySide6"))
        src = (Path(__file__).resolve().parent.parent / "salesmate" / "analysis_page.py").read_text(encoding="utf-8")
        a = src.index("def _fnum")
        b = src.index("def fix_unit_order")
        ns = {"_swallow": lambda: None}
        exec(src[a:b], ns)
        c = sqlite3.connect(":memory:")
        c.execute("create table invoices(id integer primary key, inquiry_data text, total text, paid_amount text)")
        old = [{"code": "1", "qty1": "3", "qty2": "5.8824", "price": "34500000", "cost": "202942800"}]
        new = [{"code": "1", "qty1": "3", "qty2": "6.0198", "price": "34500000", "cost": "207683100"}]
        c.execute("insert into invoices values(1,?,?,?)", (json.dumps({"tab": "analysis_import", "rows": old, "total": 202942800}), "202942800", "202942800"))
        r = c.execute("select * from invoices").fetchone()
        self.assertTrue(ns["refresh_existing_from_excel"](c, "invoices", r[0], r[1], r[2], r[3], new, 207683100))
        r = c.execute("select * from invoices").fetchone()
        self.assertEqual(r[2], "207683100"); self.assertEqual(r[3], "207683100")
        self.assertFalse(ns["refresh_existing_from_excel"](c, "invoices", r[0], r[1], r[2], r[3], new, 207683100))
        # حواله‌ی دستی (غیر اکسلی) دست نمی‌خورد
        c.execute("update invoices set inquiry_data=?", (json.dumps({"tab": "parquet", "rows": old}),))
        r = c.execute("select * from invoices").fetchone()
        self.assertFalse(ns["refresh_existing_from_excel"](c, "invoices", r[0], r[1], r[2], r[3], new, 207683100))


class StatementTest(unittest.TestCase):
    def test_statement(self):
        from statement_core import compute_statement, statement_html
        st = compute_statement([("1", "1405/08/01", "1000", "400"), ("2", "1405/08/05", "500", ""), ("3", "1405/08/06", "300", "500")], -100)
        self.assertEqual(len(st["debts"]), 1)
        self.assertEqual(st["credit"], 300)
        self.assertEqual(st["balance"], 300)
        self.assertIn("جمع کل بدهکاری", statement_html("x", "1405/08/12", st))
        st2 = compute_statement([("1", "d", "100", "400")], 0)
        self.assertEqual(st2["balance"], -300)
        h = statement_html("x", "d", st2)
        self.assertIn("مبلغ طلب شما", h)
        self.assertNotIn("شماره حواله", h)


class ExcelUntouchedTest(unittest.TestCase):
    def test_excel_rows_not_modified(self):
        d = Path(tempfile.mkdtemp())
        c = sqlite3.connect(str(d / "t.db"))
        c.execute("create table store_sales(id integer primary key, items_json text, total text)")
        rows = [{"code": "x", "name": "پارکت جناغی", "qty1": "10", "qty2": "19.608", "price": "27800000", "cost": "545102400"}]
        c.execute("insert into store_sales values(1,?,?)", (json.dumps(rows, ensure_ascii=False), "545102400"))
        c.commit()
        self.assertEqual(migrate_jenagi_v2(c, d / "t.db", d / "b"), 0)
        self.assertEqual(c.execute("select total from store_sales").fetchone()[0], "545102400")


class CoworkerRepairTest(unittest.TestCase):
    def test_repair_from_feed(self):
        import coworker_core as cc
        truth_rows = [{"code": "1", "name": "پارکت جناغی", "qty1": "10", "qty2": "19.608", "price": "27800000", "cost": "545102400"}]
        bad_rows = [{"code": "1", "name": "پارکت جناغی", "qty1": "10", "qty2": "20.066", "price": "27800000", "cost": "557834800"}]
        feed = [{"id": 1, "ckey": cc.customer_key("آقای الف"), "payload": {"customer": "آقای الف", "invoice_no": "5", "date": "1405/01/01", "total": 545102400, "rows": truth_rows}}]
        req = lambda m, p: (200, feed if "offset=0" in p else [])
        c = sqlite3.connect(":memory:")
        c.execute("create table invoices(id integer primary key, customer text, invoice_no text, total text, paid_amount text, inquiry_data text)")
        c.execute("insert into invoices values(1,'آقای الف','5','557834800','557834800',?)", (json.dumps({"tab": "analysis_import", "rows": bad_rows, "total": 557834800}, ensure_ascii=False),))
        c.execute("insert into invoices values(2,'آقای الف','9','100','100',?)", (json.dumps({"tab": "parquet", "rows": bad_rows}),))
        self.assertEqual(cc.repair_from_feed(req, "u", c), 1)
        r = c.execute("select total, paid_amount, inquiry_data from invoices where id=1").fetchone()
        self.assertEqual(r[0], "545102400"); self.assertEqual(r[1], "545102400")
        self.assertEqual(json.loads(r[2])["rows"][0]["qty2"], "19.608")
        self.assertEqual(cc.repair_from_feed(req, "u", c), 0)
        self.assertEqual(c.execute("select total from invoices where id=2").fetchone()[0], "100")


class StoreDiffTest(unittest.TestCase):
    def test_diff(self):
        src = (Path(__file__).resolve().parent.parent / "salesmate" / "stats_pages.py").read_text(encoding="utf-8")
        a = src.index("def _sig"); b = src.index("def find_store_duplicates")
        from core_utils import en_digits
        ns = {"en_digits": en_digits}
        exec(src[a:b], ns)
        ex = [("1405/01/05", "10", 1000, 5), ("1405/01/06", "11", 2000, 7), ("1405/03/01", "12", 300, 1)]
        st = [(1, "x", "10", "1405/01/05", 1000, 5), (2, "x", "AN-1", "1405/01/06", 2000, 7), (3, "x", "77", "1405/02/01", 500, 2)]
        only_store, only_excel = ns["store_diff"](ex, st)
        self.assertEqual([x[1] for x in only_store], ["77"])
        self.assertEqual([x[1] for x in only_excel], ["12"])
        # شماره و مبلغ فرق دارد ولی همان مشتری و تاریخ و یکتا → تطبیق با اختلاف مبلغ
        ex2 = [("1405/04/24", "999", 1645402200, 50.18, "فروشگاه ایزوفام - عطیه صادقی")]
        st2 = [(1, "فروشگاه ایزوفام-عطیه صادقی", "20209", "1405/04/24", 1644910350, 50.165)]
        o1, o2 = ns["store_diff"](ex2, st2)
        self.assertEqual((o1, o2), ([], []))
        self.assertEqual(ns["store_diff"].last_diffs[0][3:], (1644910350, 1645402200))


class StoreDupTest(unittest.TestCase):
    def test_dups(self):
        src = (Path(__file__).resolve().parent.parent / "salesmate" / "stats_pages.py").read_text(encoding="utf-8")
        a = src.index("def find_store_duplicates"); b = src.index("class ParquetStatsPage")
        from core_utils import en_digits
        ns = {"en_digits": en_digits}
        exec(src[a:b], ns)
        rows = [(1, "فروشگاه ایزوفام - نیلوفر", "20498", "1405/08/10", 6038070800),
                (2, "فروشگاه ایزوفام-نیلوفر", "20498", "1405/08/10", 6038070800),
                (3, "x", "20499", "1405/08/10", 100), (4, "x", "20499", "1405/08/11", 100),
                (5, "y", "AN-1", "1405/08/10", 5), (6, "y", "AN-2", "1405/08/10", 5), (7, "z", "AN-3", "1405/08/10", 5),
                (8, "ع", "20209", "1405/04/24", 1645402200), (9, "ع", "20209", "1405/04/24", 1644910350)]
        self.assertEqual(ns["find_store_duplicates"](rows), [(2, 1), (6, 5), (9, 8)])


class DedupeNamesTest(unittest.TestCase):
    def test_name_variants(self):
        import pandas as pd
        from core_utils import customer_key
        src = (Path(__file__).resolve().parent.parent / "salesmate" / "analysis_page.py").read_text(encoding="utf-8")
        a = src.index("def _name_sig"); b = src.index("def load_excel")
        ns = {"customer_key": customer_key, "pd": pd}
        exec(src[a:b], ns)
        df = pd.DataFrame([
            {"تاریخ": "1405/08/10", "شماره فرم": "20498", "کد کالا": "1", "نام مشتری": "فروشگاه ایزوفام - نیلوفر کریم زاده", "مبلغ": 100},
            {"تاریخ": "1405/08/10", "شماره فرم": "20498", "کد کالا": "1", "نام مشتری": "فروشگاه ایزوفام-نیلوفر کریم زاده", "مبلغ": 100},
            {"تاریخ": "1405/08/10", "شماره فرم": "20498", "کد کالا": "2", "نام مشتری": "فروشگاه ایزوفام-نیلوفر کریم زاده", "مبلغ": 50},
        ])
        out = ns["renorm_dedupe"](df)
        self.assertEqual(len(out), 2)
        self.assertEqual(int(out["مبلغ"].sum()), 150)


class InvoiceChipTests(unittest.TestCase):
    def test_chip(self):
        from salesmate.statement_core import invoice_chip
        self.assertEqual(invoice_chip(100, 70, 0), ("تسویه ✓", "ok", "(−30)", "neg"))
        self.assertEqual(invoice_chip(100, 130, 0), ("تسویه ✓", "ok", "(+30)", "pos"))
        self.assertEqual(invoice_chip(100, 100, 0)[0], "تسویه ✓")
        self.assertEqual(invoice_chip(100, 70, 30)[:2], ("مانده 30", "debt"))
        self.assertEqual(invoice_chip(100, 130, -30)[:2], ("بستانکار 30", "cred"))


class SampleLastTests(unittest.TestCase):
    def test_order(self):
        from salesmate.statement_core import sample_last, _items_of
        rows = [{"name": "سمپل پارکت"}, {"name": "A"}, {"type": "B"}, {"name": "Sample x"}, {"name": "C"}]
        self.assertEqual([r.get("name") or r.get("type") for r in sample_last(rows)],
                         ["A", "B", "C", "سمپل پارکت", "Sample x"])
        import json
        out = _items_of(json.dumps({"rows": rows}))
        self.assertEqual([x["name"] for x in out][-2:], ["سمپل پارکت", "Sample x"])


class FreeRowLastTests(unittest.TestCase):
    def test_zero_price(self):
        from salesmate.statement_core import sample_last
        rows = [{"name": "X", "price": 0, "cost": 0}, {"name": "A", "price": "1,000", "cost": "5,000"}, {"name": "استند", "price": "0", "cost": ""}]
        self.assertEqual([r["name"] for r in sample_last(rows)], ["A", "X", "استند"])


class RecentInvoicesTests(unittest.TestCase):
    def test_window_and_group(self):
        from salesmate.recent_core import recent_invoices
        recs = [{"تاریخ": "1405/08/12", "شماره فرم": "101.0", "نام مشتری": "الف", "تعداد 1": 2, "تعداد 2": 4, "مبلغ": 1000},
                {"تاریخ": "1405/08/12", "شماره فرم": "101", "نام مشتری": "الف", "تعداد 1": 1, "تعداد 2": 2, "مبلغ": 500},
                {"تاریخ": "1405/08/01", "شماره فرم": "99", "نام مشتری": "ب", "تعداد 1": 1, "تعداد 2": 1, "مبلغ": 7},
                {"تاریخ": "1405/07/20", "شماره فرم": "50", "نام مشتری": "ج", "تعداد 1": 1, "تعداد 2": 1, "مبلغ": 9}]
        r = recent_invoices(recs)
        self.assertEqual([g["no"] for g in r["rows"]], ["101", "99"])
        self.assertEqual(r["tot"]["amount"], 1507)

    def test_custom_range(self):
        from salesmate.recent_core import recent_invoices
        recs = [{"تاریخ": "1405/08/12", "شماره فرم": "1", "نام مشتری": "a", "تعداد 1": 1, "تعداد 2": 1, "مبلغ": 5},
                {"تاریخ": "1405/07/20", "شماره فرم": "2", "نام مشتری": "b", "تعداد 1": 1, "تعداد 2": 1, "مبلغ": 7}]
        r = recent_invoices(recs, 14, "1405/07/01", "1405/07/30")
        self.assertEqual([g["no"] for g in r["rows"]], ["2"])
        r = recent_invoices(recs, 14, "۱۴۰۵/۰۷/۱۰", None)
        self.assertEqual(len(r["rows"]), 2)


class HealthCoreTests(unittest.TestCase):
    def test_checks(self):
        import sqlite3
        from salesmate import health_core as h
        c = sqlite3.connect(":memory:")
        c.execute("create table invoices(id integer primary key,customer,invoice_no,date,total)")
        c.execute("create table store_sales(id integer primary key,customer)")
        for r in [("فروشگاه نیما", "89", "1405/08/01", "1000"), ("فروشگاه  نیما", "89", "1405/08/01", "1200"),
                  ("ب", "AN-1", "1405/08/02", "500"), ("ب", "AN-2", "1405/08/02", "500"), ("", "7", "1405/08/03", "0")]:
            c.execute("insert into invoices(customer,invoice_no,date,total) values(?,?,?,?)", r)
        c.execute("insert into store_sales(customer) values('فروشگاه-نیما')")
        s = h.summarize(c)
        self.assertEqual([[x["id"] for x in g] for g in s["dup_invoices"]], [[1, 2], [3, 4]])
        self.assertEqual(len(s["name_variants"]), 1)
        self.assertEqual(len(s["bad_invoices"]), 1)
