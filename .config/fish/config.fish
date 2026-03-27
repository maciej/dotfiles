set -gx HOMEBREW_NO_ENV_HINTS 1
set -gx DOCKER_CLI_HINTS false

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

fish_add_path "$HOME/go/bin"
fish_add_path /opt/homebrew/sbin
fish_add_path /opt/homebrew/bin
fish_add_path "$HOME/.local/bin"

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
set -x LC_ALL en_US.UTF-8
set -x LC_TIME pl_PL.UTF-8

if test (uname -s) = Darwin
    set -l intellij_bin "/Applications/IntelliJ IDEA.app/Contents/MacOS"
    if test -d "$intellij_bin"
        fish_add_path "$intellij_bin"
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

# Cloudflare WARP certs (harmless no-op when file is absent).
if test -f "$HOME/.local/share/cloudflare-warp-certs/config.fish"
    source "$HOME/.local/share/cloudflare-warp-certs/config.fish"
end

if status is-interactive
    # Commands to run in interactive sessions can go here
    if not set -q TMUX
        and command -q tmux
        and test -r /proc/device-tree/model
        and string match -qi '*raspberry pi*' (cat /proc/device-tree/model)
        exec tmux
    end
end

# Local, machine-specific overrides.
if test -f "$HOME/.config/fish/config.local.fish"
    source "$HOME/.config/fish/config.local.fish"
end

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH
