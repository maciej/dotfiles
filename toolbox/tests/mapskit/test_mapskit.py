from __future__ import annotations

import io
import json
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
