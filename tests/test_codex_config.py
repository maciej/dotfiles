from __future__ import annotations

import stat

import pytest
import tomllib

from dotfiles_install.codex_config import sync_codex_keybindings
from dotfiles_install.errors import InstallerError


def test_creates_private_codex_config(temp_home):
    sync_codex_keybindings()

    path = temp_home / ".codex/config.toml"
    assert not path.is_symlink()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert tomllib.loads(path.read_text()) == {
        "tui": {
            "keymap": {
                "chat": {
                    "decrease_reasoning_effort": "f6",
                    "increase_reasoning_effort": "f7",
                }
            }
        }
    }


def test_updates_only_owned_bindings_and_skips_a_second_write(temp_home):
    path = temp_home / ".codex/config.toml"
    path.parent.mkdir()
    original = (
        '# Host-specific settings\nmodel_reasoning_effort   = "medium"\n'
        '\n[tui.keymap.chat]\n'
        'decrease_reasoning_effort = ["alt-comma"] # lower\n'
        'increase_reasoning_effort = "alt-period"\n'
        'toggle_voice = "f8"\n'
        '\n[tui.keymap.global]\nleader = "ctrl-x"\n'
    )
    path.write_text(original)
    path.chmod(0o640)

    sync_codex_keybindings()

    expected = original.replace('["alt-comma"]', '"f6"').replace('"alt-period"', '"f7"')
    assert path.read_text() == expected
    before = path.stat()
    assert stat.S_IMODE(before.st_mode) == 0o640

    sync_codex_keybindings()

    after = path.stat()
    assert (after.st_ino, after.st_mtime_ns) == (before.st_ino, before.st_mtime_ns)


@pytest.mark.parametrize(
    ("original", "message"),
    [("[tui\n", "Invalid TOML"), ('[tui]\nkeymap = "custom"\n', "Expected a TOML table")],
)
def test_leaves_unusable_codex_config_intact(temp_home, original, message):
    path = temp_home / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text(original)

    with pytest.raises(InstallerError, match=message):
        sync_codex_keybindings()

    assert path.read_text() == original
