from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.graph.builder import get_graph
from app.services.command_listener import SimulationCommandListener
from app.services.event_emitter import init_emitter
from app.services.gdelt_pipeline import gdelt_poll_loop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    emitter = await init_emitter()
    graph = await get_graph()

    listener = SimulationCommandListener()
    listener.set_graph(graph)
    listen_task = asyncio.create_task(listener.start())
    gdelt_task = asyncio.create_task(gdelt_poll_loop())

    app.state.graph = graph
    app.state.emitter = emitter
    app.state.listener = listener

    logger.info("Simulation Service started on port %d", settings.service_port)
    yield
    listen_task.cancel()
    gdelt_task.cancel()
    for t in (listen_task, gdelt_task):
        try:
            await t
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
