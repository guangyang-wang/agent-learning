# 大学生智能学习多 Agent 系统

> 基于 **LangChain（能力封装）+ LangGraph（编排调度）** 的全场景学习辅助系统。
> 覆盖课程答疑、习题解答、课件学习、代码实验、报告撰写、论文评审、错题复习。

完整设计见 [`架构设计与业务场景.md`](./架构设计与业务场景.md)，本仓库是它的代码骨架。

---

## 一、架构总览（五层）

```
┌────────────────────────────────────────────────────────────┐
│ 1. 用户接入层：文本提问 / PDF课件上传 / 实验需求 / 论文上传     │
├────────────────────────────────────────────────────────────┤
│ 2. 智能路由层：任务复杂度分类器 → 动态路由三张子图            │
│    simple → ReAct子图  complex → Plan子图  debate → 辩论子图 │
├────────────────────────────────────────────────────────────┤
│ 3. 核心执行层：ReAct子图 | Plan+多Agent流水线子图 | 辩论子图   │
├────────────────────────────────────────────────────────────┤
│ 4. 统一安全&稳定中间层：防死循环(四层) + 工具人机确认(HITL)   │
├────────────────────────────────────────────────────────────┤
│ 5. 基础能力层：RAG三层知识库 | 短期+长期记忆 | Skill | 工具 | MCP│
└────────────────────────────────────────────────────────────┘
```

**一句话定位**：LangChain 提供「零件」（工具/RAG/记忆/Prompt/LLM），LangGraph 负责「装配与运转」（状态机/节点流转/分支路由/多 Agent 协作/人机介入）。

**范式分层（1 底座 + 2 编排）**：一种底层推理范式（ReAct）+ 两种上层编排范式（Plan-and-Execute 流水线 / 对等辩论），上层编排复用底层 ReAct 推理。

---

## 二、目录结构

```
my_agent/
├── 架构设计与业务场景.md        # 设计文档（终稿）
├── README.md                   # 本文件
├── requirements.txt            # 依赖（pip install -r）
├── pyproject.toml              # 用于 `pip install -e .` 可编辑安装
├── .env.example                # 环境变量模板（复制为 .env）
├── .gitignore
├── src/
│   └── agent/
│       ├── __init__.py         # 包说明 + 分层总览
│       ├── state.py            # AgentState 全局状态 Schema（核心契约）
│       ├── config.py           # 配置（环境变量加载）
│       ├── main.py             # 程序入口（阶段5：三图合一）
│       ├── llm/                # LLM 可插拔层（DeepSeek 默认）
│       │   └── factory.py      #   模型工厂
│       ├── graph/              # LangGraph 编排层
│       │   ├── router.py       #   路由分类器 + 三图分流
│       │   ├── nodes.py        #   共享节点
│       │   ├── react_graph.py  #   ReAct 子图（阶段1）
│       │   ├── plan_graph.py   #   Plan-and-Execute 子图（阶段3）
│       │   └── debate_graph.py #   多Agent辩论子图（阶段4）
│       ├── agents/             # 五大 Agent 固定团队
│       │   ├── router_agent.py     # 路由调度 Agent
│       │   ├── knowledge_agent.py  # 知识检索 Agent
│       │   ├── code_agent.py       # 代码实验 Agent
│       │   ├── writer_agent.py     # 内容写作 Agent
│       │   └── reviewer_agent.py   # 评审辩论 Agent
│       ├── rag/                # RAG 三层知识库（阶段2）
│       │   ├── loader.py           # 文档加载/PDF解析
│       │   ├── splitter.py         # 分块
│       │   ├── embedding.py        # 向量化
│       │   ├── vector_store.py     # 向量库（Chroma/FAISS）
│       │   └── retriever.py        # 检索 + 回退
│       ├── memory/             # 记忆系统（阶段2）
│       │   ├── short_term.py       # 短期（Checkpointer）
│       │   └── long_term.py        # 长期（向量库经验摘要）
│       ├── tools/              # 标准工具库（安全分级）
│       │   ├── registry.py         # 注册中心 + 安全分级
│       │   ├── safe_tools.py       # 安全工具（自动执行）
│       │   └── dangerous_tools.py  # 高危工具（人机确认）
│       ├── skills/             # Skill 可插拔技能库（阶段7）
│       │   ├── base.py             # Skill 基类
│       │   ├── course_qa.py        # 课件解析/习题推导
│       │   ├── code_experiment.py  # 代码实验
│       │   ├── report_gen.py       # 报告生成
│       │   └── paper_review.py     # 论文评审
│       ├── mcp/                # MCP 资源调用（阶段7）
│       │   └── client.py
│       ├── safety/             # 安全&稳定中间层（阶段6）
│       │   ├── anti_loop.py        # 防死循环（四层机制）
│       │   └── hitl.py             # 人机确认（interrupt）
│       ├── evaluation/         # 评估体系（阶段8）
│       │   ├── metrics.py          # 指标统计
│       │   └── benchmark.py        # 测试集评测
│       ├── api/                # FastAPI 部署（阶段8）
│       │   ├── app.py
│       │   └── schemas.py
│       └── observability/      # 可观测（阶段8）
│           └── tracing.py          # LangSmith/Langfuse
└── tests/                      # 测试
    └── test_react_graph.py
```

---

## 三、快速开始

```bash
# 1. 进入项目
cd my_agent

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
# Windows:
.venv\Scripts\activate
# 安装依赖
pip install -r requirements.txt
# 可编辑安装，让 `agent` 包可被 import
pip install -e .

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 4. 运行（阶段1实现后可跑）
python -m agent.main
```

> 提示：`faiss-cpu` 在 Python 3.13 上可能暂无 wheel，可先只用 `chromadb`（已在 requirements.txt 中注释说明）。

---

## 四、8 阶段落地路线图

| 阶段 | 内容 | 对应模块 | 状态 |
|---|---|---|---|
| 1 | 单 Agent ReAct + 2~3 工具 | `graph/react_graph.py`、`tools/`、`llm/` | 待实现 |
| 2 | RAG + Checkpointer 记忆 | `rag/`、`memory/` | 待实现 |
| 3 | Plan-and-Execute 子图 | `graph/plan_graph.py` | 待实现 |
| 4 | 多 Agent 辩论子图 | `graph/debate_graph.py` | 待实现 |
| 5 | 路由分类器，三图合一 | `graph/router.py`、`main.py` | 待实现 |
| 6 | 防死循环 + 人机确认 | `safety/` | 待实现 |
| 7 | MCP + Skill 插件化 | `mcp/`、`skills/` | 待实现 |
| 8 | 评估 + FastAPI + 追踪 | `evaluation/`、`api/`、`observability/` | 待实现 |

> 建议按 1 → 8 顺序推进，每阶段可运行、可演示，最后拼成完整系统。

---

## 五、核心概念：Java 类比速查

| LangGraph / LangChain | Java 类比 |
|---|---|
| `StateGraph` | 状态机 + 工作流引擎 |
| 节点（node） | 工作流里的方法 / 步骤 |
| 边（edge）/ 条件边 | 跳转条件 / if-else 分支 |
| `AgentState` (TypedDict) | 流程上下文 DTO（Context 对象） |
| `add_messages` reducer | 往 List append 而非 set 覆盖 |
| `interrupt()` | 工作流引擎「需人工审批的挂起点」 |
| `Checkpointer` | 流程实例持久化存储（如 Activiti 实例表） |
| 工具调用（Function Calling） | 接口回调 / 依赖注入 |
| 短期记忆 | 会话缓存 / 线程本地上下文 |
| 长期记忆（向量库） | 持久层 / 相似经验检索 |
| 模型工厂（可插拔 LLM） | 工厂模式 + 面向接口编程 |

---

## 六、两个真实技术亮点（答辩重点）

1. **分层范式设计**：底层 ReAct + 上层 Plan/辩论，上层复用底层推理。
2. **人机在环安全确认**：LangGraph 原生 `interrupt()` + `Command(resume=...)`，彻底解决任意代码执行、隐私爬取等风险。

另：**动态模式切换**（场景四）——一套系统、三架构自适应，是本项目的创新点。
