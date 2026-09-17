"""全局状态 Schema（AgentState）。

LangGraph 的核心契约：所有节点共享同一份状态，通过 TypedDict 定义字段类型。

Java 类比：
    - AgentState 是整个工作流引擎共享的「流程上下文对象（Context）」
    - `messages` 上的 `add_messages` reducer ≈ 往 List 里 append 而不是 set 覆盖
    - 三张子图（ReAct / Plan / Debate）只读写各自关心的字段，像多个 service 共享一个 DTO

设计要点：
    1. `messages` 用 `add_messages`，天然追加而非覆盖，是短期记忆的载体。
    2. 全局 schema 统一，避免子图间状态不兼容（场景四「动态切换」的前提）。
"""

from typing import Any, Dict, List, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """全局状态，各节点/子图共享。"""

    # ---- 用户输入与任务分类 ----
    user_input: str                                    # 用户原始提问
    task_type: str                                     # "simple" | "complex" | "debate"
    messages: List[BaseMessage]                        # 对话消息（短期记忆载体）
    # 注意：`add_messages` 是 reducer，需用 Annotated 声明才能实现「追加」语义：
    #   messages: Annotated[List[BaseMessage], add_messages]

    # ---- 规划相关（complex / Plan-and-Execute 模式） ----
    plan: List[Dict[str, Any]]                         # [{id, desc, agent, deps, status}]
    current_subtask_id: str                            # 当前执行的子任务 id

    # ---- 执行相关 ----
    rag_results: List[str]                             # RAG 检索结果
    tool_history: List[Dict[str, Any]]                 # [{tool, args, result, ts}]
    iteration_count: int                               # ReAct 循环计数器（防死循环依据）
    final_output: str                                  # 最终输出

    # ---- 人机确认（HITL）相关 ----
    pending_tool_call: Dict[str, Any]                  # 待用户确认的高危工具调用缓存

    # ---- 辩论相关（debate / 多 Agent 辩论模式） ----
    debate_messages: List[Dict[str, str]]              # [{role, content}] 辩论消息池
    debate_round: int                                  # 当前辩论轮次

    # ---- 长期记忆 ----
    long_term_index: List[str]                         # 长期记忆检索索引


# 说明：LangGraph 中带 reducer 的字段需写成 Annotated 形式。
# 真正落地时可定义如下（保留注释供后续实现时替换上方 messages 字段）：
#
#   from typing import Annotated
#   messages: Annotated[List[BaseMessage], add_messages]
