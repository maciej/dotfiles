function __gsd_prompt_git_refresh
    set -g __gsd_prompt_git_segment ""
    set -g __gsd_prompt_git_root ""
    set -g __gsd_prompt_git_pwd $PWD
    set -g __gsd_prompt_git_dirty 0

    set -l status_lines (command git status --porcelain=v2 --branch --untracked-files=no 2> /dev/null)
    or return

    set -g __gsd_prompt_git_root (command git rev-parse --show-toplevel 2> /dev/null)

    set -l branch ""
    set -l touched 0
    set -l ahead 0
    set -l behind 0

    for line in $status_lines
        if string match -qr '^# branch.head ' -- $line
            set branch (string replace '# branch.head ' '' -- $line)
        else if string match -qr '^# branch.ab ' -- $line
            set -l ab (string replace '# branch.ab ' '' -- $line)
            set -l ab_parts (string split ' ' -- $ab)
            if test (count $ab_parts) -eq 2
                set ahead (string replace '+' '' -- $ab_parts[1])
                set behind (string replace '-' '' -- $ab_parts[2])
            end
        else if test -n "$line"
            set touched 1
        end
    end

    test -z "$branch"; and set branch "?"

    set -l marker "◦"
    if test $touched -eq 1
        set marker "⨯"
    else if test "$ahead" -gt 0; and test "$behind" -gt 0
        set marker "⥄"
    else if test "$ahead" -gt 0
        set marker "↑"
    else if test "$behind" -gt 0
        set marker "↓"
    end

    set -g __gsd_prompt_git_segment "$branch $marker"
end

function __gsd_prompt_git_on_pwd_change --on-variable PWD
    set -g __gsd_prompt_git_dirty 1
end

function __gsd_prompt_git_on_postexec --on-event fish_postexec
    set -l cmd (string trim -- $argv[1])
    if test -n "$cmd"; and string match -qr '^(git|gh|hub)\b' -- $cmd
        set -g __gsd_prompt_git_dirty 1
    end
end

function fish_prompt
    set -l last_command_status $status
    set -l cwd

    if test "$theme_short_path" = 'yes'
        set cwd (basename (prompt_pwd))
    else
        set cwd (prompt_pwd)
    end

    set -l fish     "⋊>"

    set -l normal_color     (set_color normal)
    set -l success_color    (set_color cyan)
    set -l error_color      (set_color $fish_color_error 2> /dev/null; or set_color red --bold)
    set -l directory_color  (set_color $fish_color_quote 2> /dev/null; or set_color brown)
    set -l repository_color (set_color $fish_color_cwd 2> /dev/null; or set_color green)

    set -l prompt_string $fish

    if test "$theme_ignore_ssh_awareness" != 'yes' -a -n "$SSH_CLIENT$SSH_TTY"
        set prompt_string "$fish "(whoami)"@"(hostname -s)" $fish"
    end

    if test $last_command_status -eq 0
        echo -n -s $success_color $prompt_string $normal_color
    else
        echo -n -s $error_color $prompt_string $normal_color
    end

    if test "$__gsd_prompt_git_pwd" != "$PWD" -o "$__gsd_prompt_git_dirty" = "1"
        __gsd_prompt_git_refresh
    end

    if test -n "$__gsd_prompt_git_segment"
        if test "$theme_short_path" = 'yes'; and test -n "$__gsd_prompt_git_root"
            set -l escaped_root (string escape --style=regex -- "$__gsd_prompt_git_root")
            set cwd (string replace -r "^$escaped_root/?" "" -- $PWD)
            if test -z "$cwd"
                set cwd (basename "$__gsd_prompt_git_root")
            end
        end

        echo -n -s " " $directory_color $cwd $normal_color
        echo -n -s " on " $repository_color $__gsd_prompt_git_segment $normal_color
    else
        echo -n -s " " $directory_color $cwd $normal_color
    end

    echo -n -s " "
end
