from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import mapskit


class RecordingGoogleClient:
    def __init__(self) -> None:
        self.search_fields = ""
        self.info_fields = ""
        self.route_field_masks: list[str] = []

    def search_text(self, body, field_mask: str) -> dict:
        self.search_fields = field_mask
        return {"places": []}

    def place_details(
        self, place_id: str, field_mask: str, language: str, region: str
    ) -> dict:
        self.info_fields = field_mask
        return {}

    def compute_routes(self, body, field_mask: str) -> dict:
        self.route_field_masks.append(field_mask)
        return {"routes": []}


def run_polyline_route(
    monkeypatch, tmp_path: Path, *options: str
) -> RecordingGoogleClient:
    client = RecordingGoogleClient()
    monkeypatch.setattr(mapskit, "google_client", lambda config: client)
    code = mapskit.run(
        [
            "--locations-file",
            str(tmp_path / "locations.yaml"),
            "route",
            "Origin",
            "Destination",
            *options,
        ],
        io.StringIO(),
        io.StringIO(),
    )
    assert code == 0
    return client


class FakeRoutesClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = responses
        self.calls: list[tuple[dict, str]] = []

    def compute_routes(self, body: dict, fields: str) -> dict:
        self.calls.append((body, fields))
        return self.responses[len(self.calls) - 1]


def run_route(
    monkeypatch,
    tmp_path: Path,
    responses: list[dict],
    arguments: list[str],
) -> tuple[int, str, str, FakeRoutesClient]:
    client = FakeRoutesClient(responses)
    monkeypatch.setattr(mapskit, "google_client", lambda config: client)
    stdout = io.StringIO()
    stderr = io.StringIO()
    code = mapskit.run(
        [
            "--locations-file",
            str(tmp_path / "locations.yaml"),
            "route",
            *arguments,
        ],
        stdout,
        stderr,
    )
    return code, stdout.getvalue(), stderr.getvalue(), client


def test_default_api_key_file_uses_google_maps_platform_name(
    monkeypatch,
) -> None:
    monkeypatch.delenv("MAPSKIT_API_KEY_FILE", raising=False)
    assert mapskit.default_api_key_file().name == "google-maps-platform.key"


def test_load_api_key_reads_first_non_comment_line(tmp_path: Path) -> None:
    key_file = tmp_path / "google-maps-platform.key"
    key_file.write_text("\n# comment\nAIza-test-key\n", encoding="utf-8")

    assert mapskit.load_api_key(key_file) == "AIza-test-key"


def test_help_is_plain_click_text() -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    code = mapskit.run(["--help"], stdout, stderr)

    assert code == 0
    assert "Usage: mapskit [OPTIONS] COMMAND [ARGS]..." in stdout.getvalue()
    assert "Commands:" in stdout.getvalue()
    assert "╭" not in stdout.getvalue()
    assert stderr.getvalue() == ""


def test_places_subcommands_use_endpoint_specific_default_field_masks(
    monkeypatch,
) -> None:
    client = RecordingGoogleClient()
    monkeypatch.setattr(mapskit, "google_client", lambda config: client)

    assert mapskit.run(["places", "search", "coffee"], io.StringIO(), io.StringIO()) == 0
    assert mapskit.run(["places", "info", "ChIJ123"], io.StringIO(), io.StringIO()) == 0

    assert client.search_fields == mapskit.DEFAULT_PLACES_SEARCH_FIELDS
    assert client.info_fields == mapskit.DEFAULT_PLACE_DETAILS_FIELDS
    assert all(
        field == "nextPageToken" or field.startswith("places.")
        for field in client.search_fields.split(",")
    )
    assert all(not field.startswith("places.") for field in client.info_fields.split(","))


def test_places_subcommands_document_endpoint_specific_field_masks() -> None:
    search_stdout = io.StringIO()
    info_stdout = io.StringIO()

    assert mapskit.run(["places", "search", "--help"], search_stdout, io.StringIO()) == 0
    assert mapskit.run(["places", "info", "--help"], info_stdout, io.StringIO()) == 0

    search_help = " ".join(search_stdout.getvalue().split())
    info_help = " ".join(info_stdout.getvalue().split())
    assert "require the places. prefix" in search_help
    assert "must be unprefixed" in info_help
    assert "surface as API errors" in search_help
    assert "surface as API errors" in info_help


def test_places_subcommands_pass_caller_fields_through_unchanged(monkeypatch) -> None:
    client = RecordingGoogleClient()
    monkeypatch.setattr(mapskit, "google_client", lambda config: client)

    search_fields = "id,displayName"
    info_fields = "places.id,places.displayName"
    assert (
        mapskit.run(
            ["places", "search", "--fields", search_fields, "coffee"],
            io.StringIO(),
            io.StringIO(),
        )
        == 0
    )
    assert (
        mapskit.run(
            ["places", "info", "--fields", info_fields, "ChIJ123"],
            io.StringIO(),
            io.StringIO(),
        )
        == 0
    )

    assert client.search_fields == search_fields
    assert client.info_fields == info_fields


def test_locations_round_trip_uses_private_permissions(tmp_path: Path) -> None:
    path = tmp_path / "locations.yaml"
    store = {"version": 1, "locations": {}}
    store["locations"]["Home"] = {
        "address": "350 Fifth Avenue, New York, NY",
        "updated_at": "2026-04-27T00:00:00Z",
    }

    mapskit.save_locations_file(path, store)
    loaded = mapskit.load_locations_file(path)
    _, location = mapskit.lookup_location(loaded, "home")

    assert location is not None
    assert location["address"] == "350 Fifth Avenue, New York, NY"
    assert path.stat().st_mode & 0o777 == 0o600


def test_waypoint_from_input_resolves_saved_names_and_place_ids() -> None:
    store = {
        "version": 1,
        "locations": {"Home": {"address": "350 Fifth Avenue, New York, NY"}},
    }

    assert mapskit.waypoint_from_input("home", store) == {
        "address": "350 Fifth Avenue, New York, NY"
    }
    assert mapskit.waypoint_from_input("52.214000,21.036000", store) == {
        "location": {"latLng": {"latitude": 52.214, "longitude": 21.036}}
    }
    assert mapskit.waypoint_from_input("place:ChIJ123456789012345", store) == {
        "placeId": "ChIJ123456789012345"
    }


def test_clean_json_removes_empty_route_fields() -> None:
    assert mapskit.clean_json(
        {
            "origin": {"address": "A"},
            "destination": {"address": "B"},
            "intermediates": [],
            "routingPreference": "",
            "computeAlternativeRoutes": False,
        }
    ) == {"origin": {"address": "A"}, "destination": {"address": "B"}}


def test_route_default_field_mask_excludes_polyline(monkeypatch, tmp_path: Path) -> None:
    client = run_polyline_route(monkeypatch, tmp_path)

    assert client.route_field_masks == [mapskit.DEFAULT_ROUTE_FIELDS]
    assert mapskit.ROUTE_POLYLINE_FIELD not in mapskit.DEFAULT_ROUTE_FIELDS.split(",")


def test_route_polyline_flag_adds_polyline_field(monkeypatch, tmp_path: Path) -> None:
    client = run_polyline_route(monkeypatch, tmp_path, "--polyline")

    assert client.route_field_masks == [
        f"{mapskit.DEFAULT_ROUTE_FIELDS},{mapskit.ROUTE_POLYLINE_FIELD}"
    ]


def test_route_explicit_fields_are_honoured(monkeypatch, tmp_path: Path) -> None:
    fields = "routes.duration,routes.polyline.encodedPolyline"
    client = run_polyline_route(monkeypatch, tmp_path, "--fields", fields)

    assert client.route_field_masks == [fields]


def test_route_polyline_flag_appends_to_explicit_fields(monkeypatch, tmp_path: Path) -> None:
    client = run_polyline_route(
        monkeypatch, tmp_path, "--fields", "routes.duration", "--polyline"
    )

    assert client.route_field_masks == [
        "routes.duration,routes.polyline.encodedPolyline"
    ]


def test_locations_save_with_lat_lng_updates_existing_name_case_insensitively(
    tmp_path: Path,
) -> None:
    locations_file = tmp_path / "locations.yaml"
    base = [
        "--api-key-file",
        str(tmp_path / "missing.key"),
        "--locations-file",
        str(locations_file),
        "locations",
        "save",
    ]

    assert mapskit.run(base + ["Home", "--lat", "52.1", "--lng", "21.0"], io.StringIO(), io.StringIO()) == 0
    assert mapskit.run(base + ["home", "--lat", "1.0", "--lng", "2.0"], io.StringIO(), io.StringIO()) == 0

    loaded = mapskit.load_locations_file(locations_file)
    assert list(loaded["locations"]) == ["Home"]
    _, location = mapskit.lookup_location(loaded, "HOME")
    assert location is not None
    assert location["lat_lng"] == {"latitude": 1.0, "longitude": 2.0}


def test_locations_save_does_not_need_api_key(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    stdout = io.StringIO()

    code = mapskit.run(
        [
            "--api-key-file",
            str(tmp_path / "missing.key"),
            "--locations-file",
            str(locations_file),
            "locations",
            "save",
            "Office",
            "1600 Amphitheatre Parkway, Mountain View, CA",
        ],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert "saved Office" in stdout.getvalue()
    loaded = mapskit.load_locations_file(locations_file)
    _, location = mapskit.lookup_location(loaded, "office")
    assert location is not None
    assert location["address"] == "1600 Amphitheatre Parkway, Mountain View, CA"


def test_locations_list_appends_coordinates_after_existing_columns(
    tmp_path: Path,
) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Observatory": {
                    "address": "1 Example Avenue, Sample City",
                    "lat_lng": {"latitude": 40.74844, "longitude": -73.985664},
                }
            },
        },
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "list"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == (
        "Observatory\t1 Example Avenue, Sample City"
        "\tlat=40.748440\tlng=-73.985664\n"
    )


def test_locations_list_appends_place_id(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Landmark": {
                    "address": "place:ChIJExamplePlaceId123",
                    "updated_at": "2026-01-02T03:04:05Z",
                }
            },
        },
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "list"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == (
        "Landmark\tplace:ChIJExamplePlaceId123\tplaceId=ChIJExamplePlaceId123\n"
    )


def test_locations_list_leaves_address_only_entry_unchanged(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Office": {"address": "10 Fictional Road, Exampletown"}
            },
        },
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "list"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == "Office\t10 Fictional Road, Exampletown\n"


def test_locations_list_json_has_stable_public_shape(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Park": {
                    "address": "20 Imaginary Street, Sample City",
                    "place_id": "ChIJExampleParkId123",
                    "lat_lng": {"latitude": 51.5, "longitude": -0.12},
                    "updated_at": "2026-01-02T03:04:05Z",
                },
                "Studio": {"address": "30 Placeholder Lane, Exampletown"},
            },
        },
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "list", "--json"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert json.loads(stdout.getvalue()) == [
        {
            "name": "Park",
            "address": "20 Imaginary Street, Sample City",
            "lat": 51.5,
            "lng": -0.12,
            "placeId": "ChIJExampleParkId123",
            "updatedAt": "2026-01-02T03:04:05Z",
        },
        {
            "name": "Studio",
            "address": "30 Placeholder Lane, Exampletown",
            "lat": None,
            "lng": None,
            "placeId": None,
            "updatedAt": None,
        },
    ]


def test_locations_get_prints_lat_and_lng(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Museum": {
                    "address": "40 Invented Boulevard, Demo City",
                    "place_id": "ChIJExampleMuseum123",
                    "lat_lng": {"latitude": 48.86, "longitude": 2.35},
                }
            },
        },
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "get", "Museum"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == (
        "Museum\n"
        "address: 40 Invented Boulevard, Demo City\n"
        "placeId: ChIJExampleMuseum123\n"
        "location: 48.860000,2.350000\n"
        "lat: 48.860000\n"
        "lng: 2.350000\n"
    )


def test_locations_list_reads_old_locations_file_format(tmp_path: Path) -> None:
    locations_file = tmp_path / "locations.yaml"
    locations_file.write_text(
        """version: 1
locations:
  Archive:
    address: 50 Example Way, Oldtown
    updated_at: '2025-01-02T03:04:05Z'
""",
        encoding="utf-8",
    )
    stdout = io.StringIO()

    code = mapskit.run(
        ["--locations-file", str(locations_file), "locations", "list"],
        stdout,
        io.StringIO(),
    )

    assert code == 0
    assert stdout.getvalue() == "Archive\t50 Example Way, Oldtown\n"


def test_places_search_sends_circle_location_bias(monkeypatch, tmp_path: Path) -> None:
    body = run_places_search(
        monkeypatch,
        tmp_path,
        ["--near", "52.214,21.036", "--radius", "2500", "coffee"],
    )

    assert body["locationBias"] == {
        "circle": {
            "center": {"latitude": 52.214, "longitude": 21.036},
            "radius": 2500.0,
        }
    }
    assert "locationRestriction" not in body


def test_places_search_sends_rectangle_location_restriction(
    monkeypatch, tmp_path: Path
) -> None:
    body = run_places_search(
        monkeypatch,
        tmp_path,
        ["--rect", "52.1,20.9,52.3,21.2", "coffee"],
    )

    assert body["locationRestriction"] == {
        "rectangle": {
            "low": {"latitude": 52.1, "longitude": 20.9},
            "high": {"latitude": 52.3, "longitude": 21.2},
        }
    }
    assert "locationBias" not in body


def test_places_search_rejects_invalid_location_option_combinations(
    tmp_path: Path,
) -> None:
    cases = [
        (["--near", "52.2,21.0", "coffee"], "set both --near and --radius"),
        (["--radius", "1000", "coffee"], "set both --near and --radius"),
        (
            [
                "--near",
                "52.2,21.0",
                "--radius",
                "1000",
                "--rect",
                "52.1,20.9,52.3,21.2",
                "coffee",
            ],
            "set either --near/--radius or --rect, not both",
        ),
    ]

    for args, message in cases:
        stdout = io.StringIO()
        stderr = io.StringIO()
        code = mapskit.run(["places", "search", *args], stdout, stderr)

        assert code == 1
        assert message in stderr.getvalue()


def test_places_search_resolves_saved_location_for_near(
    monkeypatch, tmp_path: Path
) -> None:
    locations_file = tmp_path / "locations.yaml"
    mapskit.save_locations_file(
        locations_file,
        {
            "version": 1,
            "locations": {
                "Town Centre": {
                    "lat_lng": {"latitude": 52.214, "longitude": 21.036}
                }
            },
        },
    )

    body = run_places_search(
        monkeypatch,
        tmp_path,
        ["--near", "town centre", "--radius", "1500", "coffee"],
        locations_file=locations_file,
    )

    assert body["locationBias"]["circle"]["center"] == {
        "latitude": 52.214,
        "longitude": 21.036,
    }


def test_places_search_help_explains_bias_and_restriction() -> None:
    stdout = io.StringIO()

    code = mapskit.run(["places", "search", "--help"], stdout, io.StringIO())

    assert code == 0
    help_text = " ".join(stdout.getvalue().split())
    assert "Biases results; it does not restrict them." in help_text
    assert "restriction supports rectangles only" in help_text


def run_places_search(
    monkeypatch,
    tmp_path: Path,
    args: list[str],
    *,
    locations_file: Path | None = None,
) -> dict:
    key_file = tmp_path / "google-maps-platform.key"
    key_file.write_text("test-key\n", encoding="utf-8")
    requests: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: int):
        assert timeout == 30
        requests.append(request)
        return io.BytesIO(b'{"places": []}')

    monkeypatch.setattr(mapskit.urllib.request, "urlopen", fake_urlopen)
    command = ["--api-key-file", str(key_file)]
    if locations_file is not None:
        command.extend(["--locations-file", str(locations_file)])
    command.extend(["places", "search", *args])

    code = mapskit.run(command, io.StringIO(), io.StringIO())

    assert code == 0
    assert len(requests) == 1
    assert requests[0].data is not None
    return json.loads(requests[0].data)


def test_route_detour_prints_difference_and_direct_baseline(
    monkeypatch, tmp_path: Path
) -> None:
    responses = [
        {
            "routes": [
                {
                    "distanceMeters": 367_400,
                    "duration": "13260s",
                    "description": "A1",
                }
            ]
        },
        {
            "routes": [
                {
                    "distanceMeters": 363_900,
                    "duration": "12780s",
                    "description": "A1",
                }
            ]
        },
    ]

    code, stdout, stderr, client = run_route(
        monkeypatch,
        tmp_path,
        responses,
        ["--from", "A", "--to", "B", "--via", "C", "--detour"],
    )

    assert code == 0
    assert "detour: +8m, +3.5 km (direct 363.9 km, 3h 33m)" in stdout
    assert stderr == ""
    assert len(client.calls) == 2


def test_route_detour_requests_share_routing_options(monkeypatch, tmp_path: Path) -> None:
    route = {
        "routes": [
            {"distanceMeters": 10_000, "duration": "600s", "description": "A1"}
        ]
    }
    code, _, stderr, client = run_route(
        monkeypatch,
        tmp_path,
        [route, route],
        [
            "--from",
            "A",
            "--to",
            "B",
            "--via",
            "C",
            "--detour",
            "--departure",
            "2026-09-21T08:00:00Z",
            "--routing-preference",
            "TRAFFIC_AWARE_OPTIMAL",
            "--mode",
            "DRIVE",
            "--avoid-tolls",
            "--avoid-highways",
            "--avoid-ferries",
            "--units",
            "IMPERIAL",
        ],
    )

    assert code == 0
    assert stderr == ""
    via_request, direct_request = (call[0] for call in client.calls)
    shared_fields = (
        "departureTime",
        "routingPreference",
        "travelMode",
        "routeModifiers",
        "units",
    )
    for field in shared_fields:
        assert via_request[field] == direct_request[field]
    assert via_request["intermediates"] == [{"address": "C"}]
    assert "intermediates" not in direct_request


def test_route_detour_suppresses_difference_for_different_descriptions(
    monkeypatch, tmp_path: Path
) -> None:
    responses = [
        {
            "routes": [
                {"distanceMeters": 12_000, "duration": "900s", "description": "A1"}
            ]
        },
        {
            "routes": [
                {"distanceMeters": 10_000, "duration": "600s", "description": "A2"}
            ]
        },
    ]

    code, stdout, stderr, _ = run_route(
        monkeypatch,
        tmp_path,
        responses,
        ["--from", "A", "--to", "B", "--via", "C", "--detour"],
    )

    assert code == 0
    assert (
        "detour: not comparable because route descriptions differ "
        "(via: A1; direct: A2)" in stdout
    )
    assert "+5m" not in stdout
    assert stderr == ""


def test_route_via_default_behavior_is_unchanged(monkeypatch, tmp_path: Path) -> None:
    response = {
        "routes": [
            {"distanceMeters": 12_000, "duration": "1200s", "description": "A1"}
        ]
    }

    code, stdout, stderr, client = run_route(
        monkeypatch,
        tmp_path,
        [response],
        ["--from", "A", "--to", "B", "--via", "C"],
    )

    assert code == 0
    assert stdout == "Route 1: 12.0 km, 20m\n  description: A1\n"
    assert stderr == ""
    assert len(client.calls) == 1
