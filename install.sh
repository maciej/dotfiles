#!/usr/bin/env bash

set -euo pipefail

DOTFILES_REPO_URL="https://github.com/maciej/dotfiles.git"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
UPGRADE=false
SYNC_ZED_SETTINGS=false

log() {
  printf "[dotfiles] %s\n" "$1"
}

print_help() {
  cat <<EOF
Usage: install.sh [--upgrade] [--sync-zed-settings] [--help]

Install dotfiles packages and link configuration files.

Options:
  --upgrade            On Linux, upgrade Helix and uv when they are managed by
                       the non-apt installer path. Does not run apt upgrade or
                       brew upgrade.
  --sync-zed-settings  Regenerate ~/.config/zed/settings.json from the tracked
                       shared settings after linking dotfiles.
  --help               Show this help message and exit.
EOF
}

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --upgrade)
        UPGRADE=true
        ;;
      --sync-zed-settings)
        SYNC_ZED_SETTINGS=true
        ;;
      --help)
        print_help
        exit 0
        ;;
      *)
        log "Unknown argument: $1"
        print_help
        exit 1
        ;;
    esac
    shift
  done
}

# shellcheck disable=SC3030
BREW_PACKAGES=(
  tmux
  fish
  bat
  helix
  git
  git-delta
  fzf
  ripgrep
  zoxide
  gh
  bash
  jq
  python
  sqlite
  stow
  uv
)

# shellcheck disable=SC3030
APT_PACKAGES=(
  bat
  curl
  fish
  fzf
  gh
  git
  jq
  python3
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
  font-jetbrains-mono
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

parse_args "$@"
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

install_git_delta_linux() {
  local apt_status arch deb_arch download_url latest_url tag tmp_dir version

  apt_status="$(dpkg-query -W -f='${Status}' git-delta 2>/dev/null || true)"
  if [[ "${apt_status}" == "install ok installed" ]] || command -v delta >/dev/null 2>&1; then
    log "git-delta already installed"
    return
  fi

  if apt-cache show git-delta >/dev/null 2>&1; then
    log "Installing git-delta from apt repositories"
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y git-delta
    return
  fi

  arch="$(dpkg --print-architecture 2>/dev/null || true)"
  case "${arch}" in
    amd64)
      deb_arch="amd64"
      ;;
    arm64)
      deb_arch="arm64"
      ;;
    armhf)
      deb_arch="armhf"
      ;;
    i386)
      deb_arch="i386"
      ;;
    *)
      log "No git-delta .deb asset for architecture ${arch:-unknown}; skipping git-delta installation"
      return
      ;;
  esac

  command -v curl >/dev/null 2>&1 || {
    log "git-delta installer requires curl"
    return 1
  }

  latest_url="$(curl -fsSLI -o /dev/null -w '%{url_effective}' https://github.com/dandavison/delta/releases/latest)"
  tag="${latest_url##*/}"
  if [[ -z "${tag}" || "${tag}" == "latest" ]]; then
    log "Could not determine latest git-delta release tag"
    return 1
  fi

  version="${tag#v}"
  download_url="https://github.com/dandavison/delta/releases/download/${tag}/git-delta_${version}_${deb_arch}.deb"
  tmp_dir="$(mktemp -d -p /tmp git-delta.XXXXXX)"
  chmod 755 "${tmp_dir}"

  if ! curl -fsSL "${download_url}" -o "${tmp_dir}/git-delta.deb"; then
    rm -rf "${tmp_dir}"
    log "Could not download git-delta release package for ${deb_arch}"
    return 1
  fi
  chmod 644 "${tmp_dir}/git-delta.deb"

  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${tmp_dir}/git-delta.deb"
  rm -rf "${tmp_dir}"
  log "Installed git-delta from upstream .deb release"
}

install_uv_linux() {
  local uv_bin="${HOME}/.local/bin/uv"
  local installed=false

  if command -v uv >/dev/null 2>&1 || [[ -x "${uv_bin}" ]]; then
    installed=true
  fi

  if [[ "${installed}" == "true" && "${UPGRADE}" != "true" ]]; then
    log "uv already installed"
    return
  fi

  if command -v curl >/dev/null 2>&1; then
    if [[ "${installed}" == "true" ]]; then
      log "Upgrading uv via Astral official installer"
    else
      log "Installing uv via Astral official installer"
    fi
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  elif command -v wget >/dev/null 2>&1; then
    if [[ "${installed}" == "true" ]]; then
      log "Upgrading uv via Astral official installer"
    else
      log "Installing uv via Astral official installer"
    fi
    wget -qO- https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  else
    log "uv installer requires curl or wget"
    return 1
  fi
}

install_helix_linux() {
  local helix_bin="${HOME}/.local/bin/hx"
  local arch asset_pattern asset_url extracted_dir tarball tmp_dir
  local installed=false

  if command -v hx >/dev/null 2>&1 || [[ -x "${helix_bin}" ]]; then
    installed=true
  fi

  if [[ "${installed}" == "true" && "${UPGRADE}" != "true" ]]; then
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
  if [[ "${installed}" == "true" ]]; then
    log "Upgraded Helix from official release asset"
  else
    log "Installed Helix from official release asset"
  fi
}

install_brew_packages() {
  local installed missing pkg
  installed=$'\n'"$(brew list --versions "${BREW_PACKAGES[@]}" 2>/dev/null || true)"$'\n'
  missing=()

  for pkg in "${BREW_PACKAGES[@]}"; do
    if [[ "${installed}" == *$'\n'"${pkg} "* ]] || [[ "${installed}" == *$'\n'"${pkg}@"* ]]; then
      log "Already installed: ${pkg}"
    elif brew list --versions "${pkg}" >/dev/null 2>&1; then
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

sync_zed_settings() {
  local script_path="${DOTFILES_DIR}/scripts/zed-settings"
  local status

  if [[ ! -f "${script_path}" ]]; then
    log "Zed settings helper is missing: ${script_path}"
    return 1
  fi

  log "Generating live Zed settings"
  if "${script_path}" push; then
    return 0
  else
    status=$?
  fi

  if [[ "${status}" -eq 2 ]]; then
    log "Skipping Zed settings update; live file is newer"
    return 0
  fi

  return "${status}"
}

rebuild_bat_cache() {
  local bat_cmd

  if command -v bat >/dev/null 2>&1; then
    bat_cmd="bat"
  elif command -v batcat >/dev/null 2>&1; then
    bat_cmd="batcat"
  else
    log "bat is not installed; skipping bat cache rebuild"
    return
  fi

  if [[ ! -d "${HOME}/.config/bat/themes" ]]; then
    log "No custom bat themes found; skipping bat cache rebuild"
    return
  fi

  log "Rebuilding bat syntax/theme cache"
  "${bat_cmd}" cache --build
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
    install_git_delta_linux
    install_helix_linux
    install_uv_linux
  else
    log "Unsupported package manager on host (${os:-unknown}); skipping package installation"
  fi

  link_dotfiles
  rebuild_bat_cache
  if [[ "${SYNC_ZED_SETTINGS}" == "true" ]]; then
    sync_zed_settings
  else
    log "Skipping Zed settings sync by default; pass --sync-zed-settings to enable it"
  fi
}

main "$@"
