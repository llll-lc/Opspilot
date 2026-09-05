"""Guard the intentionally small OP-004 infrastructure and migration surface."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_compose_contains_only_the_pinned_opspilot_database() -> None:
    compose = (ROOT / "compose.yml").read_text(encoding="utf-8")

    assert "pgvector/pgvector:0.8.6-pg17-bookworm" in compose
    assert "127.0.0.1:${OPSPILOT_POSTGRES_PORT:-55432}:5432" in compose
    assert 'profiles: ["core"]' in compose
    assert "docker.sock" not in compose
    assert "superset" not in compose.lower()
    assert "redis:" not in compose.lower()
    assert "minio" not in compose.lower()


def test_initial_migration_has_vector_and_integrity_guards_but_no_ann_index() -> None:
    migration = (ROOT / "migrations" / "versions" / "0001_create_core_domain_schema.py").read_text(
        encoding="utf-8"
    )

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "Vector(1024)" in migration
    assert "validate_knowledge_chunk_scope_and_versions" in migration
    assert "validate_tool_execution_snapshot" in migration
    assert "selected provider binding requires its catalog snapshot" in migration
    assert "validate_retrieval_index_version_lifecycle" in migration
    assert "validate_versioned_contract_lifecycle" in migration
    assert "trg_tool_executions_append_only" in migration
    assert "trg_audit_events_append_only" in migration
    assert "hnsw" not in migration.lower()
    assert "ivfflat" not in migration.lower()
    assert "labs.op003" not in migration
