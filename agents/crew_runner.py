"""LangGraph-based multi-agent runner using Groq LLM."""
from __future__ import annotations

import argparse
import json
import os
from functools import lru_cache
from typing import Any, Dict, List, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import END, StateGraph

from .mcp_client import MCPClient
from .ops_agent import OpsAnalystAgent
from .traveler_agent import TravelerSupportAgent

client = MCPClient()
ops_helper = OpsAnalystAgent(client)
traveler_helper = TravelerSupportAgent(client)


class GraphState(TypedDict, total=False):
    region: str
    callsign: str
    question: str
    ops_report: str
    ops_structured: Dict[str, Any]
    traveler_response: str
    flight_context: Dict[str, Any]
    alerts: Dict[str, Any]
    last_updated: str
    errors: List[str]


OPS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an operations analyst summarizing real-time airspace telemetry. "
            "Respond in markdown with sections: METRICS, ANOMALIES, RECOMMENDATIONS, and HANDOFF. "
            "Handoff should be a concise note for the traveler support agent.",
        ),
        (
            "human",
            "Region: {region}\n"
            "Traveler question: {question}\n"
            "Snapshot JSON: {analysis_json}\n"
            "Alerts JSON: {alerts_json}\n"
            "Please follow the required sections strictly.",
        ),
    ]
)

TRAVELER_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are a traveler support agent. Use the provided telemetry and ops handoff to answer in friendly prose."
            " Include a status sentence, a movement/altitude highlight, and mention anomalies only if relevant.",
        ),
        (
            "human",
            "Callsign: {callsign}\n"
            "Traveler question: {question}\n"
            "Ops handoff: {ops_report}\n"
            "Flight context JSON: {flight_json}\n"
            "Respond as a short chat reply.",
        ),
    ]
)


def build_llm() -> ChatGroq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    temperature = float(os.getenv("GROQ_TEMPERATURE", "0.2"))
    return ChatGroq(model=model, groq_api_key=api_key, temperature=temperature)


def _compact_analysis(analysis: Dict[str, Any], alerts: Dict[str, Any]) -> Dict[str, Any]:
    compact = {
        "region": analysis.get("region"),
        "last_updated": analysis.get("last_updated"),
        "metrics": analysis.get("metrics"),
        "summary": analysis.get("summary"),
        "anomalies": (analysis.get("anomalies") or [])[:15],
    }
    slim_alerts = dict(alerts)
    slim_alerts["alerts"] = (alerts.get("alerts") or [])[:10]
    compact["alerts"] = slim_alerts["alerts"]
    return compact


def _compact_flight(flight: Dict[str, Any]) -> Dict[str, Any]:
    state = flight.get("state") or {}
    return {
        "region": flight.get("region"),
        "last_updated": flight.get("last_updated"),
        "status": flight.get("status"),
        "callsign": state.get("callsign"),
        "icao24": state.get("icao24"),
        "latitude": state.get("latitude"),
        "longitude": state.get("longitude"),
        "altitude": state.get("geo_altitude") or state.get("baro_altitude"),
        "velocity": state.get("velocity"),
        "on_ground": state.get("on_ground"),
    }


def create_ops_node(llm: ChatGroq):
    parser = StrOutputParser()
    chain = OPS_PROMPT | llm | parser

    def node(state: GraphState) -> GraphState:
        region = state["region"]
        analysis = ops_helper.analyze_region(region)
        alerts = client.list_alerts()
        compact = _compact_analysis(analysis, alerts)
        report = chain.invoke(
            {
                "region": region,
                "question": state.get("question", ""),
                "analysis_json": json.dumps(compact, ensure_ascii=False),
                "alerts_json": json.dumps({"alerts": compact.get("alerts", [])}, ensure_ascii=False),
            }
        )
        next_state = dict(state)
        next_state["ops_report"] = report
        next_state["ops_structured"] = analysis
        next_state["alerts"] = alerts
        next_state["last_updated"] = analysis.get("last_updated")
        return next_state

    return node


def create_traveler_node(llm: ChatGroq):
    parser = StrOutputParser()
    chain = TRAVELER_PROMPT | llm | parser

    def node(state: GraphState) -> GraphState:
        callsign = state["callsign"]
        flight = traveler_helper.get_flight_context(callsign)
        compact_flight = _compact_flight(flight)
        reply = chain.invoke(
            {
                "callsign": callsign,
                "question": state.get("question", ""),
                "ops_report": state.get("ops_report", ""),
                "flight_json": json.dumps(compact_flight, ensure_ascii=False),
            }
        )
        next_state = dict(state)
        next_state["traveler_response"] = reply
        next_state["flight_context"] = compact_flight
        return next_state

    return node


@lru_cache(maxsize=1)
def build_graph() -> Any:
    llm = build_llm()
    graph = StateGraph(GraphState)
    graph.add_node("ops", create_ops_node(llm))
    graph.add_node("traveler", create_traveler_node(llm))
    graph.set_entry_point("ops")
    graph.add_edge("ops", "traveler")
    graph.add_edge("traveler", END)
    return graph.compile()


def run_crewai(region: str, callsign: str, question: str) -> Dict[str, Any]:
    graph = build_graph()
    result = graph.invoke({"region": region, "callsign": callsign, "question": question})
    return {
        "ops_report": result.get("ops_report"),
        "traveler_response": result.get("traveler_response"),
        "ops_structured": result.get("ops_structured"),
        "flight_context": result.get("flight_context"),
        "alerts": result.get("alerts"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Airspace Copilot LangGraph workflow")
    parser.add_argument("--region", default=os.getenv("DEFAULT_REGION", "region1"))
    parser.add_argument("--callsign", default="TEST123")
    parser.add_argument("--question", default="Is my flight on time?")
    args = parser.parse_args()
    outputs = run_crewai(region=args.region, callsign=args.callsign, question=args.question)
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
