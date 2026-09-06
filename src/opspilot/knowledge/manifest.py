"""Load and verify the checked-in, license-bounded OP-005 corpus manifest."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from opspilot.knowledge.contracts import EvaluationCase, KnowledgeSource
from opspilot.knowledge.hashing import sha256_text


class ManifestError(ValueError):
    """Raised when frozen corpus or query truth is malformed or has drifted."""


def load_sources(repository_root: Path) -> tuple[KnowledgeSource, ...]:
    manifest_path = repository_root / "knowledge" / "sources.json"
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "opspilot.knowledge-manifest.v1":
        raise ManifestError("unsupported knowledge manifest schema")
    sources: list[KnowledgeSource] = []
    for entry in raw["entries"]:
        path = repository_root / entry["local_path"]
        content = path.read_text(encoding="utf-8")
        if entry["content_hash"] != sha256_text(content):
            raise ManifestError(f"content hash mismatch: {entry['id']}")
        sources.append(
            KnowledgeSource(
                source_key=entry["id"],
                title=entry["title"],
                source_type=entry["source_type"],
                locator=entry["url"],
                visibility="PUBLIC",
                publisher=entry["publisher"],
                license_or_terms=entry["license_or_terms"],
                accessed_at=datetime.fromisoformat(entry["accessed_at"]).replace(tzinfo=UTC),
                target_versions=tuple(entry["target_versions"]),
                local_path=entry["local_path"],
                content=content,
            )
        )
    if len({source.source_key for source in sources}) != len(sources):
        raise ManifestError("knowledge source IDs must be unique")
    return tuple(sources)


def load_frozen_cases(repository_root: Path) -> tuple[EvaluationCase, ...]:
    path = repository_root / "knowledge" / "evaluation" / "frozen_queries.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != "opspilot.rag-truth.v1":
        raise ManifestError("unsupported frozen-query schema")
    cases = tuple(
        EvaluationCase(
            case_id=item["case_id"],
            query=item["query"],
            target_version=item["target_version"],
            source_types=frozenset(item["source_types"]),
            expected_source_keys=frozenset(item["expected_source_keys"]),
            requires_parent_context=item["requires_parent_context"],
            split=item["split"],
        )
        for item in raw["cases"]
    )
    if len({case.case_id for case in cases}) != len(cases):
        raise ManifestError("frozen query IDs must be unique")
    return cases
