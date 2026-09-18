"""Skill 基类。

定义技能的通用结构，具体技能继承实现。
"""


class BaseSkill:
    """技能基类（占位）。"""

    name: str = ""                       # 技能名
    description: str = ""                # 用途描述
    prompt_template: str = ""            # 专用 Prompt
    tools: list = []                     # 专用工具
    workflow: list[str] = []             # 流程模板（节点序列）

    def run(self, *args, **kwargs) -> str:
        """执行技能。"""
        # TODO(阶段7)：按 workflow 模板装配 prompt + 工具，走 ReAct
        raise NotImplementedError
