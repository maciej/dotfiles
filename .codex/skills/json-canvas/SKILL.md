---
name: json-canvas
description: Create and edit JSON Canvas (.canvas) files with text, file, link, and group nodes plus connecting edges. Use for Obsidian Canvas files, visual canvases, mind maps, flowcharts, and related JSON Canvas work.
---

# JSON Canvas

Follow the [JSON Canvas 1.0 specification](https://jsoncanvas.org/spec/1.0/) and preserve the style and layout of an existing canvas.

## Core Shape

```json
{
  "nodes": [],
  "edges": []
}
```

Every node needs a unique string `id`, a supported `type`, and integer `x`, `y`, `width`, and `height` fields. Type-specific content is:

- `text`: `text`
- `file`: `file`, optionally `subpath`
- `link`: `url`
- `group`: optionally `label`, `background`, and `backgroundStyle`

An edge needs a unique `id`, `fromNode`, and `toNode`. Optional routing fields include `fromSide`, `toSide`, `fromEnd`, `toEnd`, `color`, and `label`.

```json
{
  "nodes": [
    {
      "id": "6f0ad84f44ce9c17",
      "type": "text",
      "x": 0,
      "y": 0,
      "width": 320,
      "height": 160,
      "text": "# Start\n\nCanvas content"
    },
    {
      "id": "a1b2c3d4e5f67890",
      "type": "file",
      "x": 440,
      "y": 0,
      "width": 320,
      "height": 220,
      "file": "Notes/Details.md"
    }
  ],
  "edges": [
    {
      "id": "0123456789abcdef",
      "fromNode": "6f0ad84f44ce9c17",
      "fromSide": "right",
      "toNode": "a1b2c3d4e5f67890",
      "toSide": "left",
      "toEnd": "arrow"
    }
  ]
}
```

Use actual JSON newline escapes such as `\n` inside text strings. Do not double-escape them into visible backslash characters.

## Editing and Layout

1. Parse the existing JSON before editing.
2. Generate IDs that do not collide with any node or edge.
3. Position new content relative to the existing layout; avoid overlaps and preserve meaningful grouping.
4. Update only the requested nodes, edges, or layout region.
5. Parse and validate the completed file.

Array order controls z-order. Coordinates may be negative; `x` increases right and `y` increases down. Use consistent spacing and alignment as heuristics, not fixed requirements.

## Validation

Verify that:

- all node and edge IDs are unique;
- every edge endpoint references an existing node;
- every node has its required generic and type-specific fields;
- side and end values are supported by the specification;
- colors use supported preset or hexadecimal forms;
- the file is valid JSON.

Read [EXAMPLES.md](references/EXAMPLES.md) only when a complete mind map, project board, research canvas, or flowchart example would help.
