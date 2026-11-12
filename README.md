# Lyrax - Phase 0 Backend

AI-agent discovery, verification, and orchestration platform.

## Phase 0 Scope
- Python 3.12 project configuration
- FastAPI application with health check endpoint
- PostgreSQL foundation with SQLAlchemy
- Docker containerization
- GitHub Actions CI
- Basic testing with pytest and httpx

## Development Setup

1. Install dependencies:
   ```bash
   pip install -e .
   ```

2. Set up environment:
   ```bash
   cp .env.example .env
   # Edit .env with your local database credentials
   ```

3. Start services:
   ```bash
   docker-compose up -d
   ```

4. Run tests:
   ```bash
   pytest
   ```

5. Run development server:
   ```bash
   uvicorn main:app --reload
   ```

## API Endpoints
- `GET /health` - Health check endpoint

## Project Structure
```
lyrax/
├── agents/          # Agent lifecycle management (placeholder)
├── schemas/         # Pydantic v2 schemas
├── evaluators/      # Verification logic (placeholder)
├── tests/           # Test suite
├── runners/         # Task orchestration (placeholder)
├── reports/         # Report generation (placeholder)
├── api/             # FastAPI route handlers
├── main.py          # FastAPI application entry point
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── README.md
```