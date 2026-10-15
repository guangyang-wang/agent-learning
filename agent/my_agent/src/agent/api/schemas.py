"""请求/响应模型（Pydantic）。

Java 类比：Controller 层的 DTO（@RequestBody / @ResponseBody 对应的类），
把 HTTP 的 JSON 和业务对象解耦——接口签名只认这些模型，内部实现怎么变都不影响调用方。
"""

from pydantic import BaseModel, Field


# ==================== 简单任务：ReAct 单 Agent（/chat） ====================

class ChatRequest(BaseModel):
    """对话请求。"""

    user_input: str
    # 可选：会话 id（对应 Checkpointer 的 thread_id）。
    # 传了就接上该会话的历史 messages；不传由服务端生成并回传。
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """对话响应。"""

    task_type: str = "simple"
    output: str
    # 回传实际使用的 thread_id，方便客户端下一轮沿用（短期记忆的钥匙）。
    thread_id: str


# ==================== 复杂任务：Plan-and-Execute（/plan） ====================

class PlanRequest(BaseModel):
    """复杂任务请求。"""

    user_input: str


class PlanStep(BaseModel):
    """计划中的单个子任务（对应 plan_graph.py 里 plan 列表的一个元素）。"""

    id: str
    desc: str
    agent: str
    deps: list[str] = Field(default_factory=list)
    status: str


class PlanResponse(BaseModel):
    """复杂任务响应：整条流水线的计划 + 中间产出 + 最终产出。"""

    task_type: str = "complex"
    plan: list[PlanStep]
    # {子任务id: 产出文本}，便于观察每一步各自产出了什么
    subtask_results: dict[str, str] = Field(default_factory=dict)
    final_output: str
    replan_count: int = 0


# ==================== 课件入库（/ingest） ====================

class IngestResponse(BaseModel):
    """课件上传结果。"""

    filename: str
    chunks: int
    collection: str


# ==================== 检索调试（/retrieve） ====================

class RetrieveRequest(BaseModel):
    """检索请求。"""

    query: str
    top_k: int = 4


class RetrieveResponse(BaseModel):
    """检索响应。

    hit_private：是否命中用户私有库（课件）。
    False 表示没在课件里找到依据，上层应标注「无课件依据」而非让模型编造。
    """

    chunks: list[str]
    hit_private: bool
