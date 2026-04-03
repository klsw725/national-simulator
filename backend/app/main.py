from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.clients.mirofish import MiroFishClient
from app.clients.shadowbroker import ShadowBrokerClient
from app.config import settings
from app.database import close_db, init_db
from app.geopolitics.router import router as geopolitics_router
from app.logging_config import setup_logging
from app.middleware import RequestIdMiddleware
from app.ontology.router import router as ontology_router
from app.resolution.router import router as resolution_router
from app.routers import (
    actions,
    analytics,
    briefing,
    causal,
    copilot,
    dashboard,
    decision_point,
    osint,
    scenario,
    seed,
    simulation_events,
    simulation_live,
    simulation_run,
)


setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.sb_client = ShadowBrokerClient(settings.shadowbroker_url)
    app.state.mf_client = MiroFishClient(settings.mirofish_url)
    from app.tasks.aggregation_scheduler import start_background_tasks
    start_background_tasks()
    yield
    await app.state.mf_client.close()
    await app.state.sb_client.close()
    await close_db()


app = FastAPI(
    title="OSINT Simulator Gateway",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(RequestIdMiddleware)

app.include_router(actions.router)
app.include_router(analytics.router)
app.include_router(briefing.router)
app.include_router(causal.router)
app.include_router(copilot.router)
app.include_router(dashboard.router)
app.include_router(decision_point.router)
app.include_router(geopolitics_router)
app.include_router(ontology_router)
app.include_router(resolution_router)
app.include_router(seed.router)
app.include_router(simulation_run.router)
app.include_router(simulation_events.router)
app.include_router(simulation_live.router)
app.include_router(scenario.router)
app.include_router(osint.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "osint-simulator-gateway",
        "port": settings.gateway_port,
    }


@app.get("/api/health/detailed")
async def health_check_detailed(request: Request):
    import time
    results: dict = {"gateway": {"status": "healthy"}}

    mf_client = request.app.state.mf_client
    try:
        t0 = time.monotonic()
        ok = await mf_client.health_check()
        latency_ms = round((time.monotonic() - t0) * 1000)
        results["mirofish"] = {
            "status": "healthy" if ok else "unhealthy",
            "latency_ms": latency_ms,
            "circuit_breaker": mf_client._circuit_breaker.state,
            "failure_count": mf_client._circuit_breaker.failure_count,
        }
    except Exception:
        results["mirofish"] = {
            "status": "unhealthy",
            "circuit_breaker": mf_client._circuit_breaker.state,
            "failure_count": mf_client._circuit_breaker.failure_count,
        }

    sb_client = request.app.state.sb_client
    try:
        t0 = time.monotonic()
        await sb_client.health_check()
        latency_ms = round((time.monotonic() - t0) * 1000)
        results["shadowbroker"] = {
            "status": "healthy",
            "latency_ms": latency_ms,
            "circuit_breaker": sb_client._circuit_breaker.state,
            "failure_count": sb_client._circuit_breaker.failure_count,
        }
    except Exception:
        results["shadowbroker"] = {
            "status": "unhealthy",
            "circuit_breaker": sb_client._circuit_breaker.state,
            "failure_count": sb_client._circuit_breaker.failure_count,
        }

    from app.database import get_pool
    try:
        pool = get_pool()
        t0 = time.monotonic()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        latency_ms = round((time.monotonic() - t0) * 1000)
        results["database"] = {"status": "healthy", "latency_ms": latency_ms}
    except Exception:
        results["database"] = {"status": "unhealthy"}

    all_healthy = all(s.get("status") == "healthy" for s in results.values())
    return {"status": "healthy" if all_healthy else "degraded", "services": results}
