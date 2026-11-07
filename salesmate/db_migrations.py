"""مهاجرت‌های دیتابیس SQLite (بدون Qt — قابل تست)."""
import logging
import shutil
from pathlib import Path

try:
    from core_utils import canon_money
except Exception:
    from salesmate.core_utils import canon_money

_log = logging.getLogger("salesmate")

_MONEY_COLUMNS = (
    ("invoices", "total", "id"),
    ("invoices", "paid_amount", "id"),
    ("store_sales", "total", "id"),
    ("customer_balance_adj", "adjustment", "customer"),
)


def migrate_money_v1(c, db_path, backup_dir):
    """یک‌بار: مبلغ‌های متنی ("۱,۲۰۰,۰۰۰"، ارقام فارسی، فاصله) → رشته‌ی عدد صحیح استاندارد.
    مقدارهایی که شبیه عدد نیستند دست نمی‌خورند. قبل از تغییر از فایل دیتابیس بکاپ گرفته می‌شود.
    خروجی: تعداد مقدارهای بازنویسی‌شده."""
    try:
        dbp = Path(db_path)
        if dbp.exists() and dbp.stat().st_size > 0:
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            shutil.copy2(dbp, Path(backup_dir) / "salesmate_before_money_fix.db")
    except Exception:
        _log.warning("backup before money migration failed", exc_info=True)
    changed = 0
    for table, col, key in _MONEY_COLUMNS:
        try:
            rows = c.execute("SELECT %s, %s FROM %s" % (key, col, table)).fetchall()
        except Exception:
            continue  # جدول/ستون در این نسخه‌ی دیتابیس نیست
        for k, v in rows:
            if v is None or str(v).strip() == "":
                continue
            new = canon_money(v)
            if new is not None and new != str(v):
                c.execute("UPDATE %s SET %s=? WHERE %s=?" % (table, col, key), (new, k))
                changed += 1
    c.execute("PRAGMA user_version = 1")
    c.commit()
    _log.info("money normalization done: %d values rewritten", changed)
    return changed


def _jenagi_fix_rows(rows):
    """ردیف‌های جناغی: متراژ = کارتن × ۲٫۰۰۶۶ و مبلغ = قیمت × متراژ. خروجی: (تعداد تغییر، جمع قدیم، جمع جدید)."""
    import json as _json  # noqa: F401
    n = old_sum = new_sum = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            cost_old = int(round(float(str(r.get("cost") or 0).replace(",", ""))))
        except Exception:
            cost_old = 0
        old_sum += cost_old
        nm = "%s %s" % (r.get("name") or "", r.get("type") or r.get("typ") or "")
        if "جناغی" in nm or "جناقی" in nm:
            try:
                q1 = float(str(r.get("qty1") or 0).replace(",", ""))
                price = float(str(r.get("price") or 0).replace(",", ""))
            except Exception:
                q1 = price = 0
            if q1 > 0 and price > 0:
                m = round(q1 * 2.0066, 4)
                cost = int(round(price * m))
                if str(r.get("qty2")) != ("%g" % m) or cost != cost_old:
                    r["qty2"] = "%g" % m
                    r["cost"] = str(cost)
                    n += 1
                    cost_old = cost
        new_sum += cost_old
    return n, old_sum, new_sum


def migrate_jenagi_v2(c, db_path, backup_dir):
    """یک‌بار: متراژ و مبلغ ردیف‌های «جناغی» که با ضریب اشتباه ۱٫۹۶۰۸ ذخیره شده‌اند اصلاح می‌شود.
    مبلغ کل حواله فقط اگر قبلاً برابر جمع ردیف‌ها بوده با جمع جدید هماهنگ می‌شود. قبل از تغییر بکاپ گرفته می‌شود."""
    import json
    try:
        dbp = Path(db_path)
        if dbp.exists() and dbp.stat().st_size > 0:
            Path(backup_dir).mkdir(parents=True, exist_ok=True)
            shutil.copy2(dbp, Path(backup_dir) / "salesmate_before_jenagi_fix.db")
    except Exception:
        _log.warning("backup before jenagi migration failed", exc_info=True)
    changed = 0
    for table, col in (("invoices", "inquiry_data"), ("store_sales", "items_json")):
        try:
            recs = c.execute("SELECT id, %s, total FROM %s" % (col, table)).fetchall()
        except Exception:
            continue
        for rid, blob, total in recs:
            try:
                data = json.loads(blob or "")
            except Exception:
                continue
            is_dict = isinstance(data, dict)
            if is_dict and data.get("tab") == "analysis_import":
                continue  # حواله‌ی اکسلی: اکسل فروش مرجع است و دست نمی‌خورد
            rows = data.get("rows") if is_dict else data
            if not is_dict and isinstance(rows, list) and any(isinstance(x, dict) and "name" in x for x in rows):
                continue  # فروش فروشگاهِ واردشده از اکسل
            if not isinstance(rows, list):
                continue
            n, old_sum, new_sum = _jenagi_fix_rows(rows)
            if not n:
                continue
            try:
                t_old = int(round(float(str(total or 0).replace(",", ""))))
            except Exception:
                t_old = None
            new_total = str(new_sum) if (t_old is not None and abs(t_old - old_sum) <= 1) else str(total)
            if is_dict and new_total.isdigit():
                data["total"] = int(new_total)
            c.execute("UPDATE %s SET %s=?, total=? WHERE id=?" % (table, col), (json.dumps(data, ensure_ascii=False), new_total, rid))
            changed += 1
    c.execute("PRAGMA user_version = 2")
    c.commit()
    _log.info("jenagi fix done: %d records", changed)
    return changed
