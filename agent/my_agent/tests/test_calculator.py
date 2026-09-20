from agent.llm.factory import get_llm
from agent.tools.registry import build_default_registry
from langchain.agents import create_agent
from rich import print as rprint

registry = build_default_registry()
deepseekModel = get_llm()
agent = create_agent(
    model=deepseekModel,
    tools=registry.all_tools(),
    system_prompt="你是一个计算助手，你能接收用户的消息，判断是否包含计算消息，然后生成响应的数学表达式，调用calculator工具去执行，calculator接收的数学表达式格式在这个工具的描述中。"
)

result=agent.invoke({"messages": [{"role": "user", "content": "请你计算9的平方根+6的平方"}]})

rprint(result)