---
name: obsidian-markdown
description: Create and edit Obsidian Flavored Markdown with internal links, embeds, callouts, properties, tags, and comments. Use for Markdown files in an Obsidian vault or when the user requests Obsidian-specific syntax.
---

# Obsidian Flavored Markdown

Use standard Markdown normally and add only the Obsidian extensions the note needs. Preserve the vault's existing conventions for properties, internal-link style, folders, and attachment paths.

## Internal Links

```markdown
[[Note Name]]
[[Note Name|Display Text]]
[[Note Name#Heading]]
[[Note Name#^block-id]]
[[#Heading in same note]]
```

Use wikilinks when the vault already prefers them or the user requests them. Otherwise preserve the surrounding link style. Define a paragraph block target by appending `^block-id`; for lists and quotes, place the block ID on a separate line after the block.

## Embeds

```markdown
![[Note Name]]
![[Note Name#Heading]]
![[image.png|300]]
![[document.pdf#page=3]]
```

Read [EMBEDS.md](references/EMBEDS.md) for less common media and embed forms.

## Callouts

```markdown
> [!note] Optional title
> Callout content.

> [!warning]- Collapsed by default
> Foldable content.
```

Read [CALLOUTS.md](references/CALLOUTS.md) for supported types, aliases, nesting, and custom callouts.

## Properties and Tags

Add YAML properties only when the note or vault conventions call for them:

```yaml
---
tags:
  - project
aliases:
  - Alternative Name
---
```

Read [PROPERTIES.md](references/PROPERTIES.md) for property types and syntax. Preserve existing property names and value shapes unless the user requests a schema change.

Inline tags use `#tag` or `#nested/tag`. Avoid inventing new tags when an established vault taxonomy exists.

## Comments

```markdown
Visible text %%hidden text%%.

%%
Hidden block.
%%
```

After editing, validate frontmatter and inspect the rendered note when layout or Obsidian-specific syntax materially matters.
