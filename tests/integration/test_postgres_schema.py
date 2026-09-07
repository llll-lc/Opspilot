"""Actual PostgreSQL/pgvector contract tests for migration 0001."""

from __future__ import annotations

import os
import uuid
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import Connection
from sqlalchemy.exc import IntegrityError

from opspilot.db.models import (
    AuditEvent,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    Organization,
    ProviderCatalogSnapshot,
    RetrievalIndexVersion,
    TargetSystem,
    ToolDefinition,
    ToolExecution,
    ToolProviderBinding,
)
from opspilot.db.session import create_database_engine

DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not DATABASE_URL, reason="DATABASE_URL is required"),
]
HASH_A = "a" * 64
HASH_B = "b" * 64


def execute_invalid(connection: Connection, statement: Any) -> None:
    """Assert one statement fails without aborting the surrounding test transaction."""
    savepoint: AbstractContextManager[Any] = connection.begin_nested()
    with pytest.raises(IntegrityError), savepoint:
        connection.execute(statement)


def seed_scope(connection: Connection) -> dict[str, uuid.UUID]:
    """Insert two isolated organizations and one fully versioned knowledge scope."""
    ids = {
        key: uuid.uuid4()
        for key in (
            "organization",
            "other_organization",
            "target",
            "other_target",
            "document",
            "document_version",
            "index_version",
            "parent",
            "child",
        )
    }
    connection.execute(
        sa.insert(Organization),
        [
            {"id": ids["organization"], "slug": f"org-{uuid.uuid4().hex}", "name": "Org A"},
            {
                "id": ids["other_organization"],
                "slug": f"org-{uuid.uuid4().hex}",
                "name": "Org B",
            },
        ],
    )
    connection.execute(
        sa.insert(TargetSystem),
        [
            {
                "id": ids["target"],
                "organization_id": ids["organization"],
                "system_key": "superset-primary",
                "system_type": "SUPERSET",
                "display_name": "Superset Primary",
                "version": "6.1.0",
            },
            {
                "id": ids["other_target"],
                "organization_id": ids["other_organization"],
                "system_key": "superset-other",
                "system_type": "SUPERSET",
                "display_name": "Superset Other",
                "version": "6.1.0",
            },
        ],
    )
    connection.execute(
        sa.insert(KnowledgeDocument).values(
            id=ids["document"],
            organization_id=ids["organization"],
            target_system_id=ids["target"],
            source_key=f"source-{uuid.uuid4().hex}",
            title="Synthetic runbook",
            source_type="SYNTHETIC",
            source_locator="data/runbook.md",
            visibility="ORGANIZATION",
        )
    )
    connection.execute(
        sa.insert(KnowledgeDocumentVersion).values(
            id=ids["document_version"],
            organization_id=ids["organization"],
            target_system_id=ids["target"],
            document_id=ids["document"],
            version=1,
            content_hash=HASH_A,
            acquisition_method="SYNTHETIC_FIXTURE",
            parser_version="fixture-v1",
        )
    )
    connection.execute(
        sa.insert(RetrievalIndexVersion).values(
            id=ids["index_version"],
            organization_id=ids["organization"],
            target_system_id=ids["target"],
            index_key=f"index-{uuid.uuid4().hex}",
            version=1,
            status="BUILDING",
            chunking_version="structure-v1",
            dense_model="bge-m3",
            dense_version="dense-v1",
            dense_dimensions=1024,
            sparse_model="bge-m3",
            sparse_version="sparse-v1",
            exact_match_version="exact-v1",
            configuration_hash=HASH_B,
        )
    )
    connection.execute(
        sa.insert(KnowledgeChunk).values(
            id=ids["parent"],
            organization_id=ids["organization"],
            target_system_id=ids["target"],
            document_version_id=ids["document_version"],
            retrieval_index_version_id=ids["index_version"],
            chunk_kind="PARENT",
            ordinal=0,
            structure_path=["Runbook", "Checks"],
            structure_unit_type="PROCEDURE",
            source_locator={"line": 1},
            safe_content="Parent context",
            content_hash=HASH_A,
            token_count=2,
            representation_status="NOT_APPLICABLE",
        )
    )
    return ids


def test_pgvector_parent_child_and_representation_versions() -> None:
    assert DATABASE_URL is not None
    engine = create_database_engine(DATABASE_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            ids = seed_scope(connection)
            extension_version = connection.scalar(
                sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
            vector_type = connection.scalar(
                sa.text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "WHERE a.attrelid = 'knowledge_chunks'::regclass "
                    "AND a.attname = 'dense_embedding'"
                )
            )
            ann_indexes = connection.scalar(
                sa.text(
                    "SELECT count(*) FROM pg_indexes WHERE schemaname = current_schema() "
                    "AND (lower(indexdef) LIKE '%hnsw%' OR lower(indexdef) LIKE '%ivfflat%')"
                )
            )

            assert extension_version == "0.8.6"
            assert vector_type == "vector(1024)"
            assert ann_indexes == 0

            connection.execute(
                sa.insert(KnowledgeChunk).values(
                    id=ids["child"],
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    document_version_id=ids["document_version"],
                    retrieval_index_version_id=ids["index_version"],
                    parent_chunk_id=ids["parent"],
                    chunk_kind="CHILD",
                    ordinal=1,
                    structure_path=["Runbook", "Checks"],
                    structure_unit_type="PROSE",
                    source_locator={"line": 2},
                    safe_content="Retrievable child",
                    content_hash=HASH_B,
                    token_count=2,
                    representation_status="READY",
                    dense_embedding=[0.0] * 1024,
                    sparse_weights={"connection": 1.0},
                    embedding_version="dense-v1",
                    sparse_version="sparse-v1",
                )
            )

            execute_invalid(
                connection,
                sa.update(KnowledgeDocumentVersion)
                .where(KnowledgeDocumentVersion.id == ids["document_version"])
                .values(content_hash=HASH_B),
            )
            execute_invalid(
                connection,
                sa.update(RetrievalIndexVersion)
                .where(RetrievalIndexVersion.id == ids["index_version"])
                .values(dense_version="dense-v2"),
            )

            execute_invalid(
                connection,
                sa.insert(KnowledgeChunk).values(
                    id=uuid.uuid4(),
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    document_version_id=ids["document_version"],
                    retrieval_index_version_id=ids["index_version"],
                    parent_chunk_id=ids["child"],
                    chunk_kind="CHILD",
                    ordinal=2,
                    structure_path=["Runbook"],
                    structure_unit_type="PROSE",
                    source_locator={"line": 3},
                    safe_content="Nested child is forbidden",
                    content_hash=HASH_A,
                    token_count=3,
                    representation_status="PENDING",
                ),
            )
            execute_invalid(
                connection,
                sa.insert(KnowledgeChunk).values(
                    id=uuid.uuid4(),
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    document_version_id=ids["document_version"],
                    retrieval_index_version_id=ids["index_version"],
                    parent_chunk_id=ids["parent"],
                    chunk_kind="CHILD",
                    ordinal=3,
                    structure_path=["Runbook"],
                    structure_unit_type="PROSE",
                    source_locator={"line": 4},
                    safe_content="Mixed representation versions",
                    content_hash=HASH_A,
                    token_count=3,
                    representation_status="READY",
                    dense_embedding=[0.0] * 1024,
                    sparse_weights={"connection": 1.0},
                    embedding_version="dense-v2",
                    sparse_version="sparse-v1",
                ),
            )
            execute_invalid(
                connection,
                sa.insert(KnowledgeChunk).values(
                    id=uuid.uuid4(),
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    document_version_id=ids["document_version"],
                    retrieval_index_version_id=ids["index_version"],
                    parent_chunk_id=ids["parent"],
                    chunk_kind="CHILD",
                    ordinal=4,
                    structure_path=["Runbook"],
                    structure_unit_type="PROSE",
                    source_locator={"line": 5},
                    safe_content="Invalid sparse lexical value",
                    content_hash=HASH_A,
                    token_count=3,
                    representation_status="READY",
                    dense_embedding=[0.0] * 1024,
                    sparse_weights={"connection": "not-a-weight"},
                    embedding_version="dense-v1",
                    sparse_version="sparse-v1",
                ),
            )
        finally:
            transaction.rollback()
    engine.dispose()


def test_provider_execution_audit_chain_rejects_cross_scope_binding() -> None:
    assert DATABASE_URL is not None
    engine = create_database_engine(DATABASE_URL)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            ids = seed_scope(connection)
            tool_id = uuid.uuid4()
            catalog_id = uuid.uuid4()
            binding_id = uuid.uuid4()
            execution_id = uuid.uuid4()
            now = datetime.now(UTC)

            connection.execute(
                sa.insert(ToolDefinition).values(
                    id=tool_id,
                    stable_name="op004_test_connector_health",
                    schema_version="1.0.0",
                    contract_hash=HASH_A,
                    business_semantics="Connector reachability only",
                    risk_level="READ_ONLY",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    authorization_policy_version="policy-v1",
                    enabled=False,
                )
            )
            connection.execute(
                sa.insert(ProviderCatalogSnapshot).values(
                    id=catalog_id,
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    provider_type="MCP",
                    endpoint_identifier="superset-mcp-primary",
                    catalog_hash=HASH_B,
                    observed_tools=[{"name": "health_check"}],
                    observed_at=now,
                )
            )
            connection.execute(
                sa.insert(ToolProviderBinding).values(
                    id=binding_id,
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    tool_definition_id=tool_id,
                    binding_key="superset-mcp-health",
                    version=1,
                    binding_hash=HASH_A,
                    provider_type="MCP",
                    priority=10,
                    endpoint_identifier="superset-mcp-primary",
                    upstream_tool_name="health_check",
                    catalog_hash=HASH_B,
                    input_transform_version="input-v1",
                    output_transform_version="output-v1",
                    health_scope="CONNECTOR",
                    enabled=False,
                )
            )
            execution_values = {
                "id": execution_id,
                "organization_id": ids["organization"],
                "target_system_id": ids["target"],
                "tool_definition_id": tool_id,
                "provider_binding_id": binding_id,
                "provider_catalog_snapshot_id": catalog_id,
                "stable_tool_name_snapshot": "op004_test_connector_health",
                "tool_schema_version_snapshot": "1.0.0",
                "provider_type_snapshot": "MCP",
                "binding_key_snapshot": "superset-mcp-health",
                "binding_version_snapshot": 1,
                "upstream_tool_name_snapshot": "health_check",
                "authorization_scope": {"organization_id": str(ids["organization"])},
                "request_summary": {},
                "response_summary": {"reachable": True},
                "status": "SUCCEEDED",
                "started_at": now,
                "finished_at": now,
                "retry_count": 0,
            }
            connection.execute(sa.insert(ToolExecution).values(**execution_values))
            connection.execute(
                sa.insert(AuditEvent).values(
                    id=uuid.uuid4(),
                    organization_id=ids["organization"],
                    target_system_id=ids["target"],
                    tool_execution_id=execution_id,
                    actor_type="SYSTEM",
                    actor_ref="op004-integration-test",
                    event_type="TOOL_EXECUTION_RECORDED",
                    entity_type="ToolExecution",
                    entity_id=str(execution_id),
                    payload_summary={"status": "SUCCEEDED"},
                    payload_hash=HASH_B,
                    occurred_at=now,
                )
            )
            assert (
                connection.scalar(
                    sa.select(sa.func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.organization_id == ids["organization"],
                        AuditEvent.target_system_id == ids["target"],
                    )
                )
                == 1
            )

            missing_catalog_snapshot_values = dict(execution_values)
            missing_catalog_snapshot_values.update(
                id=uuid.uuid4(), provider_catalog_snapshot_id=None
            )
            execute_invalid(
                connection, sa.insert(ToolExecution).values(**missing_catalog_snapshot_values)
            )

            execute_invalid(
                connection,
                sa.update(ToolProviderBinding)
                .where(ToolProviderBinding.id == binding_id)
                .values(upstream_tool_name="get_instance_info"),
            )
            execute_invalid(
                connection,
                sa.update(ProviderCatalogSnapshot)
                .where(ProviderCatalogSnapshot.id == catalog_id)
                .values(observed_tools=[{"name": "get_instance_info"}]),
            )
            execute_invalid(
                connection,
                sa.update(ToolExecution)
                .where(ToolExecution.id == execution_id)
                .values(response_summary={"reachable": False}),
            )
            execute_invalid(
                connection, sa.delete(ToolExecution).where(ToolExecution.id == execution_id)
            )
            execute_invalid(
                connection,
                sa.update(AuditEvent)
                .where(AuditEvent.tool_execution_id == execution_id)
                .values(payload_summary={"status": "rewritten"}),
            )
            execute_invalid(
                connection,
                sa.delete(AuditEvent).where(AuditEvent.tool_execution_id == execution_id),
            )

            invalid_values = dict(execution_values)
            invalid_values.update(
                id=uuid.uuid4(),
                organization_id=ids["other_organization"],
                target_system_id=ids["other_target"],
                provider_catalog_snapshot_id=None,
            )
            execute_invalid(connection, sa.insert(ToolExecution).values(**invalid_values))

            mismatched_snapshot_values = dict(execution_values)
            mismatched_snapshot_values.update(
                id=uuid.uuid4(), upstream_tool_name_snapshot="get_instance_info"
            )
            execute_invalid(
                connection, sa.insert(ToolExecution).values(**mismatched_snapshot_values)
            )

            other_tool_id = uuid.uuid4()
            connection.execute(
                sa.insert(ToolDefinition).values(
                    id=other_tool_id,
                    stable_name="op004_test_application_health",
                    schema_version="1.0.0",
                    contract_hash=HASH_B,
                    business_semantics="Application health only",
                    risk_level="READ_ONLY",
                    input_schema={"type": "object"},
                    output_schema={"type": "object"},
                    authorization_policy_version="policy-v1",
                    enabled=False,
                )
            )
            mismatched_tool_values = dict(execution_values)
            mismatched_tool_values.update(id=uuid.uuid4(), tool_definition_id=other_tool_id)
            execute_invalid(connection, sa.insert(ToolExecution).values(**mismatched_tool_values))
        finally:
            transaction.rollback()
    engine.dispose()
