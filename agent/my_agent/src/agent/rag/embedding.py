"""向量化（Embedding）。

把文本 chunk 转成向量，供向量库存储与相似检索。
"""


def get_embeddings() -> object:
    """返回 embedding 模型实例。"""
    # TODO(阶段2)：接入 OpenAIEmbeddings 或 DeepSeek 兼容 embedding
    raise NotImplementedError("embedding 待实现（阶段2）")
