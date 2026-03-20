from typing import Dict, Any, List, Optional

from ..utils.dozerdb_client import get_dozerdb_client
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger
from .zep_tools import SearchResult, NodeInfo

logger = get_logger("mirofish.local_tools_service")


class LocalToolsService:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.dozer = get_dozerdb_client()
        self._llm_client = llm_client

    @property
    def llm(self) -> LLMClient:
        if self._llm_client is None:
            self._llm_client = LLMClient()
        return self._llm_client

    def search_graph(
        self, graph_id: str, query: str, limit: int = 10, scope: str = "edges"
    ) -> SearchResult:
        return self.quick_search(graph_id, query, limit)

    def quick_search(self, graph_id: str, query: str, limit: int = 10) -> SearchResult:
        result = self.dozer.search_fulltext(graph_id, query, scope="both", limit=limit)
        return SearchResult(
            facts=result.get("facts", []),
            edges=result.get("edges", []),
            nodes=result.get("nodes", []),
            query=query,
            total_count=result.get("total_count", 0),
        )

    def panorama_search(
        self, graph_id: str, query: str, include_expired: bool = True
    ) -> SearchResult:
        all_edges = self.dozer.get_edges_by_graph(graph_id)
        all_nodes = self.dozer.get_all_nodes(graph_id)

        active_facts = []
        historical_facts = []
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.split() if len(w.strip()) > 1]

        for edge in all_edges:
            text = f"{edge.get('fact', '')} {edge.get('name', '')}".lower()
            relevant = query_lower in text or any(kw in text for kw in keywords)

            if not relevant:
                continue

            fact = edge.get("fact", "")
            if not fact:
                continue

            if edge.get("expired_at"):
                if include_expired:
                    historical_facts.append(f"[과거] {fact}")
            else:
                active_facts.append(fact)

        node_summaries = []
        for node in all_nodes:
            text = f"{node.get('name', '')} {node.get('summary', '')}".lower()
            if query_lower in text or any(kw in text for kw in keywords):
                if node.get("summary"):
                    node_summaries.append(f"[{node['name']}]: {node['summary']}")

        all_facts = active_facts + historical_facts + node_summaries

        return SearchResult(
            facts=all_facts,
            edges=[],
            nodes=all_nodes[:20],
            query=query,
            total_count=len(all_facts),
        )

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str = "",
        report_context: str = "",
    ) -> SearchResult:
        sub_questions = self._generate_sub_questions(query, simulation_requirement)

        all_facts = []
        all_edges = []
        all_nodes = []

        for sq in sub_questions:
            result = self.dozer.search_fulltext(graph_id, sq, scope="both", limit=5)
            for f in result.get("facts", []):
                if f not in all_facts:
                    all_facts.append(f)
            all_edges.extend(result.get("edges", []))
            all_nodes.extend(result.get("nodes", []))

        main_result = self.dozer.search_fulltext(
            graph_id, query, scope="both", limit=10
        )
        for f in main_result.get("facts", []):
            if f not in all_facts:
                all_facts.append(f)

        return SearchResult(
            facts=all_facts,
            edges=all_edges,
            nodes=all_nodes,
            query=query,
            total_count=len(all_facts),
        )

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        nodes = self.dozer.get_all_nodes(graph_id)
        edge_count = self.dozer.get_edge_count(graph_id)

        entity_types: Dict[str, int] = {}
        for node in nodes:
            for label in node.get("labels", []):
                if label not in ("Entity", "Node"):
                    entity_types[label] = entity_types.get(label, 0) + 1

        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": edge_count,
            "entity_types": entity_types,
        }

    def get_entity_summary(self, graph_id: str, entity_name: str) -> Dict[str, Any]:
        nodes = self.dozer.get_all_nodes(graph_id)
        for node in nodes:
            if node.get("name", "").lower() == entity_name.lower():
                edges = self.dozer.get_node_edges(node["uuid"])
                return {
                    "name": node.get("name", ""),
                    "summary": node.get("summary", ""),
                    "labels": node.get("labels", []),
                    "attributes": node.get("attributes", {}),
                    "related_facts": [
                        e.get("fact", "") for e in edges if e.get("fact")
                    ],
                }
        return {"name": entity_name, "summary": "", "error": "엔티티를 찾을 수 없음"}

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> List[NodeInfo]:
        nodes = self.dozer.get_all_nodes(graph_id)
        result = []
        for node in nodes:
            labels = node.get("labels", [])
            if entity_type in labels:
                result.append(
                    NodeInfo(
                        uuid=node.get("uuid", ""),
                        name=node.get("name", ""),
                        labels=labels,
                        summary=node.get("summary", ""),
                        attributes=node.get("attributes", {}),
                    )
                )
        return result

    def get_simulation_context(
        self, graph_id: str, simulation_requirement: str = "", limit: int = 30
    ) -> Dict[str, Any]:
        search_result = (
            self.search_graph(
                graph_id=graph_id, query=simulation_requirement, limit=limit
            )
            if simulation_requirement
            else None
        )

        stats = self.get_graph_statistics(graph_id)
        nodes = self.dozer.get_all_nodes(graph_id)

        entity_summaries = []
        for node in nodes[:limit]:
            labels = node.get("labels", [])
            entity_type = next((l for l in labels if l not in ("Entity", "Node")), "")
            if entity_type:
                entity_summaries.append(
                    {
                        "name": node.get("name", ""),
                        "type": entity_type,
                        "summary": node.get("summary", ""),
                    }
                )

        return {
            "search_result": search_result.to_dict() if search_result else {},
            "statistics": stats,
            "entity_summaries": entity_summaries,
        }

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
    ) -> SearchResult:
        from .zep_tools import ZepToolsService

        zep_service = ZepToolsService.__new__(ZepToolsService)
        zep_service._llm_client = self._llm_client
        return zep_service.interview_agents(
            simulation_id=simulation_id,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents,
        )

    def _generate_sub_questions(self, query: str, context: str = "") -> List[str]:
        prompt = (
            f"다음 질문을 분석하기 위한 3개의 하위 검색 질문을 생성하세요.\n"
            f"질문: {query}\n"
        )
        if context:
            prompt += f"맥락: {context}\n"
        prompt += "각 줄에 하나씩 3개의 검색 질문만 출력하세요."

        try:
            response = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )
            lines = [
                line.strip().lstrip("0123456789.-) ")
                for line in response.strip().split("\n")
                if line.strip()
            ]
            return lines[:3] if lines else [query]
        except Exception:
            return [query]
