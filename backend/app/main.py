from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.shadowbroker import ShadowBrokerClient
from app.config import settings
from app.database import init_db
from app.routers import osint, scenario, simulation


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.sb_client = ShadowBrokerClient(settings.shadowbroker_url)
    yield
    await app.state.sb_client.close()


app = FastAPI(
    title="OSINT Simulator Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

# Simulation router first — more specific paths under /api/scenario/{id}/*
app.include_router(simulation.router)
app.include_router(scenario.router)
app.include_router(osint.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "osint-simulator-gateway",
        "port": settings.gateway_port,
    }
