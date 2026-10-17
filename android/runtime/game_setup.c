#include "rt.h"
#include "romfs_build.h"
#include <sys/stat.h>
#include <unistd.h>

extern void android_set_status(const char *message);
static void progress(uint64_t done, uint64_t total) {
    static int previous = -1;
    int percent = total ? (int)(done * 100 / total) : 0;
    if (percent == previous) return;
    previous = percent;
    char message[160];
    snprintf(message,sizeof message,"Preparando el juego: %d%%\nEsto se hace una sola vez. Mantené la app abierta.",percent);
    android_set_status(message);
    if (percent % 10 == 0) LOG("[android-setup] RomFS image %d%%\n",percent);
}

void android_prepare_game(const char *root) {
    char source[1200], image[1200], partial[1220], why[512];
    snprintf(source,sizeof source,"%s/romfs",root);
    snprintf(image,sizeof image,"%s/romfs.bin",root);
    struct stat info;
    if (stat(image,&info) != 0) {
        snprintf(partial,sizeof partial,"%s.preparing",image);
        LOG("[android-setup] Building raw RomFS image from local files\n");
        if (!romfs_build(source,partial,progress,why,sizeof why)) FATAL("Android preparation: %s\n",why);
        if (rename(partial,image) != 0) FATAL("Cannot finish prepared RomFS image\n");
        LOG("[android-setup] RomFS image ready\n");
    }
    android_set_status("Cargando el juego…");
}
