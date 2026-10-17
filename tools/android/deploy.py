"""Install a local APK and transfer personal game assets through the app's Android UID."""
import argparse
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "io.github.braxxa.lasrecomp"
DEST = "/sdcard/Android/data/" + PACKAGE + "/files/extracted"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--adb", type=Path, default=Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe")
    p.add_argument("--serial", required=True)
    p.add_argument("--apk", type=Path)
    p.add_argument("--assets", action="store_true")
    args = p.parse_args()
    adb = [str(args.adb), "-s", args.serial]
    if args.apk:
        subprocess.run([*adb, "install", "-r", str(args.apk.resolve())], check=True)
    if args.assets:
        for folder in ("exefs", "romfs"):
            if not (ROOT / "extracted" / folder).is_dir():
                p.error("Missing local game folder: extracted/" + folder)
        subprocess.run([*adb, "shell", "run-as", PACKAGE, "mkdir", "-p", DEST], check=True)
        subprocess.run([*adb, "shell", "run-as", PACKAGE, "touch", DEST + "/.importing"], check=True)
        # Rebuild the storage image from the imported files on the next boot.
        subprocess.run([*adb, "shell", "run-as", PACKAGE, "rm", "-f", DEST + "/romfs.bin"], check=True)
        # Some Android builds deny shell's access to Android/data. run-as uses only this
        # debuggable app's UID; streamed tar avoids keeping a second copy on the device.
        count = size = 0
        process = subprocess.Popen([*adb, "exec-in", "run-as", PACKAGE, "tar", "-xf", "-", "-C", DEST], stdin=subprocess.PIPE)
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.GNU_FORMAT) as archive:
                for folder in ("exefs", "romfs"):
                    source = ROOT / "extracted" / folder
                    for item in sorted(source.rglob("*")):
                        if not item.is_file() or item.is_symlink():
                            continue
                        archive.add(item, arcname=folder + "/" + item.relative_to(source).as_posix(), recursive=False)
                        count += 1
                        size += item.stat().st_size
                        if count % 500 == 0:
                            print(json.dumps({"files_sent": count, "MiB_sent": size >> 20}), flush=True)
        finally:
            process.stdin.close()
        if process.wait():
            raise RuntimeError("Android asset transfer failed")
        subprocess.run([*adb, "shell", "run-as", PACKAGE, "rm", DEST + "/.importing"], check=True)
        print(json.dumps({"files_sent": count, "bytes_sent": size, "destination": DEST}), flush=True)


if __name__ == "__main__":
    main()
