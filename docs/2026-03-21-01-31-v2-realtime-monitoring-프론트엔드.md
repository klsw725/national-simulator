# v2 realtime monitoring 프론트엔드 구현

## 사용자 프롬프트
1. TASK: Implement the complete frontend for v2-realtime-monitoring in the osint-simulator Next.js app. This involves 6 new files + 3 file modifications.

2. EXPECTED OUTCOME: 
   - TypeScript types for all live data
   - API functions for all 6 live endpoints
   - useLiveSimulation hook with MiroFish-spec polling intervals
   - LiveActionFeed, LiveStats, GraphViewer (D3.js), IntermediateResults components
   - SimulationPanel integration showing live views during simulation
   - `npx tsc --noEmit` passes with zero errors

3. REQUIRED TOOLS: Read, Write, Edit, Bash (for tsc check), Glob

4. MUST DO:

### Step 1: Read existing files for patterns
Read these files first to understand existing patterns:
- `/home/swlee/osint-simulator/frontend/src/types/simulation.ts`
- `/home/swlee/osint-simulator/frontend/src/lib/gatewayApi.ts`
- `/home/swlee/osint-simulator/frontend/src/hooks/useSimulation.ts`
- `/home/swlee/osint-simulator/frontend/src/components/simulation/SimulationPanel.tsx`
- `/home/swlee/osint-simulator/frontend/src/components/simulation/SimulationTimeline.tsx` (for action display pattern)
- `/home/swlee/osint-simulator/frontend/src/components/simulation/PipelineProgress.tsx`

### Step 2: Add types to simulation.ts
### Step 3: Add API functions to gatewayApi.ts
### Step 4: Create useLiveSimulation.ts hook
### Step 5: Create LiveActionFeed.tsx
### Step 6: Create LiveStats.tsx
### Step 7: Create GraphViewer.tsx (D3.js force-directed)
### Step 8: Create IntermediateResults.tsx
### Step 9: Integrate into SimulationPanel.tsx
### Step 10: Install D3.js
### Step 11: Build verification

5. MUST NOT DO:
   - Do NOT use CSS modules or Tailwind classes — use inline styles only (matching existing pattern)
   - Do NOT use any UI library (no MUI, no shadcn, no chakra)
   - Do NOT modify existing component logic (PipelineProgress, SimulationTimeline, etc.) except SimulationPanel
   - Do NOT add emojis to files
   - Do NOT create overly complex components — keep GraphViewer under 200 lines
   - Do NOT suppress TypeScript errors with `as any` or `@ts-ignore`
   - Do NOT modify useSimulation.ts — IntermediateResults uses its own useLiveSimulation hook
   - Do NOT use `window` or `document` directly — use refs
   - Do NOT import from 'lucide-react' for new icons — use text/unicode symbols instead

## 변경 사항
- `frontend/src/types/simulation.ts`에 live stats/actions/graph/profiles/config 타입을 추가했다.
- `frontend/src/lib/gatewayApi.ts`에 live 엔드포인트 6개 함수(`getLiveStats`, `getLiveActions`, `getLiveGraphTask`, `getLiveGraphData`, `getLiveProfiles`, `getLiveConfig`)를 추가했다.
- `frontend/src/hooks/useLiveSimulation.ts`를 새로 만들고 상태별 폴링 주기를 적용했다.
  - `simulating:graph_build`: graph_task 2초, graph_data 10초
  - `simulating:prepare`: profiles 3초, config 2초
  - `simulating:running`: stats 2초, actions 3초(오프셋 누적)
- `frontend/src/components/simulation/LiveActionFeed.tsx`를 추가해 채팅형 액션 피드를 구현했다.
  - 최대 200개 표시
  - 신규 액션 시 자동 스크롤
  - 수동 스크롤 시 자동 스크롤 해제 및 "최신으로" 버튼 제공
- `frontend/src/components/simulation/LiveStats.tsx`를 추가해 라운드 진행률/총 액션 카드를 구현했다.
- `frontend/src/components/simulation/GraphViewer.tsx`를 추가해 D3 force-directed 그래프를 구현했다.
  - 노드/엣지 렌더링
  - 관계 라벨 표시
  - processing 상태 진행률 바 표시
- `frontend/src/components/simulation/IntermediateResults.tsx`를 추가해 파이프라인 상태별 중간 결과 뷰를 구성했다.
- `frontend/src/components/simulation/SimulationPanel.tsx`의 progress 탭 렌더링을 수정해 시뮬레이션 중 `PipelineProgress + IntermediateResults` 레이아웃을 표시하도록 통합했다.
- `frontend/package.json`, `frontend/package-lock.json`에 `d3`, `@types/d3` 의존성이 추가됐다.

## 검증
- `frontend`에서 `npx tsc --noEmit` 실행: 성공(오류 0)
- LSP diagnostics 도구는 `typescript-language-server` 미설치로 직접 실행 불가였고, 대안으로 프로젝트 타입체크 진단을 수행해 오류 없음 확인
