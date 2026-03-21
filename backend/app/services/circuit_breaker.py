"""서킷 브레이커.

5회 연속 실패 시 서킷을 열어 즉시 실패를 반환한다.
30초 후 half-open으로 전환하여 복구를 시도한다.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class CircuitBreakerOpen(Exception):
    """서킷 브레이커가 열린 상태에서 호출 시 발생."""


class CircuitBreaker:
    """비동기 서킷 브레이커.

    Args:
        failure_threshold: 서킷을 여는 연속 실패 횟수 (기본 5).
        recovery_timeout: 오픈 후 half-open 전환까지 대기 초 (기본 30).
        name: 로깅용 식별자.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        name: str = "",
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.state = "closed"  # closed | open | half-open
        self.last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    async def call(self, func, *args, **kwargs):
        """서킷 브레이커를 통해 비동기 함수를 실행한다.

        서킷이 열려 있으면 CircuitBreakerOpen을 발생시킨다.
        """
        # 상태 확인 (짧은 락)
        async with self._lock:
            if self.state == "open":
                if (
                    self.last_failure_time is not None
                    and (time.monotonic() - self.last_failure_time)
                    > self.recovery_timeout
                ):
                    self.state = "half-open"
                    logger.info("CircuitBreaker[%s] → half-open", self.name)
                else:
                    raise CircuitBreakerOpen(
                        f"Circuit breaker [{self.name}] is open"
                    )

        # 함수 실행 (락 밖 — 동시 요청 허용)
        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.monotonic()
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    logger.warning(
                        "CircuitBreaker[%s] → open (failures=%d)",
                        self.name,
                        self.failure_count,
                    )
            raise

        # 성공 — 카운터 리셋
        async with self._lock:
            if self.state == "half-open":
                self.state = "closed"
                logger.info("CircuitBreaker[%s] → closed (recovered)", self.name)
            self.failure_count = 0

        return result

    def reset(self) -> None:
        """서킷 브레이커 수동 리셋."""
        self.state = "closed"
        self.failure_count = 0
        self.last_failure_time = None
        logger.info("CircuitBreaker[%s] manually reset", self.name)
