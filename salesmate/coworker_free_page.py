# -*- coding: utf-8 -*-
"""سمپل و استند برای حساب همکار: همان صفحه‌ی مالک، اما فقط با ردیف‌های صفرِ مشتریان تیک‌خورده‌ی خودش
که برنامه‌ی مالک بعد از هر بارگذاری اکسل در ابر می‌گذارد."""
import threading

try:
    from stats_pages import FreeItemsPage
    import coworker_core as cw
    from app_core import run_in_ui, supabase_request, supabase_session_valid, supabase_user_info
except Exception:
    from salesmate.stats_pages import FreeItemsPage
    from salesmate import coworker_core as cw
    from salesmate.app_core import run_in_ui, supabase_request, supabase_session_valid, supabase_user_info


class CoworkerFreePage(FreeItemsPage):
    def __init__(self, win):
        super().__init__(win)
        self._cloud_df = None
        self._loading = False

    def _load_df(self):
        return self._cloud_df

    def refresh(self):
        """ابتدا داده‌ی ذخیره‌شده نشان داده می‌شود و هم‌زمان نسخه‌ی تازه از ابر گرفته می‌شود."""
        super().refresh()
        self.fetch()

    def fetch(self):
        if self._loading or not supabase_session_valid():
            return
        uid = supabase_user_info().get("user_id") or ""
        if not uid:
            return
        self._loading = True
        self.hint.setText("در حال دریافت از ابر…")

        def _run():
            df, err = None, None
            try:
                df = cw.fetch_free_df(supabase_request, uid)
            except Exception as ex:
                err = ex

            def _ui():
                self._loading = False
                if err is not None:
                    self.hint.setText("دریافت ناموفق: " + str(err)[:80])
                    return
                self._cloud_df = df
                FreeItemsPage.refresh(self)
                if df is None:
                    self.hint.setText("هنوز داده‌ای برای شما در ابر نیست")
            run_in_ui(_ui)
        threading.Thread(target=_run, daemon=True).start()
