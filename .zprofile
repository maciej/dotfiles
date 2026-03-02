# Load shared PATH setup.
if [[ -f "$HOME/.shell_paths" ]]; then
  # shellcheck source=/dev/null
  . "$HOME/.shell_paths"
fi

JETBRAINS_TOOLBOX_PATH="$HOME/Library/Application Support/JetBrains/Toolbox/scripts"
if [[ -d "$JETBRAINS_TOOLBOX_PATH" ]]; then
  export PATH="$PATH:$JETBRAINS_TOOLBOX_PATH"
fi
