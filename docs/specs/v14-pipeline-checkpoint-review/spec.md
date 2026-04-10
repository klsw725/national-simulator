# v14 SPEC: 파이프라인 단계별 검토 복원

> Status: In Progress
> Created: 2026-04-10
> Dependencies: v13 (서브그래프 분리)

## 목표

LangGraph `interrupt_before`를 활용하여 셋업 단계(analyze → relations → actors → configure)에서 사용자가 중간 결과를 검토하고 다음 단계를 진행/중단할 수 있도록 한다.

## 아키텍처

```
모드: auto (기존)
  START → analyze → relations → actors → configure → simulation_loop → report → END

모드: checkpoint (신규)
  START → analyze → [PAUSE] → emit checkpoint_reached
                  사용자가 검토 후 /continue 호출
                → relations → [PAUSE] → emit checkpoint_reached
                  ...
                → simulation_loop → report → END
```

## 백엔드 변경

### M1: Graph builder에 checkpoint 모드 추가
- `get_graph(mode="auto"|"checkpoint")` 파라미터 추가
- `checkpoint` 모드일 때 `interrupt_before=["build_relations","create_actors","configure_sim","simulation_loop"]`
- 두 종류의 컴파일된 그래프 캐시

### M2: command_listener checkpoint 감지
- `_run`: 실행 후 `aget_state().next` 확인 → 중단 노드 있으면 `emit_checkpoint_reached`
- `_resume_simulation`: 동일 로직 재적용 (다음 checkpoint까지 실행)

### M3: event_emitter에 `emit_checkpoint_reached` 추가
```python
async def emit_checkpoint_reached(scenario_id, step, state_snapshot):
    await self._emit({
        "type": "checkpoint_reached",
        "scenario_id": scenario_id,
        "step": step,  # "build_relations" | "create_actors" | ...
        "state": state_snapshot,
    })
```

### M4: simulation_v2.py start endpoint에 mode 전달
- `start_v2` body에 `mode: "auto" | "checkpoint"` 추가
- sim_commands payload에 포함

## 프론트엔드 변경

### M5: useSimulation checkpoint 핸들러
- `es.addEventListener("checkpoint_reached", ...)` 추가
- `setCheckpointData({step, data: state})`
- `setPipelineStatus({status: "checkpoint:" + step, ...})`

### M6: ScenarioForm mode 선택 UI
- 이미 `mode: PipelineMode` 타입 존재, 폼에 라디오/토글 추가

### M7: CheckpointReview 컴포넌트 data 바인딩
- 기존 컴포넌트가 있음, v13 state snapshot 형식에 맞춰 표시 조정

## 마일스톤

- M1-M3: 백엔드 interrupt_before + checkpoint_reached 이벤트
- M4: start_v2 mode 파라미터
- M5-M7: 프론트엔드 통합

## 제약

- LangGraph `interrupt_before`는 static 설정이므로 그래프를 모드별로 분리 컴파일
- 체크포인트 노드명과 phase 이름 매핑: `build_relations` → `checkpoint:relations`
