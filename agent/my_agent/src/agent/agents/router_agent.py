"""路由调度 Agent。

职责：任务分类、模式切换、总流程控制。
挂载能力：分类器 + 路由。
"""


class RouterAgent:
    """路由调度 Agent（占位）。"""

    def __init__(self) -> None:
        # TODO(阶段5)：加载分类 prompt + 绑定分类规则
        self.system_prompt: str = ""

    def classify(self, user_input: str) -> str:
        """分类任务类型：simple / complex / debate。"""
        # TODO(阶段5)：LLM 分类 + 关键词规则双保险
        raise NotImplementedError
