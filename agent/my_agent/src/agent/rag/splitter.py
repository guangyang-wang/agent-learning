"""文本分块。

把长文档切成适合嵌入的 chunk（兼顾语义完整与长度上限）。
"""


def split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """切分文本，返回 chunk 列表。"""
    # TODO(阶段2)：RecursiveCharacterTextSplitter
    raise NotImplementedError("文本分块待实现（阶段2）")
