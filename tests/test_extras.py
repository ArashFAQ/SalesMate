"""تست منطق گزارش بارگذاری و سمپل/استند — بدون PySide6."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))

import pandas as pd  # noqa: E402
from sales_extras import (  # noqa: E402
    classify_free_item, free_items_by_customer, free_items_of_customer,
    build_upload_report, report_to_html,
)


def mk(rows):
    cols = ["نام مشتری", "تاریخ", "شماره فرم", "مبلغ", "کد کالا", "نام کالا", "نام برگه", "دسته", "تعداد 1", "تعداد 2", "تعداد_ورق"]
    df = pd.DataFrame(rows, columns=cols)
    df["unique_key"] = df["نام مشتری"] + "|" + df["شماره فرم"].astype(str) + "|" + df["کد کالا"] + "|" + df["نام کالا"]
    df["ماه"] = df["تاریخ"].str[:7]
    return df


class Classify(unittest.TestCase):
    def test_types(self):
        self.assertEqual(classify_free_item("سمپل پارکت 123"), "سمپل")
        self.assertEqual(classify_free_item("استند نمایشگاهی"), "استند")
        self.assertEqual(classify_free_item("نمونه رنگ"), "نمونه")
        self.assertEqual(classify_free_item("پارکت NEW WAY 1234"), "")
        self.assertEqual(classify_free_item("Standard floor"), "")
        self.assertEqual(classify_free_item("x", "سمپل ها"), "سمپل")
        self.assertEqual(classify_free_item("سامپل"), "سمپل")


class Summary(unittest.TestCase):
    def setUp(self):
        self.df = mk([
            ("علی ي رضایی", "1405/08/01", "1", 0, "a", "سمپل پارکت", "", "پارکت", 2, 5, 5),
            ("علی ی رضایی", "1405/08/05", "2", 0, "b", "استند", "", "سایر", 1, 0, 0),
            ("علی ی رضایی", "1405/08/06", "3", 5_000_000, "c", "پارکت", "", "پارکت", 3, 12, 12),
            ("رضا", "1405/09/01", "4", 0, "d", "نمونه رنگ", "", "سایر", 4, 0, 0),
            ("رضا", "1405/09/02", "5", 0, "e", "کالای هدیه", "", "سایر", 1, 0, 0),
        ])

    def test_by_customer(self):
        t = free_items_by_customer(self.df)
        self.assertEqual(len(t), 2)
        ali = t[t["مشتری"].str.startswith("علی")].iloc[0]
        self.assertEqual((ali["سمپل"], ali["استند"], ali["جمع"], ali["ردیف"]), (2, 1, 3, 2))   # ي/ی یکی شد؛ ردیف پولی نیامد
        self.assertEqual(ali["آخرین تاریخ"], "1405/08/05")
        reza = t[t["مشتری"] == "رضا"].iloc[0]
        self.assertEqual((reza["نمونه"], reza["سایر"]), (4, 1))

    def test_month_and_search(self):
        self.assertEqual(len(free_items_by_customer(self.df, month="1405/09")), 1)
        self.assertEqual(len(free_items_by_customer(self.df, search="علی")), 1)
        self.assertEqual(free_items_by_customer(self.df, search="رضا").iloc[0]["مشتری"], "رضا")  # «رضایی» هم تطبیق دارد؛ اولی بیشترین جمع

    def test_category(self):
        df = self.df.copy()
        df["دسته"] = ["پارکت", "ام دی اف", "پارکت", "سایر", "خام"]
        self.assertEqual(free_items_by_customer(df, category="پارکت")["جمع"].sum(), 2)      # سمپل علی
        self.assertEqual(free_items_by_customer(df, category="ام دی اف")["جمع"].sum(), 1)   # استند علی
        self.assertEqual(free_items_by_customer(df, category="سایر")["جمع"].sum(), 5)       # نمونه+هدیه رضا
        self.assertEqual(free_items_by_customer(df, category="همه")["جمع"].sum(), 8)

    def test_detail(self):
        t = free_items_by_customer(self.df)
        key = t[t["مشتری"] == "رضا"].iloc[0]["_key"]
        self.assertEqual(len(free_items_of_customer(self.df, key)), 2)


class Report(unittest.TestCase):
    def test_report(self):
        old = mk([("علی", "1405/08/01", "1", 1000, "a", "پارکت", "", "پارکت", 1, 2, 2)])
        new = mk([
            ("علی", "1405/08/01", "1", 1000, "a", "پارکت", "", "پارکت", 1, 2, 2),   # تکراری
            ("علی", "1405/08/02", "2", 2000, "a", "پارکت", "", "پارکت", 1, 3, 3),
            ("کیان", "1405/08/02", "3", 0, "b", "سمپل", "", "سایر", 2, 0, 0),
        ])
        merged = pd.concat([old, new]).drop_duplicates("unique_key")
        rep = build_upload_report(old, new, merged, files=[("a.xlsx", 3)], dup_removed=1)
        self.assertEqual(rep["new_rows"], 2)
        self.assertEqual(rep["existing_rows"], 1)
        self.assertEqual(rep["new_customers"], ["کیان"])
        self.assertEqual(rep["zero_rows"], 1)
        self.assertEqual(rep["free_counts"]["سمپل"], 1)
        self.assertEqual(rep["date_from"], "1405/08/02")
        rep["auto"] = {"customers": 1, "added": 1, "store": 0, "skipped": 0}
        self.assertIn("مشتریان جدید", report_to_html(rep))

    def test_replace_first_load(self):
        new = mk([("علی", "1405/08/02", "2", 2000, "a", "پارکت", "", "پارکت", 1, 3, 3)])
        rep = build_upload_report(pd.DataFrame(), new, new, replace=True, files=[("a.xlsx", 1)])
        self.assertEqual(rep["new_rows"], 1)
        self.assertEqual(rep["new_customers"], [])


if __name__ == "__main__":
    unittest.main()


class BreakdownAndMonthly(unittest.TestCase):
    def test_free_breakdown(self):
        import pandas as pd
        from sales_extras import free_items_of_customer, free_items_breakdown
        df = pd.DataFrame({
            "نام مشتری": ["علی", "علی", "علی"], "نام کالا": ["سمپل پارکت A", "استند B", "سمپل پارکت A"],
            "نام برگه": ["", "", ""], "کد کالا": ["1", "2", "1"], "تاریخ": ["1405/01/01"] * 3,
            "مبلغ": [0, 0, 0], "تعداد 1": [2, 1, 3], "تعداد 2": [1.5, 0, 2.5], "ماه": ["فروردین"] * 3,
        })
        from sales_extras import free_items_by_customer
        t = free_items_by_customer(df)
        z = free_items_of_customer(df, t.iloc[0]["_key"])
        totals, rows = free_items_breakdown(z)
        self.assertEqual(sum(totals.values()), 6)
        self.assertEqual(rows[0]["تعداد"], 5)
        self.assertEqual(rows[0]["متراژ"], 4.0)

    def test_monthly_groups(self):
        from sales_extras import group_invoices_by_month, invoice_meters
        inq = '{"rows":[{"qty2":"۱۰"},{"qty2":"2.5"}]}'
        self.assertEqual(invoice_meters(inq), 12.5)
        self.assertEqual(invoice_meters(""), 0.0)
        rows = [(1, "a", "10", "1405/01/05", "", "1,000", inq),
                (2, "b", "12", "1405/01/20", "", "2000", ""),
                (3, "c", "20", "1405/02/03", "", "500", inq),
                (4, "d", "5", "", "", "7", "")]
        groups, total = group_invoices_by_month(rows, lambda t: float(str(t).replace(",", "")))
        self.assertEqual([(g["year"], g["month"]) for g in groups], [(1405, 2), (1405, 1), (0, 0)])
        self.assertEqual(groups[1]["amount"], 3000)
        self.assertEqual(groups[1]["meters"], 12.5)
        self.assertEqual([r[2] for r in groups[1]["rows"]], ["12", "10"])
        self.assertEqual(total, {"amount": 3507.0, "meters": 25.0, "count": 4})
