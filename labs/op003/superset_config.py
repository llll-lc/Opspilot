"""OP-003 isolated Superset configuration; generated secrets stay in .runtime."""

import os
from datetime import timedelta
from typing import ClassVar

from celery.schedules import crontab

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]
SQLALCHEMY_DATABASE_URI = os.environ["SUPERSET_DATABASE_URI"]
WTF_CSRF_ENABLED = True
SCARF_ANALYTICS = False

# The native server validates a local lab JWT and resolves its subject to a
# Superset user. These settings never reach an OpsPilot application process.
MCP_AUTH_ENABLED = True
MCP_JWT_SECRET = os.environ["OP003_MCP_JWT_SECRET"]
MCP_JWT_ALGORITHM = "HS256"
MCP_REQUIRED_SCOPES = ["superset:read"]
MCP_RBAC_ENABLED = True
MCP_TOOL_SEARCH_CONFIG = {"enabled": False}
MCP_RESPONSE_SIZE_CONFIG = {
    "enabled": True,
    "token_limit": int(os.getenv("OP003_MCP_RESPONSE_TOKEN_LIMIT", "256")),
    "warn_threshold_pct": 80,
    "excluded_tools": ["health_check"],
}

CACHE_CONFIG = {"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300}
DATA_CACHE_CONFIG = CACHE_CONFIG

if os.getenv("OP003_REPORTS_ENABLED", "false").lower() == "true":
    FEATURE_FLAGS = {"ALERT_REPORTS": True}

    class CeleryConfig:
        broker_url = "redis://redis:6379/0"
        result_backend = "redis://redis:6379/0"
        imports = ("superset.sql_lab", "superset.tasks.scheduler")
        worker_prefetch_multiplier = 1
        task_acks_late = True
        beat_schedule: ClassVar[dict[str, dict[str, object]]] = {
            "reports.scheduler": {
                "task": "reports.scheduler",
                "schedule": crontab(minute="*", hour="*"),
            }
        }
        task_soft_time_limit = int(timedelta(minutes=5).total_seconds())
        task_time_limit = int(timedelta(minutes=6).total_seconds())

    CELERY_CONFIG = CeleryConfig
