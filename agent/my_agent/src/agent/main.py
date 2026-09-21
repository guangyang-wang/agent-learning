"""程序入口 —— 阶段 2：ReAct + Checkpointer 短期记忆。

复用 graph/react_graph.py 编译好的 ReAct 图，喂入用户问题，
观察「思考 -> 调工具 -> 观察 -> 作答」完整循环；
同一 thread_id 连续多轮问答，验证 Checkpointer 跨轮记忆生效。

Java 类比：main 方法 = 启动一次「会话」，调用工作流引擎跑完一个请求；
    thread_id = 流程实例 ID，同一个实例多轮交互能记住上文。
"""

import sys

from langchain_core.messages import HumanMessage

from agent.graph.react_graph import build_react_graph
from agent.memory.short_term import get_checkpointer


def run_qa(question: str, thread_id: str = "default") -> str:
    """跑一次问答：构建 ReAct 图 -> 传入问题 -> 返回最终答案。

    初始 state 三个字段都要给齐（对应 state.py 的 AgentState）：
        messages         只放一条 HumanMessage（本轮问题）
        user_input       原始问题（agent_node 当前暂未读，先照写）
        iteration_count  初始 0（阶段 6 防死循环会读它做轮次上限）

    thread_id 是 Checkpointer 定位会话的键：同一个 thread_id 的多次调用，
    LangGraph 会自动加载上一轮 checkpoint，把历史 messages 接上，实现短期记忆。
    """
    graph = build_react_graph(checkpointer=get_checkpointer())

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "user_input": question,
            "iteration_count": 0,
        },
        config={"configurable": {"thread_id": thread_id}},
    )

    # 循环结束后，messages 最后一条是「不带 tool_calls」的 AIMessage（最终回答）
    return result["messages"][-1].content


def main() -> None:
    # Windows 控制台默认 GBK，打印中文 / ² 等字符会抛 UnicodeEncodeError，
    # 这里把 stdout 切成 UTF-8；部分 IDE 会重定向 stdout（没有 reconfigure），跳过即可。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    # 演示短期记忆：同一个 thread_id 连续两轮，第二轮依赖第一轮的答案。
    # 第二轮「刚才那个数再加 1」若答对，说明 Checkpointer 已把第一轮上下文接上。
    thread_id = "demo-user-1"

    q1 = "请你计算 9 的平方根"
    print(f"[第1轮] {q1}")
    a1 = run_qa(q1, thread_id=thread_id)
    print(f"[答] {a1}\n")

    q2 = "刚才那个数再加 1 等于多少？"
    print(f"[第2轮] {q2}")
    a2 = run_qa(q2, thread_id=thread_id)
    print(f"[答] {a2}")


if __name__ == "__main__":
    main()