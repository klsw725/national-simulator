# PRD: 결과 내보내기 + 브리핑 생성

> Status: Complete
> Created: 2026-03-21
> Dependencies: simulation-visualization, v3-geopolitics-integration
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-3
> 버전: v4.0

---

## 1. 문제 정의

시뮬레이션 결과를 내보내거나 공유할 수 없다. 보고서, 타임라인, 지정학 분석, 그래프 데이터 모두 UI에서만 확인 가능하며, 외부 도구(파워포인트, 이메일, 팀 브리핑)에서 활용할 수 없다.

## 2. 솔루션 개요

- **데이터 내보내기** — JSON, CSV 형식으로 시나리오/결과/관측 데이터 다운로드
- **AI 브리핑 생성** — LLM이 시뮬레이션 결과를 분석하여 전문적인 브리핑 문서 초안 작성
- **브리핑 편집기** — AI 초안을 분석관이 수정/확정
- **시각화 내보내기** — 그래프/지도 스크린샷을 PNG로 내보내기

## 3. 기술 상세

### 3.1 데이터 내보내기 API

```
GET /api/scenario/{id}/export?format=json  → 시나리오 전체 데이터 (JSON)
GET /api/scenario/{id}/export?format=csv   → 시뮬레이션 액션 (CSV)
GET /api/scenario/{id}/export/observations → 관측 데이터 (CSV)
GET /api/scenario/{id}/export/geopolitics  → 지정학 이벤트 (CSV)
GET /api/scenario/{id}/export/report       → MiroFish 보고서 (Markdown)
```

### 3.2 AI 브리핑 생성기

```python
class BriefingGenerator:
    async def generate(self, scenario_id: str) -> dict:
        """
        시뮬레이션 결과를 LLM으로 분석하여 브리핑 문서 초안 생성.
        입력: 시드, 시뮬레이션 액션, 지정학 이벤트, MiroFish 보고서
        출력: 구조화된 브리핑 문서 (마크다운)
        """
```

브리핑 문서 구조:
```markdown
# 상황 브리핑: [시나리오명]
## 1. 상황 요약
## 2. 핵심 발견 (3-5개)
## 3. 행위자 분석
## 4. 시뮬레이션 결과 요약
## 5. 지정학적 함의
## 6. 권장 조치
## 부록: 데이터 소스, 방법론, 신뢰도
```

### 3.3 수정 대상 파일

```
# 신규
backend/app/services/briefing_generator.py      # AI 브리핑 생성기
backend/app/services/data_exporter.py            # 데이터 내보내기 서비스
frontend/src/components/simulation/ExportPanel.tsx  # 내보내기 UI
frontend/src/components/simulation/BriefingEditor.tsx  # 브리핑 편집기

# 수정
backend/app/routers/simulation.py                # export 엔드포인트
frontend/src/components/simulation/SimulationPanel.tsx  # 내보내기 버튼
frontend/src/lib/gatewayApi.ts                   # 내보내기 API 호출
```

## 4. 마일스톤

- [x] **M1: 데이터 내보내기 API** — JSON/CSV 내보내기 엔드포인트 구현. 시나리오 전체 데이터, 시뮬레이션 액션, 관측 데이터, 지정학 이벤트 각각 내보내기 가능. Content-Disposition 헤더로 파일 다운로드.
  - 검증: GET /export?format=json → 전체 시나리오 데이터 다운로드

- [x] **M2: AI 브리핑 생성기** — BriefingGenerator 구현. 시뮬레이션 결과 + 지정학 분석 + 보고서를 LLM에 입력하여 브리핑 초안 생성. 마크다운 형식. briefings 테이블에 저장.
  - 검증: 완료된 시뮬레이션 → POST /briefing/generate → 마크다운 브리핑 생성

- [x] **M3: 프론트엔드 내보내기 UI** — SimulationPanel 각 탭에 다운로드 버튼 추가. 포맷 선택 (JSON/CSV). 브리핑 생성 버튼. 다운로드 진행률 표시.
  - 검증: 보고서 탭에서 "내보내기" 클릭 → JSON/CSV 파일 다운로드

- [x] **M4: 브리핑 편집기** — AI 생성 브리핑 초안을 마크다운 편집기에서 수정. 섹션별 편집. 수정 후 저장. 최종 버전 내보내기.
  - 검증: AI 브리핑 초안 생성 → 편집기에서 수정 → 저장 → 마크다운 다운로드

## 5. 성공 기준

- 시뮬레이션 결과를 JSON, CSV 형식으로 내보낼 수 있다
- AI가 전문적인 브리핑 문서 초안을 자동 생성한다
- 분석관이 브리핑 초안을 편집하고 최종 버전을 내보낼 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 브리핑 생성 LLM 비용 | 시나리오당 1회 생성. 재생성 시 확인 다이얼로그 |
| 대용량 데이터 내보내기 성능 | 스트리밍 응답. 10만 행 이상 시 백그라운드 처리 |
| AI 브리핑의 정확성 | AI 초안 + 분석관 검토/수정 단계 필수. 소스 명시 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-3 결과 내보내기 + 브리핑 PRD 초안 작성 |
| 2026-03-22 | Complete | M1-M4 전체 구현. DataExporter + BriefingGenerator + ExportPanel + BriefingEditor |
