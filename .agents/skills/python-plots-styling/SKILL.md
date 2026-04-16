---
name: python-plots-styling
description: Use when creating or restyling Python plots to follow Catppuccin themes with seaborn and matplotlib, especially when both dark and light variants are needed.
---

# Python Plot Styling

Use this skill when a repo's Python plots should share a consistent Catppuccin look without adding unnecessary abstraction.

## Core Guidance

- Prefer `seaborn` theme setup plus Catppuccin's matplotlib style instead of scattered `rcParams` tweaks.
- Use `macchiato` for dark plots and `latte` for light plots unless the repo already has a different convention.
- Keep plot titles and base filenames theme-agnostic when generating multiple variants. Separate outputs by directory or caller-provided path rather than baking the theme into the plot name.
- When chart-specific colors are needed, derive them from the selected Catppuccin palette and give them semantic local names instead of inlining hex values.
- Keep plotting code direct and minimal. Add helpers only when theme selection, annotations, or export behavior is repeated.

## Baseline Pattern

```python
import catppuccin
import matplotlib.style as mpl_style
import seaborn as sns

def set_plot_theme(flavor: str = "macchiato"):
    palette = getattr(catppuccin.PALETTE, flavor)
    sns.set_theme(style="whitegrid", context="notebook")
    mpl_style.use(palette.identifier)
    return palette
```

Use the returned palette for semantic chart colors such as `palette.colors.blue.hex` or `palette.colors.red.hex`.

## Dependencies

- If the project already uses `uv` and `pyproject.toml`, add or update `catppuccin[matplotlib]`, `matplotlib`, and `seaborn` there as part of the styling change.
- Run Python entrypoints with `uv run` when the repo uses `uv`.

## Validation

- Run the plotting script or test that produces the figures.
- Check that the generated plots render successfully and that text, gridlines, and data marks remain legible in each requested theme.
