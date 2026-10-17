"""全局使用次数计数（阶段：对外共享部署）。

所有使用者共享一个上限（默认 50 次），计数落 SQLite，进程重启不丢。
只统计真正调用大模型的任务（/chat、/plan），课件上传 / 检索调试不计。

并发安全：
    UPDATE ... WHERE used < limit 是一条原子语句，
    多个请求同时进来也不会把计数加超；超出上限的请求直接拒绝。

Java 类比：
    类似数据库里的「库存扣减」：先条件更新，rowcount=0 说明扣减失败（次数已用完）。
"""

import sqlite3
from pathlib import Path

from agent.config import settings


class UsageLimitExceeded(RuntimeError):
    """全局使用次数已用完。"""


def _connect() -> sqlite3.Connection:
    path = Path(settings.usage_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None：关闭隐式事务，由下面显式 BEGIN IMMEDIATE 控制
    conn = sqlite3.connect(
        str(path), timeout=10, check_same_thread=False, isolation_level=None
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS usage_counter ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "used INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT OR IGNORE INTO usage_counter (id, used) VALUES (1, 0)")
    return conn


def _snapshot(used: int) -> dict:
    limit = settings.usage_limit
    return {
        "used": used,
        "limit": limit,
        "remaining": max(limit - used, 0),
    }


def consume() -> dict:
    """原子地消耗一次额度，返回 {used, limit, remaining}。

    次数用完时抛 UsageLimitExceeded。调用方应在任务开始前调用——
    任务中途失败也不退还（大模型可能已经产生费用）。
    """
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            "UPDATE usage_counter SET used = used + 1 "
            "WHERE id = 1 AND used < ?",
            (settings.usage_limit,),
        )
        if cursor.rowcount == 0:
            conn.execute("ROLLBACK")
            raise UsageLimitExceeded(
                f"使用次数已用完（{settings.usage_limit}/{settings.usage_limit}），请联系管理员"
            )
        used = conn.execute(
            "SELECT used FROM usage_counter WHERE id = 1"
        ).fetchone()[0]
        conn.execute("COMMIT")
        return _snapshot(used)
    except UsageLimitExceeded:
        raise
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def status() -> dict:
    """查询当前用量，不消耗次数。"""
    conn = _connect()
    try:
        used = conn.execute(
            "SELECT used FROM usage_counter WHERE id = 1"
        ).fetchone()[0]
        return _snapshot(used)
    finally:
        conn.close()
