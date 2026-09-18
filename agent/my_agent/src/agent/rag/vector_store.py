"""向量库封装（Chroma / FAISS）。

按数据源隔离：用户私有库 / 个人沉淀库 / 公共库 可建独立 collection。
"""


def get_vector_store(collection: str) -> object:
    """获取（或创建）指定数据源的向量库。"""
    # TODO(阶段2)：Chroma / FAISS，按 collection 隔离
    raise NotImplementedError("向量库待实现（阶段2）")


def add_documents(collection: str, chunks: list[str]) -> None:
    """写入 chunk 到指定向量库。"""
    # TODO(阶段2)
    raise NotImplementedError
