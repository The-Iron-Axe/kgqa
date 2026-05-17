"""FastAPI 后端服务：数据展示、图谱可视化、问答接口。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import get_settings
from src.kg.graph_client_factory import GraphClient, create_graph_client, get_graph_db_display_name
from src.qa.kg_qa_engine import KGQAEngine
from src.qa.llm_qa_engine import LLMQAEngine

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"

kg_client: GraphClient | None = None
kg_engine: KGQAEngine | None = None
llm_engine: LLMQAEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global kg_client, kg_engine, llm_engine
    kg_client = create_graph_client()
    kg_engine = KGQAEngine(kg_client)
    llm_engine = LLMQAEngine(kg_engine)
    yield
    if llm_engine:
        llm_engine.close()


settings = get_settings()
app = FastAPI(
    title=settings.project_name,
    description=f"领域：{settings.domain} | 图谱：{get_graph_db_display_name()}",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    mode: Literal["kg", "kg_llm"] = "kg"


class QuestionResponse(BaseModel):
    question: str
    answer: str
    intent: str
    entity: str | None
    confidence: float
    evidence: list[str]
    mode: str
    matched_entities: list[str] = Field(default_factory=list)


class EntityDetailResponse(BaseModel):
    entity: dict
    outgoing: list[dict]
    incoming: list[dict]


@app.get("/")
async def index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health():
    try:
        assert kg_client is not None
        kg_client.verify_connection()
        return {
            "status": "ok",
            "domain": settings.domain,
            "graph_mode": settings.graph_mode,
            "graph_database": get_graph_db_display_name(),
            "llm_enabled": settings.llm_enabled,
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"图谱连接失败: {exc}") from exc


@app.get("/api/statistics")
async def statistics():
    assert kg_client is not None
    return kg_client.get_statistics()


@app.get("/api/entities")
async def entities(limit: int = Query(100, ge=1, le=500)):
    assert kg_client is not None
    return {"entities": kg_client.get_all_entities(limit=limit)}


@app.get("/api/graph")
async def graph(
    entity: str | None = None,
    limit: int = Query(50, ge=10, le=200),
    hops: int = Query(2, ge=1, le=2),
):
    assert kg_client is not None
    return kg_client.get_subgraph(entity_name=entity, limit=limit, hops=hops)


@app.get("/api/search")
async def search(keyword: str = Query(..., min_length=1)):
    assert kg_client is not None
    return {"results": kg_client.search_entity(keyword)}


@app.get("/api/match-entities")
async def match_entities(text: str = Query(..., min_length=1, max_length=500)):
    """从文本中匹配图谱内所有实体名（用于图谱高亮）。"""
    assert kg_engine is not None
    names = kg_engine.parser.extract_all_entities(text)
    return {"matched_entities": names}


@app.get("/api/entity/{name}", response_model=EntityDetailResponse)
async def entity_detail(name: str):
    assert kg_client is not None
    entity = kg_client.get_entity_by_name(name)
    if not entity:
        raise HTTPException(status_code=404, detail=f"未找到实体：{name}")
    return EntityDetailResponse(
        entity=entity,
        outgoing=kg_client.get_outgoing_relations(name),
        incoming=kg_client.get_incoming_relations(name),
    )


@app.post("/api/ask", response_model=QuestionResponse)
async def ask(request: QuestionRequest):
    if request.mode == "kg_llm":
        assert llm_engine is not None
        result = llm_engine.answer(request.question)
    else:
        assert kg_engine is not None
        result = kg_engine.answer(request.question)

    return QuestionResponse(
        question=result.question,
        answer=result.answer,
        intent=result.intent,
        entity=result.entity,
        confidence=result.confidence,
        evidence=result.evidence,
        mode=result.mode,
        matched_entities=result.matched_entities,
    )


@app.get("/api/project-info")
async def project_info():
    return {
        "project_name": settings.project_name,
        "domain": settings.domain,
        "graph_mode": settings.graph_mode,
        "graph_database": get_graph_db_display_name(),
        "llm_enabled": settings.llm_enabled,
        "features": ["数据展示", "知识图谱可视化", "智能问答", "对比评测"],
    }


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
