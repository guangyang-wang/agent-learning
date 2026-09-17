"""共享节点函数。

各子图都会复用的节点逻辑（工具执行、结果汇总等），避免重复代码。

Java 类比：抽取出的公共方法 / 工具类。
"""

from agent.state import AgentState


def tools_node(state: AgentState) -> dict:
    """执行工具调用的通用节点（ReAct 循环的 tools 半边）。

    对应《架构设计》：
        agent 节点（LLM 思考） <-> tools 节点（执行工具）
    """
    # TODO(阶段1)：解析 messages 里最后一条 AIMessage 的 tool_calls 并执行
    raise NotImplementedError("tools 节点待实现（阶段1）")


def finalize_node(state: AgentState) -> dict:
    """汇总中间结果，写入 final_output 字段。"""
    # TODO(阶段1)：把 agent 的最终 AIMessage 内容写入 final_output
    raise NotImplementedError("finalize 节点待实现")
