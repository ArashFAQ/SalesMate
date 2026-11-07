"""تست توابع خالص و مهاجرت دیتابیس — بدون نیاز به PySide6.
اجرا (از ریشه‌ی پروژه):  python -m unittest discover -s tests -v
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "salesmate"))

from core_utils import (  # noqa: E402
    amount, fa_digits, en_digits, fmt, canon_money, clean_number,
    gregorian_to_jalali, jalali_to_gregorian, jalali_week_range, parse_flexible_jalali,
    customer_key, names_matching,
)
from db_migrations import migrate_money_v1  # noqa: E402


class DigitsAndAmount(unittest.TestCase):
    def test_digits_roundtrip(self):
        self.assertEqual(fa_digits("1405/01/15"), "۱۴۰۵/۰۱/۱۵")
        self.assertEqual(en_digits("۱۴۰۵/۰۱/۱۵"), "1405/01/15")
        self.assertEqual(en_digits("٠١٢٣٤٥٦٧٨٩"), "0123456789")  # ارقام عربی-هندی

    def test_amount_formats(self):
        self.assertEqual(amount("1,976,501,000"), 1976501000)
        self.assertEqual(amount("۱٬۲۰۰٬۰۰۰"), 1200000)
        self.assertEqual(amount("1500000.0"), 1500000)
        self.assertEqual(amount("-250,000"), -250000)
        self.assertEqual(amount(""), 0)
        self.assertEqual(amount(None), 0)
        self.assertEqual(amount(True), 0)

    def test_fmt_and_clean(self):
        self.assertEqual(fmt(1234567), "۱,۲۳۴,۵۶۷")
        self.assertEqual(clean_number("۱,۲۳۴ ریال"), "1234")

    def test_canon_money(self):
        self.assertEqual(canon_money("۱,۲۰۰,۰۰۰"), "1200000")
        self.assertEqual(canon_money("1200000"), "1200000")
        self.assertEqual(canon_money(" 5 000 "), "5000")
        self.assertIsNone(canon_money("abc"))
        self.assertIsNone(canon_money(""))
        self.assertIsNone(canon_money(None))


class JalaliDates(unittest.TestCase):
    def test_known_dates(self):
        self.assertEqual(gregorian_to_jalali(2026, 3, 21), (1405, 1, 1))
        self.assertEqual(jalali_to_gregorian(1405, 1, 1), (2026, 3, 21))

    def test_roundtrip_many(self):
        for jy in (1399, 1403, 1404, 1405):
            for jm in range(1, 13):
                for jd in (1, 15, 29):
                    self.assertEqual(gregorian_to_jalali(*jalali_to_gregorian(jy, jm, jd)), (jy, jm, jd))

    def test_parse_flexible(self):
        self.assertEqual(parse_flexible_jalali("1405/07/08"), (1405, 7, 8))
        self.assertEqual(parse_flexible_jalali("۸/۷", default_year=1405), (1405, 7, 8))
        self.assertIsNone(parse_flexible_jalali(""))


class WeekRange(unittest.TestCase):
    def test_first_and_middle_weeks(self):
        self.assertEqual(jalali_week_range(1405, 0), ((1, 1), (1, 7)))
        self.assertEqual(jalali_week_range(1405, 1), ((1, 8), (1, 14)))
        self.assertEqual(jalali_week_range(1405, 26), ((6, 28), (7, 3)))  # عبور از شهریور به مهر

    def test_last_week_clamped(self):
        self.assertEqual(jalali_week_range(1405, 52), ((12, 29), (12, 29)))   # سال ۳۶۵ روزه
        self.assertEqual(jalali_week_range(1403, 52), ((12, 29), (12, 30)))   # کبیسه
        self.assertIsNone(jalali_week_range(1403, 53))


class MoneyMigration(unittest.TestCase):
    def test_normalizes_and_is_safe(self):
        with tempfile.TemporaryDirectory() as d:
            dbp = Path(d) / "t.db"
            c = sqlite3.connect(dbp)
            c.execute("CREATE TABLE invoices(id INTEGER PRIMARY KEY, total TEXT, paid_amount TEXT)")
            c.execute("CREATE TABLE store_sales(id INTEGER PRIMARY KEY, total TEXT)")
            c.executemany("INSERT INTO invoices(total, paid_amount) VALUES (?,?)",
                          [("۱,۲۰۰,۰۰۰", ""), ("500000", "250,000"), ("نامشخص", None)])
            c.execute("INSERT INTO store_sales(total) VALUES ('۳۰۰٬۰۰۰')")
            c.commit()
            n = migrate_money_v1(c, dbp, Path(d) / "bk")
            self.assertEqual(n, 3)
            rows = c.execute("SELECT total, paid_amount FROM invoices ORDER BY id").fetchall()
            self.assertEqual(rows[0], ("1200000", ""))        # خالی = «کامل پرداخت» دست نخورد
            self.assertEqual(rows[1], ("500000", "250000"))
            self.assertEqual(rows[2], ("نامشخص", None))        # غیرعددی دست نخورد
            self.assertEqual(c.execute("SELECT total FROM store_sales").fetchone()[0], "300000")
            self.assertEqual(c.execute("SELECT SUM(CAST(total AS INTEGER)) FROM invoices WHERE id<=2").fetchone()[0], 1700000)
            self.assertTrue((Path(d) / "bk" / "salesmate_before_money_fix.db").exists())
            self.assertEqual(c.execute("PRAGMA user_version").fetchone()[0], 1)
            # اجرای دوباره چیزی را تغییر نمی‌دهد
            self.assertEqual(migrate_money_v1(c, dbp, Path(d) / "bk"), 0)
            c.close()



class CustomerMatching(unittest.TestCase):
    def test_variants_match(self):
        self.assertEqual(customer_key("علي  رضايي"), customer_key("علی رضایی"))
        self.assertEqual(customer_key("می\u200cشود"), customer_key("می شود"))

    def test_names_matching(self):
        got = names_matching(["علی ی رضایی", "نفر دیگر"], {"علی ي رضایی"})
        self.assertEqual(got, ["علی ی رضایی"])


if __name__ == "__main__":
    unittest.main()
