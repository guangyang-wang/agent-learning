"""长期记忆。

把历史任务经验、薄弱点、易错知识点存成摘要向量，按需检索相似经验。
"""


def save_experience(summary: str) -> None:
    """沉淀一条经验摘要到长期记忆向量库。"""
    # TODO(阶段2/8)：向量库 + 摘要写入
    raise NotImplementedError("长期记忆写入待实现")


def recall_experience(query: str, top_k: int = 3) -> list[str]:
    """检索相似历史经验。"""
    # TODO(阶段2/8)
    raise NotImplementedError("长期记忆检索待实现")
