"""آپدیت سبک: اگر پوشه‌ی code کنار برنامه نسخه‌ی جدیدتری از کد داشته باشد، همان اجرا می‌شود.
این فایل باید بسیار ساده بماند؛ در ابتدای main.py (فقط در حالت frozen) صدا زده می‌شود."""
import sys
import os
import json
import importlib.abc
import importlib.util
from pathlib import Path


def _vt(v):
    out = []
    for p in str(v or "").replace("-", ".").split("."):
        try:
            out.append(int(p))
        except Exception:
            out.append(0)
    return tuple(out)


class _OverlayFinder(importlib.abc.MetaPathFinder):
    def __init__(self, root, names):
        self.root = Path(root)
        self.names = set(names)

    def find_spec(self, fullname, path=None, target=None):
        if "." in fullname or fullname not in self.names:
            return None
        f = self.root / (fullname + ".py")
        if not f.is_file():
            return None
        return importlib.util.spec_from_file_location(fullname, str(f))


def overlay_base_dir():
    return Path(sys.executable).resolve().parent / "code"


def active_overlay(bundle_version):
    """مسیر پوشه‌ی کد فعال (یا None) — فقط اگر از نسخه‌ی داخل exe جدیدتر و سازگار باشد."""
    try:
        base = overlay_base_dir()
        cur = json.loads((base / "current.json").read_text(encoding="utf-8"))
        ver = str(cur.get("version") or "")
        d = base / str(cur.get("dir") or "")
        if cur.get("bad") == ver or not d.is_dir() or not (d / "main.py").is_file():
            return None
        if _vt(ver) <= _vt(bundle_version):
            return None
        pj = {}
        try:
            pj = json.loads((d / "patch.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        if _vt(pj.get("min_bundle", "0")) > _vt(bundle_version):
            return None
        return d
    except Exception:
        return None


def mark_bad(ver):
    try:
        base = overlay_base_dir()
        p = base / "current.json"
        cur = json.loads(p.read_text(encoding="utf-8"))
        cur["bad"] = str(cur.get("version") or ver)
        p.write_text(json.dumps(cur), encoding="utf-8")
    except Exception:
        pass


def try_run_overlay(bundle_version):
    """اگر کد جدید موجود است اجرا می‌کند و با sys.exit تمام می‌شود.
    اگر در بالا آمدن خطا بدهد، به نسخه‌ی داخل exe برمی‌گردد (و آن نسخه‌ی کد را «بد» علامت می‌زند)."""
    if os.environ.get("SALESMATE_OVERLAY_ACTIVE"):
        return
    d = active_overlay(bundle_version)
    if d is None:
        return
    names = [p.stem for p in d.glob("*.py")]
    finder = _OverlayFinder(d, names)
    saved = {}
    for n in names:
        if n in sys.modules:
            saved[n] = sys.modules.pop(n)
    sys.meta_path.insert(0, finder)
    os.environ["SALESMATE_OVERLAY_ACTIVE"] = "1"
    try:
        import runpy
        runpy.run_path(str(d / "main.py"), run_name="__main__")
        sys.exit(0)
    except SystemExit:
        raise
    except BaseException:
        try:
            import traceback
            (d.parent / "overlay_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        except Exception:
            pass
        try:
            sys.meta_path.remove(finder)
        except Exception:
            pass
        for n in names:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
        os.environ.pop("SALESMATE_OVERLAY_ACTIVE", None)
        mark_bad(None)
