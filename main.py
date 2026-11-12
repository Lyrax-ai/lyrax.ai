import os
from fastapi import FastAPI

app = FastAPI(
    title="Lyrax API",
    description="AI-agent discovery, verification, and orchestration platform",
    version="0.1.0"
)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "lyrax-backend"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)