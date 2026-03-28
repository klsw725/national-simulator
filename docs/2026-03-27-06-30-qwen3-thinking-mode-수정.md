# Qwen3 thinking mode로 인한 빈 시드 텍스트 수정

## 프롬프트

```
Prepare failed: 조건에 맞는 엔티티를 찾을 수 없습니다. 그래프가 올바르게 구축되었는지 확인하십시오.
왜 이게 나올까? 기존에는 나왔었거든 모델 문제일까?
```

## 원인 분석

### 증상
- 시드 생성 `seed_status='completed'` 이지만 `text_len=0`
- MiroFish 그래프 빌드에 빈 텍스트 전달 → 0 Entity 노드 → prepare 실패

### 근본 원인
Gateway LLM 모델 `qwen/qwen3.5-27b`가 thinking mode로 동작:
- `message.content` = `null`
- `message.reasoning` = `"Thinking Process: ..."` (실제 내용이 여기에)

`_call_llm`의 `response.choices[0].message.content or ""` → `None or ""` → 빈 문자열 반환.

### 영향 범위
동일 LLM을 사용하는 모든 서비스:
- `seed_generator.py` — 시드 텍스트 생성
- `copilot.py` — 코파일럿 대화
- `briefing_generator.py` — 브리핑 생성

## 변경 사항

3개 파일의 `chat.completions.create()` 호출에 thinking mode 비활성화 파라미터 추가:
```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}
```

### 수정 파일 — Gateway (backend)
1. `backend/app/services/seed_generator.py` — `_call_llm` (1곳)
2. `backend/app/services/copilot.py` — LLM 호출 (2곳: tool-calling + fallback)
3. `backend/app/services/briefing_generator.py` — `_call_llm` (1곳)

### 수정 파일 — MiroFish (external/mirofish-backend)
4. `app/utils/llm_client.py` — `LLMClient.chat()` 중앙 게이트웨이 (모든 `.chat()`, `.chat_json()` 호출 커버). `content or ""` fallback도 추가.
5. `app/services/oasis_profile_generator.py` — 직접 `create()` 호출 (1곳)
6. `app/services/simulation_config_generator.py` — 직접 `create()` 호출 (1곳)

### 수정 파일 — OASIS 시뮬레이션 스크립트 (monkey-patch)
MiroFish LLM 서버(`10.0.40.227/litellm`)는 `chat_template_kwargs`를 무시하므로, OASIS/CAMEL이 사용하는 OpenAI SDK의 `ChatCompletionMessage.__init__`을 monkey-patch하여 `content`가 null일 때 `reasoning_content`로 fallback.
7. `scripts/run_reddit_simulation.py` — `_patch_openai_thinking_mode()` 추가
8. `scripts/run_twitter_simulation.py` — 동일
9. `scripts/run_parallel_simulation.py` — 동일
