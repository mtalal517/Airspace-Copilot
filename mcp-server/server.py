"""FastAPI-based MCP server that exposes flight snapshot tooling."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_SNAPSHOT_DIR = Path(os.getenv("DATA_SNAPSHOT_DIR", BASE_DIR / "data" / "snapshots"))
ALERTS_FILE = Path(os.getenv("ALERTS_FILE", BASE_DIR / "data" / "alerts.json"))
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "region1")

app = FastAPI(title="Airspace MCP Server", version="0.1.0")


class FlightState(BaseModel):
    icao24: str
    callsign: Optional[str]
    origin_country: Optional[str]
    time_position: Optional[int]
    last_contact: Optional[int]
    longitude: Optional[float]
    latitude: Optional[float]
    baro_altitude: Optional[float]
    on_ground: Optional[bool]
    velocity: Optional[float]
    true_track: Optional[float]
    vertical_rate: Optional[float]
    geo_altitude: Optional[float]
    squawk: Optional[str]
    spi: Optional[bool]
    position_source: Optional[int]


class SnapshotResponse(BaseModel):
    region: str
    last_updated: str
    bounds: Dict[str, float]
    states: List[FlightState]


class Alert(BaseModel):
    id: str
    region: str
    callsign: Optional[str]
    type: str
    severity: str
    message: str
    detected_at: str


class AlertsResponse(BaseModel):
    last_updated: str
    alerts: List[Alert]


def _snapshot_path(region: str) -> Path:
    return DATA_SNAPSHOT_DIR / f"{region}.json"


def _load_snapshot(region: str) -> Dict[str, Any]:
    path = _snapshot_path(region)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Snapshot for region '{region}' not found")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail=f"Corrupted snapshot file: {path}") from exc


def _load_alerts() -> Dict[str, Any]:
    if not ALERTS_FILE.exists():
        return {"last_updated": "", "alerts": []}
    try:
        return json.loads(ALERTS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise HTTPException(status_code=500, detail="Alerts file is corrupted") from exc


def _list_regions() -> List[str]:
    if not DATA_SNAPSHOT_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_SNAPSHOT_DIR.glob("*.json"))


def _find_by_callsign(callsign: str) -> Optional[Dict[str, Any]]:
    normalized = callsign.strip().upper()
    for region in _list_regions():
        snapshot = _load_snapshot(region)
        for state in snapshot.get("states", []):
            if (state.get("callsign") or "").strip().upper() == normalized:
                return {"region": region, "snapshot": snapshot, "state": state}
    return None


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "default_region": DEFAULT_REGION}


@app.get("/flights/regions")
def list_regions() -> Dict[str, List[str]]:
    return {"regions": _list_regions()}


@app.get("/flights/region/{region}", response_model=SnapshotResponse)
def get_region_snapshot(region: str) -> SnapshotResponse:
    data = _load_snapshot(region)
    return SnapshotResponse(**data)


@app.get("/flights/callsign/{callsign}")
def get_flight_by_callsign(callsign: str) -> Dict[str, Any]:
    result = _find_by_callsign(callsign)
    if not result:
        raise HTTPException(status_code=404, detail=f"Callsign '{callsign}' not found in any region")
    return result


@app.get("/alerts", response_model=AlertsResponse)
def list_alerts() -> AlertsResponse:
    return AlertsResponse(**_load_alerts())


@app.get("/tools")
def describe_tools() -> Dict[str, Any]:
    """Expose metadata describing the MCP tools available."""
    base_url = os.getenv("MCP_BASE_URL", "http://localhost:8000")
    return {
        "tools": [
            {
                "name": "flights.list_region_snapshot",
                "method": "GET",
                "endpoint": f"{base_url}/flights/region/{{region}}",
                "description": "Returns the latest snapshot for a given region.",
                "inputs": {"region": "Region identifier, e.g., region1"},
            },
            {
                "name": "flights.get_by_callsign",
                "method": "GET",
                "endpoint": f"{base_url}/flights/callsign/{{callsign}}",
                "description": "Fetch the most recent reading for a callsign across all regions.",
                "inputs": {"callsign": "Target callsign"},
            },
            {
                "name": "alerts.list_active",
                "method": "GET",
                "endpoint": f"{base_url}/alerts",
                "description": "List any active alerts detected by the ingestion pipeline.",
                "inputs": {},
            },
        ]
    }
