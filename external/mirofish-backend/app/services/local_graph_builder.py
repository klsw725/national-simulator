import json
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.dozerdb_client import get_dozerdb_client
from ..utils.logger import get_logger
from .llm_entity_extractor import LLMEntityExtractor
from .text_processor import TextProcessor

logger = get_logger("mirofish.local_graph_builder")


class LocalGraphBuilderService:
    def __init__(self):
        self.dozer = get_dozerdb_client()
        self.extractor = LLMEntityExtractor()
        self.task_manager = TaskManager()

    def build_graph_async(
        self,
        text: str,
        ontology: Dict[str, Any],
        graph_name: str = "MiroFish Graph",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        batch_size: int = 3,
    ) -> str:
        task_id = self.task_manager.create_task(
            task_type="graph_build",
            metadata={
                "graph_name": graph_name,
                "chunk_size": chunk_size,
                "text_length": len(text),
            },
        )

        thread = threading.Thread(
            target=self._build_graph_worker,
            args=(task_id, text, ontology, graph_name, chunk_size, chunk_overlap),
        )
        thread.daemon = True
        thread.start()
        return task_id

    def _build_graph_worker(
        self,
        task_id: str,
        text: str,
        ontology: Dict,
        graph_name: str,
        chunk_size: int,
        chunk_overlap: int,
    ):
        try:
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=5,
                message="그래프 구축 시작...",
            )

            graph_id = self.create_graph(graph_name)
            self.task_manager.update_task(
                task_id,
                progress=10,
                message=f"그래프 생성: {graph_id}",
            )

            self.set_ontology(graph_id, ontology)
            self.task_manager.update_task(
                task_id,
                progress=15,
                message="온톨로지 설정 완료",
            )

            chunks = TextProcessor.split_text(text, chunk_size, chunk_overlap)
            total_chunks = len(chunks)
            self.task_manager.update_task(
                task_id,
                progress=20,
                message=f"텍스트 {total_chunks}개 청크로 분할",
            )

            episode_uuids = self.add_text_batches(
                graph_id,
                chunks,
                ontology,
                progress_callback=lambda msg, prog: self.task_manager.update_task(
                    task_id,
                    progress=20 + int(prog * 60),
                    message=msg,
                ),
            )

            self.task_manager.update_task(
                task_id,
                progress=90,
                message="그래프 정보 수집 중...",
            )
            graph_info = self._get_graph_info(graph_id)

            self.task_manager.complete_task(
                task_id,
                {
                    "graph_id": graph_id,
                    "graph_info": graph_info,
                    "chunks_processed": total_chunks,
                },
            )

        except Exception as exc:
            import traceback

            self.task_manager.fail_task(task_id, f"{exc}\n{traceback.format_exc()}")

    def create_graph(self, name: str) -> str:
        graph_id = f"mirofish_{uuid.uuid4().hex[:16]}"
        self.dozer.create_graph(graph_id, name, "MiroFish Social Simulation Graph")
        return graph_id

    def set_ontology(self, graph_id: str, ontology: Dict):
        graph = self.dozer.get_graph(graph_id)
        if graph is not None:
            ontology_json = json.dumps(ontology, ensure_ascii=False)
            self.dozer._run(
                "MATCH (g:Graph {graph_id: $gid}) SET g.ontology_json = $ont",
                {"gid": graph_id, "ont": ontology_json},
                write=True,
            )

    def add_text_batches(
        self,
        graph_id: str,
        chunks: List[str],
        ontology: Dict,
        progress_callback: Optional[Callable] = None,
    ) -> List[str]:
        episode_uuids = []
        total = len(chunks)

        for i, chunk in enumerate(chunks):
            ep_uuid = uuid.uuid4().hex[:16]
            self.dozer.create_episode(graph_id, ep_uuid, chunk)
            episode_uuids.append(ep_uuid)

            if progress_callback:
                progress_callback(
                    f"엔티티 추출 중... ({i + 1}/{total})",
                    (i + 1) / total,
                )

            existing_names = [n["name"] for n in self.dozer.get_all_nodes(graph_id)]

            result = self.extractor.extract_from_chunk(chunk, ontology, existing_names)

            for entity in result.entities:
                labels = ["Entity", entity.type] if entity.type else ["Entity"]
                self.dozer.create_node(
                    graph_id=graph_id,
                    node_uuid=entity.uuid,
                    name=entity.name,
                    labels=labels,
                    summary=entity.summary,
                    attributes=entity.attributes,
                )

            for rel in result.relationships:
                self.dozer.create_edge(
                    graph_id=graph_id,
                    edge_uuid=rel.uuid,
                    source_name=rel.source,
                    target_name=rel.target,
                    name=rel.type,
                    fact=rel.fact,
                    fact_type=rel.type,
                )

            self.dozer.mark_episode_processed(ep_uuid)

        return episode_uuids

    def _get_graph_info(self, graph_id: str) -> Dict:
        nodes = self.dozer.get_all_nodes(graph_id)
        edge_count = self.dozer.get_edge_count(graph_id)

        entity_types = set()
        for node in nodes:
            for label in node.get("labels", []):
                if label not in ("Entity", "Node"):
                    entity_types.add(label)

        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": edge_count,
            "entity_types": list(entity_types),
        }

    def get_graph_data(self, graph_id: str) -> Dict:
        nodes = self.dozer.get_all_nodes(graph_id)
        edges = self.dozer.get_edges_by_graph(graph_id)

        return {
            "graph_id": graph_id,
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    def delete_graph(self, graph_id: str):
        self.dozer.delete_graph(graph_id)
