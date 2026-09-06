"""Fixed, hash-verified Skill Registry. It neither downloads nor executes Skills."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import ValidationError

from opspilot.skills.contracts import SkillDefinition

STABLE_TOOL_NAMES = frozenset(
    {
        "check_target_connector_health",
        "get_target_instance_summary",
        "get_target_application_health",
        "get_target_runtime_health",
        "list_target_databases",
        "get_target_database_info",
        "list_target_datasets",
        "get_target_dataset_info",
        "list_target_dashboards",
        "get_target_dashboard_info",
        "get_target_report_schedule",
        "get_target_report_run_history",
    }
)


class SkillRejected(ValueError):
    """A deterministic rejection that a future Agent must treat as safe unavailability."""


def _split_front_matter(content: str) -> tuple[dict[str, object], str]:
    if not content.startswith("---\n"):
        raise SkillRejected("SKILL.md must begin with JSON-compatible YAML front matter")
    _, remainder = content.split("---\n", 1)
    try:
        raw, body = remainder.split("\n---\n", 1)
    except ValueError as error:
        raise SkillRejected("SKILL.md front matter is not closed") from error
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SkillRejected("SKILL.md front matter is not valid JSON-compatible YAML") from error
    if not isinstance(parsed, dict):
        raise SkillRejected("SKILL.md front matter must be an object")
    return parsed, body


def semantic_hash(content: str) -> str:
    """Hash parsed metadata excluding self-referential hash plus exact Markdown body."""
    metadata, body = _split_front_matter(content)
    metadata.pop("content_hash", None)
    canonical = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((canonical + "\n---\n" + body).encode("utf-8")).hexdigest()


class FixedSkillRegistry:
    """Load only repository-owned allowlisted Skill directories provided at construction."""

    def __init__(self, root: Path, *, enabled: bool) -> None:
        self._root = root
        self._enabled = enabled
        self._loaded: dict[str, SkillDefinition] | None = None

    def load(self) -> dict[str, SkillDefinition]:
        if not self._enabled:
            raise SkillRejected("Skill Registry is disabled by server configuration")
        if self._loaded is not None:
            return dict(self._loaded)
        loaded: dict[str, SkillDefinition] = {}
        for directory in sorted(path for path in self._root.iterdir() if path.is_dir()):
            skill_path = directory / "SKILL.md"
            if not skill_path.is_file():
                raise SkillRejected(f"missing Skill artifact: {directory.name}")
            content = skill_path.read_text(encoding="utf-8")
            metadata, _ = _split_front_matter(content)
            try:
                definition = SkillDefinition.model_validate(metadata)
            except ValidationError as error:
                raise SkillRejected(f"invalid Skill metadata: {directory.name}") from error
            if definition.key != directory.name:
                raise SkillRejected("Skill directory and immutable key differ")
            if definition.content_hash != semantic_hash(content):
                raise SkillRejected(f"Skill content hash mismatch: {definition.key}")
            if not definition.enabled:
                raise SkillRejected(f"Skill is disabled: {definition.key}")
            unknown = set(definition.stable_tool_sequence) - STABLE_TOOL_NAMES
            if unknown:
                raise SkillRejected(
                    f"Skill references unregistered stable-tool names: {sorted(unknown)}"
                )
            if definition.key in loaded:
                raise SkillRejected(f"duplicate Skill key: {definition.key}")
            loaded[definition.key] = definition
        if set(loaded) != {
            "database-connectivity-triage",
            "access-control-triage",
            "scheduled-report-triage",
        }:
            raise SkillRejected("Registry must contain exactly the OP-005 fixed Skill set")
        self._loaded = loaded
        return dict(loaded)

    def select(self, symptom: str, *, target_version: str) -> SkillDefinition:
        """Reject no-match and ambiguous-match symptoms instead of silently choosing a method."""
        normalized = symptom.casefold()
        matches = [
            definition
            for definition in self.load().values()
            if target_version in definition.applicable_versions
            and any(term.casefold() in normalized for term in definition.trigger_terms)
        ]
        if len(matches) != 1:
            raise SkillRejected("symptom does not select exactly one applicable fixed Skill")
        return matches[0]
