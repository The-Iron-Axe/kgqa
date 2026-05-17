"""基于知识图谱的问答引擎（不依赖大模型）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.kg.graph_client_factory import GraphClient, create_graph_client
from src.qa.intent_parser import IntentParser, ParsedIntent


@dataclass
class QAResult:
    question: str
    answer: str
    intent: str
    entity: str | None
    confidence: float
    evidence: list[str] = field(default_factory=list)
    mode: str = "kg_only"
    matched_entities: list[str] = field(default_factory=list)


class KGQAEngine:
    """通过 Cypher 查询与模板生成实现结构化问答。"""

    def __init__(self, client: GraphClient | None = None) -> None:
        self.client = client or create_graph_client()
        entities = self.client.get_all_entities(limit=200)
        names = [e["name"] for e in entities]
        self.parser = IntentParser(names)

    def close(self) -> None:
        self.client.close()

    def answer(self, question: str) -> QAResult:
        intent = self.parser.parse(question)
        matched_entities = self.parser.extract_all_entities(question)

        if not intent.entity:
            return QAResult(
                question=question,
                answer="抱歉，未在知识图谱中找到相关实体，请尝试使用图谱中的关键词提问。",
                intent=intent.intent,
                entity=None,
                confidence=0.0,
                matched_entities=matched_entities,
            )

        handlers = {
            "entity_info": self._answer_entity_info,
            "entity_year": self._answer_entity_year,
            "entity_country": self._answer_entity_country,
            "org_products": self._answer_org_products,
            "person_work": self._answer_person_work,
            "product_org": self._answer_product_org,
            "category_members": self._answer_category_members,
            "application_tech": self._answer_application_tech,
            "relation_query": self._answer_relation_query,
            "entity_explore": self._answer_entity_explore,
        }

        handler = handlers.get(intent.intent, self._answer_entity_explore)
        result = handler(question, intent)
        if not result.matched_entities:
            result.matched_entities = matched_entities
        return result

    def _answer_entity_info(self, question: str, intent: ParsedIntent) -> QAResult:
        entity = self.client.get_entity_by_name(intent.entity)  # type: ignore[arg-type]
        if not entity:
            return self._not_found(question, intent)

        answer = f"{entity['name']}是{entity['type']}，{entity['description']}。"
        if entity.get("year"):
            answer += f" 出现于{entity['year']}年。"
        if entity.get("country"):
            answer += f" 相关国家/地区：{entity['country']}。"
        if entity.get("reference"):
            answer += f" 参考文献：{entity['reference']}"

        evidence = [entity["description"]]
        if entity.get("reference"):
            evidence.append(entity["reference"])

        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.95,
            evidence=evidence,
        )

    def _answer_entity_year(self, question: str, intent: ParsedIntent) -> QAResult:
        entity = self.client.get_entity_by_name(intent.entity)  # type: ignore[arg-type]
        if not entity or not entity.get("year"):
            return self._not_found(question, intent)

        answer = f"{entity['name']}的相关年份是{entity['year']}年。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.98,
            evidence=[str(entity["year"])],
        )

    def _answer_entity_country(self, question: str, intent: ParsedIntent) -> QAResult:
        entity = self.client.get_entity_by_name(intent.entity)  # type: ignore[arg-type]
        if not entity or not entity.get("country"):
            return self._not_found(question, intent)

        answer = f"{entity['name']}的相关国家/地区是{entity['country']}。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.95,
            evidence=[entity["country"]],
        )

    def _answer_org_products(self, question: str, intent: ParsedIntent) -> QAResult:
        products = self.client.get_entities_by_relation(intent.entity, "研发", "out")  # type: ignore[arg-type]
        if not products:
            return self._not_found(question, intent)

        answer = f"{intent.entity}研发的AI产品/技术包括：{'、'.join(products)}。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.92,
            evidence=products,
        )

    def _answer_person_work(self, question: str, intent: ParsedIntent) -> QAResult:
        works = self.client.get_entities_by_relation(intent.entity, "提出", "out")  # type: ignore[arg-type]
        if not works:
            works = self.client.get_entities_by_relation(intent.entity, "研究", "out")  # type: ignore[arg-type]

        if not works:
            return self._not_found(question, intent)

        answer = f"{intent.entity}的主要成果/研究方向包括：{'、'.join(works)}。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.9,
            evidence=works,
        )

    def _answer_product_org(self, question: str, intent: ParsedIntent) -> QAResult:
        orgs = self.client.get_entities_by_relation(intent.entity, "研发", "in")  # type: ignore[arg-type]
        if not orgs:
            return self._not_found(question, intent)

        answer = f"{intent.entity}由{'、'.join(orgs)}研发。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.93,
            evidence=orgs,
        )

    def _answer_category_members(self, question: str, intent: ParsedIntent) -> QAResult:
        members = self.client.get_entities_by_relation(intent.entity, "属于", "in")  # type: ignore[arg-type]
        if not members:
            return self._not_found(question, intent)

        answer = f"属于{intent.entity}的技术包括：{'、'.join(members)}。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.88,
            evidence=members,
        )

    def _answer_application_tech(self, question: str, intent: ParsedIntent) -> QAResult:
        techs = self.client.get_entities_by_relation(intent.entity, "应用", "in")  # type: ignore[arg-type]
        if not techs:
            techs = self.client.get_entities_by_relation(intent.entity, "应用", "out")  # type: ignore[arg-type]

        if not techs:
            outgoing = self.client.get_outgoing_relations(intent.entity)  # type: ignore[arg-type]
            techs = [r["target"] for r in outgoing if r["relation"] == "应用"]

        if not techs:
            return self._not_found(question, intent)

        answer = f"{intent.entity}应用/涉及的技术包括：{'、'.join(techs)}。"
        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.87,
            evidence=techs,
        )

    def _answer_relation_query(self, question: str, intent: ParsedIntent) -> QAResult:
        relation = intent.relation or "属于"

        # 优先出边
        targets = self.client.get_entities_by_relation(intent.entity, relation, "out")  # type: ignore[arg-type]
        direction = "out"
        if not targets:
            targets = self.client.get_entities_by_relation(intent.entity, relation, "in")  # type: ignore[arg-type]
            direction = "in"

        if not targets:
            return self._not_found(question, intent)

        if direction == "out":
            answer = f"{intent.entity}「{relation}」：{'、'.join(targets)}。"
        else:
            answer = f"「{relation}」{intent.entity}的有：{'、'.join(targets)}。"

        return QAResult(
            question=question,
            answer=answer,
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.9,
            evidence=targets,
        )

    def _answer_entity_explore(self, question: str, intent: ParsedIntent) -> QAResult:
        entity = self.client.get_entity_by_name(intent.entity)  # type: ignore[arg-type]
        if not entity:
            return self._not_found(question, intent)

        outgoing = self.client.get_outgoing_relations(intent.entity)  # type: ignore[arg-type]
        incoming = self.client.get_incoming_relations(intent.entity)  # type: ignore[arg-type]

        parts = [f"{entity['name']}：{entity['description']}"]
        evidence = [entity["description"]]

        if outgoing:
            rel_text = "；".join(f"{r['relation']}→{r['target']}" for r in outgoing[:5])
            parts.append(f"关联出边：{rel_text}")
            evidence.extend(r["target"] for r in outgoing)

        if incoming:
            rel_text = "；".join(f"{r['source']}→{r['relation']}" for r in incoming[:5])
            parts.append(f"关联入边：{rel_text}")
            evidence.extend(r["source"] for r in incoming)

        return QAResult(
            question=question,
            answer=" ".join(parts),
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.75,
            evidence=evidence,
        )

    def _not_found(self, question: str, intent: ParsedIntent) -> QAResult:
        return QAResult(
            question=question,
            answer=f"知识图谱中暂未找到与「{intent.entity}」相关的足够信息。",
            intent=intent.intent,
            entity=intent.entity,
            confidence=0.2,
        )

    def get_kg_context(self, entity: str, extended: bool = False) -> str:
        """为大模型提供结构化上下文；extended=True 时附带邻居实体摘要。"""
        entity_info = self.client.get_entity_by_name(entity)
        if not entity_info:
            return ""

        outgoing = self.client.get_outgoing_relations(entity)
        incoming = self.client.get_incoming_relations(entity)

        lines = [
            f"实体：{entity_info['name']}",
            f"类型：{entity_info['type']}",
            f"描述：{entity_info['description']}",
        ]
        if entity_info.get("year"):
            lines.append(f"年份：{entity_info['year']}")
        if entity_info.get("country"):
            lines.append(f"国家/地区：{entity_info['country']}")
        if entity_info.get("reference"):
            lines.append(f"参考文献：{entity_info['reference']}")

        lines.append("出边关系：")
        for rel in outgoing:
            lines.append(f"  {entity} -[{rel['relation']}]-> {rel['target']}")
        lines.append("入边关系：")
        for rel in incoming:
            lines.append(f"  {rel['source']} -[{rel['relation']}]-> {entity}")

        if extended:
            neighbor_names: set[str] = set()
            for rel in outgoing:
                neighbor_names.add(rel["target"])
            for rel in incoming:
                neighbor_names.add(rel["source"])

            if neighbor_names:
                lines.append("关联实体摘要：")
                for name in sorted(neighbor_names):
                    info = self.client.get_entity_by_name(name)
                    if info and info.get("description"):
                        lines.append(f"  · {name}（{info.get('type', '')}）：{info['description']}")

        return "\n".join(lines)
