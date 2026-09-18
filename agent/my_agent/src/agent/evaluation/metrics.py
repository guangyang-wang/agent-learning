"""评估指标统计。

指标（对应文档第十一章）：
    - 任务分类准确率        > 90%
    - 答案正确率            量化基准
    - 单任务平均工具调用轮数 验证防死循环有效
    - 单任务平均 token 成本  多 Agent 辩论成本可控
    - 平均响应延迟          简单任务 < 5s
"""


def calc_classification_accuracy(predictions: list[str], labels: list[str]) -> float:
    """分类准确率。"""
    # TODO(阶段8)
    raise NotImplementedError


def calc_avg_tool_rounds(tool_history: list) -> float:
    """平均工具调用轮数。"""
    # TODO(阶段8)
    raise NotImplementedError


def calc_avg_token_cost(runs: list) -> float:
    """平均 token 成本。"""
    # TODO(阶段8)
    raise NotImplementedError


def calc_avg_latency(runs: list) -> float:
    """平均响应延迟。"""
    # TODO(阶段8)
    raise NotImplementedError
