"""安全工具（自动执行，无需人机确认）。

示例：RAG 检索、公式计算。
"""


def rag_search(query: str) -> str:
    """RAG 检索工具。"""
    # TODO(阶段2)：调用 rag/retriever.py
    raise NotImplementedError


def calculator(expression: str) -> str:
    """公式/表达式计算工具。"""
    # TODO(阶段1)：安全 eval 或专用计算库
    raise NotImplementedError
