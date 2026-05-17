"""本地 JSON 图谱客户端 — 无需 Docker / Neo4j，直接读取 data/raw/ai_knowledge.json。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data" / "raw" / "ai_knowledge.json"


class LocalGraphClient:
    """从 JSON 文件加载图谱到内存，接口与 Neo4jClient 保持一致。"""

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or DEFAULT_DATA
        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        self._entities: dict[str, dict[str, Any]] = {e["name"]: e for e in data["entities"]}
        self._relations: list[dict[str, Any]] = data["relations"]

    def close(self) -> None:
        pass

    def verify_connection(self) -> bool:
        return len(self._entities) > 0

    def run_query(self, query: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError("本地模式不支持 Cypher 查询，请使用封装好的方法")

    def clear_graph(self) -> None:
        pass

    def get_statistics(self) -> dict[str, Any]:
        type_counts: dict[str, int] = {}
        for entity in self._entities.values():
            t = entity.get("type", "Unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "node_count": len(self._entities),
            "relation_count": len(self._relations),
            "entity_types": type_counts,
        }

    def get_all_entities(self, limit: int = 100) -> list[dict[str, Any]]:
        entities = sorted(self._entities.values(), key=lambda e: e["name"])
        return entities[:limit]

    def _append_rel(self, rel: dict, nodes: dict, edges: list, seen_edges: set) -> None:
        source_name = rel["source"]
        target_name = rel["target"]
        for name in (source_name, target_name):
            entity = self._entities.get(name)
            if entity:
                node_id = entity.get("id") or entity["name"]
                nodes[node_id] = {
                    "id": node_id,
                    "name": entity["name"],
                    "type": entity.get("type"),
                    "description": entity.get("description", ""),
                    "reference": entity.get("reference", ""),
                }

        source = self._entities.get(source_name)
        target = self._entities.get(target_name)
        if source and target:
            edge_key = (source.get("id") or source["name"], target.get("id") or target["name"], rel.get("type", ""))
            if edge_key in seen_edges:
                return
            seen_edges.add(edge_key)
            edges.append(
                {
                    "source": source.get("id") or source["name"],
                    "target": target.get("id") or target["name"],
                    "type": rel.get("type", ""),
                    "description": rel.get("description", ""),
                    "reference": rel.get("reference", ""),
                }
            )

    def get_subgraph(
        self, entity_name: str | None = None, limit: int = 50, hops: int = 2
    ) -> dict[str, list]:
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        seen_edges: set[tuple] = set()

        if entity_name:
            hop1 = [r for r in self._relations if entity_name in (r["source"], r["target"])]
            combined = list(hop1)
            if hops >= 2:
                neighbors = set()
                for r in hop1:
                    neighbors.add(r["source"])
                    neighbors.add(r["target"])
                neighbors.discard(entity_name)
                hop2 = [
                    r
                    for r in self._relations
                    if r["source"] in neighbors or r["target"] in neighbors
                ]
                combined = hop1 + hop2
            for rel in combined:
                if len(edges) >= limit:
                    break
                self._append_rel(rel, nodes, edges, seen_edges)
            return {"nodes": list(nodes.values()), "edges": edges}

        count = 0
        for rel in self._relations:
            if count >= limit:
                break

            source_name = rel["source"]
            target_name = rel["target"]

            for name in (source_name, target_name):
                entity = self._entities.get(name)
                if entity:
                    node_id = entity.get("id") or entity["name"]
                    nodes[node_id] = {
                        "id": node_id,
                        "name": entity["name"],
                        "type": entity.get("type"),
                        "description": entity.get("description", ""),
                        "reference": entity.get("reference", ""),
                    }

            source = self._entities.get(source_name)
            target = self._entities.get(target_name)
            if source and target:
                edges.append(
                    {
                        "source": source.get("id") or source["name"],
                        "target": target.get("id") or target["name"],
                        "type": rel.get("type", ""),
                        "description": rel.get("description", ""),
                        "reference": rel.get("reference", ""),
                    }
                )
                count += 1

        return {"nodes": list(nodes.values()), "edges": edges}

    def search_entity(self, keyword: str) -> list[dict[str, Any]]:
        results = []
        for entity in self._entities.values():
            if keyword in entity["name"] or keyword in entity.get("description", ""):
                results.append(
                    {
                        "name": entity["name"],
                        "type": entity.get("type"),
                        "description": entity.get("description"),
                        "reference": entity.get("reference", ""),
                    }
                )
            if len(results) >= 10:
                break
        return results

    def get_entity_by_name(self, name: str) -> dict[str, Any] | None:
        entity = self._entities.get(name)
        if not entity:
            return None
        return {
            "name": entity["name"],
            "type": entity.get("type"),
            "description": entity.get("description"),
            "year": entity.get("year"),
            "country": entity.get("country"),
            "reference": entity.get("reference", ""),
        }

    def get_outgoing_relations(self, name: str) -> list[dict[str, Any]]:
        results = []
        for rel in self._relations:
            if rel["source"] == name:
                target = self._entities.get(rel["target"], {})
                results.append(
                    {
                        "relation": rel["type"],
                        "target": rel["target"],
                        "target_desc": target.get("description", ""),
                    }
                )
        return results

    def get_incoming_relations(self, name: str) -> list[dict[str, Any]]:
        results = []
        for rel in self._relations:
            if rel["target"] == name:
                source = self._entities.get(rel["source"], {})
                results.append(
                    {
                        "source": rel["source"],
                        "relation": rel["type"],
                        "source_desc": source.get("description", ""),
                    }
                )
        return results

    def get_entities_by_relation(self, name: str, relation: str, direction: str = "out") -> list[str]:
        names: list[str] = []
        for rel in self._relations:
            if rel["type"] != relation:
                continue
            if direction == "out" and rel["source"] == name:
                names.append(rel["target"])
            elif direction == "in" and rel["target"] == name:
                names.append(rel["source"])
        return names
