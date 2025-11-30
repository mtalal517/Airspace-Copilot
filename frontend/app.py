"""Streamlit UI for the Airspace Copilot."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

load_dotenv(ROOT / ".env")

from agents.mcp_client import MCPClient
from agents.ops_agent import OpsAnalystAgent
from agents.crew_runner import run_crewai

N8N_WEBHOOK_BASE = os.getenv("N8N_WEBHOOK_BASE", "http://localhost:5678/webhook-test/airspace")

st.set_page_config(page_title="Airspace Copilot", layout="wide")

client = MCPClient()
ops_helper = OpsAnalystAgent(client)


def _trigger_latest_snapshot(region: str) -> str:
    url = f"{N8N_WEBHOOK_BASE.rstrip('/')}/latest"
    resp = httpx.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json().get("last_updated", "recent")


def _rerun_app() -> None:
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
        return
    legacy = getattr(st, "experimental_rerun", None)
    if callable(legacy):
        legacy()


def render_ops_mode() -> None:
    st.header("Operations Mode")
    regions = client.list_regions().get("regions", []) or ["region1"]
    region = st.selectbox("Region", regions)
    if st.button("Fetch Latest Snapshot", type="primary"):
        try:
            timestamp = _trigger_latest_snapshot(region)
            st.success(f"Snapshot refreshed ({timestamp}). Reloading dashboard...")
            _rerun_app()
        except Exception as exc:  # pragma: no cover - UI fallback
            st.error(f"Failed to trigger snapshot: {exc}")

    st.session_state["ops_region"] = region
    try:
        report = ops_helper.analyze_region(region)
        st.caption(f"Last updated {report['last_updated']}")
        metrics = report["metrics"]
        cols = st.columns(3)
        cols[0].metric("Tracked", metrics["aircraft"])
        cols[1].metric("Avg altitude", metrics.get("avg_altitude"))
        cols[2].metric("Avg velocity", metrics.get("avg_velocity"))

        states = report.get("bounds")
        st.json({"bounds": states})

        states_df = pd.DataFrame(client.list_region_snapshot(region).get("states", []))
        if not states_df.empty:
            st.dataframe(states_df)
        else:
            st.info("No aircraft in snapshot.")

        anomalies = pd.DataFrame(report.get("anomalies", []))
        if not anomalies.empty:
            st.subheader("Anomalies")
            st.dataframe(anomalies)
        else:
            st.success("No anomalies detected")

        st.subheader("Summary")
        st.write(report["summary"])
    except Exception as exc:  # pragma: no cover - UI fallback
        st.error(f"Failed to load region snapshot: {exc}")


def render_traveler_mode() -> None:
    st.header("Traveler Mode")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    callsign = st.text_input("Callsign", value="TEST123")
    question = st.text_area("Question", value="Is my flight on time?", height=100)
    if st.button("Ask Copilot"):
        st.session_state.chat_history.append({"role": "user", "text": question})
        try:
            outputs = run_crewai(region=st.session_state.get("ops_region", "region1"), callsign=callsign, question=question)
            st.session_state.chat_history.append({"role": "assistant", "text": outputs["traveler_response"]})
        except Exception as exc:  # pragma: no cover - UI fallback
            st.session_state.chat_history.append({"role": "error", "text": str(exc)})
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["text"])
        elif msg["role"] == "assistant":
            st.chat_message("assistant").write(msg["text"])
        else:
            st.chat_message("assistant").write(f"⚠️ {msg['text']}")


def main() -> None:
    tab1, tab2 = st.tabs(["Traveler Mode", "Ops Mode"])
    with tab1:
        render_traveler_mode()
    with tab2:
        render_ops_mode()


if __name__ == "__main__":
    main()
