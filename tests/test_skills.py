"""Regression tests for fixed Skill hash, matching, disablement, and tool boundaries."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from opspilot.skills.registry import FixedSkillRegistry, SkillRejected, semantic_hash

ROOT = Path(__file__).parents[1]


def rewrite_skill_metadata(path: Path, update: dict[str, object]) -> None:
    """Apply a valid semantic edit so registry validation reaches the intended guard."""
    _, remainder = path.read_text(encoding="utf-8").split("---\n", 1)
    raw, body = remainder.split("\n---\n", 1)
    metadata = json.loads(raw)
    metadata.update(update)
    metadata["content_hash"] = "0" * 64
    provisional = f"---\n{json.dumps(metadata, ensure_ascii=False)}\n---\n{body}"
    metadata["content_hash"] = semantic_hash(provisional)
    path.write_text(
        f"---\n{json.dumps(metadata, ensure_ascii=False)}\n---\n{body}", encoding="utf-8"
    )


def test_fixed_registry_loads_three_hashed_skills_and_selects_one() -> None:
    registry = FixedSkillRegistry(ROOT / "skills", enabled=True)
    loaded = registry.load()
    assert set(loaded) == {
        "database-connectivity-triage",
        "access-control-triage",
        "scheduled-report-triage",
    }
    assert (
        registry.select("database connection timeout", target_version="6.1.0").key
        == "database-connectivity-triage"
    )
    assert (
        registry.select("permission denied dataset access", target_version="6.1.0").key
        == "access-control-triage"
    )
    assert (
        registry.select("scheduled report not sent", target_version="6.1.0").key
        == "scheduled-report-triage"
    )


def test_disabled_tampered_and_wrong_match_skills_are_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "skills"
    shutil.copytree(ROOT / "skills", copied)
    with pytest.raises(SkillRejected, match="disabled"):
        FixedSkillRegistry(copied, enabled=False).load()

    path = copied / "database-connectivity-triage" / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nInjected text", encoding="utf-8")
    with pytest.raises(SkillRejected, match="hash mismatch"):
        FixedSkillRegistry(copied, enabled=True).load()

    with pytest.raises(SkillRejected, match="exactly one"):
        FixedSkillRegistry(ROOT / "skills", enabled=True).select(
            "restart redis immediately", target_version="6.1.0"
        )


def test_unregistered_tool_and_wrong_version_or_trigger_are_rejected(tmp_path: Path) -> None:
    copied = tmp_path / "skills"
    shutil.copytree(ROOT / "skills", copied)
    path = copied / "database-connectivity-triage" / "SKILL.md"
    rewrite_skill_metadata(
        path,
        {
            "stable_tool_sequence": [
                "get_target_application_health",
                "unregistered_stable_tool",
            ]
        },
    )
    with pytest.raises(SkillRejected, match="unregistered"):
        FixedSkillRegistry(copied, enabled=True).load()

    registry = FixedSkillRegistry(ROOT / "skills", enabled=True)
    with pytest.raises(SkillRejected, match="exactly one"):
        registry.select("database connection timeout", target_version="5.0.0")
    with pytest.raises(SkillRejected, match="exactly one"):
        registry.select("unrelated cache eviction", target_version="6.1.0")


def test_all_fixed_skills_define_stop_escalate_and_prohibited_action_boundaries() -> None:
    loaded = FixedSkillRegistry(ROOT / "skills", enabled=True).load()
    expected = {
        "database-connectivity-triage": {
            "stop": "credential change",
            "prohibited": "No SQL execution.",
        },
        "access-control-triage": {
            "stop": "role or permission",
            "prohibited": "No role grant or revoke.",
        },
        "scheduled-report-triage": {
            "stop": "worker restart",
            "prohibited": "No report rerun.",
        },
    }
    for key, boundaries in expected.items():
        definition = loaded[key]
        assert definition.stop_or_escalate
        assert definition.prohibited_actions
        assert any(boundaries["stop"] in item for item in definition.stop_or_escalate)
        assert boundaries["prohibited"] in definition.prohibited_actions
