"""Versioned stable-tool contracts and deterministic schema validation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from opspilot.db.enums import HealthScope


class EmptyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    resource_id: str = Field(min_length=1, max_length=200)


class RuntimeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component: Literal["worker", "beat", "redis"]


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"]
    component: str | None = Field(default=None, max_length=50)
    detail: str | None = Field(default=None, max_length=500)


class InstanceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    product: str = Field(max_length=100)
    version: str | None = Field(default=None, max_length=100)


class ResourceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    external_id: str = Field(min_length=1, max_length=200)
    resource_id: str | None = None
    name: str = Field(min_length=1, max_length=300)
    resource_type: str = Field(min_length=1, max_length=50)


class ResourceListData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[ResourceItem] = Field(max_length=50)


class ResourceData(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    item: ResourceItem


class ProviderEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    health_scope: HealthScope
    data: dict[str, Any]
    correlation_id: str | None = Field(default=None, max_length=200)


@dataclass(frozen=True)
class StableToolContract:
    health_scope: HealthScope
    input_model: type[BaseModel]
    output_adapter: TypeAdapter[Any]
    resource_type: str | None
    provider_bindings: tuple[tuple[str, str, int], ...]

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    @property
    def output_schema(self) -> dict[str, Any]:
        return self.output_adapter.json_schema()


def _contract(
    scope: HealthScope,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    resource_type: str | None,
    *bindings: tuple[str, str, int],
) -> StableToolContract:
    return StableToolContract(
        scope, input_model, TypeAdapter(output_model), resource_type, bindings
    )


STABLE_TOOL_CONTRACTS: dict[str, StableToolContract] = {
    "check_target_connector_health": _contract(
        HealthScope.CONNECTOR, EmptyInput, HealthData, None, ("MCP", "health_check", 10)
    ),
    "get_target_application_health": _contract(
        HealthScope.APPLICATION, EmptyInput, HealthData, None, ("REST", "application_health", 10)
    ),
    "get_target_runtime_health": _contract(
        HealthScope.RUNTIME_COMPONENT,
        RuntimeInput,
        HealthData,
        None,
        ("PROBE", "runtime_health", 10),
    ),
    "get_target_instance_summary": _contract(
        HealthScope.APPLICATION,
        EmptyInput,
        InstanceData,
        None,
        ("MCP", "get_instance_info", 10),
        ("REST", "instance_summary", 20),
    ),
}

for _plural, _singular, _resource_type, _mcp_list, _mcp_get in (
    ("databases", "database", "DATABASE", "list_databases", "get_database_info"),
    ("datasets", "dataset", "DATASET", "list_datasets", "get_dataset_info"),
    ("charts", "chart", "CHART", "list_charts", "get_chart_info"),
    ("dashboards", "dashboard", "DASHBOARD", "list_dashboards", "get_dashboard_info"),
):
    _list_bindings: tuple[tuple[str, str, int], ...] = (("REST", f"list_{_plural}", 20),)
    _get_bindings: tuple[tuple[str, str, int], ...] = (("REST", f"get_{_singular}", 20),)
    if _mcp_list:
        _list_bindings = (("MCP", _mcp_list, 10), *_list_bindings)
        _get_bindings = (("MCP", _mcp_get, 10), *_get_bindings)
    STABLE_TOOL_CONTRACTS[f"list_target_{_plural}"] = _contract(
        HealthScope.APPLICATION,
        EmptyInput,
        ResourceListData,
        _resource_type,
        *_list_bindings,
    )
    STABLE_TOOL_CONTRACTS[f"get_target_{_singular}_info"] = _contract(
        HealthScope.APPLICATION,
        ResourceInput,
        ResourceData,
        _resource_type,
        *_get_bindings,
    )

MCP_ALLOWLIST = frozenset(
    binding[1]
    for contract in STABLE_TOOL_CONTRACTS.values()
    for binding in contract.provider_bindings
    if binding[0] == "MCP"
) | {"get_schema"}


def mcp_catalog_hash(tool_names: list[str]) -> str:
    """Hash the sorted observed name set; descriptions remain stored but never authorize."""
    return hashlib.sha256("\n".join(sorted(tool_names)).encode()).hexdigest()


def validate_input(stable_name: str, arguments: dict[str, object]) -> dict[str, Any]:
    contract = STABLE_TOOL_CONTRACTS[stable_name]
    try:
        return contract.input_model.model_validate(arguments).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError("stable tool input schema rejected the request") from exc


def validate_output(stable_name: str, response: object) -> tuple[ProviderEnvelope, dict[str, Any]]:
    try:
        envelope = ProviderEnvelope.model_validate(response)
        data = STABLE_TOOL_CONTRACTS[stable_name].output_adapter.validate_python(envelope.data)
    except ValidationError as exc:
        raise ValueError("stable tool output schema rejected the provider response") from exc
    return envelope, data.model_dump(mode="json")
