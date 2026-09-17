"""Verilog / Python 代码实验技能。"""

from agent.skills.base import BaseSkill


class CodeExperimentSkill(BaseSkill):
    """代码生成、仿真、调试（占位）。"""

    name = "code_experiment"
    description = "Verilog/Python 代码生成、沙箱仿真、报错修复"
