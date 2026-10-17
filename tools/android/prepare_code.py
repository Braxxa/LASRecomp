"""Regenerate personal ARM64 sources when the game or generator ABI changes; never upload them."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from game_id import game_id

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "generated-android"


def fingerprint():
    modules = {}
    for name in ("main", "sdk"):
        source = ROOT / "extracted/exefs" / name
        with source.open("rb") as file:
            modules[name] = hashlib.file_digest(file,"sha256").hexdigest()
    return {"game_id": game_id(), "input_sha256": modules, "simd": "asm", "abi": "arm64-v8a"}


def prepare():
    expected = fingerprint()
    stamp = OUT / "generation.json"
    if stamp.is_file() and json.loads(stamp.read_text()) == expected and all((OUT / n).is_dir() for n in ("main","sdk")):
        print("Personal ARM64 generated sources match the current game and generator.",flush=True)
        return
    python = ROOT / ("tools/venv/Scripts/python.exe" if os.name == "nt" else "tools/venv/bin/python")
    if not python.is_file():
        python = Path(sys.executable)
    staging = OUT / ("staging-" + uuid.uuid4().hex)
    staging.mkdir(parents=True)
    commands = [
        [str(python), "tools/gen.py", "sdk", "extracted/exefs/sdk", "0x7004000000", str(staging/"sdk"), "--hle", "runtime/hle/hle_symbols.txt", "--simd", "asm"],
        [str(python), "tools/gen.py", "main", "extracted/exefs/main", "0x7000000000", str(staging/"main"), "--simd", "asm"],
    ]
    for command in commands:
        subprocess.run(command,cwd=ROOT,check=True)
    archive = OUT / ("previous-" + str(time.time_ns()))
    archive.mkdir()
    for name in ("main","sdk"):
        current = OUT/name
        replacement = staging/name
        destination = archive/name
        # Both sides of every directory move must resolve inside this ignored private output.
        for path in (current,replacement,destination):
            if not path.resolve().is_relative_to(OUT.resolve()):
                raise RuntimeError("Generated source path escapes private output")
        if current.exists():
            current.rename(destination)
        replacement.rename(current)
    stamp.write_text(json.dumps(expected,indent=2)+"\n")
    print("Personal ARM64 sources regenerated locally.",flush=True)


if __name__ == "__main__":
    prepare()
