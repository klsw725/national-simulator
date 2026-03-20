from typing import Dict, Any, List, Optional, Set

from ..utils.dozerdb_client import get_dozerdb_client
from ..utils.logger import get_logger
from .zep_entity_reader import EntityNode, FilteredEntities

logger = get_logger("mirofish.local_entity_reader")


class LocalEntityReader:
    def __init__(self):
        self.dozer = get_dozerdb_client()

    def get_all_nodes(self, graph_id: str) -> List[Dict]:
        return self.dozer.get_all_nodes(graph_id)

    def get_all_edges(self, graph_id: str) -> List[Dict]:
        return self.dozer.get_edges_by_graph(graph_id)

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n["uuid"]: n for n in all_nodes}

        filtered_entities: List[EntityNode] = []
        entity_types_found: Set[str] = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom_labels = [l for l in labels if l not in ("Entity", "Node")]

            if not custom_labels:
                continue

            if defined_entity_types:
                matching = [l for l in custom_labels if l in defined_entity_types]
                if not matching:
                    continue

            for label in custom_labels:
                entity_types_found.add(label)

            entity = EntityNode(
                uuid=node.get("uuid", ""),
                name=node.get("name", ""),
                labels=labels,
                summary=node.get("summary", ""),
                attributes=node.get("attributes", {}),
            )

            if enrich_with_edges:
                self._enrich_entity(entity, all_edges, node_map)

            filtered_entities.append(entity)

        logger.info(
            f"그래프 {graph_id}: 전체 {total_count}개 중 "
            f"{len(filtered_entities)}개 엔티티 필터링"
        )

        return FilteredEntities(
            entities=filtered_entities,
            entity_types=entity_types_found,
            total_count=total_count,
            filtered_count=len(filtered_entities),
        )

    def get_entity_with_context(
        self, graph_id: str, entity_uuid: str
    ) -> Optional[EntityNode]:
        node = self.dozer.get_node(entity_uuid)
        if not node:
            return None

        edges = self.dozer.get_node_edges(entity_uuid)
        all_nodes = self.dozer.get_all_nodes(graph_id)
        node_map = {n["uuid"]: n for n in all_nodes}

        entity = EntityNode(
            uuid=node.get("uuid", ""),
            name=node.get("name", ""),
            labels=node.get("labels", []),
            summary=node.get("summary", ""),
            attributes=node.get("attributes", {}),
        )

        for edge in edges:
            edge_info = {
                "edge_uuid": edge.get("uuid", ""),
                "edge_name": edge.get("name", ""),
                "fact": edge.get("fact", ""),
                "fact_type": edge.get("fact_type", ""),
            }

            src_uuid = edge.get("source_node_uuid", "")
            tgt_uuid = edge.get("target_node_uuid", "")

            if src_uuid == entity_uuid:
                edge_info["direction"] = "outgoing"
                edge_info["connected_node_uuid"] = tgt_uuid
            else:
                edge_info["direction"] = "incoming"
                edge_info["connected_node_uuid"] = src_uuid

            entity.related_edges.append(edge_info)

            connected_uuid = edge_info["connected_node_uuid"]
            if connected_uuid in node_map:
                connected = node_map[connected_uuid]
                entity.related_nodes.append(
                    {
                        "uuid": connected.get("uuid", ""),
                        "name": connected.get("name", ""),
                        "labels": connected.get("labels", []),
                        "summary": connected.get("summary", ""),
                    }
                )

        return entity

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        result = self.filter_defined_entities(
            graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        )
        return result.entities

    def _enrich_entity(
        self,
        entity: EntityNode,
        all_edges: List[Dict],
        node_map: Dict[str, Dict],
    ):
        for edge in all_edges:
            src_uuid = edge.get("source_node_uuid", "")
            tgt_uuid = edge.get("target_node_uuid", "")

            if src_uuid != entity.uuid and tgt_uuid != entity.uuid:
                continue

            edge_info = {
                "edge_uuid": edge.get("uuid", ""),
                "edge_name": edge.get("name", ""),
                "fact": edge.get("fact", ""),
                "fact_type": edge.get("fact_type", ""),
            }

            if src_uuid == entity.uuid:
                edge_info["direction"] = "outgoing"
                connected_uuid = tgt_uuid
            else:
                edge_info["direction"] = "incoming"
                connected_uuid = src_uuid

            entity.related_edges.append(edge_info)

            if connected_uuid in node_map:
                connected = node_map[connected_uuid]
                node_info = {
                    "uuid": connected.get("uuid", ""),
                    "name": connected.get("name", ""),
                    "labels": connected.get("labels", []),
                    "summary": connected.get("summary", ""),
                }
                if node_info not in entity.related_nodes:
                    entity.related_nodes.append(node_info)
