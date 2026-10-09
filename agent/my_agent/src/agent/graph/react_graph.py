"""ReAct 子图（阶段1，最小闭环）。

单 Agent 循环：思考 -> 调工具 -> 观察 -> 再思考，直到能作答。

LangGraph 实现：agent 节点 <-> tools 节点，用 add_conditional_edges 判断
    「继续调工具」还是「结束」；循环内加 guard（防死循环见 safety/anti_loop.py）。

Java 类比：一个 while 循环里反复「调接口拿结果 -> 判断是否继续」。
"""

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.graph.nodes import tools_node
from agent.llm.factory import get_llm
from agent.state import AgentState
from agent.tools.registry import build_default_registry


def make_agent_node(system_prompt: str | None = None):
    """工厂：造一个 LLM 思考节点，可选把角色 system prompt 前置到消息最前。

    阶段3 复用点：knowledge / code / writer / reviewer 四个子 Agent 共用同一个
    ReAct 循环，差异只在「角色人格」——用工厂把 system_prompt 注入循环，
    循环逻辑（思考→调工具→观察）本身一行不改，这正是「1 底座 + 2 编排」里
    上层编排复用底层推理的落地方式。

    Java 类比：模板方法里把易变的 system prompt 作为参数传入，
    不变的循环骨架（agent↔tools）留在图结构里。
    """
    def agent_node(state: AgentState) -> dict:
        llm = get_llm()
        tools = build_default_registry().all_tools()
        llm_with_tools = llm.bind_tools(tools)

        # system prompt 只用于本次调用，不写回 state（避免每轮循环重复堆积）
        messages = list(state["messages"])
        if system_prompt:
            messages = [SystemMessage(content=system_prompt), *messages]

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    return agent_node


# 默认（无角色）思考节点：阶段1/2 单 Agent 直接 build_react_graph() 时走它。
agent_node = make_agent_node()


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


def build_react_graph(checkpointer=None, system_prompt: str | None = None):
    """构建 ReAct 子图：agent <-> tools 循环 + 条件边。

    图结构：
        START -> agent
        agent --(条件)--> tools   （最后一条消息带 tool_calls）
        agent --(条件)--> END     （无 tool_calls，直接回答）
        tools -> agent             （执行完工具，循环回 agent 再思考）

    参数：
        checkpointer：可选，传入 Checkpointer 则启用短期记忆（跨轮上下文）。
            阶段 2 起由 main.py 传入 memory.get_checkpointer()；不传则保持
            阶段 1 的无状态行为（每次 invoke 都是全新会话）。
        system_prompt：可选角色提示词。阶段3 子 Agent（executor）按子任务挂载
            对应角色时传入，让同一个 ReAct 循环扮演 knowledge/code/writer/reviewer。

    返回编译后的图（CompiledStateGraph）：
        - 阶段1：在 main.py 里直接 .invoke() 跑问答
        - 阶段3：被 executor_node 按子任务复用（换 system_prompt，循环不变）
        - 阶段5：作为子图被父图 add_node 嵌入（复用同一 AgentState）
    """
    graph = StateGraph(AgentState)

    graph.add_node("agent", make_agent_node(system_prompt))
    graph.add_node("tools", tools_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END},
    )
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=checkpointer)
