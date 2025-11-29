"""Traveler Support agent helpers."""
from __future__ import annotations

from typing import Any, Dict

import httpx

from .mcp_client import MCPClient


class TravelerSupportAgent:
    """Collates snapshot data for traveler question answering."""

    def __init__(self, client: MCPClient | None = None) -> None:
        self.client = client or MCPClient()

    def get_flight_context(self, callsign: str) -> Dict[str, Any]:
        try:
            payload = self.client.find_by_callsign(callsign)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {
                    "region": None,
                    "last_updated": None,
                    "state": {},
                    "status": "Flight not found in latest snapshots. Please verify the callsign.",
                }
            raise

        state = payload.get("state", {})
        status = self._derive_status(state)
        return {
            "region": payload.get("region"),
            "last_updated": payload.get("snapshot", {}).get("last_updated"),
            "state": state,
            "status": status,
        }

    def _derive_status(self, state: Dict[str, Any]) -> str:
        if not state:
            return "No telemetry available."
        if state.get("on_ground"):
            return "Aircraft is currently on the ground."
        altitude = state.get("geo_altitude") or state.get("baro_altitude")
        velocity = state.get("velocity")
        if altitude and velocity:
            return f"Aircraft cruising at approx {altitude:.0f} m with ground speed {velocity:.0f} m/s."
        if altitude:
            return f"Aircraft altitude approx {altitude:.0f} m."
        return "Telemetry is partial but aircraft is airborne."
