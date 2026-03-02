# Maciej's dotfiles

Simple dotfiles setup for my machines.

Inspired by Matt's repo: [elithrar/dotfiles](https://github.com/elithrar/dotfiles).

## Install

Run:

```sh
sh install.sh 2>&1 | tee ~/install.log
```

### Link dotfiles with Stow

This repo uses [GNU Stow](https://www.gnu.org/software/stow/manual/stow.html) to symlink tracked dotfiles into your home directory.

```sh
cd ~/repos/dotfiles
stow -v --restow .
```

You can also rerun this command after updates; it is idempotent.
