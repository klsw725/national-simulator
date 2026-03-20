# PRD: 파이프라인 체크포인트 모드 (Pipeline Checkpoints)

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 4 (simulation-orchestration), PRD 6b (scenario-management-ui)
> 관련 스펙: `specs/MVP-SPEC.md` Section 4 (Data Flow), Section 11 (프롬프트 커스터마이징)
> 버전: v2.0

---

## 1. 문제 정의

현재 SimulationOrchestrator는 6단계 파이프라인을 완전 자동으로 실행한다. MiroFish 원래 워크플로우에는 각 단계 사이에 사람 검토/수정 단계가 있었으나, osint-simulator는 이를 모두 건너뛴다. 결과적으로:

- LLM이 생성한 온톨로지가 부적절해도 그대로 시뮬레이션에 사용됨
- 에이전트 페르소나가 비현실적이어도 수정 기회 없음
- 시뮬레이션 설정(라운드 수, 활동 수준)이 부적절해도 조정 불가
- 분석관이 시뮬레이션 과정에 전문 지식을 투입할 수 없음

## 2. 솔루션 개요

파이프라인에 **5개 체크포인트**를 삽입하여, 각 단계 완료 시 일시정지하고 사람이 검토/수정 후 다음 단계를 진행하는 모드를 추가한다. 기존 자동 모드도 유지 (선택 가능).

```
시나리오 생성 → 시드 생성 → ⏸️ CP1: 시드 검토
→ 온톨로지 생성 → ⏸️ CP2: 온톨로지 검토/수정
→ 그래프 빌드 → ⏸️ CP3: 엔티티/관계 검토
→ 프로필 생성 → ⏸️ CP4: 페르소나 검토/수정
→ 시뮬레이션 설정 생성 → ⏸️ CP5: 설정 검토/수정
→ 시뮬레이션 실행 → 보고서 생성 → 완료
```

## 3. 기술 상세

### 3.1 실행 모드

```typescript
type PipelineMode = 'auto' | 'checkpoint';
```

- **auto**: 현재 동작 (전부 자동)
- **checkpoint**: 각 체크포인트에서 일시정지, `POST /api/scenario/{id}/continue`로 진행

### 3.2 체크포인트 정의

| CP | 시점 | 검토 대상 | 수정 가능 항목 |
|----|------|-----------|---------------|
| CP1 | 시드 생성 후 | 시드 문서 마크다운 | 시드 텍스트 직접 편집 |
| CP2 | 온톨로지 생성 후 | 엔티티 타입, 관계 타입 | 타입 추가/제거/수정 |
| CP3 | 그래프 빌드 후 | 추출된 엔티티, 관계 목록 | 엔티티/관계 삭제 |
| CP4 | 프로필 생성 후 | 에이전트 페르소나 카드 | 페르소나 텍스트 수정 |
| CP5 | 시뮬레이션 설정 후 | 라운드 수, 에이전트 활동 수준, 초기 포스트 | 설정값 수정 |

### 3.3 백엔드 API 확장

```
POST /api/scenario/{id}/simulate     body: {"mode": "checkpoint"}
GET  /api/scenario/{id}/checkpoint   → 현재 체크포인트 상태 + 검토 데이터
POST /api/scenario/{id}/continue     → 다음 단계 진행 (수정사항 포함)
POST /api/scenario/{id}/continue     body: {"edits": {...}}  → 수정 후 진행
```

### 3.4 오케스트레이터 변경

SimulationOrchestrator에 체크포인트 로직 추가:
- 각 단계 완료 후 `status = "checkpoint:{step}"` 으로 DB 업데이트
- 중간 결과를 DB에 저장 (ontology JSON, profiles JSON, config JSON)
- `continue` API 호출 시 저장된 중간 결과(수정 포함)로 다음 단계 실행

### 3.5 프론트엔드 체크포인트 UI

PipelineProgress 컴포넌트 확장:
- 체크포인트 도달 시 해당 단계에 "검토" 버튼 표시
- 검토 모달: 중간 결과 표시 + 편집 UI
- "확인 & 계속" 버튼으로 다음 단계 진행
- "자동으로 계속" 체크박스 (남은 체크포인트 건너뛰기)

## 4. 마일스톤

- [ ] **M1: 백엔드 체크포인트 모드** — SimulationOrchestrator에 checkpoint 모드 추가. 중간 결과 DB 저장. `GET /checkpoint`, `POST /continue` API. 기존 auto 모드 유지.
  - 검증: checkpoint 모드로 실행 → 각 단계에서 일시정지 → continue로 진행

- [ ] **M2: 중간 결과 조회 API** — MiroFish API 활용: `GET /profiles`, `GET /config`, 온톨로지/그래프 데이터 조회. Gateway 프록시 확장.
  - 검증: 각 체크포인트에서 해당 단계의 중간 결과 조회 가능

- [ ] **M3: 프론트엔드 체크포인트 UI** — PipelineProgress에 검토 버튼 + 모달. 시드 편집기, 온톨로지 뷰어, 페르소나 카드 뷰어, 설정 에디터.
  - 검증: UI에서 중간 결과 검토 + 수정 후 계속 진행

## 5. 성공 기준

- checkpoint 모드에서 각 단계 완료 시 일시정지되고 중간 결과를 검토할 수 있다
- 검토 단계에서 수정한 내용이 다음 단계에 반영된다
- auto 모드는 기존과 동일하게 동작한다 (regression 없음)
- "자동으로 계속" 옵션으로 남은 체크포인트를 건너뛸 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| 체크포인트 대기 중 MiroFish 세션 만료 | 중간 결과를 Gateway DB에 저장, MiroFish 세션과 독립적으로 관리 |
| 수정된 데이터가 MiroFish 포맷과 불일치 | 수정 범위를 텍스트 편집으로 한정. 구조 변경은 v3에서 |
| 검토 UI가 복잡해서 분석관이 사용하지 않음 | 각 체크포인트 검토를 선택적으로 (기본은 auto) |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | 사용자 피드백 기반 PRD 생성 — MiroFish 원래 검토 단계 복원 |
