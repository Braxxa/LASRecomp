package io.github.braxxa.lasrecomp;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.io.*;
import java.nio.file.Files;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class LauncherActivity extends Activity {
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private TextView status;
    private Button play, importButton;
    private volatile boolean importing;
    private File root() { return getExternalFilesDir(null); }
    private File game() { return new File(root(), "extracted"); }
    private boolean assetsReady() {
        return !new File(game(),".importing").exists() && new File(game(), "exefs/main").isFile() && new File(game(), "exefs/sdk").isFile()
            && new File(game(), "romfs/region_common").isDirectory();
    }
    private boolean ready() {
        return assetsReady() && new File(getApplicationInfo().nativeLibraryDir,"liblasgame.so").isFile();
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        int pad = (int)(24 * getResources().getDisplayMetrics().density);
        body.setPadding(pad,pad,pad,pad);
        TextView title = new TextView(this);
        title.setText("LAS Recomp · Android"); title.setTextSize(28); body.addView(title);
        TextView subtitle = new TextView(this);
        subtitle.setText("Versión experimental para Retroid Pocket 6.\nUsá los controles de la consola; Select + Start abre el menú.\n\nImportá la carpeta extracted preparada en tu PC. Necesita varios GB de espacio libre.");
        subtitle.setTextSize(17); body.addView(subtitle);
        status = new TextView(this); status.setPadding(0,24,0,16); body.addView(status);
        play = new Button(this); play.setText("Jugar"); body.addView(play);
        play.setOnClickListener(v -> startActivity(new Intent(this, GameActivity.class)));
        importButton = new Button(this); importButton.setText("Importar archivos del juego"); body.addView(importButton);
        importButton.setOnClickListener(v -> startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION), 1));
        Button diagnose = new Button(this); diagnose.setText("Comprobar gráficos"); body.addView(diagnose);
        diagnose.setOnClickListener(v -> startActivity(new Intent(this,GameActivity.class).putExtra("diagnose",true)));
        Button logs = new Button(this); logs.setText("Ver registro"); body.addView(logs);
        logs.setOnClickListener(v -> showLog());
        ScrollView scroll = new ScrollView(this); scroll.addView(body); setContentView(scroll);
        try {
            File fonts = new File(root(), "third_party/fonts/Baloo2"); fonts.mkdirs();
            copyAsset("Baloo2-SemiBold.ttf", new File(fonts,"Baloo2-SemiBold.ttf"));
            copyAsset("Baloo2-OFL.txt", new File(fonts,"OFL.txt"));
            File gameFont = new File(root(),"third_party/fonts/DejaVu"); gameFont.mkdirs();
            copyAsset("DejaVuSans.ttf", new File(gameFont,"DejaVuSans.ttf"));
            copyAsset("DejaVu-LICENSE.txt", new File(gameFont,"LICENSE.txt"));
            File settings = new File(root(), "larecomp.ini");
            if (!settings.exists()) {
                String defaults = "aspect = original\nresolution = 75%\nupscaler = bilinear\nantialias = off\nshow_fps = 1\nlanguage = es\nblur_removal = 1\n";
                Files.write(settings.toPath(), defaults.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            }
        } catch (IOException e) { status.setText("No se pudo preparar la fuente: " + e.getMessage()); }
        refresh();
        if (getIntent().getBooleanExtra("diagnose", false))
            startActivity(new Intent(this,GameActivity.class).putExtra("diagnose",true));
        else if (getIntent().getBooleanExtra("play", false) && ready())
            startActivity(new Intent(this,GameActivity.class));
    }
    private void copyAsset(String name, File target) throws IOException {
        try (InputStream in = getAssets().open(name); OutputStream out = new FileOutputStream(target)) { in.transferTo(out); }
    }
    private void refresh() {
        if (status == null || importing) return;
        play.setEnabled(ready());
        status.setText(ready() ? "Archivos listos.\n" + root().getAbsolutePath() : !assetsReady()
            ? "Faltan los archivos del juego. Importá la carpeta que contiene exefs y romfs."
            : "Falta el código del juego preparado en la PC. Instalá el APK personal generado desde tus archivos.");
    }
    @Override protected void onResume() { super.onResume(); refresh(); }
    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request != 1 || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri tree = data.getData();
        importing = true; play.setEnabled(false); importButton.setEnabled(false);
        status.setText("Importando… Mantené la aplicación abierta.");
        worker.execute(() -> {
            String error = null;
            try {
                game().mkdirs();
                Files.write(new File(game(),".importing").toPath(),new byte[0]);
                Files.deleteIfExists(new File(game(),"romfs.bin").toPath());
                Uri dir = DocumentsContract.buildDocumentUriUsingTree(tree, DocumentsContract.getTreeDocumentId(tree));
                copyDirectory(tree, dir, game(), true);
                Files.deleteIfExists(new File(game(),".importing").toPath());
                if (!assetsReady()) throw new IOException("La carpeta elegida debe contener exefs/main, exefs/sdk y romfs/region_common.");
            } catch (Exception e) { error = e.getMessage(); }
            final String message = error;
            runOnUiThread(() -> {
                importing = false; importButton.setEnabled(true); refresh();
                if (message != null) new AlertDialog.Builder(this).setTitle("No se completó la importación").setMessage(message).setPositiveButton("Aceptar",null).show();
            });
        });
    }
    private void copyDirectory(Uri tree, Uri dir, File target, boolean top) throws IOException {
        if (!target.isDirectory() && !target.mkdirs()) throw new IOException("No se pudo crear " + target);
        Uri children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, DocumentsContract.getDocumentId(dir));
        String[] cols = {DocumentsContract.Document.COLUMN_DOCUMENT_ID, DocumentsContract.Document.COLUMN_DISPLAY_NAME, DocumentsContract.Document.COLUMN_MIME_TYPE};
        try (Cursor c = getContentResolver().query(children,cols,null,null,null)) {
            if (c == null) throw new IOException("No se puede leer la carpeta elegida.");
            while (c.moveToNext()) {
                String name = c.getString(1);
                if (name == null || name.equals(".") || name.equals("..") || name.contains("/") || name.contains("\\")) throw new IOException("Nombre de archivo inválido.");
                if (top && !name.equals("exefs") && !name.equals("romfs")) continue;
                File file = new File(target, name);
                Uri doc = DocumentsContract.buildDocumentUriUsingTree(tree,c.getString(0));
                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(c.getString(2))) copyDirectory(tree,doc,file,false);
                else {
                    File partial = new File(target,name+".importing");
                    try (InputStream in = getContentResolver().openInputStream(doc); OutputStream out = new FileOutputStream(partial)) {
                        if (in == null) throw new IOException("No se puede leer " + name);
                        byte[] buffer = new byte[1024*1024]; int n;
                        while ((n=in.read(buffer))!=-1) out.write(buffer,0,n);
                    }
                    Files.move(partial.toPath(),file.toPath(),java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                }
            }
        }
    }
    private void showLog() {
        String text;
        try (RandomAccessFile log = new RandomAccessFile(new File(root(),"lasrecomp.log"),"r")) {
            int size = (int)Math.min(log.length(),192*1024); byte[] bytes = new byte[size];
            log.seek(log.length()-size); log.readFully(bytes); text = new String(bytes,java.nio.charset.StandardCharsets.UTF_8);
        } catch (IOException e) { text = "Todavía no hay un registro de ejecución."; }
        TextView view = new TextView(this); view.setTextIsSelectable(true); view.setTextSize(11); view.setText(text); view.setPadding(16,16,16,16);
        ScrollView scroll = new ScrollView(this); scroll.addView(view);
        new AlertDialog.Builder(this).setTitle("Registro de la última partida").setView(scroll).setPositiveButton("Cerrar",null).show();
    }
}
