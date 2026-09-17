"""论文评审技能。"""

from agent.skills.base import BaseSkill


class PaperReviewSkill(BaseSkill):
    """课程论文评审、逻辑漏洞检测、修改建议（占位）。"""

    name = "paper_review"
    description = "论文评审、逻辑漏洞检测、给出修改建议"
