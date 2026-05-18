"""基于规则的中文问句意图解析。"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedIntent:
    intent: str
    entity: str | None = None
    relation: str | None = None
    raw_question: str = ""


# 常见关系词映射
RELATION_KEYWORDS = {
    "属于": "属于",
    "基于": "基于",
    "使用架构": "使用架构",
    "采用架构": "使用架构",
    "架构": "使用架构",
    "应用": "应用",
    "研发": "研发",
    "提出": "提出",
    "支撑": "支撑",
    "依赖": "依赖",
    "扩展": "扩展",
    "实现": "实现",
    "改进": "改进",
    "优化": "优化",
    "优化指标": "优化指标",
    "提升": "提升",
    "降低": "降低",
    "缓解": "缓解",
    "解决": "缓解",
    "推动": "推动",
    "提供": "提供",
    "研究": "研究",
}


class IntentParser:
    """解析用户自然语言问题，映射到图谱查询意图。"""

    def __init__(self, entity_names: list[str]) -> None:
        self.entity_names = sorted(entity_names, key=len, reverse=True)

    def extract_entity(self, question: str) -> str | None:
        matched = self.extract_all_entities(question)
        return matched[0] if matched else None

    def extract_all_entities(self, question: str) -> list[str]:
        """从问句中匹配所有图谱实体（长名优先，避免短词重复覆盖）。"""
        if not question:
            return []
        occupied = [False] * len(question)
        found: list[str] = []
        for name in self.entity_names:
            start = 0
            while True:
                idx = question.find(name, start)
                if idx < 0:
                    break
                span = range(idx, idx + len(name))
                if not any(occupied[i] for i in span):
                    found.append(name)
                    for i in span:
                        occupied[i] = True
                start = idx + 1
        return found

    def parse(self, question: str) -> ParsedIntent:
        entity = self.extract_entity(question)
        q = question.strip()

        # 实体基本信息
        if re.search(r"(是什么|什么是|介绍一下|描述|定义)", q):
            return ParsedIntent("entity_info", entity, raw_question=q)

        # 年份
        if re.search(r"(哪年|何时|什么时候|年份|发布于)", q):
            return ParsedIntent("entity_year", entity, raw_question=q)

        # 国家/地区
        if re.search(r"(哪个国家|哪国|来自哪里|国家)", q):
            return ParsedIntent("entity_country", entity, raw_question=q)

        # 机构研发产品
        if re.search(r"(研发了哪些|开发了哪些|推出了哪些|有哪些产品)", q):
            return ParsedIntent("org_products", entity, raw_question=q)

        # 人物成果
        if re.search(r"(提出了什么|发明了什么|著作|贡献)", q):
            return ParsedIntent("person_work", entity, raw_question=q)

        # 产品归属机构
        if re.search(r"(是谁研发的|谁研发的|哪个公司|哪家公司)", q):
            return ParsedIntent("product_org", entity, raw_question=q)

        # 类别成员：哪些X属于Y
        if re.search(r"(哪些.*属于|什么属于|有哪些.*属于)", q):
            return ParsedIntent("category_members", entity, raw_question=q)

        # 技术路径/解决方案：面向架构、优化、幻觉缓解等技术型问题
        if re.search(r"(技术路径|解决方案|技术方案|有哪些方法|哪些方法|有哪些技术|哪些技术|哪些架构|使用了哪些架构|采用了哪些架构|如何解决|怎么解决|如何缓解|怎么缓解|如何增强|怎么增强)", q):
            if "幻觉" in q and "模型幻觉" in self.entity_names:
                entity = "模型幻觉"
            return ParsedIntent("technical_path", entity, raw_question=q)

        # 应用领域使用了哪些技术
        if re.search(r"(应用了哪些|使用了哪些|用到哪些|依赖哪些)", q):
            return ParsedIntent("application_tech", entity, raw_question=q)

        # 关系查询：X基于/属于/支撑 Y
        for keyword, rel_type in RELATION_KEYWORDS.items():
            if keyword in q:
                return ParsedIntent("relation_query", entity, rel_type, raw_question=q)

        # 默认：实体信息 + 关联探索
        return ParsedIntent("entity_explore", entity, raw_question=q)
