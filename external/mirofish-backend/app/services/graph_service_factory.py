from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.graph_service_factory")


def get_graph_builder():
    if Config.USE_LOCAL_GRAPH:
        from .local_graph_builder import LocalGraphBuilderService

        return LocalGraphBuilderService()
    else:
        from .graph_builder import GraphBuilderService

        return GraphBuilderService(api_key=Config.ZEP_API_KEY)


def get_entity_reader():
    if Config.USE_LOCAL_GRAPH:
        from .local_entity_reader import LocalEntityReader

        return LocalEntityReader()
    else:
        from .zep_entity_reader import ZepEntityReader

        return ZepEntityReader()


def get_tools_service(llm_client=None):
    if Config.USE_LOCAL_GRAPH:
        from .local_tools_service import LocalToolsService

        return LocalToolsService(llm_client=llm_client)
    else:
        from .zep_tools import ZepToolsService

        return ZepToolsService(llm_client=llm_client)


def get_graph_memory_manager():
    if Config.USE_LOCAL_GRAPH:
        from .local_graph_memory_updater import LocalGraphMemoryManager

        return LocalGraphMemoryManager
    else:
        from .zep_graph_memory_updater import ZepGraphMemoryManager

        return ZepGraphMemoryManager
