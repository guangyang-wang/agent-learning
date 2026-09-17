"""多 Agent 对等辩论子图（阶段4）。

主观评审任务：立论 / 批判 / 仲裁 三个对等 Agent 轮流发言，写入消息池，
    满足收敛条件后由仲裁 Agent 输出评审报告。

关键点：
    - 无预先规划（独立于 Plan 架构的第二类多 Agent 形态）
    - 观点语义去重，防止重复
    - 最大辩论轮次 + 收敛条件，防止永不收敛 / token 爆炸
"""

from langgraph.graph import StateGraph

from agent.state import AgentState


def propose_node(state: AgentState) -> dict:
    """立论 Agent：总结优点，必须引用原文依据。"""
    # TODO(阶段4)
    raise NotImplementedError("立论节点待实现（阶段4）")


def critique_node(state: AgentState) -> dict:
    """批判 Agent：质疑漏洞，必须引用 RAG 依据。"""
    # TODO(阶段4)
    raise NotImplementedError("批判节点待实现（阶段4）")


def arbitrate_node(state: AgentState) -> dict:
    """仲裁 Agent：输出最终评审报告。"""
    # TODO(阶段4)
    raise NotImplementedError("仲裁节点待实现（阶段4）")


def should_converge(state: AgentState) -> str:
    """收敛条件：观点重复 / 达到最大轮次 -> 结束。"""
    # TODO(阶段4)
    raise NotImplementedError("收敛判断待实现（阶段4）")


def build_debate_graph() -> StateGraph:
    """构建多 Agent 辩论子图。"""
    # TODO(阶段4)
    raise NotImplementedError("辩论子图待实现（阶段4）")
