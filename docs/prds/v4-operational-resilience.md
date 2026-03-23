# PRD: 운영 안정성

> Status: Complete
> Created: 2026-03-21
> Dependencies: simulation-orchestration, gateway-api-foundation
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-6
> 버전: v4.0

---

## 1. 문제 정의

외부 서비스(MiroFish, ShadowBroker) 장애 시 전체 파이프라인이 실패한다. 재시도/서킷 브레이커가 없어 일시적 네트워크 오류에도 2시간짜리 시뮬레이션이 실패한다. 파이프라인 실패 시 마지막 체크포인트에서 자동 복구할 수 없다.

현재 상태:
- **MiroFishClient**: 120초 타임아웃만. 재시도 없음, 서킷 브레이커 없음.
- **ShadowBrokerClient**: 10초 타임아웃. 재시도 없음.
- **SimulationOrchestrator**: 단계 실패 시 전체 "failed" 표시. 자동 복구 없음.
- **헬스체크**: `GET /api/health` → 200만 반환. 외부 서비스 상태 미포함.

## 2. 솔루션 개요

- **재시도 + 지수 백오프** — HTTP 클라이언트에 자동 재시도 (최대 3회, 지수 백오프)
- **서킷 브레이커** — 연속 실패 5회 시 서킷 오픈. 30초 후 half-open 시도.
- **자동 체크포인트 복구** — 파이프라인 실패 시 마지막 성공 단계에서 자동 재시작
- **상세 헬스체크** — 모든 외부 서비스 상태 + 응답 시간 실시간 표시

## 3. 기술 상세

### 3.1 재시도 + 지수 백오프

```python
# tenacity 라이브러리 사용
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
)
async def _request(self, method, url, **kwargs):
    """재시도 가능한 HTTP 요청."""
```

### 3.2 서킷 브레이커

```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_count = 0
        self.state = "closed"  # closed | open | half-open
        self.last_failure_time = None
    
    async def call(self, func, *args, **kwargs):
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitBreakerOpen(f"Service unavailable (circuit open)")
        # ...
```

### 3.3 자동 체크포인트 복구

```python
# SimulationOrchestrator 확장
async def auto_recover(self, scenario_id: str, result_id: str):
    """실패한 파이프라인을 마지막 성공 체크포인트에서 자동 재시작."""
    last_checkpoint = await self._get_last_successful_step(result_id)
    if last_checkpoint:
        logger.info("[%s] Auto-recovering from %s", scenario_id, last_checkpoint)
        await self.run_from_checkpoint(scenario_id, result_id, ...)
```

### 3.4 상세 헬스체크

```
GET /api/health/detailed
→ {
    "status": "degraded",  // healthy | degraded | unhealthy
    "services": {
        "mirofish": { "status": "healthy", "response_ms": 45, "circuit": "closed" },
        "shadowbroker": { "status": "unhealthy", "error": "Connection refused", "circuit": "open" },
        "postgres": { "status": "healthy", "response_ms": 2 }
    },
    "pipeline": {
        "running": 2,
        "failed_recoverable": 1,
        "auto_recovery_enabled": true
    }
}
```

### 3.5 수정 대상 파일

```
# 신규
backend/app/services/circuit_breaker.py         # 서킷 브레이커
frontend/src/components/simulation/HealthDashboard.tsx  # 서비스 상태 UI

# 수정
backend/pyproject.toml                           # tenacity 의존성
backend/app/clients/mirofish.py                  # 재시도 + 서킷 브레이커
backend/app/clients/shadowbroker.py              # 재시도 + 서킷 브레이커
backend/app/services/simulation_orchestrator.py  # 자동 복구
backend/app/routers/health.py                    # 상세 헬스체크 (신규 또는 기존 확장)
frontend/src/components/simulation/SimulationPanel.tsx  # 헬스체크 표시
```

## 4. 마일스톤

- [x] **M1: HTTP 클라이언트 재시도 + 서킷 브레이커** — MiroFishClient, ShadowBrokerClient에 tenacity 기반 재시도 (3회, 지수 백오프). CircuitBreaker 클래스 구현 (5회 실패 → 오픈, 30초 후 half-open).
  - 검증: MiroFish 일시 중단 → 재시도 3회 → 복구 시 정상 진행. 5회 연속 실패 → 서킷 오픈 → 503 즉시 반환.

- [x] **M2: 파이프라인 자동 복구** — 파이프라인 실패 시 마지막 성공 체크포인트 확인. 재시도 가능한 에러(네트워크, 타임아웃)이면 자동 재시작. 영구 에러(데이터 무결성)이면 실패 유지.
  - 검증: 시뮬레이션 중 MiroFish 재시작 → 파이프라인 자동 복구 → 완료

- [x] **M3: 서비스 헬스체크 대시보드** — GET /api/health/detailed 엔드포인트. 모든 외부 서비스 상태 + 응답 시간 + 서킷 상태. 프론트엔드 HealthDashboard (서비스별 상태 인디케이터, 자동 새로고침).
  - 검증: ShadowBroker 중단 → 대시보드에 "unhealthy" 표시 → 복구 후 "healthy" 전환

## 5. 성공 기준

- MiroFish/ShadowBroker 일시 장애 시 자동 재시도로 파이프라인 중단 없이 진행
- 5회 연속 실패 시 서킷 브레이커가 즉시 503 반환 (불필요한 대기 방지)
- 파이프라인 실패 시 마지막 체크포인트에서 자동 복구
- 서비스 상태를 실시간으로 모니터링할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 재시도로 서버 부하 증가 | 지수 백오프 (2초→4초→8초). 최대 3회 |
| 서킷 브레이커 오탐 | 보수적 임계치 (5회). 수동 리셋 API |
| 자동 복구 무한 루프 | 최대 2회 자동 복구. 초과 시 failed 유지 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-6 운영 안정성 PRD 초안 작성 |
| 2026-03-21 | M1 Complete | CircuitBreaker 구현 + MiroFishClient/ShadowBrokerClient에 tenacity 재시도(3회, 지수 백오프 2s→4s→8s) + 서킷 브레이커(5회→open, 30s→half-open) 적용. health_check는 제외. |
| 2026-03-22 | M2 Complete | run_from_failure() — 기존 ID로 복구 지점 추론 + POST /retry 엔드포인트 + 프론트엔드 재시도 버튼 |
| 2026-03-22 | M3 Complete | GET /api/health/detailed — MiroFish/SB/DB 상태+응답시간+서킷 상태. HealthDashboard 컴포넌트 (15초 자동 갱신) + SimulationPanel "헬스" 탭 |
