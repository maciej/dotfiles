from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from helpers import ROOT_DIR, make_executable

SCRIPT = ROOT_DIR / ".local/bin/wt-agent-switch"
CONFIG_SETS = [
    "--config-set",
    'worktree-path="~/.worktrees/{{ repo }}.{{ branch | sanitize }}"',
    "--config-set",
    'pre-start.worktreeinclude="wt step copy-ignored --require-include"',
]


@pytest.fixture
def wt_log(fake_bin: Path, temp_home: Path) -> Path:
    log = temp_home / "wt.log"
    make_executable(
        fake_bin / "wt",
        f"""\
        #!/usr/bin/env bash
        printf '%s\\n' "$@" >"{log}"
        """,
    )
    return log


def run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(SCRIPT), *args],
        check=False,
        capture_output=True,
        text=True,
        cwd=cwd,
    )


@pytest.mark.parametrize(
    ("args", "base", "suffix"),
    [
        (["foo"], "@", "foo"),
        (["-b", "main"], "main", None),
        (["-bmain", "foo"], "main", "foo"),
        (["--base", "^", "foo"], "^", "foo"),
        (["--base=pr:12", "foo"], "pr:12", "foo"),
        (["foo", "-b", "develop"], "develop", "foo"),
        (["--base", "-"], "-", None),
        (["foo", "--", "-h", "--model", "x"], "@", "foo"),
        (["--", "foo"], "@", None),
    ],
)
def test_switch_arguments(
    wt_log: Path, args: list[str], base: str, suffix: str | None
) -> None:
    result = run("codex", *args)

    assert result.returncode == 0, result.stderr
    wt_args = wt_log.read_text().splitlines()
    assert wt_args[:-5] == CONFIG_SETS
    assert wt_args[-5:-1] == ["switch", "--create", f"--base={base}", "--cd"]
    if suffix is None:
        assert re.fullmatch(r"[0-9a-f]{12}", wt_args[-1])
    else:
        assert wt_args[-1] == suffix


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["foo", "bar"], "wt-codex: unexpected argument: bar (pass codex arguments after --)"),
        (["-x"], "wt-codex: unknown option: -x (see wt-codex --help)"),
        (["-"], "wt-codex: unknown option: - (see wt-codex --help)"),
        (["-b"], "wt-codex: option -b requires a value"),
        (["--base", "--", "foo"], "wt-codex: option --base requires a value"),
        (["--base=", "foo"], "wt-codex: base ref must not be empty"),
    ],
)
def test_rejects_bad_arguments(wt_log: Path, args: list[str], message: str) -> None:
    result = run("codex", *args)

    assert result.returncode == 2
    assert result.stderr.strip() == message
    assert not wt_log.exists()


def test_rejects_invalid_branch_name(wt_log: Path) -> None:
    result = run("codex", "bad..name")

    assert result.returncode != 0
    assert not wt_log.exists()


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_does_not_create_worktree(wt_log: Path, flag: str) -> None:
    result = run("claude", "-b", "main", flag)

    assert result.returncode == 0
    assert result.stdout.startswith(
        "Usage: wt-claude [-b|--base <ref>] [suffix] [-- claude arguments]\n"
    )
    assert "Arguments after -- are passed to claude." in result.stdout
    assert not wt_log.exists()


def test_complete_base_lists_shortcuts_and_branches(temp_home: Path) -> None:
    repo = temp_home / "repo"

    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    repo.mkdir()
    git("init", "-q", "-b", "main")
    git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--allow-empty", "-m", "root")
    git("branch", "develop")
    git("update-ref", "refs/remotes/origin/main", "HEAD")
    git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

    result = run("--complete-base", cwd=repo)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "^\tdefault branch",
        "@\tcurrent HEAD",
        "-\tprevious branch",
        "develop\tlocal branch",
        "main\tlocal branch",
        "origin/main\tremote branch",
    ]


def test_complete_base_outside_repo(temp_home: Path) -> None:
    result = run("--complete-base", cwd=temp_home)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "^\tdefault branch",
        "@\tcurrent HEAD",
        "-\tprevious branch",
    ]
