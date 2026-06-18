function __mlx_subtitles_seen_video_arg
    set -l skip_next 0

    for token in (commandline -opc)[2..-1]
        if test $skip_next -eq 1
            set skip_next 0
            continue
        end

        switch $token
            case -o --output --whisper-model --whisper-language --whisper-beam-size --whisper-patience --whisper-hallucination-silence-threshold --max-line-width --max-line-count
                set skip_next 1
                continue
            case '--output=*' '--whisper-model=*' '--whisper-language=*' '--whisper-beam-size=*' '--whisper-patience=*' '--whisper-hallucination-silence-threshold=*' '--max-line-width=*' '--max-line-count=*'
                continue
            case '-*'
                continue
            case '*'
                return 0
        end
    end

    return 1
end

function __mlx_subtitles_complete_any_path
    set -l token (commandline -ct)
    set -l dir .
    set -l base $token

    if string match -q -- '*/' $token
        set dir (string replace -r '/[^/]*$' '' -- $token)
        set base (string replace -r '^.*/' '' -- $token)
        test -z "$dir"; and set dir /
    else if string match -q -- '*/*' $token
        set dir (string replace -r '/[^/]*$' '' -- $token)
        set base (string replace -r '^.*/' '' -- $token)
    end

    for path in "$dir"/$base*
        test -e "$path"; or continue
        if test -d "$path"
            set path "$path/"
        end

        if test "$dir" = .
            string escape -- (string replace -r '^\\./' '' -- "$path")
        else
            string escape -- "$path"
        end
    end
end

function __mlx_subtitles_complete_path
    set -l token (commandline -ct)
    set -l dir .
    set -l base $token

    if string match -q -- '*/' $token
        set dir (string replace -r '/[^/]*$' '' -- $token)
        set base (string replace -r '^.*/' '' -- $token)
        test -z "$dir"; and set dir /
    else if string match -q -- '*/*' $token
        set dir (string replace -r '/[^/]*$' '' -- $token)
        set base (string replace -r '^.*/' '' -- $token)
    end

    set -l matches
    set -l video_exts 3g2 3gp avi flv m2ts m4v mkv mov mp4 mpeg mpg mts mxf ogv ts vob webm wmv

    for path in "$dir"/$base*
        test -e "$path"; or continue
        if test -d "$path"
            set matches $matches "$path/"
            continue
        end

        set -l extension (string lower -- (string replace -r '^.*\\.' '' -- "$path"))
        if contains -- $extension $video_exts
            set matches $matches "$path"
        end
    end

    if test (count $matches) -eq 0
        for path in "$dir"/$base*
            test -e "$path"; or continue
            if test -d "$path"
                set matches $matches "$path/"
            else
                set matches $matches "$path"
            end
        end
    end

    for match in $matches
        if test "$dir" = .
            string escape -- (string replace -r '^\\./' '' -- "$match")
        else
            string escape -- "$match"
        end
    end
end

complete -c mlx-subtitles -f
complete -c mlx-subtitles -s o -l output -r -a '(__mlx_subtitles_complete_any_path)' -d 'SRT output path'
complete -c mlx-subtitles -l whisper-model -r -a '(__mlx_subtitles_complete_any_path)' -d 'MLX Whisper model directory or Hugging Face repo'
complete -c mlx-subtitles -l whisper-language -r -d 'Spoken language code'
complete -c mlx-subtitles -l whisper-beam-size -r -d 'Beam size for temperature-0 decoding'
complete -c mlx-subtitles -l whisper-patience -r -d 'Patience value for beam decoding'
complete -c mlx-subtitles -l whisper-word-timestamps -d 'Use word-level timestamps'
complete -c mlx-subtitles -l no-whisper-word-timestamps -d 'Disable word-level timestamps'
complete -c mlx-subtitles -l whisper-hallucination-silence-threshold -r -d 'Silence threshold for hallucination skipping'
complete -c mlx-subtitles -l max-line-width -r -d 'Maximum subtitle line width'
complete -c mlx-subtitles -l max-line-count -r -d 'Maximum subtitle line count'
complete -c mlx-subtitles -l overwrite -d 'Overwrite existing SRT output'
complete -c mlx-subtitles -l help -d 'Show help and exit'
complete -c mlx-subtitles -n 'not __mlx_subtitles_seen_video_arg' -a '(__mlx_subtitles_complete_path)' -d 'video file'
