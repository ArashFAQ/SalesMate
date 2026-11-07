import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "salesmate"))
try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None
import mobile_snapshots as ms


@unittest.skipIf(pd is None, "pandas نیست")
class Snap(unittest.TestCase):
    def df(self):
        return pd.DataFrame([
            {"دسته": "پارکت", "نام مشتری": "علی", "مبلغ": 1000, "تعداد 2": "10", "تاریخ": "1405/01/02", "کد کالا": "55", "نام کالا": "الف", "ماه": "فروردین", "تعداد 1": "2"},
            {"دسته": "پارکت", "نام مشتری": "علی", "مبلغ": 500, "تعداد 2": "5", "تاریخ": "1405/01/02", "کد کالا": "55", "نام کالا": "الف", "ماه": "فروردین", "تعداد 1": "1"},
            {"دسته": "پارکت", "نام مشتری": "فروشگاه ایزوفام - x", "مبلغ": 700, "تعداد 2": "7", "تاریخ": "1405/01/09", "کد کالا": "56", "نام کالا": "ب", "ماه": "فروردین", "تعداد 1": "1"},
            {"دسته": "پارکت", "نام مشتری": "علی", "مبلغ": 0, "تعداد 2": "3", "تاریخ": "1405/01/09", "کد کالا": "57", "نام کالا": "سمپل پارکت", "ماه": "فروردین", "تعداد 1": "3"},
            {"دسته": "ام دی اف", "نام مشتری": "رضا", "مبلغ": 900, "تعداد 2": "9", "تاریخ": "1405/01/09", "کد کالا": "1", "نام کالا": "mdf", "ماه": "فروردین", "تعداد 1": "1"},
        ])

    def test_parquet(self):
        norm = lambda s: "فروشگاه ایزوفام" if str(s).startswith("فروشگاه ایزوفام") else str(s)
        s = ms.build_parquet_snapshot(self.df(), norm)
        self.assertEqual(len(s["rows"]), 2)                 # دو ردیف علی ادغام، صفر و mdf حذف
        tot = sum(r[4] for r in s["rows"])
        self.assertEqual(tot, 2200)
        self.assertIn("فروشگاه ایزوفام", s["customers"])
        r0 = [r for r in s["rows"] if r[0] == "1405/01/02"][0]
        self.assertEqual((r0[4], r0[5]), (1500, 15.0))

    def test_free(self):
        s = ms.build_free_snapshot(self.df())
        self.assertEqual(len(s["rows"]), 1)
        row = s["rows"][0]
        self.assertEqual(row[4], "سمپل")
        self.assertEqual(row[6], 3.0)

    def test_sales_report(self):
        df = self.df()
        df.loc[len(df)] = {"دسته": "ام دی اف", "نام مشتری": "x", "مبلغ": 400, "تعداد 2": "4", "تاریخ": "1405/01/09", "کد کالا": "2", "نام کالا": "هایگلاس سفید", "ماه": "فروردین", "تعداد 1": "1"}
        df.loc[len(df)] = {"دسته": "خام", "نام مشتری": "x", "مبلغ": 300, "تعداد 2": "6", "تاریخ": "1405/01/09", "کد کالا": "3", "نام کالا": "خام 16", "ماه": "فروردین", "تعداد 1": "1"}
        s = ms.build_sales_report_snapshot(df)
        by = {(r[0], r[1]): r for r in s["rows"]}
        self.assertEqual(by[("1405/01/09", "hg")][2:], [400, 4.0])
        self.assertEqual(by[("1405/01/09", "mel")][2:], [900, 9.0])
        self.assertEqual(by[("1405/01/09", "raw")][2:], [300, 6.0])
        self.assertEqual(sum(r[2] for r in s["rows"] if r[1] == "all"), 1600)  # بدون پارکت (900 mdf + 400 + 300)
        self.assertIn("sales_report", ms.build_all(df, None))

    def test_empty(self):
        self.assertIsNone(ms.build_parquet_snapshot(None))
        self.assertIsNone(ms.build_free_snapshot(None))
        self.assertIsNone(ms.build_balance_snapshot({}))

    def test_push_skips_unchanged(self):
        calls = []
        req = lambda m, p, b=None, h=None: calls.append((m, p, b))
        snaps = {"free_items": {"v": 1, "at": "x", "rows": [1]}}
        sent, h = ms.push_snapshots(req, snaps)
        self.assertEqual(sent, ["free_items"])
        self.assertIn("on_conflict=key", calls[0][1])
        sent2, _ = ms.push_snapshots(req, {"free_items": {"v": 1, "at": "y", "rows": [1]}}, h)
        self.assertEqual(sent2, [])
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
