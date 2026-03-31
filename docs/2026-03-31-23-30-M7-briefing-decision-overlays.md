# M7: BriefingOverlay + DecisionCard 구현

> 날짜: 2026-03-31
> 프롬프트: M7 — BriefingOverlay and DecisionCard components for the wargame War Room

## 변경 사항

### 신규 파일

| 파일 | 역할 |
|------|------|
| `frontend/src/components/wargame/BriefingOverlay.tsx` | Phase 2 브리핑 오버레이. 핵심 이벤트(심각도별 컬러), 상태 델타 바, 지난 결정 결과, 소셜 미디어 요약. "결정 단계로" CTA. |
| `frontend/src/components/wargame/DecisionCard.tsx` | Phase 3 결정 카드. 상황 내러티브, 2-4 선택지(카테고리별 컬러+엔진추천 배지+예측 델타+어드바이저 반응), 라디오 선택, "결정 확정" + "What-If 분기" 버튼. |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `frontend/src/components/wargame/WarRoom.tsx` | BriefingOverlay/DecisionCard import 및 phase 기반 조건 렌더링. handleDecisionConfirm (API 호출 + 확정 토스트 + 자동 전환), handleWhatIf 핸들러 추가. confirmation 토스트 오버레이 추가. |
| `frontend/src/hooks/useWargame.ts` | `setPhase()` 함수 추가. `createMockBriefing()`, `createMockDecisionPoint()` 목 데이터 생성기 추가. `advancePhase()`에서 briefing 진입 시 목 데이터 자동 생성. round ≥ 3 시 2초 후 자동 briefing 트리거 (목 모드). |

## 페이즈 전환 흐름

```
SSE: decision_required (또는 mock 자동 트리거)
  → phase="briefing" + briefing/decisionPoint 설정
  → BriefingOverlay 렌더링
  → 사용자 "결정 단계로" 클릭
  → phase="decision"
  → DecisionCard 렌더링
  → 사용자 옵션 선택 + "결정 확정"
  → resolve API 호출 → phase="confirmation"
  → 2초 후 자동 phase="simulation"
```

## 검증

- `tsc --noEmit`: 에러 0건
- `npm run build`: 성공 (4.0s 컴파일)
