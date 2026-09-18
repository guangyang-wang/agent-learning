"""ReAct 子图测试（占位）。"""


def test_placeholder() -> None:
    """占位测试，阶段1实现后替换为真实断言。"""
    # TODO(阶段1)：验证 agent->tools 循环正确流转、防死循环生效
    assert True


from agent.llm.factory import get_llm
from rich import print as rprint
baseChatModel=get_llm()
result=baseChatModel.invoke("你是谁")
rprint(result)
rprint(result.content)
