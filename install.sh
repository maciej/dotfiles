#!/usr/bin/env sh

if [ -z "${BASH_VERSION:-}" ]; then
  exec /usr/bin/env BASH_INSTALL_SCRIPT="${0}" bash -s -- "$@"
fi

set -euo pipefail

DOTFILES_REPO_URL="https://github.com/maciej/dotfiles.git"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
SCRIPT_SOURCE="${BASH_INSTALL_SCRIPT:-${BASH_SOURCE[0]:-}}"

BREW_PACKAGES=(
  tmux
  fish
  git
  fzf
  ripgrep
  zoxide
  gh
  bash
  jq
  sqlite
  stow
  uv
)

# Install non-preview cask apps
BREW_CASKS=(
  zed
)

log() {
  printf "[dotfiles] %s\n" "$1"
}

bootstrap() {
  if [[ -f "${SCRIPT_SOURCE}" && "${SCRIPT_SOURCE}" != "-" && "${SCRIPT_SOURCE}" != /dev/stdin && "${SCRIPT_SOURCE}" != /dev/fd/* ]]; then
    DOTFILES_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
    log "Using existing script location at ${DOTFILES_DIR}"
    return
  fi

  log "Running installer from stdin; bootstrapping repository in ${DOTFILES_DIR}"

  if [[ ! -d "${DOTFILES_DIR}" ]]; then
    command -v git >/dev/null 2>&1 || {
      log "git is required to bootstrap dotfiles from a remote installer."
      exit 1
    }
    git clone --depth 1 "${DOTFILES_REPO_URL}" "${DOTFILES_DIR}"
  elif [[ ! -d "${DOTFILES_DIR}/.git" ]]; then
    log "Destination exists but is not a git repository: ${DOTFILES_DIR}"
    log "Set DOTFILES_DIR to a different path and retry."
    exit 1
  fi

  exec bash "${DOTFILES_DIR}/install.sh" "$@"
}

bootstrap "$@"

ensure_brew() {
  if command -v brew >/dev/null 2>&1; then
    log "Homebrew already installed"
  else
    log "Installing Homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  if [[ -x "/opt/homebrew/bin/brew" ]]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [[ -x "/usr/local/bin/brew" ]]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}

install_brew_packages() {
  local installed missing pkg
  installed=$'\n'"$(brew list --formula)"$'\n'
  missing=()

  for pkg in "${BREW_PACKAGES[@]}"; do
    if [[ "${installed}" == *$'\n'"${pkg}"$'\n'* ]]; then
      log "Already installed: ${pkg}"
    else
      missing+=("${pkg}")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    log "All requested brew packages are already installed"
    return
  fi

  log "Installing missing brew packages: ${missing[*]}"
  brew install "${missing[@]}"
}

install_brew_casks() {
  local installed missing cask
  installed=$'\n'"$(brew list --cask 2>/dev/null || true)"$'\n'
  missing=()

  for cask in "${BREW_CASKS[@]}"; do
    if [[ "${installed}" == *$'\n'"${cask}"$'\n'* ]]; then
      log "Already installed cask: ${cask}"
    else
      missing+=("${cask}")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    log "All requested cask apps are already installed"
    return
  fi

  log "Installing missing brew casks: ${missing[*]}"
  brew install --cask "${missing[@]}"
}

link_dotfiles() {
  if command -v stow >/dev/null 2>&1; then
    local flags=(-v --restow --target="${HOME}" --dir="${DOTFILES_DIR}" .)
    if [[ "${DOTFILES_STOW_ADOPT:-false}" == "true" ]]; then
      flags=(-v --restow --adopt --target="${HOME}" --dir="${DOTFILES_DIR}" .)
    fi

    log "Linking dotfiles with stow"
    if ! stow "${flags[@]}"; then
      log "Stow reported conflicts. Existing non-symlink files already exist."
      log "Set DOTFILES_STOW_ADOPT=true to adopt existing files into this repo, then relaunch install."
      return 1
    fi
  else
    log "GNU Stow not installed; skipping symlink setup"
    return 1
  fi
}

main() {
  local os
  os="$(uname -s 2>/dev/null || true)"

  if [[ "${os}" != "Darwin" ]]; then
    log "Non-macOS host detected (${os:-unknown}); skipping Homebrew bootstrap"
    exit 0
  fi

  ensure_brew
  install_brew_packages
  install_brew_casks
  link_dotfiles
}

main "$@"
