"""Actual PostgreSQL/pgvector OP-005 ingestion and mandatory-filter retrieval test."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from opspilot.db.models import Organization, TargetSystem
from opspilot.db.session import create_database_engine
from opspilot.knowledge.contracts import Embedding, KnowledgeSource, RetrievalRequest
from opspilot.knowledge.ingestion import KnowledgeIngestor
from opspilot.knowledge.retrieval import RetrievalService

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required"),
]


class DeterministicEncoder:
    dense_version = "test-dense-v1"
    sparse_version = "test-sparse-v1"

    def encode(self, texts: Sequence[str]) -> tuple[Embedding, ...]:
        return tuple(
            Embedding(
                tuple(
                    1.0 if index == (sum(ord(char) for char in text) % 1024) else 0.0
                    for index in range(1024)
                ),
                {str(ord(char) % 31): 1.0 for char in text.casefold() if char.isalpha()},
                self.dense_version,
                self.sparse_version,
            )
            for text in texts
        )


class StaticReranker:
    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        del query
        return tuple(float(len(passages) - position) for position, _ in enumerate(passages))


class FailingReranker:
    def score(self, query: str, passages: Sequence[str]) -> tuple[float, ...]:
        del query, passages
        raise RuntimeError("model load failed")


def make_source(source_key: str, content: str, *, version: str = "6.1.0") -> KnowledgeSource:
    return KnowledgeSource(
        source_key,
        source_key,
        "SYNTHETIC",
        f"local://{source_key}",
        "PUBLIC",
        "OP-005 test",
        "Synthetic",
        datetime.now(UTC),
        (version,),
        f"{source_key}.md",
        content,
    )


def test_pgvector_ingestion_retrieval_and_scope_filter() -> None:
    assert DATABASE_URL is not None
    engine = create_database_engine(DATABASE_URL)
    organization_id, target_id = uuid4(), uuid4()
    with Session(engine) as session:
        session.add(
            Organization(id=organization_id, slug=f"op005-{organization_id.hex[:8]}", name="OP-005")
        )
        session.add(
            TargetSystem(
                id=target_id,
                organization_id=organization_id,
                system_key="superset-op005",
                system_type="SUPERSET",
                display_name="Superset OP-005",
                version="6.1.0",
            )
        )
        session.flush()
        encoder = DeterministicEncoder()
        index_id = KnowledgeIngestor(session, encoder).ingest(
            organization_id=organization_id,
            target_system_id=target_id,
            index_key="op005-integration",
            index_version=1,
            sources=(
                make_source(
                    "in-scope", "# Database\n\nAUTHENTICATION_FAILED requires scoped evidence."
                ),
                make_source(
                    "other-in-scope", "# Database\n\nAUTHENTICATION_FAILED secondary evidence."
                ),
                make_source(
                    "wrong-version", "# Database\n\nAUTHENTICATION_FAILED hidden.", version="5.0.0"
                ),
            ),
        )
        session.commit()
        request = RetrievalRequest(
            organization_id,
            target_id,
            index_id,
            "6.1.0",
            "PUBLIC",
            frozenset({"SYNTHETIC"}),
            "AUTHENTICATION_FAILED",
            3,
            reranker_enabled=False,
        )
        result = RetrievalService(session, encoder).retrieve(
            request,
            variant="hybrid",
        )
        assert {context.citation.source_key for context in result.contexts} == {
            "in-scope",
            "other-in-scope",
        }
        assert result.retrieval_index_version_id == index_id
        assert all(
            context.citation.retrieval_index_version_id == index_id for context in result.contexts
        )
        assert cast(int, result.contexts[0].citation.source_locator["start_line"]) >= 1
        assert result.contexts[0].parent_content

        # Each request field is mandatory: a value from another scope, an unavailable
        # visibility/source class, or a target version with no matching source must
        # never broaden this frozen corpus.
        scope_mismatches = (
            replace(request, organization_id=uuid4()),
            replace(request, target_system_id=uuid4()),
            replace(request, retrieval_index_version_id=uuid4()),
            replace(request, visibility="ORGANIZATION"),
            replace(request, source_types=frozenset({"OFFICIAL_DOC"})),
            replace(request, target_version="7.0.0"),
        )
        for mismatch in scope_mismatches:
            rejected = RetrievalService(session, encoder).retrieve(mismatch, variant="hybrid")
            assert rejected.contexts == ()

        hybrid_signature = tuple(
            (context.citation.child_chunk_id, context.score, context.channels)
            for context in result.contexts
        )
        disabled = RetrievalService(session, encoder, FailingReranker()).retrieve(
            request, variant="reranked"
        )
        assert disabled.reranker_status == "DISABLED"
        assert disabled.degradation_reason is None
        assert (
            tuple(
                (context.citation.child_chunk_id, context.score, context.channels)
                for context in disabled.contexts
            )
            == hybrid_signature
        )

        applied = RetrievalService(session, encoder, StaticReranker()).retrieve(
            replace(request, reranker_enabled=True), variant="reranked"
        )
        assert applied.reranker_status == "APPLIED"
        assert applied.degradation_reason is None
        assert all("reranker" in context.channels for context in applied.contexts)

        fallback = RetrievalService(session, encoder, FailingReranker()).retrieve(
            replace(request, reranker_enabled=True), variant="reranked"
        )
        assert fallback.reranker_status == "FALLBACK"
        assert fallback.degradation_reason == (
            "reranker RuntimeError: model load failed; returned hybrid RRF ranking"
        )
        assert (
            tuple(
                (context.citation.child_chunk_id, context.score, context.channels)
                for context in fallback.contexts
            )
            == hybrid_signature
        )
    engine.dispose()
