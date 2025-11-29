"""Generate a Mermaid diagram that captures the Airspace Copilot architecture."""
from pathlib import Path

MERMAID = """
flowchart LR
    subgraph DataPlane
        OpenSky[(OpenSky States API)] -->|bounding boxes| n8n[n8n Workflow]
        n8n -->|writes snapshots| Files[(data/snapshots/*.json)]
        n8n -->|writes alerts| Alerts[(data/alerts.json)]
    end

    subgraph MCP
        Files --> FastAPI{{MCP FastAPI Server}}
        Alerts --> FastAPI
        FastAPI -->|tools| MCPClients[(Agents & Frontend)]
    end

    subgraph Agents
        OpsAgent[Ops Analyst Agent]
        TravelerAgent[Traveler Support Agent]
        OpsAgent <--> TravelerAgent
        MCPClients --> OpsAgent
        MCPClients --> TravelerAgent
    end

    subgraph UI
        Streamlit[Streamlit Frontend]
        Streamlit -->|Traveler Mode chat| TravelerAgent
        Streamlit -->|Ops Mode dashboard| OpsAgent
    end
""".strip() + "\n"

def main() -> None:
    output = Path("architecture_diagram.mmd")
    output.write_text(MERMAID, encoding="utf-8")
    print(f"Mermaid diagram written to {output.resolve()}")


if __name__ == "__main__":
    main()
