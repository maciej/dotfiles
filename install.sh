#!/usr/bin/env bash

set -euo pipefail

DOTFILES_REPO_URL="https://github.com/maciej/dotfiles.git"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
UPGRADE=false
SYNC_ZED_SETTINGS=false

# Paths that used to be stowed into $HOME but are no longer present in the repo.
LEGACY_STOW_PATHS=(
  "${HOME}/.shell_paths"
)

PRECREATED_STOW_DIRECTORIES=(
  "${HOME}/.agents/skills"
)

# Package manifests. Keep these near the top so host package changes stay easy to edit.
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
  lazygit
  jq
  ncurses
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
  lazygit
  kitty
  ncurses-bin
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
  kitty
  font-jetbrains-mono
  zed
)

UV_TOOL_PACKAGES=(
  ruff
  ty
)

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

log() {
  printf "[dotfiles] %s\n" "$1"
}

log_err() {
  printf "[dotfiles] %s\n" "$1" >&2
}

ensure_user_local_bin_on_path() {
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*)
      ;;
    *)
      export PATH="${HOME}/.local/bin:${PATH}"
      ;;
  esac
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

is_raspbian_host() {
  [[ -r /etc/os-release ]] || return 1

  grep -Eq '^ID=raspbian$' /etc/os-release
}

readonly MIB=1048576
readonly HELIX_TEMP_MIN_FREE_BYTES=$((512 * MIB))
readonly GIT_DELTA_TEMP_MIN_FREE_BYTES=$((64 * MIB))

TEMP_DIR_CLEANUP_ITEMS=()

cleanup_temp_dirs() {
  local dir

  for dir in "${TEMP_DIR_CLEANUP_ITEMS[@]}"; do
    [[ -n "${dir}" ]] || continue
    rm -rf "${dir}"
  done
}

register_temp_cleanup_trap() {
  trap cleanup_temp_dirs EXIT
}

register_temp_dir_for_cleanup() {
  local dir="$1"

  TEMP_DIR_CLEANUP_ITEMS+=("${dir}")
  register_temp_cleanup_trap
}

unregister_temp_dir_for_cleanup() {
  local dir="$1"
  local remaining=()
  local item

  for item in "${TEMP_DIR_CLEANUP_ITEMS[@]}"; do
    if [[ "${item}" != "${dir}" ]]; then
      remaining+=("${item}")
    fi
  done

  TEMP_DIR_CLEANUP_ITEMS=("${remaining[@]}")
}

cleanup_temp_dir_now() {
  local dir="$1"

  unregister_temp_dir_for_cleanup "${dir}"
  rm -rf "${dir}"
}

available_bytes_for_path() {
  local path="$1"
  local available_kb

  available_kb="$(
    df -Pk "${path}" 2>/dev/null \
      | awk 'NR == 2 { print $4 }'
  )"

  if [[ -z "${available_kb}" ]] || ! [[ "${available_kb}" =~ ^[0-9]+$ ]]; then
    return 1
  fi

  printf '%s\n' "$((available_kb * 1024))"
}

describe_bytes_in_mib() {
  local bytes="$1"

  printf '%s MiB' "$(((bytes + MIB - 1) / MIB))"
}

resolve_temp_root() {
  local required_bytes="$1"
  local purpose="$2"
  local explicit_tmpdir=false
  local primary_root fallback_root available_bytes

  if [[ -n "${TMPDIR:-}" ]]; then
    explicit_tmpdir=true
    primary_root="${TMPDIR}"
  else
    primary_root="/tmp"
  fi

  mkdir -p "${primary_root}"

  if ! available_bytes="$(available_bytes_for_path "${primary_root}")"; then
    log_err "Could not determine free space for temporary directory root ${primary_root}"
    return 1
  fi

  if (( available_bytes >= required_bytes )); then
    printf '%s\n' "${primary_root}"
    return 0
  fi

  if [[ "${explicit_tmpdir}" == "true" ]]; then
    log_err "TMPDIR (${primary_root}) has only $(describe_bytes_in_mib "${available_bytes}") free, but ${purpose} requires at least $(describe_bytes_in_mib "${required_bytes}")"
    return 1
  fi

  fallback_root="${HOME}/.cache/tmp"
  mkdir -p "${fallback_root}"

  if ! available_bytes="$(available_bytes_for_path "${fallback_root}")"; then
    log_err "Could not determine free space for fallback temporary directory root ${fallback_root}"
    return 1
  fi

  if (( available_bytes < required_bytes )); then
    log_err "Default temporary directory (/tmp) has insufficient space and fallback ${fallback_root} has only $(describe_bytes_in_mib "${available_bytes}") free, but ${purpose} requires at least $(describe_bytes_in_mib "${required_bytes}")"
    return 1
  fi

  log_err "Using fallback temporary directory root ${fallback_root} because /tmp has insufficient free space for ${purpose}"
  printf '%s\n' "${fallback_root}"
}

create_managed_temp_dir() {
  local __resultvar="$1"
  local required_bytes="$2"
  local purpose="$3"
  local prefix="$4"
  local temp_root managed_tmp_dir

  temp_root="$(resolve_temp_root "${required_bytes}" "${purpose}")" || return 1
  managed_tmp_dir="$(mktemp -d -p "${temp_root}" "${prefix}.XXXXXX")"
  chmod 755 "${managed_tmp_dir}"
  register_temp_dir_for_cleanup "${managed_tmp_dir}"
  printf -v "${__resultvar}" '%s' "${managed_tmp_dir}"
}

install_git_delta_linux() {
  local apt_status arch deb_arch download_size_bytes download_url latest_url tag tmp_dir version

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

  download_size_bytes="$(
    curl -fsSLI -o /dev/null -w '%{content_length_download}' "${download_url}" 2>/dev/null || true
  )"
  if [[ -z "${download_size_bytes}" ]] || ! [[ "${download_size_bytes}" =~ ^[0-9]+$ ]] || (( download_size_bytes <= 0 )); then
    download_size_bytes="${GIT_DELTA_TEMP_MIN_FREE_BYTES}"
  fi

  create_managed_temp_dir tmp_dir "${download_size_bytes}" "git-delta download" "git-delta" || return 1

  if ! curl -fsSL "${download_url}" -o "${tmp_dir}/git-delta.deb"; then
    log "Could not download git-delta release package for ${deb_arch}"
    return 1
  fi
  chmod 644 "${tmp_dir}/git-delta.deb"

  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${tmp_dir}/git-delta.deb"
  cleanup_temp_dir_now "${tmp_dir}"
  log "Installed git-delta from upstream .deb release"
}

install_uv_linux() {
  local uv_bin="${HOME}/.local/bin/uv"
  local installed=false

  ensure_user_local_bin_on_path

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

  ensure_user_local_bin_on_path
}

resolve_uv_bin() {
  local uv_bin="${HOME}/.local/bin/uv"

  if command -v uv >/dev/null 2>&1; then
    command -v uv
    return 0
  fi

  if [[ -x "${uv_bin}" ]]; then
    printf '%s\n' "${uv_bin}"
    return 0
  fi

  return 1
}

install_helix_linux_via_snap() {
  local helix_bin="${HOME}/.local/bin/hx"
  local installed=false

  if snap list helix >/dev/null 2>&1; then
    installed=true
  fi

  if ! command -v snap >/dev/null 2>&1; then
    log "Installing snapd from apt repositories for Helix armhf support"
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y snapd
  fi

  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl enable --now snapd.socket
  fi

  if [[ ! -e /snap && -d /var/lib/snapd/snap ]]; then
    sudo ln -s /var/lib/snapd/snap /snap
  fi

  if ! snap list snapd >/dev/null 2>&1; then
    log "Installing snapd snap per Snapcraft Raspbian instructions"
    sudo snap install snapd
  fi

  if [[ "${installed}" == "true" ]]; then
    if [[ "${UPGRADE}" == "true" ]]; then
      log "Refreshing Helix from Snapcraft"
      sudo snap refresh helix
    else
      log "helix already installed"
    fi
  else
    log "Installing Helix from Snapcraft"
    sudo snap install helix --classic
  fi

  mkdir -p "${HOME}/.local/bin"
  ln -sfn /snap/bin/hx "${helix_bin}"
  log "Linked Helix snap launcher into ${helix_bin}"
}

install_helix_linux() {
  local helix_bin="${HOME}/.local/bin/hx"
  local arch asset_name asset_pattern asset_size_bytes asset_url extracted_dir tarball tmp_dir
  local installed=false

  arch="$(uname -m 2>/dev/null || true)"
  case "${arch}" in
    aarch64|arm64)
      asset_pattern="aarch64-linux.tar.xz"
      ;;
    x86_64|amd64)
      asset_pattern="x86_64-linux.tar.xz"
      ;;
    armv6l|armv7l|armhf)
      if is_raspbian_host; then
        install_helix_linux_via_snap
      else
        log "No official Helix Linux release is available for ${arch}; skipping Helix installation"
      fi
      return
      ;;
    *)
      log "Unsupported Helix Linux architecture (${arch:-unknown}); skipping Helix installation"
      return
      ;;
  esac

  if command -v hx >/dev/null 2>&1 || [[ -x "${helix_bin}" ]]; then
    installed=true
  fi

  if [[ "${installed}" == "true" && "${UPGRADE}" != "true" ]]; then
    log "helix already installed"
    return
  fi

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

  read -r asset_url asset_name asset_size_bytes < <(
    curl -fsSL https://api.github.com/repos/helix-editor/helix/releases/latest \
      | jq -r --arg pattern "${asset_pattern}" '.assets[] | select(.name | endswith($pattern)) | [.browser_download_url, .name, (.size | tostring)] | @tsv' \
      | head -n 1
  )

  if [[ -z "${asset_url}" ]]; then
    log "Could not find an official Helix release asset for ${arch}"
    return 1
  fi

  if [[ -z "${asset_size_bytes}" ]] || ! [[ "${asset_size_bytes}" =~ ^[0-9]+$ ]] || (( asset_size_bytes <= 0 )); then
    asset_size_bytes="${HELIX_TEMP_MIN_FREE_BYTES}"
  fi

  if (( asset_size_bytes < HELIX_TEMP_MIN_FREE_BYTES )); then
    asset_size_bytes="${HELIX_TEMP_MIN_FREE_BYTES}"
  fi

  create_managed_temp_dir tmp_dir "${asset_size_bytes}" "Helix archive download and extraction (${asset_name})" "helix" || return 1
  tarball="${tmp_dir}/helix.tar.xz"

  curl -fsSL "${asset_url}" -o "${tarball}"
  tar -xJf "${tarball}" -C "${tmp_dir}"

  extracted_dir="$(find "${tmp_dir}" -mindepth 1 -maxdepth 1 -type d -name 'helix-*' | head -n 1)"
  if [[ -z "${extracted_dir}" || ! -x "${extracted_dir}/hx" || ! -d "${extracted_dir}/runtime" ]]; then
    log "Helix release archive did not contain the expected files"
    return 1
  fi

  mkdir -p "${HOME}/.local/bin" "${HOME}/.config/helix"
  install -m 0755 "${extracted_dir}/hx" "${helix_bin}"

  rm -rf "${HOME}/.config/helix/runtime"
  cp -R "${extracted_dir}/runtime" "${HOME}/.config/helix/runtime"

  cleanup_temp_dir_now "${tmp_dir}"
  if [[ "${installed}" == "true" ]]; then
    log "Upgraded Helix from official release asset"
  else
    log "Installed Helix from official release asset"
  fi
}

install_uv_tools() {
  local installed=false
  local tool
  local tool_list
  local uv_bin

  ensure_user_local_bin_on_path

  if ! uv_bin="$(resolve_uv_bin)"; then
    log "uv is not installed; skipping uv tool installation"
    return 0
  fi

  tool_list="$("${uv_bin}" tool list 2>/dev/null || true)"

  for tool in "${UV_TOOL_PACKAGES[@]}"; do
    if grep -Eq "^${tool} v" <<<"${tool_list}"; then
      installed=true
      if [[ "${UPGRADE}" == "true" ]]; then
        log "Upgrading uv tool: ${tool}"
        "${uv_bin}" tool upgrade "${tool}"
      else
        log "Already installed uv tool: ${tool}"
      fi
    else
      log "Installing uv tool: ${tool}"
      "${uv_bin}" tool install "${tool}@latest"
    fi
  done

  if [[ "${installed}" == "false" && "${UPGRADE}" != "true" ]]; then
    log "Installed requested uv tools"
  fi
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

resolve_infocmp_bin() {
  local os brew_prefix
  os="$(uname -s 2>/dev/null || true)"

  if [[ "${os}" == "Darwin" ]]; then
    for brew_prefix in /opt/homebrew /usr/local; do
      if [[ -x "${brew_prefix}/opt/ncurses/bin/infocmp" ]]; then
        printf '%s\n' "${brew_prefix}/opt/ncurses/bin/infocmp"
        return 0
      fi
    done
  fi

  if command -v infocmp >/dev/null 2>&1; then
    command -v infocmp
    return 0
  fi

  return 1
}

resolve_tic_bin() {
  local os brew_prefix
  os="$(uname -s 2>/dev/null || true)"

  if [[ "${os}" == "Darwin" ]]; then
    for brew_prefix in /opt/homebrew /usr/local; do
      if [[ -x "${brew_prefix}/opt/ncurses/bin/tic" ]]; then
        printf '%s\n' "${brew_prefix}/opt/ncurses/bin/tic"
        return 0
      fi
    done
  fi

  if command -v tic >/dev/null 2>&1; then
    command -v tic
    return 0
  fi

  return 1
}

find_ghostty_terminfo_file() {
  local candidate

  for candidate in \
    "/Applications/Ghostty.app/Contents/Resources/terminfo/78/xterm-ghostty" \
    "${HOME}/Applications/Ghostty.app/Contents/Resources/terminfo/78/xterm-ghostty" \
    "${DOTFILES_DIR}/terminfo/ghostty.terminfo"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s\n' "${candidate}"
      return 0
    fi
  done

  return 1
}

sanitize_ghostty_terminfo_source() {
  awk '
    BEGIN {
      header_done = 0
      emit_alias = 0
    }
    !header_done && /^[[:space:]]*#/ {
      print
      next
    }
    !header_done && /^[[:space:]]*$/ {
      print
      next
    }
    !header_done {
      header_done = 1
      emit_alias = ($0 ~ /(^|\|)ghostty([|,])/)
      print "xterm-ghostty,"
      next
    }
    {
      print
    }
    END {
      if (header_done && emit_alias) {
        print ""
        print "ghostty,"
        print "\tuse=xterm-ghostty,"
      }
    }
  '
}

compile_ghostty_terminfo_from_infocmp() {
  local infocmp_bin="$1"
  local tic_bin="$2"
  local target_dir="$3"
  local source_dir="${4:-}"

  if [[ -n "${source_dir}" ]]; then
    "${infocmp_bin}" -x -A "${source_dir}" xterm-ghostty
  else
    "${infocmp_bin}" -x xterm-ghostty
  fi | sanitize_ghostty_terminfo_source | "${tic_bin}" -x -o "${target_dir}" -
}

ghostty_terminfo_installed_in_dir() {
  local target_dir="$1"

  if [[ -f "${target_dir}/78/xterm-ghostty" || -f "${target_dir}/67/ghostty" ]]; then
    return 0
  fi

  if [[ -d "${target_dir}" ]] && find "${target_dir}" -maxdepth 2 -type f \( -name 'xterm-ghostty' -o -name 'ghostty' \) -print -quit 2>/dev/null | grep -q .; then
    return 0
  fi

  return 1
}

install_ghostty_terminfo() {
  local infocmp_bin tic_bin target_dir source_file source_dir

  if ! tic_bin="$(resolve_tic_bin)"; then
    log "tic is not installed; skipping Ghostty terminfo setup"
    return 0
  fi

  target_dir="${HOME}/.terminfo"

  if ghostty_terminfo_installed_in_dir "${target_dir}"; then
    log "Ghostty terminfo already installed in ${target_dir}"
    return 0
  fi

  if infocmp_bin="$(resolve_infocmp_bin)"; then
    if "${infocmp_bin}" -x -A "${target_dir}" xterm-ghostty >/dev/null 2>&1; then
      log "Ghostty terminfo already installed in ${target_dir}"
      return 0
    fi
  fi

  if ! source_file="$(find_ghostty_terminfo_file)"; then
    if [[ -n "${infocmp_bin:-}" ]] && "${infocmp_bin}" -x xterm-ghostty >/dev/null 2>&1; then
      mkdir -p "${target_dir}"
      compile_ghostty_terminfo_from_infocmp "${infocmp_bin}" "${tic_bin}" "${target_dir}"
      log "Installed Ghostty terminfo from the active terminfo database"
      return 0
    fi

    log "Could not find a Ghostty terminfo source locally; skipping Ghostty terminfo setup"
    return 0
  fi

  mkdir -p "${target_dir}"

  case "$(basename "${source_file}")" in
    xterm-ghostty)
      source_dir="$(dirname "$(dirname "${source_file}")")"
      if [[ -z "${infocmp_bin:-}" ]]; then
        if ! infocmp_bin="$(resolve_infocmp_bin)"; then
          log "infocmp is not installed; skipping Ghostty terminfo setup"
          return 0
        fi
      fi

      compile_ghostty_terminfo_from_infocmp "${infocmp_bin}" "${tic_bin}" "${target_dir}" "${source_dir}"
      log "Installed Ghostty terminfo from ${source_file}"
      ;;
    *)
      "${tic_bin}" -x -o "${target_dir}" "${source_file}"
      log "Installed Ghostty terminfo from ${source_file}"
      ;;
  esac
}

validate_legacy_stow_targets() {
  local path rel_path repo_path

  for path in "${LEGACY_STOW_PATHS[@]}"; do
    if [[ "${path}" != "${HOME}/"* ]]; then
      log "Legacy stow target must be an absolute path under HOME: ${path}"
      return 1
    fi

    rel_path="${path#"${HOME}/"}"
    repo_path="${DOTFILES_DIR}/${rel_path}"
    if [[ -e "${repo_path}" ]]; then
      log "Legacy stow target is still present in the repo: ${path}"
      log "Remove it from LEGACY_STOW_PATHS or delete the repo path before rerunning install.sh."
      return 1
    fi
  done
}

remove_legacy_stow_targets() {
  local path link_target resolved_dir resolved_target

  for path in "${LEGACY_STOW_PATHS[@]}"; do
    if [[ ! -L "${path}" ]]; then
      if [[ -e "${path}" ]]; then
        log "Legacy path exists but is not a symlink; leaving it in place: ${path}"
      else
        log "No legacy stow target found: ${path}"
      fi
      continue
    fi

    link_target="$(readlink "${path}")"
    if [[ "${link_target}" == /* ]]; then
      resolved_target="${link_target}"
    else
      resolved_dir="$(
        cd "$(dirname "${path}")" \
          && cd "$(dirname "${link_target}")" 2>/dev/null \
          && pwd -P
      )" || {
        log "Could not resolve legacy symlink target; leaving it in place: ${path}"
        continue
      }
      resolved_target="${resolved_dir}/$(basename "${link_target}")"
    fi

    case "${resolved_target}" in
      "${DOTFILES_DIR}"|"${DOTFILES_DIR}"/*)
        rm -f "${path}"
        log "Removed legacy stow target: ${path}"
        ;;
      *)
        log "Legacy path points outside this dotfiles repo; leaving it in place: ${path}"
        ;;
    esac
  done
}

ensure_precreated_stow_directories() {
  local dir

  for dir in "${PRECREATED_STOW_DIRECTORIES[@]}"; do
    if [[ -L "${dir}" ]]; then
      log "Precreated stow directory is currently a symlink; leaving it in place: ${dir}"
      continue
    fi

    mkdir -p "${dir}"
    log "Ensured directory exists before stow: ${dir}"
  done
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

  ensure_user_local_bin_on_path

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

  install_uv_tools
  install_ghostty_terminfo

  validate_legacy_stow_targets
  remove_legacy_stow_targets
  ensure_precreated_stow_directories
  link_dotfiles
  rebuild_bat_cache
  if [[ "${SYNC_ZED_SETTINGS}" == "true" ]]; then
    sync_zed_settings
  else
    log "Skipping Zed settings sync by default; pass --sync-zed-settings to enable it"
  fi
}

main "$@"
