# Aliases
alias ls='ls -G'
alias ll='ls -lahG'

# Keep ANSI colors when paging with less.
if [[ -z "${LESS-}" ]]; then
  export LESS='-R -F -X'
else
  [[ " ${LESS} " != *" -R "* ]] && LESS="${LESS} -R"
  [[ " ${LESS} " != *" -F "* ]] && LESS="${LESS} -F"
  [[ " ${LESS} " != *" -X "* ]] && LESS="${LESS} -X"
  export LESS
fi

# Detect Homebrew prefix when available (macOS or Linuxbrew); empty elsewhere.
if command -v brew >/dev/null 2>&1; then
  BREW_PREFIX="$(brew --prefix)"
else
  BREW_PREFIX=""
fi

# zsh completion system (required before any script that calls compdef)
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
if [[ -n "${BREW_PREFIX}" && -f "$BREW_PREFIX/opt/fzf/shell/key-bindings.zsh" ]]; then
  source "$BREW_PREFIX/opt/fzf/shell/key-bindings.zsh"
fi
if [[ -n "${BREW_PREFIX}" && -f "$BREW_PREFIX/opt/fzf/shell/completion.zsh" ]]; then
  source "$BREW_PREFIX/opt/fzf/shell/completion.zsh"
fi

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

# Local, machine-specific overrides.
if [[ -f "$HOME/.zshrc.local" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.zshrc.local"
fi
