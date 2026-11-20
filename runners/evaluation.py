import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from evaluators.a2a_client import fetch_agent_card
from evaluators.endpoint_security import validate_endpoint
from evaluators.pinned_transport import create_pinned_async_transport
from evaluators.mcp_client import MCPClient, MCPClientError
from evaluators.test_case_loader import load_test_case
from evaluators.capability_execution import (
    execute_a2a_test_cases,
    execute_mcp_test_cases,
)


REPORTS_DIR = Path("reports")
TEST_CASES_DIR = Path("test_cases")


def determine_status(checks):
    if not checks:
        return "NOT_RUN"

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


def _combined_status(results):
    statuses = [
        result.get("status", "NOT_RUN")
        for result in results
    ]

    if "FAIL" in statuses:
        return "FAIL"

    if "UNSUPPORTED" in statuses:
        return "UNSUPPORTED"

    if "NOT_RUN" in statuses:
        return "NOT_RUN"

    if statuses and all(status == "PASS" for status in statuses):
        return "PASS"

    return "NOT_RUN"


def build_evaluation_report(
    agent,
    protocol_results,
    capability_results=None,
):
    protocols = dict(protocol_results)
    capabilities = capability_results or {}

    protocol_status = _combined_status(list(protocols.values()))

    capability_statuses = [
        result.get("status", "NOT_RUN")
        for result in capabilities.values()
    ]

    # Preserve protocol status unless capability execution finds
    # an actual failure. NOT_RUN capability checks do not invalidate
    # a successful protocol-compliance evaluation.
    overall_status = (
        "FAIL"
        if "FAIL" in capability_statuses
        else protocol_status
    )

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
            "claimed_capabilities": (
                agent.profile.claimed_capabilities
                if agent.profile else []
            ),
        },
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_type": "protocol_compliance",
        "status": overall_status,
        "protocols": protocols,
        "capabilities": capabilities,
        "limitations": [
            "Protocol compliance does not establish task accuracy.",
            "Capability scores only cover available matching test cases.",
            "A capability without a matching test case is not verified.",
            "Only protocols declared in the agent profile are evaluated.",
        ],
    }


def load_agent_test_cases(claimed_capabilities):
    if not TEST_CASES_DIR.is_dir():
        return [], {
            "status": "NOT_RUN",
            "reason": "The test_cases directory does not exist.",
        }

    cases = []
    errors = []

    normalized_claims = {
        capability.strip().lower()
        for capability in claimed_capabilities
        if isinstance(capability, str)
    }

    for path in sorted(TEST_CASES_DIR.rglob("*.yaml")):
        try:
            test_case = load_test_case(path)

            if test_case.capability.strip().lower() in normalized_claims:
                cases.append(test_case)

        except Exception as error:
            errors.append({
                "file": str(path),
                "error": str(error),
            })

    if not cases:
        return [], {
            "status": "NOT_RUN",
            "reason": "No test cases matched the agent's claimed capabilities.",
            "claimed_capabilities": sorted(normalized_claims),
            "loader_errors": errors,
        }

    return cases, {
        "status": "PASS",
        "loaded": len(cases),
        "loader_errors": errors,
    }


async def evaluate_a2a(endpoint, test_cases=None):
    evidence = {
        "protocol": "A2A",
        "operation": "agent_card_validation",
        "status": "NOT_RUN",
    }

    transport = None

    try:
        validated = validate_endpoint(endpoint)
        transport = create_pinned_async_transport(validated)

        async with httpx.AsyncClient(
            transport=transport,
            timeout=15.0,
            follow_redirects=False,
            trust_env=False,
        ) as client:
            result = await fetch_agent_card(
                client,
                validated.url,
                allow_private_network=False,
            )

            evidence.update(result)

            if result.get("status") != "PASS":
                return evidence

            if test_cases:
                evidence["capability_execution"] = (
                    await execute_a2a_test_cases(
                        client,
                        validated.url,
                        test_cases,
                    )
                )

    except Exception as error:
        evidence.update({
            "status": "FAIL",
            "error": str(error),
        })

    return evidence


def _extract_mcp_tool_definitions(tools_result):
    evidence = tools_result.get("evidence") or {}
    response = evidence.get("response") or {}

    result = response.get("result", response)

    if not isinstance(result, dict):
        return {}

    tools = result.get("tools", [])

    if not isinstance(tools, list):
        return {}

    return {
        item["name"]: item
        for item in tools
        if isinstance(item, dict)
        and isinstance(item.get("name"), str)
    }


def evaluate_mcp(endpoint, test_cases=None):
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

        if tools["status"] != "PASS":
            evidence["status"] = tools["status"]
            return evidence

        evidence["status"] = "PASS"

        if test_cases:
            definitions = _extract_mcp_tool_definitions(tools)

            evidence["capability_execution"] = (
                execute_mcp_test_cases(
                    client,
                    test_cases,
                    tool_definitions=definitions,
                )
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

    claimed_capabilities = (
        agent.profile.claimed_capabilities or []
    )

    test_cases, test_case_loading = load_agent_test_cases(
        claimed_capabilities
    )

    protocol_results = {}
    capability_results = {}

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

        capability_results["test_case_loading"] = {
            "status": "NOT_RUN",
            "reason": "Agent has no registered endpoint.",
        }

    else:
        if "A2A" in declared_protocols:
            import inspect

            a2a_parameters = inspect.signature(evaluate_a2a).parameters

            if len(a2a_parameters) >= 2:
                protocol_results["A2A"] = await evaluate_a2a(
                    agent.endpoint,
                    test_cases,
                )
            else:
                protocol_results["A2A"] = await evaluate_a2a(
                    agent.endpoint
                )

        if "MCP" in declared_protocols:
            import inspect

            mcp_parameters = inspect.signature(evaluate_mcp).parameters

            if len(mcp_parameters) >= 2:
                protocol_results["MCP"] = evaluate_mcp(
                    agent.endpoint,
                    test_cases,
                )
            else:
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

        capability_results["test_case_loading"] = test_case_loading

        if not test_cases:
            capability_results["execution"] = {
                "status": "NOT_RUN",
                "reason": test_case_loading["reason"],
            }

        else:
            for protocol in declared_protocols:
                if protocol not in {"A2A", "MCP"}:
                    continue

                protocol_result = protocol_results.get(protocol, {})

                execution = protocol_result.get(
                    "capability_execution"
                )

                capability_results[protocol] = execution or {
                    "status": "NOT_RUN",
                    "reason": (
                        "Capability execution was unavailable because "
                        "protocol validation did not complete."
                    ),
                }

    report = build_evaluation_report(
        agent,
        protocol_results,
        capability_results,
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
        "# Lyrax Evaluation Report",
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
        "## Capability Results",
        "",
    ])

    for capability, result in capability_results.items():
        lines.extend([
            f"### {capability}",
            "",
            f"Status: {result.get('status', 'NOT_RUN')}",
            "",
        ])

        if "accuracy" in result:
            lines.append(f"Accuracy: {result['accuracy']}%")
            lines.append("")

        if "test_cases" in result:
            lines.extend([
                "| Test case | Capability | Status |",
                "|---|---|---|",
            ])

            for case in result["test_cases"]:
                lines.append(
                    f"| {case.get('test_case_id')} "
                    f"| {case.get('capability')} "
                    f"| {case.get('status')} |"
                )

            lines.append("")

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
