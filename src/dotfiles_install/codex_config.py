from __future__ import annotations

import os
import stat
from collections.abc import MutableMapping
from tempfile import NamedTemporaryFile

from . import state
from .core import home_dir, log
from .errors import InstallerError

CODEX_REASONING_KEYBINDINGS = {
    "decrease_reasoning_effort": ["f6", "shift-down"],
    "increase_reasoning_effort": ["f7", "shift-up"],
}


def sync_codex_keybindings() -> None:
    # --show-mode loads the installer with system Python and no dependencies.
    import tomlkit
    from tomlkit.exceptions import ParseError
    from tomlkit.items import InlineTable

    config = home_dir() / ".codex/config.toml"
    temporary_path = None
    try:
        target = config.resolve()
        if target.is_relative_to(state.DOTFILES_DIR.resolve()):
            raise InstallerError(f"Codex config must be outside the dotfiles checkout: {config}")

        try:
            with target.open("rb") as existing:
                original = existing.read()
                original_stat = os.fstat(existing.fileno())
        except FileNotFoundError:
            original = b""
            original_stat = None

        document = tomlkit.parse(original.decode("utf-8"))
        chat: MutableMapping[str, object] = document
        for key in ("tui", "keymap", "chat"):
            if key not in chat:
                chat[key] = (
                    tomlkit.inline_table() if isinstance(chat, InlineTable) else tomlkit.table()
                )
            table = chat[key]
            if not isinstance(table, MutableMapping):
                raise InstallerError(f"Expected a TOML table for tui.keymap.chat in {config}")
            chat = table

        changes = {
            action: binding
            for action, binding in CODEX_REASONING_KEYBINDINGS.items()
            if chat.get(action) != binding
        }
        if not changes:
            return

        chat.update(changes)

        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
            temporary_path = temporary.name
            temporary.write(document.as_string().encode("utf-8"))
            if original_stat is not None:
                os.fchmod(temporary.fileno(), stat.S_IMODE(original_stat.st_mode))

        try:
            current_stat = target.stat()
        except FileNotFoundError:
            current_stat = None
        if current_stat != original_stat or config.resolve() != target:
            raise InstallerError(f"Codex config changed during install. Rerun the installer: {config}")

        os.replace(temporary_path, target)
        temporary_path = None
        log(f"Updated Codex reasoning effort keybindings in {config}")
    except (ParseError, UnicodeDecodeError) as exc:
        raise InstallerError(f"Invalid TOML in Codex config: {config}") from exc
    except OSError as exc:
        raise InstallerError(f"Could not update Codex keybindings in {config}: {exc.strerror}") from exc
    finally:
        if temporary_path is not None:
            os.unlink(temporary_path)
