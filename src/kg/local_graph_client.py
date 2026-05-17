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
        for rel in self._select_connected_relations(limit):
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

    def _select_connected_relations(self, limit: int) -> list[dict[str, Any]]:
        """Pick a connected full-graph sample so the visualization is not split."""
        picked: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        selected_nodes: set[str] = set()
        endpoint_counts: dict[str, int] = {}

        priority_types = ["研发", "基于", "实现", "属于", "应用", "支撑", "推动", "规范", "研究", "增强"]
        priority_rank = {rel_type: idx for idx, rel_type in enumerate(priority_types)}

        entity_names = set(self._entities)
        anchors = [
            "人工智能",
            "大语言模型",
            "深度学习",
            "机器学习",
            "计算机视觉",
            "自然语言处理",
            "知识图谱",
            "AI Agent",
            "算力基础设施",
        ]
        root = next((name for name in anchors if name in entity_names), None)
        if not root:
            root = self._relations[0]["source"] if self._relations else ""
        selected_nodes.add(root)
        root_degree_limit = 8

        def relation_key(rel: dict[str, Any]) -> tuple[int, int, str]:
            rel_type = rel.get("type", "")
            touches_anchor = rel["source"] in anchors or rel["target"] in anchors
            touches_root = root in (rel["source"], rel["target"])
            return (
                priority_rank.get(rel_type, len(priority_rank)),
                0 if touches_anchor and not touches_root else 1 if touches_anchor else 2,
                rel["source"] + rel["target"],
            )

        def try_add(rel: dict[str, Any], *, force: bool = False) -> bool:
            key = (rel["source"], rel["target"], rel.get("type", ""))
            if key in seen:
                return False
            if not force and root in (rel["source"], rel["target"]):
                if endpoint_counts.get(root, 0) >= root_degree_limit:
                    return False
            picked.append(rel)
            seen.add(key)
            selected_nodes.add(rel["source"])
            selected_nodes.add(rel["target"])
            endpoint_counts[rel["source"]] = endpoint_counts.get(rel["source"], 0) + 1
            endpoint_counts[rel["target"]] = endpoint_counts.get(rel["target"], 0) + 1
            return True

        # First connect several second-level cores to the root. This keeps one
        # connected graph while preventing "人工智能" from owning every edge.
        for anchor in anchors[1:]:
            bridge = next(
                (
                    rel
                    for rel in self._relations
                    if anchor in (rel["source"], rel["target"])
                    and root in (rel["source"], rel["target"])
                ),
                None,
            )
            if bridge:
                try_add(bridge, force=True)
            if endpoint_counts.get(root, 0) >= root_degree_limit:
                break

        # Grow one connected component from all selected cores. Endpoint caps are
        # relaxed in passes, but the root node keeps a strict cap.
        for cap in (5, 10, 18, 32, 9999):
            progressed = True
            while progressed and len(picked) < limit:
                progressed = False
                candidates = [
                    rel
                    for rel in self._relations
                    if (rel["source"] in selected_nodes) ^ (rel["target"] in selected_nodes)
                    and not (
                        root in (rel["source"], rel["target"])
                        and endpoint_counts.get(root, 0) >= root_degree_limit
                    )
                    and endpoint_counts.get(rel["source"], 0) < cap
                    and endpoint_counts.get(rel["target"], 0) < cap
                ]
                candidates.sort(key=relation_key)

                for rel in candidates:
                    if try_add(rel):
                        progressed = True
                    if len(picked) >= limit:
                        return picked

        # Fill remaining slots with intra-component edges. These keep the sample
        # connected because both endpoints are already in the selected component.
        for rel in sorted(self._relations, key=relation_key):
            if len(picked) >= limit:
                break
            if rel["source"] in selected_nodes and rel["target"] in selected_nodes:
                try_add(rel)

        return picked

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
