from __future__ import annotations

import os
from pathlib import Path

from dotfiles_install import shell_setup, state


def test_removes_broken_legacy_stow_symlink(temp_home: Path, monkeypatch) -> None:
    physical_home = temp_home.resolve()
    state.DOTFILES_DIR = physical_home / ".dotfiles"
    monkeypatch.setattr(
        shell_setup,
        "LEGACY_STOW_PATHS",
        [".agents/skills/gh-fix-ci"],
    )

    legacy_path = physical_home / ".agents/skills/gh-fix-ci"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.symlink_to("../../.dotfiles/.agents/skills/gh-fix-ci")

    shell_setup.remove_legacy_stow_targets()

    assert not legacy_path.exists()
    assert not legacy_path.is_symlink()


def test_removes_broken_stow_symlink_tree(temp_home: Path, monkeypatch) -> None:
    physical_home = temp_home.resolve()
    state.DOTFILES_DIR = physical_home / ".dotfiles"
    monkeypatch.setattr(
        shell_setup,
        "LEGACY_STOW_PATHS",
        [".codex/skills/playwright"],
    )

    legacy_dir = physical_home / ".codex/skills/playwright"
    for relative in ("SKILL.md", "scripts/playwright_cli.sh"):
        link = legacy_dir / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        target = state.DOTFILES_DIR / ".codex/skills/playwright" / relative
        link.symlink_to(os.path.relpath(target, link.parent))

    shell_setup.remove_legacy_stow_targets()

    assert not legacy_dir.exists()
    assert not legacy_dir.is_symlink()


def test_preserves_non_repo_entries_in_legacy_directory(temp_home: Path, monkeypatch) -> None:
    physical_home = temp_home.resolve()
    state.DOTFILES_DIR = physical_home / ".dotfiles"
    monkeypatch.setattr(
        shell_setup,
        "LEGACY_STOW_PATHS",
        [".agents/skills/gitlab"],
    )

    legacy_dir = physical_home / ".agents/skills/gitlab"
    legacy_dir.mkdir(parents=True)

    regular_file = legacy_dir / "notes.txt"
    regular_file.write_text("keep me")

    outside_target = physical_home / "outside-target.md"
    outside_target.write_text("outside")
    outside_link = legacy_dir / "outside.md"
    outside_link.symlink_to(os.path.relpath(outside_target, legacy_dir))

    repo_link = legacy_dir / "SKILL.md"
    repo_link.symlink_to(
        os.path.relpath(state.DOTFILES_DIR / ".agents/skills/gitlab/SKILL.md", legacy_dir)
    )

    shell_setup.remove_legacy_stow_targets()

    assert regular_file.exists()
    assert outside_link.is_symlink()
    assert not repo_link.exists()
    assert legacy_dir.is_dir()
