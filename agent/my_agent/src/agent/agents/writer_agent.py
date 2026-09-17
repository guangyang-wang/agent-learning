"""内容写作 Agent。

职责：报告、总结、文档结构化输出。
挂载能力：写作 Skill。
"""


class WriterAgent:
    """内容写作 Agent（占位）。"""

    def __init__(self) -> None:
        pass

    def write_report(self, context: dict) -> str:
        """从全局 State 汇总中间结果生成报告（而非重新生成，保证一致）。"""
        # TODO(阶段3)：加载 report_gen 技能 + 汇总 state
        raise NotImplementedError
