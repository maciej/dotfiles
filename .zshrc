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

  if [[ -z "${CLICOLOR_FORCE-}" && ! -t 1 ]]; then
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

# Worktrunk shell integration and completions.
if (( $+commands[wt] )); then
  eval "$(command wt config shell init zsh)"

  # Usage: _wt-agent <agent> <draft> [-b|--base <ref>] [suffix] [-- agent arguments]
  # wt-agent-switch parses the arguments and creates the worktree. The cd and
  # the agent launch stay here so this shell is already in the worktree while
  # the agent runs (wt -x would only cd the shell after the agent exits).
  _wt-agent() {
    local agent=$1 draft=$2 cd_file target rc=0
    shift 2
    cd_file=$(mktemp) || return
    WORKTRUNK_DIRECTIVE_CD_FILE=$cd_file command wt-agent-switch "$agent" "$@" || rc=$?
    target=$(<"$cd_file")
    command rm -f -- "$cd_file"
    (( rc == 0 )) || return $rc
    # No worktree path means --help ran; there is nothing to launch.
    [[ -n $target ]] || return 0
    builtin cd -- "$target" || return
    if [[ -z $draft ]]; then
      command "$agent" "${(@)argv[${argv[(i)--]}+1,-1]}"
    elif [[ $agent == claude ]]; then
      command claude --prefill "$draft"
    else
      command codex-paste-draft "$draft"
    fi
  }

  # Usage: wt-codex [-b|--base <ref>] [suffix] [-- codex arguments]
  wt-codex() { _wt-agent codex '' "$@"; }

  # Usage: wt-claude [-b|--base <ref>] [suffix] [-- claude arguments]
  wt-claude() { _wt-agent claude '' "$@"; }

  review-pr() {
    emulate -L zsh
    setopt extendedglob
    local usage='Usage: review-pr [--claude] <GitHub pull request URL>'
    local agent=codex
    if [[ ${1-} == --claude ]]; then
      agent=claude
      shift
    fi
    local pr_pattern='^https://github[.]com/([a-zA-Z0-9-]{1,39})/([a-zA-Z0-9_.-]{1,100})/pull/([1-9][0-9]{0,19})([/?#].*)?$'
    local remote_pattern='^(https://([^/@[:space:]]+@)?github[.]com(:443)?/|ssh://git@(github[.]com(:22)?|ssh[.]github[.]com:443)/|git@github[.]com:)(.+)$'
    if (( $# == 1 )) && [[ $1 == -h || $1 == --help ]]; then
      print -r -- "$usage"
      return 0
    fi
    if (( $# != 1 )) || [[ ! $1 =~ $pr_pattern || $match[2] == . || $match[2] == .. ]]; then
      print -ru2 -- "$usage"
      return 2
    fi
    local owner=$match[1] project=$match[2] number=$match[3]
    local slug=${(L)owner}/${(L)project}
    local url="https://github.com/$owner/$project/pull/$number"
    local code_root=${AGENT_REVIEW_CODE_ROOT:-$HOME/code}
    # Prefer an exact spelling within each layout, then match directory names
    # case-insensitively, as GitHub does. The remotes still determine identity.
    local -aU checkouts=(
      "$code_root/$project" "$code_root"/(#i)"$project"(N-/)
      "$code_root/$owner/$project" "$code_root"/(#i)"$owner"/"$project"(N-/)
    )
    local checkout repo_root remote fetch_url remote_slug
    for checkout in "${checkouts[@]}"; do
      repo_root=$(command git -C "$checkout" rev-parse --show-toplevel 2>/dev/null) || continue
      [[ ${repo_root:A} == ${checkout:A} ]] || continue
      for remote in ${(f)"$(command git -C "$checkout" remote)"}; do
        fetch_url=$(command git -C "$checkout" remote get-url -- "$remote") || continue
        [[ ${(L)fetch_url} =~ $remote_pattern ]] || continue
        remote_slug=${match[-1]%/}
        [[ ${remote_slug%.git} == $slug ]] && break 2
      done
      remote=''
    done
    if [[ -z $remote ]]; then
      print -ru2 -- "review-pr: no checkout of $owner/$project found under $code_root"
      return 1
    fi
    if [[ ! -t 0 || ! -t 1 ]]; then
      print -ru2 -- 'review-pr: an interactive terminal is required'
      return 1
    fi
    if (( ! $+commands[$agent] )); then
      print -ru2 -- "review-pr: $agent is required"
      return 1
    fi
    if [[ $agent == codex ]] && (( ! $+commands[codex-paste-draft] )); then
      print -ru2 -- 'review-pr: codex-paste-draft is required'
      return 1
    fi

    local draft="This worktree is at the head of $url.

Explain and review the PR."
    local nonce branch review_ref head
    nonce=$(command openssl rand -hex 6) || return
    branch="review-$number-$nonce"
    review_ref="refs/codex/reviews/$branch"
    # review-pr assumes the repository and its PRs are trusted. Git and Worktrunk
    # hooks can run during worktree setup. Codex and Claude manage workspace trust
    # and can inherit it from the main checkout. Trusted project settings can
    # start processes before the draft is submitted.
    # A per-run ref keeps parallel fetches from sharing FETCH_HEAD.
    {
      command git -C "$checkout" fetch --no-tags --no-write-fetch-head --no-recurse-submodules \
        -- "$remote" "refs/pull/$number/head:$review_ref" || return
      head=$(command git -C "$checkout" rev-parse --verify "$review_ref^{commit}") || return
      builtin cd -- "$checkout" || return
      _wt-agent "$agent" "$draft" --base "$head" "$branch"
    } always {
      command git -C "$repo_root" update-ref -d "$review_ref"
    }
  }

  _wt-agent-base-refs() {
    local -a refs
    refs=(${${(f)"$(command wt-agent-switch --complete-base 2>/dev/null)"}/$'\t'/:})
    _describe -t base-refs 'base ref' refs
  }

  _wt-agent-complete() {
    # After --, complete as if the agent itself had been typed.
    local dashdash=${words[(i)--]}
    if (( dashdash < CURRENT )); then
      words=("${words[1]#wt-}" "${(@)words[dashdash+1,-1]}")
      (( CURRENT -= dashdash - 1 ))
      _normal
      return
    fi
    _arguments -s -S : \
      '(- : *)'{-h,--help}'[show help]' \
      '(-b --base)'{-b+,--base=}'[ref to base the new branch on]:base ref:_wt-agent-base-refs' \
      '1:new branch name (random if omitted): '
  }
  compdef _wt-agent-complete wt-codex wt-claude
fi

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

if [[ -x /Applications/BambuStudio.app/Contents/MacOS/BambuStudio ]]; then
  alias bambu-studio='/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'
fi

JETBRAINS_APP_PATH="/Applications/IntelliJ IDEA.app/Contents/MacOS"
if [[ -d "$JETBRAINS_APP_PATH" ]]; then
  path=(${path:#$JETBRAINS_APP_PATH} "$JETBRAINS_APP_PATH")
  export PATH
fi

export PNPM_HOME="$HOME/Library/pnpm"
path=(${path:#$PNPM_HOME/bin} "$PNPM_HOME/bin")
export PATH

if (( $+commands[sag] )); then
  export ELEVENLABS_API_KEY_FILE="${ELEVENLABS_API_KEY_FILE:-$HOME/.config/sag/elevenlabs.key}"
  typeset -g _sag_command="${commands[sag]}"

  sag() {
    local key_file="${ELEVENLABS_API_KEY_FILE:-}"

    if [[ -z "${ELEVENLABS_API_KEY:-}" && -z "${SAG_API_KEY:-}" ]]; then
      if [[ -z "$key_file" ]]; then
        print -u2 "sag: ELEVENLABS_API_KEY_FILE is not set. Expected $HOME/.config/sag/elevenlabs.key"
        return 1
      fi

      if [[ ! -r "$key_file" ]]; then
        print -u2 "sag: ELEVENLABS_API_KEY_FILE points to a missing or unreadable file: $key_file"
        return 1
      fi

      local perms
      perms="$(stat -f %Lp "$key_file" 2>/dev/null || stat -c %a "$key_file" 2>/dev/null)"
      if [[ -n "$perms" && ( "${perms[-2]}" != "0" || "${perms[-1]}" != "0" ) ]]; then
        print -u2 "sag: warning: $key_file permissions are $perms; consider chmod 600 $key_file"
      fi
    fi

    command "$_sag_command" "$@"
  }
fi

if (( $+commands[summarize] )); then
  export SUMMARIZE_OPENAI_API_KEY_FILE="${SUMMARIZE_OPENAI_API_KEY_FILE:-$HOME/.config/summarize/openai.key}"
  typeset -g _summarize_command="${commands[summarize]}"

  summarize() {
    local key_file="${SUMMARIZE_OPENAI_API_KEY_FILE:-}"

    if [[ -z "${OPENAI_API_KEY:-}" ]]; then
      if [[ -z "$key_file" ]]; then
        print -u2 "summarize: SUMMARIZE_OPENAI_API_KEY_FILE is not set. Expected $HOME/.config/summarize/openai.key"
        return 1
      fi

      if [[ ! -r "$key_file" ]]; then
        print -u2 "summarize: SUMMARIZE_OPENAI_API_KEY_FILE points to a missing or unreadable file: $key_file"
        return 1
      fi

      local perms
      perms="$(stat -f %Lp "$key_file" 2>/dev/null || stat -c %a "$key_file" 2>/dev/null)"
      if [[ -n "$perms" && ( "${perms[-2]}" != "0" || "${perms[-1]}" != "0" ) ]]; then
        print -u2 "summarize: warning: $key_file permissions are $perms; consider chmod 600 $key_file"
      fi

      local api_key
      api_key="$(<"$key_file")"
      if [[ -z "$api_key" ]]; then
        print -u2 "summarize: SUMMARIZE_OPENAI_API_KEY_FILE is empty: $key_file"
        return 1
      fi

      OPENAI_API_KEY="$api_key" command "$_summarize_command" "$@"
      return
    fi

    command "$_summarize_command" "$@"
  }
fi

# Codex needs terminal forwarding when a macOS Rex host has a native clipboard.
if [[ $OSTYPE == darwin* && -n ${REX_SESSION:-} && -n ${REX_BLOCK:-} ]]; then
  codex() {
    HERDR_ENV=1 command codex "$@"
  }
fi

# Local, machine-specific overrides.
if [[ -o interactive ]]; then
  alias cy='codex --yolo'
  alias oc='opencode'
fi

if [[ -f "$HOME/.zshrc.local" ]]; then
  # shellcheck source=/dev/null
  source "$HOME/.zshrc.local"
fi
