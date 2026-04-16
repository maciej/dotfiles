---
name: python-plots-styling
description: Set up or restyle Python plots to use seaborn with Catppuccin styling. Use when asked to prepare a repo for styled Python plotting or adapt plots to Catppuccin dark and light themes such as Macchiato and Latte.
---

Use this pattern:

```python
import catppuccin
import matplotlib.style as mpl_style
import seaborn as sns

def set_plot_theme(flavor: str = "macchiato") -> None:
    palette = getattr(catppuccin.PALETTE, flavor)
    sns.set_theme(style="whitegrid", context="notebook")
    mpl_style.use(palette.identifier)
```

Use `macchiato` for dark plots and `latte` for light plots.

When chart-specific colors are needed, derive them from the selected Catppuccin palette and give them semantic names instead of inlining hex values.

When generating both dark and light variants, keep the plot title and base filename theme-agnostic. Distinguish outputs by directory or caller-provided path instead of embedding the theme name in the plot name.

If the project already uses `uv` and `pyproject.toml` for dependency management, add or update `catppuccin[matplotlib]`, `matplotlib`, and `seaborn` there as part of the styling change. Run Python entrypoints with `uv run`.

Keep plotting code direct and minimal. Add helpers only for repeated theme or annotation logic.

Validate by running the plotting script and checking the generated plots.
