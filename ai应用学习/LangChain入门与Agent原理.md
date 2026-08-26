# LangChain 开发流程与 Agent 原理

> 一句话总结：**LangChain 是「统一接口」，Agent 是「让模型自己决定调用哪些工具」的循环**。
> 装好依赖 → 配好环境变量 → 定义模型和工具 → `create_agent` 生成 agent → `invoke/stream` 调用。

---

## 一、LangChain 开发流程

### 1. 安装依赖

LangChain 采用「核心 + 各厂商集成包」的拆包设计，用哪家模型就装哪家的集成包：

```bash
pip install langchain              # 核心：统一的接口和 Agent 框架
pip install langchain-deepseek     # DeepSeek 集成包（封装 base_url + 读 API Key）
pip install python-dotenv          # 从 .env 文件加载环境变量
```

| 包 | 作用 |
|------|------|
| `langchain` | 核心库，提供 `create_agent`、消息类型、工具定义等统一能力 |
| `langchain-deepseek` | DeepSeek 厂商实现：内置 base_url、自动读 API Key |
| `langchain-openai` / `langchain-anthropic` | 其他厂商的集成包（用谁装谁） |
| `python-dotenv` | 读取 `.env` 里的密钥，避免硬编码 |

### 2. 配置环境变量

```bash
# .env 文件
DEEPSEEK_API_KEY=sk-xxxxxx
```

**关键点**：`langchain-deepseek` 默认从环境变量 **`DEEPSEEK_API_KEY`** 读密钥，这个名字是**写死的**。
如果你把环境变量改成别的名字（比如 `DEEP_SEEK_API_KEY`），包就读取不到，会报认证错误。

> 所以：装了 `langchain-deepseek` + 环境变量叫 `DEEPSEEK_API_KEY`，业务代码里就**不用手动传 base_url 和 api_key**。

### 3. 定义模型

```python
from langchain.chat_models import init_chat_model
import os

model = init_chat_model(
    model="deepseek-chat",
    model_provider="deepseek",   # 告诉 LangChain 用哪个集成包
)
```

`init_chat_model` 会根据 `model_provider` 找到对应的集成包（这里是 `langchain-deepseek`），
自动完成 base_url 和 api_key 的装配。

### 4. 定义工具（tools）

工具就是普通的 Python 函数，用 `@tool` 装饰器标记：

```python
from langchain.tools import tool

@tool
def web_search(query: str) -> str:
    """搜索互联网信息"""  # ← 这个 docstring 会作为「工具描述」传给模型
    return "搜索结果..."
```

### 5. 创建 Agent

```python
from langchain.agents import create_agent

agent = create_agent(
    model,                      # 模型
    tools=[web_search],         # 工具列表
    system_prompt="你是一名助手",
    checkpointer=checkpointer,  # 可选：记忆管理
)
```

### 6. 调用

```python
from langchain.messages import HumanMessage

# 一次性调用
response = agent.invoke({"messages": [HumanMessage("你好")]})

# 流式调用（逐 token 返回）
for chunk in agent.stream({"messages": [HumanMessage("你好")]}):
    ...
```

### 开发流程速查

```
装依赖 → 配 .env（DEEPSEEK_API_KEY）→ 定义模型 → 定义工具 → create_agent → invoke/stream
```

---

## 二、Agent 原理

### 核心思想

Agent 与普通「一问一答」的区别在于：**模型不只回答问题，还能「决定调用哪个工具」**。
工具是在**你本地**执行的 Python 函数，模型只负责「点菜」，不负责「做菜」。

### 完整调用循环（ReAct 模式）

一次 `agent.invoke()` 背后，是「模型 ↔ 工具」之间的**多轮循环**：

```
① 用户发消息
   HumanMessage("帮我查一下明天的天气")
        │
        ▼
② Agent 组装上下文：系统提示词 + 用户消息 + 工具信息（名称/描述/参数）
        │
        ▼
③ 把上下文发给大模型
        │
        ├── 模型觉得「需要工具」→ 返回 tool_call（工具名 + 参数 JSON）
   ┌────┤
   │    └── 模型觉得「信息够了」→ 返回最终答案 ──────────► ⑥ 直接返回给用户
   │
   ▼
④ Agent 拿到 tool_call，在本机执行对应的 Python 函数，得到结果
        │
        ▼
⑤ 把工具结果（ToolMessage）追加进对话，再发给模型 → 回到 ③
        │
        ▼
⑥ 模型不再调用工具，返回最终回答，Agent 解析后返回给用户
```

### 关键点（理解核对）

1. **这是一个循环，不是单向流程**。模型可能调用 0 次、1 次或多次工具，直到它认为信息够了才给出最终答案。
2. **模型返回的「工具调用」包含：工具名 + 参数**，例如 `{"name": "web_search", "args": {"query": "明天天气"}}`。
3. **真正执行工具的是 Agent（你的代码）**，不是模型。模型只输出「想调用哪个工具、传什么参数」。
4. **传给模型的「工具信息」是签名 + 描述，不是函数代码**。模型靠工具名和 docstring 来理解每个工具能干什么。
5. 循环里流转的消息类型有四种：
   - `HumanMessage`：用户输入
   - `AIMessage`：模型输出（可能带 `tool_calls`）
   - `ToolMessage`：工具执行结果
   - `SystemMessage`：系统提示词

### 一个最小例子

```python
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.messages import HumanMessage

@tool
def add(a: int, b: int) -> int:
    """两个数相加"""
    return a + b

agent = create_agent("deepseek-chat", tools=[add])

# 用户问「1+2 等于几」，模型会决定调用 add(1, 2)，工具算出 3，模型返回「等于 3」
agent.invoke({"messages": [HumanMessage("1 + 2 等于几？")]})
```

---

## 三、与 Java 类比

| LangChain 概念 | Java 类比 | 说明 |
|------|------|------|
| `langchain` | JDBC 统一 API | 定义统一接口，不绑定具体厂商 |
| `langchain-deepseek` | MySQL JDBC Driver | 厂商具体实现，封装连接细节 |
| `init_chat_model` / `create_agent` | 工厂方法 / Spring Bean 工厂 | 传个名字就返回配置好的对象 |
| Tool（工具函数） | 接口方法 + Javadoc | 模型看「签名 + 文档」决定调用哪个 |
| `@tool` 装饰器 | 给方法加注解/注册 | 把普通函数暴露成可被模型调用的能力 |
| API Key 环境变量 | `System.getenv()` / 配置中心 | 密钥不硬编码在代码里 |
| checkpointer（记忆） | HttpSession / 会话存储 | 保存多轮对话状态 |

> 用 JDBC 类比最好记：**你写代码面向的是 `langchain` 这个统一接口，装 `langchain-deepseek` 就像给 JDBC 装一个 MySQL 驱动**——接口不变，换厂商只换驱动。

---

## 四、速查（一页纸）

1. **装依赖**：`langchain`（核心）+ `langchain-deepseek`（DeepSeek 集成）+ `python-dotenv`
2. **配密钥**：环境变量必须叫 `DEEPSEEK_API_KEY`，改了名就读不到
3. **定模型**：`init_chat_model(model=..., model_provider=...)`
4. **定工具**：普通函数 + `@tool` 装饰器（docstring 就是工具描述）
5. **建 Agent**：`create_agent(model, tools=[...], system_prompt=...)`
6. **调用**：`invoke`（一次性）/ `stream`（流式）
7. **Agent 本质**：模型 ↔ 工具之间的循环，模型「点菜」、Agent「做菜」，循环到模型给出最终答案为止
