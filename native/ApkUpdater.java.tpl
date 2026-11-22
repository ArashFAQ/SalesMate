package __PKG__;

import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;

import androidx.core.content.FileProvider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

/** دانلود APK داخل برنامه (با گزارش پیشرفت) و باز کردن نصب‌کننده‌ی اندروید. */
@CapacitorPlugin(name = "ApkUpdater")
public class ApkUpdater extends Plugin {
    private volatile boolean busy = false;

    @PluginMethod
    public void download(final PluginCall call) {
        final String url = call.getString("url");
        if (url == null || url.isEmpty()) { call.reject("no url"); return; }
        if (busy) { call.reject("busy"); return; }
        busy = true;
        new Thread(new Runnable() {
            @Override public void run() {
                File out = new File(getContext().getCacheDir(), "SalesMate-update.apk");
                File tmp = new File(getContext().getCacheDir(), "SalesMate-update.part");
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(url).openConnection();
                    c.setInstanceFollowRedirects(true);
                    c.setConnectTimeout(20000);
                    c.setReadTimeout(30000);
                    c.connect();
                    if (c.getResponseCode() / 100 != 2) throw new IOException("HTTP " + c.getResponseCode());
                    long total = c.getContentLengthLong();
                    long done = 0, last = 0;
                    try (InputStream in = c.getInputStream(); FileOutputStream fo = new FileOutputStream(tmp)) {
                        byte[] buf = new byte[65536];
                        int n;
                        while ((n = in.read(buf)) > 0) {
                            fo.write(buf, 0, n);
                            done += n;
                            long now = System.currentTimeMillis();
                            if (now - last > 150) {
                                last = now;
                                JSObject o = new JSObject();
                                o.put("done", done);
                                o.put("total", total);
                                notifyListeners("progress", o);
                            }
                        }
                    }
                    if (total > 0 && done != total) throw new IOException("incomplete");
                    if (out.exists()) out.delete();
                    if (!tmp.renameTo(out)) throw new IOException("rename failed");
                    JSObject r = new JSObject();
                    r.put("size", out.length());
                    call.resolve(r);
                } catch (Exception e) {
                    tmp.delete();
                    call.reject(String.valueOf(e.getMessage()));
                } finally {
                    busy = false;
                }
            }
        }).start();
    }

    @PluginMethod
    public void install(PluginCall call) {
        Context ctx = getContext();
        File f = new File(ctx.getCacheDir(), "SalesMate-update.apk");
        if (!f.exists()) { call.reject("no file"); return; }
        if (Build.VERSION.SDK_INT >= 26 && !ctx.getPackageManager().canRequestPackageInstalls()) {
            Intent s = new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:" + ctx.getPackageName()));
            s.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            ctx.startActivity(s);
            JSObject r = new JSObject();
            r.put("needPermission", true);
            call.resolve(r);
            return;
        }
        Uri uri = FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", f);
        Intent i = new Intent(Intent.ACTION_VIEW);
        i.setDataAndType(uri, "application/vnd.android.package-archive");
        i.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_ACTIVITY_NEW_TASK);
        ctx.startActivity(i);
        JSObject r = new JSObject();
        r.put("needPermission", false);
        call.resolve(r);
    }
}
