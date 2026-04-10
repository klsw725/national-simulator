from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

from app.config import settings

logger = logging.getLogger(__name__)

_RETRY_COUNT = 3
_RETRY_DELAY = 2.0


class GraphStore:
    def __init__(self) -> None:
        self._driver = GraphDatabase.driver(
            settings.dozerdb_uri,
            auth=(settings.dozerdb_user, settings.dozerdb_password),
        )

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    def _run(self, query: str, params: dict | None = None, write: bool = False) -> list[dict]:
        import time
        last_exc: Exception | None = None
        delay = _RETRY_DELAY
        for attempt in range(_RETRY_COUNT):
            try:
                with self._driver.session() as session:
                    return session.run(query, params or {}).data()
            except (ServiceUnavailable, TransientError, OSError) as exc:
                last_exc = exc
                if attempt < _RETRY_COUNT - 1:
                    logger.warning("DozerDB retry %d/%d: %s", attempt + 1, _RETRY_COUNT, str(exc)[:100])
                    time.sleep(delay)
                    delay *= 2
        raise last_exc  # type: ignore[misc]

    def ensure_indexes(self) -> None:
        for stmt in [
            "CREATE CONSTRAINT entity_uuid IF NOT EXISTS FOR (n:Entity) REQUIRE n.uuid IS UNIQUE",
            "CREATE CONSTRAINT graph_gid IF NOT EXISTS FOR (g:Graph) REQUIRE g.graph_id IS UNIQUE",
        ]:
            try:
                self._run(stmt, write=True)
            except Exception:
                pass

    def store_entities_and_relations(
        self,
        graph_id: str,
        entities: list[dict[str, Any]],
        relations: list[dict[str, Any]],
    ) -> dict[str, int]:
        self._run(
            "MERGE (g:Graph {graph_id: $gid}) "
            "ON CREATE SET g.created_at = datetime()",
            {"gid": graph_id},
            write=True,
        )

        for entity in entities:
            node_uuid = str(uuid.uuid4())
            etype = entity.get("type", "Entity")
            self._run(
                "MERGE (n:Entity {name: $name, graph_id: $gid}) "
                "ON CREATE SET n.uuid = $uuid, n.entity_type = $etype, "
                "  n.attributes_json = $attrs, n.created_at = datetime() "
                "ON MATCH SET n.entity_type = $etype, n.attributes_json = $attrs",
                {
                    "gid": graph_id,
                    "uuid": node_uuid,
                    "name": entity.get("name", entity.get("id", "")),
                    "etype": etype,
                    "attrs": json.dumps(entity, ensure_ascii=False),
                },
                write=True,
            )

        edge_count = 0
        for rel in relations:
            edge_uuid = str(uuid.uuid4())
            result = self._run(
                "MATCH (a:Entity {name: $src, graph_id: $gid}), "
                "      (b:Entity {name: $tgt, graph_id: $gid}) "
                "MERGE (a)-[r:RELATES_TO {fact_type: $rtype, graph_id: $gid}]->(b) "
                "ON CREATE SET r.uuid = $uuid, r.strength = $strength, "
                "  r.created_at = datetime() "
                "ON MATCH SET r.strength = $strength "
                "RETURN r.uuid AS uuid",
                {
                    "gid": graph_id,
                    "uuid": edge_uuid,
                    "src": rel.get("source", ""),
                    "tgt": rel.get("target", ""),
                    "rtype": rel.get("type", "RELATES_TO"),
                    "strength": rel.get("strength", 0.5),
                },
                write=True,
            )
            if result:
                edge_count += 1

        return {"entities": len(entities), "relations": edge_count}

    def load_entities_and_relations(self, graph_id: str) -> dict[str, list[dict[str, Any]]]:
        entity_rows = self._run(
            "MATCH (n:Entity {graph_id: $gid}) "
            "RETURN n.name AS name, n.entity_type AS entity_type, n.attributes_json AS attrs "
            "ORDER BY n.name",
            {"gid": graph_id},
        )
        relation_rows = self._run(
            "MATCH (a:Entity {graph_id: $gid})-[r:RELATES_TO {graph_id: $gid}]->(b:Entity {graph_id: $gid}) "
            "RETURN a.name AS source, b.name AS target, r.fact_type AS rel_type, r.strength AS strength "
            "ORDER BY source, target, rel_type",
            {"gid": graph_id},
        )

        entities: list[dict[str, Any]] = []
        for row in entity_rows:
            raw_attrs = row.get("attrs")
            attrs = json.loads(raw_attrs) if isinstance(raw_attrs, str) and raw_attrs else {}
            if not isinstance(attrs, dict):
                attrs = {}
            if "name" not in attrs and row.get("name"):
                attrs["name"] = row["name"]
            if "type" not in attrs and row.get("entity_type"):
                attrs["type"] = row["entity_type"]
            entities.append(attrs)

        relations: list[dict[str, Any]] = []
        for row in relation_rows:
            relations.append({
                "source": row.get("source", ""),
                "target": row.get("target", ""),
                "type": row.get("rel_type", "RELATES_TO"),
                "strength": row.get("strength", 0.5),
            })

        return {"entities": entities, "relations": relations}


_store: GraphStore | None = None


def get_graph_store() -> GraphStore:
    global _store
    if _store is None:
        _store = GraphStore()
        _store.ensure_indexes()
    return _store
