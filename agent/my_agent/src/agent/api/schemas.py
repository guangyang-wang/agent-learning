"""请求/响应模型（Pydantic）。

Java 类比：Controller 层的 DTO（@RequestBody / @ResponseBody 对应的类），
把 HTTP 的 JSON 和业务对象解耦——接口签名只认这些模型，内部实现怎么变都不影响调用方。
"""

from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

# 姓名：去首尾空白，禁止空字符串
UserName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


# ==================== 简单任务：ReAct 单 Agent（/chat） ====================

class ChatRequest(BaseModel):
    """对话请求。"""

    user_input: str
    # 使用人姓名：历史会话展示 + 共享部署时区分使用者
    user_name: UserName
    # 可选：会话 id（对应 Checkpointer 的 thread_id）。
    # 传了就接上该会话的历史 messages；不传由服务端生成并回传。
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """对话响应。"""

    task_type: str = "simple"
    output: str
    # 回传实际使用的 thread_id，方便客户端下一轮沿用（短期记忆的钥匙）。
    thread_id: str
    # 本次消耗后的全局剩余次数
    used: int = 0
    limit: int = 0
    remaining: int = 0


# ==================== 复杂任务：Plan-and-Execute（/plan） ====================

class PlanRequest(BaseModel):
    """复杂任务请求。"""

    user_input: str
    # 使用人姓名：历史规划展示 + 共享部署时区分使用者
    user_name: UserName
    # 可选：会话 id（对应 Checkpointer 的 thread_id）。
    # 传了就接上该会话此前的请求，planner 能理解上下文指代；不传由服务端生成并回传。
    thread_id: str | None = None


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
    # 回传实际使用的 thread_id，客户端下一轮沿用即可接上规划记忆。
    thread_id: str
    # 该 thread 累计的用户请求（含本轮），让前端能直接展示「本会话问过什么」。
    requests: list[str] = Field(default_factory=list)
    # 与 requests 一一对应的提问人姓名
    request_names: list[str] = Field(default_factory=list)
    # 本次消耗后的全局剩余次数
    used: int = 0
    limit: int = 0
    remaining: int = 0


# ==================== 课件入库（/ingest） ====================

class IngestResponse(BaseModel):
    """课件上传结果。"""

    filename: str
    chunks: int
    collection: str
    # 上传记录 id，用于下载原文件
    upload_id: str = ""
    size: int = 0
    uploaded_at: str = ""
    # 内容与历史记录完全相同（sha256 一致）时为 True，此时没有重复入库
    deduplicated: bool = False


class UploadRecord(BaseModel):
    """上传历史里的一条记录。"""

    upload_id: str
    filename: str
    size: int
    chunks: int
    collection: str
    uploaded_at: str


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


# ==================== 使用次数（/usage） ====================

class UsageResponse(BaseModel):
    """全局使用次数。"""

    used: int
    limit: int
    remaining: int


# ==================== 会话历史（/sessions） ====================

class SessionSummary(BaseModel):
    """会话列表里的一条（对应一个 thread_id）。"""

    thread_id: str
    # 最后一次写入的时间（ISO 8601，来自 checkpoint 的 ts）
    updated_at: str
    # 可展示的消息条数（只算用户/AI 有文本的，不含工具调用轮）
    message_count: int
    # 首条用户提问的摘要，作为会话标题
    preview: str
    # 会话发起人（首轮提问时填写的姓名）
    user_name: str = ""


class SessionMessage(BaseModel):
    """会话里的一条可展示消息。"""

    role: str  # user | assistant
    content: str
    # 用户消息的提问人；AI 消息为空
    name: str = ""


class SessionDetail(BaseModel):
    """某个会话的完整对话（用于切回历史会话继续聊）。"""

    thread_id: str
    messages: list[SessionMessage]


# ==================== 规划会话历史（/plan/sessions） ====================

class PlanSessionSummary(BaseModel):
    """规划会话列表里的一条。"""

    thread_id: str
    updated_at: str
    # 该会话累计问过多少次（plan_messages 条数）
    request_count: int
    # 首个请求的摘要，作为会话标题
    preview: str
    # 会话发起人（首轮提问时填写的姓名）
    user_name: str = ""


class PlanSessionDetail(BaseModel):
    """某个规划会话：各轮请求 + 最后一次执行的计划与产出。"""

    thread_id: str
    # 该会话累计的用户请求（按时间序）
    requests: list[str]
    # 与 requests 一一对应的提问人姓名
    request_names: list[str] = Field(default_factory=list)
    plan: list[PlanStep]
    subtask_results: dict[str, str] = Field(default_factory=dict)
    final_output: str
    replan_count: int = 0

