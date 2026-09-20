"""程序入口 —— 阶段 1 最小闭环：跑通一个简单问答。

复用 graph/react_graph.py 编译好的 ReAct 图，喂入用户问题，
观察「思考 -> 调工具 -> 观察 -> 作答」完整循环。

Java 类比：main 方法 = 启动一次「会话」，调用工作流引擎跑完一个请求。
"""

import sys

from langchain_core.messages import HumanMessage

from agent.graph.react_graph import build_react_graph


def run_qa(question: str) -> str:
    """跑一次问答：构建 ReAct 图 -> 传入问题 -> 返回最终答案。

    初始 state 三个字段都要给齐（对应 state.py 的 AgentState）：
        messages         只放一条 HumanMessage（本轮问题）
        user_input       原始问题（agent_node 当前暂未读，先照写）
        iteration_count  初始 0（阶段 6 防死循环会读它做轮次上限）
    """
    graph = build_react_graph()

    result = graph.invoke(
        {
            "messages": [HumanMessage(content=question)],
            "user_input": question,
            "iteration_count": 0,
        }
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

    answer = run_qa("请你计算 9 的平方根 + 6 的平方")
    print(answer)


if __name__ == "__main__":
    main()