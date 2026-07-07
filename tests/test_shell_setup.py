from __future__ import annotations

from pathlib import Path

from dotfiles_install import state
from dotfiles_install import shell_setup


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
