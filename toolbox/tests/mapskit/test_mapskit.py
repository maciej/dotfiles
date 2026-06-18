from __future__ import annotations

import io
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
