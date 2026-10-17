"""Build the Android app locally. --personal includes the user's recompiled game: never publish it."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from prepare_public import prepare

ROOT = Path(__file__).resolve().parents[2]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--personal", action="store_true")
    p.add_argument("--package-only", action="store_true")
    p.add_argument("--gradle", type=Path)
    p.add_argument("--sdk", type=Path)
    p.add_argument("--java-home", type=Path)
    args = p.parse_args()
    prepare()
    if args.personal and not args.package_only:
        from prepare_code import prepare as prepare_code
        prepare_code()
    sdk = args.sdk or Path(os.environ.get("ANDROID_HOME", str(Path.home() / "AppData/Local/Android/Sdk")))
    cfg = json.loads((ROOT / "android/port.json").read_text())
    ndk = sdk / "ndk" / cfg["ndk_version"]
    bins = sorted((sdk / "cmake").glob("*/bin"))
    suffix = ".exe" if os.name == "nt" else ""
    cmake = Path(shutil.which("cmake") or str(bins[-1] / ("cmake" + suffix)))
    ninja = Path(shutil.which("ninja") or str(bins[-1] / ("ninja" + suffix)))
    build = ROOT / "build/android/runtime"
    if not args.package_only:
        subprocess.run([str(cmake), "-S", str(ROOT / "android/runtime"), "-B", str(build), "-G", "Ninja",
            "-DCMAKE_MAKE_PROGRAM=" + str(ninja), "-DCMAKE_TOOLCHAIN_FILE=" + str(ndk / "build/cmake/android.toolchain.cmake"),
            "-DANDROID_ABI=arm64-v8a", "-DANDROID_PLATFORM=android-33", "-DANDROID_STL=c++_shared",
            "-DCMAKE_BUILD_TYPE=Release", "-DLAS_BUILD_GAME=" + ("ON" if args.personal else "OFF")], check=True)
        subprocess.run([str(cmake), "--build", str(build), "--parallel", "8"], check=True)
    stage = ROOT / "build/android/apk-libs/arm64-v8a"
    stage.mkdir(parents=True, exist_ok=True)
    # This dedicated stage must not retain game code from a previous personal build.
    for lib in stage.glob("*.so"):
        lib.unlink()
    libraries = [build / "libmain.so", *sorted((ROOT / "build/android/deps/lib").glob("*.so")),
        ROOT / "build/android/sdl/aar/prefab/modules/SDL3-shared/libs/android.arm64-v8a/libSDL3.so"]
    if args.personal:
        libraries.append(build / "liblasgame.so")
    for lib in libraries:
        if not lib.is_file():
            p.error("Missing native library: " + str(lib))
        shutil.copy2(lib, stage / lib.name)
    assets = ROOT / "build/android/apk-assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(ROOT / "third_party/fonts/Baloo2/Baloo2-SemiBold.ttf", assets / "Baloo2-SemiBold.ttf")
    shutil.copy2(ROOT / "third_party/fonts/Baloo2/OFL.txt", assets / "Baloo2-OFL.txt")
    for font in (ROOT / "build/android/public/fonts").iterdir():
        shutil.copy2(font, assets / font.name)
    for lib in (ROOT / "build/android/deps").glob("*-LICENSE.txt"):
        shutil.copy2(lib, assets / lib.name)
    shutil.copy2(ROOT / "build/android/sdl/aar/META-INF/LICENSE.txt", assets / "SDL-LICENSE.txt")
    project = ROOT / "android/app"
    (project / "local.properties").write_text("sdk.dir=" + sdk.resolve().as_posix() + "\n")
    env = os.environ.copy()
    if args.java_home:
        env["JAVA_HOME"] = str(args.java_home)
        env["PATH"] = str(args.java_home / "bin") + os.pathsep + env["PATH"]
    gradle = args.gradle or shutil.which("gradle")
    if not gradle:
        candidates = sorted((Path.home() / ".gradle/wrapper/dists/gradle-9.3.0-bin").glob("*/gradle-*/bin/gradle.bat"))
        if candidates:
            gradle = candidates[-1]
    if not gradle:
        p.error("Pass --gradle with Gradle 9.3 or later")
    subprocess.run([str(gradle), "--no-daemon", "assembleDebug"], cwd=project, env=env, check=True)
    output = ROOT / "build/android/output"
    output.mkdir(exist_ok=True)
    name = "LASRecomp-Android-personal.apk" if args.personal else "LASRecomp-Android-runtime.apk"
    shutil.copy2(project / "app/build/outputs/apk/debug/app-debug.apk", output / name)
    report = {"apk": str(output / name), "personal_game_code_included": args.personal,
        "game_assets_included": False, "gameplay_verified": False, "abi": "arm64-v8a"}
    (output / "build-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
