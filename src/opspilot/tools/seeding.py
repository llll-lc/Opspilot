"""Repeatable append-only seeds for stable tools and reviewed Provider bindings."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from opspilot.db.enums import HealthScope, ProviderType, ToolRiskLevel
from opspilot.db.models import ProviderCatalogSnapshot, ToolDefinition, ToolProviderBinding
from opspilot.tools.contracts import MCP_ALLOWLIST, STABLE_TOOL_CONTRACTS, mcp_catalog_hash

REJECTION_TOOL_NAME = "gateway_rejected_call"


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _definition(
    session: Session,
    *,
    stable_name: str,
    semantics: str,
    risk: ToolRiskLevel,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    enabled: bool,
) -> ToolDefinition:
    existing = session.scalar(
        sa.select(ToolDefinition).where(
            ToolDefinition.stable_name == stable_name,
            ToolDefinition.schema_version == "1.0.0",
        )
    )
    contract_hash = canonical_hash(
        {
            "stable_name": stable_name,
            "input_schema": input_schema,
            "output_schema": output_schema,
            "policy": "op006-v1",
        }
    )
    if existing is not None:
        if existing.contract_hash != contract_hash:
            raise ValueError(f"stable tool contract drift: {stable_name}")
        return existing
    created = ToolDefinition(
        stable_name=stable_name,
        schema_version="1.0.0",
        contract_hash=contract_hash,
        business_semantics=semantics,
        risk_level=risk,
        input_schema=input_schema,
        output_schema=output_schema,
        authorization_policy_version="op006-v1",
        enabled=enabled,
    )
    session.add(created)
    session.flush()
    return created


def record_mcp_catalog(
    session: Session,
    organization_id: uuid.UUID,
    target_system_id: uuid.UUID,
    tools: list[dict[str, object]],
    *,
    correlation_id: str | None = None,
) -> ProviderCatalogSnapshot:
    """Persist the complete untrusted observation; it never grants a discovered tool."""
    names = [str(item["name"]) for item in tools if isinstance(item.get("name"), str)]
    catalog_hash = mcp_catalog_hash(names)
    existing = session.scalar(
        sa.select(ProviderCatalogSnapshot).where(
            ProviderCatalogSnapshot.organization_id == organization_id,
            ProviderCatalogSnapshot.target_system_id == target_system_id,
            ProviderCatalogSnapshot.provider_type == ProviderType.MCP,
            ProviderCatalogSnapshot.endpoint_identifier == "superset-mcp-6.1.0",
            ProviderCatalogSnapshot.catalog_hash == catalog_hash,
        )
    )
    if existing is not None:
        return existing
    snapshot = ProviderCatalogSnapshot(
        organization_id=organization_id,
        target_system_id=target_system_id,
        provider_type=ProviderType.MCP,
        endpoint_identifier="superset-mcp-6.1.0",
        catalog_hash=catalog_hash,
        observed_tools=tools,
        observed_at=datetime.now(UTC),
        correlation_id=correlation_id,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def seed_stable_tools(
    session: Session,
    organization_id: uuid.UUID,
    target_system_id: uuid.UUID,
    *,
    reviewed_mcp_catalog: ProviderCatalogSnapshot | None = None,
) -> None:
    """Seed stable contracts plus explicit REST/Probe and reviewed MCP bindings."""
    rejection = _definition(
        session,
        stable_name=REJECTION_TOOL_NAME,
        semantics="Internal audit sink for rejected requests; never Agent-visible",
        risk=ToolRiskLevel.FORBIDDEN,
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        enabled=False,
    )
    _binding(
        session,
        organization_id,
        target_system_id,
        rejection,
        ProviderType.INTERNAL,
        "gateway_rejection",
        0,
        HealthScope.CONNECTOR,
        None,
        enabled=False,
    )
    observed_names = (
        {item.get("name") for item in reviewed_mcp_catalog.observed_tools if isinstance(item, dict)}
        if reviewed_mcp_catalog is not None
        else set()
    )
    for stable_name, contract in STABLE_TOOL_CONTRACTS.items():
        definition = _definition(
            session,
            stable_name=stable_name,
            semantics=f"Read-only {contract.health_scope.value} observation",
            risk=ToolRiskLevel.READ_ONLY,
            input_schema=contract.input_schema,
            output_schema=contract.output_schema,
            enabled=True,
        )
        for provider_name, upstream_name, priority in contract.provider_bindings:
            provider_type = ProviderType(provider_name)
            if provider_type is ProviderType.MCP:
                if upstream_name not in MCP_ALLOWLIST or upstream_name not in observed_names:
                    continue
                assert reviewed_mcp_catalog is not None
                catalog_hash = reviewed_mcp_catalog.catalog_hash
            else:
                catalog_hash = None
            _binding(
                session,
                organization_id,
                target_system_id,
                definition,
                provider_type,
                upstream_name,
                priority,
                contract.health_scope,
                catalog_hash,
                enabled=True,
            )


def _binding(
    session: Session,
    organization_id: uuid.UUID,
    target_system_id: uuid.UUID,
    definition: ToolDefinition,
    provider_type: ProviderType,
    upstream_name: str,
    priority: int,
    health_scope: HealthScope,
    catalog_hash: str | None,
    *,
    enabled: bool,
) -> ToolProviderBinding:
    key = f"{provider_type.value.lower()}-{definition.stable_name}-v1"
    existing = session.scalar(
        sa.select(ToolProviderBinding).where(
            ToolProviderBinding.organization_id == organization_id,
            ToolProviderBinding.target_system_id == target_system_id,
            ToolProviderBinding.tool_definition_id == definition.id,
            ToolProviderBinding.binding_key == key,
            ToolProviderBinding.version == 1,
        )
    )
    binding_hash = canonical_hash(
        {
            "stable_name": definition.stable_name,
            "provider": provider_type,
            "upstream": upstream_name,
            "health_scope": health_scope,
            "catalog_hash": catalog_hash,
        }
    )
    if existing is not None:
        if existing.binding_hash != binding_hash:
            raise ValueError(f"provider binding drift: {key}")
        return existing
    created = ToolProviderBinding(
        organization_id=organization_id,
        target_system_id=target_system_id,
        tool_definition_id=definition.id,
        binding_key=key,
        version=1,
        binding_hash=binding_hash,
        provider_type=provider_type,
        priority=priority,
        endpoint_identifier=(
            "superset-mcp-6.1.0"
            if provider_type is ProviderType.MCP
            else "opspilot-internal"
            if provider_type is ProviderType.INTERNAL
            else "opspilot-runtime-probe-v1"
            if provider_type is ProviderType.PROBE
            else "superset-readonly-v1"
        ),
        upstream_tool_name=upstream_name,
        catalog_hash=catalog_hash,
        input_transform_version="op006-v1",
        output_transform_version="op006-v1",
        health_scope=health_scope,
        enabled=enabled,
    )
    session.add(created)
    session.flush()
    return created
