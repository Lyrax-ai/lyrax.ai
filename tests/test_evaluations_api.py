import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from agents.models import Agent, AgentProfile
from database import Base, get_db
from main import app
import api.evaluations as evaluations_api
import runners.evaluation as evaluation


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def registered_agent(db_session):
    agent = Agent(
        name="API Evaluation Agent",
        provider="Test Provider",
        endpoint="https://example.com/agent",
        version="1.0",
        auth_type="none",
        profile=AgentProfile(
            claimed_capabilities=["research"],
            protocols=["A2A", "MCP"],
            input_types=["text"],
            output_types=["text"],
        ),
    )

    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    return agent


@pytest.fixture
def mock_protocol_checks(monkeypatch):
    async def mock_a2a(endpoint):
        return {
            "protocol": "A2A",
            "status": "PASS",
        }

    def mock_mcp(endpoint):
        return {
            "protocol": "MCP",
            "status": "PASS",
        }

    monkeypatch.setattr(evaluation, "evaluate_a2a", mock_a2a)
    monkeypatch.setattr(evaluation, "evaluate_mcp", mock_mcp)


def test_run_agent_evaluation(
    client,
    registered_agent,
    mock_protocol_checks,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(evaluation, "REPORTS_DIR", tmp_path)

    response = client.post(
        f"/evaluations/{registered_agent.id}"
    )

    assert response.status_code == 200

    report = response.json()

    assert report["status"] == "PASS"
    assert report["agent"]["name"] == "API Evaluation Agent"
    assert report["protocols"]["A2A"]["status"] == "PASS"
    assert report["protocols"]["MCP"]["status"] == "PASS"
    assert report["evaluation_id"]


def test_run_evaluation_for_unknown_agent(client):
    response = client.post("/evaluations/9999")

    assert response.status_code == 404


def test_get_evaluation_report(
    client,
    registered_agent,
    mock_protocol_checks,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(evaluation, "REPORTS_DIR", tmp_path)

    create_response = client.post(
        f"/evaluations/{registered_agent.id}"
    )

    evaluation_id = create_response.json()["evaluation_id"]

    response = client.get(
        f"/evaluations/{evaluation_id}"
    )

    assert response.status_code == 200
    assert response.json()["evaluation_id"] == evaluation_id


def test_get_unknown_evaluation_report(client):
    response = client.get(
        "/evaluations/agent-1-20260101T120000Z"
    )

    assert response.status_code == 404


def test_get_evaluation_rejects_invalid_id(client):
    response = client.get(
        "/evaluations/../../some-file"
    )

    assert response.status_code in (400, 404)


def test_list_agent_evaluations(
    client,
    registered_agent,
    mock_protocol_checks,
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(evaluation, "REPORTS_DIR", tmp_path)

    client.post(f"/evaluations/{registered_agent.id}")
    client.post(f"/evaluations/{registered_agent.id}")

    response = client.get(
        f"/evaluations/agent/{registered_agent.id}"
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_evaluations_for_unknown_agent(client):
    response = client.get("/evaluations/agent/9999")

    assert response.status_code == 404
