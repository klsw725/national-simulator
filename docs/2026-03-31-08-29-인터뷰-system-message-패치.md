# 인터뷰 API system message 순서 패치

## 프롬프트

> ValueError: System message must be at the beginning. LLM에서 이런 에러가 간혹 뜨던데 너 뭐 잘못 보내고 있너ㅓ? → 패치해

## 문제

MiroFish 리포트 생성 시 `batch_interview` 호출에서 LLM API 400 에러 발생:
```
Error code: 400 - {'error': {'message': 'System message must be at the beginning.'}}
```

## 원인

OASIS 라이브러리 `SocialAgent.perform_interview()`가 `memory.get_context()`에서 반환된 대화 기록을 그대로 openai_messages 배열 중간에 삽입. memory에 `role: "system"` 메시지가 포함되어 있으면 배열 중간에 system 메시지가 위치하게 됨. vLLM/OpenRouter 등 엄격한 프로바이더에서 이를 거부.

```
[{role: "system", content: "에이전트 성격"}, ← 첫 번째 OK
 {role: "user", ...},
 {role: "system", content: "You are a twitter user."}, ← memory에서 온 system 메시지 ❌
 {role: "user", content: "인터뷰 질문"}]
```

## 수정

3개 MiroFish 시뮬레이션 스크립트에 `_patch_interview_system_message()` 몽키패치 추가:
- `external/mirofish-backend/scripts/run_parallel_simulation.py`
- `external/mirofish-backend/scripts/run_twitter_simulation.py`
- `external/mirofish-backend/scripts/run_reddit_simulation.py`

패치 방식: `perform_interview` 호출 시 `_aget_model_response`를 임시 래핑하여 openai_messages 배열의 첫 번째 이후 위치에 있는 `role: "system"` 메시지를 필터링. 기존 `_patch_tool_call_text_fallback()` 몽키패치 패턴과 동일.

## 검증

MiroFish 리빌드 후 프로세스 정상 기동 확인 (`/health` OK).

추가 수정:
- 최초 패치에서 `run_twitter_simulation.py`에 `SocialAgent` import가 누락되어 프로세스가 즉시 종료됨
- `from oasis.social_agent.agent import SocialAgent` 추가 후 재빌드 완료
