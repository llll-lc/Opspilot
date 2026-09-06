"""Frozen-query RAG ablation metrics; no model is used to create or judge truth."""

from __future__ import annotations

import statistics
from collections.abc import Callable, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import cast

from opspilot.knowledge.contracts import (
    EvaluationCase,
    EvaluationCaseResult,
    EvaluationSummary,
    RetrievalResult,
)
from opspilot.knowledge.retrieval import ndcg_at_k


def score_case(case: EvaluationCase, result: RetrievalResult, *, k: int) -> EvaluationCaseResult:
    keys = tuple(context.citation.source_key for context in result.contexts)
    ranks = [index for index, key in enumerate(keys, start=1) if key in case.expected_source_keys]
    citation_valid = all(
        citation.locator
        and citation.source_locator
        and citation.target_versions
        and citation.retrieval_index_version_id == result.retrieval_index_version_id
        for citation in (context.citation for context in result.contexts)
    )
    return EvaluationCaseResult(
        case_id=case.case_id,
        ranked_source_keys=keys,
        hit_at_k=bool(ranks),
        reciprocal_rank=1 / ranks[0] if ranks else 0.0,
        ndcg=ndcg_at_k(keys, case.expected_source_keys, k),
        parent_context_hit=not case.requires_parent_context or bool(result.contexts),
        citation_valid=citation_valid,
        latency_ms=result.latency_ms,
        reranker_status=result.reranker_status,
        degradation_reason=result.degradation_reason,
    )


def percentile(values: Sequence[float], ratio: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * ratio
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] * (upper - position) + values[upper] * (position - lower)


def summarize(
    variant: str, observations: Sequence[EvaluationCaseResult], *, peak_rss_bytes: int | None = None
) -> EvaluationSummary:
    """Keep failures and small-sample denominators visible in every report."""
    count = len(observations)
    latencies = sorted(item.latency_ms for item in observations)
    failures = tuple(item.case_id for item in observations if item.failure is not None)
    denominator = count or 1
    return EvaluationSummary(
        variant=variant,
        case_count=count,
        recall_at_k=sum(item.hit_at_k for item in observations) / denominator,
        mrr=sum(item.reciprocal_rank for item in observations) / denominator,
        ndcg=sum(item.ndcg for item in observations) / denominator,
        parent_context_hit_rate=sum(item.parent_context_hit for item in observations) / denominator,
        citation_valid_rate=sum(item.citation_valid for item in observations) / denominator,
        p50_latency_ms=statistics.median(latencies) if latencies else 0.0,
        p95_latency_ms=percentile(latencies, 0.95),
        peak_rss_bytes=process_rss_bytes() if peak_rss_bytes is None else peak_rss_bytes,
        failures=failures,
    )


def process_rss_bytes() -> int:
    """Use psutil when installed; a missing optional observer never changes retrieval behavior."""
    try:
        import psutil  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return 0
    return cast(int, psutil.Process().memory_info().rss)


def serial_ablation(
    cases: Sequence[EvaluationCase],
    retrieve: Callable[[EvaluationCase, str], RetrievalResult],
    *,
    k: int = 3,
) -> dict[str, tuple[EvaluationSummary, tuple[EvaluationCaseResult, ...]]]:
    """Run four isolated variants serially on exactly the same frozen cases."""
    output: dict[str, tuple[EvaluationSummary, tuple[EvaluationCaseResult, ...]]] = {}
    for variant in ("dense", "dense_exact", "hybrid", "reranked"):
        observations: list[EvaluationCaseResult] = []
        peak_rss_bytes = process_rss_bytes()
        for case in cases:
            try:
                observations.append(score_case(case, retrieve(case, variant), k=k))
            except Exception as error:  # evaluation must retain rather than conceal a failed query
                observations.append(
                    EvaluationCaseResult(
                        case_id=case.case_id,
                        ranked_source_keys=(),
                        hit_at_k=False,
                        reciprocal_rank=0.0,
                        ndcg=0.0,
                        parent_context_hit=False,
                        citation_valid=False,
                        latency_ms=0.0,
                        failure=str(error),
                    )
                )
            peak_rss_bytes = max(peak_rss_bytes, process_rss_bytes())
        frozen = tuple(observations)
        output[variant] = (summarize(variant, frozen, peak_rss_bytes=peak_rss_bytes), frozen)
    return output


def write_report(
    path: Path, output: dict[str, tuple[EvaluationSummary, tuple[EvaluationCaseResult, ...]]]
) -> None:
    """Serialize summary and individual cases without raw source bodies or secrets."""
    import json

    payload = {
        variant: {"summary": asdict(summary), "cases": [asdict(case) for case in cases]}
        for variant, (summary, cases) in output.items()
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
