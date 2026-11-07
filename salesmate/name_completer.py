"""پیشنهاد نام: هر بخشی از نام (چند کلمه، هر ترتیب) — برای کادرهای جست‌وجوی مشتری."""
from PySide6.QtCore import Qt, QSortFilterProxyModel, QStringListModel
from PySide6.QtWidgets import QCompleter


def norm(t):
    t = str(t or "").replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    return t.lower()


class TokenProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.q = []

    def set_query(self, text):
        self.q = [w for w in norm(text).split() if w]
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        if not self.q:
            return True
        t = norm(self.sourceModel().index(row, 0, parent).data())
        return all(w in t for w in self.q)


def make_completer(owner, source_model):
    """(completer, proxy) — کامپلیتر روی proxy که فیلتر چندکلمه‌ای دارد."""
    proxy = TokenProxy(owner)
    proxy.setSourceModel(source_model)
    comp = QCompleter(proxy, owner)
    comp.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
    comp.setCaseSensitivity(Qt.CaseInsensitive)
    comp.setMaxVisibleItems(12)
    return comp, proxy


def attach_to_line_edit(line_edit, names):
    """به یک QLineEdit ساده وصل می‌شود؛ برای به‌روزرسانی: result['model'].setStringList(names)"""
    model = QStringListModel(list(names))
    comp, proxy = make_completer(line_edit, model)
    line_edit.setCompleter(comp)
    line_edit.textEdited.connect(proxy.set_query)
    return {"model": model, "proxy": proxy, "completer": comp}
