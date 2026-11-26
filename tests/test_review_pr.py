from __future__ import annotations

import os
import pty
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import ROOT_DIR, make_executable

PR_URL = "https://github.com/example-org/example-project/pull/42"


@pytest.mark.parametrize(
    ("relative_path", "remote_url", "pr_url", "suffix", "ssh_over_https"),
    [
        (
            "example-project",
            "https://github.com/example-org/example-project.git",
            PR_URL,
            "/?tab=files",
            False,
        ),
        (
            "example-org/example-project",
            "git@github.com:Example-Org/Example-Project.git",
            "https://github.com/Example-Org/Example-Project/pull/42",
            "/commits",
            False,
        ),
        (
            "Example-Project",
            "git@github.com:example-org/example-project.git",
            PR_URL,
            "/files?diff=split#diff-example",
            True,
        ),
    ],
)
@pytest.mark.parametrize("agent", ["codex", "claude"])
def test_review_starts_at_fetched_pr_head(
    temp_home: Path,
    fake_bin: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    remote_url: str,
    pr_url: str,
    suffix: str,
    ssh_over_https: bool,
    agent: str,
) -> None:
    zsh = shutil.which("zsh")
    git_binary = shutil.which("git")
    if not zsh or not git_binary or not shutil.which("openssl"):
        pytest.skip("zsh, git, and openssl are required")

    def git(repo: Path, *args: str) -> str:
        return subprocess.check_output([git_binary, *args], cwd=repo, text=True).strip()

    def commit(repo: Path, message: str) -> None:
        git(
            repo,
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            message,
        )

    origin = temp_home / "origin"
    origin.mkdir()
    git(origin, "init", "-qb", "main")
    commit(origin, "base")
    base = git(origin, "rev-parse", "HEAD")

    code_root = temp_home / "source trees"
    checkout = code_root / relative_path
    checkout.parent.mkdir(parents=True)
    git(temp_home, "clone", "-q", str(origin), str(checkout))
    git(
        checkout,
        "remote",
        "set-url",
        "origin",
        "https://github.com/another-org/example-project.git",
    )
    git(checkout, "remote", "add", "upstream", remote_url)
    if ssh_over_https:
        git(
            checkout,
            "config",
            "url.ssh://git@ssh.github.com:443/.insteadOf",
            "git@github.com:",
        )
        assert git(checkout, "remote", "get-url", "upstream") == (
            "ssh://git@ssh.github.com:443/example-org/example-project.git"
        )
    (checkout / "local.txt").write_text("local changes\n")
    if checkout.parent != code_root:
        wrong_checkout = code_root / "example-project"
        git(code_root, "clone", "-q", str(origin), str(wrong_checkout))
        git(
            wrong_checkout,
            "remote",
            "set-url",
            "origin",
            "https://github.com/another-org/example-project.git",
        )

    git(origin, "switch", "-q", "--detach")
    commit(origin, "PR head")
    head = git(origin, "rev-parse", "HEAD")
    git(origin, "update-ref", "refs/pull/42/head", head)
    monkeypatch.setenv("AGENT_REVIEW_CODE_ROOT", str(code_root))
    monkeypatch.setenv("REAL_GIT", git_binary)
    monkeypatch.setenv("ORIGIN", str(origin))
    monkeypatch.setenv("REMOTE_URL", remote_url)
    monkeypatch.setenv("WORKTREE", str(temp_home / "review tree"))

    make_executable(
        fake_bin / "git",
        """
        #!/bin/sh
        if [ "${3-}" = fetch ]; then
          [ "$8" = upstream ] || exit 97
          exec "$REAL_GIT" -c "url.$ORIGIN.insteadOf=$REMOTE_URL" "$@"
        fi
        exec "$REAL_GIT" "$@"
        """,
    )
    make_executable(
        fake_bin / "wt",
        """
        #!/bin/sh
        set -eu
        [ "$1" != config ] || exit 0
        [ "$5" = switch ] && [ "$6" = --create ] && [ "$8" = --cd ]
        git worktree add -qb "$9" "$WORKTREE" "${7#--base=}"
        printf '%s\n' "$WORKTREE" > "$WORKTRUNK_DIRECTIVE_CD_FILE"
        """,
    )
    (fake_bin / "wt-agent-switch").symlink_to(ROOT_DIR / ".local/bin/wt-agent-switch")
    make_executable(
        fake_bin / "codex", '#!/bin/sh\n[ "$1" = completion ] && exit 0\nexit 98\n'
    )
    for launcher in ("codex-paste-draft", "claude"):
        make_executable(
            fake_bin / launcher,
            """
            #!/bin/sh
            printf '%s\n' "${0##*/}" "$PWD" "$#" "$@" > "$HOME/launcher.log"
            exit 7
            """,
        )

    options = ["--claude"] if agent == "claude" else []
    master, terminal = pty.openpty()
    try:
        result = subprocess.run(
            [
                zsh,
                "-fc",
                'source "$1"; shift; review-pr "$@"; rc=$?; pwd > "$HOME/end-cwd"; exit $rc',
                "zsh",
                str(ROOT_DIR / ".zshrc"),
                *options,
                pr_url + suffix,
            ],
            check=False,
            cwd=temp_home,
            stdin=terminal,
            stdout=terminal,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
    finally:
        os.close(terminal)
        os.close(master)

    worktree = temp_home / "review tree"
    assert result.returncode == 7, result.stderr
    expected_launcher = "claude" if agent == "claude" else "codex-paste-draft"
    prefill = ["--prefill"] if agent == "claude" else []
    assert (temp_home / "launcher.log").read_text().splitlines() == [
        expected_launcher,
        str(worktree.resolve()),
        str(len(prefill) + 1),
        *prefill,
        f"This worktree is at the head of {pr_url}.",
        "",
        "Explain and review the PR.",
    ]
    assert (temp_home / "end-cwd").read_text().strip() == str(worktree.resolve())
    assert git(worktree, "rev-parse", "HEAD") == head
    assert re.fullmatch(
        r"review-42-[0-9a-f]{12}", git(worktree, "branch", "--show-current")
    )
    assert git(checkout, "rev-parse", "HEAD") == base
    assert git(checkout, "status", "--porcelain") == "?? local.txt"
    assert git(checkout, "for-each-ref", "refs/codex/reviews/") == ""
