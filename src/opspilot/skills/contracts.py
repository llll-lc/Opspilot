"""Stable Skill data contracts. Skills prescribe method; they grant no tool permission."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillRegistry:
    """Compatibility marker; the concrete fixed registry is in ``registry.py``."""


class SkillOutput(BaseModel):
    """The only structured outcome a future Agent may consume from a selected Skill."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skill_key: str
    skill_version: str
    conclusion: Literal["SUPPORTED", "INSUFFICIENT_EVIDENCE", "ESCALATE"]
    required_observations: tuple[str, ...]
    collected_observation_ids: tuple[str, ...]
    missing_observations: tuple[str, ...]
    recommended_next_stable_tool: str | None
    escalation_reason: str | None


class SkillDefinition(BaseModel):
    """Validated immutable front matter of a checked-in `SKILL.md` artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    version: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    enabled: bool
    target_system: Literal["SUPERSET"]
    applicable_versions: tuple[str, ...]
    trigger_terms: tuple[str, ...]
    required_observations: tuple[str, ...]
    stable_tool_sequence: tuple[str, ...]
    evidence_threshold: str
    stop_or_escalate: tuple[str, ...]
    prohibited_actions: tuple[str, ...]
    output_schema: Literal["opspilot.skill-output.v1"]
    references: tuple[str, ...]
