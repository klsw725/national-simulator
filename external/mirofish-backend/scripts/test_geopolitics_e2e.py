"""GeopoliticsPlatform E2E 테스트.

3개 국가 행위자, 3라운드 지정학 시뮬레이션.
GeopoliticsPlatform의 OASIS Platform 호환성을 검증한다.

실행: python scripts/test_geopolitics_e2e.py
"""

import asyncio
import json
import os
import sys

_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_backend_dir = os.path.abspath(os.path.join(_scripts_dir, ".."))
sys.path.insert(0, _backend_dir)

from app.platforms.geopolitics_platform import GeopoliticsPlatform, _HAS_OASIS


async def main():
    print("=" * 60)
    print("GeopoliticsPlatform E2E 테스트")
    print(f"OASIS 설치 여부: {_HAS_OASIS}")
    print("=" * 60)

    events_log: list[dict] = []

    def collect_event(event: dict):
        events_log.append(event)

    platform = GeopoliticsPlatform(event_callback=collect_event)

    actors = ["US", "CN", "PH"]
    action_sequences = [
        ("US", "diplomatic_statement", "Freedom of navigation must be maintained"),
        ("CN", "military_movement", "Naval patrol in disputed waters"),
        ("PH", "diplomatic_engagement", "Requesting allied support"),
        ("US", "military_exercise", "Joint naval exercise with allies"),
        ("CN", "trade_restriction", "Limiting imports from opposing nations"),
        ("PH", "alliance_support", "Supporting US position on maritime law"),
        ("US", "treaty_sign", "Strengthening mutual defense treaty"),
        ("CN", "diplomatic_statement", "Asserting sovereignty over island chains"),
        ("PH", "strategic_observation", "Monitoring situation closely"),
    ]

    print(f"\n행위자: {actors}")
    print(f"액션 수: {len(action_sequences)}")
    print(f"라운드: 3")

    for round_num in range(1, 4):
        platform.set_round(round_num)
        print(f"\n--- 라운드 {round_num} ---")

        round_actions = action_sequences[(round_num - 1) * 3: round_num * 3]
        for actor_id, action_type, content in round_actions:
            handler = getattr(platform, action_type)
            result = await handler(
                actor_id=actor_id,
                content=content,
                target_actor_ids=[a for a in actors if a != actor_id],
                magnitude=0.5,
            )
            print(f"  {actor_id} → {action_type}: {content[:40]}...")

    all_events = platform.get_events()
    print(f"\n{'=' * 60}")
    print(f"결과:")
    print(f"  총 이벤트: {len(all_events)}")
    print(f"  콜백 이벤트: {len(events_log)}")
    print(f"  OASIS Platform 상속: {_HAS_OASIS}")

    assert len(all_events) == 9, f"Expected 9 events, got {len(all_events)}"
    assert len(events_log) == 9, f"Expected 9 callback events, got {len(events_log)}"

    for event in all_events:
        assert "action_type" in event
        assert "actor_id" in event
        assert "round" in event
        assert "timestamp" in event

    action_types_seen = {e["action_type"] for e in all_events}
    expected_types = {
        "diplomatic_statement", "military_movement", "diplomatic_engagement",
        "military_exercise", "trade_restriction", "alliance_support",
        "treaty_sign", "strategic_observation",
    }
    assert action_types_seen == expected_types, f"Missing: {expected_types - action_types_seen}"

    rounds_seen = {e["round"] for e in all_events}
    assert rounds_seen == {1, 2, 3}, f"Expected rounds {{1,2,3}}, got {rounds_seen}"

    print(f"\n  모든 검증 통과!")
    print(f"{'=' * 60}")

    if _HAS_OASIS:
        print("\nOASIS Platform 호환성: VERIFIED")
    else:
        print("\nOASIS 미설치 — 독립 모드로 테스트됨 (Docker 환경에서 재검증 필요)")


if __name__ == "__main__":
    asyncio.run(main())
