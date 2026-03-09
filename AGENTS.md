# AGENTS.md

## Dotfiles & Stow
- This repo is Stow-managed. Only commit paths that should be symlinked into `$HOME` unless they are explicitly ignored.
- If you add a repo-only path that should not be stowed into `$HOME` (for example `README` files, helper scripts, repo metadata, or top-level utility directories), add it to `.stow-local-ignore` in the same change.
- Do not treat every non-dotfile as ignorable: files inside dot-directories such as `.config/...` are often valid Stow payload and should stay tracked normally.
