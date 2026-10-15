"""ReAct 子图测试（占位）。

注意：下面的 LLM 冒烟代码放在 __main__ 里，pytest 收集时不会执行
（否则每次跑 pytest 都会真的发一次 API 请求）。
手动运行：python tests/test_react_graph.py
"""


def test_placeholder() -> None:
    """占位测试，阶段1实现后替换为真实断言。"""
    # TODO(阶段1)：验证 agent->tools 循环正确流转、防死循环生效
    assert True


def _smoke() -> None:
    """手动冒烟：调一次 LLM 看是否能通。"""
    from agent.llm.factory import get_llm
    from rich import print as rprint

    base_chat_model = get_llm()
    result = base_chat_model.invoke("你是谁")
    rprint(result)
    rprint(result.content)


if __name__ == "__main__":
    _smoke()

