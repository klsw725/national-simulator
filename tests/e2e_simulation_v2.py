"""E2E 통합 테스트: v12 Simulation Service 전체 파이프라인 검증.

실행 전제: docker-compose up (gateway + simulation-service + postgres + shadowbroker)

사용법:
    uv run python tests/e2e_simulation_v2.py
    uv run python tests/e2e_simulation_v2.py --gateway http://localhost:4000
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx

GATEWAY = "http://localhost:4000"
SCENARIO_ID = "e2e_test_v12"
MAX_WAIT = 120
SSE_COLLECT_TIMEOUT = 90


class TestResult:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []

    def ok(self, name: str) -> None:
        self.passed.append(name)
        print(f"  ✅ {name}")

    def fail(self, name: str, reason: str) -> None:
        self.failed.append(f"{name}: {reason}")
        print(f"  ❌ {name} — {reason}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*50}")
        print(f"결과: {len(self.passed)}/{total} 통과")
        if self.failed:
            print("실패 항목:")
            for f in self.failed:
                print(f"  - {f}")
        return 0 if not self.failed else 1


async def test_health(client: httpx.AsyncClient, result: TestResult) -> bool:
    print("\n[1] 헬스 체크")
    try:
        resp = await client.get(f"{GATEWAY}/api/health")
        data = resp.json()
        if data.get("status") == "ok":
            result.ok("Gateway health")
        else:
            result.fail("Gateway health", f"status={data.get('status')}")
            return False
    except Exception as e:
        result.fail("Gateway health", str(e))
        return False

    try:
        resp = await client.get(f"{GATEWAY}/api/health/detailed")
        data = resp.json()
        db_status = data.get("services", {}).get("database", {}).get("status")
        if db_status == "healthy":
            result.ok("Database health")
        else:
            result.fail("Database health", f"status={db_status}")
            return False
    except Exception as e:
        result.fail("Database health", str(e))
        return False

    return True


async def test_create_scenario(client: httpx.AsyncClient, result: TestResult) -> bool:
    print("\n[2] 시나리오 생성")
    try:
        resp = await client.post(
            f"{GATEWAY}/api/scenarios",
            json={
                "name": "E2E Test v12",
                "region": {"bbox": [120, 0, 140, 30], "name": "South China Sea"},
                "question": "남중국해 긴장 시나리오 테스트",
                "max_rounds": 3,
                "data_sources": ["ships", "flights"],
            },
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            result.ok(f"Scenario created: {data.get('id', '?')}")
            return True
        result.fail("Scenario create", f"HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        result.fail("Scenario create", str(e))
        return False


async def test_start_v2(client: httpx.AsyncClient, result: TestResult) -> bool:
    print("\n[3] Simulation v2 시작")
    try:
        resp = await client.post(
            f"{GATEWAY}/api/scenario/{SCENARIO_ID}/start_v2",
            json={
                "seed_text": "남중국해에서 중국 해군 함정 3척이 스프래틀리 군도 인근으로 이동 중. 미국 7함대 구축함이 대만 해협을 통과.",
                "max_rounds": 3,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "started":
                result.ok("start_v2 accepted")
                return True
            result.fail("start_v2", f"unexpected response: {data}")
            return False
        result.fail("start_v2", f"HTTP {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        result.fail("start_v2", str(e))
        return False


async def test_sse_stream(result: TestResult) -> dict:
    print(f"\n[4] SSE 스트림 수신 (최대 {SSE_COLLECT_TIMEOUT}초)")
    collected: dict[str, list] = {
        "phase_change": [],
        "round_complete": [],
        "agent_action": [],
        "intervention_required": [],
        "report_ready": [],
        "error": [],
        "keepalive": [],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(SSE_COLLECT_TIMEOUT + 10)) as client:
            async with client.stream("GET", f"{GATEWAY}/api/scenario/{SCENARIO_ID}/stream") as resp:
                result.ok("SSE connection opened")
                deadline = time.monotonic() + SSE_COLLECT_TIMEOUT
                buffer = ""

                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        block, buffer = buffer.split("\n\n", 1)
                        lines = block.strip().split("\n")

                        event_type = "message"
                        data_str = ""
                        for line in lines:
                            if line.startswith("event: "):
                                event_type = line[7:].strip()
                            elif line.startswith("data: "):
                                data_str = line[6:]
                            elif line.startswith(": "):
                                event_type = "keepalive"

                        if event_type == "keepalive":
                            collected["keepalive"].append(True)
                            continue

                        if data_str:
                            try:
                                data = json.loads(data_str)
                                collected.setdefault(event_type, []).append(data)
                                print(f"    📡 {event_type}: {json.dumps(data, ensure_ascii=False)[:120]}")
                            except json.JSONDecodeError:
                                pass

                        if collected["report_ready"] or collected["error"]:
                            break

                    if time.monotonic() > deadline:
                        break
                    if collected["report_ready"] or collected["error"]:
                        break

    except httpx.ReadTimeout:
        pass
    except Exception as e:
        result.fail("SSE stream", str(e))
        return collected

    if collected["phase_change"]:
        result.ok(f"phase_change 이벤트 {len(collected['phase_change'])}건 수신")
    else:
        result.fail("phase_change", "이벤트 수신 없음")

    if collected["agent_action"]:
        result.ok(f"agent_action 이벤트 {len(collected['agent_action'])}건 수신")
    else:
        result.fail("agent_action", "이벤트 수신 없음 — LLM 호출 실패 가능")

    if collected["report_ready"]:
        result.ok("report_ready 수신 — 시뮬레이션 완료")
    elif collected["error"]:
        result.fail("simulation", f"에러: {collected['error'][0]}")
    else:
        result.fail("report_ready", "타임아웃 — 시뮬레이션 미완료")

    return collected


async def test_decide_v2(client: httpx.AsyncClient, result: TestResult, collected: dict) -> None:
    print("\n[5] Decision v2 테스트")
    if not collected.get("intervention_required"):
        result.ok("intervention 미발생 — decide_v2 스킵 (정상)")
        return

    dp = collected["intervention_required"][0].get("decision_point", {})
    options = dp.get("options", [])
    if not options:
        result.fail("decide_v2", "decision_point에 옵션 없음")
        return

    try:
        resp = await client.post(
            f"{GATEWAY}/api/scenario/{SCENARIO_ID}/decide_v2",
            json={
                "decision_point_id": dp.get("id", ""),
                "chosen_action": options[0],
            },
        )
        if resp.status_code == 200:
            result.ok("decide_v2 accepted")
        else:
            result.fail("decide_v2", f"HTTP {resp.status_code}")
    except Exception as e:
        result.fail("decide_v2", str(e))


async def main(gateway: str) -> int:
    global GATEWAY
    GATEWAY = gateway

    print(f"v12 E2E 통합 테스트")
    print(f"Gateway: {GATEWAY}")
    print(f"Scenario: {SCENARIO_ID}")
    print("=" * 50)

    result = TestResult()

    async with httpx.AsyncClient(timeout=30.0) as client:
        if not await test_health(client, result):
            return result.summary()

        await test_create_scenario(client, result)
        if not await test_start_v2(client, result):
            return result.summary()

    collected = await test_sse_stream(result)

    async with httpx.AsyncClient(timeout=30.0) as client:
        await test_decide_v2(client, result, collected)

    return result.summary()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="v12 E2E Integration Test")
    parser.add_argument("--gateway", default="http://localhost:4000")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.gateway)))
