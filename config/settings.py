"""项目全局配置。"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 图谱模式：neo4j=Neo4j 图数据库（答辩正式模式） | local=临时预览用
    graph_mode: str = "neo4j"

    # Neo4j（仅 graph_mode=neo4j 时需要）
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "kgqa123456"

    # LLM（可选）
    llm_enabled: bool = False
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_model: str = "deepseek-chat"
    # rich=图谱锚定+常识扩展（答辩演示推荐）| strict=仅复述图谱
    llm_answer_style: str = "rich"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 1024
    # 批量评测加速（scripts/02_run_evaluation.py）
    eval_llm_workers: int = 6
    eval_llm_fast: bool = True
    eval_llm_max_tokens: int = 384

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8001

    # 项目元信息（答辩报告可直接引用）
    project_name: str = "中国先进人工智能技术知识图谱问答系统"
    domain: str = "人工智能"
    graph_db_name: str = "Neo4j 5.26"


@lru_cache
def get_settings() -> Settings:
    return Settings()
