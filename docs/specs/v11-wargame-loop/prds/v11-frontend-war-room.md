# PRD: 프론트엔드 상황실 (War Room)

> Status: Draft
> Created: 2026-03-31
> Dependencies: v11-backend-wargame-engine (SSE, 오케스트레이터), v4-interactive-simulation (DecisionPointView, GeopoliticsDecisionView)
> 관련 스펙: [v11-wargame-loop/spec.md](../spec.md) 섹션 3.8
> 버전: v11.2

---

## 1. 문제 정의

V11 스펙의 프론트엔드 전환: 탭 기반 `SimulationPanel`을 **페이즈 기반 상황실(War Room) UI**로 변경한다. 사용자가 워게임 루프의 4개 페이즈(시뮬레이션 → 브리핑 → 결정 → 확정)를 직관적으로 경험할 수 있는 인터페이스를 구축한다.

### 범위

스펙의 마일스톤 M6~M8에 해당:

| 마일스톤 | 내용 | 산출물 |
|----------|------|--------|
| M6 | 상황실 기본 레이아웃 | `WarRoom.tsx`, `PhaseBar.tsx`, `LensPanel.tsx`, `ContextPanel.tsx`, `FeedPanel.tsx`, `useWargame.ts` |
| M7 | 브리핑 + 결정 카드 | `BriefingOverlay.tsx`, `DecisionCard.tsx` |
| M8 | 디브리프 + 타임라인 | `DebriefView.tsx`, `RoundTimeline.tsx` |

### 제약 조건

- 기존 `SimulationPanel`은 `wargame_enabled=false` 시 그대로 유지
- 워게임 모드는 별도 `WarRoom` 컴포넌트로 분리 — 기존 컴포넌트에 조건 분기 최소화
- 기존 컴포넌트 재활용: `GeopoliticsDecisionView.tsx`, `LiveActionFeed.tsx`, `LiveStats.tsx` 내부 로직 가져오기
- SSE 기반 (백엔드 M5 의존). SSE 미연결 시 5초 폴링 폴백
- No Redux/Zustand — 기존 프로젝트 패턴대로 React hooks + context

---

## 2. UX 설계 원칙

### 워게임/외교 시뮬레이션 UX 리서치 기반

스펙에 반영된 레퍼런스 (Paradox Victoria 3, XCOM, Battleplan, Palantir, Statecraft, Suzerain)에서 도출한 원칙:

1. **관찰/행동 하드 분리**: 시뮬레이션 실행 중 결정 UI 부재 (비활성이 아니라 물리적 부재)
2. **브리핑은 필수**: 결정 전 구조화된 상황 요약 화면을 거침 (XCOM 월말 리포트)
3. **결과 예측 표시**: 선택지별 예측 델타를 결정 전에 보여줌 (Into the Breach)
4. **3단계 정보 공개**: Tier 1(항상 보임) → Tier 2(호버) → Tier 3(클릭) (CK3)
5. **맵이 진리**: 맵은 항상 보이고, 피드/패널이 맵을 대체하지 않음 (Palantir)
6. **위기 에스컬레이션**: 심각도에 따라 알림 방식이 달라짐 (Low=뱃지, High=오버레이, Critical=풀스크린)

---

## 3. 기술 상세

### M6: 상황실 기본 레이아웃

**화면 구조:**

```
┌───────────────────────────────────────────────────────────────────────┐
│ PhaseBar: [● 시뮬레이션] → [○ 브리핑] → [○ 결정] → [○ 확정]          │
│ Round 3/8         🇺🇸 USA (ACTOR_ROLE)         Tension: ■■■□□ 0.6   │
├───────────┬──────────────────────────────────┬───────────────────────┤
│ LensPanel │         MAP (기존 MaplibreViewer) │ ContextPanel          │
│           │                                  │                      │
│ [정보전]   │   OSINT + 에이전트 + 이벤트 마커  │ 선택 객체 상세        │
│ [외교]     │   (렌즈에 따라 오버레이 전환)      │ + 가능한 액션         │
│ [군사]     │                                  │                      │
│ [경제]     │                                  │ Actor 상태 요약       │
│ [관계망]   │                                  │                      │
│ [What-If]  │                                  │                      │
├───────────┴──────────────────────────────────┴───────────────────────┤
│ FeedPanel: 소셜 미디어 피드                 │ RoundTimeline          │
└─────────────────────────────────────────────┴────────────────────────┘
```

**신규 컴포넌트:**

| 컴포넌트 | 위치 | 역할 |
|----------|------|------|
| `WarRoom.tsx` | 메인 | 상황실 전체 레이아웃. `wargame_enabled` 시 `SimulationPanel` 대신 렌더링 |
| `PhaseBar.tsx` | 상단 | 4개 페이즈 인디케이터 + 라운드 카운터 + 역할 표시 + 긴장도 게이지 |
| `LensPanel.tsx` | 좌측 | 렌즈 버튼 목록. 클릭 시 맵 오버레이 전환 |
| `ContextPanel.tsx` | 우측 | 선택된 맵 객체의 상세정보 + 해당 객체에 대한 가능한 액션 + Actor 상태 바 |
| `FeedPanel.tsx` | 하단 좌 | 소셜 미디어 피드. 기존 `LiveActionFeed` 로직 재활용 |

**신규 훅:**

| 훅 | 역할 |
|----|------|
| `useWargame.ts` | SSE 연결 + 워게임 상태 관리 (phase, round, tension, actorStates, briefing, decisionPoint) |

**타입 추가:**

```typescript
// frontend/src/types/simulation.ts 에 추가

type WargamePhase = "simulation" | "briefing" | "decision" | "confirmation";

interface WargameState {
  phase: WargamePhase;
  round: number;
  totalRounds: number;
  role: "actor_role" | "game_master";
  actorId: string | null;
  tension: number;
  actorStates: Record<string, ActorState>;
  briefing: RoundBriefing | null;
  decisionPoint: DecisionPoint | null;
}

interface ActorState {
  actor_id: string;
  name: string;
  threat_perception: number;
  domestic_pressure: number;
  resource_level: number;
}

interface RoundBriefing {
  round: number;
  key_events: BriefingEvent[];
  state_deltas: Record<string, number>;
  previous_decision_outcome: string | null;
  social_media_summary: { total_posts: number; top_topics: string[] };
}
```

**페이즈별 UI 상태:**

| 페이즈 | PhaseBar 색상 | 맵 상태 | 결정 UI | 피드 |
|--------|-------------|---------|---------|------|
| simulation | Cool 블루 | 에이전트 활동 애니메이션 | 없음 (부재) | 실시간 스크롤 |
| briefing | Neutral | 이벤트 마커 하이라이트 | 없음 | 라운드 요약 |
| decision | Warm 앰버 | 관련 지역 하이라이트 | DecisionCard 오버레이 | 관련 피드 필터 |
| confirmation | Neutral | 결정 반영 애니메이션 | 토스트 "결정 반영됨" | 전체 피드 |

**렌즈 시스템:**

렌즈 선택 시 맵 오버레이가 자동 전환 (Victoria 3 패턴):

| 렌즈 | 맵 오버레이 |
|------|-----------|
| 정보전 | 소셜 미디어 영향력 히트맵 (에이전트 포스트 밀도) |
| 외교 | 국가 간 관계선 (동맹=파랑, 적대=빨강) |
| 군사 | 군사 이동/배치 마커 (OSINT 선박/항공/위성 데이터) |
| 경제 | 무역/제재 영향 표시 |
| 관계망 | 엔티티 관계 그래프 (기존 GraphTab 로직) |
| What-If | 분기 생성 UI (기존 WhatIfBranchView 로직) |

**검증:**
- 워게임 모드 시뮬레이션 시작 → `WarRoom` 렌더링 (탭 네비게이션 없음)
- PhaseBar에 현재 페이즈 표시 + 라운드 카운터
- 렌즈 클릭 → 맵 오버레이 전환
- SSE `phase_change` 수신 → 페이즈 바 자동 업데이트
- `wargame_enabled=false` → 기존 `SimulationPanel` 그대로 렌더링

### M7: 브리핑 + 결정 카드

**신규 컴포넌트:**

| 컴포넌트 | 역할 |
|----------|------|
| `BriefingOverlay.tsx` | Phase 2 브리핑 오버레이. 맵 위 반투명 카드. 핵심 이벤트, 상태 델타, 지난 결정 결과, 소셜 미디어 요약 표시. "결정 단계로" 버튼. |
| `DecisionCard.tsx` | Phase 3 결정 카드. 맵 위 중앙 오버레이. 상황 내러티브 + 2~4 선택지 + 선택지별 예측 델타 + 어드바이저 반응. "결정 확정" + "What-If 분기" 버튼. |

**브리핑 오버레이 구성:**

```
┌─ BriefingOverlay ────────────────────────────┐
│  📋 ROUND N 브리핑                            │
│                                              │
│  [핵심 이벤트] 이벤트 타입별 컬러 아이콘 + 1줄  │
│  [상태 변화] threat/pressure/resource 바 + 델타 │
│  [지난 결정 결과] 피드백 텍스트                  │
│  [소셜 미디어 요약] 포스트 수 + 주요 화제        │
│                                              │
│              [ 브리핑 확인 → 결정 단계로 ]       │
└──────────────────────────────────────────────┘
```

**결정 카드 구성:**

스펙 3.8의 결정 카드 상세 UI 구현. 기존 `GeopoliticsDecisionView.tsx`의 옵션 렌더링 로직을 재활용하되, 레이아웃을 오버레이 카드 형태로 변경.

- 선택지별 `predicted_deltas` → PROPAGATION_RULES에서 계산 (기존 로직)
- 어드바이저 반응 → 선택지 영향도에 따라 규칙 기반 생성
- "엔진 추천" 배지 → `engine_recommended=true` 옵션에 표시
- 선택 확정 → `resolveDecisionPoint()` API 호출 (기존 엔드포인트 재활용)

**페이즈 전환 흐름:**

```
SSE: decision_required
  → setPhase("briefing") + setBriefing(data.briefing)
  → BriefingOverlay 렌더링
  → 사용자 "결정 단계로" 클릭
  → setPhase("decision") + setDecisionPoint(data.decision_point)
  → DecisionCard 렌더링
  → 사용자 선택 + "결정 확정" 클릭
  → resolveDecisionPoint() API 호출
  → setPhase("confirmation")
  → 2초 후 자동 setPhase("simulation") (다음 라운드)
```

**검증:**
- SSE `decision_required` 수신 → 브리핑 오버레이 자동 표시
- 브리핑에 핵심 이벤트 + 상태 델타 + 소셜 미디어 요약 표시
- "결정 단계로" 클릭 → 결정 카드 오버레이 전환
- 선택지별 예측 델타 + 어드바이저 반응 표시
- 선택 확정 → API 호출 → 시뮬레이션 재개

### M8: 디브리프 + 타임라인

**신규 컴포넌트:**

| 컴포넌트 | 역할 |
|----------|------|
| `DebriefView.tsx` | 게임 종료 후 디브리프 화면. 긴장도 곡선 (Recharts), 최종 상태 요약, 결정 히스토리, "전체 리포트 보기" / "새 시뮬레이션" / "What-If 분기" 버튼 |
| `RoundTimeline.tsx` | 하단 타임라인 바. 라운드 마커 + 결정 마커(⚡). 스크러버 드래그로 과거 라운드 상태 확인. 클릭 시 해당 라운드의 이벤트/결정 상세 팝업 |

**타임라인 바 구성:**

```
[R1]──[R2]──[R3 ⚡]──[R4]──[R5 ⚡]──[R6]──[R7]──[R8]
               ↑ 스크러버: 드래그 가능
```

- 일반 라운드: 회색 원
- 결정 라운드: 앰버 ⚡ 마커
- 현재 라운드: 하이라이트 (크기 확대 + 색상)
- 완료된 라운드: 체크 마크
- 스크러빙 시: 해당 시점의 맵 상태 + 이벤트를 `ContextPanel`에 표시

**디브리프 구성:**

```
┌─ DebriefView (전체 화면 오버레이) ──────────────────┐
│                                                    │
│  긴장도 곡선 (Recharts LineChart, 전체 너비)         │
│  X축: 라운드, Y축: 긴장도 0~1                       │
│  결정 마커: 수직 점선 + 라벨                         │
│                                                    │
│  ┌─ 최종 상태 ─────┐  ┌─ 결정 히스토리 ──────────┐ │
│  │ 총 라운드: 8     │  │ R3: 군사 대응 → 긴장도↑  │ │
│  │ 결정 횟수: 2     │  │ R5: 외교적 대응 → 긴장↓  │ │
│  │ 최종 긴장: 0.45  │  │                         │ │
│  └─────────────────┘  └─────────────────────────┘ │
│                                                    │
│  [ 전체 리포트 ]  [ 새 시뮬레이션 ]  [ What-If 분기 ] │
└────────────────────────────────────────────────────┘
```

- "전체 리포트" → 기존 ReportViewer로 이동
- "What-If 분기" → 결정 마커 클릭 후 해당 라운드에서 분기 생성 (기존 WhatIfEngine)

**검증:**
- 전체 시뮬레이션 완료 (SSE `simulation_complete`) → 디브리프 화면 자동 표시
- 긴장도 곡선에 라운드별 긴장도 + 결정 마커 표시
- 타임라인 스크러빙 → 해당 라운드 상태 표시
- 결정 마커 클릭 → 당시 선택지 + 결과 팝업
- "What-If 분기" → WhatIfEngine 호출 확인

---

## 4. 수정 대상 파일 요약

```
# 신규
frontend/src/hooks/useWargame.ts
frontend/src/components/wargame/WarRoom.tsx
frontend/src/components/wargame/PhaseBar.tsx
frontend/src/components/wargame/LensPanel.tsx
frontend/src/components/wargame/ContextPanel.tsx
frontend/src/components/wargame/FeedPanel.tsx
frontend/src/components/wargame/BriefingOverlay.tsx
frontend/src/components/wargame/DecisionCard.tsx
frontend/src/components/wargame/DebriefView.tsx
frontend/src/components/wargame/RoundTimeline.tsx
frontend/src/lib/api/wargameApi.ts

# 수정
frontend/src/components/simulation/SimulationPanel.tsx  # wargame_enabled 분기
frontend/src/types/simulation.ts                        # WargamePhase, WargameState 타입
```

---

## 5. 구현 순서

M6 → M7 → M8 (순차적 의존성)

- M6(레이아웃)이 없으면 M7(브리핑/결정)의 오버레이를 붙일 곳이 없음
- M7이 없으면 M8(디브리프)의 결정 히스토리를 표시할 데이터가 없음
- M6는 백엔드 M5(SSE) 완료 후 시작

---

## 6. 성공 기준

- 워게임 모드에서 탭 네비게이션이 없고, 페이즈 기반 UI만 존재
- 페이즈 전환이 SSE로 실시간 반영 (폴링 지연 없음)
- 결정 카드에 선택지별 예측 결과 + 어드바이저 반응 표시
- 브리핑 화면에서 지난 결정의 결과 피드백 확인 가능
- 디브리프 타임라인에서 과거 라운드 스크러빙 + 결정 복기 가능
- `wargame_enabled=false` 시 기존 SimulationPanel 그대로 동작

---

## 7. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 상황실 레이아웃이 기존 OSINT 패널(좌측 400px)과 충돌 | WarRoom은 전체 뷰포트 사용. OSINT 패널은 렌즈 중 하나로 통합 |
| 렌즈별 맵 오버레이 구현 복잡도 | M6에서는 기존 OSINT 오버레이만 렌즈로 전환. 커스텀 히트맵 등은 후속 |
| SSE 연결 불안정 | 자동 재연결 + 5초 폴링 폴백 (기존 useLiveSimulation 패턴) |
| Recharts 긴장도 곡선 성능 | 라운드 수 최대 20~30 — 성능 이슈 없음 |
| 모바일/태블릿 레이아웃 | v11은 데스크톱 전용. 반응형은 후속 |

---

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-31 | Draft | v11.2 프론트엔드 상황실 PRD 작성 |
