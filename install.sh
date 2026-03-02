#!/usr/bin/env bash

set -euo pipefail

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
  uv
)

log() {
  printf "[dotfiles] %s\n" "$1"
}

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

main() {
  local os
  os="$(uname -s 2>/dev/null || true)"

  if [[ "${os}" != "Darwin" ]]; then
    log "Non-macOS host detected (${os:-unknown}); skipping Homebrew bootstrap"
    exit 0
  fi

  ensure_brew
  install_brew_packages
}

main "$@"
