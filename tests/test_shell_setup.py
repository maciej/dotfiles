from __future__ import annotations

import os
from pathlib import Path

import pytest

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


def test_precreates_missing_stow_directory(temp_home: Path, monkeypatch) -> None:
    physical_home = temp_home.resolve()
    monkeypatch.setattr(shell_setup, "PRECREATED_STOW_DIRECTORIES", [".config/opencode"])

    shell_setup.ensure_precreated_stow_directories()

    directory = physical_home / ".config/opencode"
    assert directory.is_dir()
    assert not directory.is_symlink()


def test_precreate_keeps_existing_directory_contents(temp_home: Path, monkeypatch) -> None:
    physical_home = temp_home.resolve()
    monkeypatch.setattr(shell_setup, "PRECREATED_STOW_DIRECTORIES", [".config/opencode"])
    local_file = physical_home / ".config/opencode/service.json"
    local_file.parent.mkdir(parents=True)
    local_file.write_text("{}")

    shell_setup.ensure_precreated_stow_directories()

    assert local_file.read_text() == "{}"


def test_warns_loudly_when_precreated_directory_is_symlink(
    temp_home: Path, monkeypatch, capsys
) -> None:
    physical_home = temp_home.resolve()
    monkeypatch.setattr(shell_setup, "PRECREATED_STOW_DIRECTORIES", [".config/opencode"])
    repo_dir = physical_home / ".dotfiles/.config/opencode"
    repo_dir.mkdir(parents=True)
    link = physical_home / ".config/opencode"
    link.parent.mkdir(parents=True)
    link.symlink_to("../.dotfiles/.config/opencode")

    shell_setup.ensure_precreated_stow_directories()

    assert link.is_symlink()
    assert os.readlink(link) == "../.dotfiles/.config/opencode"
    err = capsys.readouterr().err
    assert "WARNING" in err
    assert str(link) in err
    assert "../.dotfiles/.config/opencode" in err


@pytest.mark.parametrize("os_name", ["Linux", "Darwin"])
@pytest.mark.parametrize("previous_link", [None, "directory", "file"])
def test_sync_scheduled_codex_skill(temp_home, monkeypatch, os_name, previous_link):
    monkeypatch.setattr(shell_setup, "uname", lambda _: os_name)
    skill_path = Path(".codex/skills/scheduled-codex-prompts")
    source = state.DOTFILES_DIR / skill_path
    target = temp_home / skill_path
    target.parent.mkdir(parents=True)
    if previous_link == "directory":
        target.symlink_to(os.path.relpath(source, target.parent))
    elif previous_link == "file":
        target.mkdir()
        (target / "SKILL.md").symlink_to(source / "SKILL.md")

    shell_setup.sync_scheduled_codex_prompt_skill()
    shell_setup.sync_scheduled_codex_prompt_skill()

    if os_name == "Linux":
        assert target.is_symlink()
        assert target.resolve() == source
    else:
        assert not target.exists()
        assert not target.is_symlink()


def test_sync_scheduled_codex_skill_keeps_user_files(temp_home, monkeypatch):
    monkeypatch.setattr(shell_setup, "uname", lambda _: "Darwin")
    skill_path = Path(".codex/skills/scheduled-codex-prompts")
    source = state.DOTFILES_DIR / skill_path
    target = temp_home / skill_path
    target.mkdir(parents=True)
    (target / "SKILL.md").symlink_to(source / "SKILL.md")
    notes = target / "notes.txt"
    notes.write_text("local")

    shell_setup.sync_scheduled_codex_prompt_skill()

    assert not (target / "SKILL.md").is_symlink()
    assert notes.read_text() == "local"


@pytest.mark.parametrize(
    ("os_name", "fragment"),
    [
        ("Darwin", "git/credential-darwin.gitconfig"),
        ("Linux", "git/credential-linux.gitconfig"),
    ],
)
def test_sync_gitconfig_os_links_fragment(temp_home, monkeypatch, os_name, fragment):
    monkeypatch.setattr(shell_setup, "uname", lambda _: os_name)
    target = temp_home / ".gitconfig-os"

    shell_setup.sync_gitconfig_os()
    first_link = os.readlink(target)
    shell_setup.sync_gitconfig_os()

    assert target.is_symlink()
    assert os.readlink(target) == first_link
    assert target.resolve() == (state.DOTFILES_DIR / fragment).resolve()


def test_sync_gitconfig_os_replaces_own_stale_link(temp_home, monkeypatch):
    target = temp_home / ".gitconfig-os"
    monkeypatch.setattr(shell_setup, "uname", lambda _: "Darwin")
    shell_setup.sync_gitconfig_os()

    monkeypatch.setattr(shell_setup, "uname", lambda _: "Linux")
    shell_setup.sync_gitconfig_os()

    assert target.resolve() == (state.DOTFILES_DIR / "git/credential-linux.gitconfig").resolve()


def test_sync_gitconfig_os_keeps_user_file(temp_home, monkeypatch, capsys):
    monkeypatch.setattr(shell_setup, "uname", lambda _: "Linux")
    target = temp_home / ".gitconfig-os"
    target.write_text("[user]\n")

    shell_setup.sync_gitconfig_os()

    assert not target.is_symlink()
    assert target.read_text() == "[user]\n"
    assert str(target) in capsys.readouterr().err


def test_sync_gitconfig_os_keeps_foreign_link(temp_home, monkeypatch):
    monkeypatch.setattr(shell_setup, "uname", lambda _: "Linux")
    target = temp_home / ".gitconfig-os"
    target.symlink_to("/nonexistent/gitconfig")

    shell_setup.sync_gitconfig_os()

    assert os.readlink(target) == "/nonexistent/gitconfig"


def test_sync_gitconfig_os_skips_unknown_os(temp_home, monkeypatch):
    monkeypatch.setattr(shell_setup, "uname", lambda _: "FreeBSD")

    shell_setup.sync_gitconfig_os()

    assert not (temp_home / ".gitconfig-os").exists()
    assert not (temp_home / ".gitconfig-os").is_symlink()


def test_sync_gitconfig_os_warns_without_gh(temp_home, monkeypatch, capsys):
    monkeypatch.setattr(shell_setup, "uname", lambda _: "Linux")
    monkeypatch.setattr(shell_setup, "command_exists", lambda _: False)

    shell_setup.sync_gitconfig_os()

    assert "gh is not installed" in capsys.readouterr().err
    assert (temp_home / ".gitconfig-os").is_symlink()
