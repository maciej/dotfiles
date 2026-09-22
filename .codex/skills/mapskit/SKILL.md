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

### Location Scoping

Search places:

```bash
mapskit places search --limit 5 "coffee near Central Park"
mapskit places search --near 40.7812,-73.9665 --radius 2000 "coffee"
mapskit places search --rect 40.7000,-74.0200,40.8000,-73.9300 "coffee"
```

Text in the query does not scope the search. Use `--near <lat,lng> --radius
<metres>` (or a saved location name with stored coordinates) to set a circular
`locationBias`. This favors nearby results but does not exclude results outside
the circle. Use `--rect <sw_lat,sw_lng,ne_lat,ne_lng>` to set a hard rectangular
`locationRestriction`; only rectangles can restrict results.

`--near` and `--rect` are mutually exclusive. `--near` requires `--radius`, and
`--radius` cannot be used alone. A saved name passed to `--near` must contain
coordinates saved with `--lat` and `--lng`; an address-only entry fails with
guidance to add them.

### Place Details and Routes

Fetch details:

```bash
mapskit places info ChIJ...
```

Route between saved names, addresses, place IDs, or coordinates:

```bash
mapskit route Home "John F. Kennedy International Airport"
mapskit route --via "Penn Station" Home "John F. Kennedy International Airport"
mapskit route --polyline Home "John F. Kennedy International Airport"
```

Routes omit the encoded polyline by default to keep output small. Add
`--polyline` when geometry is needed. It appends
`routes.polyline.encodedPolyline` to the default field mask or to an explicit
`--fields` value.

### Manage Saved Locations

```bash
mapskit locations list
mapskit locations list --json
mapskit locations save Work "350 Fifth Avenue, New York, NY" --lat 40.7484 --lng -73.9857
mapskit locations save Venue --place-id ChIJ... --lat 40.7484 --lng -73.9857
mapskit locations get Home
mapskit locations rm Work
```

`locations list` preserves the name and address columns and appends `lat=`,
`lng=`, and `placeId=` when known. `locations list --json` emits a structured
array whose `lat`, `lng`, and `placeId` values are `null` when unknown.
`locations get` prints known coordinates and resolves `placeId` from either a
`--place-id` save or an address stored as `place:<id>`.

For the illustrative `Venue` entry above (`ChIJ...` is a placeholder), human
list output includes:

```text
Venue	place:ChIJ...	lat=40.748400	lng=-73.985700	placeId=ChIJ...
```

The corresponding JSON array entry contains `"lat": 40.7484`,
`"lng": -73.9857`, and `"placeId": "ChIJ..."`; an address-only entry has
`null` for all three fields.

Location reads never geocode. An address-only entry keeps unknown coordinates,
so do not assume every saved location can be used with `places search --near`.
The on-disk YAML format is unchanged and files written by earlier versions
continue to load.

For structured saved-location listings, use the subcommand form
`mapskit locations list --json`. The global form
`mapskit --json locations get NAME` emits the raw stored location mapping rather
than the normalized list schema.

## Location Syntax

For ad hoc route inputs, use:

- `place:<place-id>` or `places/<place-id>`
- `address:<address>`
- `<latitude>,<longitude>`
- plain text, which falls back to a Routes API address string

Use repeated `--via` flags for multiple intermediate stops. Do not request `--alternatives` with `--via`; the Routes API does not return alternatives when intermediates are present.

## Gotchas

Field-mask syntax is endpoint-specific:

- `places search --fields` requires the `places.` prefix, for example
  `places.id,places.displayName`.
- `places info --fields` requires unprefixed names, for example
  `id,displayName`.
- The wrong prefix produces an HTTP 400 `INVALID_ARGUMENT`. Unrecognized field
  names also surface as API errors; neither case silently falls back to defaults.

```bash
mapskit places search --fields places.id,places.displayName "coffee near Central Park"
mapskit places info --fields id,displayName ChIJ...
```

Replace `ChIJ...` with an actual place ID returned by search.

## Known Limitations

`route --detour` requests both the route with `--via` and a direct route, but
its comparability guard checks the Routes API `description`. That description
typically changes when an intermediate is present, so real routes often report
that the two results are not comparable instead of printing the detour cost.

`--detour` requires at least one `--via` waypoint:

```bash
mapskit route --detour --via Stop Home Destination
```

Here `Home`, `Stop`, and `Destination` stand for saved names or valid route inputs.

For a reliable comparison, run the direct and via routes separately and compare
their total distance and duration. The `--via` result also prints `leg 1`, `leg
2`, and subsequent legs for inspecting each segment:

```bash
mapskit route Home Destination
mapskit route --via Stop Home Destination
```
