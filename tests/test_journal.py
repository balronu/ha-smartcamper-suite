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
    stop_id = store.accept_suggestion(suggestions[0]["id"], name="Rast", trip_id=trip_id)
    store.upsert_overnight(stop_id, place_kind="campsite", large_rv_suitable=True)
    store.upsert_rating(stop_id, 5, facilities=4, review_text="Gut")
    store.create_expense("vehicle-a", trip_id=trip_id, category="fuel", amount_minor=1234)
    pdf = store.render_pdf("vehicle-a", trip_id)
    assert pdf.startswith(b"%PDF-1.4") and pdf.endswith(b"%%EOF\n")
    assert b"Reisebericht" in pdf
    assert b"GPX-Reise" in pdf
    assert b"Rast" in pdf
    assert b"fuel" in pdf
    assert b"GPS-Punkte" in pdf
    calls = []
    assert store.reverse_geocode(50.0, 8.0, lambda lat, lon: calls.append((lat, lon)) or "Alpenpunkt") == "Alpenpunkt"
    assert store.reverse_geocode(50.0, 8.0, lambda _lat, _lon: "unerwartet") == "Alpenpunkt"
    assert len(calls) == 1
    store.close()


def test_gpx_import_persists_ordered_geometry_and_route_segments(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    trip_id = store.create_trip("vehicle-a", "Geometriereise")
    gpx = b'''<gpx version="1.1"><trk><trkseg><trkpt lat="50.0" lon="8.0"><time>2026-01-01T10:00:00Z</time></trkpt><trkpt lat="50.001" lon="8.002"><time>2026-01-01T10:01:00Z</time></trkpt><trkpt lat="50.003" lon="8.004"><time>2026-01-01T10:02:00Z</time></trkpt></trkseg></trk></gpx>'''
    preview = store.analyze_gpx(gpx, "vehicle-a")
    result = store.import_gpx(preview, trip_id)
    assert result["drives_imported"] == 1
    segment = store.route_segments("vehicle-a", trip_id)[0]
    assert [point["recorded_at"] for point in segment["points"]] == [point["recorded_at"] for point in preview["points"]]
    assert [(point["latitude"], point["longitude"]) for point in segment["points"]] == [(point["latitude"], point["longitude"]) for point in preview["points"]]
    assert segment["source"] == "gpx"
    store.close()


def test_legacy_import_preserves_drive_geometry_and_associations(tmp_path):
    source = tmp_path / "legacy.sqlite"
    connection = sqlite3.connect(source)
    connection.executescript("""
        CREATE TABLE trips(id TEXT PRIMARY KEY, vehicle_id TEXT, title TEXT, started_at TEXT, status TEXT);
        CREATE TABLE gps_points(id INTEGER PRIMARY KEY, vehicle_id TEXT, recorded_at TEXT, latitude REAL, longitude REAL, accuracy_m REAL);
        CREATE TABLE drives(id TEXT PRIMARY KEY, vehicle_id TEXT, started_at TEXT, ended_at TEXT, distance_m REAL, source TEXT, start_latitude REAL, start_longitude REAL, end_latitude REAL, end_longitude REAL);
        CREATE TABLE trip_drives(trip_id TEXT, drive_id TEXT, linked_at TEXT);
        CREATE TABLE drive_gps_points(drive_id TEXT, gps_point_id INTEGER, ordinal INTEGER);
        INSERT INTO trips VALUES('trip-old','old-vehicle','Route','2026-01-01T00:00:00+00:00','completed');
        INSERT INTO gps_points VALUES(1,'old-vehicle','2026-01-01T10:00:00+00:00',50.0,8.0,5.0);
        INSERT INTO gps_points VALUES(2,'old-vehicle','2026-01-01T10:01:00+00:00',50.1,8.1,5.0);
        INSERT INTO drives VALUES('drive-old','old-vehicle','2026-01-01T10:00:00+00:00','2026-01-01T10:01:00+00:00',12000,'gpx',50.0,8.0,50.1,8.1);
        INSERT INTO trip_drives VALUES('trip-old','drive-old','2026-01-01T00:00:00+00:00');
        INSERT INTO drive_gps_points VALUES('drive-old',1,0);
        INSERT INTO drive_gps_points VALUES('drive-old',2,1);
    """)
    connection.commit()
    before = source.read_bytes()
    connection.close()
    store = JournalStore(tmp_path / "suite.sqlite")
    result = store.import_legacy(source, opt_in=True, dry_run=False, vehicle_map={"old-vehicle": "suite-vehicle"})
    assert result["counts"]["drives"] == 1
    assert result["counts"]["drive_gps_points"] == 2
    assert len(store.route_segments("suite-vehicle")) == 1
    assert len(store.route_segments("suite-vehicle")[0]["points"]) == 2
    assert source.read_bytes() == before
    store.close()


def test_drive_and_historical_update_contracts_are_transactional(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    trip_id = store.create_trip("vehicle-a", "Fahrtentest")
    drive_id = store.create_manual_drive("vehicle-a", "2026-01-01T10:00:00+00:00", "Start", "Ziel", 12.5, 30)
    assert store.list_drives("vehicle-a")[0]["id"] == drive_id
    assert store.route_segments("vehicle-a")[0]["source"] == "manual"
    store.update_manual_drive(drive_id, manual_distance_km=13.0, start_label="Neuer Start")
    assert store.list_drives("vehicle-a")[0]["manual_distance_km"] == 13.0
    stop_id = store.create_stop("vehicle-a", trip_id=trip_id, name="Pause")
    store.update_stop(stop_id, name="Pause 2")
    expense_id = store.create_expense("vehicle-a", trip_id=trip_id, category="fuel", amount_minor=500)
    store.update_expense(expense_id, amount_minor=750)
    store.link_drives(trip_id, [drive_id])
    store.unlink_drive(trip_id, drive_id)
    store.delete_expense(expense_id)
    store.delete_stop(stop_id)
    store.delete_manual_drive(drive_id)
    assert store.list_drives("vehicle-a") == []
    store.close()


def test_automatic_drive_detection_is_gap_aware_and_idempotent(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    store.add_gps_point("vehicle-a", 50.0000, 8.0000, "2026-01-01T10:00:00+00:00")
    store.add_gps_point("vehicle-a", 50.0010, 8.0000, "2026-01-01T10:01:00+00:00")
    store.add_gps_point("vehicle-a", 50.0020, 8.0000, "2026-01-01T10:02:00+00:00")
    store.add_gps_point("vehicle-a", 50.0020, 8.0000, "2026-01-01T10:12:00+00:00")
    detected = store.auto_detect_drives("vehicle-a")
    assert len(detected) == 1
    assert store.list_drives("vehicle-a")[0]["source"] == "gps_auto"
    assert store.list_drives("vehicle-a")[0]["end_reason"] == "stationary_timeout"
    assert len(store.route_segments("vehicle-a")[0]["points"]) == 3
    assert store.auto_detect_drives("vehicle-a") == detected
    store.close()


def test_expense_historical_fields_round_trip(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    trip_id = store.create_trip("vehicle-a", "Kostenfelder")
    stop_id = store.create_stop("vehicle-a", trip_id=trip_id, name="Camping")
    expense_id = store.create_expense("vehicle-a", trip_id=trip_id, category="camping", amount_minor=4200, occurred_on="2026-01-02", occurred_time="18:30", odometer_km=12345.6, stay_id=stop_id, place_id=stop_id)
    row = store.list_related("vehicle-a", trip_id)["expenses"][0]
    assert row["occurred_on"] == "2026-01-02"
    assert row["occurred_time"] == "18:30"
    assert row["odometer_km"] == 12345.6
    assert row["stay_id"] == stop_id and row["place_id"] == stop_id
    store.update_expense(expense_id, occurred_on="2026-01-03", odometer_km=12346.0)
    assert store.list_related("vehicle-a", trip_id)["expenses"][0]["occurred_on"] == "2026-01-03"
    store.close()


def test_route_output_applies_point_limit_and_simplification_without_mutating_source(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    for index in range(8):
        store.add_gps_point("vehicle-a", 50.0 + index * 0.001, 8.0 + (index % 2) * 0.001, f"2026-01-01T10:0{index}:00+00:00")
    drive_ids = store.auto_detect_drives("vehicle-a", min_movement_m=25, start_samples=2)
    assert drive_ids
    full = store.route_segments("vehicle-a", max_points=5000)
    limited = store.route_segments("vehicle-a", max_points=3)
    simplified = store.route_segments("vehicle-a", max_points=5000, simplify_tolerance_m=200)
    assert len(full[0]["points"]) >= 6
    assert len(limited[0]["points"]) == 3
    assert limited[0]["points"][0]["recorded_at"] == full[0]["points"][0]["recorded_at"]
    assert limited[0]["points"][-1]["recorded_at"] == full[0]["points"][-1]["recorded_at"]
    assert len(simplified[0]["points"]) < len(full[0]["points"])
    assert len(store.route_segments("vehicle-a", max_points=5000)[0]["points"]) == len(full[0]["points"])
    with pytest.raises(ValueError, match="route_parameters_invalid"):
        store.route_segments("vehicle-a", max_points=1)
    store.close()


def test_gpx_import_rejects_mismatched_file_hash(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    gpx = b'<gpx><trk><trkseg><trkpt lat="50" lon="8"><time>2026-01-01T10:00:00Z</time></trkpt></trkseg></trk></gpx>'
    preview = store.analyze_gpx(gpx, "vehicle-a")
    with pytest.raises(ValueError, match="gpx_file_hash_mismatch"):
        store.import_gpx(preview, expected_file_hash="wrong")
    assert store.import_gpx(preview, expected_file_hash=preview["file_hash"])["imported"] is True
    assert store.import_gpx(preview, expected_file_hash=preview["file_hash"])["reason"] == "already_imported"
    store.close()


def test_vehicle_scope_rejects_cross_vehicle_mutations(tmp_path):
    store = JournalStore(tmp_path / "suite.sqlite")
    trip_id = store.create_trip("vehicle-a", "A")
    expense_id = store.create_expense("vehicle-a", trip_id=trip_id, category="fuel", amount_minor=100)
    with pytest.raises(ValueError, match="vehicle_scope_mismatch"):
        store.assert_vehicle_scope("vehicle-b", trip_id=trip_id)
    with pytest.raises(ValueError, match="vehicle_scope_mismatch"):
        store.assert_vehicle_scope("vehicle-b", expense_id=expense_id)
    with pytest.raises(ValueError, match="trip_id_not_found"):
        store.assert_vehicle_scope("vehicle-a", trip_id="missing")
    store.close()
