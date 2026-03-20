"""시뮬레이션 결과를 GeoJSON으로 변환하는 프로젝터.

MiroFish 시뮬레이션 액션 로그를 분석하여:
- 국가 행위자별 Point 피처 (위치, 긴장도, 입장, 핵심 발언)
- 행위자 간 관계 LineString 피처 (동맹, 적대, 외교)
를 GeoJSON FeatureCollection으로 생성한다.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 입장별 색상
STANCE_COLORS = {
    "supportive": "#22c55e",
    "opposing": "#ef4444",
    "neutral": "#6b7280",
    "cautious_ally": "#f59e0b",
}

# 관계별 색상
RELATIONSHIP_COLORS = {
    "alliance": "#22c55e",
    "support": "#3b82f6",
    "hostile": "#ef4444",
    "diplomatic": "#f59e0b",
}

# 지지 행동 vs 적대 행동
SUPPORT_ACTIONS = {"REPOST", "RETWEET", "LIKE", "LIKE_POST", "FOLLOW"}
OPPOSE_ACTIONS = {"QUOTE_POST", "REPLY"}


class ResultProjector:
    def __init__(self, actor_locations_path: str | Path | None = None):
        if actor_locations_path is None:
            actor_locations_path = (
                Path(__file__).parent.parent / "data" / "actor_locations.json"
            )
        self._locations = self._load_locations(Path(actor_locations_path))

    @staticmethod
    def _load_locations(path: Path) -> dict[str, dict]:
        if not path.exists():
            logger.warning("Actor locations not found: %s", path)
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def project_to_geojson(
        self,
        simulation_results: dict[str, Any],
        fallback_center: tuple[float, float] | None = None,
    ) -> dict[str, Any]:
        """시뮬레이션 결과를 GeoJSON FeatureCollection으로 변환.

        Args:
            simulation_results: MiroFish actions 데이터 ({"actions": [...]})
            fallback_center: 매칭 실패 시 사용할 좌표 (lng, lat)

        Returns:
            GeoJSON FeatureCollection (Point + LineString)
        """
        actions = simulation_results.get("actions", [])
        if not actions:
            return {"type": "FeatureCollection", "features": []}

        # 1. 에이전트별 액션 집계
        agent_data = self._aggregate_by_agent(actions)

        # 2. Point 피처 생성 (행위자)
        features: list[dict] = []
        for agent_name, data in agent_data.items():
            coords = self._get_coordinates(agent_name, fallback_center)
            if not coords:
                continue

            tension = self._calculate_tension(data)
            stance = self._classify_stance(data)
            key_stmt = self._extract_key_statement(data)

            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [coords["lng"], coords["lat"]],
                },
                "properties": {
                    "feature_type": "actor",
                    "actor": agent_name,
                    "tension_level": tension,
                    "stance": stance,
                    "key_statement": key_stmt,
                    "post_count": data["post_count"],
                    "total_actions": data["total_actions"],
                    "sentiment_avg": data["sentiment_avg"],
                    "color": STANCE_COLORS.get(stance, "#6b7280"),
                },
            })

        # 3. LineString 피처 생성 (관계)
        relationship_lines = self._build_relationship_lines(actions, fallback_center)
        features.extend(relationship_lines)

        return {"type": "FeatureCollection", "features": features}

    def _aggregate_by_agent(
        self, actions: list[dict]
    ) -> dict[str, dict[str, Any]]:
        """에이전트별 액션 집계."""
        agents: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "posts": [],
                "post_count": 0,
                "total_actions": 0,
                "action_types": defaultdict(int),
                "sentiment_sum": 0.0,
                "sentiment_count": 0,
                "sentiment_avg": 0.0,
                "targets": defaultdict(int),
            }
        )

        for action in actions:
            name = action.get("agent_name", "")
            if not name:
                continue

            data = agents[name]
            data["total_actions"] += 1
            action_type = action.get("action_type", "")
            data["action_types"][action_type] += 1

            # 포스트 내용 수집
            args = action.get("action_args", {}) or {}
            content = args.get("content", "")
            if content and action_type in ("CREATE_POST", "QUOTE_POST", "REPLY"):
                data["posts"].append(content)
                data["post_count"] += 1

            # 상호작용 대상 추적
            target_name = args.get("target_agent_name", "")
            if target_name:
                data["targets"][target_name] += 1

        # sentiment_avg 계산 (포스트 기반 간단 추정)
        for data in agents.values():
            if data["post_count"] > 0:
                # 포스트 길이와 액션 유형으로 간단 추정
                oppose_ratio = sum(
                    data["action_types"].get(a, 0) for a in OPPOSE_ACTIONS
                ) / max(data["total_actions"], 1)
                data["sentiment_avg"] = round(-oppose_ratio + 0.5, 2)

        return dict(agents)

    def _get_coordinates(
        self,
        agent_name: str,
        fallback: tuple[float, float] | None,
    ) -> dict[str, float] | None:
        """에이전트 이름으로 좌표를 찾는다."""
        loc = self._locations.get(agent_name)
        if loc:
            return loc

        # 부분 매칭 시도
        name_lower = agent_name.lower()
        for key, val in self._locations.items():
            if key.lower() in name_lower or name_lower in key.lower():
                return val

        if fallback:
            logger.warning("No coordinates for '%s', using fallback", agent_name)
            return {"lng": fallback[0], "lat": fallback[1]}

        logger.warning("No coordinates for '%s', skipping", agent_name)
        return None

    @staticmethod
    def _calculate_tension(data: dict[str, Any]) -> float:
        """긴장 수준 계산 (0.0~1.0).

        높은 QUOTE_POST/REPLY 비율 = 높은 긴장.
        """
        total = max(data["total_actions"], 1)
        oppose_count = sum(
            data["action_types"].get(a, 0) for a in OPPOSE_ACTIONS
        )
        support_count = sum(
            data["action_types"].get(a, 0) for a in SUPPORT_ACTIONS
        )
        post_count = data["action_types"].get("CREATE_POST", 0)

        # 적대 행동 비율 + 활동량 보정
        oppose_ratio = oppose_count / total
        activity_factor = min(1.0, total / 20.0)

        tension = (oppose_ratio * 0.6 + activity_factor * 0.4)
        return round(min(1.0, max(0.0, tension)), 2)

    @staticmethod
    def _classify_stance(data: dict[str, Any]) -> str:
        """입장 분류."""
        total = max(data["total_actions"], 1)
        support = sum(data["action_types"].get(a, 0) for a in SUPPORT_ACTIONS)
        oppose = sum(data["action_types"].get(a, 0) for a in OPPOSE_ACTIONS)
        nothing = data["action_types"].get("DO_NOTHING", 0)

        support_ratio = support / total
        oppose_ratio = oppose / total
        nothing_ratio = nothing / total

        if nothing_ratio > 0.5:
            return "neutral"
        if oppose_ratio > support_ratio and oppose_ratio > 0.3:
            return "opposing"
        if support_ratio > oppose_ratio and support_ratio > 0.3:
            if data["post_count"] < 3:
                return "cautious_ally"
            return "supportive"
        return "neutral"

    @staticmethod
    def _extract_key_statement(data: dict[str, Any]) -> str:
        """가장 긴 포스트를 핵심 발언으로 추출 (간단한 휴리스틱)."""
        posts = data.get("posts", [])
        if not posts:
            return ""
        # 가장 긴 포스트 = 가장 상세한 발언
        return max(posts, key=len)[:200]

    def _build_relationship_lines(
        self,
        actions: list[dict],
        fallback: tuple[float, float] | None,
    ) -> list[dict]:
        """에이전트 간 상호작용에서 관계 라인을 생성."""
        # 에이전트 쌍별 상호작용 집계
        interactions: dict[tuple[str, str], dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        for action in actions:
            src = action.get("agent_name", "")
            args = action.get("action_args", {}) or {}
            tgt = args.get("target_agent_name", "")
            action_type = action.get("action_type", "")

            if src and tgt and src != tgt:
                pair = (src, tgt)
                interactions[pair][action_type] += 1

        # 양방향 상호작용 합산
        merged: dict[frozenset, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        pair_names: dict[frozenset, tuple[str, str]] = {}
        for (src, tgt), counts in interactions.items():
            pair_key = frozenset([src, tgt])
            if pair_key not in pair_names:
                pair_names[pair_key] = (src, tgt)
            for action_type, count in counts.items():
                merged[pair_key][action_type] += count

        # 관계 라인 생성
        lines: list[dict] = []

        for pair_key, counts in merged.items():
            src, tgt = pair_names[pair_key]

            src_coords = self._get_coordinates(src, fallback)
            tgt_coords = self._get_coordinates(tgt, fallback)
            if not src_coords or not tgt_coords:
                continue

            # 관계 유형 결정
            support = sum(counts.get(a, 0) for a in SUPPORT_ACTIONS)
            oppose = sum(counts.get(a, 0) for a in OPPOSE_ACTIONS)
            total = support + oppose
            if total == 0:
                continue

            # 강도 임계값: 최소 2회 이상 상호작용
            if total < 2:
                continue

            if support > oppose:
                rel_type = "alliance" if support >= 3 else "support"
            else:
                rel_type = "hostile"

            strength = round(min(1.0, total / 10.0), 2)

            lines.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [src_coords["lng"], src_coords["lat"]],
                        [tgt_coords["lng"], tgt_coords["lat"]],
                    ],
                },
                "properties": {
                    "feature_type": "relationship",
                    "from_actor": src,
                    "to_actor": tgt,
                    "relationship_type": rel_type,
                    "strength": strength,
                    "color": RELATIONSHIP_COLORS.get(rel_type, "#6b7280"),
                },
            })

        return lines
