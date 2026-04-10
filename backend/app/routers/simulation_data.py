from __future__ import annotations

import json
import hashlib

from fastapi import APIRouter

from app.database import get_pool

router = APIRouter()


def _node_uuid(entity: dict) -> str:
    raw = str(entity.get("id") or entity.get("name") or entity)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _empty_graph() -> dict:
    return {"nodes": [], "edges": [], "node_count": 0, "edge_count": 0}


def _build_graph_response(entities: list[dict], relations: list[dict]) -> dict:
    nodes = []
    node_map: dict[str, str] = {}
    for entity in entities:
        uuid = _node_uuid(entity)
        name = str(entity.get("name") or entity.get("id") or uuid)
        node_map[str(entity.get("id") or name)] = uuid
        node_map[name] = uuid
        nodes.append({
            "uuid": uuid,
            "name": name,
            "entityType": entity.get("type", "Entity"),
            "labels": [entity.get("type", "Entity")],
            "attributes": entity,
            "summary": entity.get("summary"),
        })

    edges = []
    for rel in relations:
        src = str(rel.get("source", ""))
        tgt = str(rel.get("target", ""))
        src_uuid = node_map.get(src)
        tgt_uuid = node_map.get(tgt)
        if not src_uuid or not tgt_uuid:
            continue
        edges.append({
            "uuid": hashlib.sha1(f"{src}:{tgt}:{rel.get('type', '')}".encode("utf-8")).hexdigest()[:16],
            "source_node_uuid": src_uuid,
            "target_node_uuid": tgt_uuid,
            "name": rel.get("type", "RELATES_TO"),
            "fact": rel.get("fact"),
            "fact_type": rel.get("type", "RELATES_TO"),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


@router.get("/api/scenario/{scenario_id}/live/actions")
async def get_live_actions(scenario_id: str, offset: int = 0, limit: int = 100):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT payload, sequence_num, created_at
               FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'agent_action'
               ORDER BY sequence_num
               OFFSET $2 LIMIT $3""",
            scenario_id, offset, limit,
        )
        count_row = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'agent_action'",
            scenario_id,
        )

    actions = []
    for row in rows:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        actions.append({
            "sequence_num": row["sequence_num"],
            "created_at": str(row["created_at"]),
            **payload,
        })

    return {"actions": actions, "count": count_row["cnt"] if count_row else 0}


@router.get("/api/scenario/{scenario_id}/live/stats")
async def get_live_stats(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1",
            scenario_id,
        )
        rounds = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'round_complete'",
            scenario_id,
        )
        actions = await conn.fetchrow(
            "SELECT count(*) AS cnt FROM simulation_events WHERE scenario_id = $1 AND event_type = 'agent_action'",
            scenario_id,
        )

    return {
        "scenario_id": scenario_id,
        "total_events": total["cnt"] if total else 0,
        "total_rounds": rounds["cnt"] if rounds else 0,
        "total_actions": actions["cnt"] if actions else 0,
    }


@router.get("/api/scenario/{scenario_id}/live/graph_data")
async def get_live_graph_data(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT payload
               FROM simulation_events
               WHERE scenario_id = $1 AND event_type = 'graph_data'
               ORDER BY sequence_num DESC LIMIT 1""",
            scenario_id,
        )

        checkpoint_row = None
        if not row:
            checkpoint_row = await conn.fetchrow(
                """SELECT checkpoint
                   FROM checkpoints
                   WHERE thread_id = $1
                   ORDER BY checkpoint_id DESC LIMIT 1""",
                scenario_id,
            )

    if row:
        payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else row["payload"]
        entities = payload.get("entities", [])
        relations = payload.get("relations", [])
        return _build_graph_response(entities, relations)

    if not checkpoint_row:
        return _empty_graph()

    checkpoint = checkpoint_row["checkpoint"]
    if isinstance(checkpoint, str):
        checkpoint = json.loads(checkpoint)
    channel_values = checkpoint.get("channel_values", {})
    entities = channel_values.get("graph_entities")
    relations = channel_values.get("graph_relations")

    if entities is None or relations is None:
        engine_state = channel_values.get("decision_engine_state", {})
        entities = engine_state.get("extracted_entities", [])
        relations = engine_state.get("extracted_relations", [])

    return _build_graph_response(entities or [], relations or [])


@router.get("/api/scenario/{scenario_id}/geopolitics")
async def get_geopolitics_summary(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM geopolitics_events WHERE scenario_id = $1",
            scenario_id,
        )
        max_round = await conn.fetchrow(
            "SELECT COALESCE(MAX(round_number), 0) AS max_r FROM geopolitics_events WHERE scenario_id = $1",
            scenario_id,
        )
        actor_rows = await conn.fetch(
            "SELECT DISTINCT actor_id FROM geopolitics_events WHERE scenario_id = $1 AND actor_id != ''",
            scenario_id,
        )
        target_rows = await conn.fetch(
            "SELECT DISTINCT unnest(string_to_array(target_actor_ids, ',')) AS aid FROM geopolitics_events WHERE scenario_id = $1 AND target_actor_ids != ''",
            scenario_id,
        )

    actor_set = {r["actor_id"] for r in actor_rows}
    for r in target_rows:
        aid = r["aid"].strip()
        if aid:
            actor_set.add(aid)

    return {
        "scenario_id": scenario_id,
        "total_events": total["cnt"] if total else 0,
        "total_rounds": max_round["max_r"] if max_round else 0,
        "actors": sorted(actor_set),
    }


@router.get("/api/scenario/{scenario_id}/geopolitics/events")
async def get_geopolitics_events(scenario_id: str, limit: int = 100):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, action_type, actor_id, target_actor_ids, content, magnitude, round_number, event_at
               FROM geopolitics_events
               WHERE scenario_id = $1
               ORDER BY event_at DESC LIMIT $2""",
            scenario_id, limit,
        )

    return [
        {
            "id": row["id"],
            "action_type": row["action_type"],
            "actor_id": row["actor_id"],
            "target_actor_ids": row["target_actor_ids"],
            "content": row["content"],
            "magnitude": row["magnitude"],
            "round_number": row["round_number"],
            "event_at": str(row["event_at"]),
        }
        for row in rows
    ]


@router.get("/api/scenario/{scenario_id}/geopolitics/timeline")
async def get_geopolitics_timeline(scenario_id: str):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT action_type, actor_id, target_actor_ids, content, magnitude, round_number
               FROM geopolitics_events
               WHERE scenario_id = $1
               ORDER BY round_number, event_at""",
            scenario_id,
        )

    rounds: dict[int, list] = {}
    for row in rows:
        rn = row["round_number"] or 0
        target_str = row["target_actor_ids"] or ""
        targets = [t.strip() for t in target_str.split(",") if t.strip()]
        rounds.setdefault(rn, []).append({
            "action_type": row["action_type"],
            "actor_id": row["actor_id"],
            "target_actor_ids": targets,
            "content": row["content"] or "",
            "magnitude": row["magnitude"] or 0.5,
        })

    timeline = [
        {"round": rn, "events": events}
        for rn, events in sorted(rounds.items())
    ]

    return {"scenario_id": scenario_id, "timeline": timeline}
