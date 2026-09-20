from __future__ import annotations

import io
from pathlib import Path

import mapskit


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
