# Agentic AI Assignment 3 — Real-Time Airspace Copilot

This project delivers a local, multi-agent **Airspace Copilot** that ingests OpenSky Network traffic, stores region-based snapshots, exposes MCP tools, and powers both ops and traveler workflows.

## Repository Layout

```
airspace-copilot/
├── agents/
│   ├── crew_runner.py
│   ├── ops_agent.py
│   └── traveler_agent.py
├── data/
│   ├── alerts.json
│   └── snapshots/
│       └── region1.json
├── frontend/
│   └── app.py
├── mcp-server/
│   └── server.py
├── n8n/
│   └── airspace_workflow.json
├── .well-known/
│   └── mcp.json
├── architecture_diagram.py
├── requirements.txt
└── README.md
```

## Prerequisites

- Python 3.11+
- Docker Desktop (for n8n)
- Node 18+ (optional if editing Streamlit assets)
- Groq API key

## Environment Variables

Create `.env` in the project root:

```
GROQ_API_KEY=sk-...
MCP_BASE_URL=http://localhost:8000
DATA_SNAPSHOT_DIR=./data/snapshots
DEFAULT_REGION=region1
ALERTS_FILE=./data/alerts.json
GROQ_MODEL=mixtral-8x7b-32768
```

## Quick Start

1. **Install deps**
   ```powershell
   cd airspace-copilot
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Run MCP server**
   ```powershell
   uvicorn mcp-server.server:app --reload --port 8000
   ```

3. **Run LangGraph agents**
   ```powershell
   python -m agents.crew_runner --region region1 --callsign TEST123 --question "Is my flight on time?"
   ```

4. **Start Streamlit frontend**
   ```powershell
   streamlit run frontend/app.py
   ```

5. **Start n8n (Docker)**
   ```powershell
   docker run -it --rm -p 5678:5678 -v ${PWD}/n8n:/home/node/.n8n n8nio/n8n
   ```
   Import `n8n/airspace_workflow.json` and set credentials.

## Architecture Diagram

Generate Mermaid description via:
```powershell
python architecture_diagram.py
```
The script outputs `architecture_diagram.mmd` you can paste into any Mermaid renderer.

## Data Flow Overview

1. **n8n workflow** polls OpenSky with bounding boxes, stores JSON snapshots per region, and exposes a webhook that returns the latest snapshot.
2. **FastAPI MCP server** reads stored JSON files and serves the MCP tools (`flights.list_region_snapshot`, `flights.get_by_callsign`, `alerts.list_active`).
3. **LangGraph agents** (Ops Analyst & Traveler Support) call MCP tools via HTTP clients and collaborate via A2A handoffs, powered by Groq LLMs.
4. **Streamlit UI** provides Traveler Mode chat and Ops Mode region dashboards referencing the same MCP tools for consistency.

## Next Steps

- Configure additional regions by adding bounding boxes to the n8n workflow and creating matching `data/snapshots/<region>.json` files.
- Extend anomaly detection rules in `ops_agent.py` or the MCP server if on-server compute is preferred.
- Harden persistence (e.g., SQLite) if multiple concurrent users require write isolation.
