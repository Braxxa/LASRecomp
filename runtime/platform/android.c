// Android host layer. Game preparation and recompilation run on the user's PC.
#define _GNU_SOURCE
#include <SDL3/SDL.h>
#include <SDL3/SDL_system.h>
#include <jni.h>
#include <dlfcn.h>
#include <errno.h>
#include <ftw.h>
#include <pthread.h>
#include <signal.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/ucontext.h>
#include <time.h>
#include <unistd.h>
#include <unwind.h>
#include "../platform.h"

#ifndef MAP_FIXED_NOREPLACE
#define MAP_FIXED_NOREPLACE 0x100000
#endif
static char log_path[1200];
static atomic_bool app_active = true;
bool android_app_is_active(void) { return atomic_load(&app_active); }
JNIEXPORT void JNICALL Java_io_github_braxxa_lasrecomp_GameActivity_nativeSetActive(JNIEnv *env,jclass cls,jboolean active) {
    (void)env; (void)cls; atomic_store(&app_active,active);
}

void android_set_status(const char *message) {
    JNIEnv *env = SDL_GetAndroidJNIEnv();
    jobject activity = SDL_GetAndroidActivity();
    if (!env || !activity) return;
    jclass cls = (*env)->GetObjectClass(env,activity);
    jmethodID method = (*env)->GetMethodID(env,cls,"setNativeStatus","(Ljava/lang/String;)V");
    if (method) {
        jstring text = (*env)->NewStringUTF(env,message);
        (*env)->CallVoidMethod(env,activity,method,text);
        (*env)->DeleteLocalRef(env,text);
    }
    (*env)->DeleteLocalRef(env,cls); (*env)->DeleteLocalRef(env,activity);
}

bool plat_reserve_guest(uint64_t lo, uint64_t hi) {
    void *p = mmap((void *)(uintptr_t)lo, hi - lo, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED_NOREPLACE, -1, 0);
    if (p == MAP_FAILED) return false;
    if (p != (void *)(uintptr_t)lo) { munmap(p, hi - lo); return false; }
    return true;
}
bool plat_reset_guest(uint64_t lo, uint64_t hi) {
    return mmap((void *)(uintptr_t)lo, hi - lo, PROT_READ | PROT_WRITE,
                MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE | MAP_FIXED, -1, 0) == (void *)(uintptr_t)lo;
}
void plat_commit(uint64_t addr, uint64_t size) { (void)addr; (void)size; }
int plat_written_pages(uint64_t addr, uint64_t size, uint64_t *pages, int max, uint64_t *page) {
    (void)addr; (void)size; (void)pages; (void)max; (void)page;
    return -1;
}
int plat_protect(uint64_t addr, uint64_t size, int prot) {
    int p = prot == PLAT_PROT_NONE ? PROT_NONE : prot == PLAT_PROT_READ ? PROT_READ : PROT_READ | PROT_WRITE;
    return mprotect((void *)(uintptr_t)addr, size, p);
}
uint64_t plat_now_ns(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (uint64_t)t.tv_sec * 1000000000ull + t.tv_nsec;
}
void plat_sleep_until_ns(uint64_t ns) {
    struct timespec t = {.tv_sec = ns / 1000000000ull, .tv_nsec = ns % 1000000000ull};
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &t, NULL) == EINTR) {}
}
void plat_thread_realtime(uint64_t period_ns) { (void)period_ns; }  // Android owns thread scheduling policy.
bool plat_exe_path(char *buf, size_t size) {
    Dl_info info = {0};
    if (!dladdr((void *)plat_exe_path, &info) || !info.dli_fname) return false;
    return snprintf(buf, size, "%s", info.dli_fname) < (int)size;
}
void plat_exec(char *const argv[]) { (void)argv; errno = ENOTSUP; }
void plat_init(void) {
    const char *external = SDL_GetAndroidExternalStoragePath();
    const char *internal = SDL_GetAndroidInternalStoragePath();
    if (!external || !internal) { fprintf(stderr, "Android storage unavailable\n"); abort(); }
    setenv("LARECOMP_DATA_ROOT", external, 1);
    setenv("LARECOMP_UNIT_HEAP_SCALE", "1", 0);  // The vanilla game's pool sizes fit an 8 GB handheld.
    // SDL's working directory is app_process's, not the app data directory.
    chdir(external);
    mkdir(external, 0755);
    snprintf(log_path, sizeof log_path, "%s/lasrecomp.log", external);
    if (freopen(log_path, "w", stderr)) dup2(STDERR_FILENO, STDOUT_FILENO);
    setvbuf(stderr, NULL, _IOLBF, 0);
    FILE *debug = fopen("android-debug.env","r");
    if (debug) {
        char line[2048], name[128], value[1900];
        while (fgets(line,sizeof line,debug))
            if (sscanf(line,"%127[^=]=%1899[^\r\n]",name,value) == 2 && !strncmp(name,"LARECOMP_",9)) setenv(name,value,1);
        fclose(debug);
    }
    char library[1200], own[1200];
    snprintf(library, sizeof library, "%s/lasgame.so", internal);
    if (access(library, R_OK) != 0 && plat_exe_path(own, sizeof own)) {
        char *slash = strrchr(own, '/');
        if (slash) *slash = 0;
        snprintf(library, sizeof library, "%s/liblasgame.so", own);
    }
    setenv("LARECOMP_GAME_LIB", library, 1);
    fprintf(stderr, "[android] native ARM64 runtime; game preparation stays on PC\n");
}
const char *plat_symbol(uint64_t pc, uint64_t *offset) {
    Dl_info info = {0};
    if (!dladdr((void *)(uintptr_t)pc, &info) || !info.dli_sname) return NULL;
    if (offset) *offset = pc - (uint64_t)(uintptr_t)info.dli_saddr;
    return info.dli_sname;
}
static _Unwind_Reason_Code unwind_line(struct _Unwind_Context *ctx, void *arg) {
    int *count = arg;
    if ((*count)++ >= 48) return _URC_END_OF_STACK;
    uint64_t pc = _Unwind_GetIP(ctx), offset = 0;
    const char *name = plat_symbol(pc, &offset);
    fprintf(stderr, "  #%d %llx %s+%llx\n", *count, (unsigned long long)pc,
            name ? name : "?", (unsigned long long)offset);
    return _URC_NO_REASON;
}
void plat_print_backtrace(void) { int count = 0; _Unwind_Backtrace(unwind_line, &count); }
void plat_fatal_notice(void) {
    fflush(stderr);
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "LAS Recomp", "El juego se detuvo. Revisa el registro desde la pantalla inicial.", NULL);
}
static void crash_handler(int sig, siginfo_t *si, void *context) {
    ucontext_t *uc = context;
    uint64_t fault = (uint64_t)(uintptr_t)si->si_addr;
    uint64_t pc = uc->uc_mcontext.pc, lr = uc->uc_mcontext.regs[30];
    if (rt_fault_watch(fault, pc)) return;
    char message[32];
    snprintf(message, sizeof message, "signal %d", sig);
    rt_fault_report(message, fault, pc, lr);
}
void plat_crash_handler_install(void) {
    stack_t stack = {.ss_sp = malloc(1 << 20), .ss_size = 1 << 20};
    sigaltstack(&stack, NULL);
    struct sigaction sa = {.sa_sigaction = crash_handler, .sa_flags = SA_SIGINFO | SA_ONSTACK};
    sigemptyset(&sa.sa_mask);
    sigaction(SIGSEGV, &sa, NULL); sigaction(SIGBUS, &sa, NULL); sigaction(SIGILL, &sa, NULL);
    sigaction(SIGFPE, &sa, NULL);
}
PlatProc plat_spawn(const char *const argv[], const char *log, bool append) {
    (void)argv; (void)log; (void)append;
    errno = ENOTSUP;
    return 0;  // Android cannot execute the desktop Python/compiler helpers.
}
void plat_proc_kill(PlatProc proc) { (void)proc; }
int plat_proc_wait(PlatProc proc, bool block) { (void)proc; (void)block; return 255; }
static int remove_entry(const char *path, const struct stat *st, int kind, struct FTW *tree) {
    (void)st; (void)kind; (void)tree;
    return remove(path);
}
bool plat_remove_tree(const char *dir) { return nftw(dir, remove_entry, 16, FTW_DEPTH | FTW_PHYS) == 0; }
void plat_terminate(void) { _exit(0); }  // GameActivity runs in its own :game process.
