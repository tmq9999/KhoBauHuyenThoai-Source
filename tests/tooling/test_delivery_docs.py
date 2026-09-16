from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "tools/ci/check_delivery_docs.py"


def git(repo, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                           "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
                           "-c", "core.hooksPath=" + str(repo / "disabled-hooks"), *args],
                          cwd=repo, check=check, capture_output=True, text=True, timeout=10)


def commit(repo, names, message="deliver", *, empty=False):
    for name in names:
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((path.read_text() if path.exists() else "") + message + "\n", encoding="utf-8")
    if names:
        git(repo, "add", "--", *names)
    git(repo, "commit", *( ["--allow-empty"] if empty else []), "-m", message)
    return git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "work")
    base = commit(tmp_path, ["README.md", "CHANGELOG.md"], "baseline")
    return tmp_path, base


def run_check(repo, base, head="HEAD", baseline=None):
    assert ENTRY.is_file(), "M0.2 delivery-docs checker is missing"
    args = [sys.executable, str(ENTRY), "--repo", str(repo), "--base=" + base, "--head=" + head]
    if baseline:
        args += ["--baseline", baseline]
    return subprocess.run(args, capture_output=True, text=True, timeout=15)


def test_each_delivery_commit_requires_both_docs_not_just_range(repo):
    directory, base = repo
    first = commit(directory, ["code.py"], "missing docs")
    commit(directory, ["code.py", "README.md", "CHANGELOG.md"], "later docs")
    result = run_check(directory, base)
    assert result.returncode == 1
    assert first[:12] in result.stdout
    assert "README.md" in result.stdout and "CHANGELOG.md" in result.stdout


@pytest.mark.parametrize("docs", [["README.md"], ["CHANGELOG.md"], []])
def test_one_or_both_missing_docs_fails(repo, docs):
    directory, base = repo
    commit(directory, ["code.py", *docs])
    assert run_check(directory, base).returncode == 1


def test_complete_docs_per_commit_passes_without_changing_worktree(repo):
    directory, base = repo
    commit(directory, ["a.py", "README.md", "CHANGELOG.md"], "first")
    commit(directory, ["b.py", "README.md", "CHANGELOG.md"], "second")
    before = git(directory, "status", "--porcelain=v1").stdout
    result = run_check(directory, base)
    assert result.returncode == 0, result.stderr
    assert "commits=2" in result.stdout
    assert git(directory, "status", "--porcelain=v1").stdout == before


def test_empty_range_passes(repo):
    directory, base = repo
    assert run_check(directory, base, base).returncode == 0


@pytest.mark.parametrize("bad_base", ["not-a-revision", "--all", "f" * 40])
def test_invalid_sha_is_error_not_empty_success(repo, bad_base):
    directory, _ = repo
    result = run_check(directory, bad_base)
    assert result.returncode == 2
    assert "INVALID_REVISION" in result.stderr


def test_historical_baseline_excludes_earlier_commits(repo):
    directory, original = repo
    old = commit(directory, ["old.py"], "legacy")
    baseline = commit(directory, ["README.md", "CHANGELOG.md"], "policy")
    commit(directory, ["new.py", "README.md", "CHANGELOG.md"], "new work")
    result = run_check(directory, original, baseline=baseline)
    assert result.returncode == 0, result.stderr
    assert old[:12] not in result.stdout
    assert "commits=1" in result.stdout


def test_diverged_range_is_rejected(repo):
    directory, base = repo
    git(directory, "checkout", "-b", "side")
    side = commit(directory, ["side.py", "README.md", "CHANGELOG.md"], "side")
    git(directory, "checkout", "work")
    commit(directory, ["main.py", "README.md", "CHANGELOG.md"], "work")
    result = run_check(directory, side)
    assert result.returncode == 2
    assert "NON_ANCESTOR_RANGE" in result.stderr


def test_merge_commit_cannot_hide_bad_side_branch_commit(repo):
    directory, base = repo
    git(directory, "checkout", "-b", "side")
    bad = commit(directory, ["side.py"], "undocumented")
    git(directory, "checkout", "work")
    commit(directory, ["README.md", "CHANGELOG.md", "main.py"], "documented")
    git(directory, "merge", "--no-ff", "side", "-m", "merge side")
    result = run_check(directory, base)
    assert result.returncode == 1
    assert bad[:12] in result.stdout


def test_deleting_both_docs_cannot_satisfy_delivery_policy(repo):
    directory, base = repo
    git(directory, "rm", "README.md", "CHANGELOG.md")
    commit(directory, [], "remove docs", empty=True)
    result = run_check(directory, base)
    assert result.returncode == 1


def test_frozen_policy_baseline_must_be_ancestor_of_head(repo):
    directory, base = repo
    result = run_check(directory, base, baseline="a" * 40)
    assert result.returncode == 2
