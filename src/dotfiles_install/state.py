from __future__ import annotations

import os
from pathlib import Path

from .options import Options


DOTFILES_DIR = Path(
    os.environ.get("DOTFILES_DIR", Path(__file__).resolve().parents[2])
).resolve()
CURRENT_OPTIONS = Options()
