"""向量库封装（阶段 2 任务 4）。

用 Chroma 存储 embedding，按数据源隔离（用户私有库 / 个人沉淀库 / 公共库
各自一个 collection），暴露「存」和「查」两个核心能力。

设计（可插拔，沿用 loader.py / embedding.py 的「接口 + 实现」思路）：
    VectorStore        抽象接口（Java 类比：接口）
    ChromaVectorStore   Chroma 实现（当前默认）
    get_vector_store()  工厂：按 collection 名返回对应向量库

说明：这里直接用 chromadb，而不是 langchain 的 Chroma 封装，是为了看清
    「向量库」底层其实就是 collection.add / collection.query 两步。
    以后想换 FAISS / Milvus，新增一个实现类 + 工厂加分支即可。
"""

import uuid
from abc import ABC, abstractmethod

import chromadb

from agent.config import settings
from agent.rag.embedding import get_embeddings

# 三个数据源（对应 README 的优先级：高 -> 低），各建独立 collection 互不干扰
COLLECTION_PRIVATE = "user_private"  # 用户私有上传库（课件/教材/试卷）
COLLECTION_HISTORY = "user_history"  # 个人学习沉淀库（历史代码/错题/笔记）
COLLECTION_PUBLIC = "public"         # 公共库（联网兜底，阶段后置）


class VectorStore(ABC):
    """向量库抽象接口：存文本 + 相似检索。

    Java 类比：接口。定义 add / search 两个方法，由具体实现（Chroma / FAISS）提供。
    """

    @abstractmethod
    def add(self, texts: list[str], metadatas: list[dict] | None = None) -> None:
        """把文本向量化后写入向量库。"""
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, top_k: int = 4) -> list[dict]:
        """相似检索，返回 top_k 个最相关片段（每个含 text 与 distance）。"""
        raise NotImplementedError


class ChromaVectorStore(VectorStore):
    """Chroma 向量库实现。

    每个数据源一个 collection，互不干扰。底层就是 collection.add / collection.query，
    这里直接调用看清「存」和「查」到底发生了什么。

    注意：distance 是 L2 距离，越小越相关（0 = 完全一致）。
    """

    def __init__(self, collection_name: str, persist_dir: str) -> None:
        self._embedder = get_embeddings()
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name
        )

    def add(self, texts: list[str], metadatas: list[dict] | None = None) -> None:
        if not texts:
            return
        # 1. 文本 -> 向量（复用阶段 2 任务 3 的 embedder）
        vectors = self._embedder.embed_documents(texts)
        # 2. 写入 collection；Chroma 要求每条记录 id 唯一，用 uuid4 生成
        ids = [uuid.uuid4().hex for _ in texts]
        self._collection.add(
            ids=ids,
            documents=texts,
            embeddings=vectors,
            metadatas=metadatas,
        )

    def search(self, query: str, top_k: int = 4) -> list[dict]:
        query_vec = self._embedder.embed_query(query)
        result = self._collection.query(
            query_embeddings=[query_vec], n_results=top_k
        )
        # result 是「每个查询对应一个结果列表」，单查询取 [0]
        documents = result["documents"][0]
        distances = result["distances"][0]
        return [
            {"text": doc, "distance": dist}
            for doc, dist in zip(documents, distances)
        ]


def get_vector_store(collection: str = COLLECTION_PRIVATE) -> VectorStore:
    """工厂：返回指定数据源的向量库（按 collection 隔离）。"""
    return ChromaVectorStore(
        collection_name=collection,
        persist_dir=settings.chroma_db_path,
    )


def add_documents(
    collection: str, chunks: list[str], metadatas: list[dict] | None = None
) -> None:
    """便捷函数：把 chunk 写入指定数据源的向量库。"""
    get_vector_store(collection).add(chunks, metadatas)