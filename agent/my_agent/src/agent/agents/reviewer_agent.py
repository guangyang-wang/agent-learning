"""评审辩论 Agent。

职责：代码审查、论文纠错、多 Agent 博弈评审。
挂载能力：RAG + 分析工具。
"""


class ReviewerAgent:
    """评审辩论 Agent（占位）。"""

    def __init__(self) -> None:
        pass

    def review(self, content: str) -> str:
        """给出评审意见，须引用原文依据。"""
        # TODO(阶段4)：立论/批判/仲裁三个对等角色
        raise NotImplementedError
