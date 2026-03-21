from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.clients.shadowbroker import BBox, ShadowBrokerClient
from app.services.observation_collector import ObservationCollector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/osint", tags=["osint"])


def _get_sb(request: Request) -> ShadowBrokerClient:
    return request.app.state.sb_client


def _parse_bbox(
    s: float | None, w: float | None, n: float | None, e: float | None
) -> BBox | None:
    if s is not None and w is not None and n is not None and e is not None:
        return BBox(s=s, w=w, n=n, e=e)
    return None


async def _proxy(request: Request, coro):
    """SB 클라이언트 호출을 프록시하고 에러를 적절한 HTTP 응답으로 변환."""
    sb = _get_sb(request)
    try:
        data = await coro
        return data
    except httpx.ConnectError:
        logger.warning("ShadowBroker unreachable: %s", sb.base_url)
        return JSONResponse(
            status_code=503,
            content={
                "detail": "ShadowBroker unavailable",
                "shadowbroker_url": sb.base_url,
            },
        )
    except httpx.TimeoutException:
        logger.warning("ShadowBroker timeout: %s", sb.base_url)
        return JSONResponse(
            status_code=504,
            content={"detail": "ShadowBroker timeout"},
        )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ShadowBroker error: %s %s", exc.response.status_code, exc.request.url
        )
        return JSONResponse(
            status_code=502,
            content={
                "detail": "ShadowBroker error",
                "status": exc.response.status_code,
            },
        )


@router.get("/live_data/fast")
async def proxy_fast_data(
    request: Request,
    s: float | None = Query(None, ge=-90, le=90),
    w: float | None = Query(None, ge=-180, le=180),
    n: float | None = Query(None, ge=-90, le=90),
    e: float | None = Query(None, ge=-180, le=180),
):
    """SB /api/live-data/fast 프록시 — bbox 쿼리 파라미터 포워딩."""
    bbox = _parse_bbox(s, w, n, e)
    sb = _get_sb(request)
    return await _proxy(request, sb.get_fast_data(bbox))


@router.get("/live_data/slow")
async def proxy_slow_data(
    request: Request,
    s: float | None = Query(None, ge=-90, le=90),
    w: float | None = Query(None, ge=-180, le=180),
    n: float | None = Query(None, ge=-90, le=90),
    e: float | None = Query(None, ge=-180, le=180),
):
    """SB /api/live-data/slow 프록시 — bbox 쿼리 파라미터 포워딩."""
    bbox = _parse_bbox(s, w, n, e)
    sb = _get_sb(request)
    return await _proxy(request, sb.get_slow_data(bbox))


@router.get("/live_data")
async def proxy_all_data(request: Request):
    """SB /api/live-data 프록시 — 전체 데이터."""
    sb = _get_sb(request)
    return await _proxy(request, sb.get_all_data())


@router.post("/collect")
async def collect_observations(
    request: Request,
    source: str = Query("ship", regex="^(ship|flight|satellite)$"),
    auto_resolve: bool = Query(True),
    s: float | None = Query(None, ge=-90, le=90),
    w: float | None = Query(None, ge=-180, le=180),
    n: float | None = Query(None, ge=-90, le=90),
    e: float | None = Query(None, ge=-180, le=180),
):
    """SB 데이터 수집 → observations INSERT + Entity Resolution 매칭."""
    sb = _get_sb(request)
    bbox = _parse_bbox(s, w, n, e)
    collector = ObservationCollector(sb)
    try:
        result = await collector.collect(
            source_type=source, bbox=bbox, auto_resolve=auto_resolve,
        )
    except httpx.ConnectError:
        return JSONResponse(status_code=503, content={"detail": "ShadowBroker unavailable"})
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"detail": "ShadowBroker timeout"})
    return result
