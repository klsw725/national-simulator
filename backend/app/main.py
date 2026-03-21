from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.mirofish import MiroFishClient
from app.clients.shadowbroker import ShadowBrokerClient
from app.config import settings
from app.database import close_db, init_db
from app.geopolitics.router import router as geopolitics_router
from app.ontology.router import router as ontology_router
from app.resolution.router import router as resolution_router
from app.routers import actions, osint, scenario, simulation


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.sb_client = ShadowBrokerClient(settings.shadowbroker_url)
    app.state.mf_client = MiroFishClient(settings.mirofish_url)
    yield
    await app.state.mf_client.close()
    await app.state.sb_client.close()
    await close_db()


app = FastAPI(
    title="OSINT Simulator Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(actions.router)
app.include_router(geopolitics_router)
app.include_router(ontology_router)
app.include_router(resolution_router)
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
