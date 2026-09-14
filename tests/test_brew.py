from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from helpers import make_executable

import dotfiles_install as installer


@pytest.mark.parametrize("modern", [False, True], ids=["legacy", "homebrew-7"])
@pytest.mark.parametrize("manpath", [None, "", "/custom/man"])
def test_brew_shellenv_preserves_shell_semantics(
    fake_bin: Path, monkeypatch: pytest.MonkeyPatch, modern: bool, manpath: str | None,
) -> None:
    original_path = os.environ["PATH"]
    monkeypatch.setenv("SHELL", "/bin/fish")
    monkeypatch.setenv("INFOPATH", "/custom/info")
    if manpath is None:
        monkeypatch.delenv("MANPATH", raising=False)
    else:
        monkeypatch.setenv("MANPATH", manpath)
    # Track mutations performed by the installer for fixture cleanup.
    for name in ("PATH", "INFOPATH", "HOMEBREW_PREFIX"):
        monkeypatch.setenv(name, os.environ.get(name, ""))
    exports = (
        'export HOMEBREW_PREFIX="/example/brew";\n'
        'export PATH="/example/brew/bin:/example/brew/sbin${PATH+:$PATH}";\n'
        'export INFOPATH="/example/brew/share/info:${INFOPATH:-}";\n'
    )
    if modern:
        exports += (
            '[ -z "${MANPATH-}" ] || { '
            'export MANPATH="${MANPATH%"${MANPATH##*[!:]}"}"; '
            'export MANPATH=":${MANPATH#"${MANPATH%%[!:]*}"}"; };\n'
        )
    else:
        exports += 'export MANPATH="/example/brew/share/man${MANPATH+:$MANPATH}:";\n'
    make_executable(
        fake_bin / "brew",
        '#!/bin/bash\n'
        '[ "$*" = "shellenv bash" ] || exit 42\n'
        "cat <<'EXPORTS'\n" + exports + "EXPORTS\n",
    )

    installer.ensure_brew()

    assert os.environ["PATH"] == f"/example/brew/bin:/example/brew/sbin:{original_path}"
    assert os.environ["HOMEBREW_PREFIX"] == "/example/brew"
    assert os.environ["INFOPATH"] == "/example/brew/share/info:/custom/info"
    if modern:
        assert os.environ.get("MANPATH") == (f":{manpath}" if manpath else manpath)
    else:
        suffix = f":{manpath}" if manpath is not None else ""
        assert os.environ["MANPATH"] == f"/example/brew/share/man{suffix}:"


def test_brew_shellenv_failure_does_not_change_environment(fake_bin: Path) -> None:
    make_executable(fake_bin / "brew", "#!/bin/bash\nexit 42\n")
    before = dict(os.environ)
    with pytest.raises(subprocess.CalledProcessError) as error:
        installer.ensure_brew()
    assert error.value.returncode == 42
    assert dict(os.environ) == before


def test_brew_shellenv_empty_output_is_noop(fake_bin: Path) -> None:
    make_executable(fake_bin / "brew", "#!/bin/bash\nexit 0\n")
    before = dict(os.environ)
    installer.ensure_brew()
    assert dict(os.environ) == before
