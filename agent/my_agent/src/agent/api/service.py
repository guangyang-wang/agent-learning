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

from langchain_core.messages import HumanMessage

from agent.graph.plan_graph import build_plan_graph
from agent.graph.react_graph import build_react_graph
from agent.memory.short_term import get_checkpointer
from agent.rag.ingest import ingest_bytes
from agent.rag.retriever import retrieve_with_fallback

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
    _plan_graph = build_plan_graph()


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


def execute_plan(question: str) -> dict:
    """复杂任务：跑一次 Plan-and-Execute 子图，返回完整 State。

    不接 Checkpointer（每次全新会话）——Plan 图的记忆/恢复是后续阶段的议题。
    """
    if _plan_graph is None:
        init()

    return _plan_graph.invoke(
        {"user_input": question, "messages": [], "iteration_count": 0},
        config={"recursion_limit": 60},
    )


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


def ingest_upload(filename: str, data: bytes) -> int:
    """把上传的 PDF 字节入库，返回写入的 chunk 数。"""
    return ingest_bytes(data, filename)


def search(query: str, top_k: int = 4) -> tuple[list[str], bool]:
    """检索课件片段，返回 (片段列表, 是否命中私有课件库)。"""
    return retrieve_with_fallback(query, top_k)
