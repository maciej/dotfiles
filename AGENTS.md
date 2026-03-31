# AGENTS.md

## Dotfiles
- When searching this repo for files or directories, include dotfiles by default and use tools or flags that do not hide them.

## Dotfiles & Stow
- This repo is Stow-managed. Only commit paths that should be symlinked into `$HOME` unless they are explicitly ignored.
- If you add a repo-only path that should not be stowed into `$HOME` (for example `README` files, helper scripts, repo metadata, or top-level utility directories), add it to `.stow-local-ignore` in the same change.
- `.stow-local-ignore` entries are Stow Perl regexes, not gitignore globs.
- For top-level-only repo paths, use exact root-anchored regexes such as `^/README\.md$` or `^/scripts$`, and escape literal `.` characters so nested payloads such as `.config/.../scripts/...` are not excluded accidentally.
- A package-local `.stow-local-ignore` replaces Stow's built-in ignore list rather than extending it, so preserve any default ignores you still need by re-declaring them explicitly and do not add default patterns that are intentional payloads in this repo such as `.gitignore`.
- Do not treat every non-dotfile as ignorable: files inside dot-directories such as `.config/...` are often valid Stow payload and should stay tracked normally.
- If you remove a previously stowed path from the repo, update `LEGACY_STOW_PATHS` in `install.sh` in the same change.
- Only keep entries there for paths that are no longer present anywhere in this repo.

## Git
- Escape backticks in shell-quoted git commit messages, or avoid them entirely, so the shell does not perform command substitution.

## Privacy
- Do not include or repeat real machine or host names in tracked files, comments, docs, commit messages, GitHub issues, issue comments, or AGENT-facing instructions. Use generic labels such as `macOS host`, `Linux host`, or `Raspberry Pi`.
