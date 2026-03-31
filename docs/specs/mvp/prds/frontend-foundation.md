# PRD: Frontend Foundation + OSINT Map

> Status: Complete
> Created: 2026-03-20
> Dependencies: PRD 1 (gateway-api-foundation), PRD 2 (shadowbroker-integration)
> 관련 스펙: `specs/MVP-SPEC.md` Section 2, 7 프론트엔드

---

## 1. 문제 정의

OSINT Simulator는 ShadowBroker의 실시간 OSINT 데이터를 지도에 표시하고, 그 위에 시뮬레이션 결과를 오버레이하는 프론트엔드가 필요하다. ShadowBroker 프론트엔드(Next.js 16 + MapLibre GL 4.7)의 패턴을 참조하되, 소스 프로젝트를 수정하지 않고 별도 프론트엔드 프로젝트로 구축한다.

이 PRD는 프론트엔드 프로젝트 초기화와 기본 OSINT 지도 레이어 구현까지를 다룬다.

## 2. 솔루션 개요

- **독립 Next.js 앱** (port 3000) — SB 패턴 참조, Gateway API를 통해 데이터 조회
- **MapLibre GL 지도** — SB의 mapStyles, useImperativeSource 패턴 재사용
- **OSINT 데이터 레이어** — 선박 + 항공기 레이어 (Gateway OSINT 프록시 경유)
- **Gateway API 프록시 라우트** — Next.js API 라우트로 Gateway 요청 프록시

## 3. 기술 상세

### 3.1 ShadowBroker 프론트엔드 아키텍처 (참조용)

| 항목 | 값 |
|------|------|
| 프레임워크 | Next.js 16.1.6 (App Router) |
| UI | React 19.2.3 + Tailwind CSS 4 |
| 지도 | MapLibre GL 4.7.1 + react-map-gl 8.1.0 |
| 상태관리 | React Context (DashboardDataContext) |
| 데이터 폴링 | useDataPolling 훅 (fast 15s, slow 120s) |
| 소스 업데이트 | useImperativeSource 훅 (명령형, React 렌더링 우회) |
| 테마 | Dark/Light (CSS Variables + Carto basemaps) |

### 3.2 ShadowBroker 레이어 추가 패턴

SB 프론트엔드는 5단계 패턴으로 데이터 레이어를 추가한다:

```
1. GeoJSON 빌더 함수 (geoJSONBuilders.ts)
   → 데이터 배열을 GeoJSON FeatureCollection으로 변환

2. 타입 정의 (types/dashboard.ts)
   → 데이터 인터페이스 추가

3. DashboardData 인터페이스 확장
   → 새 필드 추가

4. 레이어 토글 (page.tsx의 activeLayers)
   → 레이어 on/off 상태 추가

5. Source + Layer 등록 (MaplibreViewer.tsx)
   → useImperativeSource + <Source> + <Layer> JSX
```

### 3.3 프론트엔드 프로젝트 구조

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # 메인 대시보드
│   │   └── api/[...path]/route.ts      # Gateway API 프록시
│   ├── components/
│   │   └── map/
│   │       ├── MaplibreViewer.tsx       # 지도 컴포넌트
│   │       └── geoJSONBuilders.ts      # GeoJSON 빌더
│   ├── hooks/
│   │   └── useDataPolling.ts           # 데이터 폴링 훅
│   ├── types/
│   │   └── dashboard.ts               # OSINT 데이터 타입
│   └── lib/
│       └── gatewayApi.ts              # Gateway API 클라이언트
├── package.json
├── next.config.ts
└── Dockerfile
```

### 3.4 프론트엔드 접근 방식

ShadowBroker 프론트엔드를 직접 수정하지 않고, **별도 프론트엔드 프로젝트**로 구축한다 (MVP-SPEC.md 설계 원칙 #1, AGENTS.md "소스 프로젝트는 절대 수정하지 않는다").

- SB의 MapLibre 설정, 스타일, 유틸리티를 참조하되 자체 앱으로 구축
- OSINT 데이터는 Gateway 프록시(`/api/osint/*`)를 통해 조회

### 3.5 Gateway API 클라이언트 (OSINT 부분)

```typescript
// lib/gatewayApi.ts
const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL || '';

export const gatewayApi = {
  // OSINT
  getOsintFast: (bbox?: { s: number; w: number; n: number; e: number }) =>
    fetch(`${GATEWAY_URL}/api/osint/live_data/fast${bboxToQuery(bbox)}`),

  getOsintSlow: (bbox?: { s: number; w: number; n: number; e: number }) =>
    fetch(`${GATEWAY_URL}/api/osint/live_data/slow${bboxToQuery(bbox)}`),
};
```

## 4. 마일스톤

- [x] **M1: 프론트엔드 프로젝트 셋업** — Next.js 16 + React 19 + Tailwind CSS + MapLibre GL + react-map-gl 프로젝트 초기화. SB의 mapStyles.ts, useImperativeSource 패턴 참조. Gateway API 프록시 라우트 설정.
  - 검증: `npm run dev` → MapLibre 지도 렌더링 + Gateway API 연결

- [x] **M2: 기본 OSINT 지도 레이어** — Gateway OSINT 프록시를 통해 SB 데이터 폴링. 선박 + 항공기 레이어 렌더링 (SB 패턴 동일). 레이어 토글 UI.
  - 검증: 지도에 실시간 선박/항공기 표시. SB와 동일한 시각적 결과

## 5. 성공 기준

- MapLibre 지도가 정상 렌더링된다
- Gateway OSINT 프록시를 통해 SB 실시간 데이터를 폴링한다
- 선박/항공기가 지도에 표시되고 레이어 토글이 동작한다
- SB 프론트엔드와 동일한 시각적 패턴을 따른다

## 6. 위험 및 완화

| 위험 | 완화 |
|------|------|
| SB 프론트엔드 패턴과의 불일치 | SB 코드를 직접 참조하여 동일 패턴 적용. react-map-gl + useImperativeSource 훅 재사용 |
| Gateway API CORS 문제 | Gateway에 CORS 설정 추가 (PRD 1). 프론트엔드 API 프록시 라우트 활용 |

## 7. 참고

### 관련 PRD
- **PRD 1 (gateway-api-foundation)** — Gateway API 엔드포인트
- **PRD 2 (shadowbroker-integration)** — OSINT 프록시 데이터
- **PRD 6b (scenario-management-ui)** — 이 프론트엔드 위에 시나리오 관리 UI 추가
- **PRD 6c (simulation-visualization)** — 이 프론트엔드 위에 시뮬레이션 시각화 추가

### ShadowBroker 프론트엔드 참조
- 지도 컴포넌트: `/home/swlee/Shadowbroker/frontend/src/components/MaplibreViewer.tsx`
- GeoJSON 빌더: `/home/swlee/Shadowbroker/frontend/src/components/map/geoJSONBuilders.ts`
- 명령형 소스: `/home/swlee/Shadowbroker/frontend/src/components/map/hooks/useImperativeSource.ts`
- 데이터 폴링: `/home/swlee/Shadowbroker/frontend/src/hooks/useDataPolling.ts`
- 타입 정의: `/home/swlee/Shadowbroker/frontend/src/types/dashboard.ts`
- 패키지: `/home/swlee/Shadowbroker/frontend/package.json`

> **주의**: ShadowBroker 프론트엔드 소스 코드를 직접 수정하지 않는다 (AGENTS.md). 패턴만 참조.

## 진행 로그

| 날짜 | 상태 | 내용 |
|------|------|------|
| 2026-03-20 | Draft | PRD 6 분할로 생성 |
