from __future__ import annotations

import re
import shutil
from pathlib import Path

from . import state
from .core import home_dir, is_executable, log, run, uname


def remove_legacy_ghostty_config_macos() -> None:
    ghostty_dir = home_dir() / "Library/Application Support/com.mitchellh.ghostty"
    if not ghostty_dir.is_dir():
        log("No legacy Ghostty config directory found")
        return

    legacy_files = [ghostty_dir / "config", *ghostty_dir.glob("config.*.bak")]
    removed = False
    for file_path in legacy_files:
        if file_path.exists():
            file_path.unlink()
            removed = True
            log(f"Removed legacy Ghostty config: {file_path}")

    if not removed:
        log("No legacy Ghostty config files found")
        return

    if not any(ghostty_dir.iterdir()):
        ghostty_dir.rmdir()
        log("Removed empty legacy Ghostty config directory")
    else:
        log("Legacy Ghostty config directory still has other contents; leaving it in place")


def resolve_infocmp_bin() -> str | None:
    if uname("-s") == "Darwin":
        for brew_prefix in (Path("/opt/homebrew"), Path("/usr/local")):
            candidate = brew_prefix / "opt/ncurses/bin/infocmp"
            if is_executable(candidate):
                return str(candidate)

    return shutil.which("infocmp")


def resolve_tic_bin() -> str | None:
    if uname("-s") == "Darwin":
        for brew_prefix in (Path("/opt/homebrew"), Path("/usr/local")):
            candidate = brew_prefix / "opt/ncurses/bin/tic"
            if is_executable(candidate):
                return str(candidate)

    return shutil.which("tic")


def find_ghostty_terminfo_file() -> Path | None:
    candidates = [
        Path("/Applications/Ghostty.app/Contents/Resources/terminfo/78/xterm-ghostty"),
        home_dir() / "Applications/Ghostty.app/Contents/Resources/terminfo/78/xterm-ghostty",
        state.DOTFILES_DIR / "terminfo/ghostty.terminfo",
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def sanitize_ghostty_terminfo_source(source: str) -> str:
    output: list[str] = []
    header_done = False
    emit_alias = False

    for line in source.splitlines():
        if not header_done and re.match(r"^\s*#", line):
            output.append(line)
            continue
        if not header_done and re.match(r"^\s*$", line):
            output.append(line)
            continue
        if not header_done:
            header_done = True
            emit_alias = re.search(r"(^|\|)ghostty([|,])", line) is not None
            output.append("xterm-ghostty,")
            continue
        output.append(line)

    if header_done and emit_alias:
        output.extend(["", "ghostty,", "\tuse=xterm-ghostty,"])

    return "\n".join(output) + "\n"


def compile_ghostty_terminfo_from_infocmp(
    infocmp_bin: str,
    tic_bin: str,
    target_dir: Path,
    source_dir: Path | None = None,
) -> None:
    if source_dir is None:
        infocmp_args = [infocmp_bin, "-x", "xterm-ghostty"]
    else:
        infocmp_args = [infocmp_bin, "-x", "-A", source_dir, "xterm-ghostty"]

    source = run(infocmp_args, capture=True).stdout
    sanitized = sanitize_ghostty_terminfo_source(source)
    run([tic_bin, "-x", "-o", target_dir, "-"], input_text=sanitized)


def ghostty_terminfo_installed_in_dir(target_dir: Path) -> bool:
    if (target_dir / "78/xterm-ghostty").is_file() or (
        target_dir / "67/ghostty"
    ).is_file():
        return True

    if not target_dir.is_dir():
        return False

    for path in target_dir.rglob("*"):
        try:
            depth = len(path.relative_to(target_dir).parts)
        except ValueError:
            continue
        if depth <= 2 and path.is_file() and path.name in {"xterm-ghostty", "ghostty"}:
            return True

    return False


def install_ghostty_terminfo() -> None:
    tic_bin = resolve_tic_bin()
    if tic_bin is None:
        log("tic is not installed; skipping Ghostty terminfo setup")
        return

    target_dir = home_dir() / ".terminfo"
    if ghostty_terminfo_installed_in_dir(target_dir):
        log(f"Ghostty terminfo already installed in {target_dir}")
        return

    infocmp_bin = resolve_infocmp_bin()
    if infocmp_bin is not None:
        installed = run(
            [infocmp_bin, "-x", "-A", target_dir, "xterm-ghostty"],
            check=False,
            capture=True,
        ).returncode == 0
        if installed:
            log(f"Ghostty terminfo already installed in {target_dir}")
            return

    source_file = find_ghostty_terminfo_file()
    if source_file is None:
        if infocmp_bin is not None:
            active = run(
                [infocmp_bin, "-x", "xterm-ghostty"],
                check=False,
                capture=True,
            )
            if active.returncode == 0:
                target_dir.mkdir(parents=True, exist_ok=True)
                compile_ghostty_terminfo_from_infocmp(infocmp_bin, tic_bin, target_dir)
                log("Installed Ghostty terminfo from the active terminfo database")
                return

        log("Could not find a Ghostty terminfo source locally; skipping Ghostty terminfo setup")
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    if source_file.name == "xterm-ghostty":
        if infocmp_bin is None:
            log("infocmp is not installed; skipping Ghostty terminfo setup")
            return
        source_dir = source_file.parent.parent
        compile_ghostty_terminfo_from_infocmp(
            infocmp_bin,
            tic_bin,
            target_dir,
            source_dir,
        )
    else:
        run([tic_bin, "-x", "-o", target_dir, source_file])

    log(f"Installed Ghostty terminfo from {source_file}")
