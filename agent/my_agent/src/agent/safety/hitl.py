"""工具安全人机确认（Human-in-the-loop）。

高危工具调用流程：
    Agent 生成调用参数 -> 安全拦截节点判断工具级别
        -> 高危：interrupt() 挂起，展示详情给用户
        -> 用户 同意 / 拒绝 / 修改参数
        -> Command(resume=...) 恢复执行

Java 类比：工作流引擎里「需要人工审批的挂起点」，审批通过后继续流转。
"""

from agent.state import AgentState


def intercept_tool_call(state: AgentState) -> bool:
    """判断当前工具调用是否需要人工确认。"""
    # TODO(阶段6)：查询工具级别，高危返回 True
    raise NotImplementedError("工具拦截待实现（阶段6）")


def request_approval(state: AgentState) -> None:
    """挂起等待用户确认（interrupt）。"""
    # TODO(阶段6)：LangGraph interrupt() 挂起，Command(resume=...) 恢复
    raise NotImplementedError("interrupt 待实现（阶段6）")
