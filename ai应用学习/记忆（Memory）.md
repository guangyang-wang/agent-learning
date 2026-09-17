# 记忆（Memory）

> 一句话：**Agent 底层通过 checkpointer 管理记忆——把每轮「你的问题 + 模型的回答」存起来，下次调用时把这些历史消息一起打包发给模型**，这样模型就「记得」之前聊过什么。

---

## 一、没有记忆时的问题

默认情况下，Agent 是「失忆」的：每次 `invoke` 都是独立的一次对话，前一轮说了什么，后一轮完全不知道。

```python
agent = create_agent(model="deepseek-chat")

agent.invoke({"messages": [HumanMessage("你好，我叫虎哥，我最喜欢猫猫。")]})
agent.invoke({"messages": [HumanMessage("我最喜欢什么动物?")]})
# 第二次模型回答「我不知道你喜欢什么」——因为它没看到第一轮的对话
```

> 原因：大模型本身**无状态**，每次调用只看你「当前这一次」发过去的消息。上一轮的消息如果不再发一遍，它就不会知道。

---

## 二、checkpointer 是怎么工作的

checkpointer 的本质是一个**「存档器」**：

1. 每次 `invoke` 结束后，把这一轮的 `messages`（用户问题 + 模型回答）**存起来**
2. 下次 `invoke` 时，把这些历史 `messages` **一起打包**，和当前新消息一并发给模型
3. 模型看到了完整历史，自然就「记得」之前说过什么

> 你的理解是对的：**记忆 = 把历史消息找个地方存起来 + 下次打包发给模型**。

### 用 thread_id 区分不同会话

历史消息按 `thread_id` 分桶存储，每个 `thread_id` 是一段独立的对话：

| 概念 | 作用 |
|------|------|
| `thread_id` | 会话标识，区分「这是哪段对话」 |
| 同一个 `thread_id` | 共享记忆（能看到之前聊的） |
| 不同 `thread_id` | 记忆互不干扰（各存各的） |

---

## 三、添加短期记忆（内存存储）

三步：

1. 导入并初始化 Checkpointer
2. 创建 Agent，指定 checkpointer
3. 调用 Agent，指定 thread_id

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langchain.messages import HumanMessage

# 1. 初始化 checkpointer（存内存里）
agent = create_agent("deepseek-chat", checkpointer=InMemorySaver())

# 2. 用 thread_id 标识这段对话
config = {"configurable": {"thread_id": "thread_1"}}

# 3. 每次调用都带上同一个 config
agent.invoke({"messages": [HumanMessage("你好，我叫虎哥，我最喜欢猫猫。")]}, config)
agent.invoke({"messages": [HumanMessage("我最喜欢的动物是什么？")]}, config)
# 第二次能答出「猫猫」，因为 checkpointer 把第一轮历史打包发了过去
```

> `InMemorySaver` 存在**内存**里，程序一结束就清空，适合临时测试。

---

## 四、持久化存储（SQLite）

想让记忆**重启后还在**，就换成 SQLite 存储：

```python
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

# 连接（或创建）sqlite 数据库文件
connection = sqlite3.connect("resources/checkpoint.db", check_same_thread=False)
# 初始化 checkpointer
checkpointer = SqliteSaver(connection)
# 自动建表
checkpointer.setup()

agent = create_agent("deepseek-chat", checkpointer=checkpointer)
```

> 先装依赖：`uv add langgraph-checkpoint-sqlite`

| 存储方式 | 类 | 特点 |
|------|------|------|
| 内存 | `InMemorySaver` | 快，但进程结束就丢 |
| 文件/数据库 | `SqliteSaver` | 持久化，重启后仍在 |

---

## 五、记忆管理（会话过长时）

历史消息越攒越多，可能**超出模型的上下文窗口限制**。常见解决方案：

| 方案 | 做法 |
|------|------|
| 修剪消息 | 只保留最近 N 条 |
| 删除消息 | 手动删掉不重要的 |
| 总结消息摘要 | 把旧消息压缩成一段摘要 |

这里演示「总结摘要」：用 `SummarizationMiddleware`，当消息数超过阈值时自动把旧消息总结成摘要：

```python
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

middleware = SummarizationMiddleware(
    model="deepseek-chat",
    trigger=("messages", 6),  # 消息数超过 6 条时触发总结
    keep=("messages", 1),     # 总结后保留最近 1 条完整消息
)

agent = create_agent(
    model="deepseek-chat",
    middleware=[middleware],
    checkpointer=InMemorySaver(),
)
```

> 总结后，旧消息会被替换成一条 `HumanMessage`（内容是一段「会话摘要」），模型靠摘要也能「记住」关键信息，同时大幅省 token。

---

## 六、与 Java 类比

| LangChain | Java 类比 | 说明 |
|------|------|------|
| checkpointer | HttpSession / 会话存储 | 保存多轮对话状态 |
| `thread_id` | sessionId | 区分不同会话 |
| `InMemorySaver` | 内存中的 Session 实现 | 进程结束丢失 |
| `SqliteSaver` | 数据库持久化 Session（如 Spring Session + JDBC） | 重启后仍保留 |
| 打包历史消息发给模型 | 把 session 里的上下文序列化后一并传给后端 | 每次请求带上完整上下文 |
| `SummarizationMiddleware` | 会话压缩 / 过期清理策略 | 历史太长时做摘要，省空间 |

---

## 七、速查（一页纸）

1. **本质**：checkpointer 把历史 `messages` 存起来，下次 `invoke` 时打包发给模型
2. **无记忆**：不配 checkpointer，每次调用独立，模型「失忆」
3. **加短期记忆**：`checkpointer=InMemorySaver()` + 每次传 `{"configurable": {"thread_id": "..."}}`
4. **持久化**：`SqliteSaver(connection)` + `checkpointer.setup()` 自动建表
5. **记忆管理**：会话过长用 `SummarizationMiddleware`（`trigger` 触发、`keep` 保留）做摘要
