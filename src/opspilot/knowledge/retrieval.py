"""Metadata-first exact, Dense, Sparse, RRF, reranking, and parent-context retrieval."""

from __future__ import annotations

import math
import re
import time
from collections import defaultdict
from collections.abc import Iterable
from typing import Literal
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from opspilot.db.enums import ChunkKind, RepresentationStatus
from opspilot.db.models import KnowledgeChunk
from opspilot.knowledge.contracts import (
    Citation,
    RetrievalRequest,
    RetrievalResult,
    RetrievedContext,
)
from opspilot.knowledge.models import Encoder, Reranker

TERM = re.compile(r"[A-Za-z_][A-Za-z0-9_.:-]{2,}")


def query_terms(query: str) -> tuple[str, ...]:
    """Extract exact error/config/task-like tokens without trusting query metadata."""
    return tuple(dict.fromkeys(term.casefold() for term in TERM.findall(query)))


def rrf_fuse(
    rankings: dict[str, Iterable[UUID]], *, constant: int = 60
) -> dict[UUID, tuple[float, tuple[str, ...]]]:
    """Fuse ranked lists while retaining the channels that supplied each result."""
    scores: dict[UUID, float] = defaultdict(float)
    channels: dict[UUID, list[str]] = defaultdict(list)
    for channel, items in rankings.items():
        for rank, item in enumerate(items, start=1):
            scores[item] += 1 / (constant + rank)
            channels[item].append(channel)
    return {item: (score, tuple(channels[item])) for item, score in scores.items()}


class RetrievalService:
    """Small-corpus retrieval. Every database query begins with the mandatory scope."""

    def __init__(
        self, session: Session, encoder: Encoder, reranker: Reranker | None = None
    ) -> None:
        self._session = session
        self._encoder = encoder
        self._reranker = reranker

    @staticmethod
    def _base_statement(request: RetrievalRequest) -> sa.Select[tuple[KnowledgeChunk]]:
        return sa.select(KnowledgeChunk).where(
            KnowledgeChunk.organization_id == request.organization_id,
            KnowledgeChunk.target_system_id == request.target_system_id,
            KnowledgeChunk.retrieval_index_version_id == request.retrieval_index_version_id,
            KnowledgeChunk.chunk_kind == ChunkKind.CHILD,
            KnowledgeChunk.representation_status == RepresentationStatus.READY,
        )

    @staticmethod
    def _metadata_match(chunk: KnowledgeChunk, request: RetrievalRequest) -> bool:
        metadata = chunk.retrieval_metadata
        if metadata.get("visibility") != request.visibility:
            return False
        if metadata.get("source_type") not in request.source_types:
            return False
        versions = metadata.get("target_versions")
        return isinstance(versions, list) and request.target_version in versions

    def _eligible(self, request: RetrievalRequest) -> list[KnowledgeChunk]:
        rows = self._session.scalars(self._base_statement(request)).all()
        return [row for row in rows if self._metadata_match(row, request)]

    def retrieve(self, request: RetrievalRequest, *, variant: str = "reranked") -> RetrievalResult:
        """Retrieve only citations from the requested frozen scope and matching metadata."""
        if request.limit < 1:
            raise ValueError("retrieval limit must be positive")
        if variant not in {"dense", "dense_exact", "hybrid", "reranked"}:
            raise ValueError("unknown RAG ablation variant")
        started = time.perf_counter()
        query_embedding = self._encoder.encode([request.query])[0]
        eligible = self._eligible(request)
        if not eligible:
            no_result_status: Literal["NOT_REQUESTED", "DISABLED", "APPLIED", "FALLBACK"] = (
                "NOT_REQUESTED"
                if variant != "reranked"
                else "DISABLED"
                if not request.reranker_enabled
                else "FALLBACK"
                if self._reranker is None
                else "NOT_REQUESTED"
            )
            return RetrievalResult(
                (),
                {"eligible": 0},
                (time.perf_counter() - started) * 1000,
                request.retrieval_index_version_id,
                no_result_status,
                "reranker unavailable; no eligible hybrid candidates"
                if no_result_status == "FALLBACK"
                else None,
            )
        eligible_ids = {chunk.id for chunk in eligible}
        dense_rows = self._session.scalars(
            self._base_statement(request)
            .where(KnowledgeChunk.id.in_(eligible_ids))
            .order_by(KnowledgeChunk.dense_embedding.cosine_distance(list(query_embedding.dense)))
            .limit(max(request.limit * 8, 12))
        ).all()
        dense_ids = [row.id for row in dense_rows if row.id in eligible_ids]
        terms = query_terms(request.query)
        exact_ids = [
            chunk.id
            for chunk in eligible
            if any(term in chunk.safe_content.casefold() for term in terms)
        ]
        sparse_ids = [
            chunk.id
            for chunk in sorted(
                eligible,
                key=lambda item: (
                    -sum(
                        query_embedding.sparse.get(key, 0.0) * value
                        for key, value in (item.sparse_weights or {}).items()
                    )
                ),
            )
            if any(key in query_embedding.sparse for key in (chunk.sparse_weights or {}))
        ]
        rankings: dict[str, Iterable[UUID]] = {"dense": dense_ids}
        if variant in {"dense_exact", "hybrid", "reranked"}:
            rankings["exact"] = exact_ids
        if variant in {"hybrid", "reranked"}:
            rankings["sparse"] = sparse_ids
        fused = rrf_fuse(rankings)
        ranked = sorted(fused, key=lambda item: (-fused[item][0], str(item)))
        if variant == "dense":
            ranked = dense_ids
            fused = {item: (1 / (position + 1), ("dense",)) for position, item in enumerate(ranked)}
        reranker_status: Literal["NOT_REQUESTED", "DISABLED", "APPLIED", "FALLBACK"] = (
            "NOT_REQUESTED"
        )
        degradation_reason: str | None = None
        if variant == "reranked" and not request.reranker_enabled:
            reranker_status = "DISABLED"
        elif variant == "reranked" and self._reranker is None:
            reranker_status = "FALLBACK"
            degradation_reason = "reranker unavailable; returned hybrid RRF ranking"
        elif variant == "reranked":
            candidates = ranked[: max(request.limit * 4, 8)]
            by_id = {chunk.id: chunk for chunk in eligible}
            reranker = self._reranker
            if reranker is None:  # narrowed above; keep the load/score boundary explicit.
                raise AssertionError("reranker state changed during one retrieval")
            try:
                rerank_scores = reranker.score(
                    request.query, [by_id[item].safe_content for item in candidates]
                )
                if len(rerank_scores) != len(candidates):
                    raise ValueError("reranker returned a score count different from candidates")
            except Exception as error:
                # Loading and scoring are both on-demand in BGE reranking.  Neither
                # failure is allowed to manufacture a reranked result: retain the
                # pre-existing hybrid Dense+exact+Sparse/RRF order and scores.
                reranker_status = "FALLBACK"
                degradation_reason = (
                    f"reranker {type(error).__name__}: {error}; returned hybrid RRF ranking"
                )
            else:
                ranked = [
                    item
                    for _, item in sorted(
                        zip(rerank_scores, candidates, strict=True),
                        key=lambda pair: (-pair[0], str(pair[1])),
                    )
                ] + ranked[len(candidates) :]
                fused = {
                    item: (float(score), tuple((*fused[item][1], "reranker")))
                    for score, item in zip(rerank_scores, candidates, strict=True)
                } | {item: value for item, value in fused.items() if item not in candidates}
                reranker_status = "APPLIED"
        by_id = {chunk.id: chunk for chunk in eligible}
        selected: list[UUID] = []
        seen_parent_ids: set[UUID] = set()
        for child_id in ranked:
            parent_id = by_id[child_id].parent_chunk_id
            if parent_id is None or parent_id in seen_parent_ids:
                continue
            selected.append(child_id)
            seen_parent_ids.add(parent_id)
            if len(selected) == request.limit:
                break
        parent_ids = {by_id[item].parent_chunk_id for item in selected}
        parents = {
            parent.id: parent
            for parent in self._session.scalars(
                sa.select(KnowledgeChunk).where(KnowledgeChunk.id.in_(parent_ids))
            ).all()
        }
        contexts: list[RetrievedContext] = []
        for child_id in selected:
            child = by_id[child_id]
            if child.parent_chunk_id is None:
                continue
            parent = parents.get(child.parent_chunk_id)
            if parent is None:
                continue
            metadata = child.retrieval_metadata
            locator = str(metadata["locator"])
            source_locator: dict[str, object] = dict(child.source_locator)
            contexts.append(
                RetrievedContext(
                    citation=Citation(
                        child_chunk_id=child.id,
                        parent_chunk_id=parent.id,
                        retrieval_index_version_id=request.retrieval_index_version_id,
                        title=child.structure_path[-1]
                        if child.structure_path
                        else str(metadata["source_key"]),
                        source_key=str(metadata["source_key"]),
                        source_type=str(metadata["source_type"]),
                        target_versions=tuple(str(item) for item in metadata["target_versions"]),
                        locator=locator,
                        source_locator=source_locator,
                        quote=child.safe_content[:280],
                    ),
                    parent_content=parent.safe_content,
                    score=fused[child.id][0],
                    channels=fused[child.id][1],
                )
            )
        elapsed = (time.perf_counter() - started) * 1000
        return RetrievalResult(
            tuple(contexts),
            {key: len(tuple(values)) for key, values in rankings.items()}
            | {"eligible": len(eligible)},
            elapsed,
            request.retrieval_index_version_id,
            reranker_status,
            degradation_reason,
        )


def ndcg_at_k(ranked_source_keys: tuple[str, ...], expected: frozenset[str], k: int) -> float:
    """Binary relevance nDCG for frozen retrieval truth."""
    observed = 0.0
    seen: set[str] = set()
    for position, key in enumerate(ranked_source_keys[:k], start=1):
        if key in expected and key not in seen:
            observed += 1 / math.log2(position + 1)
            seen.add(key)
    ideal = sum(1 / math.log2(position + 1) for position in range(1, min(k, len(expected)) + 1))
    return observed / ideal if ideal else 0.0
