"""为 OP-003 与 OP-006 预留的仅类型 MCP Provider 边界。"""

from typing import Protocol


class McpProvider(Protocol):
    """仅作标记；本任务不打开 MCP 连接或工具目录。"""
