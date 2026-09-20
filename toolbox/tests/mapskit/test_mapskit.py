from __future__ import annotations

import io
from pathlib import Path

import mapskit


class RecordingGoogleClient:
    def __init__(self) -> None:
        self.search_fields = ""
        self.info_fields = ""

    def search_text(self, body, field_mask: str) -> dict:
        self.search_fields = field_mask
        return {"places": []}

    def place_details(
        self, place_id: str, field_mask: str, language: str, region: str
    ) -> dict:
        self.info_fields = field_mask
        return {}


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
