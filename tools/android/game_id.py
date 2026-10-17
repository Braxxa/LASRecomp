"""Version the native game ABI identically on Windows and Linux."""
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "tools/gen.py", "tools/lifter.py", "tools/analyze.py", "tools/nso.py", "tools/passes.py",
    "tools/patches.py", "tools/simd_c.py", "tools/rando/patch_variants.json", "tools/gamelib_entry.c",
    "runtime/hle/hle_symbols.txt", "runtime/cpu.h", "runtime/simd.h", "runtime/simd_fp.h", "runtime/gamelib.h",
)


def game_id():
    digest = hashlib.sha256(b"android-arm64-api33-ndk28-asm-v1\n")
    for name in SOURCES:
        digest.update((ROOT / name).read_bytes().replace(b"\r\n", b"\n"))
    return "android-" + digest.hexdigest()[:16]


if __name__ == "__main__":
    print(game_id())
