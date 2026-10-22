from __future__ import annotations

import base64
import sqlite3

import pytest

from custom_components.smartcamper_suite.journal import JournalStore


def test_journal_crud_is_transactional_and_summary_is_vehicle_scoped(tmp_path):
    store = JournalStore(tmp_path / "smartcamper_suite_travel_journal.sqlite")
    trip_id = store.create_trip("vehicle-a", "Alpenfahrt", destination="Tirol")
    store.update_trip(trip_id, status="active")
    store.create_stay("vehicle-a", trip_id=trip_id, name="Campingplatz")
    store.create_stop("vehicle-a", trip_id=trip_id, name="Passhöhe")
    store.create_expense("vehicle-a", trip_id=trip_id, category="fuel", amount_minor=12345)

    assert store.list_trips("vehicle-a")[0]["status"] == "active"
    assert store.summary("vehicle-a")["expense_total_minor"] == 12345
    assert store.summary("vehicle-b")["trip_count"] == 0
    store.close()


def test_legacy_import_requires_opt_in_is_idempotent_and_preserves_source(tmp_path):
    source = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(source)
    connection.executescript("""
        CREATE TABLE trips(id TEXT PRIMARY KEY, vehicle_id TEXT, title TEXT, started_at TEXT, status TEXT);
        CREATE TABLE expenses(id TEXT PRIMARY KEY, vehicle_id TEXT, trip_id TEXT, occurred_at TEXT, category TEXT, amount_minor INTEGER, currency TEXT, note TEXT);
        INSERT INTO trips VALUES('old-trip','old-vehicle','Sommer','2026-01-01T00:00:00+00:00','completed');
        INSERT INTO expenses VALUES('old-expense','old-vehicle','old-trip','2026-01-02T00:00:00+00:00','fuel',2500,'EUR','');
    """)
    connection.commit()
    before = source.read_bytes()
    connection.close()

    store = JournalStore(tmp_path / "suite.sqlite")
    with pytest.raises(PermissionError):
        store.import_legacy(source)
    preview = store.import_legacy(source, opt_in=True, dry_run=True, vehicle_map={"old-vehicle": "suite-vehicle"})
    assert preview["counts"] == {"trips": 1, "expenses": 1}
    result = store.import_legacy(source, opt_in=True, dry_run=False, vehicle_map={"old-vehicle": "suite-vehicle"})
    assert result["imported"] is True
    repeated = store.import_legacy(source, opt_in=True, dry_run=False, vehicle_map={"old-vehicle": "suite-vehicle"})
    assert repeated["reason"] == "already_imported"
    assert store.summary("suite-vehicle")["trip_count"] == 1
    assert source.read_bytes() == before
    store.close()


def test_legacy_import_rejects_invalid_schema_without_writing(tmp_path):
    source = tmp_path / "invalid.sqlite"
    connection = sqlite3.connect(source)
    connection.execute("CREATE TABLE trips(id TEXT PRIMARY KEY, title TEXT)")
    connection.execute("INSERT INTO trips VALUES('x','invalid')")
    connection.commit()
    connection.close()
    store = JournalStore(tmp_path / "suite.sqlite")
    with pytest.raises(ValueError, match="legacy_schema_invalid"):
        store.import_legacy(source, opt_in=True, dry_run=False)
    assert store.summary("x")["trip_count"] == 0
    store.close()


def test_gpx_preview_import_pdf_and_suggestion_contracts(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    trip_id = store.create_trip("vehicle-a", "GPX-Reise")
    gpx = b'''<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg><trkpt lat="50.0" lon="8.0"><time>2026-01-01T10:00:00Z</time></trkpt><trkpt lat="50.0001" lon="8.0001"><time>2026-01-01T10:20:00Z</time></trkpt></trkseg></trk></gpx>'''
    preview = store.analyze_gpx(gpx, "vehicle-a")
    assert preview["point_count"] == 2
    assert base64.b64decode(base64.b64encode(gpx)) == gpx
    assert store.import_gpx(preview, trip_id)["imported"] is True
    assert store.import_gpx(preview, trip_id)["reason"] == "already_imported"
    suggestions = store.generate_suggestions("vehicle-a", minimum_minutes=10, radius_m=150)
    assert suggestions
    stop_id = store.accept_suggestion(suggestions[0]["id"], name="Rast")
    store.upsert_overnight(stop_id, place_kind="campsite", large_rv_suitable=True)
    store.upsert_rating(stop_id, 5, facilities=4, review_text="Gut")
    pdf = store.render_pdf("vehicle-a", trip_id)
    assert pdf.startswith(b"%PDF-1.4") and pdf.endswith(b"%%EOF\n")
    calls = []
    assert store.reverse_geocode(50.0, 8.0, lambda lat, lon: calls.append((lat, lon)) or "Alpenpunkt") == "Alpenpunkt"
    assert store.reverse_geocode(50.0, 8.0, lambda _lat, _lon: "unerwartet") == "Alpenpunkt"
    assert len(calls) == 1
    store.close()
