from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/osint", tags=["osint"])

_NOT_IMPLEMENTED = {
    "detail": "Not implemented. See PRD 2 (shadowbroker-integration)."
}


@router.get("/live_data")
async def proxy_all_data():
    return JSONResponse(status_code=501, content=_NOT_IMPLEMENTED)


@router.get("/live_data/fast")
async def proxy_fast_data():
    return JSONResponse(status_code=501, content=_NOT_IMPLEMENTED)


@router.get("/live_data/slow")
async def proxy_slow_data():
    return JSONResponse(status_code=501, content=_NOT_IMPLEMENTED)
