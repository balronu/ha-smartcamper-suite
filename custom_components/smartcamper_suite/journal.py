"""Camper Travel Journal runtime for the SmartCamper Suite.

The journal deliberately owns a separate SQLite file from the legacy
``camper_travel_journal`` integration.  The adapter is small and synchronous
at its storage boundary so Home Assistant can execute it in its executor.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

JOURNAL_SCHEMA_VERSION = 1
TRIP_STATUSES = {"planned", "active", "completed", "cancelled"}
EXPENSE_CATEGORIES = {"camping", "fuel", "toll", "parking", "food", "activities", "other"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


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
            self.connection.execute("INSERT INTO stops(id,vehicle_id,trip_id,name,occurred_at,latitude,longitude,description,category,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (stop_id, vehicle_id, fields.get("trip_id"), str(fields.get("name", "Zwischenstopp")).strip() or "Zwischenstopp", fields.get("occurred_at", now), fields.get("latitude"), fields.get("longitude"), fields.get("description", ""), fields.get("category", "other"), now, now))
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

    def preview_legacy_import(self, source_path: str | Path) -> dict[str, Any]:
        source = Path(source_path)
        if not source.is_file():
            raise FileNotFoundError("legacy_database_not_found")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
        try:
            tables = {row[0] for row in source_db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            mapping = {table: table for table in ("trips", "stays", "stops", "expenses", "gps_points") if table in tables}
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
                for table in ("trips", "stays", "stops", "expenses", "gps_points"):
                    if table not in preview["mapping"]:
                        continue
                    columns = {row[1] for row in source.execute(f"PRAGMA table_info({table})")}
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
