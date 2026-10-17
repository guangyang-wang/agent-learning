"""大模型任务闸门：同一时刻只允许一个任务调用大模型。

实现：进程级非阻塞互斥锁。
    拿到锁 -> 执行任务 -> finally 释放
    拿不到 -> 立刻抛 BusyError（HTTP 429），不排队等待

注意：锁是进程内的。当前用单个 uvicorn worker 部署是够的；
如果以后开多 worker / 多实例，需要换成 Redis 锁或数据库租约。
"""

import threading
from contextlib import contextmanager


class BusyError(RuntimeError):
    """已有任务正在使用大模型。"""


_lock = threading.Lock()


@contextmanager
def llm_slot():
    """非阻塞地占用大模型执行权；忙时抛 BusyError。"""
    if not _lock.acquire(blocking=False):
        raise BusyError("别人正在使用，请你稍后")
    try:
        yield
    finally:
        _lock.release()
