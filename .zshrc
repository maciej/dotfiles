# Fish-like ls/ll behavior with automatic color support.
_ensure_ls_opts() {
  local opt

  [[ -n "${__ls_base_command-}" ]] && return 0

  typeset -g __ls_base_command="ls"
  typeset -g __ls_color_opt=""
  typeset -g __ls_indicators_opt=""

  for opt in '--color=auto' '-G' '--color'; do
    if command ls "$opt" / >/dev/null 2>&1; then
      __ls_color_opt="$opt"
      break
    fi
  done

  if command ls -F / >/dev/null 2>&1; then
    __ls_indicators_opt="-F"
  fi
}

ls() {
  local cmd color_opt indicators_opt
  local -a args

  _ensure_ls_opts

  cmd="$__ls_base_command"
  color_opt="$__ls_color_opt"
  indicators_opt=""

  if [[ -t 1 ]]; then
    indicators_opt="$__ls_indicators_opt"
  fi

  args=()
  [[ -n "$color_opt" ]] && args+=("$color_opt")
  [[ -n "$indicators_opt" ]] && args+=("$indicators_opt")

  if [[ -n "${CLICOLOR_FORCE-}" && ! -t 1 ]]; then
    args=(${args:#"$color_opt"})
  fi

  if [[ "$TERM_PROGRAM" == "Apple_Terminal" ]]; then
    CLICOLOR=1 command "$cmd" "${args[@]}" "$@"
  else
    command "$cmd" "${args[@]}" "$@"
  fi
}

ll() {
  ls -lh "$@"
}

# Keep ANSI colors when paging with less.
if [[ -z "${LESS-}" ]]; then
  export LESS='-R -F'
else
  typeset -a less_flags filtered_flags
  less_flags=(${=LESS})
  filtered_flags=()
  for flag in "${less_flags[@]}"; do
    case "$flag" in
      -X|--mouse|--wheel-lines=*) ;;
      *) filtered_flags+=("$flag") ;;
    esac
  done
  [[ " ${filtered_flags[*]} " != *" -R "* ]] && filtered_flags+=(-R)
  [[ " ${filtered_flags[*]} " != *" -F "* ]] && filtered_flags+=(-F)
  export LESS="${(j: :)filtered_flags}"
fi

# Detect Homebrew prefix when available (macOS or Linuxbrew); empty elsewhere.
if command -v brew >/dev/null 2>&1; then
  BREW_PREFIX="$(brew --prefix)"
else
  BREW_PREFIX=""
fi

# zsh completion system (required before any script that calls compdef)
if command -v codex >/dev/null 2>&1; then
  CODEX_COMPLETION_DIR="$HOME/.zsh/completions"
  CODEX_COMPLETION_FILE="$CODEX_COMPLETION_DIR/_codex"

  mkdir -p "$CODEX_COMPLETION_DIR"
  if [[ ! -s "$CODEX_COMPLETION_FILE" || "$(command -v codex)" -nt "$CODEX_COMPLETION_FILE" ]]; then
    codex_completion_tmp="$(mktemp "${TMPDIR:-/tmp}/codex-zsh-completion.XXXXXX")"
    if codex completion zsh >| "$codex_completion_tmp"; then
      mv "$codex_completion_tmp" "$CODEX_COMPLETION_FILE"
    else
      rm -f "$codex_completion_tmp"
    fi
  fi

  unset CODEX_COMPLETION_DIR CODEX_COMPLETION_FILE codex_completion_tmp
fi

fpath=("$HOME/.zsh/completions" $fpath)
if [[ -n "${BREW_PREFIX}" && -d "${BREW_PREFIX}/share/zsh/site-functions" ]]; then
  fpath=("${BREW_PREFIX}/share/zsh/site-functions" $fpath)
fi
if command -v docker >/dev/null 2>&1 && [[ -d "$HOME/.docker/completions" ]]; then
  fpath=("$HOME/.docker/completions" $fpath)
fi
autoload -Uz compinit
compinit -d "$HOME/.zcompdump"

# Completion UX polish
zmodload zsh/complist
setopt AUTO_MENU COMPLETE_IN_WORD
zstyle ':completion:*' menu select
zstyle ':completion:*' group-name ''
zstyle ':completion:*:descriptions' format '%F{yellow}-- %d --%f'
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}' 'r:|[._-]=* r:|=*'
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"

# OpenClaw completion
if [[ -f "$HOME/.openclaw/completions/openclaw.zsh" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.openclaw/completions/openclaw.zsh"
fi

# --- Better history behavior ---
HISTFILE="$HOME/.zsh_history"
HISTSIZE=100000
SAVEHIST=100000
setopt APPEND_HISTORY
setopt INC_APPEND_HISTORY
setopt SHARE_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_FIND_NO_DUPS
setopt HIST_REDUCE_BLANKS
setopt EXTENDED_HISTORY

# --- fzf: Ctrl+R fuzzy history + completions ---
typeset -a fzf_key_binding_candidates fzf_completion_candidates

fzf_key_binding_candidates=()
fzf_completion_candidates=()

if [[ -n "${BREW_PREFIX}" ]]; then
  fzf_key_binding_candidates+=("$BREW_PREFIX/opt/fzf/shell/key-bindings.zsh")
  fzf_completion_candidates+=("$BREW_PREFIX/opt/fzf/shell/completion.zsh")
fi

fzf_key_binding_candidates+=(
  /usr/share/fzf/key-bindings.zsh
  /usr/share/doc/fzf/examples/key-bindings.zsh
)

fzf_completion_candidates+=(
  /usr/share/fzf/completion.zsh
  /usr/share/doc/fzf/examples/completion.zsh
)

for fzf_file in "${fzf_key_binding_candidates[@]}"; do
  if [[ -f "$fzf_file" ]]; then
    source "$fzf_file"
    break
  fi
done

for fzf_file in "${fzf_completion_candidates[@]}"; do
  if [[ -f "$fzf_file" ]]; then
    source "$fzf_file"
    break
  fi
done

unset fzf_key_binding_candidates fzf_completion_candidates fzf_file

# --- z command via zoxide ---
if command -v zoxide >/dev/null 2>&1; then
  eval "$(zoxide init zsh --cmd z)"
fi

# --- Shell power pack ---
ZSH_AUTOSUGGEST_STRATEGY=(history completion)
ZSH_AUTOSUGGEST_HIGHLIGHT_STYLE='fg=8'
if [[ -n "${BREW_PREFIX}" && -f "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh" ]]; then
  source "$BREW_PREFIX/share/zsh-autosuggestions/zsh-autosuggestions.zsh"
fi

# Make Option/Alt+Backspace reliably delete the previous word, including over
# SSH to hosts with older/default Zsh keymaps.
bindkey -M emacs '^[^?' backward-kill-word
bindkey -M emacs '^[^H' backward-kill-word
bindkey -M viins '^[^?' backward-kill-word
bindkey -M viins '^[^H' backward-kill-word

# Make Option/Alt+Arrow move by word across terminals that either send Meta+b/f
# or xterm-style modified arrow sequences.
bindkey -M emacs '^[b' backward-word
bindkey -M emacs '^[f' forward-word
bindkey -M emacs '^[[1;3D' backward-word
bindkey -M emacs '^[[1;3C' forward-word
bindkey -M emacs '^[[1;9D' backward-word
bindkey -M emacs '^[[1;9C' forward-word
bindkey -M viins '^[b' backward-word
bindkey -M viins '^[f' forward-word
bindkey -M viins '^[[1;3D' backward-word
bindkey -M viins '^[[1;3C' forward-word
bindkey -M viins '^[[1;9D' backward-word
bindkey -M viins '^[[1;9C' forward-word

# --- Prompt (fast, fish-like, left-only) ---
autoload -Uz vcs_info add-zsh-hook
zstyle ':vcs_info:*' enable git
zstyle ':vcs_info:*' check-for-changes false
zstyle ':vcs_info:git:*' use-simple true
zstyle ':vcs_info:git:*' formats ' %F{magenta}(%b)%f'
zstyle ':vcs_info:git:*' actionformats ' %F{magenta}(%b|%a)%f'

_folded_pwd() {
  local p="${PWD/#$HOME/~}"
  local prefix=""
  local -a parts out
  local i n part

  [[ "$p" == "/" ]] && { print -r -- "/"; return; }
  [[ "$p" == /* ]] && prefix="/"

  parts=(${(s:/:)p})
  n=${#parts}
  for (( i = 1; i <= n; i++ )); do
    part="${parts[i]}"
    [[ -z "$part" ]] && continue

    if (( i < n )); then
      if [[ "$part" == "~" ]]; then
        out+=("~")
      else
        out+=("${part[1,1]}")
      fi
    else
      out+=("$part")
    fi
  done

  print -r -- "${prefix}${(j:/:)out}"
}

precmd_prompt() {
  vcs_info
  PROMPT_PATH="$(_folded_pwd)"
  if [[ -n "$SSH_CONNECTION" || -n "$SSH_TTY" ]]; then
    PROMPT_USERHOST='%F{green}%n@%m%f '
  else
    PROMPT_USERHOST=''
  fi
}
add-zsh-hook precmd precmd_prompt

setopt PROMPT_SUBST
PROMPT='${PROMPT_USERHOST}%F{blue}${PROMPT_PATH}%f${vcs_info_msg_0_} %F{blue}%(!.#.>)%f '
RPROMPT=''

# Keep syntax highlighting last
if [[ -n "${BREW_PREFIX}" && -f "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh" ]]; then
  source "$BREW_PREFIX/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
fi

JETBRAINS_APP_PATH="/Applications/IntelliJ IDEA.app/Contents/MacOS"
if [[ -d "$JETBRAINS_APP_PATH" ]]; then
  path=(${path:#$JETBRAINS_APP_PATH} "$JETBRAINS_APP_PATH")
  export PATH
fi

# Local, machine-specific overrides.
if [[ -o interactive ]]; then
  alias cy='codex --yolo'
fi

if [[ -f "$HOME/.zshrc.local" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.zshrc.local"
fi
