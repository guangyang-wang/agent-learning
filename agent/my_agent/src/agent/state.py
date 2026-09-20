"""全局状态 Schema（AgentState）—— 阶段 1 最小版本。

作用：
    LangGraph 的核心契约：ReAct 循环里 agent / tools 两个节点共享同一份状态，
    通过读写这些字段在节点之间传递信息。

Java 类比：
    - AgentState 是整个工作流引擎共享的「流程上下文对象（Context / DTO）」
    - `messages` 上的 `add_messages` reducer ≈ 往 List 里 add() 追加，而不是重新赋值覆盖

阶段说明：
    阶段 1 只定义最小字段（user_input / messages / iteration_count）。
    后续阶段要加的字段先在这里留空标注（暂不实现，用到时再补）：
      - 阶段 2：rag_results（RAG 检索结果）、long_term_index（长期记忆索引）
      - 阶段 3：plan / current_subtask_id（任务计划 / 当前子任务）
      - 阶段 4：debate_messages / debate_round（辩论消息池 / 轮次）
      - 阶段 6：pending_tool_call（待用户确认的高危工具调用）
"""

from typing import Annotated, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """全局状态，ReAct 循环的 agent / tools 节点共享读写。"""

    # ---- 用户原始输入 ----
    # 作用：保存本轮用户提的问题，agent 节点从这里读取问题，作为第一轮思考的起点。
    user_input: str

    # ---- 对话消息（短期记忆载体）----
    # 作用：保存整段对话历史（用户消息 + AI 消息 + 工具消息），是短期记忆。
    # 关键：`add_messages` 是 reducer，实现「追加」而非「覆盖」——
    #       每个节点往里写消息时都是在原列表上追加，不会冲掉别人写入的消息。
    messages: Annotated[List[BaseMessage], add_messages]

    # ---- ReAct 循环计数器（防死循环的依据）----
    # 作用：每走一轮「agent 思考 → 调工具」就 +1；阶段 6 的防死循环机制
    #       会读这个字段做轮次硬上限，防止模型无限循环调工具。
    # 注意：初始调用时需置为 0（在入口处传入，见后续 main.py）。
    iteration_count: int