"""ReAct 子图（阶段1，最小闭环）。

单 Agent 循环：思考 -> 调工具 -> 观察 -> 再思考，直到能作答。

LangGraph 实现：agent 节点 <-> tools 节点，用 add_conditional_edges 判断
    「继续调工具」还是「结束」；循环内加 guard（防死循环见 safety/anti_loop.py）。

Java 类比：一个 while 循环里反复「调接口拿结果 -> 判断是否继续」。
"""

from langgraph.graph import StateGraph

from agent.state import AgentState


def agent_node(state: AgentState) -> dict:
    """LLM 思考节点：绑定工具，产出 tool_calls 或最终回答。"""
    # TODO(阶段1)：create_react_agent 或手写 agent 节点
    raise NotImplementedError("ReAct agent 节点待实现（阶段1）")


def should_continue(state: AgentState) -> str:
    """条件边：判断继续调工具还是结束。

    同时在此处接入防死循环 guard（见 safety/anti_loop.py）。
    """
    # TODO(阶段1/6)：有 tool_calls -> "tools"；否则 -> "end"
    raise NotImplementedError("ReAct 条件边待实现")


def build_react_graph() -> StateGraph:
    """构建 ReAct 子图。"""
    # TODO(阶段1)：add_node(agent/tools) + add_conditional_edges
    raise NotImplementedError("ReAct 子图待实现（阶段1）")
