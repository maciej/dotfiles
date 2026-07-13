---
name: obsidian-bases
description: Create and edit Obsidian Bases (.base files) with filters, formulas, properties, summaries, and views. Use for database-like views of notes or when the user requests Obsidian Bases, table, card, list, or map configurations.
---

# Obsidian Bases

Preserve the vault's existing property names and Base conventions. Use the smallest configuration that satisfies the requested view.

## Workflow

1. Inspect relevant notes and existing `.base` files to learn the available properties and local conventions.
2. Define global or view-specific filters for the intended note set.
3. Add formulas only for values that must be computed.
4. Configure the requested views and display order.
5. Parse the file as YAML, verify every referenced property and formula, and open it in Obsidian when rendered behavior matters.

## Minimal Shape

```yaml
filters:
  and:
    - 'file.hasTag("task")'
    - 'status != "done"'

formulas:
  days_until_due: 'if(due, (date(due) - today()).days, "")'

properties:
  formula.days_until_due:
    displayName: "Days Until Due"

views:
  - type: table
    name: "Active Tasks"
    order:
      - file.name
      - status
      - due
      - formula.days_until_due
```

Omit unused top-level sections. Global filters apply to every view; a view may add its own `filters`, `groupBy`, `order`, `summaries`, or `limit`.

Define custom summaries at the top level, then map displayed properties to built-in or custom summary names in a view:

```yaml
summaries:
  mean_3dp: 'values.mean().round(3)'

views:
  - type: table
    summaries:
      score: mean_3dp
      estimate: Average
```

## Expressions

- Refer to note properties as `property_name` or `note.property_name`.
- Use `file.name`, `file.path`, `file.folder`, `file.ext`, `file.ctime`, `file.mtime`, `file.tags`, and related file properties for metadata.
- Refer to computed values as `formula.name`, and define each one under `formulas`.
- Use a single expression string or a recursive filter object containing exactly one of `and`, `or`, or `not`; nest objects to combine them.
- Guard optional properties with `if()`.

`this` refers to the Base file in the main content area, the embedding note when the Base is embedded, or the active main-content file when the Base is in the sidebar.

Subtracting dates returns a Duration, not a number. Access a numeric field before number operations:

```yaml
formulas:
  age_days: '(now() - file.ctime).days'
  days_until_due: 'if(due, (date(due) - today()).days, "")'
```

Read [FUNCTIONS_REFERENCE.md](references/FUNCTIONS_REFERENCE.md) only when the requested formula needs a function or type not covered here.

## Views

Use `table`, `cards`, or `list` according to the requested presentation. Use `map` only when the vault has the required map support and latitude/longitude properties.

Specify only meaningful displayed properties:

```yaml
views:
  - type: cards
    name: "Library"
    order:
      - cover
      - file.name
      - author
```

## Quoting and Validation

- Quote expressions and strings containing YAML-special characters.
- Prefer single quotes around formulas that contain double-quoted string literals.
- Verify YAML syntax, formula names, view types, filter expressions, and property references.
- Treat a Base that parses but renders an error as invalid; inspect the Obsidian error before changing syntax blindly.

Official references:

- [Bases syntax](https://help.obsidian.md/bases/syntax)
- [Functions](https://help.obsidian.md/bases/functions)
- [Views](https://help.obsidian.md/bases/views)
- [Formulas](https://help.obsidian.md/formulas)
