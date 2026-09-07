"""Fast structural tests for the OP-004 metadata boundary."""

from typing import Protocol, cast

from sqlalchemy import Enum, ForeignKeyConstraint, Table
from sqlalchemy.orm import Session

from opspilot.db.base import Base
from opspilot.db.models import ALL_MODELS, KnowledgeChunk
from opspilot.db.session import create_database_engine, create_session_factory


class VectorType(Protocol):
    dim: int


def test_expected_l0_tables_are_registered_without_connecting() -> None:
    assert set(Base.metadata.tables) == {
        "audit_events",
        "case_messages",
        "knowledge_chunks",
        "knowledge_document_versions",
        "knowledge_documents",
        "organizations",
        "provider_catalog_snapshots",
        "retrieval_index_versions",
        "target_systems",
        "target_resources",
        "tool_definitions",
        "tool_executions",
        "tool_provider_bindings",
        "support_cases",
        "user_resource_grants",
        "user_target_scopes",
        "users",
    }
    assert {model.__tablename__ for model in ALL_MODELS} == set(Base.metadata.tables)


def test_chunk_metadata_preserves_parent_child_and_exact_vector_contract() -> None:
    table = cast(Table, KnowledgeChunk.__table__)
    dense_type = cast(VectorType, table.c.dense_embedding.type)

    assert dense_type.dim == 1024
    assert isinstance(table.c.chunk_kind.type, Enum)
    assert table.c.chunk_kind.type.name == "knowledge_chunk_kind"
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.name == "fk_knowledge_chunks_scope_parent"
        for constraint in table.constraints
    )
    assert "ix_knowledge_chunks_retrieval_filter" in {index.name for index in table.indexes}
    assert not any(
        token in (index.name or "").lower()
        for index in table.indexes
        for token in ("hnsw", "ivfflat")
    )


def test_provider_audit_tables_keep_stable_and_upstream_names_separate() -> None:
    definitions = Base.metadata.tables["tool_definitions"]
    bindings = Base.metadata.tables["tool_provider_bindings"]
    executions = Base.metadata.tables["tool_executions"]

    assert "stable_name" in definitions.c
    assert "upstream_tool_name" not in definitions.c
    assert "upstream_tool_name" in bindings.c
    assert {
        "stable_tool_name_snapshot",
        "provider_type_snapshot",
        "binding_version_snapshot",
        "upstream_tool_name_snapshot",
        "authorization_scope",
        "fallback_reason",
    } <= set(executions.c.keys())


def test_engine_and_session_factories_are_explicit_and_lazy() -> None:
    engine = create_database_engine("postgresql+psycopg://local:local@127.0.0.1:1/local")
    factory = create_session_factory(engine)
    session = factory()

    assert isinstance(session, Session)

    session.close()
    engine.dispose()
