"""Compile an isolated update when present, otherwise the current Android core."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    repo = ROOT
    report = ROOT / "build/android/upstream/latest.json"
    result = None
    if report.is_file():
        result = json.loads(report.read_text(encoding="utf-8"))
        if result["status"] == "prepared":
            repo = Path(result["candidate_directory"]).resolve()
            if not repo.is_relative_to((ROOT / "build/android/upstream").resolve()):
                raise RuntimeError("Candidate directory escaped the build folder")
        elif result["status"] != "unchanged":
            raise RuntimeError("Candidate is not ready: " + result["status"])
    code = subprocess.run([sys.executable, str(repo / "tools/android/build_core.py")], cwd=repo).returncode
    if result is not None:
        result["core_check_passed"] = code == 0
        # A successful core compile never promotes a version to playable or stable.
        report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main())
