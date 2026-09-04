"""为 OP-005 预留的仅类型 Skill Registry 边界。"""

from typing import Protocol


class SkillRegistry(Protocol):
    """仅作标记；有意不实现发现、解析或加载。"""
