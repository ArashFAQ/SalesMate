"""لاگ فایلی SalesMate + جایگزین `except Exception: pass`.

به‌جای بلعیدن بی‌صدای خطا، اولین رخداد هر خطا (با traceback) در salesmate.log کنار برنامه ثبت می‌شود؛
تکرارهای بعدی فقط شمرده می‌شوند تا لاگ پر نشود.
"""
import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("salesmate")
_seen = {}


def setup_logging(app_dir):
    """یک‌بار در شروع برنامه صدا زده می‌شود. خطاهای کنترل‌نشده هم ثبت می‌شوند."""
    try:
        if log.handlers:
            return
        log.setLevel(logging.INFO)
        h = RotatingFileHandler(
            Path(app_dir) / "salesmate.log", maxBytes=512 * 1024, backupCount=3, encoding="utf-8"
        )
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)

        def _hook(et, ev, tb):
            try:
                log.error("uncaught exception", exc_info=(et, ev, tb))
            except Exception:
                pass
            sys.__excepthook__(et, ev, tb)

        sys.excepthook = _hook
    except Exception:
        pass


def swallow(note=""):
    """داخل بلوک except صدا بزن: خطا را (محدود) لاگ می‌کند و برنامه ادامه می‌دهد."""
    try:
        et, ev, tb = sys.exc_info()
        if et is None:
            return
        fr = traceback.extract_tb(tb)[-1] if tb else None
        where = "%s:%s" % (Path(fr.filename).name, fr.lineno) if fr else (note or "?")
        key = (where, et.__name__)
        n = _seen.get(key, 0) + 1
        _seen[key] = n
        if n == 1:
            log.warning("swallowed %s at %s %s", et.__name__, where, ev, exc_info=True)
        elif n % 200 == 0:
            log.warning("swallowed %s at %s (x%d)", et.__name__, where, n)
    except Exception:
        pass
