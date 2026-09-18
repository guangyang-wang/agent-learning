"""MCP 客户端封装。

统一访问向量库、文件、沙箱、数据库等资源。
"""


class MCPClient:
    """MCP 客户端（占位）。"""

    def __init__(self) -> None:
        self._servers: dict = {}

    def connect(self, server_name: str) -> None:
        """连接某个 MCP server。"""
        # TODO(阶段7)：加载 MCP server（向量库 / 文件 / 沙箱 / 数据库）
        raise NotImplementedError

    def call_tool(self, server: str, tool: str, args: dict) -> object:
        """调用 MCP 工具。"""
        # TODO(阶段7)
        raise NotImplementedError
