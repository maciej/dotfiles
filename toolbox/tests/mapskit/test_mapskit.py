from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import mapskit


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
