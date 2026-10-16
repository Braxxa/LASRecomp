"""Inspect upstream or prepare an isolated update candidate; never update stable."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BOT = ["-c", "user.name=LASRecomp Android", "-c", "user.email=android-port@localhost"]


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", str(repo), *args], text=True,
                          encoding="utf-8", errors="replace", capture_output=True, check=check)


def config(repo):
    return json.loads((repo / "android/port.json").read_text(encoding="utf-8"))


def inspect(repo, upstream=None):
    cfg = config(repo)
    url = upstream or cfg["upstream_url"]
    ref = "refs/heads/" + cfg["upstream_branch"]
    lines = git(repo, "ls-remote", "--exit-code", url, ref).stdout.splitlines()
    if len(lines) != 1:
        raise RuntimeError("Upstream branch is missing or ambiguous")
    target = lines[0].split()[0]
    base = cfg["upstream_base"]
    return {
        "status": "unchanged" if target == base else "available",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": git(repo, "rev-parse", "HEAD").stdout.strip(),
        "upstream_base": base, "upstream_target": target,
        "upstream_url": url, "testing_branch": cfg["testing_branch"],
        "stable_changed": False, "game_tested": False,
    }


def prepare(repo, upstream=None):
    # A candidate is made only from committed source, so no edits can be lost or omitted.
    if git(repo, "status", "--porcelain").stdout.strip():
        raise RuntimeError("Commit or save working changes before preparing an update")
    result = inspect(repo, upstream)
    if result["status"] == "unchanged":
        return result
    cfg = config(repo)
    output = repo / "build/android/upstream"
    output.mkdir(parents=True, exist_ok=True)
    trial = Path(tempfile.mkdtemp(prefix="candidate-", dir=output))
    result["candidate_directory"] = str(trial)
    git(repo, "clone", "--no-hardlinks", "--no-checkout", str(repo), str(trial))
    git(trial, "switch", "-c", cfg["testing_branch"], result["source_commit"])
    git(trial, "fetch", "--no-tags", result["upstream_url"], "refs/heads/" + cfg["upstream_branch"])
    # Freeze what was inspected; a moving main must be inspected again on the next run.
    target = git(trial, "rev-parse", "FETCH_HEAD").stdout.strip()
    if target != result["upstream_target"]:
        result["status"] = "upstream-moved"
        return result
    if git(trial, "merge-base", "--is-ancestor", cfg["upstream_base"], target, check=False).returncode:
        result["status"] = "upstream-history-changed"
        return result
    result["upstream_commits"] = git(trial, "log", "--format=%h %s", cfg["upstream_base"] + ".." + target).stdout.splitlines()
    changed = git(trial, "diff", "--name-only", cfg["upstream_base"], target).stdout.splitlines()
    result["changed_files"] = changed
    result["regenerate_game_code"] = any(
        p.startswith("tools/") or p in {"Makefile", "runtime/cpu.h", "runtime/simd.h",
        "runtime/simd_fp.h", "runtime/gamelib.h", "runtime/hle/hle_symbols.txt"} for p in changed)
    merge = git(trial, *BOT, "merge", "--no-ff", "--no-commit", target, check=False)
    if merge.returncode:
        conflicts = git(trial, "diff", "--name-only", "--diff-filter=U").stdout.splitlines()
        result.update(status="conflict" if conflicts else "merge-failed",
                      conflicts=conflicts, details=merge.stdout + merge.stderr)
        return result
    merged_config = config(trial)
    # Preserve this port's upstream/branch policy even if upstream adds its own Android port.
    for key in ("upstream_url", "upstream_branch", "development_branch", "testing_branch", "stable_branch"):
        if merged_config[key] != cfg[key]:
            result["status"] = "port-policy-changed"
            return result
    merged_config["upstream_base"] = target
    (trial / "android/port.json").write_text(json.dumps(merged_config, indent=2) + "\n", encoding="utf-8")
    git(trial, "add", "android/port.json")
    git(trial, *BOT, "commit", "-m", "Merge LASRecomp upstream " + target[:12] + " for Android testing")
    result["candidate_commit"] = git(trial, "rev-parse", "HEAD").stdout.strip()
    bundle = trial.parent / (trial.name + ".bundle")
    git(trial, "bundle", "create", str(bundle), "refs/heads/" + cfg["testing_branch"])
    result.update(status="prepared", candidate_bundle=str(bundle),
                  next_step="Cross-compile this candidate, then test on the Retroid. Stable is untouched.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["check", "prepare"])
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--upstream", help="Override upstream for local fixture testing")
    args = parser.parse_args()
    repo = args.repo.resolve()
    report = repo / "build/android/upstream/latest.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = (inspect if args.action == "check" else prepare)(repo, args.upstream)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        details = getattr(error, "stderr", None) or str(error)
        result = {"status": "error", "details": details, "stable_changed": False}
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] in {"unchanged", "available", "prepared"} else 1


if __name__ == "__main__":
    sys.exit(main())
