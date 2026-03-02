if status is-interactive
    # Commands to run in interactive sessions can go here
end

set -gx HOMEBREW_NO_ENV_HINTS 1

if test -d "$HOME/go/bin"; and not contains -- "$HOME/go/bin" $PATH
    set -gx PATH "$HOME/go/bin" $PATH
end

if test -d "$HOME/.local/bin"; and not contains -- "$HOME/.local/bin" $PATH
    set -gx PATH "$HOME/.local/bin" $PATH
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
    if command -q nvim
        set -gx EDITOR nvim
        set -gx VISUAL nvim
    else if command -q vim
        set -gx EDITOR vim
        set -gx VISUAL vim
    end
else
    if command -q zed
        set -gx EDITOR "zed --wait"
        set -gx VISUAL "zed --wait"
    else if command -q nvim
        set -gx EDITOR nvim
        set -gx VISUAL nvim
    else if command -q vim
        set -gx EDITOR vim
        set -gx VISUAL vim
    end
end

set -x LANG en_US.UTF-8
set -x LC_ALL en_US.UTF-8
set -x LC_TIME pl_PL.UTF-8

if test (uname -s) = Darwin
    if test -d "/Applications/IntelliJ IDEA.app/Contents/MacOS"; and not contains -- "/Applications/IntelliJ IDEA.app/Contents/MacOS" $PATH
        set -gx PATH "/Applications/IntelliJ IDEA.app/Contents/MacOS" $PATH
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
