import time
import threading
from typing import Dict, Any, List, Optional
from queue import Queue, Empty

from ..utils.dozerdb_client import get_dozerdb_client
from ..utils.logger import get_logger
from .llm_entity_extractor import LLMEntityExtractor
from .zep_graph_memory_updater import AgentActivity

logger = get_logger("mirofish.local_graph_memory_updater")


class LocalGraphMemoryUpdater:
    BATCH_SIZE = 5
    PLATFORM_DISPLAY_NAMES = {"twitter": "월드1", "reddit": "월드2"}
    SEND_INTERVAL = 0.5
    MAX_RETRIES = 3
    RETRY_DELAY = 2

    def __init__(self, graph_id: str):
        self.graph_id = graph_id
        self.dozer = get_dozerdb_client()
        self.extractor = LLMEntityExtractor()
        self._ontology = self._load_ontology()

        self._activity_queue: Queue = Queue()
        self._platform_buffers: Dict[str, List[AgentActivity]] = {
            "twitter": [],
            "reddit": [],
        }
        self._buffer_lock = threading.Lock()

        self._running = False
        self._worker_thread: Optional[threading.Thread] = None

        self._total_activities = 0
        self._total_sent = 0
        self._total_items_sent = 0
        self._failed_count = 0
        self._skipped_count = 0

    def _load_ontology(self) -> Dict:
        import json

        graph = self.dozer.get_graph(self.graph_id)
        if graph and graph.get("ontology_json"):
            try:
                return json.loads(graph["ontology_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def _get_platform_display_name(self, platform: str) -> str:
        return self.PLATFORM_DISPLAY_NAMES.get(platform.lower(), platform)

    def start(self):
        if self._running:
            return
        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name=f"LocalMemoryUpdater-{self.graph_id[:8]}",
        )
        self._worker_thread.start()
        logger.info(f"LocalGraphMemoryUpdater 시작: graph_id={self.graph_id}")

    def stop(self):
        self._running = False
        self._flush_remaining()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=10)
        logger.info(
            f"LocalGraphMemoryUpdater 중지: graph_id={self.graph_id}, "
            f"total={self._total_activities}, sent={self._total_items_sent}, "
            f"failed={self._failed_count}, skipped={self._skipped_count}"
        )

    def add_activity(self, activity: AgentActivity):
        if activity.action_type == "DO_NOTHING":
            self._skipped_count += 1
            return
        self._activity_queue.put(activity)
        self._total_activities += 1

    def add_activity_from_dict(self, data: Dict[str, Any], platform: str):
        if "event_type" in data:
            return
        from datetime import datetime

        activity = AgentActivity(
            platform=platform,
            agent_id=data.get("agent_id", 0),
            agent_name=data.get("agent_name", ""),
            action_type=data.get("action_type", ""),
            action_args=data.get("action_args", {}),
            round_num=data.get("round", 0),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )
        self.add_activity(activity)

    def _worker_loop(self):
        while self._running or not self._activity_queue.empty():
            try:
                try:
                    activity = self._activity_queue.get(timeout=1)
                    platform = activity.platform.lower()
                    with self._buffer_lock:
                        if platform not in self._platform_buffers:
                            self._platform_buffers[platform] = []
                        self._platform_buffers[platform].append(activity)

                        if len(self._platform_buffers[platform]) >= self.BATCH_SIZE:
                            batch = self._platform_buffers[platform][: self.BATCH_SIZE]
                            self._platform_buffers[platform] = self._platform_buffers[
                                platform
                            ][self.BATCH_SIZE :]
                            self._send_batch_activities(batch, platform)
                            time.sleep(self.SEND_INTERVAL)
                except Empty:
                    pass
            except Exception as e:
                logger.error(f"작업 루프 예외: {e}")
                time.sleep(1)

    def _send_batch_activities(self, activities: List[AgentActivity], platform: str):
        if not activities:
            return

        episode_texts = [a.to_episode_text() for a in activities]
        combined_text = "\n".join(episode_texts)

        for attempt in range(self.MAX_RETRIES):
            try:
                result = self.extractor.extract_from_chunk(
                    combined_text, self._ontology
                )

                for entity in result.entities:
                    labels = ["Entity", entity.type] if entity.type else ["Entity"]
                    self.dozer.create_node(
                        graph_id=self.graph_id,
                        node_uuid=entity.uuid,
                        name=entity.name,
                        labels=labels,
                        summary=entity.summary,
                        attributes=entity.attributes,
                    )

                for rel in result.relationships:
                    self.dozer.create_edge(
                        graph_id=self.graph_id,
                        edge_uuid=rel.uuid,
                        source_name=rel.source,
                        target_name=rel.target,
                        name=rel.type,
                        fact=rel.fact,
                        fact_type=rel.type,
                    )

                self._total_sent += 1
                self._total_items_sent += len(activities)
                display = self._get_platform_display_name(platform)
                logger.info(
                    f"{len(activities)}개 {display} 활동 → "
                    f"{len(result.entities)}개 엔티티, {len(result.relationships)}개 관계 추출"
                )
                return

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning(
                        f"로컬 그래프 업데이트 실패 ({attempt + 1}/{self.MAX_RETRIES}): {e}"
                    )
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(
                        f"로컬 그래프 업데이트 실패, {self.MAX_RETRIES}회 재시도: {e}"
                    )
                    self._failed_count += 1

    def _flush_remaining(self):
        while not self._activity_queue.empty():
            try:
                activity = self._activity_queue.get_nowait()
                platform = activity.platform.lower()
                with self._buffer_lock:
                    if platform not in self._platform_buffers:
                        self._platform_buffers[platform] = []
                    self._platform_buffers[platform].append(activity)
            except Empty:
                break

        with self._buffer_lock:
            for platform, buffer in self._platform_buffers.items():
                if buffer:
                    display = self._get_platform_display_name(platform)
                    logger.info(f"{display} 남은 {len(buffer)}개 활동 전송")
                    self._send_batch_activities(buffer, platform)
            for platform in self._platform_buffers:
                self._platform_buffers[platform] = []

    def get_stats(self) -> Dict[str, Any]:
        with self._buffer_lock:
            buffer_sizes = {p: len(b) for p, b in self._platform_buffers.items()}
        return {
            "graph_id": self.graph_id,
            "batch_size": self.BATCH_SIZE,
            "total_activities": self._total_activities,
            "batches_sent": self._total_sent,
            "items_sent": self._total_items_sent,
            "failed_count": self._failed_count,
            "skipped_count": self._skipped_count,
            "queue_size": self._activity_queue.qsize(),
            "buffer_sizes": buffer_sizes,
            "running": self._running,
        }


class LocalGraphMemoryManager:
    _updaters: Dict[str, LocalGraphMemoryUpdater] = {}
    _lock = threading.Lock()

    @classmethod
    def create_updater(
        cls, simulation_id: str, graph_id: str
    ) -> LocalGraphMemoryUpdater:
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
            updater = LocalGraphMemoryUpdater(graph_id)
            updater.start()
            cls._updaters[simulation_id] = updater
            logger.info(
                f"로컬 그래프 메모리 업데이트기 생성: sim={simulation_id}, graph={graph_id}"
            )
            return updater

    @classmethod
    def get_updater(cls, simulation_id: str) -> Optional[LocalGraphMemoryUpdater]:
        return cls._updaters.get(simulation_id)

    @classmethod
    def stop_updater(cls, simulation_id: str):
        with cls._lock:
            if simulation_id in cls._updaters:
                cls._updaters[simulation_id].stop()
                del cls._updaters[simulation_id]

    _stop_all_done = False

    @classmethod
    def stop_all(cls):
        if cls._stop_all_done:
            return
        cls._stop_all_done = True
        with cls._lock:
            for sid, updater in list(cls._updaters.items()):
                try:
                    updater.stop()
                except Exception as e:
                    logger.error(f"업데이트기 중지 실패: sim={sid}, error={e}")
            cls._updaters.clear()

    @classmethod
    def get_all_stats(cls) -> Dict[str, Dict[str, Any]]:
        return {sid: u.get_stats() for sid, u in cls._updaters.items()}
