# Minimal PATH for ALL zsh sessions (incl. non-interactive SSH command mode).
path_prepend() {
  if [[ -d "$1" ]]; then
    case ":$PATH:" in
      *":$1:"*) ;;
      *) PATH="$1:$PATH" ;;
    esac
  fi
}

path_prepend "$HOME/go/bin"
path_prepend "$HOME/.local/bin"
path_prepend "/opt/homebrew/bin"
path_prepend "/opt/homebrew/sbin"

export PATH

# Set editor based on session type:
# - Local: prefer zed --wait
# - SSH: prefer nvim, then vim
if [[ -n "${SSH_TTY-}" || -n "${SSH_CONNECTION-}" || -n "${SSH_CLIENT-}" ]]; then
  if command -v nvim >/dev/null 2>&1; then
    export EDITOR=nvim
    export VISUAL=nvim
  elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim
    export VISUAL=vim
  fi
else
  if command -v zed >/dev/null 2>&1; then
    export EDITOR="zed --wait"
    export VISUAL="zed --wait"
  elif command -v nvim >/dev/null 2>&1; then
    export EDITOR=nvim
    export VISUAL=nvim
  elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim
    export VISUAL=vim
  fi
fi
