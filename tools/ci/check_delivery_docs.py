"""Check README/CHANGELOG changes per delivery commit, never mutate Git state."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys


REQUIRED = frozenset({"README.md", "CHANGELOG.md"})


class PolicyError(ValueError):
    pass


def _git(repo: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=30)
    if result.returncode not in allowed:
        raise PolicyError("GIT_COMMAND_FAILED")
    return result


def _revision(repo: Path, ref: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{7,64}|HEAD", ref):
        raise PolicyError("INVALID_REVISION")
    result = _git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}", allowed=(0, 128))
    if result.returncode != 0:
        raise PolicyError("INVALID_REVISION")
    return result.stdout.strip()


def _ancestor(repo: Path, before: str, after: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", before, after, allowed=(0, 1)).returncode == 0


def check(repo: Path, base: str, head: str, baseline: str | None = None) -> dict:
    base, head = _revision(repo, base), _revision(repo, head)
    if not _ancestor(repo, base, head):
        raise PolicyError("NON_ANCESTOR_RANGE")
    if baseline:
        baseline = _revision(repo, baseline)
        if not _ancestor(repo, baseline, head):
            raise PolicyError("BASELINE_NOT_ANCESTOR")
        if _ancestor(repo, base, baseline):
            base = baseline
        elif not _ancestor(repo, baseline, base):
            raise PolicyError("BASELINE_DIVERGED")
    commits = _git(repo, "rev-list", "--reverse", "--no-merges", base + ".." + head).stdout.splitlines()
    failures = []
    for commit in commits:
        changed = set(_git(repo, "diff-tree", "--root", "--no-commit-id", "--no-renames", "--name-only",
                           "--diff-filter=AM", "-r", "-z", commit, "--").stdout.rstrip("\0").split("\0"))
        missing = sorted(REQUIRED - changed)
        if missing:
            failures.append({"commit": commit, "missing": missing})
    return {"commits": len(commits), "failures": failures}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--baseline")
    args = parser.parse_args(argv)
    try:
        report = check(args.repo.resolve(strict=True), args.base, args.head, args.baseline)
        for failure in report["failures"]:
            print(f"{failure['commit'][:12]} missing: {', '.join(failure['missing'])}")
        print(f"DELIVERY_DOCS {'FAIL' if report['failures'] else 'PASS'} commits={report['commits']}")
        return 1 if report["failures"] else 0
    except PolicyError as exc:
        print(str(exc), file=sys.stderr)
    except (OSError, subprocess.TimeoutExpired):
        print("GIT_IO_ERROR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
