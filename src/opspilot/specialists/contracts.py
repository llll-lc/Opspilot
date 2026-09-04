"""为 OP-009 预留的仅类型 Specialist 边界。"""

from typing import Protocol


class Specialist(Protocol):
    """仅作标记；这里不实现委派或子智能体执行。"""
