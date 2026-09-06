"""Explicit local CLI for OP-005 ingestion plus four frozen RAG ablations.

This is not imported by the app. It creates only an OpsPilot-owned scoped corpus in
the DATABASE_URL selected by the operator and never touches the OP-003 control plane.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from opspilot.db.models import Organization, TargetSystem
from opspilot.db.session import create_database_engine
from opspilot.knowledge.contracts import RetrievalRequest
from opspilot.knowledge.evaluation import serial_ablation, write_report
from opspilot.knowledge.ingestion import KnowledgeIngestor
from opspilot.knowledge.manifest import load_frozen_cases, load_sources
from opspilot.knowledge.models import BgeM3Encoder, BgeRerankerLarge
from opspilot.knowledge.retrieval import RetrievalService


def repository_root() -> Path:
    return Path(__file__).parents[2]


def git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def worktree_metadata(root: Path) -> dict[str, object]:
    """Bind evidence to HEAD plus the exact dirty worktree, including untracked artifacts."""
    try:
        status = subprocess.check_output(
            ["git", "status", "--porcelain=v1"], cwd=root, text=True
        ).splitlines()
        diff = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=root)
    except (OSError, subprocess.CalledProcessError):
        return {"head_commit": git_commit(root), "available": False}
    changed_paths = tuple(line[3:] for line in status if len(line) >= 4)
    fingerprint = hashlib.sha256(diff)
    for line in status:
        if not line.startswith("?? "):
            continue
        path = root / line[3:]
        if path.is_file():
            fingerprint.update(line[3:].encode("utf-8"))
            fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
    return {
        "head_commit": git_commit(root),
        "is_dirty": bool(status),
        "changed_paths": changed_paths,
        "fingerprint_sha256": fingerprint.hexdigest(),
        "available": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=os.getenv("DATABASE_URL"))
    parser.add_argument(
        "--embedding-path", default=os.getenv("EMBEDDING_MODEL_PATH", r"D:\Agent\models\bge-m3")
    )
    parser.add_argument(
        "--reranker-path",
        default=os.getenv("RERANKER_MODEL_PATH", r"D:\Agent\models\bge-reranker-large"),
    )
    parser.add_argument(
        "--report", type=Path, default=Path("evidence/OP-005_RAG_ABLATION.local.json")
    )
    args = parser.parse_args()
    if not args.database_url:
        raise SystemExit(
            "DATABASE_URL or --database-url is required for the explicit OP-005 evaluation"
        )
    root = repository_root()
    encoder = BgeM3Encoder(args.embedding_path)
    reranker = BgeRerankerLarge(args.reranker_path)
    engine = create_database_engine(args.database_url)
    organization_id, target_id = uuid4(), uuid4()
    with Session(engine) as session:
        session.add(
            Organization(
                id=organization_id,
                slug=f"op005-eval-{organization_id.hex[:8]}",
                name="OP-005 evaluation",
            )
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
        index_id = KnowledgeIngestor(session, encoder).ingest(
            organization_id=organization_id,
            target_system_id=target_id,
            index_key="op005-frozen-corpus",
            index_version=1,
            sources=load_sources(root),
        )
        session.commit()
        service = RetrievalService(session, encoder, reranker)
        cases = load_frozen_cases(root)

        def retrieve(case, variant):
            return service.retrieve(
                RetrievalRequest(
                    organization_id,
                    target_id,
                    index_id,
                    case.target_version,
                    "PUBLIC",
                    case.source_types,
                    case.query,
                    3,
                    variant == "reranked",
                ),
                variant=variant,
            )

        results = serial_ablation(cases, retrieve)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    write_report(args.report, results)
    metadata_path = args.report.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "run_at": datetime.now(UTC).isoformat(),
                "worktree": worktree_metadata(root),
                "index_key": "op005-frozen-corpus",
                "retrieval_index_version_id": str(index_id),
                "source_manifest": "opspilot.knowledge-manifest.v1",
                "query_truth": "opspilot.rag-truth.v1",
                "dense_model": "BAAI/bge-m3",
                "reranker": "BAAI/bge-reranker-large",
                "cpu_serial": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    encoder.close()
    reranker.close()
    engine.dispose()


if __name__ == "__main__":
    main()
