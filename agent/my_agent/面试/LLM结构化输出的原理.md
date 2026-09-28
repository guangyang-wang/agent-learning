# 面试亮点：LLM 结构化输出的原理（从软约束到硬约束）

> **一句话亮点**：让大模型输出结构化数据，本质是「约束它的采样过程」。手段从弱到强有四层，但真正的分水岭只有一道——是「事后校验」还是「事中禁止」。前者（prompt / JSON Mode / Function Calling）永远到不了 100%，后者（约束解码 / Structured Outputs）才能百分百锁死结构。

> 配套文档：`LLM结构化输出的容错与降级设计.md` 讲「输出错了怎么办」，本篇讲「怎么让它尽量不错 / 为什么有的能做到不错」。

---

## 一、问题的本质

大模型逐 token 生成，本质是**每一步在整个词表（十几万 token）上算概率分布，然后采样**。所谓"结构化输出"，就是**干预这个采样过程，让它只能落在合法的结构里**。

干预方式有两种哲学，这是全篇的纲：

| 哲学 | 做法 | 结果 |
|---|---|---|
| **事后校验** | 模型自由生成 → 我 parse → 错了再修 | 永远有概率错 |
| **事中禁止** | 生成时就屏蔽掉非法 token | 物理上不可能错 |

下面所有手段，都可以归到这两种哲学里。

---

## 二、先分清两层：信封 vs 内容（保证力度天差地别）

一次带结构化输出的 HTTP 响应长这样：

```json
{
  "choices": [
    {
      "message": {
        "tool_calls": [
          { "function": { "arguments": "{\"plan\": [...]}" } }
        ]
      }
    }
  ]
}
```

拆成两层，保证来源完全不同：

| 层 | 谁生成 | 正确率 | Java 类比 |
|---|---|---|---|
| **信封**（`choices`/`message`/`tool_calls` 这个壳） | **服务器自己的代码**序列化 | 100% | Jackson 把 POJO 序列化成 JSON，字段名是框架定的，不会错 |
| **内容**（`arguments` 里那个字符串） | **模型**逐 token 生成 | 看手段 | POJO 里有个 `String arguments` 字段，Jackson 保证它是合法 String，但**不保证它是合法 JSON** |

> **关键认知**：服务器只能保证信封对（这是它代码写的），模型只负责填 `arguments` 这个字符串。所以"结构化输出"的所有技术，争的都是**那个字符串到底能多严格地被约束**。

---

## 三、四种手段，由弱到强

| 层 | 手段 | 约束哲学 | 结构正确率 | 备注 |
|---|---|---|---|---|
| ① | Prompt 工程（"只输出 JSON"） | 事后校验 | 靠运气 | 本项目 `plan_graph.py` 用的就是这条 |
| ② | JSON Mode（`response_format: json_object`） | 事后校验（软约束） | 合法 JSON 对象，**字段名不管** | DeepSeek / OpenAI 都有 |
| ③ | Function Calling（`tools` + schema） | 事后校验（软约束） | 大概率对齐 schema | schema 里 enum / required 是软约束 |
| ④ | Structured Outputs / 约束解码 | **事中禁止（硬约束）** | **100%（除截断）** | 仅 OpenAI / Anthropic / Gemini，**DeepSeek 没有** |

**关键分水岭在第 ④ 层**：只有它把"约束"搬进了解码过程本身，其余三层都是"生成完了再想办法"。

### 实测证据（本项目 `scripts/demo_http_structured.py`）

同一个任务「写二次函数复习讲义」，两个变体的真实返回对比：

- **JSON Mode（变体 1）**：模型吐了 `{"subtasks": [{"description": "...", "dependencies": []}]}` —— 是合法 JSON，但字段叫 `subtasks`/`description`/`dependencies`，**没有 `agent` 字段**，跟想要的 `plan`/`desc`/`deps` 对不上。
- **Function Calling（变体 2）**：模型严格对齐 schema，`agent` 乖乖落在 `enum: ["knowledge","code","writer","reviewer"]` 里，必填字段全对。

这正好证明：JSON Mode 只锁"形状"（是 JSON），锁不住"语义"（字段叫什么）；Function Calling 锁得更死，但依然是软约束，仍可能翻车。

---

## 四、底层原理：软约束 vs 硬约束

### 软约束（①②③）：指令 + 训练，不碰采样

JSON Mode 和 Function Calling 都没有 token 屏蔽，本质是**把"输出格式"的信息通过系统指令注入 + 靠模型训练对齐**：

1. 提供商往系统层注入"只输出 JSON"的指令
2. 模型训练阶段对齐过 JSON / 工具调用的输出格式
3. 服务端可能加一层"合法性校验"，不合法就内部重试一次

所以它保证的是"模型**更可能**遵守"，不是"模型**无法**违反"。

### 硬约束（④）：约束解码，直接改采样

Structured Outputs 背后是 **grammar-constrained decoding（语法约束解码）**，原理：

1. 你的 **JSON Schema 被编译成一个有限状态机（FSM）/ 文法**，每个状态代表"当前 JSON 写到哪了"
2. 模型每一步算完概率分布后，**逐 token 判断**：接上这个 token 还能不能留在合法 schema 的路径上
3. 不能的 token **概率置 0（-inf）**，重新归一化，只从合法 token 里采样

```text
FSM 大致长这样：
开始 → 只允许 { 或 [ 或 " 或数字
  │
  { " → 只允许 key 的合法字符
  key : → 只允许 value 开头（" { [ 数字 true/false/null）
  ...
```

每走一步，状态推进一次，合法 token 集合随之变化。**非法 token 概率被清零，模型采样不到它，所以错不了。**

> **Java 类比**：软约束 = 运行时 `try/catch` + `instanceof` 校验（跑了才知道错）；硬约束 = 类型系统 + 只生成"能通过编译"的代码（错的东西根本无法产生）。

---

## 五、怎么用

### JSON Mode

原始 HTTP，关键是 **prompt 里必须出现 "json" 这个词**：

```json
{
  "model": "deepseek-chat",
  "messages": [
    {"role": "user", "content": "把任务拆成子任务，只输出 json"}
  ],
  "response_format": { "type": "json_object" }
}
```

LangChain：

```python
llm = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key="sk-xxx",
    model_kwargs={"response_format": {"type": "json_object"}},
)
```

### Structured Outputs（OpenAI）

原始 HTTP，用 `json_schema` 类型 + `"strict": true`，把完整 schema 塞进去：

```json
{
  "model": "gpt-4o",
  "messages": [{"role": "user", "content": "写一篇二次函数复习讲义"}],
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "task_plan",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "plan": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "id": {"type": "string"},
                "desc": {"type": "string"},
                "agent": {"type": "string", "enum": ["knowledge", "code", "writer", "reviewer"]},
                "deps": {"type": "array", "items": {"type": "string"}}
              },
              "required": ["id", "desc", "agent", "deps"],
              "additionalProperties": false
            }
          }
        },
        "required": ["plan"],
        "additionalProperties": false
      }
    }
  }
}
```

LangChain 一行，用 `with_structured_output`（内部自动走 Structured Outputs，不可用时回退 Function Calling）：

```python
class SubTask(TypedDict):
    id: str
    desc: str
    agent: str
    deps: list[str]

class Plan(TypedDict):
    plan: list[SubTask]

llm = ChatOpenAI(model="gpt-4o", ...)
structured_llm = llm.with_structured_output(Plan)
result = structured_llm.invoke("写一篇二次函数复习讲义")
```

`strict: true` 的两个硬性要求：**所有字段必须写进 `required`**、**必须 `additionalProperties: false`**，否则 OpenAI 直接拒收。

---

## 六、谁支持什么

| 提供商 | JSON Mode | Structured Outputs（strict schema） | 说明 |
|---|---|---|---|
| **OpenAI** | ✅ | ✅ Structured Outputs（2024.8） | 服务端约束解码，官方保证匹配 schema |
| **Anthropic** | ✅ | ✅ | 也有结构化输出保证 |
| **Google Gemini** | ✅ | ✅ controlled generation | `response_schema` 约束 |
| **DeepSeek** | ✅ | ❌ 只有 JSON Mode | 没有 strict schema 模式 |

> **对项目的含义**：本项目用 DeepSeek，拿不到"100% 严格匹配 schema"的能力——不是不会发请求，是 DeepSeek 服务端没开放这个模式。所以 `_validate_plan` + `_default_plan` 这套兜底在 DeepSeek 上是**必需且不可省**的。

---

## 七、面试话术（可直接说）

> 「让大模型输出结构化数据，本质是约束它的采样过程，分两条路：事后校验和事中禁止。prompt、JSON Mode、Function Calling 都是事后——模型自由生成我再 parse，所以永远到不了 100%；真正能做到百分百的只有约束解码，也就是把 JSON Schema 编译成有限状态机，在解码每一步把非法 token 的概率置零，模型想错都错不了。OpenAI 的 Structured Outputs 就是这个原理，但它搬到了服务端，通过 strict schema 开放；DeepSeek 只提供 JSON Mode，没有这个能力。所以我用的 DeepSeek 上，校验加降级兜底这套纵深防御是不可省的——这就是我上一份文档讲的容错链。」

---

## 八、可能的追问与应对

| 追问 | 应对 |
|---|---|
| 「JSON Mode 和 Structured Outputs 到底差在哪？」 | 差在约束哲学：JSON Mode 是软约束（指令 + 训练 + 服务端校验），只保证合法 JSON 对象，字段名不管；Structured Outputs 是硬约束（schema 编译成 FSM + token 屏蔽），保证严格匹配 schema。前者"更可能遵守"，后者"无法违反"。 |
| 「Function Calling 不就是给 schema 了吗，为什么还不是 100%？」 | enum / required 在多数 provider 里是**软约束**（训练 + 提示），不是 FSM 级 token 屏蔽，模型极少数情况仍可能越界或漏字段；且 `max_tokens` 截断会出半截 JSON。真正的硬保证只有约束解码。 |
| 「约束解码为什么非要自托管，云 API 不行吗？」 | 约束解码要挂进解码循环做 token 屏蔽，采样在服务器内部，外部只能发 HTTP 没资格屏蔽。除非提供商自己把约束解码做进服务端（如 OpenAI Structured Outputs）并通过 API 开放，否则你只能用开源模型 + llama.cpp / vLLM / Outlines 自托管。 |
| 「结构化输出是不是就等于结果可靠了？」 | 不是。约束解码保证的是**结构**（字段名、类型、枚举、必填），保证不了**语义**——`desc` 里写的内容对不对、依赖合不合理、选的 agent 是不是真合适，schema 管不了。所以校验 + 降级这层永远要有。 |