"""向量化（阶段 2 任务 3）。

把文本 chunk 转成向量，供向量库存储与相似检索。

关键认知：向量化不是「大模型」（Chat LLM）做的，而是专门的 embedding 模型。
    DeepSeek 官方没有 embedding 接口，所以这里接硅基流动（OpenAI 兼容）的 BGE 模型。

设计（可插拔，沿用 loader.py 的「接口 + 实现」思路）：
    Embedder                  抽象接口（Java 类比：接口）
    OpenAICompatibleEmbedder   OpenAI 兼容服务的通用实现（硅基流动 / OpenAI 都走这一套）
    get_embeddings()           工厂：按 .env 的 EMBEDDING_PROVIDER 返回对应实现

说明：langchain 的 OpenAIEmbeddings 底层就是调 openai SDK 的 embeddings.create()，
    这里手写这一层，看清「文本 -> 向量」到底发生了什么。以后想换本地 BGE，
    只需新增一个 LocalBgeEmbedder(Embedder) 实现，工厂加一个分支即可。
"""

from abc import ABC, abstractmethod

from openai import OpenAI

from agent.config import settings


class Embedder(ABC):
    """embedding 抽象接口：把文本转成定长向量。

    Java 类比：接口。定义两个方法，由具体服务实现：
        embed_documents  批量向量化（文档分块入库时用）
        embed_query      单条查询向量化（检索时用）
    """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量把多个文本转成向量，返回与输入等长的向量列表。"""
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """把单条查询文本转成向量。"""
        raise NotImplementedError


class OpenAICompatibleEmbedder(Embedder):
    """OpenAI 兼容 embedding 服务（硅基流动、OpenAI 均适用）。

    底层就是一次 HTTP POST /embeddings，openai SDK 帮我们做鉴权与重试；
    这正是 langchain 的 OpenAIEmbeddings 封装的那一层，这里手写出来看清底层。
    """

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        if not api_key:
            raise ValueError(
                "embedding API Key 为空，请在 .env 里配置 SILICONFLOW_API_KEY"
            )
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self._model, input=texts
        )
        # 返回顺序与 input 一致，逐条取 .embedding
        return [item.embedding for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def get_embeddings() -> Embedder:
    """工厂：按 .env 的 EMBEDDING_PROVIDER 返回对应 embedding 实现。

    可插拔点：以后想换本地 BGE / OpenAI，改 .env 一行 + 这里加一个分支即可。
    """
    provider = settings.embedding_provider

    if provider == "siliconflow":
        return OpenAICompatibleEmbedder(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            model=settings.embedding_model,
        )

    if provider == "openai":
        return OpenAICompatibleEmbedder(
            api_key=settings.openai_api_key,
            base_url="https://api.openai.com/v1",
            model=settings.embedding_model,
        )

    raise ValueError(
        f"未知的 EMBEDDING_PROVIDER：{provider}（可选：siliconflow / openai）"
    )