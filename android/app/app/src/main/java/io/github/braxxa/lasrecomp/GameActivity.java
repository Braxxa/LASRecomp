package io.github.braxxa.lasrecomp;

import org.libsdl.app.SDLActivity;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.TextView;
import android.widget.RelativeLayout;

/** A separate process gives each game session a fresh guest address space. */
public final class GameActivity extends SDLActivity {
    private static native void nativeSetActive(boolean active);
    private TextView nativeStatus;
    @Override protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        // Use SDL's command queue so its initial windowed-style command cannot
        // restore the status-bar inset after the immersive view is laid out.
        SDLActivity.setWindowStyle(true);
        if (mLayout != null) {
            nativeStatus = new TextView(this);
            nativeStatus.setText("Arrancando…"); nativeStatus.setTextSize(20);
            nativeStatus.setTextColor(0xffffffff); nativeStatus.setBackgroundColor(0xdd101820);
            nativeStatus.setGravity(Gravity.CENTER); nativeStatus.setPadding(16,16,16,16);
            mLayout.addView(nativeStatus,new RelativeLayout.LayoutParams(-1,-2));
        }
    }
    public void setNativeStatus(String message) {
        runOnUiThread(() -> {
            if (nativeStatus == null) return;
            nativeStatus.setText(message);
            nativeStatus.setVisibility(message.isEmpty() ? View.GONE : View.VISIBLE);
        });
    }
    @Override protected void onResume() {
        super.onResume();
        try { nativeSetActive(true); } catch (UnsatisfiedLinkError ignored) { /* SDL shows library load errors. */ }
    }
    @Override protected void onPause() {
        try { nativeSetActive(false); } catch (UnsatisfiedLinkError ignored) { /* Native loading may have failed. */ }
        super.onPause();
    }
    @Override protected String[] getLibraries() {
        return new String[] {"SDL3", "avutil", "avcodec", "avformat", "swscale", "shaderc_shared", "main"};
    }
    @Override protected String[] getArguments() {
        return new String[] {getExternalFilesDir(null).getAbsolutePath() + "/extracted",
            getIntent().getBooleanExtra("diagnose", false) ? "--android-probe" : "--play"};
    }
    @Override protected void onDestroy() {
        super.onDestroy();
        android.os.Process.killProcess(android.os.Process.myPid());
    }
}
