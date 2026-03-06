#!/usr/bin/env bash

set -euo pipefail

DOTFILES_REPO_URL="https://github.com/maciej/dotfiles.git"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"

log() {
  printf "[dotfiles] %s\n" "$1"
}

# shellcheck disable=SC3030
BREW_PACKAGES=(
  tmux
  fish
  helix
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

# shellcheck disable=SC3030
APT_PACKAGES=(
  curl
  fish
  fzf
  gh
  git
  jq
  ripgrep
  sqlite3
  stow
  tmux
  vim
  zoxide
  zsh
)

# Install non-preview cask apps
BREW_CASKS=(
  zed
)

bootstrap() {
  case "${SCRIPT_SOURCE}" in
    "")
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
      ;;
    /dev/stdin|/dev/fd/*|stdin|-)
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
      ;;

    *)
      DOTFILES_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
      log "Using existing script location at ${DOTFILES_DIR}"
      ;;
  esac
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

is_debian_apt_host() {
  [[ "$(uname -s 2>/dev/null || true)" == "Linux" ]] || return 1
  command -v apt-get >/dev/null 2>&1 || return 1
  [[ -r /etc/os-release ]] || return 1

  grep -Eqi '^(ID|ID_LIKE)=.*(debian|ubuntu)' /etc/os-release
}

install_apt_packages() {
  local missing pkg status
  missing=()

  log "Updating apt package metadata"
  sudo env DEBIAN_FRONTEND=noninteractive apt-get update

  for pkg in "${APT_PACKAGES[@]}"; do
    status="$(dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null || true)"
    if [[ "${status}" == "install ok installed" ]]; then
      log "Already installed: ${pkg}"
    else
      missing+=("${pkg}")
    fi
  done

  if (( ${#missing[@]} == 0 )); then
    log "All requested apt packages are already installed"
    return
  fi

  log "Installing missing apt packages: ${missing[*]}"
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

install_uv_linux() {
  local uv_bin="${HOME}/.local/bin/uv"

  if command -v uv >/dev/null 2>&1 || [[ -x "${uv_bin}" ]]; then
    log "uv already installed"
    return
  fi

  if command -v curl >/dev/null 2>&1; then
    log "Installing uv via Astral official installer"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  elif command -v wget >/dev/null 2>&1; then
    log "Installing uv via Astral official installer"
    wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  else
    log "uv installer requires curl or wget"
    return 1
  fi
}

install_helix_linux() {
  local helix_bin="${HOME}/.local/bin/hx"
  local arch asset_pattern asset_url extracted_dir tarball tmp_dir

  if command -v hx >/dev/null 2>&1 || [[ -x "${helix_bin}" ]]; then
    log "helix already installed"
    return
  fi

  arch="$(uname -m 2>/dev/null || true)"
  case "${arch}" in
    aarch64|arm64)
      asset_pattern="aarch64-linux.tar.xz"
      ;;
    x86_64|amd64)
      asset_pattern="x86_64-linux.tar.xz"
      ;;
    armv6l|armv7l|armhf)
      log "No official Helix Linux release is available for ${arch}; skipping Helix installation"
      return
      ;;
    *)
      log "Unsupported Helix Linux architecture (${arch:-unknown}); skipping Helix installation"
      return
      ;;
  esac

  command -v curl >/dev/null 2>&1 || {
    log "Helix installer requires curl"
    return 1
  }
  command -v jq >/dev/null 2>&1 || {
    log "Helix installer requires jq"
    return 1
  }
  command -v tar >/dev/null 2>&1 || {
    log "Helix installer requires tar"
    return 1
  }

  asset_url="$(
    curl -fsSL https://api.github.com/repos/helix-editor/helix/releases/latest \
      | jq -r --arg pattern "${asset_pattern}" '.assets[] | select(.name | endswith($pattern)) | .browser_download_url' \
      | head -n 1
  )"

  if [[ -z "${asset_url}" ]]; then
    log "Could not find an official Helix release asset for ${arch}"
    return 1
  fi

  tmp_dir="$(mktemp -d)"
  tarball="${tmp_dir}/helix.tar.xz"

  curl -fsSL "${asset_url}" -o "${tarball}"
  tar -xJf "${tarball}" -C "${tmp_dir}"

  extracted_dir="$(find "${tmp_dir}" -mindepth 1 -maxdepth 1 -type d -name 'helix-*' | head -n 1)"
  if [[ -z "${extracted_dir}" || ! -x "${extracted_dir}/hx" || ! -d "${extracted_dir}/runtime" ]]; then
    rm -rf "${tmp_dir}"
    log "Helix release archive did not contain the expected files"
    return 1
  fi

  mkdir -p "${HOME}/.local/bin" "${HOME}/.config/helix"
  install -m 0755 "${extracted_dir}/hx" "${helix_bin}"

  rm -rf "${HOME}/.config/helix/runtime"
  cp -R "${extracted_dir}/runtime" "${HOME}/.config/helix/runtime"

  rm -rf "${tmp_dir}"
  log "Installed Helix from official release asset"
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

remove_legacy_ghostty_config_macos() {
  local ghostty_dir="${HOME}/Library/Application Support/com.mitchellh.ghostty"
  local -a legacy_files=(
    "${ghostty_dir}/config"
    "${ghostty_dir}"/config.*.bak
  )
  local file removed=false

  if [[ ! -d "${ghostty_dir}" ]]; then
    log "No legacy Ghostty config directory found"
    return
  fi

  shopt -s nullglob
  for file in "${legacy_files[@]}"; do
    if [[ -e "${file}" ]]; then
      rm -f "${file}"
      removed=true
      log "Removed legacy Ghostty config: ${file}"
    fi
  done
  shopt -u nullglob

  if [[ "${removed}" == "false" ]]; then
    log "No legacy Ghostty config files found"
    return
  fi

  if [[ -z "$(find "${ghostty_dir}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    rmdir "${ghostty_dir}"
    log "Removed empty legacy Ghostty config directory"
  else
    log "Legacy Ghostty config directory still has other contents; leaving it in place"
  fi
}

link_dotfiles() {
  if command -v stow >/dev/null 2>&1; then
    local restow="${DOTFILES_STOW_RESTOW:-false}"
    local adopt="${DOTFILES_STOW_ADOPT:-false}"
    local -a flags=(
      -v
      --target="${HOME}"
      --dir="${DOTFILES_DIR}"
    )

    if [[ "${restow}" == "true" || "${adopt}" == "true" ]]; then
      flags+=(--restow)
    fi

    if [[ "${DOTFILES_STOW_ADOPT:-false}" == "true" ]]; then
      flags+=(--adopt)
    fi

    flags+=(.)

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

  if [[ "${os}" == "Darwin" ]]; then
    ensure_brew
    install_brew_packages
    install_brew_casks
    remove_legacy_ghostty_config_macos
  elif is_debian_apt_host; then
    install_apt_packages
    install_helix_linux
    install_uv_linux
  else
    log "Unsupported package manager on host (${os:-unknown}); skipping package installation"
  fi

  link_dotfiles
}

main "$@"
