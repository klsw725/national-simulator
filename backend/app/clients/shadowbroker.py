from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.constants import (
    CLIENT_DEFAULT_TIMEOUT,
    CLIENT_RETRY_ATTEMPTS,
    CLIENT_RETRY_WAIT_MAX,
    CLIENT_RETRY_WAIT_MIN,
)
from app.services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class BBox:
    s: float
    w: float
    n: float
    e: float

    def to_params(self) -> dict[str, float]:
        return {"s": self.s, "w": self.w, "n": self.n, "e": self.e}


class ShadowBrokerClient:
    """ShadowBroker HTTP 클라이언트.

    - httpx AsyncClient 기반
    - ETag 캐싱 (If-None-Match / 304 처리)
    - bbox 쿼리 파라미터 포워딩
    """

    def __init__(self, base_url: str, timeout: float = CLIENT_DEFAULT_TIMEOUT):
        self.base_url = base_url
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self._circuit_breaker = CircuitBreaker(name="shadowbroker")
        # ETag 캐시: cache_key → (etag, response_body)
        self._etag_cache: dict[str, tuple[str, dict]] = {}

    @retry(
        stop=stop_after_attempt(CLIENT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=CLIENT_RETRY_WAIT_MIN, max=CLIENT_RETRY_WAIT_MAX),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """재시도 + 서킷 브레이커를 적용한 HTTP 요청."""
        async def _do():
            return await getattr(self._client, method)(url, **kwargs)
        return await self._circuit_breaker.call(_do)

    # ------------------------------------------------------------------
    # Core data endpoints
    # ------------------------------------------------------------------

    async def get_fast_data(self, bbox: BBox | None = None) -> dict:
        """GET /api/live-data/fast — 선박, 항공기, 위성 등 (빠른 갱신)"""
        return await self._get_with_etag("/api/live-data/fast", bbox)

    async def get_slow_data(self, bbox: BBox | None = None) -> dict:
        """GET /api/live-data/slow — GDELT, 뉴스, 지진 등 (느린 갱신)"""
        return await self._get_with_etag("/api/live-data/slow", bbox)

    async def get_all_data(self) -> dict:
        """GET /api/live-data — 전체 데이터 (fast + slow, bbox 미지원)"""
        return await self._get_with_etag("/api/live-data")

    # ------------------------------------------------------------------
    # Convenience extractors
    # ------------------------------------------------------------------

    async def get_ships(self, bbox: BBox | None = None) -> list[dict]:
        """fast 데이터에서 ships 필드만 추출."""
        data = await self.get_fast_data(bbox)
        return data.get("ships", [])

    async def get_gdelt(self, bbox: BBox | None = None) -> list:
        """slow 데이터에서 gdelt 필드만 추출."""
        data = await self.get_slow_data(bbox)
        return data.get("gdelt", [])

    # ------------------------------------------------------------------
    # Viewport & control
    # ------------------------------------------------------------------

    async def set_viewport(self, bbox: BBox) -> None:
        """POST /api/viewport — AIS 스트림 뷰포트 설정."""
        resp = await self._request("post", "/api/viewport", json=bbox.to_params())
        resp.raise_for_status()

    async def health_check(self) -> dict:
        """GET /api/health — SB 상태 확인."""
        resp = await self._client.get("/api/health")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internal: ETag caching
    # ------------------------------------------------------------------

    def _cache_key(self, path: str, bbox: BBox | None) -> str:
        if bbox:
            return f"{path}|{bbox.s},{bbox.w},{bbox.n},{bbox.e}"
        return f"{path}|full"

    async def _get_with_etag(
        self, path: str, bbox: BBox | None = None
    ) -> dict:
        params = bbox.to_params() if bbox else None
        cache_key = self._cache_key(path, bbox)

        headers: dict[str, str] = {}
        cached = self._etag_cache.get(cache_key)
        if cached:
            headers["If-None-Match"] = cached[0]

        resp = await self._request("get", path, params=params, headers=headers)

        if resp.status_code == 304 and cached:
            logger.debug("ETag cache hit: %s", cache_key)
            return cached[1]

        resp.raise_for_status()
        body = resp.json()

        etag = resp.headers.get("etag")
        if etag:
            self._etag_cache[cache_key] = (etag, body)

        return body
