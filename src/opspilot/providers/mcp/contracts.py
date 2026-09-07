"""受控 MCP Provider 的保留边界；具体客户端由 OP-006 Gateway 隔离。"""

from typing import Protocol


class McpProvider(Protocol):
    """Marker Protocol; no runtime implementation belongs in this reserved contract."""
