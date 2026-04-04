from pathlib import Path

from pydantic_settings import BaseSettings


def _find_env_file() -> str | None:
    for candidate in [Path(".env"), Path("../.env")]:
        if candidate.exists():
            return str(candidate)
    return None


class Settings(BaseSettings):
    database_url: str = "postgresql://osint:osint_dev@localhost:5432/osint_simulator"
    shadowbroker_url: str = "http://localhost:8000"
    dozerdb_uri: str = "bolt://localhost:7687"
    dozerdb_user: str = "neo4j"
    dozerdb_password: str = "mirofish"
    llm_api_key: str = ""
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    service_port: int = 5001

    model_config = {"env_file": _find_env_file(), "extra": "ignore"}


settings = Settings()
