# Maciej's dotfiles

Simple dotfiles setup for my machines.

Inspired by Matt's repo: [elithrar/dotfiles](https://github.com/elithrar/dotfiles).

### Editor preference

- Local sessions use **Zed** (`zed --wait`) as the default editor.
- SSH / non-GUI sessions use **NeoVim** as the terminal fallback (then Vim if Neovim is unavailable).

## Install

Run:

```sh
curl -fsSL https://raw.githubusercontent.com/maciej/dotfiles/main/install.sh | bash 2>&1 | tee ~/install.log
```

By default, the remote bootstrap installs into `~/.dotfiles`. Override with `DOTFILES_DIR` if you prefer a different destination.

### Link dotfiles with Stow

This repo uses [GNU Stow](https://www.gnu.org/software/stow/manual/stow.html) to symlink tracked dotfiles into your home directory.

```sh
cd ~/.dotfiles
stow -v --restow .
```

You can also rerun this command after updates; it is idempotent.
