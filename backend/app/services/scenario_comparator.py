import json

from app.database import get_pool


class ScenarioComparator:
    async def compare(self, scenario_id_a: str, scenario_id_b: str) -> dict:
        pool = get_pool()
        async with pool.acquire() as conn:
            a = await conn.fetchrow(
                "SELECT * FROM scenarios WHERE id = $1", scenario_id_a
            )
            b = await conn.fetchrow(
                "SELECT * FROM scenarios WHERE id = $1", scenario_id_b
            )
            if not a or not b:
                raise ValueError("Scenario not found")

            result_a = await conn.fetchrow(
                "SELECT results, report FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id_a,
            )
            result_b = await conn.fetchrow(
                "SELECT results, report FROM simulation_results WHERE scenario_id = $1 ORDER BY created_at DESC LIMIT 1",
                scenario_id_b,
            )

            geo_count_a = await conn.fetchval(
                "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1",
                scenario_id_a,
            )
            geo_count_b = await conn.fetchval(
                "SELECT COUNT(*) FROM geopolitics_events WHERE scenario_id = $1",
                scenario_id_b,
            )

            actions_a = (
                json.loads(result_a["results"])
                if result_a and result_a["results"]
                else []
            )
            actions_b = (
                json.loads(result_b["results"])
                if result_b and result_b["results"]
                else []
            )

            actors_a = set()
            actors_b = set()
            for act in actions_a:
                actor = act.get("actor", act.get("author", ""))
                if actor:
                    actors_a.add(actor)
            for act in actions_b:
                actor = act.get("actor", act.get("author", ""))
                if actor:
                    actors_b.add(actor)

            return {
                "scenario_a": {
                    "id": a["id"],
                    "name": a["name"],
                    "region_name": a["region_name"],
                    "status": a["status"],
                    "actors": sorted(actors_a),
                    "action_count": len(actions_a),
                    "geopolitics_events": geo_count_a,
                },
                "scenario_b": {
                    "id": b["id"],
                    "name": b["name"],
                    "region_name": b["region_name"],
                    "status": b["status"],
                    "actors": sorted(actors_b),
                    "action_count": len(actions_b),
                    "geopolitics_events": geo_count_b,
                },
                "diff": {
                    "actors_only_a": sorted(actors_a - actors_b),
                    "actors_only_b": sorted(actors_b - actors_a),
                    "actors_common": sorted(actors_a & actors_b),
                    "action_count_delta": len(actions_b) - len(actions_a),
                    "geopolitics_events_delta": geo_count_b - geo_count_a,
                },
            }
