# ShadowBroker Integration 구현 (PRD 2 — M1~M4)

> 날짜: 2026-03-20
> 프롬프트: "PRD Next - 다음 작업 진행" → PRD 2 (shadowbroker-integration) 선택 → 구현

## 변경 사항

### 생성된 파일

| 파일 | 용도 |
|---|---|
| `backend/app/clients/shadowbroker.py` | ShadowBroker httpx 비동기 클라이언트 (ETag 캐싱, bbox 파라미터, 에러 핸들링) |

### 수정된 파일

| 파일 | 변경 내용 |
|---|---|
| `backend/app/main.py` | lifespan에 ShadowBrokerClient 생성/해제 등록 (`app.state.sb_client`) |
| `backend/app/routers/osint.py` | 501 스텁 → 실제 SB 프록시 (fast/slow/all + bbox 쿼리 포워딩 + 에러 핸들링) |

### ShadowBrokerClient 인터페이스

```python
class ShadowBrokerClient:
    async def get_fast_data(bbox: BBox | None) -> dict   # /api/live-data/fast
    async def get_slow_data(bbox: BBox | None) -> dict   # /api/live-data/slow
    async def get_all_data() -> dict                      # /api/live-data
    async def get_ships(bbox: BBox | None) -> list[dict]  # fast에서 ships 추출
    async def get_gdelt(bbox: BBox | None) -> list        # slow에서 gdelt 추출
    async def set_viewport(bbox: BBox) -> None            # POST /api/viewport
    async def health_check() -> dict                      # /api/health
    async def close() -> None                             # 클라이언트 정리
```

### OSINT 프록시 엔드포인트 (501 → 구현)

```
GET /api/osint/live_data/fast  → SB /api/live-data/fast (bbox 포워딩)
GET /api/osint/live_data/slow  → SB /api/live-data/slow (bbox 포워딩)
GET /api/osint/live_data       → SB /api/live-data
```

### 에러 핸들링

| SB 상태 | Gateway 응답 |
|---------|-------------|
| 정상 | 200 + 데이터 |
| 연결 불가 | 503 `{"detail": "ShadowBroker unavailable"}` |
| 타임아웃 | 504 `{"detail": "ShadowBroker timeout"}` |
| SB 에러 | 502 `{"detail": "ShadowBroker error", "status": N}` |

### ETag 캐싱

- 엔드포인트+bbox 조합별 `(etag, response_body)` 인메모리 캐시
- `If-None-Match` 헤더 전송 → SB 304 응답 시 캐시 반환
- 캐시 키 형식: `"/api/live-data/fast|5.0,108.0,23.0,121.0"` 또는 `"/api/live-data|full"`

## 검증 결과

- ✅ 앱 로드: `ShadowBrokerClient` 정상 생성, 3개 OSINT 라우트 등록
- ✅ SB 미기동 시: 3개 엔드포인트 모두 503 + 명확한 에러 메시지
- ✅ bbox 파라미터: `/api/osint/live_data/fast?s=5&w=108&n=23&e=121` 정상 수용
- ⏳ ETag 캐싱: SB 실행 상태에서 추가 검증 필요 (M5)
- ⏳ 연동 검증 (M5): SB 실행 → 실제 데이터 프록시 확인

## PRD 2 마일스톤 완료 상태

- [x] M1: ShadowBroker HTTP 클라이언트 구현
- [x] M2: OSINT 프록시 엔드포인트 구현
- [x] M3: ETag 캐싱 지원 (구현 완료, SB 연동 검증은 M5)
- [x] M4: 에러 핸들링 + 연결 상태 관리
- [ ] M5: 연동 검증 (SB 실행 상태에서 E2E 확인 필요)

## 다음 단계

- M5 연동 검증은 ShadowBroker를 실행한 상태에서 수행
- PRD 2 완료 후 PRD 3 (seed-generation)과 PRD 6a (frontend-foundation) 시작 가능
