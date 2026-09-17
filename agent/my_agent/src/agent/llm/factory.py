"""LLM 模型工厂。

按环境变量决定返回哪个模型的 ChatModel，屏蔽各家 SDK 差异。
LangChain 统一接口（BaseChatModel）是「可插拔」的关键。

Java 类比：工厂模式 + 面向接口编程，调用方只依赖 BaseChatModel 接口，
    切换实现（DeepSeek → OpenAI → Claude）不改业务代码。
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain.chat_models import init_chat_model
from agent.config import settings


def get_llm(model_name: str | None = None) -> BaseChatModel:
    """返回统一的 ChatModel 实例。


    当前默认 DeepSeek；后续可扩展：
        - 读取环境变量 LLM_PROVIDER 决定 provider
        - provider == "deepseek" -> ChatDeepSeek
        - provider == "openai"   -> ChatOpenAI
        - provider == "anthropic"-> ChatAnthropic
    """
    # TODO(阶段1)：接入 langchain-deepseek
    # from langchain_deepseek import ChatDeepSeek
    # return ChatDeepSeek(
    #     model=model_name or settings.deepseek_model,
    #     api_key=settings.deepseek_api_key,
    #     base_url=settings.deepseek_base_url,
    # )
    # raise NotImplementedError("LLM 工厂待实现（阶段1：接入 DeepSeek）")
    return init_chat_model("deepseek-flash")
