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
