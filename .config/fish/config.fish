set -gx HOMEBREW_NO_ENV_HINTS 1
set -gx HOMEBREW_NO_ASK 1
set -gx DOCKER_CLI_HINTS false
set -gx GH_TELEMETRY false
set -gx CLAUDE_CODE_ENABLE_AUTO_MODE 1
set -gx OPENCODE_ENABLE_EXA 1
set -gx CODEX_HOME "$HOME/.codex"

# Keep ANSI colors when paging with less.
if not set -q LESS
    set -gx LESS "-R -F"
else
    set -l less_flags
    for flag in (string split ' ' -- $LESS)
        switch $flag
            case '' -X --mouse --wheel-lines='*'
                continue
            case '*'
                set less_flags $less_flags $flag
        end
    end
    for flag in -R -F
        if not contains -- $flag $less_flags
            set less_flags $less_flags $flag
        end
    end
    set -gx LESS (string join ' ' -- $less_flags)
end

fish_add_path "$HOME/.docker/bin"
fish_add_path "$HOME/go/bin"
fish_add_path /opt/homebrew/sbin
fish_add_path /opt/homebrew/bin
fish_add_path "$HOME/.opencode/bin"
fish_add_path "$HOME/.local/bin"
fish_add_path --path --append "$HOME/.cargo/bin"

if status is-interactive; and command -q wt
    command wt config shell init fish | source
    COMPLETE=fish command wt | source

    # Usage: _wt-agent <agent> [-b|--base <ref>] [suffix] [-- agent arguments]
    # wt-agent-switch parses the arguments and creates the worktree. The cd and
    # the agent launch stay here so this shell is already in the worktree while
    # the agent runs (wt -x would only cd the shell after the agent exits).
    function _wt-agent
        set -l agent $argv[1]
        set -e argv[1]
        set -l cd_file (mktemp); or return
        WORKTRUNK_DIRECTIVE_CD_FILE=$cd_file command wt-agent-switch $agent $argv
        set -l rc $status
        set -l target (cat $cd_file)
        command rm -f -- $cd_file
        test $rc -eq 0; or return $rc
        # No worktree path means --help ran; there is nothing to launch.
        test -n "$target"; or return 0
        builtin cd -- $target; or return
        set -l agent_args
        set -l dashdash (contains --index -- -- $argv)
        and set agent_args $argv[(math $dashdash + 1)..-1]
        command $agent $agent_args
    end

    # Usage: wt-codex [-b|--base <ref>] [suffix] [-- codex arguments]
    function wt-codex
        _wt-agent codex $argv
    end

    # Usage: wt-claude [-b|--base <ref>] [suffix] [-- claude arguments]
    function wt-claude
        _wt-agent claude $argv
    end

    function __wt_agent_after_dashdash
        contains -- -- (commandline --tokenize --cut-at-cursor)
    end

    # After --, complete as if the agent itself had been typed.
    function __wt_agent_complete_agent
        set -l tokens (commandline --tokenize --cut-at-cursor)
        set -l dashdash (contains --index -- -- $tokens)
        set -l agent (string replace -- wt- '' $tokens[1])
        set -l rest $tokens[(math $dashdash + 1)..-1]
        complete --do-complete (string join ' ' -- (string escape -- $agent $rest) (commandline --current-token))
    end

    for agent in codex claude
        complete -c wt-$agent -f
        complete -c wt-$agent -n 'not __wt_agent_after_dashdash' -s h -l help -d 'Show help'
        complete -c wt-$agent -n 'not __wt_agent_after_dashdash' -s b -l base -x \
            -a '(command wt-agent-switch --complete-base 2>/dev/null)' -d 'Ref to base the new branch on'
        complete -c wt-$agent -n __wt_agent_after_dashdash -a '(__wt_agent_complete_agent)'
    end
end

if command -q zoxide
    zoxide init fish | source
end

set -l in_ssh 0
if set -q SSH_TTY
    set in_ssh 1
else if set -q SSH_CONNECTION
    set in_ssh 1
else if set -q SSH_CLIENT
    set in_ssh 1
end

if test $in_ssh -eq 1
    if command -q hx
        set -gx EDITOR hx
        set -gx VISUAL hx
    else if command -q vim
        set -gx EDITOR vim
        set -gx VISUAL vim
    end
else
    if command -q zed
        set -gx EDITOR "$HOME/.local/bin/wait-zed"
        set -gx VISUAL "$HOME/.local/bin/wait-zed"
    else if command -q hx
        set -gx EDITOR hx
        set -gx VISUAL hx
    else if command -q vim
        set -gx EDITOR vim
        set -gx VISUAL vim
    end
end

set -x LANG en_US.UTF-8
set -x LC_TIME pl_PL.UTF-8

if test (uname -s) = Darwin
    if test -x /Applications/BambuStudio.app/Contents/MacOS/BambuStudio
        alias bambu-studio='/Applications/BambuStudio.app/Contents/MacOS/BambuStudio'
    end

    set -l intellij_bin "/Applications/IntelliJ IDEA.app/Contents/MacOS"
    if test -d "$intellij_bin"
        fish_add_path "$intellij_bin"
    end

    if test -d "/Applications/Brave Browser.app"; or test -d "$HOME/Applications/Brave Browser.app"
        alias brave-cdp='open -na "Brave Browser" --args --remote-debugging-port=9222 --user-data-dir="$HOME/Library/Application Support/BraveSoftware/Brave-Browser"'
    end
end

if test -f "$HOME/.config/sops/age/keys.txt"
    set -gx SOPS_AGE_KEY_FILE "$HOME/.config/sops/age/keys.txt"
end

functions -e fish_right_prompt

if command -q op
    op completion fish | source
end

set -l openclaw_completion "$HOME/.openclaw/completions/openclaw.fish"
if test -r "$openclaw_completion"
    source "$openclaw_completion"
end

if command -q himalaya
    function himalaya --wraps himalaya
        RUST_LOG=error command himalaya $argv
    end
end

if command -q opencode
    alias oc opencode
end

# Local, machine-specific overrides.
if test -f "$HOME/.config/fish/config.local.fish"
    source "$HOME/.config/fish/config.local.fish"
end

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH

# pnpm
set -gx PNPM_HOME "$HOME/Library/pnpm"
fish_add_path "$PNPM_HOME/bin"

if command -q sag
    set -gx ELEVENLABS_API_KEY_FILE "$HOME/.config/sag/elevenlabs.key"
end

if command -q summarize; and not set -q SUMMARIZE_OPENAI_API_KEY_FILE
    set -gx SUMMARIZE_OPENAI_API_KEY_FILE "$HOME/.config/summarize/openai.key"
end
