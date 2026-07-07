#!/usr/bin/env bash

set -euo pipefail

DOTFILES_REPO_URL="https://github.com/maciej/dotfiles.git"
DOTFILES_DIR="${DOTFILES_DIR:-${HOME}/.dotfiles}"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-}"
SCRIPT_SOURCED=false
(return 0 2>/dev/null) && SCRIPT_SOURCED=true

log() {
  printf "[dotfiles] %s\n" "$1"
}

log_err() {
  printf "[dotfiles] %s\n" "$1" >&2
}

print_help() {
  cat <<EOF
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
EOF
}

args_include_help() {
  local arg

  for arg in "$@"; do
    if [[ "${arg}" == "--help" ]]; then
      return 0
    fi
  done

  return 1
}

args_include_upgrade() {
  local arg

  for arg in "$@"; do
    if [[ "${arg}" == "--upgrade" ]]; then
      return 0
    fi
  done

  return 1
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

install_or_upgrade_local_uv() {
  local installed="$1"

  if command -v curl >/dev/null 2>&1; then
    if [[ "${installed}" == "true" ]]; then
      log "Upgrading uv via Astral official installer"
    else
      log "Installing uv via Astral official installer"
    fi
    curl -LsSf https://astral.sh/uv/install.sh \
      | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  elif command -v wget >/dev/null 2>&1; then
    if [[ "${installed}" == "true" ]]; then
      log "Upgrading uv via Astral official installer"
    else
      log "Installing uv via Astral official installer"
    fi
    wget -qO- https://astral.sh/uv/install.sh \
      | env UV_INSTALL_DIR="${HOME}/.local/bin" UV_NO_MODIFY_PATH=1 sh
  else
    log_err "uv installer requires curl or wget"
    return 1
  fi
}

ensure_uv_bootstrap() {
  local installed=false
  local local_uv="${HOME}/.local/bin/uv"
  local upgrade=false

  ensure_user_local_bin_on_path

  if resolve_uv_bin >/dev/null 2>&1; then
    installed=true
  fi

  if args_include_upgrade "$@"; then
    upgrade=true
  fi

  if [[ "${installed}" == "true" && "${upgrade}" != "true" ]]; then
    log "uv already installed"
    return 0
  fi

  if [[ "${installed}" == "true" && "${upgrade}" == "true" && ! -x "${local_uv}" ]]; then
    log "uv already installed outside ~/.local/bin; skipping bootstrap upgrade"
    return 0
  fi

  install_or_upgrade_local_uv "${installed}"
  ensure_user_local_bin_on_path
}

bootstrap_repo_if_needed() {
  case "${SCRIPT_SOURCE}" in
    "")
      log "Running installer from stdin; bootstrapping repository in ${DOTFILES_DIR}"
      if [[ ! -d "${DOTFILES_DIR}" ]]; then
        command -v git >/dev/null 2>&1 || {
          log_err "git is required to bootstrap dotfiles from a remote installer."
          exit 1
        }
        git clone --depth 1 "${DOTFILES_REPO_URL}" "${DOTFILES_DIR}"
      elif [[ ! -d "${DOTFILES_DIR}/.git" ]]; then
        log_err "Destination exists but is not a git repository: ${DOTFILES_DIR}"
        log_err "Set DOTFILES_DIR to a different path and retry."
        exit 1
      fi

      exec bash "${DOTFILES_DIR}/install.sh" "$@"
      ;;
    /dev/stdin|/dev/fd/*|stdin|-)
      log "Running installer from stdin; bootstrapping repository in ${DOTFILES_DIR}"
      if [[ ! -d "${DOTFILES_DIR}" ]]; then
        command -v git >/dev/null 2>&1 || {
          log_err "git is required to bootstrap dotfiles from a remote installer."
          exit 1
        }
        git clone --depth 1 "${DOTFILES_REPO_URL}" "${DOTFILES_DIR}"
      elif [[ ! -d "${DOTFILES_DIR}/.git" ]]; then
        log_err "Destination exists but is not a git repository: ${DOTFILES_DIR}"
        log_err "Set DOTFILES_DIR to a different path and retry."
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

main() {
  local uv_bin

  if args_include_help "$@"; then
    print_help
    return 0
  fi

  bootstrap_repo_if_needed "$@"
  ensure_uv_bootstrap "$@"

  if ! uv_bin="$(resolve_uv_bin)"; then
    log_err "uv is required to run the dotfiles installer."
    return 1
  fi

  export DOTFILES_DIR
  exec "${uv_bin}" run --script "${DOTFILES_DIR}/src/dotfiles_install/__main__.py" "$@"
}

if [[ "${SCRIPT_SOURCED}" != "true" ]]; then
  main "$@"
fi
