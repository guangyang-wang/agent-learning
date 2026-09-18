"""大学生智能学习多Agent系统。

LangChain（能力封装）+ LangGraph（编排调度）。

分层结构（对应《架构设计与业务场景.md》五层架构）：
    llm/          —— LLM 可插拔层（DeepSeek 默认）
    graph/        —— LangGraph 编排层（路由 + 三张子图）
    agents/       —— 五大 Agent 固定团队
    rag/          —— RAG 三层知识库
    memory/       —— 短期 + 长期记忆
    tools/        —— 标准工具库（安全分级）
    skills/       —— Skill 可插拔技能库
    mcp/          —— MCP 资源调用
    safety/       —— 安全 & 稳定中间层（防死循环 + 人机确认）
    evaluation/   —— 评估体系
    api/          —— FastAPI 部署
    observability/—— LangSmith/Langfuse 追踪
"""

__version__ = "0.1.0"
