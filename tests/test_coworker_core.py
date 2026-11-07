import os, sys, unittest, sqlite3
from urllib.parse import urlparse, parse_qs, unquote
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "salesmate"))
try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None
import coworker_core as cc

A, B = "uid-ali", "uid-reza"


class FakeSB:
    """نسخه‌ی کوچک PostgREST برای تست."""
    def __init__(self):
        self.t = {"sales_feed": [], "coworker_customers": [], "coworker_accounts": [], "invoices": [], "coworker_snapshots": []}
        self.seq = 0

    def _match(self, row, q):
        for k, v in q.items():
            if k in ("select", "limit", "offset", "order", "on_conflict"):
                continue
            op, _, val = v[0].partition(".")
            if op == "eq":
                if str(row.get(k)) != unquote(val):
                    return False
            elif op == "in":
                if str(row.get(k)) not in val.strip("()").split(","):
                    return False
        return True

    def __call__(self, method, path, body=None, extra=None):
        u = urlparse(path)
        q = parse_qs(u.query)
        if u.path.endswith("/rpc/coworker_list"):
            return 200, [{"user_id": A, "email": "ali@sales.local"}, {"user_id": B, "email": "reza@sales.local"}]
        tbl = u.path.rsplit("/", 1)[1]
        rows = self.t[tbl]
        if method == "GET":
            sel = [r for r in rows if self._match(r, q)]
            if "order" in q:
                sel.sort(key=lambda r: r.get("id", 0))
            off = int(q.get("offset", ["0"])[0]); lim = int(q.get("limit", ["1000"])[0])
            return 200, sel[off:off + lim]
        if method == "DELETE":
            self.t[tbl] = [r for r in rows if not self._match(r, q)]
            return 204, None
        if method == "PATCH":
            for r in rows:
                if self._match(r, q):
                    r.update(body)
            return 204, None
        if method == "POST":
            conflict = q.get("on_conflict", [""])[0].split(",") if "on_conflict" in q else None
            pref = (extra or {}).get("Prefer", "")
            for b in body:
                b = dict(b)
                if conflict:
                    ex = [r for r in rows if all(r.get(c) == b.get(c) for c in conflict)]
                    if ex:
                        if "merge" in pref:
                            ex[0].update(b)
                        continue
                if tbl == "sales_feed":
                    self.seq += 1
                    b["id"] = self.seq
                    b.setdefault("status", "pending")
                rows.append(b)
            return 201, None
        raise AssertionError(method)


def mkdb():
    c = sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE invoices(id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, invoice_no TEXT,
        date TEXT, time TEXT, total TEXT, created_at TEXT, image_path TEXT DEFAULT '',
        inquiry_data TEXT DEFAULT '', paid_amount TEXT DEFAULT '')""")
    return c


@unittest.skipIf(pd is None, "pandas نیست")
class Core(unittest.TestCase):
    def df(self, extra=None):
        rows = [
            {"نام مشتری": "علی ي", "تاریخ": "1405/01/02", "شماره فرم": "100", "مبلغ": 1000, "نام کالا": "الف", "کد کالا": "1", "دسته": "پارکت", "تعداد 1": "2", "تعداد 2": "10", "قیمت": "100"},
            {"نام مشتری": "علی ي", "تاریخ": "1405/01/02", "شماره فرم": "100", "مبلغ": 500, "نام کالا": "ب", "کد کالا": "2", "دسته": "پارکت", "تعداد 1": "1", "تعداد 2": "5", "قیمت": "100"},
            {"نام مشتری": "رضا", "تاریخ": "1405/01/03", "شماره فرم": "101", "مبلغ": 700, "نام کالا": "ج", "کد کالا": "3", "دسته": "پارکت", "تعداد 1": "1", "تعداد 2": "1", "قیمت": "100"},
            {"نام مشتری": "فروشگاه ایزوفام", "تاریخ": "1405/01/03", "شماره فرم": "102", "مبلغ": 900, "نام کالا": "د", "کد کالا": "4", "دسته": "پارکت", "تعداد 1": "1", "تعداد 2": "1", "قیمت": "100"},
        ]
        return pd.DataFrame(rows + (extra or []))

    def test_login_email(self):
        self.assertEqual(cc.login_email("Ali"), "ali@sales.local")
        self.assertEqual(cc.login_email("a@b.com"), "a@b.com")
        self.assertEqual(cc.login_email(" "), "")
        self.assertTrue(cc.is_owner_email("Arash.E.Maleki@gmail.com"))
        self.assertFalse(cc.is_owner_email("ali@sales.local"))

    def test_excel_invoices(self):
        inv = cc.excel_invoices(self.df())
        self.assertEqual(len(inv), 2)                     # فروشگاه حذف
        a = [i for i in inv if i["invoice_no"] == "100"][0]
        self.assertEqual(a["total"], 1500)
        self.assertEqual(len(a["rows"]), 2)
        only = cc.excel_invoices(self.df(), {cc.customer_key("رضا"): {"parquet"}})
        self.assertEqual([i["invoice_no"] for i in only], ["101"])

    def asg(self, sb, ck, kind, uid, df=None):
        saved = cc.load_assignments(sb)
        cc.apply_changes(sb, saved, {(ck, kind): uid}, {ck: ck})

    def test_sync_idempotent_and_apply(self):
        sb = FakeSB()
        ck = cc.customer_key("علی ی")
        self.asg(sb, ck, "parquet", A)
        st = {}
        self.assertEqual(cc.sync_feed(sb, self.df(), stats=st), 1)
        self.assertEqual(st, {A: 1})   # تعداد حواله‌ی اضافه‌شده برای هر همکار
        self.assertEqual(cc.sync_feed(sb, self.df()), 0)  # بدون تکرار
        c = mkdb()
        r = cc.apply_feed(sb, A, c)
        self.assertEqual(r["added"], 1)
        row = c.execute("SELECT customer,invoice_no,total,paid_amount FROM invoices").fetchone()
        self.assertEqual(row, ("علی ي", "100", "1500", "1500"))
        self.assertEqual(cc.apply_feed(sb, A, c), {"added": 0, "revoked": 0, "skipped": 0})
        extra = [{"نام مشتری": "علی ي", "تاریخ": "1405/01/09", "شماره فرم": "110", "مبلغ": 300, "نام کالا": "ه", "کد کالا": "5", "دسته": "پارکت", "تعداد 1": "1", "تعداد 2": "1", "قیمت": "1"}]
        self.assertEqual(cc.sync_feed(sb, self.df(extra)), 1)
        self.assertEqual(cc.apply_feed(sb, A, c)["added"], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 2)

    def test_apply_skips_existing_number(self):
        sb = FakeSB()
        self.asg(sb, cc.customer_key("رضا"), "parquet", A)
        cc.sync_feed(sb, self.df())
        c = mkdb()
        c.execute("INSERT INTO invoices(customer,invoice_no,date,time,total,created_at) VALUES('رضا','101','1405/01/03','1','1','x')")
        r = cc.apply_feed(sb, A, c)
        self.assertEqual((r["added"], r["skipped"]), (0, 1))

    def test_move_customer_revokes_only_excel(self):
        sb = FakeSB()
        ck = cc.customer_key("علی ي")
        self.asg(sb, ck, "parquet", A)
        cc.sync_feed(sb, self.df())
        c = mkdb()
        cc.apply_feed(sb, A, c)
        c.execute("INSERT INTO invoices(customer,invoice_no,date,time,total,created_at) VALUES('علی ي','M1','1405/02/01','1','5','x')")
        self.asg(sb, ck, "parquet", B)
        self.assertEqual(cc.load_assignments(sb)[(ck, "parquet")]["assignee"], B)
        r = cc.apply_feed(sb, A, c)
        self.assertEqual(r["revoked"], 1)
        self.assertEqual([x[0] for x in c.execute("SELECT invoice_no FROM invoices")], ["M1"])
        self.assertEqual(cc.sync_feed(sb, self.df()), 1)
        self.assertEqual(cc.apply_feed(sb, B, mkdb())["added"], 1)

    def test_revoke_then_return_readds(self):
        sb = FakeSB()
        ck = cc.customer_key("رضا")
        self.asg(sb, ck, "parquet", A)
        cc.sync_feed(sb, self.df()); c = mkdb(); cc.apply_feed(sb, A, c)
        self.asg(sb, ck, "parquet", None)
        self.assertNotIn((ck, "parquet"), cc.load_assignments(sb))
        self.assertEqual(cc.apply_feed(sb, A, c)["revoked"], 1)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM invoices").fetchone()[0], 0)
        self.asg(sb, ck, "parquet", A)
        self.assertEqual(cc.sync_feed(sb, self.df()), 1)
        self.assertEqual(cc.apply_feed(sb, A, c)["added"], 1)

    def mixed(self):
        # یک مشتری با یک فرم شامل پارکت و ام دی اف + یک فرم فقط ام دی اف
        base = {"نام مشتری": "سارا", "مبلغ": 100, "کد کالا": "1", "تعداد 1": "1", "تعداد 2": "1", "قیمت": "1"}
        rows = [dict(base, تاریخ="1405/03/01", **{"شماره فرم": "300", "دسته": "پارکت", "نام کالا": "پ"}),
                dict(base, تاریخ="1405/03/01", **{"شماره فرم": "300", "دسته": "ام دی اف", "نام کالا": "م"}, مبلغ=50),
                dict(base, تاریخ="1405/03/02", **{"شماره فرم": "301", "دسته": "خام", "نام کالا": "خ"}, مبلغ=70)]
        return pd.DataFrame(rows)

    def test_split_kinds_between_coworkers(self):
        sb = FakeSB()
        ck = cc.customer_key("سارا")
        info = cc.excel_customer_info(self.mixed())
        self.assertEqual(info[ck][1], {"parquet", "mdf"})
        self.asg(sb, ck, "parquet", A)
        self.asg(sb, ck, "mdf", B)
        self.assertEqual(cc.sync_feed(sb, self.mixed()), 3)   # A: فرم ۳۰۰ پارکت ؛ B: فرم‌های ۳۰۰ و ۳۰۱
        ca, cb = mkdb(), mkdb()
        cc.apply_feed(sb, A, ca); cc.apply_feed(sb, B, cb)
        self.assertEqual(ca.execute("SELECT invoice_no,total FROM invoices").fetchall(), [("300", "100")])
        self.assertEqual(sorted(cb.execute("SELECT invoice_no,total FROM invoices").fetchall()), [("300", "50"), ("301", "70")])

    def test_same_coworker_both_kinds_merges(self):
        sb = FakeSB()
        ck = cc.customer_key("سارا")
        self.asg(sb, ck, "parquet", A)
        cc.sync_feed(sb, self.mixed()); c = mkdb(); cc.apply_feed(sb, A, c)
        self.assertEqual(c.execute("SELECT total FROM invoices WHERE invoice_no='300'").fetchone()[0], "100")
        self.asg(sb, ck, "mdf", A)                           # حالا هر دو گروه → برچسب all، بازسازی
        self.assertEqual(cc.sync_feed(sb, self.mixed()), 2)
        r = cc.apply_feed(sb, A, c)
        self.assertEqual((r["revoked"], r["added"]), (1, 2))
        self.assertEqual(sorted(c.execute("SELECT invoice_no,total FROM invoices").fetchall()), [("300", "150"), ("301", "70")])

    def test_compare_data(self):
        base = {"مبلغ": 100, "کد کالا": "1", "قیمت": "1", "شماره فرم": "1", "تعداد 1": "1"}
        rows = [dict(base, **{"نام مشتری": "علی", "تاریخ": "1405/01/02", "دسته": "پارکت", "تعداد 2": "10"}),
                dict(base, **{"نام مشتری": "علی", "تاریخ": "1405/01/09", "دسته": "ام دی اف", "تعداد 2": "4", "مبلغ": 50}),
                dict(base, **{"نام مشتری": "رضا", "تاریخ": "1405/02/01", "دسته": "پارکت", "تعداد 2": "7", "مبلغ": 300}),
                dict(base, **{"نام مشتری": "فروشگاه ایزوفام", "تاریخ": "1405/02/01", "دسته": "پارکت", "تعداد 2": "9"}),
                dict(base, **{"نام مشتری": "قدیمی", "تاریخ": "1404/12/29", "دسته": "پارکت", "تعداد 2": "9"})]
        df = pd.DataFrame(rows)
        ali = cc.customer_key("علی")
        asg = {(ali, "parquet"): {"assignee": A, "name": "علی"}}
        d = cc.compare_data(df, asg, {A: "ali"})
        self.assertEqual(d["years"], [1404, 1405]); self.assertEqual(d["year"], 1405)
        self.assertEqual(d["names"], ["من", "ali"])
        m = d["charts"]["month"]
        self.assertEqual(m["labels"], ["فروردین", "اردیبهشت"])
        self.assertEqual(m["series"]["ali"][0], [100, 10.0, 0.0])      # پارکت علی → همکار
        self.assertEqual(m["series"]["من"][0], [50, 0.0, 4.0])         # ام دی اف علی → خودم
        self.assertEqual(m["series"]["من"][1], [300, 7.0, 0.0])        # رضا → خودم؛ فروشگاه حذف
        w = d["charts"]["week"]
        self.assertEqual(len(w["labels"]), 5)                          # روز ۳۲ → هفته ۵
        t = d["charts"]["total"]
        self.assertEqual(t["series"]["من"][-1], [350, 7.0, 4.0])       # تجمعی
        d3 = cc.compare_data(df, asg, {A: "ali"}, mine={ali})        # فقط علی تیک خودم است؛ رضا کنار می‌رود
        self.assertEqual(d3["charts"]["month"]["series"]["من"][-1][0], 50)
        self.assertEqual(d3["charts"]["month"]["series"]["ali"][0][0], 100)
        d2 = cc.compare_data(df, asg, {A: "ali"}, year=1404)
        self.assertEqual(d2["charts"]["month"]["series"]["من"][-1][0], 100)

    def test_free_snapshot(self):
        base = {"مبلغ": 0, "کد کالا": "1", "قیمت": "0", "تعداد 1": "2", "تعداد 2": "3", "دسته": "پارکت", "ماه": "فروردین", "نام برگه": "ش"}
        rows = [dict(base, **{"نام مشتری": "علی", "تاریخ": "1405/01/02", "نام کالا": "سمپل الف"}),
                dict(base, **{"نام مشتری": "رضا", "تاریخ": "1405/01/03", "نام کالا": "استند ب"}),
                dict(base, **{"نام مشتری": "علی", "تاریخ": "1405/01/04", "نام کالا": "پارکت", "مبلغ": 500})]
        df = pd.DataFrame(rows)
        sb = FakeSB(); sb.t["coworker_snapshots"] = [{"assignee": B, "free": {}}]
        ali = cc.customer_key("علی")
        cc.apply_changes(sb, {}, {(ali, "parquet"): A}, {ali: "علی"})
        self.assertEqual(cc.push_free_snapshots(sb, df), 2)           # A و B (B خالی می‌شود)
        out = cc.fetch_free_df(sb, A)
        self.assertEqual(len(out), 1); self.assertEqual(out.iloc[0]["نام کالا"], "سمپل الف")
        self.assertEqual(len(cc.fetch_free_df(sb, B)), 0)

    def test_cache_skips_existing_lookup(self):
        import tempfile
        cc.CACHE_PATH = os.path.join(tempfile.mkdtemp(), "c.json")
        try:
            sb = FakeSB(); gets = []
            orig = sb.__call__
            def spy(method, path, body=None, extra=None):
                if method == "GET" and "select=feed_key" in path:
                    gets.append(path)
                return orig(method, path, body, extra)
            ck = cc.customer_key("علی ي")
            cc.apply_changes(spy, {}, {(ck, "parquet"): A}, {ck: "علی"})
            self.assertEqual(cc.sync_feed(spy, self.df()), 1)
            self.assertEqual(len(gets), 1)
            self.assertEqual(cc.sync_feed(spy, self.df()), 0)
            self.assertEqual(len(gets), 1)                       # بار دوم از حافظه
            self.assertEqual(cc.sync_feed(spy, self.df(), use_cache=False), 0)
            self.assertEqual(len(gets), 2)                       # ارسال مجدد: با ابر تطبیق می‌دهد
            cc.apply_changes(spy, cc.load_assignments(sb), {(ck, "parquet"): None}, {ck: "علی"})
            cc.apply_changes(spy, cc.load_assignments(sb), {(ck, "parquet"): A}, {ck: "علی"})
            self.assertEqual(cc.sync_feed(spy, self.df()), 1)    # بعد از revoke دوباره ساخته می‌شود
        finally:
            cc.CACHE_PATH = None

    def test_exclude_store_customers(self):
        ck = cc.customer_key("رضا")
        self.assertNotIn(ck, cc.excel_customer_info(self.df(), {ck}))
        self.assertEqual(cc.excel_invoices(self.df(), {ck: {"parquet"}}, {ck}), [])

    def test_suggest_and_accounts(self):
        sb = FakeSB()
        sb.t["invoices"] += [{"user_id": "old", "customer": "علی ی"}, {"user_id": "old", "customer": "ناشناس"}]
        s = cc.suggest_from_old(sb, "old", {cc.customer_key("علی ي"), cc.customer_key("رضا")})
        self.assertEqual(s, {cc.customer_key("علی ي")})
        cc.save_account(sb, A, "علی", "old")
        acc = {a["user_id"]: a for a in cc.load_accounts(sb)}
        self.assertEqual(acc[A]["label"], "علی"); self.assertEqual(acc[A]["old_user_id"], "old")
        self.assertEqual(acc[B]["label"], "reza")


if __name__ == "__main__":
    unittest.main()
