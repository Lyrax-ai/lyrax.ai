from fastapi import FastAPI

from api.agents import router as agents_router
from api.evaluations import router as evaluations_router


app = FastAPI(
    title="Lyrax API",
    description="AI-agent discovery, verification, and orchestration platform",
    version="0.2.0",
)

app.include_router(agents_router)
app.include_router(evaluations_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "lyrax-backend",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
