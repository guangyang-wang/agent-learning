"""文档加载与解析。

支持 PDF 课件 / 教材 / 实验指导书等。解析失败时容错降级（分段解析）。
"""


def load_document(path: str) -> list[str]:
    """加载单个文档，返回分页/分段的原始文本列表。"""
    # TODO(阶段2)：PyPDFLoader / UnstructuredLoader，失败时分段降级
    raise NotImplementedError("文档加载待实现（阶段2）")


def load_directory(dir_path: str) -> list[str]:
    """批量加载目录下所有文档。"""
    # TODO(阶段2)
    raise NotImplementedError
