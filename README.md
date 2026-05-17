# 中国先进人工智能技术 · 知识图谱问答系统

> **课程设计 / 答辩项目** — 领域：**人工智能**

## 实验报告 · 数据收集章节

撰写「数据来源 / 收集方法 / 步骤与质量评估」时，请直接参考项目内说明文档：  
[docs/DATA_COLLECTION_REPORT.md](docs/DATA_COLLECTION_REPORT.md)（含统计数字、来源分类、答辩话术与 Neo4j 结构说明，与 `data/raw/ai_knowledge.json` 一致）。

## 一、Docker 不是必须的

本项目提供 **两种运行方式**，默认使用 **本地模式**，**无需 Docker、无需 Neo4j**：

| 模式 | 配置 | 是否需要 Docker | 适合场景 |
|------|------|-----------------|----------|
| **本地模式（默认）** | `GRAPH_MODE=local` | 否 | PyCharm 直接运行、快速演示 |
| **Neo4j 模式** | `GRAPH_MODE=neo4j` | 否* | 答辩强调「图数据库 Neo4j」 |

\* Neo4j 模式可用 **Neo4j Desktop**（图形界面安装），不必用 Docker。

---

## 二、PyCharm 运行指南（推荐，不用命令行）

### 第 1 步：用 PyCharm 打开项目

1. 打开 PyCharm → **File → Open** → 选择 `d:\knowledgegraph`
2. 提示创建虚拟环境时选 **Yes**，或手动：**File → Settings → Project → Python Interpreter → Add → Virtualenv**

### 第 2 步：安装依赖

PyCharm 通常会自动识别 `requirements.txt` 并提示安装；也可在底部 **Terminal** 中执行一次：

```
pip install -r requirements.txt
```

### 第 3 步：配置运行项（只需做一次）

**运行 Web 演示（主程序）：**

1. 在项目树中右键 `run_server.py`
2. 点击 **Run 'run_server'**
3. 浏览器打开 http://localhost:8001

**运行评测报告：**

1. 右键 `scripts/02_run_evaluation.py` → **Run**
2. 报告生成在 `data/evaluation/reports/evaluation_report.md`

**导入 Neo4j 数据（仅 Neo4j 模式需要）：**

1. 右键 `scripts/01_import_data.py` → **Run**
2. 本地模式下运行会提示「无需导入」，可忽略

### 第 4 步：设置工作目录（如运行报错再配置）

若提示找不到模块，对 `run_server.py` 的运行配置：

- **Run → Edit Configurations**
- **Working directory** 设为 `d:\knowledgegraph`
- 勾选 **Add content roots to PYTHONPATH**

---

## 三、本地模式（零安装，最快开始）

默认已是本地模式，**不用装 Docker，不用装 Neo4j**。

在 PyCharm 中 **直接运行 `run_server.py`** 即可，数据来自 `data/raw/ai_knowledge.json`。

答辩时可说明：
> 系统基于知识图谱架构，开发阶段使用 JSON 内存图谱；生产/完整版可切换至 Neo4j 图数据库。

---

## 四、Neo4j 模式（答辩想强调图数据库时）

### 方式 A：Neo4j Desktop（推荐，有图形界面）

1. 下载 **Neo4j Desktop**：https://neo4j.com/download/
2. 安装后新建 Local DB，设置密码（如 `kgqa123456`）
3. 点击 **Start** 启动数据库
4. 复制 `.env.example` 为 `.env`，修改：

```env
GRAPH_MODE=neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=你设置的密码
```

5. PyCharm 运行 `scripts/01_import_data.py` 导入数据
6. PyCharm 运行 `run_server.py`

### 方式 B：Docker（可选，不是必须）

```powershell
docker compose up -d
```

然后同样设置 `GRAPH_MODE=neo4j` 并运行导入脚本。

---

## 五、可选：启用大模型

编辑 `.env`（没有则复制 `.env.example`）：

```env
LLM_ENABLED=true
LLM_API_KEY=你的API密钥
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

DeepSeek 注册：https://platform.deepseek.com/

---

## 六、PyCharm 运行顺序速查

### 本地模式（最简单）

```
1. 运行 run_server.py          → 打开 http://localhost:8001
2. 运行 scripts/02_run_evaluation.py  → 生成评测报告（可选）
```

### Neo4j 模式

```
1. 启动 Neo4j Desktop 中的数据库
2. （可选）修改 data/raw/ai_knowledge.json 后，运行 scripts/03_enrich_references.py 重新生成参考文献字段
3. 运行 scripts/01_import_data.py（写入 Neo4j，含 reference）
4. 运行 run_server.py
5. 运行 scripts/02_run_evaluation.py（可选）
```

---

## 七、项目文件说明

| 文件 | 作用 | PyCharm 是否运行 |
|------|------|------------------|
| `run_server.py` | 启动 Web 演示服务 | **是（主程序）** |
| `scripts/02_run_evaluation.py` | 生成 KG vs KG+LLM 评测报告 | 可选 |
| `scripts/01_import_data.py` | 导入数据到 Neo4j（含 `reference`） | 仅 Neo4j 模式 |
| `scripts/03_enrich_references.py` | 为 JSON 批量写入/更新 `reference` 字段 | 改数据后可选 |
| `data/raw/ai_knowledge.json` | 知识图谱数据（35 实体 + 43 关系 + 参考文献） | 不运行，只读 |
| `config/settings.py` | 全局配置 | 不运行 |
| `src/kg/local_graph_client.py` | 本地 JSON 图谱（无需数据库） | 不运行 |
| `src/kg/neo4j_client.py` | Neo4j 图数据库客户端 | 不运行 |
| `src/qa/kg_qa_engine.py` | 纯图谱问答引擎 | 不运行 |
| `src/qa/llm_qa_engine.py` | 图谱+大模型问答 | 不运行 |
| `frontend/` | 演示页面（图谱+表格+问答） | 不运行 |

---

## 八、需下载的软件

### 本地模式（最少）

| 软件 | 下载 |
|------|------|
| Python 3.10+ | https://www.python.org/downloads/ |
| PyCharm | https://www.jetbrains.com/pycharm/download/ |

### Neo4j 模式（额外）

| 软件 | 下载 |
|------|------|
| Neo4j Desktop | https://neo4j.com/download/ |

### 大模型（可选）

| 服务 | 下载 |
|------|------|
| DeepSeek API | https://platform.deepseek.com/ |

---

## 九、答辩演示建议

1. **数据展示**：实体表格
2. **知识图谱**：vis.js 交互可视化
3. **问答**：KG-only 与 KG+LLM 对比
4. **评测**：打开 `data/evaluation/reports/evaluation_report.md`

**答辩关键信息：**
- 领域：中国先进人工智能技术
- 图谱：本地 JSON / Neo4j 5.26（按你实际使用的模式说明）
- 方案：意图解析 → 图谱检索 → 模板/LLM 生成
