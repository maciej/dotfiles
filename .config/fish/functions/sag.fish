function sag --wraps sag
    if not command -q sag
        echo "sag: command not found. Install sag first." >&2
        return 127
    end

    if not set -q ELEVENLABS_API_KEY; and not set -q SAG_API_KEY
        if not set -q ELEVENLABS_API_KEY_FILE
            echo "sag: ELEVENLABS_API_KEY_FILE is not set. Expected $HOME/.config/sag/elevenlabs.key" >&2
            return 1
        end

        if not test -r "$ELEVENLABS_API_KEY_FILE"
            echo "sag: ELEVENLABS_API_KEY_FILE points to a missing or unreadable file: $ELEVENLABS_API_KEY_FILE" >&2
            return 1
        end

        set -l perms (stat -f %Lp "$ELEVENLABS_API_KEY_FILE" 2>/dev/null; or stat -c %a "$ELEVENLABS_API_KEY_FILE" 2>/dev/null)
        if test -n "$perms"
            set -l group_digit (string sub -s -2 -l 1 -- "$perms")
            set -l other_digit (string sub -s -1 -l 1 -- "$perms")
            if test "$group_digit" != 0; or test "$other_digit" != 0
                echo "sag: warning: $ELEVENLABS_API_KEY_FILE permissions are $perms; consider chmod 600 $ELEVENLABS_API_KEY_FILE" >&2
            end
        end
    end

    command sag $argv
end
