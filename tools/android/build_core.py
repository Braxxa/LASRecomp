"""Cross-compile the shared core for Android; this does not build an APK."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path)
    parser.add_argument("--cmake", type=Path)
    parser.add_argument("--ninja", type=Path)
    args = parser.parse_args()
    config = json.loads((ROOT / "android/port.json").read_text())
    build = ROOT / "build/android/core"
    build.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, text=True, capture_output=True)
    report = {
        "check": "android-core-cross-compile",
        "source_commit": revision.stdout.strip(),
        "working_tree_dirty": bool(dirty.stdout.strip()),
        "abi": config["abi"], "api": config["android_api"],
        "apk_built": False, "game_tested": False, "passed": False,
    }
    result_path = build / "result.json"
    result_path.write_text(json.dumps(report, indent=2) + "\n")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk and os.name == "nt":
        # Sandboxed shells may redirect LOCALAPPDATA; also check the real profile.
        for candidate in [Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk",
                          Path.home() / "AppData/Local/Android/Sdk"]:
            if candidate.is_dir():
                sdk = str(candidate)
                break
    ndk = args.ndk or os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT")
    if not ndk and sdk:
        ndk = Path(sdk) / "ndk" / config["ndk_version"]
    if not ndk or not (Path(ndk) / "build/cmake/android.toolchain.cmake").is_file():
        parser.error("NDK missing: pass --ndk or install ndk;" + config["ndk_version"])
    ndk = Path(ndk).resolve()
    cmake = args.cmake or shutil.which("cmake")
    ninja = args.ninja or shutil.which("ninja")
    if sdk and (not cmake or not ninja):
        candidates = sorted((Path(sdk) / "cmake").glob("*/bin"))
        suffix = ".exe" if os.name == "nt" else ""
        for candidate in reversed(candidates):
            cmake = cmake or (candidate / ("cmake" + suffix) if (candidate / ("cmake" + suffix)).is_file() else None)
            ninja = ninja or (candidate / ("ninja" + suffix) if (candidate / ("ninja" + suffix)).is_file() else None)
    if not cmake or not ninja:
        parser.error("CMake and Ninja are required (--cmake / --ninja)")
    commands = [
        [str(cmake), "-S", str(ROOT / "android/native"), "-B", str(build), "-G", "Ninja",
         "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
         "-DCMAKE_TOOLCHAIN_FILE=" + str(ndk / "build/cmake/android.toolchain.cmake"),
         "-DANDROID_ABI=" + config["abi"], "-DANDROID_PLATFORM=android-" + str(config["android_api"]),
         "-DCMAKE_BUILD_TYPE=Release"],
        [str(cmake), "--build", str(build), "--parallel", str(min(os.cpu_count() or 2, 8))],
    ]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode:
            return result.returncode
    report["passed"] = True
    result_path.write_text(json.dumps(report, indent=2) + "\n")
    print("Android ARM64 core compiled. No APK built; gameplay not tested.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
