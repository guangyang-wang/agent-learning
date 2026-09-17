"""短期记忆。

用 LangGraph Checkpointer 持久化 State，跨轮次保留上下文。
是场景四「动态模式切换」时复用历史 messages 的基础。

Java 类比：流程实例的持久化存储（如 Activiti 的流程实例表）。
"""


def get_checkpointer() -> object:
    """返回 Checkpointer（MemorySaver / SqliteSaver 持久化）。"""
    # TODO(阶段2)：MemorySaver（内存）或 SqliteSaver（落盘）
    raise NotImplementedError("Checkpointer 待实现（阶段2）")
