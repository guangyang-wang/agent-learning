"""ReAct 子图（阶段1，最小闭环）。

单 Agent 循环：思考 -> 调工具 -> 观察 -> 再思考，直到能作答。

LangGraph 实现：agent 节点 <-> tools 节点，用 add_conditional_edges 判断
    「继续调工具」还是「结束」；循环内加 guard（防死循环见 safety/anti_loop.py）。

Java 类比：一个 while 循环里反复「调接口拿结果 -> 判断是否继续」。
"""

from langgraph.graph import END, START, StateGraph

from agent.graph.nodes import tools_node
from agent.llm.factory import get_llm
from agent.state import AgentState
from agent.tools.registry import build_default_registry


def agent_node(state: AgentState) -> dict:
    """LLM 思考节点：绑定工具，产出 tool_calls 或最终回答。

    逻辑：
        1. 取出统一 ChatModel（可插拔，默认 DeepSeek）
        2. bind_tools 把工具描述注入模型，让模型知道何时该调哪个工具
        3. 用整段 messages 历史调用模型，模型返回一条 AIMessage
           （可能带 tool_calls，也可能是最终回答）
    """
    llm = get_llm()
    tools = build_default_registry().all_tools()
    llm_with_tools = llm.bind_tools(tools)

    response = llm_with_tools.invoke(state["messages"])
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    """条件边：判断继续调工具还是结束。

    规则：看 messages 里最后一条 AIMessage 是否带 tool_calls。
        - 带 tool_calls -> "tools"（去执行工具，然后循环回 agent）
        - 不带         -> "end"  （模型已给出最终回答，结束）

    阶段6 会在此处接入防死循环 guard（读 iteration_count 做轮次硬上限，
    见 safety/anti_loop.py），当前先按最简规则判断。
    """
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return "end"


def build_react_graph():
    """构建 ReAct 子图：agent <-> tools 循环 + 条件边。

    图结构：
        START -> agent
        agent --(条件)--> tools   （最后一条消息带 tool_calls）
        agent --(条件)--> END     （无 tool_calls，直接回答）
        tools -> agent             （执行完工具，循环回 agent 再思考）

    返回编译后的图（CompiledStateGraph）：
        - 阶段1：在 main.py 里直接 .invoke() 跑问答
        - 阶段5：作为子图被父图 add_node 嵌入（复用同一 AgentState）
    """
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile()
