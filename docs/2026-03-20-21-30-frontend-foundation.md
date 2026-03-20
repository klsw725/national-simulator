# PRD 6a: Frontend Foundation + OSINT Map 구현

> 날짜: 2026-03-20
> 프롬프트: `prd-next` → PRD 6a (frontend-foundation) 선택 → 구현

## 변경 사항

### 신규 프로젝트: `frontend/`

Next.js 16 + React 19 + MapLibre GL 4.7 + Tailwind CSS 4 프론트엔드 프로젝트.

| 카테고리 | 파일 |
|----------|------|
| 설정 | `package.json`, `next.config.ts`, `tsconfig.json`, `postcss.config.mjs` |
| App Shell | `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css` |
| API 프록시 | `src/app/api/[...path]/route.ts` → Gateway :4000 포워딩 |
| 지도 | `src/components/map/MaplibreViewer.tsx` (Carto dark, 클러스터 + 선박 아이콘) |
| 지도 유틸 | `src/components/map/styles/mapStyles.ts`, `src/components/map/geoJSONBuilders.ts` |
| 훅 | `src/hooks/useDataPolling.ts` (15s/120s, ETag), `src/hooks/useImperativeSource.ts` |
| 인프라 | `src/lib/ThemeContext.tsx`, `src/types/dashboard.ts` |

## 아키텍처 패턴 (ShadowBroker 참조)

- **useImperativeSource**: React 렌더링 우회하여 MapLibre 소스 직접 업데이트
- **useDataPolling**: ETag 캐싱 + 적응형 폴링 (fast 15s, slow 120s)
- **geoJSONBuilders**: 순수 함수 — ship 배열→GeoJSON FeatureCollection
- **Carto Dark basemap**: 래스터 타일, CSS variable 기반 다크 테마

## 검증

- ✅ `npm install` — 112 패키지 설치 성공
- ✅ `npm run build` — TypeScript 에러 0, 빌드 성공
- ✅ 15개 파일 생성 완료
