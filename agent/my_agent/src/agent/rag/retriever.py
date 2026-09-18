"""检索器（含回退策略）。

检索为空时回退公共知识，并明确标注「未找到课件依据」。
"""


def retrieve(query: str, top_k: int = 4) -> list[str]:
    """相似检索，返回相关片段列表。"""
    # TODO(阶段2)：向量库 similarity_search + 相关性校验
    raise NotImplementedError("检索待实现（阶段2）")


def retrieve_with_fallback(query: str) -> tuple[list[str], bool]:
    """检索 + 回退。返回 (片段列表, 是否命中私有知识库)。"""
    # TODO(阶段2)：私有库为空时回退公共资源，标注无课件依据
    raise NotImplementedError
