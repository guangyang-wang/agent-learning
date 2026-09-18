"""工具注册中心 + 安全分级。

统一注册所有工具，标注安全级别；所有工具调用都经过安全中间层。
"""

from enum import Enum


class ToolLevel(str, Enum):
    """工具安全级别。"""

    SAFE = "safe"            # 自动执行
    DANGEROUS = "dangerous"  # 必须人机确认


class ToolRegistry:
    """工具注册表（占位）。"""

    def __init__(self) -> None:
        self._tools: dict[str, dict] = {}  # name -> {func, level}

    def register(self, name: str, func, level: ToolLevel) -> None:
        """注册工具并标注安全级别。"""
        self._tools[name] = {"func": func, "level": level}

    def get_level(self, name: str) -> ToolLevel:
        """查询工具安全级别。"""
        # TODO(阶段6)：白名单校验，非法工具名直接拒绝
        raise NotImplementedError

    def all_tools(self) -> list:
        """返回所有工具的 LangChain Tool 包装。"""
        # TODO(阶段1/6)
        raise NotImplementedError
