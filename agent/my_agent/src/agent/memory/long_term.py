"""长期记忆（阶段 2 任务 7）。

把「跨会话」沉淀的经验存成向量：用户薄弱点、易错知识点、历史任务经验，
存进向量库，下次遇到相似问题按需检索。

与短期记忆的区别（关键认知）：
    短期记忆 = 本次会话的上下文（Checkpointer 存 State，会话结束即定格）
    长期记忆 = 跨会话的知识（向量库存摘要，任何会话都能检索相似经验）

复用：直接复用 rag/vector_store.py 的 COLLECTION_HISTORY（个人沉淀库）
    「存」走 add()，「查」走 search()，向量化已在 vector_store 内部封装好。

Java 类比：
    短期记忆像「方法局部变量」，调用结束就消失；
    长期记忆像「数据库经验表」，每次任务后 INSERT，下次任务前 SELECT 相似记录。
"""

from agent.rag.vector_store import COLLECTION_HISTORY, get_vector_store

# 相关性阈值：与 rag/retriever.py 保持一致（L2 距离越小越相关）。
# 超过该距离视为「不相似」不召回，避免把无关经验塞给模型。
_DISTANCE_THRESHOLD = 1.0


def save_experience(summary: str) -> None:
    """沉淀一条经验摘要到长期记忆向量库（个人沉淀库）。

    参数 summary 是一段自然语言摘要，如「该生在二次方程求根上常漏判判别式」。
    内部走 vector_store.add()：先向量化，再写入 collection。
    """
    get_vector_store(COLLECTION_HISTORY).add([summary])


def recall_experience(query: str, top_k: int = 3) -> list[str]:
    """检索相似历史经验：把 query 向量化后到沉淀库做相似检索，返回相关摘要。"""
    results = get_vector_store(COLLECTION_HISTORY).search(query, top_k)
    return [r["text"] for r in results if r["distance"] <= _DISTANCE_THRESHOLD]
