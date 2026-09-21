"""短期记忆（阶段 2 任务 6）。

用 LangGraph Checkpointer 把 AgentState 持久化，跨轮次保留对话上下文，
是场景四「动态模式切换」时复用历史 messages 的基础。

原理（Checkpointer 用两个维度定位一张状态快照）：
    thread_id      区分不同会话（Java 类比：流程实例 ID）
    checkpoint_id  区分同一会话的不同时刻（同一实例的历史版本号）

三种实现，都实现同一个 Checkpointer 接口，可插拔：
    MemorySaver   进程内存，进程重启即丢（开发 / 单测）
    SqliteSaver   落盘 SQLite，重启仍在（默认，单机持久化）
    RedisSaver    共享 Redis，多实例共享（阶段 8 微服务，预留分支）

Java 类比：
    get_checkpointer() = 工厂方法，按配置返回不同 Checkpointer 实现
    （类似 Spring 里 @ConditionalOnProperty 选择不同 Bean）
"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.config import settings


def get_checkpointer() -> object:
    """工厂：按 .env 的 CHECKPOINTER_TYPE 返回对应 Checkpointer。

    可插拔点：将来上微服务换 Redis，只需在这里加一个分支
    （pip install langgraph-checkpoint-redis 后引入 RedisSaver），
    调用方 compile(checkpointer=...) 一行都不用改。
    """
    kind = settings.checkpointer_type

    if kind == "memory":
        # 进程内存，重启即丢，仅开发 / 单测用
        return MemorySaver()

    if kind == "sqlite":
        # 落盘 SQLite（默认）。sqlite3.connect 不会自动建目录，
        # 先确保父目录存在，否则会报 unable to open database file。
        db_path = Path(settings.short_term_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False：允许跨线程访问，FastAPI 多线程部署时需要。
        # conn 与 checkpointer 同生命周期，进程退出由系统回收，无需手动 close。
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        return SqliteSaver(conn)

    if kind == "redis":
        # TODO(阶段8)：pip install langgraph-checkpoint-redis 后启用
        #   from langgraph.checkpoint.redis import RedisSaver
        #   return RedisSaver.from_conn_string(settings.redis_url)
        raise NotImplementedError(
            "Redis Checkpointer 待实现（阶段8，需安装 langgraph-checkpoint-redis）"
        )

    raise ValueError(
        f"未知的 CHECKPOINTER_TYPE：{kind}（可选：memory / sqlite / redis）"
    )
