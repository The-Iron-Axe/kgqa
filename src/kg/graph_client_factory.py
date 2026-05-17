"""根据配置创建图谱客户端。"""

from __future__ import annotations

import logging
from typing import Union

from config.settings import Settings, get_settings
from src.kg.local_graph_client import LocalGraphClient
from src.kg.neo4j_client import Neo4jClient

GraphClient = Union[Neo4jClient, LocalGraphClient]

logger = logging.getLogger(__name__)

# 实际运行模式（Neo4j 不可用时可能从 neo4j 回退为 local）
_runtime_graph_mode: str | None = None


def get_runtime_graph_mode(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return _runtime_graph_mode or settings.graph_mode


def create_graph_client(settings: Settings | None = None) -> GraphClient:
    global _runtime_graph_mode
    settings = settings or get_settings()

    if settings.graph_mode == "local":
        _runtime_graph_mode = "local"
        return LocalGraphClient()

    client = Neo4jClient()
    try:
        client.verify_connection()
        _runtime_graph_mode = "neo4j"
        return client
    except Exception as exc:
        logger.warning("Neo4j 连接失败，已自动回退本地 JSON 模式: %s", exc)
        print(
            "\n[提示] Neo4j 未启动（localhost:7687 拒绝连接），"
            "已自动使用本地 JSON 图谱。\n"
            "      若需 Neo4j：请先启动数据库；或在 .env 中设置 GRAPH_MODE=local\n"
        )
        _runtime_graph_mode = "local"
        return LocalGraphClient()


def get_graph_db_display_name(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    mode = get_runtime_graph_mode(settings)
    if mode == "local":
        return "本地 JSON 内存图谱（无需安装数据库）"
    return settings.graph_db_name
