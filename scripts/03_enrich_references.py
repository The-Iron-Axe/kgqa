"""
为 ai_knowledge.json 批量写入 reference 字段（实体 + 关系）。
运行：python scripts/03_enrich_references.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "ai_knowledge.json"

ENTITY_REF: dict[str, str] = {
    "人工智能": "国务院.《新一代人工智能发展规划》；https://www.gov.cn/zhengce/content/2017-07/20/content_2122384.htm",
    "机器学习": "Goodfellow et al., Deep Learning；https://en.wikipedia.org/wiki/Machine_learning",
    "深度学习": "Goodfellow et al., Deep Learning；https://en.wikipedia.org/wiki/Deep_learning",
    "大语言模型": "https://en.wikipedia.org/wiki/Large_language_model",
    "多模态大模型": "产业公开技术综述与产品发布材料",
    "计算机视觉": "https://en.wikipedia.org/wiki/Computer_vision",
    "自然语言处理": "https://en.wikipedia.org/wiki/Natural_language_processing",
    "强化学习": "https://en.wikipedia.org/wiki/Reinforcement_learning",
    "知识图谱": "https://en.wikipedia.org/wiki/Knowledge_graph",
    "图神经网络": "https://en.wikipedia.org/wiki/Graph_neural_network",
    "联邦学习": "https://en.wikipedia.org/wiki/Federated_learning",
    "检索增强生成": "Lewis et al., RAG (NeurIPS 2020)；https://arxiv.org/abs/2005.11401",
    "Transformer": "Vaswani et al., Attention Is All You Need；https://arxiv.org/abs/1706.03762",
    "BERT": "Devlin et al., BERT；https://arxiv.org/abs/1810.04805",
    "GPT": "Radford et al., GPT；OpenAI 技术报告",
    "ChatGPT": "https://openai.com/chatgpt",
    "文心一言": "https://yiyan.baidu.com/",
    "文心大模型": "https://yiyan.baidu.com/",
    "通义千问": "https://tongyi.aliyun.com/",
    "通义大模型": "https://tongyi.aliyun.com/",
    "DeepSeek": "https://www.deepseek.com/",
    "DeepSeek-V3": "https://www.deepseek.com/",
    "讯飞星火": "https://xinghuo.xfyun.cn/",
    "星火大模型": "https://xinghuo.xfyun.cn/",
    "ChatGLM": "https://chatglm.cn/",
    "智谱GLM": "https://www.zhipuai.cn/",
    "腾讯混元": "https://cloud.tencent.com/product/hunyuan",
    "字节豆包": "https://www.doubao.com/",
    "Kimi": "https://kimi.moonshot.cn/",
    "昇腾AI": "https://www.hiascend.com/",
    "寒武纪": "https://www.cambricon.com/",
    "寒武纪思元": "https://www.cambricon.com/",
    "百度": "https://www.baidu.com/",
    "阿里巴巴": "https://www.alibabagroup.com/",
    "腾讯": "https://www.tencent.com/",
    "华为": "https://www.huawei.com/",
    "科大讯飞": "https://www.iflytek.com/",
    "智谱AI": "https://www.zhipuai.cn/",
    "月之暗面": "https://www.moonshot.cn/",
    "商汤科技": "https://www.sensetime.com/",
    "深度求索": "https://www.deepseek.com/",
    "OpenAI": "https://openai.com/",
    "何恺明": "He et al., ResNet；https://arxiv.org/abs/1512.03385",
    "张钹": "清华大学人工智能研究院公开资料",
    "Apollo自动驾驶": "https://apollo.auto/",
    "《新一代人工智能发展规划》": "https://www.gov.cn/zhengce/content/2017-07/20/content_2122384.htm",
    "《生成式人工智能服务管理暂行办法》": "国家网信办公开文件（2023）",
    "算力基础设施": "工信部新型数据中心相关政策文件",
    "智算中心": "国家发改委算力基础设施相关政策",
    "东数西算": "国家发改委东数西算工程公开资料",
}

DEFAULT_ENTITY_REF = "公开资料整理"
DEFAULT_RELATION_REF = "公开资料整理"


def clean_reference(text: str) -> str:
    """去除冗余提示语，保留简洁引用说明或 URL。"""
    if not text:
        return DEFAULT_ENTITY_REF
    text = re.sub(r"[；;]\s*建议补充具体\s*URL", "", text, flags=re.I)
    text = re.sub(r"建议补充具体\s*URL", "", text, flags=re.I)
    text = re.sub(r"建议引用\s*URL", "", text, flags=re.I)
    text = re.sub(r"（检索整理）", "", text)
    text = re.sub(r"（课程实验标注）", "", text)
    text = re.sub(r"（课程实验）", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ；;")
    return text or DEFAULT_ENTITY_REF


def default_relation_ref(source: str, target: str, rel_type: str) -> str:
    if "《新一代人工智能发展规划》" in (source, target) or rel_type == "推动":
        return "国务院.《新一代人工智能发展规划》；https://www.gov.cn/zhengce/content/2017-07/20/content_2122384.htm"
    if rel_type == "研发" and source in ENTITY_REF:
        return ENTITY_REF.get(source, DEFAULT_RELATION_REF)
    if rel_type in ("实现", "基于") and target in ("大语言模型", "Transformer", "GPT", "深度学习"):
        return "公开论文与产品文档"
    return DEFAULT_RELATION_REF


def main() -> None:
    with DATA.open(encoding="utf-8") as f:
        data = json.load(f)

    for e in data["entities"]:
        name = e["name"]
        raw = ENTITY_REF.get(name, DEFAULT_ENTITY_REF)
        e["reference"] = clean_reference(raw)

    for r in data["relations"]:
        raw = default_relation_ref(r["source"], r["target"], r["type"])
        r["reference"] = clean_reference(raw)

    with DATA.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已写入 reference：{len(data['entities'])} 实体，{len(data['relations'])} 关系 → {DATA}")


if __name__ == "__main__":
    main()
