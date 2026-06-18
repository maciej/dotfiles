from __future__ import annotations

import json
import os
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, TextIO

import typer
import yaml


DEFAULT_PLACES_SEARCH_FIELDS = (
    "places.id,places.name,places.displayName,places.formattedAddress,"
    "places.location,places.googleMapsUri,places.types,nextPageToken"
)
DEFAULT_PLACE_DETAILS_FIELDS = (
    "id,name,displayName,formattedAddress,location,googleMapsUri,businessStatus,"
    "types,primaryType,primaryTypeDisplayName,utcOffsetMinutes,websiteUri,"
    "internationalPhoneNumber,nationalPhoneNumber,rating,userRatingCount"
)
DEFAULT_ROUTE_FIELDS = (
    "routes.routeLabels,routes.distanceMeters,routes.duration,routes.staticDuration,"
    "routes.description,routes.warnings,routes.polyline.encodedPolyline,"
    "routes.legs.distanceMeters,routes.legs.duration,routes.legs.staticDuration,"
    "routes.legs.localizedValues,routes.optimizedIntermediateWaypointIndex,"
    "geocodingResults"
)

PLACES_SEARCH_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
PLACE_DETAILS_ENDPOINT = "https://places.googleapis.com/v1/places/"
ROUTES_ENDPOINT = "https://routes.googleapis.com/directions/v2:computeRoutes"

API_KEY_FILE_ENV = "MAPSKIT_API_KEY_FILE"
LOCATIONS_FILE_ENV = "MAPSKIT_LOCATIONS_FILE"
CONTEXT_SETTINGS = {"help_option_names": ["--help", "-h"]}


@dataclass
class AppConfig:
    api_key_file: Path
    locations_file: Path
    json: bool = False


class MapsKitError(Exception):
    pass


class GoogleClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search_text(self, body: dict[str, Any], field_mask: str) -> dict[str, Any]:
        return self._request_json("POST", PLACES_SEARCH_ENDPOINT, body, field_mask)

    def place_details(
        self, place_id: str, field_mask: str, language: str, region: str
    ) -> dict[str, Any]:
        place_id = place_id.strip().removeprefix("places/")
        if not place_id:
            raise MapsKitError("empty place id")
        url = PLACE_DETAILS_ENDPOINT + urllib.parse.quote(place_id, safe="")
        params = {}
        if language:
            params["languageCode"] = language
        if region:
            params["regionCode"] = region
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request_json("GET", url, None, field_mask)

    def compute_routes(
        self, body: dict[str, Any], field_mask: str
    ) -> dict[str, Any]:
        return self._request_json("POST", ROUTES_ENDPOINT, body, field_mask)

    def _request_json(
        self,
        method: str,
        url: str,
        body: dict[str, Any] | None,
        field_mask: str,
    ) -> dict[str, Any]:
        if not self.api_key.strip():
            raise MapsKitError("missing Google Maps Platform API key")
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Content-Type", "application/json")
        request.add_header("X-Goog-Api-Key", self.api_key)
        if field_mask:
            request.add_header("X-Goog-FieldMask", compact_field_mask(field_mask))
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read(4096).decode("utf-8", errors="replace").strip()
            raise MapsKitError(f"google API returned {exc.code} {exc.reason}: {raw}") from exc
        except urllib.error.URLError as exc:
            raise MapsKitError(f"google API request failed: {exc.reason}") from exc


def main() -> None:
    app(prog_name="mapskit")


def run(argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    from typer.testing import CliRunner

    result = CliRunner().invoke(app, argv, color=False)
    stdout.write(result.stdout)
    stderr.write(result.stderr)
    return result.exit_code


def get_config(ctx: typer.Context) -> AppConfig:
    if not isinstance(ctx.obj, AppConfig):
        raise RuntimeError("mapskit command context was not initialized")
    return ctx.obj


def fail(exc: Exception) -> None:
    typer.echo(f"mapskit: {exc}", err=True)
    raise typer.Exit(1)


HELP_EPILOG = f"""\b
Environment:
  {API_KEY_FILE_ENV}     overrides the default API key file
  {LOCATIONS_FILE_ENV}   overrides the default saved locations file

\b
Location syntax:
  Saved names are resolved first, case-insensitively. Otherwise use:
  place:<place-id>, places/<place-id>, address:<address>, or <lat>,<lng>.
  Plain text falls back to a Routes API address string.

\b
Examples:
  mapskit places search --limit 5 "coffee near Central Park"
  mapskit places info ChIJ...
  mapskit route --via "Penn Station" Home "John F. Kennedy International Airport"
  mapskit locations save Home "350 Fifth Avenue, New York, NY"
  mapskit auth check
"""


app = typer.Typer(
    add_completion=False,
    context_settings=CONTEXT_SETTINGS,
    epilog=HELP_EPILOG,
    help="Small Google Maps Platform CLI.",
    name="mapskit",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
    rich_markup_mode=None,
)
places_app = typer.Typer(
    add_completion=False,
    context_settings=CONTEXT_SETTINGS,
    help="Search and inspect Google Places.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
locations_app = typer.Typer(
    add_completion=False,
    context_settings=CONTEXT_SETTINGS,
    help="Manage saved locations.",
    no_args_is_help=True,
    rich_markup_mode=None,
)
auth_app = typer.Typer(
    add_completion=False,
    context_settings=CONTEXT_SETTINGS,
    help="Check API key configuration.",
    no_args_is_help=True,
    rich_markup_mode=None,
)


@app.callback()
def configure(
    ctx: typer.Context,
    api_key_file: Annotated[
        str | None,
        typer.Option(
            "--api-key-file",
            envvar=API_KEY_FILE_ENV,
            help=(
                "Plain-text Google Maps Platform API key file. "
                f"Default: {display_path(default_api_key_file())}"
            ),
            show_default=False,
        ),
    ] = None,
    locations_file: Annotated[
        str | None,
        typer.Option(
            "--locations-file",
            envvar=LOCATIONS_FILE_ENV,
            help="Saved locations YAML file.",
            show_default=False,
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print raw API JSON for places and route commands."),
    ] = False,
) -> None:
    ctx.obj = AppConfig(
        api_key_file=Path(api_key_file) if api_key_file else default_api_key_file(),
        locations_file=Path(locations_file) if locations_file else default_locations_file(),
        json=json_output,
    )


@app.command("help", hidden=True)
def help_command(ctx: typer.Context) -> None:
    parent = ctx.parent
    typer.echo(parent.get_help() if parent is not None else ctx.get_help())


@app.command("version")
def version() -> None:
    typer.echo("mapskit 0.1.0")


@places_app.command("search")
@app.command("search", hidden=True)
def places_search(
    ctx: typer.Context,
    query_words: Annotated[
        list[str] | None,
        typer.Argument(metavar="QUERY", help="Search query words."),
    ] = None,
    fields: Annotated[str, typer.Option("--fields", help="Places field mask.")] = (
        DEFAULT_PLACES_SEARCH_FIELDS
    ),
    language: Annotated[str, typer.Option("--language", help="BCP-47 language code.")] = "",
    region: Annotated[str, typer.Option("--region", help="Two-character region code.")] = "",
    page_token: Annotated[
        str,
        typer.Option("--page-token", help="nextPageToken from a previous search."),
    ] = "",
    limit: Annotated[int, typer.Option("--limit", min=1, max=20)] = 5,
) -> None:
    config = get_config(ctx)
    query = " ".join(query_words or []).strip()
    if not query and not page_token:
        fail(MapsKitError("places search requires a query"))
    try:
        response = google_client(config).search_text(
            {
                "textQuery": query,
                "pageSize": limit,
                "pageToken": page_token,
                "languageCode": language,
                "regionCode": region,
            },
            fields,
        )
    except MapsKitError as exc:
        fail(exc)
    if config.json:
        print_json(sys.stdout, response)
        return
    print_places(sys.stdout, response.get("places") or [])
    next_page_token = response.get("nextPageToken")
    if next_page_token:
        sys.stdout.write(f"\nnextPageToken: {next_page_token}\n")


@places_app.command("info")
@places_app.command("details", hidden=True)
@app.command("info", hidden=True)
def places_info(
    ctx: typer.Context,
    place_id: Annotated[str, typer.Argument(help="Google place ID.")],
    fields: Annotated[str, typer.Option("--fields", help="Place Details field mask.")] = (
        DEFAULT_PLACE_DETAILS_FIELDS
    ),
    language: Annotated[str, typer.Option("--language", help="BCP-47 language code.")] = "",
    region: Annotated[str, typer.Option("--region", help="Two-character region code.")] = "",
) -> None:
    config = get_config(ctx)
    try:
        place = google_client(config).place_details(place_id, fields, language, region)
    except MapsKitError as exc:
        fail(exc)
    if config.json:
        print_json(sys.stdout, place)
        return
    print_place_details(sys.stdout, place)


@app.command("route")
@app.command("routes", hidden=True)
def route(
    ctx: typer.Context,
    waypoints: Annotated[
        list[str] | None,
        typer.Argument(metavar="WAYPOINT", help="Origin, destination, then optional via."),
    ] = None,
    origin: Annotated[str, typer.Option("--from", help="Origin waypoint.")] = "",
    destination: Annotated[str, typer.Option("--to", help="Destination waypoint.")] = "",
    via: Annotated[
        list[str] | None,
        typer.Option("--via", help="Intermediate waypoint; repeat for multiple hops."),
    ] = None,
    mode: Annotated[str, typer.Option("--mode", help="Travel mode.")] = "DRIVE",
    routing_preference: Annotated[
        str,
        typer.Option("--routing-preference", help="Routing preference for driving modes."),
    ] = "TRAFFIC_AWARE",
    alternatives: Annotated[
        bool,
        typer.Option("--alternatives", help="Request alternative routes."),
    ] = False,
    optimize: Annotated[
        bool,
        typer.Option("--optimize", help="Let Routes API reorder intermediate stops."),
    ] = False,
    avoid_tolls: Annotated[bool, typer.Option("--avoid-tolls")] = False,
    avoid_highways: Annotated[bool, typer.Option("--avoid-highways")] = False,
    avoid_ferries: Annotated[bool, typer.Option("--avoid-ferries")] = False,
    language: Annotated[str, typer.Option("--language", help="BCP-47 language code.")] = "",
    region: Annotated[str, typer.Option("--region", help="Two-character region code.")] = "",
    units: Annotated[str, typer.Option("--units", help="METRIC or IMPERIAL.")] = "METRIC",
    fields: Annotated[str, typer.Option("--fields", help="Routes API field mask.")] = (
        DEFAULT_ROUTE_FIELDS
    ),
    departure: Annotated[str, typer.Option("--departure", help="RFC3339 departure time.")] = "",
    arrival: Annotated[
        str,
        typer.Option("--arrival", help="RFC3339 arrival time; TRANSIT only."),
    ] = "",
) -> None:
    config = get_config(ctx)
    remaining = list(waypoints or [])
    from_waypoint = origin
    to_waypoint = destination
    if not from_waypoint and remaining:
        from_waypoint = remaining.pop(0)
    if not to_waypoint and remaining:
        to_waypoint = remaining.pop(0)
    via_waypoints = list(via or []) + remaining

    if not from_waypoint or not to_waypoint:
        fail(MapsKitError("route requires origin and destination"))
    if alternatives and via_waypoints:
        fail(
            MapsKitError(
                "Routes API does not return alternative routes when intermediates are present"
            )
        )
    if departure and arrival:
        fail(MapsKitError("set either --departure or --arrival, not both"))

    try:
        locations = load_locations_file(config.locations_file)
        intermediates = [waypoint_from_input(raw, locations) for raw in via_waypoints]
        travel_mode = mode.upper()
        body: dict[str, Any] = {
            "origin": waypoint_from_input(from_waypoint, locations),
            "destination": waypoint_from_input(to_waypoint, locations),
            "intermediates": intermediates,
            "travelMode": travel_mode,
            "routingPreference": routing_preference.upper(),
            "computeAlternativeRoutes": alternatives,
            "optimizeWaypointOrder": optimize,
            "languageCode": language,
            "regionCode": region,
            "units": units.upper(),
            "departureTime": departure,
            "arrivalTime": arrival,
        }
        if travel_mode not in {"DRIVE", "TWO_WHEELER"}:
            body["routingPreference"] = ""
        route_modifiers = {
            "avoidTolls": avoid_tolls,
            "avoidHighways": avoid_highways,
            "avoidFerries": avoid_ferries,
        }
        if any(route_modifiers.values()):
            body["routeModifiers"] = route_modifiers
        response = google_client(config).compute_routes(clean_json(body), fields)
    except MapsKitError as exc:
        fail(exc)

    if config.json:
        print_json(sys.stdout, response)
        return
    print_routes(sys.stdout, response)


@locations_app.command("list")
@locations_app.command("ls", hidden=True)
def locations_list(ctx: typer.Context) -> None:
    config = get_config(ctx)
    try:
        store = load_locations_file(config.locations_file)
    except MapsKitError as exc:
        fail(exc)
    print_locations(sys.stdout, store)


@locations_app.command("get")
def locations_get(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Saved location name.")],
) -> None:
    config = get_config(ctx)
    try:
        store = load_locations_file(config.locations_file)
        actual_name, location = lookup_location(store, name)
        if location is None:
            raise MapsKitError(f"saved location {name!r} not found")
    except MapsKitError as exc:
        fail(exc)
    if config.json:
        print_json(sys.stdout, location)
    else:
        print_saved_location(sys.stdout, actual_name, location)


@locations_app.command("save")
@locations_app.command("set", hidden=True)
def locations_save(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Saved location name.")],
    address_words: Annotated[
        list[str] | None,
        typer.Argument(metavar="ADDRESS", help="Address words."),
    ] = None,
    place_id: Annotated[str, typer.Option("--place-id", help="Google place ID.")] = "",
    lat: Annotated[float | None, typer.Option("--lat", help="Latitude.")] = None,
    lng: Annotated[float | None, typer.Option("--lng", help="Longitude.")] = None,
) -> None:
    config = get_config(ctx)
    address = " ".join(address_words or []).strip()
    has_lat = lat is not None
    has_lng = lng is not None
    if not address and not place_id and not (has_lat and has_lng):
        fail(MapsKitError("locations save requires an address, --place-id, or --lat/--lng"))
    if has_lat != has_lng:
        fail(MapsKitError("set both --lat and --lng"))

    location: dict[str, Any] = {
        "address": address,
        "place_id": place_id,
        "updated_at": now_utc(),
    }
    if has_lat and has_lng:
        location["lat_lng"] = {"latitude": lat, "longitude": lng}
    try:
        store = load_locations_file(config.locations_file)
        store.setdefault("locations", {})[name.strip()] = {
            key: value for key, value in location.items() if value not in {"", None}
        }
        save_locations_file(config.locations_file, store)
    except MapsKitError as exc:
        fail(exc)
    typer.echo(f"saved {name} in {config.locations_file}")


@locations_app.command("remove")
@locations_app.command("delete", hidden=True)
@locations_app.command("rm", hidden=True)
def locations_remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Saved location name.")],
) -> None:
    config = get_config(ctx)
    try:
        store = load_locations_file(config.locations_file)
        actual_name, location = lookup_location(store, name)
        if location is None:
            raise MapsKitError(f"saved location {name!r} not found")
        del store["locations"][actual_name]
        save_locations_file(config.locations_file, store)
    except MapsKitError as exc:
        fail(exc)
    typer.echo(f"removed {name}")


@auth_app.command("check")
def auth_check(ctx: typer.Context) -> None:
    config = get_config(ctx)
    try:
        key = load_api_key(config.api_key_file)
        if not key:
            raise MapsKitError("API key resolved to an empty value")
    except MapsKitError as exc:
        fail(exc)
    typer.echo("Google Maps Platform API key is available; value not printed.")


app.add_typer(places_app, name="places")
app.add_typer(locations_app, name="locations")
app.add_typer(locations_app, name="location", hidden=True)
app.add_typer(locations_app, name="loc", hidden=True)
app.add_typer(auth_app, name="auth")


def google_client(config: AppConfig) -> GoogleClient:
    return GoogleClient(load_api_key(Path(config.api_key_file)))


def load_api_key(path: Path) -> str:
    path = expand_home(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise MapsKitError(
            f"missing API key file {path}; set {API_KEY_FILE_ENV} or --api-key-file"
        ) from exc
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def load_locations_file(path: Path) -> dict[str, Any]:
    path = expand_home(path)
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"version": 1, "locations": {}}
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as exc:
        raise MapsKitError(f"read saved locations: {exc}") from exc
    if not isinstance(data, dict):
        raise MapsKitError("saved locations file must contain a YAML mapping")
    data.setdefault("version", 1)
    data.setdefault("locations", {})
    if not isinstance(data["locations"], dict):
        raise MapsKitError("saved locations file must contain a locations mapping")
    return data


def save_locations_file(path: Path, store: dict[str, Any]) -> None:
    path = expand_home(path)
    store.setdefault("version", 1)
    store.setdefault("locations", {})
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    raw = yaml.safe_dump(store, sort_keys=True)
    path.write_text(raw, encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def lookup_location(
    store: dict[str, Any], name: str
) -> tuple[str, dict[str, Any] | None]:
    locations = store.get("locations") or {}
    if name in locations:
        return name, locations[name]
    wanted = name.strip().lower()
    for saved_name, location in locations.items():
        if saved_name.lower() == wanted:
            return saved_name, location
    return name, None


def location_names(store: dict[str, Any]) -> list[str]:
    return sorted((store.get("locations") or {}).keys())


def waypoint_from_input(raw: str, store: dict[str, Any]) -> dict[str, Any]:
    raw = raw.strip()
    if not raw:
        raise MapsKitError("empty waypoint")
    _, location = lookup_location(store, raw)
    if location is not None:
        return saved_location_waypoint(location)
    lower = raw.lower()
    if lower.startswith("place:"):
        return {"placeId": raw[len("place:") :].strip()}
    if raw.startswith("places/"):
        return {"placeId": raw.removeprefix("places/")}
    if lower.startswith("address:"):
        return {"address": raw[len("address:") :].strip()}
    point = parse_lat_lng(raw)
    if point is not None:
        return {"location": {"latLng": point}}
    if looks_like_place_id(raw):
        return {"placeId": raw}
    return {"address": raw}


def saved_location_waypoint(location: dict[str, Any]) -> dict[str, Any]:
    if location.get("place_id"):
        return {"placeId": location["place_id"]}
    if location.get("lat_lng"):
        return {"location": {"latLng": location["lat_lng"]}}
    return {"address": location.get("address", "")}


def parse_lat_lng(raw: str) -> dict[str, float] | None:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        return None
    try:
        return {"latitude": float(parts[0]), "longitude": float(parts[1])}
    except ValueError:
        return None


def looks_like_place_id(raw: str) -> bool:
    if any(char.isspace() or char == "," for char in raw):
        return False
    if len(raw) < 16:
        return False
    return raw.startswith(("ChIJ", "GhIJ"))


def default_api_key_file() -> Path:
    value = os.environ.get(API_KEY_FILE_ENV, "").strip()
    if value:
        return expand_home(Path(value))
    return Path.home() / ".config" / "mapskit" / "google-maps-platform.key"


def default_locations_file() -> Path:
    value = os.environ.get(LOCATIONS_FILE_ENV, "").strip()
    if value:
        return expand_home(Path(value))
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "mapskit" / "locations.yaml"


def expand_home(path: Path) -> Path:
    return path.expanduser()


def display_path(path: Path) -> str:
    home = Path.home()
    try:
        relative = path.relative_to(home)
    except ValueError:
        return str(path)
    return str(Path("~") / relative)


def compact_field_mask(mask: str) -> str:
    return ",".join(part.strip() for part in mask.split(",") if part.strip())


def clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: clean_json(item)
            for key, item in value.items()
            if not is_empty_json_value(item)
        }
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def is_empty_json_value(value: Any) -> bool:
    return value is None or value is False or value == "" or value == []


def print_json(stream: TextIO, value: Any) -> None:
    json.dump(value, stream, indent=2)
    stream.write("\n")


def print_places(stream: TextIO, places: list[dict[str, Any]]) -> None:
    if not places:
        stream.write("No places found.\n")
        return
    for index, place in enumerate(places, 1):
        stream.write(f"{index}. {place_title(place)}\n")
        if place.get("id"):
            stream.write(f"   id: {place['id']}\n")
        if place.get("formattedAddress"):
            stream.write(f"   address: {place['formattedAddress']}\n")
        if place.get("location"):
            location = place["location"]
            stream.write(
                f"   location: {location['latitude']:.6f},{location['longitude']:.6f}\n"
            )
        if place.get("types"):
            stream.write(f"   types: {', '.join(place['types'])}\n")
        if place.get("googleMapsUri"):
            stream.write(f"   maps: {place['googleMapsUri']}\n")


def print_place_details(stream: TextIO, place: dict[str, Any]) -> None:
    stream.write(f"{place_title(place)}\n")
    fields = [
        ("id", "id"),
        ("formattedAddress", "address"),
        ("businessStatus", "businessStatus"),
        ("googleMapsUri", "maps"),
        ("websiteUri", "website"),
    ]
    for source, label in fields:
        if place.get(source):
            stream.write(f"{label}: {place[source]}\n")
    if place.get("location"):
        location = place["location"]
        stream.write(f"location: {location['latitude']:.6f},{location['longitude']:.6f}\n")
    phone = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
    if phone:
        stream.write(f"phone: {phone}\n")
    if place.get("rating", 0) > 0:
        stream.write(
            f"rating: {place['rating']:.1f} ({place.get('userRatingCount', 0)} ratings)\n"
        )
    if place.get("types"):
        stream.write(f"types: {', '.join(place['types'])}\n")
    hours = (place.get("currentOpeningHours") or {}).get("weekdayDescriptions") or []
    if hours:
        stream.write("hours:\n")
        for line in hours:
            stream.write(f"  {line}\n")


def print_routes(stream: TextIO, response: dict[str, Any]) -> None:
    routes = response.get("routes") or []
    if not routes:
        stream.write("No routes found.\n")
        return
    for index, route in enumerate(routes, 1):
        if index > 1:
            stream.write("\n")
        stream.write(
            f"Route {index}: {human_distance(route.get('distanceMeters', 0))}, "
            f"{human_duration(route.get('duration', ''))}\n"
        )
        if route.get("description"):
            stream.write(f"  description: {route['description']}\n")
        if route.get("routeLabels"):
            stream.write(f"  labels: {', '.join(route['routeLabels'])}\n")
        for leg_index, leg in enumerate(route.get("legs") or [], 1):
            distance = human_distance(leg.get("distanceMeters", 0))
            duration = human_duration(leg.get("duration", ""))
            localized = leg.get("localizedValues") or {}
            if (localized.get("distance") or {}).get("text"):
                distance = localized["distance"]["text"]
            if (localized.get("duration") or {}).get("text"):
                duration = localized["duration"]["text"]
            stream.write(f"  leg {leg_index}: {distance}, {duration}\n")
        if route.get("optimizedIntermediateWaypointIndex"):
            stream.write(
                "  optimized via order: "
                f"{route['optimizedIntermediateWaypointIndex']}\n"
            )
        if route.get("warnings"):
            stream.write(f"  warnings: {' | '.join(route['warnings'])}\n")
        encoded = (route.get("polyline") or {}).get("encodedPolyline")
        if encoded:
            stream.write(f"  encodedPolyline: {encoded}\n")
    if response.get("geocodingResults"):
        print_geocoding_results(stream, response["geocodingResults"])


def print_geocoding_results(stream: TextIO, geocoding: dict[str, Any]) -> None:
    lines: list[str] = []
    origin = geocoding.get("origin") or {}
    destination = geocoding.get("destination") or {}
    if origin.get("placeId"):
        lines.append(f"origin={origin['placeId']}")
    if destination.get("placeId"):
        lines.append(f"destination={destination['placeId']}")
    for waypoint in geocoding.get("intermediates") or []:
        if waypoint.get("placeId"):
            lines.append(
                f"via[{waypoint.get('intermediateWaypointRequestIndex', 0)}]="
                f"{waypoint['placeId']}"
            )
    if lines:
        stream.write(f"\ngeocoded place ids: {', '.join(lines)}\n")


def print_locations(stream: TextIO, store: dict[str, Any]) -> None:
    names = location_names(store)
    if not names:
        stream.write("No saved locations.\n")
        return
    for name in names:
        location = store["locations"][name]
        stream.write(f"{name}\t{location_summary(location)}\n")


def print_saved_location(stream: TextIO, name: str, location: dict[str, Any]) -> None:
    stream.write(f"{name}\n")
    if location.get("address"):
        stream.write(f"address: {location['address']}\n")
    if location.get("place_id"):
        stream.write(f"placeId: {location['place_id']}\n")
    if location.get("lat_lng"):
        point = location["lat_lng"]
        stream.write(f"location: {point['latitude']:.6f},{point['longitude']:.6f}\n")
    if location.get("updated_at"):
        stream.write(f"updatedAt: {location['updated_at']}\n")


def location_summary(location: dict[str, Any]) -> str:
    if location.get("address"):
        return location["address"]
    if location.get("place_id"):
        return "place:" + location["place_id"]
    if location.get("lat_lng"):
        point = location["lat_lng"]
        return f"{point['latitude']:.6f},{point['longitude']:.6f}"
    return "(empty)"


def place_title(place: dict[str, Any]) -> str:
    display_name = place.get("displayName") or {}
    if display_name.get("text"):
        return display_name["text"]
    if place.get("formattedAddress"):
        return place["formattedAddress"]
    if place.get("id"):
        return place["id"]
    if place.get("name"):
        return place["name"]
    return "(unnamed place)"


def human_distance(meters: int | float) -> str:
    if not meters:
        return "0 m"
    meters = int(meters)
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{meters} m"


def human_duration(raw: str) -> str:
    if not raw:
        return "unknown duration"
    if not raw.endswith("s"):
        return raw
    try:
        seconds = float(raw[:-1])
    except ValueError:
        return raw
    duration = timedelta(seconds=round(seconds))
    total_seconds = int(duration.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds}s"
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
