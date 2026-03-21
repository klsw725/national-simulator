# V4-1 M4: DecisionPointView 프론트엔드

> 날짜: 2026-03-21
> PRD: v4-ai-guided-decisions (V4-1)
> 마일스톤: M4

## 프롬프트

```
prd-next → V4-1 M4 추천 → visual-engineering 위임 → 파라미터 필드명 수정 → SimulationPanel 통합
```

## 변경 사항

### 신규 파일

- `frontend/src/components/simulation/DecisionPointView.tsx` (487줄)
  - Props: scenarioId, type (seed_selection | parameter_recommendation), onResolved
  - 옵션 카드: label, confidence 바 (cyan/amber/red), reasoning, AI 추천 배지
  - seed_selection: seed_text 미리보기 (150자 truncate)
  - parameter_recommendation: 파라미터 그리드 (platform, max_rounds, simulation_hours, geopolitics_enabled, web_search_enabled)
  - 선택 상태: 라디오 스타일 원형 + 체크 아이콘 + cyan 테두리
  - 커스텀 입력: 접이식 섹션 (textarea 또는 number inputs)
  - resolve 버튼: disabled 상태 + 로딩 스피너
  - 로딩/빈 상태 처리

### 수정 파일

- `frontend/src/components/simulation/SimulationPanel.tsx`
  - "결정" 탭 추가 (activeScenario 있을 때만 표시)
  - seed_selection + parameter_recommendation DecisionPointView 2개 렌더링
  - DecisionPointView import 추가
  - Tab 타입에 "decisions" 추가

### 설계 결정

- visual-engineering 카테고리로 위임 (frontend-ui-ux 스킬 로드)
- 파라미터 필드명: param_recommender.py의 실제 필드명 (max_rounds, simulation_hours 등)에 맞춰 수정
- "결정" 탭은 activeScenario가 있을 때만 표시 — 시나리오 선택 전에는 무의미
