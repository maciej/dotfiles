function summarize --wraps summarize
    if not command -q summarize
        echo "summarize: command not found. Install summarize first." >&2
        return 127
    end

    if not set -q OPENAI_API_KEY
        if not set -q SUMMARIZE_OPENAI_API_KEY_FILE
            echo "summarize: SUMMARIZE_OPENAI_API_KEY_FILE is not set. Expected $HOME/.config/summarize/openai.key" >&2
            return 1
        end

        if not test -r "$SUMMARIZE_OPENAI_API_KEY_FILE"
            echo "summarize: SUMMARIZE_OPENAI_API_KEY_FILE points to a missing or unreadable file: $SUMMARIZE_OPENAI_API_KEY_FILE" >&2
            return 1
        end

        set -l perms (stat -f %Lp "$SUMMARIZE_OPENAI_API_KEY_FILE" 2>/dev/null; or stat -c %a "$SUMMARIZE_OPENAI_API_KEY_FILE" 2>/dev/null)
        if test -n "$perms"
            set -l group_digit (string sub -s -2 -l 1 -- "$perms")
            set -l other_digit (string sub -s -1 -l 1 -- "$perms")
            if test "$group_digit" != 0; or test "$other_digit" != 0
                echo "summarize: warning: $SUMMARIZE_OPENAI_API_KEY_FILE permissions are $perms; consider chmod 600 $SUMMARIZE_OPENAI_API_KEY_FILE" >&2
            end
        end

        set -l api_key
        if not read -l api_key < "$SUMMARIZE_OPENAI_API_KEY_FILE"; or test -z "$api_key"
            echo "summarize: SUMMARIZE_OPENAI_API_KEY_FILE is empty: $SUMMARIZE_OPENAI_API_KEY_FILE" >&2
            return 1
        end

        set -lx OPENAI_API_KEY "$api_key"
    end

    command summarize $argv
end
