"""آزمایش دود GUI: برنامه را بدون صفحه‌ی نمایش (offscreen) باز می‌کند، داده‌ی ساختگی می‌گذارد،
همه‌ی صفحه‌ها را refresh می‌کند و هر خطا را به‌صورت annotation + خلاصه‌ی run گزارش می‌دهد."""
import json, os, sys, traceback

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "salesmate"))

FAILS, OKS = [], []


def step(name, fn):
    try:
        fn()
        OKS.append(name)
        print("OK  ", name, flush=True)
    except Exception:
        tb = traceback.format_exc()
        FAILS.append((name, tb))
        print("FAIL", name, "\n", tb, flush=True)
        last = tb.strip().splitlines()[-1]
        print("::error title=%s::%s" % (name, last.replace("\n", " ")[:300]), flush=True)


def main():
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    import main as m

    step("init_ui_invoker", m.init_ui_invoker)
    step("db()", lambda: m.db().close())

    def seed():
        c = m.db()
        rows = [{"code": "55001010010009", "name": "پارکت تولیدی 8mm درجه 1 AC4 جناغی 6433 A", "type": "x", "qty1": "3", "qty2": "5.8824", "price": "34500000", "cost": "202942800"},
                {"code": "55001010020009", "name": "پارکت تولیدی 8mm درجه 1 AC4 جناغی 6433 B", "type": "x", "qty1": "2", "qty2": "3.9216", "price": "34500000", "cost": "135295200"},
                {"code": "5452101126", "name": "HDF پارکت AC4 luxury G4 - 2113", "type": "y", "qty1": "30", "qty2": "58.824", "price": "26800000", "cost": "1576483200"},
                {"code": "S1", "name": "سمپل پارکت", "type": "z", "qty1": "1", "qty2": "1", "price": "0", "cost": "0"}]
        blob = json.dumps({"tab": "parquet", "buyer": "فروشگاه نیما", "date": "1405/08/10", "rows": rows, "total": 1914721200}, ensure_ascii=False)
        for i, (cu, no, dt, tt) in enumerate([("فروشگاه نیما", "89", "1405/08/10", "1914721200"), ("فروشگاه  نیما", "89", "1405/08/10", "1914721200"),
                                              ("علی رضایی", "90", "1405/08/11", "500000000"), ("", "91", "1405/08/12", "0")]):
            c.execute("INSERT INTO invoices(customer,invoice_no,date,time,total,created_at,inquiry_data,paid_amount) VALUES(?,?,?,?,?,?,?,?)",
                      (cu, no, dt, "10:00", tt, "2026-11-07", blob, "1000000000" if i == 2 else ""))
        items = json.dumps([r for r in rows[:3]], ensure_ascii=False)
        for no in ("20209", "20210"):
            c.execute("INSERT INTO store_sales(customer,invoice_no,date,time,total,tab,items_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
                      ("فروشگاه-نیما", no, "1405/08/10", "10:00", "1914721200", "parquet", items, "2026-11-07"))
        c.execute("INSERT OR REPLACE INTO customer_balance_adj(customer,adjustment) VALUES('علی رضایی','-100000')")
        c.commit(); c.close()
    step("seed data", seed)

    holder = {}

    def mk():
        holder["w"] = m.MainWindow()
    step("MainWindow()", mk)
    w = holder.get("w")
    if w is not None:
        w.show()
        app.processEvents()
        for attr in ["home_page", "inv_page", "inquiry_page", "cust_page", "contacts_page", "rep_page", "store_page",
                     "ras_page", "balance_page", "calc_page", "parquet_page", "free_page", "cw_free_page",
                     "coworker_page", "set_page"]:
            p = getattr(w, attr, None)
            if p is None:
                continue

            def go(p=p):
                for fn in ("refresh", "refresh_list"):
                    f = getattr(p, fn, None)
                    if callable(f):
                        f()
                p.show()
                app.processEvents()
            step("page " + attr, go)

        step("refresh_all", lambda: (w.refresh_all(), app.processEvents()))

        def ras():
            for _ in range(30):
                w.ras_page.add_check_row()
            app.processEvents()
        step("ras 30 rows", ras)

        def health():
            from health_page import HealthDialog
            d = HealthDialog(w)
            d.show(); app.processEvents(); d.close()
        step("HealthDialog", health)

        def store_types():
            w.store_page.type_from.setText("1405/01/01"); w.store_page.type_to.setText("1405/12/29")
            w.store_page._fill_store_types(); app.processEvents()
        step("store types/codes", store_types)

        def inv_html():
            from invoice_pages import invoice_items_html
            d = json.loads(__import__("sqlite3").connect(str(m.DB_PATH)).execute("select inquiry_data from invoices limit 1").fetchone()[0])
            assert invoice_items_html(d)
        step("invoice_items_html", inv_html)

    summary = ["## GUI smoke test", "", "OK: %d | FAIL: %d" % (len(OKS), len(FAILS)), ""]
    for n in OKS:
        summary.append("- ✅ " + n)
    for n, tb in FAILS:
        summary.append("- ❌ **%s**\n```\n%s\n```" % (n, tb[-1500:]))
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(summary) + "\n")
    print("\n".join(summary))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
