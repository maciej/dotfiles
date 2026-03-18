ensure_preferred_path_order

JETBRAINS_TOOLBOX_PATH="$HOME/Library/Application Support/JetBrains/Toolbox/scripts"
if [[ -d "$JETBRAINS_TOOLBOX_PATH" ]]; then
  path=(${path:#$JETBRAINS_TOOLBOX_PATH} "$JETBRAINS_TOOLBOX_PATH")
  export PATH
fi
