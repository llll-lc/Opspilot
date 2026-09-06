"""OP-005 unit coverage for source integrity, structures, fusion, and offline metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from opspilot.knowledge.chunking import chunk_markdown
from opspilot.knowledge.contracts import (
    Citation,
    EvaluationCase,
    KnowledgeSource,
    RetrievalResult,
    RetrievedContext,
)
from opspilot.knowledge.evaluation import score_case, serial_ablation
from opspilot.knowledge.manifest import load_frozen_cases, load_sources
from opspilot.knowledge.retrieval import ndcg_at_k, rrf_fuse

ROOT = Path(__file__).parents[1]


def source(content: str) -> KnowledgeSource:
    return KnowledgeSource(
        "unit-source",
        "Unit source",
        "SYNTHETIC",
        "local://unit",
        "PUBLIC",
        "Unit test",
        "Synthetic",
        datetime.now(UTC),
        ("6.1.0",),
        "test.md",
        content,
    )


def test_manifest_is_hashed_link_bounded_and_synthetic_is_labeled() -> None:
    sources = load_sources(ROOT)
    assert len(sources) == 8
    assert all(item.locator for item in sources)
    assert all(item.license_or_terms for item in sources)
    runbooks = [item for item in sources if item.source_type == "INTERNAL_RUNBOOK"]
    assert len(runbooks) == 3
    assert all("Synthetic OpsPilot" in item.content for item in runbooks)
    assert len(load_frozen_cases(ROOT)) == 12


def test_structure_chunking_never_hard_splits_code_table_or_steps() -> None:
    content = """# Main\n\n## Config\n\n```ini\nA_SETTING=value\nB_SETTING=value\n```\n\n## Steps\n\n1. First safe read.\n2. Second safe read.\n\n## Table\n\n| Scope | Check |\n| --- | --- |\n| APP | Read |\n"""
    chunks = chunk_markdown(source(content), max_child_characters=80)
    children = [item for item in chunks if item.chunk_kind == "CHILD"]
    assert any("A_SETTING=value\nB_SETTING=value" in item.content for item in children)
    assert any("1. First safe read.\n2. Second safe read." in item.content for item in children)
    assert any("| Scope | Check |\n| --- | --- |" in item.content for item in children)
    assert all(item.structure_path for item in chunks)
    assert all("start_line" in item.source_locator for item in chunks)


def test_oversized_indivisible_structure_unit_is_explicit_and_locatable() -> None:
    block = "\n".join(f"SETTING_{index}=value" for index in range(20))
    content = f"# Main\n\n```ini\n{block}\n```\n\nA short paragraph.\n"
    children = [
        item
        for item in chunk_markdown(source(content), max_child_characters=100)
        if item.chunk_kind == "CHILD"
    ]
    oversized = [
        item for item in children if item.retrieval_metadata.get("oversized_structure_unit")
    ]
    assert len(oversized) == 1
    item = oversized[0]
    assert item.structure_unit_type == "CODE_BLOCK"
    assert item.content == f"```ini\n{block}\n```"
    assert item.source_locator == {"start_line": 3, "end_line": 24}
    assert item.retrieval_metadata["configured_max_child_characters"] == 100
    assert item.retrieval_metadata["structure_unit_characters"] == len(item.content)


def test_rrf_deduplicates_and_retains_channels() -> None:
    first, second = uuid4(), uuid4()
    fused = rrf_fuse({"dense": [first, second], "sparse": [second, first], "exact": [first]})
    assert set(fused) == {first, second}
    assert fused[first][1] == ("dense", "sparse", "exact")
    assert fused[first][0] > fused[second][0]
    assert ndcg_at_k(("expected", "expected"), frozenset({"expected"}), 3) == 1.0


def test_evaluation_preserves_failure_and_uses_frozen_single_variable_variants() -> None:
    case = EvaluationCase(
        "case",
        "query",
        "6.1.0",
        frozenset({"SYNTHETIC"}),
        frozenset({"expected"}),
        True,
        "development",
    )
    context = RetrievedContext(
        Citation(
            uuid4(),
            uuid4(),
            uuid4(),
            "Title",
            "expected",
            "SYNTHETIC",
            ("6.1.0",),
            "local://unit",
            {"line": 1},
            "quote",
        ),
        "parent",
        1.0,
        ("dense",),
    )
    result = RetrievalResult(
        (context,),
        {"dense": 1},
        4.0,
        context.citation.retrieval_index_version_id,
        "NOT_REQUESTED",
    )
    assert result.retrieval_index_version_id == context.citation.retrieval_index_version_id
    assert score_case(case, result, k=3).hit_at_k

    def retrieve(_: EvaluationCase, variant: str) -> RetrievalResult:
        if variant == "hybrid":
            raise RuntimeError("record this failure")
        return result

    output = serial_ablation((case,), retrieve)
    assert output["hybrid"][0].failures == ("case",)
    assert output["dense"][0].recall_at_k == 1.0


def test_chunking_rejects_unusable_limit() -> None:
    with pytest.raises(ValueError, match="meaningful"):
        chunk_markdown(source("# Heading\n\ntext"), max_child_characters=1)
