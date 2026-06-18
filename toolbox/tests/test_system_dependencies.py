from __future__ import annotations

import system_dependencies


def test_install_hint_uses_homebrew_on_macos() -> None:
    assert system_dependencies.install_hint("ffmpeg", system="Darwin") == (
        "Install it with: brew install ffmpeg"
    )


def test_is_debian_like_accepts_raspbian() -> None:
    assert system_dependencies.is_debian_like(
        {"ID": "raspbian", "ID_LIKE": "debian"}
    )


def test_install_hint_uses_apt_on_debian_like_linux(monkeypatch) -> None:
    monkeypatch.setattr(system_dependencies, "is_debian_like", lambda: True)

    assert system_dependencies.install_hint("ffmpeg", system="Linux") == (
        "Install it with: sudo apt update && sudo apt install ffmpeg"
    )


def test_install_hint_falls_back_for_unknown_system() -> None:
    assert system_dependencies.install_hint("ffmpeg", system="FreeBSD") == (
        "Install ffmpeg with your system package manager."
    )
