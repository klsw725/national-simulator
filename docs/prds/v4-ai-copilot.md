# PRD: AI 코파일럿

> Status: Draft
> Created: 2026-03-21
> Dependencies: v4-ai-guided-decisions, v4-interactive-simulation
> 관련 스펙: `specs/V4-SPEC.md` PRD V4-4
> 버전: v4.0

---

## 1. 문제 정의

분석관이 시뮬레이션 결과를 스스로 해석해야 한다. "이 지역에서 최근 어떤 군사 활동이 있었나?", "가장 공격적인 행위자는 누구인가?" 같은 질문에 시스템이 답하지 못한다. 데이터가 있지만 분석관이 직접 탐색해야 한다.

## 2. 솔루션 개요

채팅 기반 AI 코파일럿. 현재 시나리오의 모든 데이터(관측, 시드, 시뮬레이션 결과, 지정학 분석)를 컨텍스트로 이해하고 분석관의 질문에 답한다.

**코파일럿 기능**:
- **데이터 질문** — "남중국해에 현재 몇 척의 군함이 있나?" → 관측 DB 검색 → 답변
- **결과 분석** — "시뮬레이션에서 가장 공격적인 행위자는?" → 액션 통계 분석 → 순위
- **What-If 제안** — "중국이 군사 훈련을 확대하면?" → What-If 시나리오 파라미터 제안
- **요약 생성** — "이 결과를 요약해줘" → 핵심 발견 추출 + 브리핑 초안
- **비교 분석** — "이전 시뮬레이션과 뭐가 달라졌나?" → 결과 diff 분석

## 3. 기술 상세

### 3.1 코파일럿 API

```
POST /api/copilot/chat
{
    "scenario_id": "scn_xxx",
    "message": "남중국해에 현재 몇 척의 군함이 있나?",
    "conversation_id": "conv_xxx"  // 대화 연속성
}
→ {
    "response": "현재 남중국해 해역에 12척의 군함이 관측되었습니다...",
    "sources": ["observations:obs_123", "seed:seed_456"],
    "tools_used": ["search_observations", "count_vessels"],
    "suggestions": ["이 군함들의 국적 분포를 보시겠습니까?"]
}
```

### 3.2 코파일럿 도구 (Function Calling)

```python
COPILOT_TOOLS = [
    search_observations,       # PostGIS 관측 검색
    count_entities,            # 엔티티 수 집계
    analyze_simulation_actions,  # 시뮬레이션 액션 통계
    get_geopolitics_summary,   # 지정학 분석 요약
    compare_scenarios,         # 2개 시나리오 비교
    suggest_whatif,            # What-If 파라미터 제안
    generate_summary,          # 핵심 발견 요약
]
```

### 3.3 컨텍스트 빌더

```python
class CopilotContextBuilder:
    async def build(self, scenario_id: str) -> str:
        """현재 시나리오의 모든 데이터를 LLM 컨텍스트로 구성."""
        # 시나리오 메타데이터
        # 시드 요약 (전문 아닌 핵심만)
        # 시뮬레이션 결과 통계
        # 지정학 분석 요약
        # 최근 관측 요약
```

### 3.4 수정 대상 파일

```
# 신규
backend/app/services/copilot.py               # 코파일럿 서비스 (LLM + 도구)
backend/app/services/copilot_tools.py          # 코파일럿 도구 함수
backend/app/services/copilot_context.py        # 컨텍스트 빌더
backend/app/routers/copilot.py                 # 코파일럿 API 라우터
frontend/src/components/simulation/CopilotPanel.tsx  # 채팅 UI

# 수정
backend/app/main.py                            # copilot 라우터 등록
frontend/src/components/simulation/SimulationPanel.tsx  # 코파일럿 탭/패널
frontend/src/lib/gatewayApi.ts                 # 코파일럿 API 호출
```

## 4. 마일스톤

- [ ] **M1: 코파일럿 API + 컨텍스트 빌더** — POST /api/copilot/chat 엔드포인트. CopilotContextBuilder로 시나리오 컨텍스트 구성. LLM 호출 (OpenAI Compatible). 대화 이력 관리.
  - 검증: "이 시나리오를 요약해줘" → 시드 + 결과 기반 요약 응답

- [ ] **M2: 코파일럿 도구 구현** — 7개 도구 (search_observations, count_entities, analyze_actions 등). LLM Function Calling으로 도구 자동 선택/실행. 도구 결과를 응답에 통합.
  - 검증: "남중국해에 군함 몇 척?" → search_observations 도구 호출 → 정확한 수 응답

- [ ] **M3: 코파일럿 도구 확장 (What-If, 비교)** — suggest_whatif: What-If 파라미터 제안. compare_scenarios: 2개 시나리오 diff. generate_summary: 핵심 발견 3-5개 추출.
  - 검증: "이전 시뮬레이션과 뭐가 달라졌나?" → diff 분석 응답

- [ ] **M4: 프론트엔드 CopilotPanel** — 채팅 UI (메시지 입력 + 응답 표시). 도구 사용 표시 (어떤 데이터를 검색했는지). 소스 링크 (관측/시드/결과). 제안 버튼 (다음 질문 추천).
  - 검증: 채팅으로 질문 → AI 응답 + 소스 표시 + 제안 버튼

## 5. 성공 기준

- 코파일럿이 시나리오 컨텍스트를 이해하고 질문에 정확하게 답한다
- 도구를 사용하여 실제 데이터를 검색/분석하여 답변한다 (환각 방지)
- 소스를 명시하여 답변의 근거를 확인할 수 있다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| LLM 환각 (없는 데이터 지어냄) | 도구 사용 강제. 도구 결과 없으면 "데이터 없음" 응답 |
| 컨텍스트 길이 초과 | 요약 기반 컨텍스트. 전체 데이터 대신 통계 + 핵심만 포함 |
| 응답 지연 (LLM + 도구 호출) | 스트리밍 응답. 도구 호출 중 "검색 중..." 표시 |

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V4-4 AI 코파일럿 PRD 초안 작성 |
