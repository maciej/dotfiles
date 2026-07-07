from __future__ import annotations

BREW_PACKAGES = [
    "tmux",
    "cloudflared",
    "fish",
    "bat",
    "helix",
    "git",
    "git-delta",
    "fzf",
    "ripgrep",
    "rsync",
    "zoxide",
    "gh",
    "bash",
    "lazygit",
    "jq",
    "ncurses",
    "python",
    "sqlite",
    "stow",
    "poppler",
    "qpdf",
    "tesseract",
    "ocrmypdf",
]

BREW_K8S_PACKAGES = [
    "kubernetes-cli",
    "kubie",
]

APT_PACKAGES = [
    "bat",
    "curl",
    "fish",
    "fzf",
    "gh",
    "git",
    "jq",
    "kitty",
    "ncurses-bin",
    "python3",
    "ripgrep",
    "sqlite3",
    "stow",
    "tmux",
    "vim",
    "zoxide",
    "zsh",
]

APT_OPTIONAL_PACKAGES = [
    "lazygit",
]

BREW_CASKS = [
    "brave-browser",
    "claude-code",
    "codex",
    "ghostty",
    "kitty",
    "font-jetbrains-mono",
    "obsidian",
    "vlc",
    "zed",
]

UV_TOOL_PACKAGES = [
    "ruff",
    "ty",
]

LEGACY_STOW_PATHS = [
    ".agents/skills/gitlab",
    ".agents/skills/browser-use",
    ".agents/skills/browser-use-cli",
    ".agents/skills/gh-address-comments",
    ".agents/skills/gh-fix-ci",
    ".agents/skills/gh-yeet",
    ".agents/skills/github",
    ".agents/skills/mapskit",
    ".agents/skills/python-plots-styling",
    ".config/opencode/commands/fix-mr.md",
    ".config/opencode/skills/gitlab",
    ".shell_paths",
]

PRECREATED_STOW_DIRECTORIES = [
    ".codex/skills",
]

KNOWN_WITH_GROUPS = {"k8s"}

MIB = 1048576
HELIX_TEMP_MIN_FREE_BYTES = 512 * MIB
GIT_DELTA_TEMP_MIN_FREE_BYTES = 64 * MIB
BAT_TEMP_MIN_FREE_BYTES = 64 * MIB
KUBECTL_TEMP_MIN_FREE_BYTES = 128 * MIB
KUBIE_TEMP_MIN_FREE_BYTES = 32 * MIB

HELP_TEXT = """\
Usage: install.sh [--local] [--no-local] [--with GROUP[,GROUP...]] [--upgrade] [--sync-zed-settings] [--help]

Install dotfiles packages and link configuration files.

Options:
  --local              Link dotfiles and install user-local tools only. This
                       currently installs bat, git-delta, Helix, and Codex CLI
                       into user-local locations and does not install packages
                       or modify system state. Also remember this as the
                       default for future installs on this host.
  --no-local           Run a full install even when the local-install default
                       marker exists, and remove that marker.
  --with GROUP         Include optional tool group(s). May be repeated or use
                       comma-separated values. Available groups:
                       k8s (kubectl, kubie). Not valid with --local.
  --upgrade            On Linux, upgrade Helix and Codex CLI when they are
                       managed by the non-apt installer path. Does not run apt
                       upgrade or brew upgrade.
  --sync-zed-settings  Regenerate ~/.config/zed/settings.json from the tracked
                       shared settings after linking dotfiles.
  --help               Show this help message and exit.
"""
