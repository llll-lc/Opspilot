"""SQLAlchemy models for OP-004's deterministic L0 data foundation.

The module intentionally contains no repositories, ingestion, retrieval, provider calls,
authentication, tickets, or Agent behavior. Database constraints own the invariants that
later OPs must not delegate to a model.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from opspilot.db.base import Base
from opspilot.db.enums import (
    AuditActorType,
    ChunkKind,
    HealthScope,
    KnowledgeSourceType,
    ProviderType,
    RepresentationStatus,
    RetrievalIndexStatus,
    StructureUnitType,
    SupportCaseStatus,
    ToolExecutionStatus,
    ToolRiskLevel,
    UserRole,
    Visibility,
)

JSON_OBJECT_DEFAULT = text("'{}'::jsonb")
JSON_ARRAY_DEFAULT = text("'[]'::jsonb")
SHA256_CHECK = "^[0-9a-f]{64}$"


def enum_type(enum_class: type[Any], name: str) -> Enum:
    """Keep Python and PostgreSQL enum values identical and explicitly named."""
    return Enum(enum_class, name=name, native_enum=True, validate_strings=True)


class TimestampMixin:
    """UTC-aware creation/update timestamps shared by mutable registry records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class Organization(TimestampMixin, Base):
    """Top-level data and authorization boundary."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("slug = lower(slug)", name="slug_lowercase"),
        CheckConstraint("length(slug) >= 2", name="slug_length"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class TargetSystem(TimestampMixin, Base):
    """A supported software instance within one organization."""

    __tablename__ = "target_systems"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_target_systems_scope_id"),
        UniqueConstraint("organization_id", "system_key", name="uq_target_systems_scope_key"),
        CheckConstraint("system_key = lower(system_key)", name="system_key_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    system_key: Mapped[str] = mapped_column(String(100), nullable=False)
    system_type: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str | None] = mapped_column(String(100))
    configuration_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=JSON_OBJECT_DEFAULT
    )


class User(TimestampMixin, Base):
    """Authenticated human principal; roles and scopes are server-owned facts."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("subject", name="uq_users_subject"),
        UniqueConstraint("organization_id", "id", name="uq_users_organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[UserRole] = mapped_column(enum_type(UserRole, "user_role"), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class UserTargetScope(Base):
    """Explicit user-to-target grant; no request parameter may expand this scope."""

    __tablename__ = "user_target_scopes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_user_target_scopes_scope_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_user_target_scopes_scope_target",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id", "target_system_id", name="uq_user_target_scopes_user_target"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class TargetResource(TimestampMixin, Base):
    """A target-owned resource whose external identifier is never trusted by itself."""

    __tablename__ = "target_resources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_target_resources_scope_target",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "target_system_id", "id", name="uq_target_resources_scope_id"
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "resource_type",
            "external_id",
            name="uq_target_resources_external",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)


class UserResourceGrant(Base):
    """Optional least-privilege grant for an individual target resource."""

    __tablename__ = "user_resource_grants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "user_id"],
            ["users.organization_id", "users.id"],
            name="fk_user_resource_grants_scope_user",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "resource_id"],
            [
                "target_resources.organization_id",
                "target_resources.target_system_id",
                "target_resources.id",
            ],
            name="fk_user_resource_grants_scope_resource",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("user_id", "resource_id", name="uq_user_resource_grants_user_resource"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SupportCase(TimestampMixin, Base):
    """Durable L0 support case. Agent and approval concepts are intentionally absent."""

    __tablename__ = "support_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_support_cases_scope_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reporter_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_support_cases_scope_reporter",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "resource_id"],
            [
                "target_resources.organization_id",
                "target_resources.target_system_id",
                "target_resources.id",
            ],
            name="fk_support_cases_scope_resource",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_support_cases_organization_id"),
        UniqueConstraint(
            "organization_id", "deduplication_key", name="uq_support_cases_deduplication"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("ix_support_cases_scope_status", "organization_id", "target_system_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    reporter_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    symptom_code: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[SupportCaseStatus] = mapped_column(
        enum_type(SupportCaseStatus, "support_case_status"), nullable=False
    )
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class CaseMessage(Base):
    """Append-only human-visible timeline item; no model reasoning is stored here."""

    __tablename__ = "case_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "support_case_id"],
            ["support_cases.organization_id", "support_cases.id"],
            name="fk_case_messages_scope_case",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "author_user_id"],
            ["users.organization_id", "users.id"],
            name="fk_case_messages_scope_author",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "support_case_id", "id", name="uq_case_messages_scope_id"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    support_case_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    author_user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KnowledgeDocument(TimestampMixin, Base):
    """Stable source identity; content changes create KnowledgeDocumentVersion rows."""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_knowledge_documents_scope_target",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "target_system_id", "id", name="uq_knowledge_documents_scope_id"
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "source_key",
            name="uq_knowledge_documents_scope_source",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_key: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[KnowledgeSourceType] = mapped_column(
        enum_type(KnowledgeSourceType, "knowledge_source_type"), nullable=False
    )
    source_locator: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[Visibility] = mapped_column(
        enum_type(Visibility, "knowledge_visibility"), nullable=False
    )


class KnowledgeDocumentVersion(Base):
    """Immutable content/source snapshot used by historical citations."""

    __tablename__ = "knowledge_document_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "document_id"],
            [
                "knowledge_documents.organization_id",
                "knowledge_documents.target_system_id",
                "knowledge_documents.id",
            ],
            name="fk_knowledge_document_versions_scope_document",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "id",
            name="uq_knowledge_document_versions_scope_id",
        ),
        UniqueConstraint("document_id", "version", name="uq_knowledge_document_versions_version"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_sha256"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(200))
    license_or_terms: Mapped[str | None] = mapped_column(String(500))
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    target_versions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=JSON_ARRAY_DEFAULT
    )
    acquisition_method: Mapped[str] = mapped_column(String(100), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(100), nullable=False)
    object_key: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RetrievalIndexVersion(Base):
    """Frozen representation/chunking configuration for one retrieval corpus version."""

    __tablename__ = "retrieval_index_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_retrieval_index_versions_scope_target",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "id",
            name="uq_retrieval_index_versions_scope_id",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "index_key",
            "version",
            name="uq_retrieval_index_versions_key_version",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("dense_dimensions = 1024", name="dense_dimensions_1024"),
        CheckConstraint("configuration_hash ~ '^[0-9a-f]{64}$'", name="config_hash_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    index_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[RetrievalIndexStatus] = mapped_column(
        enum_type(RetrievalIndexStatus, "retrieval_index_status"), nullable=False
    )
    chunking_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dense_model: Mapped[str] = mapped_column(String(200), nullable=False)
    dense_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dense_dimensions: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1024)
    sparse_model: Mapped[str] = mapped_column(String(200), nullable=False)
    sparse_version: Mapped[str] = mapped_column(String(100), nullable=False)
    exact_match_version: Mapped[str] = mapped_column(String(100), nullable=False)
    fusion_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=JSON_OBJECT_DEFAULT
    )
    reranker_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=JSON_OBJECT_DEFAULT
    )
    configuration_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeChunk(Base):
    """Structure-aware context parent or retrievable child chunk."""

    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "document_version_id"],
            [
                "knowledge_document_versions.organization_id",
                "knowledge_document_versions.target_system_id",
                "knowledge_document_versions.id",
            ],
            name="fk_knowledge_chunks_scope_document_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "retrieval_index_version_id"],
            [
                "retrieval_index_versions.organization_id",
                "retrieval_index_versions.target_system_id",
                "retrieval_index_versions.id",
            ],
            name="fk_knowledge_chunks_scope_index_version",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "target_system_id",
                "document_version_id",
                "retrieval_index_version_id",
                "parent_chunk_id",
            ],
            [
                "knowledge_chunks.organization_id",
                "knowledge_chunks.target_system_id",
                "knowledge_chunks.document_version_id",
                "knowledge_chunks.retrieval_index_version_id",
                "knowledge_chunks.id",
            ],
            name="fk_knowledge_chunks_scope_parent",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "document_version_id",
            "retrieval_index_version_id",
            "id",
            name="uq_knowledge_chunks_scope_id",
        ),
        UniqueConstraint(
            "document_version_id",
            "retrieval_index_version_id",
            "ordinal",
            name="uq_knowledge_chunks_version_ordinal",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal_nonnegative"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_sha256"),
        CheckConstraint("token_count >= 0", name="token_count_nonnegative"),
        CheckConstraint(
            "(chunk_kind = 'PARENT' AND parent_chunk_id IS NULL "
            "AND representation_status = 'NOT_APPLICABLE' AND dense_embedding IS NULL "
            "AND sparse_weights IS NULL AND embedding_version IS NULL AND sparse_version IS NULL) "
            "OR (chunk_kind = 'CHILD' AND parent_chunk_id IS NOT NULL "
            "AND representation_status IN ('PENDING', 'READY', 'FAILED'))",
            name="parent_child_representation_shape",
        ),
        CheckConstraint(
            "representation_status <> 'READY' OR "
            "(dense_embedding IS NOT NULL AND sparse_weights IS NOT NULL "
            "AND embedding_version IS NOT NULL AND sparse_version IS NOT NULL)",
            name="ready_representation_complete",
        ),
        CheckConstraint(
            "sparse_weights IS NULL OR jsonb_typeof(sparse_weights) = 'object'",
            name="sparse_weights_object",
        ),
        Index(
            "ix_knowledge_chunks_retrieval_filter",
            "organization_id",
            "target_system_id",
            "retrieval_index_version_id",
            "chunk_kind",
            "representation_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    document_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    retrieval_index_version_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    chunk_kind: Mapped[ChunkKind] = mapped_column(
        enum_type(ChunkKind, "knowledge_chunk_kind"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    structure_path: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    structure_unit_type: Mapped[StructureUnitType] = mapped_column(
        enum_type(StructureUnitType, "structure_unit_type"), nullable=False
    )
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    safe_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    retrieval_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=JSON_OBJECT_DEFAULT
    )
    representation_status: Mapped[RepresentationStatus] = mapped_column(
        enum_type(RepresentationStatus, "representation_status"), nullable=False
    )
    dense_embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    sparse_weights: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    embedding_version: Mapped[str | None] = mapped_column(String(100))
    sparse_version: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ToolDefinition(TimestampMixin, Base):
    """Global, Provider-agnostic tool contract visible to future Agent/Skills."""

    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint("stable_name", "schema_version", name="uq_tool_definitions_contract"),
        CheckConstraint("stable_name = lower(stable_name)", name="stable_name_lowercase"),
        CheckConstraint("contract_hash ~ '^[0-9a-f]{64}$'", name="contract_hash_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stable_name: Mapped[str] = mapped_column(String(150), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    contract_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    business_semantics: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[ToolRiskLevel] = mapped_column(
        enum_type(ToolRiskLevel, "tool_risk_level"), nullable=False
    )
    input_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_policy_version: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ProviderCatalogSnapshot(Base):
    """Immutable observed Provider directory; observation never grants permission."""

    __tablename__ = "provider_catalog_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_provider_catalog_snapshots_scope_target",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "id",
            name="uq_provider_catalog_snapshots_scope_id",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "provider_type",
            "endpoint_identifier",
            "catalog_hash",
            name="uq_provider_catalog_snapshots_observation",
        ),
        CheckConstraint("catalog_hash ~ '^[0-9a-f]{64}$'", name="catalog_hash_sha256"),
        CheckConstraint("jsonb_typeof(observed_tools) = 'array'", name="observed_tools_array"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        enum_type(ProviderType, "provider_type"), nullable=False
    )
    endpoint_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    catalog_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(200))


class ToolProviderBinding(TimestampMixin, Base):
    """Versioned mapping; only its enabled lifecycle flag may change in place."""

    __tablename__ = "tool_provider_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_tool_provider_bindings_scope_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "fallback_binding_id"],
            [
                "tool_provider_bindings.organization_id",
                "tool_provider_bindings.target_system_id",
                "tool_provider_bindings.id",
            ],
            name="fk_tool_provider_bindings_scope_fallback",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "id",
            name="uq_tool_provider_bindings_scope_id",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "id",
            "tool_definition_id",
            name="uq_tool_provider_bindings_scope_tool",
        ),
        UniqueConstraint(
            "organization_id",
            "target_system_id",
            "tool_definition_id",
            "binding_key",
            "version",
            name="uq_tool_provider_bindings_version",
        ),
        CheckConstraint("priority >= 0", name="priority_nonnegative"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("binding_hash ~ '^[0-9a-f]{64}$'", name="binding_hash_sha256"),
        CheckConstraint(
            "catalog_hash IS NULL OR catalog_hash ~ '^[0-9a-f]{64}$'",
            name="catalog_hash_sha256",
        ),
        CheckConstraint(
            "provider_type <> 'MCP' OR catalog_hash IS NOT NULL",
            name="mcp_catalog_hash_required",
        ),
        Index(
            "ix_tool_provider_bindings_resolution",
            "organization_id",
            "target_system_id",
            "tool_definition_id",
            "priority",
            postgresql_where=text("enabled"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tool_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    fallback_binding_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    binding_key: Mapped[str] = mapped_column(String(150), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    binding_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        enum_type(ProviderType, "provider_type"), nullable=False
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    endpoint_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    upstream_tool_name: Mapped[str] = mapped_column(String(200), nullable=False)
    catalog_hash: Mapped[str | None] = mapped_column(String(64))
    input_transform_version: Mapped[str] = mapped_column(String(100), nullable=False)
    output_transform_version: Mapped[str] = mapped_column(String(100), nullable=False)
    health_scope: Mapped[HealthScope] = mapped_column(
        enum_type(HealthScope, "health_scope"), nullable=False
    )
    health_condition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=JSON_OBJECT_DEFAULT
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ToolExecution(Base):
    """Append-only snapshot of a stable tool attempt and the selected Provider binding."""

    __tablename__ = "tool_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_tool_executions_scope_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            [
                "organization_id",
                "target_system_id",
                "provider_binding_id",
                "tool_definition_id",
            ],
            [
                "tool_provider_bindings.organization_id",
                "tool_provider_bindings.target_system_id",
                "tool_provider_bindings.id",
                "tool_provider_bindings.tool_definition_id",
            ],
            name="fk_tool_executions_scope_binding",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "provider_catalog_snapshot_id"],
            [
                "provider_catalog_snapshots.organization_id",
                "provider_catalog_snapshots.target_system_id",
                "provider_catalog_snapshots.id",
            ],
            name="fk_tool_executions_scope_catalog",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "target_system_id", "id", name="uq_tool_executions_scope_id"
        ),
        CheckConstraint("retry_count >= 0", name="retry_count_nonnegative"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at", name="finished_after_started"
        ),
        Index(
            "ix_tool_executions_scope_started",
            "organization_id",
            "target_system_id",
            "started_at",
        ),
        Index(
            "uq_tool_executions_idempotency",
            "organization_id",
            "stable_tool_name_snapshot",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tool_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    provider_binding_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    provider_catalog_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    stable_tool_name_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    tool_schema_version_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_type_snapshot: Mapped[ProviderType] = mapped_column(
        enum_type(ProviderType, "provider_type"), nullable=False
    )
    binding_key_snapshot: Mapped[str] = mapped_column(String(150), nullable=False)
    binding_version_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    upstream_tool_name_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    request_correlation_id: Mapped[str | None] = mapped_column(String(200))
    fallback_reason: Mapped[str | None] = mapped_column(String(500))
    authorization_scope: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    request_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ToolExecutionStatus] = mapped_column(
        enum_type(ToolExecutionStatus, "tool_execution_status"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))


class AuditEvent(Base):
    """Append-only, human-explainable event associated with a tool execution when relevant."""

    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "target_system_id"],
            ["target_systems.organization_id", "target_systems.id"],
            name="fk_audit_events_scope_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "target_system_id", "tool_execution_id"],
            [
                "tool_executions.organization_id",
                "tool_executions.target_system_id",
                "tool_executions.id",
            ],
            name="fk_audit_events_scope_tool_execution",
            ondelete="RESTRICT",
        ),
        CheckConstraint("payload_hash ~ '^[0-9a-f]{64}$'", name="payload_hash_sha256"),
        Index(
            "ix_audit_events_scope_occurred",
            "organization_id",
            "target_system_id",
            "occurred_at",
        ),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    target_system_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    tool_execution_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_type: Mapped[AuditActorType] = mapped_column(
        enum_type(AuditActorType, "audit_actor_type"), nullable=False
    )
    actor_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(200), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(200))
    payload_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


ALL_MODELS = (
    Organization,
    TargetSystem,
    User,
    UserTargetScope,
    TargetResource,
    UserResourceGrant,
    SupportCase,
    CaseMessage,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    RetrievalIndexVersion,
    KnowledgeChunk,
    ToolDefinition,
    ProviderCatalogSnapshot,
    ToolProviderBinding,
    ToolExecution,
    AuditEvent,
)

__all__ = [model.__name__ for model in ALL_MODELS]
