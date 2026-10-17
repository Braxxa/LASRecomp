"""Fetch checksum-pinned SDL3 and DejaVu Sans from their official releases."""
import hashlib
import io
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def fetch(url, sha, path):
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError("Public asset checksum mismatch: " + path.name)
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        raise RuntimeError("Cached public asset checksum mismatch: " + path.name)
    return zipfile.ZipFile(path)


def prepare():
    base = ROOT / "build/android"
    with fetch("https://github.com/libsdl-org/SDL/releases/download/release-3.4.16/SDL3-devel-3.4.16-android.zip",
        "e1da8d9298471ea4ab8c6d48a804c0ac5415f35f30fcf7eba61aa7357e165765",base/"public/SDL3.zip") as archive:
        aar_name = next(n for n in archive.namelist() if n.endswith("SDL3-3.4.16.aar"))
        target = base / "sdl/SDL3-3.4.16.aar"
        target.parent.mkdir(parents=True, exist_ok=True)
        data = archive.read(aar_name)
        if not target.is_file() or target.read_bytes() != data:
            target.write_bytes(data)
        if not (base/"sdl/aar/classes.jar").is_file():
            with zipfile.ZipFile(io.BytesIO(data)) as aar:
                aar.extractall(base/"sdl/aar")
    with fetch("https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip",
        "7576310b219e04159d35ff61dd4a4ec4cdba4f35c00e002a136f00e96a908b0a",base/"public/DejaVu.zip") as archive:
        target = base / "public/fonts"
        target.mkdir(exist_ok=True)
        for suffix,name in [("/ttf/DejaVuSans.ttf","DejaVuSans.ttf"),("/LICENSE","DejaVu-LICENSE.txt")]:
            item = next(n for n in archive.namelist() if n.endswith(suffix))
            (target/name).write_bytes(archive.read(item))


if __name__ == "__main__":
    prepare()
    print("Pinned public Android assets ready.")
