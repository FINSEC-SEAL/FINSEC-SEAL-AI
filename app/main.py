from fastapi import FastAPI

from app.api.agent import router as agent_router

app = FastAPI(
    title="FINSEC SEAL AI",
    version="0.1.0",
    description="Stateless AI execution boundary for FINSEC SEAL.",
)

app.include_router(agent_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
