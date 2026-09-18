"""工具注册中心 + 安全分级。

作用：
    把散落在各文件里的工具（BaseTool 对象）统一收口到一个注册表，
    后续 graph 层用 all_tools() 取工具列表去 bind_tools / 建 ToolNode。

Java 类比：
    ToolRegistry ≈ Spring 的 Bean 容器 / 服务注册表，工具 = Bean，
    按 name 注册，使用时全量取出，或按 name 查询安全级别。
"""

from enum import Enum

from langchain_core.tools import BaseTool

from agent.tools.safe_tools import calculator, get_current_time, rag_search


class ToolLevel(str, Enum):
    """工具安全级别。"""

    SAFE = "safe"            # 安全工具：自动执行，无需确认
    DANGEROUS = "dangerous"  # 高危工具：必须人机确认（阶段6）


class ToolRegistry:
    """工具注册表：统一存放 BaseTool 对象 + 对应安全级别。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}    # name -> BaseTool 对象
        self._levels: dict[str, ToolLevel] = {}  # name -> 安全级别

    def register(self, tool: BaseTool, level: ToolLevel) -> None:
        """注册一个工具（BaseTool 对象）并标注安全级别。"""
        self._tools[tool.name] = tool
        self._levels[tool.name] = level

    def get_level(self, name: str) -> ToolLevel:
        """查询工具的安全级别。

        阶段6 会在这里加白名单校验（非法工具名直接拒绝），当前先直接查表。
        """
        return self._levels[name]

    def all_tools(self) -> list[BaseTool]:
        """返回所有已注册工具的 BaseTool 对象列表（给 bind_tools / ToolNode 用）。"""
        return list(self._tools.values())


def build_default_registry() -> ToolRegistry:
    """构建默认注册表：把阶段1 已实现的安全工具全部注册进去。"""
    registry = ToolRegistry()
    registry.register(calculator, ToolLevel.SAFE)
    registry.register(get_current_time, ToolLevel.SAFE)
    registry.register(rag_search, ToolLevel.SAFE)
    return registry