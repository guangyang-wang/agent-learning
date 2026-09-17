"""记忆系统。

    short_term  短期记忆 —— 本次会话上下文、任务进度、中间结果
                （LangGraph Checkpointer 持久化 State）
    long_term   长期记忆 —— 用户学科、薄弱点、历史任务经验、易错知识点
                （向量库存经验摘要，按需检索）
"""
