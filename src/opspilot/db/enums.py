"""Stable persisted enum values used by the OP-004 schema."""

from enum import StrEnum


class KnowledgeSourceType(StrEnum):
    OFFICIAL_DOC = "OFFICIAL_DOC"
    OFFICIAL_REPOSITORY = "OFFICIAL_REPOSITORY"
    PUBLIC_ISSUE = "PUBLIC_ISSUE"
    INTERNAL_RUNBOOK = "INTERNAL_RUNBOOK"
    SYNTHETIC = "SYNTHETIC"


class Visibility(StrEnum):
    ORGANIZATION = "ORGANIZATION"
    PUBLIC = "PUBLIC"


class RetrievalIndexStatus(StrEnum):
    BUILDING = "BUILDING"
    READY = "READY"
    FAILED = "FAILED"
    RETIRED = "RETIRED"


class ChunkKind(StrEnum):
    PARENT = "PARENT"
    CHILD = "CHILD"


class StructureUnitType(StrEnum):
    PROSE = "PROSE"
    CODE_BLOCK = "CODE_BLOCK"
    CONFIGURATION = "CONFIGURATION"
    TABLE = "TABLE"
    PROCEDURE = "PROCEDURE"
    HEADING = "HEADING"


class RepresentationStatus(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class ToolRiskLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    LOW_RISK_WRITE = "LOW_RISK_WRITE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    FORBIDDEN = "FORBIDDEN"


class ProviderType(StrEnum):
    MCP = "MCP"
    REST = "REST"
    PROBE = "PROBE"
    INTERNAL = "INTERNAL"


class HealthScope(StrEnum):
    CONNECTOR = "CONNECTOR"
    APPLICATION = "APPLICATION"
    RUNTIME_COMPONENT = "RUNTIME_COMPONENT"
    BUSINESS_JOB = "BUSINESS_JOB"


class ToolExecutionStatus(StrEnum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class AuditActorType(StrEnum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    AGENT = "AGENT"
