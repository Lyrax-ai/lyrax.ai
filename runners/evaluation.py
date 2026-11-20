import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from evaluators.a2a_client import fetch_agent_card
from evaluators.mcp_client import MCPClient, MCPClientError


REPORTS_DIR = Path("reports")


def determine_status(checks):
    statuses = {
        item.get("status", "NOT_RUN")
        for item in checks
    }

    if "FAIL" in statuses:
        return "FAIL"

    if "UNSUPPORTED" in statuses:
        return "UNSUPPORTED"

    if "NOT_RUN" in statuses:
        return "NOT_RUN"

    return "PASS"


def build_evaluation_report(agent, protocol_results):
    protocols = {}

    for protocol, result in protocol_results.items():
        protocols[protocol] = result

    statuses = [
        result.get("status", "NOT_RUN")
        for result in protocols.values()
    ]

    if "FAIL" in statuses:
        overall_status = "FAIL"
    elif "UNSUPPORTED" in statuses:
        overall_status = "UNSUPPORTED"
    elif "NOT_RUN" in statuses:
        overall_status = "NOT_RUN"
    elif statuses and all(status == "PASS" for status in statuses):
        overall_status = "PASS"
    else:
        overall_status = "NOT_RUN"

    return {
        "evaluation_id": (
            f"agent-{agent.id}-"
            f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
        ),
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "provider": agent.provider,
            "endpoint": agent.endpoint,
            "version": agent.version,
        },
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "protocol_compliance",
        "status": overall_status,
        "protocols": protocols,
        "limitations": [
            "Protocol compliance does not establish task accuracy.",
            "Capability and reliability evaluations are separate.",
            "Only protocols declared in the agent profile are evaluated.",
        ],
    }


async def evaluate_a2a(endpoint):
    evidence = {
        "protocol": "A2A",
        "operation": "agent_card_validation",
        "status": "NOT_RUN",
    }

    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,
        ) as client:
            result = await fetch_agent_card(client, endpoint)

        evidence.update(result)

    except Exception as error:
        evidence.update({
            "status": "FAIL",
            "error": str(error),
        })

    return evidence


def evaluate_mcp(endpoint):
    evidence = {
        "protocol": "MCP",
        "operations": {},
    }

    try:
        client = MCPClient(endpoint)

        discovery = client.discover()
        evidence["operations"]["server_discover"] = discovery

        if discovery["status"] != "PASS":
            evidence["status"] = discovery["status"]
            return evidence

        tools = client.list_tools()
        evidence["operations"]["tools_list"] = tools

        evidence["status"] = (
            "PASS"
            if tools["status"] == "PASS"
            else tools["status"]
        )

    except (MCPClientError, ValueError) as error:
        evidence["status"] = "FAIL"
        evidence["error"] = str(error)

    except Exception as error:
        evidence["status"] = "FAIL"
        evidence["error"] = str(error)

    return evidence


async def evaluate_agent(db, agent_id):
    from agents.models import Agent

    agent = db.query(Agent).filter(
        Agent.id == agent_id
    ).first()

    if agent is None:
        raise ValueError(f"Agent {agent_id} was not found.")

    if agent.profile is None:
        raise ValueError(
            f"Agent {agent_id} has no registered profile."
        )

    declared_protocols = {
        protocol.strip().upper()
        for protocol in agent.profile.protocols
        if isinstance(protocol, str)
    }

    protocol_results = {}

    if not declared_protocols:
        protocol_results["registry"] = {
            "status": "NOT_RUN",
            "reason": "No protocols were declared in the agent profile.",
        }

    if not agent.endpoint:
        for protocol in declared_protocols:
            protocol_results[protocol] = {
                "status": "NOT_RUN",
                "reason": "Agent has no registered endpoint.",
            }

    else:
        if "A2A" in declared_protocols:
            protocol_results["A2A"] = await evaluate_a2a(
                agent.endpoint
            )

        if "MCP" in declared_protocols:
            protocol_results["MCP"] = evaluate_mcp(
                agent.endpoint
            )

        for protocol in declared_protocols - {"A2A", "MCP"}:
            protocol_results[protocol] = {
                "status": "UNSUPPORTED",
                "reason": (
                    "Lyrax does not yet implement this protocol."
                ),
            }

    report = build_evaluation_report(
        agent,
        protocol_results,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_path = REPORTS_DIR / (
        f"{report['evaluation_id']}.json"
    )

    report_path.write_text(
        json.dumps(report, indent=2, default=str),
        encoding="utf-8",
    )

    markdown_path = report_path.with_suffix(".md")

    lines = [
        f"# Lyrax Evaluation Report",
        "",
        f"Agent: {agent.name}",
        f"Provider: {agent.provider}",
        f"Evaluation ID: {report['evaluation_id']}",
        f"Overall Status: {report['status']}",
        "",
        "## Protocol Results",
        "",
    ]

    for protocol, result in protocol_results.items():
        lines.extend([
            f"### {protocol}",
            "",
            f"Status: {result.get('status', 'NOT_RUN')}",
            "",
        ])

    lines.extend([
        "## Limitations",
        "",
        *[f"- {item}" for item in report["limitations"]],
    ])

    markdown_path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    report["report_files"] = {
        "json": str(report_path),
        "markdown": str(markdown_path),
    }

    return report
