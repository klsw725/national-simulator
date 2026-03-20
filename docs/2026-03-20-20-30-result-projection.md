# PRD 5: Result Projection 구현

> 날짜: 2026-03-20
> 프롬프트: `prd-next` → PRD 5 (result-projection) 선택 → 구현

## 변경 사항

### 신규 파일

| 파일 | 설명 |
|------|------|
| `backend/app/data/actor_locations.json` | 35개 항목 — 국가 20개(코드+이름 매핑) + 국제기구 5개 수도/본부 좌표 |
| `backend/app/services/result_projector.py` | ResultProjector — 시뮬레이션 액션 로그를 GeoJSON FeatureCollection으로 변환. Point(행위자) + LineString(관계) |

### 수정 파일

| 파일 | 변경 내용 |
|------|-----------|
| `backend/app/routers/simulation.py` | PRD 5 스텁(501) 2개를 실제 구현으로 교체: `GET /geojson`(ResultProjector + DB 캐시), `GET /report`(보고서 반환) |

## GeoJSON 출력 구조

- **Point 피처**: 행위자별 위치, tension_level, stance, key_statement, post_count, color
- **LineString 피처**: 행위자 간 관계선, relationship_type(alliance/hostile/support), strength

## 분석 로직

| 분석 항목 | 구현 |
|-----------|------|
| 긴장도 (0.0~1.0) | QUOTE_POST/REPLY 비율(60%) + 활동량 보정(40%) |
| 입장 분류 | supportive/opposing/neutral/cautious_ally — 액션 유형 비율 기반 |
| 핵심 발언 | 가장 긴 포스트 (상세 발언 휴리스틱) |
| 관계 라인 | 양방향 상호작용 합산 → REPOST→alliance, QUOTE(부정)→hostile |

## 검증 결과

- ✅ 35개 국가/기구 좌표 데이터 로드
- ✅ 테스트 액션 데이터 → 4 Point + 2 LineString GeoJSON 생성
- ✅ US↔Japan alliance, China→US hostile 관계 정확 추출
- ✅ South Korea neutral 분류 (DO_NOTHING 비율 높음)
- ✅ GET /geojson, GET /report 라우트 등록 확인
