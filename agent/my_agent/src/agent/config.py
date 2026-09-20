"""配置管理。

统一从环境变量 / .env 读取配置，供 LLM 工厂、服务层、可观测层使用。

Java 类比：类似 Spring Boot 的 application.yml + @ConfigurationProperties，
    把散落的配置集中到一个 Config 对象里。
"""

import os

from dotenv import load_dotenv


class Settings:
    """集中配置对象（占位，后续按需扩展字段）。"""

    def __init__(self) -> None:
        load_dotenv()  # 加载项目根目录 .env

        # ---- LLM（DeepSeek 默认） ----
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.deepseek_base_url: str = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com"
        )

        # ---- Embedding（向量化，默认硅基流动 BGE） ----
        self.embedding_provider: str = os.getenv(
            "EMBEDDING_PROVIDER", "siliconflow"
        )
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
        self.siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
        self.siliconflow_base_url: str = os.getenv(
            "SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1"
        )
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

        # ---- 可观测 ----
        self.langsmith_tracing: bool = (
            os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        )
        self.langsmith_project: str = os.getenv(
            "LANGSMITH_PROJECT", "learning-agent"
        )

        # ---- 服务 ----
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8000"))


# 全局单例（Java 类比：静态单例 Bean）
settings = Settings()
