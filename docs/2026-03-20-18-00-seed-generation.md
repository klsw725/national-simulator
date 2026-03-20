# PRD 3: Seed Generation 구현

> 날짜: 2026-03-20
> 프롬프트: `prd-next` → PRD 3 (seed-generation) 선택 → 구현

## 변경 사항

### 신규 파일

| 파일 | 설명 |
|------|------|
| `backend/app/data/military_vessels.json` | 9개국(US,CN,RU,JP,KR,UK,FR,IN,AU) 68척 군함 정적 데이터베이스. MMSI, hull_number, class, type, country, navy, status 포함 |
| `backend/app/services/vessel_mapper.py` | VesselMapper — SB ship type 기반 군함 필터 + DB MMSI 매칭 enrichment + 국가별 전력 그룹핑 + 배치 현황 텍스트 포맷 |
| `backend/app/services/gdelt_extractor.py` | GDELT GeoJSON 파싱, bbox 필터링, 이벤트 밀도 기반 긴장도 추정(0-10), 헤드라인 요약 |
| `backend/app/services/seed_generator.py` | SeedGenerator — SB client→vessel_mapper→gdelt_extractor→LLM 프롬프트→마크다운 시드 문서 생성. OpenAI Compatible API 사용 |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/routers/simulation.py` | POST/GET `/api/scenario/{id}/seed` 스텁(501)을 실제 구현으로 교체. 시나리오 조회→시드 생성→seeds 테이블 저장→seed_status 업데이트 |

## 설계 결정

### GDELT Goldstein Scale 부재
ShadowBroker의 GDELT 데이터는 위치별 집계 데이터로, 개별 이벤트의 Goldstein Scale이 포함되지 않는다. 이벤트 밀도(count) 기반의 간략한 긴장도 추정(0-10)으로 대체.

### 군함 식별 전략
ShadowBroker가 이미 `type: "military_vessel"/"carrier"` 분류와 `country` 필드를 제공하므로, 이를 1차 필터로 사용하고 `military_vessels.json`은 enrichment(hull_number, class 등) 목적으로만 활용.

### LLM 호출
OpenAI Compatible API (`openai` 라이브러리) 사용. `config.py`의 `llm_api_key`, `llm_base_url`, `llm_model_name` 설정 활용. 특정 프로바이더 고유 기능 미사용.

## 검증 결과

- ✅ 전체 import 검증 통과
- ✅ VesselMapper: 테스트 데이터에서 군함 2/3척 정확 식별, 국가 매핑 정확
- ✅ GDELT Extractor: bbox 필터링, 긴장도 계산, 헤드라인 추출 동작
- ✅ military_vessels.json: 68척, 9개국, 필수 필드 전체 존재
- ✅ FastAPI 앱 기동 + 라우트 등록 확인 (POST/GET seed 포함)
