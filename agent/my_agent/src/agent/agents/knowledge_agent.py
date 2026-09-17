"""知识检索 Agent。

职责：RAG 课件解析、知识点提取、资料溯源。
挂载能力：RAG + MCP。
"""


class KnowledgeAgent:
    """知识检索 Agent（占位）。"""

    def __init__(self) -> None:
        # TODO(阶段2)：绑定 retriever 工具 + 溯源 prompt
        pass

    def retrieve(self, query: str) -> list[str]:
        """检索相关知识，返回溯源片段。"""
        # TODO(阶段2)：调用 rag/retriever.py
        raise NotImplementedError
