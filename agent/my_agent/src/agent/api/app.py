"""FastAPI 应用入口。

把阶段 1-3 的能力暴露成 HTTP 接口，便于用 curl / Swagger UI 测试：

    GET  /health    存活探针
    POST /chat      简单任务：单 Agent ReAct（带 thread_id 短期记忆）
    POST /plan      复杂任务：Plan-and-Execute 子图
    POST /ingest    上传 PDF 课件入库（阶段 2 RAG 的入口）
    POST /retrieve  只跑检索不经过 LLM（单独验证 RAG）

阶段 5 的路由分类器还没实现，所以这里不自动分流，由调用方选 /chat 还是 /plan。

Java 类比：@RestController。Controller 只做三件事——收 DTO、调 Service、转异常/返回 DTO，
真正的业务逻辑在 service.py。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from agent.api import service
from agent.api.schemas import (
    ChatRequest,
    ChatResponse,
    IngestResponse,
    PlanRequest,
    PlanResponse,
    RetrieveRequest,
    RetrieveResponse,
)
from agent.config import settings
from agent.rag.vector_store import COLLECTION_PRIVATE


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时构建图 / checkpointer 单例（只跑一次，不再每请求新建）。"""
    service.init()
    yield
    # 关闭无需清理：sqlite 连接随进程回收（见 memory/short_term.py 注释）


app = FastAPI(title="大学生智能学习多Agent系统", lifespan=lifespan)

# 允许浏览器 / Swagger UI 跨域直调，方便本地测试
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """存活探针。"""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """简单任务：跑一次 ReAct 问答。传同一个 thread_id 即可连续多轮带上下文。"""
    try:
        output, thread_id = service.answer(req.user_input, req.thread_id)
    except Exception as exc:  # noqa: BLE001 —— LLM/网络等外部故障，统一转 502
        raise HTTPException(
            status_code=502, detail=f"问答失败：{type(exc).__name__}: {exc}"
        ) from exc
    return ChatResponse(output=output, thread_id=thread_id)


@app.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest) -> PlanResponse:
    """复杂任务：跑一次 Plan-and-Execute，返回计划 + 各步产出 + 最终产出。"""
    try:
        state = service.execute_plan(req.user_input)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"规划执行失败：{type(exc).__name__}: {exc}"
        ) from exc

    steps = state.get("plan", [])
    results = state.get("subtask_results", {}) or {}
    _, output = service.final_output(steps, results)
    return PlanResponse(
        plan=steps,
        subtask_results=results,
        final_output=output,
        replan_count=state.get("replan_count", 0),
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(file: UploadFile = File(...)) -> IngestResponse:
    """上传 PDF 课件入库（加载 -> 分块 -> 向量化 -> 写向量库）。"""
    filename = file.filename or "upload.pdf"
    data = file.file.read()
    try:
        chunks = service.ingest_upload(filename, data)
    except (ValueError, FileNotFoundError) as exc:  # 解析不出文本 / 文件问题 —— 客户端输入错
        raise HTTPException(status_code=400, detail=f"课件解析失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 向量化/写库等外部故障
        raise HTTPException(
            status_code=502, detail=f"入库失败：{type(exc).__name__}: {exc}"
        ) from exc
    return IngestResponse(filename=filename, chunks=chunks, collection=COLLECTION_PRIVATE)


@app.post("/retrieve", response_model=RetrieveResponse)
def retrieve(req: RetrieveRequest) -> RetrieveResponse:
    """只跑检索（不经过 LLM），用于单独验证 RAG 是否命中课件。"""
    try:
        chunks, hit_private = service.search(req.query, req.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"检索失败：{type(exc).__name__}: {exc}"
        ) from exc
    return RetrieveResponse(chunks=chunks, hit_private=hit_private)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
