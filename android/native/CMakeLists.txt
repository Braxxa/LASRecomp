cmake_minimum_required(VERSION 3.22)
project(LASRecompAndroidCore LANGUAGES C)

if(NOT ANDROID OR NOT ANDROID_ABI STREQUAL "arm64-v8a")
    message(FATAL_ERROR "Use the Android NDK toolchain with ANDROID_ABI=arm64-v8a")
endif()

get_filename_component(LAS_ROOT "${CMAKE_CURRENT_LIST_DIR}/../.." ABSOLUTE)

# This is an actual cross-compile of the shared core, not the complete runtime.
# SDL, FFmpeg, Vulkan, the Android host layer and the application are later stages.
set(CORE_SOURCES
    runtime/loader.c
    runtime/kernel.c
    runtime/dispatch.c
    runtime/ipc.c
    runtime/gamelib.c
    runtime/fnprof.c
    runtime/rando.c
    runtime/romfs_build.c
    runtime/services/acc.c
    runtime/services/am.c
    runtime/services/fs.c
    runtime/services/hid_set.c
    runtime/services/misc.c
    runtime/services/time.c
    runtime/nvn/astc.c
    runtime/nvn/cmdbuf.c
    runtime/nvn/formats.c
    runtime/nvn/objects.c
    runtime/nvn/output_scale.c
    runtime/nvn/tegra.c
    runtime/nvn/texpatch.c
    runtime/nvn/maxwell/translate.c
)
list(TRANSFORM CORE_SOURCES PREPEND "${LAS_ROOT}/")
add_library(lasrecomp_android_core STATIC ${CORE_SOURCES})
target_include_directories(lasrecomp_android_core PRIVATE "${LAS_ROOT}/runtime")
target_compile_features(lasrecomp_android_core PRIVATE c_std_11)
target_compile_options(lasrecomp_android_core PRIVATE
    -O2 -fno-strict-aliasing -Wall -Wno-format -Wno-unused-function)
set_target_properties(lasrecomp_android_core PROPERTIES POSITION_INDEPENDENT_CODE ON)
