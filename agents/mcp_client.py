"""Simple HTTP client used by agents to call MCP tools."""
from __future__ import annotations

from typing import Any, Dict, Optional
import os

import httpx


class MCPClient:
    """Lightweight wrapper around the REST-style MCP tools."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0) -> None:
        self.base_url = base_url or os.getenv("MCP_BASE_URL", "http://localhost:8000")
        self._client = httpx.Client(timeout=timeout)

    def list_region_snapshot(self, region: str) -> Dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/flights/region/{region}")
        resp.raise_for_status()
        return resp.json()

    def find_by_callsign(self, callsign: str) -> Dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/flights/callsign/{callsign}")
        resp.raise_for_status()
        return resp.json()

    def list_alerts(self) -> Dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/alerts")
        resp.raise_for_status()
        return resp.json()

    def list_regions(self) -> Dict[str, Any]:
        resp = self._client.get(f"{self.base_url}/flights/regions")
        resp.raise_for_status()
        return resp.json()
