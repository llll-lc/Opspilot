"""Typed, side-effect-free contracts for the OP-005 knowledge boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

SourceType = Literal[
    "OFFICIAL_DOC", "OFFICIAL_REPOSITORY", "PUBLIC_ISSUE", "INTERNAL_RUNBOOK", "SYNTHETIC"
]
Visibility = Literal["PUBLIC", "ORGANIZATION"]
StructureType = Literal["PROSE", "CODE_BLOCK", "CONFIGURATION", "TABLE", "PROCEDURE", "HEADING"]


@dataclass(frozen=True)
class KnowledgeSource:
    """A locally stored, license-bounded source snapshot described by the manifest."""

    source_key: str
    title: str
    source_type: SourceType
    locator: str
    visibility: Visibility
    publisher: str
    license_or_terms: str
    accessed_at: datetime
    target_versions: tuple[str, ...]
    local_path: str
    content: str


@dataclass(frozen=True)
class ChunkDraft:
    """A parent context or retrievable child prior to persistence."""

    chunk_kind: Literal["PARENT", "CHILD"]
    parent_ordinal: int | None
    ordinal: int
    structure_path: tuple[str, ...]
    structure_unit_type: StructureType
    source_locator: dict[str, int | str]
    content: str
    retrieval_metadata: dict[str, object]


@dataclass(frozen=True)
class Embedding:
    """BGE-M3-derived single-vector and lexical sparse representation."""

    dense: tuple[float, ...]
    sparse: dict[str, float]
    dense_version: str
    sparse_version: str


@dataclass(frozen=True)
class RetrievalRequest:
    """All scope filters are required so callers cannot accidentally query globally."""

    organization_id: UUID
    target_system_id: UUID
    retrieval_index_version_id: UUID
    target_version: str
    visibility: Visibility
    source_types: frozenset[SourceType]
    query: str
    limit: int = 3
    reranker_enabled: bool = False


@dataclass(frozen=True)
class Citation:
    """A short citation that always points to a versioned source location."""

    child_chunk_id: UUID
    parent_chunk_id: UUID
    retrieval_index_version_id: UUID
    title: str
    source_key: str
    source_type: str
    target_versions: tuple[str, ...]
    locator: str
    source_locator: dict[str, object]
    quote: str


@dataclass(frozen=True)
class RetrievedContext:
    """One ranked child plus its full parent context and a localizable citation."""

    citation: Citation
    parent_content: str
    score: float
    channels: tuple[str, ...]


@dataclass(frozen=True)
class RetrievalResult:
    """A deterministic retrieval response; it makes no root-cause assertion."""

    contexts: tuple[RetrievedContext, ...]
    channel_counts: dict[str, int]
    latency_ms: float
    retrieval_index_version_id: UUID
    reranker_status: Literal["NOT_REQUESTED", "DISABLED", "APPLIED", "FALLBACK"]
    degradation_reason: str | None = None


@dataclass(frozen=True)
class EvaluationCase:
    """Frozen query truth. Source keys identify supporting documents, not a diagnosis."""

    case_id: str
    query: str
    target_version: str
    source_types: frozenset[SourceType]
    expected_source_keys: frozenset[str]
    requires_parent_context: bool
    split: Literal["development", "validation"]


@dataclass(frozen=True)
class EvaluationCaseResult:
    """One immutable evaluation observation for one ablation configuration."""

    case_id: str
    ranked_source_keys: tuple[str, ...]
    hit_at_k: bool
    reciprocal_rank: float
    ndcg: float
    parent_context_hit: bool
    citation_valid: bool
    latency_ms: float
    reranker_status: str = "NOT_REQUESTED"
    degradation_reason: str | None = None
    failure: str | None = None


@dataclass(frozen=True)
class EvaluationSummary:
    """Aggregate metrics retain the denominator and individual observations."""

    variant: str
    case_count: int
    recall_at_k: float
    mrr: float
    ndcg: float
    parent_context_hit_rate: float
    citation_valid_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    peak_rss_bytes: int
    failures: tuple[str, ...] = field(default_factory=tuple)
