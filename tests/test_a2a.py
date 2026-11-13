import copy
import json

import pytest

from evaluators.a2a import validate_agent_card


@pytest.fixture
def valid_card():
    with open(
        "test_cases/a2a/valid-agent-card.json",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def test_valid_agent_card(valid_card):
    result = validate_agent_card(valid_card)

    assert result["status"] == "PASS"
    assert result["agent_name"] == "Example Research Agent"


def test_all_protocol_checks_pass(valid_card):
    result = validate_agent_card(valid_card)

    statuses = {
        check["name"]: check["status"]
        for check in result["checks"]
    }

    assert statuses["agent_card_schema"] == "PASS"
    assert statuses["supported_interfaces"] == "PASS"
    assert statuses["protocol_binding_declarations"] == "PASS"
    assert statuses["protocol_version_declarations"] == "PASS"


def test_missing_required_field(valid_card):
    card = copy.deepcopy(valid_card)
    del card["name"]

    result = validate_agent_card(card)

    assert result["status"] == "FAIL"
    assert result["checks"][0]["status"] == "FAIL"


def test_invalid_interface_url(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"][0]["url"] = "not-a-url"

    result = validate_agent_card(card)

    assert result["status"] == "FAIL"


def test_unsupported_protocol_version(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"][0]["protocolVersion"] = "9.0"

    result = validate_agent_card(card)

    assert result["status"] == "UNSUPPORTED"

    version_check = next(
        check for check in result["checks"]
        if check["name"] == "protocol_version_declarations"
    )

    assert version_check["status"] == "PASS"
    assert result["checks"][-1]["status"] == "UNSUPPORTED"


def test_unsupported_protocol_binding(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"][0]["protocolBinding"] = "UNKNOWN"

    result = validate_agent_card(card)

    assert result["status"] == "FAIL"


def test_non_dictionary_rejected():
    with pytest.raises(TypeError):
        validate_agent_card("invalid")



def test_valid_grpc_card_is_unsupported_by_lyrax(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"] = [
        {
            "url": "grpc.example.com:443",
            "protocolBinding": "GRPC",
            "protocolVersion": "1.0",
        }
    ]

    result = validate_agent_card(card)

    assert result["status"] == "UNSUPPORTED"
    assert result["checks"][-1]["status"] == "UNSUPPORTED"


def test_lyrax_selects_jsonrpc_from_multiple_interfaces(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"] = [
        {
            "url": "grpc.example.com:443",
            "protocolBinding": "GRPC",
            "protocolVersion": "1.0",
        },
        {
            "url": "https://example.com/a2a",
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        },
    ]

    result = validate_agent_card(card)

    assert result["status"] == "PASS"
    assert len(result["usable_interfaces"]) == 1
    assert result["usable_interfaces"][0]["protocol_binding"] == "JSONRPC"


def test_invalid_grpc_address_fails(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"] = [
        {
            "url": "not-a-valid-grpc-address",
            "protocolBinding": "GRPC",
            "protocolVersion": "1.0",
        }
    ]

    result = validate_agent_card(card)

    assert result["status"] == "FAIL"


def test_custom_binding_requires_uri(valid_card):
    card = copy.deepcopy(valid_card)
    card["supportedInterfaces"][0]["protocolBinding"] = "UNKNOWN"

    result = validate_agent_card(card)

    assert result["status"] == "FAIL"
