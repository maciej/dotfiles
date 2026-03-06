#!/usr/bin/env bash

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTS_FILE="${DOTFILES_DEPLOY_HOSTS_FILE:-${XDG_CONFIG_HOME:-${HOME}/.config}/deploy/deploy-hosts}"
CONNECT_TIMEOUT="${DOTFILES_DEPLOY_CONNECT_TIMEOUT:-3}"
SERVER_ALIVE_INTERVAL="${DOTFILES_DEPLOY_SERVER_ALIVE_INTERVAL:-5}"
SERVER_ALIVE_COUNT_MAX="${DOTFILES_DEPLOY_SERVER_ALIVE_COUNT_MAX:-1}"
UPGRADE=false

log() {
  printf "[deploy] %s\n" "$1"
}

warn() {
  printf "[deploy] warning: %s\n" "$1" >&2
}

print_help() {
  cat <<EOF
Usage: deploy.sh [--upgrade] [--help]

Run install.sh locally, then SSH into each host listed in ${HOSTS_FILE}, update
~/.dotfiles, and run install.sh there.

Options:
  --upgrade  Pass --upgrade through to install.sh on each reachable host.
  --help     Show this help message and exit.

Environment:
  DOTFILES_DEPLOY_HOSTS_FILE              Override the host inventory file.
  DOTFILES_DEPLOY_CONNECT_TIMEOUT         SSH connect timeout in seconds.
  DOTFILES_DEPLOY_SERVER_ALIVE_INTERVAL   SSH server alive interval in seconds.
  DOTFILES_DEPLOY_SERVER_ALIVE_COUNT_MAX  SSH server alive retry count.

Notes:
  The local install is a hard failure and stops the deployment immediately.
  Per-host SSH or remote install failures are reported and skipped.
  The script exits non-zero only for local setup, local install, or argument errors.
EOF
}

parse_args() {
  while (( $# > 0 )); do
    case "$1" in
      --upgrade)
        UPGRADE=true
        ;;
      --help)
        print_help
        exit 0
        ;;
      *)
        warn "Unknown argument: $1"
        print_help
        exit 1
        ;;
    esac
    shift
  done
}

trim_whitespace() {
  local value="$1"

  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"

  printf "%s" "$value"
}

shell_quote_single() {
  local value="$1"

  value="${value//\'/\'\\\'\'}"
  printf "'%s'" "$value"
}

deploy_host() {
  local host="$1"
  local remote_cmd
  local remote_cmd_quoted
  local -a install_args ssh_opts

  install_args=()
  if [[ "${UPGRADE}" == "true" ]]; then
    install_args+=(--upgrade)
  fi

  ssh_opts=(
    -tt
    -o "ConnectTimeout=${CONNECT_TIMEOUT}"
    -o "ConnectionAttempts=1"
    -o "ServerAliveInterval=${SERVER_ALIVE_INTERVAL}"
    -o "ServerAliveCountMax=${SERVER_ALIVE_COUNT_MAX}"
    -o "LogLevel=ERROR"
  )

  remote_cmd='set -euo pipefail

if [[ -d "${HOME}/.dotfiles/.git" ]]; then
  git -C "${HOME}/.dotfiles" pull --ff-only
  cd "${HOME}/.dotfiles"
  ./install.sh'

  if (( ${#install_args[@]} > 0 )); then
    printf -v remote_cmd '%s %q' "${remote_cmd}" "${install_args[0]}"
    if (( ${#install_args[@]} > 1 )); then
      local arg
      for arg in "${install_args[@]:1}"; do
        printf -v remote_cmd '%s %q' "${remote_cmd}" "${arg}"
      done
    fi
  fi

  remote_cmd+=$'\nelse\n  curl -fsSL https://raw.githubusercontent.com/maciej/dotfiles/main/install.sh | bash -s --'
  if (( ${#install_args[@]} > 0 )); then
    local arg
    for arg in "${install_args[@]}"; do
      printf -v remote_cmd '%s %q' "${remote_cmd}" "${arg}"
    done
  fi
  remote_cmd+=$'\nfi'

  remote_cmd_quoted="$(shell_quote_single "${remote_cmd}")"
  ssh "${ssh_opts[@]}" "${host}" "exec bash -lc ${remote_cmd_quoted}" < /dev/null
}

deploy_local() {
  local -a install_args

  install_args=()
  if [[ "${UPGRADE}" == "true" ]]; then
    install_args+=(--upgrade)
  fi

  log "Deploying locally"
  bash "${ROOT_DIR}/install.sh" "${install_args[@]}"
}

main() {
  local raw_host host
  local success_count=0
  local failure_count=0

  parse_args "$@"
  deploy_local

  if [[ ! -r "${HOSTS_FILE}" ]]; then
    warn "Host inventory file is missing or unreadable: ${HOSTS_FILE}"
    exit 1
  fi

  while IFS= read -r raw_host || [[ -n "${raw_host}" ]]; do
    if [[ "${raw_host}" =~ ^[[:space:]]*$ ]] || [[ "${raw_host}" =~ ^[[:space:]]*# ]]; then
      continue
    fi

    host="$(trim_whitespace "${raw_host}")"
    if [[ -z "${host}" ]]; then
      continue
    fi

    log "Deploying to ${host}"
    if deploy_host "${host}"; then
      success_count=$((success_count + 1))
    else
      warn "Failed to deploy to ${host}; continuing"
      failure_count=$((failure_count + 1))
    fi
  done < "${HOSTS_FILE}"

  log "Finished: ${success_count} succeeded, ${failure_count} failed"
}

main "$@"
