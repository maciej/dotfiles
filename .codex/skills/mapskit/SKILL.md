---
name: mapskit
description: Use the globally installed MapsKit Google Maps Platform CLI for Places and Routes work. Trigger when Codex needs to search Google Maps places, fetch Place Details, calculate point-to-point or multi-hop routes, or manage saved locations such as Home without handling Google Maps API keys directly.
---

# MapsKit

Use the globally installed `mapskit` CLI:

```bash
mapskit --help
```

## Credentials

Do not open, print, summarize, or copy API key files. The CLI reads a plain-text Google Maps Platform API key from:

- `--api-key-file FILE`
- `MAPSKIT_API_KEY_FILE`
- default: `~/.config/mapskit/google-maps-platform.key`

The key is for Google Maps Platform APIs such as Places and Routes. Do not use encrypted secret-file lookup.

Verify that a key is available without printing it:

```bash
mapskit auth check
```

## Saved Locations

Saved locations default to `${XDG_CONFIG_HOME:-$HOME/.config}/mapskit/locations.yaml`. Override with `--locations-file` or `MAPSKIT_LOCATIONS_FILE` when a task needs an isolated file.

Prefer saved names for personal locations, and do not expose private addresses in examples, tracked files, or final responses unless the user explicitly asks.

## Common Tasks

Search places:

```bash
mapskit places search --limit 5 "coffee near Central Park"
```

Fetch details:

```bash
mapskit places info ChIJ...
```

Route between saved names, addresses, place IDs, or coordinates:

```bash
mapskit route Home "John F. Kennedy International Airport"
mapskit route --via "Penn Station" Home "John F. Kennedy International Airport"
```

Manage saved locations:

```bash
mapskit locations list
mapskit locations save Work "350 Fifth Avenue, New York, NY"
mapskit locations get Home
mapskit locations rm Work
```

Use `--json` when another tool or agent needs structured output.

## Location Syntax

For ad hoc route inputs, use:

- `place:<place-id>` or `places/<place-id>`
- `address:<address>`
- `<latitude>,<longitude>`
- plain text, which falls back to a Routes API address string

Use repeated `--via` flags for multiple intermediate stops. Do not request `--alternatives` with `--via`; the Routes API does not return alternatives when intermediates are present.
