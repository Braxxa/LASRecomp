#!/usr/bin/env bash
# Public dependencies only. Never reads the user's game, generated code, or keys.
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME}"
BASE="$PWD/build/android"
S="$BASE/deps-src"
W="$BASE/deps-work"
P="$BASE/deps"
mkdir -p "$S" "$W" "$P/include" "$P/lib"
JOBS=${JOBS:-4}
TC="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/bin"
CROSS=(-DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_HOME/build/cmake/android.toolchain.cmake"
       -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-33 -DANDROID_STL=c++_shared)

fetch() {
    if [[ ! -f "$S/$3" ]]; then curl --retry 3 -fL "$1" -o "$S/$3.part"; mv "$S/$3.part" "$S/$3"; fi
    echo "$2  $S/$3" | sha256sum --check --status
}
unpack() {
    # Fresh CI paths; reuse existing sources to support interrupted local builds.
    if [[ ! -d "$W/$2" ]]; then mkdir -p "$W/$2"; tar -xf "$S/$1" -C "$W/$2" --strip-components=1; fi
}

fetch https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz \
  8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e ffmpeg.tar.xz
fetch https://github.com/google/shaderc/archive/refs/tags/v2026.3.tar.gz \
  ee493ccf1b3038b4ef2fe024664c5eb2dc4bcc1f6b05b33e3909de0e19c81024 shaderc.tar.gz
fetch https://github.com/KhronosGroup/Vulkan-Headers/archive/refs/tags/vulkan-sdk-1.4.350.1.tar.gz \
  6d1bb65e49520344cc0a48af3dc02e993781efff14c7ebdcb8ae9fa23ddf7e83 vulkan.tar.gz
fetch https://github.com/GPUOpen-LibrariesAndSDKs/VulkanMemoryAllocator/archive/refs/tags/v3.3.0.tar.gz \
  c4f6bbe6b5a45c2eb610ca9d231158e313086d5b1a40c9922cb42b597419b14e vma.tar.gz

unpack vulkan.tar.gz vulkan
unpack vma.tar.gz vma
cp -R "$W/vulkan/include/vulkan" "$W/vulkan/include/vk_video" "$P/include/"
mkdir -p "$P/include/vma"
cp "$W/vma/include/vk_mem_alloc.h" "$P/include/vma/"

if [[ ! -f "$P/lib/libavcodec.so" ]]; then
    unpack ffmpeg.tar.xz ffmpeg
    (cd "$W/ffmpeg"
     ./configure --prefix="$P" --enable-cross-compile --target-os=android --arch=aarch64 \
       --cc="$TC/aarch64-linux-android33-clang" --cxx="$TC/aarch64-linux-android33-clang++" \
       --ar="$TC/llvm-ar" --nm="$TC/llvm-nm" --ranlib="$TC/llvm-ranlib" --strip="$TC/llvm-strip" \
       --enable-shared --disable-static --enable-pic --disable-autodetect --disable-programs --disable-doc \
       --disable-network --disable-avdevice --disable-avfilter --disable-swresample --disable-everything \
       --enable-protocol=file --enable-demuxer=matroska,mov --enable-decoder=vp9,vp8,vorbis,opus,h264,aac \
       --enable-parser=vp9,vp8,vorbis,opus,h264,aac
     make -j"$JOBS"
     make install)
fi
if grep -q 'GPL version 3\|--enable-gpl' "$P/lib/pkgconfig/libavcodec.pc"; then echo "FFmpeg must remain LGPL"; exit 1; fi

if [[ ! -f "$P/lib/libshaderc_shared.so" ]]; then
    unpack shaderc.tar.gz shaderc
    (cd "$W/shaderc"; python3 utils/git-sync-deps)
    cmake -S "$W/shaderc" -B "$W/shaderc/build-android" -G Ninja "${CROSS[@]}" \
      -DCMAKE_BUILD_TYPE=Release -DSHADERC_SKIP_TESTS=ON -DSHADERC_SKIP_EXAMPLES=ON \
      -DSHADERC_SKIP_COPYRIGHT_CHECK=ON -DSPIRV_SKIP_TESTS=ON -DSPIRV_SKIP_EXECUTABLES=ON \
      -DENABLE_GLSLANG_BINARIES=OFF -DSPIRV_TOOLS_BUILD_STATIC=ON -DBUILD_SHARED_LIBS=OFF
    cmake --build "$W/shaderc/build-android" --target shaderc_shared --parallel "$JOBS"
    mkdir -p "$P/include/shaderc"
    cp "$W/shaderc/libshaderc/include/shaderc/"*.h "$P/include/shaderc/"
    cp "$W/shaderc/build-android/libshaderc/libshaderc_shared.so" "$P/lib/"
fi
cp "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/libc++_shared.so" "$P/lib/"
cp "$W/ffmpeg/COPYING.LGPLv2.1" "$P/FFmpeg-LICENSE.txt"
cp "$W/shaderc/LICENSE" "$P/shaderc-LICENSE.txt"
printf '%s\n' "Android ARM64 dependencies built from pinned public sources."
