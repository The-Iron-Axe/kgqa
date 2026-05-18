"""可选的大模型增强问答（基于图谱证据组织自然语言回答）。"""

from __future__ import annotations

from openai import OpenAI

from config.settings import get_settings
from src.qa.kg_qa_engine import KGQAEngine, QAResult

STRICT_PROMPT = """你是中国先进人工智能技术领域的问答助手。

【知识图谱证据（必须准确采用，不得与下列事实矛盾）】
{context}

【用户问题】
{question}

请严格基于图谱证据，用简洁、准确的中文回答。图谱未提及的内容不要编造。"""

RICH_PROMPT = """你是中国先进人工智能技术领域的专业问答助手，擅长把知识图谱检索结果扩展成清晰、完整的讲解。

【知识图谱检索结果（核心事实，必须保留且不得矛盾）】
{context}

【用户问题】
{question}

【回答要求】
1. **以图谱信息为准确核心**：实体属性、关系、年份、机构、产品等必须与图谱一致。
2. **允许适当扩展**：在不违背图谱事实的前提下，可结合领域常识补充：
   - 基本概念与工作原理
   - 典型应用场景与代表案例
   - 与相关技术/产品的联系
   - 在中国的发展现状或产业意义（若适用）
3. **结构清晰**：分 2～4 个自然段或分点说明，介绍类问题建议 200～400 字。
4. **区分来源**：扩展的通用知识放在最后一段，以「补充说明：」开头，并注明「以下内容来自模型常识扩展，非图谱直接存储」。
5. 语言自然流畅，适合课程答辩演示，避免只复读一行定义。

请用中文回答："""


class LLMQAEngine:
    """图谱证据增强模式：先做结构化图谱问答，再调用大模型润色表达。"""

    def __init__(self, kg_engine: KGQAEngine | None = None) -> None:
        self.kg_engine = kg_engine or KGQAEngine()
        settings = get_settings()
        self.enabled = settings.llm_enabled and bool(settings.llm_api_key)
        self.model = settings.llm_model
        self.answer_style = settings.llm_answer_style
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        self._client: OpenAI | None = None

        if self.enabled:
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_base_url,
            )

    def close(self) -> None:
        self.kg_engine.close()

    def _build_context(self, kg_result: QAResult, *, extended: bool = True) -> str:
        parts = [f"图谱初步答案：{kg_result.answer}"]
        if kg_result.entity:
            parts.append(self.kg_engine.get_kg_context(kg_result.entity, extended=extended))
        if kg_result.evidence:
            parts.append("证据关键词：" + "；".join(kg_result.evidence))
        return "\n".join(parts)

    def _build_prompt(self, question: str, context: str, *, strict: bool = False) -> str:
        if strict:
            template = STRICT_PROMPT
        else:
            template = RICH_PROMPT if self.answer_style == "rich" else STRICT_PROMPT
        return template.format(context=context, question=question)

    def answer(self, question: str, *, fast: bool = False) -> QAResult:
        """fast=True：评测批跑时使用，缩短上下文与生成长度。"""
        kg_result = self.kg_engine.answer(question)

        if not self.enabled or not self._client:
            kg_result.mode = "kg_only"
            return kg_result

        context = self._build_context(kg_result, extended=not fast)
        prompt = self._build_prompt(question, context, strict=fast)
        settings = get_settings()
        max_tokens = settings.eval_llm_max_tokens if fast else self.max_tokens
        temperature = 0.3 if fast else self.temperature

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            llm_answer = response.choices[0].message.content or kg_result.answer
            if fast:
                mode = "kg_llm_fast"
            else:
                mode = "kg_llm_rich" if self.answer_style == "rich" else "kg_llm"
            return QAResult(
                question=question,
                answer=llm_answer.strip(),
                intent=kg_result.intent,
                entity=kg_result.entity,
                confidence=min(kg_result.confidence + 0.05, 0.99),
                evidence=kg_result.evidence,
                mode=mode,
            )
        except Exception as exc:
            kg_result.answer = f"{kg_result.answer}\n\n（大模型调用失败，已回退至图谱问答：{exc}）"
            kg_result.mode = "kg_fallback"
            return kg_result
