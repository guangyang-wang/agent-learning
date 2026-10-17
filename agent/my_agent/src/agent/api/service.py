"""服务层（用例层）—— CLI 与 HTTP 共用的业务入口。

职责：把阶段 1-3 已实现的能力（ReAct 问答 / Plan-and-Execute / 课件入库 / 检索）
包装成与「怎么调用」无关的用例函数。这样 main.py（命令行）和 app.py（HTTP）
都调同一套逻辑，不必两处各写一份 invoke。

Java 类比：@Service 层。Controller（app.py）只管收请求、校验、转异常，
业务逻辑落在 Service；命令行入口相当于另一个调用方（比如定时任务），复用同一个 Service。

生命周期（关键）：
    图（graph）和 checkpointer 做成**进程级单例**，由 app.py 的 lifespan 在启动时 init() 一次。
    否则每来一个请求就 build_react_graph() + 新建一条 sqlite 连接，既慢又浪费句柄。
"""

import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage

from agent.graph.plan_graph import build_plan_graph
from agent.graph.react_graph import build_react_graph
from agent.memory.short_term import get_checkpointer
from agent.rag import upload_store
from agent.rag.ingest import ingest_bytes
from agent.rag.retriever import retrieve_with_fallback
from agent.rag.vector_store import COLLECTION_PRIVATE

# 进程级单例（模块加载时为空，由 init() 填充）
_react_graph = None
_plan_graph = None


def init() -> None:
    """构建并缓存两张图 + checkpointer（幂等：已建过就直接返回）。

    由 FastAPI 的 lifespan 在启动时调用；测试可提前把 _react_graph/_plan_graph
    塞成桩对象，init() 会短路，从而不触发真实建图 / 开 sqlite。
    """
    global _react_graph, _plan_graph
    if _react_graph is not None:
        return

    checkpointer = get_checkpointer()
    # SqliteSaver 构造时不会建表，必须显式 setup()（幂等：建表语句带 IF NOT EXISTS）。
    # MemorySaver 没有 setup，用 hasattr 兼容两种实现。
    if hasattr(checkpointer, "setup"):
        checkpointer.setup()

    _react_graph = build_react_graph(checkpointer=checkpointer)
    _plan_graph = build_plan_graph(checkpointer=checkpointer)


def answer(question: str, thread_id: str | None = None) -> tuple[str, str]:
    """简单任务：跑一次 ReAct 问答，返回 (回答文本, 实际使用的 thread_id)。

    同一个 thread_id 连续多轮，会接上该会话的历史 messages（短期记忆）。
    未传 thread_id 时生成一个并回传，供客户端下一轮沿用。
    """
    if _react_graph is None:
        init()

    tid = thread_id or uuid.uuid4().hex
    result = _react_graph.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "user_input": question,
            "iteration_count": 0,
        },
        config={"configurable": {"thread_id": tid}},
    )
    return result["messages"][-1].content, tid


def execute_plan(question: str, thread_id: str | None = None) -> tuple[dict, str]:
    """复杂任务：跑一次 Plan-and-Execute 子图，返回 (完整 State, 实际使用的 thread_id)。

    与 /chat 一样用 thread_id 挂短期记忆：同一 id 续跑时，planner 能看到此前
    的请求（存在 plan_messages），从而理解「它 / 刚才那个」等指代。
    未传 thread_id 时生成一个并回传，供客户端下一轮沿用。
    """
    if _plan_graph is None:
        init()

    tid = thread_id or uuid.uuid4().hex
    state = _plan_graph.invoke(
        {
            "user_input": question,
            "plan_messages": [HumanMessage(content=question)],
            "messages": [],
            "iteration_count": 0,
        },
        config={"configurable": {"thread_id": tid}, "recursion_limit": 60},
    )
    return state, tid


def final_output(plan: list[dict], results: dict) -> tuple[str | None, str]:
    """从子任务产出里挑出「最终输出」。

    优先取「没人依赖它」的收尾子任务（sink）——它代表整条流水线的终点产出。
    若该子任务没有产出（失败/被放弃），退回到最后一个有产出的子任务。
    """
    depended = {dep for t in plan for dep in t.get("deps", [])}
    sinks = [t for t in plan if t["id"] not in depended]
    for t in reversed(sinks):
        if t["id"] in results:
            return t["id"], results[t["id"]]
    for t in reversed(plan):
        if t["id"] in results:
            return t["id"], results[t["id"]]
    return None, "(没有可用产出)"


def ingest_upload(filename: str, data: bytes) -> dict:
    """把上传的 PDF 入库，保存原文件 + 元数据，返回上传记录。

    按内容去重：sha256 相同的文件直接复用已有记录，不重复向量化，
    避免同一份课件在检索结果里重复命中。
    """
    digest = upload_store.sha256_of(data)
    existing = upload_store.find_by_sha256(digest)
    if existing is not None:
        return {**existing, "deduplicated": True}

    chunks = ingest_bytes(data, filename)
    record = upload_store.save_upload(
        data, filename, chunks, COLLECTION_PRIVATE, digest
    )
    return {**record, "deduplicated": False}


def list_uploads() -> list[dict]:
    """上传历史（按时间倒序）。"""
    return upload_store.list_uploads()


def get_upload_file(upload_id: str) -> tuple[Path, dict] | None:
    """取下载所需的（文件路径, 记录）；不存在返回 None。"""
    return upload_store.get_upload_file(upload_id)


def search(query: str, top_k: int = 4) -> tuple[list[str], bool]:
    """检索课件片段，返回 (片段列表, 是否命中私有课件库)。"""
    return retrieve_with_fallback(query, top_k)


# ==================== 会话历史 ====================
# ReAct 图的每轮状态都被 Checkpointer 写进 sqlite（按 thread_id 分），
# 所以「历史会话」不需要新存储，只是把已有 checkpoint 读出来给前端用。

_PREVIEW_LEN = 40
_SCAN_LIMIT = 500  # list 的扫描上限，防止会话很多时全表遍历


def _role_of(message) -> str | None:
    """把 LangChain 消息类型映射成前端用的角色；工具消息返回 None（不展示）。"""
    name = type(message).__name__
    if name == "HumanMessage":
        return "user"
    if name == "AIMessage":
        return "assistant"
    return None


def _text_of(message) -> str:
    """取消息文本。多模态内容块（list）只拼其中的 text 部分。"""
    content = getattr(message, "content", "") or ""
    if isinstance(content, list):
        content = "".join(
            block.get("text", "") for block in content if isinstance(block, dict)
        )
    return content.strip()


def visible_messages(messages: list) -> list[dict]:
    """只保留「用户提问」和「有正文的 AI 回答」。

    丢掉两类噪声：
        - ToolMessage（工具返回，不该出现在对话历史里）
        - 只带 tool_calls、content 为空的 AIMessage（模型调工具那一轮，没有正文）
    """
    out: list[dict] = []
    for m in messages:
        role = _role_of(m)
        if role is None:
            continue
        text = _text_of(m)
        if not text:
            continue
        out.append({"role": role, "content": text})
    return out


def list_sessions(limit: int = 20) -> list[dict]:
    """列出最近的会话（按最后更新时间倒序）。

    实现上不依赖 checkpointer 的返回顺序：遍历扫描窗口内的所有快照，
    每个 thread 只留 ts 最大的那条，最后统一排序取前 limit 条。
    """
    checkpointer = get_checkpointer()

    latest: dict[str, dict] = {}
    for tup in checkpointer.list(None, limit=_SCAN_LIMIT):
        configurable = tup.config["configurable"]
        if configurable.get("checkpoint_ns"):
            continue  # 子图的 checkpoint 不算独立会话

        thread_id = configurable["thread_id"]
        updated_at = tup.checkpoint.get("ts", "")
        previous = latest.get(thread_id)
        if previous is not None and previous["updated_at"] >= updated_at:
            continue  # 该会话已有更新的快照

        messages = visible_messages(
            (tup.checkpoint.get("channel_values") or {}).get("messages") or []
        )
        if not messages:
            continue

        first_user = next((m["content"] for m in messages if m["role"] == "user"), "")
        latest[thread_id] = {
            "thread_id": thread_id,
            "updated_at": updated_at,
            "message_count": len(messages),
            "preview": first_user[:_PREVIEW_LEN] or "(无提问)",
        }

    ordered = sorted(latest.values(), key=lambda s: s["updated_at"], reverse=True)
    return ordered[:limit]


def get_session(thread_id: str) -> list[dict]:
    """取某个会话最新的可展示对话；会话不存在时返回空列表。"""
    checkpointer = get_checkpointer()
    tup = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
    if tup is None:
        return []
    return visible_messages(
        (tup.checkpoint.get("channel_values") or {}).get("messages") or []
    )


# ==================== 规划（Plan）会话历史 ====================
# Plan 图把每轮的「用户请求」存进 plan_messages（与 chat 的 messages 分开），
# 所以这里单开一套列表/详情读取逻辑，和上面的 chat 会话互不干扰。

def plan_texts(channel_values: dict) -> list[str]:
    """从状态的 plan_messages 取出各轮用户请求文本。

    入参既能是 checkpoint 的 channel_values，也能是 invoke 返回的完整 State
    （两者都含 plan_messages 键）。
    """
    return [
        str(getattr(m, "content", "")).strip()
        for m in (channel_values.get("plan_messages") or [])
        if str(getattr(m, "content", "")).strip()
    ]


def list_plan_sessions(limit: int = 20) -> list[dict]:
    """列出最近的规划会话（按最后更新时间倒序）。

    与 list_sessions 同思路：遍历扫描窗口，每个 thread 只留 ts 最大的快照，
    再统一排序取前 limit；没有 plan_messages 的 thread（chat 会话）一律跳过。
    """
    checkpointer = get_checkpointer()

    latest: dict[str, dict] = {}
    for tup in checkpointer.list(None, limit=_SCAN_LIMIT):
        configurable = tup.config["configurable"]
        if configurable.get("checkpoint_ns"):
            continue  # 子图（executor:*）的 checkpoint 不算独立会话

        texts = plan_texts(tup.checkpoint.get("channel_values") or {})
        if not texts:
            continue  # 不是规划会话

        thread_id = configurable["thread_id"]
        updated_at = tup.checkpoint.get("ts", "")
        previous = latest.get(thread_id)
        if previous is not None and previous["updated_at"] >= updated_at:
            continue

        latest[thread_id] = {
            "thread_id": thread_id,
            "updated_at": updated_at,
            "request_count": len(texts),
            "preview": texts[0][:_PREVIEW_LEN] or "(无提问)",
        }

    ordered = sorted(latest.values(), key=lambda s: s["updated_at"], reverse=True)
    return ordered[:limit]


def get_plan_session(thread_id: str) -> dict | None:
    """取某个规划会话：各轮请求 + 最后一次执行的计划/产出/最终输出。

    plan_messages 累积多轮请求；plan / subtask_results 是「最后一次运行」的，
    因为 planner 每轮会重置执行态（见 plan_graph.planner_node）。
    返回 None 表示该 thread 不是规划会话（不存在或没有 plan_messages）。
    """
    checkpointer = get_checkpointer()
    tup = checkpointer.get_tuple({"configurable": {"thread_id": thread_id}})
    if tup is None:
        return None

    channel_values = tup.checkpoint.get("channel_values") or {}
    texts = plan_texts(channel_values)
    if not texts:
        return None

    plan = channel_values.get("plan") or []
    results = channel_values.get("subtask_results") or {}
    _, output = final_output(plan, results)
    return {
        "thread_id": thread_id,
        "requests": texts,
        "plan": plan,
        "subtask_results": results,
        "final_output": output,
        "replan_count": channel_values.get("replan_count", 0),
    }
