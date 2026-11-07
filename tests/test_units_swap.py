import sys, types, unittest
class T(unittest.TestCase):
    def test_swap(self):
        import re, pandas as pd
        src = open("salesmate/analysis_page.py", encoding="utf-8").read()
        m = re.search(r"def fix_unit_order.*?\n    return df\n", src, re.S)
        ns = {"pd": pd}; exec(m.group(0), ns)
        df = pd.DataFrame({"دسته": ["ام دی اف", "خام", "پارکت", "پارکت", "ام دی اف"],
                           "تعداد 1": [100, 3, 2, 50, 0], "تعداد 2": [2, 90, 40, 5, 7]})
        r = ns["fix_unit_order"](df)
        self.assertEqual(list(r["تعداد 1"]), [2, 3, 2, 5, 0])
        self.assertEqual(list(r["تعداد 2"]), [100, 90, 40, 50, 7])
