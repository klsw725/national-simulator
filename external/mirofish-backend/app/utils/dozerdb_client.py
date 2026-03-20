import json
import time
import uuid as uuid_mod
from typing import Dict, Any, List, Optional
from datetime import datetime

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, TransientError

from ..config import Config
from .logger import get_logger

logger = get_logger("mirofish.dozerdb")

_RETRY_COUNT = 3
_RETRY_DELAY = 2.0


class DozerDBClient:
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._uri = uri or Config.DOZERDB_URI
        self._user = user or Config.DOZERDB_USER
        self._password = password or Config.DOZERDB_PASSWORD
        self._driver = GraphDatabase.driver(
            self._uri, auth=(self._user, self._password)
        )
        logger.info(f"DozerDB 연결: {self._uri}")

    def close(self):
        if self._driver:
            self._driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # retry helper
    # ------------------------------------------------------------------

    def _run(self, query: str, params: Optional[Dict] = None, write: bool = False):
        last_exc = None
        delay = _RETRY_DELAY
        for attempt in range(_RETRY_COUNT):
            try:
                with self._driver.session() as session:
                    if write:
                        return session.run(query, params or {}).data()
                    else:
                        return session.run(query, params or {}).data()
            except (ServiceUnavailable, TransientError, OSError) as exc:
                last_exc = exc
                if attempt < _RETRY_COUNT - 1:
                    logger.warning(
                        f"DozerDB 쿼리 재시도 ({attempt + 1}/{_RETRY_COUNT}): "
                        f"{str(exc)[:100]}"
                    )
                    time.sleep(delay)
                    delay *= 2
        raise last_exc  # type: ignore[misc]

    def _run_single(
        self, query: str, params: Optional[Dict] = None, write: bool = False
    ):
        rows = self._run(query, params, write=write)
        return rows[0] if rows else None

    # ------------------------------------------------------------------
    # Graph metadata
    # ------------------------------------------------------------------

    def create_graph(
        self, graph_id: str, name: str, description: str = "", ontology_json: str = ""
    ):
        self._run(
            "CREATE (g:Graph {graph_id: $gid, name: $name, description: $desc, "
            "ontology_json: $ont, created_at: datetime()})",
            {"gid": graph_id, "name": name, "desc": description, "ont": ontology_json},
            write=True,
        )
        logger.info(f"그래프 생성: {graph_id}")

    def delete_graph(self, graph_id: str):
        self._run(
            "MATCH (n) WHERE n.graph_id = $gid DETACH DELETE n",
            {"gid": graph_id},
            write=True,
        )
        self._run(
            "MATCH (g:Graph {graph_id: $gid}) DELETE g",
            {"gid": graph_id},
            write=True,
        )
        logger.info(f"그래프 삭제: {graph_id}")

    def get_graph(self, graph_id: str) -> Optional[Dict]:
        row = self._run_single(
            "MATCH (g:Graph {graph_id: $gid}) RETURN g", {"gid": graph_id}
        )
        return dict(row["g"]) if row else None

    # ------------------------------------------------------------------
    # Indexes & constraints (idempotent)
    # ------------------------------------------------------------------

    def ensure_indexes(self):
        stmts = [
            "CREATE CONSTRAINT entity_uuid IF NOT EXISTS FOR (n:Entity) REQUIRE n.uuid IS UNIQUE",
            "CREATE CONSTRAINT graph_gid IF NOT EXISTS FOR (g:Graph) REQUIRE g.graph_id IS UNIQUE",
            "CREATE CONSTRAINT episode_uuid IF NOT EXISTS FOR (e:Episode) REQUIRE e.uuid IS UNIQUE",
        ]
        for s in stmts:
            try:
                self._run(s, write=True)
            except Exception as exc:
                logger.debug(f"인덱스/제약 생성 스킵 (이미 존재 가능): {exc}")

        # Full-text indexes — 별도 try/except (이미 존재하면 에러)
        ft = [
            "CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (n:Entity) ON EACH [n.name, n.summary]",
        ]
        for s in ft:
            try:
                self._run(s, write=True)
            except Exception as exc:
                logger.debug(f"Full-text 인덱스 스킵: {exc}")

    # ------------------------------------------------------------------
    # Node CRUD
    # ------------------------------------------------------------------

    def create_node(
        self,
        graph_id: str,
        node_uuid: str,
        name: str,
        labels: List[str],
        summary: str = "",
        attributes: Optional[Dict] = None,
    ) -> Dict:
        attrs_json = json.dumps(attributes or {}, ensure_ascii=False)
        custom_labels = [l for l in labels if l not in ("Entity", "Node")]

        row = self._run_single(
            "MERGE (n:Entity {name: $name, graph_id: $gid}) "
            "ON CREATE SET n.uuid = $uuid, n.summary = $summary, "
            "  n.attributes_json = $attrs, n.created_at = datetime() "
            "ON MATCH SET "
            "  n.summary = CASE WHEN n.summary IS NULL OR n.summary = '' "
            "    THEN $summary ELSE n.summary + '\\n' + $summary END, "
            "  n.attributes_json = $attrs "
            "RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary, "
            "  n.attributes_json AS attributes_json, "
            "  toString(n.created_at) AS created_at, labels(n) AS labels",
            {
                "gid": graph_id,
                "uuid": node_uuid,
                "name": name,
                "summary": summary,
                "attrs": attrs_json,
            },
            write=True,
        )

        if custom_labels and row:
            actual_uuid = row.get("uuid", node_uuid)
            for lbl in custom_labels:
                try:
                    self._run(
                        f"MATCH (n:Entity {{uuid: $uuid}}) SET n:{lbl}",
                        {"uuid": actual_uuid},
                        write=True,
                    )
                except Exception:
                    logger.debug(f"라벨 추가 실패: {lbl}")

        return self._node_row_to_dict(row) if row else {}

    def get_node(self, node_uuid: str) -> Optional[Dict]:
        row = self._run_single(
            "MATCH (n:Entity {uuid: $uuid}) "
            "RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary, "
            "  n.attributes_json AS attributes_json, "
            "  toString(n.created_at) AS created_at, labels(n) AS labels",
            {"uuid": node_uuid},
        )
        return self._node_row_to_dict(row) if row else None

    def get_nodes_by_graph(
        self, graph_id: str, limit: int = 100, skip: int = 0
    ) -> List[Dict]:
        rows = self._run(
            "MATCH (n:Entity {graph_id: $gid}) "
            "RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary, "
            "  n.attributes_json AS attributes_json, "
            "  toString(n.created_at) AS created_at, labels(n) AS labels "
            "ORDER BY n.created_at SKIP $skip LIMIT $limit",
            {"gid": graph_id, "skip": skip, "limit": limit},
        )
        return [self._node_row_to_dict(r) for r in rows]

    def get_all_nodes(self, graph_id: str) -> List[Dict]:
        rows = self._run(
            "MATCH (n:Entity {graph_id: $gid}) "
            "RETURN n.uuid AS uuid, n.name AS name, n.summary AS summary, "
            "  n.attributes_json AS attributes_json, "
            "  toString(n.created_at) AS created_at, labels(n) AS labels "
            "ORDER BY n.created_at",
            {"gid": graph_id},
        )
        return [self._node_row_to_dict(r) for r in rows]

    def get_node_count(self, graph_id: str) -> int:
        row = self._run_single(
            "MATCH (n:Entity {graph_id: $gid}) RETURN count(n) AS cnt",
            {"gid": graph_id},
        )
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Edge CRUD
    # ------------------------------------------------------------------

    def create_edge(
        self,
        graph_id: str,
        edge_uuid: str,
        source_name: str,
        target_name: str,
        name: str = "",
        fact: str = "",
        fact_type: str = "",
        valid_at: Optional[str] = None,
        invalid_at: Optional[str] = None,
        expired_at: Optional[str] = None,
    ) -> Dict:
        row = self._run_single(
            "MATCH (a:Entity {name: $src, graph_id: $gid}), "
            "      (b:Entity {name: $tgt, graph_id: $gid}) "
            "MERGE (a)-[r:RELATES_TO {fact: $fact, graph_id: $gid}]->(b) "
            "ON CREATE SET r.uuid = $uuid, r.name = $name, r.fact_type = $ft, "
            "  r.valid_at = $va, r.invalid_at = $ia, r.expired_at = $ea, "
            "  r.created_at = datetime() "
            "ON MATCH SET r.name = $name, r.fact_type = $ft "
            "RETURN r.uuid AS uuid, r.name AS name, r.fact AS fact, "
            "  r.fact_type AS fact_type, "
            "  a.uuid AS source_node_uuid, b.uuid AS target_node_uuid, "
            "  toString(r.created_at) AS created_at, "
            "  r.valid_at AS valid_at, r.invalid_at AS invalid_at, "
            "  r.expired_at AS expired_at",
            {
                "gid": graph_id,
                "uuid": edge_uuid,
                "src": source_name,
                "tgt": target_name,
                "name": name,
                "fact": fact,
                "ft": fact_type,
                "va": valid_at,
                "ia": invalid_at,
                "ea": expired_at,
            },
            write=True,
        )
        return dict(row) if row else {}

    def get_edges_by_graph(self, graph_id: str) -> List[Dict]:
        rows = self._run(
            "MATCH (a:Entity {graph_id: $gid})-[r:RELATES_TO]->(b:Entity {graph_id: $gid}) "
            "RETURN r.uuid AS uuid, r.name AS name, r.fact AS fact, "
            "  r.fact_type AS fact_type, "
            "  a.uuid AS source_node_uuid, b.uuid AS target_node_uuid, "
            "  a.name AS source_node_name, b.name AS target_node_name, "
            "  toString(r.created_at) AS created_at, "
            "  r.valid_at AS valid_at, r.invalid_at AS invalid_at, "
            "  r.expired_at AS expired_at",
            {"gid": graph_id},
        )
        return [dict(r) for r in rows]

    def get_node_edges(self, node_uuid: str) -> List[Dict]:
        rows = self._run(
            "MATCH (n:Entity {uuid: $uuid})-[r:RELATES_TO]-(m:Entity) "
            "RETURN r.uuid AS uuid, r.name AS name, r.fact AS fact, "
            "  r.fact_type AS fact_type, "
            "  startNode(r).uuid AS source_node_uuid, "
            "  endNode(r).uuid AS target_node_uuid, "
            "  toString(r.created_at) AS created_at, "
            "  r.valid_at AS valid_at, r.invalid_at AS invalid_at, "
            "  r.expired_at AS expired_at",
            {"uuid": node_uuid},
        )
        return [dict(r) for r in rows]

    def get_edge_count(self, graph_id: str) -> int:
        row = self._run_single(
            "MATCH (a:Entity {graph_id: $gid})-[r:RELATES_TO]->(b:Entity {graph_id: $gid}) "
            "RETURN count(r) AS cnt",
            {"gid": graph_id},
        )
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Full-text search
    # ------------------------------------------------------------------

    def search_fulltext(
        self, graph_id: str, query: str, scope: str = "edges", limit: int = 10
    ) -> Dict[str, Any]:
        facts: List[str] = []
        edges: List[Dict] = []
        nodes: List[Dict] = []

        safe_query = query.replace('"', '\\"').replace("'", "\\'")

        if scope in ("edges", "both"):
            all_edges = self.get_edges_by_graph(graph_id)
            query_lower = query.lower()
            keywords = [w.strip() for w in query_lower.split() if len(w.strip()) > 1]

            scored = []
            for e in all_edges:
                score = 0
                text = f"{e.get('fact', '')} {e.get('name', '')}".lower()
                if query_lower in text:
                    score += 100
                for kw in keywords:
                    if kw in text:
                        score += 10
                if score > 0:
                    scored.append((score, e))

            scored.sort(key=lambda x: x[0], reverse=True)
            for _, e in scored[:limit]:
                if e.get("fact"):
                    facts.append(e["fact"])
                edges.append(e)

        if scope in ("nodes", "both"):
            all_nodes = self.get_all_nodes(graph_id)
            query_lower = query.lower()
            keywords = [w.strip() for w in query_lower.split() if len(w.strip()) > 1]

            scored = []
            for n in all_nodes:
                score = 0
                text = f"{n.get('name', '')} {n.get('summary', '')}".lower()
                if query_lower in text:
                    score += 100
                for kw in keywords:
                    if kw in text:
                        score += 10
                if score > 0:
                    scored.append((score, n))

            scored.sort(key=lambda x: x[0], reverse=True)
            for _, n in scored[:limit]:
                nodes.append(n)
                if n.get("summary"):
                    facts.append(f"[{n['name']}]: {n['summary']}")

        return {
            "facts": facts,
            "edges": edges,
            "nodes": nodes,
            "query": query,
            "total_count": len(facts),
        }

    # ------------------------------------------------------------------
    # Episode tracking
    # ------------------------------------------------------------------

    def create_episode(
        self, graph_id: str, ep_uuid: str, data: str, type_: str = "text"
    ):
        self._run(
            "CREATE (e:Episode {uuid: $uuid, graph_id: $gid, data: $data, "
            "type: $type, processed: false, created_at: datetime()})",
            {"uuid": ep_uuid, "gid": graph_id, "data": data, "type": type_},
            write=True,
        )

    def mark_episode_processed(self, ep_uuid: str):
        self._run(
            "MATCH (e:Episode {uuid: $uuid}) SET e.processed = true",
            {"uuid": ep_uuid},
            write=True,
        )

    def get_episode(self, ep_uuid: str) -> Optional[Dict]:
        row = self._run_single(
            "MATCH (e:Episode {uuid: $uuid}) "
            "RETURN e.uuid AS uuid, e.processed AS processed, "
            "  e.graph_id AS graph_id, toString(e.created_at) AS created_at",
            {"uuid": ep_uuid},
        )
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _node_row_to_dict(row: Dict) -> Dict:
        attrs_json = row.get("attributes_json", "{}")
        try:
            attributes = json.loads(attrs_json) if attrs_json else {}
        except (json.JSONDecodeError, TypeError):
            attributes = {}

        return {
            "uuid": row.get("uuid", ""),
            "name": row.get("name", ""),
            "labels": row.get("labels", []),
            "summary": row.get("summary", ""),
            "attributes": attributes,
            "created_at": row.get("created_at"),
        }


# ------------------------------------------------------------------
# Singleton
# ------------------------------------------------------------------

_client_instance: Optional[DozerDBClient] = None


def get_dozerdb_client() -> DozerDBClient:
    global _client_instance
    if _client_instance is None:
        _client_instance = DozerDBClient()
        _client_instance.ensure_indexes()
    return _client_instance
