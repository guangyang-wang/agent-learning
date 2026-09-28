"""演示：不依赖 LangChain，直接向 DeepSeek 发原始 HTTP 请求获取结构化数据。

两个变体（对应「结构化输出」由弱到强的两种手段）：
    1. JSON Mode      —— response_format={"type": "json_object"}，让模型只吐 JSON
    2. Function Calling—— tools=[...]，让模型按 schema 吐工具调用参数

运行：
    python scripts/demo_http_structured.py

依赖：httpx（requests 也行，这里用 httpx 是为了展示完整请求细节）
"""
import json

import httpx
from dotenv import load_dotenv

# 显式指定 .env 路径：load_dotenv() 不带参数时靠调用栈定位，从 stdin 跑会崩。
import os

load_dotenv("D:/agent/agent/my_agent/.env")

URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com") + "/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

# ==================== 变体 1：JSON Mode ====================
# 核心就一行：response_format={"type": "json_object"}
# 注意：DeepSeek 要求 prompt 里必须出现 "json" 这个词，否则会报错。
body_json_mode = {
    "model": MODEL,
    "messages": [
        {
            "role": "system",
            "content": "你是任务规划器。把用户任务拆成有依赖关系的子任务，只输出 JSON。",
        },
        {"role": "user", "content": "写一篇关于二次函数的中考复习讲义"},
    ],
    "response_format": {"type": "json_object"},
}

print("=" * 70)
print("【变体 1】JSON Mode —— 请求体")
print("=" * 70)
print(json.dumps(body_json_mode, ensure_ascii=False, indent=2))

resp = httpx.post(URL, headers=HEADERS, json=body_json_mode, timeout=60)
print("\n【响应】HTTP", resp.status_code)
data = resp.json()
content = data["choices"][0]["message"]["content"]
print("模型返回内容：")
print(content)
print("\n解析成 Python 对象：")
print(json.loads(content))

# ==================== 变体 2：Function Calling ====================
# 核心：tools 里声明参数 schema，模型会输出 function 调用（tool_calls）
body_function_calling = {
    "model": MODEL,
    "messages": [
        {"role": "user", "content": "写一篇关于二次函数的中考复习讲义"},
    ],
    "tools": [
        {
            "type": "function",
            "function": {
                "name": "submit_plan",
                "description": "提交拆解好的任务计划",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan": {
                            "type": "array",
                            "description": "有依赖关系的子任务列表",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "desc": {"type": "string"},
                                    "agent": {
                                        "type": "string",
                                        "enum": ["knowledge", "code", "writer", "reviewer"],
                                    },
                                    "deps": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["id", "desc", "agent", "deps"],
                            },
                        }
                    },
                    "required": ["plan"],
                },
            },
        }
    ],
    "tool_choice": "auto",
}

print("\n\n" + "=" * 70)
print("【变体 2】Function Calling —— 请求体")
print("=" * 70)
print(json.dumps(body_function_calling, ensure_ascii=False, indent=2))

resp = httpx.post(URL, headers=HEADERS, json=body_function_calling, timeout=60)
print("\n【响应】HTTP", resp.status_code)
data = resp.json()
msg = data["choices"][0]["message"]
print("模型返回内容：")
print(json.dumps(msg, ensure_ascii=False, indent=2))

# 参数在 tool_calls[0].function.arguments 里，是个 JSON 字符串，再 json.loads
args = msg["tool_calls"][0]["function"]["arguments"]
print("\n解析出参数：")
print(json.loads(args))
