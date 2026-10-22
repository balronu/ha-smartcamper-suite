"""Camper Travel Journal runtime for the SmartCamper Suite.

The journal deliberately owns a separate SQLite file from the legacy
``camper_travel_journal`` integration.  The adapter is small and synchronous
at its storage boundary so Home Assistant can execute it in its executor.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

JOURNAL_SCHEMA_VERSION = 3
TRIP_STATUSES = {"planned", "active", "completed", "cancelled"}
EXPENSE_CATEGORIES = {"camping", "fuel", "toll", "parking", "food", "activities", "other"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _distance_m(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> float:
    radius = 6_371_000.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


@dataclass(slots=True)
class JournalVehicle:
    vehicle_id: str
    name: str
    tracker_entity_id: str | None = None


class JournalStore:
    """Versioned, transaction-safe store isolated from all legacy databases."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False, timeout=30)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=30000")
        self._lock = threading.RLock()
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self.connection:
            self.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS trips(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, title TEXT NOT NULL,
                  description TEXT NOT NULL DEFAULT '', destination TEXT NOT NULL DEFAULT '',
                  started_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL,
                  start_date TEXT, end_date TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS stays(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, trip_id TEXT, name TEXT NOT NULL,
                  started_at TEXT NOT NULL, ended_at TEXT, latitude REAL, longitude REAL,
                  address TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS stops(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, trip_id TEXT, name TEXT NOT NULL,
                  occurred_at TEXT NOT NULL, latitude REAL, longitude REAL, description TEXT NOT NULL DEFAULT '',
                  category TEXT NOT NULL DEFAULT 'other', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS expenses(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, trip_id TEXT,
                  occurred_at TEXT NOT NULL, category TEXT NOT NULL, amount_minor INTEGER NOT NULL,
                  currency TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS gps_points(
                  id INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id TEXT NOT NULL, recorded_at TEXT NOT NULL,
                  latitude REAL NOT NULL, longitude REAL NOT NULL, accuracy_m REAL,
                  UNIQUE(vehicle_id, recorded_at, latitude, longitude)
                );
                CREATE TABLE IF NOT EXISTS drives(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, started_at TEXT NOT NULL,
                  ended_at TEXT NOT NULL, distance_m REAL, source TEXT NOT NULL DEFAULT 'manual',
                  start_label TEXT, end_label TEXT, manual_distance_km REAL,
                  end_reason TEXT, start_latitude REAL, start_longitude REAL,
                  end_latitude REAL, end_longitude REAL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS drive_gps_points(
                  drive_id TEXT NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
                  gps_point_id INTEGER NOT NULL REFERENCES gps_points(id) ON DELETE CASCADE,
                  ordinal INTEGER NOT NULL,
                  association_source TEXT NOT NULL DEFAULT 'import',
                  PRIMARY KEY(drive_id, gps_point_id), UNIQUE(drive_id, ordinal)
                );
                CREATE TABLE IF NOT EXISTS trip_drives(
                  trip_id TEXT NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
                  drive_id TEXT NOT NULL REFERENCES drives(id) ON DELETE CASCADE,
                  linked_at TEXT NOT NULL, PRIMARY KEY(trip_id, drive_id), UNIQUE(drive_id)
                );
                CREATE TABLE IF NOT EXISTS interruption_links(
                  trip_id TEXT NOT NULL, interruption_id TEXT NOT NULL,
                  status TEXT NOT NULL, stop_id TEXT, updated_at TEXT NOT NULL,
                  PRIMARY KEY(trip_id, interruption_id)
                );
                CREATE TABLE IF NOT EXISTS overnight_details(
                  place_id TEXT PRIMARY KEY, place_kind TEXT NOT NULL DEFAULT 'other', website_url TEXT,
                  booking_note TEXT, large_rv_suitable INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(place_id) REFERENCES stops(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS place_ratings(
                  place_id TEXT PRIMARY KEY, overall INTEGER NOT NULL, large_rv_access INTEGER,
                  space_maneuvering INTEGER, facilities INTEGER, surroundings INTEGER,
                  review_text TEXT NOT NULL DEFAULT '', rated_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  FOREIGN KEY(place_id) REFERENCES stops(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS stop_suggestions(
                  id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, trip_id TEXT, arrived_at TEXT NOT NULL,
                  departed_at TEXT, latitude REAL NOT NULL, longitude REAL NOT NULL,
                  status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  UNIQUE(vehicle_id, arrived_at, latitude, longitude)
                );
                CREATE TABLE IF NOT EXISTS gpx_imports(
                  file_hash TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL, imported_at TEXT NOT NULL,
                  point_count INTEGER NOT NULL, trip_id TEXT
                );
                CREATE TABLE IF NOT EXISTS geocode_cache(
                  cache_key TEXT PRIMARY KEY, latitude REAL NOT NULL, longitude REAL NOT NULL,
                  label TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS import_log(
                  source_hash TEXT PRIMARY KEY, imported_at TEXT NOT NULL, dry_run INTEGER NOT NULL,
                  counts_json TEXT NOT NULL, id_map_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_journal_trips_vehicle ON trips(vehicle_id, started_at);
                CREATE INDEX IF NOT EXISTS idx_journal_stays_trip ON stays(trip_id, started_at);
                CREATE INDEX IF NOT EXISTS idx_journal_expenses_trip ON expenses(trip_id, occurred_at);
                """
            )
            current = self.connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if current is not None and int(current[0]) > JOURNAL_SCHEMA_VERSION:
                raise RuntimeError("journal_schema_newer_than_supported")
            self.connection.execute(
                "INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)",
                (str(JOURNAL_SCHEMA_VERSION),),
            )
            stop_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(stops)")}
            if "drive_id" not in stop_columns:
                self.connection.execute("ALTER TABLE stops ADD COLUMN drive_id TEXT")
            drive_columns = {row[1] for row in self.connection.execute("PRAGMA table_info(drives)")}
            for column in ("end_reason", "start_latitude", "start_longitude", "end_latitude", "end_longitude"):
                if column not in drive_columns:
                    self.connection.execute(f"ALTER TABLE drives ADD COLUMN {column} {'TEXT' if column == 'end_reason' else 'REAL'}")

    def _row(self, row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def create_trip(self, vehicle_id: str, title: str, **fields: Any) -> str:
        title = title.strip()
        if not vehicle_id or not title:
            raise ValueError("vehicle_and_title_required")
        status = fields.get("status", "planned")
        if status not in TRIP_STATUSES:
            raise ValueError("trip_status_invalid")
        trip_id, now = _id("trip"), _now()
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO trips(id,vehicle_id,title,description,destination,started_at,ended_at,status,start_date,end_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (trip_id, vehicle_id, title, fields.get("description", ""), fields.get("destination", ""), fields.get("started_at", now), fields.get("ended_at"), status, fields.get("start_date"), fields.get("end_date"), now, now),
            )
        return trip_id

    def update_trip(self, trip_id: str, **fields: Any) -> None:
        allowed = {"title", "description", "destination", "started_at", "ended_at", "status", "start_date", "end_date"}
        values = {key: value for key, value in fields.items() if key in allowed}
        if "status" in values and values["status"] not in TRIP_STATUSES:
            raise ValueError("trip_status_invalid")
        if "title" in values and not str(values["title"]).strip():
            raise ValueError("title_required")
        if not values:
            return
        with self._lock, self.connection:
            self.connection.execute(
                f"UPDATE trips SET {','.join(f'{key}=?' for key in values)},updated_at=? WHERE id=?",
                (*values.values(), _now(), trip_id),
            )

    def delete_trip(self, trip_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM trips WHERE id=?", (trip_id,))

    def list_trips(self, vehicle_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self.connection.execute("SELECT * FROM trips WHERE vehicle_id=? ORDER BY started_at DESC", (vehicle_id,)).fetchall()
        return [dict(row) for row in rows]

    def create_stay(self, vehicle_id: str, **fields: Any) -> str:
        name = str(fields.get("name", "Aufenthalt")).strip() or "Aufenthalt"
        stay_id, now = _id("stay"), _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO stays(id,vehicle_id,trip_id,name,started_at,ended_at,latitude,longitude,address,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (stay_id, vehicle_id, fields.get("trip_id"), name, fields.get("started_at", now), fields.get("ended_at"), fields.get("latitude"), fields.get("longitude"), fields.get("address", ""), now, now))
        return stay_id

    def create_stop(self, vehicle_id: str, **fields: Any) -> str:
        stop_id, now = _id("stop"), _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO stops(id,vehicle_id,trip_id,drive_id,name,occurred_at,latitude,longitude,description,category,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (stop_id, vehicle_id, fields.get("trip_id"), fields.get("drive_id"), str(fields.get("name", "Zwischenstopp")).strip() or "Zwischenstopp", fields.get("occurred_at", now), fields.get("latitude"), fields.get("longitude"), fields.get("description", ""), fields.get("category", "other"), now, now))
        return stop_id

    def create_stop_from_interruption(self, vehicle_id: str, trip_id: str, interruption_id: str, name: str, **fields: Any) -> str:
        stop_id = self.create_stop(vehicle_id, trip_id=trip_id, name=name, category=fields.get("place_type", "other"), address=fields.get("address", ""), description=fields.get("description", ""), occurred_at=fields.get("occurred_at", _now()))
        self.assign_interruption(trip_id, interruption_id, "assigned", stop_id)
        return stop_id

    def create_expense(self, vehicle_id: str, **fields: Any) -> str:
        category = fields.get("category", "other")
        amount = int(fields.get("amount_minor", 0))
        if category not in EXPENSE_CATEGORIES or amount < 0:
            raise ValueError("expense_invalid")
        expense_id, now = _id("expense"), _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO expenses(id,vehicle_id,trip_id,occurred_at,category,amount_minor,currency,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (expense_id, vehicle_id, fields.get("trip_id"), fields.get("occurred_at", now), category, amount, str(fields.get("currency", "EUR")).upper(), fields.get("note", ""), now, now))
        return expense_id

    def update_stop(self, stop_id: str, **fields: Any) -> None:
        allowed = {"trip_id", "drive_id", "name", "occurred_at", "latitude", "longitude", "description", "category"}
        values = {key: value for key, value in fields.items() if key in allowed}
        if not values:
            return
        with self._lock, self.connection:
            cursor = self.connection.execute(f"UPDATE stops SET {','.join(f'{key}=?' for key in values)},updated_at=? WHERE id=?", (*values.values(), _now(), stop_id))
            if cursor.rowcount != 1:
                raise ValueError("stop_not_found")

    def delete_stop(self, stop_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM stops WHERE id=?", (stop_id,))

    def update_expense(self, expense_id: str, **fields: Any) -> None:
        allowed = {"trip_id", "occurred_at", "category", "amount_minor", "currency", "note"}
        values = {key: value for key, value in fields.items() if key in allowed}
        if "category" in values and values["category"] not in EXPENSE_CATEGORIES:
            raise ValueError("expense_category_invalid")
        if "amount_minor" in values and int(values["amount_minor"]) < 0:
            raise ValueError("expense_amount_invalid")
        if not values:
            return
        with self._lock, self.connection:
            cursor = self.connection.execute(f"UPDATE expenses SET {','.join(f'{key}=?' for key in values)},updated_at=? WHERE id=?", (*values.values(), _now(), expense_id))
            if cursor.rowcount != 1:
                raise ValueError("expense_not_found")

    def delete_expense(self, expense_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM expenses WHERE id=?", (expense_id,))

    def create_manual_drive(self, vehicle_id: str, occurred_at: str, start_location: str, end_location: str, distance_km: float, duration_minutes: int | None = None, trip_id: str | None = None) -> str:
        if not vehicle_id or float(distance_km) < 0 or (duration_minutes is not None and int(duration_minutes) < 0):
            raise ValueError("manual_drive_invalid")
        try:
            started = datetime.fromisoformat(occurred_at)
        except ValueError as err:
            raise ValueError("manual_drive_time_invalid") from err
        ended = started + timedelta(minutes=int(duration_minutes or 0))
        drive_id, now = _id("drive"), _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO drives(id,vehicle_id,started_at,ended_at,distance_m,source,start_label,end_label,manual_distance_km,end_reason,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (drive_id, vehicle_id, started.isoformat(), ended.isoformat(), float(distance_km) * 1000, "manual", start_location, end_location, float(distance_km), "manual", now))
            if trip_id:
                self.connection.execute("INSERT INTO trip_drives(trip_id,drive_id,linked_at) VALUES(?,?,?)", (trip_id, drive_id, now))
        return drive_id

    def update_manual_drive(self, drive_id: str, **fields: Any) -> None:
        allowed = {"started_at", "ended_at", "start_label", "end_label", "manual_distance_km"}
        values = {key: value for key, value in fields.items() if key in allowed}
        if "manual_distance_km" in values:
            values["manual_distance_km"] = float(values["manual_distance_km"])
            values["distance_m"] = values["manual_distance_km"] * 1000
        if not values:
            return
        with self._lock, self.connection:
            cursor = self.connection.execute(f"UPDATE drives SET {','.join(f'{key}=?' for key in values)} WHERE id=? AND source='manual'", (*values.values(), drive_id))
            if cursor.rowcount != 1:
                raise ValueError("manual_drive_not_found")

    def delete_manual_drive(self, drive_id: str) -> None:
        with self._lock, self.connection:
            cursor = self.connection.execute("DELETE FROM drives WHERE id=? AND source='manual'", (drive_id,))
            if cursor.rowcount != 1:
                raise ValueError("manual_drive_not_found")

    def list_drives(self, vehicle_id: str, trip_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT d.*,td.trip_id FROM drives d LEFT JOIN trip_drives td ON td.drive_id=d.id WHERE d.vehicle_id=?"
        args: list[Any] = [vehicle_id]
        if trip_id:
            query += " AND td.trip_id=?"
            args.append(trip_id)
        with self._lock:
            return [dict(row) for row in self.connection.execute(query + " ORDER BY d.started_at DESC", args).fetchall()]

    def link_drives(self, trip_id: str, drive_ids: list[str]) -> None:
        with self._lock, self.connection:
            if self.connection.execute("SELECT 1 FROM trips WHERE id=?", (trip_id,)).fetchone() is None:
                raise ValueError("trip_not_found")
            for drive_id in drive_ids:
                if self.connection.execute("SELECT 1 FROM drives WHERE id=?", (drive_id,)).fetchone() is None:
                    raise ValueError("drive_not_found")
                try:
                    self.connection.execute("INSERT INTO trip_drives(trip_id,drive_id,linked_at) VALUES(?,?,?)", (trip_id, drive_id, _now()))
                except sqlite3.IntegrityError as err:
                    raise ValueError("drive_already_assigned") from err

    def unlink_drive(self, trip_id: str, drive_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM trip_drives WHERE trip_id=? AND drive_id=?", (trip_id, drive_id))

    def route_segments(self, vehicle_id: str, trip_id: str | None = None, drive_ids: list[str] | None = None) -> list[dict[str, Any]]:
        drives = self.list_drives(vehicle_id, trip_id)
        if drive_ids is not None:
            allowed = set(drive_ids)
            drives = [drive for drive in drives if drive["id"] in allowed]
        result = []
        with self._lock:
            for drive in drives:
                rows = self.connection.execute(
                    "SELECT p.id,p.recorded_at,p.latitude,p.longitude,p.accuracy_m,dgp.ordinal "
                    "FROM drive_gps_points dgp JOIN gps_points p ON p.id=dgp.gps_point_id "
                    "WHERE dgp.drive_id=? ORDER BY dgp.ordinal", (drive["id"],)
                ).fetchall()
                points = [dict(row) for row in rows]
                result.append({
                    "drive_id": drive["id"], "started_at": drive["started_at"], "ended_at": drive["ended_at"],
                    "source": drive["source"], "end_reason": drive.get("end_reason"),
                    "start_latitude": drive.get("start_latitude"), "start_longitude": drive.get("start_longitude"),
                    "end_latitude": drive.get("end_latitude"), "end_longitude": drive.get("end_longitude"),
                    "points": points,
                })
        return result

    def assign_interruption(self, trip_id: str, interruption_id: str, status: str, stop_id: str | None = None) -> None:
        if status not in {"assigned", "dismissed", "pending"}:
            raise ValueError("interruption_status_invalid")
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO interruption_links(trip_id,interruption_id,status,stop_id,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(trip_id,interruption_id) DO UPDATE SET status=excluded.status,stop_id=excluded.stop_id,updated_at=excluded.updated_at", (trip_id, interruption_id, status, stop_id, _now()))

    def list_related(self, vehicle_id: str, trip_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
        where = "vehicle_id=?" + (" AND trip_id=?" if trip_id else "")
        args = (vehicle_id, trip_id) if trip_id else (vehicle_id,)
        with self._lock:
            result = {}
            for table, order in (("stays", "started_at"), ("stops", "occurred_at"), ("expenses", "occurred_at")):
                result[table] = [dict(row) for row in self.connection.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY {order}", args).fetchall()]
        return result

    def summary(self, vehicle_id: str) -> dict[str, Any]:
        trips = self.list_trips(vehicle_id)
        active = [trip for trip in trips if trip["status"] == "active"]
        with self._lock:
            expense = self.connection.execute("SELECT COALESCE(SUM(amount_minor),0) FROM expenses WHERE vehicle_id=?", (vehicle_id,)).fetchone()[0]
            points = self.connection.execute("SELECT COUNT(*) FROM gps_points WHERE vehicle_id=?", (vehicle_id,)).fetchone()[0]
        return {"vehicle_id": vehicle_id, "trip_count": len(trips), "active_trip_count": len(active), "active_trip": active[0] if active else None, "expense_total_minor": expense, "gps_point_count": points}

    def add_gps_point(self, vehicle_id: str, latitude: float, longitude: float, recorded_at: str | None = None, accuracy_m: float | None = None) -> None:
        if not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180:
            raise ValueError("coordinates_invalid")
        with self._lock, self.connection:
            self.connection.execute("INSERT OR IGNORE INTO gps_points(vehicle_id,recorded_at,latitude,longitude,accuracy_m) VALUES(?,?,?,?,?)", (vehicle_id, recorded_at or _now(), latitude, longitude, accuracy_m))

    def upsert_overnight(self, place_id: str, **fields: Any) -> None:
        now = _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO overnight_details(place_id,place_kind,website_url,booking_note,large_rv_suitable,created_at,updated_at) VALUES(?,?,?,?,?,?,?) ON CONFLICT(place_id) DO UPDATE SET place_kind=excluded.place_kind,website_url=excluded.website_url,booking_note=excluded.booking_note,large_rv_suitable=excluded.large_rv_suitable,updated_at=excluded.updated_at", (place_id, fields.get("place_kind", "other"), fields.get("website_url"), fields.get("booking_note"), fields.get("large_rv_suitable"), now, now))

    def upsert_rating(self, place_id: str, overall: int, **fields: Any) -> None:
        if not 1 <= int(overall) <= 5:
            raise ValueError("rating_overall_invalid")
        for key in ("large_rv_access", "space_maneuvering", "facilities", "surroundings"):
            if fields.get(key) is not None and not 1 <= int(fields[key]) <= 5:
                raise ValueError("rating_criterion_invalid")
        now = _now()
        with self._lock, self.connection:
            self.connection.execute("INSERT INTO place_ratings(place_id,overall,large_rv_access,space_maneuvering,facilities,surroundings,review_text,rated_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(place_id) DO UPDATE SET overall=excluded.overall,large_rv_access=excluded.large_rv_access,space_maneuvering=excluded.space_maneuvering,facilities=excluded.facilities,surroundings=excluded.surroundings,review_text=excluded.review_text,rated_at=excluded.rated_at,updated_at=excluded.updated_at", (place_id, overall, fields.get("large_rv_access"), fields.get("space_maneuvering"), fields.get("facilities"), fields.get("surroundings"), fields.get("review_text", ""), fields.get("rated_at", now), now, now))

    def delete_rating(self, place_id: str) -> None:
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM place_ratings WHERE place_id=?", (place_id,))

    def list_suggestions(self, vehicle_id: str, status: str = "pending") -> list[dict[str, Any]]:
        if status not in {"pending", "accepted", "dismissed"}:
            raise ValueError("suggestion_status_invalid")
        with self._lock:
            return [dict(row) for row in self.connection.execute("SELECT * FROM stop_suggestions WHERE vehicle_id=? AND status=? ORDER BY arrived_at", (vehicle_id, status)).fetchall()]

    def generate_suggestions(self, vehicle_id: str, *, minimum_minutes: int = 10, radius_m: float = 150.0, trip_id: str | None = None) -> list[dict[str, Any]]:
        if minimum_minutes < 1 or radius_m <= 0:
            raise ValueError("suggestion_parameters_invalid")
        with self._lock:
            points = [dict(row) for row in self.connection.execute("SELECT * FROM gps_points WHERE vehicle_id=? ORDER BY recorded_at", (vehicle_id,)).fetchall()]
        created: list[dict[str, Any]] = []
        for start, end in itertools.pairwise(points):
            started = datetime.fromisoformat(start["recorded_at"])
            ended = datetime.fromisoformat(end["recorded_at"])
            seconds = (ended - started).total_seconds()
            distance = _distance_m(start["latitude"], start["longitude"], end["latitude"], end["longitude"])
            if seconds < minimum_minutes * 60 or distance > radius_m:
                continue
            suggestion_id = _id("suggestion")
            with self._lock, self.connection:
                self.connection.execute("INSERT OR IGNORE INTO stop_suggestions(id,vehicle_id,trip_id,arrived_at,departed_at,latitude,longitude,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (suggestion_id, vehicle_id, trip_id, start["recorded_at"], end["recorded_at"], start["latitude"], start["longitude"], "pending", _now(), _now()))
                row = self.connection.execute("SELECT * FROM stop_suggestions WHERE vehicle_id=? AND arrived_at=? AND latitude=? AND longitude=?", (vehicle_id, start["recorded_at"], start["latitude"], start["longitude"])).fetchone()
            if row is not None:
                created.append(dict(row))
        return created

    def accept_suggestion(self, suggestion_id: str, *, name: str = "GPS-Stopp", category: str = "other", trip_id: str | None = None) -> str:
        with self._lock:
            row = self.connection.execute("SELECT * FROM stop_suggestions WHERE id=? AND status='pending'", (suggestion_id,)).fetchone()
        if row is None:
            raise ValueError("suggestion_not_pending")
        stop_id = self.create_stop(row["vehicle_id"], trip_id=trip_id or row["trip_id"], name=name, category=category, occurred_at=row["arrived_at"], latitude=row["latitude"], longitude=row["longitude"])
        with self._lock, self.connection:
            self.connection.execute("UPDATE stop_suggestions SET status='accepted',updated_at=? WHERE id=?", (_now(), suggestion_id))
        return stop_id

    def dismiss_suggestion(self, suggestion_id: str) -> None:
        with self._lock, self.connection:
            cursor = self.connection.execute("UPDATE stop_suggestions SET status='dismissed',updated_at=? WHERE id=? AND status='pending'", (_now(), suggestion_id))
            if cursor.rowcount != 1:
                raise ValueError("suggestion_not_pending")

    @staticmethod
    def analyze_gpx(data: bytes, vehicle_id: str) -> dict[str, Any]:
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("gpx_file_too_large")
        try:
            root = ElementTree.fromstring(data)
        except ElementTree.ParseError as err:
            raise ValueError("gpx_xml_invalid") from err
        if root.tag.rsplit("}", 1)[-1] != "gpx":
            raise ValueError("gpx_root_invalid")
        points: list[dict[str, Any]] = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1] != "trkpt":
                continue
            try:
                lat, lon = float(node.attrib["lat"]), float(node.attrib["lon"])
                time_node = next(child for child in node if child.tag.rsplit("}", 1)[-1] == "time")
                raw_time = time_node.text or ""
                raw_time = f"{raw_time[:-1]}+00:00" if raw_time.endswith("Z") else raw_time
                recorded_at = datetime.fromisoformat(raw_time).astimezone(UTC).isoformat()
            except (KeyError, StopIteration, TypeError, ValueError) as err:
                raise ValueError("gpx_point_invalid") from err
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise ValueError("gpx_coordinate_invalid")
            points.append({"vehicle_id": vehicle_id, "recorded_at": recorded_at, "latitude": lat, "longitude": lon})
        if not points:
            raise ValueError("gpx_no_valid_points")
        digest = hashlib.sha256(data).hexdigest()
        started_at, ended_at = points[0]["recorded_at"], points[-1]["recorded_at"]
        distance_m = sum(_distance_m(left["latitude"], left["longitude"], right["latitude"], right["longitude"]) for left, right in itertools.pairwise(points))
        return {
            "file_hash": digest, "vehicle_id": vehicle_id, "points": points, "point_count": len(points), "warnings": [],
            "drives": [{"key": f"{digest}:0", "started_at": started_at, "ended_at": ended_at, "distance_m": distance_m, "duration_seconds": max(0, int((datetime.fromisoformat(ended_at) - datetime.fromisoformat(started_at)).total_seconds())), "reason": "gpx_track"}],
        }

    def import_gpx(self, preview: dict[str, Any], trip_id: str | None = None, drive_keys: list[str] | None = None) -> dict[str, Any]:
        digest = preview["file_hash"]
        with self._lock:
            if self.connection.execute("SELECT 1 FROM gpx_imports WHERE file_hash=?", (digest,)).fetchone():
                return {"imported": False, "reason": "already_imported", "file_hash": digest}
        with self._lock, self.connection:
            point_ids = []
            for point in preview["points"]:
                self.connection.execute("INSERT OR IGNORE INTO gps_points(vehicle_id,recorded_at,latitude,longitude) VALUES(?,?,?,?)", (point["vehicle_id"], point["recorded_at"], point["latitude"], point["longitude"]))
                row = self.connection.execute("SELECT id FROM gps_points WHERE vehicle_id=? AND recorded_at=? AND latitude=? AND longitude=?", (point["vehicle_id"], point["recorded_at"], point["latitude"], point["longitude"])).fetchone()
                point_ids.append(int(row[0]))
            selected = {item["key"] for item in preview.get("drives", [])} if drive_keys is None else set(drive_keys)
            imported_drives = 0
            for drive in preview.get("drives", []):
                if drive["key"] not in selected:
                    continue
                drive_id = _id("drive")
                first, last = preview["points"][0], preview["points"][-1]
                self.connection.execute("INSERT INTO drives(id,vehicle_id,started_at,ended_at,distance_m,source,end_reason,start_latitude,start_longitude,end_latitude,end_longitude,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (drive_id, preview["vehicle_id"], drive["started_at"], drive["ended_at"], drive["distance_m"], "gpx", drive.get("reason"), first["latitude"], first["longitude"], last["latitude"], last["longitude"], _now()))
                for ordinal, point_id in enumerate(point_ids):
                    self.connection.execute("INSERT INTO drive_gps_points(drive_id,gps_point_id,ordinal,association_source) VALUES(?,?,?,?)", (drive_id, point_id, ordinal, "gpx"))
                if trip_id:
                    self.connection.execute("INSERT INTO trip_drives(trip_id,drive_id,linked_at) VALUES(?,?,?)", (trip_id, drive_id, _now()))
                imported_drives += 1
            self.connection.execute("INSERT INTO gpx_imports(file_hash,vehicle_id,imported_at,point_count,trip_id) VALUES(?,?,?,?,?)", (digest, preview["vehicle_id"], _now(), preview["point_count"], trip_id))
        return {"imported": True, "file_hash": digest, "point_count": preview["point_count"], "drives_imported": imported_drives}

    def render_pdf(self, vehicle_id: str, trip_id: str, language: str = "de") -> bytes:
        """Create a dependency-free, text report with the stable data sections.

        ReportLab is intentionally not a runtime dependency of the suite.  The
        generated document is therefore deliberately conservative (Helvetica,
        A4, deterministic text layout), but it contains the same journal data
        sections needed by the export contract and remains usable offline.
        """
        trip = next((item for item in self.list_trips(vehicle_id) if item["id"] == trip_id), None)
        if trip is None:
            raise ValueError("trip_not_found")
        related = self.list_related(vehicle_id, trip_id)
        summary = self.summary(vehicle_id)
        label = "Reisebericht" if language == "de" else "Travel report"
        sections = {
            "trip": "Reiseinformationen" if language == "de" else "Trip information",
            "stays": "Aufenthalte" if language == "de" else "Stays",
            "stops": "Zwischenstopps" if language == "de" else "Stops",
            "expenses": "Kosten" if language == "de" else "Expenses",
            "gps": "GPS-Informationen" if language == "de" else "GPS information",
        }
        lines = [
            label,
            str(trip["title"]),
            f"Fahrzeug / Vehicle: {vehicle_id}",
            f"Status: {trip['status']}",
            f"Ziel / Destination: {trip.get('destination') or '-'}",
            f"Beginn / Start: {trip.get('started_at') or '-'}",
            f"Ende / End: {trip.get('ended_at') or '-'}",
            f"Beschreibung / Description: {trip.get('description') or '-'}",
            "",
            sections["stays"],
        ]
        lines.extend(f"- {item['name']} | {item['started_at']} – {item.get('ended_at') or '-'} | {item.get('address') or '-'}" for item in related["stays"])
        if not related["stays"]:
            lines.append("- keine / none")
        lines.append(sections["stops"])
        lines.extend(f"- {item['name']} | {item['occurred_at']} | {item.get('description') or '-'}" for item in related["stops"])
        if not related["stops"]:
            lines.append("- keine / none")
        lines.append(sections["expenses"])
        expense_total = 0
        for item in related["expenses"]:
            expense_total += int(item["amount_minor"])
            lines.append(f"- {item['category']} | {item['amount_minor'] / 100:.2f} {item['currency']} | {item.get('note') or '-'}")
        if not related["expenses"]:
            lines.append("- keine / none")
        lines.append(f"Summe / Total: {expense_total / 100:.2f} EUR")
        lines.extend(("", sections["gps"], f"GPS-Punkte / points: {summary['gps_point_count']}"))

        def pdf_escape(value: str) -> bytes:
            return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").encode("latin-1", "replace")

        page_lines = [lines[index : index + 42] for index in range(0, len(lines), 42)] or [[label]]
        content_streams: list[bytes] = []
        for page in page_lines:
            commands = [b"BT", b"/F1 16 Tf", b"72 780 Td"]
            for index, line in enumerate(page):
                if index == 1:
                    commands.append(b"/F1 12 Tf")
                commands.append(b"(" + pdf_escape(line) + b") Tj")
                commands.append(b"0 -17 Td")
            commands.append(b"ET")
            content_streams.append(b"\n".join(commands))
        page_count = len(content_streams)
        pages_id = 2
        font_id = 3
        first_page_id = 4
        first_content_id = first_page_id + page_count
        objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        page_refs = " ".join(f"{first_page_id + index} 0 R" for index in range(page_count))
        objects[1] = f"<< /Type /Pages /Kids [{page_refs}] /Count {page_count} >>".encode()
        for index in range(page_count):
            content_id = first_content_id + index
            objects.append(f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>".encode())
        for stream in content_streams:
            objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        result = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(result)); result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
        xref = len(result); result.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        result.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
        result.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(result)

    def reverse_geocode(self, latitude: float, longitude: float, resolver: Any) -> str:
        """Resolve a coordinate through an injected provider and cache the label."""
        key = f"{float(latitude):.4f}:{float(longitude):.4f}"
        with self._lock:
            row = self.connection.execute("SELECT label FROM geocode_cache WHERE cache_key=?", (key,)).fetchone()
        if row is not None:
            return str(row[0])
        label = str(resolver(float(latitude), float(longitude))).strip()
        if not label:
            raise ValueError("geocode_empty")
        with self._lock, self.connection:
            self.connection.execute("INSERT OR REPLACE INTO geocode_cache(cache_key,latitude,longitude,label,updated_at) VALUES(?,?,?,?,?)", (key, latitude, longitude, label, _now()))
        return label

    def preview_legacy_import(self, source_path: str | Path) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError("legacy_database_not_found")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in source_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            mapping = {table: table for table in ("trips", "stays", "stops", "expenses", "gps_points", "drives", "drive_gps_points", "trip_drives") if table in tables}
            counts = {table: int(source_db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in mapping}
        finally:
            source_db.close()
        return {"source_hash": digest, "tables": sorted(tables), "mapping": mapping, "counts": counts, "already_imported": self._already_imported(digest)}

    def _already_imported(self, digest: str) -> bool:
        with self._lock:
            return self.connection.execute("SELECT 1 FROM import_log WHERE source_hash=?", (digest,)).fetchone() is not None

    def import_legacy(self, source_path: str | Path, *, opt_in: bool = False, dry_run: bool = True, vehicle_map: dict[str, str] | None = None) -> dict[str, Any]:
        if not opt_in:
            raise PermissionError("legacy_import_requires_opt_in")
        preview = self.preview_legacy_import(source_path)
        if preview["already_imported"]:
            return {**preview, "imported": False, "reason": "already_imported"}
        if dry_run:
            return {**preview, "imported": False, "dry_run": True}
        source = sqlite3.connect(f"file:{Path(source_path)}?mode=ro", uri=True)
        id_map: dict[str, str] = {}
        counts: dict[str, int] = {}
        try:
            with self._lock, self.connection:
                for table in ("trips", "stays", "stops", "expenses", "gps_points", "drives", "trip_drives", "drive_gps_points"):
                    if table not in preview["mapping"]:
                        continue
                    columns = {row[1] for row in source.execute(f"PRAGMA table_info({table})")}
                    if table == "trip_drives":
                        if not {"trip_id", "drive_id"} <= columns:
                            raise ValueError(f"legacy_schema_invalid:{table}")
                        for data_row in source.execute("SELECT * FROM trip_drives"):
                            data = dict(zip([column[1] for column in source.execute("PRAGMA table_info(trip_drives)")], data_row))
                            trip_id = id_map.get(f"trips:{data.get('trip_id')}")
                            drive_id = id_map.get(f"drives:{data.get('drive_id')}")
                            if trip_id and drive_id:
                                self.connection.execute("INSERT OR IGNORE INTO trip_drives(trip_id,drive_id,linked_at) VALUES(?,?,?)", (trip_id, drive_id, data.get("linked_at", _now())))
                            counts[table] = counts.get(table, 0) + 1
                        continue
                    if table == "drive_gps_points":
                        if not {"drive_id", "gps_point_id"} <= columns:
                            raise ValueError(f"legacy_schema_invalid:{table}")
                        association_columns = [column[1] for column in source.execute("PRAGMA table_info(drive_gps_points)")]
                        for data_row in source.execute("SELECT * FROM drive_gps_points"):
                            data = dict(zip(association_columns, data_row))
                            drive_id = id_map.get(f"drives:{data.get('drive_id')}")
                            gps_row = source.execute("SELECT vehicle_id,recorded_at,latitude,longitude,accuracy_m FROM gps_points WHERE id=?", (data.get("gps_point_id"),)).fetchone()
                            if drive_id and gps_row is not None:
                                gps_vehicle, recorded_at, latitude, longitude, _accuracy_m = gps_row
                                mapped_vehicle = (vehicle_map or {}).get(str(gps_vehicle), str(gps_vehicle))
                                local = self.connection.execute("SELECT id FROM gps_points WHERE vehicle_id=? AND recorded_at=? AND latitude=? AND longitude=?", (mapped_vehicle, recorded_at, latitude, longitude)).fetchone()
                                if local is not None:
                                    self.connection.execute("INSERT OR IGNORE INTO drive_gps_points(drive_id,gps_point_id,ordinal,association_source) VALUES(?,?,?,?)", (drive_id, local[0], int(data.get("ordinal", 0)), "legacy"))
                            counts[table] = counts.get(table, 0) + 1
                        continue
                    required = {"id", "vehicle_id"}
                    if not required <= columns:
                        raise ValueError(f"legacy_schema_invalid:{table}")
                    column_names = [column[1] for column in source.execute(f"PRAGMA table_info({table})")]
                    for row in source.execute(f"SELECT * FROM {table}"):
                        data = dict(zip(column_names, row))
                        old_id = str(data["id"])
                        new_id = id_map.setdefault(f"{table}:{old_id}", _id(table[:-1]))
                        vehicle_id = (vehicle_map or {}).get(str(data["vehicle_id"]), str(data["vehicle_id"]))
                        if table == "trips":
                            self.connection.execute("INSERT INTO trips(id,vehicle_id,title,description,destination,started_at,ended_at,status,start_date,end_date,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (new_id, vehicle_id, data.get("title", "Importierte Reise"), data.get("description", ""), data.get("destination", ""), data.get("started_at", _now()), data.get("ended_at"), data.get("status", "completed") if data.get("status", "completed") in TRIP_STATUSES else "completed", data.get("start_date"), data.get("end_date"), _now(), _now()))
                        elif table == "expenses":
                            category = data.get("category", "other") if data.get("category", "other") in EXPENSE_CATEGORIES else "other"
                            self.connection.execute("INSERT INTO expenses(id,vehicle_id,trip_id,occurred_at,category,amount_minor,currency,note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (new_id, vehicle_id, id_map.get(f"trips:{data.get('trip_id')}"), data.get("occurred_at", _now()), category, int(data.get("amount_minor", 0)), str(data.get("currency", "EUR")), data.get("note", ""), _now(), _now()))
                        elif table == "stays":
                            self.connection.execute("INSERT INTO stays(id,vehicle_id,trip_id,name,started_at,ended_at,latitude,longitude,address,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (new_id, vehicle_id, id_map.get(f"trips:{data.get('trip_id')}"), data.get("name", "Importierter Aufenthalt"), data.get("started_at", _now()), data.get("ended_at"), data.get("latitude"), data.get("longitude"), data.get("address", ""), _now(), _now()))
                        elif table == "stops":
                            self.connection.execute("INSERT INTO stops(id,vehicle_id,trip_id,name,occurred_at,latitude,longitude,description,category,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (new_id, vehicle_id, id_map.get(f"trips:{data.get('trip_id')}"), data.get("name", "Importierter Zwischenstopp"), data.get("occurred_at", _now()), data.get("latitude"), data.get("longitude"), data.get("description", ""), data.get("category", "other"), _now(), _now()))
                        elif table == "gps_points":
                            latitude, longitude = float(data["latitude"]), float(data["longitude"])
                            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                                raise ValueError("legacy_coordinates_invalid")
                            self.connection.execute("INSERT OR IGNORE INTO gps_points(vehicle_id,recorded_at,latitude,longitude,accuracy_m) VALUES(?,?,?,?,?)", (vehicle_id, data.get("recorded_at", _now()), latitude, longitude, data.get("accuracy_m")))
                        elif table == "drives":
                            started_at, ended_at = data.get("started_at"), data.get("ended_at")
                            if not started_at or not ended_at:
                                raise ValueError("legacy_drive_times_invalid")
                            self.connection.execute(
                                "INSERT OR IGNORE INTO drives(id,vehicle_id,started_at,ended_at,distance_m,source,start_label,end_label,manual_distance_km,end_reason,start_latitude,start_longitude,end_latitude,end_longitude,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                (new_id, vehicle_id, started_at, ended_at, data.get("distance_m"), data.get("source", "legacy"), data.get("start_label"), data.get("end_label"), data.get("manual_distance_km"), data.get("end_reason"), data.get("start_latitude"), data.get("start_longitude"), data.get("end_latitude"), data.get("end_longitude"), _now()),
                            )
                        elif table == "trip_drives":
                            trip_id = id_map.get(f"trips:{data.get('trip_id')}")
                            drive_id = id_map.get(f"drives:{data.get('drive_id')}")
                            if trip_id and drive_id:
                                self.connection.execute("INSERT OR IGNORE INTO trip_drives(trip_id,drive_id,linked_at) VALUES(?,?,?)", (trip_id, drive_id, data.get("linked_at", _now())))
                        elif table == "drive_gps_points":
                            drive_id = id_map.get(f"drives:{data.get('drive_id')}")
                            gps_id = data.get("gps_point_id")
                            if drive_id and gps_id is not None:
                                gps_row = source.execute("SELECT vehicle_id,recorded_at,latitude,longitude,accuracy_m FROM gps_points WHERE id=?", (gps_id,)).fetchone()
                                if gps_row is not None:
                                    gps_vehicle, recorded_at, latitude, longitude, _accuracy_m = gps_row
                                    mapped_vehicle = (vehicle_map or {}).get(str(gps_vehicle), str(gps_vehicle))
                                    local = self.connection.execute("SELECT id FROM gps_points WHERE vehicle_id=? AND recorded_at=? AND latitude=? AND longitude=?", (mapped_vehicle, recorded_at, latitude, longitude)).fetchone()
                                    if local is not None:
                                        self.connection.execute("INSERT OR IGNORE INTO drive_gps_points(drive_id,gps_point_id,ordinal,association_source) VALUES(?,?,?,?)", (drive_id, local[0], int(data.get("ordinal", 0)), "legacy"))
                        counts[table] = counts.get(table, 0) + 1
                self.connection.execute("INSERT INTO import_log(source_hash,imported_at,dry_run,counts_json,id_map_json) VALUES(?,?,?,?,?)", (preview["source_hash"], _now(), 0, json.dumps(counts, sort_keys=True), json.dumps(id_map, sort_keys=True)))
        finally:
            source.close()
        return {**preview, "imported": True, "dry_run": False, "counts": counts, "id_map": id_map}

    def close(self) -> None:
        with self._lock:
            self.connection.close()


@dataclass(slots=True)
class JournalRuntime:
    store: JournalStore
    vehicles: dict[str, JournalVehicle]
    enabled: bool = False
    _unsub: Any = None
    _hass: Any = None

    async def async_start(self, hass: Any | None = None) -> None:
        """Listen to tracker changes only when the module is explicitly enabled."""
        self._hass = hass
        if not self.enabled or hass is None or self._unsub is not None:
            return
        trackers = {vehicle.tracker_entity_id: vehicle_id for vehicle_id, vehicle in self.vehicles.items() if vehicle.tracker_entity_id}

        async def on_state_changed(event: Any) -> None:
            entity_id = event.data.get("entity_id")
            vehicle_id = trackers.get(entity_id)
            new_state = event.data.get("new_state")
            if vehicle_id is None or new_state is None or new_state.state in {"unknown", "unavailable"}:
                return
            try:
                latitude = float(new_state.attributes["latitude"])
                longitude = float(new_state.attributes["longitude"])
            except (KeyError, TypeError, ValueError):
                return
            await hass.async_add_executor_job(self.store.add_gps_point, vehicle_id, latitude, longitude)

        self._unsub = hass.bus.async_listen("state_changed", on_state_changed)

    async def async_stop(self) -> None:
        if self._unsub is not None:
            self._unsub()
            self._unsub = None
        self.store.close()

    async def async_create_trip(self, vehicle_id: str, title: str, **fields: Any) -> str:
        if vehicle_id not in self.vehicles:
            raise ValueError("vehicle_not_found")
        return self.store.create_trip(vehicle_id, title, **fields)
