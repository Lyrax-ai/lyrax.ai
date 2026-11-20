import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from agents.models import Agent, AgentProfile
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
def registered_agent(db_session):
    agent = Agent(
        name="Test Evaluation Agent",
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


def test_determine_status():
    assert evaluation.determine_status([
        {"status": "PASS"},
        {"status": "PASS"},
    ]) == "PASS"

    assert evaluation.determine_status([
        {"status": "PASS"},
        {"status": "FAIL"},
    ]) == "FAIL"

    assert evaluation.determine_status([
        {"status": "PASS"},
        {"status": "NOT_RUN"},
    ]) == "NOT_RUN"


def test_build_evaluation_report(registered_agent):
    report = evaluation.build_evaluation_report(
        registered_agent,
        {
            "A2A": {"status": "PASS"},
            "MCP": {"status": "PASS"},
        },
    )

    assert report["status"] == "PASS"
    assert report["evaluation_type"] == "protocol_compliance"
    assert report["agent"]["name"] == "Test Evaluation Agent"
    assert set(report["protocols"]) == {"A2A", "MCP"}


@pytest.mark.asyncio
async def test_evaluate_agent_generates_reports(
    db_session,
    registered_agent,
    monkeypatch,
    tmp_path,
):
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
    monkeypatch.setattr(evaluation, "REPORTS_DIR", tmp_path)

    report = await evaluation.evaluate_agent(
        db_session,
        registered_agent.id,
    )

    assert report["status"] == "PASS"
    assert report["protocols"]["A2A"]["status"] == "PASS"
    assert report["protocols"]["MCP"]["status"] == "PASS"

    json_path = tmp_path / f"{report['evaluation_id']}.json"
    markdown_path = tmp_path / f"{report['evaluation_id']}.md"

    assert json_path.exists()
    assert markdown_path.exists()

    assert "Test Evaluation Agent" in markdown_path.read_text(
        encoding="utf-8"
    )


@pytest.mark.asyncio
async def test_evaluate_agent_marks_missing_endpoint_not_run(
    db_session,
    registered_agent,
    monkeypatch,
    tmp_path,
):
    registered_agent.endpoint = None
    db_session.commit()

    monkeypatch.setattr(evaluation, "REPORTS_DIR", tmp_path)

    report = await evaluation.evaluate_agent(
        db_session,
        registered_agent.id,
    )

    assert report["status"] == "NOT_RUN"
    assert report["protocols"]["A2A"]["status"] == "NOT_RUN"
    assert report["protocols"]["MCP"]["status"] == "NOT_RUN"


@pytest.mark.asyncio
async def test_evaluate_agent_rejects_unknown_id(db_session):
    with pytest.raises(ValueError, match="was not found"):
        await evaluation.evaluate_agent(db_session, 9999)
