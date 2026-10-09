"""
Resilient Local Storage Layer for BharatRiskAI.
Provides a self-contained, in-memory & JSON-persisted database matching
the Supabase PostgREST table query builder interface.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("bharatrisk.local_db")

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_DB_PATH = REPO_ROOT / "data" / "local_db.json"


# Default seed data for Kolkata Metropolitan Area
DEFAULT_ZONES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "Zone 17 - Dhapa Wetlands",
        "latitude": 22.5460,
        "longitude": 88.4380,
        "rainfall_24h": 186.0,
        "rainfall_7d": 512.0,
        "elevation": 4.2,
        "drainage_score": 32.0,
        "population_density": 18500.0,
        "population": 41000,
        "historical_flood_count": 12,
        "citizen_report_count": 2,
        "risk_score": 88.4,
        "risk_category": "CRITICAL",
        "area_km2": 3.1,
    },
    {
        "id": 2,
        "name": "Zone 08 - Kalighat",
        "latitude": 22.5220,
        "longitude": 88.3430,
        "rainfall_24h": 154.0,
        "rainfall_7d": 448.0,
        "elevation": 8.5,
        "drainage_score": 42.0,
        "population_density": 23600.0,
        "population": 38500,
        "historical_flood_count": 8,
        "citizen_report_count": 1,
        "risk_score": 79.2,
        "risk_category": "CRITICAL",
        "area_km2": 2.4,
    },
    {
        "id": 3,
        "name": "Zone 04 - Salt Lake Sector V",
        "latitude": 22.5750,
        "longitude": 88.4330,
        "rainfall_24h": 138.0,
        "rainfall_7d": 390.0,
        "elevation": 6.8,
        "drainage_score": 51.0,
        "population_density": 17500.0,
        "population": 32000,
        "historical_flood_count": 6,
        "citizen_report_count": 0,
        "risk_score": 64.5,
        "risk_category": "HIGH",
        "area_km2": 3.8,
    },
    {
        "id": 4,
        "name": "Zone 12 - Howrah Maidan",
        "latitude": 22.5890,
        "longitude": 88.3100,
        "rainfall_24h": 168.0,
        "rainfall_7d": 470.0,
        "elevation": 5.5,
        "drainage_score": 38.0,
        "population_density": 28200.0,
        "population": 46000,
        "historical_flood_count": 10,
        "citizen_report_count": 1,
        "risk_score": 82.1,
        "risk_category": "CRITICAL",
        "area_km2": 2.9,
    },
    {
        "id": 5,
        "name": "Zone 21 - Behala",
        "latitude": 22.4990,
        "longitude": 88.3100,
        "rainfall_24h": 142.0,
        "rainfall_7d": 410.0,
        "elevation": 7.2,
        "drainage_score": 45.0,
        "population_density": 21400.0,
        "population": 39800,
        "historical_flood_count": 7,
        "citizen_report_count": 0,
        "risk_score": 69.8,
        "risk_category": "HIGH",
        "area_km2": 4.2,
    },
    {
        "id": 6,
        "name": "Zone 02 - Esplanade",
        "latitude": 22.5670,
        "longitude": 88.3520,
        "rainfall_24h": 126.0,
        "rainfall_7d": 345.0,
        "elevation": 10.5,
        "drainage_score": 61.0,
        "population_density": 30800.0,
        "population": 27500,
        "historical_flood_count": 5,
        "citizen_report_count": 0,
        "risk_score": 55.3,
        "risk_category": "HIGH",
        "area_km2": 1.8,
    },
    {
        "id": 7,
        "name": "Zone 25 - Rajarhat",
        "latitude": 22.6230,
        "longitude": 88.4800,
        "rainfall_24h": 118.0,
        "rainfall_7d": 310.0,
        "elevation": 9.8,
        "drainage_score": 64.0,
        "population_density": 12200.0,
        "population": 24000,
        "historical_flood_count": 3,
        "citizen_report_count": 0,
        "risk_score": 48.0,
        "risk_category": "MEDIUM",
        "area_km2": 5.2,
    },
    {
        "id": 8,
        "name": "Zone 31 - Tollygunge",
        "latitude": 22.4960,
        "longitude": 88.3490,
        "rainfall_24h": 132.0,
        "rainfall_7d": 370.0,
        "elevation": 11.0,
        "drainage_score": 58.0,
        "population_density": 19100.0,
        "population": 30000,
        "historical_flood_count": 4,
        "citizen_report_count": 0,
        "risk_score": 51.7,
        "risk_category": "HIGH",
        "area_km2": 3.6,
    },
]

DEFAULT_EMERGENCIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "message_id": "SOS-KOL-8841",
        "emergency_type": "TRAPPED",
        "latitude": 22.5460,
        "longitude": 88.4380,
        "people": 5,
        "vulnerable": "elderly,child",
        "priority": "CRITICAL",
        "status": "RECEIVED",
        "assigned_resource_id": None,
        "ttl": 10,
        "hop_count": 2,
        "created_at": "2026-10-09T15:20:00+00:00",
    },
    {
        "id": 2,
        "message_id": "SOS-KOL-3920",
        "emergency_type": "MEDICAL",
        "latitude": 22.5220,
        "longitude": 88.3430,
        "people": 2,
        "vulnerable": "pregnant",
        "priority": "CRITICAL",
        "status": "ASSIGNED",
        "assigned_resource_id": 4,
        "ttl": 8,
        "hop_count": 1,
        "created_at": "2026-10-09T15:05:00+00:00",
    },
    {
        "id": 3,
        "message_id": "SOS-KOL-1104",
        "emergency_type": "EVACUATION",
        "latitude": 22.5890,
        "longitude": 88.3100,
        "people": 8,
        "vulnerable": "child",
        "priority": "HIGH",
        "status": "RECEIVED",
        "assigned_resource_id": None,
        "ttl": 12,
        "hop_count": 0,
        "created_at": "2026-10-09T14:48:00+00:00",
    },
]

DEFAULT_RESOURCES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "NDRF Quick Response Team Alpha",
        "type": "rescue_team",
        "latitude": 22.5700,
        "longitude": 88.4300,
        "quantity": 5,
        "available": 4,
        "road_status": "OPEN",
    },
    {
        "id": 2,
        "name": "Inflatable Rescue Boat Unit 03",
        "type": "boat",
        "latitude": 22.5400,
        "longitude": 88.4350,
        "quantity": 6,
        "available": 5,
        "road_status": "OPEN",
    },
    {
        "id": 3,
        "name": "Heavy Dewatering Pump Station 02",
        "type": "water_pump",
        "latitude": 22.5200,
        "longitude": 88.3400,
        "quantity": 8,
        "available": 6,
        "road_status": "OPEN",
    },
    {
        "id": 4,
        "name": "KMC Disaster Mobile Ambulance",
        "type": "ambulance",
        "latitude": 22.5650,
        "longitude": 88.3500,
        "quantity": 4,
        "available": 3,
        "road_status": "OPEN",
    },
    {
        "id": 5,
        "name": "Civil Defense Personnel Batt. 1",
        "type": "emergency_personnel",
        "latitude": 22.5800,
        "longitude": 88.3150,
        "quantity": 12,
        "available": 10,
        "road_status": "OPEN",
    },
    {
        "id": 6,
        "name": "Salt Lake Stadium Flood Shelter",
        "type": "shelter",
        "latitude": 22.5780,
        "longitude": 88.4200,
        "quantity": 1,
        "available": 1,
        "road_status": "OPEN",
    },
]

DEFAULT_REPORTS: List[Dict[str, Any]] = [
    {
        "id": 1,
        "zone_id": 1,
        "latitude": 22.5465,
        "longitude": 88.4382,
        "water_level_cm": 65.0,
        "description": "Severe waterlogging above 60cm near EM Bypass connector. Multiple vehicles stalled.",
        "photo_url": None,
        "severity": "CRITICAL",
        "credible": True,
        "created_at": "2026-10-09T15:15:00+00:00",
    },
    {
        "id": 2,
        "zone_id": 2,
        "latitude": 22.5225,
        "longitude": 88.3435,
        "water_level_cm": 42.0,
        "description": "Drainage backup near Kalighat temple approach road, water entering low-lying shops.",
        "photo_url": None,
        "severity": "HIGH",
        "credible": True,
        "created_at": "2026-10-09T15:00:00+00:00",
    },
    {
        "id": 3,
        "zone_id": 4,
        "latitude": 22.5895,
        "longitude": 88.3105,
        "water_level_cm": 28.0,
        "description": "Subway and underpass water accumulation restricting two-wheeler traffic.",
        "photo_url": None,
        "severity": "MEDIUM",
        "credible": True,
        "created_at": "2026-10-09T14:40:00+00:00",
    },
]


class LocalPostgrestResponse:
    """Matches the response contract of postgrest-py / supabase-py."""
    def __init__(self, data: Optional[List[Dict[str, Any]]] = None, count: Optional[int] = None):
        self.data: List[Dict[str, Any]] = data if data is not None else []
        self.count: Optional[int] = count

    def __repr__(self) -> str:
        return f"LocalPostgrestResponse(data_count={len(self.data)}, count={self.count})"


class LocalQueryBuilder:
    """Emulates Supabase PostgREST query builder chaining."""
    def __init__(self, table_name: str, db: LocalDatabase):
        self.table_name = table_name
        self.db = db
        self._columns: str = "*"
        self._count_mode: Optional[str] = None
        self._filters: List[Callable[[Dict[str, Any]], bool]] = []
        self._orders: List[tuple[str, bool]] = []  # (column, desc)
        self._limit: Optional[int] = None
        self._operation: str = "select"
        self._payload: Any = None
        self._on_conflict: Optional[str] = None

    def select(self, columns: str = "*", count: Optional[str] = None) -> LocalQueryBuilder:
        self._operation = "select"
        self._columns = columns
        self._count_mode = count
        return self

    def eq(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) == value)
        return self

    def neq(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) != value)
        return self

    def gt(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) is not None and r.get(column) > value)
        return self

    def gte(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) is not None and r.get(column) >= value)
        return self

    def lt(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) is not None and r.get(column) < value)
        return self

    def lte(self, column: str, value: Any) -> LocalQueryBuilder:
        self._filters.append(lambda r: r.get(column) is not None and r.get(column) <= value)
        return self

    def order(self, column: str, desc: bool = False) -> LocalQueryBuilder:
        self._orders.append((column, desc))
        return self

    def limit(self, count: int) -> LocalQueryBuilder:
        self._limit = count
        return self

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> LocalQueryBuilder:
        self._operation = "insert"
        self._payload = data
        return self

    def update(self, data: Dict[str, Any]) -> LocalQueryBuilder:
        self._operation = "update"
        self._payload = data
        return self

    def upsert(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        on_conflict: Optional[str] = None,
    ) -> LocalQueryBuilder:
        self._operation = "upsert"
        self._payload = data
        self._on_conflict = on_conflict
        return self

    def delete(self) -> LocalQueryBuilder:
        self._operation = "delete"
        return self

    def execute(self) -> LocalPostgrestResponse:
        return self.db._execute(self)


class LocalDatabase:
    """Thread-safe, file-persisted local database store."""
    def __init__(self, persistence_path: Path = LOCAL_DB_PATH):
        self.persistence_path = persistence_path
        self._lock = threading.RLock()
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self.persistence_path.exists():
                try:
                    with open(self.persistence_path, "r", encoding="utf-8") as f:
                        self.tables = json.load(f)
                    logger.info(f"Loaded local database from {self.persistence_path}")
                except Exception as exc:
                    logger.warning(f"Failed to read {self.persistence_path} ({exc}), re-seeding defaults.")
                    self.tables = {}

            # Seed default tables if missing or empty
            if not self.tables.get("zones"):
                self.tables["zones"] = deepcopy(DEFAULT_ZONES)
            if "emergencies" not in self.tables or not self.tables["emergencies"]:
                self.tables["emergencies"] = deepcopy(DEFAULT_EMERGENCIES)
            if "resources" not in self.tables or not self.tables["resources"]:
                self.tables["resources"] = deepcopy(DEFAULT_RESOURCES)
            if "citizen_reports" not in self.tables or not self.tables["citizen_reports"]:
                self.tables["citizen_reports"] = deepcopy(DEFAULT_REPORTS)
            self.tables.setdefault("sync_queue", [])
            self.tables.setdefault("risk_assessments", [])
            self.tables.setdefault("recommendations", [])
            self.tables.setdefault("shelters", [])
            self.tables.setdefault("roads", [])
            self.tables.setdefault("alert_deliveries", [])

            self._save()

    def _save(self) -> None:
        with self._lock:
            try:
                self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = self.persistence_path.with_suffix(".json.tmp")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(self.tables, f, indent=2, default=str)
                tmp_path.replace(self.persistence_path)
            except Exception as exc:
                logger.error(f"Failed to persist local database: {exc}")

    def _next_id(self, table_name: str) -> int:
        existing = self.tables.get(table_name, [])
        return max((r["id"] for r in existing if isinstance(r.get("id"), int)), default=0) + 1

    def _execute(self, builder: LocalQueryBuilder) -> LocalPostgrestResponse:
        with self._lock:
            op = builder._operation
            table = builder.table_name

            if op == "select":
                rows = [deepcopy(r) for r in self.tables.get(table, [])]
                for f in builder._filters:
                    rows = [r for r in rows if f(r)]

                count = len(rows) if builder._count_mode == "exact" else None

                if builder._orders:
                    for col, desc in reversed(builder._orders):
                        def sort_key(r: Dict[str, Any]):
                            val = r.get(col)
                            if val is None:
                                return (1, "")
                            return (0, val)
                        rows.sort(key=sort_key, reverse=desc)

                if builder._limit is not None:
                    rows = rows[: builder._limit]

                if builder._columns and builder._columns != "*":
                    col_names = [c.strip() for c in builder._columns.split(",") if c.strip()]
                    if col_names:
                        rows = [{k: r.get(k) for k in col_names if k in r} for r in rows]

                return LocalPostgrestResponse(data=rows, count=count)

            elif op == "insert":
                payload = builder._payload
                items = [payload] if isinstance(payload, dict) else list(payload)
                inserted = []
                for item in items:
                    row = deepcopy(item)
                    if "id" not in row or row["id"] is None:
                        row["id"] = self._next_id(table)
                    if "created_at" not in row or row["created_at"] is None:
                        row["created_at"] = datetime.now(timezone.utc).isoformat()
                    self.tables.setdefault(table, []).append(row)
                    inserted.append(deepcopy(row))
                self._save()
                return LocalPostgrestResponse(data=inserted, count=len(inserted))

            elif op == "update":
                payload = deepcopy(builder._payload)
                table_rows = self.tables.setdefault(table, [])
                updated = []
                for row in table_rows:
                    if all(f(row) for f in builder._filters):
                        row.update(payload)
                        updated.append(deepcopy(row))
                self._save()
                return LocalPostgrestResponse(data=updated, count=len(updated))

            elif op == "upsert":
                payload = builder._payload
                items = [payload] if isinstance(payload, dict) else list(payload)
                conflict_keys = (
                    [k.strip() for k in builder._on_conflict.split(",")]
                    if builder._on_conflict
                    else ["id"]
                )
                table_rows = self.tables.setdefault(table, [])
                upserted = []
                for item in items:
                    row = deepcopy(item)
                    match_idx = None
                    for idx, existing in enumerate(table_rows):
                        if all(existing.get(k) == row.get(k) for k in conflict_keys):
                            match_idx = idx
                            break
                    if match_idx is not None:
                        table_rows[match_idx].update(row)
                        upserted.append(deepcopy(table_rows[match_idx]))
                    else:
                        if "id" not in row or row["id"] is None:
                            row["id"] = self._next_id(table)
                        if "created_at" not in row or row["created_at"] is None:
                            row["created_at"] = datetime.now(timezone.utc).isoformat()
                        table_rows.append(row)
                        upserted.append(deepcopy(row))
                self._save()
                return LocalPostgrestResponse(data=upserted, count=len(upserted))

            elif op == "delete":
                table_rows = self.tables.get(table, [])
                retained = []
                deleted = []
                for row in table_rows:
                    if all(f(row) for f in builder._filters):
                        deleted.append(deepcopy(row))
                    else:
                        retained.append(row)
                self.tables[table] = retained
                self._save()
                return LocalPostgrestResponse(data=deleted, count=len(deleted))

            raise ValueError(f"Unknown operation: {op}")


class LocalSupabaseClient:
    """Drop-in mock for Supabase Client."""
    def __init__(self, db: Optional[LocalDatabase] = None):
        self._db = db or _default_db

    def table(self, table_name: str) -> LocalQueryBuilder:
        return LocalQueryBuilder(table_name, self._db)

    def from_(self, table_name: str) -> LocalQueryBuilder:
        return self.table(table_name)


# Global singleton database instance
_default_db = LocalDatabase()
_local_client = LocalSupabaseClient(_default_db)


def get_local_database() -> LocalDatabase:
    return _default_db


def get_local_client() -> LocalSupabaseClient:
    return _local_client
