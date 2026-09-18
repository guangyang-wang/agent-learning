"""智能路由层（系统大脑）。

职责：任务复杂度分类器 + 动态路由三张 LangGraph 子图。

    simple  -> react 子图（单 Agent ReAct）
    complex -> plan 子图（Plan-and-Execute + 多 Agent 流水线）
    debate  -> debate 子图（多 Agent 对等辩论）

Java 类比：入口 Controller / 路由分发器，按请求类型转发到不同 Handler。
"""

from langgraph.graph import StateGraph

from agent.state import AgentState


def classifier_node(state: AgentState) -> dict:
    """任务复杂度分类器节点。

    返回 {"task_type": "simple" | "complex" | "debate"}。

    设计：分类器 LLM + 规则双保险（文档 2.3 / 场景四），支持用户手动纠正。
    """
    # TODO(阶段5)：LLM 分类 + 关键词规则兜底
    raise NotImplementedError("分类器节点待实现（阶段5）")


def route_edge(state: AgentState) -> str:
    """条件边：按 task_type 分流到对应子图。"""
    return state["task_type"]


def build_parent_graph() -> StateGraph:
    """组装父图：classifier 节点 + 三张子图 + 条件边。"""
    # TODO(阶段5)：用 add_node 包装三个子图，add_conditional_edges 分流
    raise NotImplementedError("父图组装待实现（阶段5：三图合一）")
