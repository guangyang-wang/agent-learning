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

### 3. 定义模型（初始化模型）

先说本质：`langchain-deepseek` 包里**并没有一个现成的模型实例，而是提供了一个「模型类」`ChatDeepSeek`**。
这个类把两样东西**写死**了：

| 写死的东西 | 值 | 说明 |
|------|------|------|
| `base_url` | `https://api.deepseek.com/v1` | DeepSeek 官方接口地址 |
| 读 api_key 的环境变量名 | `DEEPSEEK_API_KEY` | 类初始化时从这个名字读密钥 |

所以装了 `langchain-deepseek` + 环境变量叫 `DEEPSEEK_API_KEY`，业务代码里就能「什么都不传」直接用。

但**写死的东西不一定符合你的要求**（换平台、环境变量名对不上等），这时就要「自己初始化模型」。初始化方式有两种：

#### 方式一：直接用厂商提供的模型类（早期方式）

每个集成包提供一个类，导入后自己 `new` 一个：

```python
from langchain_deepseek import ChatDeepSeek

# 什么都不传：用写死的 base_url + 自动读 DEEPSEEK_API_KEY
model = ChatDeepSeek(model="deepseek-chat")

# 或手动覆盖默认值（换 base_url、换 api_key）
model = ChatDeepSeek(
    model="deepseek-chat",
    base_url="https://自定义地址",
    api_key="sk-xxx",
)
```

#### 方式二：用 `init_chat_model`（现在最常用）

```python
from langchain.chat_models import init_chat_model

# 只传模型名，LangChain 根据名字自动推断「用哪家、base_url 是多少、读哪个环境变量」
model = init_chat_model(model="deepseek-chat")
```

`init_chat_model` 底层就是「帮你挑对模型类再 new 出来」，但**只支持 LangChain 官方收录的常见模型**
（deepseek、openai、anthropic 等）。换成没收录的平台（比如阿里百炼的 qwen-max），就得显式指定
`model_provider` + `base_url` + `api_key`：

```python
import os

model = init_chat_model(
    model="qwen-max",
    model_provider="openai",                 # 阿里百炼兼容 OpenAI 协议，借它的「驱动」访问
    base_url=os.getenv("DASHSCOPE_BASE_URL"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
)
```

**两种方式的区别一句话**：`ChatDeepSeek()` 是「你亲手挑类来 new」，`init_chat_model()` 是「你只报模型名，它帮你挑类」。
前者灵活但啰嗦，后者省事但只认官方收录的模型。

### 4. 定义工具（tools）

工具就是普通的 Python 函数，用 `@tool` 装饰器标记：

```python
from langchain.tools import tool

@tool
def web_search(query: str) -> str:
    """搜索互联网信息"""  # ← 这个 docstring 会作为「工具描述」传给模型
    return "搜索结果..."
```

> 工具的定义方式（三种）和标准化的 `tool_call` 调用机制，详见《[工具（Tool）.md](工具（Tool）.md)》。

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

> 记忆（checkpointer）的工作原理、`thread_id` 和持久化，详见《[记忆（Memory）.md](记忆（Memory）.md)》。

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

## 三、消息类型（Message）

### 1. 核心思想：所有消息都是 `BaseMessage`

LangChain 把「发给模型的消息」和「模型返回的消息」**统一封装**成 `BaseMessage`，它是 Agent 里最基本的上下文单元。
我们不用自己 `new` 一个 `BaseMessage`，LangChain 已经按**角色（Role）** 准备好了 4 个子类：

| 子类 | role | 谁发出的 | 作用 |
|------|------|------|------|
| `SystemMessage` | `system` | 开发者 | 设定模型角色和交互背景（系统提示词） |
| `HumanMessage` | `user` | 用户 | 用户的输入 |
| `AIMessage` | `assistant` | 模型 | 模型的响应，含文本、工具调用、元数据 |
| `ToolMessage` | `tool` | 工具（本机函数） | 工具执行后返回的结果 |

```python
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
```

> 导入路径 `langchain_core.messages` 和 `langchain.messages` 是**同一批类**（`langchain` 只是转发），用哪个都行。

### 2. 一条消息长什么样（字段）

创建消息后，它内部自带一堆字段：

```python
HumanMessage("你好，我是虎哥")
# content='你好，我是虎哥'   ← 正文
# id='de1a0f0b-...'          ← 每条消息唯一 ID
# additional_kwargs={}       ← 厂商特有的额外字段
# response_metadata={}       ← 模型返回的元信息
```

`AIMessage` 额外多了「工具调用 + 用量」相关字段：

| 字段 | 含义 |
|------|------|
| `content` | 正文（文本） |
| `tool_calls` | 模型要求调用的工具列表（每个含 `name` + `args` + `id`） |
| `usage_metadata` | token 用量（输入 / 输出 / 缓存命中） |
| `response_metadata` | 返回元信息（如 `finish_reason`、模型名） |

`ToolMessage` 额外有：

| 字段 | 含义 |
|------|------|
| `name` | 工具名（如 `get_weather`） |
| `tool_call_id` | 对应的那次 `tool_call` 的 ID，用来「对上号」 |

### 3. 常用方法：`pretty_print()`

消息对象提供了 `pretty_print()`，把一条消息**格式化打印**，方便调试 Agent 循环：

```python
for msg in response["messages"]:
    msg.pretty_print()
```

输出长这样（自动带分隔线和角色名）：

```
================================ System Message ================================
请使用工具来获取天气信息。
================================== Ai Message ==================================
我来帮你查询一下北京今天的天气情况。
Tool Calls:
  get_weather (call_00_...)
  Args:
    location: 北京
```

> `pretty_print()` 会**自动识别角色**，打印出 `System Message` / `Human Message` / `Ai Message` / `Tool Message` 标题，一眼看清整段对话流程。

### 4. 多模态消息

消息不只装文本，还能装**图片、音频、视频**（前提是模型支持多模态，如 `qwen3.5-plus`、`gpt-5-nano`）。
做法是给 `HumanMessage` 传一个**内容列表**，每个元素是一个 `{"type": ..., ...}` 字典：

**① 在线图片（给 url）**

```python
message = HumanMessage([
    {"type": "text", "text": "描述以下这张图片的内容."},
    {"type": "image", "url": "https://xxx/dog_and_girl.jpeg"},
])
```

**② 本地图片（转 base64）**

```python
import base64
img_b64 = base64.b64encode(img_bytes).decode("utf-8")

message = HumanMessage(content=[
    {"type": "image", "base64": img_b64, "mime_type": "image/jpeg"},
    {"type": "text", "text": "给我讲讲图片中的城市"},
])
```

> 本地图片没法直接传文件，要先读成字节再 `base64` 编码成字符串，并带上 `mime_type`（如 `image/jpeg`）告诉模型「这是张图」。

### 消息类型速查

```
BaseMessage（基类，统一封装）
 ├─ SystemMessage  → role=system     设定背景
 ├─ HumanMessage   → role=user       用户输入（可多模态）
 ├─ AIMessage      → role=assistant  模型输出（文本/工具调用/元数据）
 └─ ToolMessage    → role=tool       工具执行结果
```

常用操作：`msg.content` 取正文；`msg.pretty_print()` 格式化打印；`AIMessage.tool_calls` 看工具调用。

---

## 四、与 Java 类比

| LangChain 概念 | Java 类比 | 说明 |
|------|------|------|
| `langchain` | JDBC 统一 API | 定义统一接口，不绑定具体厂商 |
| `langchain-deepseek` | MySQL JDBC Driver | 厂商具体实现，封装连接细节 |
| `ChatDeepSeek`（厂商模型类） | `new MySQL Driver()` / `new DataSource` | 直接 new 厂商实现，能手动改默认参数（灵活） |
| `init_chat_model` / `create_agent` | 工厂方法 / Spring Bean 工厂 | 传个名字就返回配置好的对象（内部自动挑实现，省事） |
| Tool（工具函数） | 接口方法 + Javadoc | 模型看「签名 + 文档」决定调用哪个 |
| `@tool` 装饰器 | 给方法加注解/注册 | 把普通函数暴露成可被模型调用的能力 |
| API Key 环境变量 | `System.getenv()` / 配置中心 | 密钥不硬编码在代码里 |
| checkpointer（记忆） | HttpSession / 会话存储 | 保存多轮对话状态 |
| `BaseMessage` | 接口 / 抽象基类 | 所有消息的父类，统一封装「谁发的 + 内容」 |
| `SystemMessage` 等 4 个子类 | 按 Role 区分的实现类（枚举） | 每种角色一个子类，构造时就定好了 role |
| `pretty_print()` | 重写 `toString()` | 把对象格式化成易读字符串，方便调试 |
| 多模态消息（content 列表） | 方法重载 / 多态 | 同一个 `HumanMessage` 能装文本、图片等多种内容 |

> 用 JDBC 类比最好记：**你写代码面向的是 `langchain` 这个统一接口，装 `langchain-deepseek` 就像给 JDBC 装一个 MySQL 驱动**——接口不变，换厂商只换驱动。

---

## 五、速查（一页纸）

1. **装依赖**：`langchain`（核心）+ `langchain-deepseek`（DeepSeek 集成）+ `python-dotenv`
2. **配密钥**：环境变量必须叫 `DEEPSEEK_API_KEY`，改了名就读不到
3. **定模型**：`init_chat_model(model=...)`（自动挑厂商）；或 `ChatDeepSeek(model=...)`（手动 new 厂商类）
4. **定工具**：普通函数 + `@tool` 装饰器（docstring 就是工具描述）
5. **建 Agent**：`create_agent(model, tools=[...], system_prompt=...)`
6. **调用**：`invoke`（一次性）/ `stream`（流式）
7. **Agent 本质**：模型 ↔ 工具之间的循环，模型「点菜」、Agent「做菜」，循环到模型给出最终答案为止
8. **消息类型**：`BaseMessage` 统一封装，按角色分 `SystemMessage`(system) / `HumanMessage`(user) / `AIMessage`(assistant) / `ToolMessage`(tool)
9. **常用方法**：`msg.content` 取正文；`msg.pretty_print()` 格式化打印；`AIMessage.tool_calls` 看工具调用；多模态用 content 列表传图片（url 或 base64）
