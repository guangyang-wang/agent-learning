"""防死循环模块（四层机制）。

   1. 最大轮次硬限制：iteration_count >= 5 强制结束
   2. 重复工具参数检测：相同 (tool_name, args_hash) 拒绝调用
   3. 信息增益评估：LLM 判断新结果是否带来新内容（启发式，非严格信息论）
   4. 工具失败重试限制：同一工具连续失败 2 次自动停止
"""

from agent.state import AgentState


class AntiLoopGuard:
    """防死循环守卫（占位）。"""

    MAX_ITERATION = 5
    MAX_TOOL_FAILURE = 2

    def check(self, state: AgentState) -> bool:
        """综合判断是否应终止循环。返回 True 表示应停止。"""
        # TODO(阶段6)：依次应用四层机制
        raise NotImplementedError("防死循环守卫待实现（阶段6）")
