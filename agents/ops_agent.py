"""Ops Analyst agent helpers for Crew workflows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from .mcp_client import MCPClient


@dataclass
class Anomaly:
    callsign: str
    issue: str
    value: Any


class OpsAnalystAgent:
    """Provides region-level situational awareness."""

    def __init__(self, client: MCPClient | None = None) -> None:
        self.client = client or MCPClient()

    def analyze_region(self, region: str) -> Dict[str, Any]:
        snapshot = self.client.list_region_snapshot(region)
        states = snapshot.get("states", [])
        frame = pd.DataFrame(states)
        metrics = self._compute_metrics(frame)
        anomalies = self._detect_anomalies(states)
        summary = self._build_summary(region, snapshot, metrics, anomalies)
        return {
            "region": region,
            "last_updated": snapshot.get("last_updated"),
            "bounds": snapshot.get("bounds"),
            "metrics": metrics,
            "anomalies": [a.__dict__ for a in anomalies],
            "summary": summary,
        }

    def _compute_metrics(self, frame: pd.DataFrame) -> Dict[str, Any]:
        if frame.empty:
            return {"aircraft": 0, "avg_altitude": None, "avg_velocity": None}
        return {
            "aircraft": int(frame.shape[0]),
            "avg_altitude": round(frame["geo_altitude"].dropna().mean(), 2) if "geo_altitude" in frame else None,
            "avg_velocity": round(frame["velocity"].dropna().mean(), 2) if "velocity" in frame else None,
        }

    def _detect_anomalies(self, states: List[Dict[str, Any]]) -> List[Anomaly]:
        anomalies: List[Anomaly] = []
        for state in states:
            callsign = (state.get("callsign") or state.get("icao24") or "UNKNOWN").strip()
            if state.get("velocity") and state["velocity"] > 280:
                anomalies.append(Anomaly(callsign, "High velocity", state["velocity"]))
            if state.get("baro_altitude") is not None and state["baro_altitude"] < 300:
                anomalies.append(Anomaly(callsign, "Low altitude", state["baro_altitude"]))
            if state.get("last_contact") and state.get("time_position"):
                latency = state["last_contact"] - state["time_position"]
                if latency > 45:
                    anomalies.append(Anomaly(callsign, "Stale telemetry", latency))
            if not state.get("latitude") or not state.get("longitude"):
                anomalies.append(Anomaly(callsign, "Missing coordinates", "n/a"))
        return anomalies

    def _build_summary(
        self,
        region: str,
        snapshot: Dict[str, Any],
        metrics: Dict[str, Any],
        anomalies: List[Anomaly],
    ) -> str:
        lines = [
            f"Region {region} has {metrics['aircraft']} tracked aircraft as of {snapshot.get('last_updated')}.",
        ]
        if metrics.get("avg_altitude"):
            lines.append(f"Average altitude: {metrics['avg_altitude']} m.")
        if metrics.get("avg_velocity"):
            lines.append(f"Average velocity: {metrics['avg_velocity']} m/s.")
        if anomalies:
            lines.append(f"Detected {len(anomalies)} anomalies requiring follow-up.")
        else:
            lines.append("No anomalies detected in the last snapshot.")
        return " ".join(lines)
