# Keep preferred user/Homebrew bins ahead of macOS system paths.
typeset -gU path PATH

ensure_preferred_path_order() {
  local dir
  local -a preferred_path

  preferred_path=()
  for dir in \
    "$HOME/.local/bin" \
    "/opt/homebrew/bin" \
    "/opt/homebrew/sbin" \
    "/opt/homebrew/opt/postgresql/bin" \
    "$HOME/go/bin"
  do
    [[ -d "$dir" ]] && preferred_path+=("$dir")
  done

  path=($preferred_path $path)
  export PATH
}

ensure_preferred_path_order

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

ensure_preferred_path_order

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
    export EDITOR="$HOME/.local/bin/wait-zed"
    export VISUAL="$HOME/.local/bin/wait-zed"
  elif command -v hx >/dev/null 2>&1; then
    export EDITOR=hx
    export VISUAL=hx
  elif command -v vim >/dev/null 2>&1; then
    export EDITOR=vim
    export VISUAL=vim
  fi
fi
