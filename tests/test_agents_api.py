import pytest
import httpx

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from database import Base, get_db


@pytest.fixture
def test_app():
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

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    yield app

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.asyncio
async def test_agent_registry_crud(test_app):
    transport = httpx.ASGITransport(app=test_app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        # Register an agent
        payload = {
            "name": "Test Research Agent",
            "provider": "Test Provider",
            "marketplace": "Lyrax",
            "endpoint": "https://example.com/test",
            "version": "1.0",
            "auth_type": "none",
            "profile": {
                "claimed_capabilities": ["web_research", "summarization"],
                "protocols": ["A2A"],
                "input_types": ["text"],
                "output_types": ["text"],
            },
        }

        response = await client.post("/agents/", json=payload)

        assert response.status_code == 201

        agent = response.json()
        agent_id = agent["id"]

        assert agent["name"] == "Test Research Agent"
        assert agent["profile"]["claimed_capabilities"] == [
            "web_research",
            "summarization",
        ]

        # Retrieve the agent
        response = await client.get(f"/agents/{agent_id}")

        assert response.status_code == 200
        assert response.json()["provider"] == "Test Provider"

        # Update the agent
        response = await client.put(
            f"/agents/{agent_id}",
            json={
                "name": "Updated Research Agent",
                "profile": {
                    "claimed_capabilities": ["summarization"],
                    "protocols": ["A2A", "MCP"],
                    "input_types": ["text"],
                    "output_types": ["text", "json"],
                },
            },
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Research Agent"
        assert response.json()["profile"]["protocols"] == ["A2A", "MCP"]

        # List agents
        response = await client.get("/agents/")

        assert response.status_code == 200
        assert len(response.json()) == 1

        # Delete the agent
        response = await client.delete(f"/agents/{agent_id}")

        assert response.status_code == 204

        # Confirm deletion
        response = await client.get(f"/agents/{agent_id}")

        assert response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_agent_registration(test_app):
    transport = httpx.ASGITransport(app=test_app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:

        response = await client.post(
            "/agents/",
            json={
                "name": "A",
                "provider": "Test Provider",
            },
        )

        assert response.status_code == 422
