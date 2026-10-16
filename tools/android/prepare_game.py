"""Prepare a user's local base NSP for recompilation. No keys or game data are published."""
import argparse
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def partitions(path):
    with path.open("rb") as source:
        magic, count, names_size, _ = struct.unpack("<4sIII", source.read(16))
        if magic != b"PFS0" or count > 10000 or names_size > 16 * 1024 * 1024:
            raise ValueError("Not a supported PFS0/NSP container")
        table = source.read(count * 24)
        names = source.read(names_size)
        start = 16 + count * 24 + names_size
        result = []
        for i in range(count):
            offset, size, name_offset, _ = struct.unpack_from("<QQII", table, i * 24)
            if name_offset >= len(names) or start + offset + size > path.stat().st_size:
                raise ValueError("Invalid NSP entry bounds")
            name = names[name_offset:].split(b"\0", 1)[0].decode("utf-8")
            result.append((name, start + offset, size))
        return result


def extract_entry(source, entry, target):
    _, offset, size = entry
    if target.is_file() and target.stat().st_size == size:
        return
    temp = target.with_suffix(target.suffix + ".part")
    with source.open("rb") as src, temp.open("wb") as dst:
        src.seek(offset)
        left = size
        last = -1
        while left:
            data = src.read(min(left, 8 * 1024 * 1024))
            if not data:
                raise ValueError("Unexpected end of NSP")
            dst.write(data)
            left -= len(data)
            step = int((size - left) / size * 10)
            if step != last:
                print(f"Extracting container: {step * 10}%", flush=True)
                last = step
    temp.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--keys", type=Path)
    parser.add_argument("--nstool", type=Path, default=ROOT / "build/tools/nstool/nstool.exe")
    args = parser.parse_args()
    source = args.source.resolve()
    choices = [source] if source.is_file() else list(source.rglob("*.nsp"))
    if len(choices) != 1:
        parser.error("Provide a folder containing exactly one base NSP")
    nsp = choices[0]
    key_folder = (args.keys or (source if source.is_dir() else source.parent)).resolve()
    if not (key_folder / "prod.keys").is_file():
        parser.error("prod.keys missing from the selected local key folder")
    out = ROOT / "extracted"
    if (out / "exefs/main").is_file() and (out / "exefs/sdk").is_file() and (out / "romfs/region_common").is_dir():
        print("Game files already prepared locally.")
        return 0
    private = ROOT / "input/private"
    private.mkdir(parents=True, exist_ok=True)
    entries = partitions(nsp)
    ncas = [entry for entry in entries if entry[0].endswith(".nca")]
    if not ncas:
        parser.error("No NCA content in NSP")
    program = max(ncas, key=lambda entry: entry[2])
    required = program[2] * 2 + 2 * 1024**3
    if shutil.disk_usage(ROOT).free < required:
        parser.error("Insufficient free disk space for local extraction")
    print(f"Container entries: {len(entries)}; largest content: {program[2] // 1024**2} MiB", flush=True)
    extract_entry(nsp, program, private / "program.nca")
    command = [str(args.nstool.resolve()), "-k", str(key_folder / "prod.keys")]
    tickets = [entry for entry in entries if entry[0].endswith(".tik")]
    if len(tickets) == 1:
        extract_entry(nsp, tickets[0], private / "title.tik")
        command += ["--tik", str(private / "title.tik")]
    command += ["--part0", str(out / "exefs"), "--part1", str(out / "romfs"), str(private / "program.nca")]
    print("Extracting local executable and filesystem partitions...", flush=True)
    # Run beside the user's title.keys; never copy it into source or print its contents.
    result = subprocess.run(command, cwd=key_folder, capture_output=True)
    (private / "extract.log").write_bytes(result.stdout + result.stderr)
    expected = [out / "exefs/main", out / "exefs/sdk", out / "exefs/main.npdm", out / "romfs/region_common"]
    if result.returncode or not all(p.exists() for p in expected):
        print("Extraction incomplete. Inspect the private local extraction log.", file=sys.stderr)
        return 1
    print("Base game extracted locally: exefs + romfs. No keys copied to the project.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
