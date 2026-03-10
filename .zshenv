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
path_prepend "/opt/homebrew/opt/postgresql/bin"

export PATH

# Optional SOPS key path.
if [[ -f "$HOME/.config/sops/age/keys.txt" ]]; then
  export SOPS_AGE_KEY_FILE="$HOME/.config/sops/age/keys.txt"
fi

# Optional Rust/Cargo environment.
if [[ -f "$HOME/.cargo/env" ]]; then
  . "$HOME/.cargo/env"
fi

# Optional Cloudflare WARP certs.
if [[ -f "$HOME/.local/share/cloudflare-warp-certs/config.sh" ]]; then
  . "$HOME/.local/share/cloudflare-warp-certs/config.sh"
fi

# Set editor based on session type:
# - Local: prefer zed --wait
# - Terminal fallback: prefer hx, then vim
if [[ -n "${SSH_TTY-}" || -n "${SSH_CONNECTION-}" || -n "${SSH_CLIENT-}" ]]; then
  if command -v hx >/dev/null 2>&1; then
    export EDITOR=hx
    export VISUAL=hx
  elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim
    export VISUAL=vim
  fi
else
  if command -v zed >/dev/null 2>&1; then
    export EDITOR="zed --wait"
    export VISUAL="zed --wait"
  elif command -v hx >/dev/null 2>&1; then
    export EDITOR=hx
    export VISUAL=hx
  elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim
    export VISUAL=vim
  fi
fi
