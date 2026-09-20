"""共享节点函数。

各子图都会复用的节点逻辑（工具执行、结果汇总等），避免重复代码。

Java 类比：抽取出的公共方法 / 工具类。
"""

from langchain_core.messages import ToolMessage

from agent.state import AgentState
from agent.tools.registry import build_default_registry


def tools_node(state: AgentState) -> dict:
    """执行工具调用的通用节点（ReAct 循环的 tools 半边）。

    对应《架构设计》：
        agent 节点（LLM 思考） <-> tools 节点（执行工具）

    逻辑：
        1. 取 messages 里最后一条 AIMessage，读取它的 tool_calls
        2. 逐个执行工具，把返回值包成 ToolMessage 回填给模型
        3. 单个工具执行失败不中断整个循环，把错误文本回传
           （与 calculator 工具的 try/except 思路一致，让模型知道失败原因）
    """
    tools_by_name = {t.name: t for t in build_default_registry().all_tools()}

    last_message = state["messages"][-1]
    tool_messages: list[ToolMessage] = []

    for call in last_message.tool_calls:
        tool = tools_by_name.get(call["name"])
        if tool is None:
            content = f"未知工具：{call['name']}"
        else:
            try:
                content = str(tool.invoke(call["args"]))
            except Exception as exc:  # noqa: BLE001 —— 工具失败也要回传，别让循环崩掉
                content = f"工具执行失败：{exc}"

        tool_messages.append(
            ToolMessage(
                content=content,
                tool_call_id=call["id"],
                name=call["name"],
            )
        )

    return {"messages": tool_messages}


def finalize_node(state: AgentState) -> dict:
    """汇总中间结果，写入 final_output 字段。"""
    # TODO(阶段1)：把 agent 的最终 AIMessage 内容写入 final_output
    raise NotImplementedError("finalize 节点待实现")
