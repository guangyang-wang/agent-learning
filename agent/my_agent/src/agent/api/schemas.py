"""请求/响应模型（Pydantic）。"""

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """对话请求。"""

    user_input: str
    # 可选：会话 id（对应 Checkpointer 的 thread_id）
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """对话响应。"""

    task_type: str
    output: str
