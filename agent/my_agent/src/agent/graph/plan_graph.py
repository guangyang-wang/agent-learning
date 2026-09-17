"""Plan-and-Execute 子图（阶段3）。

复杂流程任务：顶层规划 -> 多 Agent 按依赖序执行 -> 汇总。
每个子 Agent 内部仍是 ReAct 循环（复用底层推理底座）。

关键点：
    - 计划结构校验，失败重新规划
    - 子任务按依赖拓扑序执行
    - 子任务失败 -> 局部重规划（只重跑失败部分，保留成功结果）
"""

from langgraph.graph import StateGraph

from agent.state import AgentState


def planner_node(state: AgentState) -> dict:
    """规划 Agent 生成任务计划 plan，做结构校验。"""
    # TODO(阶段3)：生成 [{id, desc, agent, deps, status}]，校验依赖完整
    raise NotImplementedError("planner 节点待实现（阶段3）")


def dispatcher_node(state: AgentState) -> dict:
    """按拓扑序分发子任务，更新 current_subtask_id。"""
    # TODO(阶段3)：依赖序执行
    raise NotImplementedError("dispatcher 节点待实现（阶段3）")


def replan_node(state: AgentState) -> dict:
    """局部重规划：子任务失败时回填失败信息，只重规划失败部分。"""
    # TODO(阶段3)：更新 plan 中失败子任务，保留成功子任务结果
    raise NotImplementedError("replan 节点待实现（阶段3）")


def build_plan_graph() -> StateGraph:
    """构建 Plan-and-Execute 子图。"""
    # TODO(阶段3)：planner -> dispatcher -> (子 Agent 流水线) -> replan 兜底
    raise NotImplementedError("Plan 子图待实现（阶段3）")
