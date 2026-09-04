"""守护 OP-002 承诺：增强包只能包含契约。"""

from pathlib import Path

from opspilot.agent.contracts import IncidentCommander
from opspilot.providers.mcp.contracts import McpProvider
from opspilot.skills.contracts import SkillRegistry
from opspilot.specialists.contracts import Specialist

BOUNDARY_FILES = (
    "agent/contracts.py",
    "providers/mcp/contracts.py",
    "skills/contracts.py",
    "specialists/contracts.py",
)
FORBIDDEN_RUNTIME_TOKENS = ("def ", "async def ", "import langgraph", "import mcp")


def test_reserved_enhancement_boundaries_do_not_implement_runtime_behavior() -> None:
    source_root = Path(__file__).parents[1] / "src" / "opspilot"

    for relative_path in BOUNDARY_FILES:
        source = (source_root / relative_path).read_text(encoding="utf-8")
        assert not any(token in source for token in FORBIDDEN_RUNTIME_TOKENS), relative_path


def test_reserved_boundaries_are_named_protocols() -> None:
    assert [
        IncidentCommander.__name__,
        McpProvider.__name__,
        SkillRegistry.__name__,
        Specialist.__name__,
    ] == ["IncidentCommander", "McpProvider", "SkillRegistry", "Specialist"]
