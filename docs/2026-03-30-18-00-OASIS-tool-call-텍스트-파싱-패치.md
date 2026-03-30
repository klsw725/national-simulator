# OASIS tool_call 텍스트 파싱 패치

> 날짜: 2026-03-30
> 관련: 2026-03-30-17-00-시뮬레이션-침묵-OASIS-프롬프트-수정.md

## 프롬프트

시뮬레이션 침묵 근본 원인 추적. LLM 모델(gpt-oss-120b, Qwen3.5-122b)이 OpenAI 표준 tool_calls를 반환하지 않아 OASIS 에이전트가 아무 행동도 실행하지 못하는 문제.

## 진단

### LLM 모델별 tool calling 응답 형식

| 모델 | tool_calls 필드 | 실제 응답 |
|------|----------------|----------|
| gpt-oss-120b | NONE | `{"content": "hello"}` (JSON 텍스트) |
| Qwen3-VL-8B | 400 Bad Request | tools 파라미터 자체를 거부 |
| Qwen3.5-122b | NONE | `<tool_call><function=create_post><parameter=content>...</parameter></function></tool_call>` |

### OASIS의 기대 vs 현실

```python
# OASIS agent.py의 perform_action_by_llm():
response = await self.astep(user_msg)
for tool_call in response.info['tool_calls']:  # ← 항상 빈 리스트
    action_name = tool_call.tool_name           # ← 실행 안 됨
```

## 수정

### 변경 파일: `external/mirofish-backend/scripts/run_twitter_simulation.py`

`_patch_tool_call_text_fallback()` 함수 추가:
- `SocialAgent.perform_action_by_llm`을 monkey-patch
- 기존 tool_calls가 있으면 기존 동작 유지
- tool_calls가 비어있으면 텍스트 응답에서 파싱:
  1. Qwen XML 형식: `<tool_call><function=name><parameter=key>value</parameter></function></tool_call>`
  2. JSON 형식: `{"action": "create_post", "content": "..."}`
  3. JSON에 action 없이 content만 있으면 create_post로 추론
- 파싱된 action을 `self.env.action.{action_name}(**args)`로 직접 실행

### 지원하는 파싱 형식
- Qwen3.5 XML: `<tool_call><function=create_post><parameter=content>text</parameter></function></tool_call>`
- gpt-oss JSON: `{"content": "text"}` → `create_post(content="text")`로 변환
- Mixed JSON: `{"action": "quote_post", "content": "text", "post_id": 3}`

### 적용 방법
MiroFish Docker 컨테이너 재빌드:
```bash
docker-compose build mirofish && docker-compose up -d mirofish
```
