from __future__ import annotations

import copy
import sqlite3
from pathlib import Path
from typing import Any

from .const import STORAGE_VERSION
from .models import Vehicle


class SuiteStore:
    """Versioned, isolated SQLite store. Phase 2A never opens legacy databases."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS vehicles (
              vehicle_id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT NOT NULL,
              archived INTEGER NOT NULL DEFAULT 0
            );
        """)
        self.connection.execute("INSERT OR REPLACE INTO metadata(key,value) VALUES('schema_version',?)", (str(STORAGE_VERSION),))
        self.connection.commit()

    def save_vehicle(self, vehicle: Vehicle) -> None:
        import json
        payload = json.dumps(vehicle.to_dict(), sort_keys=True)
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO vehicles(vehicle_id,name,payload,archived) VALUES(?,?,?,?)", (vehicle.vehicle_id, vehicle.name, payload, int(vehicle.archived)))

    def list_vehicles(self, include_archived: bool = False) -> list[Vehicle]:
        import json
        query = "SELECT payload FROM vehicles" if include_archived else "SELECT payload FROM vehicles WHERE archived=0"
        return [Vehicle.from_dict(json.loads(row[0])) for row in self.connection.execute(query)]

    def archive_vehicle(self, vehicle_id: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE vehicles SET archived=1 WHERE vehicle_id=?", (vehicle_id,))

    def snapshot(self) -> dict[str, Any]:
        return {"schema_version": STORAGE_VERSION, "vehicles": [copy.deepcopy(v.to_dict()) for v in self.list_vehicles(True)]}
