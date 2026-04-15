---
name: python-plots-styling
description: Set up or restyle Python plots to use seaborn with Catppuccin Macchiato styling. Use when asked to prepare a repo for styled Python plotting or adapt existing plots to this styling.
---

Use this pattern:

```python
import catppuccin
import matplotlib.style as mpl_style
import seaborn as sns

MACCHIATO = catppuccin.PALETTE.macchiato

def set_plot_theme() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    mpl_style.use(MACCHIATO.identifier)
```

When chart-specific colors are needed, derive them from `MACCHIATO.colors.*.hex` and give them semantic names instead of inlining hex values.

If the project already uses `uv` and `pyproject.toml` for dependency management, add or update `catppuccin[matplotlib]`, `matplotlib`, and `seaborn` there as part of the styling change. Run Python entrypoints with `uv run`.

Keep plotting code direct and minimal. Add helpers only for repeated theme or annotation logic.

Validate by running the plotting script and checking the generated plots.
