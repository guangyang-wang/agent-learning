"""检索器（含回退策略）（阶段 2 任务 5）。

把 vector_store 的「相似检索」包装成对上层友好的两个能力：

    retrieve(query)               只查用户私有库（课件），过滤低相关片段
    retrieve_with_fallback(query) 私有库没命中 -> 逐级回退沉淀库 / 公共库，
                                  并用布尔值标注「是否命中课件」，避免模型编造

数据源优先级（高 -> 低）：
    用户私有上传库（课件/教材） -> 个人学习沉淀库 -> 公共库（联网兜底，阶段后置）

Java 类比：
    retriever = Service 层，vector_store = DAO 层。
    Service 不关心底层是 Chroma 还是 FAISS，只把「查库」翻译成业务语义
    （拿到哪些片段 + 是不是来自课件），上层 graph 节点据此决定要不要补一句「无课件依据」。
"""

from agent.rag.vector_store import (
    COLLECTION_HISTORY,
    COLLECTION_PRIVATE,
    COLLECTION_PUBLIC,
    get_vector_store,
)

# 相关性阈值：Chroma 返回 L2 距离（越小越相关，0 = 完全一致）。
# 超过该距离的片段视为「不相关」不返回，从而触发空结果回退。
# BGE 归一化向量下，距离 1.0 ≈ 余弦相似度 0.5，是偏保守的起点，可按业务调优。
_DISTANCE_THRESHOLD = 1.0


def _filter_relevant(results: list[dict], threshold: float) -> list[str]:
    """过滤 search 结果，只留 distance <= threshold 的文本片段。

    vector_store.search() 返回 [{"text": ..., "distance": ...}]，
    这里只取 text，并按相关性阈值筛掉「沾边但不够像」的片段。
    """
    return [r["text"] for r in results if r["distance"] <= threshold]


def _search_collection(collection: str, query: str, top_k: int) -> list[str]:
    """查指定数据源并过滤低相关片段（retrieve 与回退共用的底层）。"""
    results = get_vector_store(collection).search(query, top_k)
    return _filter_relevant(results, _DISTANCE_THRESHOLD)


def retrieve(query: str, top_k: int = 4) -> list[str]:
    """相似检索：只查用户私有库（课件），返回相关片段列表。"""
    return _search_collection(COLLECTION_PRIVATE, query, top_k)


def retrieve_with_fallback(query: str, top_k: int = 4) -> tuple[list[str], bool]:
    """检索 + 回退。

    优先级：私有库（课件）-> 个人沉淀库 -> 公共库。
    返回 (片段列表, 是否命中私有库)：hit_private=False 说明没在课件里找到依据，
    上层应据此标注「无课件依据」，而不是让模型凭空编造。
    """
    # 1. 私有库（课件）—— 最高优先级，命中即返回，无需标注
    chunks = retrieve(query, top_k)
    if chunks:
        return chunks, True

    # 2. 回退 1：个人沉淀库（历史代码 / 错题 / 笔记）
    chunks = _search_collection(COLLECTION_HISTORY, query, top_k)
    if chunks:
        return chunks, False

    # 3. 回退 2：公共库（联网兜底，阶段后置，通常为空）
    chunks = _search_collection(COLLECTION_PUBLIC, query, top_k)
    if chunks:
        return chunks, False

    # 4. 全部为空 —— 明确返回「未命中」，由上层标注「无课件依据」
    return [], False