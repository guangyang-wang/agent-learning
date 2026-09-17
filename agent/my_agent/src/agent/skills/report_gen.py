"""报告生成技能。"""

from agent.skills.base import BaseSkill


class ReportGenSkill(BaseSkill):
    """实验报告 / 文档结构化生成（占位）。"""

    name = "report_gen"
    description = "汇总中间结果，生成结构化实验报告"
