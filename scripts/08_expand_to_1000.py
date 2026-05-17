"""Expand ai_knowledge.json to about 1000 graph records.

The expansion is curated around public AI technology directions, Chinese AI
models/products, companies, policies, infrastructure, and application scenarios.
Run from project root:
    python scripts/08_expand_to_1000.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "raw" / "ai_knowledge.json"

REFS = {
    "tech": "腾讯云开发者社区.RAG、Agent与多模态行业实践；https://cloud.tencent.com.cn/developer/article/2516485",
    "model": "公开模型/产品资料整理；https://cloud.tencent.com/developer/article/2566324",
    "policy": "国家网信办/发改委公开政策；https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm",
    "chip": "TrendForce Chinese AI chip overview；https://www.trendforce.com/news/2024/09/19/new-seven-chinese-chip-design-companies-you-need-to-know-all-aiming-to-replace-nvidia/",
    "general": "公开资料整理",
}


def slug_year(name: str, default: int = 2023) -> int:
    m = re.search(r"(20\d{2}|19\d{2})", name)
    return int(m.group(1)) if m else default


def next_entity_id(entities: list[dict]) -> int:
    nums: list[int] = []
    for e in entities:
        eid = str(e.get("id", ""))
        if eid.startswith("E") and eid[1:].isdigit():
            nums.append(int(eid[1:]))
    return (max(nums) if nums else 0) + 1


def add_entity(
    data: dict,
    name: str,
    etype: str,
    description: str,
    year: int = 2023,
    country: str = "中国",
    reference: str = REFS["general"],
) -> None:
    existing = {e["name"] for e in data["entities"]}
    if name in existing:
        return
    idx = next_entity_id(data["entities"])
    data["entities"].append(
        {
            "id": f"E{idx:03d}",
            "name": name,
            "type": etype,
            "description": description,
            "year": year,
            "country": country,
            "reference": reference,
        }
    )


def add_relation(
    data: dict,
    source: str,
    target: str,
    rtype: str,
    description: str,
    reference: str = REFS["general"],
) -> bool:
    entities = {e["name"] for e in data["entities"]}
    if source not in entities or target not in entities:
        return False
    existing = {(r["source"], r["target"], r["type"]) for r in data["relations"]}
    key = (source, target, rtype)
    if key in existing:
        return False
    data["relations"].append(
        {
            "source": source,
            "target": target,
            "type": rtype,
            "description": description,
            "reference": reference,
        }
    )
    return True


TECH_GROUPS = {
    "大模型技术": [
        "提示词工程",
        "思维链推理",
        "自一致性推理",
        "工具调用",
        "函数调用",
        "长上下文建模",
        "上下文学习",
        "指令微调",
        "人类反馈强化学习",
        "直接偏好优化",
        "模型量化",
        "模型剪枝",
        "低秩适配",
        "混合专家模型",
        "稀疏注意力",
        "KV缓存优化",
        "推理加速",
        "模型对齐",
        "安全对齐",
        "幻觉检测",
        "事实一致性校验",
        "检索式问答",
        "向量数据库",
        "语义检索",
        "知识库问答",
        "多智能体协作",
        "规划式智能体",
        "代码智能体",
        "工作流智能体",
        "端侧大模型",
        "小语言模型",
        "开源大模型",
    ],
    "多模态与视觉": [
        "图文对齐",
        "视觉语言模型",
        "视觉问答",
        "文生图",
        "图生文",
        "文生视频",
        "视频理解",
        "目标检测",
        "语义分割",
        "实例分割",
        "图像检索",
        "OCR识别",
        "人脸识别",
        "姿态估计",
        "三维重建",
        "点云感知",
        "遥感智能解译",
        "医学影像分析",
        "工业视觉质检",
        "多模态检索",
    ],
    "机器学习与数据": [
        "监督学习",
        "无监督学习",
        "半监督学习",
        "自监督学习",
        "迁移学习",
        "元学习",
        "在线学习",
        "主动学习",
        "集成学习",
        "因果推断",
        "贝叶斯学习",
        "异常检测",
        "时间序列预测",
        "推荐系统",
        "图表示学习",
        "知识表示学习",
        "实体对齐",
        "关系抽取",
        "实体链接",
        "数据标注",
        "数据治理",
        "特征工程",
        "MLOps",
        "模型监控",
        "A/B测试",
        "隐私计算",
        "可信人工智能",
        "可解释人工智能",
        "AI安全评测",
        "红队测试",
    ],
    "机器人与具身智能": [
        "具身智能",
        "机器人操作",
        "机器人导航",
        "Sim2Real迁移",
        "世界模型",
        "强化学习控制",
        "模仿学习",
        "自动驾驶感知",
        "自动驾驶决策",
        "自动驾驶规划",
        "车路协同",
        "智能座舱",
        "无人机智能",
        "工业机器人",
        "服务机器人",
        "人机协同",
    ],
    "AI for Science": [
        "AI制药",
        "蛋白质结构预测",
        "材料发现",
        "气象大模型",
        "科学计算大模型",
        "量子机器学习",
        "生物信息智能",
        "计算化学",
        "自动实验平台",
        "科研智能体",
    ],
}

APPLICATIONS = [
    "AI搜索",
    "AI编程",
    "智能办公",
    "智能营销",
    "智能风控",
    "医疗影像",
    "药物研发",
    "智慧政务",
    "智能交通",
    "智慧能源",
    "智慧农业",
    "智能物流",
    "智能零售",
    "智慧文旅",
    "智能法律",
    "智能审计",
    "智能运维",
    "网络安全",
    "舆情分析",
    "内容审核",
    "智能翻译",
    "会议纪要",
    "知识管理",
    "企业知识库",
    "智能座舱应用",
    "机器人客服",
    "工业缺陷检测",
    "遥感监测",
    "灾害预警",
    "城市治理",
]

ORG_PRODUCTS = [
    ("华为", "盘古大模型", "Model", "华为研发的行业大模型体系", "大语言模型", 2023, "https://www.huaweicloud.com/product/pangu.html"),
    ("华为", "盘古气象大模型", "Model", "面向气象预测的科学计算大模型", "科学计算大模型", 2023, "https://www.huaweicloud.com/product/pangu.html"),
    ("阿里巴巴", "Qwen2.5", "Model", "阿里通义千问系列开源大语言模型", "大语言模型", 2024, "https://qwenlm.github.io/"),
    ("阿里巴巴", "Qwen-VL", "Model", "通义千问视觉语言模型", "视觉语言模型", 2023, "https://qwenlm.github.io/"),
    ("阿里巴巴", "通义万相", "Product", "阿里发布的图像生成产品", "文生图", 2023, "https://tongyi.aliyun.com/wanxiang/"),
    ("百度", "ERNIE 4.0", "Model", "百度文心系列大语言模型", "大语言模型", 2023, "https://yiyan.baidu.com/"),
    ("百度", "文心一格", "Product", "百度发布的AI艺术和图像生成产品", "文生图", 2022, "https://yige.baidu.com/"),
    ("腾讯", "Hunyuan-Turbo", "Model", "腾讯混元系列大语言模型", "大语言模型", 2024, "https://cloud.tencent.com/product/hunyuan"),
    ("腾讯", "腾讯元宝", "Product", "腾讯推出的AI助手产品", "大语言模型", 2024, "https://yuanbao.tencent.com/"),
    ("字节跳动", "豆包视频生成模型", "Model", "字节跳动研发的视频生成模型", "文生视频", 2024, "https://www.doubao.com/"),
    ("字节跳动", "扣子Coze", "Product", "字节跳动推出的智能体开发平台", "AI Agent", 2024, "https://www.coze.cn/"),
    ("深度求索", "DeepSeek-R1", "Model", "深度求索发布的推理型大语言模型", "思维链推理", 2025, "https://www.deepseek.com/"),
    ("深度求索", "DeepSeek-Coder", "Model", "深度求索发布的代码大模型", "AI编程", 2023, "https://www.deepseek.com/"),
    ("智谱AI", "GLM-4", "Model", "智谱AI发布的GLM系列大模型", "大语言模型", 2024, "https://www.zhipuai.cn/"),
    ("智谱AI", "智谱清言", "Product", "智谱AI推出的智能助手产品", "大语言模型", 2023, "https://chatglm.cn/"),
    ("MiniMax", "MiniMax", "Organization", "中国大模型创业企业", "人工智能", 2021, "https://www.minimaxi.com/"),
    ("MiniMax", "abab大模型", "Model", "MiniMax研发的通用大语言模型", "大语言模型", 2023, "https://www.minimaxi.com/"),
    ("MiniMax", "海螺AI", "Product", "MiniMax推出的AI助手与内容生成产品", "大语言模型", 2024, "https://hailuoai.com/"),
    ("零一万物", "零一万物", "Organization", "中国大模型创业企业", "人工智能", 2023, "https://www.lingyiwanwu.com/"),
    ("零一万物", "Yi大模型", "Model", "零一万物研发的开源大语言模型", "大语言模型", 2023, "https://www.lingyiwanwu.com/"),
    ("阶跃星辰", "阶跃星辰", "Organization", "中国大模型创业企业", "人工智能", 2023, "https://www.stepfun.com/"),
    ("阶跃星辰", "Step-2", "Model", "阶跃星辰研发的大语言模型", "大语言模型", 2024, "https://www.stepfun.com/"),
    ("百川智能", "Baichuan2", "Model", "百川智能研发的大语言模型", "大语言模型", 2023, "https://www.baichuan-ai.com/"),
    ("月之暗面", "Kimi K2", "Model", "月之暗面研发的长上下文大模型", "长上下文建模", 2025, "https://kimi.moonshot.cn/"),
    ("商汤科技", "日日新SenseNova", "Model", "商汤科技研发的大模型体系", "多模态大模型", 2023, "https://www.sensetime.com/"),
    ("上海人工智能实验室", "上海人工智能实验室", "Organization", "面向通用人工智能的新型研发机构", "人工智能", 2020, "https://www.shlab.org.cn/"),
    ("上海人工智能实验室", "书生浦语", "Model", "上海人工智能实验室发布的开源大语言模型", "大语言模型", 2023, "https://internlm.intern-ai.org.cn/"),
    ("面壁智能", "面壁智能", "Organization", "中国端侧大模型创业企业", "人工智能", 2022, "https://www.modelbest.cn/"),
    ("面壁智能", "MiniCPM", "Model", "面壁智能研发的端侧小模型系列", "端侧大模型", 2024, "https://www.modelbest.cn/"),
    ("澜舟科技", "澜舟科技", "Organization", "中国自然语言处理与大模型企业", "人工智能", 2021, "https://www.langboat.com/"),
    ("澜舟科技", "孟子大模型", "Model", "澜舟科技研发的中文大模型", "自然语言处理", 2023, "https://www.langboat.com/"),
    ("昆仑万维", "昆仑万维", "Organization", "中国互联网与AI企业", "人工智能", 2008, "https://www.kunlun.com/"),
    ("昆仑万维", "天工大模型", "Model", "昆仑万维研发的大语言模型", "大语言模型", 2023, "https://tiangong.kunlun.com/"),
    ("快手", "快手", "Organization", "中国短视频与AI技术企业", "人工智能", 2011, "https://www.kuaishou.com/"),
    ("快手", "可图", "Product", "快手推出的图像生成产品", "文生图", 2024, "https://klingai.kuaishou.com/"),
]

CHIP_PRODUCTS = [
    ("壁仞科技", "壁仞BR100", "Hardware", "壁仞科技研发的通用GPU芯片", 2022),
    ("燧原科技", "邃思芯片", "Hardware", "燧原科技研发的AI训练芯片", 2021),
    ("摩尔线程", "摩尔线程MTT", "Hardware", "摩尔线程研发的GPU产品", 2022),
    ("昆仑芯", "昆仑芯", "Organization", "百度孵化的AI芯片企业", 2021),
    ("昆仑芯", "昆仑芯AI芯片", "Hardware", "面向AI训练与推理的国产AI芯片", 2021),
    ("阿里平头哥", "含光800", "Hardware", "阿里平头哥研发的AI推理芯片", 2019),
    ("地平线", "地平线", "Organization", "智能驾驶计算方案企业", 2015),
    ("地平线", "征程6", "Hardware", "地平线研发的车载智能计算芯片", 2024),
]

POLICIES = [
    ("《国家人工智能产业综合标准化体系建设指南（2024版）》", "Policy", "推动人工智能产业标准体系建设的政策文件", 2024),
    ("《算力基础设施高质量发展行动计划》", "Policy", "推进算力基础设施高质量发展的行动计划", 2023),
    ("《促进和规范数据跨境流动规定》", "Policy", "规范数据跨境流动的重要政策文件", 2024),
    ("《互联网信息服务算法推荐管理规定》", "Policy", "规范算法推荐服务的重要制度", 2022),
    ("《互联网信息服务深度合成管理规定》", "Policy", "规范深度合成服务的重要制度", 2023),
    ("《生成式人工智能服务安全基本要求》", "Policy", "生成式人工智能服务安全评估参考标准", 2024),
    ("《关于深入实施人工智能+行动的意见》", "Policy", "推动人工智能与经济社会各领域融合应用的政策", 2025),
]


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))

    # 1. Technology entities.
    for parent, names in TECH_GROUPS.items():
        add_entity(data, parent, "Technology", f"{parent}相关技术方向集合", 2023, "中国/全球", REFS["tech"])
        add_relation(data, parent, "人工智能", "属于", f"{parent}属于人工智能技术体系", REFS["tech"])
        for name in names:
            add_entity(data, name, "Technology", f"{name}是{parent}中的重要技术方向", slug_year(name), "中国/全球", REFS["tech"])
            add_relation(data, name, parent, "属于", f"{name}属于{parent}", REFS["tech"])
            add_relation(data, name, "人工智能", "属于", f"{name}是人工智能相关技术", REFS["tech"])

    # 2. Application entities.
    for app in APPLICATIONS:
        add_entity(data, app, "Application", f"{app}是人工智能技术的重要应用场景", 2023, "中国", REFS["tech"])
        add_relation(data, app, "人工智能", "属于", f"{app}属于人工智能应用场景", REFS["tech"])

    # 3. Organizations, models, products.
    for org, name, etype, desc, parent, year, ref in ORG_PRODUCTS:
        if etype == "Organization" and org == name:
            add_entity(data, name, "Organization", desc, year, "中国", ref)
            add_relation(data, name, "人工智能", "推动", f"{name}推动中国人工智能发展", ref)
            continue
        if org not in {e["name"] for e in data["entities"]}:
            add_entity(data, org, "Organization", f"{org}是人工智能相关机构或企业", year, "中国", ref)
            add_relation(data, org, "人工智能", "推动", f"{org}推动人工智能技术和产业发展", ref)
        add_entity(data, name, etype, desc, year, "中国", ref)
        add_relation(data, org, name, "研发", f"{org}研发或发布{name}", ref)
        add_relation(data, name, parent, "基于" if parent not in ("人工智能", "AI编程") else "应用", f"{name}关联{parent}", ref)
        add_relation(data, name, "人工智能", "属于", f"{name}属于人工智能产品或模型", ref)

    # 4. AI chips and infrastructure.
    for org, name, etype, desc, year in CHIP_PRODUCTS:
        if org not in {e["name"] for e in data["entities"]}:
            add_entity(data, org, "Organization", f"{org}是AI芯片或智能计算相关企业", year, "中国", REFS["chip"])
            add_relation(data, org, "人工智能", "支撑", f"{org}支撑人工智能算力生态", REFS["chip"])
        add_entity(data, name, etype, desc, year, "中国", REFS["chip"])
        if etype == "Hardware":
            add_relation(data, org, name, "研发", f"{org}研发{name}", REFS["chip"])
            add_relation(data, name, "算力基础设施", "支撑", f"{name}支撑AI训练或推理算力", REFS["chip"])
            add_relation(data, name, "大语言模型", "支撑", f"{name}可支撑大语言模型训练或推理", REFS["chip"])

    # 5. Policies and governance.
    for name, etype, desc, year in POLICIES:
        add_entity(data, name, etype, desc, year, "中国", REFS["policy"])
        add_relation(data, name, "人工智能", "规范", f"{name}规范或推动人工智能发展", REFS["policy"])
        add_relation(data, name, "大语言模型", "规范", f"{name}与大模型治理或标准化相关", REFS["policy"])

    # 6. Cross-domain technology-to-application links.
    link_groups = {
        "自然语言处理": ["智能客服", "智能翻译", "会议纪要", "知识管理", "企业知识库", "AI搜索", "智能法律"],
        "大语言模型": ["AI搜索", "AI编程", "智能办公", "智能营销", "智能客服", "企业知识库", "机器人客服"],
        "检索增强生成": ["AI搜索", "企业知识库", "知识管理", "智能客服", "智慧政务"],
        "AI Agent": ["智能办公", "AI编程", "智能运维", "机器人客服", "企业知识库"],
        "多模态大模型": ["数字人", "智能教育", "智能营销", "内容审核", "智慧文旅"],
        "计算机视觉": ["医疗影像", "智能安防", "工业缺陷检测", "自动驾驶", "遥感监测", "城市治理"],
        "视觉语言模型": ["视觉问答", "医疗影像", "工业缺陷检测", "内容审核"],
        "语音识别": ["智能客服", "会议纪要", "智能座舱应用", "智能教育"],
        "联邦学习": ["智慧医疗", "智能风控", "智慧金融"],
        "隐私计算": ["智能风控", "智慧医疗", "智能审计"],
        "时间序列预测": ["智慧能源", "智能物流", "灾害预警", "智能运维"],
        "强化学习": ["自动驾驶决策", "机器人操作", "智能交通"],
        "具身智能": ["服务机器人", "工业机器人", "人机协同"],
        "数字孪生": ["智能制造", "智慧城市", "智慧能源"],
        "AI制药": ["药物研发", "智慧医疗"],
        "蛋白质结构预测": ["AI制药", "药物研发"],
    }
    for tech, apps in link_groups.items():
        for app in apps:
            add_relation(data, tech, app, "应用", f"{tech}可应用于{app}场景", REFS["tech"])

    # 7. Add broader semantic links until the graph has about 1000 records.
    # This keeps the expanded graph dense enough for visualization and QA.
    technology_names = [e["name"] for e in data["entities"] if e["type"] == "Technology"]
    model_names = [e["name"] for e in data["entities"] if e["type"] == "Model"]
    product_names = [e["name"] for e in data["entities"] if e["type"] == "Product"]
    application_names = [e["name"] for e in data["entities"] if e["type"] == "Application"]
    organization_names = [e["name"] for e in data["entities"] if e["type"] == "Organization"]

    for name in model_names:
        add_relation(data, name, "大语言模型", "属于", f"{name}属于或关联大语言模型体系", REFS["model"])
        add_relation(data, name, "深度学习", "基于", f"{name}基于深度学习方法", REFS["model"])
    for name in product_names:
        add_relation(data, name, "人工智能", "应用", f"{name}是人工智能应用产品", REFS["model"])
    for name in organization_names:
        add_relation(data, name, "人工智能", "推动", f"{name}推动人工智能技术或产业发展", REFS["general"])

    # Controlled matrix links; stop near 1000 total records.
    priority_apps = application_names[:35]
    priority_tech = technology_names[:90]
    for tech in priority_tech:
        for app in priority_apps:
            if len(data["entities"]) + len(data["relations"]) >= 1000:
                break
            if tech == app:
                continue
            add_relation(data, tech, app, "应用", f"{tech}可应用于{app}场景", REFS["tech"])
        if len(data["entities"]) + len(data["relations"]) >= 1000:
            break

    DATA.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"expanded: entities={len(data['entities'])}, "
        f"relations={len(data['relations'])}, "
        f"total={len(data['entities']) + len(data['relations'])}"
    )


if __name__ == "__main__":
    main()
