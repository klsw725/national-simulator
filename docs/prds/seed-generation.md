# PRD: Seed Generation

> Status: Draft
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 2 (shadowbroker-integration)
> 관련 스펙: `specs/MVP-SPEC.md` Section 3.1.1, 4 Phase 1

---

## 1. 문제 정의

ShadowBroker의 실시간 AIS 선박 데이터에서 군함을 식별하고, 이를 국가 행위자로 매핑한 뒤, GDELT 분쟁 컨텍스트와 결합하여 MiroFish가 이해하는 자연어 시드 문서를 생성해야 한다. 이 시드 문서가 전체 시뮬레이션 파이프라인의 입력이 된다.

핵심 과제:
- AIS 데이터에서 군함 식별 (shiptype 기반 + 정적 DB 매칭)
- 군함 → 국가 행위자 매핑 (flag 필드 + military_vessels.json)
- GDELT 이벤트로 지역 긴장도 컨텍스트 추출
- LLM으로 구조화된 자연어 시드 문서 생성

## 2. 솔루션 개요

- **Military Vessel Database** — 공개 군함 데이터를 정적 JSON으로 관리
- **Vessel Mapper** — 선박 데이터를 군함 DB와 매칭하여 국가별 전력 매핑
- **Seed Generator** — LLM을 사용하여 OSINT 데이터를 마크다운 시드 문서로 변환
- **시드 생성 API** — POST/GET `/api/scenario/{id}/seed`

## 3. 기술 상세

### 3.1 군함 데이터베이스 (military_vessels.json)

```json
[
  {
    "mmsi": "369970455",
    "imo": "9619767",
    "name": "USS GERALD R FORD",
    "hull_number": "CVN-78",
    "class": "Gerald R. Ford-class",
    "type": "carrier",
    "country": "US",
    "navy": "United States Navy",
    "status": "active"
  }
]
```

**군함 식별 전략** (우선순위):
1. MMSI/IMO 직접 매칭 (military_vessels.json)
2. AIS `shiptype` 코드 기반 필터링 (35=military, 55=law enforcement 등)
3. `flag` 필드 + 선명 패턴 매칭 (USS, PLAN, HMS 등)

### 3.2 Vessel Mapper 인터페이스

```python
# backend/app/services/vessel_mapper.py
class VesselMapper:
    def __init__(self, vessel_db_path: str):
        self.vessel_db = self._load_db(vessel_db_path)

    def identify_military_vessels(self, ships: list[dict]) -> list[MilitaryVessel]:
        """AIS 선박 목록에서 군함 식별"""

    def map_to_actors(self, vessels: list[MilitaryVessel]) -> dict[str, ActorForce]:
        """군함을 국가별 전력으로 그룹핑
        반환 예: {"US": {carriers: 1, destroyers: 2}, "CN": {destroyers: 3, frigates: 2}}
        """
```

### 3.3 GDELT 컨텍스트 추출

ShadowBroker의 `/api/live-data/slow` 응답에서 `gdelt` 필드를 추출한다.
GDELT 데이터는 GeoJSON FeatureCollection로 제공된다.

```python
def extract_gdelt_context(gdelt_geojson: dict, bbox: BBox) -> GdeltContext:
    """
    bbox 내의 GDELT 이벤트를 필터링하고 긴장도 컨텍스트 추출.
    - Goldstein Scale 평균 계산 (음수일수록 긴장)
    - 주요 행위자(actor1, actor2) 추출
    - 이벤트 코드별 분류 (외교, 군사, 경제 등)
    """
```

### 3.4 Seed Generator

```python
# backend/app/services/seed_generator.py
class SeedGenerator:
    def __init__(self, sb_client: ShadowBrokerClient, vessel_mapper: VesselMapper, llm_client):
        self.sb = sb_client
        self.mapper = vessel_mapper
        self.llm = llm_client

    async def generate(self, scenario: ScenarioConfig) -> SeedDocument:
        """
        1. SB에서 해당 해역의 선박 데이터 조회 (get_ships with bbox)
        2. 군함 식별 및 국가 매핑 (vessel_mapper)
        3. SB에서 GDELT 데이터 조회 (get_gdelt with bbox)
        4. LLM으로 시드 문서 생성
        """
```

### 3.5 LLM 시드 문서 생성 프롬프트

```python
SEED_GENERATION_PROMPT = """
당신은 지정학적 분석가입니다. 아래 OSINT 데이터를 기반으로
시뮬레이션 시드 문서를 마크다운으로 작성해 주세요.

## 군함 배치 현황
{vessel_deployment}

## GDELT 분쟁 이벤트 (최근 48시간)
{gdelt_context}

## 시뮬레이션 질문
{user_question}

다음 형식으로 작성하세요:
1. 현재 상황 요약 (200자 이내)
2. 주요 행위자와 그 입장
3. 긴장 요인 및 잠재적 충돌 시나리오
4. 각 행위자의 예상 반응 경로

시드 문서는 약 2000자 이내로 작성하세요.
"""
```

> **LLM 호출 주의**: OpenAI Compatible API 사용 (AGENTS.md). 특정 프로바이더 고유 기능 사용 금지.

### 3.6 시드 문서 출력 형식

MiroFish의 `ontology_generator.py`는 시드 문서를 **파일(MD/TXT)** 로 받는다.
시드 문서는 마크다운 텍스트로, MiroFish에 multipart/form-data로 전달된다.

```markdown
## 현재 상황 요약
남중국해 서사군도 인근에서 미국 항공모함 전단과
중국 해군 구축함 편대가 근접 기동 중이다.

## 주요 행위자
### 미국 (US)
- 항공모함 USS Gerald Ford (CVN-78) 포함 항모전단
- 구축함 2척 (Arleigh Burke급)
...

## 긴장 요인
- GDELT Goldstein Scale: -5.2 (높은 긴장)
- 최근 48시간 내 외교적 갈등 이벤트 8건
...
```

## 4. 마일스톤

- [ ] **M1: 군함 데이터베이스 구축** — `military_vessels.json` 생성. 주요 해군 강대국(US, CN, RU, JP, KR, UK, FR, IN, AU) 주력 함정 데이터 수집. MMSI/IMO, 함급, 함종, 소속국 포함.
  - 검증: JSON 파일이 유효하고 최소 50척 이상의 군함 데이터 포함

- [ ] **M2: Vessel Mapper 서비스 구현** — AIS 선박 데이터에서 군함 식별 (3단계 전략). 국가별 전력 그룹핑. 선박 데이터에 `country`, `vessel_type` 등 부가 정보 추가.
  - 검증: 테스트용 AIS 데이터 입력 → 군함 식별 및 국가 매핑 정확

- [ ] **M3: GDELT 컨텍스트 추출기 구현** — SB slow 데이터에서 GDELT GeoJSON 파싱. bbox 내 이벤트 필터링. Goldstein Scale 기반 긴장도 점수 계산. 주요 행위자 쌍 추출.
  - 검증: 실제 GDELT 데이터에서 bbox 필터링 및 긴장도 계산 동작

- [ ] **M4: LLM 기반 시드 문서 생성기 구현** — OpenAI Compatible API 호출. 군함 배치 + GDELT 컨텍스트 + 사용자 질문을 프롬프트에 조합. 마크다운 시드 문서 출력.
  - 검증: 테스트 데이터 입력 → 구조화된 마크다운 시드 문서 생성 (약 2000자)

- [ ] **M5: 시드 생성 API 통합** — POST `/api/scenario/{id}/seed` → 시드 생성 트리거. GET `/api/scenario/{id}/seed` → 생성된 시드 조회. 시드 메타데이터 (군함 수, 행위자, 긴장도 등) 포함.
  - 검증: 시나리오 생성 → 시드 생성 → 시드 조회 플로우 동작

- [ ] **M6: E2E 검증** — ShadowBroker 실행 상태에서 실제 AIS 데이터로 시드 문서 자동 생성. 생성된 시드 문서가 MiroFish에 전달 가능한 형식인지 확인.
  - 검증: 실제 SB 데이터 → 시드 문서 → MiroFish ontology/generate에 전달 시 정상 처리

## 5. 성공 기준

- 실제 AIS 데이터에서 군함을 식별하고 국가 행위자로 매핑할 수 있다
- GDELT 데이터에서 관심 해역의 긴장도 컨텍스트를 추출할 수 있다
- LLM이 구조화된 마크다운 시드 문서를 생성한다
- 생성된 시드 문서가 MiroFish의 ontology/generate 엔드포인트에서 정상 처리된다
- 전체 시드 생성 프로세스가 API 호출 하나로 트리거된다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| AIS 데이터에 군함이 부족 (군함은 AIS를 끌 수 있음) | Carrier Tracker 데이터 병행 사용. 테스트용 시드 문서 수동 작성 옵션 제공 |
| military_vessels.json 데이터 부정확/불완전 | 공개 데이터 소스 복수 교차 검증. 미식별 군함은 flag + shiptype으로 최선 추정 |
| LLM이 부적절한 시드 문서 생성 | 프롬프트 정교화. 출력 길이 제한. 필수 섹션 존재 여부 검증 |
| LLM API 비용 | 시드 문서 캐싱 (동일 시나리오 재요청 시 기존 시드 반환) |

## 7. 참고

### 관련 PRD
- **PRD 2 (shadowbroker-integration)** — SB 클라이언트 제공
- **PRD 4 (simulation-orchestration)** — 시드 문서를 MiroFish에 전달

### MiroFish 시드 입력 형식
MiroFish `/api/graph/ontology/generate`는 `multipart/form-data`로 파일을 받는다:
- `files`: MD/TXT 파일 (시드 문서)
- `simulation_requirement`: 시뮬레이션 요구사항 텍스트
- `project_name`: 프로젝트 이름 (optional)

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 초안 작성 |
