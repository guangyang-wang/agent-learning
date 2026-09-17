"""FastAPI 应用入口。

暴露 /chat 等接口，把 HTTP 请求接入父图。
"""

from fastapi import FastAPI

app = FastAPI(title="大学生智能学习多Agent系统")


@app.post("/chat")
def chat(request: dict) -> dict:
    """对话接口（占位）。"""
    # TODO(阶段8)：调用父图，返回 task_type + output
    raise NotImplementedError("API 待实现（阶段8）")
