"""五大 Agent 固定团队。

    router_agent     路由调度 Agent  —— 任务分类、模式切换、总流程控制
    knowledge_agent  知识检索 Agent  —— RAG 课件解析、知识点提取、资料溯源
    code_agent       代码实验 Agent  —— 代码生成、仿真、调试、报错修复
    writer_agent     内容写作 Agent  —— 报告、总结、文档结构化输出
    reviewer_agent   评审辩论 Agent  —— 代码审查、论文纠错、多 Agent 博弈评审

每个 Agent = 一个 system prompt + 一组挂载工具/技能 + 内部 ReAct 推理。
"""
