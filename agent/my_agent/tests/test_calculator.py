"""calculator 工具 + create_agent 手动演示（**不是 pytest 用例**）。

这段代码会真的调用 LLM，所以放在 __main__ 里，避免 pytest 收集时触网。
手动运行：python tests/test_calculator.py
"""


def _demo() -> None:
    from agent.llm.factory import get_llm
    from agent.tools.registry import build_default_registry
    from langchain.agents import create_agent
    from rich import print as rprint

    registry = build_default_registry()
    model = get_llm()
    agent = create_agent(
        model=model,
        tools=registry.all_tools(),
        system_prompt=(
            "你是一个计算助手，你能接收用户的消息，判断是否包含计算消息，"
            "然后生成响应的数学表达式，调用calculator工具去执行，"
            "calculator接收的数学表达式格式在这个工具的描述中。"
        ),
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": "请你计算9的平方根+6的平方"}]}
    )
    rprint(result)


if __name__ == "__main__":
    _demo()