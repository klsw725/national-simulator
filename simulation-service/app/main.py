from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.graph.builder import get_graph
from app.services.command_listener import SimulationCommandListener
from app.services.event_emitter import init_emitter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    emitter = await init_emitter()
    graph = await get_graph()

    listener = SimulationCommandListener()
    listener.set_graph(graph)
    listen_task = asyncio.create_task(listener.start())

    app.state.graph = graph
    app.state.emitter = emitter
    app.state.listener = listener

    logger.info("Simulation Service started on port %d", settings.service_port)
    yield
    listen_task.cancel()
    try:
        await listen_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Simulation Service",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "simulation-service",
        "port": settings.service_port,
    }
