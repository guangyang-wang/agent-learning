# 工具（Tool）

> 一句话：**工具是 Agent 的「手脚」——本质是普通函数，但调用者是模型，所以要把「名字、作用、参数」描述清楚，让模型知道怎么用。**

---

## 一、工具是什么

一个完整的 Agent 至少包含两部分：

| 部分 | 角色 | 职责 |
|------|------|------|
| 模型 | 大脑 | 负责推理、分析、规划任务步骤 |
| 工具 | 手脚 | 负责执行任务、与外界交互 |

**工具本质就是一个可调用的函数**，但它不是我们自己调用，而是**给模型调用**的。
所以我们除了定义函数，还必须「描述」这个工具，让模型知道三件事：

- **工具名**：叫什么
- **作用**：能干什么
- **参数**：需要哪些入参

---

## 二、定义工具的三种方式（核心：让模型认识工具）

### 方式一：在 `@tool` 里直接写描述

`@tool` 装饰器第一个参数是「工具名」，`description` 是「作用」：

```python
from langchain_core.tools import tool

@tool("square_root", description="Calculate the square root of a number")
def tool1(x: float) -> float:
    return x ** 0.5
```

### 方式二：靠函数名 + 文档注释（最常用）

如果 `@tool` 里什么都不写，LangChain 会自动「借用」函数的自带信息：

| 工具的什么 | 默认取自 |
|------|------|
| 工具名 | 函数名 |
| 作用描述 | 函数的文档注释 docstring |
| 参数列表 | 函数的参数列表 |

```python
@tool
def square_root(x: float) -> float:
    """Calculate the square root of a number"""   # ← docstring 就是「工具作用」
    return x ** 0.5

@tool
def get_weather(location: str, units: str = "celsius", include_forecast: bool = False) -> str:
    """
    Get current weather and optional forecast.
    Args:
        location: city name or coordinates
        units: unit of degrees
        include_forecast: does it include the weather forecast
    """
    ...
```

> 所以「写清楚 docstring」很重要——它直接决定模型能不能正确理解和使用这个工具。

### 方式三：用 pydantic 类描述参数（参数复杂时）

参数多、类型复杂（如枚举、可选值）时，建议用 pydantic model 单独描述参数，再通过 `args_schema` 挂到工具上：

```python
from pydantic import BaseModel, Field
from typing import Literal

class WeatherInput(BaseModel):
    """查询天气的输入参数."""
    location: str = Field(description="City name or coordinates")
    units: Literal["celsius", "fahrenheit"] = Field(
        default="celsius",
        description="Temperature unit preference, default is celsius."
    )
    include_forecast: bool = Field(
        default=False,
        description="Include 5-day forecast"
    )

@tool(args_schema=WeatherInput)   # ← 用 args_schema 挂上参数描述
def get_weather(location: str, units: str = "celsius", include_forecast: bool = False) -> str:
    """Get current weather and optional forecast."""
    ...
```

> `Field(description=...)` 会告诉模型每个参数「什么意思、可取值、默认值」，比裸的 `str`/`bool` 信息量大多了。

### 三种方式怎么选

| 场景 | 推荐方式 |
|------|------|
| 简单工具，函数名和 docstring 已足够清晰 | 方式二（最省事） |
| 想给工具起个跟函数名不同的名字，或想单独写描述 | 方式一 |
| 参数多、类型复杂（枚举/可选/嵌套） | 方式三 |

---

## 三、工具怎么被调用（标准化的 tool_call）

工具定义好后，模型是怎么「点菜」的？看一次实际调用：

```python
agent = create_agent(model="deepseek-chat", tools=[square_root, get_weather])
agent.invoke({"messages": [HumanMessage("467和529的平方根是多少?")]})
```

模型返回的 `AIMessage` 里带了一条 `tool_calls`：

```
Ai Message:
  Tool Calls:
    square_root (call_00_aQ0QNpiJNd4qKupaSlDGchGM)   ← 工具名 + 调用ID
    Args:
      x: 467                                          ← 参数
```

这条 `tool_call` 是**标准化结构**，固定包含三样：

| 字段 | 含义 |
|------|------|
| `name` | 要调用的工具名（对应函数名） |
| `args` | 传进去的参数（JSON） |
| `id` | 这次调用的唯一 ID |

**Agent 拿到 tool_call 后的动作**（你的理解是对的）：

1. **解析**：读 `name`，找到对应的 Python 函数
2. **执行**：把 `args` 作为参数传给函数，运行得到结果
3. **回填**：把结果包成 `ToolMessage`（带 `name` + `tool_call_id`，用于和那次调用「对上号」）
4. **续聊**：把 ToolMessage 追加进对话，再发给模型，让它基于结果继续回答

> 关键点：**模型只负责「点菜」（输出 tool_call），真正「做菜」（执行函数）的是 Agent 代码**。模型不知道函数内部怎么实现，只按 name/args 下指令。

### 工具也能像普通函数一样直接调用

工具对象自带 `.invoke()` 方法，我们可以直接调用测试（传参用 dict）：

```python
square_root.invoke({"x": 467})                              # 21.61018278497431
get_weather.invoke({"location": "杭州", "include_forecast": True})
```

---

## 四、预定义工具（以 tavily 为例）

LangChain 官方提供了很多现成工具，比如 `tavily`（网络搜索）。用起来三步：

1. 注册账号，创建 API_KEY
2. 配置环境变量 `TAVILY_API_KEY`
3. 安装依赖：`uv add langchain-tavily`

```python
from langchain_tavily import TavilySearch

search_tool = TavilySearch(max_results=5, topic="general")
```

官方工具参数齐全但**偏重**（多耗 token），简单业务可以自己再包一层瘦身：

```python
@tool
def web_search(query: str):
    """Search the web for information"""
    return tavily.invoke(query)
```

---

## 五、与 Java 类比

| LangChain | Java 类比 | 说明 |
|------|------|------|
| `@tool` 装饰器 | `@Override` / `@Bean` 注解 | 给函数打标记，注册成工具 |
| 工具的描述（名/作用/参数） | 接口方法签名 + Javadoc | 模型靠「签名 + 文档」理解怎么调用 |
| docstring 当描述 | Javadoc 注释 | 写清楚别人（模型）才会用 |
| pydantic `args_schema` | DTO / 参数对象 | 用类约束入参类型和含义 |
| `tool_call`（name+args+id） | RPC 请求（方法名 + 参数 + 请求ID） | 标准化的「调用指令」 |
| Agent 执行工具 | 反射调用方法 | 拿到方法名和参数，动态调用 |
| `ToolMessage` | 方法返回值 / 响应对象 | 把执行结果回传给调用方 |

> 最好记：**模型返回的 `tool_call` 就像一次「远程方法调用（RPC）」，`name` 是方法名、`args` 是参数、`id` 是请求编号**——Agent 拿到后「反射」调用本地函数，再把结果（ToolMessage）返回。

---

## 六、速查（一页纸）

1. **工具本质**：普通函数，但给模型调用，要描述「名 / 作用 / 参数」
2. **方式一**：`@tool("名字", description="作用")` 直接写
3. **方式二**：`@tool` + 函数名/docstring（最常用，自动借用）
4. **方式三**：`@tool(args_schema=类)`，用 pydantic 类描述复杂参数
5. **调用机制**：模型输出标准 `tool_call`（name+args+id）→ Agent 解析 → 执行函数 → 结果包成 `ToolMessage` 回填
6. **测试工具**：`工具.invoke({"参数": 值})`，跟普通函数调用一样
7. **预定义工具**：tavily 等，`TavilySearch(max_results=...)`，可再包一层瘦身
