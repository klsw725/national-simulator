# PRD: 실시간 시뮬레이션 모니터링 (Realtime Monitoring)

> Status: Complete
> Created: 2026-03-20
> Dependencies: PRD 4 (simulation-orchestration), PRD 6b (scenario-management-ui), PRD 6c (simulation-visualization)
> 관련 스펙: `specs/MVP-SPEC.md` Section 4 Phase 2-3
> 버전: v2.0

---

## 1. 문제 정의

현재 시뮬레이션은 블랙박스로 실행된다. PipelineProgress가 "시뮬레이션 실행 중"을 표시할 뿐, **어떤 에이전트가 무엇을 하고 있는지** 보이지 않는다. 시뮬레이션이 수십 분 동안 돌아가는데 사용자는 완료될 때까지 아무것도 할 수 없다.

MiroFish는 이미 실시간 데이터를 제공한다:
- `GET /api/simulation/{id}/run-status` — 현재 라운드, 액션 수, 진행률
- `GET /api/simulation/{id}/actions` — 발생한 액션 목록 (실시간)
- `GET /api/simulation/{id}/posts` — 생성된 포스트 (실시간)
- `GET /api/simulation/{id}/agent-stats` — 에이전트별 통계

이 데이터를 활용하여 시뮬레이션 실행 중 실시간 피드를 제공해야 한다.

## 2. 솔루션 개요

3개 실시간 뷰를 추가한다:

- **LiveActionFeed** — 에이전트 행동이 발생할 때마다 실시간 스트림 (채팅 UI 유사)
- **LiveStats** — 현재 라운드, 에이전트별 활동량, 전체 진행률 대시보드
- **Intermediate Results** — 각 파이프라인 단계의 중간 산출물 실시간 표시 (온톨로지, 페르소나, 설정)

## 3. 기술 상세

### 3.1 실시간 데이터 흐름

```
MiroFish 시뮬레이션 (백그라운드)
  ↓ actions.jsonl (실시간 기록)
  ↓
Gateway API (폴링 프록시)
  GET /api/scenario/{id}/live/actions?since={last_id}
  GET /api/scenario/{id}/live/stats
  ↓
프론트엔드 (2초 폴링)
  LiveActionFeed + LiveStats
```

### 3.2 Gateway 라이브 프록시 API

```
GET /api/scenario/{id}/live/actions    → MiroFish actions 포워딩 (offset 기반)
GET /api/scenario/{id}/live/stats      → MiroFish run-status 포워딩
GET /api/scenario/{id}/live/profiles   → MiroFish profiles 포워딩
GET /api/scenario/{id}/live/config     → MiroFish config 포워딩
```

### 3.3 LiveActionFeed 컴포넌트

채팅/타임라인 UI:
```
┌─────────────────────────────────────┐
│ 🔴 라이브 — 라운드 5/10 (50%)       │
├─────────────────────────────────────┤
│ 🇺🇸 United States [CREATE_POST]     │
│ "항행의 자유 작전 지속을 재확인..."    │
│                                     │
│ 🇨🇳 China [QUOTE_POST → US]         │
│ "내정 간섭에 강력히 반대한다"         │
│                                     │
│ 🇯🇵 Japan [REPOST → US]             │
│ (동맹국 성명 지지)                   │
│                                     │
│ 🇰🇷 South Korea [DO_NOTHING]        │
│ (전략적 관망)                        │
│                            ▼ 자동 스크롤 │
└─────────────────────────────────────┘
```

- 2초 간격 폴링으로 새 액션 추가
- 에이전트별 국기 이모지 + 이름
- 액션 유형별 아이콘/색상
- 콘텐츠 프리뷰 (CREATE_POST, QUOTE_POST만)
- 자동 스크롤 + 수동 스크롤 시 일시정지

### 3.4 LiveStats 컴포넌트

```
┌──────────────────────────────────┐
│ 라운드: ████████░░ 5/10 (50%)     │
│ 총 액션: 147                      │
│                                  │
│ 에이전트 활동:                     │
│ US ████████████ 32 (활발)          │
│ CN ██████████   28 (활발)          │
│ JP ██████       15 (보통)          │
│ KR ██           5 (관망)           │
│ PH ████         12 (보통)          │
│                                  │
│ 액션 유형:                        │
│ CREATE_POST  45 (31%)             │
│ QUOTE_POST   38 (26%)             │
│ REPOST       32 (22%)             │
│ LIKE_POST    20 (14%)             │
│ DO_NOTHING   12 (8%)              │
└──────────────────────────────────┘
```

### 3.5 중간 산출물 뷰어

파이프라인 각 단계가 완료되면 결과를 즉시 표시:

| 단계 | 표시 내용 |
|------|-----------|
| 온톨로지 생성 | 엔티티 타입 목록 + 관계 타입 목록 (트리 뷰) |
| 그래프 빌드 | 추출된 엔티티 카드 (이름, 타입, 설명) |
| 프로필 생성 | 에이전트 페르소나 카드 (이름, 역할, 성격 요약) — 실시간으로 한 장씩 추가 |
| 시뮬레이션 설정 | 라운드 수, 에이전트 활동 수준, 초기 이벤트 |
| 시뮬레이션 실행 | LiveActionFeed + LiveStats |
| 보고서 생성 | 진행률 표시 → 완료 시 ReportViewer |

### 3.6 수정 대상 파일

```
backend/app/routers/simulation.py     — 수정: +live/* 프록시 엔드포인트 4개
frontend/src/components/simulation/
├── LiveActionFeed.tsx                — 신규: 실시간 액션 스트림
├── LiveStats.tsx                     — 신규: 실시간 통계 대시보드
├── IntermediateResults.tsx           — 신규: 중간 산출물 뷰어 (온톨로지/페르소나/설정)
└── SimulationPanel.tsx               — 수정: 시뮬레이션 실행 중 라이브 뷰 전환
frontend/src/hooks/
└── useLiveSimulation.ts              — 신규: 실시간 폴링 훅 (2초 간격, offset 기반)
```

## 4. 마일스톤

- [x] **M1: Gateway 라이브 프록시** — MiroFish 실시간 엔드포인트를 Gateway로 프록시. `GET /live/actions`, `/live/stats`, `/live/profiles`, `/live/config`. mirofish_simulation_id를 사용하여 MiroFish API 호출.
  - 검증: 시뮬레이션 실행 중 Gateway API로 실시간 데이터 조회

- [x] **M2: LiveActionFeed + LiveStats** — 실시간 액션 스트림 컴포넌트. 2초 폴링. 에이전트별 국기+이름, 액션 유형 아이콘. 실시간 통계 (라운드, 액션 수, 에이전트 활동량).
  - 검증: 시뮬레이션 실행 중 실시간 액션 피드 표시

- [x] **M3: IntermediateResults 뷰어** — 각 파이프라인 단계 완료 시 중간 결과 표시. 온톨로지 트리, 페르소나 카드 (실시간 추가), 시뮬레이션 설정 요약.
  - 검증: 파이프라인 진행 중 각 단계의 산출물이 실시간으로 표시

- [x] **M4: SimulationPanel 통합** — SimulationPanel에서 시뮬레이션 상태에 따라 뷰 자동 전환: 준비 중→중간 결과, 실행 중→라이브 피드, 완료→결과 시각화.
  - 검증: 전체 파이프라인에서 뷰 전환이 자연스럽게 동작

## 5. 성공 기준

- 시뮬레이션 실행 중 에이전트 행동이 실시간으로 보인다
- 현재 라운드, 진행률, 에이전트별 활동량이 실시간으로 업데이트된다
- 파이프라인 각 단계의 중간 산출물(온톨로지, 페르소나, 설정)을 볼 수 있다
- 페르소나 카드가 생성되는 과정을 실시간으로 볼 수 있다 (한 장씩 추가)
- 기존 auto 모드에서도 실시간 모니터링이 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 2초 폴링이 Gateway/MiroFish에 부담 | offset 기반 incremental fetch. 변경 없으면 빈 응답 |
| 라이브 피드 자동 스크롤이 수동 탐색을 방해 | 수동 스크롤 시 자동 스크롤 일시정지. "최신으로" 버튼 |
| MiroFish 실시간 엔드포인트 응답 지연 | 폴링 실패 시 재시도. 타임아웃 3초. 실패 표시 UI |

## 7. 참고

### MiroFish 실시간 API (이미 존재)
- `GET /api/simulation/{id}/run-status` — runner_status, current_round, progress_percent
- `GET /api/simulation/{id}/actions?limit=N&offset=M` — 액션 목록 (페이징)
- `GET /api/simulation/{id}/posts?platform=twitter` — 생성된 포스트
- `GET /api/simulation/{id}/agent-stats` — 에이전트별 통계
- `GET /api/simulation/{id}/profiles/realtime` — 프로필 생성 중 실시간 조회
- `GET /api/simulation/{id}/config/realtime` — 설정 생성 중 실시간 조회

### 관련 PRD
- **PRD 4 (simulation-orchestration)** — 파이프라인 실행 로직
- **v2-pipeline-checkpoints** — 체크포인트 모드 (이 PRD와 상호 보완)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | 사용자 피드백 기반 PRD 생성 — "시뮬레이션이 보이지 않는다" 문제 해결 |
