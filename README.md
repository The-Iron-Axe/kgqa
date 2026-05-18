# 中国人工智能技术知识图谱问答系统

> 课程设计 / 答辩项目  
> 领域：人工智能技术、模型、机构、产品、政策、算力基础设施与应用场景  
> 当前图谱规模：377 个实体、954 条关系，共 1331 条图谱记录

本项目是一个面向中国人工智能技术领域的知识图谱问答演示系统。系统使用结构化图谱数据组织 AI 相关实体、技术机制、模型架构、优化方法、问题风险与应用场景，支持知识图谱可视化、实体检索、智能问答、分屏对比、Neo4j Cypher 控制台、查询结果导出和问答评测。

项目不是工业级技术情报平台，而是课程设计场景下的知识图谱应用原型。当前版本避免把普通科普词条包装成“技术追踪数据库”，重点展示技术实体建模、图数据库存储、结构化图谱检索、可视化交互和图谱证据增强问答流程。

## 主要功能

- 知识图谱可视化：基于 `vis-network` 展示实体和关系，支持搜索、聚焦、全屏、节点数量设置和动态布局。
- 智能问答：支持 KG-only 和 KG + LLM 两种模式。
- 问答联动图谱：问答结果可同步高亮相关实体与关系。
- 分屏对比：智能问答页可左右分屏，左侧问答，右侧图谱。
- 实体数据管理：以表格方式查看和筛选实体。
- 图谱控制台：Neo4j 模式下支持输入 Cypher 语句进行查询、新增、修改和删除。
- 结果展示与导出：Cypher 查询结果可在表格和原始 JSON 之间切换，并支持 CSV / JSON 导出。
- 评测报告：支持运行脚本生成 KG-only 与 KG + LLM 的问答评测结果。

## 图谱数据

核心数据文件：

```text
data/raw/ai_knowledge.json
```

当前数据规模：

```text
实体：377
关系：954
总计：1331
```

实体类型包括：

```text
Technology、Model、Organization、Product、Application、Policy、Hardware、Algorithm、Person、Infrastructure、Problem、Metric
```

数据内容覆盖：

- 基础 AI 技术：机器学习、深度学习、自然语言处理、计算机视觉、知识图谱等。
- 大模型与产品：DeepSeek-R1、DeepSeek-V3、Qwen3、Qwen2.5、Kimi K2、GLM、文心一言、讯飞星火等。
- 技术机制：RAG、LoRA、RLHF、DPO、MoE、MLA、FlashAttention、RoPE、推测解码、量化、蒸馏、长上下文等。
- 技术问题与优化指标：模型幻觉、事实一致性校验、引用溯源、事实性评估、吞吐量、KV 缓存优化等。
- 企业与机构：百度、阿里巴巴、腾讯、华为、科大讯飞、智谱 AI、月之暗面、DeepSeek 等。
- 政策与基础设施：新一代人工智能发展规划、算力网络、智算中心、AI 芯片等。
- 应用场景：智能客服、自动驾驶、智慧医疗、工业质检、金融风控、教育辅助等。

## 运行环境

推荐使用 Conda：

```powershell
conda create -n kgqa python=3.11 -y
conda activate kgqa
pip install -r requirements.txt
```

如果下载较慢，可以使用清华源：

```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

主要依赖：

- FastAPI / Uvicorn：后端 Web 服务
- Neo4j Python Driver：连接 Neo4j 图数据库
- Pydantic / python-dotenv：配置和数据校验
- OpenAI SDK：可选的大模型接口
- scikit-learn / jieba：问答评测与中文处理
- vis-network：前端图谱可视化

## 配置文件

如果没有 `.env`，先复制模板：

```powershell
copy .env.example .env
```

常用配置：

```env
GRAPH_MODE=local

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=kgqa123456

LLM_ENABLED=false
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-v4-flash

API_HOST=0.0.0.0
API_PORT=8001
```

说明：

- `GRAPH_MODE=local`：使用本地 JSON 内存图谱，不需要安装 Neo4j。
- `GRAPH_MODE=neo4j`：使用 Neo4j 图数据库，支持 Cypher 控制台。
- `LLM_ENABLED=false`：只使用图谱问答。
- `LLM_ENABLED=true`：启用图谱证据增强的大模型问答，需要配置 API Key。

不要把包含真实密码或 API Key 的 `.env` 上传到 GitHub。

## 启动方式

### 本地 JSON 模式

适合快速演示，无需 Neo4j。

`.env` 设置：

```env
GRAPH_MODE=local
```

启动：

```powershell
conda activate kgqa
python run_server.py
```

浏览器访问：

```text
http://localhost:8001
```

### Neo4j 模式

适合正式演示图数据库、Cypher 查询和图谱 CRUD。

1. 打开 Neo4j Desktop。
2. 创建并启动本地数据库。
3. 修改 `.env`：

```env
GRAPH_MODE=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=你的数据库密码
```

4. 导入数据：

```powershell
python scripts/01_import_data.py
```

5. 启动服务：

```powershell
python run_server.py
```

6. 浏览器访问：

```text
http://localhost:8001
```

## 页面说明

### 知识图谱

知识图谱页支持加载全图、搜索实体、聚焦节点、查看实体邻域、全屏展示和调节渲染节点数量。节点数量设置用于控制前端一次渲染的规模，适合在流畅度和展示完整度之间做平衡。

### 智能问答

智能问答页支持 KG-only 和 KG + LLM 两种回答方式。

- KG-only：根据问题识别实体和意图，从图谱中检索关系并生成模板化回答，已支持技术路径、架构、优化和风险缓解类问题。
- KG + LLM：先生成结构化图谱答案，再把图谱证据和用户问题交给大模型组织自然语言表达。

这里更准确的定位是“图谱证据增强问答”。系统没有宣称自己是完整工业级检索增强生成框架，LLM 只作为可选的表达增强层。

示例问题：

```text
解决大语言模型幻觉的技术路径有哪些？
Qwen3 使用了哪些架构？
Kimi K2 使用了哪些架构？
FlashAttention 优化了什么？
Kimi 支持什么技术能力？
低秩适配属于什么微调方法？
```

### 分屏对比

点击智能问答页的“分屏对比”按钮后，页面会分为左右两部分：

- 左侧：问答窗口
- 右侧：知识图谱

提问后，相关实体会在右侧图谱中高亮，便于答辩时说明答案来源。

### 图谱控制台

图谱控制台仅在 Neo4j 模式下完整可用。它支持直接执行 Cypher：

```cypher
MATCH (n:Entity)
RETURN n.name AS name, n.type AS type
LIMIT 10
```

支持的操作包括：

- 查询实体和关系
- 新增实体
- 新增关系
- 修改属性
- 删除实体或关系
- 表格 / 原始 JSON 切换
- CSV / JSON 导出

示例查询可以点击页面中的 `?` 按钮查看。

## 常用脚本

| 脚本 | 作用 |
|------|------|
| `run_server.py` | 启动 Web 服务 |
| `scripts/01_import_data.py` | 将 JSON 图谱导入 Neo4j |
| `scripts/02_run_evaluation.py` | 生成问答评测报告 |
| `scripts/05_check_islands.py` | 检查图谱是否存在孤立子图 |
| `scripts/06_list_low_degree.py` | 检查低连接度实体 |
| `scripts/08_expand_to_1000.py` | 扩充图谱数据到 1000 条左右 |

## 项目结构

```text
knowledgegraph/
├── run_server.py
├── requirements.txt
├── config/
│   └── settings.py
├── data/
│   ├── raw/
│   │   └── ai_knowledge.json
│   └── evaluation/
│       └── qa_test_set.json
├── scripts/
├── src/
│   ├── api/
│   ├── kg/
│   ├── qa/
│   └── evaluation/
├── frontend/
│   ├── css/
│   ├── js/
│   └── index.html
└── docs/
```

## 评测

运行：

```powershell
python scripts/02_run_evaluation.py
```

如果不想调用大模型：

```powershell
python scripts/02_run_evaluation.py --skip-llm
```

评测报告输出到：

```text
data/evaluation/reports/
```

## 常见问题

### Neo4j 认证失败

检查 `.env` 里的密码是否和 Neo4j Desktop 中的数据库密码一致：

```env
NEO4J_PASSWORD=你的真实密码
```

修改后重新运行导入脚本和服务。

### 图谱控制台显示 Not Found

通常是后端没有重启。停止当前服务后重新运行：

```powershell
python run_server.py
```

然后浏览器按 `Ctrl + F5` 强制刷新。

### Cypher 查询是不是 SELECT

不是。Neo4j 使用 Cypher，查询语法通常是：

```cypher
MATCH (n)
RETURN n
LIMIT 10
```

SQL 的 `SELECT ... FROM ...` 是关系型数据库写法。

### 本地模式能不能执行 Cypher

不能。本地模式使用 JSON 内存图谱，不是 Neo4j 图数据库。需要执行 Cypher 时，请切换到：

```env
GRAPH_MODE=neo4j
```

并先运行：

```powershell
python scripts/01_import_data.py
```

## 答辩演示建议

1. 打开首页，说明当前图谱规模和两种运行模式。
2. 进入知识图谱页，加载全图并展示节点数量调节。
3. 搜索 `DeepSeek`、`文心一言`、`RAG` 等实体，展示邻域关系。
4. 进入智能问答页，提问并展示图谱证据。
5. 打开分屏对比，展示问答和图谱高亮联动。
6. 进入图谱控制台，执行 `MATCH ... RETURN ...` 查询。
7. 切换表格 / JSON 结果展示，并导出查询结果。
8. 展示评测报告，说明 KG-only 与 KG + LLM 的差异。

推荐表述：

> 本项目围绕中国人工智能技术领域，构建了包含技术、模型、产品、机构、政策、硬件和应用场景的知识图谱，并在此基础上实现了可视化浏览、结构化查询、图谱证据增强问答和结果评测。项目重点不在于替代工业级技术情报系统，而是完整展示知识图谱从数据组织到应用服务的课程设计流程。
