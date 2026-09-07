"""Run redacted, read-only OP-006 Provider checks against an approved Superset target."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from opspilot.providers.mcp.client import SupersetMcpProvider
from opspilot.providers.runtime import (
    ProviderFailure,
    RuntimeProbeProvider,
    SupersetRestProvider,
    UrllibRestTransport,
)


def summarize(result: dict[str, object]) -> dict[str, object]:
    data = result.get("data")
    summary: dict[str, object] = {"health_scope": result.get("health_scope")}
    if isinstance(data, dict):
        if isinstance(data.get("items"), list):
            summary["item_count"] = len(data["items"])
        if isinstance(data.get("status"), str):
            summary["status"] = data["status"]
        if isinstance(data.get("component"), str):
            summary["component"] = data["component"]
        if isinstance(data.get("product"), str):
            summary["product"] = data["product"]
        if isinstance(data.get("version"), str):
            summary["version"] = data["version"]
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8088")
    parser.add_argument("--mcp-url")
    parser.add_argument("--expect-mcp-error")
    args = parser.parse_args()
    access_token = os.getenv("OP006_SUPERSET_ACCESS_TOKEN")
    rest = SupersetRestProvider(UrllibRestTransport(args.base_url, access_token))
    results: dict[str, Any] = {
        "application_health": summarize(rest.invoke("application_health", {})),
        "instance_summary": summarize(rest.invoke("instance_summary", {})),
    }
    if access_token:
        for resource in ("databases", "datasets", "charts", "dashboards"):
            results[f"list_{resource}"] = summarize(rest.invoke(f"list_{resource}", {}))
    else:
        results["authenticated_metadata"] = "SKIPPED_NO_TOKEN"
    probe = RuntimeProbeProvider({})
    for component in ("worker", "beat", "redis"):
        results[f"probe_{component}"] = summarize(
            probe.invoke("runtime_health", {"component": component})
        )
    results["mcp_policy_default"] = "DISABLED"
    if args.mcp_url:
        mcp_token = os.getenv("OP006_MCP_BEARER_TOKEN")
        if not mcp_token:
            raise RuntimeError("OP006_MCP_BEARER_TOKEN is required with --mcp-url")
        try:
            SupersetMcpProvider(args.mcp_url, mcp_token).catalog_hash()
            results["mcp_catalog"] = "ACCEPTED"
        except ProviderFailure as exc:
            results["mcp_catalog"] = {"status": "REJECTED", "error_type": exc.error_type}
            if args.expect_mcp_error != exc.error_type:
                raise
        else:
            if args.expect_mcp_error:
                raise RuntimeError("MCP catalog unexpectedly passed the required rejection")
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
