"""یک Qt ساختگیِ بسیار کوچک برای تست منطق صفحه‌ها بدون نصب PySide6 (فقط برای تست!)."""
import sys
import types


class _QtMeta(type):
    _vals = {}

    def __getattr__(cls, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name not in cls._vals:
            cls._vals[name] = 1 << (len(cls._vals) % 30)
        return cls._vals[name]


class Qt(metaclass=_QtMeta):
    pass


class _BoundSignal:
    def __init__(self):
        self.slots = []

    def connect(self, fn):
        self.slots.append(fn)

    def emit(self, *a):
        for s in list(self.slots):
            s(*a)

    def disconnect(self, *a):
        self.slots = []


class Signal:
    def __init__(self, *types):
        pass

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, obj, owner):
        if obj is None:
            return self
        d = obj.__dict__
        key = "_sig_" + self.name
        if key not in d:
            d[key] = _BoundSignal()
        return d[key]


class QObject:
    def __init__(self, *a, **k):
        pass


class Anything:
    """هر متدی را می‌پذیرد و None برمی‌گرداند."""
    def __init__(self, *a, **k):
        self._text = a[0] if a and isinstance(a[0], str) else ""

    def __getattr__(self, n):
        if n.startswith("__"):
            raise AttributeError(n)
        return lambda *a, **k: None

    def style(self):
        return Anything()


class QWidget(Anything):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._enabled = True
        self._hidden = False
        self._tip = ""
        self.clicked = _BoundSignal()
        self.textChanged = _BoundSignal()
        self.currentIndexChanged = _BoundSignal()
        self.valueChanged = _BoundSignal()
        self.editingFinished = _BoundSignal()
        self.itemSelectionChanged = _BoundSignal()
        self.itemChanged = _BoundSignal()
        self.cellDoubleClicked = _BoundSignal()
        self.currentChanged = _BoundSignal()
        self.triggered = _BoundSignal()
        self.textEdited = _BoundSignal()
        self.returnPressed = _BoundSignal()

    def setText(self, t): self._text = t
    def text(self): return self._text
    def setToolTip(self, t): self._tip = t
    def toolTip(self): return self._tip
    def setEnabled(self, b): self._enabled = b
    def hide(self): self._hidden = True
    def setVisible(self, b): self._hidden = not b
    def isVisible(self): return not self._hidden
    def blockSignals(self, b): pass
    def underMouse(self): return False


class QLabel(QWidget): pass
class QFrame(QWidget):
    NoFrame = 0
class QPushButton(QWidget): pass
class QMenu(QWidget):
    def addAction(self, t):
        a = QWidget(); return a
class QSplitter(QWidget): pass
class QScrollArea(QWidget): pass
class QTabBar(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.tabs = []; self.cur = 0
    def addTab(self, t): self.tabs.append(t)
    def setTabText(self, i, t): self.tabs[i] = t
    def setCurrentIndex(self, i): self.cur = i
    def currentIndex(self): return self.cur
class QTabWidget(QWidget):
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self.pages = []; self.cur = 0
    def addTab(self, w, t): self.pages.append((w, t))
    def setCurrentIndex(self, i): self.cur = i; self.currentChanged.emit(i)
    def currentIndex(self): return self.cur


class QLineEdit(QWidget):
    def __init__(self, t="", *a, **k):
        super().__init__(); self._text = t if isinstance(t, str) else ""
    def setText(self, t):
        self._text = t
        self.textChanged.emit(t)


class QCheckBox(QWidget):
    def __init__(self, *a, **k): super().__init__(); self._c = False
    def setChecked(self, b): self._c = b
    def isChecked(self): return self._c


class QComboBox(QWidget):
    def __init__(self, *a, **k): super().__init__(); self.items = []; self.idx = -1
    def addItem(self, t): self.items.append(t); self.idx = max(self.idx, 0)
    def addItems(self, ts): [self.addItem(t) for t in ts]
    def currentText(self): return self.items[self.idx] if 0 <= self.idx < len(self.items) else ""
    def currentIndex(self): return self.idx
    def setCurrentIndex(self, i): self.idx = i; self.currentIndexChanged.emit(i)


class QDoubleSpinBox(QWidget):
    def __init__(self, *a, **k): super().__init__(); self.v = 0.0
    def setValue(self, v): self.v = v
    def value(self): return self.v


class QTableWidgetItem:
    def __init__(self, text=""):
        self._text = text if isinstance(text, str) else ""
        self._data = {}
        self._row = -1
        self._col = -1
        self._check = Qt.Unchecked
        self._tip = ""
    def text(self): return self._text
    def setText(self, t): self._text = t
    def setData(self, role, v): self._data[role] = v
    def data(self, role): return self._data.get(role)
    def row(self): return self._row
    def column(self): return self._col
    def setToolTip(self, t): self._tip = t
    def toolTip(self): return self._tip
    def setForeground(self, c): pass
    def setFlags(self, f): pass
    def setTextAlignment(self, a): pass
    def setCheckState(self, s): self._check = s
    def checkState(self): return self._check
    def font(self): return Anything()
    def setFont(self, f): pass


class QTableWidget(QWidget):
    NoEditTriggers = SelectRows = SingleSelection = ExtendedSelection = 0

    def __init__(self, rows=0, cols=0, *a, **k):
        super().__init__()
        self.cols = cols
        self.rows = [[None] * cols for _ in range(rows)]
        self._cur = -1
        self._sel = set()
        self.sorting = False

    def setHorizontalHeaderLabels(self, l): self.headers = l
    def horizontalHeader(self): return Anything()
    def verticalHeader(self): return Anything()
    def setSortingEnabled(self, b): self.sorting = b
    def rowCount(self): return len(self.rows)
    def setRowCount(self, n):
        if n < len(self.rows):
            self.rows = self.rows[:n]
        else:
            self.rows += [[None] * self.cols for _ in range(n - len(self.rows))]
        self._cur = -1; self._sel = set()
        self.itemSelectionChanged.emit()
    def insertRow(self, r): self.rows.insert(r, [None] * self.cols)
    def setItem(self, r, c, it):
        it._row, it._col = r, c
        self.rows[r][c] = it
    def item(self, r, c): return self.rows[r][c] if 0 <= r < len(self.rows) else None
    def currentRow(self): return self._cur
    def selectRow(self, r):
        self._cur = r; self._sel = {r}; self.itemSelectionChanged.emit()
    def selectedItems(self):
        return [self.rows[r][c] for r in sorted(self._sel) for c in range(self.cols) if self.rows[r][c]]
    def scrollToItem(self, it): pass
    def sortItems(self, col, order=None):
        desc = (order == Qt.DescendingOrder)
        def key(row):
            it = row[col]
            return getattr(it, "_k", it._text)
        self.rows.sort(key=key, reverse=desc)
        for r, row in enumerate(self.rows):
            for c, it in enumerate(row):
                if it: it._row = r
    def blockSignals(self, b): pass


class QMessageBox:
    Yes = 1; No = 2; AcceptRole = 3; DestructiveRole = 4; RejectRole = 5; ActionRole = 6
    log = []
    answer = 1

    def __init__(self, *a, **k): self._btns = []; self._clicked = None
    @classmethod
    def _rec(cls, kind, args):
        cls.log.append((kind, args[1:3])); return cls.answer
    @classmethod
    def information(cls, *a): return cls._rec("info", a)
    @classmethod
    def warning(cls, *a): return cls._rec("warn", a)
    @classmethod
    def critical(cls, *a): return cls._rec("crit", a)
    @classmethod
    def question(cls, *a): return cls._rec("question", a)
    def setWindowTitle(self, t): pass
    def setText(self, t): pass
    def addButton(self, t, role=None):
        b = QWidget(); b._text = t; self._btns.append(b); return b
    def exec(self): self._clicked = self._btns[-1] if self._btns else None
    def clickedButton(self): return self._clicked


class QFileDialog:
    open_path = ""
    save_path = ""
    @classmethod
    def getOpenFileName(cls, *a, **k): return cls.open_path, ""
    @classmethod
    def getSaveFileName(cls, *a, **k): return cls.save_path, ""


class QDialog(QWidget):
    def exec(self): return 1
    def accept(self): pass
    def reject(self): pass


class QTimer(QObject):
    def __init__(self, *a, **k):
        super().__init__(); self.timeout = _BoundSignal(); self.started = None
    def setSingleShot(self, b): pass
    def start(self, ms=0): self.started = ms
    @staticmethod
    def singleShot(ms, fn): pass


class QHeaderView(Anything):
    Stretch = 1
    ResizeToContents = 2
    Interactive = 3


class QColor:
    def __init__(self, *a): pass


def install():
    def mod(name, **attrs):
        m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m
    mod("PySide6")
    mod("PySide6.QtCore", Qt=Qt, QTimer=QTimer, QObject=QObject, Signal=Signal, QUrl=Anything)
    mod("PySide6.QtGui", QColor=QColor, QDesktopServices=Anything)
    W = {n: globals()[n] for n in ("QWidget", "QLabel", "QFrame", "QPushButton", "QMenu", "QSplitter", "QTabBar", "QTabWidget",
                                   "QLineEdit", "QCheckBox", "QComboBox", "QDoubleSpinBox", "QTableWidget", "QTableWidgetItem",
                                   "QMessageBox", "QFileDialog", "QDialog", "QScrollArea")}
    W.update(QVBoxLayout=Anything, QHBoxLayout=Anything, QGridLayout=Anything, QFormLayout=Anything, QHeaderView=QHeaderView, QApplication=Anything, QSizePolicy=Anything)
    mod("PySide6.QtWidgets", **W)
