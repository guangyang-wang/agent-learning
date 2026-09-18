"""高危工具（调用前必须经人机确认）。

示例：代码运行（沙箱）、联网搜索、文件写入。
"""


def run_code(code: str) -> str:
    """在沙箱中运行代码（高危，需 HITL 确认）。"""
    # TODO(阶段3)：沙箱执行 + 报错回传
    raise NotImplementedError


def web_search(query: str) -> str:
    """联网搜索（高危，需 HITL 确认）。"""
    # TODO(阶段7)
    raise NotImplementedError


def write_file(path: str, content: str) -> str:
    """写文件（高危，需 HITL 确认）。"""
    # TODO(阶段7)
    raise NotImplementedError
