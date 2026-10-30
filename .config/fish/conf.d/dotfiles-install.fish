# Register at startup: path-invoked scripts do not reliably autoload completions.
# Scope these options to the dotfiles installer, including relative paths.
function __fish_is_dotfiles_installer
    set -l tokens (commandline -opc)
    set -l installer (path resolve -- $tokens[1])
    test -f (path dirname -- "$installer")/src/dotfiles_install/__main__.py
end

complete -c install.sh -n __fish_is_dotfiles_installer -f
complete -c install.sh -n __fish_is_dotfiles_installer -l local -d 'Link dotfiles and install user-local tools only'
complete -c install.sh -n __fish_is_dotfiles_installer -l system -d 'Run a full system install and clear the local default'
complete -c install.sh -n __fish_is_dotfiles_installer -l no-local -d 'Alias for --system'
complete -c install.sh -n __fish_is_dotfiles_installer -l show-mode -d 'Print the effective mode and exit without installing'
complete -c install.sh -n __fish_is_dotfiles_installer -l with -r -a k8s -d 'Include an optional tool group'
complete -c install.sh -n __fish_is_dotfiles_installer -l upgrade -d 'Upgrade managed Helix and Codex CLI installations'
complete -c install.sh -n __fish_is_dotfiles_installer -l sync-zed-settings -d 'Regenerate Zed settings after linking dotfiles'
complete -c install.sh -n __fish_is_dotfiles_installer -l help -d 'Show help and exit'
