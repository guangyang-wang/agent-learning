"""LLM 可插拔层。

统一模型创建入口，通过环境变量在 DeepSeek / OpenAI / Claude 之间切换。
"""

from agent.llm.factory import get_llm

__all__ = ["get_llm"]
