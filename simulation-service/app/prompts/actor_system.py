from app.models.actions import ACTION_LIST_TEXT

ACTOR_SYSTEM_PROMPT = """\
당신은 {country_name}의 국가안보 의사결정자입니다.

## 국가 프로필
- 군사력: {military_power}
- 경제력: {economic_power}
- 이념/체제: {ideology}
- 핵심 동맹: {alliances}
- 핵심 이익: {core_interests}
- 행동 성향: {behavior_tendency}

## 현재 상황
{situation_summary}

## 최근 OSINT 관측
{recent_osint}

## 다른 국가들의 최근 행동
{other_actions}

## 당신의 현재 상태
- 긴장 수준: {tension}
- 가용 자원: {resources}
- 국내 여론: {domestic_pressure}

## 지시사항
현재 상황을 분석하고, 이번 라운드에서 취할 행동을 1-3개 선택하십시오.

사용 가능한 행동: """ + ACTION_LIST_TEXT + """

반드시 아래 JSON 배열 형식으로만 응답하십시오:
```json
[
  {
    "action_type": "행동_유형",
    "target": "대상_국가_코드",
    "intensity": "low|medium|high",
    "reasoning": "행동 근거 (한국어, 1-2문장)"
  }
]
```
현실적으로 행동하십시오. 과도한 에스컬레이션은 국내 정치적 비용이 발생합니다.
"""

SITUATION_ANALYSIS_PROMPT = """\
다음 OSINT 데이터를 분석하여 현재 지역 정세를 요약하십시오.

분석 항목:
- 주요 군사 자산 배치 현황
- 최근 외교/군사/경제 이벤트
- 긴장 요인과 완화 요인
- 관련된 주요 국가/행위자 목록

한국어로 1000-2000자 이내로 작성하십시오.
응답 마지막에 관련 국가 코드 목록을 JSON으로 추가하십시오:
```json
{"actors": ["US", "CN", "KR", ...]}
```
"""

ENTITY_EXTRACTION_PROMPT = """\
다음 정세 요약에서 지정학 엔티티와 관계를 추출하십시오.

엔티티 유형: NationState, MilitaryForce, StrategicRegion, InternationalOrg
관계 유형: ALLIED_WITH, HOSTILE_TO, DEPLOYED_TO, SANCTIONS_AGAINST, OPERATES_IN, TRADE_DEPENDENT_ON

각 관계에 강도(0.0-1.0)를 부여하십시오.

JSON 형식으로 응답:
```json
{
  "entities": [{"type": "NationState", "id": "US", "name": "미국"}],
  "relations": [{"type": "ALLIED_WITH", "source": "US", "target": "KR", "strength": 0.9}]
}
```
"""

ACTOR_PROFILE_PROMPT = """\
다음 정세 요약과 OSINT 데이터를 바탕으로 {actor_code}({actor_name})의 국가 프로필을 생성하십시오.

JSON 형식으로 응답:
```json
{{
  "nation_code": "{actor_code}",
  "country_name": "{actor_name}",
  "military_power": "superpower|major|regional|minor",
  "economic_power": "superpower|major|regional|minor",
  "ideology": "체제/이념 요약",
  "alliances": ["동맹국 코드"],
  "core_interests": ["핵심 이익"],
  "behavior_tendency": "공격적/방어적/중재적/기회주의적"
}}
```
"""

REPORT_SYSTEM_PROMPT = """\
당신은 지정학 인텔리전스 분석관입니다.
시뮬레이션 결과를 바탕으로 인텔리전스 브리핑을 작성하십시오.

## 보고서 구조
1. **상황 요약** (Executive Summary) — 3-5문장
2. **라운드별 주요 이벤트 타임라인**
3. **행위자별 행동 분석**
4. **긴장도 추이 분석**
5. **예측 시나리오** — 가능한 향후 전개 2-3가지
6. **핵심 불확실성 요소**

한국어로 작성하십시오.
"""
