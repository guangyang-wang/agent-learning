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
from fastapi.responses import FileResponse

from agent.api import service
from agent.api.schemas import (
    ChatRequest,
    ChatResponse,
    IngestResponse,
    PlanRequest,
    PlanResponse,
    PlanSessionDetail,
    PlanSessionSummary,
    RetrieveRequest,
    RetrieveResponse,
    SessionDetail,
    SessionSummary,
    UploadRecord,
)
from agent.config import settings


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
    """复杂任务：跑一次 Plan-and-Execute，返回计划 + 各步产出 + 最终产出。

    传同一个 thread_id 即可连续多轮，planner 能看到此前的请求（规划记忆）。
    """
    try:
        state, thread_id = service.execute_plan(req.user_input, req.thread_id)
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
        thread_id=thread_id,
        requests=service.plan_texts(state),
    )


@app.post("/ingest", response_model=IngestResponse)
def ingest(file: UploadFile = File(...)) -> IngestResponse:
    """上传 PDF 课件入库（加载 -> 分块 -> 向量化 -> 写向量库），并保留原文件。"""
    filename = file.filename or "upload.pdf"
    data = file.file.read()
    try:
        record = service.ingest_upload(filename, data)
    except (ValueError, FileNotFoundError) as exc:  # 解析不出文本 / 文件问题 —— 客户端输入错
        raise HTTPException(status_code=400, detail=f"课件解析失败：{exc}") from exc
    except Exception as exc:  # noqa: BLE001 —— 向量化/写库等外部故障
        raise HTTPException(
            status_code=502, detail=f"入库失败：{type(exc).__name__}: {exc}"
        ) from exc
    return IngestResponse(
        filename=record["filename"],
        chunks=record["chunks"],
        collection=record["collection"],
        upload_id=record["upload_id"],
        size=record["size"],
        uploaded_at=record["uploaded_at"],
        deduplicated=record.get("deduplicated", False),
    )


@app.get("/ingest/history", response_model=list[UploadRecord])
def ingest_history() -> list[UploadRecord]:
    """上传历史（按上传时间倒序）。"""
    try:
        records = service.list_uploads()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"读取上传历史失败：{type(exc).__name__}: {exc}"
        ) from exc
    return [UploadRecord(**record) for record in records]


@app.get("/ingest/history/{upload_id}/download")
def download_upload(upload_id: str) -> FileResponse:
    """下载某次上传的原始 PDF。"""
    try:
        found = service.get_upload_file(upload_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"下载失败：{type(exc).__name__}: {exc}"
        ) from exc
    if found is None:
        raise HTTPException(status_code=404, detail=f"上传记录不存在：{upload_id}")

    path, record = found
    return FileResponse(
        path, media_type="application/pdf", filename=record["filename"]
    )


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


@app.get("/sessions", response_model=list[SessionSummary])
def sessions(limit: int = 20) -> list[SessionSummary]:
    """列出最近的会话（按最后更新时间倒序），供前端展示历史会话列表。"""
    try:
        return service.list_sessions(limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"读取会话列表失败：{type(exc).__name__}: {exc}"
        ) from exc


@app.get("/sessions/{thread_id}", response_model=SessionDetail)
def session_detail(thread_id: str) -> SessionDetail:
    """取某个会话的完整对话，用于切回历史会话继续聊。"""
    try:
        messages = service.get_session(thread_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"读取会话失败：{type(exc).__name__}: {exc}"
        ) from exc

    if not messages:
        raise HTTPException(status_code=404, detail=f"会话不存在或没有可展示的消息：{thread_id}")
    return SessionDetail(thread_id=thread_id, messages=messages)


@app.get("/plan/sessions", response_model=list[PlanSessionSummary])
def plan_sessions(limit: int = 20) -> list[PlanSessionSummary]:
    """列出最近的规划会话（供 /plan 页左侧展示历史）。"""
    try:
        return service.list_plan_sessions(limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"读取规划会话列表失败：{type(exc).__name__}: {exc}"
        ) from exc


@app.get("/plan/sessions/{thread_id}", response_model=PlanSessionDetail)
def plan_session_detail(thread_id: str) -> PlanSessionDetail:
    """取某个规划会话：各轮请求 + 最后一次执行的计划与产出。"""
    try:
        data = service.get_plan_session(thread_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502, detail=f"读取规划会话失败：{type(exc).__name__}: {exc}"
        ) from exc

    if data is None:
        raise HTTPException(status_code=404, detail=f"规划会话不存在：{thread_id}")
    return PlanSessionDetail(**data)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
