"""Transactional ingestion into the immutable OP-004 knowledge contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from opspilot.db.enums import ChunkKind, RepresentationStatus, RetrievalIndexStatus
from opspilot.db.models import (
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    RetrievalIndexVersion,
)
from opspilot.knowledge.chunking import chunk_markdown
from opspilot.knowledge.contracts import KnowledgeSource
from opspilot.knowledge.hashing import canonical_hash, sha256_text
from opspilot.knowledge.models import Encoder


class KnowledgeIngestor:
    """Build one frozen index version in a caller-owned transaction."""

    def __init__(self, session: Session, encoder: Encoder) -> None:
        self._session = session
        self._encoder = encoder

    def ingest(
        self,
        *,
        organization_id: UUID,
        target_system_id: UUID,
        index_key: str,
        index_version: int,
        sources: tuple[KnowledgeSource, ...],
        chunking_version: str = "markdown-structure-parent-child-v1",
    ) -> UUID:
        """Persist documents and chunks, then transition the newly created index to READY."""
        configuration = {
            "chunking_version": chunking_version,
            "dense_model": "BAAI/bge-m3",
            "dense_version": self._encoder.dense_version,
            "dense_dimensions": 1024,
            "sparse_model": "BAAI/bge-m3",
            "sparse_version": self._encoder.sparse_version,
            "exact_match_version": "error-config-task-token-v1",
            "fusion": {"method": "rrf", "k": 60},
            "reranker": {"model": "BAAI/bge-reranker-large", "default_enabled": False},
        }
        existing = self._session.scalar(
            sa.select(RetrievalIndexVersion.id).where(
                RetrievalIndexVersion.organization_id == organization_id,
                RetrievalIndexVersion.target_system_id == target_system_id,
                RetrievalIndexVersion.index_key == index_key,
                RetrievalIndexVersion.version == index_version,
            )
        )
        if existing is not None:
            raise ValueError("retrieval index version already exists and is immutable")
        index_id = uuid4()
        self._session.add(
            RetrievalIndexVersion(
                id=index_id,
                organization_id=organization_id,
                target_system_id=target_system_id,
                index_key=index_key,
                version=index_version,
                status=RetrievalIndexStatus.BUILDING,
                chunking_version=chunking_version,
                dense_model="BAAI/bge-m3",
                dense_version=self._encoder.dense_version,
                dense_dimensions=1024,
                sparse_model="BAAI/bge-m3",
                sparse_version=self._encoder.sparse_version,
                exact_match_version="error-config-task-token-v1",
                fusion_configuration=configuration["fusion"],
                reranker_configuration=configuration["reranker"],
                configuration_hash=canonical_hash(configuration),
            )
        )
        for source in sources:
            self._persist_source(organization_id, target_system_id, index_id, source)
        self._session.flush()
        index = self._session.get(RetrievalIndexVersion, index_id)
        if index is None:
            raise RuntimeError("new retrieval index vanished before finalization")
        index.status = RetrievalIndexStatus.READY
        index.completed_at = datetime.now(UTC)
        self._session.flush()
        return index_id

    def _persist_source(
        self, organization_id: UUID, target_system_id: UUID, index_id: UUID, source: KnowledgeSource
    ) -> None:
        document = self._session.scalar(
            sa.select(KnowledgeDocument).where(
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.target_system_id == target_system_id,
                KnowledgeDocument.source_key == source.source_key,
            )
        )
        if document is None:
            document = KnowledgeDocument(
                id=uuid4(),
                organization_id=organization_id,
                target_system_id=target_system_id,
                source_key=source.source_key,
                title=source.title,
                source_type=source.source_type,
                source_locator=source.locator,
                visibility=source.visibility,
            )
            self._session.add(document)
            self._session.flush()
        current = self._session.scalar(
            sa.select(sa.func.coalesce(sa.func.max(KnowledgeDocumentVersion.version), 0)).where(
                KnowledgeDocumentVersion.document_id == document.id
            )
        )
        document_version_id = uuid4()
        self._session.add(
            KnowledgeDocumentVersion(
                id=document_version_id,
                organization_id=organization_id,
                target_system_id=target_system_id,
                document_id=document.id,
                version=int(current or 0) + 1,
                content_hash=sha256_text(source.content),
                publisher=source.publisher,
                license_or_terms=source.license_or_terms,
                accessed_at=source.accessed_at,
                target_versions=list(source.target_versions),
                acquisition_method="LOCAL_LICENSE_BOUNDED_SNAPSHOT",
                parser_version="op005-manifest-markdown-v1",
                object_key=source.local_path,
            )
        )
        self._session.flush()
        drafts = chunk_markdown(source)
        parent_ids: dict[int, UUID] = {}
        child_drafts = [draft for draft in drafts if draft.chunk_kind == "CHILD"]
        representations = iter(self._encoder.encode([draft.content for draft in child_drafts]))
        for draft in drafts:
            chunk_id = uuid4()
            if draft.chunk_kind == "PARENT":
                parent_ids[len(parent_ids)] = chunk_id
                self._session.add(
                    KnowledgeChunk(
                        id=chunk_id,
                        organization_id=organization_id,
                        target_system_id=target_system_id,
                        document_version_id=document_version_id,
                        retrieval_index_version_id=index_id,
                        chunk_kind=ChunkKind.PARENT,
                        ordinal=draft.ordinal,
                        structure_path=list(draft.structure_path),
                        structure_unit_type=draft.structure_unit_type,
                        source_locator=draft.source_locator,
                        safe_content=draft.content,
                        content_hash=sha256_text(draft.content),
                        token_count=len(draft.content.split()),
                        retrieval_metadata=draft.retrieval_metadata,
                        representation_status=RepresentationStatus.NOT_APPLICABLE,
                    )
                )
                continue
            if draft.parent_ordinal is None:
                raise RuntimeError("child chunk lacks parent ordinal")
            representation = next(representations)
            self._session.add(
                KnowledgeChunk(
                    id=chunk_id,
                    organization_id=organization_id,
                    target_system_id=target_system_id,
                    document_version_id=document_version_id,
                    retrieval_index_version_id=index_id,
                    parent_chunk_id=parent_ids[draft.parent_ordinal],
                    chunk_kind=ChunkKind.CHILD,
                    ordinal=draft.ordinal,
                    structure_path=list(draft.structure_path),
                    structure_unit_type=draft.structure_unit_type,
                    source_locator=draft.source_locator,
                    safe_content=draft.content,
                    content_hash=sha256_text(draft.content),
                    token_count=len(draft.content.split()),
                    retrieval_metadata=draft.retrieval_metadata,
                    representation_status=RepresentationStatus.READY,
                    dense_embedding=list(representation.dense),
                    sparse_weights=representation.sparse,
                    embedding_version=representation.dense_version,
                    sparse_version=representation.sparse_version,
                )
            )
