"""The fixed stable tool vocabulary. Provider catalog observations never extend it."""

from opspilot.db.enums import HealthScope
from opspilot.tools.contracts import STABLE_TOOL_CONTRACTS

STABLE_READ_ONLY_TOOLS = frozenset(STABLE_TOOL_CONTRACTS)


def health_scope_for(stable_name: str) -> HealthScope:
    """Return the only allowed health scope for a registered stable tool."""
    return STABLE_TOOL_CONTRACTS[stable_name].health_scope
