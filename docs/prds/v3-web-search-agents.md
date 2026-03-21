# PRD: DuckDuckGo 웹 검색 통합

> Status: Draft
> Created: 2026-03-21
> Dependencies: seed-generation, v3-simulation-params
> 관련 스펙: `specs/V3-SPEC.md` PRD V3-4
> 버전: v3.0

---

## 1. 문제 정의

시뮬레이션 에이전트가 사전 주입된 컨텍스트(시드 문서, 페르소나)에만 의존하고, 실시간 뉴스/정보를 검색할 수 없다.

현재 제한:
- SeedGenerator가 ShadowBroker OSINT 데이터만 사용 — 일반 뉴스/언론 보도 미포함
- OASIS SocialAgent가 내장 지식에만 의존 — 시뮬레이션 중 실시간 정보 검색 불가
- 시뮬레이션 맥락이 GDELT 이벤트 데이터에만 한정 — 뉴스 기사 본문 미반영

## 2. 솔루션 개요

2단계 통합:

**Phase 1 (시드 보강)**: 시드 생성 시 DuckDuckGo로 관련 뉴스 검색 → 시드 문서에 "최근 뉴스" 섹션 추가. MiroFish/OASIS 수정 없이 가능.

**Phase 2 (에이전트 도구)**: OASIS SocialAgent의 `tools` 파라미터에 `SearchToolkit().search_duckduckgo` 주입. `single_iteration=False` 필수. MiroFish simulation_runner 수정 필요.

## 3. 기술 상세

### 3.1 WebSearchService (Phase 1)

```python
# backend/app/services/web_search.py (신규)
from duckduckgo_search import DDGS

class WebSearchService:
    def __init__(self, max_results: int = 5, cache_ttl: int = 3600):
        self.max_results = max_results
        self.cache = {}  # 간단한 인메모리 캐시

    async def search_news(self, keywords: list[str], region: str = "wt-wt") -> list[dict]:
        """
        DuckDuckGo 뉴스 검색.
        반환: [{title, url, body, source, date}, ...]
        """

    async def search_web(self, query: str) -> list[dict]:
        """
        DuckDuckGo 일반 웹 검색.
        반환: [{title, url, body}, ...]
        """

    def format_for_seed(self, results: list[dict]) -> str:
        """검색 결과를 시드 문서 삽입용 마크다운으로 포맷"""
```

### 3.2 SeedGenerator 웹 검색 통합 (Phase 1)

```python
# seed_generator.py 수정

async def generate(self, bbox, question, region_name, web_search_enabled=False):
    # ... 기존 SB 데이터 수집 ...

    web_context = ""
    if web_search_enabled:
        keywords = self._extract_keywords(question, region_name, actors)
        news_results = await self.web_search.search_news(keywords)
        web_context = self.web_search.format_for_seed(news_results)

    # LLM 프롬프트에 web_context 추가
    prompt = SEED_GENERATION_PROMPT.format(
        # ... 기존 컨텍스트 ...
        recent_news=web_context  # 신규 섹션
    )
```

### 3.3 MiroFish simulation_runner 도구 주입 (Phase 2)

MiroFish의 simulation_runner에 tools 파라미터를 전달하는 경로 추가.

```python
# external/mirofish-backend에서 수정 필요:
# simulation_runner.py의 SocialAgent 생성 시 tools 파라미터 전달

# OASIS SearchToolkit 사용:
from camel.toolkits import SearchToolkit
tools = [SearchToolkit().search_duckduckgo]

# SocialAgent 생성 시:
agent = SocialAgent(
    # ... 기존 파라미터 ...
    tools=tools,
    single_iteration=False  # 도구 사용을 위해 필수
)
```

### 3.4 레이트 리밋 및 캐싱

```python
# 레이트 리밋 전략
MAX_SEARCHES_PER_SEED = 3        # 시드 생성당 최대 검색 횟수
MAX_SEARCHES_PER_SIMULATION = 10  # 시뮬레이션당 최대 검색 횟수 (Phase 2)
SEARCH_CACHE_TTL = 3600          # 검색 결과 캐시 1시간

# ddgs는 API 키 불필요하지만 레이트 리밋 존재
# 과도한 요청 시 일시적 차단 가능
```

### 3.5 의존성 추가

```toml
# backend/pyproject.toml
[project]
dependencies = [
    "duckduckgo-search>=7.0.0",  # ddgs 패키지
]

# Phase 2 추가:
# "camel-ai[tools]"  # OASIS SearchToolkit
```

### 3.6 프론트엔드 웹 검색 토글

ScenarioForm에 웹 검색 관련 설정 추가:

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| web_search_enabled | toggle | false | 웹 검색 활성화 |
| search_keywords | text input | (자동 추출) | 커스텀 검색 키워드 (선택) |

### 3.7 수정 대상 파일

```
# Phase 1 (시드 보강)
backend/app/services/web_search.py              # 신규: WebSearchService
backend/app/services/seed_generator.py           # 웹 검색 결과 주입
backend/pyproject.toml                           # ddgs 의존성 추가
backend/app/models/scenario.py                   # SimulationParams에 web_search_enabled
frontend/src/components/simulation/ScenarioForm.tsx  # 웹 검색 토글

# Phase 2 (에이전트 도구)
external/mirofish-backend/app/services/simulation_runner.py  # tools 파라미터 전달
backend/app/clients/mirofish.py                               # start_simulation에 tools 플래그
```

## 4. 마일스톤

- [x] **M1: ddgs 패키지 의존성 추가 + WebSearchService 생성** — duckduckgo-search 패키지 설치. WebSearchService 클래스 구현 (search_news, search_web, format_for_seed). 인메모리 캐시 + 레이트 리밋.
  - 검증: WebSearchService.search_news(["South China Sea tension"]) → 뉴스 결과 반환

- [x] **M2: SeedGenerator에 웹 검색 결과 주입 (시드 보강)** — web_search_enabled=true일 때 시드 생성 시 DuckDuckGo 검색. 키워드 자동 추출 (지역명 + 시나리오 질문에서). 검색 결과를 시드 문서 "최근 뉴스" 섹션에 추가.
  - 검증: web_search_enabled=true로 시드 생성 → 시드 문서에 뉴스 섹션 포함

- [x] **M3: MiroFish simulation_runner에 tools 파라미터 전달 경로 추가** — MiroFish start_simulation API에 tools_enabled 플래그 추가. simulation_runner에서 SearchToolkit().search_duckduckgo를 SocialAgent tools에 주입. single_iteration=False 설정.
  - 검증: 시뮬레이션 에이전트가 실행 중 DuckDuckGo 검색을 수행하고 결과를 포스트에 반영

- [x] **M4: 프론트엔드 웹 검색 활성화 토글 + 검색 키워드 설정** — ScenarioForm에 web_search_enabled 토글 추가. 커스텀 검색 키워드 입력 필드 (선택적). 시드 미리보기에 검색 결과 포함 여부 표시.
  - 검증: 프론트엔드에서 웹 검색 활성화 → 시드에 뉴스 결과 포함

## 5. 성공 기준

- DuckDuckGo 웹 검색 결과가 시드 문서에 "최근 뉴스" 섹션으로 포함된다
- 검색 결과가 캐싱되어 동일 키워드 재검색 시 API 호출을 절약한다
- (Phase 2) 시뮬레이션 에이전트가 실행 중 DuckDuckGo 검색을 수행할 수 있다
- web_search_enabled=false일 때 기존 시드 생성이 변경 없이 동작한다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| DuckDuckGo 스크래핑 레이트 리밋 | 검색 결과 캐싱(1시간 TTL) + 시드당 최대 3회 검색 제한 |
| 뉴스 검색 결과가 시뮬레이션과 무관 | 키워드를 지역명 + 군사/지정학 용어로 구성. 결과 필터링 |
| Phase 2에서 에이전트 검색이 시뮬레이션 속도 저하 | 시뮬레이션당 최대 10회 검색 제한. 검색 타임아웃 5초 |
| ddgs 패키지 안정성 | ddgs는 활발히 유지보수되는 패키지. 검색 실패 시 graceful fallback |
| Phase 2의 MiroFish 코드 수정 필요 | Phase 1은 MiroFish 수정 없이 가능. Phase 2는 별도 일정 |

## 7. 참고

### 관련 PRD
- **seed-generation** — 현재 SeedGenerator 구현
- **v3-simulation-params (V3-3)** — SimulationParams에 web_search_enabled 추가
- **v3-oasis-runtime (V3-6)** — OASIS 에이전트 도구 주입 (Phase 2 관련)

### ddgs 패키지
- 패키지: `duckduckgo-search` (PyPI)
- API 키 불필요 — 무료 웹 스크래핑 기반
- 주요 메서드: `DDGS().news()`, `DDGS().text()`
- 레이트 리밋: 명시적 제한 없으나 과도한 요청 시 일시 차단 가능

### OASIS SearchToolkit
- 패키지: `camel-ai[tools]`
- `SearchToolkit().search_duckduckgo` — OASIS SocialAgent의 tools에 주입 가능
- `single_iteration=False` 필수 — 도구 호출을 위한 다중 반복 필요

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-21 | Draft | V3-4 DuckDuckGo 웹 검색 통합 PRD 초안 작성 |
| 2026-03-21 | M1-M2 완료 | duckduckgo-search 8.1.1 설치. WebSearchService (search_news, format_for_seed, extract_keywords, 캐시 1h TTL, 시드당 최대 3회). SeedGenerator에 web_search_enabled 파라미터 + "최근 뉴스" 섹션 주입. SimulationParams에 web_search_enabled 추가. 프론트엔드 토글 추가. M3-M4(OASIS 에이전트 도구)는 W4 예정. |
| 2026-03-21 | M3-M4 완료 | tools_enabled 전달 경로: MiroFishClient → MiroFish API → SimulationRunner → subprocess --tools-enabled 플래그. run_twitter_simulation.py에서 camel SearchToolkit().search_duckduckgo 주입 + single_iteration=False 설정. camel-ai[tools] 미설치 시 graceful fallback. 프론트엔드 web_search_enabled 토글은 M2에서 이미 완료. |
