"""Provider-agnostic stable Tool Gateway with per-attempt append-only audit."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import sqlalchemy as sa
from sqlalchemy.orm import Session

from opspilot.db.enums import AuditActorType, HealthScope, ProviderType, ToolExecutionStatus
from opspilot.db.models import (
    AuditEvent,
    ProviderCatalogSnapshot,
    TargetResource,
    ToolDefinition,
    ToolExecution,
    ToolProviderBinding,
)
from opspilot.providers.runtime import ProviderFailure
from opspilot.support.services import AuthorizationContext, AuthorizationDenied, require_scope
from opspilot.tools.contracts import (
    MCP_ALLOWLIST,
    STABLE_TOOL_CONTRACTS,
    validate_input,
    validate_output,
)

MAX_RESPONSE_BYTES = 32_768
MAX_SUMMARY_DEPTH = 6
MAX_SUMMARY_ITEMS = 50
REDACTED_KEYS = ("password", "secret", "token", "cookie", "authorization", "credential")
REJECTION_TOOL_NAME = "gateway_rejected_call"


class GatewayRejected(ValueError):
    """A stable contract, authorization, or deterministic policy rejected the call."""


class ProviderUnavailable(RuntimeError):
    """All eligible Providers failed; their attempts remain audited."""


class ProviderClient(Protocol):
    def invoke(
        self, upstream_tool_name: str, arguments: dict[str, object]
    ) -> dict[str, object]: ...


class CatalogAwareProvider(ProviderClient, Protocol):
    def catalog_hash(self) -> str: ...


@dataclass(frozen=True)
class GatewayResult:
    stable_name: str
    health_scope: HealthScope
    payload: dict[str, Any]
    provider_type: ProviderType
    execution_id: uuid.UUID
    degraded_chain: tuple[str, ...]


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _safe(value: object, *, depth: int = 0) -> object:
    if depth >= MAX_SUMMARY_DEPTH:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, item in list(value.items())[:MAX_SUMMARY_ITEMS]:
            normalized = str(key)[:100]
            result[normalized] = (
                "[REDACTED]"
                if any(secret in normalized.lower() for secret in REDACTED_KEYS)
                else _safe(item, depth=depth + 1)
            )
        return result
    if isinstance(value, list):
        return [_safe(item, depth=depth + 1) for item in value[:MAX_SUMMARY_ITEMS]]
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return str(value)[:500]


class ToolGateway:
    def __init__(
        self,
        session: Session,
        clients: dict[ProviderType, ProviderClient],
        *,
        mcp_enabled: bool = False,
    ) -> None:
        self.session = session
        self.clients = clients
        self.mcp_enabled = mcp_enabled

    def invoke(
        self,
        context: AuthorizationContext,
        stable_name: str,
        target_system_id: uuid.UUID,
        arguments: dict[str, object],
        *,
        idempotency_key: str | None = None,
    ) -> GatewayResult:
        group_id = str(uuid.uuid4())
        audit_target = self._audit_target(context, target_system_id)
        if stable_name not in STABLE_TOOL_CONTRACTS:
            self._record_rejection(
                context, audit_target, group_id, "UNKNOWN_STABLE_TOOL", stable_name, arguments
            )
            raise GatewayRejected("unknown or forbidden stable tool")
        contract = STABLE_TOOL_CONTRACTS[stable_name]
        try:
            parsed_input = validate_input(stable_name, arguments)
            provider_arguments = self._authorize_and_transform_input(
                context, target_system_id, contract.resource_type, parsed_input
            )
        except (ValueError, AuthorizationDenied) as exc:
            error_type = (
                "AUTHORIZATION_REJECTED"
                if isinstance(exc, AuthorizationDenied)
                else "INPUT_SCHEMA_REJECTED"
            )
            self._record_rejection(
                context, audit_target, group_id, error_type, stable_name, arguments
            )
            raise GatewayRejected("stable tool request rejected") from exc
        definition = self.session.scalar(
            sa.select(ToolDefinition).where(
                ToolDefinition.stable_name == stable_name,
                ToolDefinition.schema_version == "1.0.0",
                ToolDefinition.enabled.is_(True),
            )
        )
        if (
            definition is None
            or definition.input_schema != contract.input_schema
            or definition.output_schema != contract.output_schema
        ):
            self._record_rejection(
                context, audit_target, group_id, "CONTRACT_DRIFT", stable_name, arguments
            )
            raise GatewayRejected("stable tool contract is unavailable")
        bindings = list(
            self.session.scalars(
                sa.select(ToolProviderBinding)
                .where(
                    ToolProviderBinding.organization_id == context.organization_id,
                    ToolProviderBinding.target_system_id == target_system_id,
                    ToolProviderBinding.tool_definition_id == definition.id,
                    ToolProviderBinding.enabled.is_(True),
                )
                .order_by(ToolProviderBinding.priority)
            )
        )
        failures: list[str] = []
        for sequence, binding in enumerate(bindings, start=1):
            snapshot = self._catalog_snapshot(context, target_system_id, binding)
            policy_error = self._binding_policy_error(stable_name, binding, snapshot)
            if policy_error is not None:
                self._record_attempt(
                    context,
                    audit_target,
                    definition,
                    binding,
                    snapshot,
                    group_id,
                    sequence,
                    ToolExecutionStatus.REJECTED,
                    policy_error,
                    arguments,
                    None,
                    failures,
                    idempotency_key,
                )
                failures.append(policy_error)
                continue
            client = self.clients.get(binding.provider_type)
            if client is None:
                error_type = "PROVIDER_NOT_CONFIGURED"
                self._record_attempt(
                    context,
                    audit_target,
                    definition,
                    binding,
                    snapshot,
                    group_id,
                    sequence,
                    ToolExecutionStatus.FAILED,
                    error_type,
                    arguments,
                    None,
                    failures,
                    idempotency_key,
                )
                failures.append(error_type)
                continue
            if binding.provider_type is ProviderType.MCP:
                try:
                    observed_hash = cast(CatalogAwareProvider, client).catalog_hash()
                except Exception as exc:
                    error_type = self._provider_error_type(exc)
                    self._record_attempt(
                        context,
                        audit_target,
                        definition,
                        binding,
                        snapshot,
                        group_id,
                        sequence,
                        ToolExecutionStatus.FAILED,
                        error_type,
                        arguments,
                        None,
                        failures,
                        idempotency_key,
                        correlation_id=(
                            exc.correlation_id if isinstance(exc, ProviderFailure) else None
                        ),
                    )
                    failures.append(error_type)
                    continue
                if observed_hash != binding.catalog_hash:
                    error_type = "MCP_CATALOG_DRIFT"
                    self._record_attempt(
                        context,
                        audit_target,
                        definition,
                        binding,
                        snapshot,
                        group_id,
                        sequence,
                        ToolExecutionStatus.REJECTED,
                        error_type,
                        arguments,
                        None,
                        failures,
                        idempotency_key,
                    )
                    failures.append(error_type)
                    continue
            started = datetime.now(UTC)
            try:
                raw = client.invoke(binding.upstream_tool_name, provider_arguments)
                if len(json.dumps(raw, default=str).encode()) > MAX_RESPONSE_BYTES:
                    raise ProviderFailure("RESPONSE_TOO_LARGE", "provider response exceeded limit")
                envelope, payload = validate_output(stable_name, raw)
                if envelope.health_scope is not contract.health_scope:
                    raise ProviderFailure("HEALTH_SCOPE_MISMATCH", "provider health scope mismatch")
                payload = self._authorize_output(
                    context, target_system_id, contract.resource_type, parsed_input, payload
                )
            except Exception as exc:
                error_type = self._provider_error_type(exc)
                self._record_attempt(
                    context,
                    audit_target,
                    definition,
                    binding,
                    snapshot,
                    group_id,
                    sequence,
                    ToolExecutionStatus.FAILED,
                    error_type,
                    arguments,
                    None,
                    failures,
                    idempotency_key,
                    correlation_id=(
                        exc.correlation_id if isinstance(exc, ProviderFailure) else None
                    ),
                    started=started,
                )
                failures.append(error_type)
                continue
            execution = self._record_attempt(
                context,
                audit_target,
                definition,
                binding,
                snapshot,
                group_id,
                sequence,
                ToolExecutionStatus.SUCCEEDED,
                None,
                arguments,
                payload,
                failures,
                idempotency_key,
                correlation_id=envelope.correlation_id,
                started=started,
            )
            return GatewayResult(
                stable_name=stable_name,
                health_scope=contract.health_scope,
                payload=payload,
                provider_type=binding.provider_type,
                execution_id=execution.id,
                degraded_chain=tuple(failures),
            )
        if not bindings:
            self._record_rejection(
                context, audit_target, group_id, "NO_ENABLED_BINDING", stable_name, arguments
            )
            failures.append("NO_ENABLED_BINDING")
        raise ProviderUnavailable(";".join(failures))

    @staticmethod
    def _audit_target(context: AuthorizationContext, requested: uuid.UUID) -> uuid.UUID:
        if requested in context.target_system_ids:
            return requested
        if context.target_system_ids:
            return sorted(context.target_system_ids, key=str)[0]
        raise GatewayRejected("authorized audit scope is required")

    def _authorize_and_transform_input(
        self,
        context: AuthorizationContext,
        target_system_id: uuid.UUID,
        resource_type: str | None,
        arguments: dict[str, Any],
    ) -> dict[str, object]:
        require_scope(context, target_system_id)
        transformed: dict[str, object] = {
            key: value for key, value in arguments.items() if key != "resource_id"
        }
        if resource_type is not None and "resource_id" in arguments:
            try:
                resource_id = uuid.UUID(str(arguments["resource_id"]))
            except ValueError as exc:
                raise ValueError("resource_id must be an OpsPilot UUID") from exc
            require_scope(context, target_system_id, resource_id)
            resource = self.session.scalar(
                sa.select(TargetResource).where(
                    TargetResource.id == resource_id,
                    TargetResource.organization_id == context.organization_id,
                    TargetResource.target_system_id == target_system_id,
                    TargetResource.resource_type == resource_type,
                )
            )
            if resource is None:
                raise AuthorizationDenied("resource mapping is outside the stable tool scope")
            transformed["external_resource_id"] = resource.external_id
        return transformed

    def _authorize_output(
        self,
        context: AuthorizationContext,
        target_system_id: uuid.UUID,
        resource_type: str | None,
        arguments: dict[str, Any],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if resource_type is None:
            return payload
        rows = payload.get("items") or ([payload["item"]] if "item" in payload else [])
        external_ids = {row["external_id"] for row in rows}
        resources = list(
            self.session.scalars(
                sa.select(TargetResource).where(
                    TargetResource.organization_id == context.organization_id,
                    TargetResource.target_system_id == target_system_id,
                    TargetResource.resource_type == resource_type,
                    TargetResource.external_id.in_(external_ids),
                    TargetResource.id.in_(context.resource_ids),
                )
            )
        )
        by_external = {resource.external_id: resource for resource in resources}
        authorized = []
        for row in rows:
            if row["resource_type"] != resource_type:
                raise ProviderFailure("RESOURCE_SCOPE_MISMATCH", "provider resource type mismatch")
            resource = by_external.get(row["external_id"])
            if resource is not None:
                authorized.append({**row, "resource_id": str(resource.id)})
        if "resource_id" in arguments:
            requested = str(arguments["resource_id"])
            if len(authorized) != 1 or authorized[0]["resource_id"] != requested:
                raise ProviderFailure(
                    "RESOURCE_SCOPE_MISMATCH", "provider returned another resource"
                )
            return {"item": authorized[0]}
        return {"items": authorized}

    def _catalog_snapshot(
        self,
        context: AuthorizationContext,
        target_system_id: uuid.UUID,
        binding: ToolProviderBinding,
    ) -> ProviderCatalogSnapshot | None:
        if binding.catalog_hash is None:
            return None
        return self.session.scalar(
            sa.select(ProviderCatalogSnapshot).where(
                ProviderCatalogSnapshot.organization_id == context.organization_id,
                ProviderCatalogSnapshot.target_system_id == target_system_id,
                ProviderCatalogSnapshot.provider_type == binding.provider_type,
                ProviderCatalogSnapshot.endpoint_identifier == binding.endpoint_identifier,
                ProviderCatalogSnapshot.catalog_hash == binding.catalog_hash,
            )
        )

    def _binding_policy_error(
        self,
        stable_name: str,
        binding: ToolProviderBinding,
        snapshot: ProviderCatalogSnapshot | None,
    ) -> str | None:
        contract = STABLE_TOOL_CONTRACTS[stable_name]
        if binding.health_scope is not contract.health_scope:
            return "HEALTH_SCOPE_MISMATCH"
        if binding.provider_type is ProviderType.MCP:
            if not self.mcp_enabled:
                return "MCP_DISABLED_BY_POLICY"
            if binding.upstream_tool_name not in MCP_ALLOWLIST:
                return "MCP_ALLOWLIST_REJECTED"
            if snapshot is None:
                return "MCP_CATALOG_SNAPSHOT_MISSING"
        return None

    @staticmethod
    def _provider_error_type(exc: Exception) -> str:
        if isinstance(exc, ProviderFailure):
            return exc.error_type
        if isinstance(exc, TimeoutError):
            return "TIMEOUT"
        if isinstance(exc, ValueError):
            return "RESPONSE_SCHEMA_INVALID"
        return "PROVIDER_INTERNAL_ERROR"

    def _record_rejection(
        self,
        context: AuthorizationContext,
        audit_target: uuid.UUID,
        group_id: str,
        error_type: str,
        attempted_name: str,
        arguments: dict[str, object],
    ) -> None:
        definition, binding = self._rejection_contract(context, audit_target)
        self._record_attempt(
            context,
            audit_target,
            definition,
            binding,
            None,
            group_id,
            0,
            ToolExecutionStatus.REJECTED,
            error_type,
            {"attempted_stable_name": attempted_name, "arguments": arguments},
            None,
            [],
            None,
        )

    def _rejection_contract(
        self, context: AuthorizationContext, audit_target: uuid.UUID
    ) -> tuple[ToolDefinition, ToolProviderBinding]:
        definition = self.session.scalar(
            sa.select(ToolDefinition).where(ToolDefinition.stable_name == REJECTION_TOOL_NAME)
        )
        if definition is None:
            raise GatewayRejected("gateway rejection audit contract is missing")
        binding = self.session.scalar(
            sa.select(ToolProviderBinding).where(
                ToolProviderBinding.organization_id == context.organization_id,
                ToolProviderBinding.target_system_id == audit_target,
                ToolProviderBinding.tool_definition_id == definition.id,
                ToolProviderBinding.provider_type == ProviderType.INTERNAL,
            )
        )
        if binding is None:
            raise GatewayRejected("gateway rejection audit binding is missing")
        return definition, binding

    def _record_attempt(
        self,
        context: AuthorizationContext,
        audit_target: uuid.UUID,
        definition: ToolDefinition,
        binding: ToolProviderBinding,
        snapshot: ProviderCatalogSnapshot | None,
        group_id: str,
        sequence: int,
        status: ToolExecutionStatus,
        error_type: str | None,
        request: object,
        response: object,
        previous_failures: list[str],
        idempotency_key: str | None,
        *,
        correlation_id: str | None = None,
        started: datetime | None = None,
    ) -> ToolExecution:
        now = datetime.now(UTC)
        execution = ToolExecution(
            organization_id=context.organization_id,
            target_system_id=audit_target,
            tool_definition_id=definition.id,
            provider_binding_id=binding.id,
            provider_catalog_snapshot_id=snapshot.id if snapshot is not None else None,
            stable_tool_name_snapshot=definition.stable_name,
            tool_schema_version_snapshot=definition.schema_version,
            provider_type_snapshot=binding.provider_type,
            binding_key_snapshot=binding.binding_key,
            binding_version_snapshot=binding.version,
            upstream_tool_name_snapshot=binding.upstream_tool_name,
            request_correlation_id=group_id,
            fallback_reason=";".join(previous_failures) or None,
            authorization_scope={
                "actor_user_id": str(context.actor_user_id),
                "organization_id": str(context.organization_id),
                "target_system_id": str(audit_target),
                "resource_ids": sorted(str(item) for item in context.resource_ids),
            },
            request_summary=_safe(request),
            response_summary=_safe(response) if response is not None else None,
            error_type=error_type,
            status=status,
            started_at=started or now,
            finished_at=now,
            retry_count=sequence - 1 if sequence else 0,
            idempotency_key=(f"{idempotency_key}:{sequence}" if idempotency_key else None),
        )
        self.session.add(execution)
        self.session.flush()
        payload = {
            "status": status,
            "error_type": error_type,
            "provider": binding.provider_type,
            "binding": binding.binding_key,
            "sequence": sequence,
            "previous_failures": previous_failures,
        }
        self.session.add(
            AuditEvent(
                organization_id=context.organization_id,
                target_system_id=audit_target,
                tool_execution_id=execution.id,
                actor_type=AuditActorType.USER,
                actor_ref=str(context.actor_user_id),
                event_type="TOOL_ATTEMPT_RECORDED",
                entity_type="ToolExecution",
                entity_id=str(execution.id),
                correlation_id=correlation_id or group_id,
                payload_summary=_safe(payload),
                payload_hash=_digest(payload),
                occurred_at=now,
            )
        )
        self.session.flush()
        return execution
