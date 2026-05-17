"""将 JSON 数据导入 Neo4j 知识图谱（仅 graph_mode=neo4j 时需要运行）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings  # noqa: E402
from src.kg.neo4j_client import Neo4jClient  # noqa: E402


def load_data() -> dict:
    data_path = ROOT / "data" / "raw" / "ai_knowledge.json"
    with data_path.open(encoding="utf-8") as f:
        return json.load(f)


def import_to_neo4j() -> None:
    settings = get_settings()

    if settings.graph_mode == "local":
        print("当前为【本地模式】(GRAPH_MODE=local)，数据已内置在 data/raw/ai_knowledge.json")
        print("无需运行本脚本，直接在 PyCharm 中运行 run_server.py 即可。")
        print("\n若需使用 Neo4j 图数据库，请将 .env 中 GRAPH_MODE 改为 neo4j 后再运行本脚本。")
        return

    data = load_data()
    client = Neo4jClient()

    try:
        print("正在连接 Neo4j...")
        client.verify_connection()
        print("连接成功，清空旧数据...")
        client.clear_graph()

        print(f"导入 {len(data['entities'])} 个实体...")
        for entity in data["entities"]:
            row = {**entity, "reference": entity.get("reference", "")}
            client.run_query(
                """
                CREATE (n:Entity {
                    id: $id,
                    name: $name,
                    type: $type,
                    description: $description,
                    year: $year,
                    country: $country,
                    reference: $reference
                })
                """,
                row,
            )

        print(f"导入 {len(data['relations'])} 条关系...")
        for rel in data["relations"]:
            rel_row = {**rel, "reference": rel.get("reference", "")}
            client.run_query(
                """
                MATCH (s:Entity {name: $source}), (t:Entity {name: $target})
                CREATE (s)-[:RELATION {type: $type, description: $description, reference: $reference}]->(t)
                """,
                rel_row,
            )

        stats = client.get_statistics()
        print("\n导入完成！")
        print(f"  节点数: {stats['node_count']}")
        print(f"  关系数: {stats['relation_count']}")
        print(f"  实体类型分布: {stats['entity_types']}")
    finally:
        client.close()


if __name__ == "__main__":
    import_to_neo4j()
