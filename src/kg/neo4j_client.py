"""Neo4j 图数据库客户端。"""

from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase, Driver

from config.settings import get_settings


class Neo4jClient:
    """封装 Neo4j 连接与常用图查询。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._driver: Driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        self._driver.close()

    def verify_connection(self) -> bool:
        self._driver.verify_connectivity()
        return True

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def clear_graph(self) -> None:
        self.run_query("MATCH (n) DETACH DELETE n")

    def get_statistics(self) -> dict[str, int]:
        node_count = self.run_query("MATCH (n) RETURN count(n) AS count")[0]["count"]
        rel_count = self.run_query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]
        type_stats = self.run_query(
            """
            MATCH (n)
            RETURN n.type AS type, count(n) AS count
            ORDER BY count DESC
            """
        )
        return {
            "node_count": node_count,
            "relation_count": rel_count,
            "entity_types": {row["type"]: row["count"] for row in type_stats},
        }

    def get_all_entities(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (n:Entity)
            RETURN n.id AS id, n.name AS name, n.type AS type,
                   n.description AS description, n.year AS year, n.country AS country,
                   n.reference AS reference
            ORDER BY n.name
            LIMIT $limit
            """,
            {"limit": limit},
        )

    def get_subgraph(
        self, entity_name: str | None = None, limit: int = 50, hops: int = 2
    ) -> dict[str, list]:
        # 显式返回标量字段，避免 Neo4j 2026 驱动下 RETURN n,r,m 时 r 被序列化为 tuple
        if entity_name:
            hop_max = max(1, min(int(hops), 2))
            query = f"""
            MATCH (c:Entity {{name: $name}})
            MATCH p = (c)-[:RELATION*1..{hop_max}]-(m:Entity)
            UNWIND relationships(p) AS r
            WITH DISTINCT startNode(r) AS sn, r, endNode(r) AS en
            RETURN
                sn.id AS n_id, sn.name AS n_name, sn.type AS n_type,
                sn.description AS n_description, sn.reference AS n_reference,
                en.id AS m_id, en.name AS m_name, en.type AS m_type,
                en.description AS m_description, en.reference AS m_reference,
                r.type AS rel_type, r.description AS rel_description, r.reference AS rel_reference,
                sn.id AS src_id, en.id AS tgt_id
            LIMIT $limit
            """
            params = {"name": entity_name, "limit": limit}
        else:
            query = """
            MATCH (n:Entity)-[r:RELATION]->(m:Entity)
            RETURN
                n.id AS n_id, n.name AS n_name, n.type AS n_type,
                n.description AS n_description, n.reference AS n_reference,
                m.id AS m_id, m.name AS m_name, m.type AS m_type,
                m.description AS m_description, m.reference AS m_reference,
                r.type AS rel_type, r.description AS rel_description, r.reference AS rel_reference,
                startNode(r).id AS src_id, endNode(r).id AS tgt_id
            LIMIT $limit
            """
            params = {"limit": limit}

        records = self.run_query(query, params)
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        for row in records:
            for prefix in ("n", "m"):
                node_id = row.get(f"{prefix}_id") or row.get(f"{prefix}_name")
                if not node_id:
                    continue
                nodes[node_id] = {
                    "id": node_id,
                    "name": row.get(f"{prefix}_name"),
                    "type": row.get(f"{prefix}_type"),
                    "description": row.get(f"{prefix}_description") or "",
                    "reference": row.get(f"{prefix}_reference") or "",
                }

            src_id = row.get("src_id") or row.get("n_id")
            tgt_id = row.get("tgt_id") or row.get("m_id")
            if src_id and tgt_id:
                edges.append(
                    {
                        "source": src_id,
                        "target": tgt_id,
                        "type": row.get("rel_type") or "",
                        "description": row.get("rel_description") or "",
                        "reference": row.get("rel_reference") or "",
                    }
                )

        return {"nodes": list(nodes.values()), "edges": edges}

    def search_entity(self, keyword: str) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (n:Entity)
            WHERE n.name CONTAINS $keyword OR n.description CONTAINS $keyword
            RETURN n.name AS name, n.type AS type, n.description AS description, n.reference AS reference
            """,
            {"keyword": keyword},
        )

    def get_entity_by_name(self, name: str) -> dict[str, Any] | None:
        rows = self.run_query(
            """
            MATCH (n:Entity {name: $name})
            RETURN n.name AS name, n.type AS type, n.description AS description,
                   n.year AS year, n.country AS country, n.reference AS reference
            """,
            {"name": name},
        )
        return rows[0] if rows else None

    def get_outgoing_relations(self, name: str) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (n:Entity {name: $name})-[r:RELATION]->(m:Entity)
            RETURN r.type AS relation, m.name AS target, m.description AS target_desc
            """,
            {"name": name},
        )

    def get_incoming_relations(self, name: str) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (n:Entity)-[r:RELATION]->(m:Entity {name: $name})
            RETURN n.name AS source, r.type AS relation, n.description AS source_desc
            """,
            {"name": name},
        )

    def get_entities_by_relation(self, name: str, relation: str, direction: str = "out") -> list[str]:
        if direction == "out":
            rows = self.run_query(
                """
                MATCH (n:Entity {name: $name})-[r:RELATION {type: $relation}]->(m:Entity)
                RETURN m.name AS name
                """,
                {"name": name, "relation": relation},
            )
        else:
            rows = self.run_query(
                """
                MATCH (n:Entity)-[r:RELATION {type: $relation}]->(m:Entity {name: $name})
                RETURN n.name AS name
                """,
                {"name": name, "relation": relation},
            )
        return [row["name"] for row in rows]
