"""为 OP-007 预留的仅类型 Agent 边界。

OP-002 不实现图、节点、模型调用或其他运行时行为。
"""

from typing import Protocol


class IncidentCommander(Protocol):
    """未来 L1 协调器的标记；契约细节由对应任务负责。"""
